"""Synthetic loss binding, never a substitute for complete native replay."""
import copy
import unittest
from . import competing_incoming_loss as m
from .test_competing_local_grant_evidence import fixture


def value():
    r,a,local,loss,stop=fixture();r.rows=[];loss['afterEvent']=12
    source=r.by_basis['higher'];source['promise']=b'higher-original'
    higher=dict(ballot=source['ballot'],sender=r.identities['node-3'],recipient=r.identities['node-2'],
                payload=dict(promise=m.p.prefix.sha(source['promise'])))
    prepare=r.attempts[0]
    pull=dict(ballot=a['ballot'],sender=r.identities['node-1'],recipient=r.identities['node-2'],sequence=1,
              payload=dict(id='one',action='REQUEST',offset=0,digest=m.p.prefix.sha(local['promise']),bytes=''))
    r.attempts=[prepare,dict(kind='PREPARE',request=higher,sent=8,received=9),
                *[dict(kind='CHUNK',request=copy.deepcopy(pull),sent=i,received=i+1) for i in (10,13,15)]]
    r.by_basis['incoming']=dict(node=a['node'],ballot=source['ballot'],returnEvent=18,capturedEvent=19)
    return m.claim(r,a,local,loss,stop)


class CompetingIncomingLossTest(unittest.TestCase):
    def test_unanswered_preparation_and_pull_cannot_become_votes(self):
        v=value();before=copy.deepcopy(v);result=m.bind(v)
        self.assertEqual(v,before);self.assertEqual([6,10,13,15],result['unanswered'])
        self.assertEqual('incoming-prepare',result['cause']);self.assertEqual(0,result['remoteGrants']);self.assertFalse(result['selected'])

    def test_unadvertised_grant_still_needs_original_incoming_authority(self):
        v=value();v['attempts']=[v['attempts'][1]]
        self.assertEqual([],m.bind(v)['unanswered'])

    def test_every_declared_negative_has_exact_reason(self):
        for name,reason in m.NEGATIVES.items():
            v=value();m.mutate(v,name)
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'^'+reason+'$'):m.bind(v)

    def test_reverse_pull_requires_original_reference_complete_identity_and_order(self):
        for change in ('digest','offset','sender','late','overlap','kind'):
            v=value();p=v['attempts'][2]
            if change in ('digest','offset'):p['request']['payload'][change]='foreign' if change=='digest' else 1
            elif change=='sender':p['request']['sender']=dict(p['request']['sender'],storage='foreign')
            elif change=='late':p['received']=20
            elif change=='overlap':v['attempts'][3]['sent']=11
            else:p['kind']='TRANSFER_COMMIT'
            with self.subTest(change=change),self.assertRaises(ValueError):m.bind(v)

    def test_loss_cannot_precede_incoming_fence_or_follow_activation(self):
        for at in (8,20):
            v=value();v['loss']['afterEvent']=at
            with self.subTest(at=at),self.assertRaises(ValueError):m.bind(v)
