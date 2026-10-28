import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import successor_typed_evidence as e


class SuccessorTypedEvidenceTest(unittest.TestCase):
    def test_receipt_requires_semantics_and_both_forces_on_each_open(self):
        for resume in (False,True):
            original=e.t.trace(resume);e.check_trace(original,resume)
            for event in ('SEMANTICS_VERIFIED','RECEIPT_FORCED','RECEIPT_PARENT_FORCED'):
                rows=original.copy();rows.remove('LEARNER_TYPED_'+event)
                with self.assertRaisesRegex(ValueError,'exact force order'):e.check_trace(rows,resume)
            rows=original.copy();rows.remove('LEARNER_TYPED_RECEIPT_FORCED');rows.insert(rows.index('LEARNER_TYPED_SEMANTICS_VERIFIED'),'LEARNER_TYPED_RECEIPT_FORCED')
            with self.assertRaisesRegex(ValueError,'exact force order'):e.check_trace(rows,resume)

    def test_incomplete_extension_is_not_silently_projected_away(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'successor-typed').mkdir()
            with patch.object(e.installed,'validate') as original:
                with self.assertRaisesRegex(ValueError,'extension incomplete'):e.validate(root)
                original.assert_not_called()

    def test_linked_extension_is_refused_before_copying(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'successor-typed').symlink_to('/tmp',target_is_directory=True)
            with patch.object(e.installed,'validate') as original:
                with self.assertRaisesRegex(ValueError,'regular evidence'):e.validate(root)
                original.assert_not_called()

    def test_invalid_original_cannot_count_as_rejected_mutations(self):
        with patch.object(e,'validate',side_effect=ValueError('invalid original')) as validate,patch.object(e.tempfile,'TemporaryDirectory') as temporary:
            with self.assertRaisesRegex(ValueError,'invalid original'):e.qualify('/absent')
            validate.assert_called_once();temporary.assert_not_called()


if __name__=='__main__':unittest.main()
