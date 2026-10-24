import unittest
from unittest.mock import patch
from . import covered_context_process_evidence as q


class CoveredContextProcessTest(unittest.TestCase):
    def rows(self):
        expected = ['CONTEXT_SETTLEMENT_VALIDATED', 'SETTLED_VOTE_PARENT_FORCED', 'CONTEXT_SETTLEMENT_CLEARED']
        return expected, [dict(event=v) for v in expected]

    def test_exact_order_and_explicit_scope(self):
        expected, rows = self.rows(); rows.append(dict(status='PASS', peakImages=6, runtimeEnabled=False))
        self.assertEqual(6, q.force_trace(rows, expected, 'none', None, True))

    def test_missing_or_reordered_force_is_rejected(self):
        for replacement in ([], ['SETTLED_VOTE_PARENT_FORCED', 'CONTEXT_SETTLEMENT_VALIDATED', 'CONTEXT_SETTLEMENT_CLEARED']):
            expected, _ = self.rows()
            with self.assertRaisesRegex(ValueError, 'exact force/death order'):
                q.force_trace([dict(event=v) for v in replacement], expected, 'halt', expected[-1], False)

    def test_old_ack_cannot_be_ignored(self):
        expected, rows = self.rows(); rows.append(dict(event='APPLY_BEFORE_RETURN'))
        with self.assertRaisesRegex(ValueError, 'exact force/death order'): q.force_trace(rows, expected, 'halt', expected[-1], False)

    def test_kill_requires_exact_boundary_handshake(self):
        expected, rows = self.rows()
        with self.assertRaisesRegex(ValueError, 'kill handshake'): q.force_trace(rows, expected, 'kill', expected[-1], False)
        rows.append(dict(event='AWAITING_KILL', cut='other'))
        with self.assertRaisesRegex(ValueError, 'kill handshake'): q.force_trace(rows, expected, 'kill', expected[-1], False)
        rows[-1]['cut'] = expected[-1]; q.force_trace(rows, expected, 'kill', expected[-1], False)

    def test_boolean_capacity_and_enabled_runtime_are_rejected(self):
        for capacity, runtime in ((True, False), (8, False), (0, False), (4, True), (4, 0)):
            expected, rows = self.rows(); rows.append(dict(status='PASS', peakImages=capacity, runtimeEnabled=runtime))
            with self.assertRaisesRegex(ValueError, 'result scope'): q.force_trace(rows, expected, 'none', None, True)

    def test_success_requires_actual_return(self):
        with self.assertRaisesRegex(ValueError, 'missing return'): q.force_trace([], [], 'none', None, True)

    def test_original_validation_precedes_mutations(self):
        with patch.object(q, 'validate', side_effect=ValueError('invalid original')), patch.object(q.shutil, 'copytree') as copy:
            with self.assertRaisesRegex(ValueError, 'invalid original'): q.qualify('raw')
            copy.assert_not_called()

    def test_fixed_matrix_and_negative_inventory(self):
        self.assertEqual(11, len(q.CUTS)); self.assertEqual(11, len(set(q.CUTS))); self.assertEqual(20, len(q.VARIANTS))


if __name__ == '__main__': unittest.main()
