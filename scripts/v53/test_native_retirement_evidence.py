import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import native_retirement_evidence as evidence


class NativeRetirementEvidenceTest(unittest.TestCase):
    def test_original_must_pass_before_mutations(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(evidence.shutil, 'copytree') as copied:
            with self.assertRaises(ValueError):
                evidence.qualify(temp)
            copied.assert_not_called()

    def test_cleanup_requires_original_force_and_forbids_new_ack(self):
        events = ['CERTIFICATE_ACTIVE_FORCED', 'CERTIFICATE_ACTIVE_PARENT_FORCED',
                  'NATIVE_RETIREMENT_CERTIFICATE_RETAINED', 'STAGED_RETIREMENT_AUTHORITY_VALIDATED',
                  'SUPERSEDED_END_AUTHORITY_FORCED', 'SUPERSEDED_END_FILE_DELETED']
        expected = events[3:]
        evidence.order(events, expected, True)
        for index in range(len(events)):
            with self.subTest(index=index), self.assertRaises(ValueError):
                evidence.order(events[:index]+events[index+1:], expected, True)
        for event in ('APPLY_ACK_DIRECTORY_FORCED', 'APPLY_BEFORE_RETURN'):
            with self.subTest(event=event), self.assertRaisesRegex(ValueError, 'old ACK'):
                evidence.order(events+[event], expected, True)
        with self.assertRaisesRegex(ValueError, 'before certificate'):
            evidence.order([expected[0]]+events[:3]+expected[1:], expected, True)
        evidence.order([], [], False)
        with self.assertRaises(ValueError):
            evidence.order(events, expected, False)

    def test_worker_error_is_not_an_event(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'worker.log'
            path.write_text('EVENT CERTIFICATE_ACTIVE_FORCED\nRESPONSE digest 0\n')
            self.assertEqual(evidence.lines(path)[1], ['CERTIFICATE_ACTIVE_FORCED'])
            path.write_text('EVENT CERTIFICATE_ACTIVE_FORCED\nException: corrupt original\n')
            with self.assertRaisesRegex(ValueError, 'worker log'):
                evidence.lines(path)
