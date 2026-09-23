"""A successful recovery read does not lease leadership for the next mutation."""
from concurrent.futures import Future
import copy
from pathlib import Path
import unittest
from unittest.mock import patch
from . import hardening_harness as h, hardening_evidence as e, public_history


class ResumeTest(unittest.TestCase):
    def fixture(self, writes, *, chosen=True, reads=None):
        group=h.RecoveryGroup(Path('/unused'), 'unused'); group.expected=[]
        outcomes=iter(writes); actual=[]; responses=iter(reads) if reads is not None else None
        class Worker:
            def send(worker, kind, **values):
                identity=str(len(group.history)+1)
                record=dict(opId=identity,kind=kind,node='node-1',pid=11,generation=1,
                            startNanos=len(group.history)*10+10,endNanos=len(group.history)*10+11,**values)
                result=dict(kind=kind,opId=identity,**values)
                if kind=='read':
                    result.update(next(responses) if responses is not None else dict(outcome='SUCCESS',documents=list(actual)))
                else:
                    reply=next(outcomes)
                    if isinstance(reply,Exception):raise reply
                    if reply is None:
                        group.history.append(dict(record,outcome='PENDING',endNanos=None));f=Future();f.set_result(None);return f
                    result.update(reply)
                    if result['outcome']=='SUCCESS' or chosen and result['outcome']=='INDETERMINATE':actual.extend(values['documents'])
                group.history.append(dict(record,**{k:v for k,v in result.items() if k not in ('kind','opId')}))
                f=Future();f.set_result(result);return f
            call=h.q.Worker.call
        worker=Worker();group.workers={'node-1':worker};return group,worker

    def run_resume(self, group, worker, row=None):
        row={} if row is None else row
        with patch.object(h.fault,'leader',return_value=('node-1',worker)):
            h.resume(group,row,140)
        return row

    def test_ci_stale_epoch_chosen_write_is_preserved_and_next_write_has_fresh_keys(self):
        group,worker=self.fixture([dict(outcome='INDETERMINATE',reasonCode='STALE_EPOCH'),dict(outcome='SUCCESS')])
        row=self.run_resume(group,worker)
        self.assertEqual([140,141,142,143],[d['id'] for d in group.expected])
        self.assertEqual(['SUCCESS','INDETERMINATE','SUCCESS','SUCCESS'],[r['outcome'] for r in group.history])
        self.assertEqual([dict(read='1',write='2'),dict(read='3',write='4')],row['recoveryWrites'])
        self.assertEqual(('3','4'),(row['recoveredRead'],row['resumedWrite']))

    def test_unchosen_uncertainty_does_not_get_fabricated_into_projection(self):
        group,worker=self.fixture([dict(outcome='INDETERMINATE',reasonCode='STALE_EPOCH'),dict(outcome='SUCCESS')],chosen=False)
        self.run_resume(group,worker)
        self.assertEqual([142,143],[d['id'] for d in group.expected])

    def test_no_fourth_write_after_three_classified_failures(self):
        group,worker=self.fixture([dict(outcome='NOT_SUBMITTED',reasonCode='NOT_READY')]*4);row={}
        with self.assertRaisesRegex(ValueError,'three fresh'):self.run_resume(group,worker,row)
        self.assertEqual(3,len(row['recoveryWrites']));self.assertEqual(6,len(group.history))
        self.assertEqual([140,142,144],[r['documents'][0]['id'] for r in group.history if r['kind']=='addAll'])

    def test_only_conservative_availability_outcomes_can_continue(self):
        replies=[dict(outcome='NOT_SUBMITTED',reasonCode=r) for r in h.q.RECOVERY_REASONS]
        replies += [dict(outcome='INDETERMINATE',reasonCode=r) for r in h.q.UNCERTAIN_RECOVERY_REASONS]
        for reply in replies:
            with self.subTest(reply=reply):
                group,worker=self.fixture([reply,dict(outcome='SUCCESS')]);self.run_resume(group,worker)
                self.assertEqual(4,len(group.history))

    def test_integrity_capacity_unknown_or_impossible_outcomes_fail_without_more_writes(self):
        replies=[dict(outcome='INDETERMINATE',reasonCode=r) for r in ('INTEGRITY_FAILURE','STORAGE_FAILURE','CAPACITY_EXCEEDED','CLOSED','NOT_LEADER','NOT_READY',None)]
        replies += [dict(outcome=o,reasonCode='STALE_EPOCH') for o in ('PENDING','CANCELLED','NOT_APPLICABLE')]
        replies += [None]
        for reply in replies:
            with self.subTest(reply=reply):
                group,worker=self.fixture([reply,dict(outcome='SUCCESS')])
                with self.assertRaises(ValueError):self.run_resume(group,worker)
                self.assertEqual(2,len(group.history))

    def test_changed_partial_or_reordered_read_cannot_be_used_as_expected_state(self):
        for observed in ([dict(id=999,value='injected')],[dict(id=140,value='wrong')]):
            group,worker=self.fixture([dict(outcome='INDETERMINATE',reasonCode='STALE_EPOCH'),dict(outcome='SUCCESS')],
                reads=[dict(outcome='SUCCESS',documents=[]),dict(outcome='SUCCESS',documents=observed)])
            with self.subTest(observed=observed),self.assertRaisesRegex(ValueError,'projection'):self.run_resume(group,worker)
            self.assertEqual(1,sum(r['kind']=='addAll' for r in group.history))

    def test_reads_still_have_four_attempt_limit_and_reject_nonavailability(self):
        group,worker=self.fixture([dict(outcome='SUCCESS')],reads=[dict(outcome='NOT_APPLICABLE',reasonCode='STALE_EPOCH')]*4)
        with self.assertRaisesRegex(ValueError,'four'):self.run_resume(group,worker)
        self.assertEqual(4,len(group.history));self.assertTrue(all(r['kind']=='read' for r in group.history))
        group,worker=self.fixture([],reads=[dict(outcome='NOT_APPLICABLE',reasonCode='STORAGE_FAILURE')])
        with self.assertRaises(ValueError):self.run_resume(group,worker)

    def test_original_history_checker_keeps_chosen_uncertainty_and_rejects_lost_ack(self):
        group,worker=self.fixture([dict(outcome='INDETERMINATE',reasonCode='STALE_EPOCH'),dict(outcome='SUCCESS')])
        self.run_resume(group,worker)
        with patch.object(h.fault,'leader',return_value=('node-1',worker)):group.read()
        r=public_history.check(group.history)
        self.assertTrue(next(v for v in r['witness'] if v['opId']=='2')['included'])
        bad=copy.deepcopy(group.history);bad[-1]['documents']=[]
        with self.assertRaisesRegex(ValueError,'not linearizable'):public_history.check(bad)

    def test_history_budget_prevents_a_49th_dispatch(self):
        group,worker=self.fixture([dict(outcome='SUCCESS')]);group.history=[{}]*48
        with self.assertRaisesRegex(ValueError,'dispatch bound'):self.run_resume(group,worker)
        self.assertEqual(48,len(group.history))

    def recovery_receipt(self):
        group,worker=self.fixture([dict(outcome='INDETERMINATE',reasonCode='STALE_EPOCH'),dict(outcome='SUCCESS')])
        row=self.run_resume(group,worker)
        row.update(number=1,beginNanos=1,recoveryBeginNanos=2,endNanos=1000,expected=group.expected)
        return row,group.history

    def test_independent_recovery_accounting_accepts_chosen_or_absent_uncertainty(self):
        for chosen in (True,False):
            group,worker=self.fixture([dict(outcome='INDETERMINATE',reasonCode='STALE_EPOCH'),dict(outcome='SUCCESS')],chosen=chosen)
            row=self.run_resume(group,worker)
            row.update(number=1,beginNanos=1,recoveryBeginNanos=2,endNanos=1000,expected=group.expected)
            e.recovery_writes(row,group.history,[])

    def test_evidence_cannot_drop_attempt_replay_keys_or_forge_successful_projection(self):
        for change in ('drop','replay','false-refusal','false-success','lost-prefix','wrong-read','overlap','extra-call'):
            row,history=self.recovery_receipt()
            if change=='drop':row['recoveryWrites'].pop(0)
            elif change=='replay':history[-1]['documents']=history[1]['documents']
            elif change=='false-refusal':history[1]['reasonCode']='STORAGE_FAILURE'
            elif change=='false-success':history[1]['outcome']='SUCCESS'
            elif change=='lost-prefix':row['expected']=row['expected'][2:]
            elif change=='wrong-read':history[2]['documents']=[dict(id=999,value='forged')]
            elif change=='overlap':history[2]['startNanos']=history[1]['startNanos']
            else:history.insert(2,dict(history[1],opId='undeclared',startNanos=25,endNanos=26))
            with self.subTest(change=change),self.assertRaises(ValueError):e.recovery_writes(row,history,[])

    def test_evidence_checks_leading_read_refusals_and_three_write_limit(self):
        row,history=self.recovery_receipt()
        history.insert(0,dict(opId='refused',kind='read',outcome='NOT_APPLICABLE',reasonCode='STALE_EPOCH',startNanos=3,endNanos=4))
        e.recovery_writes(row,history,[])
        history[0]['reasonCode']='INTEGRITY_FAILURE'
        with self.assertRaises(ValueError):e.recovery_writes(row,history,[])
        row,history=self.recovery_receipt();row['recoveryWrites']*=2
        with self.assertRaisesRegex(ValueError,'attempt bound'):e.recovery_writes(row,history,[])
