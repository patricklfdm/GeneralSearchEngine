from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import learner_store_evidence as s


class LearnerStoreEvidenceTest(unittest.TestCase):
    def test_partial_execution_can_never_report_complete_matrix(self):
        with patch.object(s,'_validate_cases',return_value={'status':'PASS','processCases':1}) as verify:
            result=s.validate_case('raw','LEARNER_RETENTION_RENAMED-halt')
        verify.assert_called_once_with('raw',('LEARNER_RETENTION_RENAMED-halt',))
        self.assertEqual('PARTIAL',result['status']);self.assertIs(False,result['completeProcessMatrix'])

    def test_unknown_empty_or_duplicate_case_selection_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            for selected in ((),('unknown',),('LEARNER_RETENTION_RENAMED-halt',)*2):
                with self.assertRaisesRegex(ValueError,'^learner store declared cases$'):s._validate_cases(temp,selected)

    def test_invalid_original_cannot_count_as_rejected_mutations(self):
        with patch.object(s,'validate',side_effect=ValueError('bad original')),patch.object(s.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'^bad original$'):s.qualify('/missing')
        copy.assert_not_called()

    def test_complete_case_inventory_is_required_before_source_replay(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(s.source,'validate') as original:
            with self.assertRaisesRegex(ValueError,'^learner store complete case inventory$'):s.validate(temp)
        original.assert_not_called()

    def test_symlinks_are_rejected_before_any_original_replay(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(s.source,'validate') as original:
            (Path(temp)/'foreign').symlink_to('/missing')
            with self.assertRaisesRegex(ValueError,'^learner store regular evidence$'):s.validate(temp)
        original.assert_not_called()

    def test_native_cache_is_invalidated_by_every_source_byte_and_filename(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(s.source,'validate',return_value={'status':'PASS'}) as original:
            root=Path(temp);member=root/'a';member.write_bytes(b'first');cache={}
            s.native(root,cache);s.native(root,cache);self.assertEqual(1,original.call_count)
            member.write_bytes(b'changed');s.native(root,cache);self.assertEqual(2,original.call_count)
            member.rename(root/'b');s.native(root,cache);self.assertEqual(3,original.call_count)
            (root/'directory').mkdir();s.native(root,cache);self.assertEqual(4,original.call_count)

    def test_failed_native_validation_is_never_cached(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(s.source,'validate',side_effect=ValueError('changed original')) as original:
            cache={}
            for _ in range(2):
                with self.assertRaisesRegex(ValueError,'^changed original$'):s.native(Path(temp),cache)
            self.assertEqual(2,original.call_count);self.assertEqual({},cache)

    def test_resume_trace_reforces_existing_metadata_but_never_repeats_the_move(self):
        expected={'root.gsr':b'root','node.gsr':b'node',s.ADMISSION:b'admission'}
        trace=s.resume_trace(expected,'retained',False,expected)
        self.assertNotIn('LEARNER_SOURCE_MOVED',trace);self.assertNotIn('LEARNER_ROOT_WRITTEN',trace)
        for prefix in ('ROOT','NODE','ADMISSION'):
            self.assertIn('LEARNER_'+prefix+'_FORCED',trace);self.assertIn('LEARNER_'+prefix+'_PARENT_FORCED',trace)
        self.assertEqual('LEARNER_STORE_BEFORE_RETURN',trace[-1])


if __name__=='__main__':unittest.main()
