import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import special_export_resource_evidence as r
from . import special_export_resource_negatives as n
from .test_resource_transitions import charge,row,trace


def fixture(family):
    specs=[('vote-export',letter*64,200) for letter in 'abc'] if family=='vote' else [('learner-root-export','a'*64,5000),('prefix-export','b'*64,4096)]
    expected={(role,ref):size for role,ref,size in specs};base=charge('SOURCE','original-storage',100)
    rows=[row('START'),row('RESERVE',added=[base])];cases=[]
    for i,mode in enumerate(('close','expiry'),1):
        events=[];leases=[]
        def mark(name):events.append(dict(event=name,point=dict(sequence=len(rows)-1,usage={})))
        mark('BEGIN')
        for j,(role,ref,size) in enumerate(specs):
            lease=charge('CONTROL',role+'-'+ref+'-'+f'00000000-0000-0000-0000-{i*10+j:012d}',size);leases.append(lease)
            rows.append(row('RESERVE',added=[lease]))
        mark('OPENED');mark('READS_FINISHED');mark('RELEASE_BEGIN')
        deferred=family=='learner-root' and mode=='expiry'
        if deferred:mark('INVALIDATED')
        for lease in leases:rows.append(row('RELEASE',[lease]))
        if not deferred:mark('INVALIDATED')
        mark('RELEASED');mark('REUSE_REFUSED');mark('FINISHED');cases.append(dict(mode=mode,events=events))
    rows.append(row('RELEASE',[base]));history=dict(schema='gse-v53-special-export-resources-v1',family=family,status='PASS',cases=cases,completeMembershipHistory=False)
    value=trace(rows);n.recount(value,history);return value,history,expected


class SpecialExportResourceEvidenceTest(unittest.TestCase):
    def test_separate_vote_receipts_and_nested_root_borrow_are_all_required(self):
        for family,count in (('vote',6),('learner-root',4)):
            data=fixture(family);before=copy.deepcopy(data);result=r.replay(*data)
            self.assertEqual(before,data);self.assertEqual(count,result['exportReservations']);self.assertTrue(result['exportReservationBindingsQualified'])
            for flag in ('networkReservationCompositionQualified','expiryClockIndependentlyQualified','allExportFamiliesQualified','wholeRuntimeResourcesQualified','phase3Complete'):
                self.assertFalse(result[flag])

    def test_all_exact_negatives_preserve_original_claims(self):
        for family in ('vote','learner-root'):
            data=fixture(family);before=copy.deepcopy(data)
            self.assertEqual([dict(case=k,status='REJECTED',reason=v) for k,v in n.NEGATIVES.items()],n.replay(data));self.assertEqual(before,data)

    def test_original_physical_failure_prevents_negative_mutation(self):
        with patch.object(r.t.collection,'inventory',return_value={}),patch.object(r,'load',side_effect=ValueError('original failed')),patch.object(n,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'^original failed$'):n.qualify('unused')
            mutate.assert_not_called()

    def test_original_accounting_failure_prevents_negative_mutation(self):
        data=fixture('vote');data[1]['status']='FAIL'
        with patch.object(n,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'original scope'):n.replay(data)
            mutate.assert_not_called()

    def test_recounted_missing_nested_borrow_cannot_hide_behind_final_zero(self):
        data=fixture('learner-root');n.mutate(data,'missing-allocation');r.t.replay(data[0]);self.assertEqual(0,data[0]['current']['leases'])
        with self.assertRaisesRegex(ValueError,'complete acquisitions'):r.replay(*data)

    def test_reference_substitution_is_rejected_even_if_extent_is_equal(self):
        data=fixture('vote');n.mutate(data,'wrong-binding');r.t.replay(data[0])
        with self.assertRaisesRegex(ValueError,'original content binding'):r.replay(*data)

    def test_release_then_reacquire_original_storage_is_not_continuous_custody(self):
        data=fixture('learner-root');n.mutate(data,'baseline-gap');r.t.replay(data[0])
        with self.assertRaisesRegex(ValueError,'continuous original custody'):r.replay(*data)

    def test_clock_expiry_policies_are_family_specific(self):
        for family in ('vote','learner-root'):
            data=fixture(family);n.mutate(data,'wrong-expiry-policy');r.t.replay(data[0])
            with self.assertRaisesRegex(ValueError,'expiry release policy'):r.replay(*data)

    def test_boundaries_reject_bool_negative_and_past_end(self):
        for value in (True,-1,1000):
            data=fixture('vote');data[1]['cases'][0]['events'][0]['point']['sequence']=value
            with self.assertRaisesRegex(ValueError,'original boundaries'):r.replay(*data)

    def test_malformed_original_claims_cannot_enable_a_partial_family(self):
        for family in ('vote','learner-root'):
            for bad in ({}, {('wrong','a'*64):10},{('vote-export','bad'):10}):
                data=fixture(family)
                with self.assertRaisesRegex(ValueError,'original expectations'):r.replay(data[0],data[1],bad)

    def test_learner_physical_replay_receives_only_the_two_declared_sidecars(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(r.learner,'validate',side_effect=ValueError('native original failed')) as validate:
            with self.assertRaisesRegex(ValueError,'native original failed'):r.originals(Path(temp),'learner-root')
            validate.assert_called_once_with(Path(temp),additional=r.FILES,current_retention=True)


if __name__=='__main__':unittest.main()
