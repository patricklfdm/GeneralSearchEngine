"""Finite accounting and classification counterexamples, independent of the JVM."""
import copy
import unittest
from .backpressure_evidence import mailbox, classify


class BackpressureEvidenceTest(unittest.TestCase):
    def fixture(self,kind):
        size=32 if kind=='inputs' else 16;failed=kind=='completions'
        return dict(execution='internal-runtime-mailbox',publicRuntime=False,case=kind,limit=size,
                    initialSize=0,initialRemaining=size,fullSize=size,fullRemaining=0,executed=list(range(size)),finalSize=0,
                    rejection=dict(reason='CAPACITY_EXCEEDED',outcome='INDETERMINATE' if failed else 'NOT_SUBMITTED'),
                    closingAtOverflow=failed,failureAtOverflow=failed,resumed=not failed,
                    afterOverflow=dict(reason='CLOSED',outcome='NOT_SUBMITTED'))

    def test_both_actual_mailbox_bounds(self):
        for kind in ('inputs','completions'):mailbox(self.fixture(kind))

    def test_lost_duplicated_reordered_and_refused_tasks_are_rejected(self):
        for kind in ('inputs','completions'):
            row=self.fixture(kind);tasks=row['executed']
            for bad in (tasks[:-1],tasks+[tasks[-1]],tasks[::-1],tasks+[row['limit']]):
                with self.subTest(kind=kind,tasks=bad),self.assertRaises(ValueError):mailbox(dict(row,executed=bad))

    def test_bounds_cannot_be_lowered_to_manufacture_saturation(self):
        for kind in ('inputs','completions'):
            with self.assertRaises(ValueError):mailbox(dict(self.fixture(kind),limit=1))

    def test_full_and_empty_occupancy_must_be_observed(self):
        for key in ('initialSize','initialRemaining','fullSize','fullRemaining','finalSize'):
            row=self.fixture('inputs');row[key]+=1
            with self.subTest(key=key),self.assertRaises(ValueError):mailbox(row)

    def test_overflow_outcomes_are_not_interchangeable(self):
        for kind in ('inputs','completions'):
            row=self.fixture(kind);row['rejection']['outcome']='SUCCESS'
            with self.assertRaises(ValueError):mailbox(row)

    def test_completion_overflow_requires_failure_and_closing(self):
        for key in ('failureAtOverflow','closingAtOverflow'):
            with self.assertRaises(ValueError):mailbox(dict(self.fixture('completions'),**{key:False}))

    def test_input_overflow_must_remain_reusable(self):
        with self.assertRaises(ValueError):mailbox(dict(self.fixture('inputs'),resumed=False))

    def test_no_input_after_completion_failure(self):
        row=self.fixture('completions');row['afterOverflow']['reason']='CAPACITY_EXCEEDED'
        with self.assertRaises(ValueError):mailbox(row)

    def test_internal_fixture_cannot_be_relabelled(self):
        for values in (dict(publicRuntime=True),dict(execution='public-runtime-backpressure')):
            with self.assertRaises(ValueError):mailbox(dict(self.fixture('inputs'),**values))

    def test_queued_deadline_requires_safe_pre_dispatch_outcome(self):
        classify(dict(reasonCode='DEADLINE_EXCEEDED',outcome='NOT_SUBMITTED'),'DEADLINE_EXCEEDED','NOT_SUBMITTED')
        for outcome in ('INDETERMINATE','SUCCESS','NOT_APPLICABLE'):
            with self.assertRaises(ValueError):classify(dict(reasonCode='DEADLINE_EXCEEDED',outcome=outcome),'DEADLINE_EXCEEDED','NOT_SUBMITTED')

    def test_reentrant_denial_is_not_a_role_or_capacity_rejection(self):
        for reason in ('NOT_READY','NOT_LEADER','CAPACITY_EXCEEDED'):
            with self.assertRaises(ValueError):classify(dict(reasonCode=reason,outcome='NOT_APPLICABLE'),'REENTRANT_CALL','NOT_APPLICABLE')

if __name__=='__main__':unittest.main()
