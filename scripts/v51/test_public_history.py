import copy
import unittest
from .public_history import check


def write(name='w', start=1, end=2, outcome='SUCCESS'):
    return dict(opId=name, kind='addAll', startNanos=start, endNanos=end, outcome=outcome,
                documents=[dict(id=1, value='one'), dict(id=2, value='two')])


def read(docs, start=3, end=4):
    return dict(opId='r', kind='read', startNanos=start, endNanos=end, outcome='SUCCESS', documents=docs)


class PublicHistoryTest(unittest.TestCase):
    def test_completed_atomic_write_and_ordered_read(self):
        w = write(); self.assertEqual(check([w, read(w['documents'])])['status'], 'PASS')

    def test_stale_read_after_success_rejected(self):
        with self.assertRaisesRegex(ValueError, 'not linearizable'): check([write(), read([])])

    def test_partial_atomic_bulk_rejected(self):
        w = write()
        with self.assertRaisesRegex(ValueError, 'not linearizable'): check([w, read(w['documents'][:1])])

    def test_document_order_is_observable(self):
        w = write()
        with self.assertRaisesRegex(ValueError, 'not linearizable'): check([w, read(w['documents'][::-1])])

    def test_overlapping_old_read_is_legal(self):
        self.assertEqual(check([write(start=2, end=3), read([], start=1, end=4)])['status'], 'PASS')

    def test_pending_write_can_be_included_or_omitted(self):
        w = write(end=None, outcome='PENDING')
        for docs in ([], w['documents']): self.assertEqual(check([w, read(docs)])['status'], 'PASS')

    def test_indeterminate_response_does_not_claim_completion(self):
        w = write(outcome='INDETERMINATE')
        history = [w, read([], 3, 4), dict(read(w['documents'], 5, 6), opId='later')]
        self.assertEqual(check(history)['status'], 'PASS')

    def test_not_submitted_cannot_explain_effect(self):
        w = write(outcome='NOT_SUBMITTED')
        with self.assertRaisesRegex(ValueError, 'not linearizable'): check([w, read(w['documents'])])

    def test_search_and_operation_bounds_fail_closed(self):
        for bounds in (dict(max_operations=1), dict(max_states=0)):
            with self.assertRaisesRegex(ValueError, 'bound'): check([write(), read([])], **bounds)

    def test_malformed_history_rejected(self):
        for change in (dict(endNanos=0), dict(endNanos=None), dict(outcome='PASS'), dict(documents=[])):
            with self.assertRaises(ValueError): check([dict(write(), **change)])
        with self.assertRaisesRegex(ValueError, 'duplicate'): check([write(), copy.deepcopy(write())])
