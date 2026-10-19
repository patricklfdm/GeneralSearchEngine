"""Native factory with mocked external I/O plus real local stream/process tests."""
from copy import deepcopy
from contextlib import ExitStack
import json
import os
from pathlib import Path
from types import SimpleNamespace
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock,mock_open,patch
from . import cloud_iap as iap,cloud_guest_identity as guest,cloud_identity as identity
from . import test_cloud_native_runner as runner_test
from .test_cloud_identity import public_key
from .evidence import strict,encoded,digest

ECHO='import os\nwhile True:\n b=os.read(0,16384)\n if not b:break\n os.write(1,b)\n'


def until(predicate,seconds=5):
    end=time.monotonic()+seconds
    while not predicate():
        if time.monotonic()>=end:raise AssertionError('local helper did not reach expected state')
        time.sleep(.01)


def process_exited(pid):
    # Reaping can remove the process after stat is opened but before read().
    try:return Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()[0] in ('Z','X')
    except (FileNotFoundError,ProcessLookupError):return True


class ProcessExitObservationTest(unittest.TestCase):
    def test_process_disappearance_at_open_or_read_means_exited(self):
        for stage in ('open','read'):
            for error in (FileNotFoundError(2,'No such file'),ProcessLookupError(3,'No such process')):
                opened=mock_open()
                if stage=='open':opened.side_effect=error
                else:opened.return_value.read.side_effect=error
                with self.subTest(stage=stage,error=type(error).__name__),patch.object(Path,'open',opened):
                    self.assertTrue(process_exited(123))

    def test_running_and_sleeping_children_are_not_mistaken_for_exited(self):
        for state,exited in (('R',False),('S',False),('D',False),('T',False),('Z',True),('X',True)):
            with self.subTest(state=state),patch.object(Path,'open',mock_open(read_data='123 (helper with ) in name) '+state+' 1 2 3')):
                self.assertEqual(exited,process_exited(123))

    def test_permission_and_io_errors_are_not_mistaken_for_exited(self):
        for stage in ('open','read'):
            for error in (PermissionError(13,'Permission denied'),OSError(5,'I/O error')):
                opened=mock_open()
                if stage=='open':opened.side_effect=error
                else:opened.return_value.read.side_effect=error
                with self.subTest(stage=stage,error=type(error).__name__),patch.object(Path,'open',opened), \
                     self.assertRaises(type(error)) as raised:
                    process_exited(123)
                self.assertIs(error,raised.exception)


class GuestProbeTest(unittest.TestCase):
    def setUp(self):
        self.user='gse-'+'b'*24
        self.expected=dict(instanceId='123',privateAddress='10.1.2.3',user=self.user,publicKey=public_key())
        self.actual=dict(instanceId='123',privateAddress='10.1.2.3',sshKeys=self.user+':'+public_key(),
                         blockProjectSshKeys='TRUE',enableOslogin='FALSE')

    def observe(self,actual=None,uid=1001):
        with ExitStack() as stack:
            for name in ('getuid','geteuid'):stack.enter_context(patch.object(guest.os,name,return_value=uid))
            for name in ('getgid','getegid'):stack.enter_context(patch.object(guest.os,name,return_value=1002))
            stack.enter_context(patch.object(guest.pwd,'getpwnam',return_value=SimpleNamespace(pw_uid=1001,pw_gid=1002,pw_name=self.user)))
            stack.enter_context(patch.object(guest,'metadata',return_value=self.actual if actual is None else actual))
            return guest.observe(self.expected)

    def test_exact_metadata_effective_user_boot_and_private_address(self):
        value=self.observe();guest.validate(value)
        self.assertEqual('123',value['instanceId']);self.assertEqual(1001,value['uid'])
        self.assertEqual(iap.command.boot_id(),value['bootId'])
        self.assertNotIn('publicKey',value);self.assertNotIn('sshKeys',value)

    def test_metadata_drift_wrong_privileges_and_extra_fields_reject(self):
        for field,value in (('instanceId','124'),('privateAddress','10.1.2.4'),('sshKeys','another key'),
                            ('enableOslogin','TRUE'),('blockProjectSshKeys','FALSE')):
            with self.subTest(field=field),self.assertRaises(ValueError):self.observe(dict(self.actual,**{field:value}))
        with self.assertRaises(ValueError):self.observe(uid=0)
        self.expected['path']='/arbitrary'
        with self.assertRaises(ValueError):self.observe()

    def test_guest_output_has_closed_fields_and_real_uuid_numeric_ids(self):
        value=self.observe()
        for change in (dict(extra=True),dict(uid=True),dict(gid=0),dict(instanceId='001'),dict(bootId='0'*36),
                       dict(privateAddress='8.8.8.8'),dict(user='root')):
            with self.subTest(change=change),self.assertRaises((ValueError,TypeError)):guest.validate(dict(value,**change))

    def test_metadata_disables_proxies_and_reads_only_five_fixed_paths(self):
        response=Mock();response.status=200;response.headers={'Metadata-Flavor':'Google'};response.read.return_value=b'value'
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        opener=Mock();opener.open.return_value=response
        with patch.object(guest.urllib.request,'build_opener',return_value=opener) as build:
            values=guest.metadata()
        self.assertEqual(5,len(values));self.assertEqual(5,opener.open.call_count)
        self.assertEqual({},build.call_args.args[0].proxies)
        for call in opener.open.call_args_list:
            self.assertTrue(call.args[0].full_url.startswith('http://169.254.169.254/computeMetadata/v1/instance/'))
            self.assertEqual(3,call.kwargs['timeout'])
        with self.assertRaises(ValueError):build.call_args.args[1].redirect_request(None,None,None,None,None,None)
        response.headers={}
        with patch.object(guest.urllib.request,'build_opener',return_value=opener),self.assertRaises(ValueError):guest.metadata()

    def test_cli_bounds_duplicate_json_and_reports_only_closed_diagnostic(self):
        for raw in (b'{"user":1,"user":2}',b'not json',b'x'*8193):
            result=subprocess.run([sys.executable,'-I','-S',guest.__file__],input=raw,capture_output=True,timeout=5)
            self.assertEqual(2,result.returncode);self.assertEqual(b'',result.stdout)
            self.assertEqual(b'V52_GUEST_IDENTITY_REJECTED\n',result.stderr)


