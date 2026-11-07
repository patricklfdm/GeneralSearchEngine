"""Conditional resource transcripts; fresh Java physical evidence is separate."""
import base64
import copy
import unittest
from unittest.mock import patch

from . import slot_control_resources as r
from . import slot_control_resource_negatives as negatives
from . import native_resource_evidence as native
from . import test_transport_resource_evidence as transport
from .test_resource_transitions import charge,row


def fixture():
    events,wires,traces,points,ids,root=transport.fixture()
    digest=events[0]['request'];client=events[0]['node'];server=events[1]['node']
    def owner(role,binding,nonce):return role+'-'+binding+'-00000000-0000-0000-0000-'+f'{nonce:012d}'
    def insert(node,at,value):
        traces[node]['changes'].insert(at,value)
        for p in points:
            if p['node']==node and p['sequence']>=at:p['sequence']+=1
    delivery=charge('CONTROL',owner('slot-delivery',digest,1),len(base64.b64decode(events[0]['bytes'])))
    waiter=charge('WAITER',owner('slot-waiter',digest,2),0)
    child=charge('WAITER',owner('voting-waiter',digest,3),0)
    insert(client,1,row('RESERVE',added=[delivery]));traces[client]['changes'].append(row('RELEASE',[delivery]))
    pos=points[1]['sequence']+1
    insert(server,pos,row('RESERVE',added=[waiter]));insert(server,pos+1,row('RESERVE',added=[child]))
    pos=points[2]['sequence']
    insert(server,pos,row('RELEASE',[child]));insert(server,pos+1,row('RELEASE',[waiter]))
    expected={};transactions=[]
    def event(value):
        at=len(events);events.append(value);points.append(dict(eventIndex=at,node=client,sequence=len(traces[client]['changes'])-1,usage={}));return at
    def wire(name,kind,value):
        raw=r.publication.native.f.encode('wire',kind,value);encoded=base64.b64encode(raw).decode()
        event(dict(node=client,event=name,record=r.publication.sha(raw),bytes=encoded));return r.publication.sha(raw)
    _,q=r.source.network.t.wire(events[0]['bytes'])
    for i in (1,2):
        f=r.publication.native.f;catalog=f.catalog()
        record=f.sample(catalog['records']['CERTIFICATE']['schema'],catalog['types']);record['index']=i
        raw_certificate=f.encode('records','CERTIFICATE',record);certificate=r.publication.sha(raw_certificate)
        request=dict(q,recipient=ids[client],trace=f'00000000-0000-0000-0000-{10+i:012d}',payload=dict(certificate=certificate))
        payload=dict(certificate=certificate,selection='d'*64,published=dict(application='a'*64,catalog='b'*64,cut=dict(entry='c'*64,index=i,view=dict(generation=0,new=['node-1','node-2','node-3'],old=['node-1','node-2','node-3'],operation=None))),generation='e'*64)
        expected[client,certificate]=dict(view=q['view'],ballot=q['ballot'],payload=payload)
        binding=wire('LOCAL_SLOT_REQUEST','PUBLISH',request)
        local=charge('WAITER',owner('slot-waiter',binding,10+i),0)
        traces[client]['changes'].append(row('RESERVE',added=[local]))
        transaction=[]
        for name in r.publication.POINTS:
            at=event(dict(node=client,event=name));transaction.append(dict(node=client,eventIndex=at,files={'applied-end/certificate.gsr':raw_certificate}))
        transactions.append(transaction);traces[client]['changes'].append(row('RELEASE',[local]))
        wire('LOCAL_SLOT_RESPONSE','PUBLISH_ACK',dict(request,payload=payload))
    negatives.recount(traces,points)
    return events,wires,traces,points,ids,root,expected,transactions


