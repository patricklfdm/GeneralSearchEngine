import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import retained_provenance_evidence as r


class RetainedProvenanceEvidenceTest(unittest.TestCase):
    def test_invalid_original_is_not_negative_qualification(self):
        with patch.object(r,'validate',side_effect=ValueError('invalid original')) as check,patch.object(r.p.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'invalid original'):r.qualify('absent')
            check.assert_called_once_with('absent');copy.assert_not_called()

    def test_different_copy_scope_is_not_the_previous_packet_download_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('stable-3','stable-4','stable-5'):(root/name).mkdir()
            (root/'receipt.json').write_text('{}')
            with patch.object(r.p,'case',side_effect=lambda p,n:dict(size=n,exchanges=7)):
                with self.assertRaisesRegex(ValueError,'scope/receipt'):r.validate(root)

    def test_unrelated_negative_failure_is_not_accepted(self):
        with patch.object(r,'validate',side_effect=[{},ValueError('unrelated')]) as check,patch.object(r.p.shutil,'copytree'),patch.object(r.p,'load',return_value={}),patch.object(Path,'write_text',return_value=1):
            with self.assertRaisesRegex(ValueError,'unrelated negative: scope: unrelated'):r.qualify('absent')
            self.assertEqual(2,check.call_count)
