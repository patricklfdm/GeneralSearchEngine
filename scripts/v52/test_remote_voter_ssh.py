from copy import deepcopy
import io
import os
from pathlib import Path
import shlex
import stat
import struct
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from . import remote_voter as v,remote_voter_relay as relay,remote_voter_ssh as ssh,remote_voter_ssh_evidence as e
from . import test_remote_voter as fixtures


class ReaderTest(unittest.TestCase):
    def reader(self,raw):
        source=io.BytesIO(raw)
        stream=SimpleNamespace(read_deadline=time.monotonic()+2,proc=SimpleNamespace(stdout=Mock()),check_exit=Mock())
        return ssh.Reader(stream),source
    def read(self,reader,source):
        with patch.object(ssh.select,'select',return_value=([reader.stream.proc.stdout],[],[])),\
             patch.object(ssh.os,'read',side_effect=lambda fd,n:source.read(n)):
            return reader.readline(v.FRAME+1)

    def test_fragmented_and_multiple_frames_preserve_exact_bytes(self):
        reader,source=self.reader(b'{"seq":1}\n{"seq":2}\n')
        self.assertEqual(b'{"seq":1}\n',self.read(reader,source));self.assertEqual(b'{"seq":2}\n',self.read(reader,source))
        self.assertEqual(b'',self.read(reader,source));reader.stream.check_exit.assert_called_once()

    def test_partial_frame_is_not_invented_response(self):
        reader,source=self.reader(b'{"seq":1')
        with patch.object(reader,'readline',side_effect=lambda n:self.read(ssh.Reader(reader.stream),source)):
            with self.assertRaisesRegex(ValueError,'truncated'):v.receive(reader)

    def test_safe_guest_error_is_permanent_and_does_not_echo_wire_secrets(self):
        reader,source=self.reader(v.encoded(dict(schema=relay.ERROR_SCHEMA,code='SOURCE_CHANGED'))+b'\n')
        with self.assertRaises(ssh.Rejected) as rejected:self.read(reader,source)
        self.assertFalse(rejected.exception.retryable);self.assertEqual('SOURCE_CHANGED',rejected.exception.code)
        reader,source=self.reader(v.encoded(dict(schema=relay.ERROR_SCHEMA,code='SOURCE_CHANGED',secret='not-for-output'))+b'\n')
        with self.assertRaisesRegex(ValueError,'error envelope'):self.read(reader,source)

    def test_handshake_timeout_and_oversize_are_bounded(self):
        reader,source=self.reader(b'');reader.stream.read_deadline=time.monotonic()-1
        with self.assertRaisesRegex(TimeoutError,'handshake'):self.read(reader,source)
        reader,source=self.reader(b'x'*(v.FRAME+100))
        self.assertEqual(v.FRAME+1,len(self.read(reader,source)))


class EndpointTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        for name,data in (('key','key'),('known','gse-v52-'+'a'*32+' ssh-ed25519 AAAA\n')):
            p=self.root/name;p.write_text(data);p.chmod(0o600)
        self.target=dict(host='127.0.0.1',port=12000,user='operator',key=str(self.root/'key'),knownHosts=str(self.root/'known'),alias='gse-v52-'+'a'*32)
        self.endpoint=ssh.Endpoint(self.target,v.h.ROOT);self.addCleanup(self.endpoint.close)

    def test_persistent_channel_uses_fixed_entry_and_disallows_ssh_fallback(self):
        master=Mock();master.args=self.endpoint.args[:-1];self.endpoint.master=master
        with patch.object(ssh,'Stream',return_value='stream') as stream:
            self.assertEqual('stream',self.endpoint.open(self.root/'node-control','a'*64,time.monotonic()+30))
        argv=stream.call_args.args[0];self.assertIn('ProxyCommand=false',argv)
        remote=shlex.split(argv[-1]);self.assertEqual(['python3','-I','-c',relay.LAUNCH],remote[:4])
        self.assertEqual([str(v.h.ROOT),str(self.root/'node-control'),'a'*64],remote[4:])
        self.assertEqual(1,stream.call_count)

    def test_changed_pin_or_target_cannot_open_another_channel(self):
        with patch.object(ssh,'Stream') as stream:
            (self.root/'key').write_text('changed')
            with self.assertRaisesRegex(ValueError,'credential changed'):self.endpoint.open(self.root,'a'*64,time.monotonic()+30)
            stream.assert_not_called()
        with self.assertRaisesRegex(ValueError,'not admitted'):ssh.public_target(dict(self.target,host='10.0.0.1'))

    def test_connect_failure_does_not_retry_or_fall_back(self):
        with patch.object(ssh.ssh.master,'Master',side_effect=ConnectionError('lost')) as connect:
            with self.assertRaises(ConnectionError):self.endpoint.open(self.root,'a'*64,time.monotonic()+30)
        self.assertEqual(1,connect.call_count);self.assertIsNone(self.endpoint.master)

    def test_target_binding_rejected_before_starting_local_service(self):
        with patch.object(v.Client,'__init__',side_effect=AssertionError('started')):
            with self.assertRaisesRegex(ValueError,'target binding'):ssh.Client(self.root,'node-1',{},[],target=self.target)
        public=ssh.public_target(self.target);self.assertEqual({'host','port','user','alias','hostPinSha256'},set(public))
        self.assertNotIn('key',str(public))

    def test_channel_attempt_limit_does_not_relaunch_original_voter(self):
        client=object.__new__(ssh.Client);client.channels=[None]*4;client.endpoint=Mock()
        with self.assertRaisesRegex(ValueError,'attempts exhausted'):client.open_channel()
        client.endpoint.open.assert_not_called()


