import base64
from copy import deepcopy
import io
import os
from pathlib import Path
import tarfile
import tempfile
import time
import unittest
from unittest.mock import Mock,patch
from . import remote_delivery_package as p,remote_delivery_guest as g,remote_delivery as d,remote_delivery_evidence as e
from . import remote_voter as v,remote_voter_lifecycle as lifecycle
from . import test_remote_voter_ssh as ssh_fixture


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.producer=self.root/'producer';self.producer.mkdir()
        for name in ('artifacts/general-search-engine-5.2.0-SNAPSHOT.jar','artifacts/general-search-engine-replication-5.2.0-SNAPSHOT.jar',
                     'artifacts/general-search-engine-4.4.0.jar','consumer/a.class','observer/b.class',*sorted(p.SEED)):
            file=self.producer/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(name.encode()+b'-original')
        self.source=dict(source='a'*40,checkoutSha256='b'*64,java={'java.runtime.version':'21','java.vendor':'test'})
        topology=dict(schema=p.h.topology.SCHEMA,placement='local-no-gcp',groupId='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
                      members=[dict(node=node,host='127.0.0.1',port=12000+i) for i,node in enumerate(p.h.topology.NODES)])
        self.binding=dict(self.source,mode='candidate-minimum',driverExercise=True,remoteTopology=topology,
            artifacts={q.name:p.h.bundle.sha_file(q) for q in (self.producer/'artifacts').iterdir()},
            classes={str(q.relative_to(self.producer)):p.h.bundle.sha_file(q) for q in self.producer.rglob('*.class')})
        self.archive,self.meta=p.create(self.producer,self.root/'capsule',self.binding)
        self.parent=self.root/'guests';self.parent.mkdir(mode=0o700)
        self.value=dict(schema='gse-v52-receiver-delivery-v1',execution=p.EXECUTION,parent=str(self.parent),host=p.host.observe(self.parent),
                        node='node-1',session='c'*32,package=self.meta)
        self.store=g.store_for(self.value)
    def begin(self):
        with patch.object(p.h,'source',return_value=self.source):return g.begin(self.parent,self.value)
    def upload(self):
        self.begin()
        with self.archive.open('rb') as stream:
            for index,row in enumerate(self.meta['parts']):
                g.part(self.store,self.value,dict(index=index,data=base64.b64encode(stream.read(row['bytes'])).decode()))


class PackageTest(Fixture):
    def test_same_capsule_is_verified_before_any_destination_exists(self):
        self.assertEqual(self.meta,p.verify_archive(self.archive,self.meta))
        self.assertFalse((self.parent/'node-1').exists());self.assertEqual(p.SEED,{n for n in self.meta['members'] if n.startswith('control/')})

    def test_extra_files_traversal_wrong_hash_and_formal_scope_reject(self):
        mutations=[lambda x:x['members'].update({'../escape':dict(bytes=1,sha256='a'*64)}),
                   lambda x:x['members'].update({'run.sh':dict(bytes=1,sha256='a'*64)}),
                   lambda x:x['classes'].update({'consumer/a.class':'0'*64}),lambda x:x.update(bytes=p.MAX_BYTES+1),
                   lambda x:x['parts'][0].update(bytes=0),lambda x:x.update(mode='formal'),
                   lambda x:x['topology'].update(placement='owned-private-hosts')]
        for mutate in mutations:
            bad=deepcopy(self.meta);mutate(bad)
            with self.assertRaises(ValueError):p.validate(bad)
        with self.assertRaisesRegex(ValueError,'exact M04 profile'):
            p.create(self.producer,self.root/'formal',dict(self.binding,measurementProfile={}))

    def test_archive_corruption_and_changed_declaration_fail(self):
        raw=self.archive.read_bytes();self.archive.write_bytes(bytes([raw[0]^1])+raw[1:])
        with self.assertRaisesRegex(ValueError,'archive bytes changed'):p.verify_archive(self.archive,self.meta)
        self.archive.write_bytes(raw);bad=deepcopy(self.meta);bad['members'][next(iter(p.SEED))]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'inventory mismatch'):p.verify_archive(self.archive,bad)

    def test_link_or_extended_archive_member_is_not_extracted(self):
        for kind in (tarfile.SYMTYPE,tarfile.LNKTYPE,tarfile.XHDTYPE):
            archive=self.root/('bad-'+kind.decode()+'.gz')
            with tarfile.open(archive,'w:gz',format=tarfile.USTAR_FORMAT) as out:
                item=tarfile.TarInfo(p.h.bundle.INDEX);raw=p.encoded(self.meta['members']);item.size=len(raw);out.addfile(item,io.BytesIO(raw))
                item=tarfile.TarInfo('consumer/a.class');item.type=kind;item.linkname='/tmp/escape';out.addfile(item)
            bad=deepcopy(self.meta);bad['bytes']=archive.stat().st_size;bad['sha256']=p.h.bundle.sha_file(archive)
            raw=archive.read_bytes();bad['parts']=[dict(bytes=len(raw),sha256=p.digest(raw))]
            with self.assertRaises(ValueError):p.verify_archive(archive,bad)

    def test_installed_source_bytes_must_remain_exact(self):
        target=p.h.bundle.unpack(self.archive,self.parent/'node-1');p.installed(target,self.meta)
        (target/'consumer/a.class').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'installed input changed'):p.installed(target,self.meta)


