"""Phase 5B must not treat a completed strong read as a lease for a later write."""
import copy
import unittest
from unittest.mock import patch
from . import combined_lifecycle_harness as h, combined_lifecycle_evidence as e
from . import test_hardening_harness as fixtures, public_history


class CombinedRecoveryTest(unittest.TestCase):
    def fixture(self, writes, **kwargs):
        return fixtures.ResumeTest.fixture(self,writes,group_class=h.Group,**kwargs)

    def resume(self, group, worker, receipt=None):
        receipt = {} if receipt is None else receipt
        with patch.object(h.fault,'leader',return_value=('node-1',worker)):
            h.resume(group,receipt)
        return receipt

    def test_ci_retained_higher_promise_keeps_chosen_uncertainty_and_uses_new_keys(self):
        group,worker=self.fixture([dict(outcome='INDETERMINATE',reasonCode='STALE_EPOCH'),dict(outcome='SUCCESS')])
        receipt=self.resume(group,worker)
        self.assertEqual([80,81,82,83],[d['id'] for d in group.expected])
        self.assertEqual(['SUCCESS','INDETERMINATE','SUCCESS','SUCCESS'],[r['outcome'] for r in group.history])
        self.assertEqual([dict(read='1',write='2'),dict(read='3',write='4')],receipt['recoveryWrites'])
        self.assertEqual(('3','4'),(receipt['recoveredRead'],receipt['resumedWrite']))
        with patch.object(h.fault,'leader',return_value=('node-1',worker)):group.read()
        witness=public_history.check(group.application(),max_operations=32)['witness']
        self.assertTrue(next(v for v in witness if v['opId']=='2')['included'])

    def test_uncertainty_absent_at_next_read_does_not_create_documents(self):
        group,worker=self.fixture([dict(outcome='INDETERMINATE',reasonCode='STALE_EPOCH'),dict(outcome='SUCCESS')],chosen=False)
        self.resume(group,worker)
        self.assertEqual([82,83],[d['id'] for d in group.expected])

    def test_three_attempt_limit_uses_80_82_84_then_stops(self):
        group,worker=self.fixture([dict(outcome='NOT_SUBMITTED',reasonCode='NOT_READY')]*4);receipt={}
        with self.assertRaisesRegex(ValueError,'three fresh'):self.resume(group,worker,receipt)
        self.assertEqual(3,len(receipt['recoveryWrites']))
        self.assertEqual([80,82,84],[r['documents'][0]['id'] for r in group.application() if r['kind']=='addAll'])

    def test_only_existing_availability_outcomes_continue(self):
        outcomes=[dict(outcome='NOT_SUBMITTED',reasonCode=r) for r in h.q.RECOVERY_REASONS]
        outcomes += [dict(outcome='INDETERMINATE',reasonCode=r) for r in h.q.UNCERTAIN_RECOVERY_REASONS]
        for reply in outcomes:
            with self.subTest(reply=reply):
                group,worker=self.fixture([reply,dict(outcome='SUCCESS')]);self.resume(group,worker)
                self.assertEqual(4,len(group.application()))
        for reply in [None]+[dict(outcome='INDETERMINATE',reasonCode=r) for r in
                ('INTEGRITY_FAILURE','STORAGE_FAILURE','CAPACITY_EXCEEDED','CLOSED','NOT_LEADER','unknown')]:
            with self.subTest(reply=reply):
                group,worker=self.fixture([reply,dict(outcome='SUCCESS')])
                with self.assertRaises(ValueError):self.resume(group,worker)
                self.assertEqual(2,len(group.application()))

    def test_partial_changed_or_reordered_uncertain_bulk_is_not_adopted(self):
        docs=[dict(id=i,value=f'tag-{i}-'+'x'*512) for i in (80,81)]
        for bad in (docs[:1],list(reversed(docs)),[dict(docs[0],value='wrong'),docs[1]]):
            group,worker=self.fixture([dict(outcome='INDETERMINATE',reasonCode='STALE_EPOCH')],
                reads=[dict(outcome='SUCCESS',documents=[]),dict(outcome='SUCCESS',documents=bad)])
            with self.subTest(bad=bad),self.assertRaisesRegex(ValueError,'projection'):self.resume(group,worker)
            self.assertEqual(1,sum(h['kind']=='addAll' for h in group.application()))

    def test_four_read_attempt_limit_and_32_application_calls_remain_fixed(self):
        group,worker=self.fixture([],reads=[dict(outcome='NOT_APPLICABLE',reasonCode='STALE_EPOCH')]*5)
        with self.assertRaisesRegex(ValueError,'four'):self.resume(group,worker)
        self.assertEqual(4,len(group.application()))
        group,worker=self.fixture([dict(outcome='SUCCESS')]);group.history=[dict(kind='read')]*32
        with self.assertRaisesRegex(ValueError,'dispatch bound'):self.resume(group,worker)
        self.assertEqual(32,len(group.history))
        group,worker=self.fixture([dict(outcome='SUCCESS')]);group.history=[dict(kind='closeHandle')]*32
        self.resume(group,worker);self.assertEqual(2,len(group.application()))

    def test_final_read_cannot_exceed_application_history_budget(self):
        group,worker=self.fixture([dict(outcome='SUCCESS')]);group.history=[dict(kind='read')]*30
        self.resume(group,worker)
        with patch.object(h.fault,'leader',return_value=('node-1',worker)),self.assertRaisesRegex(ValueError,'dispatch bound'):
            group.read()
        self.assertEqual(32,len(group.application()))