class LocalForwardTest(unittest.TestCase):
    def setUp(self):
        self.private=tempfile.TemporaryDirectory();self.addCleanup(self.private.cleanup)
        self.calls=[];self.failures=[];self.program=ECHO
        self.group=SimpleNamespace(private=self.private,authorize=self.authorize,fail=self.failures.append)
        self.forward=iap._Forward(self.group,'node-1');self.addCleanup(self.forward.close);self.forward.start()

    def authorize(self,node,path,deadline):
        self.calls.append((node,path,deadline));iap._private(path/'token',b'local-test-not-a-credential')
        return [sys.executable,'-I','-S','-u','-c',self.program],{'PATH':'/usr/bin:/bin'}

    def connect(self):
        value=socket.create_connection(('127.0.0.1',self.forward.port),timeout=5)
        self.addCleanup(value.close);return value

    def test_real_fragmented_pipe_and_tcp_stream_preserves_all_bytes(self):
        client=self.connect();raw=bytes(range(256))*1024;received=bytearray()
        def send():
            for off in range(0,len(raw),1021):client.sendall(raw[off:off+1021])
            client.shutdown(socket.SHUT_WR)
        sender=threading.Thread(target=send);sender.start()
        while True:
            chunk=client.recv(4093)
            if not chunk:break
            received.extend(chunk)
        sender.join(5);self.assertFalse(sender.is_alive());self.assertEqual(raw,received)
        until(lambda:not self.forward.channels[0].thread.is_alive())
        record=self.forward.channels[0].record
        self.assertEqual('CLOSED',record['status']);self.assertEqual(len(raw),record['sentBytes'])
        self.assertEqual(len(raw),record['receivedBytes']);self.assertEqual(1,len(self.calls))
        self.assertEqual([],list(Path(self.private.name).iterdir()))

    def test_connection_close_reaps_owned_process_and_never_replays(self):
        client=self.connect();client.sendall(b'original');self.assertEqual(b'original',client.recv(8))
        channel=self.forward.channels[0];pid=channel.proc.pid
        self.forward.close();self.assertFalse(channel.thread.is_alive());self.assertIsNotNone(channel.proc.returncode)
        self.assertEqual(1,len(self.calls));self.assertFalse(Path('/proc/'+str(pid)).exists())
        self.assertEqual([],list(Path(self.private.name).iterdir()))
        self.forward.close()

    def test_every_new_connection_gets_own_credentials_and_one_process(self):
        for number in range(2):
            client=self.connect();client.sendall(bytes([number]));self.assertEqual(bytes([number]),client.recv(1));client.close()
        self.forward.close();self.assertEqual(2,len(self.calls))
        self.assertEqual(2,len({path for _,path,_ in self.calls}))
        self.assertEqual(2,len({c.proc.pid for c in self.forward.channels}))

    def test_denied_authority_never_starts_process_and_closes_socket(self):
        self.group.authorize=Mock(side_effect=ValueError('sensitive provider body'))
        client=self.connect();self.assertEqual(b'',client.recv(1))
        until(lambda:not self.forward.channels[0].thread.is_alive())
        channel=self.forward.channels[0];self.assertIsNone(channel.proc)
        self.assertEqual('IAP_IDENTITY_OR_AUTHORITY_REJECTED',channel.record['failureCode'])
        self.assertNotIn('sensitive',str(channel.record));self.assertEqual(1,self.group.authorize.call_count)

    def test_denied_iap_is_terminal_and_stderr_never_enters_record(self):
        self.program='import os;os.write(2,b"403 forbidden secret-value");raise SystemExit(1)'
        client=self.connect();self.assertEqual(b'',client.recv(1))
        until(lambda:not self.forward.channels[0].thread.is_alive())
        self.assertEqual('IAP_PERMISSION',self.forward.channels[0].record['failureCode'])
        self.assertEqual(['IAP_PERMISSION'],self.failures);self.assertNotIn('secret-value',str(self.forward.channels[0].record))

    def test_disconnection_is_not_automatically_replayed(self):
        self.program='import os;os.write(2,b"connection reset");raise SystemExit(1)'
        client=self.connect();self.assertEqual(b'',client.recv(1))
        until(lambda:not self.forward.channels[0].thread.is_alive())
        self.assertEqual('SSH_DISCONNECTED',self.forward.channels[0].record['failureCode'])
        self.assertEqual([],self.failures);self.assertEqual(1,len(self.calls))

    def test_diagnostic_bound_fails_closed_and_reaps_process(self):
        self.program='import os,time;os.write(2,b"x"*70000);time.sleep(60)'
        client=self.connect();self.assertEqual(b'',client.recv(1))
        until(lambda:not self.forward.channels[0].thread.is_alive())
        channel=self.forward.channels[0];self.assertEqual('FAIL',channel.record['status'])
        self.assertIsNotNone(channel.proc.returncode);self.assertLess(len(encoded(channel.record)),512)

    def test_original_connection_deadline_does_not_become_a_stream_duration_limit(self):
        with patch.object(iap,'CONNECT_SECONDS',.3):
            client=self.connect();client.sendall(b'1');self.assertEqual(b'1',client.recv(1))
            time.sleep(.35);client.sendall(b'2');self.assertEqual(b'2',client.recv(1))
        self.forward.close();self.assertEqual(1,len(self.calls))

    def test_no_remote_banner_exhausts_original_connect_deadline(self):
        self.program='import time;time.sleep(60)'
        with patch.object(iap,'CONNECT_SECONDS',.1):
            client=self.connect();self.assertEqual(b'',client.recv(1))
            until(lambda:not self.forward.channels[0].thread.is_alive())
        self.assertEqual('IAP_ORIGINAL_CONNECT_TIMEOUT',self.forward.channels[0].record['failureCode'])
        self.assertEqual(1,len(self.calls))

    def test_connection_count_is_bounded_without_starting_extra_sdk(self):
        with patch.object(iap,'MAX_CONNECTIONS',1):
            first=self.connect();first.sendall(b'1');self.assertEqual(b'1',first.recv(1))
            second=self.connect();self.assertEqual(b'',second.recv(1))
        self.assertEqual(1,len(self.calls));self.assertEqual(1,len(self.forward.channels))

    def test_close_stops_process_group_even_after_sdk_parent_exits(self):
        self.program='import os,time\npid=os.fork()\nif pid==0:time.sleep(60)\nelse:os.write(1,str(pid).encode()+b"\\n");os._exit(0)'
        client=self.connect()
        with client.makefile('rb') as stream:pid=int(stream.readline())
        process=dict(bootId=iap.command.boot_id(),pid=pid,
            startTicks=int(Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()[19]))
        def stop():
            try:
                if iap.command.process_alive(process):os.kill(pid,9)
            except ProcessLookupError:pass
        self.addCleanup(stop)
        self.forward.channels[0].proc.wait(timeout=5);self.forward.close()
        until(lambda:process_exited(pid));self.assertEqual(1,len(self.calls))


