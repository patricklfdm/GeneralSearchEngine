from copy import deepcopy
import json
import unittest
from . import cloud_plan
from .process_harness import validate


class FoundationTest(unittest.TestCase):
    def test_no_gcp_plan_keeps_three_concurrent_voters_and_no_paid_admission(self):
        r=cloud_plan.qualify('a'*40);self.assertEqual(3,len(r['plan']['voters']))
        self.assertFalse(r['plan']['paidAdmission']);self.assertEqual([],r['cleanup']['leftovers'])

    def test_budget_and_expiry_are_not_bypassed_by_manual_cleanup(self):
        for kwargs in (dict(maximum_cost_microusd=0),dict(budget_microusd=1),dict(lease_seconds=5401),dict(grace_seconds=1081),dict(previous_cost_microusd=True)):
            with self.assertRaises(ValueError):cloud_plan.plan('a'*40,now=100,**kwargs)
        lease=dict(suite=cloud_plan.SUITE,owner='owner',expiresAt=100,operationGraceSeconds=10,
                   resources=[dict(name='node',id='123',owner='owner')])
        self.assertEqual('WAITING',cloud_plan.reconcile(lease,{'node':lease['resources'][0]},109)['status'])
        for changes in (dict(id='124'),dict(owner='foreign')):
            changed=dict(lease['resources'][0],**changes)
            with self.assertRaises(ValueError):cloud_plan.reconcile(lease,{'node':changed},110)
        with self.assertRaises(ValueError):cloud_plan.reconcile(dict(lease,resources=lease['resources']*2),{},200)

    def test_process_oracle_rejects_fabricated_force_exit_identity_and_bytes(self):
        import hashlib
        events=[dict(event='ready',pid=10,monotonicNanos=1),dict(event='before-write',pid=10,monotonicNanos=2),
                dict(event='after-write',pid=10,monotonicNanos=3),dict(event='after-force',pid=10,monotonicNanos=4),
                dict(event='before-ack',pid=10,monotonicNanos=5),dict(event='ack',pid=10,monotonicNanos=6,sha256=hashlib.sha256(b'bytes').hexdigest()),
                dict(event='after-ack',pid=10,monotonicNanos=7),dict(event='barrier',pid=10,monotonicNanos=8,cut='after-ack')]
        validate(events,'after-ack',-9,'kill',b'bytes',b'bytes',[10,11,12])
        for key in ('force','exit','pid','bytes'):
            e=deepcopy(events);code=-9;pids=[10,11,12];raw=b'bytes'
            if key=='force':e.pop(3)
            if key=='exit':code=0
            if key=='pid':pids=[10,10,12]
            if key=='bytes':raw=b'wrong'
            with self.subTest(key=key):
                with self.assertRaises((ValueError,IndexError)):validate(e,'after-ack',code,'kill',raw,b'bytes',pids)

if __name__=='__main__':unittest.main()