class UploadTest(Fixture):
    def test_complete_upload_and_identical_part_are_byte_only_idempotent(self):
        self.upload();before=g.query(self.store,self.value);self.assertEqual('READY',before['state'])
        raw=self.archive.read_bytes();self.assertLess(len(raw),p.PART)
        payload=dict(index=0,data=base64.b64encode(raw).decode());self.assertEqual(before,g.part(self.store,self.value,payload))
        with patch.object(g.subprocess,'Popen') as spawn:g.query(self.store,self.value);spawn.assert_not_called()

    def test_changed_part_invalid_index_and_hash_reject_without_writing(self):
        self.begin()
        for payload in (dict(index=True,data=''),dict(index=10,data=''),dict(index=0,data='YQ=='),dict(index=0,data='!'),dict(index=0,data='',pid=1)):
            with self.assertRaises(ValueError):g.part(self.store,self.value,payload)
        self.assertEqual([],list((self.store/'parts').iterdir()))

    def test_partial_part_or_unknown_file_remains_uncertain_not_ready(self):
        self.begin();partial=self.store/'parts/0000.json.writing';partial.write_text('partial')
        self.assertEqual('UNCERTAIN',g.query(self.store,self.value)['state'])
        with patch.object(g.subprocess,'Popen') as spawn,patch.object(p.h,'source',return_value=self.source):
            self.assertEqual('UNCERTAIN',g.install(self.store,self.value)['state']);spawn.assert_not_called()
        partial.unlink();(self.store/'parts/unexpected').write_text('bad')
        with self.assertRaisesRegex(ValueError,'unknown part'):g.query(self.store,self.value)

    def test_incomplete_begin_never_repairs_or_reuses_destination(self):
        self.store.mkdir(mode=0o700);(self.store/'descriptor.json.writing').write_text('partial')
        with self.assertRaises(FileNotFoundError):self.begin()
        self.assertFalse((self.store/'parts').exists())
        self.store.rename(self.parent/'retained-failure');(self.parent/'node-1').mkdir()
        with self.assertRaisesRegex(ValueError,'consumed'):self.begin()

    def test_stale_host_and_source_reject_before_destination_creation(self):
        wrong=deepcopy(self.value);wrong['host']['parentInode']+=1
        with self.assertRaisesRegex(ValueError,'host changed'):g.begin(self.parent,wrong)
        with patch.object(p.h,'source',return_value=dict(self.source,source='f'*40)):
            with self.assertRaisesRegex(ValueError,'source changed'):g.begin(self.parent,self.value)
        self.assertFalse(self.store.exists())

    def test_changed_descriptor_cannot_rebind_consumed_transfer(self):
        self.begin();wrong=deepcopy(self.value);wrong['session']='d'*32
        with patch.object(p.h,'source',return_value=self.source):
            with self.assertRaisesRegex(ValueError,'descriptor changed'):g.begin(self.parent,wrong)


