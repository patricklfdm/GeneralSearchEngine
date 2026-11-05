import copy
import unittest
from unittest.mock import patch
from . import direct_export_evidence as r
from . import direct_export_negatives as negatives
from . import session_export_negatives
from .test_session_export_evidence import fixture as session_fixture


def fixture(phase='ACTIVATION'):
    traces,closes=session_fixture();session_export_negatives.mutate(traces,closes,'unclaimed-export')
    account=r.close.replay(traces,closes,export_ownership=True)['owners']['node-1']
    owned={name for row in account['exportAttachments'].values() for name in row['children']}
    old=next(name for name in account['lifetimes'] if r.exports.kind(name) and name not in owned)
    role=r.close.DIRECT_ROLES[phase];name=role+'-'+'c'*64+'-00000000-0000-0000-0000-000000000002'
    size=4096 if phase=='MAINTENANCE' else 1024
    for row in traces['node-1']['changes']:
        for value in row['added']+row['removed']:
            if value['owner']==old:value.update(owner=name,bytes=size)
    negatives.recount(traces['node-1'])
    life=r.close.allocations(traces['node-1'])[name];value=closes['node-1'];rows=value['rows']
    for event,point in (('ACQUIRED',life['start']),('CLOSE_BEGIN',life['end']-1),('RETURNED',life['end'])):
        rows.append(dict(event=phase+'_BORROW_'+event,owner=name,resourceSequence=point,children=[]))
    rows.sort(key=lambda row:row['resourceSequence']);negatives.renumber(value)
    expected=dict(node='node-1',phase=phase,reference='c'*64,bytes=size,through=life['end']-2)
    expected['before' if phase=='MAINTENANCE' else 'after']=life['start']+(1 if phase=='MAINTENANCE' else -1)
    return traces,closes,[expected]


class DirectExportEvidenceTest(unittest.TestCase):
    def test_all_three_scopes_bind_to_original_extent_and_operation_interval(self):
        for phase in r.close.DIRECT_ROLES:
            with self.subTest(phase=phase):
                result=r.replay(*fixture(phase));self.assertEqual(1,result['directExports'])
                self.assertEqual({phase:1},result['phases']);self.assertEqual(2,result['exportInventory']['ownedAllocations'])
                self.assertEqual(1,result['exportInventory']['sessionOwnedAllocations']);self.assertFalse(result['phase3Complete'])

    def test_each_negative_preserves_its_specific_obligation(self):
        result=negatives.replay(*fixture());self.assertEqual(len(negatives.NEGATIVES),len(result['negatives']))

    def test_original_corruption_never_counts_as_negative_qualification(self):
        data=fixture();data[1]['node-1']['failed']=True
        with patch.object(negatives,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'complete bounded recorder'):negatives.replay(*data)
            mutate.assert_not_called()

    def test_physical_failure_precedes_resource_or_mutation_replay(self):
        with patch.object(negatives.a.collection,'inventory',return_value={}), \
             patch.object(negatives.a,'validate',side_effect=ValueError('original failed')),patch.object(negatives,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'original failed'):negatives.validate('/unused')
            replay.assert_not_called()

    def test_original_extent_is_required_even_with_consistent_accounting(self):
        for phase in r.close.DIRECT_ROLES:
            data=fixture(phase);data[2][0]['bytes']+=1
            with self.assertRaisesRegex(ValueError,'original content extent'):r.replay(*data)

    def test_maintenance_must_span_copy_admission_through_floor_release(self):
        for field in ('before','through'):
            data=fixture('MAINTENANCE');expected=data[2][0]
            expected[field]=0 if field=='before' else 999
            with self.assertRaisesRegex(ValueError,'original maintenance lifetime'):r.replay(*data)

    def test_source_must_follow_forced_grant_and_span_installation(self):
        for field in ('after','through'):
            data=fixture();data[2][0][field]=999
            with self.assertRaisesRegex(ValueError,'original activation lifetime'):r.replay(*data)

    def test_extra_and_missing_local_owners_cannot_be_inferred(self):
        data=fixture();extra=copy.deepcopy(data[2][0]);extra['node']='node-2';data[2].append(extra)
        with self.assertRaisesRegex(ValueError,'missing original local owner'):r.replay(*data)
        data=fixture();data[2].clear()
        with self.assertRaisesRegex(ValueError,'original content/cohort'):r.replay(*data)

    def test_duplicate_expectation_and_wrong_phase_are_rejected(self):
        data=fixture();data[2].append(copy.deepcopy(data[2][0]))
        with self.assertRaisesRegex(ValueError,'duplicate original expectation'):r.replay(*data)
        data=fixture();data[2][0]['phase']='SELECTED'
        with self.assertRaisesRegex(ValueError,'original content/cohort'):r.replay(*data)

    def test_observation_of_zero_usage_cannot_replace_return(self):
        data=fixture();negatives.mutate(*data[:2],'missing-return')
        self.assertEqual(0,data[0]['node-1']['current']['leases'])
        with self.assertRaisesRegex(ValueError,'incomplete direct cleanup'):r.replay(*data)

    def test_old_session_capture_stays_partial_and_is_not_upgraded(self):
        traces,closes=session_fixture();session_export_negatives.mutate(traces,closes,'unclaimed-export')
        self.assertEqual('PARTIAL',r.exports.inspect(traces,closes)['status'])
        with self.assertRaisesRegex(ValueError,'unclaimed allocation'):r.replay(traces,closes,[])

    def test_negatives_do_not_modify_original_evidence(self):
        data=fixture();before=copy.deepcopy(data);negatives.replay(*data);self.assertEqual(before,data)

    def test_malformed_event_type_is_a_validation_rejection(self):
        for event in ([],{},False):
            data=fixture();data[1]['node-1']['rows'][0]['event']=event
            with self.assertRaisesRegex(ValueError,'exact ordered row'):r.replay(*data)


if __name__=='__main__':unittest.main()
