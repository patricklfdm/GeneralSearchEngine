"""Actual seed/archive/API composition with synthetic physical-reader results.

No JVM/maximum history is executed. Owning result/negative/memory readers remain
real; only the native producer/member and child execution are fixture boundaries.
"""
from contextlib import ExitStack,redirect_stdout
import copy
import io
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from . import maximum_resource_attested as c
from . import test_maximum_resource_artifacts as binding_fixture
from . import test_maximum_native_run as native
from . import test_maximum_queue_run as queue
from .test_process_toolchain import record


class MaximumAttestedTest(unittest.TestCase):
    def setUp(self):
        self.fixture=binding_fixture.MaximumArtifactTest();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root;self.index=self.fixture.index;self.value=self.fixture.value
        self.zips=self.fixture.zips;self.bundles=self.fixture.bundles;self.modules=self.fixture.fixture.modules
        self.stack=ExitStack();self.addCleanup(self.stack.close);self.calls=[];self.outputs=0;self.after=None;self.change=None
        self.stack.enter_context(patch.object(c,'capacity',return_value={'status':'PASS','synthetic':True}))
        source=self.fixture.fixture.source;source['files']['scripts/v53/fixture.py']=c.h.digest(b'synthetic source reader')
        self.stack.enter_context(patch.object(c.seeds,'checkout_source',side_effect=lambda _:copy.deepcopy(source)))
        self.reader=dict(files={'scripts/v53/fixture.py':source['files']['scripts/v53/fixture.py']},sha256='f'*64)
        self.data={}
        for name,adapter in self.modules.items():
            self.stack.enter_context(patch.object(adapter.m,'reader_manifest',return_value=self.reader))
            self.stack.enter_context(patch.object(adapter.m,'member',side_effect=self.member))
            self.stack.enter_context(patch.object(adapter,'verify',side_effect=lambda *args,n=name:self.verify(n,*args)))
            data=self.root/(name+'-seed');(data/'synthetic.txt').unlink();self.data[name]=data
            producer=data/'producer';work=producer/'workspace';work.mkdir(parents=True)
            for filename in source['files']:
                path=work/filename;path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(b'synthetic source reader' if filename=='scripts/v53/fixture.py' else (c.seeds.ROOT/filename).read_bytes())
            c.h.save(producer/'source.json',source)
            for folder in adapter.m.BUILDS:
                path=work/folder;path.mkdir(parents=True);(path/'synthetic.class').write_bytes(b'same synthetic compiled bytes')
            self.reports=work/c.h.MODULE/'target/surefire-reports';self.reports.mkdir(parents=True)
            cls='io.github.patricklfdm.generalsearch.replication.V53BallotAllocatorTest'
            suite=ET.Element('testsuite',dict(name=cls,tests='1',failures='0',errors='0',skipped='0'))
            ET.SubElement(suite,'testcase',dict(classname=cls,name='synthetic'))
            ET.ElementTree(suite).write(self.reports/'TEST-synthetic.xml')
            c.h.save(producer/'toolchain.json',record());repo=data/'repository';repo.mkdir();(repo/'surefire.jar').write_bytes(b'same dependency')
            seed=dict(schema=adapter.SCHEMA,context=self.value['cohorts'][name],profile=adapter.PROFILE,status='PARTIAL',phase3Complete=False,
                reader=self.reader,readerSha256=self.reader['sha256'],preparationExecution=dict(exit=0,elapsedSeconds=1))
            seed=adapter.m.marked(seed,adapter.PROFILE) if name=='maximum-native' else adapter.marked(seed)
            c.h.save(data/'seed.json',seed);self.refresh_seed(name)
            raw=self.root/(name+'-raw');(raw/'producer').mkdir();c.h.save(raw/'producer/receipt.json',dict(status='synthetic-not-physical'))
            self.repack(name,'raw',raw)

    def repack(self,name,kind,data):
        adapter=self.modules[name];bundle=self.bundles/name/kind
        shutil.rmtree(bundle);adapter.pack(data,bundle,self.value['cohorts'][name],kind)
        path=self.zips/name/(kind+'.zip');self.fixture.make_zip(path,bundle)
        row=self.fixture.rows(name)[0 if kind=='seed' else 1]
        row.update(size_in_bytes=path.stat().st_size,digest='sha256:'+c.tc.file_hash(path))

    def refresh_seed(self,name):
        adapter=self.modules[name];data=self.data[name];p=data/'producer';seed=c.seeds.read(data/'seed.json')
        c.h.save(p/'build.json',{k:c.h.inventory(p/'workspace'/k) for k in adapter.m.BUILDS})
        seed.update(sourceSha256=c.h.digest((p/'source.json').read_bytes()),buildSha256=c.h.digest((p/'build.json').read_bytes()),
            toolchainSha256=c.tc.pin((p/'toolchain.json').read_bytes()),repositorySha256=adapter.shared.dependencies(data/'repository'))
        c.h.save(data/'seed.json',seed);self.repack(name,'seed',data)

    def member(self,path,*args):
        return dict(raw=path,producerReceiptSha256=c.tc.file_hash(path/'receipt.json'),inventory=c.inventory(path,maximum=1024**2))

    def verify(self,name,seed_bundle,raw_bundle,output,ctx,result):
        self.calls.append(name);self.assertEqual('success',result)
        self.assertEqual(self.bundles/name/'seed',seed_bundle);self.assertEqual(self.bundles/name/'raw',raw_bundle)
        adapter=self.modules[name];output.mkdir(parents=True);seed_root,seed_manifest=adapter.unpack(seed_bundle,output/'seed',ctx,'seed')
        raw,raw_manifest=adapter.unpack(raw_bundle,output/'original',ctx,'raw');seed=adapter.seed_inputs(seed_root,ctx);pins=adapter.pins(seed)
        member=self.member(raw/'producer')
        qualified=dict(schema=adapter.m.SCHEMA if name=='maximum-native' else adapter.m.MAXIMUM_SCHEMA,
            status='PASS',scope=c.SCOPES[name],profile=adapter.PROFILE,**pins,
            producerReceiptSha256=member['producerReceiptSha256'],rawInventorySha256=c.h.digest(c.h.snapshot.f.canonical(member['inventory'])),
            originalFirst=True,originalPreserved=True,combinedResourcesQualified=False,phase3Complete=False,
            verificationCapacity=native.capacity_record('verify'),qualification=native.maximum_result() if name=='maximum-native' else queue.result())
        if name=='maximum-native':qualified=adapter.m.marked(dict(qualified,observedResourcesQualified=True),adapter.PROFILE)
        else:qualified.update(queuePressureQualified=True,nativeFinalCompleted=True)
        reader=output/'measurement/reader';(reader/'verification').mkdir(parents=True);c.h.save(reader/'verification/receipt.json',qualified)
        proc=b'Pid: 12345\nVmHWM: 100 kB\n';(reader/'memory-status.txt').write_bytes(proc)
        memory=dict(schema=adapter.reader.SCHEMA,status='PASS',profile=adapter.PROFILE,processId=12345,
            scope='fresh-process-whole-resource-verification',retries=0,wholeReaderMemoryQualified=False,phase3Complete=False,
            elapsedNanos=100,cpuNanos=90,peakRssBytes=102400,rusagePeakRssBytes=102400,
            rssSource='/proc/self/status:VmHWM',procStatusSha256=c.h.digest(proc),
            verificationReceiptSha256=c.tc.file_hash(reader/'verification/receipt.json'))
        c.h.save(reader/'memory.json',memory)
        measurement=output/'measurement';c.h.save(measurement/'pins.json',pins);(measurement/'reader.log').write_text('synthetic reader execution')
        command=[sys.executable,'-B','-m',adapter.reader.__name__,str(reader),
                 '--producer',str(output/'original/data/producer'),'--pins',str(measurement/'pins.json')]
        c.h.save(measurement/'execution.json',dict(command=command,exit=0,elapsedSeconds=1))
        value=dict(schema=adapter.SCHEMA,status='PASS',context=ctx,profile=adapter.PROFILE,scope=c.SCOPES[name],wholeHistories=1,
            originalFirstDownloadedReplay=True,combinedResourcesQualified=False,wholeReaderMemoryQualified=False,phase3Complete=False,
            **pins,seedArchiveSha256=seed_manifest['archiveSha256'],rawArchiveSha256=raw_manifest['archiveSha256'],
            readerMemory=memory,qualification=qualified)
        if name=='maximum-native':value.update(observedResourcesQualified=True)
        else:value.update(queuePressureQualified=True,nativeFinalCompleted=True,maximumImageQueueQualified=True)
        if self.change:self.change(name,output,value)
        c.h.save(output/'receipt.json',value)
        if name=='maximum-queue' and self.after:self.after()
        return value

    def run_gate(self):
        self.outputs+=1;self.output=self.root/('attested-'+str(self.outputs))
        with redirect_stdout(io.StringIO()):return c.run(self.index,self.zips,self.bundles,self.output,self.fixture.get)

    def test_both_actual_seed_readers_and_full_result_gates_compose_with_live_byte_binding(self):
        result=self.run_gate();self.assertEqual('PARTIAL',result['status']);self.assertEqual(list(self.modules),self.calls)
        self.assertEqual(2,result['wholeHistories']);self.assertEqual(set(c.COMMON_PINS),set(result['commonPins']))
        self.assertTrue(result['workflowExecutionAttested']);self.assertTrue(result['artifactBytesBound']);self.assertTrue(result['maximumComponentOriginalsReplayed'])
        for key in ('combinedResourcesQualified','wholeReaderMemoryQualified','finalSourceCohortQualified','priorFailuresResolved','phase3Complete'):
            self.assertFalse(result[key])
        self.assertEqual(2,result['priorAttempts']);self.assertTrue(result['priorAttemptsRequireReview'])
        self.assertEqual(64,len(self.fixture.calls));self.assertEqual(set(self.modules),set(result['members']))

    def test_different_build_or_dependencies_fail_before_either_physical_reader(self):
        name='maximum-queue';data=self.data[name];classes=data/'producer/workspace'/self.modules[name].m.BUILDS[0]/'synthetic.class'
        original=classes.read_bytes();classes.write_bytes(b'different valid compiled class inventory');self.refresh_seed(name)
        with self.assertRaisesRegex(ValueError,'mixed source/build'):self.run_gate()
        self.assertEqual([],self.calls)
        classes.write_bytes(original);(data/'repository/surefire.jar').write_bytes(b'different dependency');self.refresh_seed(name)
        with self.assertRaisesRegex(ValueError,'mixed source/build'):self.run_gate()
        self.assertEqual([],self.calls)

    def test_failed_prepare_test_cannot_be_replaced_by_partial_label(self):
        path=self.data['maximum-queue']/'producer/workspace'/c.h.MODULE/'target/surefire-reports/TEST-synthetic.xml'
        suite=ET.parse(path);suite.getroot().set('skipped','1');ET.SubElement(suite.getroot().find('testcase'),'skipped');suite.write(path)
        self.refresh_seed('maximum-queue')
        with self.assertRaisesRegex(ValueError,'preparation unretried'):self.run_gate()
        self.assertEqual([],self.calls)

    def test_parent_scope_or_archive_binding_drift_is_rejected(self):
        for key,value in [('scope','small-resource'),('profile','small-queue'),('wholeHistories',True),('combinedResourcesQualified',True),
                          ('phase3Complete',True),('originalFirstDownloadedReplay',False),('rawArchiveSha256','e'*64)]:
            self.change=lambda name,path,result,k=key,v=value:result.update({k:v})
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'owning replay scope'):self.run_gate()
        self.assertFalse(c.seeds.read(self.output/'receipt.json')['maximumComponentOriginalsReplayed'])

    def test_exact_child_negatives_and_process_memory_are_revalidated(self):
        def missing(name,path,value):
            child=value['qualification'];child['qualification']['resources']['negatives']['staging-profile']=[]
            dest=path/'measurement/reader/verification/receipt.json';c.h.save(dest,child)
            value['readerMemory']['verificationReceiptSha256']=c.tc.file_hash(dest)
            c.h.save(path/'measurement/reader/memory.json',value['readerMemory'])
        self.change=missing
        with self.assertRaisesRegex(ValueError,'negative'):self.run_gate()
        def changed(name,path,value):
            value['readerMemory']['peakRssBytes']=1;c.h.save(path/'measurement/reader/memory.json',value['readerMemory'])
        self.change=changed
        with self.assertRaisesRegex(ValueError,'proc status binding'):self.run_gate()

    def test_child_execution_must_be_exact_successful_and_use_the_same_original(self):
        for mode in ('exit','command','duration','pins'):
            def change(name,path,value,mode=mode):
                measurement=path/'measurement';execution=c.seeds.read(measurement/'execution.json')
                if mode=='exit':execution['exit']=True
                elif mode=='command':execution['command'][6]='/another/original'
                elif mode=='duration':execution['elapsedSeconds']=-1
                else:c.h.save(measurement/'pins.json',{})
                c.h.save(measurement/'execution.json',execution)
            self.change=change
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'fresh reader execution'):self.run_gate()

    def test_new_rerun_during_readers_is_not_hidden_by_old_green_binding(self):
        self.after=lambda:self.fixture.api['actions/runs/100'].update(run_attempt=3)
        with self.assertRaisesRegex(ValueError,'exact context'):self.run_gate()
        self.assertEqual(list(self.modules),self.calls)
        value=c.seeds.read(self.output/'receipt.json');self.assertEqual('FAIL',value['status']);self.assertEqual(2,len(value['members']))
        self.assertFalse(value['maximumComponentOriginalsReplayed'])

    def test_changed_but_still_green_step_observations_are_rejected_across_replay(self):
        def change():
            self.fixture.api['actions/runs/100/attempts/2/jobs?per_page=100&page=1']['jobs'][0]['steps'][0]['started_at']='2026-01-01T00:00:01Z'
        self.after=change
        with self.assertRaisesRegex(ValueError,'workflow observations changed'):self.run_gate()

    def test_selected_artifact_identity_change_is_rejected_across_replay(self):
        self.after=lambda:self.fixture.rows()[0].update(id=400)
        with self.assertRaisesRegex(ValueError,'external bindings changed'):self.run_gate()

    def test_first_original_cannot_change_during_second_reader(self):
        def change():
            (self.output/'replay/maximum-native/original/data/producer/receipt.json').write_bytes(b'{}')
        self.after=change
        with self.assertRaisesRegex(ValueError,'producer/result binding'):self.run_gate()
        self.assertFalse(c.seeds.read(self.output/'receipt.json')['phase3Complete'])

    def test_retained_first_observation_or_preparation_cannot_be_replaced(self):
        self.after=lambda:(self.output/'binding-before/artifacts-before/maximum-native/page-1.json').write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError,'first observation changed'):self.run_gate()
        self.after=lambda:(self.output/'seeds/maximum-native/data/repository/surefire.jar').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'dependencies'):self.run_gate()

    def test_first_reader_failure_is_retained_without_running_second(self):
        def failed(*args):raise ValueError('original history rejected')
        with patch.object(self.modules['maximum-native'],'verify',side_effect=failed):
            with self.assertRaisesRegex(ValueError,'original history rejected'):self.run_gate()
        self.assertEqual([],self.calls);value=c.seeds.read(self.output/'receipt.json')
        self.assertEqual('maximum-native',value['active']);self.assertFalse(value['maximumComponentOriginalsReplayed'])
        self.assertFalse((self.output/'binding-after').exists())

    def test_capacity_rejection_precedes_api_hashing_unpacking_and_readers(self):
        with patch.object(c,'capacity',side_effect=ValueError('unqualified host')),patch.object(c.artifacts,'bind') as bind:
            with self.assertRaisesRegex(ValueError,'unqualified host'):self.run_gate()
            bind.assert_not_called()
        self.assertEqual([],self.calls);self.assertEqual([],self.fixture.calls)
        self.assertEqual('FAIL',c.seeds.read(self.output/'receipt.json')['status'])

    def test_output_overlap_cannot_touch_inputs(self):
        with self.assertRaisesRegex(ValueError,'overlaps'):
            c.run(self.index,self.zips,self.bundles,self.bundles/'invalid',self.fixture.get)
        self.assertFalse((self.bundles/'invalid').exists())


class MaximumAttestedCapacityTest(unittest.TestCase):
    def test_pair_workspace_reserve_does_not_relax_underlying_environment_checks(self):
        with patch.object(c.hosted_capacity,'check',side_effect=ValueError('not native Linux')):
            with self.assertRaisesRegex(ValueError,'not native Linux'):c.capacity('/workspace')
        for free in (c.MINIMUM_FREE_BYTES-1,c.MINIMUM_FREE_BYTES):
            record={'capacity':{'freeBytes':free}}
            with patch.object(c.hosted_capacity,'check',return_value=record) as check:
                if free<c.MINIMUM_FREE_BYTES:
                    with self.assertRaisesRegex(ValueError,'both retained originals'):c.capacity('/workspace')
                else:
                    value=c.capacity('/workspace');self.assertFalse(value['runtimeBudgetsChanged']);self.assertFalse(value['phase3Complete'])
                    self.assertEqual(c.MINIMUM_FREE_BYTES,value['minimumFreeBytes'])
                check.assert_called_once_with('/workspace','verify-download')


if __name__=='__main__':unittest.main()
