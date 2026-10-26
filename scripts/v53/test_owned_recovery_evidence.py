import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import owned_recovery_evidence as r


class OwnedRecoveryEvidenceTest(unittest.TestCase):
    def test_receipt_types_do_not_conflate_false_with_zero(self):
        self.assertFalse(r.same({'publicRuntime':0},{'publicRuntime':False}))
        self.assertFalse(r.same({'profiles':True},{'profiles':1}))
        self.assertTrue(r.same({'publicRuntime':False},{'publicRuntime':False}))

    def test_original_failure_cannot_be_a_successful_negative(self):
        with patch.object(r,'validate',side_effect=ValueError('invalid original')) as check,patch.object(r.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'invalid original'):r.qualify('absent')
            check.assert_called_once_with('absent');copy.assert_not_called()

    def test_unrelated_rejection_does_not_count(self):
        with patch.object(r,'validate',side_effect=[{},ValueError('unrelated')]),patch.object(r.shutil,'copytree'),patch.object(r,'load',return_value={}),patch.object(Path,'write_bytes',return_value=1):
            with self.assertRaisesRegex(ValueError,'unrelated negative: scope: unrelated'):r.qualify('absent')

    def test_root_inventory_required_before_any_receipt(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(r,'load') as read:
            with self.assertRaisesRegex(ValueError,'owned recovery root inventory'):r.validate(tmp)
            read.assert_not_called()

    def test_crash_original_failure_cannot_be_a_successful_negative(self):
        with patch.object(r,'validate_crashes',side_effect=ValueError('invalid original')) as check,patch.object(r.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'invalid original'):r.qualify_crashes('absent')
            check.assert_called_once_with('absent');copy.assert_not_called()
