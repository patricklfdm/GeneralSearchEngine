"""Conditional accounting checks; native TCP and physical replay are separate."""
import base64
import copy
from itertools import permutations
import random
import unittest
from unittest.mock import patch

from . import voting_control_resources as r
from . import voting_control_resource_negatives as negatives
from . import native_resource_evidence as native
from .test_resource_transitions import charge, trace, row


def fixture():
    binding='a'*64;node='node-2'
    control=charge('CONTROL','voting-control-'+binding+'-00000000-0000-0000-0000-000000000001',1200)
    waiter=charge('WAITER','voting-waiter-'+binding+'-00000000-0000-0000-0000-000000000002',0)
    other=charge('CONTROL','unrelated-buffer',1)
    traces={node:trace([row('START'),row('RESERVE',added=[waiter]),row('RESERVE',added=[control]),
                       row('RESERVE',added=[other]),row('RELEASE',[other]),row('RELEASE',[control]),row('RELEASE',[waiter])])}
    events=[dict(node=node,event=name) for name in ('NETWORK_REQUEST','ACCEPT_PARENT_FORCED','ACCEPT_BEFORE_RETURN','WIRE_RESPONSE')]
    points=[dict(eventIndex=i,node=node,sequence=seq,usage={}) for i,seq in enumerate((0,3,4,6))]
    negatives.recount(traces,points)
    wires=[dict(connection=dict(id='original'),request=base64.b64encode(b'q'*1200).decode())]
    q=dict(sender=dict(node='node-1'),recipient=dict(node=node),root='b'*64,view='c'*64,ballot={'counter':1},payload={'acceptance':'d'*64})
    reply=dict(kind='ACCEPT',answer='ACCEPT_ACK',request=q,requestHash=binding,received=0,offered=3,sent=-1,serverConnection='original')
    return (events,wires,traces,points,{},'b'*64),dict(rows=[reply],failed=[])


class VotingControlResourcesTest(unittest.TestCase):
    def replay(self,data,network):
        with patch.object(r.source.network,'replay',return_value=network):return r.replay(*data)

    def test_exact_writer_waiter_and_original_force_extent(self):
        data,network=fixture();result=self.replay(data,network)
        self.assertEqual((2,1,1),(result['boundReservations'],result['writerControls'],result['waiterReservations']))
        self.assertTrue(result['incomingVotingResourcesQualified']);self.assertFalse(result['wholeRuntimeResourcesQualified'])
        self.assertFalse(result['phase3Complete']);self.assertFalse(result['interruptedHandlersQualified'])

    def test_all_coherent_mutations_reject_for_exact_reasons(self):
        data,network=fixture();before=copy.deepcopy(data)
        with patch.object(r.source.network,'replay',return_value=network):result=negatives.replay(data)
        self.assertEqual(16,len(result['negatives']));self.assertEqual(data,before)

    def test_lost_ack_duplicate_can_share_a_single_original_writer(self):
        data,network=fixture();network['rows'].append(dict(network['rows'][0]))
        network['rows'][0]['failedAttempt']=True
        network['failed'].append(dict(kind='ACCEPT',received=0,sent=-1))
        result=self.replay(data,network)
        self.assertEqual((1,2,1),(result['writerControls'],result['connectedAttempts'],result['repeatedIdenticalAttempts']))

    def test_new_trace_fast_ack_needs_the_same_observed_statement(self):
        data,network=fixture();original=network['rows'][0];network['rows'].append(dict(original,requestHash='e'*64))
        result=self.replay(data,network);self.assertEqual(1,result['separatelyTracedFastAcks'])
        network['rows'][1]['request']=dict(original['request'],payload={'acceptance':'f'*64})
        with self.assertRaisesRegex(ValueError,'cached reply without original force'):self.replay(data,network)

    def test_failed_server_handler_is_not_silently_outside_the_count(self):
        data,network=fixture();network['failed'].append(dict(kind='PROOF',received=0,sent=99))
        with self.assertRaisesRegex(ValueError,'failed handler outside qualification'):self.replay(data,network)

    def test_unconnected_attempt_does_not_invent_a_server_handler(self):
        data,network=fixture();network['failed'].append(dict(kind='PROOF',received=None,sent=99))
        self.assertEqual(1,self.replay(data,network)['writerControls'])

    def test_rejected_vote_cannot_be_counted_as_a_durable_success(self):
        data,network=fixture();network['rows'][0]['answer']='REJECT'
        with self.assertRaisesRegex(ValueError,'successful original reply'):self.replay(data,network)

    def test_unit_and_uuid_are_independently_checked(self):
        for kind in ('unit','uuid'):
            data,_=fixture();rows=data[2]['node-2']['changes']
            for v in rows[2]['added']+rows[5]['removed']:
                if kind=='unit':v.update(unit='WAITER',bytes=0)
                else:v['owner']=v['owner'][:-36]+'00000000-0000-0000-0000-000000000000'
            negatives.recount(data[2],data[3])
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'voting resources (role/unit|allocation UUID)'):r.scan(data[2])

    def test_missing_and_legacy_bindings_never_pass_strict_mode(self):
        data,_=fixture();negatives.mutate(data,'legacy-binding')
        with self.assertRaisesRegex(ValueError,'original bindings required'):r.replay(*data)
        result=r.replay(*data,require_complete=False)
        self.assertEqual('NOT_OBSERVED',result['status']);self.assertFalse(result['incomingVotingResourcesQualified'])
        with self.assertRaisesRegex(ValueError,'original bindings required'):r.replay([],[],{},[],{},'b'*64)

    def test_incomplete_close_and_nonboolean_options_refuse(self):
        data,_=fixture();data[2]['node-2']['changes'].pop();negatives.recount(data[2],[])
        with self.assertRaises(ValueError):r.scan(data[2])
        with self.assertRaisesRegex(ValueError,'completeness policy'):r.replay([],[],{},[],{},'b'*64,require_complete=1)
        with self.assertRaisesRegex(ValueError,'voting control policy'):native.validate('unused','3-ADD',voting_control=True)

    def test_invalid_original_cannot_be_counted_as_sixteen_rejections(self):
        with patch.object(r,'replay',side_effect=ValueError('bad original')),patch.object(negatives,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'bad original'):negatives.replay([])
            mutate.assert_not_called()

    def test_waiter_matching_does_not_count_one_connection_twice(self):
        attempts=[dict(receivedSequence=0,offeredSequence=5)]
        with self.assertRaisesRegex(ValueError,'waiter request interval'):
            r.match_waiters([dict(start=1,end=3),dict(start=2,end=4)],attempts)

    def test_waiter_matching_agrees_with_independent_exhaustive_assignment(self):
        randomizer=random.Random(53)
        for _ in range(1000):
            waiters=[dict(start=a,end=b) for a,b in (sorted(randomizer.sample(range(1,9),2)) for i in range(3))]
            attempts=[dict(receivedSequence=a,offeredSequence=b) for a,b in (sorted(randomizer.sample(range(0,10),2)) for i in range(3))]
            possible=any(all(a['receivedSequence']<w['start']<w['end']<=a['offeredSequence'] for w,a in zip(waiters,p)) for p in permutations(attempts))
            try:r.match_waiters(waiters,attempts);actual=True
            except ValueError:actual=False
            self.assertEqual(possible,actual,(waiters,attempts))


if __name__=='__main__':unittest.main()
