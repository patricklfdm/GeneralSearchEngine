import unittest
from unittest.mock import patch
from . import learner_prepared_evidence as e


class LearnerPreparedEvidenceTest(unittest.TestCase):
    def rows(self):
        return e.t.trace(False)+['LEARNER_PREPARED'+v for v in ('_CREATED','_PREFIX_WRITTEN','_WRITTEN','_FORCED',
                                '_PARENT_FORCED','_BEFORE_SELECT','_BEFORE_RETURN')]

    def test_selection_requires_complete_ordered_file_and_directory_forces(self):
        rows=self.rows();e.check_trace(rows)
        for event in rows:
            changed=rows.copy();changed.remove(event)
            with self.assertRaisesRegex(ValueError,'force order'):e.check_trace(changed)

    def test_selection_cannot_precede_semantic_receipt_or_parent_force(self):
        for before in ('LEARNER_TYPED_SEMANTICS_VERIFIED','LEARNER_PREPARED_PARENT_FORCED'):
            rows=self.rows();rows.remove('LEARNER_PREPARED_BEFORE_SELECT')
            rows.insert(rows.index(before),'LEARNER_PREPARED_BEFORE_SELECT')
            with self.assertRaisesRegex(ValueError,'selection force order'):e.check_trace(rows)

    def test_duplicate_selection_cannot_be_hidden_in_trace(self):
        with self.assertRaisesRegex(ValueError,'selection force order'):e.check_trace(self.rows()+['LEARNER_PREPARED_FORCED'])

    def test_invalid_original_cannot_count_as_successful_rejections(self):
        with patch.object(e,'validate',side_effect=ValueError('original failed')) as validate, \
                patch.object(e.tempfile,'TemporaryDirectory') as temporary:
            with self.assertRaisesRegex(ValueError,'original failed'):e.qualify('/absent/evidence')
            validate.assert_called_once();temporary.assert_not_called()


if __name__=='__main__':unittest.main()
