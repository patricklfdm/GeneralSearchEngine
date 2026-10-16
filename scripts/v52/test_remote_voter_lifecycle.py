import base64
from copy import deepcopy
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import Mock,patch
from . import remote_voter as v,remote_voter_guest as guest,remote_voter_lifecycle as client
from . import remote_voter_lifecycle_evidence as evidence,remote_voter_evidence as full
from . import test_remote_voter as fixtures,test_remote_voter_ssh as ssh_fixtures


class LaunchTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.config=dict(host=dict(bootId=v.c.boot_id()),session='a'*32,socket=str(self.root/'channel'))
        self.sha=v.digest(v.encoded(self.config))

    def test_lost_launch_response_only_queries_and_never_launches_again(self):
        submit=Mock(side_effect=ConnectionError('lost'));query=Mock(return_value={'state':'READY'});lost=Mock()
        self.assertEqual({'state':'READY'},client.original_launch(submit,query,lost=lost))
        submit.assert_called_once();query.assert_called_once();lost.assert_called_once()
        query.side_effect=ConnectionError('again')
        with self.assertRaises(ConnectionError):client.original_launch(submit,query)
        self.assertEqual(2,submit.call_count);self.assertEqual(2,query.call_count)

    def test_permanent_auth_pin_source_and_request_errors_do_not_query(self):
        errors=[client.Rejected(code) for code in guest.ERRORS]+[
            client.stream.ssh.transport.ProcessError(code) for code in ('SSH_HOST_KEY','SSH_AUTHENTICATION','SSH_UNCLASSIFIED','REMOTE_EXIT')]
        for error in errors:
            query=Mock()
            with self.assertRaises(type(error)):client.original_launch(Mock(side_effect=error),query)
            query.assert_not_called()

    def test_transient_master_and_disconnect_only_query(self):
        for code in ('SSH_DISCONNECTED','SSH_MASTER_CLOSED'):
            query=Mock(return_value='original')
            self.assertEqual('original',client.original_launch(Mock(side_effect=client.stream.ssh.transport.ProcessError(code)),query))
            query.assert_called_once()

    def test_duplicate_and_partial_claims_cannot_spawn(self):
        for name in ('launch.json','launch.json.writing'):
            path=self.root/name;path.write_bytes(v.encoded(dict(configSha256=self.sha)))
            with patch.object(guest.subprocess,'Popen') as spawn:
                guest.start(self.root,self.config);spawn.assert_not_called()
            path.unlink()

    def test_spawn_failure_consumes_launch_forever(self):
        with patch.object(guest.subprocess,'Popen',side_effect=OSError('spawn failed')) as spawn:
            with self.assertRaises(OSError):guest.start(self.root,self.config)
            self.assertEqual('STARTING',guest.start(self.root,self.config)['state'])
            spawn.assert_called_once()
        self.assertEqual({'configSha256':self.sha},v.c.read(self.root/'launch.json'))

    def test_missing_launch_with_previous_worker_is_not_fresh(self):
        for suffix in ('.json','.json.writing'):
            path=self.root/('started'+suffix);path.write_text('{}')
            with patch.object(guest.subprocess,'Popen') as spawn:
                with self.assertRaisesRegex(ValueError,'orphaned launch'):guest.start(self.root,self.config)
                spawn.assert_not_called()
            path.unlink()

    def test_changed_launch_identity_rejects_before_spawn(self):
        (self.root/'launch.json').write_text('{}')
        with patch.object(guest.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(ValueError,'launch binding'):guest.start(self.root,self.config)
            spawn.assert_not_called()

    def test_foreign_or_reused_process_is_never_signalled(self):
        identity=v.process(os.getpid())
        with patch.object(v.c,'process_alive',side_effect=[True,False]),patch.object(guest.os,'pidfd_open',return_value=100),\
             patch.object(guest.signal,'pidfd_send_signal') as send,patch.object(guest.os,'close') as close:
            self.assertFalse(guest.signal_owned(identity));send.assert_not_called();close.assert_called_once_with(100)
        with patch.object(v.c,'process_alive',return_value=False),patch.object(guest.os,'pidfd_open') as opened:
            self.assertFalse(guest.signal_owned(identity));opened.assert_not_called()

    def test_signal_uses_pinned_descriptor_not_numeric_kill(self):
        identity=v.process(os.getpid())
        with patch.object(v.c,'process_alive',return_value=True),patch.object(guest.os,'pidfd_open',return_value=100),\
             patch.object(guest.signal,'pidfd_send_signal') as send,patch.object(guest.os,'close'),patch.object(guest.os,'kill') as kill:
            self.assertTrue(guest.signal_owned(identity));send.assert_called_once_with(100,guest.signal.SIGTERM);kill.assert_not_called()

    def test_active_collection_rejected_before_filesystem_copy(self):
        with patch.object(guest,'inspection',return_value={'state':'READY'}),patch.object(guest,'selected') as select:
            with self.assertRaisesRegex(ValueError,'stopped original'):guest.collect(self.root,self.config)
            select.assert_not_called()

    def test_safe_error_categories(self):
        for error,code in ((ValueError('voter source changed'),'SOURCE_CHANGED'),(ValueError('lifecycle host changed'),'HOST_CHANGED'),
                           (OSError('secret'),'GUEST_IO_FAILURE'),(ValueError('secret'),'REQUEST_REJECTED')):
            self.assertEqual(code,guest.error_code(error));self.assertNotIn('secret',str(client.Rejected(code)))


class CollectionTest(unittest.TestCase):
    def test_chunks_reject_wrong_offset_hash_length_and_non_base64(self):
        meta={'bytes':3,'sha256':'a'*64};good=dict(sha256='a'*64,offset=0,data=base64.b64encode(b'abc').decode())
        self.assertEqual(b'abc',client.decode_chunk(good,meta,0))
        for values in ({'offset':1},{'offset':False},{'sha256':'b'*64},{'data':'!'}, {'data':'YQ=='},{'extra':1}):
            with self.assertRaises(ValueError):client.decode_chunk(dict(good,**values),meta,0)

    def test_export_excludes_other_receivers_and_rejects_symlink_and_hardlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);own=root/'node-1';own.mkdir();(own/'entry').write_bytes(b'one')
            (root/'node-2-secret').write_text('secret')
            self.assertEqual({'node-1/entry'},set(guest.selected(root,'node-1')))
            link=own/'alias';link.symlink_to(own/'entry')
            with self.assertRaisesRegex(ValueError,'symlink'):guest.selected(root,'node-1')
            link.unlink();os.link(own/'entry',link)
            with self.assertRaisesRegex(ValueError,'unlinked file'):guest.selected(root,'node-1')

    def test_export_size_and_count_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'node-1-log').write_text('data')
            with patch.object(guest,'MAX_ARCHIVE',1):
                with self.assertRaisesRegex(ValueError,'collection bound'):guest.selected(root,'node-1')
            with patch.object(guest,'MAX_FILES',0):
                with self.assertRaisesRegex(ValueError,'collection bound'):guest.selected(root,'node-1')

    def test_expanded_manifest_mismatch_rejects_before_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);stage=root/'stage';stage.mkdir();(stage/'node-1-log').write_text('data')
            archive=root/'export.tar.gz';v.h.bundle.pack(stage,archive)
            with patch.object(v.h.bundle,'unpack') as extract:
                with self.assertRaisesRegex(ValueError,'declared inventory'):client.unpack_export(archive,root/'out',{'members':{}})
                extract.assert_not_called()
            meta={'members':v.h.bundle.inventory(stage)}
            self.assertEqual(root/'out',client.unpack_export(archive,root/'out',meta))

    def test_resource_limits_apply_before_hashing_oversize_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'node-1-log').write_text('large')
            with patch.object(guest,'MAX_ARCHIVE',1),patch.object(v.h.bundle,'sha_file') as hashed:
                with self.assertRaisesRegex(ValueError,'collection bound'):guest.selected(root,'node-1')
                hashed.assert_not_called()
            own=root/'node-1';own.mkdir();(own/'empty').mkdir()
            with patch.dict(v.h.bundle.LIMITS,{'directories':0}):
                with self.assertRaisesRegex(ValueError,'directory bound'):guest.selected(root,'node-1')

    def test_all_transport_owners_close_even_when_one_cleanup_fails(self):
        from . import remote_voter_lifecycle_qualification as q
        owner=object.__new__(q.Receivers);first=Mock();second=Mock();owner.clients=[first,second]
        first.close_transport.side_effect=ValueError('failed cleanup')
        with patch.object(q.previous.Receivers,'finish'):
            with self.assertRaisesRegex(ValueError,'transport cleanup failed'):owner.finish(None)
        first.close_transport.assert_called_once();second.close_transport.assert_called_once()

    def test_release_does_not_remove_socket_directory_of_live_jvm(self):
        with patch.object(guest,'inspection',return_value=dict(state='FAILED',serviceAlive=False,jvmAlive=True)),patch.object(v.host,'path') as path:
            with self.assertRaisesRegex(ValueError,'stopped owner'):guest.release(Path('/root'),{})
            path.assert_not_called()

    def test_payload_cannot_pass_shell_pid_or_unknown_action(self):
        for action,value in (('shell',{}),('query',{'pid':1}),('start',{'argv':['sh']})):
            with self.assertRaises(ValueError):guest.exchange(action,Path('/invalid'),value)

    def test_configuration_drift_rejects_before_guest_io(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(v.c,'read',return_value={}),patch.object(v,'validate_config') as checked:
            with self.assertRaisesRegex(ValueError,'configuration changed'):guest.load(Path(directory),'a'*64)
            checked.assert_not_called()


class EndpointTest(unittest.TestCase):
    setUp=ssh_fixtures.EndpointTest.setUp
    def test_control_uses_fixed_entry_and_exact_payload_once(self):
        endpoint=client.Endpoint(self.target,v.h.ROOT);self.addCleanup(endpoint.close)
        master=Mock();endpoint.master=master;master.exchange.return_value=b'{"answer":1}'
        result=endpoint.exchange('query',self.root,{'configSha256':'a'*64,'request':None},time.monotonic()+30)
        self.assertEqual({'answer':1},result);master.exchange.assert_called_once()
        args=master.exchange.call_args.args
        self.assertEqual(['python3','-I','-c',guest.LAUNCH,str(v.h.ROOT),'query',str(self.root)],args[0])
        self.assertEqual({'configSha256':'a'*64,'request':None},v.strict(args[1]))


class RetainedTest(unittest.TestCase):
    def fixture(self,root):
        helper=fixtures.RetainedVoterTest();binding=helper.fixture(root)
        target=dict(host='127.0.0.1',port=12000,user='operator',alias='gse-v52-'+'a'*32,hostPinSha256='b'*64)
        binding['remoteVoterTransport']=dict(schema=evidence.ssh.SCHEMA,execution=evidence.ssh.EXECUTION,
            nodes={node:dict(target,alias='gse-v52-'+str(i)*32) for i,node in enumerate(v.h.topology.NODES)})
        binding['remoteVoterLifecycle']=guest.EXECUTION;helper.write(root/'binding.json',binding)
        for node in v.h.topology.NODES:
            control=root/(node+'-control');config=v.c.read(control/'config.json');config['binding']=binding
            sha=v.digest(v.encoded(config));helper.write(control/'config.json',config)
            for file in ('launch.json','started.json','stopped.json'):
                row=v.c.read(control/file);row['configSha256']=sha;helper.write(control/file,row)
            identity=v.c.read(control/'identity.json')
            helper.write(control/'exited.json',dict(configSha256=sha,service=identity['service'],exitCode=0))
            helper.write(control/'preparation.json',dict(node=node,binding=binding,session=config['session'],host=config['host']))
            meta=dict(schema=guest.SCHEMA,configSha256=sha,node=node,bytes=1,sha256='a'*64,
                members={n:r for n,r in v.h.bundle.members(root).items() if n.split('/')[0]==node+'-control'},
                terminal=dict(state='STOPPED',serviceAlive=False,jvmAlive=False,**{k:v.c.read(control/(k+'.json')) for k in ('started','identity','stopped','exited')}))
            helper.write(control/'lifecycle.json',dict(schema=guest.SCHEMA,execution=guest.EXECUTION,configSha256=sha,
                launchSubmissions=1,launchReplyLost=node=='node-1',collection=meta))
            helper.write(control/'ssh-streams.json',dict(schema='gse-v52-voter-ssh-streams-v1',target=binding['remoteVoterTransport']['nodes'][node],configSha256=sha,
                channels=[dict(configSha256=sha,after=0,through=3,terminal=True)]))
        helper.index(root);return binding

    def test_complete_and_relocated_collection_replays_with_original_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'original';root.mkdir();binding=self.fixture(root);result=full.validate(root,binding)
            relocated=Path(directory)/'relocated';shutil.copytree(root,relocated)
            self.assertEqual(result,full.validate(relocated,binding))

    def test_refreshed_outer_inventory_cannot_hide_export_or_terminal_changes(self):
        mutations=[lambda r:r.update(launchSubmissions=2),lambda r:r['collection']['terminal'].update(serviceAlive=True),
                   lambda r:r['collection'].update(node='node-2'),lambda r:r['collection']['members'].clear(),
                   lambda r:r['collection']['terminal']['exited'].update(exitCode=1),
                   lambda r:r['collection']['terminal']['identity']['service'].update(startTicks=99),
                   lambda r:r['collection'].update(sha256='invalid'),lambda r:r['collection'].update(bytes=guest.MAX_ARCHIVE+1)]
        for mutate in mutations:
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);binding=self.fixture(root);path=root/'node-1-control/lifecycle.json'
                value=v.c.read(path);mutate(value);fixtures.RetainedVoterTest().write(path,value);fixtures.RetainedVoterTest().index(root)
                with self.assertRaises(ValueError):full.validate(root,binding)

    def test_missing_or_downgraded_lifecycle_fails_even_after_inventory_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);binding=self.fixture(root)
            (root/'node-1-control/lifecycle.json').unlink();fixtures.RetainedVoterTest().index(root)
            with self.assertRaises(FileNotFoundError):full.validate(root,binding)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);binding=self.fixture(root);config=v.c.read(root/'node-1-control/config.json');sha=v.digest(v.encoded(config))
            binding.pop('remoteVoterLifecycle')
            with self.assertRaisesRegex(ValueError,'retained scope'):evidence.validate(root,binding,config,sha)


if __name__=='__main__':unittest.main()
