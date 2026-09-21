import copy
import unittest
from .public_recovery_evidence import admission, cursors, lifecycle, negatives


def fixture():
    history = [dict(opId='w', node='node-1', pid=11, kind='addAll', outcome='CANCELLED', documents=[dict(id=1, value='one')])]
    rows = [dict(event='CUT_REACHED', cut='READ_CAPTURED', order=1),
            dict(event='CLIENT_INVOKE', opId='w', order=2),
            dict(event='CLIENT_CANCEL', target='w', cancelled=True, order=3),
            dict(event='CUT_RELEASED', cut='READ_CAPTURED', order=4)]
    return history, {'node-1': [dict(row, pid=11) for row in rows]}


class PublicRecoveryEvidenceTest(unittest.TestCase):
    def test_queued_cancel_requires_a_crossing_cancel_and_no_authority(self):
        history, traces = fixture()
        self.assertEqual('PASS', lifecycle(history, traces, 'cancel-queued', 'w')['status'])
        self.assertEqual(3, len(negatives(history, traces, 'cancel-queued', 'w')))

    def test_cancel_before_invocation_or_after_release_is_not_the_required_cut(self):
        for order in (0, 5):
            history, traces = fixture(); traces['node-1'][2]['order'] = order
            with self.assertRaisesRegex(ValueError, 'cancel did not cross'): lifecycle(history, traces, 'cancel-queued', 'w')
        history, traces = fixture(); traces['node-1'][1]['order'] = 0
        with self.assertRaisesRegex(ValueError, 'queued cancellation'): lifecycle(history, traces, 'cancel-queued', 'w')

    def test_false_cancel_and_wrong_boundary_fail(self):
        for key, value in [('target', 'other'), ('cancelled', False)]:
            history, traces = fixture(); traces['node-1'][2][key] = value
            with self.assertRaises(ValueError): lifecycle(history, traces, 'cancel-queued', 'w')
        history, traces = fixture(); traces['node-1'][0]['cut'] = 'ACCEPT_AFTER_FORCE'
        with self.assertRaises(ValueError): lifecycle(history, traces, 'cancel-queued', 'w')

    def test_cancel_inside_pause_still_requires_its_target_invocation_first(self):
        history, traces = fixture(); traces['node-1'][1]['order'] = 3; traces['node-1'][2]['order'] = 2
        with self.assertRaisesRegex(ValueError, 'precedes target'): lifecycle(history, traces, 'cancel-queued', 'w')

    def test_admission_requires_distinct_processes_and_unchanged_authority(self):
        before = {'promises.gsr': dict(size=1, sha256='abc')}
        results = [dict(pid=p, state='FAILED', outcome='NOT_APPLICABLE', reasonCode='INTEGRITY_FAILURE') for p in (1, 2)]
        self.assertEqual('PASS', admission(before, before, results)['status'])
        with self.assertRaisesRegex(ValueError, 'changed retained'): admission(before, {}, results)
        with self.assertRaisesRegex(ValueError, 'independent'): admission(before, before, [results[0], results[0]])
        for change in [dict(state='FOLLOWER'), dict(outcome='SUCCESS'), dict(reasonCode='NOT_READY')]:
            with self.assertRaisesRegex(ValueError, 'unsafe authority'): admission(before, before, [dict(results[0], **change), results[1]])

    def test_close_evidence_binds_the_actual_pinned_read(self):
        history = [dict(opId='held', node='node-1', pid=11, kind='read', outcome='SUCCESS'),
                   dict(opId='new-owner', kind='duplicateStart', outcome='SUCCESS')]
        events = [dict(event='CLIENT_INVOKE', opId='held'), dict(event='CUT_REACHED', cut='READ_CAPTURED'),
                  dict(event='CLIENT_FAILURE', kind='closeHandle', reasonCode='DEADLINE_EXCEEDED'),
                  dict(event='CLIENT_FAILURE', kind='duplicateStart', reasonCode='STORAGE_FAILURE'),
                  dict(event='CUT_RELEASED'), dict(event='READ_CALLBACK', opId='held'),
                  dict(event='CLIENT_SUCCESS', opId='held'), dict(event='HANDLE_CLOSED')]
        traces = {'node-1': [dict(r, pid=11, order=i+1) for i, r in enumerate(events)]}
        self.assertEqual('PASS', lifecycle(history, traces, 'close-pinned', 'held')['status'])
        self.assertEqual(3, len(negatives(history, traces, 'close-pinned', 'held')))
        changed = copy.deepcopy(traces); changed['node-1'][5]['opId'] = 'earlier-read'
        with self.assertRaisesRegex(ValueError, 'unrelated read'): lifecycle(history, changed, 'close-pinned', 'held')

    def test_cursor_oracle_rejects_changed_continuation_and_stale_success(self):
        report = dict(first=[3], continuedAfterReads=[1], freshAfterRebuild=[3], mutationFailure='CursorError', rebuildFailure='CursorError',
                      sequenceAfterReads=1, sequenceAfterRebuild=2)
        self.assertEqual('PASS', cursors(report, report)['status'])
        for change in [dict(continuedAfterReads=[3]), dict(rebuildFailure='ACCEPTED'), dict(mutationFailure='ACCEPTED'), dict(sequenceAfterReads=2)]:
            with self.assertRaises(ValueError): cursors(dict(report, **change), report)
        for key in ('mutationFailure', 'rebuildFailure'):
            changed = dict(report, **{key: 'ACCEPTED'})
            with self.assertRaisesRegex(ValueError, 'stale cursor'): cursors(changed, changed)


if __name__ == '__main__': unittest.main()
