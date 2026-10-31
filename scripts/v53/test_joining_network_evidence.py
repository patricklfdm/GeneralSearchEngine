"""Causal regressions; these small fixtures do not claim native qualification."""
import base64
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import joining_network_evidence as n
from . import test_joining_phase_evidence as fixture


class JoiningNetworkEvidenceTest(unittest.TestCase):
    def exchange(self, scoped=False):
        responses,wires,identities,root,q,a = fixture.JoiningPhaseEvidenceTest().wire(scoped)
        digest=n.sha(base64.b64decode(wires[0]['request']))
        send=dict(node='node-1',event='NETWORK_SEND',request=digest,kind='ACCEPT',bytes=wires[0]['request'])
        received=dict(node=q['recipient']['node'],event='NETWORK_REQUEST',request=digest,kind='ACCEPT')
        if scoped:received.update(event='AFTER_REQUEST_READ',scope='continuation-endpoint')
        return [send,received,*responses],wires,identities,root

    def test_complete_and_scoped_exchanges_bind_each_original_boundary(self):
        for scoped in (False,True):
            events,wires,identities,root=self.exchange(scoped)
            row=n.causal(events,wires,identities,root)[0]
            self.assertEqual((0,1,2,3),tuple(row[k] for k in ('sent','received','offered','delivered')))

    def test_received_request_requires_prior_send_not_a_later_matching_digest(self):
        events,wires,ids,root=self.exchange()
        for es in (events[1:],[events[1],events[0],*events[2:]]):
            with self.assertRaisesRegex(ValueError,'^joining network receive without send$'):n.causal(es,wires,ids,root)

    def test_offered_response_requires_received_request_not_just_a_send(self):
        events,wires,ids,root=self.exchange()
        with self.assertRaisesRegex(ValueError,'^joining network response without request$'):
            n.causal([events[0],*events[2:]],wires,ids,root)

    def test_each_duplicate_request_consumes_its_own_send_receive_and_delivery(self):
        events,wires,ids,root=self.exchange()
        self.assertEqual(2,len(n.causal(events*2,wires*2,ids,root)))
        with self.assertRaisesRegex(ValueError,'^joining network receive without send$'):
            n.causal(events+events[1:],wires*2,ids,root)

    def test_extra_send_and_undelivered_response_do_not_disappear(self):
        events,wires,ids,root=self.exchange()
        for es,reason in ((events+[events[0]],'incomplete healthy exchange'),(events[:-1],'undelivered healthy response')):
            with self.assertRaisesRegex(ValueError,'^joining network '+reason+'$'):n.causal(es,wires,ids,root)

    def test_overlapping_identical_attempts_do_not_invent_socket_pairing(self):
        events,wires,ids,root=self.exchange()
        with self.assertRaisesRegex(ValueError,'^joining network ambiguous overlapping retry$'):
            n.causal([events[0],*events],wires,ids,root)

    def test_late_request_mutation_targets_its_own_reply_after_nested_exchanges(self):
        events,wires,_,_=self.exchange();request=events[1]['request']
        events.insert(2,dict(events[2],request='other-request'))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'events.json').write_bytes(n.f.canonical(events));(root/'wire.json').write_bytes(n.f.canonical(wires))
            n.mutate(root,'late-request');changed=n.s.collection.read_json(root,'events.json',4096)
            receive=next(i for i,v in enumerate(changed) if v['event']=='NETWORK_REQUEST')
            reply=next(i for i,v in enumerate(changed) if v['event']=='WIRE_RESPONSE' and v['request']==request)
            self.assertGreater(receive,reply)

    def test_request_bytes_kind_and_permanent_sender_are_bound(self):
        for mutation,reason in [('digest','send bytes'),('kind','send bytes'),('sender','send identity'),('receiver','request binding')]:
            events,wires,ids,root=self.exchange()
            if mutation=='digest':events[0]['request']='f'*64
            elif mutation=='kind':events[0]['kind']='PROOF'
            elif mutation=='sender':events[0]['node']='node-3'
            else:events[1]['node']='node-3'
            with self.subTest(mutation=mutation),self.assertRaisesRegex(ValueError,'^joining network '+reason+'$'):
                n.causal(events,wires,ids,root)

    def test_scoped_callback_must_be_same_server_lifetime(self):
        events,wires,ids,root=self.exchange(True);events[1]['scope']='pending-listener'
        with self.assertRaisesRegex(ValueError,'^joining network response request binding$'):n.causal(events,wires,ids,root)

    def test_scoped_callback_must_be_same_client_lifetime(self):
        events,wires,ids,root=self.exchange();events[0].update(event='BEFORE_REQUEST_WRITE',scope='learner-source')
        with self.assertRaisesRegex(ValueError,'^joining network client lifetime$'):n.causal(events,wires,ids,root)

    def transfer(self):
        data=b'original transfer';digest=n.sha(data)
        q=dict(sender=dict(node='node-1'),recipient=dict(node='node-2'),trace='trace',root='root',view='view',ballot={'counter':1})
        def row(index,kind,answer,request,response):
            return dict(request=dict(q,sequence=index,payload=request),response=dict(payload=response),kind=kind,answer=answer,
                        requestHash=str(index),responseHash=str(index),sent=index*4,received=index*4+1,offered=index*4+2,delivered=index*4+3)
        request=dict(id='id',action='REQUEST',offset=0,digest=digest,bytes='')
        return [row(1,'CHUNK','SOURCE_OFFER',request,dict(id='id',digest=digest,bytes=len(data),kind='RECORD')),
                row(2,'CHUNK','CHUNK',request,dict(id='id',action='DATA',offset=0,digest=digest,bytes=base64.b64encode(data).decode())),
                row(3,'TRANSFER_COMMIT','TRANSFER_COMMIT',dict(id='id',digest=digest),dict(id='id',digest=digest))]

    def test_transfer_checks_complete_bytes_and_identical_last_exchange_retry(self):
        rows=self.transfer();retry=copy.deepcopy(rows[0]);retry.update(sent=7.1,delivered=7.9)
        result=n.transfers([rows[0],retry,*rows[1:]])
        self.assertEqual((1,1,len(b'original transfer')),(result['committedTransfers'],result['exactTransferRetries'],result['transferredBytes']))
        retry['responseHash']='changed'
        with self.assertRaisesRegex(ValueError,'^joining network changed transfer retry$'):n.transfers([rows[0],retry,*rows[1:]])

    def test_transfer_next_exchange_waits_for_observed_delivery(self):
        rows=self.transfer();rows[1]['sent']=rows[0]['delivered']
        with self.assertRaisesRegex(ValueError,'^joining network transfer next before delivery$'):n.transfers(rows)

    def test_transfer_missing_or_reordered_chunks_cannot_commit(self):
        for mutation,reason in [('missing','transfer sequence'),('offset','exact transfer chunk'),('hash','exact transfer chunk'),
                                ('commit','complete transfer commit'),('truncated','incomplete transfer')]:
            rows=self.transfer()
            if mutation=='missing':rows.pop(1)
            elif mutation=='offset':rows[1]['response']['payload']['offset']=1
            elif mutation=='hash':rows[1]['response']['payload']['digest']='f'*64
            elif mutation=='commit':rows[-1]['request']['payload']['digest']='f'*64
            else:rows.pop()
            with self.subTest(mutation=mutation),self.assertRaisesRegex(ValueError,'^joining network '+reason+'$'):n.transfers(rows)

    def test_transfer_cannot_reset_sequence_by_changing_view_or_ballot(self):
        rows=self.transfer();rows[1]['request']['view']='changed'
        with self.assertRaisesRegex(ValueError,'^joining network transfer context$'):n.transfers(rows)

    def test_reject_is_counted_separately_and_cannot_become_a_committed_transfer(self):
        rows=self.transfer();rows[0]['answer']='REJECT';rows[0]['response']['payload']={'reason':'NOT_READY'}
        result=n.transfers(rows[:1]);self.assertEqual((1,0),(result['rejectedTransferAttempts'],result['committedTransfers']))
        with self.assertRaisesRegex(ValueError,'^joining network transfer sequence$'):n.transfers(rows)

    def test_empty_transfer_is_valid_only_with_its_empty_digest(self):
        rows=self.transfer();digest=n.sha(b'')
        rows[0]['response']['payload'].update(bytes=0,digest=digest)
        rows[-1]['request'].update(sequence=2);rows[-1]['request']['payload']['digest']=digest;rows[-1]['response']['payload']['digest']=digest
        self.assertEqual(1,n.transfers([rows[0],rows[-1]])['committedTransfers'])
        rows[0]['response']['payload']['digest']='f'*64
        with self.assertRaisesRegex(ValueError,'^joining network complete transfer commit$'):n.transfers([rows[0],rows[-1]])

    def test_durable_interval_requires_multiplicity_order_and_same_owner_scope(self):
        names=['PROMISE_FORCED','SOURCE_IMAGE_FORCED','SOURCE_IMAGE_FORCED','BASIS_FORCED']
        events=[dict(node='node-2',event=name) for name in names]
        n.interval(events,'node-2',-1,5,names,'force missing')
        for changed in (events[:-1],events[:2]+events[3:],list(reversed(events))):
            with self.assertRaisesRegex(ValueError,'^force missing$'):n.interval(changed,'node-2',-1,5,names,'force missing')
        events[0]['scope']='different-owner'
        with self.assertRaisesRegex(ValueError,'^force missing$'):n.interval(events,'node-2',-1,5,names,'force missing')

    def test_original_physical_failure_cannot_become_network_acceptance(self):
        with patch.object(n.s.collection,'inventory',return_value={}),patch.object(n.physical,'validate',side_effect=ValueError('physical invalid')),patch.object(n,'network') as network:
            with self.assertRaisesRegex(ValueError,'^physical invalid$'):n.validate('/unused')
            network.assert_not_called()

    def test_original_mutation_during_replay_is_rejected(self):
        with patch.object(n.s.collection,'inventory',side_effect=[{}, {'changed':1}]),patch.object(n.physical,'validate',return_value={'scope':'physical'}),patch.object(n,'network',return_value={}):
            with self.assertRaisesRegex(ValueError,'^joining network original changed$'):n.validate('/unused')

    def test_invalid_original_cannot_supply_successful_negative_results(self):
        with patch.object(n,'validate',side_effect=ValueError('original invalid')),patch.object(n.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^original invalid$'):n.qualify('/unused')
            copied.assert_not_called()

    def test_negative_cannot_reuse_derivation_if_any_physical_file_changes(self):
        original=dict(files={'original.gsr':'digest','events.json':'events'},directories=['directory'])
        changed=dict(files={'original.gsr':'changed','events.json':'changed'},directories=['directory'])
        with patch.object(n,'validate',return_value={}),patch.object(n.s.collection,'inventory',side_effect=[original,changed]), \
                patch.object(n.shutil,'copytree'),patch.object(n,'mutate'),patch.object(n,'network') as network:
            with self.assertRaisesRegex(ValueError,'^joining network negative changed physical inputs$'):n.qualify('/unused')
            network.assert_not_called()

    def test_accepted_negative_cannot_count_as_rejection(self):
        original=dict(files={},directories=[])
        with patch.object(n,'validate',return_value={}),patch.object(n.s.collection,'inventory',return_value=original), \
                patch.object(n.shutil,'copytree'),patch.object(n,'mutate'),patch.object(n,'network',return_value={}):
            with self.assertRaisesRegex(ValueError,'^joining network mutation accepted:'):n.qualify('/unused')

    def test_wrong_negative_failure_is_reported_instead_of_counting_success(self):
        original=dict(files={},directories=[])
        with patch.object(n,'validate',return_value={}),patch.object(n.s.collection,'inventory',return_value=original), \
                patch.object(n.shutil,'copytree'),patch.object(n,'mutate'),patch.object(n,'network',side_effect=ValueError('wrong boundary')):
            with self.assertRaisesRegex(ValueError,'^joining unrelated network negative: missing-send: wrong boundary$'):n.qualify('/unused')


if __name__=='__main__':unittest.main()
