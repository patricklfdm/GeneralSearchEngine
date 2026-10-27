import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import native_application_evidence as evidence


class NativeApplicationEvidenceTest(unittest.TestCase):
    def test_native_force_is_required_for_each_new_application(self):
        one = ['CERTIFICATE_ACTIVE_FORCED', 'CERTIFICATE_ACTIVE_PARENT_FORCED',
               'NATIVE_CERTIFICATE_RETAINED', 'APPLICATION_AUTHORITY_VALIDATED',
               'APPLY_ACK_DIRECTORY_FORCED', 'APPLY_BEFORE_RETURN']
        evidence.native_order(one*2, 2)
        for missing in one:
            changed = one+[v for v in one if v != missing]
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                evidence.native_order(changed, 2)
        with self.assertRaisesRegex(ValueError, 'exact force order'):
            evidence.native_order(one+one[:-2]+list(reversed(one[-2:])), 2)

    def test_original_evidence_must_pass_before_any_negative_copy(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(evidence.shutil, 'copytree') as copied:
            with self.assertRaises(ValueError):
                evidence.qualify(Path(temp))
            copied.assert_not_called()

    def test_worker_errors_and_unrecognized_lines_are_not_events(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'worker.log'
            path.write_text('EVENT APPLY_BEFORE_RETURN\nRESULT {}\n')
            self.assertEqual(['APPLY_BEFORE_RETURN'], evidence.lines(path)[1])
            path.write_text('EVENT APPLY_BEFORE_RETURN\nException: lost authority\n')
            with self.assertRaisesRegex(ValueError, 'worker log'):
                evidence.lines(path)
