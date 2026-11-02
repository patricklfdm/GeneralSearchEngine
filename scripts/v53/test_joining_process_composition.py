"""Conditional composition regressions; no synthetic native qualification."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import joining_process_composition as m
from . import test_joining_process_run as fixtures


class JoiningProcessCompositionTest(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.JoiningProcessRunTest(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        self.raw = fixture.raw(); self.case = fixture.case
        self.final = {name: (str(i), ('original-'+name).encode()) for i, name in enumerate(m.transaction.ACTIVE)}
        self.trace = m.run.lines(self.raw/'process-trace.jsonl')
        callbacks = m.child_callbacks(self.final, self.case)
        def parent(scope): return dict(origin='parent', value=dict(node='node-4', scope=scope, event='ORIGINAL_BOUNDARY'))
        trace = [parent('initial-owner')]
        for origin in ('halt', 'resume'):
            controls = [v for v in self.trace if v['origin'] == origin]
            trace.append(controls[0])
            for point in callbacks[origin]:
                if point == 'FIXTURE_CLOSE_RETURNED': trace.append(controls[1])
                trace.append(dict(origin=origin, value=dict(kind='EVENT', value=dict(node='node-4', scope='initialization-'+origin, event=point))))
            trace.append(controls[-1])
        trace.extend(parent(scope) for scope in ('process-retention-observe', 'retaining-owner', 'repeated-basis-owner'))
        m.save_trace(self.raw, trace); self.trace = trace
        (self.raw/'wire.json').write_bytes(b'[]')

    def test_projection_is_exact_actual_order_and_retains_all_origins(self):
        observed = m.observations(self.raw, self.case)
        expected = [(i, v) for i, v in enumerate(self.trace) if v['origin'] == 'parent' or v['value']['kind'] == 'EVENT']
        self.assertEqual([v['value'] if v['origin'] == 'parent' else v['value']['value'] for _, v in expected], observed['events'])
        self.assertEqual([dict(trace=i, origin=v['origin']) for i, v in expected], observed['positions'])
        self.assertEqual({'parent', 'halt', 'resume'}, {v['origin'] for v in observed['positions']})
        self.assertEqual([], observed['wires'])

    def test_actual_child_wire_is_preserved_not_regenerated(self):
        row = dict(request='original-request', response='original-response', withheld=False)
        trace = copy.deepcopy(self.trace)
        trace.insert(-4, dict(origin='resume', value=dict(kind='WIRE', value=row)))
        m.save_trace(self.raw, trace)
        self.assertEqual([row], m.observations(self.raw, self.case)['wires'])

    def test_overlapping_children_and_early_parent_reopen_refuse(self):
        for name in ('overlapping-children', 'observer-before-close', 'foreign-child-owner'):
            with self.subTest(name=name):
                m.save_trace(self.raw, self.trace); m.mutate(self.raw, self.case, name)
                with self.assertRaisesRegex(ValueError, '^'+m.NEGATIVES[name]+'$'): m.observations(self.raw, self.case)

    def test_event_after_child_cut_or_before_start_is_not_projected(self):
        for after in (True, False):
            trace = copy.deepcopy(self.trace)
            i = next(i for i, v in enumerate(trace) if v['origin'] == 'halt' and v['value']['kind'] == 'EVENT')
            row = trace.pop(i); cut = 'CUT' if after else 'STARTED'
            at = next(i for i, v in enumerate(trace) if v['origin'] == 'halt' and v['value']['kind'] == cut)
            trace.insert(at+1 if after else at, row); m.save_trace(self.raw, trace)
            with self.assertRaisesRegex(ValueError, 'outside child lifetime'): m.observations(self.raw, self.case)

    def child_check(self):
        observed = m.observations(self.raw, self.case)
        with patch.object(m.transaction.ledgers.snapshot, 'read', return_value=None), patch.object(m.transaction, 'files', return_value=self.final):
            return m.child_order(self.raw, self.case, observed)

    def test_child_order_and_readiness_use_original_positions(self):
        self.assertEqual(dict(interruptedCallbacks=10, recoveredCallbacks=50), self.child_check())
        for name in ('missing-child-current-force', 'premature-ready'):
            with self.subTest(name=name):
                m.save_trace(self.raw, self.trace); m.mutate(self.raw, self.case, name)
                with self.assertRaisesRegex(ValueError, '^'+m.NEGATIVES[name]+'$'): self.child_check()

    def test_unknown_or_extra_callback_fields_are_not_ignored(self):
        for key, value in (('extra', True), ('event', 'UNKNOWN_CALLBACK')):
            trace = copy.deepcopy(self.trace)
            row = next(v['value']['value'] for v in trace if v['origin'] == 'resume' and v['value']['kind'] == 'EVENT')
            row[key] = value; m.save_trace(self.raw, trace)
            with self.assertRaisesRegex(ValueError, 'exact child owner callbacks'): self.child_check()

    def test_all_declared_cut_models_retain_complete_force_paths(self):
        for case in m.run.CASES:
            selected = m.run.selected(case); at = m.run.POINTS.index(selected['point']); rows = m.child_callbacks(self.final, case)
            self.assertEqual(list(m.run.POINTS[:at+1]), [v for v in rows[selected['mode']] if v.startswith('JOINING_RETENTION_')])
            self.assertEqual(1, rows['resume'].count('FIXTURE_OPEN_RETURNED'))
            self.assertEqual('FIXTURE_CLOSE_RETURNED', rows['resume'][-1])
            self.assertEqual(at < 2, 'INCOMPLETE_NATIVE_USES_REFUSED' in rows['resume'])
            self.assertLess(rows['resume'].index('CURRENT_DIRECTORY_FORCED'), rows['resume'].index('FIXTURE_OPEN_RETURNED'))
            initialized = next(i for i, v in enumerate(rows['resume']) if v.startswith('JOINING_RETENTION_'))
            opened = rows['resume'].index('FIXTURE_OPEN_RETURNED')
            self.assertEqual(at < 2, opened < initialized)
            for point in m.LEDGERS: self.assertEqual(1, rows['resume'].count(point))

    def test_projection_copy_never_changes_original_even_when_reader_fails(self):
        observed = m.observations(self.raw, self.case); before = m.run.h.inventory(self.raw)
        with self.assertRaisesRegex(ValueError, 'reader failed'):
            with m.view(self.raw, observed) as copied:
                self.assertNotEqual(copied, self.raw)
                self.assertEqual(observed['events'], m.run.metadata.read(copied/'events.json'))
                (copied/'events.json').write_bytes(b'changed'); raise ValueError('reader failed')
        self.assertFalse(copied.exists()); self.assertEqual(before, m.run.h.inventory(self.raw))

    def test_original_failure_prevents_projection_and_negatives(self):
        with patch.object(m.transaction, 'validate', side_effect=ValueError('invalid original')), patch.object(m, 'view') as projected:
            with self.assertRaisesRegex(ValueError, 'invalid original'): m.validate(self.raw, self.case)
            projected.assert_not_called()
        with patch.object(m, 'validate', side_effect=ValueError('invalid original')), patch.object(m, 'mutate') as mutated:
            with self.assertRaisesRegex(ValueError, 'invalid original'): m.qualify(self.raw, self.case)
            mutated.assert_not_called()

    def test_unrelated_negative_failure_is_not_a_rejection_success(self):
        with patch.object(m, 'validate', side_effect=[dict(status='PARTIAL'), ValueError('unrelated original error')]):
            with self.assertRaisesRegex(ValueError, 'unrelated composition negative'): m.qualify(self.raw, self.case)

    def test_shared_ordinary_reader_keeps_early_copy_requirement(self):
        owner = object.__new__(m.init.Initialization); owner.root = self.raw
        owner.joined = {'original/generation.gsr': b'generation'}
        with self.assertRaises(FileNotFoundError): owner.initial_current('original/', {'source.gscp': b'capsule', 'ancestry.gsr': b'ancestry'})

    def test_full_physical_failure_cannot_fall_through_to_transport(self):
        with patch.object(m.transaction, 'validate', return_value={}), patch.object(m, 'child_order', return_value={}), \
             patch.object(m, 'physical', side_effect=ValueError('invalid physical history')), patch.object(m.network, 'causal') as transport:
            with self.assertRaisesRegex(ValueError, 'invalid physical history'): m.validate(self.raw, self.case)
            transport.assert_not_called()


if __name__ == '__main__': unittest.main()
