"""Synthetic coordinator faults and real source-byte replay; no cloud claims."""
from copy import deepcopy
from contextlib import chdir
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import uuid
from unittest.mock import Mock, patch
from . import guest_owned_three_mode as batch, guest_shared_source as source, guest_three_mode_evidence as evidence
from . import cloud_fake, cloud_package as package, guest_bootstrap as boot, remote_collection as parts
from . import performance_model as m, performance_plan, remote_command as c
from .test_guest_service import config
from .test_guest_backup import payloads
from . import test_guest_owned_workload as workload_tests


class SourceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.clock=cloud_fake.Clock();self.shared=source.SharedSource(self.root/'shared',clock=self.clock.seconds,sleep=self.clock.sleep)
        self.initial=config(self.root/package.MODES[0]);self.initial['mode']=package.MODES[0]
        self.backup=payloads(m.initial(performance_plan.load()))
        self.remote=Mock(side_effect=self.produce);self.shared.remote.prepare=self.remote
        self.deadline=self.clock.seconds()+600
    def configs(self, mode):
        base=deepcopy(self.initial);base.update(mode=mode,root=str(self.root/mode),groupId=str(uuid.uuid5(uuid.NAMESPACE_URL,mode)))
        return [dict(base,binding=dict(base['binding'],node='node-'+str(n))) for n in package.experiment_nodes(mode)]
    def produce(self, configs, deadline, *, endpoint, output):
        output.mkdir();raw=output.absolute()/'seed';raw.mkdir();(raw/'source').mkdir()
        for n,b in self.backup.items():(raw/'source'/n).write_bytes(b)
        cfg=configs[0]
        for n,text in zip(boot.TOPOLOGY, ('\n'.join(cfg['hosts'])+'\n','\n'.join(map(str,cfg['ports']))+'\n',cfg['groupId']+'\n')):(raw/n).write_text(text)
        folder=output/'node-1';row=boot.export(raw,folder,cfg,producer_config=dict(cfg,root=str(raw)))
        return [dict(row,folder=str(folder))]
    def prepare(self, mode, **changes):
        configs=self.configs(mode)
        for cfg in configs:cfg.update(changes)
        adapter=source.Source(self.shared)
        result=adapter.prepare(configs,self.deadline,endpoint=object(),output=self.root/('export-'+mode))
        return adapter,result
    def test_exact_one_producer_and_identical_source_across_fresh_modes_and_seven_receivers(self):
        values=[]
        for mode in package.MODES:
            adapter,rows=self.prepare(mode)
            for row in rows:
                value=c.read(Path(row['folder'])/'bootstrap.json')
                values.append({n:v for n,v in value['files'].items() if n.startswith('source/')})
            retained=list(adapter.retention_files());self.assertTrue(retained)
        self.assertEqual(self.remote.call_count,1);self.assertEqual(len(values),7);self.assertTrue(all(v==values[0] for v in values))
    def test_relative_controller_exports_preserve_seven_exact_guest_configs_and_one_seed(self):
        inventories=[]
        with chdir(self.root):
            for mode in package.MODES:
                configs=self.configs(mode);original=deepcopy(configs)
                adapter=source.Source(self.shared)
                rows=adapter.prepare(configs,self.deadline,endpoint=object(),output=Path('export-'+mode))
                self.assertEqual(original,configs)
                for cfg,row in zip(configs,rows):
                    folder=Path(row['folder']);self.assertTrue(folder.is_absolute())
                    value=boot.descriptor(folder,row['descriptorSha256'],cfg)
                    inventories.append({n:v for n,v in value['files'].items() if n.startswith('source/')})
                self.assertTrue(list(adapter.retention_files()))
        self.remote.assert_called_once();self.assertEqual(7,len(inventories))
        self.assertTrue(all(v==inventories[0] for v in inventories))
    def test_linked_export_parent_is_rejected_before_source_download(self):
        (self.root/'real').mkdir();(self.root/'link').symlink_to(self.root/'real',target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'directory symlink'):
            self.shared.prepare(self.configs(package.MODES[0]),self.deadline,endpoint=object(),output=self.root/'link/export')
        self.remote.assert_not_called();self.assertEqual([],list((self.root/'real').iterdir()))
    def test_mode_order_and_repeat_are_rejected_before_remote_operation(self):
        with self.assertRaisesRegex(ValueError,'order'):self.prepare(package.MODES[1])
        self.remote.assert_not_called();self.prepare(package.MODES[0])
        with self.assertRaisesRegex(ValueError,'consumed'):self.prepare(package.MODES[0])
        self.assertEqual(self.remote.call_count,1)
    def test_changed_source_bytes_do_not_create_the_next_mode_export(self):
        self.prepare(package.MODES[0]);(self.shared.root/'seed/source'/boot.SOURCE[0]).write_bytes(b'changed')
        with self.assertRaises(ValueError):self.prepare(package.MODES[1])
        self.assertEqual(self.remote.call_count,1)
        self.assertFalse((self.root/('export-'+package.MODES[1])/'node-1').exists())
    def test_changed_package_or_extended_deadline_rejected(self):
        self.prepare(package.MODES[0])
        with self.assertRaisesRegex(ValueError,'identity'):self.prepare(package.MODES[1],packageManifestSha256='e'*64)
        self.deadline+=1
        with self.assertRaisesRegex(ValueError,'deadline'):self.prepare(package.MODES[1])
        self.assertEqual(self.remote.call_count,1)


