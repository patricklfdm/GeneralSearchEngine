import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import owned_adoption_process_evidence as o


class OwnedAdoptionProcessEvidenceTest(unittest.TestCase):
    def test_original_crash_failure_cannot_count_as_successful_negatives(self):
        with patch.object(o,'validate',side_effect=ValueError('original crash invalid')) as validate, patch.object(o.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'original crash invalid'):o.qualify('/unused')
            validate.assert_called_once_with('/unused');copy.assert_not_called()

    def test_unrelated_failure_does_not_satisfy_intended_crash_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);case=root/'cases/kill-ADOPTION_INSTALL_FENCED/first';case.mkdir(parents=True)
            (case/'grants.gsr').write_bytes(b'original')
            with patch.object(o,'validate',return_value=(dict(status='PASS'),({'grants.gsr':b'before'},{},{}))), \
                 patch.object(o.a,'validate_case',side_effect=ValueError('unrelated source failure')):
                with self.assertRaisesRegex(ValueError,'unrelated negative: first-journal'):o.qualify(root)


if __name__=='__main__':unittest.main()
