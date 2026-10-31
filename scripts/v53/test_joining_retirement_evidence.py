"""Independent original projection/accounting and qualification driver checks."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import joining_retirement_evidence as j


def fixture():
    original = {
        'initialTyped': {'.': None, 'preparation.json': b'original config', 'learner.gsr': b'receipt',
            'preparation.lock': b'', 'prepared.json': b'prepared', 'backup': None, 'backup/member': b'backup'},
        'replica': {'.': None, 'replica.lock': b'', 'learner-admission.gslp': b'old', 'learner': None, 'learner/source': b'old',
            'generations': None, 'generations/a': None, 'generations/a/generation.gsr': b'current', 'grants.gsr': b'promise'},
        'intent': {'.': None, 'source': None, 'source/file': b'old', 'intent.json': b'old'},
        'operation': {'.': None, 'operation.lock': b'', 'nonempty.lock': b'foreign', 'learner.gslp': b'plan'},
        'voterStage': {'.': None, 'replica.lock': b'', 'root.gsr': b'old'},
        'placement': {'.': None, 'joined.json': b'original'},
    }
    sources = {index: {'source.gscp': b'x'*index, 'generation.gsr': b'y', 'same.image': b'image'} for index in (4, 8, 9)}
    installed = {'.': None, 'root.gsr': b'root', 'grants.gsr': b'promise', 'generations': None, 'generations/a': None,
        'generations/a/source.gscp': b'packet', 'generations/a/generation.gsr': b'manifest', 'generations/a/same.image': b'image'}
    return SimpleNamespace(expected=original, receipt=b'receipt', history=SimpleNamespace(sources=sources), installed=installed)


class JoiningRetirementEvidenceTest(unittest.TestCase):
    def test_projection_preserves_live_generation_locks_and_unique_typed_proofs(self):
        owner = fixture(); before = copy.deepcopy(owner.expected)
        removed = {(r['root'], r['name']) for r in j.deletions(owner.expected, owner.receipt)}
        self.assertEqual({('initialTyped', 'backup/member'), ('initialTyped', 'backup'), ('initialTyped', 'prepared.json'),
            ('replica', 'learner/source'), ('replica', 'learner'), ('replica', 'learner-admission.gslp'),
            ('intent', 'source/file'), ('intent', 'source'), ('intent', 'intent.json'),
            ('operation', 'nonempty.lock'), ('operation', 'learner.gslp'), ('voterStage', 'root.gsr')}, removed)
        self.assertEqual(before, owner.expected)

    def test_deletion_order_is_root_then_deepest_then_name(self):
        owner = fixture(); rows = j.deletions(owner.expected, owner.receipt)
        self.assertEqual([dict(root='initialTyped', name=n) for n in ('backup/member', 'backup', 'prepared.json')], rows[:3])
        self.assertLess(rows.index(dict(root='intent', name='source/file')), rows.index(dict(root='intent', name='source')))

    def test_nested_empty_lock_keeps_ancestors(self):
        owner = fixture(); owner.expected['intent'].update({'source/nested': None, 'source/nested/owned.lock': b''})
        removed = j.deletions(owner.expected, owner.receipt)
        for name in ('source', 'source/nested', 'source/nested/owned.lock'):
            self.assertNotIn(dict(root='intent', name=name), removed)
        self.assertIn(dict(root='intent', name='source/file'), removed)

    def test_absent_or_ambiguous_original_receipt_is_rejected(self):
        for mode in ('absent', 'duplicate'):
            owner = fixture()
            if mode == 'absent': del owner.expected['initialTyped']['learner.gsr']
            else: owner.expected['voterStage']['learner.gsr'] = owner.receipt
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, '^joining retirement unique typed original$'):
                j.deletions(owner.expected, owner.receipt)

    def test_same_image_in_four_owners_is_charged_four_times_plus_full_typed_reservation(self):
        rows = j.reservations(fixture())
        self.assertEqual([5, 5, 5, 5, 64*1024*1024], [r['bytes'] for r in rows if r['unit'] == 'APPLICATION'])
        self.assertEqual(11, len(rows))

    def test_original_pending_and_published_source_charges_remain_distinct(self):
        owner = fixture(); rows = j.reservations(owner)
        self.assertEqual([9], [r['bytes'] for r in rows if r['unit'] == 'SOURCE'])
        self.assertEqual([10], [r['bytes'] for r in rows if r['unit'] == 'LEARNER'])
        self.assertEqual([5758292], [r['bytes'] for r in rows if r['unit'] == 'JOURNAL'])
        # Post-retirement files must never reduce original charges.
        owner.expected.clear(); self.assertEqual(rows, j.reservations(owner))

    def test_stage_companions_are_charged_in_addition_to_dormant_files(self):
        owner = fixture(); rows = j.reservations(owner)
        owner.installed['admitted.gsr'] = b'x'*123
        changed = j.reservations(owner)
        self.assertEqual([5, 983065], [r['bytes'] for r in rows if r['unit'] == 'GENERATION'])
        self.assertEqual([5, 983188], [r['bytes'] for r in changed if r['unit'] == 'GENERATION'])

    def test_native_owner_charges_only_installed_generation_with_original_image_owner(self):
        owner = fixture(); rows = j.native_storage(owner.installed, owner.expected)
        self.assertEqual([
            dict(unit='APPLICATION', owner='generation-a:same.image', bytes=5),
            dict(unit='GENERATION', owner='a', bytes=14),
            dict(unit='JOURNAL', owner='membership-grants', bytes=32*1024*1024),
            dict(unit='MISC', owner='current-authority', bytes=2*1024*1024)], rows)

    def test_surviving_proofs_cannot_overflow_native_misc(self):
        owner = fixture(); owner.expected['operation']['oversized'] = b'x'*(2*1024*1024)
        with self.assertRaisesRegex(ValueError, '^joining retirement native immutable capacity$'):
            j.native_storage(owner.installed, owner.expected)

    def test_original_inode_is_never_obtained_from_relocated_filesystem(self):
        gate = j.Retirement.__new__(j.Retirement); gate.ids = {'retirement': {'retired.json': dict(key='original-key')}}
        with patch.object(Path, 'stat', side_effect=AssertionError('original paths cannot be opened')):
            self.assertEqual(dict(key='original-key', size=3, sha256=j.sha(b'abc')), gate.fingerprint('retirement', 'retired.json', b'abc'))

    def test_invalid_original_is_not_negative_evidence(self):
        with patch.object(j, 'validate', side_effect=ValueError('original failed')), patch.object(j.shutil, 'copytree') as copied:
            with self.assertRaisesRegex(ValueError, '^original failed$'): j.qualify(Path('/original'))
            copied.assert_not_called()

    def test_prior_gate_failure_cannot_count_as_new_rejection(self):
        with patch.object(j, 'validate', return_value={}) as checked, patch.object(j.shutil, 'copytree'), patch.object(j, 'mutate'), \
             patch.object(j.placement, 'validate', side_effect=ValueError('prior gate failed')):
            with self.assertRaisesRegex(ValueError, '^prior gate failed$'): j.qualify(Path('/original'))
            self.assertEqual(1, checked.call_count)

    def test_unrelated_rejection_is_not_a_pass(self):
        with patch.object(j, 'validate', side_effect=[{}, ValueError('wrong reason')]), patch.object(j.shutil, 'copytree'), \
             patch.object(j, 'mutate'), patch.object(j.placement, 'validate'):
            with self.assertRaisesRegex(ValueError, '^joining unrelated retirement negative:'): j.qualify(Path('/original'))

    def test_accepted_mutation_is_a_failure(self):
        with patch.object(j, 'validate', return_value={}), patch.object(j.shutil, 'copytree'), patch.object(j, 'mutate'), \
             patch.object(j.placement, 'validate'):
            with self.assertRaisesRegex(ValueError, '^joining retirement mutation accepted:'): j.qualify(Path('/original'))


if __name__ == '__main__': unittest.main()
