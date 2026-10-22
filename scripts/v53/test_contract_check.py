from copy import deepcopy
import json
import unittest

from . import contract_check as c


class ContractTest(unittest.TestCase):
    def test_frozen_plan_rejects_incomplete_cohort_and_inconsistent_call_windows(self):
        original=json.loads((c.DOCS/'acceptance-plan.json').read_text());c.plan_check(original)
        for key in ('profiles','scenarios','negatives','measurements','calls','source','retry'):
            plan=deepcopy(original)
            if key in ('profiles','scenarios','negatives','measurements'):plan[key].pop()
            elif key=='calls':plan['workload']['measurementCalls']-=1
            elif key=='source':plan['experiment']['sameSource']=False
            else:plan['experiment']['measurementRetries']=True
            with self.subTest(key=key),self.assertRaises(ValueError):c.plan_check(plan)


if __name__=='__main__':unittest.main()
