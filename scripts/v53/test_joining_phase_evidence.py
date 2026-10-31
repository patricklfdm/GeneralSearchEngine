import base64
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from . import joining_phase_evidence as j
from . import test_joining_catalog_evidence as fixture


class JoiningPhaseEvidenceTest(unittest.TestCase):
    def wire(self, scoped=False):
        _, _, identities, root = fixture.JoiningCatalogEvidenceTest().phase()
        peer = 'node-4' if scoped else 'node-2'
        q = dict(root=root,view='b'*64,ballot=dict(counter=2,proposer='node-1',incarnation=identities['node-1']['storage']),
                 sender=identities['node-1'],recipient=identities[peer],trace=str(uuid.UUID(int=20)),sequence=1,
                 payload=dict(acceptance='c'*64))
        a = dict(q,sender=q['recipient'],recipient=q['sender'],payload=dict(entry='d'*64,receipt='e'*64))
        qr=j.f.encode('wire','ACCEPT',q);ar=j.f.encode('wire','ACCEPT_ACK',a)
        wire=dict(request=base64.b64encode(qr).decode(),response=base64.b64encode(ar).decode(),withheld=False)
        offered=dict(node=peer,event='WIRE_RESPONSE',request=j.sha(qr),response=j.sha(ar))
        if scoped: offered.update(event='BEFORE_RESPONSE_WRITE',scope='continuation-endpoint',kind='ACCEPT',responseKind='ACCEPT_ACK')
        delivered=dict(node='node-1',event='NETWORK_RECEIVED',kind='ACCEPT_ACK',response=j.sha(ar))
        return [offered,delivered],[wire],identities,root,q,a

    def test_scoped_and_original_responses_bind_one_delivery(self):
        for scoped in (False,True):
            events,wire,identities,root,q,a=self.wire(scoped)
            rows=j.exchanges(events,wire,identities,root)
            self.assertEqual((0,1),(rows[0]['offered'],rows[0]['delivered']))
            self.assertEqual(a,rows[0]['response'])
            rows=j.exchanges(events[:1],wire,identities,root)
            self.assertIsNone(rows[0]['delivered'])

    def test_duplicate_or_early_delivery_cannot_supply_a_second_ack(self):
        for mode in ('duplicate','early'):
            events,wire,identities,root,_,_=self.wire()
            changed=events+[dict(events[-1])] if mode=='duplicate' else list(reversed(events))
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'^joining delivery without original response$'):
                j.exchanges(changed,wire,identities,root)

    def test_no_wire_or_event_may_be_invented_or_omitted(self):
        events,wire,identities,root,_,_=self.wire()
        for es,ws,reason in [(events,[],'joining unmatched original response'),([],wire,'joining missing original response'),
                              (events,wire*2,'joining missing original response')]:
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,'^'+reason+'$'):
                j.exchanges(es,ws,identities,root)

    def test_response_owner_and_permanent_identity_are_required(self):
        for mode in ('owner','incarnation','root'):
            events,wire,identities,root,_,_=self.wire()
            if mode=='owner': events[0]['node']='node-3'
            elif mode=='incarnation': identities=copy.deepcopy(identities);identities['node-2']['storage']=str(uuid.UUID(int=99))
            else: root='f'*64
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'^joining wire permanent identity$'):
                j.exchanges(events,wire,identities,root)

    def test_scoped_receiver_must_name_actual_response_kind(self):
        events,wire,identities,root,_,_=self.wire(True);events[0]['responseKind']='PROOF_ACK'
        with self.assertRaisesRegex(ValueError,'^joining response event kind$'): j.exchanges(events,wire,identities,root)

    def test_phase_ack_requires_original_bytes_and_causal_delivery(self):
        events,wire,identities,root,q,a=self.wire();rows=j.exchanges(events,wire,identities,root)
        selected={k:q[k] for k in ('ballot','view')}
        self.assertEqual(rows,j.control(rows,'ACCEPT','node-2',q['payload'],a['payload'],selected,-1,2))
        with self.assertRaisesRegex(ValueError,'^joining original phase ACK$'):
            j.control(rows,'ACCEPT','node-2',q['payload'],dict(a['payload'],receipt='0'*64),selected,-1,2)
        for lower,upper in [(0,2),(-1,1)]:
            with self.subTest(lower=lower,upper=upper),self.assertRaisesRegex(ValueError,'^joining force before delivered phase ACK$'):
                j.control(rows,'ACCEPT','node-2',q['payload'],a['payload'],selected,lower,upper)

    def test_undelivered_response_is_not_a_phase_ack(self):
        events,wire,identities,root,q,a=self.wire();rows=j.exchanges(events[:1],wire,identities,root)
        with self.assertRaisesRegex(ValueError,'^joining force before delivered phase ACK$'):
            j.control(rows,'ACCEPT','node-2',q['payload'],a['payload'],q,-1,2)

    def test_retry_count_and_identical_bytes_remain_bounded(self):
        events,wire,identities,root,q,a=self.wire();rows=j.exchanges(events,wire,identities,root)
        with self.assertRaisesRegex(ValueError,'^joining complete bounded phase control$'):
            j.control(rows*4,'ACCEPT','node-2',q['payload'],a['payload'],q,-1,2)
        changed=copy.deepcopy(rows[0]);changed['response']['payload']['receipt']='f'*64
        with self.assertRaisesRegex(ValueError,'^joining identical phase retries$'):
            j.control([*rows,changed],'ACCEPT','node-2',q['payload'],a['payload'],q,-1,2)

    def test_every_original_slot_force_is_required_in_order(self):
        parts,_,_,_=fixture.JoiningCatalogEvidenceTest().phase();replay=SimpleNamespace(phases=[parts],old=('node-1','node-2','node-3'),joining='node-4')
        events=[dict(node=node,event=event) for node in ('node-1','node-2') for event in j.force_names()]
        self.assertEqual(2,len(j.blocks(events,replay)))
        for ordinal in range(len(j.force_names())):
            with self.subTest(event=j.force_names()[ordinal]),self.assertRaisesRegex(ValueError,'^joining exact slot force order: node-1$'):
                j.blocks(events[:ordinal]+events[ordinal+1:],replay)

    def test_joined_slot_forces_cannot_come_from_a_different_lifetime(self):
        parts,_,_,_=fixture.JoiningCatalogEvidenceTest().phase(True);replay=SimpleNamespace(phases=[parts],old=('node-1','node-2','node-3'),joining='node-4')
        events=[dict(node=node,event=event,**(dict(scope='continuation-owner') if node=='node-4' else {}))
                for node in ('node-1','node-2','node-4') for event in j.force_names()]
        self.assertEqual(3,len(j.blocks(events,replay)))
        events[-1]['scope']='stable-cold-owner'
        with self.assertRaisesRegex(ValueError,'^joining force owner lifetime$'):j.blocks(events,replay)

    def test_original_must_pass_before_mutations(self):
        with patch.object(j,'validate',side_effect=ValueError('original failed')),patch.object(j.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^original failed$'):j.qualify(Path('/original'))
            copied.assert_not_called()

    def test_profile_force_owners_do_not_alias_old_node_four_with_the_joiner(self):
        for size in (3,4,5):
            old=tuple('node-'+str(i) for i in range(1,size+1));joining='node-'+str(size+1)
            selected=(*old[:size//2],old[-1],joining)
            replay=SimpleNamespace(old=old,joining=joining,phases=[{'CERTIFICATE':b'original'}])
            cert=dict(proofs=[dict(voter=n) for n in selected])
            events=[dict(node=n,event=e,**({'scope':'continuation-owner'} if n==joining else {}))
                    for n in selected for e in j.force_names()]
            with self.subTest(size=size),patch.object(j.f,'decode',return_value=cert):
                self.assertEqual({(1,n) for n in selected},set(j.blocks(events,replay)))
                with self.assertRaisesRegex(ValueError,'^joining exact slot force order: '+joining+'$'):
                    j.blocks(events[:-1],replay)
                events[-1]['scope']='old-owner'
                with self.assertRaisesRegex(ValueError,'^joining force owner lifetime$'):j.blocks(events,replay)

    def test_foreign_force_owner_cannot_disappear_outside_the_known_profile(self):
        parts,_,_,_=fixture.JoiningCatalogEvidenceTest().phase()
        replay=SimpleNamespace(phases=[parts],old=('node-1','node-2','node-3'),joining='node-4')
        events=[dict(node=n,event=e) for n in replay.old[:2] for e in j.force_names()]
        with self.assertRaisesRegex(ValueError,'^joining slot force unknown owner$'):
            j.blocks(events+[dict(node='node-99',event=j.force_names()[0])],replay)

    def test_metadata_force_multiplicity_and_parent_order_are_checked(self):
        names=['APPLY_METADATA_FORCED']*4+['APPLY_PARENT_STATEMENT_FORCED']
        events=[dict(node='node-2',event=v) for v in names]
        j.forced_interval(events,'node-2',-1,len(events),names,'bad interval')
        for changed in (events[1:],list(reversed(events))):
            with self.assertRaisesRegex(ValueError,'^bad interval$'):
                j.forced_interval(changed,'node-2',-1,len(changed),names,'bad interval')

    def test_empty_future_requires_original_frame_and_owner(self):
        _,_,identities,root=fixture.JoiningCatalogEvidenceTest().phase()
        meta=dict(root=root,owner=identities['node-1'],revision=0,previous=None,parent=None,peers=[])
        raw=j.future.frame(meta,{})
        with patch.object(j.future,'initial',return_value=meta):
            self.assertEqual(meta,j.empty_future(raw,{}))
            with self.assertRaisesRegex(ValueError,'^joining original empty future ledger$'):j.empty_future(raw+b'extra',{})
        with patch.object(j.future,'initial',return_value=dict(meta,owner=identities['node-2'])):
            with self.assertRaisesRegex(ValueError,'^joining original empty future ledger$'):j.empty_future(raw,{})

    def test_unrelated_mutation_rejection_does_not_count(self):
        with patch.object(j,'validate',side_effect=[{},ValueError('wrong gate')]),patch.object(j.shutil,'copytree'),patch.object(j,'mutate'):
            with self.assertRaisesRegex(ValueError,'^joining unrelated phase negative:'):j.qualify(Path('/original'))


if __name__=='__main__':unittest.main()
