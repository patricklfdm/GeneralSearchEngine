"""Reject borrowed pauses, reordered fencing and non-identical PREPARE retries."""
import base64
import copy
from pathlib import Path
import tempfile
import unittest
from . import public_selection_evidence as e, storage_fixture as fixture


class PublicSelectionEvidenceTest(unittest.TestCase):
    def pause(self):
        boundary = dict(event='WIRE_BASIS', cut='continuation', pid=10, order=1)
        pause = dict(event='CUT_REACHED', cut='WIRE_BASIS:continuation', mode='pause', pid=10, order=2)
        release = dict(event='CUT_RELEASED', cut='WIRE_BASIS', pid=10, order=4)
        return [boundary, pause, release], pause

    def test_exact_boundary_and_release_from_same_process(self):
        rows, pause = self.pause()
        before, released, own = e.paused(rows, pause, pause['cut'])
        self.assertEqual(before, rows[0]); self.assertEqual(released, rows[-1]); self.assertEqual(own, rows)

    def test_borrowed_boundary_or_release_cannot_qualify(self):
        rows, pause = self.pause()
        for index, change in ((0, dict(pid=11)), (0, dict(event='OTHER')), (0, dict(cut='first')),
                              (2, dict(pid=11)), (2, dict(order=1)), (2, dict(cut='OTHER'))):
            changed = copy.deepcopy(rows); changed[index].update(change)
            with self.subTest(index=index, change=change), self.assertRaises(ValueError): e.paused(changed, pause, pause['cut'])

    def test_missing_or_duplicate_release_rejected(self):
        rows, pause = self.pause()
        for changed in (rows[:-1], rows+[dict(rows[-1], order=5)], rows+[dict(pause)]):
            with self.assertRaises(ValueError): e.paused(changed, pause, pause['cut'])

    def test_halt_marker_does_not_establish_a_live_held_exchange(self):
        rows, pause = self.pause(); pause['mode'] = 'halt'
        with self.assertRaises(ValueError): e.paused(rows, pause, pause['cut'])

    def test_promise_must_be_higher_and_forced_between_pause_and_release(self):
        with tempfile.TemporaryDirectory() as temp:
            frame = fixture.create(Path(temp))['PROMISE']
        rows, pause = self.pause()
        forced = dict(event='FORCE', kind='PROMISE', pid=10, order=3, record=base64.b64encode(frame).decode())
        rows.insert(2, forced)
        self.assertEqual(2, e.higher_between(rows, pause, rows[-1], forced, 1)['epoch'])
        for epoch, change in ((2, {}), (3, {}), (1, dict(order=1)), (1, dict(order=5)), (1, dict(pid=11)), (1, dict(event='WRITE'))):
            altered = dict(forced, **change)
            with self.subTest(epoch=epoch, change=change), self.assertRaises(ValueError):
                e.higher_between([*rows, altered], pause, rows[-1], altered, epoch)
        with self.assertRaises(ValueError): e.higher_between([r for r in rows if r != forced], pause, rows[-1], forced, 1)

    def test_identical_retry_after_lost_reply_qualifies(self):
        lost = dict(pid=10, order=4, request='prepare-1', frame='frozen-basis-1')
        e.retry_identity(lost, dict(lost, order=8), dict(lost, pid=20, order=2))

    def test_different_request_response_process_or_order_rejects(self):
        lost = dict(pid=10, order=4, request='prepare-1', frame='frozen-basis-1')
        for change in (dict(request='prepare-2'), dict(frame='frozen-basis-2'), dict(pid=11), dict(order=3)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                e.retry_identity(lost, dict(dict(lost, order=8), **change), dict(lost, pid=20))
        for change in (dict(request='prepare-2'), dict(frame='frozen-basis-2')):
            with self.subTest(change=change), self.assertRaises(ValueError):
                e.retry_identity(lost, dict(lost, order=8), dict(lost, **change))


if __name__ == '__main__': unittest.main()
