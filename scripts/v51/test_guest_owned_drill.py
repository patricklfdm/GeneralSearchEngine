"""Closed drill commands, once-only crashes and complete offline admission."""
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from . import guest_fault_service as service, guest_fault_recovery as recovery, guest_fault_jvm as jvm
from . import guest_owned_drill as drill, guest_owned_experiment as experiment, cloud_guest, cloud_fake
from . import remote_command as c, guest_fault_evidence as evidence
from .test_guest_service import config
from . import test_guest_owned_workload as common


class DrillScopeTest(unittest.TestCase):
    def test_all_twelve_are_offline_and_native_keeps_three_faults(self):
        expected=('leader-loss','isolated-old-leader','asymmetric-requests','asymmetric-responses','slow-follower',
                  'interrupted-transfer','entry-chosen','proof-quorum','group-restart','maintenance','no-quorum','minority-capacity')
        self.assertEqual(expected,drill.CASES)
        for case in expected:
            cfg=dict(config(Path('/tmp/drill')),faultCell=case);cloud_guest.validate(cfg)
            cfg['execution']=cloud_guest.NATIVE_EXECUTION
            if case in service.CASES:cloud_guest.validate(cfg)
            else:
                with self.assertRaisesRegex(ValueError,'fault cell'):cloud_guest.validate(cfg)
        self.assertEqual(('healthy','leader-loss','maintenance','no-quorum'),experiment.CELLS)

    def test_every_offline_cell_uses_its_frozen_plan_budget(self):
        from . import native_experiment_timing as timing, cloud_workload_contract as plan
        for cell in plan.load()['cells']:
            self.assertEqual(cell['seconds'],timing.cell({},cell['name']))
        for case in recovery.CASES:
            with self.assertRaises(KeyError):timing.cell(dict(schema=timing.REQUEST_SCHEMA,timingProfile=timing.PROFILE),case)

    def test_partition_routes_to_each_guest_with_a_distinct_target_node(self):
        with tempfile.TemporaryDirectory() as temp:
            cell=drill.Cell(SimpleNamespace(clients=[(n,None,{}) for n in (1,2,3)],provider=SimpleNamespace(req={})),Path(temp)/'cell','interrupted-transfer')
            cell.end=time.monotonic()+30;cell.succeeded=Mock(return_value={'result':{}})
            cell.partition('node-2','isolate')
            self.assertEqual(3,cell.succeeded.call_count)
            for call in cell.succeeded.call_args_list:
                self.assertEqual({'action':'isolate','node':'node-2'},call.args[2])
            self.assertEqual({1,2,3},{v.args[0][0] for v in cell.succeeded.call_args_list})

    def test_partial_or_reordered_cases_cannot_close_drill(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);req,_,_=cloud_fake.fixture();c.write_once(root/'plan.json',dict(scope=drill.SCOPE,request=req))
            for index,cases in enumerate((drill.CASES[:-1],tuple(reversed(drill.CASES)),recovery.CASES)):
                with self.assertRaisesRegex(ValueError,'aggregate scope'):
                    evidence.validate(root,root/str(index),cases=cases,scope=drill.SCOPE)

    def test_closed_command_line_scope_does_not_admit_mixed_presets(self):
        from .guest_owned_qualification import run
        for name in ('network','experiment','maintenance','faults','workload','bootstrap'):
            with self.assertRaisesRegex(ValueError,'own scope'):
                run('/unused','/unused','a'*40,failure_drill=True,**{name:True})


class DrillRunnerTest(common.RunnerWorkloadTest):
    def setUp(self):
        super().setUp();self.probe.mode=drill.MODE;self.probe.scope=drill.SCOPE
        self.probe.collect_validate.return_value.update(mode=drill.MODE,scope=drill.SCOPE,cells=list(drill.CASES))
    def test_partial_scope_runs_only_healthy_and_preserves_cleanup_and_charge(self):
        result=self.run_case();self.assertEqual('PASS',result['status'],result['errors'])
        self.assertEqual(list(drill.CASES),[v.args[0] for v in self.probe.cell.call_args_list])
        self.assertTrue(result['leaseReleased']);self.assertFalse(result['fullRemoteQualification'])
    def test_missing_one_cell_rejects_complete_drill(self):
        self.probe.collect_validate.return_value['cells']=list(drill.CASES[:-1])
        self.assertEqual('FAIL',self.run_case()['status'])


class RecoveryHandlerTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.jvm=Mock(closed=False,identity=dict(pid=41,node='node-1',generation=1))
    def handler(self,case):
        return service.Handler(SimpleNamespace(config=dict(config(self.root),faultCell=case),cell=self.root,root=self.root,
            node='node-1',jvm=self.jvm))
    def command(self,h,**payload):return h.handle('fault',payload,lambda:None)

    def test_exact_large_documents_do_not_enable_arbitrary_sizes_or_tags(self):
        for case,size in (('interrupted-transfer',4096),('minority-capacity',20000)):
            self.assertTrue(recovery.bulk_allowed(case,recovery.documents(40,size)))
            for docs in (recovery.documents(40,size+1),recovery.documents(40,size-1),recovery.documents(80,size),[{}]):
                self.assertFalse(recovery.bulk_allowed(case,docs))
            self.assertFalse(recovery.bulk_allowed('leader-loss',recovery.documents(40,size)))
        self.assertFalse(recovery.bulk_allowed('interrupted-transfer',recovery.documents(60,4096)))
        self.assertTrue(recovery.bulk_allowed('minority-capacity',recovery.documents(60,20000)))

    def test_arm_is_one_fixed_cut_and_cannot_rearm(self):
        h=self.handler('entry-chosen');h.generation=1
        with self.assertRaises(ValueError):self.command(h,action='arm-cut',cut='PROOF_ACK_RECEIVED')
        result=self.command(h,action='arm-cut');self.assertEqual(recovery.CUTS[h.case],result['cut'])
        self.assertEqual('ACCEPT_ACK_RECEIVED\nkill\n',(self.root/'node-1-arm.txt').read_text())
        with self.assertRaisesRegex(ValueError,'consumed'):self.command(h,action='arm-cut')

    def test_target_claim_precedes_pipe_submission_and_survives_lost_reply(self):
        h=self.handler('proof-quorum');h.generation=1;self.command(h,action='arm-cut')
        self.jvm.submit.side_effect=ConnectionError('lost original pipe write')
        with self.assertRaises(ConnectionError):self.command(h,action='start-target',intentId='call-05')
        self.assertEqual({'action':'start-target','intentId':'call-05'},c.read(self.root/'target-claim.json'))
        with self.assertRaises(FileExistsError):self.command(h,action='start-target',intentId='call-05')
        self.jvm.submit.assert_called_once_with('addAll',intentId='call-05',documents=recovery.documents(40,512))

    def test_target_is_pending_and_never_calls_finish(self):
        h=self.handler('entry-chosen');h.generation=1;self.command(h,action='arm-cut')
        request=dict(kind='addAll',intentId='call-05',opId='node-1-g1-6',documents=recovery.documents(40,512));future=Future()
        self.jvm.submit.return_value=({'request':request},future)
        self.assertEqual(dict(identity=self.jvm.identity,request=request),self.command(h,action='start-target',intentId='call-05'))
        self.assertFalse(future.done());self.jvm.finish.assert_not_called()
        with self.assertRaisesRegex(ValueError,'consumed'):self.command(h,action='start-target',intentId='call-06')

    def test_cut_must_belong_to_current_process_before_sigkill(self):
        h=self.handler('interrupted-transfer');h.generation=1;self.command(h,action='arm-cut')
        cut=dict(event='CUT_REACHED',cut=recovery.CUTS[h.case],mode='kill',pid=40)
        with patch.object(recovery.public_trace,'live_rows',return_value=[cut]):
            with self.assertRaisesRegex(ValueError,'before original cut'):h.handle('stop-voter',dict(forced=True),lambda:None)
            self.jvm.stop.assert_not_called()
            cut['pid']=41;h.recovery.before_kill()

    def test_prepare_direction_consumed_and_watchdog_remains_invalid(self):
        h=self.handler('minority-capacity');h.s.jvm=None
        with patch.object(recovery.threading,'Timer') as timer:
            result=self.command(h,action='prepare-direction')
            self.assertEqual(60,timer.call_args.args[0]);self.assertEqual(4,len(result['rules']))
            with self.assertRaises(ValueError):self.command(h,action='prepare-direction')
            timer.call_args.args[1]();self.assertTrue(c.read(self.root/'prepare-isolation.json')['watchdog'])
            h.s.jvm=self.jvm
            self.assertTrue(self.command(h,action='heal-direction')['watchdog'])

    def test_capacity_isolation_needs_completed_initial_direction_and_fixed_target(self):
        h=self.handler('minority-capacity')
        with self.assertRaises(ValueError):self.command(h,action='isolate',node='node-3')
        h.recovery.direction_healed=True
        with self.assertRaises(ValueError):self.command(h,action='isolate',node='node-1')
        with patch.object(recovery.threading,'Timer') as timer:
            result=self.command(h,action='isolate',node='node-3');self.assertEqual(60,timer.call_args.args[0])
            self.assertTrue(all('node-3' in row.split()[:2] for row in result['rules']))
            self.assertFalse(self.command(h,action='heal')['watchdog'])
            with self.assertRaises(ValueError):self.command(h,action='isolate',node='node-3')

    def test_recovery_actions_reject_native_execution_and_arbitrary_inputs(self):
        h=self.handler('group-restart');h.s.config['execution']=cloud_guest.NATIVE_EXECUTION
        with self.assertRaisesRegex(ValueError,'not admitted natively'):self.command(h,action='observe-recovery')
        h.s.config['execution']=cloud_guest.EXECUTION
        for values in (dict(action='observe-recovery',path='/tmp'),dict(action='arm-cut'),dict(action='start-target',intentId='call-01'),
                       dict(action='isolate',node='node-1',seconds=70)):
            with self.assertRaises(ValueError):self.command(h,**values)

    def test_failed_retained_stop_is_consumed_before_a_second_attempt(self):
        cell=drill.Cell(SimpleNamespace(clients=[(1,None,{})],provider=SimpleNamespace(req={})),self.root/'cell','group-restart')
        cell.end=time.monotonic()+30;cell.succeeded=Mock(side_effect=ConnectionError('lost close'))
        with self.assertRaises(ConnectionError):cell.retained_stop('node-1')
        with self.assertRaisesRegex(ValueError,'consumed'):cell.retained_stop('node-1')
        cell.succeeded.assert_called_once()


class DisconnectedJvmTest(unittest.TestCase):
    def test_sigkill_retains_unresolved_original_invocation(self):
        with tempfile.TemporaryDirectory() as temp:
            v=object.__new__(jvm.Jvm);v.root=Path(temp);v.node='node-1';v.prefix='node-1-g1';v.generation=1
            v.identity=dict(pid=1,node=v.node,generation=1);v.closed=False;v.deadline=time.monotonic()+10
            v.rows=[dict(request=dict(kind='addAll',opId='op-1'),startNanos=1,outcome='PENDING')]
            v.proc=Mock(returncode=-9);v.proc.poll.return_value=-9;v.reader=Mock();v.reader.is_alive.return_value=False;v.streams_close=Mock()
            with patch.object(jvm.public_trace,'finish'):v.stop(True)
            row=c.read(v.root/(v.prefix+'-exchanges.json'))[0]
            self.assertEqual('PENDING',row['outcome']);self.assertGreater(row['disconnectNanos'],row['startNanos'])
            self.assertNotIn('response',row);self.assertNotIn('failure',row)
            v.proc.stdin.write.assert_not_called()


if __name__=='__main__':unittest.main()