class PackageTest(unittest.TestCase):
    def setUp(self):
        self.descriptor=dict(binding=dict(node='node-1'))
        self.ep=SimpleNamespace(target={'id':1},parent='/mount',value=self.descriptor)
        self.factory=Mock(return_value=self.ep);self.pool=batch.PackagePool(self.factory)
    def test_reused_original_endpoint_and_completion_does_not_mutate_twice(self):
        with patch.object(batch.delivery,'deliver',return_value=dict(state='SUCCEEDED')) as deliver:
            for _ in range(3):
                self.assertIs(self.pool.endpoint({'id':1},'/mount',self.descriptor),self.ep)
                self.assertEqual(self.pool.deliver(self.ep,'/archive',600),dict(state='SUCCEEDED'))
            deliver.assert_called_once();self.factory.assert_called_once()
            with self.assertRaises(ValueError):self.pool.deliver(self.ep,'/archive',601)
            with self.assertRaises(ValueError):self.pool.endpoint({'id':2},'/mount',self.descriptor)
    def test_uncertain_package_is_consumed_without_retry(self):
        with patch.object(batch.delivery,'deliver',side_effect=ConnectionError('lost')) as deliver:
            with self.assertRaises(ConnectionError):self.pool.deliver(self.ep,'/archive',600)
            with self.assertRaisesRegex(ValueError,'consumed'):self.pool.deliver(self.ep,'/archive',600)
            deliver.assert_called_once()


class HandoffTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.clock=cloud_fake.Clock();self.req,_,_=cloud_fake.fixture()
        self.services=SimpleNamespace(offline=True,mode=batch.MODE,provider=SimpleNamespace(req=self.req))
        self.probe=batch.Probe(self.services,self.root/'probe',clock=self.clock.seconds,sleep=self.clock.sleep)
        self.events=[];self.failed=None;self.slow=None
        for mode in package.MODES:
            def cell(name,deadline,mode=mode):self.events.append((mode,'start'));self.clock.sleep(290 if self.slow==mode else 90)
            def close(deadline,mode=mode):
                self.events.append((mode,'close'));self.clock.sleep(20 if self.slow==mode else 1)
                return ['original failed close'] if self.failed==mode else []
            self.probe.probes[mode]=Mock(cell=cell,close_voters=close,engineWorkloadExecuted=True)
        self.probe.prepared=True
    def run_cell(self):self.probe.cell('healthy',self.clock.nanos()+900*10**9)
    def test_order_close_barrier_and_single_consumed_tape(self):
        self.run_cell();self.assertEqual(self.events,[(mode,action) for mode in package.MODES for action in ('start','close')])
        evidence.timeline(c.read(self.probe.raw/'timeline.json'))
        with self.assertRaisesRegex(ValueError,'consumed'):self.run_cell()
    def test_failed_stop_blocks_next_mode_and_retains_failed_timing(self):
        self.failed=package.MODES[0]
        with self.assertRaisesRegex(ValueError,'not closed'):self.run_cell()
        self.assertEqual(self.events,[(self.failed,'start'),(self.failed,'close')]);self.assertEqual(self.probe.cells,[])
        self.assertEqual(c.read(self.probe.raw/'timeline.json')['status'],'FAIL')
    def test_close_time_counts_in_original_mode_budget(self):
        self.slow=package.MODES[0]
        with self.assertRaisesRegex(ValueError,'ceiling including close'):self.run_cell()
        self.assertEqual(len(self.events),2)
    def test_missing_duplicate_reversed_overlap_and_budget_tampering_rejected(self):
        self.run_cell();original=c.read(self.probe.raw/'timeline.json')
        for mutate in (lambda v:v['modes'].pop(),lambda v:v['modes'].append(v['modes'][0]),
            lambda v:v['modes'].reverse(),lambda v:v['modes'][1].update(startNanos=v['modes'][0]['endNanos']-1),
            lambda v:v['modes'][0].update(endNanos=v['modes'][0]['startNanos']+301*10**9),lambda v:v.update(endNanos=v['startNanos']+901*10**9)):
            value=deepcopy(original);mutate(value)
            with self.assertRaises(ValueError):evidence.timeline(value)


