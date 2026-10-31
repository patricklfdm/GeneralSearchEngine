"""Conditional merger tests; generated records are not native force evidence."""
import base64
import copy
import unittest
from unittest.mock import patch
from .test_joining_retention_evidence import Inputs
from . import joining_retention_evidence as e
from . import joining_confirmation_evidence as c


def proof(v, node, point, generation='a'):
    return base64.b64encode(e.f.encode('records','GENERATION',dict(root=v.cap['root'],node=node,generation=generation,
        **point,capsule='e'*64,promise='f'*64,basis=None,selection=None,ownedTail=None,
        files=[dict(path='source.gscp',size=1,sha256='e'*64)]))).decode()


def fixture(size=3, replace=False):
    v=Inputs(size,replace)
    if len(v.peer_plans)==3:
        v.peer_plans[2]=copy.deepcopy(v.peer_plans[0]);v.learner_plans[2]=copy.deepcopy(v.learner_plans[0])
    row=v.peer_plans[0]['peers'][0];row.update(possible=[v.endpoint(5)],renewals=[v.endpoint(3),v.endpoint(4)],
        confirmation=proof(v,row['identity']['node'],v.endpoint(5)))
    return v


def derive(v):return e.derive(v.current,v.joining,v.sources(),confirmed_peers=True)


class JoiningConfirmationEvidenceTest(unittest.TestCase):
    def test_all_profiles_discharge_peer_renewals_but_keep_other_peers_and_learner_debt(self):
        for size,replace in [(3,False),(4,False),(3,True),(4,True),(5,True)]:
            with self.subTest(size=size,replace=replace):
                v=fixture(size,replace);_,initial=derive(v);plan=e.peer_source.r.decode(initial[e.LEDGERS[0]])['plan']
                self.assertEqual([v.endpoint(5)],plan['peers'][0]['possible']);self.assertNotIn('renewals',plan['peers'][0])
                self.assertEqual(v.peer_plans[0]['peers'][0]['confirmation'],plan['peers'][0]['confirmation'])
                self.assertEqual([v.endpoint(3),v.endpoint(4)],plan['peers'][1]['possible'])
                self.assertEqual([v.endpoint(3),v.endpoint(4)],e.learner.decode(initial[e.LEDGERS[2]])['plan']['possible'])

    def test_explicit_mode_and_legacy_bytes_remain_required(self):
        v=fixture()
        with self.assertRaisesRegex(ValueError,'peer identity'):e.derive(v.current,v.joining,v.sources())
        v=Inputs();self.assertEqual(e.derive(v.current,v.joining,v.sources()),derive(v))

    def test_conflicts_are_rejected_before_confirmed_discharge(self):
        for other in (0,1):
            v=fixture();v.peer_plans[1]['peers'][other]['possible']=[dict(v.endpoint(3),catalog='f'*64)]
            with self.subTest(other=other),self.assertRaisesRegex(ValueError,'inconsistent original endpoint'):derive(v)

    def test_future_endpoint_and_foreign_permanent_identity_or_view_refuse(self):
        for field in ('future','identity','view','root'):
            v=fixture();row=v.peer_plans[0]['peers'][0]
            if field=='future':row.update(possible=[v.endpoint(7)],confirmation=proof(v,'node-1',v.endpoint(7)))
            elif field=='identity':row['identity']=dict(row['identity'],storage=v.joining['storage'])
            elif field=='view':v.peer_plans[0]['view']=dict(v.view,generation=1)
            else:v.peer_plans[0]['root']='f'*64
            with self.subTest(field=field),self.assertRaises(ValueError):derive(v)

    def test_unconfirmed_later_endpoint_survives_but_three_unresolved_points_refuse(self):
        v=fixture();terminal=c.anchor(v.cap);v.peer_plans[1]['peers'][0]['possible']=[v.endpoint(4),terminal]
        plan=e.peer_source.r.decode(derive(v)[1][e.LEDGERS[0]])['plan']
        self.assertEqual([v.endpoint(5),terminal],plan['peers'][0]['possible'])
        v=fixture();del v.peer_plans[0]['peers'][0]['confirmation']
        with self.assertRaisesRegex(ValueError,'unresolved endpoint capacity'):derive(v)

    def test_highest_confirmation_then_digest_tie_is_deterministic(self):
        v=fixture();row=v.peer_plans[1]['peers'][0]
        row.update(possible=[v.endpoint(5)],confirmation=proof(v,'node-1',v.endpoint(5),'b'))
        expected=min([p['peers'][0]['confirmation'] for p in v.peer_plans],key=lambda p:e.sha(base64.b64decode(p)))
        self.assertEqual(expected,e.peer_source.r.decode(derive(v)[1][e.LEDGERS[0]])['plan']['peers'][0]['confirmation'])
        row.update(possible=[v.endpoint(4)],confirmation=proof(v,'node-1',v.endpoint(4),'b'))
        self.assertEqual(v.peer_plans[0]['peers'][0]['confirmation'],e.peer_source.r.decode(derive(v)[1][e.LEDGERS[0]])['plan']['peers'][0]['confirmation'])

    def test_learner_debt_is_never_discharged_by_peer_confirmation(self):
        v=fixture();v.learner_plans[0].update(possible=[v.endpoint(5)],renewals=[v.endpoint(3),v.endpoint(4)])
        with self.assertRaisesRegex(ValueError,'conservative endpoint capacity'):derive(v)

    def test_original_failure_in_new_mode_stops_before_mutations(self):
        with patch.object(e,'validate',side_effect=ValueError('invalid original')) as original,patch.object(e.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'invalid original'):e.qualify('/absent',confirmed_peers=True)
            original.assert_called_once_with('/absent',confirmed_peers=True);copied.assert_not_called()

    def test_source_ancestry_inputs_cannot_be_omitted_or_truncated_silently(self):
        v=fixture()
        with self.assertRaisesRegex(ValueError,'ancestry inputs'):
            e.derive(v.current,v.joining,v.sources(),confirmed_peers=True,source_ancestry=[])
        with self.assertRaisesRegex(ValueError,'original ancestry missing'):
            e.derive(v.current,v.joining,v.sources(),confirmed_peers=True,source_ancestry=[b'',b''])


