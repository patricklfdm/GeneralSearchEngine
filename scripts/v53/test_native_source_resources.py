"""Native ownership policy and strict legacy/connection compatibility."""
import copy
import unittest
from unittest.mock import patch
from . import native_source_resources as r
from . import native_dispatch_evidence as dispatch
from . import native_source_resource_negatives as negatives
from .test_source_control_resource_evidence import lifetime
from .test_transport_resource_evidence import recount
from .test_connection_transcript import trace,overlap


class NativeSourceResourcesTest(unittest.TestCase):
    def test_cancelled_logical_request_may_end_before_its_transport_copy(self):
        logical=dict(start=1,end=3,initial=1200,growth=[]);copied=dict(start=2,end=7,initial=1200,growth=[])
        r.request_handoff(logical,copied,1200)

    def test_copy_must_be_reserved_while_the_original_request_is_still_owned(self):
        for start in (0,1,3,4):
            with self.subTest(start=start),self.assertRaisesRegex(ValueError,'request copy handoff'):
                r.request_handoff(dict(start=1,end=3,initial=1200,growth=[]),dict(start=start,end=7,initial=1200,growth=[]),1200)

    def test_both_request_and_copy_extents_come_from_original_bytes(self):
        for first in (False,True):
            logical=dict(start=1,end=3,initial=1200,growth=[]);copied=dict(start=2,end=7,initial=1200,growth=[])
            (logical if first else copied)['initial']+=1
            with self.subTest(first=first),self.assertRaises(ValueError):r.request_handoff(logical,copied,1200)

    def test_distinct_allocations_can_recur_for_one_original_binding(self):
        traces=lifetime();rows=traces['node-1']['changes'];repeat=copy.deepcopy(rows[1:])
        for row in repeat:
            for value in row['removed']+row['added']:value['owner']=value['owner'][:-1]+'2'
        traces['node-1']=recount(rows+repeat);leases,legacy,other=r.scan(traces)
        self.assertEqual((2,0,0),(len(leases),len(legacy),other))
        self.assertEqual(1,len({v['binding'] for v in leases.values()}))

    def test_reused_allocation_is_not_a_new_service_generation(self):
        traces=lifetime();rows=traces['node-1']['changes'];traces['node-1']=recount(rows+copy.deepcopy(rows[1:]))
        with self.assertRaisesRegex(ValueError,'reused allocation'):r.scan(traces)

    def test_checkpoint_trace_has_the_same_bounded_cache_growth_contract(self):
        leases,_,_=r.scan(lifetime('joining-checkpoint-trace',1024,34000))
        self.assertEqual('joining-checkpoint-trace',next(iter(leases.values()))['role'])
        self.assertEqual([(2,34000)],next(iter(leases.values()))['growth'])

    def test_legacy_owners_are_explicitly_unobserved_only_in_compatibility_mode(self):
        traces=lifetime()
        for row in traces['node-1']['changes']:
            for v in row['removed']+row['added']:v['owner']='source-request-00000000-0000-0000-0000-000000000001'
        result=r.replay([],[],traces,[],{},'a'*64,require_complete=False)
        self.assertEqual('NOT_OBSERVED',result['status']);self.assertEqual(1,result['legacyReservations'])
        self.assertFalse(result['allObservedSourceBuffersBound'])
        with self.assertRaisesRegex(ValueError,'required original bindings absent'):r.replay([],[],traces,[],{},'a'*64)

    def test_fully_missing_collection_does_not_pass_strict_mode(self):
        with self.assertRaisesRegex(ValueError,'required original bindings absent'):r.replay([],[],{},[],{},'a'*64)

    def test_boolean_policy_is_explicit(self):
        with self.assertRaisesRegex(ValueError,'completeness policy'):r.replay([],[],{},[],{},'a'*64,require_complete=0)

    def test_original_failure_cannot_count_as_negative_rejections(self):
        with patch.object(r,'replay',side_effect=ValueError('invalid original')),patch.object(negatives,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'invalid original'):negatives.replay([])
            mutate.assert_not_called()

    def test_stable_semantic_reader_first_validates_all_actual_socket_attempts(self):
        for fixture in (trace,overlap):
            events,wires,ids,root=fixture();before=copy.deepcopy((events,wires))
            projected_events,projected_rows=dispatch.successful_wire_observations(events,wires,ids,root)
            self.assertEqual(before,(events,wires))
            self.assertEqual(len(events),len(projected_events));self.assertEqual(len(wires),len(projected_rows))
            self.assertTrue(all('connection' not in v for v in projected_events+projected_rows))

    def test_projection_cannot_hide_missing_or_forged_connections(self):
        for mode in ('partial','endpoint','response'):
            events,wires,ids,root=trace()
            if mode=='partial':events[1].pop('connection')
            elif mode=='endpoint':events[1]['connection']['remote']['port']+=1
            else:wires[0]['connection']['id']='00000000-0000-0000-0000-000000000099'
            with self.subTest(mode=mode),self.assertRaises(ValueError):dispatch.successful_wire_observations(events,wires,ids,root)

    def test_wholly_legacy_semantic_rows_stay_unchanged(self):
        events,wires,ids,root=trace()
        for v in events+wires:v.pop('connection')
        self.assertEqual((events,wires),dispatch.successful_wire_observations(events,wires,ids,root))


if __name__=='__main__':unittest.main()
