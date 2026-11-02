"""Conditional process authority checks; native originals are separate evidence."""
from concurrent.futures import ThreadPoolExecutor
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import joining_process_authority as m
from . import test_joining_process_composition as fixtures


class ProcessAuthorityTest(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.JoiningProcessCompositionTest(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        self.raw, self.case = fixture.raw, fixture.case
        self.observed = m.observations(self.raw, self.case)

    def test_control_projection_keeps_every_actual_event_and_original_control(self):
        before = m.run.h.inventory(self.raw)
        prior = m.physical.observations(self.raw, self.case)
        self.assertEqual(prior['events'], [v for v in self.observed['events'] if v['event'] != m.CONTROL])
        self.assertEqual(5, len(self.observed['events'])-len(prior['events']))
        anchors = m.controls(self.observed['events'], self.observed)
        self.assertLess(anchors['halt']['CUT'], anchors['resume']['STARTED'])
        self.assertLess(anchors['resume']['READY'], anchors['resume']['CLOSED'])
        self.assertEqual(self.observed, m.observations(self.raw, self.case))
        self.assertEqual(before, m.run.h.inventory(self.raw))

    def test_missing_duplicate_changed_and_foreign_control_anchors_refuse(self):
        rows = self.observed['events']; at = next(i for i, v in enumerate(rows) if v['event'] == m.CONTROL)
        for action in ('missing', 'duplicate', 'changed', 'foreign'):
            changed = copy.deepcopy(rows)
            if action == 'missing': changed.pop(at)
            elif action == 'duplicate': changed.insert(at, changed[at])
            elif action == 'changed': changed[at]['value']['pid'] += 10
            else: changed[at]['origin'] = 'foreign'
            with self.subTest(action=action), self.assertRaisesRegex(ValueError, 'original control anchors'):
                m.controls(changed, self.observed)
        with self.assertRaisesRegex(ValueError, 'original control catalogue'): m.controls([], dict(events=[]))

    def test_child_transport_requires_open_return_and_live_process(self):
        events = copy.deepcopy(self.observed['events'])
        scope = 'initialization-resume'
        at = next(i for i, v in enumerate(events) if v.get('scope') == scope and v['event'] == 'FIXTURE_OPEN_RETURNED')
        event = dict(node='node-4', scope=scope, event='BEFORE_REQUEST_WRITE')
        events.insert(at+1, event)
        m.transport_lifetimes(events, m.controls(events, self.observed), self.case)
        events.remove(event); events.insert(at, event)
        with self.assertRaisesRegex(ValueError, 'original endpoint lifetime'):
            m.transport_lifetimes(events, m.controls(events, self.observed), self.case)
        events.remove(event); events.append(event)
        with self.assertRaisesRegex(ValueError, 'original endpoint lifetime'):
            m.transport_lifetimes(events, m.controls(events, self.observed), self.case)

    def test_original_completion_boundary_depends_on_cut_not_global_return_count(self):
        for case in m.run.CASES:
            profile, point, mode = case.split(','); joining = m.physical.topology(profile)[3][-1]
            completed = m.run.POINTS.index(point) >= m.run.POINTS.index('JOINING_RETENTION_DONE_RENAMED')
            wanted = 'JOINING_RETENTION_DONE_RECOVERY_PARENT_FORCED' if completed else 'JOINING_RETENTION_BEFORE_RETURN'
            events = [dict(node=joining, scope='initialization-'+mode, event='JOINING_RETENTION_BEFORE_RETURN'),
                      dict(node=joining, scope='initialization-resume', event=wanted)]
            self.assertEqual(1, m.initialization_point(events, case))
            with self.assertRaisesRegex(ValueError, 'original resumed initialization boundary'):
                m.initialization_point(events[:1], case)
            with self.assertRaisesRegex(ValueError, 'original resumed initialization boundary'):
                m.initialization_point(events+[events[-1]], case)

    def test_ordinary_readers_do_not_accept_a_process_reseal_as_initialization(self):
        for cls in (m.peer.peer.Replay, m.future.Replay, m.learner.Replay):
            reader = object.__new__(cls)
            reader.events = [dict(event='JOINING_RETENTION_DONE_RECOVERY_PARENT_FORCED')]
            with self.assertRaisesRegex(ValueError, 'original initialization count'): reader.initialization_point()
            reader.events = [dict(event='JOINING_RETENTION_BEFORE_RETURN')]*2
            with self.assertRaisesRegex(ValueError, 'original initialization count'): reader.initialization_point()

    def test_all_profiles_require_exact_six_initialized_joining_lifetimes(self):
        for profile in m.run.profiles.PROFILES:
            _, _, old, new = m.physical.topology(profile); reader = m.ProcessLedgers()
            reader.model = SimpleNamespace(old=old, joining=new[-1]); actual = reader.lifetimes()
            self.assertEqual(len(old)+6, len(actual)); self.assertEqual(len(actual), len(set(actual)))
            self.assertNotIn((new[-1], 'initial-owner'), actual)
            for mode in ('halt', 'kill'): self.assertNotIn((new[-1], 'initialization-'+mode), actual)
            self.assertIn((new[-1], 'initialization-resume'), actual)
            self.assertIn((new[-1], 'process-retention-observe'), actual)

    def endpoint(self):
        events = [dict(node='node-4', scope='initialization-resume', event='CURRENT_VALIDATED')]
        events += [dict(node='node-4', scope='initialization-resume', event='AFTER_REQUEST_READ') for _ in range(10)]
        return SimpleNamespace(case=self.case, events=events, model=SimpleNamespace(joining='node-4'),
                               controls={'resume': dict(STARTED=-1, READY=3, CLOSED=8), 'halt': dict(STARTED=-1, CUT=8)})

    def test_endpoint_control_bounds_survive_unrelated_event_insertions(self):
        reader = self.endpoint(); m.lifetime(reader, 'initialization-resume', 4, 7, ready=True)
        for lower, upper in ((2, 7), (4, 8), (-1, 7), (7, 4)):
            with self.assertRaisesRegex(ValueError, 'endpoint lifetime|original positions'):
                m.lifetime(reader, 'initialization-resume', lower, upper, ready=True)
        reader.events[7]['scope'] = 'initialization-halt'
        with self.assertRaisesRegex(ValueError, 'endpoint lifetime'): m.lifetime(reader, 'initialization-resume', 4, 7)

    def test_neither_initial_parent_nor_dying_child_may_export_completion(self):
        for scope in ('initial-endpoint', 'initialization-halt'):
            with self.assertRaisesRegex(ValueError, 'completion before child recovery'):
                m.lifetime(self.endpoint(), scope, 4, 7, ready=True)
        with self.assertRaisesRegex(ValueError, 'original endpoint'):
            m.lifetime(self.endpoint(), 'foreign-endpoint', 4, 7)

    def test_partial_seed_reopen_keeps_native_refusal_and_force_order(self):
        reader = object.__new__(m.Future); reader.case = self.case; reader.model = SimpleNamespace(joining='node-4')
        names = ['ACCEPT_ACTIVE_FORCED', 'ACCEPT_ACTIVE_PARENT_FORCED', 'FIXTURE_OPEN_RETURNED',
                 'INCOMPLETE_NATIVE_USES_REFUSED', 'JOINING_RETENTION_BEFORE_RETURN',
                 'RETENTION_RECOVERY_PARENT_FORCED', 'FUTURE_RETENTION_RECOVERY_FORCED', 'FUTURE_RETENTION_RECOVERY_PARENT_FORCED']
        reader.events = [dict(node='node-4', scope='initialization-resume', event=v) for v in names]
        rows = list(enumerate(names)); reader.reopen_boundary('node-4', 'initialization-resume', 7, [5, 6, 7], rows)
        with self.assertRaisesRegex(ValueError, 'native refusal'):
            reader.reopen_boundary('node-4', 'initialization-resume', 7, [5, 6, 7], rows[:3]+rows[4:])
        moved = [(8 if point == 'FIXTURE_OPEN_RETURNED' else i, point) for i, point in rows]
        with self.assertRaisesRegex(ValueError, 'recovery order'):
            reader.reopen_boundary('node-4', 'initialization-resume', 7, [5, 6, 7], moved)

    def test_complete_seed_keeps_original_accept_recovery_rule(self):
        reader = object.__new__(m.Future); reader.case = '3-ADD,JOINING_RETENTION_DONE_RENAMED,halt'
        rows = [(1, 'ACCEPT_ACTIVE_FORCED'), (2, 'ACCEPT_ACTIVE_PARENT_FORCED')]
        with self.assertRaisesRegex(ValueError, 'reopen before accept recovery'):
            reader.reopen_boundary('node-4', 'initialization-resume', 7, [5, 6, 7], rows)

    def test_mutation_catalogue_includes_all_shared_families(self):
        self.assertEqual(130, len(m.NEGATIVES))
        for stage, module in m.MODULES.items():
            for name, reason in module.NEGATIVES.items(): self.assertEqual(reason, m.NEGATIVES[stage+'/'+name])

    def test_bad_original_and_bad_selection_never_launch_mutations(self):
        with patch.object(m, 'validate', side_effect=ValueError('original failed')), patch.object(m, 'negative') as negative:
            with self.assertRaisesRegex(ValueError, 'original failed'): m.qualify(self.raw, self.case)
            negative.assert_not_called()
        for chosen in ([], ['unknown'], ['exports/source-alias']*2, 'exports/source-alias'):
            with patch.object(m, 'validate') as original, self.assertRaisesRegex(ValueError, 'negative selection'):
                m.qualify(self.raw, self.case, selected=chosen)
            original.assert_not_called()

    def test_subset_and_failures_never_claim_full_catalogue(self):
        original = dict(case=self.case, exports=dict(boundSessions={'pending-joining-checkpoint': 1}), joiningLearnerWrites=1)
        selected = ['exports/source-alias', 'controls/root-alias']
        def result(root, case, anchors, name): return dict(case=name, status='REJECTED', reason=m.NEGATIVES[name])
        with patch.object(m, 'validate', return_value=original), patch.object(m, 'negative', side_effect=result), \
             patch.object(m, 'ProcessPoolExecutor', ThreadPoolExecutor):
            value = m.qualify(self.raw, self.case, selected=selected, workers=2)
        self.assertEqual('PARTIAL', value['status']); self.assertFalse(value['completeNegativeCatalogue'])
        with patch.object(m, 'validate', return_value=original), patch.object(m, 'negative', side_effect=ValueError('unrelated failure')), \
             patch.object(m, 'ProcessPoolExecutor', ThreadPoolExecutor):
            value = m.qualify(self.raw, self.case, selected=selected)
        self.assertEqual('FAIL', value['status']); self.assertEqual(2, len(value['negatives']))
        self.assertFalse(value['phase3Complete']); self.assertTrue(value['originalPreserved'])

    def test_callback_negatives_cannot_change_other_events_or_wire(self):
        anchors = dict(events=[v for v in self.observed['events'] if v['event'] == m.CONTROL])
        for changed in ('events', 'wire'):
            def corrupt(root, *_):
                path = root/(changed+'.json')
                value = m.run.metadata.read(path)
                value.append(dict(event='CURRENT_FILES_FORCED', node='node-1'))
                path.write_bytes(m.f.canonical(value))
            with self.subTest(changed=changed), patch.object(m, 'mutate', side_effect=corrupt), patch.object(m, 'staged') as staged:
                with self.assertRaisesRegex(ValueError, 'changed other callbacks|changed physical inputs'):
                    m.negative(self.raw, self.case, anchors, 'future/write-force-missing')
                staged.assert_not_called()

    def test_isolated_callback_gates_keep_full_original_as_prerequisite(self):
        for stage in ('future', 'learner', 'ballots'):
            reader = SimpleNamespace(run=lambda: dict(status='REJECTED-BY-TARGET'))
            with patch.object(m, 'context_reader', return_value=reader) as selected, patch.object(m, 'Control') as other:
                self.assertEqual(dict(status='REJECTED-BY-TARGET'), m.staged(self.raw, self.case, {}, stage))
                selected.assert_called_once_with(self.raw, self.case, {}, stage); other.assert_not_called()


if __name__ == '__main__': unittest.main()
