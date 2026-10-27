import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import round_driver_evidence as e


class RoundDriverEvidenceTest(unittest.TestCase):
    def test_original_failure_cannot_count_as_mutation_rejection(self):
        with patch.object(e, 'validate', side_effect=ValueError('broken original')) as validate, patch.object(e.shutil, 'copytree') as copy:
            with self.assertRaisesRegex(ValueError, '^broken original$'):e.qualify(Path('/unread-original'))
        validate.assert_called_once_with(Path('/unread-original'));copy.assert_not_called()

    def test_projection_rejects_symlinks_before_copying(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'link').symlink_to('/missing')
            with self.assertRaisesRegex(ValueError, '^round original regular inventory$'):e.projection(root)

    def test_internal_readiness_does_not_qualify_public_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=root/'round-result.json'
            value=dict(status='PASS',mode='stable',internalReady=True,publicReady=False);p.write_text(json.dumps(value))
            self.assertEqual(value,e.projection(root))
            for change in ({'publicReady':True},{'internalReady':False},{'mode':'joint'},{'phase3Complete':True}):
                p.write_text(json.dumps(dict(value,**change)))
                with self.assertRaisesRegex(ValueError,'^round result scope$'):e.projection(root)


if __name__=='__main__':unittest.main()
