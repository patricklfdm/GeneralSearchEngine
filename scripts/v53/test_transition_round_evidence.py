import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import transition_round_evidence as e


class TransitionRoundEvidenceTest(unittest.TestCase):
    def test_invalid_original_is_never_counted_as_negative_success(self):
        with patch.object(e,'validate',side_effect=ValueError('invalid original')),patch.object(e.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):e.qualify(Path('/original'))
        copied.assert_not_called()

    def test_physical_original_precedes_lifecycle_and_negative_mutations(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'transition-round-result.json').write_text(json.dumps(e.RESULT))
            with patch.object(e.continuous,'history',side_effect=ValueError('bad original image')) as history,patch.object(e,'lifecycle') as lifecycle:
                with self.assertRaisesRegex(ValueError,'^bad original image$'):e.validate(root)
            history.assert_called_once_with(root,'transition-round-result.json');lifecycle.assert_not_called()

    def test_local_transition_cannot_claim_other_profiles_or_public_service(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for change in ({'publicReady':True},{'activations':2},{'kind':'ADD'},{'phase3Complete':True},{'originalBudgetSeconds':180}):
                (root/'transition-round-result.json').write_text(json.dumps(dict(e.RESULT,**change)))
                with self.assertRaisesRegex(ValueError,'^transition round scope$'):e.validate(root)

    def test_missing_joint_activation_or_early_readiness_is_rejected(self):
        names=['INSTALLED','SLOT_BEGIN','SLOT_COMPLETE']*3+['BEFORE_READY']
        missing=names.copy();missing.pop(3)
        early=names.copy();early.insert(3,early.pop())
        for invalid in (missing,early):
            with patch.object(e.d,'read',return_value=[dict(event='ROUND_'+name) for name in invalid]):
                with self.assertRaisesRegex(ValueError,'^transition round exact lifecycle$'):e.lifecycle(Path('/original'))


if __name__=='__main__':unittest.main()
