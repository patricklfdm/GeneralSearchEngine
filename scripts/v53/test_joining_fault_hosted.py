"""Synthetic orchestration/provenance; never a native or hosted acceptance claim."""
import copy
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from . import joining_fault_hosted as w
from . import test_joining_fault_composition as fixtures
from .test_process_toolchain import record


class JoiningFaultHostedTest(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.JoiningFaultCohortTest();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root;self.case='SOURCE_OFFER'
        self.ctx=dict(kind='synthetic',repository='patricklfdm/GeneralSearchEngine',source='a'*40,
                      ref=w.BRANCH,event='push',run='13',attempt='2',workflow=w.WORKFLOW)
        self.data=self.root/'seed-data';self.data.mkdir()
        shutil.copytree(self.fixture.paths[self.case],self.data/'producer');self.portable(self.data/'producer')
        repo=self.data/'repository';repo.mkdir();(repo/'surefire.jar').write_bytes(b'dependency');(repo/'plugin.pom').write_bytes(b'pom')
        self.pins=list(self.fixture.pins);self.pins[2]=w.tc.pin((self.data/'producer/toolchain.json').read_bytes())
        self.seed=dict(schema=w.SCHEMA,context=self.ctx,status='PARTIAL',phase3Complete=False,cases=list(w.m.KINDS),
            **{k+'Sha256':v for k,v in zip(('source','build','toolchain','reader'),self.pins)},reader=self.fixture.reader,
            repositorySha256=w.shared.dependencies(repo))
        w.h.save(self.data/'seed.json',self.seed);self.bundle=self.root/'seed-bundle';self.manifest=w.pack(self.data,self.bundle,self.ctx,'seed')

    def portable(self,producer):
        w.h.save(producer/'toolchain.json',record());value=w.m.legacy.read(producer/'receipt.json')
        value['toolchainSha256']=w.h.digest((producer/'toolchain.json').read_bytes());w.h.save(producer/'receipt.json',value)

    def produce(self,output,maven,*,fault,source_from,portable_toolchain):
        self.assertTrue(portable_toolchain);self.assertTrue((source_from/'source.json').is_file())
        self.fixture.fixture.producer(output,fault);w.h.save(output/'execution.json',dict(exit=0));self.portable(output)

    def result(self,case):
        producer=self.fixture.paths[case];receipt=w.m.legacy.read(producer/'receipt.json')
        return self.fixture.replay(producer/receipt['raw'],full_chain=True)

    def replay(self,raw,*,full_chain):
        self.assertTrue(full_chain);return self.result((raw/'original-plan.gsbp').read_text())

    def raw(self,case='SOURCE_OFFER'):
        data=self.root/('raw-'+w.m.slug(case));data.mkdir()
        self.produce(data/'producer','mvn',fault=case,source_from=self.data/'producer',portable_toolchain=True)
        original=w.m.member(data/'producer',case,*self.pins)
        value=dict(schema=w.SCHEMA,context=self.ctx,case=case,status='PARTIAL',phase3Complete=False,
            seedArchiveSha256=self.manifest['archiveSha256'],producerReceiptSha256=original['receiptSha256'],originalPlanSha256=original['plan'],
            **{k+'Sha256':v for k,v in zip(('source','build','toolchain','reader'),self.pins)})
        w.h.save(data/'hosted-member.json',value);bundle=self.root/('bundle-'+w.m.slug(case));w.pack(data,bundle,self.ctx,'raw',case)
        return data,bundle

    def verified(self):
        root=self.root/'verifiers';root.mkdir()
        for case in w.m.KINDS:
            member=dict(case=case,status='PASS',phase3Complete=False,qualification=self.result(case),
                producerReceiptSha256=w.h.digest((case+'receipt').encode()),originalPlanSha256=w.h.digest((case+'plan').encode()),
                **{k+'Sha256':v for k,v in zip(('source','build','toolchain','reader'),self.pins)})
            value=dict(schema=w.SCHEMA,context=self.ctx,case=case,status='PARTIAL',phase3Complete=False,
                seedArchiveSha256=self.manifest['archiveSha256'],rawArchiveSha256=w.h.digest((case+'archive').encode()),
                originalFirstDownloadedReplay=True,member=member)
            directory=root/w.artifact_name(self.ctx,'verified',case);directory.mkdir();w.h.save(directory/'receipt.json',value)
        return root

    def test_seed_roundtrip_requires_actual_reader_source_classes_tools_and_dependencies(self):
        data,manifest=w.unpack(self.bundle,self.root/'copy',self.ctx,'seed')
        self.assertEqual(self.seed,w.seed_inputs(data,self.ctx));self.assertEqual(self.manifest,manifest)
        changes=('producer/workspace/original.java','producer/workspace/target/classes/original.class','producer/toolchain.json','repository/surefire.jar','seed.json')
        for i,name in enumerate(changes):
            data,_=w.unpack(self.bundle,self.root/f'changed-{i}',self.ctx,'seed');path=data/name
            if name=='seed.json':
                value=w.m.legacy.read(path);value['readerSha256']='b'*64;w.h.save(path,value)
            elif name.endswith('.json'):w.h.save(path,dict(exit=0,stdout='changed tools',stderr=''))
            else:path.write_bytes(b'drift')
            with self.subTest(name=name),self.assertRaises(ValueError):w.seed_inputs(data,self.ctx)
        value=w.m.legacy.read(self.data/'seed.json');value['cases']=list(reversed(value['cases']));w.h.save(self.data/'seed.json',value)
        with self.assertRaisesRegex(ValueError,'seed scope'):w.seed_inputs(self.data,self.ctx)

    def test_archive_binding_rejects_workflow_source_attempt_case_role_and_schema(self):
        for i,ctx in enumerate((dict(self.ctx,attempt='3'),dict(self.ctx,source='b'*40),dict(self.ctx,workflow=w.shared.WORKFLOW))):
            with self.assertRaisesRegex(ValueError,'artifact binding'):w.unpack(self.bundle,self.root/f'bad-{i}',ctx,'seed')
        _,bundle=self.raw()
        with self.assertRaisesRegex(ValueError,'artifact binding'):w.unpack(bundle,self.root/'wrong-case',self.ctx,'raw','CHUNK')
        with self.assertRaisesRegex(ValueError,'artifact binding'):w.unpack(bundle,self.root/'wrong-role',self.ctx,'seed')
        with self.assertRaisesRegex(ValueError,'artifact binding'):w.shared.unpack(self.bundle,self.root/'wrong-schema',self.ctx,'seed')

    def test_each_whole_fault_runs_once_from_seed_and_never_ordinary_profile(self):
        for case in w.m.KINDS:
            with patch.object(w.tc,'capture',return_value=record()),patch.object(w.h,'run',side_effect=self.produce) as run:
                result=w.execute(self.bundle,self.root/('execute-'+case),'mvn',case,self.ctx)
            run.assert_called_once();self.assertEqual(case,run.call_args.kwargs['fault'])
            self.assertEqual('PARTIAL',result['status']);self.assertFalse(result['phase3Complete'])

    def test_wrong_case_or_worker_tools_refuse_before_native_execution(self):
        with patch.object(w.h,'run') as run,self.assertRaisesRegex(ValueError,'declared execution'):
            w.execute(self.bundle,self.root/'unknown','mvn','UNKNOWN',self.ctx)
        run.assert_not_called();self.assertFalse((self.root/'unknown').exists())
        tools=record();tools['identity']['binaries']['java/bin/java']='b'*64
        with patch.object(w.tc,'capture',return_value=tools),patch.object(w.h,'run') as run:
            with self.assertRaisesRegex(ValueError,'worker toolchain'):w.execute(self.bundle,self.root/'bad-tools','mvn',self.case,self.ctx)
        run.assert_not_called()

    def test_native_failure_retains_failed_archive_without_retry(self):
        with patch.object(w.tc,'capture',return_value=record()),patch.object(w.h,'run',side_effect=ValueError('native failure')) as run:
            with self.assertRaisesRegex(ValueError,'native failure'):w.execute(self.bundle,self.root/'failed','mvn',self.case,self.ctx)
        run.assert_called_once();data,_=w.unpack(self.root/'failed/artifact',self.root/'failed-copy',self.ctx,'raw',self.case)
        self.assertEqual('FAIL',w.m.legacy.read(data/'hosted-member.json')['status'])

    def test_archive_failure_preserves_native_failure_and_also_fails_successful_execution(self):
        for success in (False,True):
            output=self.root/('archive-failure-'+str(success))
            native=self.produce if success else ValueError('native failure')
            with patch.object(w.tc,'capture',return_value=record()),patch.object(w.h,'run',side_effect=native),patch.object(w,'pack',side_effect=OSError('pack failed')):
                with self.assertRaisesRegex(OSError if success else ValueError,'pack failed' if success else 'native failure'):
                    w.execute(self.bundle,output,'mvn',self.case,self.ctx)
            value=w.m.legacy.read(output/'receipt.json');self.assertEqual('FAIL',value['status']);self.assertEqual('pack failed',value['artifactFailure']['message'])
            if not success:self.assertEqual('native failure',value['failure']['message'])

    def test_runtime_classes_and_dependencies_cannot_drift_from_seed(self):
        for kind in ('classes','dependencies'):
            def mutate(output,maven,**kwargs):
                self.produce(output,maven,**kwargs)
                path=output/'workspace/target/classes/original.class' if kind=='classes' else Path(os.environ['MAVEN_OPTS'].split('=',1)[1])/'surefire.jar'
                path.write_bytes(b'drift')
            with patch.object(w.tc,'capture',return_value=record()),patch.object(w.h,'run',side_effect=mutate) as run:
                with self.assertRaisesRegex(ValueError,'original built bytes|runtime dependency drift'):
                    w.execute(self.bundle,self.root/('drift-'+kind),'mvn',self.case,self.ctx)
            run.assert_called_once()

    def test_downloaded_verifier_replays_original_before_both_negative_families(self):
        for case in w.m.KINDS:
            _,bundle=self.raw(case)
            with patch.object(w.m.gate,'qualify',side_effect=self.replay) as replay:
                result=w.verify(self.bundle,bundle,self.root/('verify-'+case),case,self.ctx)
            replay.assert_called_once();self.assertIn('original/data/producer',str(replay.call_args.args[0]));self.assertTrue(replay.call_args.kwargs['full_chain'])
            self.assertEqual('PARTIAL',result['status']);self.assertTrue(result['originalFirstDownloadedReplay'])
            w.m.check_result(result['member']['qualification'],case)

    def test_failed_original_and_changed_binding_cannot_be_negative_success(self):
        data,bundle=self.raw()
        with patch.object(w.m.gate,'qualify',side_effect=ValueError('physical original failed')):
            with self.assertRaisesRegex(ValueError,'physical original failed'):w.verify(self.bundle,bundle,self.root/'failed-verify',self.case,self.ctx)
        self.assertEqual('FAIL',w.m.legacy.read(self.root/'failed-verify/receipt.json')['status'])
        value=w.m.legacy.read(data/'hosted-member.json');value['sourceSha256']='b'*64;w.h.save(data/'hosted-member.json',value)
        bundle=self.root/'modified';w.pack(data,bundle,self.ctx,'raw',self.case)
        with patch.object(w.m,'qualify_member') as replay,self.assertRaisesRegex(ValueError,'original member binding'):
            w.verify(self.bundle,bundle,self.root/'modified-verify',self.case,self.ctx)
        replay.assert_not_called()

    def test_downloaded_bytes_changed_during_replay_are_refused(self):
        _,bundle=self.raw();original=w.m.qualify_member
        def changed(producer,*args):
            result=original(producer,*args);(producer.parent/'unexpected').write_bytes(b'new data');return result
        with patch.object(w.m.gate,'qualify',side_effect=self.replay),patch.object(w.m,'qualify_member',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'downloaded original changed'):w.verify(self.bundle,bundle,self.root/'changed-verify',self.case,self.ctx)

    def test_all_three_aggregate_requires_two_exact_negative_families_and_stays_scoped(self):
        result=w.aggregate(self.bundle,self.verified(),self.root/'aggregate',self.ctx,'success','success')
        self.assertEqual('PASS',result['status']);self.assertEqual(3,result['wholeHistories']);self.assertEqual(42,result['faultNegativeCases'])
        self.assertEqual(63,result['ballotNegativeCases']);self.assertEqual(99,result['rejected']);self.assertEqual(6,result['notApplicable'])
        self.assertEqual(list(w.m.KINDS),[v['case'] for v in result['cases']]);self.assertTrue(result['joiningSourceFaultCompositionQualified'])
        for key in ('phase3Complete','processDeathQualified','allMembershipProfilesQualified','originalObservationCoverageComplete'):self.assertFalse(result[key])

    def test_missing_extra_failed_cancelled_or_skipped_stage_cannot_aggregate(self):
        root=self.verified()
        for i,(execute,verify) in enumerate((('failure','success'),('success','failure'),('success','cancelled'),('skipped','success'),(None,'success'))):
            with self.assertRaisesRegex(ValueError,'workflow stage'):w.aggregate(self.bundle,root,self.root/f'failed-{i}',self.ctx,execute,verify)
        first=root/w.artifact_name(self.ctx,'verified',self.case);first.rename(root/'extra')
        with self.assertRaisesRegex(ValueError,'verified inventory'):w.aggregate(self.bundle,root,self.root/'extra',self.ctx,'success','success')
        shutil.rmtree(root/'extra')
        with self.assertRaisesRegex(ValueError,'verified inventory'):w.aggregate(self.bundle,root,self.root/'missing',self.ctx,'success','success')

    def test_receipt_changes_cannot_relabel_failure_wrong_case_or_duplicate_history(self):
        root=self.verified();path=root/w.artifact_name(self.ctx,'verified',self.case)/'receipt.json';original=w.m.legacy.read(path)
        second=w.m.legacy.read(root/w.artifact_name(self.ctx,'verified','CHUNK')/'receipt.json')
        changes=[lambda v:v['context'].update(attempt='1'),lambda v:v.update(schema=w.shared.SCHEMA),lambda v:v.update(status='FAIL'),
            lambda v:v.update(case='CHUNK'),lambda v:v.update(phase3Complete=True),lambda v:v.update(originalFirstDownloadedReplay=False),
            lambda v:v.update(seedArchiveSha256='c'*64),lambda v:v['member'].update(buildSha256='c'*64),
            lambda v:v['member']['qualification']['negatives'].pop(),lambda v:v['member']['qualification']['ballotQualification']['negatives'][0].update(reason='unrelated failure'),
            lambda v:v['member']['qualification']['original'].update(fullImplementedCompositionQualified=False),
            lambda v:v['member'].update(originalPlanSha256=second['member']['originalPlanSha256']),lambda v:v.update(rawArchiveSha256=second['rawArchiveSha256'])]
        for i,change in enumerate(changes):
            value=copy.deepcopy(original);change(value);w.h.save(path,value)
            with self.subTest(mutation=i),self.assertRaises(ValueError):w.aggregate(self.bundle,root,self.root/f'bad-receipt-{i}',self.ctx,'success','success')

    def test_context_plan_and_failure_summary_bind_new_workflow(self):
        env=dict(GITHUB_ACTIONS='true',GITHUB_REPOSITORY=self.ctx['repository'],GITHUB_SHA=self.ctx['source'],GITHUB_REF=w.BRANCH,
            GITHUB_EVENT_NAME='push',GITHUB_RUN_ID='13',GITHUB_RUN_ATTEMPT='2',V53_WORKFLOW_SHA=self.ctx['source'],
            V53_WORKFLOW_REF=self.ctx['repository']+'/'+w.WORKFLOW+'@'+w.BRANCH)
        with patch.dict(os.environ,env,clear=True),patch.object(w.shared.subprocess,'check_output',return_value=self.ctx['source']+'\n'):
            self.assertEqual(dict(self.ctx,kind='github'),w.context())
            for key,value in [('V53_WORKFLOW_REF',self.ctx['repository']+'/'+w.shared.WORKFLOW+'@'+w.BRANCH),('GITHUB_EVENT_NAME','pull_request'),('GITHUB_REF',w.shared.BRANCH),('GITHUB_RUN_ATTEMPT','1x')]:
                with patch.dict(os.environ,{key:value}),self.assertRaises(ValueError):w.context()
            with patch.dict(os.environ,{'GITHUB_EVENT_NAME':'workflow_dispatch'}):self.assertEqual('workflow_dispatch',w.context()['event'])
        output=io.StringIO()
        with patch.object(w,'context',return_value=self.ctx),patch('sys.argv',['hosted','plan']),redirect_stdout(output):w.main()
        self.assertEqual(dict(include=[dict(case=k,id=k.lower()) for k in w.m.KINDS]),json.loads(output.getvalue()))
        summary=self.root/'summary.md'
        with patch.object(w,'context',return_value=self.ctx),patch.object(w.tc,'locate',return_value='mvn'),patch.object(w,'prepare',side_effect=ValueError('prepare failed')),\
             patch.dict(os.environ,{'GITHUB_STEP_SUMMARY':str(summary)}),patch('sys.argv',['hosted','prepare','--output',str(self.root/'out')]):
            with self.assertRaisesRegex(ValueError,'prepare failed'):w.main()
        self.assertIn('| Status | `FAIL` |',summary.read_text());self.assertIn('| Phase 3 complete | `False` |',summary.read_text())

    def test_existing_output_is_never_overwritten(self):
        path=self.root/'existing';path.mkdir();(path/'prior').write_text('original')
        with self.assertRaises(FileExistsError):w.execute(self.bundle,path,'mvn',self.case,self.ctx)
        self.assertEqual('original',(path/'prior').read_text())

    def fake_source(self,repo,work):
        work.mkdir();(work/'original.java').write_bytes(b'original source');return dict(head=self.ctx['source'],files=self.fixture.reader['files'])

    def fake_build(self,command,work,log,**kwargs):
        self.assertEqual(['-Dtest=V53BallotAllocatorTest','test'],command[-2:])
        for name in w.m.legacy.BUILDS:
            target=work/name;target.mkdir(parents=True);(target/'original.class').write_bytes(b'original build')
        reports=work/w.h.MODULE/'target/surefire-reports';reports.mkdir()
        suite=ET.Element('testsuite',dict(name='io.test.V53BallotAllocatorTest',tests='1',failures='0',errors='0',skipped='0'))
        ET.SubElement(suite,'testcase',dict(classname='io.test.V53BallotAllocatorTest',name='syntheticPreparationOnly'))
        ET.ElementTree(suite).write(reports/'TEST-original.xml')
        repository=Path(os.environ['MAVEN_OPTS'].split('=',1)[1]);(repository/'surefire.jar').write_bytes(b'dependency');(repository/'plugin.pom').write_bytes(b'pom')
        return dict(exit=0)

    def test_prepare_uses_shared_reference_build_once_and_retains_three_case_scope(self):
        with patch.object(w.h,'source_copy',side_effect=self.fake_source),patch.object(w.tc,'capture',return_value=record()),patch.object(w.h,'execute',side_effect=self.fake_build) as build:
            result=w.prepare(self.root/'prepare','mvn',self.ctx)
        build.assert_called_once();self.assertEqual(self.pins,w.pins(result));self.assertEqual(list(w.m.KINDS),result['cases'])
        self.assertEqual('PARTIAL',result['status']);data,_=w.unpack(self.root/'prepare/artifact',self.root/'prepared-copy',self.ctx,'seed')
        self.assertEqual(result,w.seed_inputs(data,self.ctx))

    def test_failed_preparation_cannot_upload_seed(self):
        with patch.object(w.h,'source_copy',side_effect=self.fake_source),patch.object(w.tc,'capture',return_value=record()),patch.object(w.h,'execute',return_value=dict(exit=1)) as run:
            with self.assertRaisesRegex(ValueError,'preparation failed'):w.prepare(self.root/'failed-prepare','mvn',self.ctx)
        run.assert_called_once();self.assertEqual('FAIL',w.m.legacy.read(self.root/'failed-prepare/receipt.json')['status'])
        self.assertFalse((self.root/'failed-prepare/artifact').exists())


if __name__=='__main__':unittest.main()