class CombinedRecoveryEvidenceTest(unittest.TestCase):
    def fixture(self, *, chosen=True, case='cancel-chosen-recovery'):
        driver=CombinedRecoveryTest()
        group,worker=driver.fixture([dict(outcome='INDETERMINATE',reasonCode='STALE_EPOCH'),dict(outcome='SUCCESS')],chosen=chosen)
        receipt=driver.resume(group,worker)
        with patch.object(h.fault,'leader',return_value=('node-1',worker)):group.read()
        receipt.update(case=case,recoveryBeginNanos=2,finalRead=group.call_id(),expected=group.expected,
                       duringAfterWriteRead='before',majorityAfterWriteRead='before',whileClosingRead='before')
        before=dict(opId='before',kind='read',outcome='SUCCESS',documents=[],startNanos=-10,endNanos=-5)
        return [before,*group.history],receipt,dict(readyNanos=-6 if case.startswith('torn-') else 1)

    def test_independent_accounting_covers_all_four_schedules_and_uncertain_results(self):
        for case in h.CASES:
            for chosen in (True,False):
                with self.subTest(case=case,chosen=chosen):e.recovery_writes(*self.fixture(case=case,chosen=chosen))

    def test_dropped_attempt_replayed_key_unsafe_failure_or_forged_projection_is_rejected(self):
        for change in ('drop','replay','failure','success','prefix','read','overlap','extra','boundary','begin-before-ready'):
            history,receipt,restarted=self.fixture()
            if change=='drop':receipt['recoveryWrites'].pop(0)
            elif change=='replay':history[4]['documents']=copy.deepcopy(history[2]['documents'])
            elif change=='failure':history[2]['reasonCode']='STORAGE_FAILURE'
            elif change=='success':history[2]['outcome']='SUCCESS'
            elif change=='prefix':receipt['expected']=receipt['expected'][2:]
            elif change=='read':history[3]['documents']=[dict(id=999,value='forged')]
            elif change=='overlap':history[3]['startNanos']=history[2]['startNanos']
            elif change=='extra':history.insert(3,dict(history[2],opId='extra',startNanos=25,endNanos=26))
            elif change=='boundary':receipt['recoveryBeginNanos']=history[2]['endNanos']
            else:receipt['recoveryBeginNanos']=restarted['readyNanos']
            with self.subTest(change=change),self.assertRaises(ValueError):e.recovery_writes(history,receipt,restarted)

    def test_no_unreported_call_before_the_declared_recovery_boundary(self):
        for case in h.CASES:
            history,receipt,restarted=self.fixture(case=case)
            history.insert(1,dict(history[1],opId='hidden',startNanos=3,endNanos=4))
            receipt['recoveryBeginNanos']=5
            with self.subTest(case=case),self.assertRaisesRegex(ValueError,'boundary'):
                e.recovery_writes(history,receipt,restarted)

    def test_read_refusals_and_limits_remain_independently_checked(self):
        history,receipt,restarted=self.fixture()
        history.insert(1,dict(opId='refused',kind='read',outcome='NOT_APPLICABLE',reasonCode='STALE_EPOCH',startNanos=3,endNanos=4))
        e.recovery_writes(history,receipt,restarted)
        history[1]['reasonCode']='INTEGRITY_FAILURE'
        with self.assertRaises(ValueError):e.recovery_writes(history,receipt,restarted)
        history,receipt,restarted=self.fixture();receipt['recoveryWrites']*=2
        with self.assertRaisesRegex(ValueError,'attempt bound'):e.recovery_writes(history,receipt,restarted)
        history,receipt,restarted=self.fixture()
        history.extend(dict(history[0],opId='extra-'+str(i)) for i in range(33-len(history)))
        with self.assertRaisesRegex(ValueError,'history bound'):e.recovery_writes(history,receipt,restarted)


if __name__=='__main__':unittest.main()
