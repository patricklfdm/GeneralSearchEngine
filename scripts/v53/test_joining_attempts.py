"""Conditional terminal-observation checks; original TCP replay is separate."""
import base64
import copy
import unittest
from unittest.mock import patch

from . import joining_attempts as e
from . import joining_transcript as t
from . import transport_attempt_evidence as native
from . import test_joining_network_evidence as network_fixture
from .test_joining_source_loss import trace as loss_trace


def failed_trace(scoped=False):
    events,wires,ids,root=network_fixture.JoiningNetworkEvidenceTest().exchange(scoped)
    send,received=events[:2]
    def terminal(row,direction):
        return {k:v for k,v in row.items() if k!='bytes'}|dict(event=e.EVENT,direction=direction,reason='IO')
    failed=[copy.deepcopy(send),copy.deepcopy(received),terminal(received,'INBOUND'),terminal(send,'OUTBOUND')]
    return failed+events,wires,ids,root


class JoiningAttemptsTest(unittest.TestCase):
    def test_response_less_controls_are_explicit_failures_never_replies(self):
        for scoped in (False,True):
            events,wires,ids,root=failed_trace(scoped);failed=[]
            rows=t.causal(events,wires,ids,root,failed=failed)
            self.assertEqual(1,len(rows));self.assertEqual(1,len(failed))
            self.assertEqual(4,rows[0]['sent']);self.assertEqual(3,failed[0]['finished'])
            self.assertEqual(1,failed[0]['received']);self.assertFalse(failed[0]['withheldResponse'])

    def test_missing_original_terminals_are_not_inferred_from_later_success(self):
        events,wires,ids,root=failed_trace();events=[v for v in events if v['event']!=e.EVENT]
        with self.assertRaisesRegex(ValueError,'^joining network ambiguous overlapping retry$'):t.causal(events,wires,ids,root)

    def test_sender_and_receiver_terminal_are_independently_required(self):
        for direction,reason in [('OUTBOUND','missing caller terminal'),('INBOUND','missing receiver terminal')]:
            events,wires,ids,root=failed_trace();events=[v for v in events if v.get('direction')!=direction]
            with self.subTest(direction=direction),self.assertRaisesRegex(ValueError,'^joining failure '+reason+'$'):
                t.causal(events,wires,ids,root)

    def test_never_received_control_requires_only_actual_sender_failure(self):
        events,wires,ids,root=failed_trace();events=[events[0],events[3],*events[4:]];failed=[]
        rows=t.causal(events,wires,ids,root,failed=failed)
        self.assertEqual(1,len(rows));self.assertIsNone(failed[0]['received']);self.assertIsNone(failed[0]['serverFailed'])

    def test_foreign_owners_and_scopes_cannot_end_an_attempt(self):
        for at,field,value,reason in [(2,'node','node-3','receiver lifetime'),(3,'node','node-3','sender lifetime'),
                                       (2,'scope','other','receiver lifetime'),(3,'scope','other','sender lifetime')]:
            events,wires,ids,root=failed_trace(True);events[at][field]=value
            with self.subTest(at=at,field=field),self.assertRaisesRegex(ValueError,'^joining failure '+reason+'$'):
                t.causal(events,wires,ids,root)

    def test_duplicate_terminal_cannot_hide_second_attempt(self):
        for at,side in ((2,'inbound'),(3,'outbound')):
            events,wires,ids,root=failed_trace();events.insert(at,dict(events[at]))
            with self.subTest(side=side),self.assertRaisesRegex(ValueError,'^joining duplicate '+side+' terminal$'):
                t.causal(events,wires,ids,root)

    def test_late_receiver_terminal_cannot_be_borrowed_by_an_identical_retry(self):
        events,wires,ids,root=failed_trace();terminal=events.pop(2);events.append(terminal)
        with self.assertRaisesRegex(ValueError,'^joining failure missing caller terminal$'):t.causal(events,wires,ids,root)

    def test_missing_failed_transfer_is_not_reclassified_as_a_control(self):
        events,_,ids,root=failed_trace();kind,q=e.wire(events[0]['bytes'])
        q['payload']=dict(id=q['trace'],action='REQUEST',offset=0,digest='f'*64,bytes='')
        raw=e.phase.f.encode('wire','CHUNK',q)
        for row in events[:4]:row.update(kind='CHUNK',request=e.sha(raw))
        events[0]['bytes']=base64.b64encode(raw).decode()
        with self.assertRaisesRegex(ValueError,'^joining failure unqualified transfer attempt$'):t.causal(events[:4],[],ids,root)

    def test_unknown_failure_reason_is_rejected(self):
        events,wires,ids,root=failed_trace();events[3]['reason']='SUCCESS'
        with self.assertRaisesRegex(ValueError,'^joining failure observation shape$'):t.causal(events,wires,ids,root)

    def test_malformed_terminal_fields_fail_with_a_validation_reason(self):
        for field in ('node','request','kind','reason','direction','scope'):
            for value in ([],{},None,1,''):
                events,wires,ids,root=failed_trace(True);events[3][field]=value
                with self.subTest(field=field,value=value),self.assertRaisesRegex(ValueError,'^joining failure observation shape$'):
                    t.causal(events,wires,ids,root)

    def test_post_delivery_failure_is_not_silently_treated_as_success(self):
        events,wires,ids,root=network_fixture.JoiningNetworkEvidenceTest().exchange()
        send,read=events[:2]
        events.extend([{k:v for k,v in read.items()}|dict(event=e.EVENT,direction='INBOUND',reason='IO'),
                       {k:v for k,v in send.items() if k!='bytes'}|dict(event=e.EVENT,direction='OUTBOUND',reason='IO')])
        with self.assertRaisesRegex(ValueError,'^joining failure unqualified response delivery$'):t.causal(events,wires,ids,root)

    def test_existing_declared_source_loss_can_bind_both_terminals(self):
        for kind in ('SOURCE_OFFER','CHUNK','TRANSFER_COMMIT'):
            events,wires,ids,root=loss_trace(kind)
            lost=next(v for v in wires if v['withheld']);digest=e.sha(base64.b64decode(lost['request']))
            at=next(i for i,v in enumerate(events) if v['event']=='WIRE_RESPONSE' and v['request']==digest)
            send=next(v for v in events if v.get('request')==digest and v['event'] in e.SENDS)
            received=next(v for v in events if v.get('request')==digest and v['event'] in e.READS)
            server={k:v for k,v in received.items()}|dict(event=e.EVENT,direction='INBOUND',reason='IO')
            client={k:v for k,v in send.items() if k!='bytes'}|dict(event=e.EVENT,direction='OUTBOUND',reason='IO')
            events[at+1:at+1]=[server,client];failed=[]
            rows=t.causal(events,wires,ids,root,failed=failed)
            self.assertEqual(1,len(failed));self.assertTrue(failed[0]['withheldResponse'])
            self.assertEqual(1,t.transfers(rows)['exactTransferRetries'])

    def test_invalid_native_original_cannot_count_as_negatives(self):
        with patch.object(native,'validate',side_effect=ValueError('invalid original')),patch.object(native.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):native.qualify('/unused')
            copied.assert_not_called()

    def test_unrelated_native_negative_failure_is_not_accepted(self):
        with patch.object(native,'validate',side_effect=[{},ValueError('unrelated')]),patch.object(native.collection,'inventory',return_value={}),patch.object(native.shutil,'copytree'),patch.object(native,'mutate'):
            with self.assertRaisesRegex(ValueError,'^transport attempt unrelated negative:'):native.qualify('/unused')

    def test_qualification_cannot_change_original_bytes(self):
        with patch.object(native,'validate',return_value={}),patch.object(native,'NEGATIVES',{}),patch.object(native.collection,'inventory',side_effect=[{},dict(changed=True)]):
            with self.assertRaisesRegex(ValueError,'^transport attempt qualification changed original$'):native.qualify('/unused')


if __name__=='__main__':unittest.main()
