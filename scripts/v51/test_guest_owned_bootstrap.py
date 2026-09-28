"""Controller/receiver fixtures; no claim of cloud, block or JVM execution."""
from copy import deepcopy
import base64
import io
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from . import guest_owned_bootstrap as owned, guest_bootstrap as boot, remote_command as c, performance_model as m
from . import cloud_fake, guest_package_receiver as receiver, guest_delivery_receiver as helper
from . import guest_package_delivery as delivery
from . import guest_bootstrap_source as source_adapter, cloud_guest as guest
from .test_guest_service import config
from . import test_guest_owned_services as service_tests


class BootstrapTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.clock=cloud_fake.Clock();self.req,self.pre,self.approval=cloud_fake.fixture()
        self.configs=[config(self.root/'mount'/'candidate-v5.1-automatic') for _ in range(3)]
        for i in range(3):
            self.configs[i]=deepcopy(self.configs[0]);self.configs[i]['binding']=c.binding(self.req['source'],self.req['bundleSha256'],self.req['attempt'],'node-'+str(i+1))
        self.events=[];self.fault=None;test=self
        class Source:
            offline=True;scope='qualification-shared-source-paths'
            def prepare(_,configs,deadline):
                test.events.append('source');root=Path(configs[0]['root']);root.mkdir(parents=True)
                for name in boot.expected_files(configs[0]):
                    path=root/name;path.parent.mkdir(exist_ok=True);path.write_bytes(name.encode())
                for name,value in zip(boot.TOPOLOGY,('\n'.join(configs[0]['hosts'])+'\n','\n'.join(map(str,configs[0]['ports']))+'\n',configs[0]['groupId']+'\n')):
                    (root/name).write_text(value)
                result=[]
                for cfg in configs:
                    folder=test.root/('export-'+cfg['binding']['node']);row=boot.export(root,folder,cfg);row['folder']=str(folder);result.append(row)
                return result
        class Endpoint:
            offline=True
            def __init__(self,cfg):self.value=dict(binding=cfg['binding']);self.node=cfg['binding']['node'];self.states={};self.counts={}
            def bootstrap(ep,action,request,deadline):
                test.events.append((ep.node,action));ep.counts[action]=ep.counts.get(action,0)+1
                phase=action.removeprefix('query-')
                if action.startswith('query-'):
                    if test.fault=='consumed' and phase=='install':return dict(state='SUCCEEDED')
                    return ep.states.get(phase,dict(state='NOT_FOUND'))
                if test.fault=='uncertain':
                    ep.states[phase]=dict(state='UNCERTAIN');raise ConnectionError('lost mutation')
                if phase=='install':result=dict(status='PASS',node=ep.node,descriptorSha256=request['descriptorSha256'],files=6)
                else:
                    files=c.read(Path(request['folder'])/'bootstrap.json')['files']
                    identity=dict(sourceSha256=m.sha(m.canonical({k:v for k,v in files.items() if k.startswith('source/')})),manifestSha256='a'*64,genesisSha256='b'*64)
                    if test.fault=='wrong-genesis' and ep.node=='node-2':identity['genesisSha256']='c'*64
                    if test.fault=='wrong-source':identity['sourceSha256']='c'*64
                    result=dict(status='PASS',node=ep.node,identity=identity)
                ep.states[phase]=dict(state='SUCCEEDED',result=result)
                if test.fault=='lost-replies':raise ConnectionError('lost completed reply')
                return ep.states[phase]
        self.source=Source();self.endpoints=[Endpoint(cfg) for cfg in self.configs]
        self.bridge=owned.Bootstrap(self.source,clock=self.clock.seconds,sleep=self.clock.sleep)
    def run_bootstrap(self,deadline=None):
        def check(i,phase):
            self.events.append((i,phase))
            if self.fault=='mount-drift' and phase=='seeded':raise ValueError('mounted UUID changed')
        return self.bridge.prepare(self.req,self.configs,self.endpoints,self.root/'owned',deadline or self.clock.seconds()+10,recheck=check)
    def test_all_imports_precede_local_seals_and_shared_identity_is_retained(self):
        row=self.run_bootstrap();self.assertEqual(row['status'],'PASS');self.assertTrue(row['publicBootstrapVerified'])
        self.assertLess(self.events.index(('node-3','install')),self.events.index(('node-1','seal')))
        self.assertEqual(len(list(self.bridge.retention_files())),15)
        self.assertFalse(row['engineWorkloadExecuted']);self.assertFalse(row['paidCloud'])
    def test_lost_completed_replies_query_each_original_operation_once(self):
        self.fault='lost-replies';self.assertEqual(self.run_bootstrap()['status'],'PASS')
        for ep in self.endpoints:
            for phase in ('install','seal'):
                self.assertEqual(ep.counts[phase],1);self.assertEqual(ep.counts['query-'+phase],2)
    def test_partial_claim_expires_without_resubmission(self):
        self.fault='uncertain'
        with self.assertRaisesRegex(ValueError,'no replay|query budget'):self.run_bootstrap(self.clock.seconds()+.2)
        self.assertEqual(self.endpoints[0].counts['install'],1)
        self.assertFalse(any('seal' in ep.counts for ep in self.endpoints))
        self.assertTrue((self.root/'owned/node-1-install-intent.json').is_file())
    def test_consumed_destination_is_not_reused(self):
        self.fault='consumed'
        with self.assertRaisesRegex(ValueError,'consumed'):self.run_bootstrap()
        self.assertNotIn('install',self.endpoints[0].counts)
    def test_group_and_source_disagreement_fail_before_service_admission(self):
        for fault in ('wrong-genesis','wrong-source'):
            with self.subTest(fault=fault):
                case=BootstrapTest();case.setUp()
                try:
                    case.fault=fault
                    with self.assertRaisesRegex(ValueError,'disagree|source identity'):case.run_bootstrap()
                    self.assertEqual(c.read(case.root/'owned/receipt.json')['status'],'FAIL')
                finally:case.doCleanups()
    def test_fresh_mount_drift_stops_the_next_member(self):
        self.fault='mount-drift'
        with self.assertRaisesRegex(ValueError,'UUID'):self.run_bootstrap()
        self.assertNotIn('install',self.endpoints[1].counts)
    def test_changed_group_path_attempt_or_native_source_cannot_enter(self):
        self.configs[1]['root']=str(self.root/'different')
        with self.assertRaisesRegex(ValueError,'binding'):self.run_bootstrap()
        self.source.offline=False
        with self.assertRaisesRegex(ValueError,'disabled'):owned.Bootstrap(self.source)
    def test_second_preparation_and_unknown_retention_are_rejected(self):
        self.run_bootstrap()
        with self.assertRaisesRegex(ValueError,'consumed'):self.run_bootstrap()
        (self.root/'owned/unexpected.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'inventory'):list(self.bridge.retention_files())


class OwnedBootstrapLifecycleTest(service_tests.OwnedServiceTest):
    """Run inherited lifecycle cases with explicit synthetic Linux boot identity."""
    def setUp(self):
        mocked=patch.object(helper,'boot_identity',return_value='11111111-1111-4111-8111-111111111111')
        mocked.start();self.addCleanup(mocked.stop)
        original=Path.read_text
        def modeled_proc(path,*args,**kwargs):
            if str(path)=='/proc/sys/kernel/random/boot_id': return helper.boot_identity()
            if str(path)=='/proc/self/stat': return '1 (modeled) '+' '.join(['0']*20)
            return original(path,*args,**kwargs)
        mocked=patch.object(Path,'read_text',modeled_proc);mocked.start();self.addCleanup(mocked.stop)
        super().setUp()
    def test_bootstrap_group_failure_prevents_any_service_and_keeps_cleanup(self):
        test=self
        class Failed:
            offline=True
            def prepare(_,req,configs,endpoints,output,deadline,*,recheck):
                test.assertTrue(all((n,'finish') in test.events for n in (1,2,3)))
                recheck(0,'bootstrap');raise ValueError('group bootstrap disagreement')
            def retention_files(_):return iter(())
        self.services.bootstrap=Failed();result=self.run_owned()
        self.assertEqual(result['status'],'FAIL');self.assertFalse(self.clients);self.assert_clean(result)
    def test_bootstrap_precedes_launch_and_original_deadline_is_forwarded(self):
        test=self
        class Observed:
            offline=True
            def prepare(_,req,configs,endpoints,output,deadline,*,recheck):
                test.events.append('bootstrap');test.assertEqual(req,test.req)
                for i in range(3):recheck(i,'bootstrap');recheck(i,'seeded');recheck(i,'sealed')
                return dict(status='PASS',publicBootstrapVerified=True)
            def retention_files(_):return iter(())
        self.services.bootstrap=Observed();result=self.run_owned();self.assertEqual(result['status'],'PASS',result['errors'])
        self.assertLess(self.events.index((3,'finish')),self.events.index('bootstrap'))
        self.assertLess(self.events.index('bootstrap'),self.events.index((1,'start')))
    def test_unverified_bootstrap_receipt_blocks_launch_and_cleanup_continues(self):
        class Unverified:
            offline=True
            def prepare(_,req,configs,endpoints,output,deadline,*,recheck):return dict(status='PASS',publicBootstrapVerified=False)
            def retention_files(_):return iter(())
        self.services.bootstrap=Unverified();result=self.run_owned()
        self.assertEqual(result['status'],'FAIL');self.assertFalse(self.clients);self.assert_clean(result)
    def test_default_idle_retention_does_not_admit_bootstrap_records(self):
        self.assertEqual(self.run_owned()['status'],'PASS')
        (self.services.root/'node-1-check-bootstrap.json').write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError,'inventory'):list(self.services.retention_files())


