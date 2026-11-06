"""Conditional reader checks; the fresh native original is replayed separately."""
import base64
import copy
from itertools import permutations
import random
import unittest
from unittest.mock import patch

from . import activation_control_resources as r
from . import activation_control_resource_negatives as negatives
from . import native_resource_evidence as native
from .test_resource_transitions import charge,row,trace


def fixture():
    node='node-2';binding='a'*64
    control=charge('CONTROL','activation-control-'+binding+'-00000000-0000-0000-0000-000000000001',1200)
    grown=dict(control,bytes=2000)
    waiter=charge('WAITER','activation-waiter-'+binding+'-00000000-0000-0000-0000-000000000002',0)
    other=charge('CONTROL','unrelated',1)
    traces={node:trace([row('START'),row('RESERVE',added=[waiter]),row('RESERVE',added=[control]),
        row('RESERVE',added=[other]),row('RELEASE',[other]),row('CONTROL_GROW',[control],[grown]),
        row('RELEASE',[waiter]),row('RELEASE',[grown])])}
    events=[dict(node=node,event=name) for name in ('NETWORK_REQUEST','PROMISE_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN','WIRE_RESPONSE')]
    points=[dict(eventIndex=i,node=node,sequence=seq,usage={}) for i,seq in enumerate((0,3,3,4,6))]
    negatives.recount(traces,points)
    wires=[dict(connection=dict(id='original'),request=base64.b64encode(b'q'*1200).decode(),response=base64.b64encode(b'r'*800).decode())]
    q=dict(sender=dict(node='node-1'),recipient=dict(node=node),root='b'*64,view='c'*64,ballot={'counter':1},payload={'promise':'d'*64})
    reply=dict(kind='PREPARE',answer='PROMISE',request=q,response={'payload':{}},requestHash=binding,
               received=0,offered=4,sent=-1,serverConnection='original')
    return (events,wires,traces,points,{},'b'*64,{},[]),dict(rows=[reply],failed=[])


