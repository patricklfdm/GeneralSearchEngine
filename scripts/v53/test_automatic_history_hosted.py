"""Downloaded synthetic originals exercise provenance, not native acceptance."""
import copy
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
from . import automatic_history_hosted as w
from . import test_automatic_history as fixtures
from .test_process_toolchain import record


class AutomaticHistoryHostedTest(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.AutomaticHistoryTest();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root;self.case=w.m.CASES[0];self.pins=self.fixture.pins
        self.ctx=dict(kind='synthetic',repository='patricklfdm/GeneralSearchEngine',source='a'*40,
            ref=w.BRANCH,event='push',run='13',attempt='2',workflow=w.WORKFLOW)
        self.data=self.root/'seed-data';self.data.mkdir();shutil.copytree(self.fixture.path,self.data/'producer')
        repo=self.data/'repository';repo.mkdir();(repo/'surefire.jar').write_bytes(b'dependency');(repo/'plugin.pom').write_bytes(b'pom')
        self.seed=dict(schema=w.SCHEMA,context=self.ctx,status='PARTIAL',phase3Complete=False,cases=list(w.m.CASES),
            **{k+'Sha256':v for k,v in zip(('source','build','toolchain','reader'),self.pins)},reader=self.fixture.reader,
            repositorySha256=w.shared.dependencies(repo))
        w.h.save(self.data/'seed.json',self.seed);self.bundle=self.root/'seed-bundle'
        self.manifest=w.pack(self.data,self.bundle,self.ctx,'seed')

    def produce(self,output,maven,case,*,source_from):
        self.assertTrue((source_from/'source.json').is_file());self.fixture.producer(output,case)

    def result(self,case):
        return fixtures.replay(case)

    def verified(self):
        root=self.root/'verifiers';root.mkdir()
        for case in w.m.CASES:
            member=dict(case=case,status='PASS',phase3Complete=False,qualification=self.result(case),
                producerReceiptSha256=w.h.digest((case+'receipt').encode()),plans={name:w.h.digest((case+'/'+name).encode()) for name in w.m.histories(case)},
                **{k+'Sha256':v for k,v in zip(('source','build','toolchain','reader'),self.pins)})
            value=dict(schema=w.SCHEMA,context=self.ctx,case=case,status='PARTIAL',phase3Complete=False,
                seedArchiveSha256=self.manifest['archiveSha256'],rawArchiveSha256=w.h.digest((case+'archive').encode()),
                originalFirstDownloadedReplay=True,member=member)
            directory=root/w.artifact_name(self.ctx,'verified',case);directory.mkdir();w.h.save(directory/'receipt.json',value)
        return root

    def test_each_whole_history_runs_once_and_downloaded_copy_is_replayed(self):
        for case in w.m.CASES:
            output=self.root/('execute-'+case)
            with patch.object(w.tc,'capture',return_value=record()),patch.object(w.m,'capture',side_effect=self.produce) as run:
                result=w.execute(self.bundle,output,'mvn',case,self.ctx)
            run.assert_called_once();self.assertEqual(case,run.call_args.args[2]);self.assertEqual('PARTIAL',result['status'])
            with patch.object(w.m,'replay',return_value=fixtures.replay(case)) as replay:
                result=w.verify(self.bundle,output/'artifact',self.root/('verify-'+case),case,self.ctx)
            replay.assert_called_once();self.assertIn('original/data/producer',str(replay.call_args.args[0]))
            self.assertTrue(result['originalFirstDownloadedReplay']);self.assertEqual('PARTIAL',result['status'])

    def test_native_failure_keeps_original_and_does_not_retry(self):
        def failure(output,maven,case,**kwargs):
            output.mkdir();(output/'failed-original').write_text('retained');raise ValueError('native failure')
        output=self.root/'failed'
        with patch.object(w.tc,'capture',return_value=record()),patch.object(w.m,'capture',side_effect=failure) as run:
            with self.assertRaisesRegex(ValueError,'native failure'):w.execute(self.bundle,output,'mvn',self.case,self.ctx)
        run.assert_called_once();data,_=w.unpack(output/'artifact',self.root/'failed-copy',self.ctx,'raw',self.case)
        self.assertEqual('retained',(data/'producer/failed-original').read_text());self.assertEqual('FAIL',w.m.read(data/'hosted-member.json')['status'])

    def test_downloaded_bundle_rejects_links_and_extra_members_before_unpacking(self):
        alias=self.root/'seed-alias';alias.symlink_to(self.bundle,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'artifact directory'):w.unpack(alias,self.root/'linked-output',self.ctx,'seed')
        (self.bundle/'unbound-file').write_bytes(b'not in the artifact contract')
        with self.assertRaisesRegex(ValueError,'artifact directory'):w.unpack(self.bundle,self.root/'extra-output',self.ctx,'seed')
        self.assertFalse((self.root/'linked-output').exists());self.assertFalse((self.root/'extra-output').exists())

    def test_wrong_tools_or_unknown_case_refuse_before_execution(self):
        tools=record();tools['identity']['binaries']['java/bin/java']='b'*64
        with patch.object(w.tc,'capture',return_value=tools),patch.object(w.m,'capture') as run:
            with self.assertRaisesRegex(ValueError,'worker toolchain'):w.execute(self.bundle,self.root/'wrong-tools','mvn',self.case,self.ctx)
            with self.assertRaisesRegex(ValueError,'declared execution'):w.execute(self.bundle,self.root/'wrong-case','mvn','unknown',self.ctx)
        run.assert_not_called()

    def test_seed_and_archive_enforce_source_attempt_workflow_and_case(self):
        for i,ctx in enumerate((dict(self.ctx,attempt='3'),dict(self.ctx,source='b'*40),dict(self.ctx,workflow=w.shared.WORKFLOW))):
            with self.assertRaisesRegex(ValueError,'artifact binding'):w.unpack(self.bundle,self.root/f'wrong-{i}',ctx,'seed')
        for i,name in enumerate(('producer/workspace/scripts/v53/reader.py','producer/workspace/target/classes/original.class','repository/surefire.jar')):
            data,_=w.unpack(self.bundle,self.root/f'drift-{i}',self.ctx,'seed');(data/name).write_bytes(b'drift')
            with self.assertRaises(ValueError):w.seed_inputs(data,self.ctx)
        for kind,case in (('raw',self.case),('seed',self.case)):
            with self.assertRaisesRegex(ValueError,'artifact binding'):w.unpack(self.bundle,self.root/('role-'+kind),self.ctx,kind,case)
        data,_=w.unpack(self.bundle,self.root/'legacy-tools',self.ctx,'seed')
        w.h.save(data/'producer/toolchain.json',dict(exit=0,stdout='unbound tools',stderr=''))
        seed=w.m.read(data/'seed.json');seed['toolchainSha256']=w.tc.pin((data/'producer/toolchain.json').read_bytes())
        w.h.save(data/'seed.json',seed)
        with self.assertRaisesRegex(ValueError,'process toolchain record'):w.seed_inputs(data,self.ctx)

    def test_aggregate_requires_fifty_exact_originals_and_all_negative_results(self):
        result=w.aggregate(self.bundle,self.verified(),self.root/'aggregate',self.ctx,'success','success')
        self.assertEqual('PASS',result['status']);self.assertEqual(50,result['wholeOwnershipHistories']);self.assertEqual(3,result['executionGroups']);self.assertEqual(142,result['negativeCases'])
        self.assertTrue(result['declaredMatricesQualified']);self.assertFalse(result['phase3Complete'])
        self.assertEqual(142,result['rejected']);self.assertEqual(7,result['notApplicable'])

    def test_superseded_competition_requires_its_own_complete_vector(self):
        root=self.verified();path=root/w.artifact_name(self.ctx,'verified','competition')/'receipt.json'
        value=w.m.read(path);value['member']['qualification']=fixtures.replay('competition','superseded');w.h.save(path,value)
        result=w.aggregate(self.bundle,root,self.root/'superseded',self.ctx,'success','success')
        self.assertEqual((207,207,0),(result['negativeCases'],result['rejected'],result['notApplicable']))
        value['member']['qualification']['negatives']=fixtures.replay('competition')['negatives'];w.h.save(path,value)
        with self.assertRaisesRegex(ValueError,'negative'):
            w.aggregate(self.bundle,root,self.root/'shortened-superseded',self.ctx,'success','success')

    def test_unrecognized_competition_cannot_choose_an_easier_catalogue(self):
        root=self.verified();path=root/w.artifact_name(self.ctx,'verified','competition')/'receipt.json'
        original=w.m.read(path)
        for i,change in enumerate((lambda v:v['original']['exports'].update(sourceWindows=3),
                                  lambda v:v['notApplicable'].clear(),
                                  lambda v:v['original']['lifecycle'].update(fullLifecycleQualified=True))):
            value=copy.deepcopy(original);change(value['member']['qualification']);w.h.save(path,value)
            with self.subTest(change=i),self.assertRaises(ValueError):
                w.aggregate(self.bundle,root,self.root/f'unsupported-{i}',self.ctx,'success','success')

    def test_restart_attachment_travels_with_original_and_corruption_fails_before_replay(self):
        case='higher-ballot-restart';output=self.root/'restart'
        with patch.object(w.tc,'capture',return_value=record()),patch.object(w.m,'capture',side_effect=self.produce):
            w.execute(self.bundle,output,'mvn',case,self.ctx)
        data,_=w.unpack(output/'artifact',self.root/'restart-download',self.ctx,'raw',case)
        producer=data/'producer';captured=producer/w.m.read(producer/'receipt.json')['captures']
        self.assertTrue((captured/w.m.restart.OBSERVATIONS).is_file())
        (captured/w.m.restart.OBSERVATIONS).write_bytes(b'changed observations')
        bundle=self.root/'corrupt-restart';w.pack(data,bundle,self.ctx,'raw',case)
        with patch.object(w.m,'replay') as replay,self.assertRaisesRegex(ValueError,'collection'):
            w.verify(self.bundle,bundle,self.root/'rejected-restart',case,self.ctx)
        replay.assert_not_called()

    def test_reply_matrix_must_have_all_forty_eight_distinct_plans(self):
        root=self.verified();path=root/w.artifact_name(self.ctx,'verified','reply-revocation')/'receipt.json'
        original=w.m.read(path);names=list(original['member']['plans'])
        for i,change in enumerate((lambda p:p.pop(names[-1]),lambda p:p.update({names[-1]:p[names[0]]}))):
            value=copy.deepcopy(original);change(value['member']['plans']);w.h.save(path,value)
            with self.subTest(change=i),self.assertRaisesRegex(ValueError,'complete original plans'):
                w.aggregate(self.bundle,root,self.root/f'partial-replies-{i}',self.ctx,'success','success')

    def test_plan_emits_only_three_complete_groups_without_execution(self):
        stream=io.StringIO()
        with patch.object(w,'context',return_value=self.ctx),patch('sys.argv',['hosted','plan']),redirect_stdout(stream),\
                patch.object(w,'prepare') as prepare,patch.object(w.m,'capture') as capture:
            w.main()
        self.assertEqual({'include':[dict(case=case,id=case) for case in w.m.CASES]},json.loads(stream.getvalue()))
        prepare.assert_not_called();capture.assert_not_called()
        self.assertEqual([1,1,48],[len(v) for v in w.SHARDS.values()]);self.assertEqual(50,len(set(w.HISTORIES)))

    def test_bad_stage_or_missing_verifier_cannot_aggregate(self):
        root=self.verified()
        for i,(execute,verify) in enumerate((('failure','success'),('success','failure'),('success','cancelled'),('skipped','success'),(None,'success'))):
            with self.assertRaisesRegex(ValueError,'workflow stage'):w.aggregate(self.bundle,root,self.root/f'failed-{i}',self.ctx,execute,verify)
        shutil.rmtree(root/w.artifact_name(self.ctx,'verified',self.case))
        with self.assertRaisesRegex(ValueError,'verified inventory'):w.aggregate(self.bundle,root,self.root/'missing',self.ctx,'success','success')

    def test_changed_receipts_cannot_mix_attempts_duplicate_originals_or_relax_negatives(self):
        root=self.verified();path=root/w.artifact_name(self.ctx,'verified',self.case)/'receipt.json';original=w.m.read(path)
        second=w.m.read(root/w.artifact_name(self.ctx,'verified',w.m.CASES[1])/'receipt.json')
        changes=[lambda v:v['context'].update(attempt='1'),lambda v:v.update(status='FAIL'),lambda v:v.update(case=w.m.CASES[1]),
            lambda v:v.update(originalFirstDownloadedReplay=False),lambda v:v.update(seedArchiveSha256='b'*64),
            lambda v:v['member'].update(sourceSha256='b'*64),lambda v:v['member']['qualification']['negatives'].pop(),
            lambda v:v['member']['qualification']['negatives'][0].update(reason='unrelated'),
            lambda v:v['member']['qualification']['original']['exports'].update(phase3Complete=True),
            lambda v:v['member']['plans'].update({next(iter(v['member']['plans'])):next(iter(second['member']['plans'].values()))}),lambda v:v.update(rawArchiveSha256=second['rawArchiveSha256'])]
        for i,change in enumerate(changes):
            value=copy.deepcopy(original);change(value);w.h.save(path,value)
            with self.subTest(change=i),self.assertRaises(ValueError):w.aggregate(self.bundle,root,self.root/f'changed-{i}',self.ctx,'success','success')

    def test_original_failure_cannot_count_as_negative_success(self):
        output=self.root/'execute'
        with patch.object(w.tc,'capture',return_value=record()),patch.object(w.m,'capture',side_effect=self.produce):
            w.execute(self.bundle,output,'mvn',self.case,self.ctx)
        with patch.object(w.m,'replay',side_effect=ValueError('invalid original')):
            with self.assertRaisesRegex(ValueError,'invalid original'):w.verify(self.bundle,output/'artifact',self.root/'verify',self.case,self.ctx)
        self.assertEqual('FAIL',w.m.read(self.root/'verify/receipt.json')['status'])

    def test_complete_download_execute_replay_aggregate_path(self):
        inputs=self.root/'downloaded-verifiers';inputs.mkdir()
        for case in w.m.CASES:
            output=self.root/('roundtrip-'+case)
            with patch.object(w.tc,'capture',return_value=record()),patch.object(w.m,'capture',side_effect=self.produce):
                w.execute(self.bundle,output,'mvn',case,self.ctx)
            with patch.object(w.m,'replay',return_value=fixtures.replay(case)):
                w.verify(self.bundle,output/'artifact',self.root/('replayed-'+case),case,self.ctx)
            directory=inputs/w.artifact_name(self.ctx,'verified',case);directory.mkdir()
            shutil.copyfile(self.root/('replayed-'+case)/'receipt.json',directory/'receipt.json')
        result=w.aggregate(self.bundle,inputs,self.root/'roundtrip-aggregate',self.ctx,'success','success')
        self.assertEqual((50,3,142),(result['wholeOwnershipHistories'],result['executionGroups'],result['negativeCases']))
        for field in ('phase3Complete','combinedPeakResourcesQualified','allMembershipProfilesQualified','fullLifecycleQualified','completeExportLifetimesQualified'):
            self.assertIs(False,result[field])

    def test_preparation_freezes_complete_catalogue_without_executing_histories(self):
        def prepare(data,maven,ctx):
            shutil.copytree(self.data/'producer',data/'producer');shutil.copytree(self.data/'repository',data/'repository')
            return {k:v for k,v in self.seed.items() if k.endswith('Sha256') and k!='readerSha256'}
        output=self.root/'prepared'
        with patch.object(w.shared,'prepare_source',side_effect=prepare) as source,patch.object(w.m,'capture') as native:
            result=w.prepare(output,'mvn',self.ctx)
        source.assert_called_once();native.assert_not_called();self.assertEqual('PARTIAL',result['status'])
        downloaded,_=w.unpack(output/'artifact',self.root/'prepared-download',self.ctx,'seed')
        self.assertEqual(list(w.m.CASES),w.seed_inputs(downloaded,self.ctx)['cases'])
        with self.assertRaises(FileExistsError):w.prepare(output,'mvn',self.ctx)

    def test_pack_failure_retains_native_failure_and_never_becomes_partial(self):
        def fail(output,*args,**kwargs):
            output.mkdir();(output/'original-failure').write_text('kept');raise ValueError('native failed first')
        output=self.root/'native-and-pack-failure'
        with patch.object(w.tc,'capture',return_value=record()),patch.object(w.m,'capture',side_effect=fail) as native,patch.object(w,'pack',side_effect=ValueError('pack failed')):
            with self.assertRaisesRegex(ValueError,'native failed first'):w.execute(self.bundle,output,'mvn',self.case,self.ctx)
        native.assert_called_once();result=w.m.read(output/'receipt.json')
        self.assertEqual('FAIL',result['status']);self.assertEqual('native failed first',result['failure']['message'])
        self.assertEqual('pack failed',result['artifactFailure']['message']);self.assertTrue((output/'data/producer/original-failure').is_file())

    def test_missing_duplicate_or_foreign_original_plans_refuse(self):
        root=self.verified();path=root/w.artifact_name(self.ctx,'verified',self.case)/'receipt.json';original=w.m.read(path)
        for index,change in enumerate((lambda v:v['member']['plans'].pop(next(iter(v['member']['plans']))),
            lambda v:v['member']['plans'].update(foreign='a'*64))):
            value=copy.deepcopy(original);change(value);w.h.save(path,value)
            with self.assertRaisesRegex(ValueError,'complete original plans'):
                w.aggregate(self.bundle,root,self.root/f'plans-{index}',self.ctx,'success','success')

    def test_only_dispatch_or_dedicated_branch_context_is_admitted(self):
        env=dict(GITHUB_ACTIONS='true',GITHUB_REPOSITORY=self.ctx['repository'],GITHUB_SHA=self.ctx['source'],GITHUB_REF=w.BRANCH,
            GITHUB_EVENT_NAME='push',GITHUB_RUN_ID='13',GITHUB_RUN_ATTEMPT='2',V53_WORKFLOW_SHA=self.ctx['source'],
            V53_WORKFLOW_REF=self.ctx['repository']+'/'+w.WORKFLOW+'@'+w.BRANCH)
        with patch.dict(os.environ,env,clear=True),patch.object(w.shared.subprocess,'check_output',return_value=self.ctx['source']+'\n'):
            self.assertEqual(dict(self.ctx,kind='github'),w.context())
            for key,value in (('GITHUB_EVENT_NAME','pull_request'),('GITHUB_REF',w.shared.BRANCH),('V53_WORKFLOW_SHA','b'*40)):
                with patch.dict(os.environ,{key:value}),self.assertRaises(ValueError):w.context()
            with patch.dict(os.environ,{'GITHUB_EVENT_NAME':'workflow_dispatch'}):self.assertEqual('workflow_dispatch',w.context()['event'])


if __name__=='__main__':unittest.main()
