import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import native_voting_evidence as v
from . import native_voting_restart_evidence as r


class NativeVotingEvidenceTest(unittest.TestCase):
    def test_both_negative_drivers_reject_invalid_originals_before_mutation(self):
        for module in (v,r):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as temp, patch.object(module,'validate',side_effect=ValueError('original invalid')) as validate, patch.object(module.shutil,'copytree') as copy:
                with self.assertRaisesRegex(ValueError,'original invalid'):module.qualify(Path(temp))
                validate.assert_called_once();copy.assert_not_called()

    def test_worker_diagnostic_or_hidden_failure_cannot_be_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'worker.log';path.write_text('READY resume\nException in thread main: lost vote\nCLOSED resume\n')
            with self.assertRaisesRegex(ValueError,'log shape'):r.log(path)


if __name__=='__main__':unittest.main()
