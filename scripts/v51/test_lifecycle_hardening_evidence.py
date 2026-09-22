"""Witnesses reject false overlap, leaked counters and unrelated disk corruption."""
import base64
import copy
from pathlib import Path
import tempfile
import unittest
from . import lifecycle_hardening_evidence as e, storage_inspector as s, storage_fixture as fixture


class LifecycleHardeningEvidenceTest(unittest.TestCase):
    def sample(self):
        return dict(admissionAvailable=4, orderedQueue=0, deadlinesQueue=0, inputsQueue=0, inputsRemaining=32,
                    completionsQueue=0, completionsRemaining=16, networkQueue=0, networkActive=0,
                    appQueue=0, appActive=0, clientsQueue=0, clientsActive=0)

    def test_bounded_samples_and_quiescent_reuse(self):
        e.bounded_sample(self.sample(), drained=True)
        e.bounded_sample(dict(self.sample(), admissionAvailable=0, orderedQueue=3, deadlinesQueue=3, appActive=1))

    def test_missing_noninteger_negative_or_overbound_counter_rejected(self):
        for field, value in (('inputsQueue',33),('completionsQueue',17),('appQueue',5),('deadlinesQueue',5),
                             ('admissionAvailable',5),('orderedQueue',-1),('clientsActive',True)):
            with self.subTest(field=field), self.assertRaises(ValueError): e.bounded_sample(dict(self.sample(), **{field:value}))
        value=self.sample(); del value['inputsQueue']
        with self.assertRaises(ValueError): e.bounded_sample(value)

    def test_expired_work_must_release_both_timer_and_admission(self):
        for change in (dict(admissionAvailable=3),dict(orderedQueue=1),dict(deadlinesQueue=1)):
            with self.subTest(change=change), self.assertRaises(ValueError): e.bounded_sample(dict(self.sample(),**change),drained=True)

    def order(self):
        return [dict(pid=10,generation=1,order=i,id=4,index=10) for i in range(1,8)]

    def test_install_and_queue_overlap_but_actual_rebuild_waits_for_read(self): e.rebuild_order(*self.order())

    def test_reconstruction_cannot_start_before_view_release(self):
        values=self.order(); values[5]['order']=4
        with self.assertRaises(ValueError): e.rebuild_order(*values)

    def test_snapshot_installed_only_after_read_does_not_qualify_overlap(self):
        values=self.order(); values[1]['order']=8
        with self.assertRaises(ValueError): e.rebuild_order(*values)

    def test_borrowed_process_generation_or_rebuild_is_rejected(self):
        for change in (dict(pid=11),dict(generation=2),dict(id=5),dict(index=11)):
            values=self.order(); values[-1].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError): e.rebuild_order(*values)

    def torn(self,kind='ACCEPT'):
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); root=Path(temp.name); frames=fixture.create(root)
        directory=root/'node-1'; name='accepted.gsr' if kind=='ACCEPT' else 'proofs.gsr'; path=directory/name
        before=path.read_bytes(); after=before+frames[kind][:64]; path.write_bytes(after)
        witness=dict(kind=kind,path=name,before=base64.b64encode(before).decode(),after=base64.b64encode(after).decode())
        return directory,witness,frames

    def test_torn_accept_and_proof_remain_rejected_authority(self):
        for kind in ('ACCEPT','PROOF'):
            directory,witness,_=self.torn(kind)
            self.assertEqual('QUARANTINED',s.torn_append(directory,witness)['status'])
            with self.assertRaises(ValueError): s.inspect(directory)

    def test_full_record_is_not_a_partial_write(self):
        directory,witness,frames=self.torn(); after=s.raw(witness['before'])+frames['ACCEPT']; (directory/witness['path']).write_bytes(after)
        witness['after']=base64.b64encode(after).decode()
        with self.assertRaises(ValueError): s.torn_append(directory,witness)

    def test_missing_changed_or_repaired_tail_cannot_be_quarantined_witness(self):
        directory,witness,_=self.torn()
        for data in (s.raw(witness['before']),s.raw(witness['after'])[:-1],s.raw(witness['after'])+b'x'):
            (directory/witness['path']).write_bytes(data)
            with self.subTest(size=len(data)), self.assertRaises(ValueError): s.torn_append(directory,witness)

    def test_wrong_kind_path_or_corrupt_prefix_does_not_qualify(self):
        directory,witness,_=self.torn()
        for change in (dict(kind='PROOF'),dict(path='../accepted.gsr'),dict(before=base64.b64encode(b'x').decode())):
            with self.subTest(change=change), self.assertRaises(ValueError): s.torn_append(directory,dict(witness,**change))
        altered=copy.deepcopy(witness); data=bytearray(s.raw(altered['before'])); data[-1]^=1
        altered['before']=base64.b64encode(data).decode(); changed=bytes(data)+s.raw(altered['after'])[-64:]
        altered['after']=base64.b64encode(changed).decode(); (directory/altered['path']).write_bytes(changed)
        with self.assertRaises(ValueError): s.torn_append(directory,altered)


if __name__=='__main__': unittest.main()
