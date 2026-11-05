import copy
import unittest
from unittest.mock import patch
from . import export_resource_evidence as r
from . import export_resource_negatives as n
from .test_resource_transitions import charge,row,trace


def fixture():
    expected={role:dict(reference=letter*64,bytes=size) for role,letter,size in zip(r.ROLES,'abc',(500,200,4096))}
    base=charge('SOURCE','original-storage',100);rows=[row('START'),row('RESERVE',added=[base])];cases=[]
    for i,mode in enumerate(('close','expiry'),1):
        events=[];leases={}
        def mark(name):events.append(dict(event=name,point=dict(sequence=len(rows)-1,usage={})))
        mark('BEGIN')
        for role,label in zip(r.ROLES,('SOURCE','RECORD','PREFIX')):
            value=expected[role];lease=charge('CONTROL',role+'-'+value['reference']+'-'+f'00000000-0000-0000-0000-{i:012d}',value['bytes']);leases[label]=lease
            rows.append(row('RESERVE',added=[lease]));mark(label+'_OPENED')
        mark('READS_FINISHED')
        for label in ('RECORD','SOURCE','PREFIX'):
            mark(label+'_RELEASE_BEGIN');rows.append(row('RELEASE',[leases[label]]));mark(label+'_RELEASED')
        mark('REUSE_REFUSED');mark('FINISHED');cases.append(dict(mode=mode,events=events))
    rows.append(row('RELEASE',[base]));history=dict(schema='gse-v53-export-resources-v1',size=3,status='PASS',cases=cases,completeMembershipHistory=False)
    value=trace(rows);n.recount(value,history);return value,history,expected


class ExportResourceEvidenceTest(unittest.TestCase):
    def test_bindings_derive_six_independent_extents_without_promoting_other_scopes(self):
        data=fixture();before=copy.deepcopy(data);result=r.replay(*data)
        self.assertEqual(before,data);self.assertEqual(6,result['exportReservations']);self.assertTrue(result['exportReservationBindingsQualified'])
        for flag in ('networkSessionQualified','expiryClockIndependentlyQualified','allExportFamiliesQualified','wholeRuntimeResourcesQualified','phase3Complete'):
            self.assertFalse(result[flag])

    def test_all_negatives_reject_exact_obligations_without_mutating_original_claims(self):
        data=fixture();before=copy.deepcopy(data);result=n.replay(data)
        self.assertEqual([dict(case=k,status='REJECTED',reason=v) for k,v in n.NEGATIVES.items()],result);self.assertEqual(before,data)

    def test_physical_failure_prevents_negative_mutations(self):
        with patch.object(r.t.collection,'inventory',return_value={}),patch.object(r,'validate',side_effect=ValueError('physical original failed')),patch.object(n,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'physical original failed'):n.qualify('unused')
            mutate.assert_not_called()

    def test_failed_accounting_original_prevents_mutations(self):
        data=fixture();data[1]['status']='FAIL'
        with patch.object(n,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'original scope'):n.replay(data)
            mutate.assert_not_called()

    def test_content_substitution_with_the_same_size_is_not_a_binding(self):
        data=fixture();n.mutate(data,'wrong-binding');r.t.replay(data[0])
        with self.assertRaisesRegex(ValueError,'original content binding'):r.replay(*data)

    def test_missing_or_extra_reservations_cannot_hide_behind_final_zero(self):
        for mutation in ('missing-allocation','extra-allocation'):
            data=fixture();n.mutate(data,mutation);r.t.replay(data[0]);self.assertEqual(0,data[0]['current']['leases'])
            with self.assertRaises(ValueError):r.replay(*data)

    def test_original_storage_must_remain_continuously_owned(self):
        data=fixture();n.mutate(data,'baseline-gap');r.t.replay(data[0])
        with self.assertRaisesRegex(ValueError,'continuous original custody'):r.replay(*data)

    def test_legacy_random_names_are_unbound_even_when_extent_matches(self):
        data=fixture();n.mutate(data,'legacy-name');r.t.replay(data[0])
        with self.assertRaisesRegex(ValueError,'observed owner binding'):r.replay(*data)

    def test_boundaries_cannot_be_negative_boolean_or_past_the_original_stream(self):
        for value in (-1,True,1000):
            data=fixture();data[1]['cases'][0]['events'][0]['point']['sequence']=value
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'original boundaries'):r.replay(*data)

    def test_incomplete_stream_cannot_be_promoted_by_zero_final_counts(self):
        for field in ('failed','truncated'):
            data=fixture();data[0][field]=True
            with self.assertRaisesRegex(ValueError,'incomplete observation'):r.replay(*data)

    def test_explicit_role_digest_and_extent_are_required_in_physical_expectations(self):
        for mutation in ('missing','extra','digest','size'):
            data=fixture();claims=data[2]
            if mutation=='missing':claims.pop('prefix-export')
            elif mutation=='extra':claims['unobserved']=dict(reference='d'*64,bytes=1)
            elif mutation=='digest':claims['source-export']['reference']='not a digest'
            else:claims['source-export']['bytes']=True
            with self.assertRaisesRegex(ValueError,'original content expectations'):r.replay(*data)


if __name__=='__main__':unittest.main()
