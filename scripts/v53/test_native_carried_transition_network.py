"""Protocol refusal tests; full original history checks are separate receipts."""
import base64
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import native_carried_transition_network as m


class NativeCarriedTransitionNetworkTest(unittest.TestCase):
    def unanswered(self,change=None):
        selected=dict(root='root',view='view',ballot=dict(counter=4),sources=[dict(voter='node-1'),dict(voter='node-3')],
                      cut=dict(view=dict(old=['node-1','node-2','node-3'],new=['node-1','node-2','node-3'])))
        q=dict(sender=dict(node='node-1'),recipient=dict(node='node-2'),ballot=selected['ballot'],view='view',
               payload=dict(promise=m.e.digest(b'promise')))
        values=[dict(kind='PREPARE',request=q,at=2,response=None)]
        events=[dict(node='node-1',event=p) for p in ('begin','GRANT_BEFORE_RETURN','send','SELECTED_FORCED','end')]
        history=SimpleNamespace(root=Path('/original'),ranges=[dict(kind='campaign',start=0,stop=4,after='installed')])
        if change=='selected':q['recipient']['node']='node-3'
        elif change=='foreign':q['recipient']['node']='node-4'
        elif change=='view':q['view']='wrong'
        elif change=='promise':q['payload']['promise']='wrong'
        elif change=='response':values[0]['response']=3
        elif change=='too-early':values[0]['at']=1
        elif change=='too-late':values[0]['at']=3
        elif change=='extra':values*=4
        with patch.object(m.c,'inventory',return_value={}),patch.object(m.c,'current',return_value=('',{'promise.gsr':b'promise','selected.gsr':b'selected'},{})),\
                patch.object(m.f,'decode',return_value=selected):return m.unanswered_prepare(history,events,values)

    def test_unanswered_prepare_cannot_contribute_a_vote_or_skip_the_original_promise(self):
        self.assertTrue(self.unanswered())
        for change in ('selected','foreign'):
            with self.subTest(change=change):self.assertFalse(self.unanswered(change))
        for change in ('view','promise','response','too-early','too-late','extra'):
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'unanswered prepare authority'):self.unanswered(change)

    def checkpoint(self,change=None):
        catalog=m.f.catalog();types=catalog['types'];sample=lambda kind:m.f.sample(catalog['records'][kind]['schema'],types)
        statement=sample('CHECKPOINT');statement['end']['view'].update(old=['node-1','node-2','node-3'],new=['node-1','node-2','node-3'])
        raw=m.f.encode('records','CHECKPOINT',statement);selected=sample('SELECTED')
        selected['sources']=[dict(selected['sources'][0],voter=node) for node in ('node-1','node-3')]
        selected['root']=statement['root'];selected_raw=m.f.encode('records','SELECTED',selected)
        ids={n:dict(m.f.sample(types['identity'],types),node=n) for n in ('node-1','node-2')}
        original={'identity':ids['node-1'],'applied-end/statement.gsr':raw}
        ack=m.f.encode('records','CHECKPOINT_ACK',dict(root=statement['root'],voter='node-2',incarnation=ids['node-2']['storage'],
            cut=statement['end'],statement=m.e.digest(raw)))
        q=dict(root=statement['root'],view=selected['view'],ballot=selected['ballot'],sender=ids['node-1'],recipient=ids['node-2'],
            trace='00000000-0000-0000-0000-000000000010',sequence=1,
            payload=dict(id='00000000-0000-0000-0000-000000000011',action='REQUEST',offset=0,digest=m.e.digest(ack),bytes=''))
        values=[dict(kind='CHUNK',request=q,at=3,received=4,response=None)]
        history=SimpleNamespace(phases=[dict(SELECTED=selected_raw)],applied={(1,'node-1'):original,(1,'node-2'):{'identity':ids['node-2']}})
        if change=='digest':q['payload']['digest']='a'*64
        elif change=='view':q['view']='a'*64
        elif change=='offset':q['payload']['offset']=1
        elif change=='delivered':values[0]['response']=5
        elif change=='outside':values[0]['at']=11
        elif change=='extra':values*=4
        elif change=='selected':
            selected['sources'][1]['voter']='node-2';history.phases[0]['SELECTED']=m.f.encode('records','SELECTED',selected)
        with patch.object(m.d.future,'identity',side_effect=lambda v:v['identity']):
            return m.unused_checkpoint(history,values,{(1,'node-1'):dict(APPLY_BEFORE_RETURN=2,PUBLICATION_VALIDATED=10)})

    def test_silent_checkpoint_lookup_requires_original_statement_unselected_peer_and_interval(self):
        self.assertTrue(self.checkpoint())
        for change in ('digest','outside','selected'):
            with self.subTest(change=change):self.assertFalse(self.checkpoint(change))
        for change in ('view','offset','delivered','extra'):
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'unused checkpoint lookup'):self.checkpoint(change)

    def test_lost_or_late_vote_ack_needs_exact_delivered_retry_in_same_phase(self):
        for kind in ('PREPARE','SELECTED','ACCEPT','PROOF','APPLY'):
            original=dict(kind=kind,answer=kind+'_ACK',request={'trace':'original','sequence':1},
                          response={'receipt':'original'},offered=4,delivered=None)
            good=dict(original,offered=8,delivered=9);stage=dict(start=0,stop=10)
            self.assertTrue(m.recovered_delivery(original,[original,good],stage))
            self.assertTrue(m.recovered_delivery(original,[dict(good,offered=2,delivered=3),original],stage))
            for change in ({'request':{'trace':'new','sequence':1}}, {'response':{'receipt':'forged'}},
                           {'kind':'STATUS_PROBE'}, {'answer':'STATUS'}, {'delivered':None},
                           {'offered':-2,'delivered':-1}, {'delivered':11}):
                with self.subTest(kind=kind,change=change):
                    self.assertFalse(m.recovered_delivery(original,[original,dict(good,**change)],stage))

    def transport(self,change=None):
        catalog=m.f.catalog();types=catalog['types'];events=[];wires=[];groups={}
        base=m.f.sample(catalog['wire']['STATUS_PROBE']['schema'],types)
        identities={f'node-{i}':dict(m.f.sample(types['identity'],types,i),node=f'node-{i}') for i in (1,2)}
        first_trace=base['trace']
        for life in (1,2):
            kind='HEARTBEAT' if change in ('undelivered-heartbeat','cross-death-heartbeat') and life==1 else 'STATUS_PROBE'
            answer='HEARTBEAT_ACK' if kind=='HEARTBEAT' else 'STATUS'
            cut=m.f.sample(types['cut'],types);cut['view']['generation']=life
            q=deepcopy(base);q.update(sender=identities['node-1'],recipient=identities['node-2'],
                view=m.e.authority(q['root'],cut['view']),trace=f'00000000-0000-0000-0000-{life:012d}')
            if life==1:first_trace=q['trace']
            if life==2 and change=='trace':q['trace']=first_trace
            if life==2 and change=='view':q['view']=m.e.authority(q['root'],groups['one']['node-1']['capsule']['cut']['view'])
            if kind=='HEARTBEAT':q['payload']=dict(cut=cut,activated=True)
            a=dict(q,sender=q['recipient'],recipient=q['sender'],payload=dict(cut=cut) if kind=='HEARTBEAT' else dict(nonce=q['payload']['nonce'],cut=cut,ready=False))
            qr=m.f.encode('wire',kind,q);ar=m.f.encode('wire',answer,a);qh,ah=m.e.digest(qr),m.e.digest(ar)
            wire=dict(request=base64.b64encode(qr).decode(),response=base64.b64encode(ar).decode(),withheld=False)
            wires.append(wire)
            events.extend([dict(node='node-1',incarnation=life,event='NETWORK_SEND',kind=kind,request=qh,bytes=wire['request']),
                dict(node='node-2',incarnation=life,event='NETWORK_REQUEST',kind=kind,request=qh),
                dict(node='node-2',incarnation=life,event='WIRE_RESPONSE',request=qh,response=ah),
                dict(node='node-1',incarnation=life,event='NETWORK_RECEIVED',kind=answer,response=ah)])
            if life==1:events.append(dict(event='GROUP_CRASH',incarnation=1))
            groups['one' if life==1 else 'two']={n:dict(identity=v,capsule=dict(root=q['root'],cut=cut)) for n,v in identities.items()}
        if change in ('send-life','read-life','reply-life','delivery-life'):
            events[('send-life','read-life','reply-life','delivery-life').index(change)]['incarnation']=2
        elif change in ('cross-death','cross-death-heartbeat'):
            delivery=deepcopy(events[3]);delivery['incarnation']=2;events[3]=dict(event='NOT_TRANSPORT')
            events.insert(8,delivery)
        elif change=='outside':events.append(dict(events[0],incarnation=2))
        elif change=='silent':
            wires.pop(0);events[2]=events[3]=dict(event='NOT_TRANSPORT')
        elif change in ('undelivered-heartbeat','undelivered-status'):events[3]=dict(event='NOT_TRANSPORT')
        ranges=[dict(start=-1,stop=4,life=1,before='one'),dict(start=4,stop=10 if change in ('cross-death','cross-death-heartbeat') else 9,life=2,before='two')]
        history=SimpleNamespace(ranges=ranges)
        with patch.object(m.forces,'group',side_effect=lambda root,name:groups['one' if name=='before-network' else name]),\
                patch.object(m.d.future,'identity',side_effect=lambda files:files['identity']),\
                patch.object(m.c,'current',side_effect=lambda files:('',{},dict(capsule=files['capsule']))),\
                patch.object(m.process,'read',return_value=wires):
            return m.transport(Path('/original'),history,events)

    def test_each_phase_uses_its_derived_membership_authority(self):
        _,rows,_,_=self.transport();self.assertEqual(2,len(rows))
        self.assertNotEqual(rows[0]['request']['view'],rows[1]['request']['view'])
        with self.assertRaisesRegex(ValueError,'original send bytes/identity'):self.transport('view')

    def test_all_transport_boundaries_belong_to_the_original_group_life(self):
        for change in ('send-life','read-life','reply-life','delivery-life','cross-death'):
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'crosses phase or group death'):self.transport(change)

    def test_cross_phase_trace_reuse_and_unbound_writes_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'trace reused across phases'):self.transport('trace')
        with self.assertRaisesRegex(ValueError,'send outside history'):self.transport('outside')

    def test_unanswered_original_request_never_becomes_a_response(self):
        _,rows,sent,_=self.transport('silent')
        self.assertEqual(1,len(rows));self.assertEqual(1,sum(v['response'] is None for values in sent.values() for v in values))

    def test_offered_unreceived_heartbeat_does_not_invent_client_delivery(self):
        _,rows,sent,_=self.transport('undelivered-heartbeat')
        self.assertEqual('HEARTBEAT',rows[0]['kind']);self.assertIsNone(rows[0]['delivered'])
        self.assertEqual(2,len(rows));self.assertEqual(2,sum(len(v) for v in sent.values()))

    def test_undelivered_control_and_cross_death_heartbeat_are_still_rejected(self):
        with self.assertRaisesRegex(ValueError,'undelivered required response'):self.transport('undelivered-status')
        with self.assertRaisesRegex(ValueError,'delivery crosses phase or group death'):self.transport('cross-death-heartbeat')

    def test_unclassified_silence_cannot_supply_a_quorum(self):
        history=SimpleNamespace(phases=[])
        values=[dict(kind='ACCEPT',request=dict(recipient=dict(node='node-2')),response=None)]
        with self.assertRaisesRegex(ValueError,'unclassified unanswered request'):m.silents(history,[],[],{'x':values},set(),{})

    def slot(self,*,sequence=5,voters=None):
        selected=dict(ballot={'counter':5},sources=[dict(voter=n) for n in ('node-1','node-2','node-3')],
            cut=dict(view=dict(old=['node-1','node-2','node-3','node-4'],new=['node-1','node-2','node-3'])))
        stage=dict(start=-1,stop=4,kind='slot',before='original-installed',index=6)
        history=SimpleNamespace(root=Path('/original'),ranges=[stage])
        event=dict(node='node-1',event='FUTURE_QUORUM_COMPLETE',index=6,voters=voters or ['node-1','node-2','node-3'])
        row=dict(kind='PUBLISH',offered=2,request=dict(sender=dict(node='node-1'),recipient=dict(node='node-2'),
            ballot=selected['ballot'],sequence=sequence))
        with patch.object(m.c,'inventory',return_value={}),patch.object(m.c,'current',return_value=('',{'selected.gsr':b'original'},{})),\
                patch.object(m.f,'decode',return_value=selected):m.slot_envelopes(history,[event,deepcopy(event)], [row])

    def test_joint_slot_does_not_use_the_old_fixed_pair_or_three_node_sequence(self):
        self.slot()
        with self.assertRaisesRegex(ValueError,'original slot envelope'):self.slot(sequence=4)
        with self.assertRaisesRegex(ValueError,'exact original recording quorums'):self.slot(voters=['node-1','node-2'])

    def test_invalid_original_prevents_wire_and_negative_credit(self):
        with patch.object(m.process.collection,'inventory',return_value={}),\
                patch.object(m.forces,'validate',side_effect=ValueError('bad original')),patch.object(m,'replay') as wire,patch.object(m.shutil,'copytree') as copies:
            with self.assertRaisesRegex(ValueError,'^bad original$'):m.qualify('/original')
            wire.assert_not_called();copies.assert_not_called()

    def test_storage_mutation_cannot_manufacture_a_network_negative(self):
        original=dict(files={'pending.accept':'a'},directories=[]);changed=dict(files={'pending.accept':'b'},directories=[])
        with patch.object(m.process.collection,'inventory',side_effect=[original,changed]),patch.object(m,'validate',return_value={}) as validate,\
                patch.object(m.shutil,'copytree'),patch.object(m.mutation,'mutate'),patch.object(m,'NEGATIVES',{'one':'refusal'}):
            with self.assertRaisesRegex(ValueError,'negative changed storage input'):m.qualify('/original')
            validate.assert_called_once_with(Path('/original'))

    def test_unrelated_refusal_is_never_negative_success(self):
        inventory=dict(files={},directories=[])
        for effect,reason in (({},'accepted mutation'),(ValueError('different error'),'wrong negative')):
            with patch.object(m.process.collection,'inventory',return_value=inventory),patch.object(m,'validate',side_effect=[{},effect]),\
                    patch.object(m.shutil,'copytree'),patch.object(m.mutation,'mutate'),patch.object(m,'NEGATIVES',{'one':'expected refusal'}):
                with self.assertRaisesRegex(ValueError,reason):m.qualify('/original')

    def test_mutating_original_during_replay_cannot_pass(self):
        original=dict(original=dict(physical=dict(kind='FINAL')))
        with patch.object(m.process.collection,'inventory',side_effect=[{},dict(changed=True)]),\
                patch.object(m.forces,'validate',return_value=original),patch.object(m,'replay',return_value={}):
            with self.assertRaisesRegex(ValueError,'original changed'):m.validate('/original')


if __name__=='__main__':unittest.main()
