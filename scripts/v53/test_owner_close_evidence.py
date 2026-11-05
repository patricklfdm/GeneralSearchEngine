"""Conditional close interval checks; actual native evidence is qualified separately."""
import copy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from . import owner_close_evidence as r, owner_close_negatives as negatives
from .test_resource_transitions import charge,row,trace
from . import test_native_resource_evidence as native_test


def fixture():
    value=charge('SOURCE','original',20)
    journal=trace([row('START'),row('RESERVE',added=[value],metadata=20,staging=20,counts={'SOURCE':1}),row('RELEASE',[value])])
    events=[dict(node='node-1',event=v) for v in ('OPEN',r.BEGIN,r.RETURNED)]
    boundaries=[dict(eventIndex=i,node='node-1',sequence=seq,usage=copy.deepcopy(journal['changes'][seq]['usage']))
                for i,seq in enumerate((0,1,2))]
    return dict(schema=r.V2,closingOwners=['node-1']),{'node-1':journal},boundaries,events,{'node-1'}


class OwnerCloseEvidenceTest(unittest.TestCase):
    def test_original_close_is_quiescent_release_only_and_terminal(self):
        data=fixture();before=copy.deepcopy(data);result=r.replay(*data)
        self.assertEqual(1,result['releasedLeases']);self.assertTrue(result['ownerCloseIntervalsQualified']);self.assertEqual(before,data)
        for flag in ('physicalShutdownOrderQualified','wholeRuntimeResourcesQualified','phase3Complete'):self.assertFalse(result[flag])

    def test_historical_trace_never_invents_close_observations(self):
        data=fixture();data[0].pop('closingOwners');data[0]['schema']=r.V1
        for event in data[3]:event['event']='OLD_CALLBACK'
        result=r.replay(*data);self.assertEqual('NOT_OBSERVED',result['status']);self.assertFalse(result['ownerCloseIntervalsQualified'])
        with self.assertRaisesRegex(ValueError,'original markers required'):negatives.replay(data)

    def test_all_coherent_negatives_reject_for_their_specific_reason(self):
        data=fixture();before=copy.deepcopy(data);results=negatives.replay(data)
        self.assertEqual(list(negatives.NEGATIVES),[v['case'] for v in results]);self.assertEqual(before,data)

    def test_invalid_original_is_rejected_before_negative_mutation(self):
        data=fixture();data[1]['node-1']['failed']=True
        with patch.object(negatives,'mutate') as mutate,self.assertRaisesRegex(ValueError,'incomplete observation'):negatives.replay(data)
        mutate.assert_not_called()

    def test_full_entry_requires_original_physical_native_validation(self):
        with patch.object(negatives.native.collection,'inventory',return_value={}), \
             patch.object(negatives.native,'validate',side_effect=ValueError('bad original')),patch.object(negatives.native,'load') as load:
            with self.assertRaisesRegex(ValueError,'bad original'):negatives.qualify('/unused')
        load.assert_not_called()

    def test_duplicate_marker_extra_scope_or_wrong_owner_cannot_substitute(self):
        for mode in ('duplicate','scope','foreign'):
            data=fixture();events=data[3]
            if mode=='duplicate':events.append(copy.deepcopy(events[-1]))
            elif mode=='scope':events[-1]['scope']='another-owner'
            else:events[-1]['node']='node-2'
            with self.subTest(mode=mode),self.assertRaises(ValueError):r.replay(*data)

    def test_checkpoints_require_exact_node_position_sequence_and_usage(self):
        for key,value in (('node','node-2'),('eventIndex',True),('sequence',True),('sequence',-1),('sequence',3),('usage',{})):
            data=fixture();data[2][1][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):r.replay(*data)

    def test_every_original_owner_is_required_even_if_one_has_no_basis(self):
        data=fixture();data[4].add('node-2')
        with self.assertRaisesRegex(ValueError,'complete original owners'):r.replay(*data)

    def test_terminal_zero_alone_cannot_authorize_a_later_reservation(self):
        data=fixture();journal=data[1]['node-1'];value=charge('SOURCE','later',1)
        journal['changes'].extend([row('RESERVE',added=[value]),row('RELEASE',[value])]);negatives.recount(data[1],data[2])
        with self.assertRaisesRegex(ValueError,'terminal resource interval'):r.replay(*data)

    def test_v2_loader_requires_exact_schema_and_preserves_declared_owners(self):
        helper=native_test.NativeResourceEvidenceTest();data=list(helper.original());data[0]['schema']=r.V2;data[0]['closingOwners']=['node-1','node-2','node-3']
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);helper.write(root,data);loaded=negatives.native.load(root)
            self.assertEqual(data[0]['closingOwners'],loaded[0]['closingOwners'])
            data[0].pop('closingOwners');helper.write(root,data)
            with self.assertRaisesRegex(ValueError,'native resources index'):negatives.native.load(root)


if __name__=='__main__':unittest.main()
