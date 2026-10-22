import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from . import capsule_evidence as e
from . import capsule_negatives as n


class CapsuleEvidenceTest(unittest.TestCase):
    def test_compaction_retains_each_boundary_and_current_range(self):
        entries = [dict(kind=k) for k in ('BARRIER', 'RESERVE', 'PREPARE', 'READY', 'SEAL', 'INTENT', 'FINAL', 'BARRIER', 'RETIRE')]
        self.assertEqual([(0,5,'RANGE'), (5,6,'MEMBERSHIP'), (6,7,'MEMBERSHIP'), (7,9,'RANGE')], e.spans(entries, 9))
        self.assertEqual([(0,5,'RANGE'), (5,6,'MEMBERSHIP')], e.spans(entries, 6))
        self.assertEqual([], e.spans(entries, 0))
        self.assertEqual([(0,1,'RANGE')], e.spans(entries, 1))

    def test_no_negative_qualifies_without_original_validation(self):
        with patch.object(e, 'validate', side_effect=ValueError('invalid original')) as validate, patch.object(n.shutil, 'copytree') as copytree:
            with self.assertRaisesRegex(ValueError, 'invalid original'): n.run('absent')
            validate.assert_called_once(); copytree.assert_not_called()

    def test_oversized_linked_and_missing_files_fail_before_payload_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); file = root/'file'; file.write_bytes(b'abc'); link = root/'link'; link.symlink_to(file)
            for path, limit in ((file,2), (link,3), (root/'missing',3)):
                with self.assertRaises(ValueError): e.file_bytes(path, limit)
            self.assertEqual(b'abc', e.file_bytes(file,3))


if __name__ == '__main__': unittest.main()
