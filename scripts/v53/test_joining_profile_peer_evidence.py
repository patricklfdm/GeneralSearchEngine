"""Conditional owner/chain checks; larger native cohorts remain independent."""
from contextlib import ExitStack
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch,Mock

from . import joining_profile_peer_evidence as p
from . import test_joining_peer_evidence as fixtures
from . import test_joining_profile_maintenance_evidence as floors


class ProfilePeerTest(unittest.TestCase):
    def model(self,profile):
        _,kind,old,new=p.topology(profile)
        return SimpleNamespace(old=old,joining=new[-1],kind=kind)

    def opens(self,model):
        return [dict(node=node,event=point,**({} if scope is None else dict(scope=scope)))
                for node,scope in p.peer.owner_lifetimes(model)
                for point in ['CURRENT_VALIDATED','LEARNER_RETENTION_RECOVERY_PARENT_FORCED',*p.peer.RESEAL,'FUTURE_RETENTION_RECOVERY_FORCED']]

    def test_all_original_voters_and_five_actual_joining_opens_are_required(self):
        for profile in p.PROFILES:
            model=self.model(profile);owners=p.peer.owner_lifetimes(model)
            self.assertEqual([(n,None) for n in model.old],owners[:len(model.old)])
            self.assertEqual([(model.joining,s) for s in p.peer.JOINING_SCOPES],owners[len(model.old):])
            rows=p.peer.reseal_lifetimes(self.opens(model),owners)
            self.assertEqual(len(model.old)+5,len(rows))
        for old,joining in ((['node-1','node-1'],'node-5'),(['node-1','node-2'],'node-2')):
            with self.assertRaisesRegex(ValueError,'^joining peer original owner cohort$'):
                p.peer.owner_lifetimes(SimpleNamespace(old=old,joining=joining))

    def test_unused_original_voter_reseal_cannot_be_omitted(self):
        for profile in ('4-ADD','5-REPLACE'):
            model=self.model(profile);events=[v for v in self.opens(model) if v['node']!=model.old[-1]]
            with self.assertRaisesRegex(ValueError,'^joining peer exact open reseal count$'):
                p.peer.reseal_lifetimes(events,p.peer.owner_lifetimes(model))

    def test_wrong_joiner_and_foreign_open_cannot_supply_original_reseals(self):
        model=self.model('5-REPLACE');owners=p.peer.owner_lifetimes(model);events=self.opens(model)
        for row in events:
            if row['node']==model.joining:row['node']='node-7'
        with self.assertRaisesRegex(ValueError,'^joining peer exact open reseal count$'):p.peer.reseal_lifetimes(events,owners)
        events=self.opens(model);events.extend(dict(node='foreign',event=point) for point in p.peer.RESEAL)
        with self.assertRaisesRegex(ValueError,'^joining peer unbound open reseal$'):p.peer.reseal_lifetimes(events,owners)

    def chain(self,node,joining,scope):
        reader=p.Replay.__new__(p.Replay);reader.model=SimpleNamespace(joining=joining)
        values=fixtures.JoiningPeerEvidenceTest().ledger();states=[p.peer.peers.decode(v) for v in values]
        for state in states:state['owner']=dict(state['owner'],node=node)
        before=p.peer.peers.frame(states[0]);states[1]['previous']=p.peer.sha(before);after=p.peer.peers.frame(states[1])
        reader.tx=[dict(node=node,scope=scope,start=2,end=8)];reader.used=set();reader.steps=[]
        return reader,[(before,after,'selected')]

    def test_joiner_write_scope_uses_actual_node_five_or_six(self):
        for joining in ('node-5','node-6'):
            reader,changes=self.chain(joining,joining,'continuation-owner')
            reader.sequence(joining,changes,1,9,'selected');self.assertEqual({2},reader.used)
            for scope in (None,'initial-owner','other'):
                reader,changes=self.chain(joining,joining,scope)
                with self.assertRaisesRegex(ValueError,'^joining peer original write owner$'):reader.sequence(joining,changes,1,9,'selected')

    def test_old_node_four_is_not_misclassified_as_the_joining_owner(self):
        reader,changes=self.chain('node-4','node-5',None)
        reader.sequence('node-4',changes,1,9,'selected');self.assertEqual(1,len(reader.steps))
        reader,changes=self.chain('node-4','node-5','continuation-owner')
        with self.assertRaisesRegex(ValueError,'^joining peer original write owner$'):reader.sequence('node-4',changes,1,9,'selected')

    def test_joining_initialization_uses_exact_seed_for_actual_owner(self):
        for joining in ('node-5','node-6'):
            reader=p.Replay.__new__(p.Replay);reader.model=SimpleNamespace(joining=joining);reader.state={}
            reader.root=Path('/original');reader.sources=[];reader.comparisons=0
            own=dict(node=joining,identity=dict(node=joining),packet=dict(capsule=dict(cut=dict(view=dict(old=['node-1','node-2','node-3'])))))
            reader.current=Mock(return_value=own);reader.files=Mock(return_value={p.peer.FILE:b'derived original ledger'})
            with patch.object(p.peer.init.retention,'derive',return_value=(b'original seed',{p.peer.FILE:b'derived original ledger'})) as derive, \
                 patch.object(Path,'read_bytes',return_value=b'original seed'):
                reader.initialize(10)
            self.assertEqual({joining:b'derived original ledger'},reader.state)
            reader.current.assert_called_once_with(joining,10,10);self.assertEqual(own['identity'],derive.call_args.args[1])
            with self.assertRaisesRegex(ValueError,'^joining peer duplicate joining initialization$'):reader.initialize(11)

    def test_joiner_reseal_uses_current_generation_while_old_voter_uses_bootstrap(self):
        reader=p.Replay.__new__(p.Replay);reader.model=SimpleNamespace(joining='node-6');reader.root=Path('/original')
        reader.state={'node-4':b'old','node-6':b'joined'};reader.comparisons=0
        reader.current=Mock(return_value=dict(node='node-6',path='joined'));reader.files=Mock(return_value={p.peer.FILE:b'joined'})
        with patch.object(p.peer.disk,'inventory',return_value={p.peer.FILE:b'old'}) as inventory:
            reader.reseal((9,'node-4'));reader.reseal((10,'node-6'))
        inventory.assert_called_once_with(Path('/original/before-network/node-4'))
        reader.current.assert_called_once_with('node-6',10,10);self.assertEqual(2,reader.comparisons)

    def test_adoption_compares_existing_state_without_resetting_the_chain(self):
        reader=p.Replay.__new__(p.Replay);reader.state={'node-6':b'prior'};reader.comparisons=0;own=dict(node='node-6')
        reader.files=Mock(return_value={p.peer.FILE:b'prior'});reader.adoption(own)
        reader.files.return_value={p.peer.FILE:b'forged'}
        with self.assertRaisesRegex(ValueError,'^joining peer exact original ledger: adoption: node-6$'):reader.adoption(own)
        self.assertEqual({'node-6':b'prior'},reader.state);self.assertEqual(1,reader.comparisons)

    def test_profile_floor_paths_record_inputs_once_with_original_copy_order(self):
        reader=p.Replay.__new__(p.Replay);reader.floor_inputs=[];own=dict(node='node-2');copies={'node-2':own,'node-1':dict(node='node-1')}
        with patch.object(p.maintenance.m.Replay,'acquired',return_value=(copies,['original'])):
            reader.acquired(own,0,10)
        self.assertEqual(1,len(reader.floor_inputs));self.assertEqual(['node-2','node-1'],reader.floor_inputs[0]['order'])
        for profile in ('4-ADD','5-REPLACE'):
            original,own=floors.ProfileMaintenanceTest().direct_reader(profile)
            reader=p.Replay.__new__(p.Replay);reader.__dict__.update(vars(original));reader.direct(own,10)
            self.assertEqual(1,len(reader.floor_inputs))
            self.assertEqual(reader.expected_confirmations|{reader.model.joining},set(reader.floor_inputs[0]['copies']))

    def test_covering_future_copy_does_not_erase_unresolved_local_debt(self):
        before,_=fixtures.JoiningPeerEvidenceTest().ledger();plan=p.peer.peers.decode(before)['plan']
        local=dict(node='node-1',packet=dict(capsule=dict(cut=dict(index=2,view=plan['view']),catalog='a'*64,application='b'*64)))
        future=copy.deepcopy(local);future['node']='node-2';future['packet']['capsule']['cut']['index']=3
        reader=p.Replay.__new__(p.Replay);reader.model=SimpleNamespace(joining='node-6');reader.state={'node-1':before};reader.sequence=Mock()
        reader.files=lambda own:{p.peer.FILE:before}
        reader.events=[dict(node='node-1',event=v) for v in ('FLOOR_RESERVED','FLOOR_BEFORE_RETURN','FLOOR_RELEASE_AUTHORITY_CREATED')]
        with patch.object(p.peer.t.observation,'observe_same_cut',return_value=before) as observe:
            reader.floor(dict(start=0,own=local,copies={'node-1':local,'node-2':future},order=['node-1','node-2']))
        self.assertEqual(1,observe.call_count);self.assertEqual(before,reader.state['node-1']);self.assertEqual([],reader.sequence.call_args.args[1])

    def test_original_maintenance_failure_prevents_peer_replay_and_negatives(self):
        with patch.object(p.collection,'inventory',return_value={}),patch.object(p.maintenance,'validate',side_effect=ValueError('bad original')), \
             patch.object(p,'replay') as replay,patch.object(p.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^bad original$'):p.qualify('/unused','4-ADD')
            replay.assert_not_called();copied.assert_not_called()

    def test_result_does_not_claim_other_ledgers_or_full_cohort(self):
        with patch.object(p.collection,'inventory',return_value={}),patch.object(p.maintenance,'validate',return_value={}),patch.object(p,'replay',return_value={}):
            result=p.validate('/unused','5-REPLACE');self.assertTrue(result['peerLedgerCompositionQualified'])
            for key in ('learnerLedgerCompositionQualified','futureLedgerCompositionQualified','allMembershipProfilesQualified','processDeathQualified','phase3Complete'):
                self.assertFalse(result[key])
        with patch.object(p.collection,'inventory',side_effect=[{},dict(changed=True)]),patch.object(p.maintenance,'validate'),patch.object(p,'replay'):
            with self.assertRaisesRegex(ValueError,'^joining profile peer original changed$'):p.validate('/unused','4-ADD')

    def guards(self,stack):
        for module,name,result in ((p,'validate',{}),(p.collection,'inventory',dict(files={},directories=[])),(p.shutil,'copytree',None),
                                   (p,'Replay',None),(p.peer,'mutate',None),(p.peer.n,'network',None),
                                   (p.maintenance.control.exports,'replay',None),(p.maintenance.control,'replay',None),(p.maintenance,'replay',None)):
            stack.enter_context(patch.object(module,name,return_value=result))

    def test_negatives_preserve_wire_physical_members_and_directories(self):
        for changed in (dict(files={'wire.json':'changed'},directories=[]),dict(files={'original':'changed'},directories=[]),dict(files={},directories=['added'])):
            with ExitStack() as stack:
                self.guards(stack);stack.enter_context(patch.object(p.collection,'inventory',side_effect=[dict(files={},directories=[]),changed]))
                network=stack.enter_context(patch.object(p.peer.n,'network'))
                with self.assertRaisesRegex(ValueError,'^joining profile peer negative changed physical inputs$'):p.qualify('/unused','5-REPLACE')
                network.assert_not_called()

    def test_prior_layer_errors_are_not_peer_rejections(self):
        for module,name in ((p.peer.n,'network'),(p.maintenance.control.exports,'replay'),(p.maintenance.control,'replay'),(p.maintenance,'replay')):
            with ExitStack() as stack:
                self.guards(stack);stack.enter_context(patch.object(module,name,side_effect=ValueError('prior failed')))
                replay=stack.enter_context(patch.object(p,'replay'))
                with self.assertRaisesRegex(ValueError,'^prior failed$'):p.qualify('/unused','4-ADD')
                replay.assert_not_called()

    def test_missing_target_is_not_a_successful_rejection(self):
        with ExitStack() as stack:
            self.guards(stack);stack.enter_context(patch.object(p.peer,'mutate',side_effect=StopIteration))
            with self.assertRaisesRegex(ValueError,'^joining profile peer missing negative target: force-missing$'):p.qualify('/unused','4-ADD')

    def test_wrong_error_or_accepted_mutation_fails_qualification(self):
        for failure,reason in ((None,'mutation accepted: force-missing'),(ValueError('other'),'unrelated peer negative: force-missing: other')):
            with ExitStack() as stack:
                self.guards(stack);stack.enter_context(patch.object(p,'replay',side_effect=failure))
                with self.assertRaisesRegex(ValueError,reason):p.qualify('/unused','5-REPLACE')


if __name__=='__main__':unittest.main()
