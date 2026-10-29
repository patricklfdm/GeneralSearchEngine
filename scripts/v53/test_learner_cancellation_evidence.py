"""Reader control-flow regressions; these do not claim native qualification."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import learner_cancellation_evidence as e


class LearnerCancellationEvidenceTest(unittest.TestCase):
    def test_invalid_original_never_counts_as_negative_qualification(self):
        with patch.object(e,'validate',side_effect=ValueError('original failed')),patch.object(e.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^original failed$'):e.qualify('/absent')
            copied.assert_not_called()

    def test_extra_or_linked_evidence_fails_before_authority_reduction(self):
        for link in (False,True):
            with self.subTest(link=link),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);path=root/'foreign'
                if link:path.symlink_to('/original-path-must-not-open')
                else:path.write_bytes(b'bad')
                with patch.object(e.t,'physical_history') as physical:
                    with self.assertRaises(ValueError):e.validate(root)
                    physical.assert_not_called()

    def test_voter_failure_prevents_learner_or_network_claims(self):
        with patch.object(e,'inventory'),patch.object(e.t,'physical_history',side_effect=ValueError('unproven CANCEL')), \
             patch.object(e,'snapshots') as snapshots,patch.object(e.t.source,'network_rows') as network:
            with self.assertRaisesRegex(ValueError,'^unproven CANCEL$'):e.validate('/absent')
            snapshots.assert_not_called();network.assert_not_called()

    def test_missing_or_unrelated_negative_does_not_count_as_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            for failure in (None,ValueError('unrelated')):
                with self.subTest(failure=failure),patch.object(e,'NEGATIVES',{'extra-file':'expected rejection'}), \
                     patch.object(e,'validate',side_effect=[{},failure]):
                    with self.assertRaisesRegex(ValueError,'learner cancellation (accepted|unrelated) negative'):e.qualify(temp)


if __name__=='__main__':unittest.main()
