import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import scratch_recovery_evidence as e


class ScratchRecoveryEvidenceTest(unittest.TestCase):
    def test_invalid_original_does_not_count_as_mutation_rejections(self):
        with patch.object(e,'validate',side_effect=ValueError('bad original')) as validate,patch.object(e.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'bad original'):e.qualify('absent')
            validate.assert_called_once_with('absent');copy.assert_not_called()

    def test_incomplete_or_linked_original_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);raw=root/'raw';raw.mkdir();link=root/'link';link.symlink_to(raw,target_is_directory=True)
            for path in (root/'absent',raw,link):
                with self.subTest(path=path),self.assertRaises(ValueError):e.validate(path)

    def test_unrelated_error_cannot_count_as_a_negative(self):
        with patch.object(e,'validate',side_effect=[{},ValueError('unrelated')]),patch.object(e.shutil,'copytree'),patch.object(e,'load',return_value={}),patch.object(Path,'write_text',return_value=0):
            with self.assertRaisesRegex(ValueError,'scratch unrelated negative: scope: unrelated'):e.qualify('absent')
