"""Complete experiment scope, original pinned calls and aggregate anti-mixing."""
from concurrent.futures import Future
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import io
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from . import guest_owned_experiment as experiment, guest_experiment_evidence as evidence
from . import guest_fault_service as service, guest_fault_jvm as jvm, cloud_fake, cloud_package as package, remote_command as c
from . import test_guest_owned_faults as faults, test_guest_owned_workload as common


class MaintenanceHandlerTest(faults.HandlerTest):
    def test_pin_consumed_before_uncertain_submit(self):
        self.handler.case='maintenance';self.jvm.submit.side_effect=ConnectionError('lost')
        payload=dict(action='pin',intentId='call-05')
        with self.assertRaises(ConnectionError):self.call('fault',payload)
        with self.assertRaises(FileExistsError):self.call('fault',payload)
        self.assertEqual(self.jvm.submit.call_count,1)
    def test_pin_release_cannot_be_replayed_after_uncertain_completion(self):
        self.handler.case='maintenance';future=Future();self.handler.pin=({},future)
        self.jvm.finish.side_effect=ConnectionError('lost')
        with self.assertRaises(ConnectionError):self.call('fault',dict(action='release-pin'))
        with self.assertRaises(FileExistsError):self.call('fault',dict(action='release-pin'))
        self.assertEqual(self.jvm.finish.call_count,1)
    def test_no_pin_outside_maintenance_and_no_arbitrary_cut(self):
        for value in (dict(action='pin',intentId='call-05'),dict(action='pin-state'),dict(action='release-pin')):
            with self.assertRaises(ValueError):self.call('fault',value)
        self.handler.case='maintenance'
        with self.assertRaises(ValueError):self.call('fault',dict(action='pin',intentId='call-05',cut='ACCEPT_BEFORE_WRITE'))
    def test_completed_pin_cannot_claim_overlap(self):
        self.handler.case='maintenance';future=Future();future.set_result({});self.handler.pin=({},future)
        with self.assertRaisesRegex(ValueError,'release state'):self.call('fault',dict(action='release-pin'))
    def test_only_old_leader_edges_are_isolated_and_watchdog_cannot_pass(self):
        self.handler.case='maintenance'
        with patch.object(service.threading,'Timer') as timer:
            result=self.call('fault',dict(action='isolate',node='node-1'))
            self.assertEqual(timer.call_args.args[0],60)
            self.assertEqual(len(result['rules']),4)
            self.assertTrue(all('node-1' in r.split()[:2] for r in result['rules']))
            timer.call_args.args[1]();self.assertTrue(c.read(self.root/'isolation.json')['watchdog'])
    def test_each_guest_installs_the_same_isolated_leader_edges(self):
        self.handler.case='maintenance'
        self.s.node='node-2'
        with patch.object(service.threading,'Timer'):
            result=self.call('fault',dict(action='isolate',node='node-1'))
        self.assertEqual(result['rules'],[r for r in service.RULES if 'node-1' in r.split()[:2]])
        self.assertNotIn('node-2 node-3 BEFORE_REQUEST_WRITE *',result['rules'])
    def test_maintenance_requires_a_named_member_and_rejects_arbitrary_edges(self):
        self.handler.case='maintenance'
        for payload in (dict(action='isolate'),dict(action='isolate',node='node-4'),dict(action='isolate',node='node-1',rules=[])):
            with self.assertRaisesRegex(ValueError,'isolation consumed/scope'):self.call('fault',payload)

    def test_checkpoint_backup_not_available_in_other_faults(self):
        for kind in ('checkpoint','backup'):
            with self.assertRaises(ValueError):self.call('fault',dict(action='call',kind=kind,intentId='call-01'))


class PendingJvmTest(unittest.TestCase):
    def test_pending_read_keeps_original_id_and_does_not_block_status_or_resubmit(self):
        v=object.__new__(jvm.Jvm);v.lock=threading.Lock();v.failed=None;v.closed=False;v.rows=[];v.pending={}
        v.prefix='node-1-g1';v.identity=dict(pid=2);v.deadline=jvm.time.monotonic()+30;v.proc=SimpleNamespace(stdin=io.BytesIO())
        pin=v.submit('read',intentId='call-05');status=v.submit('status')
        self.assertFalse(pin[1].done());status[1].set_result(dict(status[0]['request'],outcome='SUCCESS'))
        self.assertEqual(v.finish(status)['response']['kind'],'status')
        original=v.proc.stdin.getvalue();pin[1].set_result(dict(pin[0]['request'],outcome='SUCCESS',documents=[]))
        result=v.finish(pin)
        self.assertEqual(result['response']['opId'],'node-1-g1-1');self.assertEqual(v.proc.stdin.getvalue(),original)
        self.assertEqual([r['outcome'] for r in v.rows],['SUCCESS','SUCCESS'])


