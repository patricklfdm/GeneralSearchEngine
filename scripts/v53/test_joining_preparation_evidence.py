"""Independent preparation comparison and deletion-order boundaries."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch
from . import joining_preparation_evidence as p
from .test_joining_initialization_evidence import preparing


class JoiningPreparationEvidenceTest(unittest.TestCase):
    def inputs(self):
        v, files, _, observed, _ = preparing(); files['grants.gsr'] = observed
        basis = p.f.decode(v.sources()[0][0], 'records', 'BASIS'); key = 'node-1', p.f.canonical(basis['ballot'])
        capture = object.__new__(p.Captures); capture.used = set(); capture.derived = {}; capture.comparisons = 0
        capture.by_ballot = {key:{}}; capture.root = Path('/unused')
        return capture, files, basis, key

    def test_complete_derived_inventory_matches_once_without_using_copy_as_expected(self):
        capture, files, _, _ = self.inputs(); before = copy.deepcopy(files)
        with patch.object(capture, 'original', return_value=copy.deepcopy(files)):
            capture.match('node-1', files); capture.complete()
            with self.assertRaisesRegex(ValueError, 'duplicate derivation'): capture.match('node-1', files)
        self.assertEqual(before, files); self.assertEqual(1, capture.comparisons)

    def test_checksum_valid_extra_or_changed_file_is_not_derived(self):
        for action in ('extra', 'allocator', 'omitted'):
            capture, files, _, _ = self.inputs(); actual = copy.deepcopy(files)
            if action == 'extra': actual['extra.gsr'] = b'unowned'
            elif action == 'omitted': actual.pop(p.c.PEERS)
            else:
                row = p.f.decode(actual['allocator.gsr'], 'records', 'ALLOCATOR'); row['counter'] += 1
                actual['allocator.gsr'] = p.f.encode('records', 'ALLOCATOR', row)
            with self.subTest(action=action), patch.object(capture, 'original', return_value=actual), \
                    self.assertRaisesRegex(ValueError, 'exact captured inventory'):
                capture.match('node-1', files)
            self.assertFalse(capture.used)

    def test_missing_or_underived_grant_cannot_be_ignored(self):
        capture, _, basis, _ = self.inputs()
        with self.assertRaisesRegex(ValueError, 'underived captured grant'): capture.complete()
        with self.assertRaisesRegex(ValueError, 'original capture missing'): capture.original('node-2', basis['ballot'])

    def test_capture_prefix_is_a_complete_grant_not_a_selected_suffix(self):
        capture, files, _, _ = self.inputs(); files['grants.gsr'] = p.f.encode('records', 'PROMISE',
            {k:p.f.decode(preparing()[2][0], 'records', 'BASIS')[k] for k in ('root','view','ballot','basisId')})
        with self.assertRaisesRegex(ValueError, 'derived complete grant'):capture.match('node-1', files)

    def retirement(self, count=2):
        return ['SOURCE_RETIREMENT_'+v for v in ('CREATED','WRITTEN','FORCED','PARENT_FORCED')]+\
            ['JOURNAL_ROTATION_'+v for v in ('CREATED','WRITTEN','FORCED','RENAMED','PARENT_FORCED')]+\
            ['SOURCE_RETIREMENT_JOURNAL_PRUNED']+['SOURCE_RETIREMENT_FILE_DELETED']*count+\
            ['SOURCE_RETIREMENT_'+v for v in ('DIRECTORY_DELETED','CLEARED','BEFORE_RETURN')]

    def test_source_removal_counts_only_original_files_and_preserves_other_sources(self):
        before = {'sources/a':None,'sources/a/source.gscp':b'p','sources/a/x.image':b'i',
                  'sources/b':None,'sources/b/source.gscp':b'q','other':b'z'}
        after = {k:v for k,v in before.items() if not k.startswith('sources/a')}
        self.assertEqual([2], p.source_deletions(before, after)); self.assertEqual([],p.source_deletions(before,before))
        p.retirement_order(['UNRELATED',*self.retirement(), 'UNRELATED'], [2]); p.retirement_order([],[])
        p.retirement_order(self.retirement(3)+self.retirement(2),[2,3])

    def test_missing_force_early_delete_extra_retirement_or_wrong_extent_refuse(self):
        original = self.retirement()
        for changed in ([v for v in original if v != 'SOURCE_RETIREMENT_FORCED'],
                        [original[10],*original[:10],*original[11:]], original[:-1]):
            with self.assertRaisesRegex(ValueError, 'source retirement order'):p.retirement_order(changed,[2])
        for rows,counts in [(original,[]),(original,[3]),([],[2]),(original+original,[2])]:
            with self.assertRaisesRegex(ValueError, 'source retirement count'):p.retirement_order(rows,counts)

    def test_invalid_original_never_becomes_negative_evidence(self):
        with patch.object(p,'validate',side_effect=ValueError('invalid original')),patch.object(p,'mutate') as mutation:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):p.qualify('/unused')
            mutation.assert_not_called()

    def test_collection_or_initialization_failure_cannot_count_as_new_rejection(self):
        for gate in ('collection','initialization'):
            with patch.object(p,'validate',return_value={}) as replay,patch.object(p.shutil,'copytree'),patch.object(p,'mutate'), \
                    patch.object(p.s.collection,'read_json',return_value=[]), \
                    patch.object(p.captures,'validate',side_effect=ValueError('prior collection') if gate=='collection' else None), \
                    patch.object(p.init,'validate',side_effect=ValueError('prior initialization')):
                with self.assertRaisesRegex(ValueError,'^prior '+gate+'$'):p.qualify('/unused')
                self.assertEqual(1,replay.call_count)

    def test_accepted_mutation_or_unrelated_rejection_is_not_a_pass(self):
        for effect,reason in [([{},{}],'mutation accepted'),([{},ValueError('unrelated')],'unrelated joining preparation negative')]:
            with patch.object(p,'validate',side_effect=effect),patch.object(p.shutil,'copytree'),patch.object(p,'mutate'), \
                    patch.object(p.s.collection,'read_json',return_value=[]),patch.object(p.captures,'validate'), \
                    patch.object(p.init,'validate'),self.assertRaisesRegex(ValueError,reason):p.qualify('/unused')


if __name__ == '__main__':unittest.main()
