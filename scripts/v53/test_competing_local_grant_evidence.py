"""Causal synthetic guards; the retained original supplies native qualification."""
import copy
from types import SimpleNamespace
import unittest
from . import competing_local_grant_evidence as m


def fixture():
    ids={n:dict(node=n,storage=n) for n in ('node-1','node-2','node-3')}
    ballot=dict(counter=2,proposer='node-2',incarnation='two')
    higher=dict(counter=2,proposer='node-3',incarnation='three')
    local=dict(node='node-2',ballot=ballot,promise=b'original',returnEvent=4,capturedEvent=5)
    remote=dict(node='node-3',ballot=higher,capturedEvent=2)
    q=dict(ballot=ballot,sender=ids['node-2'],recipient=ids['node-1'],sequence=1,trace='one',
           payload=dict(promise=m.prefix.sha(local['promise'])))
    asks=[dict(kind='PREPARE',request=copy.deepcopy(q),sent=i,received=i+1) for i in (6,8,10)]
    other=dict(q,recipient=ids['node-3'],sequence=2)
    asks.append(dict(kind='PREPARE',request=other,sent=12,received=13))
    row=dict(asks[-1],answer='REJECT',response=dict(payload=dict(promised=higher,reason='STALE_EPOCH')),
             offered=14,delivered=15)
    replay=SimpleNamespace(identities=ids,by_basis={'local':local,'higher':remote},selections={},attempts=asks,rows=[row])
    allocation=dict(node='node-2',ballot=ballot,start=0,end=3)
    loss=dict(node='node-2',event='LOSS',detail='HIGHER_BALLOT',state='STARTING',rounds=1,pending=0,afterEvent=15)
    return replay,allocation,local,loss,20


class CompetingLocalGrantEvidenceTest(unittest.TestCase):
    def test_same_counter_higher_proposer_and_unanswered_are_not_a_majority(self):
        args=fixture();before=copy.deepcopy(args);result,reply=m.bind(*args)
        self.assertEqual(before,args)
        self.assertEqual([6,8,10],result['unanswered'])
        self.assertEqual(0,result['remoteGrants']);self.assertIs(result['selected'],False)
        self.assertEqual(result['rejection'],reply['delivered'])

    def test_actual_loss_and_local_force_are_required(self):
        for field,value in [('detail','CONTACT_UNAVAILABLE'),('rounds',2),('pending',1),('state','READY'),('afterEvent',5)]:
            args=fixture();args[3][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'actual first-round loss'):m.bind(*args)

    def test_remote_grant_or_selection_cannot_use_local_only_branch(self):
        for change in ('grant','selection'):
            args=fixture();r,a=args[:2]
            if change=='grant':r.by_basis['extra']=dict(node='node-1',ballot=a['ballot'])
            else:r.selections['chosen']=dict(value=dict(ballot=a['ballot']))
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'cannot select a majority'):m.bind(*args)

    def test_exact_prepares_require_observed_bytes_sequence_and_owner(self):
        for field,value in [('sequence',2),('trace','different'),('payload',dict(promise='invented')),('sender',dict(node='foreign'))]:
            args=fixture();args[0].attempts[0]['request'][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'exact original PREPAREs'):m.bind(*args)

    def test_undelivered_equal_or_late_rejection_never_proves_loss(self):
        for change in ('missing','late','same-ballot','wrong-reason','wrong-kind'):
            args=fixture();r=args[0];row=r.rows[0]
            if change=='missing':row['delivered']=None
            elif change=='late':row['delivered']=16
            elif change=='same-ballot':row['response']['payload']['promised']=args[1]['ballot']
            elif change=='wrong-reason':row['response']['payload']['reason']='BUSY'
            else:row['answer']='PROMISE'
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'delivered higher rejection'):m.bind(*args)

    def test_higher_ballot_requires_original_durable_grant(self):
        for change in ('absent','late'):
            args=fixture();r=args[0]
            if change=='absent':del r.by_basis['higher']
            else:r.by_basis['higher']['capturedEvent']=13
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'original higher promise'):m.bind(*args)

    def test_bounded_unanswered_history_is_not_arbitrary_loss(self):
        for change in ('missing','extra','overlap','other-peer'):
            args=fixture();r=args[0]
            if change=='missing':r.attempts.pop(0)
            elif change=='extra':r.attempts.insert(0,copy.deepcopy(r.attempts[0]))
            elif change=='overlap':r.attempts[1]['sent']=7
            else:r.attempts[0]['request'].update(recipient=r.identities['node-3'],sequence=2)
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'bounded unanswered'):m.bind(*args)


if __name__=='__main__':unittest.main()
