"""Fixed fault controls, consumed claims, bounded holds and partial admission."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import json
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


class NetworkReservationTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.members=[(node,Mock(),{}) for node in (1,2,3)]
        self.cell=network.Cell(SimpleNamespace(clients=self.members,provider=SimpleNamespace(req={})),
            Path(self.temp.name)/'cell','asymmetric-responses')
        self.cell.end=time.monotonic()+5

    def test_original_poll_finishes_before_reservation_and_new_poll_cannot_overtake_heal(self):
        entered=threading.Event();finish=threading.Event();reserved=threading.Event();heal=threading.Event()
        poll_waiting=threading.Event();seen=[];errors=[]
        def execute(cell,member,name,payload,end):
            seen.append(payload['action'])
            if payload['action']=='original':
                entered.set()
                if not finish.wait(3):raise AssertionError('original command stalled')
            return {'state':'SUCCEEDED'}
        def original():self.cell.execute(self.members[0],'fault',dict(action='original'),self.cell.end)
        def release():
            with self.cell.reserve_heal(self.members[:1],self.cell.end):
                reserved.set()
                if not heal.wait(3):raise AssertionError('heal stalled')
                guest_owned_faults.Cell.execute(self.cell,self.members[0],'fault',dict(action='heal'),self.cell.end)
        def poll():
            poll_waiting.set();self.cell.execute(self.members[0],'fault',dict(action='poll'),self.cell.end)
        def run(fn):
            try:fn()
            except BaseException as error:errors.append(error)
        threads=[threading.Thread(target=run,args=(fn,)) for fn in (original,release,poll)]
        with patch.object(guest_owned_faults.Cell,'execute',execute):
            try:
                threads[0].start();self.assertTrue(entered.wait(2));threads[1].start()
                with self.cell.admission:
                    self.assertTrue(self.cell.admission.wait_for(lambda:self.cell.reserved=={1},2))
                threads[2].start();self.assertTrue(poll_waiting.wait(2))
                finish.set();self.assertTrue(reserved.wait(2))
                self.assertEqual(['original'],seen)
                # An unaffected guest remains usable throughout the reservation.
                self.cell.execute(self.members[1],'fault',dict(action='other-guest'),self.cell.end)
            finally:
                finish.set();heal.set()
                for thread in threads:
                    if thread.ident is not None:thread.join(3)
        self.assertFalse(any(t.is_alive() for t in threads));self.assertEqual([],errors)
        self.assertEqual(['original','other-guest','heal','poll'],seen)

    def test_heal_waits_until_original_hold_and_observes_each_command_once(self):
        # Model the CI timing: a queued poll costs ~1.16s and SSH ~1.23s.
        # Reserving at 12s drains that work before 15s instead of after it.
        clock=cloud_fake.Clock();clock.sleep(12-clock.seconds())
        self.cell.clock=clock.seconds;self.cell.end=120
        cancelled=Mock();original_lock=self.cell.command_locks[1]
        draining=Mock(wraps=original_lock)
        def acquire(*,timeout):
            clock.sleep(1.162489220)
            return original_lock.acquire(timeout=timeout)
        draining.acquire.side_effect=acquire;self.cell.command_locks[1]=draining
        def wait(seconds):clock.sleep(seconds);return False
        cancelled.wait.side_effect=wait;seen=[]
        def execute(cell,member,name,payload,end):
            seen.append((member[0],clock.seconds(),end,payload))
            return {'state':'SUCCEEDED'}
        with patch.object(guest_owned_faults.Cell,'execute',execute):
            self.cell.heal_at(self.members,15,cancelled)
        self.assertEqual([(n,15,120,{'action':'heal'}) for n in (1,2,3)],sorted(seen))
        self.assertAlmostEqual(3-1.162489220,cancelled.wait.call_args.args[0]);self.assertTrue(self.cell.network_healed)
        # Measured transport/receipt gap fits after draining early. If the poll
        # drained only at 15s, the same delays would cross the 17s watchdog.
        self.assertLess(15+.2+1.225744524,17)
        self.assertGreater(15+.2+1.162489220+1.225744524,17)
        self.assertEqual(set(),self.cell.reserved)
        self.assertTrue(all(not lock.locked() for lock in self.cell.command_locks.values()))

    def test_scenario_reserves_at_twelve_seconds_with_unchanged_fifteen_second_target(self):
        clock=cloud_fake.Clock();self.cell.clock=clock.seconds;self.cell.end=120
        self.cell.case='asymmetric-requests'
        self.cell.succeeded=Mock(return_value={'result':{}})
        self.cell.status=Mock(return_value={'provenIndex':1});self.cell.running={}
        def released(members,when,cancelled):
            self.assertEqual(13,clock.seconds());self.assertEqual(16,when)
            self.assertEqual(self.members,members);self.cell.network_healed=True
        self.cell.heal_at=Mock(side_effect=released)
        with patch.object(network.threading,'Timer') as timer:
            timer.return_value.is_alive.return_value=False
            def progress(*args,**kwargs):
                delay,release=timer.call_args.args
                clock.sleep(delay);release();return 'node-2'
            self.cell.progress=Mock(side_effect=progress)
            network.scenario(self.cell,'node-1',60)
        self.cell.heal_at.assert_called_once()

    def test_reservation_timeout_releases_partial_locks_and_fails_polling_without_blocking_cleanup(self):
        self.cell.command_locks[2].acquire()
        try:
            with self.assertRaisesRegex(ValueError,'reservation deadline'):
                with self.cell.reserve_heal(self.members,time.monotonic()+.01):self.fail('reservation admitted')
            self.assertFalse(self.cell.command_locks[1].locked());self.assertFalse(self.cell.reserved)
        finally:self.cell.command_locks[2].release()
        with patch.object(guest_owned_faults.Cell,'execute',return_value={'state':'SUCCEEDED'}) as execute:
            with self.assertRaisesRegex(ValueError,'reservation deadline'):
                self.cell.execute(self.members[0],'fault',dict(action='status'),self.cell.end)
            execute.assert_not_called()
            for name in ('stop-voter','collect'):
                self.cell.execute(self.members[0],name,{},self.cell.end)
            self.assertEqual(['stop-voter','collect'],[v.args[1] for v in execute.call_args_list])

    def test_lost_heal_failure_is_not_replayed_and_releases_all_slots(self):
        cancelled=threading.Event()
        with patch.object(guest_owned_faults.Cell,'execute',side_effect=ConnectionError('uncertain original heal')) as execute:
            # Give admission a future instant, and let the wait reach it.
            with self.assertRaisesRegex(ConnectionError,'uncertain original heal'):
                self.cell.heal_at(self.members,time.monotonic()+.01,cancelled)
            self.assertEqual(3,execute.call_count)
            with self.assertRaisesRegex(ValueError,'uncertain original heal'):
                self.cell.execute(self.members[0],'fault',dict(action='status'),self.cell.end)
            self.assertEqual(3,execute.call_count)
        self.assertFalse(self.cell.reserved)
        self.assertTrue(all(not lock.locked() for lock in self.cell.command_locks.values()))

    def test_cancelled_hold_never_submits_early_heal_and_releases_slots(self):
        cancelled=threading.Event();cancelled.set()
        with patch.object(guest_owned_faults.Cell,'execute') as execute:
            self.cell.heal_at(self.members,time.monotonic()+1,cancelled)
            execute.assert_not_called()
        self.assertFalse(self.cell.reserved);self.assertIsNone(self.cell.release_error)
        self.assertNotIn('network-heal-request',[v['event'] for v in self.cell.record['events']])

    def test_poll_admission_deadline_is_not_extended_by_reservation(self):
        with self.cell.reserve_heal(self.members,time.monotonic()+1):
            with patch.object(guest_owned_faults.Cell,'execute') as execute:
                with self.assertRaisesRegex(ValueError,'command admission deadline'):
                    self.cell.execute(self.members[0],'fault',dict(action='status'),time.monotonic()+.01)
                execute.assert_not_called()


class NetworkDiagnosticTest(unittest.TestCase):
    def test_watchdog_and_excessive_hold_remain_failures_with_case_and_node(self):
        from . import guest_network_evidence as validator
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);case='asymmetric-responses';leader='node-2'
            record=dict(case=case,seedLeader=leader,faultStartNanos=0,
                events=[dict(event='network-ready',controllerNanos=10**9),dict(event='network-heal-request',controllerNanos=16*10**9)])
            applied=dict(node=leader,rules=controls.rules(case,leader),appliedNanos=0)
            for watchdog,seconds in ((True,17.002325005),(True,16),(False,17.002325005),(False,14)):
                actual=dict(applied,healedNanos=int(seconds*1e9),watchdog=watchdog)
                (root/'isolation.json').write_text(json.dumps(actual))
                rows={'node-1':[(dict(command='fault',payload=dict(action='isolate',node=leader)),dict(result=applied)),
                                (dict(command='fault',payload=dict(action='heal')),dict(result=actual))]}
                with self.assertRaisesRegex(ValueError,rf'guest hold/watchdog: case={case} node=node-1 .*watchdog={watchdog}'):
                    validator.check(record,[],{},root,rows,{},dict({'node-1':root}),{})

    def test_controller_completion_reports_original_nested_validation_error(self):
        from .guest_owned_qualification import require_completion
        detail='owned network guest hold/watchdog: case=asymmetric-responses node=node-1'
        result=dict(status='FAIL',leaseReleased=True,errors=[dict(phase='retention',message='owned workload qualification failed')],
                    evidence=dict(errors=[dict(phase='validation',message=detail)]))
        with self.assertRaisesRegex(ValueError,detail):require_completion(result,{})
        result.update(status='PASS',errors=[],evidence=None)
        require_completion(result,{})
        for change,resources in (({'leaseReleased':False},{}),({}, {'live-vm':{}})):
            with self.assertRaisesRegex(ValueError,'owned controller completion'):require_completion(dict(result,**change),resources)


if __name__=='__main__':unittest.main()
