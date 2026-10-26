import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import owned_generation_evidence as r


class OwnedGenerationEvidenceTest(unittest.TestCase):
    def test_original_failure_cannot_count_as_negative_qualification(self):
        with patch.object(r,'validate',side_effect=ValueError('invalid original')) as check,patch.object(r.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'invalid original'):r.qualify('absent')
            check.assert_called_once_with('absent');copy.assert_not_called()

    def test_receipt_cannot_promote_reader_to_public_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('stable-3','stable-4','stable-5'):(root/name).mkdir()
            (root/'receipt.json').write_text('{}')
            with patch.object(r,'case',side_effect=lambda p,n:dict(size=n,freshReaders=n)):
                with self.assertRaisesRegex(ValueError,'scope/receipt'):r.validate(root)

    def test_unrelated_failure_is_not_successful_rejection(self):
        with patch.object(r,'validate',side_effect=[{},ValueError('unrelated')]),patch.object(r.shutil,'copytree'),patch.object(r,'load',return_value={}),patch.object(Path,'write_text',return_value=1):
            with self.assertRaisesRegex(ValueError,'unrelated negative: scope: unrelated'):r.qualify('absent')
