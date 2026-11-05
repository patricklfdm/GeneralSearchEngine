"""Reject balanced journals with wrong storage owners or custody gaps."""
import copy
import unittest
from unittest.mock import patch

from . import publication_generation_resources as g
from . import test_publication_resource_evidence as fixtures
from .test_resource_transitions import charge, row, trace


class PublicationGenerationResourcesTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.PublicationResourceEvidenceTest()
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.rows = g.p.collect(self.fixture.root, self.fixture.events)[0]
        old = g.extents(self.fixture.before); final = g.extents(self.fixture.after)
        self.generation = next(key for key in final if key not in old and key[0] == 'GENERATION')
        self.image = next(key for key in final if key not in old and key[0] == 'APPLICATION')
        base = {**g.FIXED, **old, ('SOURCE', 'old'): len(b'packet'),
                ('APPLICATION', 'old:application.image'): len(b'old-image'),
                g.COMPLETION: g.MAXIMUM, **dict.fromkeys(g.TEMPORARIES, g.MAXIMUM)}
        self.changes = [row('START')]+[row('RESERVE', added=[charge(*key, size)]) for key, size in base.items()]
        self.positions = [len(self.changes)-1]
        self.changes += [row('EXTEND_BEGIN'), row('RESERVE', added=[charge(*self.generation, final[self.generation])]),
                         row('EXTEND_COMMIT', [charge(*g.COMPLETION, g.MAXIMUM)], [charge(*self.image, g.MAXIMUM)])]
        self.positions += [len(self.changes)-1]*7
        self.changes += [row('GENERATION_RELOAD', [charge(*self.image, g.MAXIMUM)], [charge(*self.image, final[self.image])])]
        self.positions += [len(self.changes)-1]
        self.changes += [row('RELEASE', [charge(*key, g.MAXIMUM)]) for key in g.TEMPORARIES]
        self.positions += [len(self.changes)-1]*2
        end = {**g.FIXED, **final, ('SOURCE', 'old'): len(b'packet'),
               ('APPLICATION', 'old:application.image'): len(b'old-image')}
        self.changes += [row('RELEASE', [charge(*key, size)]) for key, size in end.items()]

    def build(self):
        state = {}; rows = copy.deepcopy(self.changes)
        for value in rows:
            for old in value['removed']:
                self.assertEqual(old, state.pop(g.t.key(old)))
            for new in value['added']:
                self.assertNotIn(g.t.key(new), state); state[g.t.key(new)] = new
            for field in ('removed', 'added'): value[field].sort(key=g.t.order_key)
            value['usage'] = g.t.usage(state, (384*g.t.MIB, 512*g.t.MIB, 64*g.t.MIB))
        value = trace(rows); g.t.replay(value)
        boundaries = [dict(eventIndex=i, node='node-1', sequence=seq,
                           usage=copy.deepcopy(value['changes'][seq]['usage'])) for i, seq in enumerate(self.positions)]
        return value, boundaries

    def check(self):
        value, boundaries = self.build()
        return g.replay([self.rows], {'node-1': value}, boundaries)

    def rename(self, key, replacement):
        for change in self.changes:
            for value in change['removed']+change['added']:
                if g.t.key(value) == key: value.update(unit=replacement[0], owner=replacement[1])

    def insert(self, at, changes):
        self.changes[at:at] = changes
        self.positions = [seq+len(changes) if seq >= at else seq for seq in self.positions]

    def test_complete_publication_keeps_original_and_new_generation_charges(self):
        result = self.check()
        self.assertEqual((1, 11), (result['publications'], result['physicalBoundaries']))
        self.assertGreater(result['mutationStates'], 1)
        self.assertTrue(result['generationIdentitiesDerived']); self.assertTrue(result['completionTransferDerived'])
        for flag in ('wholeRuntimePhysicalCustodyQualified', 'physicalPeakQualified', 'finalSourceCohortQualified', 'phase3Complete'):
            self.assertFalse(result[flag])

    def test_equal_image_bytes_do_not_merge_distinct_slot_owners(self):
        files = copy.deepcopy(self.fixture.after)
        files['generations/b/application.image'] = files['generations/a/application.image']
        values = g.extents(files)
        self.assertEqual(values['APPLICATION', 'generation-a:application.image'], values[self.image])
        self.assertIn(('GENERATION', 'a'), values); self.assertIn(('GENERATION', 'b'), values)

    def test_balanced_wrong_old_slot_or_image_owner_is_rejected(self):
        for key in (('GENERATION', 'a'), ('APPLICATION', 'generation-a:application.image')):
            with self.subTest(key=key):
                original = copy.deepcopy(self.changes)
                self.rename(key, (key[0], 'wrong-owner'))
                with self.assertRaisesRegex(ValueError, 'exact owner extents'): self.check()
                self.changes = original

    def test_balanced_wrong_new_slot_or_image_owner_is_rejected(self):
        for key in (self.generation, self.image):
            with self.subTest(key=key):
                original = copy.deepcopy(self.changes)
                self.rename(key, (key[0], 'wrong-owner'))
                with self.assertRaisesRegex(ValueError, 'unexpected custody transition'): self.check()
                self.changes = original

    def test_fixed_authority_journal_and_completion_owners_are_exact(self):
        for key in (*g.FIXED, g.COMPLETION, *g.TEMPORARIES):
            with self.subTest(key=key):
                original = copy.deepcopy(self.changes); self.rename(key, (key[0], 'substitute'))
                with self.assertRaisesRegex(ValueError, 'exact owner extents'): self.check()
                self.changes = original

    def test_balanced_metadata_shift_between_generations_is_not_accepted(self):
        # Change sizes only after both generations exist; change initial old size
        # too, then preserve every recorded aggregate by a matching source shift.
        original = copy.deepcopy(self.changes)
        for change in self.changes:
            for value in change['removed']+change['added']:
                if g.t.key(value) == ('GENERATION', 'a'): value['bytes'] += 1
                if g.t.key(value) == ('SOURCE', 'old'): value['bytes'] -= 1
                if g.t.key(value) == ('APPLICATION', 'old:application.image'): value['bytes'] += 1
        with self.assertRaisesRegex(ValueError, 'exact owner extents'): self.check()
        self.changes = original

    def test_release_and_reacquire_between_callbacks_cannot_hide_gap(self):
        old = charge('GENERATION', 'a', len(b'manifest'))
        self.insert(self.positions[8], [row('RELEASE', [old]), row('RESERVE', added=[old])])
        # No publication callback sees the temporary disappearance; accounting
        # and all physical boundary totals still pass.
        with self.assertRaisesRegex(ValueError, 'unexpected custody transition'): self.check()

    def test_completion_transfer_cannot_be_replaced_with_release_and_reserve(self):
        at = self.positions[1]
        self.changes[at] = row('EXTEND_COMMIT')
        self.insert(at, [row('RELEASE', [charge(*g.COMPLETION, g.MAXIMUM)]),
                         row('RESERVE', added=[charge(*self.image, g.MAXIMUM)])])
        with self.assertRaisesRegex(ValueError, 'unexpected custody transition'): self.check()

    def test_early_reload_cannot_shrink_before_current_force_boundary(self):
        # Point 7 observes the actual smaller size; alter its capture total to
        # match as well. Independent derived publication charges must reject it.
        self.positions[7] = self.positions[8]
        value, boundaries = self.build(); self.rows[7]['storage'] = g.p.usage(boundaries[7]['usage'])
        with self.assertRaisesRegex(ValueError, 'admitted publication inventory'):
            g.replay([self.rows], {'node-1': value}, boundaries)

    def test_maximum_actual_image_still_requires_one_reload_boundary(self):
        # Exercise the no-delta atomic reload without allocating a 64 MiB test
        # image. The independently admitted plan supplies its exact extent.
        value, boundaries = self.build(); plan = g.plans([self.rows], boundaries)[0]
        plan['final'][self.image] = g.MAXIMUM
        for change in self.changes:
            for item in change['removed']+change['added']:
                if g.t.key(item) == self.image: item['bytes'] = g.MAXIMUM
            if change['event'] == 'GENERATION_RELOAD': change['removed'] = []; change['added'] = []
        value, _ = self.build(); state = {}
        for change in value['changes'][:self.positions[0]+1]:
            for item in change['added']: state[g.t.key(item)] = item
        self.assertGreater(g.bind(plan, value['changes'], state), 0)
        value['changes'][self.positions[8]]['event'] = 'CONTROL_GROW'
        with self.assertRaisesRegex(ValueError, 'completed boundary handoff'):
            g.bind(plan, value['changes'], state)

    def test_unrelated_control_activity_does_not_change_storage_custody(self):
        control = charge('CONTROL', 'other', 17)
        self.insert(self.positions[8], [row('RESERVE', added=[control]), row('RELEASE', [control])])
        self.assertEqual('PASS', self.check()['status'])

    def test_missing_duplicate_swapped_and_wrong_node_boundaries_are_rejected(self):
        value, boundaries = self.build()
        for mode in ('missing', 'duplicate', 'swap', 'owner', 'boolean', 'range'):
            rows = copy.deepcopy(self.rows); points = copy.deepcopy(boundaries)
            if mode == 'missing': rows.pop()
            elif mode == 'duplicate': rows[2]['eventIndex'] = rows[1]['eventIndex']
            elif mode == 'swap': rows[1], rows[2] = rows[2], rows[1]
            elif mode == 'owner': points[3]['node'] = 'node-2'
            elif mode == 'boolean': points[3]['sequence'] = True
            else: points[-1]['sequence'] = len(value['changes'])
            with self.subTest(mode=mode), self.assertRaises(ValueError): g.replay([rows], {'node-1': value}, points)

    def test_extra_overlapping_publication_and_missing_owner_are_rejected(self):
        value, boundaries = self.build()
        with self.assertRaisesRegex(ValueError, 'original boundary'): g.replay([self.rows, self.rows], {'node-1': value}, boundaries)
        with self.assertRaisesRegex(ValueError, 'missing original owner'): g.replay([self.rows], {}, boundaries)
        with self.assertRaisesRegex(ValueError, 'missing publications'): g.replay([], {'node-1': value}, boundaries)

    def test_incomplete_journal_cannot_be_accepted_by_storage_boundaries(self):
        value, boundaries = self.build(); value['truncated'] = True
        with self.assertRaisesRegex(ValueError, 'incomplete observation'): g.replay([self.rows], {'node-1': value}, boundaries)

    def test_full_composition_still_requires_independent_original_first(self):
        from . import native_resource_evidence as native
        with patch.object(native.collection, 'inventory', return_value={}), \
             patch.object(native.publication, 'validate', side_effect=ValueError('invalid original')), \
             patch.object(g, 'replay') as replay:
            with self.assertRaisesRegex(ValueError, 'invalid original'): native.validate('/unused')
        replay.assert_not_called()

    def test_all_balanced_mutations_reject_the_exact_physical_binding_reason(self):
        from . import publication_generation_negatives as negatives
        value, boundaries = self.build(); original = copy.deepcopy((self.rows, value, boundaries))
        result = negatives.qualify([self.rows], {'node-1': value}, boundaries)
        self.assertEqual(10, len(result['negatives']))
        self.assertEqual(original, (self.rows, value, boundaries))
        self.assertFalse(result['phase3Complete'])

    def test_bad_original_never_counts_as_successful_negative_qualification(self):
        from . import publication_generation_negatives as negatives
        value, boundaries = self.build(); value['truncated'] = True
        with patch.object(negatives, 'mutate') as mutate:
            with self.assertRaisesRegex(ValueError, 'incomplete observation'):
                negatives.qualify([self.rows], {'node-1': value}, boundaries)
        mutate.assert_not_called()


if __name__ == '__main__': unittest.main()
