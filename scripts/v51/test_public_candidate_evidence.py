"""Reject reused campaigns and a recovery schedule rescued by the old leader."""
import unittest
from .public_candidate_evidence import fresh_campaigns, restart_schedule, prepare_order


class PublicCandidateEvidenceTest(unittest.TestCase):
    def test_each_prepare_or_reply_requires_prior_force_and_frozen_basis(self):
        prepare_order([10], [20], [30, 40])

    def test_final_basis_bytes_cannot_prove_publication_before_dispatch(self):
        for force, basis, message in ((10, 30, 20), (20, 10, 30), (10, 20, 20), (20, 20, 30)):
            with self.subTest(force=force, basis=basis, message=message), self.assertRaises(ValueError):
                prepare_order([force], [basis], [message])

    def test_a_later_valid_dispatch_cannot_hide_an_early_one(self):
        with self.assertRaises(ValueError): prepare_order([10], [20], [15, 30])

    def test_absent_force_basis_or_message_cannot_establish_order(self):
        for forces, bases, messages in (([], [20], [30]), ([10], [], [30]), ([10], [20], [])):
            with self.subTest(forces=forces, bases=bases, messages=messages), self.assertRaises(ValueError):
                prepare_order(forces, bases, messages)

    def ballot(self, epoch, incarnation, proposer='node-1'):
        return dict(epoch=epoch, incarnation=incarnation, proposer=proposer)

    def test_repeated_force_of_same_ballot_is_not_another_campaign(self):
        old = [self.ballot(2, 'old')]; new = self.ballot(5, 'new')
        self.assertEqual([5], fresh_campaigns(old, [new, dict(new)], 'node-1'))

    def test_retries_may_advance_again_with_new_incarnations(self):
        self.assertEqual([5, 8], fresh_campaigns([self.ballot(2, 'old')],
                         [self.ballot(5, 'a'), self.ballot(8, 'b')], 'node-1'))

    def test_reused_or_lower_retained_epoch_rejected(self):
        for epoch in (2, 5):
            with self.subTest(epoch=epoch), self.assertRaisesRegex(ValueError, 'retained epoch'):
                fresh_campaigns([self.ballot(5, 'old')], [self.ballot(epoch, 'new')], 'node-1')

    def test_all_retained_incarnations_remain_unavailable(self):
        old = [self.ballot(2, 'a'), self.ballot(5, 'b')]
        for incarnation in ('a', 'b'):
            with self.subTest(incarnation=incarnation), self.assertRaisesRegex(ValueError, 'retained incarnation'):
                fresh_campaigns(old, [self.ballot(8, incarnation)], 'node-1')

    def test_an_epoch_cannot_acquire_a_second_incarnation(self):
        with self.assertRaisesRegex(ValueError, 'same-epoch'):
            fresh_campaigns([self.ballot(2, 'old')], [self.ballot(5, 'a'), self.ballot(5, 'b')], 'node-1')

    def test_a_new_incarnation_cannot_span_multiple_epochs(self):
        with self.assertRaisesRegex(ValueError, 'across campaigns'):
            fresh_campaigns([self.ballot(2, 'old')], [self.ballot(5, 'a'), self.ballot(8, 'a')], 'node-1')

    def test_forces_cannot_move_back_to_an_earlier_campaign(self):
        with self.assertRaisesRegex(ValueError, 'backwards'):
            fresh_campaigns([self.ballot(2, 'old')], [self.ballot(8, 'a'), self.ballot(5, 'b')], 'node-1')

    def test_missing_campaign_or_peer_grant_is_not_self_election(self):
        for values in ([], [self.ballot(5, 'new', 'node-2')]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                fresh_campaigns([self.ballot(2, 'old')], values, 'node-1')

    def schedule(self):
        starts = [dict(node=node, generation=generation, pid=pid, startNanos=start, readyNanos=start+1)
                  for node, generation, pid, start in [('node-1', 1, 11, 1), ('node-2', 1, 12, 3),
                                                       ('node-3', 1, 13, 5), ('node-1', 2, 14, 10), ('node-2', 2, 15, 40)]]
        traces = {n: [dict(row, event='STARTED') for row in starts if row['node'] == n] for n in ('node-1', 'node-2', 'node-3')}
        docs = [dict(id=1, value='acknowledged')]
        history = [dict(node='node-1', pid=14, opId='write', kind='addAll', outcome='SUCCESS', startNanos=20, endNanos=25, documents=docs),
                   dict(node='node-1', pid=14, opId='read', kind='read', outcome='SUCCESS', startNanos=30, endNanos=35, documents=docs)]
        receipt = dict(crash=dict(node='node-1'), oldLeader='node-2', postRestartWrite='write')
        return starts, history, traces, receipt

    def test_candidate_writes_and_reads_before_old_leader_starts(self):
        args = self.schedule()
        self.assertEqual('write', restart_schedule(*args)['opId'])

    def test_old_leader_cannot_rescue_the_claimed_two_voter_recovery(self):
        for began in (20, 24, 25, 31, 34, 35):
            starts, history, traces, receipt = self.schedule(); starts[-1]['startNanos'] = began
            with self.subTest(began=began), self.assertRaises(ValueError): restart_schedule(starts, history, traces, receipt)

    def test_missing_read_or_missing_documents_is_not_recovered_service(self):
        for change in ('missing', 'wrong-data', 'wrong-pid', 'failed'):
            args = self.schedule(); history = args[1]
            if change == 'missing': history.pop()
            elif change == 'wrong-data': history[-1]['documents'] = []
            elif change == 'wrong-pid': history[-1]['pid'] = 13
            else: history[-1]['outcome'] = 'NOT_APPLICABLE'
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'candidate read'): restart_schedule(*args)

    def test_wrong_write_process_or_outcome_cannot_establish_recovery(self):
        for change in (dict(pid=11), dict(node='node-2'), dict(outcome='PENDING'), dict(startNanos=10)):
            args = self.schedule(); args[1][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError): restart_schedule(*args)

    def test_process_generations_and_start_trace_must_bind(self):
        for change in ('duplicate-pid', 'missing-start', 'changed-generation'):
            starts, history, traces, receipt = self.schedule()
            if change == 'duplicate-pid': starts[-1]['pid'] = starts[-2]['pid']
            elif change == 'missing-start': traces['node-1'].pop()
            else: starts[-2]['generation'] = 1
            with self.subTest(change=change), self.assertRaises(ValueError): restart_schedule(starts, history, traces, receipt)


if __name__ == '__main__': unittest.main()
