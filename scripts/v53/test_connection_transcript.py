"""Conditional socket-correlation tests, separate from actual transport evidence."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import connection_transcript as e
from . import transport_connection_evidence as native
from . import test_joining_network_evidence as fixture


def trace():
    old,wires,ids,root=fixture.JoiningNetworkEvidenceTest().exchange(True)
    client=dict(id='00000000-0000-0000-0000-000000000011',local=dict(address='127.0.0.1',port=57001),remote=dict(address='127.0.0.1',port=ids[old[1]['node']]['port']))
    server=dict(id='00000000-0000-0000-0000-000000000012',local=copy.deepcopy(client['remote']),remote=copy.deepcopy(client['local']))
    kinds=[e.SEND,e.READ,e.OFFER,e.DELIVER];events=[]
    for at,name in enumerate(kinds):
        row=dict(old[at],scope='connection-test',event=name,request=old[0]['request'],kind=old[0]['kind'],
                 connection=copy.deepcopy(client if at in (0,3) else server))
        if at==3:row['responseKind']=old[2]['responseKind']
        events.append(row)
    wires[0]['connection']=copy.deepcopy(server)
    return events,wires,ids,root


def overlap():
    first,wires,ids,root=trace();second=copy.deepcopy(first);other=copy.deepcopy(wires)
    for row in second:
        client=row['event'] in (e.SEND,e.DELIVER);row['connection']['id']='00000000-0000-0000-0000-0000000000'+('21' if client else '22')
        row['connection']['local' if client else 'remote']['port']=57002
    other[0]['connection']=copy.deepcopy(second[2]['connection'])
    def fail(row,direction):
        return {k:copy.deepcopy(v) for k,v in row.items() if k!='bytes'}|dict(event=e.FAIL,direction=direction,reason='DEADLINE' if direction=='OUTBOUND' else 'IO')
    return [first[0],first[1],fail(first[0],'OUTBOUND'),second[0],second[1],first[2],fail(first[1],'INBOUND'),second[2],second[3]],wires+other,ids,root


class ConnectionTranscriptTest(unittest.TestCase):
    def test_complete_connection_preserves_real_boundaries(self):
        result=e.replay(*trace());self.assertEqual(1,result['attempts']);self.assertEqual([],result['failed'])
        self.assertEqual((0,1,2,3),tuple(result['rows'][0][k] for k in ('sent','received','offered','delivered')))

    def test_late_terminal_and_identical_reply_bind_only_to_original_socket(self):
        result=e.replay(*overlap());old,new=result['rows'];failure=result['failed'][0]
        self.assertEqual(2,result['attempts']);self.assertEqual(0,old['sent']);self.assertIsNone(old['delivered'])
        self.assertEqual(3,new['sent']);self.assertEqual(8,new['delivered']);self.assertEqual(6,failure['serverFailed'])
        self.assertNotEqual(old['clientConnection'],new['clientConnection']);self.assertTrue(old['failedAttempt']);self.assertFalse(new['failedAttempt'])

    def test_response_less_failed_attempt_still_requires_both_terminals(self):
        events,wires,ids,root=overlap();events.pop(5);wires.pop(0)
        result=e.replay(events,wires,ids,root);self.assertEqual(1,len(result['rows']));self.assertFalse(result['failed'][0]['responseOffered'])

    def test_caller_failure_does_not_require_receiver_failure_after_original_offer(self):
        for before_offer in (False,True):
            events,wires,ids,root=trace()
            fail={k:v for k,v in events[0].items() if k!='bytes'}
            fail.update(event=e.FAIL,direction='OUTBOUND',reason='IO')
            events=events[:2]+([fail,events[2]] if before_offer else [events[2],fail])
            result=e.replay(events,wires,ids,root);row=result['rows'][0];failure=result['failed'][0]
            self.assertIsNone(row['delivered']);self.assertTrue(row['failedAttempt'])
            self.assertIsNone(failure['serverFailed']);self.assertIsNone(failure['serverReason'])
            self.assertEqual(3,failure['finished']);self.assertTrue(failure['responseOffered'])

    def test_unread_offer_cannot_become_the_identical_retry_ack(self):
        events,wires,ids,root=overlap();events.pop(6) # Server offered; it did not report a failure.
        result=e.replay(events,wires,ids,root);old,new=result['rows']
        self.assertIsNone(old['delivered']);self.assertEqual(7,new['delivered'])
        self.assertEqual(5,result['failed'][0]['finished'])
        events[-1]['connection']=copy.deepcopy(events[0]['connection'])
        with self.assertRaisesRegex(ValueError,'incomplete invocation'):e.replay(events,wires,ids,root)

    def test_failed_client_still_requires_complete_authenticated_receiver_observation(self):
        for change in ('missing-offer','missing-wire','foreign-wire','changed-response'):
            events,wires,ids,root=overlap();events.pop(6)
            if change=='missing-offer':events.pop(5)
            elif change=='missing-wire':wires.pop(0)
            elif change=='foreign-wire':wires[0]['connection']=copy.deepcopy(wires[1]['connection'])
            else:events[5]['response']='0'*64
            with self.subTest(change=change),self.assertRaises(ValueError):e.replay(events,wires,ids,root)

    def test_identity_does_not_replace_reversed_original_socket_pair(self):
        events,wires,ids,root=trace()
        for row in (events[1],events[2],wires[0]):row['connection']['remote']['port']+=1
        with self.assertRaisesRegex(ValueError,'exact socket pairing'):e.replay(events,wires,ids,root)

    def test_reused_identifier_changed_scope_or_swapped_endpoint_refuses(self):
        for field in ('id','scope','endpoint'):
            events,wires,ids,root=trace()
            if field=='id':events[1]['connection']['id']=events[0]['connection']['id']
            elif field=='scope':events[2]['scope']='restarted-owner'
            else:events[2]['connection']['local'],events[2]['connection']['remote']=events[2]['connection']['remote'],events[2]['connection']['local']
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'invocation changed'):e.replay(events,wires,ids,root)

    def test_different_tokens_cannot_claim_overlapping_reuse_of_one_socket(self):
        events,wires,ids,root=overlap()
        for row in events+wires:
            conn=row['connection']
            for end in ('local','remote'):
                if conn[end]['port']==57002:conn[end]['port']=57001
        with self.assertRaisesRegex(ValueError,'overlapping socket reuse'):e.replay(events,wires,ids,root)

    def test_same_tuple_may_be_reused_only_after_complete_prior_observations(self):
        first,wires,ids,root=trace();second=copy.deepcopy(first);next_wire=copy.deepcopy(wires)
        for row in second+next_wire:
            row['connection']['id']=row['connection']['id'].replace('000011','000021').replace('000012','000022')
        result=e.replay(first+second,wires+next_wire,ids,root);self.assertEqual(2,result['attempts'])

    def test_wrong_route_cannot_be_authorized_by_two_matching_observers(self):
        events,wires,ids,root=trace()
        for row in events:row['connection']['remote' if row['node']=='node-1' else 'local']['port']+=1
        wires[0]['connection']['local']['port']+=1
        with self.assertRaisesRegex(ValueError,'original route identity'):e.replay(events,wires,ids,root)

    def test_false_delivery_of_first_reply_is_not_successful_retry(self):
        events,wires,ids,root=overlap();events[-1]['connection']=copy.deepcopy(events[0]['connection'])
        with self.assertRaisesRegex(ValueError,'incomplete invocation'):e.replay(events,wires,ids,root)

    def test_old_trace_or_partial_metadata_cannot_guess_identity(self):
        events,wires,ids,root=trace();del events[1]['connection']
        with self.assertRaisesRegex(ValueError,'event shape'):e.replay(events,wires,ids,root)
        events,wires,ids,root=trace();del wires[0]['connection']
        with self.assertRaisesRegex(ValueError,'original response shape'):e.replay(events,wires,ids,root)

    def test_duplicate_or_missing_original_response_is_rejected(self):
        events,wires,ids,root=trace()
        for changed,reason in ((wires*2,'duplicate original response'),([], 'missing original response')):
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):e.replay(events,changed,ids,root)

    def test_terminals_cannot_follow_successful_client_read(self):
        events,wires,ids,root=trace();event={k:v for k,v in events[0].items() if k!='bytes'}
        events.append(dict(event,event=e.FAIL,direction='OUTBOUND',reason='IO'))
        with self.assertRaisesRegex(ValueError,'post-read failure unqualified'):e.replay(events,wires,ids,root)

    def test_malformed_addresses_and_boolean_ports_fail_closed(self):
        for value in (True,0,65536,'9001'):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'endpoint shape'):e.endpoint(dict(address='127.0.0.1',port=value))
        for address in ('not-an-ip','127.0.0.1%scope',''):
            with self.subTest(address=address),self.assertRaises(ValueError):e.endpoint(dict(address=address,port=1))
        self.assertEqual(('::1',1),e.endpoint(dict(address='0:0:0:0:0:0:0:1',port=1)))

    def test_invalid_original_stops_before_mutation(self):
        with patch.object(native.n.collection,'inventory',return_value={}),patch.object(native,'validate',side_effect=ValueError('original')),patch.object(native.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^original$'):native.qualify('/unused')
            copied.assert_not_called()

    def test_unrelated_failure_or_accepted_mutation_cannot_qualify(self):
        for error,reason in (({},'mutation accepted'),(ValueError('unrelated'),'unrelated negative')):
            with patch.object(native.n.collection,'inventory',return_value={}),patch.object(native,'validate',side_effect=[{},error]),patch.object(native.shutil,'copytree'),patch.object(native,'mutate'):
                with self.assertRaisesRegex(ValueError,reason):native.qualify('/unused')

    def test_qualification_refuses_original_change(self):
        with patch.object(native.n.collection,'inventory',side_effect=[{},dict(changed=True)]),patch.object(native,'validate',side_effect=[{}]+[ValueError(v) for v in native.NEGATIVES.values()]),patch.object(native.shutil,'copytree'),patch.object(native,'mutate'):
            with self.assertRaisesRegex(ValueError,'qualification changed original'):native.qualify('/unused')

    def test_unknown_negative_cannot_modify_a_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'original').write_bytes(b'original')
            with self.assertRaisesRegex(ValueError,'declared mutation'):native.mutate(root,'unknown')
            self.assertEqual(b'original',(root/'original').read_bytes())

    def test_component_missing_terminal_mutation_removes_all_receiver_outcomes(self):
        events,wires,ids,root=overlap()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'late-response';path.mkdir()
            (path/'events.json').write_bytes(e.f.canonical(events));original=e.f.canonical(wires)
            (path/'wire.json').write_bytes(original);native.mutate(Path(tmp),'missing-server-terminal')
            changed=native.n.transport.load(path/'events.json')
            self.assertEqual(original,(path/'wire.json').read_bytes())
            with self.assertRaisesRegex(ValueError,native.NEGATIVES['missing-server-terminal']):e.replay(changed,wires,ids,root)


if __name__=='__main__':unittest.main()