class SlotControlResourcesTest(unittest.TestCase):
    def test_real_format_transport_and_separate_local_calls(self):
        data=fixture();before=copy.deepcopy(data);result=r.replay(*data)
        self.assertEqual((1,1,1,2,2,4),(result['deliveryReservations'],result['deliveryAttempts'],result['networkWaiters'],
                         result['localWaiters'],result['publicationTransactions'],result['boundReservations']))
        self.assertTrue(result['slotResourcesQualified']);self.assertFalse(result['wholeRuntimeResourcesQualified'])
        self.assertFalse(result['phase3Complete']);self.assertEqual(data,before)

    def test_all_coherent_mutations_reject_for_the_declared_reasons(self):
        data=fixture();before=copy.deepcopy(data);updates=[];result=negatives.replay(data,updates.append)
        self.assertEqual(22,len(result['negatives']));self.assertEqual(data,before)
        self.assertEqual([dict(stage='slot-control-negatives',case=case,completed=i,total=22)
                          for i,case in enumerate(negatives.NEGATIVES,1)],updates)

    def test_unrelated_original_failure_cannot_count_as_rejections(self):
        with patch.object(r,'replay',side_effect=ValueError('bad original')),patch.object(negatives,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'bad original'):negatives.replay([])
            mutate.assert_not_called()

    def test_missing_transport_bytes_fail_before_resource_matching(self):
        data=fixture();data[1][0]['request']=base64.b64encode(b'not a frame').decode()
        with self.assertRaises(ValueError):r.replay(*data)

    def test_legacy_and_absent_bindings_never_pass_strict_mode(self):
        data=fixture();negatives.mutate(data,'legacy-binding')
        with self.assertRaisesRegex(ValueError,'original bindings required'):r.replay(*data)
        self.assertEqual('NOT_OBSERVED',r.replay(*data,require_complete=False)['status'])
        with self.assertRaisesRegex(ValueError,'original bindings required'):r.replay([],[],{},[],{},'a'*64,{},[])

    def test_explicit_scope_and_boolean_policy(self):
        with self.assertRaisesRegex(ValueError,'completeness policy'):r.replay(*fixture(),require_complete=1)
        with self.assertRaisesRegex(ValueError,'slot control policy'):native.validate('unused','3-ADD',slot_control=True)
        with self.assertRaisesRegex(ValueError,'slot control policy'):native.validate('unused',slot_control=1)
        with self.assertRaisesRegex(ValueError,'voting control policy'):native.validate('unused',slot_control=True,voting_control=1)

    def test_unit_uuid_and_closed_lifetime_are_not_guessed(self):
        for mode in ('unit','uuid','close'):
            data=fixture();lives,_=r.scan(data[2]);life=next(v for v in lives.values() if v['role']=='slot-delivery')
            rows=data[2][life['node']]['changes']
            if mode=='close':rows.pop(life['end'])
            else:
                for x in rows[life['start']]['added']+rows[life['end']]['removed']:
                    if mode=='unit':x.update(unit='WAITER',bytes=0)
                    else:x['owner']=x['owner'][:-36]+'00000000-0000-0000-0000-000000000000'
            negatives.recount(data[2],[])
            with self.subTest(mode=mode),self.assertRaises(ValueError):r.scan(data[2])

    def test_complete_drain_does_not_prove_handoff_before_copy(self):
        data=fixture();lives,_=r.scan(data[2]);life=next(v for v in lives.values() if v['role']=='slot-delivery')
        rows=data[2][life['node']]['changes'];rows[1],rows[2]=rows[2],rows[1]
        negatives.recount(data[2],data[3])
        with self.assertRaisesRegex(ValueError,'unique request handoff'):r.replay(*data)

    def test_delivery_must_remain_live_until_actual_ack(self):
        data=fixture();lives,_=r.scan(data[2]);life=next(v for v in lives.values() if v['role']=='slot-delivery')
        rows=data[2][life['node']]['changes'];at=data[3][3]['sequence']+1
        rows.insert(at,rows.pop(life['end']))
        # No transport boundary moves: release immediately after the delivered
        # frame's growth but before its observed delivery, using that sequence.
        data[3][3]['sequence']=at
        negatives.recount(data[2],data[3])
        with self.assertRaisesRegex(ValueError,'delivery released before acknowledgement'):r.replay(*data)

    def test_local_response_requires_original_generation_not_just_certificate(self):
        data=fixture();call=r.local_calls(data[0],data[4],data[5],data[6])[0];ev=data[0][call['offered']]
        kind,value=r.source.network.t.wire(ev['bytes']);value['payload']['generation']='0'*64
        raw=r.publication.native.f.encode('wire',kind,value);ev.update(bytes=base64.b64encode(raw).decode(),record=r.publication.sha(raw))
        with self.assertRaisesRegex(ValueError,'local original acknowledgement'):r.replay(*data)

    def test_local_ack_cannot_be_replayed_as_another_call(self):
        data=fixture();calls=r.local_calls(data[0],data[4],data[5],data[6]);data[0][calls[1]['offered']]=copy.deepcopy(data[0][calls[0]['offered']])
        with self.assertRaisesRegex(ValueError,'local original acknowledgement'):r.replay(*data)

    def test_missing_observations_cannot_infer_local_calls_from_waiter_count(self):
        data=fixture()
        for event in data[0]:
            if event['event'].startswith('LOCAL_SLOT_'):event['event']='UNRECORDED_LOCAL'
        with self.assertRaisesRegex(ValueError,'complete local observations'):r.replay(*data)

    def test_original_publication_must_be_covered_through_last_boundary(self):
        data=fixture();negatives.mutate(data,'publication-after-release')
        with self.assertRaisesRegex(ValueError,'publication waiter custody'):r.replay(*data)


if __name__=='__main__':unittest.main()