class RealSshForwardTest(unittest.TestCase):
    def test_real_openssh_crosses_owned_stream_and_rejects_wrong_host_pin(self):
        from scripts.v51.guest_ssh_qualification import Server
        helper=LocalForwardTest('test_connection_close_reaps_owned_process_and_never_replays')
        helper.setUp();self.addCleanup(helper.doCleanups)
        # sshd StrictModes rejects keys below world-writable /tmp. Use the same
        # private repository-target placement as the existing real SSH gate.
        workspace=Path(__file__).resolve().parents[2]/'target';workspace.mkdir(exist_ok=True)
        owned=tempfile.TemporaryDirectory(prefix='v52-iap-ssh-',dir=workspace);self.addCleanup(owned.cleanup)
        root=Path(owned.name);private=root/'ssh';private.mkdir(mode=0o700)
        evidence=root/'evidence';evidence.mkdir()
        with Server(private,evidence) as server:
            helper.program=("import socket,select,os\n"
                "s=socket.create_connection(('127.0.0.1',"+str(server.port)+"),timeout=5)\n"
                "while True:\n"
                " ready,_,_=select.select([0,s],[],[])\n"
                " if 0 in ready:\n"
                "  b=os.read(0,65536)\n"
                "  if not b:break\n"
                "  s.sendall(b)\n"
                " if s in ready:\n"
                "  b=s.recv(65536)\n"
                "  if not b:break\n"
                "  os.write(1,b)\n")
            alias='gse-v52-'+'f'*32;known=root/'known'
            iap.access.pin(known,alias,server.host['publicKey'])
            target=dict(host='127.0.0.1',port=helper.forward.port,user=server.user,
                key=str(private/'client/identity'),knownHosts=str(known),alias=alias)
            args=iap.ssh.ssh.ssh_args(target);args[-1]="python3 -I -S -c 'print(4321)'"
            try:result=iap.transport.process(args,b'',time.monotonic()+15,maximum=128)
            except iap.transport.ProcessError as error:
                raise AssertionError('isolated loopback sshd: '+(evidence/'sshd.log').read_text()[-3000:]) from error
            self.assertEqual(b'4321\n',result)
            known.write_text(alias+' '+server.access['publicKey']+'\n')
            with self.assertRaises(iap.transport.ProcessError) as error:
                iap.transport.process(args,b'',time.monotonic()+15,maximum=128)
            self.assertEqual('SSH_HOST_KEY',error.exception.code)
            self.assertIn('ConnectTimeout=30',iap.ssh.ssh.ssh_args(dict(target,connectSeconds=30)))
            self.assertIn('ConnectTimeout=10',iap.ssh.ssh.ssh_args(target))
            for seconds in (True,0,60,300):
                with self.assertRaisesRegex(ValueError,'connection allowance'):iap.ssh.ssh.ssh_args(dict(target,connectSeconds=seconds))
        helper.forward.close();self.assertEqual(2,len(helper.calls))
        self.assertTrue(all(not c.thread.is_alive() and c.proc.poll() is not None for c in helper.forward.channels))


