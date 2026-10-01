"""Coordinate retained rejoin without treating a majority read as a write lease."""
import copy
import unittest
from concurrent.futures import Future
from contextlib import ExitStack
from unittest.mock import patch
from . import public_selection_harness as h


def states(epoch=7, leader='node-1', index=12):
    return {node: dict(state='LEADER_READY' if node == leader else 'FOLLOWER',
                       epoch=epoch, provenIndex=index) for node in h.protocol.NODES}


class PublicSelectionRejoinTest(unittest.TestCase):
    def run_fixture(self, snapshots, reads=None, *, read_seconds=0, observations=None):
        self.clock = 0
        self.reads = []
        self.snapshots = 0
        self.observations = observations if observations is not None else []
        responses = iter(reads if reads is not None else [dict(outcome='SUCCESS', documents=[])])
        test = self

        class Worker:
            def __init__(self, node): self.node = node

            def send(self, kind):
                future = Future()
                if kind == 'status':
                    sample = snapshots[min(test.snapshots, len(snapshots)-1)]
                    result = dict(sample[self.node], outcome='SUCCESS')
                    if self.node == h.protocol.NODES[-1]: test.snapshots += 1
                else:
                    test.assertEqual('read', kind)  # Recovery must not replay a write.
                    sample = snapshots[min(test.snapshots-1, len(snapshots)-1)]
                    test.reads.append(dict(node=self.node, statuses=copy.deepcopy(sample)))
                    test.clock += read_seconds
                    result = next(responses)
                future.set_result(result)
                return future

            def call(self, kind): return self.send(kind).result()

        workers = {node: Worker(node) for node in h.protocol.NODES}

        def sleep(seconds): self.clock += seconds

        with ExitStack() as stack:
            stack.enter_context(patch.object(h.time, 'monotonic', side_effect=lambda: self.clock))
            stack.enter_context(patch.object(h.time, 'sleep', side_effect=sleep))
            return h.read_after_rejoin(workers, [], self.observations)

    def test_ci_epoch_five_majority_waits_for_restarted_epoch_six_voter(self):
        before = states(epoch=5); before['node-2']['epoch'] = 6
        node, _ = self.run_fixture([before, states(), states()])
        self.assertEqual('node-1', node)
        self.assertEqual([7], [r['statuses'][r['node']]['epoch'] for r in self.reads])
        self.assertEqual(before, self.observations[0]['statuses'])
        self.assertEqual('after-read', self.observations[-1]['phase'])

    def test_same_epoch_still_waits_for_restarted_prefix_to_catch_up(self):
        behind = states(); behind['node-2']['provenIndex'] = 6
        self.run_fixture([behind, states(), states()])
        self.assertEqual(12, self.reads[0]['statuses']['node-2']['provenIndex'])

    def test_higher_promise_during_successful_read_requires_fresh_election(self):
        crossed = states(); crossed['node-2']['epoch'] = 8
        later = states(epoch=9, leader='node-2')
        node, _ = self.run_fixture([states(), crossed, later, later],
                                  [dict(outcome='SUCCESS', documents=[])]*2)
        self.assertEqual('node-2', node)
        self.assertEqual(['node-1', 'node-2'], [r['node'] for r in self.reads])
        self.assertEqual(2, len([r for r in self.observations if r['phase'] == 'read']))

    def test_read_failure_only_allows_existing_availability_rejections(self):
        for reason in h.protocol.READ_REJECTIONS:
            with self.subTest(reason=reason):
                self.run_fixture([states()], [dict(outcome='NOT_APPLICABLE', reasonCode=reason),
                                              dict(outcome='SUCCESS', documents=[])])
                self.assertEqual(2, len(self.reads))
        for reply in (None, dict(outcome='NOT_APPLICABLE', reasonCode='INTEGRITY_FAILURE'),
                      dict(outcome='NOT_APPLICABLE', reasonCode='STORAGE_FAILURE'),
                      dict(outcome='INDETERMINATE', reasonCode='STALE_EPOCH')):
            with self.subTest(reply=reply), self.assertRaises(ValueError):
                self.run_fixture([states()], [reply])
            self.assertEqual(1, len(self.reads))

    def test_changed_successful_projection_is_not_retried(self):
        with self.assertRaisesRegex(ValueError, 'projection changed'):
            self.run_fixture([states()], [dict(outcome='SUCCESS', documents=[dict(id=1, value='unexpected')])])
        self.assertEqual(1, len(self.reads))

    def test_failed_voter_stops_without_a_read(self):
        failed = states(); failed['node-2']['state'] = 'FAILED'
        with self.assertRaisesRegex(ValueError, 'voter failed'): self.run_fixture([failed])
        self.assertEqual([], self.reads)

    def test_two_leaders_or_activating_voter_cannot_qualify(self):
        for state in ('LEADER_READY', 'CANDIDATE'):
            pending = states(); pending['node-2']['state'] = state
            with self.subTest(state=state):
                self.run_fixture([pending, states(), states()])
                self.assertEqual('FOLLOWER', self.reads[0]['statuses']['node-2']['state'])

    def test_no_convergence_fails_at_existing_forty_second_wait_bound(self):
        pending = states(); pending['node-2']['epoch'] = 8
        with self.assertRaisesRegex(ValueError, 'rejoin did not converge'): self.run_fixture([pending])
        self.assertEqual([], self.reads)
        self.assertLess(self.clock, 40.1)

    def test_read_attempts_do_not_reset_deadline(self):
        rejected = dict(outcome='NOT_APPLICABLE', reasonCode='STALE_EPOCH')
        with self.assertRaisesRegex(ValueError, 'deadline exceeded'):
            self.run_fixture([states()], [rejected]*4, read_seconds=21)
        self.assertEqual(2, len(self.reads))

    def test_four_read_limit_preserves_all_rejections(self):
        rejected = dict(outcome='NOT_APPLICABLE', reasonCode='STALE_EPOCH')
        with self.assertRaisesRegex(ValueError, 'four reads'):
            self.run_fixture([states()], [rejected]*5)
        self.assertEqual(4, len(self.reads))
        self.assertEqual([rejected]*4, [r['result'] for r in self.observations if r['phase'] == 'read'])


if __name__ == '__main__': unittest.main()
