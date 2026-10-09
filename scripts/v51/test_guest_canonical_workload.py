"""Synthetic full tapes test accounting, never substitute for physical qualification."""
from copy import deepcopy
import base64
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from . import cloud_guest as guest, cloud_package as package, guest_workload_spec as workload
from . import guest_evidence as evidence, performance_model as m, performance_plan as plan
from . import remote_schedule as schedule, remote_schedule_evidence as scheduling
from .test_guest_evidence import Fixture
from .test_guest_service import config


class TapeFixture(Fixture):
    def __init__(self, root, cell='healthy', mode=package.MODES[2], active=True, serial_apis=False):
        super().__init__(root, mode=mode, active=active)
        self.config['workload'] = dict(cell=cell, preset='canonical')
        self.cell = cell
        self.transcript = self.transcript[:1 if mode == package.MODES[0] else 2]
        self.exchanges = self.exchanges[:0 if mode == package.MODES[0] else 1]
        self.results = self.results[:len(self.exchanges)]
        self.state = m.initial(plan.load())
        now = 2*10**9
        starts = []
        for spec in workload.specs(self.config):
            response = self.exchange('configure', dict(window=spec['window']), now+100, now+200)
            starts.append((now+150, spec['window']))
            if not active:
                self.control('fault', dict(action='configure',window=spec['window']), response, now, now+1000)
                now += spec['durationNanos']+10**9
                continue
            events = []
            window = schedule.WindowState(spec, now+1000, events.append)
            # Deliberately reverse simultaneous pipe dispatch and journal result
            # order. Ordinals still identify the exact four offered lanes.
            calls = spec['calls']
            if cell != 'healthy':
                calls = [c for offset in range(0,len(calls),4) for c in reversed(calls[offset:offset+4])]
            for call in calls:
                when = window.start+call['dueMillis']*10**6
                window.offer(call,when); window.invoke(call['ordinal'],when)
                response = self.exchange('call',call,when+5,when+15)
                before = self.state.sequence; answer = None
                if call['operation'] in m.OP_IDS:
                    self.state.apply(m.OP_IDS[call['operation']],bytes.fromhex(call['payload']))
                else:
                    answer = self.state.answer(call['operation'],call['cycle']) if cell == 'healthy' else []
                response['call'] = dict({k:call[k] for k in ('ordinal','window','cycle','operation','keys','lane')},
                    outcome='SUCCESS',payloadSha256=m.sha(bytes.fromhex(call['payload'])),answer=answer,
                    answerSha256=m.sha(m.canonical(answer)),beforeSequence=before,afterSequence=self.state.sequence,
                    apiStartNanos=when+7+(call['lane'] if cell != 'healthy' else 0),apiEndNanos=when+13)
                if serial_apis:
                    response['call'].update(apiStartNanos=when+7+2*call['lane'],apiEndNanos=when+8+2*call['lane'])
                window.complete(call['ordinal'],when+20,dict(outcome='SUCCESS',opId=response['opId'],resultSha256=m.sha(m.canonical(response))))
            result = window.finish(window.start+spec['durationNanos'])
            self.control('window',dict(cell=cell,preset='canonical',window=spec['window']),
                dict(window=spec['window'],calls=len(calls),validation=scheduling.validate(spec,events,result)),now,result['endedNanos']+100)
            prefix = 'window-'+cell+'-'+spec['window']+'/'
            self.files.update({prefix+'spec.json':m.canonical(spec), prefix+'result.json':m.canonical(result),
                               prefix+'arrivals.jsonl':b''.join(m.canonical(r)+b'\n' for r in events)})
            now = result['endedNanos']+10**9
        if active:
            negative = self.control('collect',{},None,now,now+100)
            negative.pop('result'); negative.update(state='FAILED',error=dict(type='ValueError',message='guest collection requires stopped JVM'))
        self.exchange('close',{},now+200,now+300)
        self.control('stop-voter',dict(forced=False),dict(stopped=True),now+150,now+400)
        self.control('collect',{},None,now+500,now+600)
        self.samples = [self.sample(0,t,'start' if t==0 else 'periodic') for t in range(0,now,10**9)]
        self.samples += [self.sample(0,now+300,'closed')]
        self.samples += [dict(self.sample(0,t,'window-start'),window=name) for t,name in starts]
        self.samples.sort(key=lambda row:row['localNanos'])
        for i,row in enumerate(self.samples,1): row['order']=i
        if cell != 'healthy':
            self.results[1:-1] = reversed(self.results[1:-1])

    def render(self):
        active = self.active
        try:
            self.active = False  # The base fixture's experiment window is absent.
            super().render()
        finally:
            self.active = active

    def validate(self):
        return evidence.validate(self.root,self.config,self.manifest,self.base,self.transcript,active=self.active,healthy=True)


class CanonicalWorkloadTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.serial = 0

    def fixture(self, **kwargs):
        self.serial += 1
        return TapeFixture(self.root/str(self.serial),**kwargs)

    def test_five_frozen_tapes_preserve_calls_durations_and_lanes(self):
        calls,seconds = 0,0
        for mode,cell in workload.CASES:
            cfg = config(self.root); cfg.update(mode=mode,workload=dict(cell=cell,preset='canonical'))
            specs = workload.specs(cfg)
            self.assertEqual(sum(len(s['calls']) for s in specs),260 if cell=='healthy' else 120 if cell=='read-heavy' else 180)
            self.assertTrue(all(s['lanes']==(1 if cell=='healthy' else 4) for s in specs))
            calls += sum(len(s['calls']) for s in specs)
            seconds += sum(s['durationNanos'] for s in specs)//10**9
        self.assertEqual((calls,seconds),(1080,1080))

    def test_expected_sequence_comes_from_selected_frozen_program(self):
        cfg=config(self.root);cfg['mode']=package.MODES[1]
        self.assertEqual(workload.final_state(cfg).sequence,76)
        cfg['workload']=dict(cell='healthy',preset='canonical')
        self.assertEqual(workload.final_state(cfg).sequence,212)
        from . import guest_configured_evidence as configured
        from unittest.mock import patch
        with patch.object(configured,'observations'),patch.object(configured.legacy,'configured_physical') as oracle:
            configured.audit(self.root,[],{}, {},final_sequence=workload.final_state(cfg).sequence)
            self.assertEqual(oracle.call_args.kwargs,dict(final_sequence=212))

    def test_four_scheduled_lanes_cannot_hide_serial_java_execution(self):
        for cell in ('read-heavy','sustained'):
            f=self.fixture(cell=cell,serial_apis=True)
            f.render()
            with self.subTest(cell=cell),self.assertRaisesRegex(ValueError,'real concurrent Java API overlap'):f.validate()

    def test_canonical_keeps_stored_node_bound_and_shared_decoded_budget(self):
        from unittest.mock import patch
        f=self.fixture();f.render()
        limits=deepcopy(evidence.contract.load())
        stored=sum(p.stat().st_size for p in f.root.glob(f.node+'-*.jsonl*'))
        limits['evidence']['perNodePerCellTraceBytes']=stored
        budget=[limits['evidence']['traceBytes']]
        def validate():
            return evidence.validate(f.root,f.config,f.manifest,f.base,f.transcript,active=True,healthy=True,trace_budget=budget)
        with patch.object(evidence.contract,'load',return_value=limits):
            validate();used=limits['evidence']['traceBytes']-budget[0]
            self.assertGreater(used,stored)  # Compressed output is not decoded size.
            budget[0]=used+1;validate()
            with self.assertRaisesRegex(ValueError,'trace'):validate()
            budget[0]=limits['evidence']['traceBytes']
            limits['evidence']['perNodePerCellTraceBytes']=stored-1
            with self.assertRaisesRegex(ValueError,'node/cell trace budget'):validate()

    def test_preflight_requires_exact_reviewed_matrix_and_all_five_job_names(self):
        from . import cloud_ci
        text=(Path(__file__).resolve().parents[2]/'.github/workflows/ci.yml').read_text()
        names=cloud_ci.expected_jobs(text)
        self.assertTrue(all('V5.1 owned canonical tape ('+tape+', no GCP)' in names for tape,_,_ in cloud_ci.CANONICAL_TAPES))
        for before,after in (('tape: v44-healthy','tape: duplicated'),('cell: read-heavy','cell: healthy'),
                             ('mode: published-v5.0-configured','mode: candidate-v5.1-automatic'),
                             ('          - tape: automatic-sustained','        extra: [unreviewed]\n          - tape: automatic-sustained')):
            with self.subTest(before=before),self.assertRaisesRegex(ValueError,'canonical matrix changed'):
                cloud_ci.expected_jobs(text.replace(before,after))

    def test_native_fault_unknown_and_reduced_tapes_cannot_select_canonical(self):
        cfg = config(self.root); cfg['workload']=dict(cell='healthy',preset='canonical')
        guest.validate(cfg)
        for delta in (dict(execution=guest.NATIVE_EXECUTION),dict(faultCell='leader-loss'),
                      dict(workload=dict(cell='healthy',preset='experiment')),dict(workload=dict(cell='missing',preset='canonical')),
                      dict(workload=dict(cell='healthy',preset='canonical',seconds=1)),dict(workload=None)):
            bad=deepcopy(cfg);bad.update(delta)
            with self.subTest(delta=delta),self.assertRaises(ValueError):guest.validate(bad)
        for mode in package.MODES[:2]:
            bad=deepcopy(cfg);bad.update(mode=mode,workload=dict(cell='read-heavy',preset='canonical'))
            with self.assertRaises(ValueError):guest.validate(bad)

    def test_all_healthy_modes_and_passive_members_replay_full_tapes(self):
        for mode,active in [(v,True) for v in package.MODES]+[(v,False) for v in package.MODES[1:]]:
            with self.subTest(mode=mode,active=active):
                f=self.fixture(mode=mode,active=active);f.render();result=f.validate()
                self.assertEqual(result['calls'],260 if active else 0)
                self.assertTrue(result['logicalSemanticsQualified'])
                self.assertFalse(result['fullRemoteQualification'])

    def test_reordered_concurrent_dispatch_is_bound_but_requires_physical_oracle(self):
        for cell in ('read-heavy','sustained'):
            for active in (True,False):
                f=self.fixture(cell=cell,active=active);f.render();result=f.validate()
                self.assertEqual(result['calls'],(120 if cell=='read-heavy' else 180) if active else 0)
                self.assertFalse(result['logicalSemanticsQualified'])
                self.assertFalse(result['physicalHistoryQualified'])

    def test_missing_duplicate_or_changed_concurrent_ordinal_rejected(self):
        for value in (None,1,9999):
            f=self.fixture(cell='sustained')
            call=next(e for e in f.exchanges if e['request'].get('ordinal')==2)
            call['request']['ordinal']=value;f.render()
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'ordinal coverage'):f.validate()

    def test_experiment_cannot_be_relabelled_as_canonical(self):
        from .test_guest_healthy_evidence import HealthyFixture
        f=HealthyFixture(self.root/'relabelled');f.config['workload']=dict(cell='healthy',preset='canonical');f.render()
        with self.assertRaisesRegex(ValueError,'frozen call coverage'):f.validate()

    def test_selected_tape_cannot_execute_another_cell(self):
        service=object.__new__(guest.Service)
        service.config=config(self.root);service.config['workload']=dict(cell='healthy',preset='canonical')
        service.jvm=object();service.ack=__import__('threading').Event();service.shutting_down=False
        with self.assertRaisesRegex(ValueError,'admitted workload'):
            service.handler('window',dict(cell='sustained',preset='canonical',window='sustained'),lambda:None)

    def test_owned_runner_routes_only_selected_cell_and_never_admits_paid_preset(self):
        from .test_guest_owned_workload import RunnerWorkloadTest
        for mode,cell in workload.CASES:
            with self.subTest(mode=mode,cell=cell):
                fixture=RunnerWorkloadTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
                probe=fixture.probe
                probe.scope=workload.scope(mode,cell);probe.mode=mode;probe.cell_name=cell
                probe.require_physical=probe.require_backup=mode in package.MODES[1:]
                result=probe.collect_validate.return_value
                result.update(scope=probe.scope,mode=mode,cells=[cell],
                    physicalHistoryQualified=probe.require_physical,backupRestoreQualified=probe.require_backup)
                completion=fixture.run_case()
                self.assertEqual(completion['status'],'PASS',completion['errors'])
                self.assertEqual(probe.cell.call_count,1);self.assertEqual(probe.cell.call_args.args[0],cell)
                self.assertFalse(completion['fullRemoteQualification'])
                with self.assertRaisesRegex(ValueError,'not a full preset'):
                    fixture.run_case(member='canonical-1',order='canonical-first')

    def test_replicated_owned_tape_cannot_skip_physical_or_backup_checks(self):
        from types import SimpleNamespace
        from . import cloud_fake, guest_owned_workload
        req,_,_=cloud_fake.fixture()
        services=SimpleNamespace(offline=True,mode=package.MODES[2],canonical_cell='sustained',bootstrap=object(),provider=SimpleNamespace(req=req))
        for physical,backup in ((False,False),(True,False),(False,True)):
            with self.subTest(physical=physical,backup=backup),self.assertRaisesRegex(ValueError,'requires physical history'):
                guest_owned_workload.Probe(services,self.root/'rejected',physical=physical,backup=backup)

    def test_backup_requires_selected_complete_tape_and_keeps_once_only_claim(self):
        from .test_guest_backup import BackupLifecycleTest
        from . import guest_backup
        for cell in workload.CELLS:
            f=BackupLifecycleTest();f.setUp();self.addCleanup(f.doCleanups)
            f.service.config.update(execution=guest.EXECUTION,workload=dict(cell=cell,preset='canonical'))
            # Existing reduced healthy evidence must not allow canonical backup.
            with self.assertRaises((ValueError,FileNotFoundError)):guest_backup.create(f.service)
            f.service.jvm.command.assert_not_called()
            for spec in workload.specs(f.service.config):
                path=f.service.root/('window-'+cell+'-'+spec['window'])/'result.json'
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(m.canonical(dict(status='PASS',calls=spec['calls'])))
            guest_backup.create(f.service)
            with self.assertRaises(FileExistsError):guest_backup.create(f.service)
            f.service.jvm.command.assert_called_once_with('backup')


