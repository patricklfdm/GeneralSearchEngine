import unittest
from unittest.mock import patch
from . import hidden_staging_process_evidence as q


class HiddenStagingProcessTest(unittest.TestCase):
    def test_exact_offered_bytes_keep_ack_order(self):
        value = dict(statement='0102', acknowledgements=['0304','0506'])
        self.assertEqual(bytes(range(1,7)), q.proof_bytes(value))
        value['acknowledgements'].reverse()
        self.assertNotEqual(bytes(range(1,7)), q.proof_bytes(value))

    def test_bad_proof_fields_are_rejected(self):
        for value in (dict(statement=True, acknowledgements=['01','02']),
                      dict(statement='01', acknowledgements=['02']),
                      dict(statement='01', acknowledgements=['02',True]),
                      dict(statement='01', acknowledgements=['02','03'], extra=True)):
            with self.assertRaises(ValueError): q.proof_bytes(value)

    def test_invalid_hex_is_rejected(self):
        with self.assertRaises(ValueError): q.proof_bytes(dict(statement='zz', acknowledgements=['01','02']))

    def test_proof_comparison_uses_binary_bytes(self):
        value = dict(statement='01', acknowledgements=['02','03'])
        q.check_proof(value, b'\x01\x02\x03')
        with self.assertRaisesRegex(ValueError, 'exact offered proof'): q.check_proof(value, b'\x01\x03\x02')

    def test_prepared_reference_does_not_require_completion_or_interruptions(self):
        for mode in (None, False, True):
            with patch.object(q.h.p, 'profile', return_value=dict(size=3,backup=False,phase='CERTIFICATE')), \
                 patch.object(q.h.p, 'layout', side_effect=ValueError('captured')) as layout:
                with self.assertRaisesRegex(ValueError, 'captured'): q.h.prefix('raw', mode)
                extras = layout.call_args.args[2]
                self.assertEqual(mode is False, 'interruptions.json' in extras)
                self.assertEqual(mode is True, 'continued.gsr' in extras)
                self.assertIn('applied-ancestry.gsr', extras)

    def test_invalid_original_prevents_negative_qualification(self):
        with patch.object(q, 'validate', side_effect=ValueError('invalid original')), patch.object(q.shutil, 'copytree') as copied:
            with self.assertRaisesRegex(ValueError, 'invalid original'): q.qualify('raw')
            copied.assert_not_called()

    def test_fixed_cases_and_shared_trace_validation(self):
        self.assertEqual(16, len(set(q.CUTS))); self.assertEqual(21, len(q.VARIANTS))
        from .covered_staging_process_evidence import force_trace
        self.assertIs(force_trace, q.force_trace)


if __name__ == '__main__': unittest.main()
