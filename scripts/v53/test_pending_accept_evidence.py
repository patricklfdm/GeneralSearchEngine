import tempfile
import unittest
from pathlib import Path
from unittest import mock
from . import pending_accept_evidence as e
from . import pending_accept_negatives as n


class PendingAcceptEvidenceTest(unittest.TestCase):
    def test_exact_matrix_includes_each_accept_and_recovery_death(self):
        cases=e.cases();self.assertEqual(42,len(cases));self.assertEqual(42,len({c['name'] for c in cases}))
        for mode in ('halt','kill'):self.assertEqual(set(e.CUTS),{c['cut'] for c in cases if c['mode']==mode})
        for mode in ('repeat-halt','repeat-kill'):self.assertEqual(set(e.RECOVERY+e.SEAL),{c['cut'] for c in cases if c['mode']==mode})
        self.assertEqual({(size,tail) for size in (3,4,5) for tail in (False,True)},{(c['size'],c['tail']) for c in cases if c['mode']=='clean'})

    def test_missing_or_extra_case_cannot_qualify(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'pending complete case set'):e.validate(temp)
            (Path(temp)/'unknown').mkdir()
            with self.assertRaisesRegex(ValueError,'pending complete case set'):e.validate(temp)

    def test_container_bounds_complete_originals_and_payload(self):
        import struct
        raw=e.container([b'a',b'bc'],b'def')
        self.assertEqual(b'GSPV\x00\x01\x00\x03',raw[:8]);self.assertEqual(len(raw),struct.unpack('>I',raw[8:12])[0]);self.assertEqual(b'abc\x00\x00\x00\x03def',raw[12:])
        with self.assertRaisesRegex(ValueError,'pending payload bound'):e.container([],bytes(8*1024*1024+1))

    def test_invalid_original_cannot_be_counted_as_negative_success(self):
        with mock.patch.object(e,'validate',side_effect=ValueError('bad original')),mock.patch.object(n,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'bad original'):n.run('/nonexistent')
            mutate.assert_not_called()

    def test_negative_cases_select_real_scenarios_and_precise_reasons(self):
        self.assertEqual(12,len(n.CASES));self.assertEqual(12,len({name for name,_ in n.CASES}))
        for name,reason in n.CASES:self.assertIn(n.selected(name),e.cases());self.assertTrue(reason.startswith('pending '))
