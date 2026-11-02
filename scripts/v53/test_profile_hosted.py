"""Synthetic hosted orchestration, not original JVM or Actions qualification."""
import copy
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from . import profile_hosted as w
from . import test_profile_matrix as fixtures
from .test_process_toolchain import record


class ProfileHostedTest(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ProfileMatrixTest();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root;self.profile='3-ADD'
        self.ctx=dict(kind='synthetic',repository='patricklfdm/GeneralSearchEngine',source='a'*40,
                      ref=w.BRANCH,event='push',run='13',attempt='2',workflow=w.WORKFLOW)
        self.data=self.root/'seed-data';self.data.mkdir()
        shutil.copytree(self.fixture.paths[self.profile],self.data/'producer');self.portable(self.data/'producer')
        repo=self.data/'repository';repo.mkdir();(repo/'surefire.jar').write_bytes(b'synthetic dependency');(repo/'plugin.pom').write_bytes(b'pom')
        self.pins=list(self.fixture.pins);self.pins[2]=w.tc.pin((self.data/'producer/toolchain.json').read_bytes())
        self.seed=dict(schema=w.SCHEMA,context=self.ctx,status='PARTIAL',phase3Complete=False,profiles=list(w.m.PROFILES),
                       **{k+'Sha256':v for k,v in zip(('source','build','toolchain','reader'),self.pins)},reader=self.fixture.reader,
                       repositorySha256=w.shared.dependencies(repo))
        w.h.save(self.data/'seed.json',self.seed);self.bundle=self.root/'seed-bundle';self.manifest=w.pack(self.data,self.bundle,self.ctx,'seed')

    def portable(self,producer):
        w.h.save(producer/'toolchain.json',record());value=w.m.read(producer/'receipt.json')
        value['toolchainSha256']=w.h.digest((producer/'toolchain.json').read_bytes());w.h.save(producer/'receipt.json',value)

    def raw(self,profile='3-ADD'):
        data=self.root/('raw-'+w.m.slug(profile));data.mkdir();self.fixture.producer(data/'producer',profile);self.portable(data/'producer')
        original=w.m.member(data/'producer',profile,*self.pins)
        receipt=dict(schema=w.SCHEMA,context=self.ctx,profile=profile,status='PARTIAL',phase3Complete=False,
            seedArchiveSha256=self.manifest['archiveSha256'],producerReceiptSha256=original['receiptSha256'],originalPlanSha256=original['plan'],
            **{k+'Sha256':v for k,v in zip(('source','build','toolchain','reader'),self.pins)})
        w.h.save(data/'hosted-member.json',receipt);bundle=self.root/('bundle-'+w.m.slug(profile));w.pack(data,bundle,self.ctx,'raw',profile)
        return data,bundle

    def verified(self):
        root=self.root/'verifiers';root.mkdir()
        for profile in w.m.PROFILES:
            member=dict(profile=profile,status='PASS',phase3Complete=False,qualification=self.fixture.result(profile),
                producerReceiptSha256=w.h.digest((profile+'receipt').encode()),originalPlanSha256=w.h.digest((profile+'plan').encode()),
                **{k+'Sha256':v for k,v in zip(('source','build','toolchain','reader'),self.pins)})
            value=dict(schema=w.SCHEMA,context=self.ctx,profile=profile,status='PARTIAL',phase3Complete=False,
                seedArchiveSha256=self.manifest['archiveSha256'],rawArchiveSha256=w.h.digest((profile+'archive').encode()),
                originalFirstDownloadedReplay=True,member=member)
            directory=root/w.artifact_name(self.ctx,'verified',profile);directory.mkdir();w.h.save(directory/'receipt.json',value)
        return root

    def test_seed_roundtrip_and_reader_source_dependencies_are_bound(self):
        data,manifest=w.unpack(self.bundle,self.root/'unpack',self.ctx,'seed')
        self.assertEqual(self.seed,w.seed_inputs(data,self.ctx));self.assertEqual(self.manifest,manifest)
        (data/'repository/surefire.jar').write_bytes(b'drift')
        with self.assertRaisesRegex(ValueError,'seed dependencies'):w.seed_inputs(data,self.ctx)
        (data/'repository/surefire.jar').write_bytes(b'synthetic dependency');(data/'producer/workspace/scripts/v53/pinned.py').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'recorded source changed'):w.seed_inputs(data,self.ctx)

    def test_archive_cannot_be_reused_across_workflow_source_attempt_profile_or_role(self):
        for index,ctx in enumerate((dict(self.ctx,attempt='3'),dict(self.ctx,source='b'*40),dict(self.ctx,workflow=w.shared.WORKFLOW))):
            with self.assertRaisesRegex(ValueError,'artifact binding'):w.unpack(self.bundle,self.root/f'wrong-{index}',ctx,'seed')
        with self.assertRaisesRegex(ValueError,'artifact binding'):w.unpack(self.bundle,self.root/'wrong-role',self.ctx,'raw','4-ADD')
        with self.assertRaisesRegex(ValueError,'artifact binding'):w.shared.unpack(self.bundle,self.root/'wrong-schema',self.ctx,'seed')

    def test_classes_toolchain_and_reader_drift_refuse(self):
        for i,name in enumerate(('producer/workspace/target/classes/original.class','producer/toolchain.json','seed.json')):
            data,_=w.unpack(self.bundle,self.root/f'copy-{i}',self.ctx,'seed');path=data/name
            if name=='seed.json':
                value=w.m.read(path);value['readerSha256']='b'*64;w.h.save(path,value)
            elif name.endswith('json'):w.h.save(path,dict(exit=0,stdout='different tools',stderr=''))
            else:path.write_bytes(b'changed')
            with self.assertRaises(ValueError):w.seed_inputs(data,self.ctx)

    def test_execution_selects_complete_joining_or_same_history_captured_removal_once(self):
        for profile in ('3-ADD','5-REMOVE'):
            with self.subTest(profile=profile):
                calls=[]
                def produce(output,maven,p,**options):
                    calls.append(options);self.fixture.producer(output,p);self.portable(output)
                with patch.object(w.tc,'capture',return_value=record()),patch.object(w.m.joining_run,'run',side_effect=produce) as joining,\
                     patch.object(w.m.remove_run,'run',side_effect=produce) as removal:
                    result=w.execute(self.bundle,self.root/('execute-'+profile),'mvn',profile,self.ctx)
                self.assertEqual(1,len(calls));self.assertTrue(calls[0]['portable_toolchain']);self.assertIn('source_from',calls[0])
                if profile.endswith('REMOVE'):self.assertTrue(calls[0]['retirement_captures']);joining.assert_not_called()
                else:self.assertTrue(calls[0]['complete']);removal.assert_not_called()
                self.assertEqual('PARTIAL',result['status']);self.assertFalse(result['phase3Complete'])

    def test_execution_failure_retains_failed_archive_without_retry(self):
        with patch.object(w.tc,'capture',return_value=record()),patch.object(w.m.joining_run,'run',side_effect=ValueError('native failure')) as run:
            with self.assertRaisesRegex(ValueError,'native failure'):w.execute(self.bundle,self.root/'failed','mvn',self.profile,self.ctx)
        run.assert_called_once();data,_=w.unpack(self.root/'failed/artifact',self.root/'failed-copy',self.ctx,'raw',self.profile)
        self.assertEqual('FAIL',w.m.read(data/'hosted-member.json')['status'])

    def test_archive_failure_preserves_original_failure_and_is_separately_recorded(self):
        with patch.object(w.tc,'capture',return_value=record()),patch.object(w.m.joining_run,'run',side_effect=ValueError('native failure')),\
             patch.object(w,'pack',side_effect=OSError('archive failed')):
            with self.assertRaisesRegex(ValueError,'native failure'):w.execute(self.bundle,self.root/'two-failures','mvn',self.profile,self.ctx)
        value=w.m.read(self.root/'two-failures/receipt.json');self.assertEqual('FAIL',value['status'])
        self.assertEqual('native failure',value['failure']['message']);self.assertEqual('archive failed',value['artifactFailure']['message'])

    def test_archive_failure_after_execution_is_fatal_and_not_a_partial_success(self):
        def produce(output,maven,profile,**options):self.fixture.producer(output,profile);self.portable(output)
        with patch.object(w.tc,'capture',return_value=record()),patch.object(w.m.joining_run,'run',side_effect=produce),\
             patch.object(w,'pack',side_effect=OSError('archive failed')):
            with self.assertRaisesRegex(OSError,'archive failed'):w.execute(self.bundle,self.root/'pack-failure','mvn',self.profile,self.ctx)
        self.assertEqual('FAIL',w.m.read(self.root/'pack-failure/receipt.json')['status'])

    def test_wrong_worker_tools_refuse_before_native_execution(self):
        tools=record();tools['identity']['binaries']['java/bin/java']='b'*64
        with patch.object(w.tc,'capture',return_value=tools),patch.object(w.m.joining_run,'run') as run:
            with self.assertRaisesRegex(ValueError,'worker toolchain'):w.execute(self.bundle,self.root/'wrong-tools','mvn',self.profile,self.ctx)
        run.assert_not_called()

    def test_both_families_replay_only_downloaded_originals(self):
        for profile in ('3-ADD','4-REMOVE'):
            _,bundle=self.raw(profile)
            with self.fixture.readers():result=w.verify(self.bundle,bundle,self.root/('verify-'+profile),profile,self.ctx)
            self.assertEqual('PARTIAL',result['status']);self.assertTrue(result['originalFirstDownloadedReplay'])
            self.assertEqual(profile,result['member']['profile']);w.m.check_result(result['member']['qualification'],profile)

    def test_failed_original_never_counts_as_negative_success(self):
        _,bundle=self.raw()
        with patch.object(w.m.joining,'qualify',side_effect=ValueError('physical original failure')):
            with self.assertRaisesRegex(ValueError,'physical original failure'):w.verify(self.bundle,bundle,self.root/'failed-verify',self.profile,self.ctx)
        self.assertEqual('FAIL',w.m.read(self.root/'failed-verify/receipt.json')['status'])

    def test_changed_hosted_binding_refuses_before_replay(self):
        data,_=self.raw();value=w.m.read(data/'hosted-member.json');value['sourceSha256']='b'*64;w.h.save(data/'hosted-member.json',value)
        bundle=self.root/'altered';w.pack(data,bundle,self.ctx,'raw',self.profile)
        with patch.object(w.m,'qualify_member') as replay,self.assertRaisesRegex(ValueError,'original member binding'):
            w.verify(self.bundle,bundle,self.root/'altered-verify',self.profile,self.ctx)
        replay.assert_not_called()

    def test_complete_seven_synthetic_results_stay_scoped(self):
        result=w.aggregate(self.bundle,self.verified(),self.root/'aggregate',self.ctx,'success','success')
        self.assertEqual('PASS',result['status']);self.assertEqual(7,result['wholeHistories']);self.assertEqual(4,result['notApplicable'])
        self.assertEqual(list(w.m.PROFILES),[v['profile'] for v in result['cases']])
        self.assertTrue(result['declaredMembershipProfileMatrixQualified'])
        for key in ('phase3Complete','processDeathQualified','originalObservationCoverageComplete'):self.assertFalse(result[key])

    def test_missing_extra_failed_cancelled_or_skipped_stages_block_aggregate(self):
        root=self.verified()
        for i,(execute,verify) in enumerate((('failure','success'),('success','failure'),('success','cancelled'),('skipped','success'))):
            with self.assertRaisesRegex(ValueError,'workflow stage'):w.aggregate(self.bundle,root,self.root/f'failed-stage-{i}',self.ctx,execute,verify)
        first=root/w.artifact_name(self.ctx,'verified',self.profile);first.rename(root/'extra')
        with self.assertRaisesRegex(ValueError,'verified inventory'):w.aggregate(self.bundle,root,self.root/'extra',self.ctx,'success','success')
        shutil.rmtree(root/'extra')
        with self.assertRaisesRegex(ValueError,'verified inventory'):w.aggregate(self.bundle,root,self.root/'missing',self.ctx,'success','success')

    def test_receipt_mutations_cannot_relabel_failed_partial_or_copied_histories(self):
        root=self.verified();path=root/w.artifact_name(self.ctx,'verified',self.profile)/'receipt.json';original=w.m.read(path)
        second=w.m.read(root/w.artifact_name(self.ctx,'verified','4-ADD')/'receipt.json')
        changes=[lambda v:v['context'].update(attempt='1'),lambda v:v.update(schema=w.shared.SCHEMA),lambda v:v.update(status='FAIL'),
                 lambda v:v.update(phase3Complete=True),lambda v:v.update(originalFirstDownloadedReplay=False),
                 lambda v:v.update(seedArchiveSha256='c'*64),lambda v:v['member'].update(buildSha256='c'*64),
                 lambda v:v['member']['qualification']['negatives'][0].update(reason='unrelated failure'),
                 lambda v:v['member'].update(originalPlanSha256=second['member']['originalPlanSha256']),
                 lambda v:v.update(rawArchiveSha256=second['rawArchiveSha256'])]
        for i,change in enumerate(changes):
            with self.subTest(mutation=i):
                value=copy.deepcopy(original);change(value);w.h.save(path,value)
                with self.assertRaises(ValueError):w.aggregate(self.bundle,root,self.root/f'bad-receipt-{i}',self.ctx,'success','success')

    def test_summary_failure_never_claims_success_or_phase_completion(self):
        summary=self.root/'summary.md'
        with patch.object(w,'context',return_value=self.ctx),patch.object(w.tc,'locate',return_value='mvn'),\
             patch.object(w,'prepare',side_effect=ValueError('preparation failed')),patch.dict(os.environ,{'GITHUB_STEP_SUMMARY':str(summary)}),\
             patch('sys.argv',['profile_hosted','prepare','--output',str(self.root/'out')]):
            with self.assertRaisesRegex(ValueError,'preparation failed'):w.main()
        self.assertIn('| Status | `FAIL` |',summary.read_text());self.assertIn('| Phase 3 complete | `False` |',summary.read_text())

    def test_context_requires_new_exact_workflow_and_branch(self):
        env=dict(GITHUB_ACTIONS='true',GITHUB_REPOSITORY=self.ctx['repository'],GITHUB_SHA=self.ctx['source'],GITHUB_REF=w.BRANCH,
            GITHUB_EVENT_NAME='push',GITHUB_RUN_ID='13',GITHUB_RUN_ATTEMPT='2',V53_WORKFLOW_SHA=self.ctx['source'],
            V53_WORKFLOW_REF=self.ctx['repository']+'/'+w.WORKFLOW+'@'+w.BRANCH)
        with patch.dict(os.environ,env,clear=True),patch.object(w.shared.subprocess,'check_output',return_value=self.ctx['source']+'\n'):
            self.assertEqual(dict(self.ctx,kind='github'),w.context())
            for key,value in [('V53_WORKFLOW_REF',self.ctx['repository']+'/'+w.shared.WORKFLOW+'@'+w.BRANCH),
                              ('GITHUB_EVENT_NAME','pull_request'),('GITHUB_REF',w.shared.BRANCH),('GITHUB_RUN_ATTEMPT','1x')]:
                with patch.dict(os.environ,{key:value}),self.assertRaises(ValueError):w.context()
            with patch.dict(os.environ,{'GITHUB_EVENT_NAME':'workflow_dispatch'}):self.assertEqual('workflow_dispatch',w.context()['event'])

    def fake_source(self,repo,work):
        (work/'scripts/v53').mkdir(parents=True);(work/'scripts/v53/pinned.py').write_bytes(b'pinned reader')
        return dict(head=self.ctx['source'],files=self.fixture.reader['files'])

    def fake_build(self,command,work,log,**kwargs):
        self.assertEqual(['-Dtest=V53BallotAllocatorTest','test'],command[-2:])
        for name in w.m.BUILDS:
            target=work/name;target.mkdir(parents=True);(target/'original.class').write_bytes(b'pinned compiled bytes')
        reports=work/w.h.MODULE/'target/surefire-reports';reports.mkdir()
        suite=ET.Element('testsuite',dict(name='io.test.V53BallotAllocatorTest',tests='1',failures='0',errors='0',skipped='0'))
        ET.SubElement(suite,'testcase',dict(classname='io.test.V53BallotAllocatorTest',name='syntheticPreparationOnly'))
        ET.ElementTree(suite).write(reports/'TEST-original.xml')
        repository=Path(os.environ['MAVEN_OPTS'].split('=',1)[1]);(repository/'surefire.jar').write_bytes(b'synthetic dependency')
        (repository/'plugin.pom').write_bytes(b'pom');return dict(exit=0)

    def test_shared_preparation_builds_reference_classes_and_returns_only_partial(self):
        with patch.object(w.h,'source_copy',side_effect=self.fake_source),patch.object(w.tc,'capture',return_value=record()),\
             patch.object(w.h,'execute',side_effect=self.fake_build) as build:
            result=w.prepare(self.root/'prepare','mvn',self.ctx)
        build.assert_called_once();self.assertEqual('PARTIAL',result['status']);self.assertEqual(list(w.m.PROFILES),result['profiles'])
        self.assertEqual(self.pins,w.pins(result));data,_=w.unpack(self.root/'prepare/artifact',self.root/'prepared-copy',self.ctx,'seed')
        self.assertEqual(result,w.seed_inputs(data,self.ctx))

    def test_shared_preparation_rejects_flaky_build_and_preserves_failure(self):
        def flaky(*args,**kwargs):
            result=self.fake_build(*args,**kwargs);report=args[1]/w.h.MODULE/'target/surefire-reports/TEST-original.xml'
            tree=ET.parse(report);ET.SubElement(tree.getroot()[0],'flakyFailure');tree.write(report);return result
        with patch.object(w.h,'source_copy',side_effect=self.fake_source),patch.object(w.tc,'capture',return_value=record()),\
             patch.object(w.h,'execute',side_effect=flaky):
            with self.assertRaisesRegex(ValueError,'unretried test'):w.prepare(self.root/'prepare-failed','mvn',self.ctx)
        self.assertEqual('FAIL',w.m.read(self.root/'prepare-failed/receipt.json')['status'])
        self.assertFalse((self.root/'prepare-failed/artifact').exists())

    def test_existing_remove_preparation_retains_its_52_case_schema_and_pins(self):
        with patch.object(w.h,'source_copy',side_effect=self.fake_source),patch.object(w.tc,'capture',return_value=record()),\
             patch.object(w.h,'execute',side_effect=self.fake_build),patch.object(w.shared.m,'reader_manifest',return_value=self.fixture.reader):
            result=w.shared.prepare(self.root/'legacy-prepare','mvn',self.ctx)
            data,_=w.shared.unpack(self.root/'legacy-prepare/artifact',self.root/'legacy-copy',self.ctx,'seed')
            self.assertEqual(result,w.shared.seed_inputs(data,self.ctx))
        self.assertEqual(w.shared.SCHEMA,result['schema']);self.assertEqual(list(w.shared.m.KINDS),result['cases'])
        self.assertEqual(self.pins,w.pins(result));self.assertEqual('PARTIAL',result['status'])


if __name__=='__main__':unittest.main()
