from copy import deepcopy
import unittest

from . import steady_model as m
from . import steady_oracle as o


class SteadyTest(unittest.TestCase):
    def test_three_sizes_two_source_choices_reuse_original_basis(self):
        for size in (3,4,5):
            for last in (False,True):
                r=m.Round(size,last);basis=deepcopy(r.basis)
                for i in range(12):r.commit(m.t.Entry(('DATA','BARRIER','CONTROL')[i%3],payload=str(i)))
                self.assertEqual(basis,r.basis);self.assertEqual(12,o.check(r.evidence())['publications'])

    def test_intent_ends_stable_round_before_final(self):
        r=m.Round();r.commit(m.t.Entry('INTENT','sealed-operation',m.NODES[:4]))
        with self.assertRaisesRegex(ValueError,'ready'):r.propose(m.t.Entry('FINAL','sealed-operation',m.NODES[:4]))
        self.assertFalse(o.check(r.evidence())['ready'])

    def test_source_substitution_lag_and_pipelining_refused(self):
        r=m.Round();r.propose(m.t.Entry('DATA',payload='a'))
        with self.assertRaisesRegex(ValueError,'busy'):r.propose(m.t.Entry('DATA',payload='b'))
        with self.assertRaisesRegex(ValueError,'offline'):r.stage(m.NODES[5],'ACCEPT')
        r.views[r.owners[-1]]=r.seed['events'][0].get('authority')  # deliberately wrong parent
        with self.assertRaisesRegex(ValueError,'predecessor'):r.stage(r.owners[-1],'ACCEPT')

    def test_crash_between_stage_and_force_does_not_create_ack(self):
        r=m.Round();r.propose(m.t.Entry('DATA',payload='a'));n=r.owners[-1]
        r.stage(n,'ACCEPT');r.crash(n);r.restart(n)
        with self.assertRaisesRegex(ValueError,'stage'):r.force(n)
        with self.assertRaisesRegex(ValueError,'quorum'):r.stage(n,'PROOF')
        o.check(r.evidence())

    def test_higher_fence_between_stage_and_force(self):
        r=m.Round();r.propose(m.t.Entry('DATA',payload='a'));n=r.owners[-1];r.stage(n,'ACCEPT')
        r.observe(n,m.a.b.Ballot(9,m.NODES[1],'new'))
        with self.assertRaisesRegex(ValueError,'fenced'):r.force(n)
        o.check(r.evidence())

    def test_leader_restart_cannot_restore_ready(self):
        r=m.Round();r.commit(m.t.Entry('DATA',payload='a'));r.crash(r.ballot.proposer);r.restart(r.ballot.proposer)
        with self.assertRaisesRegex(ValueError,'fresh round'):r.propose(m.t.Entry('DATA',payload='b'))
        self.assertFalse(o.check(r.evidence())['ready'])

    def test_higher_fence_before_callback_refuses_success(self):
        r=m.Round();r.propose(m.t.Entry('DATA',payload='a'))
        for phase in ('ACCEPT','PROOF'):
            for n in r.owners:r.stage(n,phase);r.force(n)
        c=r.certify();r.install(r.ballot.proposer,c);r.observe(r.ballot.proposer,m.a.b.Ballot(9,m.NODES[1],'new'))
        with self.assertRaisesRegex(ValueError,'fenced'):r.publish(c)
        o.check(r.evidence())

    def test_independent_observer_rejects_missing_accept_proof_or_prefix(self):
        r=m.Round();r.commit(m.t.Entry('DATA',payload='a'));o.check(r.evidence())
        for kind,phase in (('force','ACCEPT'),('force','PROOF'),('prefix-force',None)):
            changed=deepcopy(r.evidence())
            changed['events']=[e for e in changed['events'] if not (e['event']==kind and
                (phase is None and e['node']==r.ballot.proposer or e.get('phase')==phase))]
            with self.subTest(kind=kind,phase=phase),self.assertRaises(ValueError):o.check(changed)

    def test_same_era_with_wrong_generation_cannot_vote(self):
        from dataclasses import replace
        r=m.Round();r.propose(m.t.Entry('DATA',payload='a'));record=deepcopy(r.evidence())
        record['events'][0]['authority']=replace(record['events'][0]['authority'],generation=2)
        with self.assertRaisesRegex(ValueError,'proposal'):o.check(record)

    def test_restart_cannot_complete_old_publication_callback(self):
        r=m.Round();r.propose(m.t.Entry('DATA',payload='a'))
        for phase in ('ACCEPT','PROOF'):
            for n in r.owners:r.stage(n,phase);r.force(n)
        c=r.certify();r.install(r.ballot.proposer,c);r.crash(r.ballot.proposer);r.restart(r.ballot.proposer)
        with self.assertRaisesRegex(ValueError,'fresh round'):r.publish(c)
        o.check(r.evidence())


if __name__=='__main__':unittest.main()
