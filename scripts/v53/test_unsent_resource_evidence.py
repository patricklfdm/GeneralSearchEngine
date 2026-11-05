"""Conditional exact unsent frame identities, original bytes and terminal ownership."""
import base64
import copy
import unittest
from unittest.mock import patch
from . import transport_resource_evidence as r,unsent_resource_evidence as component
from . import unsent_resource_negatives as negatives
from . import test_transport_resource_evidence as fixtures
from .test_resource_transitions import charge


def fixture():
    data=fixtures.fixture();events,wires,traces,boundaries,identities,root=data
    sent=events[0];node=sent['node'];prefix=[];failures=[];points=[]
    for at in range(2):
        identifier=f'00000000-0000-0000-0000-{at+80:012d}'
        value=charge('CONTROL',fixtures.owner('request-send',identifier),len(base64.b64decode(sent['bytes'])))
        prefix.extend([dict(event='RESERVE',removed=[],added=[value]),dict(event='RELEASE',removed=[value],added=[])])
        failures.append(dict(node=node,event=r.UNSENT,invocation=identifier,reason='IO',request=sent['request'],kind=sent['kind'],bytes=sent['bytes']))
        points.append(dict(eventIndex=at,node=node,sequence=2*(at+1),usage={}))
    traces[node]['changes'][1:1]=prefix
    for point in boundaries:
        point['eventIndex']+=2
        if point['node']==node:point['sequence']+=4
    events[:0]=failures;boundaries[:0]=points;recount(data);return data


def recount(data):
    for node,trace in data[2].items():data[2][node]=fixtures.recount(trace['changes'])
    for point in data[3]:point['usage']=copy.deepcopy(data[2][point['node']]['changes'][point['sequence']]['usage'])


class UnsentResourceEvidenceTest(unittest.TestCase):
    def test_all_negatives_reject_their_exact_reason_after_original_passes(self):
        data=fixture();before=copy.deepcopy(data);results=negatives.replay(data)
        self.assertEqual(list(negatives.NEGATIVES),[v['case'] for v in results]);self.assertEqual(before,data)

    def test_invalid_original_cannot_count_as_successful_negative_replay(self):
        data=fixture();data[2]['node-1']['truncated']=True
        with patch.object(negatives,'mutate') as mutate,self.assertRaisesRegex(ValueError,'incomplete observation'):negatives.replay(data)
        mutate.assert_not_called()

    def test_identical_requests_have_distinct_unsent_and_connected_leases(self):
        data=fixture();before=copy.deepcopy(data);result=r.replay(*data)
        self.assertEqual(2,len(result['unsentAttempts']));self.assertEqual(6,result['boundFrameLifetimes'])
        self.assertTrue(result['allTransportFramesQualified']);self.assertEqual(before,data)
        self.assertFalse(result['controlLifetimesQualified']);self.assertFalse(result['wholeRuntimeResourcesQualified'])

    def test_omitted_unsent_event_remains_an_explicit_gap(self):
        data=fixture();data[0][0]['event']='UNOBSERVED'
        with self.assertRaisesRegex(ValueError,'unobserved frame lifetimes'):r.replay(*data)
        result=r.replay(*data,require_all_frames=False)
        self.assertEqual(1,len(result['unobservedFrameLifetimes']));self.assertFalse(result['allTransportFramesQualified'])

    def test_crossed_identical_failed_attempts_cannot_borrow_later_release(self):
        data=fixture();data[0][0]['invocation'],data[0][1]['invocation']=data[0][1]['invocation'],data[0][0]['invocation']
        with self.assertRaisesRegex(ValueError,'not closed at terminal'):r.replay(*data)

    def test_duplicate_or_connected_invocation_cannot_be_used_as_unsent(self):
        for connected in (False,True):
            data=fixture();data[0][1]['invocation']=data[0][2]['connection']['id'] if connected else data[0][0]['invocation']
            with self.subTest(connected=connected),self.assertRaisesRegex(ValueError,'unsent reused invocation'):r.replay(*data)

    def test_request_hash_kind_root_or_original_sender_cannot_be_relabelled(self):
        for field,value in (('request','f'*64),('kind','CHUNK'),('node','node-4')):
            data=fixture();data[0][0][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'unsent original request'):r.replay(*data)
        data=list(fixture());data[-1]='f'*64
        # Connected admission also checks root before this narrower binding.
        with self.assertRaises(ValueError):r.replay(*data)

    def test_unknown_failure_extra_connection_and_malformed_ids_fail(self):
        for key,value in (('reason','PASS'),('connection',{}),('invocation','0'*36),('scope','')):
            data=fixture();data[0][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):r.replay(*data)

    def test_consistent_wrong_extent_does_not_replace_original_request_length(self):
        data=fixture();key=fixtures.owner('request-send',data[0][0]['invocation'])
        for row in data[2]['node-1']['changes']:
            for value in row['removed']+row['added']:
                if value['owner']==key:value['bytes']+=1
        recount(data)
        with self.assertRaisesRegex(ValueError,'original send buffer'):r.replay(*data)

    def test_terminal_must_follow_original_lease_release(self):
        data=fixture();data[3][0]['sequence']-=1;recount(data)
        with self.assertRaisesRegex(ValueError,'not closed at terminal'):r.replay(*data)

    def test_receive_buffer_cannot_be_attached_to_unwritten_request(self):
        data=fixture();key=fixtures.owner('response-read',data[0][0]['invocation']);value=charge('CONTROL',key,r.HEADER)
        data[2]['node-1']['changes'].extend([dict(event='RESERVE',removed=[],added=[value]),dict(event='RELEASE',removed=[value],added=[])])
        recount(data)
        with self.assertRaisesRegex(ValueError,'foreign role on observed connection'):r.replay(*data)

    def test_unsent_record_without_actual_reserved_buffer_is_rejected(self):
        data=fixture();data[0][0]['invocation']='00000000-0000-0000-0000-000000000099'
        with self.assertRaisesRegex(ValueError,'missing original frame lease'):r.replay(*data)

    def test_component_requires_original_bootstrap_before_accounting(self):
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in ('original-plan.gsbp','original-application.image','wire.json','events.json'):(root/name).touch()
            for name in ('initial','after',r.accounting.DIRECTORY):(root/name).mkdir()
            with patch.object(r.component.n.b,'original',side_effect=ValueError('bad original')),patch.object(r.accounting,'load') as load:
                with self.assertRaisesRegex(ValueError,'bad original'):component.case(root,component.CASES[0])
            load.assert_not_called()


if __name__=='__main__':unittest.main()