class RelayTest(unittest.TestCase):
    def test_relay_validates_existing_service_and_exact_socket_peer_without_launching(self):
        with tempfile.TemporaryDirectory() as directory:
            control=Path(directory);config={'socket':str(control/'channel'),'host':{'uid':10},'session':'s'}
            identity={'host':config['host'],'session':'s','service':{'pid':42},'jvm':{'pid':43}}
            sha=v.digest(v.encoded(config));records=[config,{'configSha256':sha},identity,{'configSha256':sha,'service':identity['service']}]
            channel=Mock();channel.getsockopt.return_value=struct.pack('3i',42,10,10)
            with patch.object(v.c,'read',side_effect=records),patch.object(v,'validate_config') as check,\
                 patch.object(v.c,'validate_process'),patch.object(v.c,'process_alive',return_value=True),\
                 patch.object(Path,'lstat',return_value=SimpleNamespace(st_mode=stat.S_IFSOCK|0o600,st_uid=os.getuid())),\
                 patch.object(relay.socket,'socket',return_value=channel),patch.object(v.subprocess,'Popen') as spawn:
                self.assertIs(channel,relay.connect(control,sha));check.assert_called_once_with(config,control,fresh_socket=False)
                spawn.assert_not_called()

    def test_config_drift_rejects_before_socket_or_process_work(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(v.c,'read',return_value={}),\
             patch.object(relay.socket,'socket') as channel:
            with self.assertRaisesRegex(ValueError,'configuration changed'):relay.connect(Path(directory),'a'*64)
            channel.assert_not_called()

    def test_failure_categories_are_closed(self):
        for error,expected in ((ValueError('voter host changed'),'HOST_CHANGED'),(ValueError('voter source changed'),'SOURCE_CHANGED'),
                               (ValueError('relay voter unavailable'),'VOTER_UNAVAILABLE'),(OSError('private-secret'),'GUEST_IO_FAILURE'),
                               (ValueError('private-secret'),'REQUEST_REJECTED')):
            self.assertEqual(expected,relay.error_code(error));self.assertNotIn('private-secret',relay.error_code(error))


class StreamEvidenceTest(unittest.TestCase):
    def fixture(self):
        target=dict(host='127.0.0.1',port=12000,user='operator',alias='gse-v52-'+'a'*32,hostPinSha256='a'*64)
        value=dict(schema='gse-v52-voter-ssh-streams-v1',target=target,configSha256='b'*64,
                   channels=[dict(configSha256='b'*64,after=0,through=2,terminal=False),
                             dict(configSha256='b'*64,after=2,through=3,terminal=True)])
        return value,target,[{'kind':'SUBMIT'},{'kind':'RESULT'},{'kind':'STOPPED'}]
    def test_reconnect_starts_at_last_observed_event(self):
        value,target,events=self.fixture();self.assertEqual(2,e.channels(value,target,'b'*64,events))
    def test_missing_changed_or_replayed_route_and_cursors_reject(self):
        mutations=[lambda x:x.update(configSha256='0'*64),lambda x:x['target'].update(host='10.0.0.1'),
                   lambda x:x['channels'][1].update(after=0),lambda x:x['channels'][1].update(after=3),
                   lambda x:x['channels'][1].update(through=2),lambda x:x['channels'][0].update(terminal=True),
                   lambda x:x['channels'][1].update(terminal=False),lambda x:x['channels'].clear(),
                   lambda x:x['channels'][0].update(extra=1),lambda x:x['channels'][0].update(after=False)]
        for mutate in mutations:
            value,target,events=self.fixture();expected=deepcopy(target);mutate(value)
            with self.assertRaises(ValueError):e.channels(value,expected,'b'*64,events)
    def test_transport_rejects_missing_nodes_duplicate_aliases_and_cloud_targets(self):
        _,target,_=self.fixture();value=dict(schema=e.SCHEMA,execution=e.EXECUTION,nodes={n:dict(target,alias='gse-v52-'+str(i)*32) for i,n in enumerate(v.h.topology.NODES)})
        e.binding(value)
        for mutate in (lambda x:x['nodes'].pop('node-3'),lambda x:x['nodes']['node-3'].update(alias=x['nodes']['node-1']['alias']),
                       lambda x:x['nodes']['node-2'].update(host='10.0.0.1')):
            bad=deepcopy(value);mutate(bad)
            with self.assertRaises(ValueError):e.binding(bad)
    def test_terminal_event_cannot_be_invented_on_empty_reconnect(self):
        value,target,events=self.fixture();value['channels'][0]['through']=3;value['channels'][1]['after']=3
        with self.assertRaisesRegex(ValueError,'terminal cursor mismatch'):e.channels(value,target,'b'*64,events)
    def test_retained_transport_required_on_both_original_and_relocated_inputs(self):
        import shutil
        from . import remote_voter_evidence as evidence
        helper=fixtures.RetainedVoterTest()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'original';root.mkdir();binding=helper.fixture(root)
            _,target,events=self.fixture()
            binding['remoteVoterTransport']=dict(schema=e.SCHEMA,execution=e.EXECUTION,nodes={n:dict(target,alias='gse-v52-'+str(i)*32) for i,n in enumerate(v.h.topology.NODES)})
            helper.write(root/'binding.json',binding)
            for node in v.h.topology.NODES:
                control=root/(node+'-control');config=v.c.read(control/'config.json');config['binding']=binding
                sha=v.digest(v.encoded(config));helper.write(control/'config.json',config)
                for file in ('launch.json','started.json','stopped.json'):
                    value=v.c.read(control/file);value['configSha256']=sha;helper.write(control/file,value)
                helper.write(control/'ssh-streams.json',dict(schema='gse-v52-voter-ssh-streams-v1',target=binding['remoteVoterTransport']['nodes'][node],configSha256=sha,
                    channels=[dict(configSha256=sha,after=0,through=3,terminal=True)]))
            helper.index(root);expected=evidence.validate(root,binding)
            relocated=Path(directory)/'relocated';shutil.copytree(root,relocated)
            self.assertEqual(expected,evidence.validate(relocated,binding))
            (relocated/'node-2-control/ssh-streams.json').unlink();helper.index(relocated)
            with self.assertRaises(FileNotFoundError):evidence.validate(relocated,binding)


if __name__=='__main__':unittest.main()
