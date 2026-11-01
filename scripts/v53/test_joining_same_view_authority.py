"""Conditional timeline/discovery/composition boundaries; native evidence is separate."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch,Mock

from . import joining_same_view_authority as a
from . import test_joining_maintenance_evidence as maintenance_fixture
from . import test_joining_peer_evidence as peer_fixture


class JoiningSameViewAuthorityTest(unittest.TestCase):
    def timeline(self,change=None,explicit=True):
        cut=dict(index=11);old=dict(cut=dict(index=0),sources=[dict(voter=n) for n in ('node-1','node-2')])
        recovery=dict(cut=cut,ballot=dict(proposer='node-4'),sources=[dict(voter=n) for n in ('node-1','node-4')])
        model=SimpleNamespace(root='root',joining='node-4',phases=[dict(SELECTED=b'old',CERTIFICATE=b'certificate')]*11,
                              states=[{}]*11+[dict(cut=cut)])
        events=[]
        for node in ('node-1','node-2'):
            for event in ('INSTALL_SELECTOR_RENAMED','INSTALL_BEFORE_RETURN'):
                events.append(dict(node=node,event=event))
        events.append(dict(node='node-4',scope='initial-owner',event='CURRENT_DIRECTORY_FORCED'))
        for node,returned in [('node-4','ADOPTION_INSTALL_BEFORE_RETURN'),('node-1','INSTALL_BEFORE_RETURN'),('node-4','INSTALL_BEFORE_RETURN')]:
            events.extend([dict(node=node,event='INSTALL_SELECTOR_RENAMED'),dict(node=node,event=returned)])
        events.append(dict(event='end'))
        if change=='omitted':events[6]['event']='OMITTED'
        if change=='early':events[5],events[6]=events[6],events[5]
        if change=='cut':recovery['cut']=dict(index=10)
        def decode(raw,*args):
            if raw==b'old':return old
            if raw==b'recovery':return recovery
            if raw==b'certificate':return dict(proofs=[])
            return dict(identity=dict(node=raw.decode()))
        def inventory(path):
            node='node-4' if path.name=='replica' else path.name
            return {'node.gsr':node.encode(),'g/generation.gsr':b'original'}
        with patch.object(a.f,'decode',side_effect=decode),patch.object(a.disk,'inventory',side_effect=inventory), \
                patch.object(a.disk,'current',return_value=('g/',{},{})):
            return a.e.generation_windows(Path('/original'),events,model,**(dict(recovery=b'recovery') if explicit else {})),events

    def test_adoption_and_recovery_have_distinct_original_lifetimes(self):
        windows,events=self.timeline();own=[v for v in windows if v['node']=='node-4']
        self.assertEqual(['joining-originals-native/replica','joining-after-final-prefix/replica','joining-after-final-recovery/replica'],
                         [v['path'] for v in own])
        self.assertEqual([(4,5),(6,9),(10,len(events))],[(v['start'],v['end']) for v in own])
        with self.assertRaisesRegex(ValueError,'^joining export inactive current generation$'):a.e.current(windows,'node-4',5,6)

    def test_ordinary_reader_rejects_extra_adoption_and_recovery(self):
        with self.assertRaisesRegex(ValueError,'^joining export complete generation timeline$'):self.timeline(explicit=False)

    def test_missing_or_early_adoption_return_cannot_create_a_current_window(self):
        for change,reason in [('omitted','complete generation timeline'),('early','selector completion order')]:
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'^joining export '+reason+'$'):self.timeline(change)

    def test_recovery_window_requires_exact_final_cut(self):
        with self.assertRaisesRegex(ValueError,'^joining export same-view recovery selection$'):self.timeline('cut')

    def acquisition(self):
        base,own,generation=maintenance_fixture.JoiningMaintenanceEvidenceTest().acquisition()
        reader=a.Replay.__new__(a.Replay);reader.__dict__.update(base.__dict__);reader.floor_inputs=[]
        newer=copy.deepcopy(reader.status_rows[0]);newer.update(sent=3,delivered=5.5,requestHash='latest')
        reader.status_rows.append(newer)
        return reader,own,newer

    def test_latest_probe_is_bound_while_earlier_hint_remains_only_a_hint(self):
        reader,own,_=self.acquisition()
        with patch.object(a.e,'authorize_generation'):
            copies,used=reader.acquired(own,0,20)
        self.assertEqual(['latest'],used);self.assertEqual({'node-1','node-2'},set(copies))
        self.assertEqual(1,len(reader.floor_inputs))

    def test_latest_bad_probe_does_not_fall_back_to_older_convenient_hint(self):
        for change in ('late','cut','ballot'):
            reader,own,row=self.acquisition()
            if change=='late':row['delivered']=6
            elif change=='cut':row['response']['payload']['cut']['index']+=1
            else:row['request']['ballot']['counter']+=1
            with self.subTest(change=change),patch.object(a.e,'authorize_generation'), \
                    self.assertRaisesRegex(ValueError,'^joining maintenance acquisition before discovery$'):
                reader.acquired(own,0,20)

    def test_future_covering_copy_does_not_advance_local_peer_observation(self):
        before,_=peer_fixture.JoiningPeerEvidenceTest().ledger();plan=a.peer.peers.decode(before)['plan']
        local=dict(node='node-1',start=0,packet=dict(capsule=dict(cut=dict(index=2,view=plan['view']),catalog='a'*64,application='b'*64)))
        future=copy.deepcopy(local);future['node']='node-2';future['packet']['capsule']['cut']['index']=3
        reader=a.PeerReplay.__new__(a.PeerReplay);reader.state={'node-1':before};reader.sequence=Mock()
        reader.files=lambda own:{a.peer.FILE:before}
        reader.events=[dict(node='node-1',event=v) for v in ('FLOOR_RESERVED','FLOOR_BEFORE_RETURN','FLOOR_RELEASE_AUTHORITY_CREATED')]
        with patch.object(a.peer.t.observation,'observe_same_cut',return_value=before) as observe:
            reader.floor(dict(start=0,own=local,copies={'node-1':local,'node-2':future},order=['node-1','node-2']))
        self.assertEqual(1,observe.call_count);self.assertEqual(before,reader.state['node-1'])
        self.assertEqual([],reader.sequence.call_args.args[1])

    def test_original_physical_network_failure_prevents_authority_replay(self):
        with patch.object(a.n.s.collection,'inventory',return_value={}),patch.object(a.network,'validate',side_effect=ValueError('network')), \
                patch.object(a,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'^network$'):a.validate('/unused')
            replay.assert_not_called()

    def test_validation_keeps_unqualified_layers_explicit_and_detects_changed_input(self):
        original=dict(network=dict(committedTransfers=5,transferSessions=4,rejectedTransferAttempts=1))
        replay=dict(controls=dict(observedCommittedContents=5,observedContentSessions=3))
        with patch.object(a.n.s.collection,'inventory',return_value={}),patch.object(a.network,'validate',return_value=original), \
                patch.object(a,'replay',return_value=replay):result=a.validate('/unused')
        self.assertEqual('PARTIAL',result['status']);self.assertTrue(result['peerLedgerCompositionQualified'])
        for key in ('learnerLedgerCompositionQualified','sameViewPhysicalQualified','completePhysicalQualified','phase3Complete','processDeathQualified'):
            self.assertIs(False,result[key])
        with patch.object(a.n.s.collection,'inventory',side_effect=[{},dict(changed=True)]),patch.object(a.network,'validate',return_value=original), \
                patch.object(a,'replay',return_value=replay):
            with self.assertRaisesRegex(ValueError,'^joining same-view authority original changed$'):a.validate('/unused')
        replay['controls']['observedCommittedContents']=4
        with patch.object(a.n.s.collection,'inventory',return_value={}),patch.object(a.network,'validate',return_value=original), \
                patch.object(a,'replay',return_value=replay):
            with self.assertRaisesRegex(ValueError,'^joining same-view complete export authority coverage$'):a.validate('/unused')

    def test_failed_original_prevents_parallel_negative_work(self):
        with patch.object(a,'validate',side_effect=ValueError('original')),patch.object(a,'ProcessPoolExecutor') as pool:
            with self.assertRaisesRegex(ValueError,'^original$'):a.qualify('/unused',workers=4)
            pool.assert_not_called()

    def test_export_timeline_rejection_occurs_in_target_after_network_precondition(self):
        with patch.object(a.network,'observed',return_value={}) as network,patch.object(a,'Replay',side_effect=ValueError('timeline')) as reader:
            target=a.stages('/unused','exports');network.assert_called_once();reader.assert_not_called()
            with self.assertRaisesRegex(ValueError,'^timeline$'):target()

    def test_export_negative_does_not_swallow_failed_network_precondition(self):
        with patch.object(a.network,'observed',side_effect=ValueError('network')),patch.object(a,'Replay') as reader:
            with self.assertRaisesRegex(ValueError,'^network$'):a.stages('/unused','exports')
            reader.assert_not_called()

    def test_closed_completion_is_explicitly_owned_by_the_earlier_export_gate(self):
        with patch.object(a,'Replay',return_value=SimpleNamespace(model=None,groups=[])),patch.object(a.e,'pending_ack',return_value=b'absent'):
            cases=a.cases('/unused')
        selected=[v for v in cases if v[1]=='completion-closed-owner']
        self.assertEqual([('exports','completion-closed-owner','joining control original owner lifetime')],selected)
        self.assertEqual(65,len(cases));self.assertEqual(65,len({v[1] for v in cases}))
        self.assertNotIn('pending-after-retain',{v[1] for v in cases})

    def test_reclassified_completion_keeps_its_original_control_mutation(self):
        with patch.object(Path,'read_bytes',return_value=b'original-selection'),patch.object(a.c,'mutate') as control,patch.object(a.e,'mutate') as exports:
            a.mutate('/unused','exports','completion-closed-owner')
        control.assert_called_once_with(Path('/unused'),'completion-closed-owner',kind='REPLACE',recovery=b'original-selection')
        exports.assert_not_called()

    def test_replay_worker_bounds_are_not_measurement_retries(self):
        for value in (0,5,True,1.5):
            with self.subTest(value=value),patch.object(a,'validate') as original, \
                    self.assertRaisesRegex(ValueError,'^joining authority replay workers$'):a.qualify('/unused',workers=value)
            original.assert_not_called()

    def negative(self,*,changed=False,error=None,accepted=False,precondition=False):
        before=dict(files={'original':'hash','events.json':'events'},directories=['empty']);after=copy.deepcopy(before)
        if changed:after['files']['original']='changed'
        target=Mock(side_effect=None if accepted else ValueError(error or 'expected'))
        with patch.object(a.shutil,'copytree'),patch.object(a,'mutate'),patch.object(a.n.s.collection,'inventory',return_value=after), \
                patch.object(a,'stages',side_effect=ValueError('precondition') if precondition else None,return_value=target):
            return a.negative('/unused',before,('peers','case','expected'))

    def test_storage_changes_cannot_reuse_original_derivation(self):
        with self.assertRaisesRegex(ValueError,'^joining same-view authority negative changed physical inputs$'):self.negative(changed=True)

    def test_failed_precondition_or_wrong_failure_cannot_qualify_negative(self):
        with self.assertRaisesRegex(ValueError,'^precondition$'):self.negative(precondition=True)
        with self.assertRaisesRegex(ValueError,'^joining same-view unrelated authority negative: case: wrong$'):self.negative(error='wrong')
        with self.assertRaisesRegex(ValueError,'^joining same-view authority mutation accepted: case$'):self.negative(accepted=True)
        self.assertEqual('PASS',self.negative()['precedingLayers'])


if __name__=='__main__':unittest.main()
