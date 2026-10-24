"""Evidence rejects unrelated originals, truncated traces and false process claims."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import context_mixed_process_evidence as m


class MixedProcessEvidenceTest(unittest.TestCase):
    def test_invalid_original_stops_before_negative_mutations(self):
        with patch.object(m,'validate',side_effect=ValueError('bad original')) as validate,patch.object(m.shutil,'copytree') as copytree:
            with self.assertRaisesRegex(ValueError,'bad original'):m.qualify('absent')
            validate.assert_called_once();copytree.assert_not_called()

    def test_missing_or_linked_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'missing'
            with self.assertRaises(ValueError):m.validate(root)
            real=Path(tmp)/'real';real.mkdir();root.symlink_to(real,target_is_directory=True)
            with self.assertRaises(ValueError):m.validate(root)

    def test_matrix_is_complete_and_unambiguous(self):
        self.assertEqual(27,len(m.ACCEPT_POINTS));self.assertEqual(15,len(m.SOURCE_POINTS))
        self.assertEqual(42,len(set(m.ACCEPT_POINTS+m.SOURCE_POINTS)))
        self.assertEqual(set(m.recovery.acceptance.CUTS),set(m.ACCEPT_POINTS)-{'FLOOR_RELEASE_FILE_DELETED@2'})
        self.assertEqual(set(m.source.CUTS),set(m.SOURCE_POINTS)-{'SOURCE_RETIREMENT_FILE_DELETED@2'})

    def test_second_file_death_requires_second_occurrence(self):
        steps=[('DELETE',{}),('FORCE',{}),('DELETE',{})]
        self.assertEqual(2,m.completion.stop(steps,'DELETE@2'))
        with self.assertRaises(IndexError):m.completion.stop(steps,'DELETE@3')

    def test_trace_rejects_truncation_and_noncanonical_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trace'
            for raw in (b'',b'{"event":"OPEN_RETURNED"}',b'{ "event": "OPEN_RETURNED" }\n'):
                with self.subTest(raw=raw):
                    path.write_bytes(raw)
                    with self.assertRaises(ValueError):m.completion.trace(path)
            path.write_bytes(b'{"event":"OPEN_RETURNED"}\n')
            self.assertEqual([dict(event='OPEN_RETURNED')],m.completion.trace(path))

    def test_reopen_cannot_claim_unrelated_quorum_ack(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trace';path.write_bytes(b'{"event":"PROOF_BEFORE_RETURN"}\n')
            with self.assertRaisesRegex(ValueError,'unrelated acknowledgement'):m.completion.trace(path)


if __name__=='__main__':unittest.main()
