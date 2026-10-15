"""Counterexample checks for repeated held queries and retained resource ownership."""
from pathlib import Path
import unittest
from unittest.mock import patch
from . import public_read_hardening_evidence as h


class HardeningEvidenceTest(unittest.TestCase):
    def fixture(self):
        target=dict(opId='read',policy='STALE_ALLOWED',repeat=True)
        rows=[dict(event='REPLICA_READ_REPORT_FIRST',opId='read',order=1,report={'sequence':7}),
              dict(event='CUT_REACHED',cut='REPLICA_READ_REPORT_FIRST',mode='pause',order=2),
              dict(event='CUT_RELEASED',cut='REPLICA_READ_REPORT_FIRST',order=3),
              dict(event='REPLICA_READ_REPORT_SECOND',opId='read',order=4,report={'sequence':7})]
        return rows,target

    def test_different_or_missing_second_query_is_rejected(self):
        rows,target=self.fixture();h.repeated(rows,target)
        rows[-1]['report']['sequence']=8
        with self.assertRaisesRegex(ValueError,'callback changed'):h.repeated(rows,target)
        rows.pop()
        with self.assertRaisesRegex(ValueError,'report cardinality'):h.repeated(rows,target)

    def test_publication_inside_callback_is_rejected(self):
        rows,target=self.fixture();rows.insert(2,dict(event='LOCAL_PUBLISHED',order=2.5))
        with self.assertRaisesRegex(ValueError,'publication changed during callback'):h.repeated(rows,target)

    def test_missing_or_reversed_pause_release_is_rejected(self):
        rows,target=self.fixture();rows[2]['order']=1.5
        with self.assertRaisesRegex(ValueError,'pause order'):h.repeated(rows,target)

    def test_cancelled_future_cannot_be_counted_as_released_view(self):
        counts=dict(readsOwned=1,readsCaptured=1,readsWaiting=0,readsSettling=0,readsAlarms=0,admissionAvailable=2)
        h.counters(counts,1,1,2)
        for key,value in (('readsOwned',0),('readsCaptured',0),('admissionAvailable',3),('readsAlarms',1),('readsCaptured',True)):
            with self.subTest(key=key,value=value):
                changed=dict(counts);changed[key]=value
                with self.assertRaisesRegex(ValueError,'counters or reserved slot'):h.counters(changed,1,1,2)

    def test_invalid_original_aborts_before_any_mutation(self):
        with patch.object(h.e,'validate',side_effect=ValueError('invalid original')) as validate,patch.object(h.e,'negatives') as negatives:
            with self.assertRaisesRegex(ValueError,'invalid original'):h.negatives(Path('/unused'),{}, {})
            validate.assert_called_once();negatives.assert_not_called()

    def test_changed_frozen_plan_fails_closed(self):
        self.assertEqual(3,len(h.plan()['cases']))
        with patch.object(h,'PLAN_SHA','0'*64):
            with self.assertRaisesRegex(ValueError,'frozen plan changed'):h.plan()


if __name__=='__main__':unittest.main()
