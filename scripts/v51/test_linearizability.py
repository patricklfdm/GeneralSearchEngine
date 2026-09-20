from copy import deepcopy
import unittest
from .linearizability import check


class LinearizabilityTest(unittest.TestCase):
    def history(self):
        return [dict(id='bulk',kind='write',start=1,end=2,outcome='success',changes=[('a',1),('b',1)]),
                dict(id='read',kind='read',start=3,end=4,outcome='success',result={'a':1,'b':1})]
    def test_atomic_bulk_and_stale_read_negatives(self):
        h=self.history();self.assertEqual(['bulk','read'],check(h)['linearization'])
        for wrong in ({},{'a':1}):
            h=self.history();h[1]['result']=wrong
            with self.assertRaises(ValueError):check(h)
    def test_unknown_can_complete_or_be_absent_but_not_submitted_cannot_appear(self):
        h=self.history();h[0]['outcome']='unknown'
        self.assertEqual('PASS',check(h)['status'])
        h[1]['result']={};self.assertEqual(['read'],check(h)['linearization'])
        h[0]['outcome']='not-submitted';h[1]['result']={'a':1,'b':1}
        with self.assertRaises(ValueError):check(h)
    def test_overlapping_read_can_precede_write_but_later_stale_read_cannot(self):
        h=self.history();h[1].update(start=1,end=3,result={})
        self.assertEqual(['read','bulk'],check(h)['linearization'])
        h[1]['start']=3
        with self.assertRaises(ValueError):check(h)
    def test_checker_bound_is_an_explicit_rejection(self):
        with self.assertRaises(ValueError):check(self.history(),maximum=1)

if __name__=='__main__':unittest.main()
