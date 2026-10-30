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
            self.assertTrue(0<call.kwargs['timeout']<=3)
        with self.assertRaises(ValueError):build.call_args.args[1].redirect_request(None,None,None,None,None,None)
        response.headers={}
        with patch.object(guest.urllib.request,'build_opener',return_value=opener),self.assertRaises(ValueError):guest.metadata()

    def test_cli_bounds_duplicate_json_and_reports_only_closed_diagnostic(self):
        for raw in (b'{"user":1,"user":2}',b'not json',b'x'*8193):
            result=subprocess.run([sys.executable,'-I','-S',guest.__file__],input=raw,capture_output=True,timeout=5)
            self.assertEqual(2,result.returncode);self.assertEqual(b'',result.stdout)
            self.assertEqual(b'V52_GUEST_IDENTITY_REJECTED\n',result.stderr)


class LocalForwardTest(unittest.TestCase):
    def test_oidc_chain_deadline_retries_before_single_spawn_without_resending_bytes(self):
        original=self.authorize;calls=[]
        def authorize(node,path,deadline,*,progress=lambda stage:None):
            calls.append(path);progress('credentials')
            if len(calls)==1:
                error=iap.runner.credentials.exchange.CredentialError('OIDC_EXCHANGE_FAILED',failure_kind='timeout')
                error.read_retry=iap.cloud_read_retry.ReadError('credential-oidc',1,'timeout','deadline').detail
                raise error
            return original(node,path,deadline,progress=progress)
        self.group.authorize=authorize
        with patch.object(iap,'ADMISSION_BACKOFF',.01),patch.object(iap.subprocess,'Popen',wraps=subprocess.Popen) as spawn:
            client=self.connect();client.sendall(b'original');self.assertEqual(b'original',client.recv(32))
            client.close();self.forward.close();self.assertEqual(1,spawn.call_count)
        self.assertEqual(2,len(calls));self.assertEqual(1,self.forward.snapshot()['admissionRetries'])

    def test_repeated_typed_credential_deadlines_exhaust_two_admissions_without_spawn(self):
        error=iap.runner.credentials.exchange.CredentialError('OIDC_EXCHANGE_FAILED',failure_kind='timeout')
        error.read_retry=iap.cloud_read_retry.ReadError('credential-oidc',1,'timeout','deadline').detail
        self.group.authorize=Mock(side_effect=error)
        with patch.object(iap,'ADMISSION_BACKOFF',.01),patch.object(iap.subprocess,'Popen') as spawn:
            client=self.connect();self.assertEqual(b'',client.recv(1));self.forward.close();spawn.assert_not_called()
        self.assertEqual(2,self.group.authorize.call_count)
        self.assertEqual('OIDC_EXCHANGE_FAILED',self.forward.snapshot()['lastFailureCode'])

    def test_credential_count_exhaustion_denial_claim_and_forged_errors_are_terminal(self):
        exchange=iap.runner.credentials.exchange
        for code,kind,status,scope,stop in (
            ('OIDC_EXCHANGE_FAILED','timeout',None,'credential-oidc','attempt-limit'),
            ('OIDC_EXCHANGE_FAILED','timeout',None,'credential-sts','deadline'),
            ('OIDC_EXCHANGE_FAILED','http',403,'credential-oidc','deadline'),
            ('OIDC_CLAIMS_REJECTED','timeout',None,'credential-oidc','deadline')):
            error=exchange.CredentialError(code,failure_kind=kind,http_status=status)
            error.read_retry=iap.cloud_read_retry.ReadError(scope,1,'timeout',stop).detail
            self.assertFalse(iap._retry_admission(error))
        error=ValueError('foreign');error.reason_code='OIDC_EXCHANGE_FAILED';error.failure_kind='timeout'
        self.assertFalse(iap._retry_admission(error))

    def setUp(self):
        self.private=tempfile.TemporaryDirectory();self.addCleanup(self.private.cleanup)
        self.calls=[];self.failures=[];self.program=ECHO
        self.group=SimpleNamespace(private=self.private,authorize=self.authorize,fail=self.failures.append)
        self.forward=iap._Forward(self.group,'node-1');self.addCleanup(self.forward.close);self.forward.start()

    def authorize(self,node,path,deadline,*,progress=lambda stage:None):
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
        self.assertEqual(2,len({r['pid'] for r in self.forward.snapshot()['recent']}))

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

    def test_admission_timeout_retries_before_only_sdk_spawn_and_original_bytes(self):
        original=self.authorize;attempts=[]
        def authorize(node,path,deadline,*,progress=lambda stage:None):
            if attempts:self.assertFalse(attempts[0].exists())
            attempts.append(path);progress('identity-before')
            if len(attempts)==1:
                iap._private(path/'token',b'never-public');raise TimeoutError('never-public-provider-body')
            return original(node,path,deadline,progress=progress)
        self.group.authorize=authorize
        with patch.object(iap,'ADMISSION_BACKOFF',.01),patch.object(iap.subprocess,'Popen',wraps=subprocess.Popen) as spawn:
            client=self.connect();client.sendall(b'one original request');self.assertEqual(b'one original request',client.recv(128))
            client.close();self.forward.close()
            self.assertEqual(1,spawn.call_count)
        report=self.forward.snapshot()
        self.assertEqual(2,len(attempts));self.assertEqual(1,report['admissionRetries'])
        self.assertEqual(['FAIL','PASS'],[r['status'] for r in report['lastAdmission']])
        self.assertEqual('identity-before',report['lastAdmission'][0]['phase'])
        self.assertNotIn('never-public',str(report));self.assertEqual([],list(Path(self.private.name).iterdir()))

    def test_repeated_admission_timeouts_stop_after_two_without_sdk(self):
        def authorize(*args,progress=lambda stage:None):progress('credentials');raise TimeoutError('never-public')
        self.group.authorize=Mock(side_effect=authorize)
        with patch.object(iap,'ADMISSION_BACKOFF',.01),patch.object(iap.subprocess,'Popen') as spawn:
            client=self.connect();self.assertEqual(b'',client.recv(1));self.forward.close();spawn.assert_not_called()
        self.assertEqual(2,self.group.authorize.call_count)
        report=self.forward.snapshot();self.assertEqual(1,report['failed'])
        self.assertEqual('IAP_ORIGINAL_CONNECT_TIMEOUT',report['lastFailureCode'])
        self.assertEqual(['FAIL','FAIL'],[r['status'] for r in report['lastAdmission']])
        self.assertEqual([],self.failures)

    def test_typed_read_deadline_retries_before_one_sdk_spawn_and_keeps_original_bytes(self):
        original=self.authorize;paths=[]
        def authorize(node,path,deadline,*,progress=lambda stage:None):
            paths.append(path)
            if len(paths)==1:
                iap._private(path/'token',b'never-public')
                progress('identity-after');time.sleep(max(0,deadline-time.monotonic())+.002)
                raise iap.cloud_read_retry.ReadError('provider-read',1,'connection','deadline')
            self.assertFalse(paths[0].exists())
            return original(node,path,deadline,progress=progress)
        self.group.authorize=authorize
        with patch.object(iap,'ADMISSION_SECONDS',1),patch.object(iap,'ADMISSION_BACKOFF',.001), \
             patch.object(iap.subprocess,'Popen',wraps=subprocess.Popen) as spawn:
            client=self.connect();client.sendall(b'original request')
            self.assertEqual(b'original request',client.recv(128));client.close();self.forward.close()
            self.assertEqual(1,spawn.call_count)
        self.assertEqual(2,len(paths));self.assertNotEqual(paths[0],paths[1])
        report=self.forward.snapshot();self.assertEqual(1,report['admissionRetries'])
        self.assertEqual(['FAIL','PASS'],[r['status'] for r in report['lastAdmission']])
        self.assertEqual('V52_READ_DEADLINE',report['lastAdmission'][0]['reasonCode'])
        self.assertEqual([],self.failures);self.assertEqual([],list(Path(self.private.name).iterdir()))

    def test_real_http_late_response_retries_before_one_sdk_and_preserves_bytes(self):
        from scripts.v51 import cloud_http as http
        from scripts.v51.test_cloud_http_pool import Connection
        from . import cloud_read_retry
        original=self.authorize;attempts=[];sockets=[]
        def authorize(node,path,deadline,*,progress=lambda stage:None):
            attempts.append(path);progress('identity-after')
            if len(attempts)==1:
                def connect(host,timeout):
                    value=Connection(host,timeout);sockets.append(value)
                    def read(maximum):time.sleep(max(0,deadline-time.monotonic())+.01);return b'{}'
                    value.response.read=read;return value
                network=http.Network()
                try:
                    with patch.object(http,'HTTPSConnection',side_effect=connect), \
                         patch.object(http.urllib.request,'getproxies',return_value={}):
                        api=cloud_read_retry.Api(transport=network,tokens=lambda _:'local-test',clock=time.monotonic)
                        api.call('GET','https://compute.googleapis.com/fixed',deadline=deadline)
                finally:network.close()
                self.fail('late response was accepted')
            self.assertFalse(attempts[0].exists())
            return original(node,path,deadline,progress=progress)
        self.group.authorize=authorize
        with patch.object(iap,'ADMISSION_SECONDS',1),patch.object(iap,'ADMISSION_BACKOFF',.01), \
             patch.object(iap.subprocess,'Popen',wraps=subprocess.Popen) as spawn:
            client=self.connect();client.sendall(b'original bytes')
            self.assertEqual(b'original bytes',client.recv(128));client.close();self.forward.close()
            self.assertEqual(1,spawn.call_count)
        report=self.forward.snapshot();self.assertEqual(2,len(attempts));self.assertEqual([],self.failures)
        self.assertEqual(['FAIL','PASS'],[r['status'] for r in report['lastAdmission']])
        self.assertEqual('V52_READ_DEADLINE',report['lastAdmission'][0]['reasonCode'])
        self.assertEqual(1,len(sockets));self.assertTrue(sockets[0].closed)

    def test_repeated_typed_deadlines_stop_after_two_without_sdk_or_replaying_bytes(self):
        def authorize(node,path,deadline,*,progress=lambda stage:None):
            time.sleep(max(0,deadline-time.monotonic())+.002)
            raise iap.cloud_read_retry.ReadError('provider-read',1,'timeout','deadline')
        self.group.authorize=Mock(side_effect=authorize)
        with patch.object(iap,'ADMISSION_SECONDS',.03),patch.object(iap,'ADMISSION_BACKOFF',.001), \
             patch.object(iap.subprocess,'Popen') as spawn:
            client=self.connect();self.assertEqual(b'',client.recv(1));self.forward.close();spawn.assert_not_called()
        self.assertEqual(2,self.group.authorize.call_count)
        self.assertEqual(['V52_READ_DEADLINE'],self.failures)
        self.assertEqual(0,self.forward.snapshot()['sentBytes'])

    def test_exhausted_read_attempts_are_not_restarted_by_iap(self):
        self.group.authorize=Mock(side_effect=iap.cloud_read_retry.ReadError('provider-read',3,'connection','attempt-limit'))
        with patch.object(iap.subprocess,'Popen') as spawn:
            client=self.connect();self.assertEqual(b'',client.recv(1));self.forward.close();spawn.assert_not_called()
        self.assertEqual(1,self.group.authorize.call_count)
        self.assertEqual(['V52_READ_RETRIES_EXHAUSTED'],self.failures)

    def test_typed_deadline_cannot_renew_shared_connection_budget(self):
        def authorize(node,path,deadline,*,progress=lambda stage:None):
            time.sleep(max(0,deadline-time.monotonic())+.002)
            raise iap.cloud_read_retry.ReadError('provider-read',1,'timeout','deadline')
        self.group.authorize=Mock(side_effect=authorize)
        with patch.object(iap,'CONNECT_SECONDS',.03),patch.object(iap,'ADMISSION_BACKOFF',.001), \
             patch.object(iap.subprocess,'Popen') as spawn:
            client=self.connect();self.assertEqual(b'',client.recv(1));self.forward.close();spawn.assert_not_called()
        self.assertEqual(1,self.group.authorize.call_count)

    def test_identity_rejection_after_typed_deadline_stops_without_sdk(self):
        calls=[]
        def authorize(node,path,deadline,*,progress=lambda stage:None):
            calls.append(path)
            if len(calls)==1:
                time.sleep(max(0,deadline-time.monotonic())+.002)
                raise iap.cloud_read_retry.ReadError('provider-read',1,'timeout','deadline')
            raise ValueError('identity changed')
        self.group.authorize=authorize
        with patch.object(iap,'ADMISSION_SECONDS',.03),patch.object(iap,'ADMISSION_BACKOFF',.001), \
             patch.object(iap.subprocess,'Popen') as spawn:
            client=self.connect();self.assertEqual(b'',client.recv(1));self.forward.close();spawn.assert_not_called()
        self.assertEqual(2,len(calls));self.assertEqual(['IAP_IDENTITY_OR_AUTHORITY_REJECTED'],self.failures)

    def test_permission_after_timeout_is_terminal_without_sdk(self):
        self.group.authorize=Mock(side_effect=[TimeoutError(),iap.runner.h.ApiError(403,'GET')])
        with patch.object(iap,'ADMISSION_BACKOFF',.01),patch.object(iap.subprocess,'Popen') as spawn:
            client=self.connect();self.assertEqual(b'',client.recv(1));self.forward.close();spawn.assert_not_called()
        self.assertEqual(2,self.group.authorize.call_count)
        self.assertEqual(['IAP_PROVIDER_HTTP_403'],self.failures)

    def test_admission_cancellation_interrupts_backoff_without_second_attempt(self):
        self.group.authorize=Mock(side_effect=TimeoutError())
        with patch.object(iap,'ADMISSION_BACKOFF',10),patch.object(iap.subprocess,'Popen') as spawn:
            self.connect();until(lambda:self.forward.channels and len(self.forward.channels[0].admission)==1)
            self.forward.close();spawn.assert_not_called()
        self.assertEqual(1,self.group.authorize.call_count)
        self.assertEqual('CLOSED',self.forward.snapshot()['recent'][0]['status'])

    def test_expired_shared_deadline_never_restarts_full_allowance(self):
        deadlines=[]
        def authorize(node,path,deadline,*,progress=lambda stage:None):
            deadlines.append(deadline);time.sleep(max(0,deadline-time.monotonic())+.01);raise TimeoutError()
        self.group.authorize=authorize
        with patch.object(iap,'CONNECT_SECONDS',.04),patch.object(iap,'ADMISSION_BACKOFF',.001), \
             patch.object(iap.subprocess,'Popen') as spawn:
            client=self.connect();self.assertEqual(b'',client.recv(1));self.forward.close();spawn.assert_not_called()
        self.assertEqual(1,len(deadlines))

    def test_late_successful_authorization_cannot_spawn_sdk(self):
        original=self.authorize
        def late(node,path,deadline,*,progress=lambda stage:None):
            args=original(node,path,deadline,progress=progress)
            time.sleep(max(0,deadline-time.monotonic())+.01);return args
        self.group.authorize=late
        with patch.object(iap,'ADMISSION_SECONDS',.02),patch.object(iap,'ADMISSION_BACKOFF',.001), \
             patch.object(iap.subprocess,'Popen') as spawn:
            client=self.connect();self.assertEqual(b'',client.recv(1));self.forward.close();spawn.assert_not_called()
        self.assertEqual(2,len(self.calls));self.assertTrue(all(not path.exists() for _,path,_ in self.calls))

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

    def test_sequential_connections_reuse_slots_beyond_old_lifetime_limit(self):
        # The fifth experiment history crosses 64 even without retries. Exercise
        # actual sockets, SDK stand-ins, byte delivery and credential cleanup.
        pids=set()
        for number in range(70):
            with self.subTest(connection=number+1):
                client=self.connect();client.sendall(b'x');self.assertEqual(b'x',client.recv(1))
                channel=self.forward.channels[-1];pids.add(channel.proc.pid)
                client.shutdown(socket.SHUT_WR);self.assertEqual(b'',client.recv(1));client.close()
                until(lambda:not channel.thread.is_alive())
                self.assertIsNotNone(channel.proc.returncode)
                self.assertEqual([],list(Path(self.private.name).iterdir()))
                self.assertLessEqual(len(self.forward.channels),4)
        self.forward.close();report=self.forward.snapshot()
        self.assertEqual(70,len(self.calls));self.assertEqual(70,len(pids))
        self.assertEqual(70,len({path for _,path,_ in self.calls}))
        self.assertEqual(70,report['accepted']);self.assertEqual(70,report['completed'])
        self.assertEqual(0,report['active']);self.assertEqual(0,report['failed'])
        self.assertEqual(0,report['capacityRejections']);self.assertEqual(1,report['peakActive'])
        self.assertEqual(70,report['sentBytes']);self.assertEqual(70,report['receivedBytes'])
        self.assertEqual(list(range(7,71)),[r['ordinal'] for r in report['recent']])
        self.assertEqual(6,report['historyDropped']);self.assertEqual([],self.forward.channels)
        self.assertEqual([],self.failures)

    def test_active_limit_rejects_without_spawn_then_reuses_a_completed_slot(self):
        clients=[]
        for _ in range(4):
            client=self.connect();client.sendall(b'x');self.assertEqual(b'x',client.recv(1));clients.append(client)
        denied=self.connect();self.assertEqual(b'',denied.recv(1))
        self.assertEqual(4,len(self.calls));channel=self.forward.channels[0]
        clients[0].shutdown(socket.SHUT_WR);self.assertEqual(b'',clients[0].recv(1));clients[0].close()
        until(lambda:not channel.thread.is_alive())
        replacement=self.connect();replacement.sendall(b'y');self.assertEqual(b'y',replacement.recv(1))
        report=self.forward.snapshot()
        self.assertEqual(5,report['accepted']);self.assertEqual(4,report['active'])
        self.assertEqual(4,report['peakActive']);self.assertEqual(1,report['capacityRejections'])
        self.assertEqual(1,report['completed']);self.assertEqual(5,len(self.calls))
        self.forward.close();report=self.forward.snapshot()
        self.assertEqual(5,report['completed']);self.assertEqual(0,report['active'])
        self.assertEqual([],list(Path(self.private.name).iterdir()));self.assertEqual([],self.failures)

    def test_slot_is_held_until_private_cleanup_finishes(self):
        entered=threading.Event();release=threading.Event();self.addCleanup(release.set)
        original=iap.tempfile.TemporaryDirectory.cleanup
        def cleanup(directory):
            if Path(directory.name).parent==Path(self.private.name):
                entered.set();release.wait(5)
            original(directory)
        with patch.object(iap,'MAX_ACTIVE',1),patch.object(iap.tempfile.TemporaryDirectory,'cleanup',cleanup):
            client=self.connect();client.sendall(b'x');self.assertEqual(b'x',client.recv(1))
            channel=self.forward.channels[0];client.shutdown(socket.SHUT_WR);self.assertEqual(b'',client.recv(1))
            self.assertTrue(entered.wait(5))
            denied=self.connect();self.assertEqual(b'',denied.recv(1));self.assertEqual(1,len(self.calls))
            self.assertEqual(1,self.forward.snapshot()['active'])
            release.set();until(lambda:not channel.thread.is_alive())
            replacement=self.connect();replacement.sendall(b'y');self.assertEqual(b'y',replacement.recv(1))
        self.forward.close();self.assertEqual(2,self.forward.snapshot()['completed'])

    def test_failure_counts_survive_bounded_history_eviction(self):
        self.program='import os;os.write(2,b"connection reset");raise SystemExit(1)'
        failed=self.connect();self.assertEqual(b'',failed.recv(1))
        until(lambda:not self.forward.channels[0].thread.is_alive());self.program=ECHO
        # A small ring makes eviction quick without changing active capacity.
        self.forward.recent=iap.deque(maxlen=2)
        for _ in range(3):
            client=self.connect();client.sendall(b'x');self.assertEqual(b'x',client.recv(1))
            channel=self.forward.channels[-1];client.close();until(lambda:not channel.thread.is_alive())
        self.forward.close();report=self.forward.snapshot()
        self.assertEqual(1,report['failed']);self.assertEqual('SSH_DISCONNECTED',report['lastFailureCode'])
        self.assertEqual(2,report['historyDropped']);self.assertEqual([3,4],[r['ordinal'] for r in report['recent']])
        self.assertTrue(all(r['failureCode'] is None for r in report['recent']))

    def test_simultaneous_terminal_failures_stop_all_routes_without_join_deadlock(self):
        barrier=threading.Barrier(2);original=self.authorize
        def denied(*args,**kwargs):
            original(*args,**kwargs);barrier.wait(5);raise ValueError('never-public-authority')
        self.group.authorize=denied;self.group.lock=threading.RLock();self.group.stop=threading.Event()
        self.group.failure=None;self.group.forwards={'node-1':self.forward}
        self.group.fail=lambda code:iap.Guests.fail(self.group,code)
        first=self.connect();second=self.connect()
        until(lambda:len(self.calls)==2)
        until(lambda:all(not c.thread.is_alive() for c in self.forward.channels))
        self.assertEqual(b'',first.recv(1));self.assertEqual(b'',second.recv(1))
        self.forward.close();report=self.forward.snapshot()
        self.assertTrue(self.group.stop.is_set());self.assertEqual('IAP_IDENTITY_OR_AUTHORITY_REJECTED',self.group.failure)
        self.assertEqual(2,report['completed']);self.assertGreaterEqual(report['failed'],1)
        self.assertEqual([],list(Path(self.private.name).iterdir()))

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
            self.assertIn('ConnectTimeout=60',iap.ssh.ssh.ssh_args(dict(target,connectSeconds=60)))
            for seconds in (True,0,61,300):
                with self.assertRaisesRegex(ValueError,'connection allowance'):iap.ssh.ssh.ssh_args(dict(target,connectSeconds=seconds))
        helper.forward.close();self.assertEqual(2,len(helper.calls))
        self.assertEqual([],helper.forward.channels);self.assertEqual(2,helper.forward.snapshot()['completed'])
        self.assertEqual([],list(Path(helper.private.name).iterdir()))


