from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import learner_source_evidence as e


class LearnerSourceEvidenceTest(unittest.TestCase):
    def test_invalid_original_is_not_counted_as_negative_success(self):
        with patch.object(e,'validate',side_effect=ValueError('invalid original')),patch.object(e.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):e.qualify('/absent')
        copied.assert_not_called()

    def test_unexpected_inventory_precedes_physical_or_network_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'unexpected').write_bytes(b'bad')
            with patch.object(e.r,'physical') as physical,patch.object(e,'network') as network:
                with self.assertRaisesRegex(ValueError,'^context selection learner source inventory$'):e.validate(root)
            physical.assert_not_called();network.assert_not_called()

    def test_linked_evidence_is_rejected_before_content_is_read(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'external').symlink_to('/unrelated-evidence')
            with patch.object(e.r,'physical') as physical:
                with self.assertRaisesRegex(ValueError,'^learner source regular evidence$'):e.validate(root)
            physical.assert_not_called()

    def test_failed_physical_reduction_cannot_be_overridden_by_network_claims(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(e.b.selection,'layout'),patch.object(e.r,'physical',side_effect=ValueError('wrong original bytes')),patch.object(e,'network') as network:
                with self.assertRaisesRegex(ValueError,'^wrong original bytes$'):e.validate(Path(temp))
            network.assert_not_called()

    def test_success_claim_cannot_enable_public_readiness(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'learner-source-result.json').write_bytes(e.f.canonical(dict(status='PASS',scope='native-reservation-complete-source',
                voter=False,materialized=False,publicReady=True,phase3Complete=False)))
            with patch.object(e.b.selection,'layout'),patch.object(e.r,'physical',return_value=({}, {}, {})),patch.object(e,'network',return_value={}):
                with self.assertRaisesRegex(ValueError,'^learner source result scope$'):e.validate(root)


if __name__=='__main__':unittest.main()
