from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import learner_store_review_evidence as s


class LearnerStoreReviewEvidenceTest(unittest.TestCase):
    def test_exact_bounded_replica_refusal_cannot_be_replaced_by_another_error(self):
        value=dict(status='REFUSED',type='IllegalArgumentException',reason='basis source inventory capacity')
        s.refusal(value,'replica')
        for field,other in (('status','PASS'),('type','IOException'),('reason','learner replica unexpected files')):
            with self.assertRaisesRegex(ValueError,'^learner store review exact refusal$'):
                s.refusal(dict(value,**{field:other}),'replica')

    def test_unmodified_evidence_must_pass_before_any_negative(self):
        with patch.object(s,'validate',side_effect=ValueError('invalid original')),patch.object(s.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):s.qualify('/missing')
        copy.assert_not_called()

    def test_missing_native_history_does_not_degrade_into_metadata_only_acceptance(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(s.source,'validate') as original:
            with self.assertRaisesRegex(ValueError,'^learner store review inventory$'):s.validate(temp)
        original.assert_not_called()

    def test_linked_evidence_is_rejected_before_native_replay(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(s.source,'validate') as original:
            (Path(temp)/'source-history').symlink_to('/missing')
            with self.assertRaisesRegex(ValueError,'^learner store review regular evidence$'):s.validate(temp)
        original.assert_not_called()


if __name__=='__main__':unittest.main()
