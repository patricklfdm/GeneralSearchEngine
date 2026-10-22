import copy
import unittest
from unittest.mock import patch
from . import composition_negatives as n
from . import composition_scenarios as s


class NegativeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.originals={name:g.evidence() for name,g in (
            ('transition',s.transition(3,'ADD')[0]),('heterogeneous',s.heterogeneous(3,'ADD')[0]),
            ('accepted',s.recover_tail(3,'ADD','accepted')[0]))}

    def test_exact_rejection_inventory_after_originals_pass(self):
        results=n.run(self.originals)
        self.assertEqual([x[0] for x in n.CASES],[x['case'] for x in results])
        self.assertTrue(all(x['status']=='REJECTED' for x in results))

    def test_bad_original_is_not_successful_negative_qualification(self):
        originals=copy.deepcopy(self.originals);originals['accepted']['events'][0]['time']=10
        with patch.object(n,'mutate',side_effect=AssertionError('mutation must not start')):
            with self.assertRaisesRegex(ValueError,'event clock drift'):n.run(originals)

    def test_unrelated_rejection_and_programming_errors_do_not_count(self):
        for failure in (ValueError('unrelated parser error'),KeyError('bad fixture')):
            with self.subTest(failure=type(failure).__name__),patch.object(n.oracle,'check',side_effect=[{}, {}, {}, failure]):
                with self.assertRaises((ValueError,KeyError)):n.run(self.originals)


if __name__=='__main__':unittest.main()
