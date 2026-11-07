"""Real seed/archive readers with synthetic producer observations, no native credit."""
from contextlib import ExitStack,redirect_stdout
import io
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from . import phase3_resource_artifacts as a
from .test_process_toolchain import record

s=a.seeds;w=a.workflows


class ResourceArtifactsTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.inputs=self.root/'originals';self.inputs.mkdir();self.artifacts=self.root/'artifacts';self.artifacts.mkdir()
        self.execution=self.root/'execution.json';self.resource=self.root/'resources.json';self.count=0
        self.modules=w.adapters();self.index=dict(schema=w.INDEX_SCHEMA,source='a'*40,cohorts={})
        self.source=dict(head='a'*40,files={'scripts/v53/synthetic.py':s.h.digest(b'synthetic source')})
        files=dict(self.source['files']);self.reader=dict(files=files,sha256=s.h.digest(s.canonical(files)))
        self.data={};self.raw={};self.claims={};self.manifests={}
        for number,(name,adapter) in enumerate(self.modules.items(),100):
            owners=[adapter.source,adapter.completion] if name=='queue-resources' else [adapter.m]
            for owner in owners:self.stack.enter_context(patch.object(owner,'reader_manifest',return_value=self.reader))
            ctx=dict(kind='github',repository='patricklfdm/GeneralSearchEngine',source='a'*40,ref=adapter.BRANCH,
                event='workflow_dispatch',run=str(number),attempt='2',workflow=adapter.WORKFLOW)
            self.index['cohorts'][name]=ctx
            data=self.root/('seed-'+name);data.mkdir();self.data[name]=data
            producer=data/'producer';work=producer/'workspace';(work/'scripts/v53').mkdir(parents=True)
            (work/'scripts/v53/synthetic.py').write_bytes(b'synthetic source');s.h.save(producer/'source.json',self.source)
            for path in s.shared.m.BUILDS:
                directory=work/path;directory.mkdir(parents=True);(directory/'test.class').write_bytes(b'synthetic class')
            reports=work/s.h.MODULE/'target/surefire-reports';reports.mkdir()
            cls='io.github.patricklfdm.generalsearch.replication.V53BallotAllocatorTest'
            suite=ET.Element('testsuite',dict(name=cls,tests='1',failures='0',errors='0',skipped='0'))
            ET.SubElement(suite,'testcase',dict(classname=cls,name='syntheticPreparation'))
            ET.ElementTree(suite).write(reports/'TEST-original.xml')
            s.h.save(producer/'build.json',{k:s.h.inventory(work/k) for k in s.shared.m.BUILDS})
            s.h.save(producer/'toolchain.json',record())
            repo=data/'repository';repo.mkdir();(repo/'surefire.jar').write_bytes(b'synthetic dependency')
            fields=dict(cases=list(adapter.HISTORIES)) if name=='queue-resources' else dict(profile=adapter.PROFILE)
            seed=dict(schema=adapter.SCHEMA,context=ctx,status='PARTIAL',phase3Complete=False,reader=self.reader,
                readerSha256=self.reader['sha256'],preparationExecution=dict(exit=0,elapsedSeconds=1),**fields,
                sourceSha256=s.h.digest((producer/'source.json').read_bytes()),buildSha256=s.h.digest((producer/'build.json').read_bytes()),
                toolchainSha256=s.shared.tc.pin((producer/'toolchain.json').read_bytes()),repositorySha256=s.shared.dependencies(repo))
            s.h.save(data/'seed.json',seed);(self.artifacts/name).mkdir();self.pack_seed(name)
            for member in w.WORKFLOWS[name][2]:
                original=self.inputs/member;original.mkdir();(original/'empty').mkdir()
                (original/'physical-original.bin').write_bytes(('synthetic '+member).encode())
                s.h.save(original/'receipt.json',dict(status='PARTIAL',synthetic=True,member=member))
                raw=self.root/('raw-'+member);raw.mkdir();shutil.copytree(original,raw/'producer');self.raw[member]=raw
                label=dict(case=member) if name=='queue-resources' else dict(profile=adapter.PROFILE)
                claim=dict(schema=adapter.SCHEMA,context=ctx,status='PARTIAL',phase3Complete=False,**label,**adapter.pins(seed),
                    seedArchiveSha256=self.manifests[name]['archiveSha256'],producerReceiptSha256=s.shared.tc.file_hash(original/'receipt.json'))
                s.h.save(raw/'hosted-member.json',claim);self.claims[member]=claim;self.pack_raw(name,member)
        s.h.save(self.execution,self.index);s.h.save(self.resource,dict(synthetic=True))
        # Owning producer validation/physical replay is covered by resource_cohort.
        # Here the inspection returns independent actual directory hashes; seed
        # readers, archive bytes, inventories and before/after comparisons are real.
        self.observed=self.inspect();self.stack.enter_context(patch.object(a.resources,'inspect',side_effect=lambda *_:self.inspect()))

    def bundle(self,name,kind,member=None):return self.artifacts/name/w.artifact_name(name,self.index['cohorts'][name],kind,member)

    def pack_seed(self,name):
        bundle=self.bundle(name,'seed')
        if bundle.exists():shutil.rmtree(bundle)
        self.manifests[name]=self.modules[name].pack(self.data[name],bundle,self.index['cohorts'][name],'seed')

    def pack_raw(self,name,member):
        bundle=self.bundle(name,'raw',member)
        if bundle.exists():shutil.rmtree(bundle)
        args=(member,) if name=='queue-resources' else ()
        self.modules[name].pack(self.raw[member],bundle,self.index['cohorts'][name],'raw',*args)

    def inspect(self):
        originals={}
        for name,adapter in self.modules.items():
            seed=s.read(self.data[name]/'seed.json')
            for member in w.WORKFLOWS[name][2]:
                originals[member]=dict(pins=adapter.pins(seed),producerReceiptSha256=s.shared.tc.file_hash(self.inputs/member/'receipt.json'),
                    actualInventory=a.inventory(self.inputs/member,maximum=s.shared.MAX_BYTES))
        seed=s.read(self.data['required-four']/'seed.json')
        return dict(source='a'*40,indexSha256=s.shared.tc.file_hash(self.resource),originals=originals,
                    commonPins={k:seed[k] for k in a.resources.COMMON_PINS})

    def bind(self):
        self.count+=1;self.output=self.root/('binding-'+str(self.count))
        with redirect_stdout(io.StringIO()):return a.bind(self.execution,self.resource,self.inputs,self.artifacts,self.output)

    def test_all_nine_real_archives_and_four_preparations_bind_five_producers(self):
        result=self.bind();self.assertEqual('PARTIAL',result['status']);self.assertTrue(result['resourceArtifactsBound'])
        self.assertEqual(set(a.resources.MEMBERS),set(result['members']));self.assertEqual(4,len(result['commonPins']))
        self.assertEqual(9,len(s.read(self.output/'bundle-identities.json')))
        for key in ('originalHistoriesReplayed','workflowExecutionAttested','phase3Complete'):self.assertFalse(result[key])
        # No extra raw extraction is performed, only the small preparation seeds.
        self.assertFalse(list(self.output.rglob('physical-original.bin')))
        a.unchanged(self.execution,self.resource,self.inputs,self.artifacts,self.output,result)

    def test_changed_raw_bytes_cannot_hide_behind_manifest_or_producer_receipt(self):
        name='queue-resources';member='queue-completion';path=self.raw[member]/'producer/physical-original.bin'
        path.write_bytes(b'self-consistently repacked but not original');self.pack_raw(name,member)
        with self.assertRaisesRegex(ValueError,'producer differs'):self.bind()
        self.assertEqual('FAIL',s.read(self.output/'receipt.json')['status'])

    def test_producer_sidecar_directory_or_extra_archive_file_rejects(self):
        name='queue-resources';member='source-queue';raw=self.raw[member]
        for i,mode in enumerate(('sidecar','directory','extra')):
            with self.subTest(mode=mode):
                path=raw/('producer/new-sidecar' if mode=='sidecar' else 'producer/extra-dir' if mode=='directory' else 'unclaimed')
                if mode=='directory':path.mkdir()
                else:path.write_bytes(b'extra')
                self.pack_raw(name,member)
                with self.assertRaisesRegex(ValueError,'producer differs'):self.bind()
                if path.is_dir():path.rmdir()
                else:path.unlink()

    def test_context_attempt_profile_seed_and_producer_claims_are_exact(self):
        name='queue-resources';member='queue-completion';saved=self.claims[member]
        for key,value in [('context',dict(saved['context'],attempt='1')),('case','source-queue'),('status','PASS'),
                          ('seedArchiveSha256','0'*64),('producerReceiptSha256','0'*64),('readerSha256','0'*64)]:
            s.h.save(self.raw[member]/'hosted-member.json',dict(saved,**{key:value}));self.pack_raw(name,member)
            with self.subTest(field=key),self.assertRaisesRegex(ValueError,'execution/seed binding'):self.bind()

    def test_missing_or_failed_preparation_never_qualifies(self):
        name='required-four';seed=s.read(self.data[name]/'seed.json');seed.pop('preparationExecution');s.h.save(self.data[name]/'seed.json',seed)
        self.pack_seed(name)
        with self.assertRaisesRegex(ValueError,'preparation execution'):self.bind()

    def test_same_source_build_and_tools_but_different_dependency_seed_rejects(self):
        name='maximum-image';(self.data[name]/'repository/surefire.jar').write_bytes(b'different dependency')
        seed=s.read(self.data[name]/'seed.json');seed['repositorySha256']=s.shared.dependencies(self.data[name]/'repository')
        s.h.save(self.data[name]/'seed.json',seed);self.pack_seed(name)
        with self.assertRaisesRegex(ValueError,'mixed seeds/source/build/tools/dependencies'):self.bind()

    def test_unlisted_archive_and_missing_full_profile_reject_before_binding(self):
        path=self.artifacts/'unexpected';path.mkdir()
        with self.assertRaises(ValueError):self.bind()
        path.rmdir();self.bundle('maximum-image','raw','maximum-image').rename(self.artifacts/'renamed')
        with self.assertRaises(ValueError):self.bind()

    def test_archive_and_producer_mutations_after_binding_reject(self):
        result=self.bind();path=self.inputs/'source-queue/physical-original.bin';before=path.read_bytes();path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed after'):a.unchanged(self.execution,self.resource,self.inputs,self.artifacts,self.output,result)
        path.write_bytes(before);bundle=self.bundle('queue-resources','raw','source-queue')
        (bundle/'bundle.tar.gz').write_bytes(b'changed archive')
        with self.assertRaises(ValueError):a.unchanged(self.execution,self.resource,self.inputs,self.artifacts,self.output,result)

    def test_change_to_previously_checked_original_during_binding_rejects(self):
        original=a.check_producer
        def moving(manifest,producer,maximum):
            result=original(manifest,producer,maximum)
            if producer.name=='queue-completion':
                (self.inputs/'required-four/physical-original.bin').write_bytes(b'changed after its earlier comparison')
            return result
        with patch.object(a,'check_producer',side_effect=moving),self.assertRaisesRegex(ValueError,'inputs changed during binding'):
            self.bind()
        self.assertFalse(s.read(self.output/'receipt.json')['resourceArtifactsBound'])

    def test_false_archive_inventory_cannot_conceal_extra_or_mutated_tar_members(self):
        name='queue-resources';member='source-queue';bundle=self.bundle(name,'raw',member)
        before=s.read(bundle/'manifest.json')['inventory']
        (self.raw[member]/'producer/physical-original.bin').write_bytes(b'changed')
        self.pack_raw(name,member);manifest=s.read(bundle/'manifest.json');manifest['inventory']=before;s.h.save(bundle/'manifest.json',manifest)
        with self.assertRaisesRegex(ValueError,'actual archive inventory'):self.bind()

    def test_streamed_tar_rejects_traversal_links_duplicates_bounds_and_false_inventory(self):
        name='queue-resources';ctx=self.index['cohorts'][name];member='source-queue';adapter=self.modules[name]
        for i,(filename,kind,size) in enumerate([('../escape',tarfile.REGTYPE,1),('data/link',tarfile.SYMTYPE,0),
                ('data/hard',tarfile.LNKTYPE,0),('data/huge',tarfile.REGTYPE,256*1024**2+1),
                ('data/duplicate',tarfile.REGTYPE,1),('data/hosted-member.json',tarfile.REGTYPE,8*1024**2+1),
                ('data/omitted-from-inventory',tarfile.REGTYPE,1)]):
            bundle=self.root/f'hostile-{i}';bundle.mkdir();archive=bundle/'bundle.tar.gz'
            with tarfile.open(archive,'w:gz') as tar:
                root=tarfile.TarInfo('data');root.type=tarfile.DIRTYPE;tar.addfile(root)
                item=tarfile.TarInfo(filename);item.type=kind;item.size=size
                tar.addfile(item,io.BytesIO(b'x'*size) if size<1024 else None)
                if 'duplicate' in filename:tar.addfile(item,io.BytesIO(b'x'))
            manifest=dict(schema=adapter.SCHEMA,context=ctx,kind='raw',case=member,inventory=dict(files={},directories=[],bytes=0),
                archiveSha256=s.shared.tc.file_hash(archive));s.h.save(bundle/'manifest.json',manifest)
            with self.subTest(file=filename),self.assertRaises(ValueError):a.raw_archive(bundle,ctx,adapter.SCHEMA,member,adapter.limit('raw',member))
        self.assertFalse((self.root/'escape').exists())

    def test_raw_digest_inventory_and_limits_checked_independently(self):
        name='queue-resources';ctx=self.index['cohorts'][name];member='source-queue';adapter=self.modules[name]
        bundle=self.bundle(name,'raw',member);maximum=adapter.limit('raw',member)
        a.raw_archive(bundle,ctx,adapter.SCHEMA,member,maximum)
        for bound in (0,True,1):
            with self.assertRaises(ValueError):a.raw_archive(bundle,ctx,adapter.SCHEMA,member,bound)
        path=bundle/'manifest.json';value=s.read(path);value['inventory']['bytes']+=1;s.h.save(path,value)
        with self.assertRaisesRegex(ValueError,'actual archive inventory'):a.raw_archive(bundle,ctx,adapter.SCHEMA,member,maximum)
        with (bundle/'bundle.tar.gz').open('ab') as f:f.write(b'changed')
        with self.assertRaisesRegex(ValueError,'digest/bound'):a.raw_archive(bundle,ctx,adapter.SCHEMA,member,maximum)

    def test_linked_raw_files_and_output_overlap_reject(self):
        bundle=self.bundle('queue-resources','raw','source-queue');os.link(bundle/'bundle.tar.gz',self.root/'hardlink')
        with self.assertRaises(ValueError):self.bind()
        with self.assertRaisesRegex(ValueError,'overlaps'):a.bind(self.execution,self.resource,self.inputs,self.artifacts,self.inputs/'output')


if __name__=='__main__':unittest.main()
