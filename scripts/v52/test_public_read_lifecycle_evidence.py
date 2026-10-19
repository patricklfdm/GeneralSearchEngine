"""Exact ownership conservation and process-death boundaries."""
import copy
import unittest
from . import public_read_lifecycle_evidence as e


class LifecycleAccountingTest(unittest.TestCase):
    def rows(self):
        shared=dict(readId=1,marker=0,highWater=1,preparing=False,cancelling=0,completionReturned=False)
        return [dict(shared,event='REPLICA_READ_ADMITTED',phase='QUEUED',owned=1,waiting=1,captured=0,settling=0,alarms=1),
                dict(shared,event='REPLICA_READ_CAPTURE_VALIDATED',phase='CAPTURED',owned=1,waiting=0,captured=1,settling=0,alarms=0),
                dict(shared,event='REPLICA_READ_SETTLING',phase='SETTLING',owned=1,waiting=0,captured=0,settling=1,alarms=0),
                dict(shared,event='REPLICA_READ_OWNERSHIP_RELEASED',phase='SETTLING',owned=0,waiting=0,captured=0,settling=0,alarms=0,completionReturned=True)]

    def test_normal_process_requires_every_admission_to_release(self):
        self.assertEqual(dict(admitted=1,released=1,abruptOutstanding=0),e.ownership(self.rows()))
        with self.assertRaisesRegex(ValueError,'leaked'):e.ownership(self.rows()[:-1])

    def test_abrupt_process_retains_outstanding_without_inventing_release(self):
        self.assertEqual(dict(admitted=1,released=0,abruptOutstanding=1),e.ownership(self.rows()[:2],True))

    def test_duplicate_or_unmatched_release_rejected_even_at_abrupt_exit(self):
        rows=self.rows()
        for altered in (rows+rows[-1:],rows[-1:]):
            with self.subTest(rows=altered),self.assertRaisesRegex(ValueError,'duplicate ownership release'):e.ownership(altered,True)

    def test_future_completion_alone_never_returns_ownership(self):
        rows=self.rows();rows.insert(2,dict(event='CLIENT_SUCCESS',opId='future'))
        self.assertEqual(1,e.ownership(rows)['released'])
        for field,value in (('completionReturned',False),('preparing',True),('cancelling',1)):
            altered=copy.deepcopy(rows);altered[-1][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'before actual completion'):e.ownership(altered)

    def test_counts_timers_live_views_and_high_water_are_conserved(self):
        for index,key,value in ((0,'owned',0),(1,'alarms',1),(1,'captured',2),(2,'settling',0),(3,'highWater',0),(1,'marker',2)):
            altered=self.rows();altered[index][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'conservation'):e.ownership(altered)

    def test_cancelled_waiter_can_settle_without_capture_but_not_twice(self):
        rows=self.rows();del rows[1]
        self.assertEqual(1,e.ownership(rows)['released'])
        rows.insert(2,dict(rows[1]))
        with self.assertRaisesRegex(ValueError,'settlement ownership transition'):e.ownership(rows)

    def test_booleans_and_fractions_are_not_integer_resource_counts(self):
        for value in (True,1.0,-1):
            rows=self.rows();rows[0]['owned']=value
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'field types'):e.ownership(rows)

    def test_declared_capacity_rejects_one_extra_waiter_at_both_boundaries(self):
        for limit in (3,64):
            rows=[dict(self.rows()[0],readId=n,owned=n,waiting=n,alarms=n,highWater=n) for n in range(1,limit+2)]
            with self.subTest(limit=limit):
                self.assertEqual(limit,e.ownership(rows[:-1],True,limit=limit)['abruptOutstanding'])
                with self.assertRaisesRegex(ValueError,'conservation'):e.ownership(rows,True,limit=limit)

    def test_zero_read_limit_never_accepts_even_an_eventually_released_read(self):
        self.assertEqual(0,e.ownership([],limit=0)['admitted'])
        with self.assertRaisesRegex(ValueError,'conservation'):e.ownership(self.rows(),limit=0)


if __name__=='__main__':unittest.main()