class BootstrapTest(Fixture):
    def test_spawn_failure_is_consumed_and_never_relaunched(self):
        self.upload()
        with patch.object(p.h,'source',return_value=self.source),patch.object(g.subprocess,'Popen',side_effect=OSError('failed')) as spawn:
            with self.assertRaises(OSError):g.install(self.store,self.value)
            self.assertEqual('STARTING',g.install(self.store,self.value)['state']);spawn.assert_called_once()

    def test_partial_claim_cannot_launch(self):
        self.upload();(self.store/'launch.json.writing').write_text('partial')
        with patch.object(p.h,'source',return_value=self.source),patch.object(g.subprocess,'Popen') as spawn:
            self.assertEqual('UNCERTAIN',g.install(self.store,self.value)['state']);spawn.assert_not_called()

    def test_failed_bootstrap_retains_failure_and_original_destination(self):
        self.upload();p.c.write_once(self.store/'launch.json',dict(descriptorSha256=p.digest(p.encoded(self.value))))
        with patch.object(p.h,'source',return_value=self.source),patch.object(p.h.q,'command',side_effect=ValueError('bootstrap failure')) as boot:
            with self.assertRaisesRegex(ValueError,'bootstrap failure'):g.worker(self.store)
            with self.assertRaises(FileExistsError):g.worker(self.store)
            boot.assert_called_once()
        record=p.c.read(self.store/'terminal.json');self.assertEqual('FAILED',record['state'])
        self.assertEqual('INSTALL_FAILED',record['error']);self.assertTrue((self.parent/'node-1/artifacts').is_dir())

    def test_unknown_actions_and_raw_argv_cannot_execute(self):
        for action,value in (('shell',{}),('install',{'argv':['sh']}),('query',{'pid':12})):
            with self.assertRaises(ValueError):g.exchange(action,self.parent,value)

    def test_reply_claiming_success_before_original_executor_exit_rejects(self):
        self.upload();answer=g.query(self.store,self.value);answer['state']='SUCCEEDED'
        with self.assertRaisesRegex(ValueError,'not terminal'):d.observed(answer,self.value)
        answer['alive']=True
        with self.assertRaisesRegex(ValueError,'missing identity'):d.observed(answer,self.value)


class EndpointTest(unittest.TestCase):
    setUp=ssh_fixture.EndpointTest.setUp
    def test_fixed_delivery_entry_inherits_strict_pins_and_no_fallback(self):
        endpoint=d.Endpoint(self.target,p.h.ROOT);self.addCleanup(endpoint.close)
        master=Mock();endpoint.master=master;master.exchange.return_value=b'{"host":{}}'
        endpoint.exchange('probe',self.root,None,time.monotonic()+30)
        self.assertEqual(['python3','-I','-c',g.LAUNCH,str(p.h.ROOT),'probe',str(self.root)],master.exchange.call_args.args[0])
        master.exchange.assert_called_once()
        self.assertIn('StrictHostKeyChecking=yes',endpoint.args)
    def test_delivery_guest_error_uses_closed_permanent_codes(self):
        endpoint=d.Endpoint(self.target,p.h.ROOT);self.addCleanup(endpoint.close)
        master=Mock();endpoint.master=master;master.exchange.return_value=p.encoded(dict(schema=g.ERROR_SCHEMA,code='SOURCE_CHANGED'))
        with self.assertRaises(lifecycle.Rejected) as error:endpoint.exchange('probe',self.root,None,time.monotonic()+30)
        self.assertFalse(error.exception.retryable)


class ControllerTest(Fixture):
    def test_uncertain_part_and_install_only_query_original(self):
        obj=object.__new__(d.Delivery);obj.endpoint=Mock();obj.discarded=set();obj.losses=[];obj.exchange=Mock(side_effect=[{'state':'RUNNING'},{'state':'SUCCEEDED'}])
        self.assertEqual({'state':'SUCCEEDED'},obj.once('install',discard=True))
        self.assertEqual(['install','query'],[call.args[0] for call in obj.exchange.call_args_list]);self.assertEqual(['install'],obj.losses)
    def test_permanent_rejection_never_queries_or_repeats_install(self):
        obj=object.__new__(d.Delivery);obj.losses=[];obj.exchange=Mock(side_effect=lifecycle.Rejected('SOURCE_CHANGED'))
        with self.assertRaises(lifecycle.Rejected):obj.once('install')
        obj.exchange.assert_called_once_with('install',None)
    def test_no_local_receiver_creation_in_remote_preparation(self):
        from . import remote_delivery_qualification as q
        obj=object.__new__(q.Receivers);obj.capsule=self.archive;obj.meta=self.meta;obj.targets={'node-1':{}};obj.deliveries=[];obj.bootstraps={};obj.classpath={}
        endpoint=Mock();endpoint.run.return_value={'answer':{'status':'PREPARED_NOT_STARTED'}}
        own=self.parent/'node-1'
        with patch.object(q.delivery,'Delivery',return_value=endpoint),patch.object(q.shutil,'copyfile',side_effect=AssertionError('local copy')):
            obj.prepare_receiver('node-1',own,{},self.binding)
        self.assertFalse(own.exists());endpoint.close.assert_called_once()


if __name__=='__main__':unittest.main()
