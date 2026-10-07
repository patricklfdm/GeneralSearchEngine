"""Native session claims/clocks/configurations with modeled provider/OS context."""
import base64
from copy import deepcopy
import io
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import guest_native_session as s, guest_native_owned as owned, cloud_runner_guest_setup as setup
from . import guest_package_receiver as package, guest_native_package as native, cloud_guest as guest
from . import guest_delivery_receiver as r, performance_model as m
from . import cloud_workload_contract as contract
from . import test_cloud_runner_guest_setup as fixture
from . import guest_source_producer as producer, guest_source_transfer as source, guest_bootstrap as boot
from . import guest_session_recovery as recovery, guest_transport as transport


# Replace only the Java seed command, with a real child process producing explicit
# synthetic backup bytes. Session/config validation and producer preparation run.
SEED_COMMAND = """import pathlib, sys
root = pathlib.Path(sys.argv[1]); assert sys.argv[2] == 'prepare'
source = pathlib.Path(sys.argv[4]); source.mkdir()
for name in ('gse-backup-manifest', 'gse-backup-checkpoint', 'gse-backup-metadata'):
    (source/name).write_bytes(name.encode())
"""


class SessionTest(unittest.TestCase):
    workload_raw=m.canonical(contract.load())
    deadline=fixture.NativePackageTest.deadline
    perform=fixture.NativePackageTest.perform
    receive=fixture.NativePackageTest.receive
    def setUp(self):
        fixture.NativePackageTest.setUp(self)
        # Exercise the actual receiver and every session path with the native
        # allowance; a short synthetic deadline hid the old 600-second ceiling.
        self.token=fixture.token(self.value,package.identity,1550)
        self.receive();answer=self.perform('finish')['receipt'];self.base=Path(answer['installed']['package'])
        self.budget=r.decode(base64.b64decode(self.token))
        self.session=dict(schema=s.SCHEMA,packageSha256=m.sha(m.canonical(self.value)),preparation=self.budget,
            leaseExpiresNanos=self.budget['sample']['sampledNanos']+4000*10**9,hosts=['10.0.0.1','10.0.0.2','10.0.0.3'],port=19151)
        self.cfg=s.configuration(self.value,self.session,s.MODES[2])
    def test_session_claim_is_exact_and_cannot_renew_deadline_or_topology(self):
        expected=s.begin(self.base,self.session,self.value)
        self.assertEqual('SUCCEEDED',expected['state']);self.assertEqual(expected,s.begin(self.base,self.session,self.value))
        for name in ('leaseExpiresNanos','hosts','port'):
            bad=deepcopy(self.session)
            bad[name]=bad[name]+1 if type(bad[name]) is int else ['10.0.0.4','10.0.0.5','10.0.0.6']
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'consumed'):s.observe(self.base,bad,self.value)
    def test_controller_recovery_after_unsent_or_lost_begin_uses_one_real_claim(self):
        # Actual receiver filesystem claims; only the connection loss is modeled.
        for sent in (False,True):
            if sent:
                # Use the existing exact claim, proving a later lost reply cannot
                # replace it, rewrite its receipts, or extend its original clock.
                before=(self.base.parent/'native-session/request.json').read_bytes()
            actions=[];report={}
            def exchange(action,deadline):
                actions.append(action)
                if len(actions)==1:
                    if sent:s.begin(self.base,self.session,self.value)
                    raise transport.ProcessError('SSH_DISCONNECTED')
                return s.begin(self.base,self.session,self.value) if action=='begin' else s.observe(self.base,self.session,self.value)
            expected=dict(state='SUCCEEDED',sessionSha256=m.sha(m.canonical(self.session)))
            with patch.object(r,'publish',wraps=r.publish) as publish:
                self.assertEqual(expected,recovery.initialize(exchange,expected,r.time.monotonic()+100,report,sleep=lambda _:None))
            self.assertEqual(['begin','query'] if sent else ['begin','query','begin'],actions)
            self.assertEqual(0 if sent else 2,publish.call_count)
            if sent:self.assertEqual(before,(self.base.parent/'native-session/request.json').read_bytes())
            self.assertEqual(self.budget,package.read(self.base.parent/'deadline.json'))
    def test_long_preparation_reaches_producer_source_and_bootstrap_without_renewal(self):
        from . import guest_source_producer as producer, guest_source_transfer as source, guest_bootstrap as boot
        self.addCleanup(setattr,sys,'path',sys.path[:]);self.addCleanup(setattr,sys,'dont_write_bytecode',sys.dont_write_bytecode)
        configs=[s.configuration(self.value,self.session,s.MODES[2],node='node-'+str(i)) for i in (1,2,3)]
        # Synthetic backup bytes, real export/transfer/receipt validation. No JVM.
        seed=self.parent/'seed';seed.mkdir(mode=0o700);(seed/'source').mkdir()
        for name in boot.SOURCE:(seed/'source'/name).write_bytes(name.encode())
        for name,text in zip(boot.TOPOLOGY,('\n'.join(self.cfg['hosts'])+'\n',
                                          '\n'.join(map(str,self.cfg['ports']))+'\n',self.cfg['groupId']+'\n')):
            (seed/name).write_text(text)
        export=self.parent/'export'
        row=boot.export(seed,export,self.cfg,producer_config=dict(self.cfg,root=str(seed)))
        transfer=source.describe(export,row['descriptorSha256'],self.cfg)
        installed=package.installed
        def dispatch(action,kind,request,*,data=b'',index=None):
            tail=[kind,base64.b64encode(m.canonical(request)).decode()]
            if index is not None:tail.append(str(index))
            return s.dispatch(action,self.value,self.session,tail,io.BytesIO(data))
        # Only the fixed cloud mount is mapped to the real temporary install.
        # Keep installed-byte validation and all three receiver wrappers intact.
        with patch.object(package,'installed',side_effect=lambda _,v:installed(self.parent,v)):
            output=io.BytesIO()
            args=['receiver','begin',base64.b64encode(m.canonical(self.value)).decode(),base64.b64encode(m.canonical(self.session)).decode()]
            with patch.object(sys,'argv',args),patch.object(sys,'stdout',SimpleNamespace(buffer=output)):s.main()
            self.assertEqual('SUCCEEDED',r.decode(output.getvalue())['state'])
            request=dict(schema=producer.SCHEMA,configs=configs)
            self.assertEqual('NOT_FOUND',dispatch('producer','query',request)['receipt']['state'])
            self.assertEqual('RECEIVING',dispatch('source','begin',transfer)['receipt']['state'])
            for chunk in transfer['chunks']:
                with (export/'parts'/chunk['part']).open('rb') as stream:
                    stream.seek(chunk['offset']);data=stream.read(chunk['bytes'])
                dispatch('source','chunk',transfer,data=data,index=chunk['index'])
            self.assertEqual('SUCCEEDED',dispatch('source','finish',transfer)['receipt']['state'])
            request=dict(config=self.cfg,descriptorSha256=row['descriptorSha256'],sourceTransferSha256=m.sha(m.canonical(transfer)))
            self.assertEqual('NOT_FOUND',dispatch('bootstrap','query-install',request)['receipt']['state'])
            self.assertEqual(self.budget,package.read(self.base.parent/'deadline.json'))
            self.context.reset_mock()
            with patch.object(r.time,'monotonic_ns',return_value=self.budget['expiresNanos']),\
                 self.assertRaisesRegex(ValueError,'deadline expired'):
                dispatch('source','query',transfer)
            self.context.assert_not_called()
    def test_plain_package_cannot_admit_native_session(self):
        value=deepcopy(self.value);value['schema']='gse-v51-package-transfer-v1';value.pop('nativeVolume')
        session=dict(self.session,packageSha256=m.sha(m.canonical(value)))
        with self.assertRaisesRegex(ValueError,'package domain'):s.validate(session,value)
    def producer_call(self,kind,request):
        installed=package.installed
        self.addCleanup(setattr,sys,'path',sys.path[:]);self.addCleanup(setattr,sys,'dont_write_bytecode',sys.dont_write_bytecode)
        with patch.object(package,'installed',side_effect=lambda _,v:installed(self.parent,v)):
            return s.dispatch('producer',self.value,self.session,
                [kind,base64.b64encode(m.canonical(request)).decode()],io.BytesIO())['receipt']
    def source_request(self,mode,cell=None):
        return dict(schema=producer.SCHEMA,configs=[s.configuration(self.value,self.session,mode,cell,node='node-'+str(i))
            for i in guest.package.experiment_nodes(mode)])
    def check_real_producer_prepare(self,mode,cell=None):
        s.begin(self.base,self.session,self.value);request=self.source_request(mode,cell)
        def command(base,selected_mode,*,args):
            self.assertEqual(self.base,base);self.assertEqual(s.MODES[0],selected_mode)
            self.assertEqual(str(producer.location(self.base)/'cell'),args[0])
            return [sys.executable,'-I','-c',SEED_COMMAND,*args]
        with patch.object(guest.package,'command',side_effect=command) as launch:
            result=self.producer_call('prepare',request)
            self.assertEqual('SUCCEEDED',result['state'],result)
            self.assertEqual(result,self.producer_call('prepare',request));launch.assert_called_once()
        self.assertEqual(len(request['configs']),len(result['exports']))
        inventories=[]
        for cfg in request['configs']:
            value,folder=producer.retained(self.base,request,cfg['binding']['node'])
            source.check_archive(folder,value);inventories.append(value['bootstrap']['files'])
            self.assertEqual(boot.expected_files(cfg),set(inventories[-1]))
        self.assertTrue(all(v==inventories[0] for v in inventories))
        self.assertFalse(list((producer.location(self.base)/'cell').glob('agents')))
        self.assertEqual(self.budget,package.read(self.base.parent/'deadline.json'))
        # The same derived directory must remain invalid for a persistent service.
        changed=dict(request['configs'][0],root=str(producer.location(self.base)/'cell'))
        with self.assertRaisesRegex(ValueError,'exact configuration'):guest.Service(self.base,changed)
    def test_native_local_producer_prepares_actual_source_once(self):
        self.check_real_producer_prepare(s.MODES[0])
    def test_native_replicated_producer_exports_identical_source_to_three_members(self):
        self.check_real_producer_prepare(s.MODES[2])
    def test_native_configured_producer_prepares_source_for_three_members(self):
        self.check_real_producer_prepare(s.MODES[1])
    def test_native_fault_cell_cannot_use_healthy_source_producer(self):
        s.begin(self.base,self.session,self.value);request=self.source_request(s.MODES[2],'maintenance')
        with patch.object(guest.package,'command') as launch,self.assertRaisesRegex(ValueError,'installed configuration binding'):
            self.producer_call('prepare',request)
        launch.assert_not_called();self.assertFalse(producer.location(self.base).exists())
    def test_native_producer_cannot_substitute_service_lease_for_preparation_deadline(self):
        s.begin(self.base,self.session,self.value);request=self.source_request(s.MODES[0]);prepare=producer.prepare
        def extended(base,req,deadline,check):return prepare(base,req,deadline+1,check)
        with patch.object(producer,'prepare',side_effect=extended),patch.object(guest.package,'command') as launch:
            result=self.producer_call('prepare',request)
            self.assertEqual('FAILED',result['state']);self.assertIn('original preparation deadline',result['error']['message'])
            launch.assert_not_called()
    def test_native_producer_generation_failure_is_terminal(self):
        s.begin(self.base,self.session,self.value);request=self.source_request(s.MODES[0])
        with patch.object(guest.package,'command',return_value=[sys.executable,'-I','-c','raise SystemExit(7)']) as launch:
            result=self.producer_call('prepare',request)
            self.assertEqual('FAILED',result['state']);self.assertIn('guest setup process failed',result['error']['message'])
            self.assertEqual(result,self.producer_call('prepare',request));launch.assert_called_once()
    def test_native_producer_rejects_foreign_root_expiry_and_changed_package_before_launch(self):
        s.begin(self.base,self.session,self.value);request=self.source_request(s.MODES[0])
        with patch.object(guest.package,'command') as launch:
            changed=deepcopy(request);changed['configs'][0]['root']='/tmp/foreign'
            with self.assertRaisesRegex(ValueError,'exact configuration'):self.producer_call('prepare',changed)
            with patch.object(r.time,'monotonic_ns',return_value=self.budget['expiresNanos']),self.assertRaisesRegex(ValueError,'deadline'):
                self.producer_call('prepare',request)
            (self.base/'guest.py').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'inventory'):self.producer_call('prepare',request)
            launch.assert_not_called();self.assertFalse(producer.location(self.base).exists())
    def test_torn_claim_stays_uncertain_and_is_not_recreated(self):
        folder=self.base.parent/'native-session';folder.mkdir(mode=0o700)
        self.assertEqual({'state':'UNCERTAIN'},s.begin(self.base,self.session,self.value))
        self.assertEqual([],list(folder.iterdir()))
    def test_completed_service_uses_original_lease_after_preparation_expires(self):
        s.begin(self.base,self.session,self.value)
        with patch.object(s.time,'monotonic_ns',return_value=self.budget['expiresNanos']+1):
            self.assertEqual(self.session['leaseExpiresNanos']/1e9,s.service_deadline(self.base,self.cfg))
            with self.assertRaisesRegex(ValueError,'deadline'):s.begin(self.base,self.session,self.value)
    def test_expired_lease_or_reboot_blocks_service(self):
        s.begin(self.base,self.session,self.value)
        for patcher in (patch.object(s.time,'monotonic_ns',return_value=self.session['leaseExpiresNanos']),
                        patch.object(r,'boot_identity',return_value='00000000-0000-0000-0000-000000000000')):
            with patcher,self.assertRaisesRegex(ValueError,'expired/boot'):s.service_deadline(self.base,self.cfg)
    def test_configuration_cannot_change_root_group_package_or_peer(self):
        s.begin(self.base,self.session,self.value)
        for field,value in (('root','/tmp/elsewhere'),('groupId','foreign'),('execution',guest.EXECUTION),
                            ('packageManifestSha256','0'*64),('ports',[1,2,3]),('hosts',['10.0.0.2']*3)):
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'configuration'):
                s.service_deadline(self.base,dict(self.cfg,**{field:value}))
    def test_prepared_config_requires_session_before_writing(self):
        with patch.object(guest.c,'write_once') as write,self.assertRaises(FileNotFoundError):guest.prepared_config(self.base,self.cfg)
        write.assert_not_called()
    def test_session_rejects_foreign_package_oversized_lease_public_or_duplicate_peers(self):
        for field,value in (('packageSha256','0'*64),('leaseExpiresNanos',self.budget['sample']['sampledNanos']+5400*10**9+1),
                            ('hosts',['8.8.8.8','10.0.0.2','10.0.0.3']),('hosts',['10.0.0.1']*3),('hosts',['127.0.0.1','127.0.0.2','127.0.0.3'])):
            with self.subTest(field=field),self.assertRaises(ValueError):s.validate(dict(self.session,**{field:value}),self.value)
    def test_closed_dispatch_rejects_arbitrary_actions_and_local_source_paths(self):
        s.begin(self.base,self.session,self.value)
        config=base64.b64encode(m.canonical(self.cfg)).decode()
        with patch.object(package,'installed',return_value=self.base):
            for action,tail in (('shell',[]),('service',[config,'exec','rm']),('bootstrap',['install',base64.b64encode(m.canonical(dict(config=self.cfg,folder='/tmp/source',descriptorSha256='d'*64))).decode()])):
                with self.subTest(action=action),self.assertRaises(ValueError):s.dispatch(action,self.value,self.session,tail,io.BytesIO())
    def test_tampered_installed_bytes_block_before_service_import(self):
        s.begin(self.base,self.session,self.value);(self.base/'guest.py').write_text('must not import')
        # Fixed receiver root is mapped to this synthetic installation only.
        installed=package.installed
        with patch.object(package,'installed',side_effect=lambda _,v:installed(self.parent,v)),\
             self.assertRaisesRegex(ValueError,'inventory'):
            s.dispatch('service',self.value,self.session,[base64.b64encode(m.canonical(self.cfg)).decode(),'ready'],io.BytesIO())
    def test_changed_original_preparation_budget_cannot_start_service(self):
        s.begin(self.base,self.session,self.value)
        bad=deepcopy(self.budget);bad['expiresNanos']+=1
        (self.base.parent/'deadline.json').write_bytes(m.canonical(bad))
        with self.assertRaisesRegex(ValueError,'original package clock'):s.service_deadline(self.base,self.cfg)


class BoundaryTest(unittest.TestCase):
    def test_trusted_session_loads_without_repository(self):
        result=subprocess.run([sys.executable,'-I','-c',setup.trusted_source('session')],cwd='/tmp',capture_output=True,timeout=10)
        self.assertNotEqual(0,result.returncode);self.assertIn(b'not enough values to unpack',result.stderr)
        self.assertNotIn(b'ImportError',result.stderr)
    def test_native_bridge_rejects_plain_configuration_or_fake_services(self):
        for source in ({},object()):
            with self.assertRaises(ValueError):owned.creation(source)
        with self.assertRaises(ValueError):owned.Probe(object(),'/tmp/unused')
