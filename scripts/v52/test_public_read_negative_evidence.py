"""Reject invalid originals, unrelated failures and fabricated confirmation edges."""
import unittest
from pathlib import Path
from unittest.mock import patch
from . import public_read_negative_evidence as n, public_reads_evidence as e


class TargetedNegativeTest(unittest.TestCase):
    def test_invalid_original_stops_before_mutations(self):
        with patch.object(e,'traces_at',return_value={}),patch.object(e,'read',return_value=[]),\
                patch.object(e,'validate',side_effect=ValueError('invalid original')) as validate:
            with self.assertRaisesRegex(ValueError,'invalid original'):n.negatives(Path('/unused'),{}, {})
            self.assertEqual(1,validate.call_count)

    def test_unrelated_failure_never_counts_as_rejection(self):
        def fail():raise ValueError('missing original file')
        with self.assertRaisesRegex(ValueError,'unrelated N05'):n.rejected('N05','terminal proof presence',fail)
        with self.assertRaisesRegex(ValueError,'evidence accepted'):n.rejected('N05','terminal proof presence',lambda:None)

    def test_controller_claim_cannot_override_worker_confirmation_order(self):
        writes=[dict(opId=str(i),node='node-1',pid=7,outcome='SUCCESS',endNanos=20+i) for i in range(3)]
        strong=[dict(opId='read',node='node-1',pid=7,startNanos=100)]
        rows=[dict(event='CLIENT_SUCCESS',opId=str(i),pid=7,order=i+1) for i in range(3)]
        rows.append(dict(event='CLIENT_INVOKE',opId='read',pid=7,order=4))
        e.confirmed_order(writes,strong,{'node-1':rows})
        rows[0]['order']=5
        with self.assertRaisesRegex(ValueError,'worker confirmed-write-before-token'):e.confirmed_order(writes,strong,{'node-1':rows})

    def test_confirmation_cannot_be_borrowed_from_other_process(self):
        writes=[dict(opId=str(i),node='node-1',pid=7,outcome='SUCCESS',endNanos=20+i) for i in range(3)]
        strong=[dict(opId='read',node='node-1',pid=8,startNanos=100)]
        rows=[dict(event='CLIENT_SUCCESS',opId=str(i),pid=7,order=i+1) for i in range(3)]
        rows.append(dict(event='CLIENT_INVOKE',opId='read',pid=8,order=4))
        with self.assertRaisesRegex(ValueError,'worker confirmed-write-before-token'):e.confirmed_order(writes,strong,{'node-1':rows})


if __name__=='__main__':unittest.main()
