import tempfile
import unittest
from pathlib import Path
from unittest import mock
from . import pending_certificate_evidence as e
from . import pending_certificate_negatives as n

class PendingCertificateEvidenceTest(unittest.TestCase):
    def test_profiles_include_each_certificate_boundary_and_repeated_recovery(self):
        rows=e.cases();self.assertEqual(45,len(rows));self.assertEqual(45,len({r['name'] for r in rows}))
        self.assertEqual({(s,t) for s in (3,4,5) for t in (0,6,7)},{(r['size'],r['through']) for r in rows if r['mode']=='clean'})
        for mode in ('halt','kill'):self.assertEqual(set(e.CUTS),{r['cut'] for r in rows if r['mode']==mode})
        for mode in ('repeat-halt','repeat-kill'):self.assertEqual(set(e.RECOVERY+e.SEAL),{r['cut'] for r in rows if r['mode']==mode})
    def test_missing_inventory_and_extra_cases_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'certificate complete case set'):e.validate(temp)
            (Path(temp)/'extra').mkdir()
            with self.assertRaisesRegex(ValueError,'certificate complete case set'):e.validate(temp)
    def test_original_validation_precedes_negative_mutations(self):
        with mock.patch.object(e,'validate',side_effect=ValueError('bad original')),mock.patch.object(n,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'bad original'):n.run('/absent')
            mutate.assert_not_called()
    def test_negatives_cover_both_real_quorums_and_certificate_force(self):
        self.assertEqual(14,len(n.CASES));self.assertEqual(14,len({name for name,_ in n.CASES}))
        self.assertTrue({'peer-accept','peer-proof','peer-accept-force','peer-proof-force','candidate-force'}<={name for name,_ in n.CASES})
        for name,reason in n.CASES:self.assertIn(n.selected(name),e.cases());self.assertTrue(reason.startswith(('proof ','certificate ')))
