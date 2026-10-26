import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import checkpoint_pull_evidence as e


class CheckpointPullEvidenceTest(unittest.TestCase):
    def test_original_precedes_all_mutations(self):
        with patch.object(e,'validate',side_effect=ValueError('invalid original')) as validate,patch.object(e.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'invalid original'):e.qualify('absent')
            validate.assert_called_once_with('absent');copy.assert_not_called()

    def test_missing_linked_or_incomplete_inputs_reject(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);raw=root/'raw';raw.mkdir();link=root/'link';link.symlink_to(raw,target_is_directory=True)
            for path in (root/'absent',raw,link):
                with self.subTest(path=path),self.assertRaises(ValueError):e.validate(path)

    def test_unrelated_negative_does_not_count(self):
        with patch.object(e,'validate',side_effect=[{},ValueError('unrelated')]),patch.object(e.shutil,'copytree'),patch.object(e,'load',return_value={}),patch.object(Path,'write_text',return_value=1):
            with self.assertRaisesRegex(ValueError,'checkpoint unrelated negative: scope: unrelated'):e.qualify('absent')
