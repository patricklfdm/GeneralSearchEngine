import base64
import copy
import unittest
from .format_encoder import encode
from .public_fault_evidence import read_fence


def fixture(before=False, epoch=3):
    cut = 'READ_BEFORE_CAPTURE' if before else 'READ_CAPTURED'
    promise = encode('PROMISE', dict(manifestDigest='ab' * 32, epoch=epoch, proposer='node-2',
                                    incarnation='11111111-1111-1111-1111-111111111111'))
    rows = [dict(event='CLIENT_INVOKE', opId='read-1', order=1), dict(event=cut, epoch=2, order=2),
            dict(event='CUT_REACHED', cut=cut, order=3),
            dict(event='FORCE', kind='PROMISE', record=base64.b64encode(promise).decode(), order=4),
            dict(event='CUT_RELEASED', cut=cut, order=5)]
    if not before: rows.append(dict(event='READ_CALLBACK', opId='read-1', order=6))
    operation = dict(opId='read-1', outcome='NOT_APPLICABLE' if before else 'SUCCESS', reasonCode='STALE_EPOCH')
    return rows, operation


class PublicFaultEvidenceTest(unittest.TestCase):
    def test_both_sides_of_capture_have_distinct_legal_outcomes(self):
        for before in (True, False):
            rows, operation = fixture(before)
            self.assertEqual(read_fence(rows, operation, before)['status'], 'PASS')

    def test_missing_or_equal_promise_does_not_prove_fencing(self):
        for epoch in (2, 1):
            rows, operation = fixture(epoch=epoch)
            with self.assertRaises(ValueError): read_fence(rows, operation, False)
        rows, operation = fixture(); rows.pop(3)
        with self.assertRaisesRegex(ValueError, 'higher promise'): read_fence(rows, operation, False)

    def test_promise_outside_the_pause_interval_rejected(self):
        rows, operation = fixture(); rows[3]['order'] = 9
        with self.assertRaisesRegex(ValueError, 'higher promise'): read_fence(rows, operation, False)

    def test_uncaptured_stale_read_cannot_execute_a_callback_or_succeed(self):
        rows, operation = fixture(True)
        with self.assertRaisesRegex(ValueError, 'reject'):
            read_fence(rows, dict(operation, outcome='SUCCESS'), True)
        rows.append(dict(event='READ_CALLBACK', opId='read-1', order=6))
        with self.assertRaisesRegex(ValueError, 'callback'): read_fence(rows, operation, True)

    def test_captured_read_must_complete_after_the_crossing(self):
        rows, operation = fixture()
        with self.assertRaisesRegex(ValueError, 'complete'):
            read_fence(rows, dict(operation, outcome='NOT_APPLICABLE'), False)
        changed = copy.deepcopy(rows); changed[-1]['order'] = 4
        with self.assertRaisesRegex(ValueError, 'complete'): read_fence(changed, operation, False)
