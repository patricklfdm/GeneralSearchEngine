import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import activation_evidence as a


class ActivationEvidenceTest(unittest.TestCase):
    def test_invalid_original_never_counts_as_a_negative(self):
        with patch.object(a,'validate',side_effect=ValueError('original invalid')) as validate,patch.object(a.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'original invalid'):a.qualify('absent')
            validate.assert_called_once_with('absent');copy.assert_not_called()

    def test_missing_linked_and_incomplete_evidence_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);real=p/'raw';real.mkdir();link=p/'link';link.symlink_to(real,target_is_directory=True)
            for value in (p/'absent',real,link):
                with self.subTest(path=value),self.assertRaises(ValueError):a.validate(value)

    def test_unrelated_mutation_failure_is_not_a_success(self):
        with patch.object(a,'validate',side_effect=[{},ValueError('unrelated')]) as validate,patch.object(a.shutil,'copytree'),patch.object(a,'load',return_value={}),patch.object(Path,'write_text',return_value=1):
            with self.assertRaisesRegex(ValueError,'activation unrelated negative: scope: unrelated'):a.qualify('absent')
            self.assertEqual(2,validate.call_count)