class ReceiverTest(unittest.TestCase):
    """Real package verification/import; boot identity is explicitly synthetic."""
    def setUp(self):
        mocked=patch.object(helper,'boot_identity',return_value='11111111-1111-4111-8111-111111111111')
        mocked.start();self.addCleanup(mocked.stop)
        self.fixture=service_tests.OwnedServiceTest();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;f.parent=f.root/'mount-1'
        f.value=delivery.describe(f.archive,c.read(f.root/'package/manifest.json'),c.binding(f.req['source'],f.req['bundleSha256'],f.req['attempt'],'node-1'),
            dict(instanceId='123',diskId='456',attempt=f.req['attempt'],node=1),'c'*64)
        sample=helper.clock_sample(receiver.identity(f.value),'d'*32)
        self.budget=dict(schema='gse-v51-helper-deadline-v1',sample=sample,expiresNanos=sample['sampledNanos']+60*10**9)
        receiver.begin(f.parent,f.value,self.budget)
        with f.archive.open('rb') as stream:
            for part in f.value['parts']:receiver.put(f.parent,f.value,self.budget,part['index'],io.BytesIO(stream.read(part['bytes'])))
        receiver.finish(f.parent,f.value,self.budget)
        self.cfg=config(f.parent/'candidate-v5.1-automatic')
        self.cfg.update(binding=f.value['binding'],packageManifestSha256=f.value['manifestSha256'])
        self.root=Path(self.cfg['root']);self.root.mkdir()
        for name in boot.expected_files(self.cfg):
            path=self.root/name;path.parent.mkdir(exist_ok=True);path.write_bytes(name.encode())
        for name,value in zip(boot.TOPOLOGY,('\n'.join(self.cfg['hosts'])+'\n','\n'.join(map(str,self.cfg['ports']))+'\n',self.cfg['groupId']+'\n')):
            (self.root/name).write_text(value)
        self.folder=f.root/'export';row=boot.export(self.root,self.folder,self.cfg)
        self.root.rename(f.root/'producer')
        self.request=dict(config=self.cfg,folder=str(self.folder),descriptorSha256=row['descriptorSha256'])
        # bootstrap() normally runs in a disposable isolated interpreter.
        import sys
        old_path=sys.path[:];old_bytecode=sys.dont_write_bytecode
        self.addCleanup(setattr,sys,'path',old_path);self.addCleanup(setattr,sys,'dont_write_bytecode',old_bytecode)
    def call(self,action,request=None,budget=None):
        f=self.fixture
        return receiver.bootstrap(f.parent,f.value,budget or self.budget,
            [action,base64.b64encode(m.canonical(request or self.request)).decode()])
    def test_import_and_read_only_query_preserve_exact_identity(self):
        self.assertEqual(self.call('query-install')['receipt'],dict(state='NOT_FOUND'))
        answer=self.call('install');self.assertEqual(answer['receipt']['result']['files'],6)
        self.assertEqual(self.call('query-install')['receipt'],answer['receipt'])
        self.assertEqual(self.call('query-seal')['receipt'],dict(state='NOT_FOUND'))
        self.assertEqual(answer['deadlineSha256'],m.sha(m.canonical(self.budget)))
        with self.assertRaises(FileExistsError):self.call('install')
    def test_empty_or_partial_destination_is_uncertain_and_consumed(self):
        self.root.mkdir()
        self.assertEqual(self.call('query-install')['receipt'],dict(state='UNCERTAIN'))
        with self.assertRaises(FileExistsError):self.call('install')
        self.root.rmdir();path=self.folder/'parts/part-0000.bin';path.write_bytes(path.read_bytes()[:-1])
        with self.assertRaises(ValueError):self.call('install')
        self.assertEqual(self.call('query-install')['receipt'],dict(state='UNCERTAIN'))
        with self.assertRaises(FileExistsError):self.call('install')
    def test_changed_package_budget_path_or_binding_rejected_before_claim(self):
        renewed=dict(self.budget,expiresNanos=self.budget['expiresNanos']+1)
        with self.assertRaisesRegex(ValueError,'deadline changed'):self.call('install',budget=renewed)
        for key,value in (('root',str(self.fixture.root/'foreign')),('packageManifestSha256','0'*64)):
            changed=deepcopy(self.request);changed['config'][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'binding'):self.call('install',changed)
        installed=receiver.installed(self.fixture.parent,self.fixture.value)
        (installed/'padding').write_bytes(b'changed')
        with self.assertRaises(ValueError):self.call('install')
        self.assertFalse(self.root.exists())
    def test_expired_original_budget_and_reboot_fail_closed(self):
        with patch.object(helper.time,'monotonic_ns',return_value=self.budget['expiresNanos']+1):
            with self.assertRaisesRegex(ValueError,'expired'):self.call('install')
        with patch.object(helper,'boot_identity',return_value='22222222-2222-4222-8222-222222222222'):
            with self.assertRaisesRegex(ValueError,'boot changed'):self.call('query-install')
        self.assertFalse(self.root.exists())
    def test_seed_change_and_local_claim_cannot_be_promoted_to_success(self):
        self.call('install');path=self.root/'source'/boot.SOURCE[0];original=path.read_bytes();path.write_bytes(b'changed')
        with self.assertRaises(ValueError):self.call('query-install')
        path.write_bytes(original)
        c.write_once(self.root/boot.LOCAL_CLAIM,dict(config=self.cfg,seedSha256=self.request['descriptorSha256']))
        self.assertEqual(self.call('query-seal')['receipt'],dict(state='UNCERTAIN'))
        with patch.object(boot,'seal',side_effect=AssertionError('must not repeat')):
            with self.assertRaisesRegex(ValueError,'seed not ready'):self.call('seal')
    def test_seal_receives_original_guest_deadline(self):
        self.call('install')
        with patch.object(boot,'seal',return_value=dict(status='PASS')) as called:
            self.call('seal')
        self.assertEqual(called.call_args.kwargs['deadline'],self.budget['expiresNanos']/1e9)
    def test_completed_local_seal_query_rechecks_original_authority_inventory(self):
        self.call('install');node=self.root/self.cfg['binding']['node'];node.mkdir()
        for name in boot.authority_files(self.cfg):(node/name).write_bytes(name.encode())
        files=boot.parts.inventory(node)
        seed=c.read(self.folder/'bootstrap.json')['files']
        identity=dict(sourceSha256=m.sha(m.canonical({k:v for k,v in seed.items() if k.startswith('source/')})),
            manifestSha256=files['manifest.gsr']['sha256'],genesisSha256=files['genesis.gsr']['sha256'])
        # Synthetic authority bytes exercise query validation, not Java admission.
        c.write_once(self.root/boot.LOCAL_CLAIM,dict(config=self.cfg,seedSha256=self.request['descriptorSha256']))
        c.write_once(self.root/boot.LOCAL_READY,dict(config=self.cfg,files=files,identity=identity))
        self.assertEqual(self.call('query-seal')['receipt']['result']['identity'],identity)
        self.assertEqual(self.call('query-install')['receipt']['state'],'SUCCEEDED')
        (node/'manifest.gsr').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):self.call('query-seal')
    def test_controller_rejects_changed_response_and_renewed_deadline(self):
        class Local(delivery.Endpoint):
            offline=True
            def argv(self,remote):return remote
        ep=Local(dict(instanceId='123'),self.fixture.parent,self.fixture.value);ep.budget=self.budget;ep.deadline=time.monotonic()+10
        answer=dict(schema='gse-v51-package-bootstrap-v1',action='query-install',requestSha256=m.sha(m.canonical(self.request)),
            deadlineSha256=m.sha(m.canonical(self.budget)),receipt=dict(state='NOT_FOUND'))
        with patch.object(delivery.transport,'process',return_value=m.canonical(answer)):
            self.assertEqual(ep.bootstrap('query-install',self.request,ep.deadline),dict(state='NOT_FOUND'))
            with self.assertRaisesRegex(ValueError,'deadline'):ep.bootstrap('query-install',self.request,ep.deadline+1)
        for key in ('action','requestSha256','deadlineSha256'):
            with self.subTest(key=key),patch.object(delivery.transport,'process',return_value=m.canonical(dict(answer,**{key:'wrong'}))):
                with self.assertRaisesRegex(ValueError,'identity'):ep.bootstrap('query-install',self.request,ep.deadline)


class SourceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.cfg=config(self.root/'mount'/'candidate-v5.1-automatic');self.clock=cloud_fake.Clock();self.calls=[];self.fault=None;test=self
        class Views:
            cell=test.root/'mount';root=test.root/'views'
            def execute(_,name,argv,data,deadline):
                test.calls.append((name,argv,data,deadline))
                target=Views.root/name/guest.validate(test.cfg).relative_to(Views.cell);target.mkdir(parents=True)
                store=c.CommandStore(target/'store',test.cfg['binding'],create=True)
                req=c.request(test.cfg['binding'],m.sha(m.canonical(test.cfg))[:32],'prepare-cell',dict(distribute=True))
                # Synthetic terminal, not producer/JVM execution evidence.
                row=store.envelope(req,'FAILED' if test.fault=='failed' else 'SUCCEEDED',result=dict(bootstrap=[dict(node='node-1',descriptorSha256='a'*64)]))
                path=store.command_path(req);path.mkdir();c.write_once(path/'request.json',req)
                c.write_once(path/'terminal.json',row)
                if test.fault=='lost':raise ConnectionError('lost completed producer reply')
                if test.fault=='identity':row['commandId']='0'*32
                return m.canonical(row)
        self.adapter=source_adapter.ViewSource(Views(),self.root/'package',clock=self.clock.seconds,sleep=self.clock.sleep)
    def test_one_producer_and_original_deadline(self):
        exports=self.adapter.prepare([self.cfg],5)
        self.assertEqual(self.calls[0][1][-2:],['--deadline','5']);self.assertEqual(self.calls[0][3],5)
        self.assertTrue(exports[0]['folder'].endswith('/agents/node-1/bootstrap/node-1'))
        with self.assertRaisesRegex(ValueError,'consumed'):self.adapter.prepare([self.cfg],6)
    def test_lost_reply_queries_original_store_without_second_producer(self):
        self.fault='lost';self.adapter.prepare([self.cfg],5)
        self.assertEqual((self.adapter.submits,self.adapter.queries,len(self.calls)),(1,1,1))
    def test_failed_or_wrong_identity_receipt_is_not_accepted(self):
        self.fault='failed'
        with self.assertRaisesRegex(ValueError,'failed'):self.adapter.prepare([self.cfg],5)
    def test_changed_command_identity_is_rejected(self):
        self.fault='identity'
        with self.assertRaisesRegex(ValueError,'identity'):self.adapter.prepare([self.cfg],5)


if __name__=='__main__':unittest.main()
