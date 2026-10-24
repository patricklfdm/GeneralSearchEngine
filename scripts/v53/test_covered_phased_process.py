"""Reject missing/relabeled process originals before interpreting worker output."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import covered_phased_process_evidence as p


class CoveredPhasedProcessEvidenceTest(unittest.TestCase):
    def test_invalid_original_cannot_count_as_successful_negatives(self):
        with patch.object(p,'validate',side_effect=ValueError('original failed')) as validate,patch.object(p.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'original failed'):p.qualify('missing')
            validate.assert_called_once();copy.assert_not_called()

    def test_missing_or_linked_root_never_reaches_vote_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'root';root.mkdir();link=Path(tmp)/'link';link.symlink_to(root,target_is_directory=True)
            for path in (root,link):
                with self.subTest(path=path),patch.object(p.model,'prefix') as prefix,self.assertRaisesRegex(ValueError,'inventory'):p.validate(path)
                prefix.assert_not_called()

    def test_phase_directories_do_not_establish_complete_process_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('PROOF','CERTIFICATE'):(root/name).mkdir()
            (root/'receipt.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'phased process phase inventory'):p.validate(root)


if __name__=='__main__':unittest.main()
