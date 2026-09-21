import copy
import unittest
from .public_protocol_evidence import ranges, crash_rows, tail_decision


class PublicProtocolEvidenceTest(unittest.TestCase):
    def test_absent_minority_tail_selects_no_entry_before_new_activation(self):
        tail_decision([dict(nextEntry=None, bases=[dict(node='node-2'), dict(node='node-3')])], 'entry', 'node-1', False)

    def test_selected_tail_requires_its_original_bytes_and_owner_in_quorum(self):
        selected = dict(nextEntry='entry', bases=[dict(node='node-1'), dict(node='node-2')])
        tail_decision([selected], 'entry', 'node-1', True)
        for changes in (dict(nextEntry=None), dict(nextEntry='changed'), dict(bases=[dict(node='node-2'), dict(node='node-3')])):
            with self.subTest(changes=changes), self.assertRaises(ValueError): tail_decision([dict(selected, **changes)], 'entry', 'node-1', True)

    def test_discard_claim_requires_quorum_without_the_original_disk(self):
        with self.assertRaises(ValueError):
            tail_decision([dict(nextEntry=None, bases=[dict(node='node-1'), dict(node='node-3')])], 'entry', 'node-1', False)

    def test_identical_retries_and_out_of_order_observations(self):
        self.assertEqual(ranges([(2, b'cd'), (0, b'ab'), (0, b'ab')], 4), b'abcd')

    def test_missing_or_overlapping_ranges_do_not_establish_a_prefix(self):
        for parts in ([], [(2, b'cd')], [(0, b'ab'), (3, b'd')], [(0, b'abc'), (2, b'cd')]):
            with self.subTest(parts=parts), self.assertRaises(ValueError): ranges(parts, 4)

    def test_changed_retry_cannot_replace_retained_bytes(self):
        with self.assertRaisesRegex(ValueError, 'changed transfer retry'): ranges([(0, b'ab'), (0, b'cd')], 2)

    def test_transfer_watermark_cannot_split_an_observed_chunk(self):
        with self.assertRaises(ValueError): ranges([(0, b'abc')], 2)

    def fixture(self):
        observed = dict(event='CUT_REACHED', pid=101, generation=1, order=2, cut='cut', mode='kill')
        traces = {'node-1': [dict(event='cut', pid=101, generation=1, order=1), observed,
                             dict(event='STARTED', pid=102, generation=2, order=1)]}
        crash = dict(node='node-1', pid=101, cut='cut', mode='kill', exitCode=-9, observed=observed)
        return traces, crash

    def test_only_before_crash_rows_qualify(self):
        traces, crash = self.fixture()
        self.assertEqual(len(crash_rows(traces, crash)), 1)

    def test_marker_without_actual_boundary_rejected(self):
        traces, crash = self.fixture(); traces['node-1'][0]['event'] = 'unrelated'
        with self.assertRaisesRegex(ValueError, 'observed boundary'): crash_rows(traces, crash)

    def test_storage_marker_must_name_the_exact_storage_cut(self):
        traces, crash = self.fixture(); crash['cut'] = 'STORAGE_CUT:SELECTOR_BEFORE_ACK'
        crash['observed']['cut'] = crash['cut']
        traces['node-1'][0].update(event='STORAGE_CUT', cut='FLOOR_BEFORE_ACK')
        with self.assertRaisesRegex(ValueError, 'observed boundary'): crash_rows(traces, crash)
        traces['node-1'][0]['cut'] = 'SELECTOR_BEFORE_ACK'
        self.assertEqual(len(crash_rows(traces, crash)), 1)

    def test_wrong_cut_pid_exit_or_missing_restart_rejected(self):
        traces, crash = self.fixture()
        for values in (dict(pid=102), dict(cut='other'), dict(exitCode=0), dict(mode='halt')):
            with self.subTest(values=values), self.assertRaises(ValueError): crash_rows(traces, dict(crash, **values))
        changed = copy.deepcopy(traces); changed['node-1'].pop()
        with self.assertRaisesRegex(ValueError, 'restart'): crash_rows(changed, crash)

    def test_duplicate_crash_record_is_not_a_single_boundary(self):
        traces, crash = self.fixture(); traces['node-1'].append(copy.deepcopy(crash['observed']))
        with self.assertRaisesRegex(ValueError, 'crash cut'): crash_rows(traces, crash)
