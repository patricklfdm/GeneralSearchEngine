"""Durability, frozen basis, stale messages and checker sensitivity regressions."""
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from . import ballot_model as m
from . import ballot_research as r


def context(stage='old'):
    return m.Context('root', 1, ('node-1','node-2','node-3'),
                     ('node-2','node-3','node-4'), stage, 7, 'prefix-6')


def prepared():
    model = m.Model(context())
    ballot = m.Ballot(1, 'node-1', 'process-a')
    model.start(ballot, 'A')
    r.exchange(model, 'prepare', ballot, ('node-1','node-2'))
    model.select(ballot)
    return model, ballot


class BallotModelTest(unittest.TestCase):
    def test_ballots_have_total_order_without_three_voter_rank(self):
        left = m.Ballot(4, 'node-1', 'a')
        right = m.Ballot(4, 'node-5', 'a')
        self.assertLess(left, right)
        self.assertGreater(m.fresh_ballot(right, 2, 'node-1', 'b'), right)
        self.assertEqual(8, m.fresh_ballot(left, 7, 'node-1', 'c').counter)
        for value in (0, -1, True, 2**63):
            with self.assertRaises(ValueError): m.Ballot(value, 'node-1', 'a')
        with self.assertRaisesRegex(ValueError, 'counter'):
            m.fresh_ballot(m.Ballot(2**63-1, 'node-1', 'a'), 1, 'node-2', 'b')

    def test_ballot_reuse_and_reselection_are_rejected(self):
        model, ballot = prepared()
        with self.assertRaisesRegex(ValueError, 'reuse'): model.start(ballot, 'B')
        with self.assertRaisesRegex(ValueError, 'fixed'): model.select(ballot)

    def test_each_durable_cut_survives_only_after_force(self):
        for phase in ('prepare', 'accept', 'proof'):
            for forced in (False, True):
                with self.subTest(phase=phase, forced=forced):
                    model = m.Model(context())
                    ballot = m.Ballot(1, 'node-1', 'a')
                    model.start(ballot, 'A')
                    if phase != 'prepare':
                        r.exchange(model, 'prepare', ballot, ('node-1','node-2'))
                        model.select(ballot)
                    if phase == 'proof':
                        r.exchange(model, 'accept', ballot, ('node-1','node-2'))
                    request = model.send(phase, ballot, ('node-2',))[0]
                    model.deliver(request)
                    if forced: model.force('node-2')
                    model.crash('node-2'); model.restart('node-2')
                    voter = model.voters['node-2']
                    self.assertIsNone(voter.pending)
                    value = voter.promise if phase == 'prepare' else voter.accepted if phase == 'accept' else voter.proofs
                    self.assertEqual(forced, bool(value))
                    m.audit(model.context, model.events)

    def test_lost_majority_acceptance_acks_recover_original_value(self):
        for stage in ('old', 'joint', 'new'):
            cfg = context(stage); qs = r.minimal_quorums(cfg)
            for first, second in ((qs[0],qs[-1]), (qs[-1],qs[0])):
                with self.subTest(stage=stage):
                    _, result = r.recover(cfg, first, second, 'lost-accept-acks')
                    self.assertEqual(['operation-A'], result['chosen'])
                    self.assertEqual(1, result['publications'])

    def test_two_live_campaigns_interleave_shared_voter_prepare_and_accept(self):
        for accept_first in (True,False):
            with self.subTest(accept_first=accept_first):
                model,low=prepared();high=m.Ballot(2,'node-3','b');model.start(high,'B')
                requests=model.send('accept',low,('node-1','node-2'))
                # Low ballot owns an acceptance outside the next prepare quorum.
                model.deliver(requests[0]);model.force('node-1');model.deliver(model.next_message)
                if accept_first:
                    model.deliver(requests[1]);model.force('node-2');model.deliver(model.next_message)
                r.exchange(model,'prepare',high,('node-2','node-3'))
                self.assertEqual('A' if accept_first else 'B',model.select(high))
                if not accept_first:
                    model.deliver(requests[1]);self.assertIsNone(model.voters['node-2'].pending)
                r.exchange(model,'accept',high,('node-2','node-3'))
                r.exchange(model,'proof',high,('node-2','node-3'));model.publish(high)
                self.assertTrue(model.campaigns[low].alive)
                self.assertEqual(['A' if accept_first else 'B'],m.audit(model.context,model.events)['chosen'])

    def test_all_unforced_acceptances_can_be_discarded(self):
        _, result = r.recover(context(), ('node-1','node-2'), ('node-2','node-3'), 'all-unforced-accepts')
        self.assertEqual(['operation-B'], result['chosen'])

    def test_partial_proof_does_not_erase_accepted_value(self):
        _, result = r.recover(context('joint'), ('node-1','node-2','node-4'), ('node-2','node-3'), 'partial-proof')
        self.assertEqual(['operation-A'], result['chosen'])

    def test_duplicate_replies_do_not_form_a_quorum(self):
        model = m.Model(context()); ballot = m.Ballot(1,'node-1','a')
        model.start(ballot,'A')
        request = model.send('prepare',ballot,('node-2',))[0]
        model.deliver(request); model.force('node-2')
        duplicate = model.duplicate(model.next_message)
        original = duplicate-1
        model.deliver(original); model.deliver(duplicate)
        with self.assertRaisesRegex(ValueError, 'quorum'): model.select(ballot)
        m.audit(model.context, model.events)

    def test_frozen_basis_and_duplicate_prepare_survive_accept_and_restart(self):
        model, ballot = prepared()
        frozen = model.voters['node-2'].bases[ballot]
        self.assertIsNone(frozen.accepted)
        r.exchange(model,'accept',ballot,('node-1','node-2'))
        model.crash('node-2'); model.restart('node-2')
        request = model.send('prepare',ballot,('node-2',))[0]
        model.deliver(request)
        self.assertEqual(frozen, model.messages[model.next_message])
        self.assertIsNone(model.voters['node-2'].pending)
        model.deliver(model.next_message)
        self.assertEqual(frozen, model.campaigns[ballot].promises['node-2'])
        m.audit(model.context, model.events)

    def test_higher_promise_rejects_delayed_accept_even_after_crash(self):
        model, low = prepared()
        request = model.send('accept',low,('node-2',))[0]
        high = m.Ballot(2,'node-3','b'); model.start(high,'B')
        r.exchange(model,'prepare',high,('node-2','node-3'))
        model.crash('node-2'); model.restart('node-2')
        model.deliver(request)
        self.assertIsNone(model.voters['node-2'].pending)
        self.assertEqual(high, model.voters['node-2'].promise)
        m.audit(model.context, model.events)

    def test_late_response_after_proposer_crash_cannot_publish(self):
        model, ballot = prepared()
        request = model.send('accept',ballot,('node-2',))[0]
        model.deliver(request); model.force('node-2'); ack = model.next_message
        model.crash('node-1'); model.restart('node-1'); model.deliver(ack)
        self.assertFalse(model.campaigns[ballot].accepts)
        with self.assertRaisesRegex(ValueError,'inactive'): model.publish(ballot)

    def test_accept_quorum_is_not_public_success(self):
        model, ballot = prepared()
        r.exchange(model,'accept',ballot,('node-1','node-2'))
        with self.assertRaisesRegex(ValueError,'proof quorum'): model.publish(ballot)
        self.assertEqual(['A'],m.audit(model.context,model.events)['chosen'])
        r.exchange(model,'proof',ballot,('node-1','node-2')); model.publish(ballot)
        self.assertEqual(1,m.audit(model.context,model.events)['publications'])

    def test_proof_certificate_context_duplicate_and_phase_reject(self):
        model, ballot = prepared()
        r.exchange(model,'accept',ballot,('node-1','node-2'))
        rows = tuple(model.campaigns[ballot].accepts.values())
        model.certificate(rows,'accept-ack',ballot,'A')
        for changed in ((rows[0],rows[0]), (replace(rows[0],context=replace(model.context,generation=2)),rows[1]),
                        (replace(rows[0],kind='prepare-ack'),rows[1]), (rows[0],)):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                model.certificate(changed,'accept-ack',ballot,'A')
        for name, value in (('root','other'),('index',8),('predecessor','other'),('stage','new')):
            with self.subTest(field=name), self.assertRaises(ValueError):
                model.certificate((replace(rows[0],context=replace(model.context,**{name:value})),rows[1]),
                                  'accept-ack',ballot,'A')

    def test_stable_view_excludes_learner_and_removed_voter(self):
        for stage, outsider in (('old','node-4'),('new','node-1')):
            cfg=context(stage); node=sorted(cfg.voters)[0]
            model=m.Model(cfg); ballot=m.Ballot(1,node,'a');model.start(ballot,'A')
            with self.assertRaisesRegex(ValueError,'voters'): model.send('prepare',ballot,(outsider,))
            with self.assertRaisesRegex(ValueError,'non-voter'): model.start(m.Ballot(1,outsider,'a'),'B')

    def test_checker_detects_five_unsafe_mutants(self):
        cfg=context(); first=('node-1','node-2');second=('node-2','node-3')
        for mutant, reason in (('ack-before-force','ACK without frozen'),('forget-on-crash','basis differs from durable'),
                               ('ignore-accepted','conflicting chosen'),('accept-stale','durable promise')):
            with self.subTest(mutant=mutant), self.assertRaisesRegex(m.SafetyViolation,reason):
                r.recover(cfg,first,second,'lost-accept-acks',mutant=mutant)
        model, ballot=prepared(); model.mutant='publish-accept-only'
        r.exchange(model,'accept',ballot,first);model.publish(ballot)
        with self.assertRaisesRegex(m.SafetyViolation,'publication without durable proof'):
            m.audit(cfg,model.events)

    def test_history_checker_does_not_lose_overwritten_acceptances(self):
        model,_=r.recover(context(),('node-1','node-2'),('node-2','node-3'),'lost-accept-acks')
        changed=[]
        high=max(model.campaigns)
        for event in model.events:
            message=event.get('message')
            if event['event']=='accept-force' and message.ballot==high:
                event=dict(event,message=replace(message,value='forged-B'))
            # Only force rows needed to expose the historical chosen-value conflict.
            if event['event'] in ('promise-force','accept-force'):changed.append(event)
        with self.assertRaisesRegex(m.SafetyViolation,'conflicting chosen'):m.audit(model.context,changed)

    def test_two_locally_valid_views_can_fork_without_handoff(self):
        result=r.unsealed_switch()
        self.assertEqual('EXPECTED_REJECTION',result['status'])
        self.assertEqual('cross-configuration conflicting chosen values',result['reason'])
        histories=[(row['context'],row['events']) for row in result['histories']]
        self.assertEqual(1,m.audit_slot_family(histories[:1]))
        with self.assertRaisesRegex(m.SafetyViolation,'cross-configuration'):
            m.audit_slot_family(histories)
        # Even a different claimed predecessor cannot hide a same-index fork.
        other=m.Model(replace(histories[1][0],predecessor='different-parent'))
        ballot=m.Ballot(1,'node-2','other');votes=('node-2','node-4')
        other.start(ballot,'operation-B');r.exchange(other,'prepare',ballot,votes);other.select(ballot)
        r.exchange(other,'accept',ballot,votes)
        histories[1]=(other.context,other.events)
        with self.assertRaisesRegex(m.SafetyViolation,'cross-configuration'):
            m.audit_slot_family(histories)

    def test_retained_json_traces_replay_and_wrong_context_rejects(self):
        examples={}
        cfgs=list(r.contexts())[:3]
        for cfg in cfgs:
            votes=r.minimal_quorums(cfg)[0]
            for cut in r.CUTS:
                model,_=r.recover(cfg,votes,votes,cut)
                examples[cfg.stage+'/'+cut]=dict(context=cfg,events=model.events)
        examples['unsealed-switch']=r.unsealed_switch()
        raw=json.loads(r.encode(examples))
        self.assertEqual(14,r.replay_examples(raw))
        raw['old/lost-accept-acks']['context']['generation']=2
        with self.assertRaisesRegex(m.SafetyViolation,'foreign event context'):r.replay_examples(raw)
        with self.assertRaisesRegex(ValueError,'inventory'):r.replay_examples({})

    def test_matrix_profiles_and_quorums_match_independent_counts(self):
        profiles=list(r.contexts());self.assertEqual(21,len(profiles))
        self.assertEqual({3,4,5,6},{len(cfg.voters) for cfg in profiles})
        for cfg in profiles:
            for quorum in r.minimal_quorums(cfg):self.assertTrue(cfg.quorum(quorum))
        # Full run is an explicit CLI qualification, not repeated by every unit test.
        result=r.run(2);self.assertEqual('INCOMPLETE',result['status'])
        self.assertEqual(2,result['counts']['cases']);self.assertFalse(result['allInterleavings'])
        self.assertGreater(result['counts']['expectedCases'],1000)
        for invalid in (-1,True,0.1):
            with self.assertRaises(ValueError):r.run(invalid)

    def test_cli_preserves_incomplete_evidence_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'evidence'
            command=[sys.executable,'-m','scripts.v53.ballot_research','--output',str(output),'--max-cases','0']
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(2,result.returncode,result.stderr)
            original=(output/'receipt.json').read_bytes()
            self.assertEqual('INCOMPLETE',json.loads(original)['status'])
            again=subprocess.run(command,capture_output=True,text=True)
            self.assertNotEqual(0,again.returncode);self.assertEqual(original,(output/'receipt.json').read_bytes())

    def test_failed_matrix_retains_the_original_trace(self):
        with self.assertRaises(m.SafetyViolation) as failure:
            r.recover(context(),('node-1','node-2'),('node-2','node-3'),
                      'lost-accept-acks',mutant='ignore-accepted')
        self.assertTrue(failure.exception.research_case['events'])
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'failed'
            with patch.object(sys,'argv',['ballot_research','--output',str(output)]), \
                    patch.object(r,'run',side_effect=failure.exception), patch('builtins.print'):
                self.assertEqual(2,r.main())
            receipt=json.loads((output/'receipt.json').read_bytes())
            self.assertEqual('FAIL',receipt['status'])
            self.assertIn('failedCaseSha256',receipt)
            self.assertEqual('lost-accept-acks',json.loads((output/'failed-case.json').read_bytes())['cut'])

    def test_optimized_python_still_detects_conflicting_chosen_values(self):
        code="""
from scripts.v53 import ballot_model as m, ballot_research as r
cfg=next(r.contexts())
try:r.recover(cfg,('node-1','node-2'),('node-2','node-3'),'lost-accept-acks',mutant='ignore-accepted')
except m.SafetyViolation:raise SystemExit(0)
raise SystemExit('unsafe recovery accepted')
"""
        result=subprocess.run([sys.executable,'-O','-c',code],capture_output=True,text=True,
                              env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
