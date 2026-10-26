import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import transfer_service_evidence as e


class TransferServiceEvidenceTest(unittest.TestCase):
    def test_invalid_original_is_never_a_successful_negative(self):
        with patch.object(e,'validate',side_effect=ValueError('original invalid')) as validate,patch.object(e.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'original invalid'):e.qualify('absent')
            validate.assert_called_once_with('absent');copy.assert_not_called()

    def test_missing_linked_and_incomplete_inputs_reject(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);raw=p/'raw';raw.mkdir();link=p/'link';link.symlink_to(raw,target_is_directory=True)
            for path in (p/'absent',raw,link):
                with self.subTest(path=path),self.assertRaises(ValueError):e.validate(path)

    def test_unrelated_rejection_is_a_failure(self):
        with patch.object(e,'validate',side_effect=[{},ValueError('unrelated')]),patch.object(e.shutil,'copytree'),patch.object(e,'load',return_value={}),patch.object(Path,'write_text',return_value=1):
            with self.assertRaisesRegex(ValueError,'transfer service unrelated negative: scope: unrelated'):e.qualify('absent')
