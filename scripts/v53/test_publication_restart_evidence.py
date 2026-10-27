import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import publication_restart_evidence as r


class PublicationRestartEvidenceTest(unittest.TestCase):
    def test_invalid_original_cannot_count_as_rejected_mutations(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(r, 'validate', side_effect=ValueError('invalid original')) as validate, patch.object(r.shutil, 'copytree') as copy:
            with self.assertRaisesRegex(ValueError, 'invalid original'): r.qualify(Path(temp))
            validate.assert_called_once(); copy.assert_not_called()

    def test_unexpected_worker_failure_is_not_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'worker.log'
            path.write_text('READY resume\nException in thread main: bad disk\nCLOSED resume\n')
            with self.assertRaisesRegex(ValueError, 'log shape'): r.log(path)


if __name__ == '__main__': unittest.main()
