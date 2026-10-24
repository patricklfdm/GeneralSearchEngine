"""Process evidence must begin with originals and retain exact trace framing."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import covered_minority_process_evidence as p


class CoveredMinorityProcessEvidenceTest(unittest.TestCase):
    def test_invalid_original_does_not_count_as_negative_success(self):
        with patch.object(p,'validate',side_effect=ValueError('original failed')) as original,patch.object(p.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'original failed'):p.qualify('missing')
            original.assert_called_once();copy.assert_not_called()

    def test_missing_and_linked_roots_do_not_start_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'root';root.mkdir();link=Path(tmp)/'link';link.symlink_to(root,target_is_directory=True)
            for path in (root,link):
                with self.subTest(path=path),patch.object(p,'reference') as reference,self.assertRaisesRegex(ValueError,'inventory'):p.validate(path)
                reference.assert_not_called()

    def test_complete_layout_still_requires_valid_original_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for mode in ('halt','kill'):
                for cut in p.model.CUTS:(root/(mode+'-'+cut)).mkdir()
            (root/'reference').mkdir();(root/'inputs.json').write_text('{}');(root/'receipt.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'covered process reference inventory'):p.validate(root)

    def test_trace_rejects_partial_noncanonical_and_nondictionary_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trace'
            for data in (b'',b'{"event":"x"}',b'{ "event": "x" }\n',b'[]\n',b'{"event":"x"}\n\n'):
                path.write_bytes(data)
                with self.subTest(data=data),self.assertRaises(ValueError):p.trace(path)
            path.write_bytes(b'{"event":"x"}\n');self.assertEqual([dict(event='x')],p.trace(path))

    def test_trace_symlink_is_not_an_original_process_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trace';path.write_bytes(b'{"event":"x"}\n');link=Path(tmp)/'link';link.symlink_to(path)
            with self.assertRaisesRegex(ValueError,'bound/type'):p.trace(link)


if __name__=='__main__':unittest.main()
