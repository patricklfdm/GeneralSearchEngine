"""Small encoded traces exercise refusal boundaries, not native qualification."""
import base64
import copy
import unittest

from . import joining_source_loss as loss
from . import joining_network_evidence as n
from . import test_joining_phase_evidence as phase_fixture
from . import test_joining_network_evidence as network_fixture


def trace(kind='SOURCE_OFFER'):
    _,_,identities,root,q,_=phase_fixture.JoiningPhaseEvidenceTest().wire()
    q.update(sender=identities['node-4'],recipient=identities['node-1'])
    arm=dict(node='node-4',scope='learner-source',event=loss.ARM,kind=kind,started=123,budget=12*60*10**9)
    events=[arm];wires=[]
    for template in network_fixture.JoiningNetworkEvidenceTest().transfer():
        request=dict(q,sequence=template['request']['sequence'],payload=dict(template['request']['payload'],id=q['trace']))
        response=dict(request,sender=request['recipient'],recipient=request['sender'],payload=dict(template['response']['payload'],id=q['trace']))
        qr=n.f.encode('wire',template['kind'],request);ar=n.f.encode('wire',template['answer'],response)
        wire=dict(request=base64.b64encode(qr).decode(),response=base64.b64encode(ar).decode(),withheld=False)
        send=dict(node='node-4',scope='learner-source',event='BEFORE_REQUEST_WRITE',kind=template['kind'],request=n.sha(qr),bytes=wire['request'])
        receive=dict(node='node-1',event='NETWORK_REQUEST',kind=template['kind'],request=n.sha(qr))
        offer=dict(node='node-1',event='WIRE_RESPONSE',request=n.sha(qr),response=n.sha(ar))
        delivered=dict(node='node-4',scope='learner-source',event='AFTER_RESPONSE_READ',kind=template['kind'],request=n.sha(qr),response=n.sha(ar),responseKind=template['answer'])
        if template['answer']==kind:
            events.extend(copy.deepcopy([send,receive,offer]));wires.append(dict(wire,withheld=True))
        events.extend([send,receive,offer,delivered]);wires.append(wire)
    events.append(dict(arm,event=loss.DONE))
    return events,wires,identities,root


