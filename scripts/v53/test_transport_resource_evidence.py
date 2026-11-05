"""Conditional exact frame charges and nested lifetimes; real TCP is separate."""
import base64
import copy
import unittest

from . import transport_resource_evidence as r
from . import transport_resource_negatives as negatives
from . import test_connection_transcript as network_fixture
from .test_resource_transitions import trace,charge


def owner(role,identifier):return 'transport-'+role+'-'+identifier


def recount(rows):
    state={}
    for seq,row in enumerate(rows):
        row['sequence']=seq
        for value in row['removed']:state.pop(value['owner'])
        for value in row['added']:state[value['owner']]=value['bytes']
        counts={'CONTROL':len(state)} if state else {}
        row['usage']=dict(metadata=0,staging=0,queued=sum(state.values()),leases=len(state),counts=counts)
    return trace(rows)


def fixture(overlap=False,handler=False):
    events,wires,identities,root=network_fixture.overlap() if overlap else network_fixture.trace()
    if handler:events.pop(5);wires.pop(0)
    rows={node:[dict(event='START',removed=[],added=[])] for node in sorted({v['node'] for v in events})};states={node:{} for node in rows};boundaries=[]
    failures={v['connection']['id'] for v in events if v['event']==r.connections.t.FAIL and v['direction']=='INBOUND'}
    requests={};answers={v['connection']['id']:len(base64.b64decode(v['response'])) for v in wires}
    def add(node,event,key,size=None):
        before=states[node].get(key);removed=[] if event=='RESERVE' else [charge('CONTROL',key,before)]
        added=[] if event=='RELEASE' else [charge('CONTROL',key,size)]
        rows[node].append(dict(event=event,removed=removed,added=added))
        if added:states[node][key]=size
        else:del states[node][key]
    for at,event in enumerate(events):
        node=event['node'];identifier=event['connection']['id'];point=event['event'];post=[]
        if point==r.connections.t.SEND:
            size=len(base64.b64decode(event['bytes']));requests[event['request']]=size
            add(node,'RESERVE',owner('request-send',identifier),size)
            post=[('RESERVE',owner('response-read',identifier),r.HEADER)]
        elif point==r.connections.t.READ:
            key=owner('request-read',identifier);add(node,'RESERVE',key,r.HEADER);add(node,'CONTROL_GROW',key,requests[event['request']])
        elif point==r.connections.t.OFFER:
            key=owner('response-send',identifier);add(node,'RESERVE',key,answers[identifier]);post=[('RELEASE',key,None)]
            if identifier not in failures:post.append(('RELEASE',owner('request-read',identifier),None))
        elif point==r.connections.t.DELIVER:
            size=len(base64.b64decode(next(v['response'] for v in wires if r.connections.t.sha(base64.b64decode(v['response']))==event['response'])))
            add(node,'CONTROL_GROW',owner('response-read',identifier),size)
            post=[('RELEASE',owner('response-read',identifier),None),('RELEASE',owner('request-send',identifier),None)]
        elif event['direction']=='OUTBOUND':
            add(node,'RELEASE',owner('response-read',identifier));add(node,'RELEASE',owner('request-send',identifier))
        else:post=[('RELEASE',owner('request-read',identifier),None)]
        snapshot=recount(copy.deepcopy(rows[node]));seq=len(rows[node])-1
        boundaries.append(dict(eventIndex=at,node=node,sequence=seq,usage=copy.deepcopy(snapshot['current'])))
        for args in post:add(node,*args)
    traces={node:recount(value) for node,value in rows.items()}
    return events,wires,traces,boundaries,identities,root


def change_extent(values,role,delta):
    events,wires,traces,boundaries,*_=values
    node,trace=next((n,t) for n,t in traces.items() if any(any(v['owner'].startswith('transport-'+role+'-') for v in x['added']) for x in t['changes']))
    key=next(v['owner'] for x in trace['changes'] for v in x['added'] if v['owner'].startswith('transport-'+role+'-'))
    for row in trace['changes']:
        for value in row['removed']+row['added']:
            if value['owner']==key and (role.endswith('-send') or value['bytes']!=r.HEADER):value['bytes']+=delta
    traces[node]=recount(trace['changes'])
    for boundary in boundaries:
        if boundary['node']==node:boundary['usage']=copy.deepcopy(traces[node]['changes'][boundary['sequence']]['usage'])