class DummyForward:
    def __init__(self,group,node):self.group=group;self.node=node;self.port=21000+int(node[-1]);self.channels=[];self.closed=False
    def start(self):pass
    def close(self):self.closed=True


class GuestsLifecycleTest(unittest.TestCase):
    def test_first_forward_close_error_still_closes_other_routes(self):
        group=object.__new__(iap.Guests);group.lock=threading.RLock();group.closed=False;group.stop=threading.Event()
        first=Mock(channels=[]);first.close.side_effect=OSError('first route failure');second=Mock(channels=[])
        group.forwards={'node-1':first,'node-2':second};group.watch_thread=SimpleNamespace(ident=None)
        group.private=Mock();group.failure=None;group.diagnostic=Mock()
        with self.assertRaises(OSError):group.close()
        first.close.assert_called_once_with();second.close.assert_called_once_with();group.private.cleanup.assert_called_once_with()

    def test_failed_entry_preserves_original_error_after_close_failure(self):
        group=object.__new__(iap.Guests);original=ValueError('original probe failed')
        group.checkpoint=Mock(side_effect=original);group.close=Mock(side_effect=OSError('local failure'))
        group.diagnostic=Mock()
        with self.assertRaises(ValueError) as result:
            with group:self.fail('must not execute')
        self.assertIs(original,result.exception);group.close.assert_called_once_with()

    def test_workload_error_is_not_replaced_by_route_cleanup_error(self):
        group=object.__new__(iap.Guests);group.checkpoint=Mock();group.close=Mock(side_effect=OSError('local failure'))
        group.diagnostic=Mock();original=RuntimeError('original workload failed')
        with self.assertRaises(RuntimeError) as result:
            with group:raise original
        self.assertIs(original,result.exception);group.close.assert_called_once_with()