class JoiningSourceLossTest(unittest.TestCase):
    def test_all_three_replies_recover_without_inventing_delivery_or_duplicating_content(self):
        for kind in loss.KINDS:
            with self.subTest(kind=kind):
                events,wires,ids,root=trace(kind);rows=n.causal(events,wires,ids,root)
                lost,retry=loss.requests(events,rows)[0]
                self.assertIsNone(lost['delivered']);self.assertIsNotNone(retry['delivered'])
                self.assertEqual(3,sum(v['delivered'] is not None for v in rows))
                contents=[];result=n.transfers(rows,contents=contents)
                self.assertEqual(1,result['committedTransfers']);self.assertEqual(1,result['exactTransferRetries'])
                self.assertEqual([b'original transfer'],[v['raw'] for v in contents])

    def test_undeclared_loss_is_rejected_in_the_shared_phase_reader(self):
        events,wires,ids,root=trace()
        with self.assertRaisesRegex(ValueError,'^joining original wire row$'):n.phase.exchanges(events[1:-1],wires,ids,root)

    def test_exact_declaration_requires_original_kind_scope_start_and_budget(self):
        for field,value in [('kind','ACCEPT_ACK'),('scope','renewed-client'),('started',True),('started',2**63),('budget',13*60*10**9),('node','node-2')]:
            events,_,_,_=trace();events[0][field]=value;events[-1][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'^joining source loss exact declaration$'):loss.declaration(events)
        events,_,_,_=trace();events[-1]['started']+=1
        with self.assertRaisesRegex(ValueError,'^joining source loss exact declaration$'):loss.declaration(events)
        # System.nanoTime has an arbitrary signed origin, not a wall-clock date.
        for start in (0,-123,-2**63,2**63-1):
            events,_,_,_=trace();events[0]['started']=events[-1]['started']=start
            self.assertEqual(start,loss.declaration(events)['started'])

    def test_missing_duplicate_or_premature_completion_cannot_qualify(self):
        for mutation in ('missing','duplicate','premature'):
            events,wires,ids,root=trace()
            if mutation=='missing':events.pop()
            elif mutation=='duplicate':events.append(dict(events[-1]))
            else:events.insert(1,events.pop())
            reason='original learner reply' if mutation=='premature' else 'declaration order'
            with self.subTest(mutation=mutation),self.assertRaisesRegex(ValueError,'^joining source loss '+reason+'$'):n.causal(events,wires,ids,root)

    def test_lost_reply_does_not_supply_delivery_to_the_successful_attempt(self):
        events,wires,ids,root=trace();delivery=next(v for v in events if v['event']=='AFTER_RESPONSE_READ')
        events.insert(4,dict(delivery))
        with self.assertRaisesRegex(ValueError,'^joining delivery without original response$'):n.causal(events,wires,ids,root)

    def test_zero_or_multiple_lost_replies_fail_exact_count(self):
        for count in (0,2):
            events,wires,ids,root=trace()
            if count==0:wires[0]['withheld']=False
            else:
                wires[1]['withheld']=True
                events=[v for v in events if not(v['event']=='AFTER_RESPONSE_READ' and v['request']==events[1]['request'])]
            with self.subTest(count=count),self.assertRaisesRegex(ValueError,'^joining source loss exact withheld count$'):n.causal(events,wires,ids,root)

    def test_donor_authority_cannot_change_between_lost_reply_and_retry(self):
        for event in ('PROMISE_FORCED','RETENTION_RENAMED','SOURCE_DELETED','CURRENT_BEFORE_CAPTURE','PUBLICATION_BEFORE_RETURN','FIXTURE_CLOSE_RETURNED'):
            events,wires,ids,root=trace();events.insert(4,dict(node='node-1',event=event))
            with self.subTest(event=event),self.assertRaisesRegex(ValueError,'^joining source loss donor authority changed during retry$'):n.causal(events,wires,ids,root)

    def test_retry_keeps_exact_original_client_scope(self):
        events,wires,ids,root=trace()
        next(v for v in events if v['event']=='AFTER_RESPONSE_READ')['scope']='new-source'
        with self.assertRaisesRegex(ValueError,'^joining source loss original client scope$'):n.causal(events,wires,ids,root)

    def test_missing_retry_and_changed_response_cannot_recover(self):
        events,wires,ids,root=trace();rows=n.causal(events,wires,ids,root)
        with self.assertRaisesRegex(ValueError,'^joining source loss exact retry count$'):loss.responses(events,[rows[0],*rows[2:]])
        rows[1]['responseHash']='f'*64
        with self.assertRaisesRegex(ValueError,'^joining source loss identical recovered response$'):loss.responses(events,rows)

    def test_loss_cannot_hide_an_overlapping_transfer_step(self):
        events,wires,ids,root=trace('CHUNK');rows=n.causal(events,wires,ids,root)
        rows[1]['sent']=rows[0]['delivered']
        with self.assertRaisesRegex(ValueError,'^joining network transfer next before delivery$'):n.transfers(rows)

    def test_lost_attempt_requires_original_send_and_server_read(self):
        for event,reason in [('BEFORE_REQUEST_WRITE','receive without send'),('NETWORK_REQUEST','response without request')]:
            events,wires,ids,root=trace();events.pop(next(i for i,v in enumerate(events) if v['event']==event))
            with self.subTest(event=event),self.assertRaisesRegex(ValueError,'^joining network '+reason+'$'):n.causal(events,wires,ids,root)

    def test_lost_commit_cannot_accept_missing_or_changed_retry(self):
        events,wires,ids,root=trace('TRANSFER_COMMIT');rows=n.causal(events,wires,ids,root)
        with self.assertRaisesRegex(ValueError,'^joining network unrecovered transfer loss$'):n.transfers(rows[:-1])
        rows[-1]['responseHash']='f'*64
        with self.assertRaisesRegex(ValueError,'^joining network changed lost transfer retry$'):n.transfers(rows)


if __name__=='__main__':unittest.main()