class JoiningEndpointBindingTest(unittest.TestCase):
    def setUp(self):
        self.v=Inputs();self.packet=copy.deepcopy(self.v.current);self.lower=self.v.endpoint(3);self.upper=self.v.endpoint(4)
        stable=dict(self.v.view,new=self.v.view['old'],operation=None)
        for p in (self.lower,self.upper):p['cut']['view']=stable
        def statement(start,end,scope):return e.f.encode('records','CHECKPOINT',dict(root=self.v.cap['root'],scope=scope,
            start=start['cut'],end=end['cut'],catalogBefore=start['catalog'],catalogAfter=end['catalog'],
            applicationBefore=start['application'],applicationAfter=end['application']))
        raw=statement(self.upper,c.anchor(self.v.cap),'MEMBERSHIP')
        self.packet['objects'][e.sha(raw)]=raw;self.packet['capsule']['items']=[dict(statement=e.sha(raw))]
        self.bridge=statement(self.lower,self.upper,'RANGE');self.acks=[]
        for identity in self.v.identities[:2]:
            self.acks.append(e.f.encode('records','CHECKPOINT_ACK',dict(root=self.v.cap['root'],voter=identity['node'],
                incarnation=identity['storage'],cut=self.upper['cut'],statement=e.sha(self.bridge))))

    def test_original_bridge_checks_both_endpoints_and_every_ack(self):
        raw=self.bridge+b''.join(self.acks);self.assertEqual(self.lower,c.endpoints(self.packet,raw)[3])
        for label,data in [('missing-ack',self.bridge+self.acks[0]),('duplicate',raw+raw),
                           ('orphan',self.acks[0]+raw),('torn',raw[:-1]),('reordered',self.bridge+b''.join(reversed(self.acks)))]:
            with self.subTest(label=label),self.assertRaises(ValueError):c.endpoints(self.packet,data)
        for field in ('catalogAfter','scope','end'):
            value=e.f.decode(self.bridge,'records','CHECKPOINT')
            value[field]='f'*64 if field=='catalogAfter' else 'MEMBERSHIP' if field=='scope' else self.lower['cut']
            with self.subTest(field=field),self.assertRaises(ValueError):
                c.endpoints(self.packet,e.f.encode('records','CHECKPOINT',value)+b''.join(self.acks))
        value=e.f.decode(self.acks[1],'records','CHECKPOINT_ACK');value['incarnation']=self.v.joining['storage']
        with self.assertRaisesRegex(ValueError,'ancestry endorsement'):
            c.endpoints(self.packet,self.bridge+self.acks[0]+e.f.encode('records','CHECKPOINT_ACK',value))

    def test_all_original_obligations_checked_even_when_confirmation_would_drop_them(self):
        peer=dict(peers=[dict(possible=[self.upper],renewals=[self.lower])]);learner=dict(possible=[])
        c.bind_endpoints(self.packet,self.bridge+b''.join(self.acks),peer,learner)
        with self.assertRaisesRegex(ValueError,'original ancestry missing'):c.bind_endpoints(self.packet,b'',peer,learner)


if __name__=='__main__':unittest.main()