class DummyForward:
    def __init__(self,group,node):self.group=group;self.node=node;self.port=21000+int(node[-1]);self.channels=[];self.closed=False
    def start(self):pass
    def close(self):self.closed=True
    def stop_channels(self):self.closed=True
    def snapshot(self):return dict(accepted=0,completed=0,failed=0,active=0,peakActive=0,capacityRejections=0,
                                  sentBytes=0,receivedBytes=0,historyDropped=0,lastFailureCode=None,recent=[],activeRecords=[])


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


class ColdAdmissionHeadroomTest(unittest.TestCase):
    def test_two_admissions_leave_time_for_sdk_and_ssh_without_replaying(self):
        now=[100.0];ends=[];paths=[]
        with tempfile.TemporaryDirectory() as directory:
            def authorize(node,path,deadline,*,progress):
                paths.append(path);ends.append(deadline);progress('identity-after')
                if len(ends)==1:
                    now[0]=deadline;raise TimeoutError('first identity read deadline')
                self.assertFalse(paths[0].exists())
                now[0]+=45  # Successful but slower than the old 30-second admission.
                return ['fixture-sdk'],{}
            group=SimpleNamespace(private=SimpleNamespace(name=directory),authorize=authorize,fail=Mock())
            channel=iap._Channel(SimpleNamespace(group=group,node='node-1'),Mock(),1)
            def wait(seconds):now[0]+=seconds;return False
            def pump(deadline):
                now[0]+=50  # SDK startup/SSH banner must retain their own headroom.
                iap._remaining(deadline)
            with patch.object(iap.time,'monotonic',side_effect=lambda:now[0]), \
                 patch.object(channel.stop,'wait',side_effect=wait),patch.object(channel,'terminate'), \
                 patch.object(channel,'pump',side_effect=pump) as stream,patch.object(iap.subprocess,'Popen') as spawn:
                channel.run()
            self.assertEqual('CLOSED',channel.record['status'])
            self.assertEqual([190,281],ends);spawn.assert_called_once();stream.assert_called_once_with(340)
            self.assertEqual(['FAIL','PASS'],[row['status'] for row in channel.admission])
            self.assertEqual([],list(Path(directory).iterdir()));group.fail.assert_not_called()


    def test_native_guest_probe_keeps_full_cold_connection_and_command_allowance(self):
        now=[100.0];group=object.__new__(iap.Guests)
        group.probe_source=Path(guest.__file__).read_text();group.guests={}
        group.targets={'node-1':{'connectSeconds':240}}
        facts=dict(instanceId='123456',privateAddress='10.77.0.11')
        group.observations={'node-1':{'facts':facts}};group.observe=Mock()
        group.session=SimpleNamespace(owner=SimpleNamespace(request={'guestAccess':{'user':'gse-'+'a'*24,'publicKey':public_key(1)}}))
        response=dict(schema=guest.SCHEMA,**facts,user='gse-'+'a'*24,bootId='00000000-0000-4000-8000-000000000001',uid=1001,gid=1002)
        def process(args,data,deadline,**kwargs):
            now[0]+=250;iap._remaining(deadline);return encoded(response)
        with patch.object(iap.time,'monotonic',side_effect=lambda:now[0]), \
             patch.object(iap.ssh.ssh,'ssh_args',return_value=['ssh','fixed']), \
             patch.object(iap.transport,'process',side_effect=process) as exchange:
            self.assertEqual(response,group.probe('node-1'))
        exchange.assert_called_once();self.assertEqual(400,exchange.call_args.args[2])
        self.assertEqual([190,440],[call.args[1] for call in group.observe.call_args_list])


