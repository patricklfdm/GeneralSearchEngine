import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import floor_handoff_qualification as h


class FloorHandoffQualificationTest(unittest.TestCase):
    def test_implicit_working_directory_cannot_enter_build_inventory(self):
        for cp in ('',':','/tmp:',':/tmp','/tmp::/tmp'):
            with self.assertRaisesRegex(ValueError,'handoff explicit classpath entries'):h.classpath_binding(cp)
        with self.assertRaisesRegex(ValueError,'handoff original classpath'):h.classpath_binding('.')

    def test_invalid_original_never_reaches_mutations(self):
        with patch.object(h,'validate',side_effect=ValueError('invalid original')),patch.object(h.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'invalid original'):h.qualify('absent')
            copied.assert_not_called()

    def test_unrelated_rejection_cannot_pass(self):
        with patch.object(h,'validate',return_value=[]),patch.object(h.shutil,'copytree'),patch.object(h.n,'mutate'), \
                patch.object(h.e,'validate_case',side_effect=ValueError('unrelated')):
            with self.assertRaisesRegex(ValueError,'handoff unrelated negative'):h.qualify('absent')

    def test_mutation_must_be_rejected(self):
        with patch.object(h,'validate',return_value=[]),patch.object(h.shutil,'copytree'),patch.object(h.n,'mutate'), \
                patch.object(h.e,'validate_case',return_value={}):
            with self.assertRaisesRegex(ValueError,'handoff mutation accepted'):h.qualify('absent')

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'original';path.write_bytes(b'keep')
            with self.assertRaises(FileExistsError):h.run(temp,'unused')
            self.assertEqual(b'keep',path.read_bytes())


if __name__=='__main__':unittest.main()
