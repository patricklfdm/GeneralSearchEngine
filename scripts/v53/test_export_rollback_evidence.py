import copy
import unittest
from unittest.mock import patch
from . import export_rollback_evidence as r
from . import export_rollback_negatives as negatives
from . import direct_export_negatives as direct
from .test_session_export_evidence import fixture as sessions
from .test_joining_export_request_evidence import packet
from .test_resource_transitions import charge
from .test_transport_resource_evidence import recount


def fixture(kind='retention-expiry'):
    traces,closes=sessions();trace=traces['node-1'];rows=trace['changes'];before=len(rows)-1
    role,size,children,failure,message=r.CASES[kind];raw,_,digest=packet()
    parent=role+'-'+digest+'-00000000-0000-0000-0000-000000000002'
    child='prefix-export-'+'d'*64+'-00000000-0000-0000-0000-000000000003'
    def change(event,name,size):
        rows.append(dict(event=event,added=[charge('CONTROL',name,size)] if event=='RESERVE' else [],
                         removed=[charge('CONTROL',name,size)] if event=='RELEASE' else []))
    change('RESERVE',parent,size)
    if children:
        change('RESERVE',child,4096);change('RELEASE',child,4096)
    markers=closes['node-1']['rows'];markers.append(dict(event='EXPORT_ROLLBACK_BEGIN',owner=parent,children=[child] if children else [],resourceSequence=len(rows)-1))
    change('RELEASE',parent,size);after=len(rows)-1
    markers.append(dict(event='EXPORT_ROLLBACK_RETURNED',owner=parent,children=[],resourceSequence=after))
    traces['node-1']=recount(rows);direct.renumber(closes['node-1'])
    case=dict(schema='gse-v53-export-rollback-component-v1',case=kind,node='node-1',request=raw,before=before,after=after,
              failureType=failure,failureMessage=message,completeNativeHistory=False)
    return traces,closes,[case]


class ExportRollbackEvidenceTest(unittest.TestCase):
    def test_parent_only_and_revoked_child_keep_original_failed_call(self):
        for kind in r.CASES:
            result=r.replay(*fixture(kind));self.assertEqual('PASS',result['status']);self.assertEqual(1,result['rollbackCalls'])
            nested=kind=='retention-expiry';self.assertEqual(2 if nested else 1,result['ownedAllocations'])
            self.assertEqual(1 if nested else 0,result['revokedChildrenBeforeCleanup']);self.assertFalse(result['phase3Complete'])
            self.assertFalse(result['allExportConstructorsQualified'])

    def test_allocation_inventory_distinguishes_session_from_constructor_cleanup(self):
        for kind in r.CASES:
            data=fixture(kind);result=r.exports.replay(*data[:2]);self.assertEqual('PASS',result['status'])
            self.assertEqual(1,result['sessionOwnedAllocations']);self.assertEqual(2 if kind=='retention-expiry' else 1,result['rollbackOwnedAllocations'])
            self.assertFalse(result['failedConstructorExportsQualified'])

    def test_every_negative_fails_only_its_named_obligation(self):
        for kind in r.CASES:
            data=fixture(kind);before=copy.deepcopy(data);result=negatives.replay(*data)
            self.assertEqual(13 if kind=='retention-expiry' else 11,len(result['negatives']));self.assertEqual(before,data)

    def test_zero_usage_cannot_replace_actual_return(self):
        data=fixture();negatives.mutate(*data,'missing-return');self.assertEqual(0,data[0]['node-1']['current']['leases'])
        with self.assertRaisesRegex(ValueError,'incomplete rollback'):r.replay(*data)

    def test_original_failure_precedes_all_mutations(self):
        data=fixture();data[1]['node-1']['failed']=True
        with patch.object(negatives,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'complete bounded recorder'):negatives.replay(*data)
            mutate.assert_not_called()

    def test_disabled_scope_cannot_accept_rollback_markers(self):
        data=fixture()
        with self.assertRaisesRegex(ValueError,'original export attachment|exact ordered row'):r.close.replay(*data[:2])

    def test_unknown_and_changed_failure_receipts_are_not_original_cases(self):
        for field,value in (('case','fake'),('failureType','IOException'),('failureMessage','fake'),('completeNativeHistory',True)):
            data=fixture();data[2][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):r.replay(*data)

    def test_valid_accounting_does_not_authorize_changed_request_bytes(self):
        data=fixture();data[2][0]['request']=packet(trace=101)[0]
        self.assertEqual('PASS',r.close.replay(*data[:2],export_ownership=True)['status'])
        with self.assertRaisesRegex(ValueError,'original request allocation'):r.replay(*data)

    def test_a_session_cannot_also_claim_the_failed_constructor_handle(self):
        data=fixture('preparation-guard');value=data[1]['node-1'];attachment=next(row for row in value['rows'] if row['event']=='ATTACHED')
        rollback=next(row for row in value['rows'] if row['event']=='EXPORT_ROLLBACK_BEGIN')
        # The original construction interval also prevents attaching a later
        # failed allocation to an already closed session.
        attachment['children']=[rollback['owner']]
        with self.assertRaisesRegex(ValueError,'original export allocation'):r.replay(*data)

    def test_unmarked_rollback_allocations_stay_partial_in_global_inventory(self):
        data=fixture();negatives.mutate(*data,'unobserved-pair');result=r.exports.inspect(*data[:2])
        self.assertEqual('PARTIAL',result['status']);self.assertEqual(2,len(result['unattachedExports']))
        with self.assertRaisesRegex(ValueError,'unclaimed allocation'):r.exports.replay(*data[:2])

    def test_missing_and_duplicate_expected_calls_cannot_pass(self):
        for plans in ([],[fixture()[2][0],fixture()[2][0]]):
            data=fixture()
            with self.assertRaisesRegex(ValueError,'complete observed calls'):r.replay(*data[:2],plans)

    def test_child_release_must_finish_before_normal_rollback_return(self):
        data=fixture();trace=data[0]['node-1'];rows=trace['changes'];case=data[2][0];before=case['before']
        child_release=rows.pop(before+3);rows.append(child_release);data[0]['node-1']=recount(rows)
        for row in data[1]['node-1']['rows']:
            if row['event']=='EXPORT_ROLLBACK_BEGIN':row['resourceSequence']=before+2
            elif row['event']=='EXPORT_ROLLBACK_RETURNED':row['resourceSequence']=before+3
        with self.assertRaisesRegex(ValueError,'rollback release before return'):r.replay(*data)

    def test_new_markers_cannot_claim_arbitrary_control_children(self):
        data=fixture();rows=data[1]['node-1']['rows'];begin=next(v for v in rows if v['event']=='EXPORT_ROLLBACK_BEGIN')
        unrelated=next(name for name in r.close.allocations(data[0]['node-1']) if name.startswith('record-export-'))
        begin['children']=[unrelated]
        with self.assertRaisesRegex(ValueError,'rollback original children'):r.replay(*data)

    def test_invalid_scope_shapes_fail_with_validation_errors(self):
        for field,value in (('case',[]),('request',False),('node',{})):
            data=fixture();data[2][0][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'original component scope'):r.replay(*data)