class AdmissionDeadlineTest(unittest.TestCase):
    def setUp(self):
        self.private=tempfile.TemporaryDirectory();self.addCleanup(self.private.cleanup)
        self.directory=Path(self.private.name)/'channel';self.directory.mkdir(mode=0o700)
        self.api=SimpleNamespace(lock=threading.RLock(),deadline=float('inf'),tokens=Mock())
        self.owner=SimpleNamespace(lock=threading.RLock())
        self.group=object.__new__(iap.Guests);self.group.private=self.private
        self.group.session=SimpleNamespace(owner=self.owner,api=self.api)
        self.group.observations={'node-1':{}}
        self.group.cheap_check=Mock();self.group.observe=Mock(return_value={})

    def authorize(self):
        self.phases=[]
        return self.group.authorize('node-1',self.directory,time.monotonic()+.05,progress=self.phases.append)

    def test_authority_queue_timeout_is_typed_and_does_not_touch_api(self):
        self.owner.lock=Mock();self.owner.lock.acquire.return_value=False
        with self.assertRaises(TimeoutError) as result:self.authorize()
        self.assertTrue(iap._retry_admission(result.exception));self.api.tokens.assert_not_called()
        self.owner.lock.release.assert_not_called();self.assertEqual('owner-lock',self.phases[-1])

    def test_sdk_environment_preserves_runtime_without_ambient_credentials(self):
        self.group.sdk='/fixed/sdk/gcloud'
        self.group.observe.return_value=dict(facts=dict(instance='vm'),project='project',zone='zone')
        self.api.tokens.return_value=iap.runner.h.AccessToken('synthetic-token',time.monotonic()+300)
        with patch.dict(os.environ,{'LD_LIBRARY_PATH':'/untrusted/lib','PYTHONPATH':'/untrusted/python',
                                    'GOOGLE_APPLICATION_CREDENTIALS':'private-credentials','GH_TOKEN':'private-token'}):
            args,env=self.group.authorize('node-1',self.directory,time.monotonic()+5)
        self.assertEqual(str(Path(sys.base_prefix).resolve()/'lib'),env.get('LD_LIBRARY_PATH'))
        self.assertEqual(sys.executable,env['CLOUDSDK_PYTHON'])
        self.assertEqual(str(self.directory/'config'),env['CLOUDSDK_CONFIG'])
        for name in ('GOOGLE_APPLICATION_CREDENTIALS','GH_TOKEN','PYTHONPATH','LD_PRELOAD'):
            self.assertNotIn(name,env)
        self.assertNotIn('/untrusted',str(env));self.assertNotIn('synthetic-token',' '.join(args))

    def test_api_queue_timeout_releases_owner_without_releasing_unowned_lock(self):
        self.owner.lock=Mock();self.api.lock=Mock();self.api.lock.acquire.return_value=False
        with self.assertRaises(TimeoutError):self.authorize()
        self.owner.lock.release.assert_called_once_with();self.api.lock.release.assert_not_called()
        self.assertEqual('api-lock',self.phases[-1]);self.api.tokens.assert_not_called()

    def test_late_identity_cannot_request_token_or_write_credential(self):
        self.group.observe.side_effect=lambda node,end:time.sleep(max(0,end-time.monotonic())+.01)
        with self.assertRaises(TimeoutError):self.authorize()
        self.assertEqual(float('inf'),self.api.deadline);self.api.tokens.assert_not_called()
        self.assertEqual([],list(self.directory.iterdir()))

    def test_only_this_expired_provider_admission_deadline_can_use_next_attempt(self):
        deadline=iap.cloud_read_retry.ReadError('provider-read',1,'connection','deadline')
        with patch.object(iap.time,'monotonic',return_value=100):
            self.assertTrue(iap._retry_admission(deadline,attempt_deadline=100))
            self.assertFalse(iap._retry_admission(deadline,attempt_deadline=101))
            self.assertFalse(iap._retry_admission(deadline))
            for scope in iap.cloud_read_retry.SCOPES-{'provider-read'}:
                error=iap.cloud_read_retry.ReadError(scope,1,'connection','deadline')
                self.assertFalse(iap._retry_admission(error,attempt_deadline=99))
            exhausted=iap.cloud_read_retry.ReadError('provider-read',3,'timeout','attempt-limit')
            self.assertFalse(iap._retry_admission(exhausted,attempt_deadline=99))

    def test_known_credential_timeout_is_retryable_but_security_rejections_are_not(self):
        for error in (TimeoutError(),ConnectionError(),iap.runner.credentials.ContextError('DEADLINE')):
            self.assertTrue(iap._retry_admission(error))
        for error in (ValueError('deadline'),iap.runner.credentials.ContextError('RUN_OBSERVATION'),
                      iap.transport.ProcessError('IAP_PERMISSION'),iap.transport.ProcessError('SSH_HOST_KEY'),
                      iap.runner.h.ApiError(403,'GET'),iap.runner.h.ApiError(404,'GET'),
                      iap.runner.p.ControlReadError('V52_CONTROL_LEASE_INACTIVE')):
            self.assertFalse(iap._retry_admission(error))
        self.assertEqual('V52_CONTROL_LEASE_INACTIVE',iap._safe(iap.runner.p.ControlReadError('V52_CONTROL_LEASE_INACTIVE')))

    def test_original_credential_failure_code_survives_without_becoming_retryable(self):
        error=iap.runner.credentials.exchange.CredentialError('OIDC_URL_PATH')
        self.assertEqual('OIDC_URL_PATH',iap._safe(error));self.assertFalse(iap._retry_admission(error))


