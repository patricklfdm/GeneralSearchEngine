"""Fixed fault controls, consumed claims, bounded holds and partial admission."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
from . import cloud_guest, cloud_fake, remote_command as c, guest_owned_faults
from . import guest_fault_network as controls, guest_fault_service as service
from . import guest_owned_network as network, guest_fault_evidence as evidence
from .test_guest_service import config
from . import test_guest_owned_workload as common


class NetworkHandlerTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.jvm=Mock(closed=False)
    def handler(self, case):
        cfg=dict(config(self.root),faultCell=case)
        return service.Handler(SimpleNamespace(config=cfg,cell=self.root,node='node-1',jvm=self.jvm))
    def call(self, handler, **payload): return handler.handle('fault',payload,lambda:None)

    def test_new_cases_are_offline_only_and_never_change_complete_experiment(self):
        for case in controls.CASES:
            cfg=dict(config(self.root),faultCell=case);cloud_guest.validate(cfg)
            with self.assertRaisesRegex(ValueError,'fault cell'):cloud_guest.validate(dict(cfg,execution=cloud_guest.NATIVE_EXECUTION))
        self.assertEqual(('leader-loss','maintenance','no-quorum'),service.CASES)
        from .guest_owned_experiment import CELLS
        self.assertEqual(('healthy','leader-loss','maintenance','no-quorum'),CELLS)

    def test_asymmetric_directions_do_not_drop_reverse_requests(self):
        for case,barrier in (('asymmetric-requests','BEFORE_REQUEST_WRITE'),('asymmetric-responses','AFTER_RESPONSE_READ')):
            self.assertEqual([f'node-2 node-1 {barrier} *',f'node-2 node-3 {barrier} *'],controls.rules(case,'node-2'))
        isolated=controls.rules('isolated-old-leader','node-2')
        self.assertEqual(4,len(isolated));self.assertNotIn('node-1 node-3 BEFORE_REQUEST_WRITE *',isolated)

    def test_injection_cannot_supply_rules_duration_target_path_or_rearm(self):
        handler=self.handler('asymmetric-requests')
        for value in (dict(action='isolate'),dict(action='isolate',node='node-4'),
                      dict(action='isolate',node='node-1',seconds=16),dict(action='isolate',node='node-1',rules=[]),
                      dict(action='observe-network',path='/tmp')):
            with self.assertRaises(ValueError):self.call(handler,**value)
        with patch.object(controls.threading,'Timer') as timer:
            first=self.call(handler,action='isolate',node='node-1')
            self.assertEqual(17,timer.call_args.args[0])
            healed=self.call(handler,action='heal');self.assertFalse(healed['watchdog'])
            self.assertEqual(first['rules'],healed['rules'])
            with self.assertRaises(ValueError):self.call(handler,action='isolate',node='node-1')
            self.assertEqual(healed,self.call(handler,action='heal'))
            timer.assert_called_once()

    def test_consumed_claim_survives_lost_injection_response(self):
        handler=self.handler('asymmetric-responses')
        with patch.object(handler,'rules',side_effect=OSError('uncertain local write')):
            with self.assertRaises(OSError):self.call(handler,action='isolate',node='node-1')
        with self.assertRaises(ValueError):self.call(handler,action='isolate',node='node-1')
        self.assertEqual(dict(action='isolate',node='node-1'),c.read(self.root/'network-injection-claim.json'))

    def test_watchdog_release_stays_distinguishable_from_controller_release(self):
        handler=self.handler('isolated-old-leader')
        with patch.object(controls.threading,'Timer') as timer:
            self.call(handler,action='isolate',node='node-1');timer.call_args.args[1]()
            result=self.call(handler,action='heal');self.assertTrue(result['watchdog'])
            self.assertEqual('\n',(self.root/'network-rules.txt').read_text())

    def test_slow_force_has_fixed_delay_one_target_and_releases_on_shutdown(self):
        handler=self.handler('slow-follower')
        with self.assertRaises(ValueError):self.call(handler,action='isolate',node='node-2')
        with patch.object(controls.threading,'Timer'):
            receipt=self.call(handler,action='isolate',node='node-1')
            self.assertEqual(1500,receipt['delayMillis']);self.assertTrue((self.root/'node-1-slow-force').exists())
            handler.heal();self.assertFalse((self.root/'node-1-slow-force').exists())
            with self.assertRaises(ValueError):self.call(handler,action='isolate',node='node-1')

    def test_lost_public_reply_never_replays_and_faults_never_allow_sigkill(self):
        handler=self.handler('slow-follower');self.jvm.command.side_effect=ConnectionError('lost')
        with self.assertRaises(ConnectionError):self.call(handler,action='call',kind='read',intentId='call-01')
        with self.assertRaises(FileExistsError):self.call(handler,action='call',kind='read',intentId='call-01')
        self.jvm.command.assert_called_once()
        with self.assertRaisesRegex(ValueError,'kill scope'):handler.handle('stop-voter',dict(forced=True),lambda:None)
        self.jvm.stop.assert_not_called()

    def test_asymmetric_leader_fallback_requires_completed_heal(self):
        clock=cloud_fake.Clock()
        cell=guest_owned_faults.Cell(SimpleNamespace(clients=[],provider=SimpleNamespace(req={})),self.root/'cell','asymmetric-requests',clock=clock.seconds,sleep=clock.sleep)
        cell.end=clock.seconds()+20;cell.running={'node-1':None};cell.status=Mock(return_value={'state':'LEADER_READY'})
        with self.assertRaisesRegex(ValueError,'activation deadline'):cell.leader(clock.seconds()+.1,exclude=('node-1',))
        cell.status.assert_not_called();cell.network_healed=True
        self.assertEqual('node-1',cell.leader(cell.end,exclude=('node-1',)))

    def test_partial_cell_list_cannot_qualify_network_aggregate(self):
        req,_,_=cloud_fake.fixture();c.write_once(self.root/'plan.json',dict(scope=network.SCOPE,request=req))
        with self.assertRaisesRegex(ValueError,'aggregate scope'):
            evidence.validate(self.root,self.root/'replay',cases=network.CASES[:3],scope=network.SCOPE)


class NetworkRunnerTest(common.RunnerWorkloadTest):
    def setUp(self):
        super().setUp();self.probe.mode=network.MODE;self.probe.scope=network.SCOPE
        self.probe.collect_validate.return_value.update(mode=network.MODE,scope=network.SCOPE,cells=list(network.CASES))
    def test_partial_scope_runs_only_healthy_and_preserves_cleanup_and_charge(self):
        result=self.run_case();self.assertEqual('PASS',result['status'],result['errors'])
        self.assertEqual(list(network.CASES),[v.args[0] for v in self.probe.cell.call_args_list])
        self.assertFalse(result['fullRemoteQualification']);self.assertTrue(result['leaseReleased'])
    def test_three_cells_cannot_replace_complete_network_slice(self):
        self.probe.collect_validate.return_value['cells']=list(network.CASES[:3])
        self.assertEqual('FAIL',self.run_case()['status'])


class NetworkCommandTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.member=(1,Mock(),{})
        self.cell=network.Cell(SimpleNamespace(clients=[self.member],provider=SimpleNamespace(req={})),Path(self.temp.name)/'cell','asymmetric-responses')

    def test_heal_waits_for_original_observation_without_resubmission(self):
        entered=threading.Event();release=threading.Event();attempted=threading.Event();errors=[];seen=[]
        deadline=time.monotonic()+5
        def execute(cell,member,name,payload,end):
            seen.append((payload['action'],end))
            if payload['action']=='status':
                entered.set()
                if not release.wait(3):raise AssertionError('test release timeout')
            return {'state':'SUCCEEDED'}
        def run(action):
            try:
                if action=='heal':attempted.set()
                self.cell.execute(self.member,'fault',dict(action=action),deadline)
            except BaseException as error:errors.append(error)
        with patch.object(guest_owned_faults.Cell,'execute',execute):
            first=threading.Thread(target=run,args=('status',));second=threading.Thread(target=run,args=('heal',))
            first.start()
            try:
                self.assertTrue(entered.wait(2));second.start();self.assertTrue(attempted.wait(2))
                self.assertEqual([('status',deadline)],seen)
            finally:
                release.set();first.join(3)
                if second.ident is not None:second.join(3)
        self.assertFalse(first.is_alive() or second.is_alive());self.assertEqual([],errors)
        self.assertEqual([('status',deadline),('heal',deadline)],seen)

    def test_admission_timeout_does_not_submit_or_renew_deadline(self):
        lock=self.cell.command_locks[1];lock.acquire()
        try:
            with patch.object(guest_owned_faults.Cell,'execute') as execute:
                with self.assertRaisesRegex(ValueError,'admission deadline'):
                    self.cell.execute(self.member,'fault',dict(action='heal'),time.monotonic()+.01)
                execute.assert_not_called()
        finally:lock.release()

    def test_failure_releases_local_admission_without_replaying_command(self):
        with patch.object(guest_owned_faults.Cell,'execute',side_effect=[ValueError('uncertain'),{'state':'SUCCEEDED'}]) as execute:
            with self.assertRaisesRegex(ValueError,'uncertain'):
                self.cell.execute(self.member,'fault',dict(action='status'),time.monotonic()+1)
            self.assertEqual({'state':'SUCCEEDED'},self.cell.execute(self.member,'fault',dict(action='heal'),time.monotonic()+1))
            self.assertEqual(['status','heal'],[call.args[2]['action'] for call in execute.call_args_list])


if __name__=='__main__':unittest.main()
