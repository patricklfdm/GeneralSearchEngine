import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import pending_drain_evidence as r
from . import pending_drain_negatives as n
from .test_resource_transitions import charge,trace,row


def fixture(listener='checkpoint',mode='callback'):
    base=charge('SOURCE','original-fixture',100);pending=charge('LEARNER','retained-pending',200);control=charge('CONTROL','listener',50)
    value=trace([row('START'),row('RESERVE',added=[base]),row('RESERVE',added=[pending]),row('RESERVE',added=[control]),
                 row('RELEASE',[control]),row('RELEASE',[pending]),row('RELEASE',[base])])
    history=dict(schema='gse-v53-pending-drain-v1',listener=listener,mode=mode,status='PASS',completeMembershipHistory=False,
                 rows=[dict(event=e,sequence=s,usage={},error=r.error(listener,mode) if e=='OWNER_CLOSE_FAILED' else '',
                            interrupted=mode=='interrupt' and e in ('OWNER_CLOSE_BEGIN','OWNER_CLOSE_FAILED'))
                       for e,s in zip(r.EVENTS,[1,3,3,4,4,5,6])],
                 inventories={k:[dict(path='retained/source.gsr',sha256='a'*64)] for k in ('before','afterFailure','afterSuccess')})
    n.recount(value,history);return value,history


class PendingDrainTest(unittest.TestCase):
    def test_original_retained_storage_survives_failure_and_returns_to_baseline(self):
        for listener in ('checkpoint','head'):
            for mode in ('callback','interrupt'):
                data=fixture(listener,mode);before=copy.deepcopy(data);result=r.replay(*data)
                self.assertEqual(data,before);self.assertTrue(result['failedCloseStorageContinuityQualified'])
                self.assertEqual(1,result['retainedStorageLeases'])
                for key in ('physicalStorageQualified','wholeRuntimeResourcesQualified','phase3Complete'):self.assertFalse(result[key])

    def test_every_declared_negative_fails_its_own_obligation(self):
        for listener in ('checkpoint','head'):
            for mode in ('callback','interrupt'):
                results=n.replay(fixture(listener,mode));self.assertEqual(list(n.NEGATIVES),[v['case'] for v in results])

    def test_release_reacquire_gap_is_rejected_with_correct_point_totals(self):
        data=fixture();n.mutate(data,'release-reacquire');r.t.replay(data[0])
        for point in data[1]['rows']:self.assertEqual(point['usage'],data[0]['changes'][point['sequence']]['usage'])
        with self.assertRaisesRegex(ValueError,'storage survives failed close'):r.replay(*data)

    def test_baseline_cannot_be_replaced_between_observations(self):
        data=fixture();n.mutate(data,'baseline-release-reacquire');r.t.replay(data[0])
        with self.assertRaisesRegex(ValueError,'continuous baseline custody'):r.replay(*data)

    def test_interrupted_close_preserves_interrupt_even_when_resources_are_safe(self):
        for event in ('OWNER_CLOSE_BEGIN','OWNER_CLOSE_FAILED'):
            data=fixture(mode='interrupt');next(v for v in data[1]['rows'] if v['event']==event)['interrupted']=False
            with self.assertRaisesRegex(ValueError,'interrupt preserved'):r.replay(*data)

    def test_checkpoint_and_progress_failures_cannot_be_exchanged(self):
        data=fixture();data[1]['rows'][3]['error']=r.error('head','callback')
        with self.assertRaisesRegex(ValueError,'exact failed close outcome'):r.replay(*data)

    def test_original_failure_is_not_counted_as_successful_negative_rejection(self):
        data=fixture();data[1]['status']='FAIL'
        with patch.object(n,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'complete conditional history'):n.replay(data)
            mutate.assert_not_called()

    def test_extra_or_missing_call_rows_cannot_qualify(self):
        for extra in (True,False):
            data=fixture()
            if extra:data[1]['rows'].append(copy.deepcopy(data[1]['rows'][-1]))
            else:data[1]['rows'].pop()
            with self.assertRaisesRegex(ValueError,'exact call sequence'):r.replay(*data)

    def test_file_rows_must_be_relative_unique_hash_observations(self):
        for path in ('/tmp/authority','../authority','a//b','a/./b'):
            data=fixture()
            for values in data[1]['inventories'].values():values[0]['path']=path
            with self.assertRaisesRegex(ValueError,'file observations'):r.replay(*data)
        data=fixture()
        for values in data[1]['inventories'].values():values.append(copy.deepcopy(values[0]))
        with self.assertRaisesRegex(ValueError,'unchanged retained files'):r.replay(*data)

    def test_portable_exact_inventory_and_canonical_bytes(self):
        data=fixture()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name,value in zip(('resources.json','history.json'),data):
                (root/name).write_bytes(r.t.collection.snapshot.f.canonical(value))
            self.assertEqual('PASS',r.validate(root)['status'])
            self.assertEqual(len(n.NEGATIVES),len(n.qualify(root)['negatives']))
            (root/'extra').write_text('x')
            with self.assertRaisesRegex(ValueError,'exact original inventory'):r.load(root)
            (root/'extra').unlink();(root/'history.json').write_bytes((root/'history.json').read_bytes()+b'\n')
            with self.assertRaisesRegex(ValueError,'noncanonical JSON'):r.load(root)

    def test_final_zero_counts_cannot_replace_complete_recorder(self):
        for field in ('truncated','failed'):
            data=fixture();data[0][field]=True
            with self.assertRaisesRegex(ValueError,'incomplete observation'):r.replay(*data)


if __name__=='__main__':unittest.main()