class NativeGuestFactoryTest(unittest.TestCase):
    def setUp(self):
        runner_test.NativeRunnerTest.setUpClass()
        self.base=runner_test.NativeRunnerTest('test_complete_native_factory_original_inputs_resources_and_final_cleanup')
        self.addCleanup(self.base.doCleanups);self.base.setUp();self.root=self.base.root
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

    def test_operator_trimmed_secret_matches_native_iap_key_checks(self):
        from . import cloud_operator as operator
        subprocess.run(['ssh-keygen','-c','-P','','-C','gse-v52-experiment','-f',str(self.key)],
                       check=True,capture_output=True,timeout=10)
        secret=self.key.read_text().rstrip('\r\n')
        with patch.dict(os.environ,{'V52_SSH_KEY':secret}):
            with operator.private_key() as (key,public):
                self.assertEqual(self.access['publicKey'],public);self.key=key
                with self.open() as group:
                    self.assertEqual(3,len(group.guests));group.checkpoint()
                    self.assertNotIn('V52_SSH_KEY',os.environ)
                    self.assertEqual(secret+'\n',key.read_text())
                self.assertTrue(group.closed)
            self.assertFalse(key.exists());self.assertFalse(key.parent.exists())
        self.session.close();self.assertEqual({},self.base.case.server.resources)
        self.assertIsNone(self.base.case.get(iap.runner.a.LEASE))

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

    def test_numeric_disk_disconnect_recovers_then_persistent_failure_stops_without_mutation(self):
        from . import cloud_read_retry as retry
        with self.open() as group:
            row=next(r for r in self.session.owner.lease['resources'] if r['spec']['kind']=='disk' and
                     r['spec']['purpose']=='data' and r['spec']['node']==2)
            endpoint=self.session.owner.provider.endpoint(row['spec'],row['id']);faults=[]
            def transient(method,url,body):
                if method=='GET' and url==endpoint and not faults:
                    faults.append(url);raise ConnectionError('reproduced numeric-disk GET disconnect')
            # The owner's independent heartbeat may renew its lease while a
            # read backs off. It is not a replay of a resource/ledger mutation.
            def mutations():return [event for event in self.base.mutations() if
                iap.runner.a.LEASE not in iap.runner.p.url.unquote(event['url'])]
            before=len(mutations());self.base.case.change=transient
            group.observe('node-2',iap.time.monotonic()+30)
            self.assertEqual([endpoint],faults);self.assertEqual(before,len(mutations()))
            attempts=[]
            def persistent(method,url,body):
                if method=='GET' and url==endpoint:
                    attempts.append(url);raise ConnectionError('repeated disconnect')
            self.base.case.change=persistent
            try:
                with self.assertRaises(retry.ReadError) as caught:group.observe('node-2',iap.time.monotonic()+30)
                self.assertEqual(3,len(attempts));self.assertFalse(caught.exception.retryable)
                self.assertEqual(before,len(mutations()))
            finally:self.base.case.change=lambda *args:None
        self.session.close();self.assertEqual({},self.base.case.server.resources)
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
