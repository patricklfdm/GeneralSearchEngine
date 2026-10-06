"""Native protocol tests with modeled OS/provider boundaries; never touches a disk."""
import base64
from copy import deepcopy
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import cloud_runner_guest_setup as s, guest_native_volume as v, guest_native_package as p
from . import guest_startup_fake as fake, guest_volume, guest_package_receiver as receiver
from . import guest_package_delivery as delivery, guest_delivery_receiver as r, performance_model as m
from . import test_guest_package_delivery as package_fixture


def request(attempt='a'*32):
    access = dict(attempt=attempt,user='gse-'+attempt[:24],
                  publicKey='ssh-ed25519 '+base64.b64encode(b'\0\0\0\x0bssh-ed25519\0\0\0\x20'+b'a'*32).decode())
    return dict(schema=v.SCHEMA,binding=dict(schema='gse-v51-guest-binding-v1',source='a'*40,bundleSha256='b'*64,
        workloadSha256='c'*64,attempt=attempt,node='node-1'),
        provider=dict(instanceId='123',diskId='456',node=1,sizeGiB=100,attempt=attempt),bootDiskId='789',
        access=access,requestSha256='d'*64)


def token(value, identity):
    sample = r.clock_sample(identity(value),'e'*32)
    budget = dict(schema='gse-v51-helper-deadline-v1',sample=sample,expiresNanos=sample['sampledNanos']+30*10**9)
    return base64.b64encode(r.canonical(budget)).decode()


class NativeVolumeTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.value=request();self.token=token(self.value,v.identity)
        self.clock=SimpleNamespace(seconds=time.monotonic,sleep=lambda _:None)
        self.block=fake.Block(self.value['provider'],self.clock)
        # Only OS privilege/metadata and the synthetic root directory are replaced.
        # Claims, deadline binding, parser and write-once algorithm remain real.
        owner=os.getuid();owned=r.owned
        location=r.location;read=r.read
        self.enterContext(patch.object(v,'PARENT',str(self.root/'root-claims')))
        self.native_context=v.context
        self.context=self.enterContext(patch.object(v,'context'))
        self.enterContext(patch.object(r,'owned',side_effect=lambda path,uid,directory=False:owned(path,owner if uid==0 else uid,directory)))
        self.enterContext(patch.object(r,'location',side_effect=lambda parent,value,uid:location(parent,value,owner if uid==0 else uid)))
        self.enterContext(patch.object(r,'read',side_effect=lambda path,uid,maximum=r.MAX_BYTES:read(path,owner if uid==0 else uid,maximum)))
    def perform(self, action, token_value=None):
        return v._perform(action,self.value,token_value or self.token,self.block)
    def test_real_algorithm_consumes_once_and_rechecks_mount(self):
        answer=self.perform('prepare');self.assertEqual('SUCCEEDED',answer['state'])
        self.assertEqual(1,self.block.formats);self.assertNotIn('paidCloud',answer['startup'])
        count=len(self.block.commands);self.assertEqual(answer,self.perform('prepare'))
        self.assertEqual(count,len(self.block.commands));checked=self.perform('check')
        self.assertEqual(m.sha(m.canonical(answer['startup'])),checked['readiness']['startupSha256'])
        self.assertEqual('gse-v51-native-volume-readiness-v1',checked['readiness']['schema'])
    def test_lost_format_response_is_terminal_no_reformat(self):
        self.block.fault='lost-format-reply'
        answer=self.perform('prepare');self.assertEqual('FAILED',answer['state'])
        self.assertEqual(answer,self.perform('prepare'));self.assertEqual(1,self.block.formats)
    def test_partial_outer_claim_never_enters_algorithm(self):
        parent=Path(v.PARENT);parent.mkdir(mode=0o700)
        (parent/(self.value['binding']['attempt']+'-node-1')).mkdir(mode=0o700)
        self.assertEqual('UNCERTAIN',self.perform('prepare')['state']);self.assertEqual([],self.block.commands)
    def test_changed_budget_cannot_resume_consumed_claim(self):
        self.perform('prepare')
        with self.assertRaisesRegex(ValueError,'consumed identity/deadline'):self.perform('prepare',token(self.value,v.identity))
        self.assertEqual(1,self.block.formats)
    def test_deadline_or_boot_change_blocks_before_context_and_mutation(self):
        budget=r.decode(base64.b64decode(self.token))
        for name,patcher in (('deadline',patch.object(r.time,'monotonic_ns',return_value=budget['expiresNanos'])),
                             ('boot',patch.object(r,'boot_identity',return_value='0'*36))):
            with self.subTest(name=name),patcher,self.assertRaises(ValueError):self.perform('prepare')
        self.context.assert_not_called();self.assertEqual([],self.block.commands)
    def test_boot_used_disk_and_alias_drift_never_format(self):
        for fault in ('boot-device','used-disk','alias-drift'):
            with self.subTest(fault=fault),patch.object(v,'PARENT',str(self.root/fault)):
                self.block=fake.Block(self.value['provider'],self.clock,fault)
                self.assertEqual('FAILED',self.perform('prepare')['state']);self.assertEqual(0,self.block.formats)
    def test_remount_uuid_change_rejected_on_readiness(self):
        self.perform('prepare');blocks=self.block.blocks
        def changed():
            raw=blocks();raw['blockdevices'][2]['uuid']='aaaaaaaa-1234-1234-1234-123456789abc';return raw
        self.block.blocks=changed
        with self.assertRaisesRegex(ValueError,'identity changed'):self.perform('check')
        self.assertEqual(1,self.block.formats)
    def test_wrong_metadata_account_or_privilege_rejected(self):
        uid,gid=1001,1001;access=self.value['access']
        metadata=dict(instanceId='123',sshKeys=access['user']+':'+access['publicKey'],blockProjectSshKeys='TRUE',enableOslogin='FALSE')
        with patch.object(v.pwd,'getpwnam',return_value=SimpleNamespace(pw_uid=uid,pw_gid=gid)),\
             patch.object(v.os,'getuid',return_value=0),patch.object(v.os,'geteuid',return_value=0),\
             patch.object(v.os,'getgid',return_value=0),patch.object(v.os,'getegid',return_value=0),\
             patch.dict(os.environ,SUDO_USER=access['user'],SUDO_UID=str(uid),SUDO_GID=str(gid)),\
             patch.object(v.root,'metadata',return_value=metadata):
            self.assertEqual((uid,gid),v.account(self.value,time.monotonic()+5,privileged=True))
            with patch.dict(os.environ,SUDO_USER='foreign'),self.assertRaisesRegex(ValueError,'invoking'):v.account(self.value,99,privileged=True)
            metadata['instanceId']='999'
            with self.assertRaisesRegex(ValueError,'metadata'):v.account(self.value,99,privileged=True)
            with patch.object(v.os,'geteuid',return_value=1001),self.assertRaisesRegex(ValueError,'effective'):v.account(self.value,99,privileged=True)
    def test_legacy_entry_and_read_backend_stay_closed(self):
        with self.assertRaisesRegex(ValueError,'disabled'):
            guest_volume.prepare(self.root/'forbidden',self.value['provider'],self.value['access']['user'],v._Linux(self.value),99,recheck=lambda:None)
        with patch.object(v.transport,'process') as process,self.assertRaisesRegex(ValueError,'disabled'):
            guest_volume.Linux().run(['mkfs.ext4','/dev/sdb'],99)
        process.assert_not_called()
    def test_native_backend_rejects_force_arbitrary_device_path_and_command(self):
        backend=v._Linux(self.value)
        with patch.object(backend,'user',return_value=(1001,1001)),patch.object(v.transport,'process') as process:
            for argv in (['mkfs.ext4','-F','/dev/sdb'],['mkfs.ext4','-L','gse-'+self.value['provider']['attempt'][:12],'/tmp/disk'],
                         ['chown','0:0',guest_volume.MOUNT],['sh','-c','true']):
                with self.subTest(argv=argv),self.assertRaises(ValueError):backend.run(argv,99)
            process.assert_not_called()
    def test_native_backend_uses_fixed_write_argv_and_clean_environment(self):
        backend=v._Linux(self.value);argv=['mkfs.ext4','-L','gse-'+self.value['provider']['attempt'][:12],'/dev/sdb']
        with patch.object(backend,'user',return_value=(1001,1001)),patch.object(v.transport,'process',return_value=b'') as process:
            self.assertEqual(b'',backend.run(argv,99))
            self.assertEqual((argv,b'',99),process.call_args.args)
            self.assertEqual({'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C','LC_ALL':'C'},process.call_args.kwargs['env'])
    def test_root_parent_and_ancestors_cannot_be_linked_foreign_or_writable(self):
        parent=Path(v.PARENT)
        with patch.object(v,'account',return_value=(1001,1001)),patch.object(Path,'exists',return_value=True),\
             patch.object(v.root,'directory',return_value=dict(kind='directory',uid=0,mode=0o700)) as directory:
            self.native_context(self.value,99)
            for bad in (dict(kind='other',uid=0,mode=0o700),dict(kind='directory',uid=1001,mode=0o700),
                        dict(kind='directory',uid=0,mode=0o777)):
                directory.side_effect=lambda path,bad=bad:bad if path==parent else dict(kind='directory',uid=0,mode=0o755)
                with self.subTest(bad=bad),self.assertRaisesRegex(ValueError,'parent'):self.native_context(self.value,99)


