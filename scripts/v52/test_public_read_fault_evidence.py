"""Exact installation witness and fault declaration boundaries; real bytes run in the process gate."""
import base64
import copy
from pathlib import Path
import unittest
from unittest.mock import patch
from . import public_reads_evidence as e, public_read_fault_evidence as f, public_read_fault_harness as h


class ReadFaultEvidenceTest(unittest.TestCase):
    def test_genesis_has_no_terminal_proof(self):
        self.assertEqual((0,None),e.publication_identity(dict(anchors=[],terminalProof=None)))

    def files(self):return [dict(name=n,bytes=base64.b64encode(b'fixture').decode()) for n in
                          ('current.gsr','generation.gsr','snapshot.gsr','accepted.gsr','proofs.gsr')]

    def test_installed_source_rejects_missing_duplicate_or_unexpected_files_before_reading(self):
        for files in (self.files()[:-1],self.files()+self.files()[:1],
                      [dict(name='../outside',bytes='')]+self.files()[1:],
                      [self.files()[0]]+self.files()[:-1],{}):
            with self.subTest(files=files),patch.object(e.recovery,'source') as source:
                with self.assertRaises(ValueError):e.installed_source(files,{}, {},'node-1')
                source.assert_not_called()

    def test_installed_source_binds_node_and_verified_selected_prefix(self):
        snapshot=dict(anchors=[dict(entryDigest='chosen')],terminalProof=base64.b64encode(b'proof').decode(),application='image')
        source=dict(seal=dict(node='node-1',selectedDigest='selected'),snapshot=snapshot)
        with patch.object(e.recovery,'source',return_value=source):
            self.assertEqual((1,e.digest(b'proof')),e.installed_source(self.files(),{}, {'selected':snapshot},'node-1'))
            with self.assertRaisesRegex(ValueError,'voter'):e.installed_source(self.files(),{}, {'selected':snapshot},'node-2')
            with self.assertRaisesRegex(ValueError,'verified selection'):e.installed_source(self.files(),{}, {},'node-1')
            different=dict(snapshot,application='other')
            with self.assertRaisesRegex(ValueError,'same-cut application'):e.installed_source(self.files(),{}, {'selected':different},'node-1')

    def test_crashed_response_cannot_be_reclassified_as_success(self):
        fault=dict(scenario='capture-kill',node='node-1',lostOp='lost')
        with patch.object(e,'read',return_value=fault):
            with self.assertRaisesRegex(ValueError,'lost read response'):
                f.schedule(Path('/unused'),'capture-kill',{'node-1':[]},[dict(opId='lost',outcome='SUCCESS')],[])

    def test_unknown_fault_never_qualifies(self):
        with patch.object(e,'read',return_value=dict(scenario='invented',node='node-1')):
            with self.assertRaisesRegex(ValueError,'unknown public read fault'):
                f.schedule(Path('/unused'),'invented',{'node-1':[]},[],[])


class IsolationWitnessTest(unittest.TestCase):
    def row(self,order=2,**values):
        return dict(dict(node='node-1',pid=100,generation=1,order=order,event='NETWORK_DROP',
                         barrier='BEFORE_REQUEST_WRITE',request=base64.b64encode(b'wire').decode()),**values)

    def test_only_real_partition_barriers_for_the_isolated_peer_match(self):
        for sender,recipient,barrier,expected in (
                ('node-1','node-3','BEFORE_REQUEST_WRITE',True),
                ('node-3','node-1','AFTER_RESPONSE_READ',True),
                ('node-1','node-2','BEFORE_REQUEST_WRITE',False),
                ('node-3','node-3','BEFORE_REQUEST_WRITE',False),
                ('node-1','node-3','BEFORE_RESPONSE_WRITE',False)):
            with self.subTest(sender=sender,recipient=recipient,barrier=barrier),patch.object(
                    e.physical.f,'wire',return_value=dict(sender=sender,recipient=recipient)):
                self.assertEqual(expected,f.partition_drop(self.row(node=sender,barrier=barrier),'node-3',{}))
        with patch.object(e.physical.f,'wire',return_value=dict(sender='node-1',recipient='node-3')):
            self.assertFalse(f.partition_drop(self.row(node='node-2'),'node-3',{}))
        with patch.object(e.physical.f,'wire') as wire:
            self.assertFalse(f.partition_drop(self.row(event='RECEIVED'),'node-3',{}));wire.assert_not_called()

    def test_waits_through_no_traffic_old_drops_and_other_generations_before_new_drop(self):
        old=self.row(order=5);fresh=self.row(order=7);other=self.row(order=6,generation=2)
        unrelated=self.row(order=6,request=base64.b64encode(b'other-peer').decode())
        polls=iter(([old],[old],[old,other,unrelated],[old,other,unrelated,fresh]))
        def decoded(raw,manifest):return dict(sender='node-1',recipient='node-2' if raw==b'other-peer' else 'node-3')
        with patch.object(h.public_trace,'live_rows',side_effect=lambda *_:next(polls)),patch.object(
                h.faults,'partition') as partition,patch.object(h.faults.time,'sleep') as sleep,patch.object(
                e.physical.f,'wire',side_effect=decoded):
            result=h.isolate_observed(Path('/unused'),'node-3',['node-1'],{})
        partition.assert_called_once_with(Path('/unused'),'node-3') # the wait never heals
        self.assertEqual(2,sleep.call_count)
        self.assertEqual(dict(node='node-1',pid=100,generation=1,order=7),result['witness'])
        self.assertEqual(5,result['after']['node-1']['order'])

    def test_missing_transport_traffic_fails_at_existing_bound_without_healing(self):
        with patch.object(h.public_trace,'live_rows',return_value=[self.row(event='RECEIVED')]),patch.object(
                h.faults,'partition') as partition,patch.object(h.faults.time,'monotonic',side_effect=[0,0,41]),patch.object(
                h.faults.time,'sleep'):
            with self.assertRaisesRegex(ValueError,'partition not observed.*40s'):
                h.isolate_observed(Path('/unused'),'node-3',['node-1'],{})
        partition.assert_called_once_with(Path('/unused'),'node-3')

    def test_retained_witness_requires_exact_new_trace_and_ordered_observation(self):
        before=self.row(order=1,event='RECEIVED');drop=self.row()
        traces={'node-1':[before,drop]}
        isolation=dict(after={'node-1':dict(pid=100,generation=1,order=1)},
                       witness=dict(node='node-1',pid=100,generation=1,order=2),
                       installedNanos=10,observedNanos=20,healedNanos=30)
        with patch.object(e.physical.f,'wire',return_value=dict(sender='node-1',recipient='node-3')):
            f.check_partition_witness(traces,'node-3',{},isolation)
            for change in ('missing-drop','old-drop','other-generation','wrong-owner','missing-marker','early-heal'):
                rows=copy.deepcopy(traces);details=copy.deepcopy(isolation)
                if change=='missing-drop':rows['node-1'].pop()
                elif change=='old-drop':details['after']['node-1']['order']=2
                elif change=='other-generation':rows['node-1'][1]['generation']=2;details['witness']['generation']=2
                elif change=='wrong-owner':rows['node-1'][1]['node']='node-2'
                elif change=='missing-marker':details['after']['node-1']['order']=0
                else:details['healedNanos']=15
                with self.subTest(change=change),self.assertRaisesRegex(ValueError,'partition'):
                    f.check_partition_witness(rows,'node-3',{},details)


if __name__=='__main__':unittest.main()
