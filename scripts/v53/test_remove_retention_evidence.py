"""REMOVE composition, continuous state and original-first rejection guards."""
from contextlib import ExitStack
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from . import remove_retention_evidence as r
from .test_joining_same_view_future import event


class RemoveRetentionEvidenceTest(unittest.TestCase):
    def test_invalid_profile_prevents_read(self):
        with patch.object(r.n.collection,'inventory') as inventory:
            with self.assertRaisesRegex(ValueError,'^REMOVE retention profile$'):r.validate('/unused','3-REMOVE')
        inventory.assert_not_called()

    def test_failed_original_authority_prevents_composition_and_mutations(self):
        with patch.object(r.n.collection,'inventory',return_value={}),patch.object(r.e,'validate',side_effect=ValueError('original')),patch.object(r,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'^original$'):r.validate('/unused','4-REMOVE')
        replay.assert_not_called()
        with patch.object(r,'validate',side_effect=ValueError('original')),patch.object(r,'negative') as negative:
            with self.assertRaisesRegex(ValueError,'^original$'):r.qualify('/unused','5-REMOVE')
        negative.assert_not_called()

    def test_changed_original_cannot_complete(self):
        with patch.object(r.n.collection,'inventory',side_effect=[{},dict(changed=True)]),patch.object(r.e,'validate'),patch.object(r,'replay'):
            with self.assertRaisesRegex(ValueError,'^REMOVE retention original changed$'):r.validate('/unused','4-REMOVE')

    def test_only_component_qualification_is_claimed(self):
        with patch.object(r,'PeerReplay') as peers,patch.object(r,'FutureReplay') as future:
            peers.return_value.run.return_value={};future.return_value.run.return_value={}
            result=r.replay('/unused','5-REMOVE')
        self.assertEqual('PARTIAL',result['status']);self.assertTrue(result['retentionRevisionCompositionQualified'])
        for key in ('completeRetirementTransactions','processDeathQualified','phase3Complete'):self.assertIs(False,result[key])

    def opens(self):
        return [event(p,node) for node in ('node-1','node-4','node-5') for p in
                ['CURRENT_VALIDATED',*r.peer.RESEAL,r.future.RESEAL[0]]]

    def test_reseal_covers_unselected_original_fourth_and_fifth_voters(self):
        rows=self.opens()
        self.assertEqual([(2,'node-1'),(6,'node-4'),(10,'node-5')],r.peer_reseals(rows,('node-1','node-4','node-5')))
        rows.pop(10)
        with self.assertRaisesRegex(ValueError,'^joining peer exact open reseal count$'):r.peer_reseals(rows,('node-1','node-4','node-5'))

    def test_extra_owner_reseal_and_swapped_force_order_refuse(self):
        rows=self.opens()+[event(p,'node-9') for p in r.peer.RESEAL]
        with self.assertRaisesRegex(ValueError,'^joining peer unbound open reseal$'):r.peer_reseals(rows,('node-1','node-4','node-5'))
        rows=self.opens();rows[1],rows[2]=rows[2],rows[1]
        with self.assertRaisesRegex(ValueError,'^joining peer open reseal force order$'):r.peer_reseals(rows,('node-1','node-4','node-5'))

    def test_remove_future_has_no_joining_owner_scope(self):
        rows=[event(p,'node-4') for p in r.future.WRITES]
        self.assertEqual(1,len(r.future.observations(rows,joining=None)[0]))
        rows[0]['scope']='continuation-owner'
        with self.assertRaisesRegex(ValueError,'^joining future event shape$'):r.future.observations(rows,joining=None)
        # The pre-existing REPLACE default continues to require a scope.
        with self.assertRaisesRegex(ValueError,'^joining future event shape$'):
            r.future.observations([event(p,'node-4') for p in r.future.WRITES])

    def test_peer_writes_and_completions_cannot_claim_extra_authority(self):
        for point in (r.peer.WRITES[0],'SELECTED_RETENTION_COMPLETED',r.peer.RESEAL[0]):
            for row in (dict(event(point),scope='foreign-owner'),dict(event(point),revision=99),event(point,'node-9')):
                with self.subTest(row=row),self.assertRaisesRegex(ValueError,'^REMOVE peer event shape$'):
                    r.peer_event_shapes([row],('node-1',))
        with self.assertRaisesRegex(ValueError,'^joining peer unsupported retention event$'):
            r.peer_event_shapes([event('RETENTION_DISCARDED')],('node-1',))

    def test_future_run_carries_state_across_slots_and_compares_closed_bytes(self):
        reader=r.FutureReplay.__new__(r.FutureReplay);reader.root=Path('/original')
        reader.model=SimpleNamespace(old=('node-1',));reader.events=[event(r.future.RESEAL[-1])]
        reader.base=SimpleNamespace(phases={(1,'node-1'):{'PUBLICATION_BEFORE_RETURN':2},(2,'node-1'):{'PUBLICATION_BEFORE_RETURN':4}},windows=[])
        reader.state={};reader.used=set();reader.tx=[];reader.callbacks=set();reader.steps=[];reader.comparisons=0;reader.reseals=0
        reader.initialize=Mock(side_effect=lambda node,files:reader.state.update({node:dict(meta=dict(revision=0),raw=b'zero')}))
        reader.reopen=Mock(side_effect=lambda *args:reader.callbacks.add(0))
        seen=[]
        def phase(index,node):
            seen.append(reader.state[node]['meta']['revision']);reader.state[node]=dict(meta=dict(revision=index),raw=str(index).encode())
        reader.phase=phase
        with patch.object(r.c,'inventory',return_value={r.future.future.FILE:b'2'}):result=reader.run()
        self.assertEqual([0,1],seen);self.assertEqual({'node-1':2},result['finalRevisions'])
        self.assertEqual(1,reader.initialize.call_count)
        with self.assertRaisesRegex(ValueError,'^joining future exact continuous ledger: stale: node-1$'):
            reader.compare('node-1',{r.future.future.FILE:b'1'},'stale')

    def test_stale_snapshot_never_replaces_continuous_peer_state(self):
        reader=r.PeerReplay.__new__(r.PeerReplay);reader.state={'node-1':b'latest'};reader.comparisons=0
        with self.assertRaisesRegex(ValueError,'^joining peer exact original ledger: installed: node-1$'):
            reader.compare('node-1',b'previous','installed')
        self.assertEqual({'node-1':b'latest'},reader.state)

    def negative(self,change=None,error=None,accepted=False):
        before=dict(files={'authority':'a','wire.json':'w','events.json':'e'},directories=['empty']);after=copy.deepcopy(before)
        original=[event('CURRENT_VALIDATED')];changed=copy.deepcopy(original)
        if change=='file':after['files']['wire.json']='changed'
        elif change=='directory':after['directories']=[]
        elif change=='other-observation':changed[0]['event']='CURRENT_DIRECTORY_FORCED'
        stage='future';name='unbound-write'
        with ExitStack() as stack:
            for obj,key,value in [(r.shutil,'copytree',None),(r,'mutate',None),(r.n.collection,'inventory',after)]:stack.enter_context(patch.object(obj,key,return_value=value))
            stack.enter_context(patch.object(r.n.collection,'read_json',side_effect=[original,changed]))
            reader=stack.enter_context(patch.object(r,'FutureReplay'))
            reader.return_value.run.side_effect=None if accepted else ValueError(error or r.NEGATIVES[stage][name])
            return r.negative('/unused','4-REMOVE',before,stage,name)

    def test_negative_cannot_change_wire_physical_files_or_empty_directories(self):
        for change in ('file','directory'):
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'^REMOVE retention negative changed original files$'):self.negative(change)

    def test_negative_cannot_change_other_observation_families(self):
        with self.assertRaisesRegex(ValueError,'^REMOVE retention negative changed other observations$'):self.negative('other-observation')

    def test_unrelated_rejection_or_accepted_mutation_cannot_qualify(self):
        with self.assertRaisesRegex(ValueError,'^REMOVE unrelated retention negative:'):self.negative(error='unrelated')
        with self.assertRaisesRegex(ValueError,'^REMOVE retention mutation accepted:'):self.negative(accepted=True)
        self.assertTrue(self.negative()['originalFilesAndOtherObservationsUnchanged'])


if __name__=='__main__':unittest.main()