class TransportResourceEvidenceTest(unittest.TestCase):
    def test_original_success_and_both_late_retry_failures_have_exact_frame_lifetimes(self):
        for overlap,handler,total in ((False,False,4),(True,False,8),(True,True,7)):
            result=r.replay(*fixture(overlap,handler))
            self.assertEqual(total,result['boundFrameLifetimes']);self.assertTrue(result['allTransportFramesQualified'])
            self.assertFalse(result['controlLifetimesQualified']);self.assertFalse(result['wholeRuntimeResourcesQualified'])

    def test_same_length_identical_retry_cannot_use_original_lease(self):
        data=fixture(True);events,_,traces,*_=data;first=events[0]['connection']['id'];second=events[3]['connection']['id']
        for change in traces['node-1']['changes']:
            for value in change['removed']+change['added']:value['owner']=value['owner'].replace(second,first)
        with self.assertRaisesRegex(ValueError,'reused frame lease'):r.replay(*data)

    def test_original_send_size_is_not_accepted_from_consistent_forged_counters(self):
        for role in ('request-send','response-send'):
            data=fixture();change_extent(data,role,1)
            with self.subTest(role=role),self.assertRaisesRegex(ValueError,'original send buffer'):r.replay(*data)

    def test_receive_growth_must_match_original_wire_length(self):
        for role in ('request-read','response-read'):
            data=fixture();change_extent(data,role,1)
            with self.subTest(role=role),self.assertRaisesRegex(ValueError,'original frame extent'):r.replay(*data)

    def test_reply_cannot_outlive_its_caller_or_receiver_request(self):
        for node,reason in (('node-1','caller'),('node-4','receiver')):
            data=fixture();rows=data[2][node]['changes'];rows[-2],rows[-1]=rows[-1],rows[-2];data[2][node]=recount(rows)
            with self.subTest(node=node),self.assertRaisesRegex(ValueError,reason+' nested release order'):r.replay(*data)

    def test_failed_caller_terminal_requires_release_and_failed_receiver_requires_live_request(self):
        data=fixture(True)
        # Point a terminal at an earlier but internally consistent snapshot.
        data[3][2]['sequence']=2;data[3][2]['usage']=copy.deepcopy(data[2]['node-1']['changes'][2]['usage'])
        with self.assertRaisesRegex(ValueError,'not closed at terminal'):r.replay(*data)
        data=fixture(True);seq=data[3][6]['sequence']+1;data[3][6]['sequence']=seq;data[3][6]['usage']=copy.deepcopy(data[2]['node-4']['changes'][seq]['usage'])
        with self.assertRaisesRegex(ValueError,'not live at boundary'):r.replay(*data)

    def test_unobserved_attempt_is_an_explicit_gap_never_an_identical_retry(self):
        data=fixture();rows=data[2]['node-1']['changes'];key=owner('request-send','00000000-0000-0000-0000-000000000099')
        value=charge('CONTROL',key,100);rows.extend([dict(event='RESERVE',removed=[],added=[value]),dict(event='RELEASE',removed=[value],added=[])])
        data[2]['node-1']=recount(rows)
        with self.assertRaisesRegex(ValueError,'unobserved frame lifetimes'):r.replay(*data)
        result=r.replay(*data,require_all_frames=False)
        self.assertEqual(1,len(result['unobservedFrameLifetimes']));self.assertFalse(result['allTransportFramesQualified'])

    def test_legacy_random_lease_names_are_not_matched_by_size(self):
        data=fixture()
        for row in data[2]['node-1']['changes']:
            for value in row['added']+row['removed']:
                if value['owner'].startswith('transport-request-send-'):value['owner']=value['owner'].removeprefix('transport-request-send-')
        with self.assertRaisesRegex(ValueError,'unbound legacy frame lease'):r.replay(*data)

    def test_other_service_control_work_is_counted_but_not_qualified(self):
        data=fixture();rows=data[2]['node-1']['changes'];value=charge('CONTROL','transfer-service-foreign',32768)
        rows.extend([dict(event='RESERVE',removed=[],added=[value]),dict(event='RELEASE',removed=[value],added=[])])
        data[2]['node-1']=recount(rows);result=r.replay(*data)
        self.assertEqual(1,result['otherControlReservations']);self.assertFalse(result['controlLifetimesQualified'])

    def test_missing_checkpoints_and_boolean_positions_fail(self):
        for change in ('missing','boolean','owner','usage'):
            data=fixture()
            if change=='missing':data[3].pop()
            elif change=='boolean':data[3][0]['eventIndex']=False
            elif change=='owner':data[3][0]['node']='node-2'
            else:data[3][0]['usage']['queued']+=1
            with self.subTest(change=change),self.assertRaises(ValueError):r.replay(*data)

    def test_original_network_corruption_fails_before_resource_success(self):
        data=fixture();data[0][-1]['response']='0'*64
        with self.assertRaisesRegex(ValueError,'connection delivered response binding'):r.replay(*data)

    def test_all_negative_mutations_hit_their_declared_reason_on_both_retry_cases(self):
        for handler in (False,True):
            results=negatives.replay(fixture(True,handler))
            self.assertEqual(list(negatives.NEGATIVES),[v['case'] for v in results])

    def test_corrupt_original_is_not_sixteen_successful_rejections(self):
        data=fixture(True);data[0][-1]['response']='0'*64
        with self.assertRaisesRegex(ValueError,'connection delivered response binding'):negatives.replay(data)


if __name__=='__main__':unittest.main()
