import unittest
from pathlib import PurePosixPath
from unittest.mock import patch
from . import learner_typed_evidence as evidence


class LearnerTypedEvidenceTest(unittest.TestCase):
    def test_original_and_reopen_require_semantics_before_receipt_force(self):
        for resume in (False,True):
            rows=evidence.trace(resume);evidence.check_trace(rows,resume)
            self.assertLess(rows.index('LEARNER_TYPED_BACKUP_FORCED'),rows.index('LEARNER_TYPED_SEMANTICS_VERIFIED'))
            self.assertLess(rows.index('LEARNER_TYPED_SEMANTICS_VERIFIED'),rows.index('LEARNER_TYPED_RECEIPT_FORCED'))
            for point in ('LEARNER_TYPED_SEMANTICS_VERIFIED','LEARNER_TYPED_RECEIPT_FORCED','LEARNER_TYPED_RECEIPT_PARENT_FORCED'):
                changed=rows.copy();changed.remove(point)
                with self.assertRaisesRegex(ValueError,'exact force order'):evidence.check_trace(changed,resume)

    def test_early_receipt_and_duplicate_events_do_not_pass(self):
        rows=evidence.trace(False)
        changed=rows.copy();changed.remove('LEARNER_TYPED_RECEIPT_CREATED');changed.insert(0,'LEARNER_TYPED_RECEIPT_CREATED')
        with self.assertRaisesRegex(ValueError,'exact force order'):evidence.check_trace(changed,False)
        with self.assertRaisesRegex(ValueError,'exact force order'):evidence.check_trace(rows+rows,False)

    def test_wrong_trace_mode_and_nonstring_events_fail(self):
        with self.assertRaisesRegex(ValueError,'exact force order'):evidence.check_trace(evidence.trace(False),True)
        with self.assertRaisesRegex(ValueError,'force events'):evidence.check_trace([None],False)

    def test_recorded_path_is_checked_without_opening_it(self):
        bound=dict(path='/absent/parent/child',parentRealPath='/absent/parent',fileStoreName='disk',fileStoreType='ext4',parentFileKey='(dev=1,ino=2)')
        self.assertEqual(PurePosixPath(bound['path']),evidence.binding(bound))
        for change in (dict(path='/absent/parent/../child'),dict(parentRealPath='/other'),dict(path='relative'),dict(parentFileKey='')):
            with self.assertRaises(ValueError):evidence.binding(dict(bound,**change))

    def test_invalid_original_cannot_count_as_successful_negatives(self):
        with patch.object(evidence,'validate',side_effect=ValueError('original failed')) as validate, \
             patch.object(evidence.tempfile,'TemporaryDirectory') as temporary:
            with self.assertRaisesRegex(ValueError,'original failed'):evidence.qualify('/absent/evidence')
            validate.assert_called_once();temporary.assert_not_called()


if __name__=='__main__':unittest.main()
