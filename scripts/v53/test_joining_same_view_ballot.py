"""Allocator durability, monotone reservations and original-first rejection."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import joining_same_view_ballot as m


def event(point, node='node-1', scope=None):
    return dict(node=node, event=point, **({} if scope is None else dict(scope=scope)))


class JoiningSameViewBallotTest(unittest.TestCase):
    def allocate(self, rows): return m.allocations(rows, ('node-1', 'node-2', 'node-4'), 'node-4')

    def state(self):
        state = m.State('a'*64); state.seed('node-1', 1, 1); return state

    def tx(self): return dict(node='node-1', scope=None, start=1, end=7)

    def test_force_before_rename_and_parent_before_return_are_required(self):
        for index in (3, 5):
            rows = [event(v) for v in m.WRITES]; rows.pop(index)
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, '^joining ballot exact allocator force order$'): self.allocate(rows)
        rows = [event(v) for v in m.WRITES]; rows[3], rows[4] = rows[4], rows[3]
        with self.assertRaisesRegex(ValueError, '^joining ballot exact allocator force order$'): self.allocate(rows)

    def test_incomplete_duplicate_and_unknown_callbacks_fail_closed(self):
        for rows, reason in [([event(v) for v in m.WRITES[:-1]], 'incomplete allocation'),
                             ([event(v) for v in [*m.WRITES, m.WRITES[-1]]], 'exact allocator force order'),
                             ([event('ALLOCATOR_MAYBE_FORCED')], 'unsupported allocator event')]:
            with self.assertRaisesRegex(ValueError, '^joining ballot '+reason+'$'): self.allocate(rows)

    def test_foreign_nodes_fields_and_cross_scope_writes_are_rejected(self):
        for row in [event(m.WRITES[0], 'node-9'), dict(event(m.WRITES[0]), counter=2)]:
            with self.assertRaisesRegex(ValueError, '^joining ballot allocator event shape$'): self.allocate([row])
        rows = [event(p, 'node-4', 'retaining-owner') for p in m.WRITES]; rows[-1]['scope'] = 'continuation-owner'
        with self.assertRaisesRegex(ValueError, '^joining ballot exact allocator force order$'): self.allocate(rows)
        with self.assertRaisesRegex(ValueError, '^joining ballot allocator owner scope$'):
            self.allocate([event(m.WRITES[0], 'node-4', 'initial-owner')])

    def test_interleaved_owners_keep_independent_force_transactions(self):
        rows = [v for p in m.WRITES for v in [event(p), event(p, 'node-4', 'retaining-owner')]]
        self.assertEqual([('node-1', 0, 12), ('node-4', 1, 13)], [(v['node'], v['start'], v['end']) for v in self.allocate(rows)])

    def test_unused_reservation_is_burned_and_higher_fence_advances_counter(self):
        state = self.state(); state.reserve(self.tx()); state.reserve(dict(self.tx(), start=8, end=14))
        self.assertEqual(3, state.counters['node-1'])
        state.promise('node-1', 8); state.reserve(dict(self.tx(), start=20, end=26))
        self.assertEqual(9, state.counters['node-1']); self.assertEqual(8, state.steps[-1]['observed'])
        self.assertEqual(3, state.steps[-1]['before'])

    def test_promise_does_not_itself_allocate_and_cannot_regress(self):
        state = self.state(); state.promise('node-1', 5); self.assertEqual(1, state.counters['node-1'])
        with self.assertRaisesRegex(ValueError, '^joining ballot nonmonotonic promise$'): state.promise('node-1', 4)
        self.assertEqual(5, state.observed['node-1'])

    def test_exhaustion_or_unowned_allocation_does_not_change_state(self):
        state = self.state(); state.promise('node-1', 2**63-2)
        with self.assertRaisesRegex(ValueError, '^joining ballot allocation exhausted$'): state.reserve(self.tx())
        self.assertEqual(1, state.counters['node-1']); self.assertEqual([], state.steps)
        with self.assertRaisesRegex(ValueError, '^joining ballot allocation before ownership$'): state.reserve(dict(self.tx(), node='node-4'))

    def test_seed_is_single_use_and_rejects_bool_and_invalid_counter(self):
        state = self.state()
        with self.assertRaisesRegex(ValueError, '^joining ballot original seed$'): state.seed('node-1', 1, 1)
        for counter in (-1, True, 2**63-1):
            with self.assertRaisesRegex(ValueError, '^joining ballot original seed$'): state.seed('node-4', counter, 1)

    def test_comparison_rejects_counter_owner_and_root_substitution(self):
        state = self.state(); expected = dict(root='a'*64, node='node-1', counter=1)
        state.compare('node-1', m.f.encode('records', 'ALLOCATOR', expected), 'capture')
        for changes in (dict(counter=2), dict(node='node-2'), dict(root='b'*64)):
            with self.assertRaisesRegex(ValueError, '^joining ballot exact continuous allocator: capture: node-1$'):
                state.compare('node-1', m.f.encode('records', 'ALLOCATOR', dict(expected, **changes)), 'capture')
        self.assertEqual(1, state.comparisons)

    def reader(self, rows):
        r = m.Replay.__new__(m.Replay); r.events = rows; r.tx = self.allocate(rows)
        r.captures = []; r.used = set(); r.promise_points = set(); r.self_grants = 0; return r

    def grant_events(self): return [event(p) for p in ['CURRENT_DIRECTORY_FORCED', *m.WRITES, 'CURRENT_BEFORE_CAPTURE', *m.PROMISE, 'GRANT_BEFORE_RETURN', 'GRANT_CAPTURED']]

    def cap(self): return dict(node='node-1', scope='network-owner', returnEvent=12, capturedEvent=13, ballot=dict(counter=2, proposer='node-1'), capture='original')

    def test_original_grant_requires_one_complete_prior_allocation(self):
        r = self.reader(self.grant_events()); actions = []; r.bind_grant(self.cap(), actions)
        self.assertEqual({1}, r.used); self.assertEqual({9, 10, 11}, r.promise_points)
        self.assertEqual(['promise', 'grant', 'original'], [v[1] for v in actions])
        for tx in [[], [self.tx(), dict(self.tx(), start=2)], [dict(self.tx(), start=0)], [dict(self.tx(), end=8)]]:
            r = self.reader(self.grant_events()); r.tx = tx
            with self.assertRaisesRegex(ValueError, '^joining ballot exact allocation before local grant$'): r.bind_grant(self.cap(), [])

    def test_remote_promise_cannot_create_local_reservation(self):
        rows = [event(p) for p in ['CURRENT_DIRECTORY_FORCED', 'CURRENT_BEFORE_CAPTURE', *m.PROMISE, 'GRANT_BEFORE_RETURN', 'GRANT_CAPTURED']]
        r = self.reader(rows); cap = dict(self.cap(), returnEvent=5, capturedEvent=6, ballot=dict(counter=9, proposer='node-2'))
        actions = []; r.bind_grant(cap, actions)
        self.assertEqual(0, r.self_grants); self.assertEqual(set(), r.used); self.assertEqual(['promise', 'original'], [v[1] for v in actions])

    def test_promise_force_shape_and_occurrence_cannot_be_reused(self):
        r = self.reader(self.grant_events()); r.promise('node-1', None, 8, 12, dict(counter=2), [])
        with self.assertRaisesRegex(ValueError, '^joining ballot reused promise forces$'): r.promise('node-1', None, 8, 12, dict(counter=2), [])
        r = self.reader(self.grant_events()); r.events[10]['scope'] = 'foreign'
        with self.assertRaisesRegex(ValueError, '^joining ballot exact promise force order$'): r.promise('node-1', None, 8, 12, dict(counter=2), [])

    def test_local_ballot_uses_exact_reserved_counter_and_identity(self):
        r = self.reader([]); r.state = self.state(); r.state.reserve(self.tx()); r.model = SimpleNamespace(states=[dict(identities=[])])
        value = dict(counter=2, proposer='node-1', incarnation='uuid')
        with patch.object(m.a.n.s.catalog, 'identities', return_value={'node-1': dict(storage='uuid')}):
            r.grant('node-1', value)
            for change in [dict(counter=3), dict(proposer='node-2'), dict(incarnation='wrong')]:
                with self.assertRaisesRegex(ValueError, '^joining ballot local grant uses reserved counter$'): r.grant('node-1', dict(value, **change))

    def test_original_failure_prevents_focused_replay_and_workers(self):
        with patch.object(m.a.n.s.collection, 'inventory', return_value={}), patch.object(m.prior, 'validate', side_effect=ValueError('original')), patch.object(m, 'replay') as replay:
            with self.assertRaisesRegex(ValueError, '^original$'): m.validate('/unused')
            replay.assert_not_called()
        with patch.object(m, 'validate', side_effect=ValueError('original')), patch.object(m, 'ProcessPoolExecutor') as pool:
            with self.assertRaisesRegex(ValueError, '^original$'): m.qualify('/unused', workers=4)
            pool.assert_not_called()

    def test_qualification_is_bounded_and_does_not_promote_whole_history_flags(self):
        for workers in (0, 5, True, 1.5):
            with self.assertRaisesRegex(ValueError, '^joining ballot replay workers$'): m.qualify('/unused', workers=workers)
        with patch.object(m.a.n.s.collection, 'inventory', return_value={}), patch.object(m.prior, 'validate', return_value={}), patch.object(m, 'replay', return_value={}):
            result = m.validate('/unused')
        self.assertTrue(result['ballotForceQualified'])
        for field in ('sameViewPhysicalQualified', 'completePhysicalQualified', 'forceAndNetworkQualified', 'processDeathQualified', 'phase3Complete'): self.assertIs(False, result[field])
        with patch.object(m.a.n.s.collection, 'inventory', side_effect=[{}, dict(changed=True)]), patch.object(m.prior, 'validate', return_value={}), patch.object(m, 'replay', return_value={}):
            with self.assertRaisesRegex(ValueError, '^joining ballot original changed$'): m.validate('/unused')

    def negative(self, change=None, error=None, accepted=False):
        before = dict(files={'original':'hash', 'events.json':'events', 'wire.json':'wire'}, directories=['empty']); after = copy.deepcopy(before)
        original = [event('CURRENT_VALIDATED')]; changed = copy.deepcopy(original)
        if change == 'file': after['files']['wire.json'] = 'wrong'
        elif change == 'directory': after['directories'] = []
        elif change == 'observation': changed[0]['event'] = 'CURRENT_FILES_FORCED'
        name = 'force-missing'
        with patch.object(m.shutil, 'copytree'), patch.object(m, 'mutate'), patch.object(m.a.n.s.collection, 'inventory', return_value=after), \
                patch.object(m.a.n.s.collection, 'read_json', side_effect=[original, changed]), \
                patch.object(m, 'replay', side_effect=None if accepted else ValueError(error or m.NEGATIVES[name])):
            return m.negative('/unused', before, name)

    def test_negative_must_protect_original_files_wire_directories_and_other_callbacks(self):
        for change, reason in [('file', 'original files'), ('directory', 'original files'), ('observation', 'other observations')]:
            with self.assertRaisesRegex(ValueError, '^joining ballot negative changed '+reason+'$'): self.negative(change)

    def test_wrong_reason_and_accepted_negative_cannot_count_as_rejection(self):
        with self.assertRaisesRegex(ValueError, '^joining ballot unrelated negative:'): self.negative(error='wrong')
        with self.assertRaisesRegex(ValueError, '^joining ballot accepted mutation:'): self.negative(accepted=True)
        self.assertTrue(self.negative()['originalFilesAndOtherObservationsUnchanged'])


if __name__ == '__main__': unittest.main()
