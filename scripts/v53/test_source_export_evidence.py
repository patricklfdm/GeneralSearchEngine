import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import source_export_evidence as e


class SourceExportEvidenceTest(unittest.TestCase):
    def test_invalid_original_never_counts_as_a_negative(self):
        with patch.object(e,'validate',side_effect=ValueError('original invalid')) as validate,patch.object(e.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'original invalid'):e.qualify('absent')
            validate.assert_called_once_with('absent');copy.assert_not_called()

    def test_missing_linked_and_incomplete_evidence_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);real=p/'raw';real.mkdir();link=p/'link';link.symlink_to(real,target_is_directory=True)
            for value in (p/'absent',real,link):
                with self.subTest(path=value),self.assertRaises(ValueError):e.validate(value)

    def test_unrelated_mutation_failure_is_not_a_success(self):
        with patch.object(e,'validate',side_effect=[{},ValueError('unrelated')]) as validate,patch.object(e.shutil,'copytree'),patch.object(e,'load',return_value={}),patch.object(Path,'write_text',return_value=1):
            with self.assertRaisesRegex(ValueError,'source export unrelated negative: scope: unrelated'):e.qualify('absent')
            self.assertEqual(2,validate.call_count)
