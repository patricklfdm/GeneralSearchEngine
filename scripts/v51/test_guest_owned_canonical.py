"""Complete offline canonical boundaries; synthetic fixtures are not cloud evidence."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import uuid
from unittest.mock import Mock, patch
from . import guest_owned_canonical as run, guest_canonical_evidence as evidence
from . import cloud_package as package, cloud_fake, cloud_guest as guest, guest_bootstrap as boot
from . import performance_model as m, remote_command as c, guest_workload_spec as workload
from . import guest_shared_source, performance_plan
from .test_guest_service import config
from .test_guest_backup import payloads
from . import test_guest_canonical_workload as tapes, test_guest_owned_three_mode as shared_tests
from . import test_guest_owned_workload as common


class PlacementTest(unittest.TestCase):
    def test_exact_control_nodes_and_unique_directories_without_relabeling_automatic_leader(self):
        roots=set()
        for member in (1,2,3):
            for mode,cell in run.TAPES:
                cfg=config(Path('/tmp/canonical-test'));cfg.update(mode=mode,workload=dict(cell=cell,preset='canonical',repetition=member))
                guest.validate(cfg)
                self.assertEqual(package.control_node(cfg),'node-'+str(member))
                self.assertEqual(package.service_nodes(cfg),(member,) if mode==package.MODES[0] else (1,2,3))
                roots.add(package.bootstrap_directory_name(cfg))
                self.assertEqual(boot.topology_values(cfg).get('control-node.txt'),('node-'+str(member)+'\n') if mode==package.MODES[1] else None)
        self.assertEqual(len(roots),15)

    def test_bad_repetition_and_native_admission_stay_closed(self):
        cfg=config(Path('/tmp/canonical-test'));cfg['workload']=dict(cell='healthy',preset='canonical',repetition=1)
        for member in (0,4,True,False,'2',None):
            cfg['workload']['repetition']=member
            with self.subTest(member=member),self.assertRaises(ValueError):guest.validate(cfg)
        cfg['workload']['repetition']=1;cfg['execution']=guest.NATIVE_EXECUTION
        with self.assertRaises(ValueError):guest.validate(cfg)

    def test_ci_requires_exact_three_repetitions(self):
        from . import cloud_ci
        text=(Path(__file__).resolve().parents[2]/'.github/workflows/ci.yml').read_text()
        names=cloud_ci.expected_jobs(text)
        for n in (1,2,3):self.assertIn(f'V5.1 owned canonical (repetition {n}, no GCP)',names)
        for value in ('[1, 2]','[1, 2, 2]','[3, 2, 1]','[1, 2, 3]\n        extra: [unknown]'):
            with self.assertRaisesRegex(ValueError,'repetition matrix changed'):
                cloud_ci.expected_jobs(text.replace('repetition: [1, 2, 3]','repetition: '+value))


class ReceiverRotationTest(unittest.TestCase):
    setUp=tapes.CanonicalDeliveryTest.setUp
    new_attempt=tapes.CanonicalDeliveryTest.new_attempt
    selected=tapes.CanonicalDeliveryTest.selected
    invoke=tapes.CanonicalDeliveryTest.invoke
    producer_request=tapes.CanonicalDeliveryTest.producer_request
    exported=tapes.CanonicalDeliveryTest.exported

    def test_rotated_producers_and_five_transfers_share_each_attempt_without_claim_collision(self):
        from . import guest_source_transfer as wire
        for repetition in (2,3):
            self.new_attempt(node=repetition)
            local=self.selected(package.MODES[0],'healthy',repetition)
            self.assertEqual(self.invoke('producer','query',self.producer_request(local))['state'],'NOT_FOUND')
            for mode,cell in run.TAPES:
                with self.subTest(repetition=repetition,mode=mode,cell=cell):
                    cfg=self.selected(mode,cell,repetition);folder,digest=self.exported(cfg);request=wire.describe(folder,digest,cfg)
                    self.assertEqual(self.invoke('source','begin',request)['state'],'RECEIVING')
                    for part in request['chunks']:
                        with (folder/'parts'/part['part']).open('rb') as stream:
                            stream.seek(part['offset']);raw=stream.read(part['bytes'])
                        self.invoke('source','chunk',request,raw,part['index'])
                    self.assertEqual(self.invoke('source','finish',request)['state'],'SUCCEEDED')
                    folder.rename(folder.with_name(folder.name+'-hidden'))
                    install=dict(config=cfg,descriptorSha256=digest,sourceTransferSha256=m.sha(m.canonical(request)))
                    self.assertEqual(self.invoke('bootstrap','install',install)['state'],'SUCCEEDED')
                    self.assertEqual(self.invoke('bootstrap','query-install',install)['state'],'SUCCEEDED')
            wrong=deepcopy(local);wrong['workload']['repetition']=1;wrong['root']=str(self.parent/package.bootstrap_directory_name(wrong))
            self.invoke('producer','query',self.producer_request(wrong),reject='configuration')


class SharedSourceTest(unittest.TestCase):
    setUp=shared_tests.SourceTest.setUp
    def configs(self,mode,cell,member):
        cfg=deepcopy(self.initial);cfg.update(mode=mode,workload=dict(cell=cell,preset='canonical',repetition=member))
        label=package.bootstrap_directory_name(cfg)
        cfg.update(root=str(self.root/label),groupId=str(uuid.uuid5(uuid.NAMESPACE_URL,label)))
        return [dict(cfg,binding=dict(cfg['binding'],node='node-'+str(n))) for n in package.service_nodes(cfg)]
    def produce(self,configs,deadline,*,endpoint,output):
        output.mkdir();raw=output.absolute()/'seed';raw.mkdir();(raw/'source').mkdir()
        for name,data in self.backup.items():(raw/'source'/name).write_bytes(data)
        cfg=configs[0]
        for name,text in boot.topology_values(cfg).items():(raw/name).write_text(text)
        folder=output/cfg['binding']['node'];row=boot.export(raw,folder,cfg,producer_config=dict(cfg,root=str(raw)))
        return [dict(row,folder=str(folder))]
    def start(self,member):
        self.shared=run.Source(self.root/('shared-'+str(member)),member,clock=self.clock.seconds,sleep=self.clock.sleep)
        self.remote=Mock(side_effect=self.produce);self.shared.remote.prepare=self.remote
    def prepare(self,mode,cell,member):
        return guest_shared_source.Source(self.shared).prepare(self.configs(mode,cell,member),self.deadline,endpoint=object(),
            output=self.root/(str(member)+'-'+run.key(mode,cell)))
    def test_one_real_backup_seed_for_thirteen_receivers_per_repetition(self):
        for member in (1,2,3):
            self.start(member);inventories=[]
            for mode,cell in run.TAPES:
                for row in self.prepare(mode,cell,member):
                    value=c.read(Path(row['folder'])/'bootstrap.json')
                    inventories.append({k:v for k,v in value['files'].items() if k.startswith('source/')})
            self.remote.assert_called_once();self.assertEqual(self.remote.call_args.args[0][0]['binding']['node'],'node-'+str(member))
            self.assertEqual(len(inventories),13);self.assertTrue(all(v==inventories[0] for v in inventories))
    def test_mix_order_duplicate_and_changed_seed_fail_without_producing_again(self):
        self.start(2)
        with self.assertRaisesRegex(ValueError,'order'):self.prepare(*run.TAPES[1],2)
        self.prepare(*run.TAPES[0],2)
        with self.assertRaisesRegex(ValueError,'consumed'):self.prepare(*run.TAPES[0],2)
        with self.assertRaisesRegex(ValueError,'repetition'):self.prepare(*run.TAPES[1],3)
        (self.shared.root/'seed/source'/boot.SOURCE[0]).write_bytes(b'changed')
        with self.assertRaises(ValueError):self.prepare(*run.TAPES[1],2)
        self.remote.assert_called_once()


class RotatedOwnedServiceTest(unittest.TestCase):
    def test_startup_readiness_retention_and_cleanup_use_actual_physical_node(self):
        from .test_guest_owned_services import OwnedServiceTest
        for member in (2,3):
            fixture=OwnedServiceTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
            services=fixture.services;services.mode=package.MODES[0];services.canonical_cell='healthy';services.canonical_repetition=member
            def prepare(req,configs,endpoints,output,deadline,*,recheck):
                self.assertEqual([v['binding']['node'] for v in configs],['node-'+str(member)])
                self.assertEqual([v.value['binding']['node'] for v in endpoints],['node-'+str(member)])
                output.mkdir();recheck(0,'produced')
                return dict(status='PASS',publicBootstrapVerified=True)
            services.bootstrap=SimpleNamespace(prepare=prepare,source=SimpleNamespace(scope='authenticated-shared-source'),
                retention_files=lambda:iter(()))
            result=fixture.run_owned();self.assertEqual(result['status'],'PASS',result['errors']);fixture.assert_clean(result)
            self.assertEqual([n for n,_,_ in services.clients],[member])
            self.assertIn((member,'start'),fixture.events)
            retained={k.rsplit('/startup/',1)[-1] for k in fixture.http.objects if '/startup/' in k}
            self.assertIn(f'services/node-{member}-check-produced.json',retained)
            self.assertNotIn('services/node-1-check-produced.json',retained)


class CompleteRunnerTest(common.RunnerWorkloadTest):
    def setUp(self):
        super().setUp();self.probe.mode=run.MODE;self.probe.scope=run.SCOPE;self.probe.repetition=2
        self.probe.collect_validate.return_value.update(mode=run.MODE,scope=run.SCOPE,cells=list(run.CELLS))
    def test_partial_scope_runs_only_healthy_and_preserves_cleanup_and_charge(self):
        result=self.run_case();self.assertEqual(result['status'],'PASS',result['errors'])
        self.assertEqual([v.args[0] for v in self.probe.cell.call_args_list],list(run.CELLS))
        self.assertTrue(result['leaseReleased']);self.assertFalse(result['fullRemoteQualification']);self.assertFalse(self.provider.objects)
        self.assertEqual(result['budgetProfile'],'offline-owned-canonical-v1')
    def test_component_success_cannot_close_complete_scope(self):
        self.probe.collect_validate.return_value['cells']=['healthy']
        self.assertEqual(self.run_case()['status'],'FAIL')

    def test_validation_overrun_uses_cleanup_reserve_for_one_shutdown_and_retains_failure(self):
        report=deepcopy(self.probe.collect_validate.return_value)
        def replay(output,deadline):
            self.clock.sleep(2401);return report
        def close(deadline):
            self.assertGreater(deadline,self.clock.nanos())
            self.clock.sleep(2)
        self.probe.collect_validate.side_effect=replay;self.startup.stop.side_effect=close
        self.startup.retention_files.return_value=[('stop.json',b'original stop evidence')]
        result=self.run_case()
        self.assertEqual(result['status'],'FAIL');self.assertEqual(result['budget']['status'],'FAIL')
        self.assertEqual(result['cleanup']['status'],'PASS');self.assertFalse(self.provider.objects)
        self.startup.stop.assert_called_once();self.startup.retention_files.assert_called_once()
        self.probe.retention_files.assert_not_called();self.assertFalse(result['leaseReleased'])
        self.assertTrue(any(e['phase']=='retention' for e in result['errors']))
        self.assertFalse(any(e['phase']=='guest-stop' for e in result['errors']))
        self.assertTrue(any(key.endswith('/startup/stop.json') for key in self.store.objects))

    def test_old_replay_overrun_fits_reviewed_complete_validation_budget(self):
        report=deepcopy(self.probe.collect_validate.return_value)
        def replay(output,deadline):
            self.assertEqual(deadline-self.clock.nanos(),2400*10**9)
            self.clock.sleep(1600);return report
        self.probe.collect_validate.side_effect=replay
        result=self.run_case()
        self.assertEqual(result['status'],'PASS',result['errors'])
        self.assertEqual(result['budget']['spentNanos']['validation-retention'],1600*10**9)


class CompleteCollectionTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.clock=cloud_fake.Clock();req,_,_=cloud_fake.fixture();self.events=[]
        services=Mock(offline=True,mode=run.MODE,repetition=1,provider=SimpleNamespace(req=req))
        services.stop.side_effect=lambda deadline:self.events.append('services-stopped')
        self.probe=run.Probe(services,self.root/'probe',clock=self.clock.seconds,sleep=self.clock.sleep)
        self.probe.prepared=True;self.probe.cells=list(run.CELLS);self.probe.stopped=True
        for mode,cell in run.TAPES:
            name=run.key(mode,cell);raw=self.root/name;raw.mkdir()
            def collect(deadline,name=name):self.events.append(name);return [],[object()]
            self.probe.probes[name]=Mock(raw=raw,nodes=(1,),collect=collect,engineWorkloadExecuted=True)
        for case in run.drill.CASES:
            def collect(deadline,case=case):self.events.append(case);return []
            self.probe.programs[case]=Mock(collect=collect,attempted=True)
    def test_collect_once_close_services_then_replay_all_originals_once(self):
        def replay(*args,**kwargs):
            self.assertEqual(self.events[-1],'services-stopped');return dict(status='PASS',calls=1080)
        with patch.object(evidence,'bounded_replay',side_effect=replay) as aggregate:
            result=self.probe.collect_validate(self.root,self.clock.nanos()+600*10**9)
        self.assertEqual(result['status'],'PASS');aggregate.assert_called_once()
        self.assertEqual(aggregate.call_args.args[2],self.clock.seconds()+480)
        self.assertEqual(self.events,[run.key(*v) for v in run.TAPES]+list(run.drill.CASES)+['services-stopped'])
        for probe in self.probe.probes.values():probe.collect_validate.assert_not_called()
    def test_partial_collection_cannot_accept_cached_pass(self):
        self.probe.probes[run.key(*run.TAPES[0])].collect=lambda deadline:([dict(message='original part corrupt')],[])
        with patch.object(evidence,'bounded_replay') as aggregate:
            result=self.probe.collect_validate(self.root,self.clock.nanos()+600*10**9)
        aggregate.assert_not_called();self.assertEqual(result['status'],'FAIL')
        self.probe.services.stop.assert_called_once()
        self.assertTrue(any(e.get('message')=='original part corrupt' for e in result['errors']))
    def test_failed_replay_stays_failed_with_all_raw_inputs_retained(self):
        with patch.object(evidence,'bounded_replay',side_effect=ValueError('owned canonical replay deadline')):
            result=self.probe.collect_validate(self.root,self.clock.nanos()+600*10**9)
        self.assertEqual(result['status'],'FAIL');self.assertFalse(result['physicalHistoryQualified'])
        self.assertEqual(result['errors'],[dict(phase='aggregate',message='owned canonical replay deadline')])
        self.assertTrue(all((self.probe.raw/run.key(*v)).is_dir() for v in run.TAPES))
    def test_failed_service_stop_prevents_replay_and_does_not_hide_collection(self):
        self.probe.services.stop.side_effect=ValueError('original shutdown failed')
        with patch.object(evidence,'bounded_replay') as aggregate:
            result=self.probe.collect_validate(self.root,self.clock.nanos()+600*10**9)
        self.probe.services.stop.assert_called_once();aggregate.assert_not_called()
        self.assertEqual(result['status'],'FAIL')
        self.assertEqual(result['errors'],[dict(phase='aggregate',message='original shutdown failed')])


class BoundedReplayTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def test_real_child_timeout_is_killed_reaped_and_never_retried(self):
        import os,subprocess,sys,time
        pidfile=self.root/'pid';original=subprocess.run
        def child(command,**kwargs):
            return original([sys.executable,'-c',
                'import os,pathlib,sys,time; pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(60)',str(pidfile)],**kwargs)
        with patch.object(evidence.subprocess,'run',side_effect=child) as spawn:
            with self.assertRaisesRegex(ValueError,'replay deadline'):
                evidence.bounded_replay(self.root,self.root/'replay',time.monotonic()+1)
        spawn.assert_called_once()
        with self.assertRaises(ProcessLookupError):os.kill(int(pidfile.read_text()),0)
        self.assertFalse((self.root/'replay-result.json').exists());self.assertTrue((self.root/'replay-stderr.log').exists())
    def test_expired_deadline_does_not_launch_and_timeout_cannot_restart(self):
        with patch.object(evidence.subprocess,'run') as spawn:
            with self.assertRaisesRegex(ValueError,'replay deadline'):
                evidence.bounded_replay(self.root,self.root/'expired',0,clock=lambda:1)
            spawn.assert_not_called()
        (self.root/'replay-stderr.log').write_text('original failure')
        with patch.object(evidence.subprocess,'run') as spawn:
            with self.assertRaises(FileExistsError):evidence.bounded_replay(self.root,self.root/'replay',10,clock=lambda:1)
            spawn.assert_not_called()
    def test_child_error_preserves_diagnostic_and_cannot_use_result(self):
        import subprocess,sys,time
        original=subprocess.run
        def child(command,**kwargs):return original([sys.executable,'-c','raise ValueError("original evidence invalid")'],**kwargs)
        with patch.object(evidence.subprocess,'run',side_effect=child):
            with self.assertRaisesRegex(ValueError,'original evidence invalid'):
                evidence.bounded_replay(self.root,self.root/'replay',time.monotonic()+10)
    def test_late_success_receipt_cannot_override_deadline_or_be_reused(self):
        def child(command,**kwargs):
            c.write_once(self.root/'replay-result.json',dict(status='PASS'));return SimpleNamespace(returncode=0)
        with patch.object(evidence.subprocess,'run',side_effect=child):
            with self.assertRaisesRegex(ValueError,'replay deadline'):
                evidence.bounded_replay(self.root,self.root/'replay',10,clock=Mock(side_effect=(1,11)))
        with patch.object(evidence.subprocess,'run') as spawn:
            with self.assertRaisesRegex(ValueError,'replay consumed'):
                evidence.bounded_replay(self.root,self.root/'replay',100,clock=lambda:20)
            spawn.assert_not_called()


class HandoffTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.clock=cloud_fake.Clock();req,_,_=cloud_fake.fixture()
        services=SimpleNamespace(offline=True,mode=run.MODE,repetition=3,provider=SimpleNamespace(req=req))
        self.probe=run.Probe(services,self.root/'probe',clock=self.clock.seconds,sleep=self.clock.sleep)
        self.events=[];self.failed=None;self.slow=None
        for mode,cell in run.TAPES:
            name=run.key(mode,cell)
            def execute(cell,deadline,name=name):self.events.append((name,'start'));self.clock.sleep(290 if self.slow==name else 1)
            def close(deadline,name=name):self.events.append((name,'close'));self.clock.sleep(20 if self.slow==name else 1);return ['failed'] if self.failed==name else []
            self.probe.probes[name]=Mock(cell=execute,close_voters=close,engineWorkloadExecuted=True)
        for case in run.drill.CASES:
            self.probe.programs[case]=Mock(run=lambda deadline,case=case:(self.events.append((case,'fault')),self.clock.sleep(1)))
        self.probe.prepared=True
    def test_all_cells_sequential_and_complete_close_before_next_tape(self):
        for cell in run.CELLS:self.probe.cell(cell,self.clock.nanos()+900*10**9)
        self.assertEqual(self.probe.cells,list(run.CELLS))
        self.assertEqual(self.events,[(run.key(mode,cell),act) for mode,cell in run.TAPES for act in ('start','close')]+[(case,'fault') for case in run.drill.CASES])
        with self.assertRaisesRegex(ValueError,'consumed/order'):self.probe.cell('healthy',self.clock.nanos()+900*10**9)
    def test_failed_close_is_terminal_and_later_modes_never_start(self):
        self.failed=run.key(*run.TAPES[0])
        with self.assertRaisesRegex(ValueError,'close/deadline'):self.probe.cell('healthy',self.clock.nanos()+900*10**9)
        self.assertEqual(len(self.events),2);self.assertEqual(self.probe.cells,[])
        self.assertEqual(c.read(self.probe.raw/'healthy-timeline.json')['status'],'FAIL')
        with self.assertRaisesRegex(ValueError,'consumed/order'):self.probe.cell('healthy',self.clock.nanos()+900*10**9)
    def test_close_counts_in_original_mode_ceiling(self):
        self.slow=run.key(*run.TAPES[0])
        with self.assertRaisesRegex(ValueError,'close/deadline'):self.probe.cell('healthy',self.clock.nanos()+900*10**9)
        self.assertEqual(len(self.events),2)


class AggregateAdmissionTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.req,_,_=cloud_fake.fixture();sha=run.a.validate_request(self.req)
        services=dict(scope=run.SCOPE,repetition=2,requestSha256=sha,status='PASS',tapes=[],faults=[])
        start=1
        for cell in run.CELLS:
            selected=[(mode,kind) for mode,kind in run.TAPES if kind==cell]
            row=dict(cell=cell,status='PASS',startNanos=start,endNanos=start+10,tapes=[])
            for i,(mode,kind) in enumerate(selected):
                row['tapes'].append(dict(mode=mode,status='PASS',startNanos=start+i*2,endNanos=start+i*2+1))
            c.write_once(self.root/(cell+'-timeline.json'),row);start+=20
            for mode,kind in selected or [(package.MODES[2],cell)]:
                name=run.key(mode,kind) if selected else cell
                folder=self.root/name;folder.mkdir();cfg=config(Path('/tmp/owned-canonical'))
                cfg.update(mode=mode,packageManifestSha256=m.sha(b'package'))
                if selected:cfg['workload']=dict(cell=cell,preset='canonical',repetition=2)
                else:cfg['faultCell']=cell
                label=package.bootstrap_directory_name(cfg) if selected else cell
                cfg.update(root='/tmp/owned-canonical/'+label,groupId=str(uuid.uuid5(uuid.NAMESPACE_URL,sha+':'+label)))
                configs=[dict(cfg,binding=c.binding(self.req['source'],self.req['bundleSha256'],self.req['attempt'],'node-'+str(n))) for n in package.service_nodes(cfg)]
                scope=workload.scope(mode,kind) if selected else ('owned-network-faults' if cell in run.drill.network.CASES else run.drill.faults.SCOPE)
                local=dict(request=self.req,configs=configs,scope=scope,**(dict(mode=mode) if selected else dict(case=cell)))
                c.write_once(folder/'plan.json',local);(folder/'package-manifest.json').write_bytes(b'package')
                if selected:services['tapes'].append(dict(mode=mode,cell=cell,receipt={}))
                else:services['faults'].append(dict(case=cell,receipt={}))
        c.write_once(self.root/'plan.json',dict(scope=run.SCOPE,repetition=2,request=self.req,services=services))
    def change(self,path,mutate):
        value=c.read(path);mutate(value);path.write_bytes(m.canonical(value))
    def test_exact_fifteen_cells_seventeen_groups(self):self.assertEqual(evidence.admission(self.root)['repetition'],2)
    def test_changed_repetition_package_topology_request_and_fault_genesis_binding(self):
        path=self.root/run.key(*run.TAPES[1])/'plan.json';original=path.read_bytes()
        mutations=[lambda v:v['configs'][0]['workload'].update(repetition=3),lambda v:v['configs'][0].update(packageManifestSha256='0'*64),
            lambda v:v['configs'][0]['hosts'].__setitem__(0,'127.0.0.9'),lambda v:v['request'].update(source='f'*40),
            lambda v:v['configs'][0].update(groupId=str(uuid.uuid4()))]
        for mutate in mutations:
            self.change(path,mutate)
            with self.assertRaises(ValueError):evidence.admission(self.root)
            path.write_bytes(original)
        path=self.root/run.drill.CASES[0]/'plan.json';self.change(path,lambda v:v['configs'][0].update(workload=dict(cell='healthy',preset='canonical',repetition=2)))
        with self.assertRaises(ValueError):evidence.admission(self.root)
    def test_missing_duplicate_reordered_and_overlapping_tapes_rejected(self):
        path=self.root/'healthy-timeline.json';original=path.read_bytes()
        for mutate in (lambda v:v['tapes'].pop(),lambda v:v['tapes'].reverse(),lambda v:v['tapes'].append(v['tapes'][0]),
                       lambda v:v['tapes'][1].update(startNanos=v['tapes'][0]['startNanos']),lambda v:v.update(endNanos=v['startNanos']+901*10**9)):
            self.change(path,mutate)
            with self.assertRaises(ValueError):evidence.admission(self.root)
            path.write_bytes(original)
    def test_old_five_tape_success_and_extra_cell_rejected(self):
        (self.root/'extra-cell').mkdir()
        with self.assertRaisesRegex(ValueError,'extra input'):evidence.admission(self.root)
        (self.root/'extra-cell').rmdir();self.change(self.root/'plan.json',lambda v:v['services']['faults'].pop())
        with self.assertRaisesRegex(ValueError,'complete service set'):evidence.admission(self.root)


class AggregateReplayTest(unittest.TestCase):
    """Real binary packing/original commands; physical oracle calls are isolated mocks."""
    change=AggregateAdmissionTest.change
    def setUp(self):
        AggregateAdmissionTest.setUp(self)
        from . import remote_collection as parts
        self.serial=0;(self.root/'source').mkdir()
        for name,data in payloads(m.initial(performance_plan.load())).items():(self.root/'source'/name).write_bytes(data)
        source=m.sha(m.canonical({'source/'+p.name:dict(bytes=p.stat().st_size,sha256=m.sha(p.read_bytes())) for p in (self.root/'source').iterdir()}))
        plan=c.read(self.root/'plan.json');plan['services']['sourceSha256']=source;sha=run.a.validate_request(self.req)
        start=10**9
        for cell in run.CELLS:
            row=c.read(self.root/(cell+'-timeline.json'));row.update(startNanos=start,endNanos=start+100)
            for i,span in enumerate(row['tapes']):span.update(startNanos=start+i*20,endNanos=start+i*20+10)
            (self.root/(cell+'-timeline.json')).write_bytes(m.canonical(row));start+=200
        for entry in plan['services']['tapes']:
            mode,cell=entry['mode'],entry['cell'];name=run.key(mode,cell);folder=self.root/name
            span=next(v for v in c.read(self.root/(cell+'-timeline.json'))['tapes'] if v['mode']==mode)
            entry['receipt']=dict(status='PASS',requestSha256=sha,bootstrap=dict(status='PASS',publicBootstrapVerified=True,
                identity=dict(sourceSha256=source,manifestSha256=m.sha(b'manifest'),genesisSha256=m.sha(b'genesis'))))
            c.write_once(folder/'cell.json',dict(mode=mode,status='EXECUTED',startedNanos=span['startNanos'],endedNanos=span['endNanos']))
            for cfg in c.read(folder/'plan.json')['configs']:
                node=cfg['binding']['node'];member=folder/node;member.mkdir();transcript=[]
                for j,command in enumerate(('start-voter','stop-voter','collect')):
                    q=c.request(cfg['binding'],uuid.uuid4().hex,command,{})
                    receipt=dict(state='SUCCEEDED',result=dict(stopped=True) if command=='stop-voter' else {})
                    transcript.append(dict(request=q,receipt=receipt));original=folder/'commands'/node[-1]/q['commandId'];original.mkdir(parents=True)
                    c.write_once(original/'request.json',dict(config=cfg,request=q));c.write_once(original/'receipt.json',receipt)
                    c.write_once(original/'observation.json',dict(startNanos=span['startNanos']+j*2,endNanos=span['startNanos']+j*2+1))
                c.write_once(member/'controller.json',dict(config=cfg,active=node=='node-2',packageRoot='/package',transcript=transcript))
                with tempfile.TemporaryDirectory() as temp:
                    data=Path(temp);(data/'events.jsonl').write_bytes(b'{}\n')
                    if mode!=package.MODES[0]:
                        authority=data/'authority'/node;authority.mkdir(parents=True)
                        (authority/'manifest.gsr').write_bytes(b'manifest');(authority/'genesis.gsr').write_bytes(b'genesis')
                    parts.pack(data,member/'parts',m.sha(m.canonical(cfg['binding'])))
        for entry in plan['services']['faults']:
            cell=entry['case'];entry['receipt']=dict(status='PASS',requestSha256=sha)
            span=c.read(self.root/(cell+'-timeline.json'))
            c.write_once(self.root/cell/'receipt.json',dict(startNanos=span['startNanos'],endNanos=span['endNanos']))
        (self.root/'plan.json').write_bytes(m.canonical(plan))
        c.write_once(self.root/'validation.json',dict(status='PASS',cached=True))
    def validate(self,root=None,extra_trace=0):
        root=root or self.root;self.serial+=1;budgets=[]
        def logical(folder,cfg,*args,**kwargs):
            budgets.append(kwargs['trace_budget']);kwargs['trace_budget'][0]-=1+extra_trace
            m.need(kwargs['trace_budget'][0]>=0,'combined decoded trace budget')
            return dict(calls=sum(len(s['calls']) for s in workload.specs(cfg)) if kwargs['active'] else 0)
        def joint(members,manifest,**kwargs):
            reports=[logical(v['root'],v['controller']['config'],active=v['controller']['active'],trace_budget=kwargs['trace_budget']) for v in members]
            return dict(status='PASS',members=reports)
        with patch.object(evidence.guest_evidence,'validate',side_effect=logical) as member, \
             patch.object(evidence.guest_physical_evidence,'validate',side_effect=joint) as physical, \
             patch.object(evidence.guest_three_mode_evidence,'source_binding'), \
             patch.object(evidence.guest_fault_evidence,'replay_case',return_value=dict(status='PASS')) as fault:
            answer=evidence.validate(root,Path(self.temp.name).parent/(Path(self.temp.name).name+'-replay-'+str(self.serial)))
            self.addCleanup(__import__('shutil').rmtree,Path(self.temp.name).parent/(Path(self.temp.name).name+'-replay-'+str(self.serial)))
            self.assertEqual(member.call_count,1);self.assertEqual(physical.call_count,4);self.assertEqual(fault.call_count,12)
            self.assertEqual(len(budgets),13)
            self.assertTrue(all(v is budgets[0] for v in budgets))
            self.assertTrue(all(v.kwargs['trace_budget'] is budgets[0] for v in physical.call_args_list))
            return answer
    def test_complete_binary_archive_is_portable_and_replays_every_original(self):
        from . import remote_collection as parts
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);parts.pack(self.root,tmp/'parts','f'*64);parts.unpack(tmp/'parts',tmp/'relocated','f'*64)
            (tmp/'relocated'/parts.INDEX).unlink()
            answer=self.validate(tmp/'relocated')
            self.assertEqual(answer['calls'],1080);self.assertEqual(len(answer['cells']),15);self.assertFalse(answer['fullRemoteQualification'])
    def test_modified_binary_ignores_cached_pass(self):
        folder=self.root/run.key(*run.TAPES[0])/'node-2/parts'
        part=next(folder.glob('*.bin'));data=part.read_bytes();part.write_bytes(bytes([data[0]^1])+data[1:])
        with self.assertRaisesRegex(ValueError,'part hash'):self.validate()
    def test_changed_seed_and_combined_trace_budget_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'decoded trace budget'):self.validate(extra_trace=evidence.parts.LIMITS['traceBytes']//2)
        (self.root/'source'/boot.SOURCE[0]).write_bytes(b'changed')
        with self.assertRaises(ValueError):self.validate()
    def test_original_close_receipt_and_interval_are_required(self):
        folder=self.root/run.key(*run.TAPES[0]);controller=folder/'node-2/controller.json'
        stop=c.read(controller)['transcript'][1]['request'];path=folder/'commands/2'/stop['commandId']/'observation.json'
        self.change(path,lambda v:v.update(endNanos=900*10**9))
        with self.assertRaisesRegex(ValueError,'outside tape'):self.validate()
    def test_missing_original_fault_receipt_cannot_use_cached_pass(self):
        (self.root/run.drill.CASES[-1]/'receipt.json').unlink()
        with self.assertRaises(FileNotFoundError):self.validate()


if __name__=='__main__':unittest.main()