class NativePackageTest(unittest.TestCase):
    def setUp(self):
        # Shared independently constructed tar fixture; no product JVM is executed.
        package_fixture.PackageDeliveryTest.setUp(self)
        req=request('b'*32);req['binding']=deepcopy(self.value['binding'])
        self.value.update(schema='gse-v51-native-package-transfer-v1',guestAccessSha256=m.sha(m.canonical(req['access'])),
            nativeVolume=dict(request=req,startupSha256='f'*64,volume=dict(device='/dev/sdb',majorMinor='8:16',
                uuid='12345678-1234-1234-1234-123456789abc',mount=str(self.parent),uid=1001,gid=1001)))
        self.enterContext(patch.object(guest_volume,'MOUNT',str(self.parent)))
        self.context=self.enterContext(patch.object(p,'context'))
        self.token=token(self.value,receiver.identity)
    deadline=package_fixture.PackageDeliveryTest.deadline
    def perform(self, action, data=b'', index=None):return p.perform(action,self.value,self.token,io.BytesIO(data),index)
    def receive(self):
        self.perform('begin')
        with self.archive.open('rb') as stream:
            for part in self.value['parts']:self.perform('part',stream.read(part['bytes']),part['index'])
    def test_native_complete_transfer_checks_context_before_and_after_every_call(self):
        self.receive();answer=self.perform('finish')['receipt'];self.assertEqual('SUCCEEDED',answer['state'])
        self.assertEqual('native-guest-package',answer['execution']);self.assertNotIn('paidCloud',answer)
        self.assertEqual((len(self.value['parts'])+2)*2,self.context.call_count)
        self.assertEqual(answer,self.perform('finish')['receipt'])
    def test_corrupt_part_stays_failed_without_consuming_replacement(self):
        self.perform('begin');self.assertEqual('FAILED',self.perform('part',b'partial',0)['receipt']['state'])
        stream=io.BytesIO(b'new')
        self.assertEqual('FAILED',p.perform('part',self.value,self.token,stream,0)['receipt']['state']);self.assertEqual(0,stream.tell())
    def test_mount_identity_failure_stops_before_transfer(self):
        self.context.side_effect=ValueError('replaced volume')
        with self.assertRaisesRegex(ValueError,'replaced volume'):self.perform('begin')
        self.assertEqual([],list(self.parent.iterdir()))
    def test_package_request_binds_access_source_disk_and_mount(self):
        for field in ('instanceId','diskId','guestAccessSha256'):
            with self.subTest(field=field):
                bad=deepcopy(self.value);bad[field]='999' if field.endswith('Id') else '0'*64
                with self.assertRaisesRegex(ValueError,'binding'):p.validate(bad)
        bad=deepcopy(self.value);bad['nativeVolume']['volume']['mount']='/tmp/boot'
        with self.assertRaisesRegex(ValueError,'mount'):p.validate(bad)
    def test_engine_bootstrap_and_source_commands_remain_unreachable(self):
        for action in ('service','bootstrap','producer','source','prepare-cell'):
            with self.subTest(action=action),self.assertRaisesRegex(ValueError,'transfer-only'):self.perform(action)
        self.context.assert_not_called()
    def test_legacy_controller_and_cli_cannot_deliver_native_descriptor(self):
        endpoint=delivery.Endpoint(dict(instanceId='123'),self.parent,self.value);endpoint.offline=True
        with self.assertRaisesRegex(ValueError,'disabled'):delivery.deliver(endpoint,self.archive,time.monotonic()+30)
        with self.assertRaisesRegex(ValueError,'disabled'):endpoint.exchange('begin',b'',time.monotonic()+30)
        args=['receiver','begin',str(self.parent),base64.b64encode(m.canonical(self.value)).decode(),self.token]
        with patch.object(sys,'argv',args),self.assertRaisesRegex(ValueError,'admitted receiver'):receiver.main()


