"""The crossing promise must lie strictly within the observed hold interval."""
import unittest
import copy
from unittest.mock import patch
from . import public_read_protocol_evidence as p


class ProtocolReadEvidenceTest(unittest.TestCase):
    def promise(self,order):return dict(event='FORCE',kind='PROMISE',order=order,record='AA==')
    def test_real_higher_promise_inside_both_edges_is_required(self):
        with patch.object(p.e.physical.f,'inspect',return_value=dict(epoch=9)):
            row=self.promise(15);self.assertEqual([row],p.crossing([row],8,10,20))
            for at in (9,10,20,21):
                with self.subTest(at=at),self.assertRaisesRegex(ValueError,'crossing higher promise'):
                    p.crossing([self.promise(at)],8,10,20)

    def test_equal_or_lower_ballot_cannot_explain_fencing(self):
        for epoch in (7,8):
            with self.subTest(epoch=epoch),patch.object(p.e.physical.f,'inspect',return_value=dict(epoch=epoch)):
                with self.assertRaisesRegex(ValueError,'crossing higher promise'):p.crossing([self.promise(15)],8,10,20)

    def test_status_or_wire_claim_cannot_replace_durable_promise(self):
        for event,kind in (('REPLY','PROMISE'),('FORCE','PROOF'),('STATUS','PROMISE')):
            row=dict(self.promise(15),event=event,kind=kind)
            with self.subTest(event=event),patch.object(p.e.physical.f,'inspect') as parse:
                with self.assertRaisesRegex(ValueError,'crossing higher promise'):p.crossing([row],8,10,20)
                parse.assert_not_called()

    def test_unknown_schedule_never_qualifies(self):
        with self.assertRaisesRegex(ValueError,'unknown public read protocol schedule'):p.schedule(None,'anything',{},[],[])