class CompleteRunnerTest(common.RunnerWorkloadTest):
    def setUp(self):
        super().setUp();self.probe.mode=experiment.MODE;self.probe.scope=experiment.SCOPE
        self.probe.collect_validate.return_value.update(mode=experiment.MODE,scope=experiment.SCOPE,cells=list(experiment.CELLS))
    def test_partial_scope_runs_only_healthy_and_preserves_cleanup_and_charge(self):
        result=self.run_case();self.assertEqual(result['status'],'PASS',result['errors'])
        self.assertEqual([v.args[0] for v in self.probe.cell.call_args_list],list(experiment.CELLS))
        self.assertTrue(result['leaseReleased']);self.assertFalse(result['fullRemoteQualification']);self.assertFalse(self.provider.objects)
    def test_healthy_only_receipt_cannot_close_complete_experiment(self):
        self.probe.collect_validate.return_value['cells']=['healthy']
        self.assertEqual(self.run_case()['status'],'FAIL')


class AggregateBindingTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        req,_,_=cloud_fake.fixture();self.req=req;sha=evidence.a.validate_request(req)
        healthy=dict(status='PASS',requestSha256=sha)
        service=dict(status='PASS',requestSha256=sha,healthy=healthy,cells=[dict(case=cell,receipt=dict(status='PASS',requestSha256=sha)) for cell in experiment.FAULTS])
        c.write_once(self.root/'plan.json',dict(scope=experiment.SCOPE,request=req,services=service))
        (self.root/'healthy').mkdir();c.write_once(self.root/'healthy/plan.json',dict(request=req,services=healthy))
        number=0
        for i,cell in enumerate(experiment.CELLS):
            folder=self.root/cell;folder.mkdir(exist_ok=True)
            timing=dict(startNanos=(i+1)*100,endNanos=(i+1)*100+50)
            c.write_once(self.root/(cell+'-timeline.json'),dict(cell=cell,status='PASS',**timing))
            c.write_once(folder/('timeline.json' if cell=='healthy' else 'receipt.json'),timing)
            for group in (package.MODES if cell=='healthy' else (cell,)):
                path=folder/group if cell=='healthy' else folder;path.mkdir(exist_ok=True);number+=1
                c.write_once(path/'plan.json',dict(request=req,configs=[dict(groupId=str(number),packageManifestSha256='b'*64)]))
    def test_exact_four_cells_six_groups_one_request_and_package(self):self.assertEqual(evidence.contract(self.root),self.req)
    def mutate(self,path,fn):
        p=self.root/path;value=c.read(p);fn(value);p.write_bytes(evidence.m.canonical(value))
    def test_mixed_source_request_is_rejected(self):
        self.mutate('maintenance/plan.json',lambda v:v['request'].update(source='d'*40))
        with self.assertRaisesRegex(ValueError,'mixed source'):evidence.contract(self.root)
    def test_reused_group_is_rejected(self):
        self.mutate('maintenance/plan.json',lambda v:v['configs'][0].update(groupId='4'))
        with self.assertRaisesRegex(ValueError,'reused group'):evidence.contract(self.root)
    def test_changed_package_is_rejected(self):
        self.mutate('maintenance/plan.json',lambda v:v['configs'][0].update(packageManifestSha256='c'*64))
        with self.assertRaisesRegex(ValueError,'mixed package'):evidence.contract(self.root)
    def test_overlap_is_rejected(self):
        self.mutate('maintenance-timeline.json',lambda v:v.update(startNanos=110))
        with self.assertRaisesRegex(ValueError,'order/budget'):evidence.contract(self.root)
    def test_expanded_budget_is_rejected(self):
        self.mutate('maintenance-timeline.json',lambda v:v.update(endNanos=v['startNanos']+241*10**9))
        with self.assertRaisesRegex(ValueError,'order/budget'):evidence.contract(self.root)
    def test_extra_cell_is_rejected(self):
        (self.root/'unexpected-cell').mkdir()
        with self.assertRaisesRegex(ValueError,'extra root'):evidence.contract(self.root)
    def test_missing_service_cell_is_rejected(self):
        self.mutate('plan.json',lambda v:v['services']['cells'].pop())
        with self.assertRaisesRegex(ValueError,'service set'):evidence.contract(self.root)
    def test_unobserved_cell_is_rejected(self):
        self.mutate('maintenance/receipt.json',lambda v:v.update(endNanos=1000))
        with self.assertRaisesRegex(ValueError,'original cell interval'):evidence.contract(self.root)


class CompleteCoordinatorTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.req,_,_=cloud_fake.fixture();self.clock=cloud_fake.Clock()
        services=SimpleNamespace(offline=True,mode=experiment.MODE,provider=SimpleNamespace(req=self.req))
        self.probe=experiment.Probe(services,self.root/'probe',clock=self.clock.seconds,sleep=self.clock.sleep)
        self.probe.healthy=Mock(engineWorkloadExecuted=True)
        self.probe.programs={cell:Mock(attempted=True) for cell in experiment.FAULTS}
    def test_complete_schedule_preserves_four_cell_deadlines_without_replay(self):
        deadline=self.clock.nanos()+1000*10**9
        for cell in experiment.CELLS:self.probe.cell(cell,deadline)
        self.probe.healthy.cell.assert_called_once_with('healthy',deadline)
        for program in self.probe.programs.values():program.run.assert_called_once_with(deadline)
        self.assertEqual(self.probe.cells,list(experiment.CELLS))
        with self.assertRaisesRegex(ValueError,'consumed/order'):self.probe.cell('healthy',deadline)
        self.probe.stop();self.probe.healthy.stop.assert_called_once()
    def test_failed_cell_consumes_schedule_and_retains_failed_interval(self):
        deadline=self.clock.nanos()+1000*10**9
        self.probe.cell('healthy',deadline)
        self.probe.programs['leader-loss'].run.side_effect=ConnectionError('uncertain')
        with self.assertRaises(ConnectionError):self.probe.cell('leader-loss',deadline)
        with self.assertRaisesRegex(ValueError,'consumed/order'):self.probe.cell('leader-loss',deadline)
        self.assertEqual(c.read(self.probe.raw/'leader-loss-timeline.json')['status'],'FAIL')
        self.probe.programs['leader-loss'].run.assert_called_once()
        self.probe.programs['maintenance'].run.assert_not_called()
    def test_maintenance_isolates_and_heals_every_independent_receiver(self):
        from .guest_owned_faults import Cell
        members=[(i,None,{}) for i in (1,2,3)]
        cell=Cell(SimpleNamespace(clients=members),self.root/'cell','maintenance',clock=self.clock.seconds,sleep=self.clock.sleep)
        cell.end=self.clock.seconds()+240;cell.record['seedRead']={'documents':[]}
        issued=[]
        def command(member,name,payload,deadline):
            issued.append((member[0],payload))
            if payload['action']=='pin':return {'result':dict(opId='pin',identity=dict(pid=5,generation=1))}
            if payload['action']=='pin-state':return {'result':dict(cut={},installed={},pending=True,unpinned={})}
            if payload['action']=='release-pin':return {'result':dict(response=dict(outcome='SUCCESS',documents=[]))}
            return {'result':{}}
        cell.succeeded=command;cell.wait=Mock(side_effect=[{},dict(pending=True),{}]);cell.progress=Mock(return_value='node-2')
        cell.status=Mock(return_value={'provenIndex':5});cell.rejoin=Mock();cell.leader=Mock(return_value='node-2');cell.call=Mock(return_value={'outcome':'SUCCESS'})
        cell.maintenance('node-1',self.clock.seconds()+60)
        for action in ('isolate','heal'):
            self.assertEqual(sorted(n for n,p in issued if p['action']==action),[1,2,3])
        self.assertTrue(all(p==dict(action='isolate',node='node-1') for _,p in issued if p['action']=='isolate'))
        cell.progress.assert_called_once_with(self.clock.seconds()+60,exclude=('node-1',))

    def test_combined_budget_crosses_limit_even_when_each_cell_fits(self):
        from scripts.v51 import guest_fault_evidence
        with patch.object(evidence,'contract',return_value=self.req),patch.object(evidence.parts,'inventory'),patch.object(evidence.healthy,'validate') as h,patch.object(guest_fault_evidence,'replay_case') as f:
            h.return_value={'budgets':{k:0 for k in ('compressedBytes','expandedBytes','files','traceBytes')}}
            def cell(raw,scratch,req,budgets):
                budgets['traceBytes']+=evidence.parts.LIMITS['traceBytes']//2
                return {'status':'PASS'}
            f.side_effect=cell
            with self.assertRaisesRegex(ValueError,'combined evidence budget'):evidence.validate(self.root,self.root/'replay')
            self.assertEqual(f.call_count,3)


if __name__=='__main__':unittest.main()
