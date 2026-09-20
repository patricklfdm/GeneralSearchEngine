"""Fault schedules and independently corrupted history fixtures."""
from copy import deepcopy
from itertools import permutations
import unittest

from .history import validate
from .model import Cluster, Rejected, next_epoch


def activated():
    c = Cluster(); b = c.campaign(0); c.drain()
    return c, b


def accepted_tail():
    c,b = activated(); c.submit(b, 'ADD_ALL:a,b')
    while c.messages and not any(e['event'] == 'entry-quorum' and e['slot'] == 2 for e in c.events):
        c.deliver()
    while c.messages: c.drop()
    return c,b


def completed_history():
    c,b = activated(); c.submit(b, 'ADD_ALL:a,b'); c.drain()
    c.read(b, 'read-1'); c.drain(); c.finish_read('read-1')
    return c


class ModelTest(unittest.TestCase):
    def test_e01_e02_new_leader_activates_without_manual_promotion(self):
        for order in permutations(range(3)):
            c=Cluster(); first=c.campaign(order[0]); c.drain()
            c.submit(first,'ADD:x'); c.drain()
            c.restart(order[0]); newer=c.campaign(order[1],next_epoch(max(v.promise for v in c.voters),order[1]));c.drain()
            self.assertTrue(c.campaigns[newer]['ready']); validate(c.events)

    def test_e05_e06_highest_acceptance_survives_lost_proof(self):
        c,old=accepted_tail(); new=c.campaign(1, next_epoch(old,1)); c.drain()
        self.assertEqual('ADD_ALL:a,b',c.voters[1].prefix[1])
        self.assertEqual(f'NO_OP:{new}:activation',c.voters[1].prefix[-1]);validate(c.events)

    def test_e03_e09_read_pin_can_finish_after_election_but_later_read_cannot(self):
        c,b=activated();c.read(b,'overlap');c.drain()
        new=c.campaign(1, next_epoch(b,1));c.drain();c.submit(new,'UPDATE:x');c.drain()
        c.finish_read('overlap')
        with self.assertRaises(Rejected): c.read(b,'late')
        validate(c.events)

    def test_e04_e08_restart_retains_promise_and_loss_cannot_vote(self):
        c,b=accepted_tail();before=deepcopy(c.voters[0].accepted);c.restart(0)
        self.assertEqual(before,c.voters[0].accepted)
        with self.assertRaises(Rejected): c.campaign(0,b)
        c.restart(2,lost=True)
        with self.assertRaises(Rejected): c.campaign(2)
        validate(c.events)

    def test_e07_checkpoint_does_not_discard_accepted_next_value(self):
        c,b=accepted_tail()
        with self.assertRaises(Rejected):c.checkpoint(0)
        n=c.campaign(1,next_epoch(b,1));c.drain();c.checkpoint(1);validate(c.events)
        self.assertGreater(n,b)

    def test_e10_e11_duplicate_drop_and_finite_bounds(self):
        c=Cluster(queue_limit=4);c.campaign(0);c.duplicate();c.duplicate()
        with self.assertRaises(Rejected):c.duplicate()
        c.drop();c.drain();validate(c.events)
        c=Cluster(promise_limit=2);b=c.campaign(0);c.drain()
        with self.assertRaises(Rejected):c.campaign(0,next_epoch(b,0))
        with self.assertRaises(Rejected):next_epoch((1<<63)-1,2)
        for n in (1,2,3,4,7,100):
            epochs=[next_epoch(n,r) for r in range(3)]
            self.assertEqual(3,len(set(epochs)));self.assertTrue(all(v>n for v in epochs))

    def test_every_reordered_accept_and_proof_delivery_preserves_history(self):
        for order in permutations(range(4)):
            c,b=activated();c.submit(b,'UPDATE:y')
            for choice in order:
                if c.messages:c.deliver(choice % len(c.messages))
            c.drain();validate(c.events)

    def test_all_invariant_checker_negatives_reject_semantic_corruption(self):
        base=completed_history().events
        mutations={
            'I01':lambda es: next(e for e in es if e['event']=='accept-force').update(ballot=1),
            'I02':lambda es: next(e for e in es if e['event']=='entry-quorum').update(receipts=['missing-force','missing-force']),
            'I03':lambda es: next(e for e in es if e['event']=='success').update(receipts=[]),
            'I04':lambda es: next(e for e in es if e['event']=='proof-force').update(slot=99),
            'I05':lambda es: next(e for e in es if e['event']=='select').update(prefix=['invented']),
            'I06':lambda es: next(e for e in es if e['event']=='read-pin').update(barrier='NO_OP:2:activation'),
            'I07':lambda es: next(e for e in es if e.get('node') is not None).update(generation=99),
            'I08':lambda es: next(e for e in es if e['event']=='account').update(queued=99999),
        }
        for invariant,mutate in mutations.items():
            with self.subTest(invariant=invariant):
                es=deepcopy(base);mutate(es)
                with self.assertRaises(ValueError):validate(es)
        es=deepcopy(base);del es[next(i for i,e in enumerate(es) if e['event']=='accept-force')]
        with self.assertRaises(ValueError):validate(es)

    def test_hidden_chosen_tail_cannot_be_replaced_with_an_unrelated_value(self):
        c,b=accepted_tail();c.campaign(1,next_epoch(b,1));c.drain();es=deepcopy(c.events)
        [e for e in es if e['event']=='select'][-1]['value']='OTHER'
        with self.assertRaisesRegex(ValueError,'highest acceptance'):validate(es)

    def test_model_and_bounded_map_oracles_agree_on_small_public_history(self):
        from .linearizability import check
        c,b=activated();start=len(c.events);c.submit(b,'ADD_ALL:a,b');c.drain()
        end=next(e['position'] for e in c.events if e['event']=='success' and e['value']=='ADD_ALL:a,b')
        c.read(b,'map-read');c.drain();c.finish_read('map-read');validate(c.events)
        invoke=next(e['position'] for e in c.events if e['event']=='read-invoke')
        result=next(e for e in c.events if e['event']=='read-result')
        values={'a':1,'b':1} if 'ADD_ALL:a,b' in result['prefix'] else {}
        history=[dict(id='bulk',kind='write',start=start,end=end,outcome='success',changes=[('a',1),('b',1)]),
                 dict(id='read',kind='read',start=invoke,end=result['position'],outcome='success',result=values)]
        self.assertEqual('PASS',check(history)['status'])
        history[1]['result']={'a':1}
        with self.assertRaises(ValueError):check(history)
        result['prefix']=['partial-bulk']
        with self.assertRaises(ValueError):validate(c.events)

if __name__=='__main__':unittest.main()