class EarlyPromiseFencingTest(unittest.TestCase):
    def setUp(self):
        self.ballot=dict(epoch=6,proposer='node-2',incarnation='new')
        self.request=dict(type='HEARTBEAT',sender='node-1',recipient='node-3',epoch=2,proposer='node-1',
                          incarnationId='old',groupId='g',configurationId='c',manifestDigest='m',traceId='trace',eventSequence=39)
        self.response=dict(self.request,type='REJECT',sender='node-3',recipient='node-1',
                           payload=dict(reason='STALE_EPOCH',promised=self.ballot))
        self.wires={'request':self.request,'response':self.response}
        self.records={'local':dict(self.ballot),'peer':dict(self.ballot)}
        # Receiver settlement is order 30, local persistence follows at 40.
        # Responder order 200 is local to that process and is not compared to 30.
        self.rows=[dict(event='RECEIVED',order=20,frame='response',request='request',pid=1),
                   dict(event='FORCE',kind='PROMISE',order=40,record='local',pid=1)]
        self.peer=[dict(event='FORCE',kind='PROMISE',order=100,record='peer',pid=3),
                   dict(event='REPLY',order=200,frame='response',request='request',pid=3)]

    def check(self):
        with patch.object(p.e.physical,'raw',side_effect=lambda v:v), \
             patch.object(p.e.physical.f,'inspect',side_effect=lambda v,k:self.records[v]), \
             patch.object(p.e.physical,'frame',side_effect=lambda v,k,m:self.records[v]), \
             patch.object(p.e.physical.f,'wire',side_effect=lambda v,m:self.wires[v]):
            return p.fencing_before_settlement(self.rows,{'node-1':self.rows,'node-3':self.peer},'node-1',2,10,30,50,{})

    def test_peer_forced_rejection_can_precede_local_persistence(self):
        self.assertEqual('peer-promise',self.check())

    def test_local_persistence_before_settlement_remains_valid(self):
        self.rows=self.rows[1:];self.rows[0]['order']=25
        self.assertEqual('local-promise',self.check())

    def test_local_force_must_still_cross_the_hold_interval(self):
        for order in (9,10,50,51):
            self.rows[1]['order']=order
            with self.subTest(order=order),self.assertRaisesRegex(ValueError,'crossing higher promise'):self.check()

    def test_late_rejection_cannot_explain_earlier_settlement(self):
        for order in (9,10,30,31):
            self.rows[0]['order']=order
            with self.subTest(order=order),self.assertRaisesRegex(ValueError,'before read settlement'):self.check()

    def test_wire_claim_requires_matching_peer_reply_and_force(self):
        original=copy.deepcopy(self.peer)
        for peer,reason in ((original[:1],'unobserved'),(original[1:],'earlier durable'),
                            ([dict(original[0],order=201),original[1]],'earlier durable'),
                            ([dict(original[0],pid=99),original[1]],'earlier durable')):
            self.peer=peer
            with self.subTest(peer=peer),self.assertRaisesRegex(ValueError,reason):self.check()

    def test_wrong_ballot_cannot_explain_the_rejection(self):
        original=copy.deepcopy(self.records)
        for key,value in (('epoch',7),('proposer','node-3'),('incarnation','other')):
            self.records=copy.deepcopy(original);self.records['peer'][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'earlier durable'):self.check()

    def test_local_force_can_already_be_from_a_newer_campaign(self):
        self.records['local']=dict(epoch=9,proposer='node-3',incarnation='later')
        self.assertEqual('peer-promise',self.check())

    def test_uncorrelated_reply_never_qualifies(self):
        original=copy.deepcopy(self.response)
        for key in ('groupId','configurationId','manifestDigest','traceId','eventSequence','epoch','incarnationId','proposer','sender','recipient'):
            self.wires['response']=dict(original,**{key:'changed'})
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'uncorrelated'):self.check()

    def test_same_epoch_or_wrong_rejection_kind_is_not_a_fence(self):
        original=copy.deepcopy(self.response)
        for changed in (dict(original,type='AUTHORITY_STATUS'),dict(original,payload=dict(original['payload'],reason='CAPACITY_EXCEEDED')),
                        dict(original,payload=dict(original['payload'],promised=dict(self.ballot,epoch=2)))):
            self.wires['response']=changed
            with self.subTest(changed=changed),self.assertRaisesRegex(ValueError,'before read settlement'):self.check()

    def use_status(self):
        self.request.update(type='AUTHORITY_STATUS_PROBE',payload=dict(nonce='probe'))
        self.response.update(type='AUTHORITY_STATUS',payload=dict(nonce='probe',promised=self.ballot))

    def test_peer_authority_status_can_fence_before_local_persistence(self):
        self.use_status()
        self.assertEqual('peer-status-promise',self.check())
        self.records['local']=dict(epoch=9,proposer='node-3',incarnation='later')
        self.assertEqual('peer-status-promise',self.check())

    def test_status_requires_the_original_probe_nonce(self):
        self.use_status()
        for request,response in (({},{}),({'nonce':''},{'nonce':''}),({'nonce':1},{'nonce':1}),
                                 ({'nonce':'probe'},{}),({}, {'nonce':'probe'}),
                                 ({'nonce':'probe'},{'nonce':'other'})):
            self.request['payload']=request;self.response['payload']=dict(response,promised=self.ballot)
            with self.subTest(request=request,response=response),self.assertRaisesRegex(ValueError,'status nonce'):self.check()

    def test_status_requires_a_probe_and_higher_promise_for_the_held_epoch(self):
        self.use_status()
        for request_type,response_type,request_epoch,promised_epoch in (
                ('HEARTBEAT','AUTHORITY_STATUS',2,6),('AUTHORITY_STATUS_PROBE','OTHER',2,6),
                ('AUTHORITY_STATUS_PROBE','AUTHORITY_STATUS',3,6),
                ('AUTHORITY_STATUS_PROBE','AUTHORITY_STATUS',2,2),
                ('AUTHORITY_STATUS_PROBE','AUTHORITY_STATUS',2,1)):
            self.request.update(type=request_type,epoch=request_epoch)
            self.response.update(type=response_type,epoch=request_epoch)
            self.response['payload']['promised']=dict(self.ballot,epoch=promised_epoch)
            with self.subTest(request_type=request_type,response_type=response_type,epoch=request_epoch,promise=promised_epoch), \
                 self.assertRaisesRegex(ValueError,'before read settlement'):self.check()

    def test_status_requires_correlated_envelope(self):
        self.use_status();original=copy.deepcopy(self.response)
        for key in ('groupId','configurationId','manifestDigest','traceId','eventSequence','epoch','incarnationId','proposer','sender','recipient'):
            self.wires['response']=dict(original,**{key:'changed'})
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'uncorrelated'):self.check()

    def test_status_requires_exact_peer_reply_and_earlier_same_process_force(self):
        self.use_status();original=copy.deepcopy(self.peer)
        for peer,reason in ((original[:1],'unobserved'),(original[1:],'earlier durable'),
                            ([original[0],dict(original[1],frame='other')],'unobserved'),
                            ([original[0],dict(original[1],request='other')],'unobserved'),
                            ([dict(original[0],order=200),original[1]],'earlier durable'),
                            ([dict(original[0],order=201),original[1]],'earlier durable'),
                            ([dict(original[0],pid=99),original[1]],'earlier durable')):
            self.peer=peer
            with self.subTest(peer=peer),self.assertRaisesRegex(ValueError,reason):self.check()

    def test_status_requires_exact_durable_ballot(self):
        self.use_status();original=copy.deepcopy(self.records)
        for key,value in (('epoch',7),('proposer','node-3'),('incarnation','other')):
            self.records=copy.deepcopy(original);self.records['peer'][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'earlier durable'):self.check()

    def test_status_must_arrive_inside_the_pre_settlement_interval(self):
        self.use_status()
        for order in (9,10,30,31):
            self.rows[0]['order']=order
            with self.subTest(order=order),self.assertRaisesRegex(ValueError,'before read settlement'):self.check()

    def test_status_cannot_replace_local_persistence_within_the_hold(self):
        self.use_status()
        for order in (9,10,50,51):
            self.rows[1]['order']=order
            with self.subTest(order=order),self.assertRaisesRegex(ValueError,'crossing higher promise'):self.check()


if __name__=='__main__':unittest.main()