class CanonicalDeliveryTest(unittest.TestCase):
    """Real isolated trusted receiver and package imports; synthetic seed, no JVM."""
    def setUp(self):
        from . import cloud_bundle, cloud_authority
        from .test_cloud_package import fixture, save
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);base=self.root/'package';manifest=fixture(base)
        for name in cloud_bundle.GUEST_INPUTS:
            target=base/'source-inputs'/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(cloud_bundle.ROOT/name,target)
        (base/'workload.json').write_bytes(m.canonical(cloud_authority.workload.load()))
        manifest.update(workloadSha256=m.sha((base/'workload.json').read_bytes()),files=package.inventory(base))
        save(base/'manifest.json',manifest)
        archive=self.root/'guest.tar.gz'
        with tarfile.open(archive,'w:gz',format=tarfile.USTAR_FORMAT) as tar:
            for path in sorted(base.rglob('*')):
                if path.is_file():
                    raw=path.read_bytes();info=tarfile.TarInfo(str(path.relative_to(base)));info.size=len(raw)
                    info.mode=0o755 if path.stat().st_mode & 0o111 else 0o644
                    tar.addfile(info,io.BytesIO(raw))
        self.parent=self.root/'mounted';self.parent.mkdir(mode=0o700)
        self.archive,self.manifest,self.attempt=archive,manifest,0
        self.new_attempt()

    def new_attempt(self,node=1):
        from . import guest_delivery_receiver as helper, guest_package_delivery as delivery, guest_package_receiver as receiver
        self.attempt+=1
        self.cfg=config(self.parent/package.MODES[2])
        self.cfg['binding']['node']='node-'+str(node)
        self.cfg['binding'].update(attempt=f'{self.attempt:032x}',bundleSha256=m.sha(self.archive.read_bytes()))
        self.value=delivery.describe(self.archive,self.manifest,self.cfg['binding'],
            dict(instanceId='123',diskId='456',attempt=self.cfg['binding']['attempt'],node=node),'c'*64)
        self.cfg['packageManifestSha256']=self.value['manifestSha256']
        sample=helper.clock_sample(receiver.identity(self.value),'d'*32)
        self.budget=dict(schema='gse-v51-helper-deadline-v1',sample=sample,expiresNanos=sample['sampledNanos']+60*10**9)
        receiver.begin(self.parent,self.value,self.budget)
        with self.archive.open('rb') as stream:
            for part in self.value['parts']:
                receiver.put(self.parent,self.value,self.budget,part['index'],io.BytesIO(stream.read(part['bytes'])))
        receiver.finish(self.parent,self.value,self.budget)
        self.endpoint=delivery.Endpoint(dict(instanceId='123'),self.parent,self.value)

    def selected(self,mode,cell,repetition=None):
        cfg=deepcopy(self.cfg);cfg['mode']=mode
        label=mode if cell is None else 'canonical-'+cell+'-'+mode
        if cell is not None:cfg['workload']=dict(cell=cell,preset='canonical')
        if repetition is not None:
            cfg['workload']['repetition']=repetition
            label=package.bootstrap_directory_name(cfg)
        cfg['root']=str(self.parent/label)
        return cfg

    def invoke(self,entry,action,request,data=b'',index=None,*,reject=None):
        encode=lambda value:base64.b64encode(m.canonical(value)).decode()
        args=self.endpoint.remote(entry,encode(self.budget),action,encode(request),*(() if index is None else (str(index),)))
        result=subprocess.run([sys.executable,*args[1:]],input=data,capture_output=True,timeout=10,cwd=self.root)
        if reject:
            self.assertNotEqual(result.returncode,0);self.assertRegex(result.stderr.decode(),reject);return
        self.assertEqual(result.returncode,0,result.stderr.decode())
        answer=m.strict_json(result.stdout)
        self.assertEqual(answer['requestSha256'],m.sha(m.canonical(request)))
        self.assertEqual(answer['deadlineSha256'],m.sha(m.canonical(self.budget)))
        return answer['receipt']

    def producer_request(self,cfg):
        from . import guest_source_producer
        configs=[]
        for node in package.service_nodes(cfg):
            member=deepcopy(cfg);member['binding']['node']='node-'+str(node);configs.append(member)
        return dict(schema=guest_source_producer.SCHEMA,configs=configs)

    def exported(self,cfg):
        from . import guest_bootstrap as boot
        root=Path(cfg['root']);root.mkdir()
        for name in boot.expected_files(cfg):
            path=root/name;path.parent.mkdir(exist_ok=True);path.write_bytes(name.encode())
        for name,value in boot.topology_values(cfg).items():
            if name in boot.expected_files(cfg):(root/name).write_text(value)
        folder=self.root/(root.name+'-export');row=boot.export(root,folder,cfg)
        root.rename(self.root/(root.name+'-original'))
        return folder,row['descriptorSha256']

    def test_all_five_producer_queries_cross_the_standalone_receiver(self):
        for mode,cell in workload.CASES:
            with self.subTest(mode=mode,cell=cell):
                cfg=self.selected(mode,cell)
                self.assertEqual(self.invoke('producer','query',self.producer_request(cfg))['state'],'NOT_FOUND')
                self.assertFalse(Path(cfg['root']).exists())
        self.assertEqual(list(self.parent.rglob('__pycache__')),[])

    def test_all_five_source_transfers_cross_the_standalone_receiver(self):
        from . import guest_source_transfer as wire
        for mode,cell in workload.CASES:
            with self.subTest(mode=mode,cell=cell):
                # Each CI tape has its own attempt. Source claims are not reusable across tapes.
                self.new_attempt()
                cfg=self.selected(mode,cell);folder,digest=self.exported(cfg)
                request=wire.describe(folder,digest,cfg)
                self.assertEqual(self.invoke('source','query',request)['state'],'NOT_FOUND')
                self.assertEqual(self.invoke('source','begin',request)['state'],'RECEIVING')
                for part in request['chunks']:
                    with (folder/'parts'/part['part']).open('rb') as stream:
                        stream.seek(part['offset']);raw=stream.read(part['bytes'])
                    self.invoke('source','chunk',request,raw,part['index'])
                self.assertEqual(self.invoke('source','finish',request)['state'],'SUCCEEDED')
                # The receiving node installs only its transferred bytes; producer path is gone.
                folder.rename(folder.with_name(folder.name+'-hidden'))
                install=dict(config=cfg,descriptorSha256=digest,sourceTransferSha256=m.sha(m.canonical(request)))
                self.assertEqual(self.invoke('bootstrap','install',install)['state'],'SUCCEEDED')
                self.assertEqual(self.invoke('bootstrap','query-install',install)['state'],'SUCCEEDED')

    def test_all_five_bootstrap_queries_cross_the_standalone_receiver(self):
        for mode,cell in workload.CASES:
            with self.subTest(mode=mode,cell=cell):
                cfg=self.selected(mode,cell)
                request=dict(config=cfg,folder=str(self.root/'absent'),descriptorSha256='e'*64)
                for action in ('query-install','query-seal'):
                    self.assertEqual(self.invoke('bootstrap',action,request)['state'],'NOT_FOUND')

    def test_reduced_experiment_keeps_its_original_receiver_directories(self):
        for mode in package.MODES:
            with self.subTest(mode=mode):
                cfg=self.selected(mode,None)
                self.assertEqual(self.invoke('producer','query',self.producer_request(cfg))['state'],'NOT_FOUND')
                folder,digest=self.exported(cfg)
                self.assertEqual(self.invoke('bootstrap','install',dict(config=cfg,folder=str(folder),descriptorSha256=digest))['state'],'SUCCEEDED')

    def test_changed_root_scope_and_identity_are_rejected_before_payload_access(self):
        original=self.selected(package.MODES[2],'healthy')
        for delta in (dict(root=str(self.parent/original['mode'])),dict(root=original['root']+'/../escape'),
                      dict(root=str(self.root/'elsewhere')),dict(workload=dict(cell='sustained',preset='canonical')),
                      dict(execution=guest.NATIVE_EXECUTION),dict(faultCell='leader-loss'),dict(workload=None),
                      dict(workload=dict(cell='../healthy',preset='canonical')),
                      dict(packageManifestSha256='0'*64),dict(binding=dict(original['binding'],attempt='0'*32))):
            cfg=deepcopy(original);cfg.update(delta)
            for entry in ('producer','source','bootstrap'):
                with self.subTest(delta=delta,entry=entry):
                    request=self.producer_request(cfg) if entry=='producer' else dict(config=cfg)
                    if entry=='bootstrap':request.update(folder=str(self.root/'absent'),descriptorSha256='e'*64)
                    self.invoke(entry,'query-install' if entry=='bootstrap' else 'query',request,
                                reject='configuration|offline canonical guest workload scope')
        self.assertFalse(Path(original['root']).exists())


if __name__ == '__main__': unittest.main()
