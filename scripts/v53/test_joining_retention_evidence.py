"""Conditional source/ledger tests; no synthetic capsule is native authority."""
import copy
import struct
import unittest
from unittest.mock import patch
from . import joining_retention_evidence as e
from . import generation_install_evidence as generation
from .test_source_packet import fixture


class Inputs:
    def __init__(self,size=3,replace=False):
        f=e.f;types=f.catalog()['types'];raw,_,self.objects=fixture();cap=f.decode(raw,'records','CAPSULE')
        self.identities=[dict(node='node-'+str(i),storage='00000000-0000-0000-0000-'+str(i).zfill(12),
                             host='127.0.0.1',port=19000+i) for i in range(1,size+2)]
        self.joining=self.identities[-1];old=[v['node'] for v in self.identities[:-1]]
        new=old[:-1]+[self.joining['node']] if replace else old+[self.joining['node']]
        self.view=dict(generation=0,old=old,new=new,operation='b'*64)
        cap['cut']=dict(index=6,entry='c'*64,view=self.view)
        catalog=f.decode(self.objects[cap['catalog']],'records','CATALOG')
        self.request=dict(root=cap['root'],expected='a'*64,number=1,kind='REPLACE' if replace else 'ADD',
                          target=[v for v in self.identities if v['node'] in new])
        operation=f.sample('operation',types);operation['request']=self.request
        catalog.update(cut=cap['cut'],identities=self.identities,results=[operation])
        catalog_bytes=f.encode('records','CATALOG',catalog);self.objects[e.sha(catalog_bytes)]=catalog_bytes
        self.cap=dict(cap,catalog=e.sha(catalog_bytes));self.images={cap['application']:len(b'independent image')}
        self.current=e.packet.decode(generation.packet_bytes(self.cap,self.objects,self.images))
        self.ballot=dict(counter=2,proposer=old[0],incarnation=self.identities[0]['storage'])
        self.peer_plans=[];self.learner_plans=[]
        for i in range(size//2+1):
            endpoint=self.endpoint(3+i)
            self.peer_plans.append(dict(root=cap['root'],view=self.view,
                peers=[dict(identity=v,possible=[endpoint]) for v in self.identities]))
            self.learner_plans.append(dict(root=cap['root'],request=self.request,learner=self.joining,possible=[endpoint]))

    def endpoint(self,index):
        return dict(cut=dict(self.cap['cut'],index=index),catalog=str(index)*64,application=self.cap['application'])

    def sources(self,change=None):
        rows=[]
        for i,(peers,learner) in enumerate(zip(self.peer_plans,self.learner_plans)):
            owner=self.identities[i];promise=dict(root=self.cap['root'],view=e.sha(e.f.canonical(dict(root=self.cap['root'],**self.view))),
                ballot=self.ballot,basisId='00000000-0000-0000-0001-'+str(i+1).zfill(12))
            metadata=dict(root=self.cap['root'],owner=owner,revision=0,previous=None)
            peer=e.peer_source.r.frame(dict(metadata,plan=peers));learner=e.learner.frame(dict(metadata,plan=learner))
            objects=dict(self.objects);promise_raw=e.f.encode('records','PROMISE',promise)
            for wrapped in [e.peer_source.wrap(promise_raw,peer),e.learner.wrap(promise_raw,learner)]:objects[e.sha(wrapped)]=wrapped
            raw=generation.packet_bytes(self.cap,objects,self.images);packet=e.packet.decode(raw)
            basis=dict(promise,voter=owner['node'],cut=self.cap['cut'],capsule=e.sha(packet['capsuleBytes']),
                       inventory=e.sha(packet['indexBytes']),accepted=None)
            if change:change(i,basis)
            rows.append((e.f.encode('records','BASIS',basis),raw))
        return rows


class JoiningRetentionEvidenceTest(unittest.TestCase):
    def test_all_joining_profiles_preserve_union_and_start_new_owner_at_zero(self):
        for size,replace in [(3,False),(4,False),(3,True),(4,True),(5,True)]:
            with self.subTest(size=size,replace=replace):
                v=Inputs(size,replace)
                # Three old sources may repeat an endpoint; never require three
                # endpoints to pass a frozen two-endpoint capacity contract.
                for plans in (v.peer_plans,v.learner_plans):
                    if len(plans)==3:plans[2]=copy.deepcopy(plans[0])
                seed,initial=e.derive(v.current,v.joining,v.sources())
                self.assertEqual(len(v.sources()),len(e.snapshot.s.e.parse(seed)['sources']))
                for name,decode in [(e.LEDGERS[0],e.peer_source.r.decode),(e.LEDGERS[2],e.learner.decode)]:
                    state=decode(initial[name]);self.assertEqual(v.joining,state['owner']);self.assertEqual(0,state['revision']);self.assertIsNone(state['previous'])
                plan=e.peer_source.r.decode(initial[e.LEDGERS[0]])['plan']
                self.assertEqual([3,4],[a['cut']['index'] for a in plan['peers'][0]['possible']])
                self.assertEqual([3,4],[a['cut']['index'] for a in e.learner.decode(initial[e.LEDGERS[2]])['plan']['possible']])
                self.assertEqual(e.future.frame(dict(root=v.cap['root'],owner=v.joining,revision=0,previous=None,parent=None,peers=[]),{}),initial[e.LEDGERS[1]])

    def test_minority_duplicate_nonold_and_mixed_ballots_cannot_initialize(self):
        v=Inputs();original=v.sources()
        for rows in [original[:1],original[::-1],[original[0],original[0]],v.sources(lambda i,b:b.update(voter=v.joining['node']) if i else None),
                     v.sources(lambda i,b:b.update(ballot=dict(b['ballot'],counter=3)) if i else None)]:
            with self.subTest(rows=len(rows)),self.assertRaises(ValueError):e.derive(v.current,v.joining,rows)

    def test_foreign_or_already_old_joining_identity_refuses(self):
        v=Inputs()
        for joining in [v.identities[0],dict(v.joining,storage=v.identities[0]['storage'])]:
            with self.assertRaisesRegex(ValueError,'exact new identity'):e.derive(v.current,joining,v.sources())

    def test_well_encoded_source_with_wrong_promise_cannot_supply_ledger(self):
        v=Inputs();rows=v.sources(lambda i,b:b.update(basisId='00000000-0000-0000-0000-000000000099') if i else None)
        with self.assertRaisesRegex(ValueError,'unique frozen ledger'):e.derive(v.current,v.joining,rows)

    def test_changed_same_index_and_third_endpoint_refuse(self):
        v=Inputs();v.peer_plans[1]['peers'][0]['possible']=[dict(v.endpoint(3),catalog='d'*64)]
        with self.assertRaisesRegex(ValueError,'conflicting endpoint'):e.derive(v.current,v.joining,v.sources())
        v=Inputs();v.learner_plans[0]['possible']=[v.endpoint(2),v.endpoint(3)]
        with self.assertRaisesRegex(ValueError,'conservative endpoint capacity'):e.derive(v.current,v.joining,v.sources())

    def test_decoded_renewals_survive_merge_without_discharge(self):
        v=Inputs();v.learner_plans[0]['possible']=[v.endpoint(4)];v.learner_plans[0]['renewals']=[v.endpoint(3)]
        _,initial=e.derive(v.current,v.joining,v.sources())
        self.assertEqual([3,4],[a['cut']['index'] for a in e.learner.decode(initial[e.LEDGERS[2]])['plan']['possible']])

    def test_wrong_peer_identity_and_missing_catalog_operation_refuse(self):
        v=Inputs();v.peer_plans[0]['peers'][0]['identity']=v.joining
        with self.assertRaisesRegex(ValueError,'peer identity'):e.derive(v.current,v.joining,v.sources())
        v=Inputs();v.learner_plans[0]['request']=dict(v.request,number=2)
        with self.assertRaisesRegex(ValueError,'learner operation'):e.derive(v.current,v.joining,v.sources())

    def test_wrapper_truncation_checksum_and_future_flags_refuse(self):
        v=Inputs();basis,raw=v.sources()[0];packet=e.packet.decode(raw)
        wrapped,_=e.source(packet,e.f.decode(basis,'records','BASIS'),0x47535250,65536)
        for bad in [wrapped[:10],wrapped[:-1],wrapped+b'x',wrapped[:16]+b'0'*32+wrapped[48:]]:
            with self.assertRaises(ValueError):e.frozen(bad,0x47535250,65536)
        bad=bytearray(wrapped);bad[8:12]=struct.pack('>I',1);bad[16:48]=bytes.fromhex(e.sha(bad[:16]+bad[48:]))
        with self.assertRaisesRegex(ValueError,'settled wrapper'):e.frozen(bytes(bad),0x47535250,65536)

    def test_valid_checksum_does_not_make_an_unsettled_source_acceptable(self):
        v=Inputs();rows=v.sources(lambda i,b:b.update(accepted='f'*64))
        with self.assertRaisesRegex(ValueError,'unsettled tail'):e.derive(v.current,v.joining,rows)

    def test_unknown_or_trailing_transaction_members_refuse(self):
        self.assertEqual([b'a',b'b'],e.parts(e.part(b'a')+e.part(b'b'),[1,1]))
        for raw in [b'',e.part(b'a'),e.part(b'aa')+e.part(b'b'),e.part(b'a')+e.part(b'b')+b'x']:
            with self.assertRaises(ValueError):e.parts(raw,[1,1])

    def test_original_failure_never_counts_as_mutation_rejection(self):
        with patch.object(e,'validate',side_effect=ValueError('invalid original')) as original,patch.object(e.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'invalid original'):e.qualify('/absent')
            original.assert_called_once_with('/absent');copied.assert_not_called()

    def test_different_peers_cannot_claim_conflicting_or_future_history(self):
        for index in (3,7):
            v=Inputs();v.peer_plans[0]['peers'][1]['possible']=[dict(v.endpoint(index),catalog='d'*64)]
            with self.subTest(index=index),self.assertRaisesRegex(ValueError,'inconsistent history endpoint'):
                e.derive(v.current,v.joining,v.sources())


if __name__=='__main__':unittest.main()