class NativeGuestFactoryTest(unittest.TestCase):
    def setUp(self):
        runner_test.NativeRunnerTest.setUpClass()
        self.base=runner_test.NativeRunnerTest('test_complete_native_factory_original_inputs_resources_and_final_cleanup')
        self.base.setUp();self.addCleanup(self.base.doCleanups);self.root=self.base.root
        self.access=iap.access.generate(self.root/'keys','b'*32);self.key=self.root/'keys/identity'
        self.base.arguments['guest_access']=self.access;self.base.prepare()
        self.session=self.base.open();self.addCleanup(self.session.close)
        for number in (1,2,3):
            vm=next(r for r in self.session.owner.lease['resources'] if r['spec']['kind']=='instance' and r['spec']['node']==number)
            self.base.case.server.host_keys[vm['spec']['name']]=dict(queryPath='hostkeys/',queryValue=dict(items=[
                dict(namespace='hostkeys',key='ssh-ed25519',value=public_key(number+4).split()[1])]))
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(iap,'_gcloud',return_value='/fixed/sdk/gcloud'))
        self.stack.enter_context(patch.object(iap,'_Forward',DummyForward))
        # Replace only the external SSH exchange. Probe response parsers, provider
        # brackets, source/run credentials and actual native lifecycle still run.
        self.stack.enter_context(patch.object(iap.transport,'process',side_effect=self.exchange))
        self.reply_change=lambda value:value

    def exchange(self,args,data,deadline,**kwargs):
        value=strict(data);number=int(next(v for v in args if v.isdecimal() and v.startswith('2100'))[-1])
        return encoded(self.reply_change(dict(schema=guest.SCHEMA,instanceId=value['instanceId'],privateAddress=value['privateAddress'],
            user=value['user'],bootId=f'00000000-0000-4000-8000-{number:012d}',uid=1001,gid=1002)))

    def open(self):return self.session.open_guests(self.key,self.root/'guests')

    def test_native_identity_scoped_token_environment_binding_and_close_order(self):
        # The deployment key may carry a comment; IAP must compare only its wire key.
        subprocess.run(['ssh-keygen','-c','-P','','-C','gse-v52-experiment','-f',str(self.key)],
                       check=True,capture_output=True,timeout=10)
        with self.open() as group:
            self.assertTrue(all(v['paidCloud'] for v in group.observations.values()))
            self.assertTrue(all(v['execution']=='native-v52-provider-observation' for v in group.observations.values()))
            self.assertEqual(3,len(group.guests));bound=group.binding('00000000-0000-4000-8000-000000000123')
            iap.domains.validate(bound);iap.domains.routes(bound)
            self.assertFalse(strict((group.output/'identity.json').read_bytes())['mountedStorageVerified'])
            for number in (1,2):
                folder=Path(group.private.name)/('credential-'+str(number));folder.mkdir(mode=0o700)
                args,env=group.authorize('node-1',folder,iap.time.monotonic()+30)
                self.assertEqual('/fixed/sdk/gcloud',args[0]);self.assertIn('--listen-on-stdin',args)
                self.assertTrue(any(arg.startswith('--project=') for arg in args));self.assertIn('22',args)
                self.assertEqual(0,(folder/'token').stat().st_mode&0o077)
                self.assertNotIn('GH_TOKEN',env);self.assertNotIn('GOOGLE_APPLICATION_CREDENTIALS',env)
                self.assertNotIn('CLOUDSDK_AUTH_ACCESS_TOKEN',env)
                self.assertEqual(str(folder/'config'),env['CLOUDSDK_CONFIG'])
                self.assertNotIn((folder/'token').read_text(),' '.join(args))
            claim=group.checkpoint();self.base.case.clock.now+=1;self.session.owner.renew();self.assertEqual(claim,group.checkpoint())
            original=group.targets['node-1']['port'];group.targets['node-1']['port']+=1
            try:
                with self.assertRaisesRegex(ValueError,'routes changed'):group.checkpoint()
            finally:group.targets['node-1']['port']=original
            outside=self.root/'outside-credentials';outside.mkdir(mode=0o700)
            with self.assertRaisesRegex(ValueError,'credential directory outside'):
                group.authorize('node-1',outside,iap.time.monotonic()+30)
            self.assertEqual([],list(outside.iterdir()))
        self.assertTrue(all(f.closed for f in group.forwards.values()));self.assertFalse(group.watch_thread.is_alive())
        self.assertFalse(Path(group.private.name).exists());self.session.close();self.assertEqual({},self.base.case.server.resources)
        self.assertIsNone(self.base.case.get(iap.runner.a.LEASE))

    def test_changed_guest_identity_closes_all_forwards_without_qualifying(self):
        self.reply_change=lambda value:dict(value,instanceId='987654321')
        with self.assertRaisesRegex(ValueError,'wrong guest'):self.open()
        group=self.session.guests;self.assertTrue(group.closed);self.assertFalse((group.output/'identity.json').exists())
        self.assertTrue(all(f.closed for f in group.forwards.values()));self.assertFalse(group.watch_thread.is_alive())
        self.session.close();self.assertIsNone(self.base.case.get(iap.runner.a.LEASE))

    def test_renewal_failure_stops_existing_routes_and_session_still_cleans_resources(self):
        group=self.open();self.session.heartbeat.failure='SyntheticFailure'
        self.assertTrue(group.stop.wait(5));group.watch_thread.join(5)
        self.assertEqual('IAP_OWNER_OR_PIN_CHANGED',group.failure)
        self.assertTrue(all(f.closed for f in group.forwards.values()))
        with self.assertRaises(ValueError):group.checkpoint()
        self.session.close();self.assertTrue(group.closed);self.assertIsNone(self.base.case.get(iap.runner.a.LEASE))

    def test_guest_close_failure_cannot_bypass_original_resource_cleanup(self):
        group=self.open();original=group.close
        def close():original();raise OSError('synthetic local close failure')
        group.close=close
        with self.assertRaises(OSError):self.session.close()
        self.assertIsNone(self.base.case.get(iap.runner.a.LEASE));self.assertEqual({},self.base.case.server.resources)
        self.assertTrue(self.session.reader.tokens.closed)

    def test_provider_identity_change_during_credential_refresh_rejects_before_sdk(self):
        with self.open() as group:
            name=group.observations['node-1']['facts']['instance']
            vm=next(v for k,v in self.base.case.server.resources.items() if k[2]==name)
            original=vm['id'];changed=False
            def mutate(method,url,body):
                nonlocal changed
                if 'iamcredentials.googleapis.com' in url and not changed:changed=True;vm['id']='987654321'
            self.base.case.change=mutate
            folder=Path(group.private.name)/'changed';folder.mkdir(mode=0o700)
            try:
                with self.assertRaises(iap.runner.h.ApiError) as error:group.authorize('node-1',folder,iap.time.monotonic()+30)
                self.assertEqual(404,error.exception.status)
                self.assertTrue(changed);self.assertFalse((folder/'token').exists())
            finally:vm['id']=original;self.base.case.change=lambda *args:None

    def test_same_boot_cannot_qualify_three_independent_guests(self):
        self.reply_change=lambda value:dict(value,bootId='00000000-0000-4000-8000-000000000001')
        with self.assertRaisesRegex(ValueError,'independent native guests'):self.open()
        self.assertTrue(self.session.guests.closed);self.assertFalse((self.root/'guests/identity.json').exists())

    def test_existing_evidence_directory_is_never_overwritten_on_open_failure(self):
        output=self.root/'guests';output.mkdir();marker=output/'connections.json';marker.write_bytes(b'original retained failure')
        with self.assertRaises(FileExistsError):self.open()
        self.assertEqual(b'original retained failure',marker.read_bytes());self.assertEqual([marker],list(output.iterdir()))
        self.assertTrue(self.session.guests.closed)

    def test_next_history_scope_cannot_silently_change_same_owner_guest_boot(self):
        group=self.open();group.close()
        self.reply_change=lambda value:dict(value,bootId=value['bootId'].replace('8000','9000'))
        with self.assertRaisesRegex(ValueError,'same-owner guest identity changed'):
            self.session.open_guests(self.key,self.root/'next-history')
        self.assertTrue(self.session.guests.closed);self.assertFalse((self.root/'next-history/identity.json').exists())


if __name__=='__main__':unittest.main()
