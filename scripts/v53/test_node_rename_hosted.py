"""Downloaded synthetic originals exercise provenance, not native acceptance."""
import copy
import os
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
from . import node_rename_hosted as w
from . import test_node_rename_matrix as fixtures
from .test_process_toolchain import record


class NodeRenameHostedTest(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.NodeRenameMatrixTest();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root;self.case=w.m.KINDS[0];self.pins=self.fixture.pins
        self.ctx=dict(kind='synthetic',repository='patricklfdm/GeneralSearchEngine',source='a'*40,
            ref=w.BRANCH,event='push',run='13',attempt='2',workflow=w.WORKFLOW)
        self.data=self.root/'seed-data';self.data.mkdir();shutil.copytree(self.fixture.path,self.data/'producer')
        repo=self.data/'repository';repo.mkdir();(repo/'surefire.jar').write_bytes(b'dependency');(repo/'plugin.pom').write_bytes(b'pom')
        self.seed=dict(schema=w.SCHEMA,context=self.ctx,status='PARTIAL',phase3Complete=False,cases=list(w.m.KINDS),
            **{k+'Sha256':v for k,v in zip(('source','build','toolchain','reader'),self.pins)},reader=self.fixture.reader,
            repositorySha256=w.shared.dependencies(repo))
        w.h.save(self.data/'seed.json',self.seed);self.bundle=self.root/'seed-bundle'
        self.manifest=w.pack(self.data,self.bundle,self.ctx,'seed')

    def produce(self,output,maven,case,*,source_from):
        self.assertTrue((source_from/'source.json').is_file());self.fixture.producer(output,case)

    def result(self,case):
        path=self.fixture.paths[case];return self.fixture.replay(path/w.m.read(path/'receipt.json')['raw'])

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

    def test_each_whole_history_runs_once_and_downloaded_copy_is_replayed(self):
        for case in w.m.KINDS:
            output=self.root/('execute-'+w.m.slug(case))
            with patch.object(w.tc,'capture',return_value=record()),patch.object(w.m.run,'run',side_effect=self.produce) as run:
                result=w.execute(self.bundle,output,'mvn',case,self.ctx)
            run.assert_called_once();self.assertEqual(case,run.call_args.args[2]);self.assertEqual('PARTIAL',result['status'])
            with patch.object(w.m.gate,'qualify',side_effect=self.fixture.replay) as replay:
                result=w.verify(self.bundle,output/'artifact',self.root/('verify-'+w.m.slug(case)),case,self.ctx)
            replay.assert_called_once();self.assertIn('original/data/producer',str(replay.call_args.args[0]))
            self.assertTrue(result['originalFirstDownloadedReplay']);self.assertEqual('PARTIAL',result['status'])

    def test_native_failure_keeps_original_and_does_not_retry(self):
        def failure(output,maven,case,**kwargs):
            output.mkdir();(output/'failed-original').write_text('retained');raise ValueError('native failure')
        output=self.root/'failed'
        with patch.object(w.tc,'capture',return_value=record()),patch.object(w.m.run,'run',side_effect=failure) as run:
            with self.assertRaisesRegex(ValueError,'native failure'):w.execute(self.bundle,output,'mvn',self.case,self.ctx)
        run.assert_called_once();data,_=w.unpack(output/'artifact',self.root/'failed-copy',self.ctx,'raw',self.case)
        self.assertEqual('retained',(data/'producer/failed-original').read_text());self.assertEqual('FAIL',w.m.read(data/'hosted-member.json')['status'])

    def test_wrong_tools_or_unknown_case_refuse_before_execution(self):
        tools=record();tools['identity']['binaries']['java/bin/java']='b'*64
        with patch.object(w.tc,'capture',return_value=tools),patch.object(w.m.run,'run') as run:
            with self.assertRaisesRegex(ValueError,'worker toolchain'):w.execute(self.bundle,self.root/'wrong-tools','mvn',self.case,self.ctx)
            with self.assertRaisesRegex(ValueError,'declared execution'):w.execute(self.bundle,self.root/'wrong-case','mvn','unknown',self.ctx)
        run.assert_not_called()

    def test_seed_and_archive_enforce_source_attempt_workflow_and_case(self):
        for i,ctx in enumerate((dict(self.ctx,attempt='3'),dict(self.ctx,source='b'*40),dict(self.ctx,workflow=w.shared.WORKFLOW))):
            with self.assertRaisesRegex(ValueError,'artifact binding'):w.unpack(self.bundle,self.root/f'wrong-{i}',ctx,'seed')
        for i,name in enumerate(('producer/workspace/reader.py','producer/workspace/target/classes/original.class','repository/surefire.jar')):
            data,_=w.unpack(self.bundle,self.root/f'drift-{i}',self.ctx,'seed');(data/name).write_bytes(b'drift')
            with self.assertRaises(ValueError):w.seed_inputs(data,self.ctx)
        for kind,case in (('raw',self.case),('seed',self.case)):
            with self.assertRaisesRegex(ValueError,'artifact binding'):w.unpack(self.bundle,self.root/('role-'+kind),self.ctx,kind,case)
        data,_=w.unpack(self.bundle,self.root/'legacy-tools',self.ctx,'seed')
        w.h.save(data/'producer/toolchain.json',dict(exit=0,stdout='unbound tools',stderr=''))
        seed=w.m.read(data/'seed.json');seed['toolchainSha256']=w.tc.pin((data/'producer/toolchain.json').read_bytes())
        w.h.save(data/'seed.json',seed)
        with self.assertRaisesRegex(ValueError,'process toolchain record'):w.seed_inputs(data,self.ctx)

    def test_aggregate_requires_four_exact_originals_and_all_negative_results(self):
        result=w.aggregate(self.bundle,self.verified(),self.root/'aggregate',self.ctx,'success','success')
        self.assertEqual('PASS',result['status']);self.assertEqual(4,result['wholeHistories']);self.assertEqual(136,result['negativeCases'])
        self.assertTrue(result['declaredNodeRenameMatrixQualified']);self.assertFalse(result['phase3Complete'])

    def test_bad_stage_or_missing_verifier_cannot_aggregate(self):
        root=self.verified()
        for i,(execute,verify) in enumerate((('failure','success'),('success','failure'),('success','cancelled'),('skipped','success'),(None,'success'))):
            with self.assertRaisesRegex(ValueError,'workflow stage'):w.aggregate(self.bundle,root,self.root/f'failed-{i}',self.ctx,execute,verify)
        shutil.rmtree(root/w.artifact_name(self.ctx,'verified',self.case))
        with self.assertRaisesRegex(ValueError,'verified inventory'):w.aggregate(self.bundle,root,self.root/'missing',self.ctx,'success','success')

    def test_changed_receipts_cannot_mix_attempts_duplicate_originals_or_relax_negatives(self):
        root=self.verified();path=root/w.artifact_name(self.ctx,'verified',self.case)/'receipt.json';original=w.m.read(path)
        second=w.m.read(root/w.artifact_name(self.ctx,'verified',w.m.KINDS[1])/'receipt.json')
        changes=[lambda v:v['context'].update(attempt='1'),lambda v:v.update(status='FAIL'),lambda v:v.update(case=w.m.KINDS[1]),
            lambda v:v.update(originalFirstDownloadedReplay=False),lambda v:v.update(seedArchiveSha256='b'*64),
            lambda v:v['member'].update(sourceSha256='b'*64),lambda v:v['member']['qualification']['negatives'].pop(),
            lambda v:v['member']['qualification']['negatives'][0].update(reason='unrelated'),
            lambda v:v['member']['qualification']['original'].update(interruptedClientSuccess=True),
            lambda v:v['member'].update(originalPlanSha256=second['member']['originalPlanSha256']),lambda v:v.update(rawArchiveSha256=second['rawArchiveSha256'])]
        for i,change in enumerate(changes):
            value=copy.deepcopy(original);change(value);w.h.save(path,value)
            with self.subTest(change=i),self.assertRaises(ValueError):w.aggregate(self.bundle,root,self.root/f'changed-{i}',self.ctx,'success','success')

    def test_original_failure_cannot_count_as_negative_success(self):
        output=self.root/'execute'
        with patch.object(w.tc,'capture',return_value=record()),patch.object(w.m.run,'run',side_effect=self.produce):
            w.execute(self.bundle,output,'mvn',self.case,self.ctx)
        with patch.object(w.m.gate,'qualify',side_effect=ValueError('invalid original')):
            with self.assertRaisesRegex(ValueError,'invalid original'):w.verify(self.bundle,output/'artifact',self.root/'verify',self.case,self.ctx)
        self.assertEqual('FAIL',w.m.read(self.root/'verify/receipt.json')['status'])

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