class StopOnceTest(unittest.TestCase):
    setUp=workload_tests.OwnedWorkloadTest.setUp
    # Reuse only the setup: the original suite covers individual command replay.
    def test_close_is_not_reissued_during_final_collection(self):
        self.probe.cell('healthy',self.clock.nanos()+300*10**9)
        self.probe.clients[0][1].failure='stop-voter'
        first=self.probe.close_voters(self.clock.seconds()+30)
        self.assertEqual(len(first),1);self.probe.stop()
        self.probe.collect_validate(self.root,self.clock.nanos()+600*10**9)
        for _,client,_ in self.probe.clients:self.assertEqual(sum(q['command']=='stop-voter' for q in client.calls),1)
        self.assertEqual(self.probe.close_voters(self.clock.seconds()+30),first)


class ThreeModeRunnerTest(workload_tests.RunnerWorkloadTest):
    def setUp(self):
        super().setUp();self.probe.mode=batch.MODE;self.probe.scope=batch.SCOPE
        self.probe.collect_validate.return_value.update(mode=batch.MODE,scope=batch.SCOPE)


class AggregateTest(unittest.TestCase):
    """Exercise aggregate boundaries; member oracles have separate physical fixtures."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.raw=self.root/'raw';self.raw.mkdir();self.req,_,_=cloud_fake.fixture();sha=batch.a.validate_request(self.req)
        (self.raw/'source').mkdir()
        for n,b in payloads(m.initial(performance_plan.load())).items():(self.raw/'source'/n).write_bytes(b)
        files={n:dict(bytes=p.stat().st_size,sha256=m.sha(p.read_bytes())) for n,p in [(p.name,p) for p in (self.raw/'source').iterdir()]}
        source_sha=m.sha(m.canonical({'source/'+n:v for n,v in files.items()}))
        plan=dict(scope=batch.SCOPE,request=self.req,services=dict(status='PASS',requestSha256=sha,sourceSha256=source_sha,modes=[]))
        timing=dict(status='PASS',startNanos=0,endNanos=300*10**9,modes=[])
        for i,mode in enumerate(package.MODES):
            folder=self.raw/mode;folder.mkdir();start=i*100*10**9;end=start+90*10**9
            timing['modes'].append(dict(mode=mode,status='PASS',startNanos=start,endNanos=end))
            identity=dict(sourceSha256=source_sha,manifestSha256=m.sha(b'manifest'),genesisSha256=m.sha(b'genesis'))
            plan['services']['modes'].append(dict(mode=mode,receipt=dict(status='PASS',requestSha256=sha,
                bootstrap=dict(status='PASS',publicBootstrapVerified=True,identity=identity))))
            cfg=config(self.root/'guest'/mode);cfg.update(mode=mode,groupId=str(uuid.uuid5(uuid.NAMESPACE_URL,sha+':'+mode)),packageManifestSha256=m.sha(b'package'))
            configs=[]
            (folder/'package-manifest.json').write_bytes(b'package')
            c.write_once(folder/'cell.json',dict(status='EXECUTED',mode=mode,startedNanos=start,endedNanos=end))
            for n in package.experiment_nodes(mode):
                member=folder/f'node-{n}';member.mkdir();cfg=deepcopy(cfg);cfg['binding']=c.binding(self.req['source'],self.req['bundleSha256'],self.req['attempt'],f'node-{n}');configs.append(cfg)
                transcript=[]
                for j,name in enumerate(('start-voter','stop-voter','collect')):
                    request=c.request(cfg['binding'],uuid.uuid4().hex,name,{})
                    receipt=dict(state='SUCCEEDED',result=dict(stopped=True) if name=='stop-voter' else {})
                    transcript.append(dict(request=request,receipt=receipt))
                    original=folder/'commands'/str(n)/request['commandId'];original.mkdir(parents=True)
                    c.write_once(original/'request.json',dict(config=cfg,request=request));c.write_once(original/'receipt.json',receipt)
                    c.write_once(original/'observation.json',dict(startNanos=start+j,endNanos=start+j+1))
                c.write_once(member/'controller.json',dict(config=cfg,active=n==1,packageRoot='/package',transcript=transcript))
                data=self.root/(mode+str(n));data.mkdir()
                if mode!=package.MODES[0]:
                    authority=data/'authority'/f'node-{n}';authority.mkdir(parents=True)
                    (authority/'manifest.gsr').write_bytes(b'manifest');(authority/'genesis.gsr').write_bytes(b'genesis')
                else:(data/'synthetic').write_bytes(b'synthetic')
                parts.pack(data,member/'parts',m.sha(m.canonical(cfg['binding'])))
            c.write_once(folder/'plan.json',dict(mode=mode,request=self.req,configs=configs))
        c.write_once(self.raw/'plan.json',plan);c.write_once(self.raw/'timeline.json',timing)
    def validate(self):
        # The joint validator must invoke independent member replay, not summaries.
        with patch.object(evidence.guest_evidence,'validate',side_effect=lambda *a,**k:dict(calls=90 if k['active'] else 0)) as logical, \
             patch.object(evidence.guest_physical_evidence,'validate',return_value=dict(status='PASS')) as physical, \
             patch.object(evidence,'source_binding'):
            result=evidence.validate(self.raw,self.root/('replay-'+uuid.uuid4().hex))
            self.assertEqual(logical.call_count,7);self.assertEqual(physical.call_count,2)
            return result
    def test_complete_set_replays_all_seven_original_collections(self):
        answer=self.validate();self.assertEqual(answer['calls'],270);self.assertFalse(answer['fullRemoteQualification'])
    def change(self,path,mutate):
        value=c.read(path);mutate(value);path.write_bytes(m.canonical(value))
    def test_changed_seed_rejected_before_member_replay(self):
        (self.raw/'source'/boot.SOURCE[0]).write_bytes(b'changed')
        with self.assertRaises(ValueError):self.validate()
    def test_changed_request_or_build_and_missing_mode_rejected(self):
        folder=self.raw/package.MODES[1];plan=folder/'plan.json';original=plan.read_bytes()
        self.change(plan,lambda v:v['request'].update(source='f'*40))
        with self.assertRaisesRegex(ValueError,'request/member'):self.validate()
        plan.write_bytes(original);manifest=folder/'package-manifest.json';manifest.write_bytes(b'different')
        with self.assertRaisesRegex(ValueError,'package build'):self.validate()
        manifest.write_bytes(b'package');folder.rename(self.root/'missing')
        with self.assertRaises(FileNotFoundError):self.validate()
    def test_changed_original_close_or_handoff_interval_is_rejected(self):
        folder=self.raw/package.MODES[0];member=folder/'node-1/controller.json'
        row=next(v for v in c.read(member)['transcript'] if v['request']['command']=='stop-voter')
        original=folder/'commands/1'/row['request']['commandId']/'observation.json';raw=original.read_bytes()
        self.change(original,lambda v:v.update(endNanos=200*10**9))
        with self.assertRaisesRegex(ValueError,'outside mode'):self.validate()
        original.write_bytes(raw)
        self.change(member,lambda v:v['transcript'][1]['receipt'].update(state='FAILED'))
        with self.assertRaisesRegex(ValueError,'original command'):self.validate()
    def test_modified_binary_input_is_rejected_despite_cached_success(self):
        folder=self.raw/package.MODES[0]/'node-1/parts'
        part=next(folder.glob('*.bin'));raw=part.read_bytes();part.write_bytes(bytes([raw[0]^1])+raw[1:])
        with self.assertRaisesRegex(ValueError,'part hash'):self.validate()


if __name__=='__main__':unittest.main()
