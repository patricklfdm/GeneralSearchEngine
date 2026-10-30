import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import discovered_selection_evidence as d


class DiscoveredSelectionEvidenceTest(unittest.TestCase):
    def test_damaged_original_never_reaches_network_acceptance(self):
        with patch.object(d, 'inventory'), patch.object(d, 'physical', side_effect=ValueError('original damaged')), \
                patch.object(d, 'network') as network:
            with self.assertRaisesRegex(ValueError, '^original damaged$'): d.inspect('unused')
            network.assert_not_called()

    def test_qualification_rejects_original_before_running_negatives(self):
        with patch.object(d, 'inspect', side_effect=ValueError('original damaged')), patch.object(d.shutil, 'copytree') as copytree:
            with self.assertRaisesRegex(ValueError, '^original damaged$'): d.qualify('unused')
            copytree.assert_not_called()

    def test_late_identical_reply_can_complete_one_bounded_exchange(self):
        attempts = [dict(row=dict(request='same request', response='same response'), deliveries=[]) for _ in range(3)]
        attempts[-1]['deliveries'] = [40]
        self.assertEqual(40, d.identical_attempts(attempts))
        attempts.append(copy.deepcopy(attempts[-1]))
        with self.assertRaisesRegex(ValueError, '^discovered selection identical bounded attempts$'):
            d.identical_attempts(attempts)

    def test_changed_reply_cannot_substitute_for_an_expired_attempt(self):
        attempts = [dict(row=dict(request='same request', response='original'), deliveries=[]),
                    dict(row=dict(request='same request', response='substitute'), deliveries=[40])]
        with self.assertRaisesRegex(ValueError, '^discovered selection identical bounded attempts$'):
            d.identical_attempts(attempts)

    def test_offered_response_is_not_a_delivered_reply(self):
        with self.assertRaisesRegex(ValueError, '^discovered selection response delivered$'):
            d.identical_attempts([dict(row=dict(request='request', response='response'), deliveries=[])])

    def test_duplicate_or_missing_installation_boundary_is_not_accepted(self):
        row = dict(node='node-4', event='ROUND_INSTALLED')
        self.assertEqual(0, d.event_boundary([row], 'node-4', 'ROUND_INSTALLED'))
        for events in ([], [row, row], [dict(row, node='node-5')]):
            with self.subTest(events=events), self.assertRaisesRegex(ValueError, '^discovered selection exact boundary:'):
                d.event_boundary(events, 'node-4', 'ROUND_INSTALLED')

    def test_original_links_are_rejected_before_any_physical_decode(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'original').write_bytes(b'original')
            (root/'link').symlink_to('original')
            with self.assertRaisesRegex(ValueError, '^discovered selection regular inventory$'):
                d.inventory(root)


if __name__ == '__main__': unittest.main()