class ActivationControlResourcesTest(unittest.TestCase):
    def replay(self,data,network):
        with patch.object(r.source.network,'replay',return_value=network),patch.object(r.slots,'local_calls',return_value=[]):
            return r.replay(*data)

    def test_original_request_cached_reply_waiter_and_durable_boundaries(self):
        data,network=fixture();result=self.replay(data,network)
        self.assertEqual((2,1,1,3),(result['boundReservations'],result['cachedControls'],result['waiterReservations'],result['durableBoundaryChecks']))
        self.assertTrue(result['activationResourcesQualified'])
        for field in ('phase3Complete','wholeRuntimeResourcesQualified','interruptedHandlersQualified'):self.assertFalse(result[field])

    def test_coherent_accounting_mutations_reject_for_exact_reason(self):
        data,network=fixture();before=copy.deepcopy(data)
        for name,reason in list(negatives.NEGATIVES.items())[:-3]:
            changed=copy.deepcopy(data);negatives.mutate(changed,name)
            with self.subTest(case=name),self.assertRaisesRegex(ValueError,'^'+reason+'$'):self.replay(changed,network)
        self.assertEqual(before,data)

    def test_duplicate_ack_loss_keeps_one_cache_but_needs_another_waiter(self):
        data,network=fixture();network['rows'].append(dict(network['rows'][0],sent=9))
        with self.assertRaisesRegex(ValueError,'missing mandatory caller'):self.replay(data,network)
        rows=data[2]['node-2']['changes'];extra=dict(rows[1]['added'][0]);extra['owner']=extra['owner'][:-36]+'00000000-0000-0000-0000-000000000003'
        rows.insert(2,row('RESERVE',added=[extra]));rows.insert(8,row('RELEASE',[extra]))
        for p in data[3]:
            if p['sequence']>=2:p['sequence']+=1
            if p['eventIndex']==4:p['sequence']=8
        negatives.recount(data[2],data[3]);result=self.replay(data,network)
        self.assertEqual((1,2,2),(result['cachedControls'],result['waiterReservations'],result['calls']))

    def test_negative_driver_uses_incoming_grant_instead_of_earlier_local_campaign(self):
        data,_=fixture();events,_,traces,points,*_=data
        traces['node-1']=trace([row('START')]);events.insert(0,dict(node='node-1',event='GRANT_BEFORE_RETURN'))
        for p in points:p['eventIndex']+=1
        points.insert(0,dict(node='node-1',eventIndex=0,sequence=0,usage={}))
        negatives.recount(traces,points);negatives.mutate(data,'request-short')
        lives,_=r.scan(traces);control=next(v for v in lives.values() if v['role']=='activation-control')
        self.assertEqual(1199,control['initial']);self.assertEqual('node-2',control['node'])

    def test_failed_handler_cannot_be_silently_omitted(self):
        data,network=fixture();network['failed'].append(dict(kind='PREPARE',received=0,sent=9))
        with self.assertRaisesRegex(ValueError,'failed handler outside qualification'):self.replay(data,network)
        network['failed'][0]['received']=None;self.assertEqual('PASS',self.replay(data,network)['status'])

    def test_original_response_is_required_even_if_local_counts_match(self):
        data,network=fixture();network['rows'][0]['answer']='REJECT'
        with self.assertRaisesRegex(ValueError,'successful original reply'):self.replay(data,network)

    def test_fast_publish_can_arrive_before_completion_but_needs_a_prior_response_cut(self):
        data,network=fixture();events,wires,traces,points,ids,root,expected,transactions=data
        raw=b'original physical certificate';certificate=r.slots.publication.sha(raw)
        payload={'certificate':certificate};expected['node-2',certificate]={'payload':payload,'view':'c'*64,'ballot':{'counter':1}}
        for i,name in enumerate(('NETWORK_REQUEST','PUBLICATION_VALIDATED','NETWORK_REQUEST','PUBLICATION_BEFORE_RETURN','WIRE_RESPONSE')):
            events[i]['event']=name
        events.append(dict(node='node-2',event='WIRE_RESPONSE'));points.append(dict(points[4],eventIndex=5))
        transactions.append([dict(node='node-2',eventIndex=1,files={'applied-end/certificate.gsr':raw}),dict(node='node-2',eventIndex=3)])
        original=network['rows'][0];original.update(kind='PUBLISH',answer='PUBLISH_ACK',response={'payload':payload})
        original['request']['payload']={'certificate':certificate}
        network['rows'].append(dict(original,received=2,offered=5,sent=9))
        result=self.replay(data,network)
        self.assertEqual((1,1,1),(result['fastPublicationReplies'],result['waiterReservations'],result['publicationTransactions']))
        # A completed publication after its offered response is not authority.
        events.append(dict(node='node-2',event='PUBLICATION_BEFORE_RETURN'));points.append(dict(points[4],eventIndex=6))
        transactions[0][-1]['eventIndex']=6
        with self.assertRaisesRegex(ValueError,'missing mandatory caller'):self.replay(data,network)
        transactions.clear()
        with self.assertRaisesRegex(ValueError,'missing mandatory caller'):self.replay(data,network)

    def test_legacy_and_absent_bindings_never_qualify_strictly(self):
        data,_=fixture();negatives.mutate(data,'legacy-control')
        with self.assertRaisesRegex(ValueError,'original bindings required'):r.replay(*data)
        result=r.replay(*data,require_complete=False);self.assertEqual('NOT_OBSERVED',result['status']);self.assertFalse(result['activationResourcesQualified'])
        with self.assertRaisesRegex(ValueError,'original bindings required'):r.replay([],[],{},[],{},'b'*64,{},[])

    def test_incomplete_drain_uuid_and_unit_are_checked(self):
        data,_=fixture();data[2]['node-2']['changes'].pop();negatives.recount(data[2],[])
        with self.assertRaisesRegex(ValueError,'outstanding charges at close'):r.scan(data[2])
        for mode in ('uuid','unit'):
            data,_=fixture()
            for row in data[2]['node-2']['changes']:
                for c in row['removed']+row['added']:
                    if c['owner'].startswith('activation-waiter'):
                        if mode=='uuid':c['owner']=c['owner'][:-36]+'00000000-0000-0000-0000-000000000000'
                        else:c.update(unit='CONTROL',bytes=1)
            negatives.recount(data[2],data[3])
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'activation resources (allocation UUID|role/unit)'):r.scan(data[2])

    def test_unobserved_and_unknown_mutations_cannot_be_successful_negatives(self):
        with patch.object(r,'replay',side_effect=ValueError('invalid original')),patch.object(negatives,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'invalid original'):negatives.replay([])
            mutate.assert_not_called()
        with self.assertRaisesRegex(ValueError,'declared negative'):negatives.mutate([], 'unknown')

    def test_policy_types_and_nonstable_profiles_reject(self):
        with self.assertRaisesRegex(ValueError,'completeness policy'):r.replay([],[],{},[],{},'b'*64,{},[],require_complete=1)
        with self.assertRaisesRegex(ValueError,'activation control policy'):native.validate('unused',activation_control=1)
        with self.assertRaisesRegex(ValueError,'activation control policy'):native.validate('unused','3-ADD',activation_control=True)
        with self.assertRaisesRegex(ValueError,'slot control policy'):native.validate('unused',slot_control=1,activation_control=True)

    def test_matching_does_not_spend_a_waiter_on_optional_fast_ack_and_drop_a_required_call(self):
        waiters=[dict(start=2,end=4)]
        attempts=[dict(receivedSequence=0,offeredSequence=5,fastEligible=True),dict(receivedSequence=1,offeredSequence=5,fastEligible=False)]
        self.assertEqual({0:1},r.match_calls(waiters,attempts))
        attempts.append(dict(receivedSequence=1,offeredSequence=5,fastEligible=False))
        with self.assertRaisesRegex(ValueError,'missing mandatory caller'):r.match_calls(waiters,attempts)

    def test_matching_agrees_with_exhaustive_assignment(self):
        randomizer=random.Random(5303)
        for _ in range(1500):
            waiters=[dict(start=a,end=b) for a,b in (sorted(randomizer.sample(range(1,9),2)) for _ in range(randomizer.randrange(5)))]
            attempts=[dict(receivedSequence=a,offeredSequence=b,fastEligible=bool(randomizer.randrange(2)))
                      for a,b in (sorted(randomizer.sample(range(10),2)) for _ in range(randomizer.randrange(5)))]
            mandatory={i for i,a in enumerate(attempts) if not a['fastEligible']}
            possible=any(mandatory<=set(choice) and all(attempts[j]['receivedSequence']<w['start']<w['end']<=attempts[j]['offeredSequence']
                         for w,j in zip(waiters,choice)) for choice in permutations(range(len(attempts)),len(waiters)))
            try:assignment=r.match_calls(waiters,attempts);actual=True
            except ValueError:actual=False
            self.assertEqual(possible,actual,(waiters,attempts))
            if actual:self.assertEqual(len(waiters),len(set(assignment.values())))


if __name__=='__main__':unittest.main()
