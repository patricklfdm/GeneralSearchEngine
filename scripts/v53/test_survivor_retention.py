"""Safety counterexamples for the proposed stable-view retention obligations."""
from dataclasses import replace
import unittest

from . import survivor_retention_research as r


class SurvivorRetentionResearchTest(unittest.TestCase):
    def test_seven_required_endpoints_need_consolidation_not_a_larger_bound(self):
        state, majority = r.fixture()
        self.assertEqual({1, 2, 5, 6, 7, 8, 9}, state.required())
        before = repr(state)
        with self.assertRaisesRegex(ValueError, 'ancestry headroom'):
            state.publication(majority)
        self.assertEqual(before, repr(state))
        next_round = state.consolidate(majority)
        self.assertEqual({1, 2, 7, 8, 9}, next_round.required())
        self.assertEqual(state.peers, next_round.peers)
        next_round = next_round.publication(majority).publication(majority)
        with self.assertRaisesRegex(ValueError, 'ancestry headroom'):
            next_round.publication(majority)
        self.assertEqual(12, next_round.consolidate(majority).publication(majority).tip)

    def test_lost_ack_requires_both_old_and_possibly_published_endpoints(self):
        for delivered in (False, True):
            state, _ = r.fixture(3, (delivered,))
            node = 2
            for cut in (1, 7):
                peers = list(state.peers)
                peers[node] = r.Peer(cut)
                mutant = replace(state, peers=tuple(peers))
                if cut != state.physical[node]:
                    with self.assertRaisesRegex(ValueError, 'forgot possible'):
                        mutant.check()
            self.assertTrue({1, 7} <= state.required())

    def test_old_copy_does_not_cancel_a_delayed_publication(self):
        state, _ = r.fixture(3)
        self.assertEqual(state, state.observe(2))
        late = state.deliver_pending(2)
        self.assertEqual(state.peers, late.peers)
        self.assertEqual(7, late.physical[2])
        settled = late.observe(2)
        self.assertEqual(r.Peer(7), settled.peers[2])
        self.assertNotIn(1, settled.required())

    def test_no_second_target_while_a_peer_has_an_unresolved_publication(self):
        peers = (r.Peer(0),)*3
        state = r.State(0, 0, None, peers, (0, 0, 0))
        state = state.publication((0, 1), ((2, True),))
        self.assertEqual(r.Peer(0, 1), state.peers[2])
        with self.assertRaisesRegex(ValueError, 'unresolved or lagging'):
            state.publication((0, 1), ((2, True),))
        self.assertEqual(2, state.observe(2).publication((0, 1), ((2, False),)).tip)

    def test_minority_duplicate_or_stale_copies_cannot_consolidate(self):
        state, majority = r.fixture()
        for copies in (majority[:2], (0, 0, 1), (0, 1, 4), (0, 1, 99)):
            with self.subTest(copies=copies), self.assertRaises(ValueError):
                state.consolidate(copies)

    def test_pending_publication_cannot_be_cleared_by_a_status_hint(self):
        state, _ = r.fixture(3)
        # No hint input exists. The observation reads the separate environment
        # truth; even an actual old copy leaves uncertainty unchanged.
        self.assertEqual(state, state.observe(2))
        with self.assertRaisesRegex(ValueError, 'forgot possible'):
            replace(state, peers=state.peers[:2]+(r.Peer(7),)).check()

    def test_repeated_stable_work_preserves_missing_voters_and_six_group_bound(self):
        result = r.run(1000)
        self.assertEqual(8, result['histories'])
        self.assertEqual(8000, result['publications'])
        self.assertTrue(all(row['maximumRequiredBridges'] <= 6 for row in result['cases']))
        self.assertTrue(all(row['consolidations'] > 0 for row in result['cases'] if row['size'] == 5))
        for key in ('productionRuntime', 'crashQualification', 'jointTransitions', 'metadataBytesQualified', 'phase3Complete'):
            self.assertFalse(result[key])

    def test_invalid_delivery_and_round_parameters_are_rejected(self):
        for count in (True, 0, 1, 10001):
            with self.assertRaisesRegex(ValueError, 'research round count'):
                r.run(count)
        state = r.State(0, 0, None, (r.Peer(0),)*3, (0, 0, 0))
        for uncertain in (((2, 1),), ((0, True),), ((2, True), (2, False))):
            with self.assertRaises(ValueError):
                state.publication((0, 1), uncertain)


if __name__ == '__main__':
    unittest.main()
