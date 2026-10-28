from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import learner_plan_evidence as e


class LearnerPlanEvidenceTest(unittest.TestCase):
    def test_failed_original_cannot_count_as_successful_negatives(self):
        with patch.object(e,'validate',side_effect=ValueError('invalid original')),patch.object(e.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):e.qualify('/missing')
        copy.assert_not_called()

    def test_wrong_inventory_rejected_before_reading_source(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(e.source,'validate') as source:
            with self.assertRaisesRegex(ValueError,'^learner plan case inventory$'):e.validate(Path(temp))
        source.assert_not_called()

    def test_links_rejected_before_reading_source(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(e.source,'validate') as source:
            root=Path(temp);(root/'external').symlink_to('/missing')
            with self.assertRaisesRegex(ValueError,'^learner plan regular evidence$'):e.validate(root)
        source.assert_not_called()

    def test_original_source_failure_is_not_overridden_by_plan_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in {p+'-'+m for p in e.CUTS for m in ('halt','kill')}|{'source-history','native-plan'}:(root/name).mkdir()
            (root/'cases.json').write_text('[]')
            with patch.object(e.source,'validate',side_effect=ValueError('source changed')),patch.object(e,'plan') as plan:
                with self.assertRaisesRegex(ValueError,'^source changed$'):e.validate(root)
            plan.assert_not_called()

    def test_plan_only_store_rejects_voter_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'promise.gsr').write_bytes(b'not a learner plan')
            with self.assertRaisesRegex(ValueError,'^learner plan nonvoting inventory$'):e.snapshot(root)


if __name__=='__main__':unittest.main()