class NativeControllerTest(unittest.TestCase):
    def test_trusted_source_loads_in_isolated_process_without_repo_or_package_import(self):
        for kind in ('volume','package'):
            source=s.trusted_source(kind)
            # Source includes dependencies and a fixed entry. No args must fail
            # at entry parsing, not missing imports or a downloaded verifier.
            result=subprocess.run([sys.executable,'-I','-c',source],cwd='/tmp',capture_output=True,timeout=10)
            self.assertNotEqual(0,result.returncode)
            self.assertIn(b'not enough values to unpack',result.stderr);self.assertNotIn(b'ImportError',result.stderr)
            self.assertLess(len(source),65536)
    def test_lost_volume_response_queries_original_once(self):
        value=request();api=SimpleNamespace(clock=time.monotonic,deadline=time.monotonic()+30,provider=lambda:SimpleNamespace(sleep=lambda _:None))
        endpoint=s._VolumeEndpoint(api,{},value,lambda:None);actions=[]
        startup=dict(volume={'identity':'original'});readiness=dict(volume=startup['volume'],startupSha256=m.sha(m.canonical(startup)))
        def exchange(action):
            actions.append(action)
            if action=='prepare':raise ConnectionError('lost')
            return dict(state='SUCCEEDED',startup=startup,readiness=readiness)
        endpoint.exchange=exchange
        self.assertEqual(startup,endpoint.prepare()['startup']);self.assertEqual(['prepare','query','check'],actions)
    def test_clock_failure_never_admits_prepare_or_renews(self):
        value=request();api=SimpleNamespace(clock=time.monotonic,deadline=time.monotonic()+30)
        endpoint=s._VolumeEndpoint(api,{},value,lambda:None)
        with patch.object(endpoint,'call',side_effect=ConnectionError('clock failed')) as call:
            for _ in range(2):
                with self.assertRaises(ValueError):endpoint.exchange('prepare')
            self.assertEqual(1,call.call_count);self.assertEqual('clock',call.call_args.args[0])
    def test_native_entry_has_no_backend_credential_or_command_overrides(self):
        import inspect
        self.assertEqual(['cfg','env','source','checkout','preflight','precheck_root','value','approved','artifacts','key','output'],
                         list(inspect.signature(s.prepare_native).parameters))


class NativeMountContextTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.parent=Path(self.tmp.name)
        info=self.parent.stat();number=f'{os.major(info.st_dev)}:{os.minor(info.st_dev)}'
        self.value=dict(binding=request()['binding'],nativeVolume=dict(request=request(),volume=dict(uid=os.getuid(),gid=os.getgid(),
            device='/dev/sdb',majorMinor=number,uuid='12345678-1234-1234-1234-123456789abc',mount=str(self.parent))))
        self.mounts=dict(filesystems=[dict(source='/dev/sdb',target=str(self.parent),fstype='ext4',options='rw,nodev,nosuid',**{'maj:min':number})])
        self.blocks=dict(blockdevices=[dict(name='/dev/sdb',fstype='ext4',label='gse-'+'a'*12,
            uuid=self.value['nativeVolume']['volume']['uuid'],**{'maj:min':number})])
        self.enterContext(patch.object(guest_volume,'MOUNT',str(self.parent)))
        self.enterContext(patch.object(v,'account',return_value=(os.getuid(),os.getgid())))
        self.enterContext(patch.object(v.root,'directory',return_value=dict(kind='directory',uid=0,mode=0o755)))
        def process(argv,data,deadline,*,maximum):
            self.assertEqual(b'',data);self.assertEqual(65536,maximum)
            self.assertIn(argv,(guest_volume.FINDMNT,guest_volume.LSBLK))
            return r.canonical(self.mounts if argv==guest_volume.FINDMNT else self.blocks)
        self.process=self.enterContext(patch.object(p.transport,'process',side_effect=process))
    def test_observes_stat_mount_and_filesystem_identity(self):
        p.context(self.value,time.monotonic()+10);self.assertEqual(2,self.process.call_count)
    def test_missing_remounted_nested_or_unsafe_filesystem_is_rejected(self):
        good_mounts,good_blocks=deepcopy(self.mounts),deepcopy(self.blocks)
        changes=[lambda:self.mounts.update(filesystems=[]),lambda:self.mounts['filesystems'][0].update(options='rw'),
                 lambda:self.mounts['filesystems'][0].update(**{'maj:min':'9:9'}),
                 lambda:self.mounts['filesystems'].append(dict(target=str(self.parent)+'/nested',**{'maj:min':'9:9'})),
                 lambda:self.blocks['blockdevices'][0].update(uuid='changed'),
                 lambda:self.blocks['blockdevices'][0].update(name='/dev/sda')]
        for index,change in enumerate(changes):
            self.mounts,self.blocks=deepcopy(good_mounts),deepcopy(good_blocks);change()
            with self.subTest(index=index),self.assertRaises(ValueError):p.context(self.value,time.monotonic()+10)
    def test_changed_mount_owner_or_mode_blocks_before_commands(self):
        self.parent.chmod(0o755)
        with self.assertRaisesRegex(ValueError,'mounted device'):p.context(self.value,time.monotonic()+10)
        self.process.assert_not_called()


class RunnerGuestStageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frozen=s.resources.admission.workload.load()
        loader=patch.object(s.resources.admission.workload,'load',side_effect=lambda:deepcopy(frozen))
        loader.start();cls.addClassCleanup(loader.stop)
    def setUp(self):
        from . import cloud_runner_resource_qualification as q
        self.q=q;self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.f=q.fixture(self.root/'inputs',self.root/'private');self.disks=[];self.transfers=[];self.fault=None
    def endpoints(self):
        owner=self
        class Volume:
            def __init__(self,api,target,value,recheck):
                self.api,self.value,self.recheck=api,value,recheck;self.calls=[]
                self.block=fake.Block(value['provider'],owner.f['clock']);owner.disks.append(self)
                self.path=owner.root/('volume-'+str(value['provider']['node']))
            def prepare(self):
                self.calls.append(dict(action='prepare'));self.recheck()
                guest_volume._prepare(self.path,self.value['provider'],self.value['access']['user'],self.block,
                                      self.api.deadline,recheck=self.recheck,native=True)
                return self.exchange('check')
            def exchange(self,action):
                self.calls.append(dict(action=action));self.recheck()
                checked=guest_volume._readiness(self.path,self.value['provider'],self.value['access']['user'],self.block,
                                                self.api.deadline,native=True)
                return dict(state='SUCCEEDED',startup=s.c.read(self.path/'receipt.json'),readiness=checked)
        class Package:
            def __init__(self,api,target,value,recheck):
                self.api,self.value,self.recheck=api,p.validate(value),recheck;self.calls=[];owner.transfers.append(self)
                self.parent=owner.root/('packages-'+value['binding']['node']);self.parent.mkdir(mode=0o700)
                self.budget=r.decode(base64.b64decode(token(value,receiver.identity)))
            def exchange(self,action,data,deadline,index=None):
                owner.assertEqual(self.api.deadline,deadline);self.recheck();self.calls.append(dict(action=action,index=index))
                if owner.fault=='part' and self.value['binding']['node']=='node-2' and action=='part':data=b'broken'
                if action=='begin':return receiver.begin(self.parent,self.value,self.budget)
                if action=='part':return receiver.put(self.parent,self.value,self.budget,index,io.BytesIO(data))
                if action=='finish':return receiver.finish(self.parent,self.value,self.budget)
                return receiver.query(self.parent,self.value,self.budget)
        return Volume,Package
    def prepare(self):
        original=s.resources._run
        def run(*args,**kwargs):
            def stage(api,key,root,guests):
                self.api=api
                if self.fault=='archive':(self.f['originals']/'package.zip').write_bytes(b'changed')
                if self.fault=='provider':next(v for v in self.f['http'].resources.values() if v['id']==guests[0]['facts']['provider']['instanceId'])['id']='999999'
                if self.fault=='deadline':self.f['clock'].sleep(601)
                return s._stage(api,key,root,guests,self.f['originals'],self.f['value']['artifacts'],endpoints=self.endpoints())
            return original(*args,**kwargs,guest_stage=stage)
        with patch.object(s.resources,'_run',side_effect=run):return self.q.prepare(self.f,self.root/'evidence')
    def test_admission_to_three_package_installations_retains_partial_active_lease(self):
        result=self.prepare();self.assertEqual('PARTIAL',result['status'],result)
        self.assertEqual('GUEST_PACKAGES_READY',result['stage']);self.assertEqual(3,len(result['guestSetup']))
        self.assertEqual([1,1,1],[disk.block.formats for disk in self.disks]);self.assertEqual(13,self.f['http'].inserts)
        self.assertFalse(result['paidCloud']);self.assertFalse(result['engineWorkloadExecuted']);self.assertFalse(result['fullRemoteQualification'])
        self.assertIsNotNone(self.api.store.get(s.n.LEASE));self.assertEqual(self.api.reserved,self.api.store.get(s.n.LEDGER)[1])
    def test_node_two_package_failure_preserves_charge_and_expiry_cleanup(self):
        self.fault='part';result=self.prepare();self.assertEqual('FAIL',result['status'],result)
        self.assertEqual(dict(phase='guest-setup',type='ValueError'),result['failure']);self.assertEqual(2,len(self.disks))
        self.assertEqual([1,1],[disk.block.formats for disk in self.disks]);self.assertEqual(13,result['confirmedResourceCount'])
        self.assertTrue((self.root/'evidence/guest-setup/node-2/connections.json').exists())
        q=self.q;f=self.f;saved=q.q.cleanup.snapshot(f['http']);lease=self.api.lease
        waiting,unchanged,_=q.resources.replay(f['cfg']['provider'],q.q.pq.SOURCE,saved,self.root/'active',lease['startedAt'])
        self.assertEqual('WAITING',waiting['status']);self.assertEqual(saved,unchanged)
        clean,after,_=q.resources.replay(f['cfg']['provider'],q.q.pq.SOURCE,saved,self.root/'expired',lease['expiresAt']+lease['graceSeconds'])
        self.assertEqual('PASS',clean['status']);_,model,raw,_=q.q.cleanup.restore(after)
        self.assertFalse(model.resources);self.assertNotIn(s.n.LEASE,model.objects)
        ledger=q.g.Store(f['cfg']['provider'],raw,authority=s.n).get(s.n.LEDGER)[1];cost,entries=s.n.inspect_ledger(ledger)
        self.assertEqual(q.q.COST,cost);self.assertEqual({'FAIL'},{v['status'] for v in entries.values()})
    def test_changed_original_package_stops_before_guest_writes(self):
        self.fault='archive';self.assertEqual('FAIL',self.prepare()['status']);self.assertEqual([],self.disks)
    def test_provider_replacement_stops_before_format_or_transfer(self):
        self.fault='provider';self.assertEqual('FAIL',self.prepare()['status']);self.assertEqual(0,self.disks[0].block.formats)
        self.assertEqual([],self.transfers)
    def test_expired_original_preparation_cannot_start_guest_setup(self):
        self.fault='deadline';self.assertEqual('FAIL',self.prepare()['status']);self.assertEqual([],self.disks)
        self.assertEqual([],self.transfers)
    def test_native_constructor_wires_guest_stage_after_bound_resource_and_iap_admission(self):
        from urllib.parse import urlsplit
        from . import cloud_http as h
        f=self.f;q=self.q;a=s.resources.admission;original_read=a.artifacts.c.read
        stage=s._stage
        class Wire:
            offline=False
            def send(self,method,url,*args):
                return (q.q.auth.Provider(f['http']) if urlsplit(url).netloc in ('storage.googleapis.com','compute.googleapis.com')
                        else f['issuer']).send(method,url,*args)
        pins=a.ci.ROOT/'docs/v5x/v5.1/published-controls.json'
        # Native admission and the orchestration execute normally. External
        # provider/credential/IAP and block/mount endpoints are synthetic.
        with patch.object(a.ci,'github',side_effect=lambda path:deepcopy(f['data'][path])),\
             patch.object(a.build,'binding',return_value=f['binding']),\
             patch.object(a.entry,'credential_file',return_value=f['descriptor']),patch.object(h,'Network',Wire),\
             patch.object(s.resources.time,'time',side_effect=f['clock'].wall),\
             patch.dict(a.credentials._Exchange.__init__.__kwdefaults__,clock=f['clock'].seconds,wall=f['clock'].wall),\
             patch.object(a.artifacts.c,'read',side_effect=lambda path:f['controls'] if path==pins else original_read(path)),\
             patch.object(s.iap,'_network_probe',side_effect=lambda api,target,deadline:f['probe'].identity(target,deadline)),\
             patch.object(s,'_stage',side_effect=lambda *args:stage(*args,endpoints=self.endpoints())):
            # Native exchange clocks are explicitly bound to the fixture above;
            # the entry's monotonic clock must use that same controlled clock.
            with patch.object(s.resources.time,'monotonic',side_effect=f['clock'].seconds):
                result=s.prepare_native(f['cfg'],f['env'],q.q.pq.SOURCE,q.q.pq.SOURCE,f['preflight'],f['root'],f['value'],
                    f['approved'],f['originals'],f['key'],self.root/'native-evidence')
        self.assertEqual('PARTIAL',result['status'],result);self.assertEqual('GUEST_PACKAGES_READY',result['stage'])
        self.assertTrue(result['paidAdmission']);self.assertTrue(result['paidCloud']);self.assertFalse(result['engineWorkloadExecuted'])


if __name__=='__main__':unittest.main()
