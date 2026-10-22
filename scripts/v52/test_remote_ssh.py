from copy import deepcopy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
from . import remote_host as h,remote_ssh_guest as g,remote_ssh as ssh,remote_slots as slots,remote_command as c
from .test_remote_slots import owner


class SshGuestTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.parent=Path(self.temp.name);self.root=self.parent/'guest';self.owner=owner()
        self.config=h.config(self.owner,self.root,h.observe(self.parent))
        self.expected={k:self.owner['selection']['binding'][k] for k in ('source','checkoutSha256')}
        patched=patch('scripts.v52.remote_owned_history.source',return_value=self.expected);patched.start();self.addCleanup(patched.stop)
        g.prepare(self.config);self.store=c.CommandStore(self.root/'store',self.owner);self.value=slots.request(self.owner,'execute-history')

    def test_prepare_is_idempotent_without_erasing_original_store(self):
        original=self.store.execute(self.value,lambda *a:{'retained':True})
        self.assertEqual({'state':'PREPARED_NOT_EXECUTED'},g.prepare(self.config))
        self.assertEqual(original,self.store.query(self.value))
        with self.assertRaises(ValueError):g.prepare(dict(self.config,owner=dict(self.owner,session='1'*32)))

    def test_host_source_and_coordinator_drift_reject_before_new_root(self):
        for key in ('bootId','uid','parentDevice','parentInode'):
            changed=deepcopy(self.config);changed['root']=str(self.parent/key)
            changed['host'][key]='11111111-1111-1111-1111-111111111111' if key=='bootId' else changed['host'][key]+1
            if key=='bootId':changed['owner']['bootId']=changed['host'][key]
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'host changed'):g.prepare(changed)
            self.assertFalse(Path(changed['root']).exists())
        changed=dict(self.config,root=str(self.parent/'source'))
        with patch('scripts.v52.remote_owned_history.source',return_value=dict(self.expected,source='0'*40)),self.assertRaisesRegex(ValueError,'source changed'):
            g.prepare(changed)
        self.assertFalse(Path(changed['root']).exists())
        with self.assertRaisesRegex(ValueError,'coordinator'):h.config(dict(self.owner,node='node-2'),self.root,self.config['host'])

    def test_host_pin_and_paths_reject_noncanonical_or_unowned_inputs(self):
        for value in (dict(self.config['host'],uid=True),dict(self.config['host'],bootId=None),dict(self.config['host'],extra=1)):
            with self.assertRaises(ValueError):h.validate_pin(value)
        for value in ('relative','/tmp/../other','/tmp//other','/tmp\x00bad'):
            with self.assertRaises(ValueError):h.path(value)
        alias=self.parent/'alias';alias.symlink_to(self.root,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlink'):h.observe(alias)
        self.parent.chmod(0o755)
        with self.assertRaisesRegex(ValueError,'private parent'):h.observe(self.parent)
        self.parent.chmod(0o700)

    def test_spawn_failure_consumes_launch_and_never_tries_again(self):
        with patch.object(g.subprocess,'Popen',side_effect=OSError('launch failed')) as launch:
            with self.assertRaises(OSError):g.submit(self.root,self.config,self.store,self.value)
            answer=g.submit(self.root,self.config,self.store,self.value)
            self.assertEqual('UNCERTAIN',answer['state']);self.assertEqual(1,launch.call_count)
        self.assertEqual(g.launch_claim(self.value,self.config),c.read(self.root/'launch.json'))

    def test_each_partial_launch_boundary_retains_uncertainty(self):
        for filename in ('launch.json.writing','launch.json'):
            p=self.root/filename
            if filename.endswith('.writing'):p.write_bytes(b'{')
            else:c.write_once(p,g.launch_claim(self.value,self.config))
            with patch.object(g.subprocess,'Popen',side_effect=AssertionError('replayed')):
                self.assertEqual('UNCERTAIN',g.submit(self.root,self.config,self.store,self.value)['state'])
            p.unlink()

    def test_launch_claim_is_forced_before_spawn_and_duplicate_returns_original(self):
        def launch(*args,**kwargs):
            self.assertEqual(g.launch_claim(self.value,self.config),c.read(self.root/'launch.json'))
            self.assertTrue(kwargs['start_new_session']);self.assertIs(kwargs['stdin'],g.subprocess.DEVNULL)
            self.assertEqual('UNCERTAIN',g.submit(self.root,self.config,self.store,self.value)['state'])
            self.store.execute(self.value,lambda *a:{'original':True});return Mock()
        with patch.object(g.subprocess,'Popen',side_effect=launch) as spawn:
            answer=g.submit(self.root,self.config,self.store,self.value)
            self.assertEqual(answer,g.submit(self.root,self.config,self.store,self.value));self.assertEqual(1,spawn.call_count)
        changed=deepcopy(self.value);changed['commandId']='0'*32
        with self.assertRaisesRegex(ValueError,'semantic command identity'):g.submit(self.root,self.config,self.store,changed)

    def test_symlink_or_changed_launch_identity_is_not_retry_permission(self):
        p=self.root/'launch.json';p.symlink_to(self.parent/'missing')
        with self.assertRaises(OSError):g.query(self.root,self.config,self.store,self.value)
        p.unlink();c.write_once(p,dict(g.launch_claim(self.value,self.config),configSha256='0'*64))
        with self.assertRaisesRegex(ValueError,'launch identity'):g.query(self.root,self.config,self.store,self.value)

    def test_worker_enters_owned_history_once_and_retains_exit_process(self):
        c.write_once(self.root/'launch.json',g.launch_claim(self.value,self.config))
        with patch('scripts.v52.remote_owned_history.execute_local',return_value={'state':'SUCCEEDED'}) as execute:
            g.worker(self.root)
            with self.assertRaises(FileExistsError):g.worker(self.root)
            self.assertEqual(1,execute.call_count)
        observed=g.inspect(self.root,self.config)
        self.assertEqual('SUCCEEDED',observed['exited']['state']);self.assertEqual(observed['executor']['process'],observed['exited']['process'])

    def test_worker_failure_has_exit_evidence_without_reentry(self):
        c.write_once(self.root/'launch.json',g.launch_claim(self.value,self.config))
        with patch('scripts.v52.remote_owned_history.execute_local',side_effect=ValueError('original failed')):
            with self.assertRaisesRegex(ValueError,'original failed'):g.worker(self.root)
        self.assertEqual('FAIL',g.inspect(self.root,self.config)['exited']['state'])

    def test_inspection_cannot_change_exit_process_or_invent_liveness(self):
        start=dict(configSha256=h.sha(self.config),process=c.process_identity())
        valid=dict(executor=start,exited=dict(start,state='SUCCEEDED'),alive=False)
        self.assertEqual(valid,g.validate_inspection(valid,self.config))
        for changed in (dict(valid,alive=1),dict(valid,executor=None,alive=True),dict(valid,exited=dict(start,state='UNKNOWN')),
                        dict(valid,exited=dict(start,state='SUCCEEDED',process=dict(start['process'],pid=start['process']['pid']+1)))):
            with self.assertRaises(ValueError):g.validate_inspection(changed,self.config)

    def test_wire_rejection_never_echoes_exception_or_input_secrets(self):
        output=io.BytesIO();data=c.encoded(dict(configSha256=h.sha(self.config),request=self.value))
        with patch.object(g.sys,'argv',['guest','query',str(self.root)]),patch.object(g.sys,'stdin',Mock(buffer=io.BytesIO(data))),\
             patch.object(g.sys,'stdout',Mock(buffer=output)),patch.object(g,'exchange',side_effect=OSError('secret-credential-material')):
            g.main()
        self.assertEqual({'schema':'gse-v52-ssh-error-v1','code':'GUEST_IO_FAILURE'},json.loads(output.getvalue()))

    def test_control_envelope_and_closed_command_reject_before_dispatch(self):
        for envelope in ({'configSha256':'0'*64,'request':self.value},{'configSha256':h.sha(self.config),'request':self.value,'extra':1},
                         {'configSha256':h.sha(self.config),'request':slots.request(self.owner,'collect')}):
            with patch.object(g,'submit',side_effect=AssertionError('entered')),self.assertRaises(ValueError):g.exchange('submit',self.root,envelope)
        with self.assertRaises(ValueError):g.exchange('inspect',self.root,dict(configSha256=h.sha(self.config),request={}))


class SshEndpointTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        key=self.root/'key';key.write_text('fixture-key');key.chmod(0o600)
        known=self.root/'known';known.write_text('gse-v52-'+'a'*32+' ssh-ed25519 AAAA\n');known.chmod(0o600)
        self.target=dict(host='127.0.0.1',port=12345,user='operator',key=str(key),knownHosts=str(known),alias='gse-v52-'+'a'*32)
        self.endpoint=ssh.Endpoint(self.target,h.ROOT);self.addCleanup(self.endpoint.close)
        self.config=h.config(owner(),self.root/'guest',h.observe(self.root));self.endpoint.bind(self.config)

    def test_native_control_deadline_adds_connect_time_only_for_cold_master(self):
        native=ssh.Endpoint(dict(self.target,connectSeconds=60),h.ROOT);self.addCleanup(native.close)
        with patch.object(ssh.time,'monotonic',return_value=100):
            self.assertEqual(130,self.endpoint.control_deadline())
            self.assertEqual(190,native.control_deadline())
            native.master=Mock()
            self.assertEqual(130,native.control_deadline())
            native.disconnect()
            self.assertEqual(190,native.control_deadline())
            for invalid in (True,0,-1,float('inf'),float('nan'),241):
                with self.subTest(seconds=invalid),self.assertRaises(ValueError):native.control_deadline(invalid)
        native.close()
        with self.assertRaises(ValueError):native.control_deadline()

    def test_explicit_original_deadline_is_never_extended_for_native_connection(self):
        native=ssh.Endpoint(dict(self.target,connectSeconds=60),h.ROOT);self.addCleanup(native.close)
        with patch.object(ssh.time,'monotonic',return_value=100), \
             patch.object(ssh.master,'Master',side_effect=TimeoutError('original bound')) as connect:
            with self.assertRaises(TimeoutError):native.probe(self.root,110)
        self.assertEqual(110,connect.call_args.kwargs['connect_deadline'])
        connect.assert_called_once()

    def test_host_pins_and_noninteractive_options_have_no_fallback_or_public_route(self):
        args=ssh.ssh_args(self.target)
        for setting in ('StrictHostKeyChecking=yes','IdentityAgent=none','BatchMode=yes','ControlMaster=no','ProxyCommand=none'):
            self.assertIn(setting,args)
        for host in ('10.1.2.3','example.org','169.254.169.254'):
            with self.assertRaisesRegex(ValueError,'not admitted'):ssh.ssh_args(dict(self.target,host=host))
        Path(self.target['knownHosts']).write_text('another-host ssh-ed25519 AAAA\n')
        with self.assertRaisesRegex(ValueError,'exact host pin'):ssh.ssh_args(self.target)

    def test_changed_credentials_are_rejected_before_connection(self):
        Path(self.target['key']).write_text('changed')
        with patch.object(ssh.master,'Master',side_effect=AssertionError('connected')),self.assertRaisesRegex(ValueError,'credential changed'):
            self.endpoint.probe(self.root,ssh.time.monotonic()+10)

    def test_each_channel_is_sent_once_and_only_next_query_reconnects(self):
        value=slots.request(self.config['owner'],'execute-history');masters=[]
        def connect(*args,**kwargs):
            current=Mock();masters.append(current)
            if len(masters)==1:current.exchange.side_effect=ConnectionError('lost')
            else:current.exchange.return_value=c.encoded(g.reply(self.config,c.envelope(value,'NOT_FOUND')))
            return current
        with patch.object(ssh.master,'Master',side_effect=connect):
            with self.assertRaises(ConnectionError):self.endpoint.submit(value,ssh.time.monotonic()+10)
            self.assertEqual('NOT_FOUND',self.endpoint.query(value,ssh.time.monotonic()+10)['state'])
        self.assertEqual(2,len(masters));self.assertEqual([1,1],[x.exchange.call_count for x in masters]);masters[0].close.assert_called_once()
        self.assertEqual('submit',masters[0].exchange.call_args.args[0][-2]);self.assertEqual('query',masters[1].exchange.call_args.args[0][-2])

    def test_wrong_host_config_receipt_and_safe_error_are_terminal(self):
        value=slots.request(self.config['owner'],'execute-history');answer=g.reply(self.config,c.envelope(value,'NOT_FOUND'))
        for changed in (dict(answer,configSha256='0'*64),dict(answer,host=dict(answer['host'],uid=99999)),dict(answer,extra=1)):
            with self.assertRaisesRegex(ValueError,'host/configuration'):self.endpoint.checked(changed)
        fake=Mock();fake.exchange.return_value=c.encoded(dict(schema='gse-v52-ssh-error-v1',code='HOST_CHANGED'));self.endpoint.master=fake
        with self.assertRaises(ssh.Rejected) as rejected:self.endpoint.query(value,ssh.time.monotonic()+10)
        self.assertFalse(rejected.exception.retryable);self.assertEqual('HOST_CHANGED',rejected.exception.code)

    def test_binding_cannot_change_and_expired_exchanges_cannot_connect(self):
        with self.assertRaisesRegex(ValueError,'already bound'):self.endpoint.bind(dict(self.config,root=str(self.root/'other')))
        for deadline in (ssh.time.monotonic()-1,float('inf'),float('nan'),True,ssh.time.monotonic()+1000):
            with patch.object(ssh.master,'Master',side_effect=AssertionError('connected')),self.assertRaisesRegex(ValueError,'expired/unbounded'):
                self.endpoint.probe(self.root,deadline)
        self.endpoint.target['port']+=1
        with self.assertRaisesRegex(ValueError,'target changed'):self.endpoint.probe(self.root,ssh.time.monotonic()+10)


if __name__=='__main__':unittest.main()
