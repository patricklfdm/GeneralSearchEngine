"""Native ownership policy and strict legacy/connection compatibility."""
import copy
import base64
import unittest
from unittest.mock import patch
from . import native_source_resources as r
from . import native_dispatch_evidence as dispatch
from . import native_source_resource_negatives as negatives
from .test_source_control_resource_evidence import lifetime
from .test_transport_resource_evidence import recount
from .test_connection_transcript import trace,overlap
from . import test_transport_resource_evidence as transport_fixture
from .test_resource_transitions import charge


def discovery_probe():
    """One observed STATUS_PROBE with a source-owned logical request buffer."""
    events,wires,identities,root=trace()
    _,q=r.network.t.wire(wires[0]['request']);_,a=r.network.t.wire(wires[0]['response'])
    q['payload']=dict(nonce=q['trace']);a['payload']=dict(reason='NOT_READY',promised=q['ballot'])
    f=r.component.physical.e.f
    request=f.encode('wire','STATUS_PROBE',q);response=f.encode('wire','REJECT',a)
    digest=r.component.physical.e.digest(request);answer=r.component.physical.e.digest(response)
    wires[0].update(request=base64.b64encode(request).decode(),response=base64.b64encode(response).decode())
    for row in events:
        row.update(kind='STATUS_PROBE',request=digest)
        if 'bytes' in row:row['bytes']=wires[0]['request']
        if 'response' in row:row.update(response=answer,responseKind='REJECT')
    with patch.object(transport_fixture.network_fixture,'trace',return_value=(events,wires,identities,root)):
        data=transport_fixture.fixture()
    rows=data[2]['node-1']['changes']
    logical=charge('CONTROL','source-request-'+digest+'-00000000-0000-0000-0000-000000000001',len(request))
    rows.insert(1,dict(event='RESERVE',added=[logical],removed=[]))
    rows.append(dict(event='RELEASE',added=[],removed=[logical]))
    data[2]['node-1']=recount(rows)
    for boundary in data[3]:
        if boundary['node']=='node-1':
            boundary['sequence']+=1;boundary['usage']=copy.deepcopy(rows[boundary['sequence']]['usage'])
    return data


def unsent_discovery_probe():
    data=discovery_probe();sent=data[0][0];node=sent['node'];source=data[2][node]['changes'][1]['added'][0]
    rows=[dict(event='START',added=[],removed=[]),dict(event='RESERVE',added=[source],removed=[])]
    events=[];boundaries=[]
    for i in range(2):
        identifier=f'00000000-0000-0000-0000-{80+i:012d}'
        copied=charge('CONTROL','transport-request-send-'+identifier,source['bytes'])
        rows.extend([dict(event='RESERVE',added=[copied],removed=[]),dict(event='RELEASE',added=[],removed=[copied])])
        events.append(dict(node=node,event='NETWORK_UNSENT_FAILED',invocation=identifier,reason='IO',
                           request=sent['request'],kind=sent['kind'],bytes=sent['bytes']))
        boundaries.append(dict(eventIndex=i,node=node,sequence=len(rows)-1))
    rows.append(dict(event='RELEASE',added=[],removed=[source]));traces={node:recount(rows)}
    for boundary in boundaries:boundary['usage']=copy.deepcopy(rows[boundary['sequence']]['usage'])
    return events,[],traces,boundaries,data[4],data[5]


class NativeSourceResourcesTest(unittest.TestCase):
    def test_discovery_status_probe_binds_its_original_logical_request_and_copy(self):
        data=discovery_probe();before=copy.deepcopy(data);result=r.replay(*data)
        self.assertEqual(1,result['logicalRequests']);self.assertEqual(1,result['boundReservations'])
        self.assertTrue(result['allObservedSourceBuffersBound']);self.assertEqual([],result['unobservedReservations'])
        self.assertEqual(before,data)

    def test_discovery_probe_cannot_borrow_another_request_hash_size_or_copy(self):
        for mutation in ('hash','size','copy'):
            data=discovery_probe();rows=data[2]['node-1']['changes']
            for row in rows:
                for value in row['removed']+row['added']:
                    if value['owner'].startswith('source-request-'):
                        if mutation=='hash':value['owner']='source-request-'+'f'*64+value['owner'][-37:]
                        elif mutation=='size':value['bytes']+=1
                    elif mutation=='copy' and value['owner'].startswith('transport-request-send-'):
                        value['owner']='transport-request-send-00000000-0000-0000-0000-000000000099'
            data[2]['node-1']=recount(rows)
            for boundary in data[3]:
                if boundary['node']=='node-1':boundary['usage']=copy.deepcopy(rows[boundary['sequence']]['usage'])
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):r.replay(*data)

    def test_unobserved_original_request_stays_a_gap_even_when_size_matches(self):
        data=discovery_probe();rows=data[2]['node-1']['changes'];other=copy.deepcopy(rows[1]['added'][0])
        other['owner']=other['owner'][:-1]+'2'
        rows.extend([dict(event='RESERVE',added=[other],removed=[]),dict(event='RELEASE',added=[],removed=[other])])
        data[2]['node-1']=recount(rows)
        with self.assertRaisesRegex(ValueError,'unobserved source reservations'):r.replay(*data)
        self.assertEqual(1,len(r.replay(*data,require_complete=False)['unobservedReservations']))

    def test_discovery_unsent_retries_bind_each_copy_to_one_logical_request(self):
        data=unsent_discovery_probe();before=copy.deepcopy(data)
        result=r.replay(*data);transport=r.frames.replay(*data)
        self.assertEqual((1,2),(result['logicalRequests'],result['originalSourceAttempts']))
        self.assertTrue(result['allObservedSourceBuffersBound']);self.assertEqual(2,len(transport['unsentAttempts']))
        self.assertEqual(before,data)

    def test_unsent_source_observations_cannot_be_omitted_or_borrow_a_later_copy(self):
        for mode in ('missing','late-copy','hash'):
            data=unsent_discovery_probe()
            if mode=='missing':data[0].clear();data[3].clear()
            elif mode=='late-copy':data[0][0]['invocation']=data[0][1]['invocation']
            else:data[0][0]['request']='f'*64
            with self.subTest(mode=mode),self.assertRaises(ValueError):r.replay(*data)

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
