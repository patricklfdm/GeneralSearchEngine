"""Synthetic hosted admission/transport guards, not native qualification."""
import copy
import io
import json
import os
from pathlib import Path
import re
import shutil
import tarfile
import unittest
from unittest.mock import patch
from . import queue_resource_hosted as w
from . import test_source_queue_run as fixtures
from . import test_queue_completion_run as completed


class QueueResourceHostedTest(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.SourceQueueRunTest();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        p=patch.object(w.completion,'reader_manifest',return_value=self.fixture.reader);p.start();self.addCleanup(p.stop)
        self.root=self.fixture.root;self.ctx=dict(kind='synthetic',repository='patricklfdm/GeneralSearchEngine',source='a'*40,
            ref=w.BRANCH,event='workflow_dispatch',run='7',attempt='2',workflow=w.WORKFLOW)
        self.data=self.root/'seed-data';self.data.mkdir();shutil.copytree(self.fixture.path,self.data/'producer')
        repo=self.data/'repository';repo.mkdir();(repo/'surefire.jar').write_bytes(b'original dependency')
        self.seed=dict(schema=w.SCHEMA,context=self.ctx,status='PARTIAL',cases=list(w.HISTORIES),phase3Complete=False,
                       **self.fixture.pins,reader=self.fixture.reader,repositorySha256=w.shared.dependencies(repo))
        w.h.save(self.data/'seed.json',self.seed);self.bundle=self.root/'seed-bundle'
        self.manifest=w.pack(self.data,self.bundle,self.ctx,'seed')

    def raw(self):
        data=self.root/'raw-data';data.mkdir();shutil.copytree(self.fixture.path,data/'producer')
        original=w.source.member(data/'producer',w.source.PROFILE,w.pins(self.seed))
        claimed=dict(schema=w.SCHEMA,context=self.ctx,case='source-queue',status='PARTIAL',phase3Complete=False,
                     seedArchiveSha256=self.manifest['archiveSha256'],producerReceiptSha256=original['producerReceiptSha256'],**w.pins(self.seed))
        w.h.save(data/'hosted-member.json',claimed);bundle=self.root/'raw-bundle';w.pack(data,bundle,self.ctx,'raw','source-queue');return data,bundle

    def verify(self,bundle,name='verify'):
        return w.verify(self.bundle,bundle,self.root/name,'source-queue',self.ctx)

    def test_seed_requires_exact_source_build_reader_tools_dependencies_and_profile(self):
        self.assertEqual(self.seed,w.seed_inputs(self.data,self.ctx))
        targets=['producer/workspace/scripts/v53/reader.py','producer/workspace/target/classes/original.class',
                 'producer/toolchain.json','repository/surefire.jar','seed.json']
        for i,target in enumerate(targets):
            data,_=w.unpack(self.bundle,self.root/f'bad-{i}',self.ctx,'seed');p=data/target
            if target=='seed.json':
                value=w.source.read(p);value['cases']=['source-queue'];w.h.save(p,value)
            else:p.write_bytes(b'changed')
            with self.subTest(target=target),self.assertRaises((ValueError,json.JSONDecodeError)):w.seed_inputs(data,self.ctx)

    def test_wrong_context_kind_profile_archive_bytes_and_extra_files_are_rejected(self):
        for i,field in enumerate(('attempt','source','run','workflow')):
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'binding'):
                w.unpack(self.bundle,self.root/f'ctx-{i}',dict(self.ctx,**{field:'wrong'}),'seed')
        with self.assertRaisesRegex(ValueError,'binding'):w.unpack(self.bundle,self.root/'kind',self.ctx,'raw','source-queue')
        path=self.bundle/'manifest.json';value=w.source.read(path);value['case']='replay-smoke-1';w.h.save(path,value)
        with self.assertRaisesRegex(ValueError,'binding'):w.unpack(self.bundle,self.root/'profile',self.ctx,'seed')
        w.h.save(path,self.manifest)
        with (self.bundle/'bundle.tar.gz').open('ab') as stream:stream.write(b'changed')
        with self.assertRaisesRegex(ValueError,'digest'):w.unpack(self.bundle,self.root/'bytes',self.ctx,'seed')
        (self.bundle/'extra').write_text('extra')
        with self.assertRaisesRegex(ValueError,'artifact shape'):w.unpack(self.bundle,self.root/'shape',self.ctx,'seed')

    def test_explicit_archive_bound_does_not_change_existing_default(self):
        self.assertEqual(1024**3,w.shared.MAX_BYTES);self.assertEqual(9*1024**3,w.limit('raw','queue-completion'))
        self.assertEqual(1024**3,w.limit('seed',None))
        root=self.root/'bounded';root.mkdir();(root/'a').write_bytes(b'a'*400);(root/'b').write_bytes(b'b'*400)
        bundle=self.root/'bounded-bundle';w.shared.pack(root,bundle,self.ctx,'raw',maximum=1000)
        w.shared.unpack(bundle,self.root/'roundtrip',self.ctx,'raw',maximum=1000)
        with self.assertRaisesRegex(ValueError,'archive capacity'):w.shared.unpack(bundle,self.root/'too-small',self.ctx,'raw',maximum=700)
        with self.assertRaisesRegex(ValueError,'byte capacity'):w.shared.pack(root,self.root/'small-pack',self.ctx,'raw',maximum=700)
        for i,value in enumerate((0,-1,True,None)):
            with self.assertRaisesRegex(ValueError,'explicit byte bound'):w.shared.pack(root,self.root/f'bound-{i}',self.ctx,'raw',maximum=value)
        with self.assertRaisesRegex(ValueError,'separation'):w.pack(root,root/'archive',self.ctx,'raw','source-queue')

    def test_raw_archive_rejects_links_traversal_duplicates_and_large_files(self):
        for i,(name,kind,size) in enumerate([('../escape',tarfile.REGTYPE,1),('data/link',tarfile.SYMTYPE,0),
                ('data/hard',tarfile.LNKTYPE,0),('data/huge',tarfile.REGTYPE,256*1024*1024+1),('data/duplicate',tarfile.REGTYPE,1)]):
            bundle=self.root/f'hostile-{i}';bundle.mkdir();archive=bundle/'bundle.tar.gz'
            with tarfile.open(archive,'w:gz') as stream:
                item=tarfile.TarInfo(name);item.type=kind;item.size=size
                stream.addfile(item,io.BytesIO(b'x'*size) if size<1024 else None)
                if 'duplicate' in name:stream.addfile(item,io.BytesIO(b'x'))
            manifest=dict(self.manifest,kind='raw',case='source-queue',archiveSha256=w.tc.file_hash(archive));w.h.save(bundle/'manifest.json',manifest)
            with self.subTest(name=name),self.assertRaises(ValueError):w.unpack(bundle,self.root/f'extract-{i}',self.ctx,'raw','source-queue')
        self.assertFalse((self.root/'escape').exists())

    def test_execute_uses_one_full_profile_and_independent_seed_and_keeps_partial(self):
        def capture(output,maven,profile,**kw):
            self.assertEqual(w.source.PROFILE,profile);self.assertIn('/seed/data/producer',str(kw['source_from']))
            shutil.copytree(self.fixture.path,output)
        with patch.object(w.tc,'capture',return_value=w.source.read(self.data/'producer/toolchain.json')),patch.object(w.source,'capture',side_effect=capture) as call:
            value=w.execute(self.bundle,self.root/'execute','mvn','source-queue',self.ctx)
        self.assertEqual(1,call.call_count);self.assertEqual('PARTIAL',value['status']);self.assertFalse(value['phase3Complete'])
        data,_=w.unpack(self.root/'execute/artifact',self.root/'downloaded',self.ctx,'raw','source-queue')
        self.assertEqual(value,w.source.read(data/'hosted-member.json'));self.assertEqual(self.seed,w.seed_inputs(self.data,self.ctx))

    def test_execution_failure_is_retained_without_retry(self):
        with patch.object(w.tc,'capture',return_value=w.source.read(self.data/'producer/toolchain.json')),patch.object(w.source,'capture',side_effect=ValueError('original failure')) as call:
            with self.assertRaisesRegex(ValueError,'original failure'):w.execute(self.bundle,self.root/'execute','mvn','source-queue',self.ctx)
        self.assertEqual(1,call.call_count)
        data,_=w.unpack(self.root/'execute/artifact',self.root/'downloaded',self.ctx,'raw','source-queue')
        self.assertEqual('FAIL',w.source.read(data/'hosted-member.json')['status'])

    def test_failed_artifact_retention_preserves_original_error(self):
        with patch.object(w.tc,'capture',return_value=w.source.read(self.data/'producer/toolchain.json')),\
             patch.object(w.source,'capture',side_effect=ValueError('original failure')),patch.object(w,'pack',side_effect=OSError('disk full')):
            with self.assertRaisesRegex(ValueError,'original failure'):w.execute(self.bundle,self.root/'execute','mvn','source-queue',self.ctx)
        result=w.source.read(self.root/'execute/receipt.json')
        self.assertEqual('original failure',result['failure']['message']);self.assertEqual('disk full',result['artifactFailure']['message'])

    def test_complete_downloaded_replay_qualifies_only_observed_ownership(self):
        _,bundle=self.raw()
        with patch.object(w.source.gate,'qualify',return_value=fixtures.replay()) as call:value=self.verify(bundle)
        self.assertEqual(1,call.call_count);self.assertIn('/verify/original/data/producer/',str(call.call_args.args[0]))
        self.assertEqual('PARTIAL',value['status']);self.assertTrue(value['member']['queuePressureQualified'])
        self.assertFalse(value['member']['combinedResourcesQualified']);self.assertFalse(value['phase3Complete'])
        self.assertEqual(8,len(value['member']['qualification']['negatives']))

    def test_wrong_context_pins_case_seed_and_producer_receipt_are_rejected(self):
        data,bundle=self.raw();path=data/'hosted-member.json';original=w.source.read(path)
        changes=[lambda v:v['context'].update(attempt='3'),lambda v:v.update(status='PASS'),lambda v:v.update(case='queue-completion'),
                 lambda v:v.update(phase3Complete=True),lambda v:v.update(buildSha256='b'*64),lambda v:v.update(seedArchiveSha256='b'*64),
                 lambda v:v.update(producerReceiptSha256='b'*64)]
        for i,change in enumerate(changes):
            value=copy.deepcopy(original);change(value);w.h.save(path,value);shutil.rmtree(bundle);w.pack(data,bundle,self.ctx,'raw','source-queue')
            with patch.object(w.source.gate,'qualify',return_value=fixtures.replay()),self.assertRaises(ValueError):self.verify(bundle,'bad-member-'+str(i))

    def test_failed_original_missing_negatives_and_smoke_cannot_qualify(self):
        _,bundle=self.raw()
        with patch.object(w.source.gate,'qualify',side_effect=ValueError('original invalid')):
            with self.assertRaisesRegex(ValueError,'original invalid'):self.verify(bundle,'original')
        for i,value in enumerate((dict(fixtures.replay(),mode='diagnostic'),dict(fixtures.replay(),negatives=[]))):
            with patch.object(w.source.gate,'qualify',return_value=value),self.assertRaisesRegex(ValueError,'result shape|exact negatives'):
                self.verify(bundle,'incomplete-'+str(i))
        self.assertEqual('FAIL',w.source.read(self.root/'original/receipt.json')['status'])

    def test_context_and_failed_summary(self):
        env=dict(GITHUB_ACTIONS='true',GITHUB_REPOSITORY=self.ctx['repository'],GITHUB_SHA=self.ctx['source'],GITHUB_REF=w.BRANCH,
                 GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_RUN_ID='7',GITHUB_RUN_ATTEMPT='2',V53_WORKFLOW_SHA=self.ctx['source'],
                 V53_WORKFLOW_REF=self.ctx['repository']+'/'+w.WORKFLOW+'@'+w.BRANCH)
        with patch.dict(os.environ,env,clear=True),patch.object(w.shared.subprocess,'check_output',return_value=self.ctx['source']+'\n'):
            self.assertEqual(dict(self.ctx,kind='github'),w.context())
            for key,value in [('GITHUB_EVENT_NAME','pull_request'),('GITHUB_EVENT_NAME','push'),('V53_WORKFLOW_REF','other'),('GITHUB_RUN_ATTEMPT','0')]:
                with patch.dict(os.environ,{key:value}),self.assertRaises(ValueError):w.context()
        summary=self.root/'summary.md'
        with patch.object(w,'context',return_value=self.ctx),patch.object(w.tc,'locate',return_value='mvn'),\
             patch.object(w,'prepare',side_effect=ValueError('prepare failure')),patch.dict(os.environ,{'GITHUB_STEP_SUMMARY':str(summary)}),\
             patch('sys.argv',['hosted','prepare','--output',str(self.root/'unused')]):
            with self.assertRaisesRegex(ValueError,'prepare failure'):w.main()
        self.assertIn('| Status | `FAIL` |',summary.read_text())

    def all_members(self):
        fixture=completed.QueueCompletionRunTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        inputs=self.root/'verified';inputs.mkdir()
        for case,original,replay in (('source-queue',self.fixture,fixtures.replay()),('queue-completion',fixture,completed.replay())):
            module=w.MEMBERS[case]
            def capture(output,maven,profile,*,source_from):
                self.assertEqual(module.PROFILE,profile);shutil.copytree(original.path,output)
            with patch.object(w.tc,'capture',return_value=module.read(original.path/'toolchain.json')),patch.object(module,'capture',side_effect=capture) as execute:
                produced=w.execute(self.bundle,self.root/('executed-'+case),'mvn',case,self.ctx)
            self.assertEqual('PARTIAL',produced['status']);self.assertEqual(1,execute.call_count)
            with patch.object(module.gate,'qualify',return_value=replay) as physical:
                result=w.verify(self.bundle,self.root/('executed-'+case)/'artifact',self.root/('verified-'+case),case,self.ctx)
            self.assertEqual(1,physical.call_count);self.assertEqual('PARTIAL',result['status'])
            path=inputs/w.artifact_name(self.ctx,'verified',case);path.mkdir();w.h.save(path/'receipt.json',result)
        return inputs

    def test_both_producers_and_downloaded_readers_feed_only_partial_whole_set(self):
        inputs=self.all_members();value=w.aggregate(self.bundle,inputs,self.root/'aggregate',self.ctx,'success','success')
        self.assertEqual('PARTIAL',value['status']);self.assertEqual((2,18),(value['wholeHistories'],value['negativeCases']))
        self.assertTrue(value['declaredQueueOriginalsReplayed']);self.assertTrue(value['workflowStagesReportedSuccessful'])
        for key in ('phase3Complete','workflowExecutionAttested','combinedPeakResourcesQualified'):self.assertFalse(value[key])
        self.assertTrue(value['cases']['queue-completion']['member']['nativeFinalCompleted'])

    def test_all_stage_results_complete_cases_and_exact_negatives_are_mandatory(self):
        inputs=self.all_members()
        for i,(first,last) in enumerate((('failure','success'),('success','cancelled'),('skipped','success'),(None,'success'))):
            with self.assertRaisesRegex(ValueError,'failed or missing workflow stage'):
                w.aggregate(self.bundle,inputs,self.root/f'stage-{i}',self.ctx,first,last)
        path=inputs/w.artifact_name(self.ctx,'verified','queue-completion')/'receipt.json';original=w.read(path)
        other=w.read(inputs/w.artifact_name(self.ctx,'verified','source-queue')/'receipt.json')
        changes=[lambda v:v['context'].update(attempt='1'),lambda v:v.update(status='PASS'),lambda v:v.update(phase3Complete=True),
            lambda v:v.update(case='source-queue'),lambda v:v.update(seedArchiveSha256='e'*64),
            lambda v:v['member'].update(buildSha256='0'*64),lambda v:v['member'].update(nativeFinalCompleted=False),
            lambda v:v['member']['qualification']['negatives'].pop(),lambda v:v.update(rawArchiveSha256=other['rawArchiveSha256']),
            lambda v:v['member'].update(producerReceiptSha256=other['member']['producerReceiptSha256'])]
        for i,mutate in enumerate(changes):
            value=copy.deepcopy(original);mutate(value);w.h.save(path,value)
            with self.subTest(mutation=i),self.assertRaises(ValueError):
                w.aggregate(self.bundle,inputs,self.root/f'mutated-{i}',self.ctx,'success','success')
        w.h.save(path,original);path.unlink();path.parent.rmdir()
        with self.assertRaisesRegex(ValueError,'complete verified set'):
            w.aggregate(self.bundle,inputs,self.root/'missing',self.ctx,'success','success')

    def test_original_invalid_or_changed_during_downloaded_replay_is_not_counted(self):
        _,bundle=self.raw()
        def change(raw):
            (raw/'synthetic.bin').write_bytes(b'changed');return fixtures.replay()
        with patch.object(w.source.gate,'qualify',side_effect=change),self.assertRaisesRegex(ValueError,'original collection'):
            self.verify(bundle,'changed-during-replay')

    def test_previous_verifier_receipt_cannot_change_during_aggregate(self):
        inputs=self.all_members();path=inputs/w.artifact_name(self.ctx,'verified','source-queue')/'receipt.json'
        original=w.completion.check_result
        def change(value,profile):
            original(value,profile);path.write_text('{}')
        with patch.object(w.completion,'check_result',side_effect=change),self.assertRaisesRegex(ValueError,'verifier changed'):
            w.aggregate(self.bundle,inputs,self.root/'changed-aggregate',self.ctx,'success','success')


class QueueResourceWorkflowTest(unittest.TestCase):
    def test_manual_two_whole_histories_share_one_build_and_keep_failure_artifacts(self):
        text=(w.h.ROOT/w.WORKFLOW).read_text();jobs={n:b for n,b in re.findall(r'^  (prepare|execute|verify|aggregate):\n(.*?)(?=^  \w+:|\Z)',text,re.M|re.S)}
        self.assertEqual({'prepare','execute','verify','aggregate'},set(jobs));self.assertNotIn('branches:',text)
        event=text.split('\non:\n',1)[1].split('\npermissions:',1)[0]
        self.assertEqual({'workflow_dispatch'},set(re.findall(r'^  ([a-z_]+):',event,re.M)))
        self.assertEqual('  contents: read',text.split('permissions:\n',1)[1].split('\n\n',1)[0])
        self.assertNotRegex(text,r'secrets\.|id-token:|continue-on-error:|retry|replay-smoke|self-hosted|gse-v52')
        self.assertIn('cancel-in-progress: false',text)
        self.assertIn('needs: prepare',jobs['execute']);self.assertIn('needs: [prepare, execute]',jobs['verify'])
        self.assertIn('needs: [prepare, execute, verify]',jobs['aggregate'])
        self.assertEqual(1,text.count('queue_resource_hosted prepare'))
        for name in ('execute','verify'):
            self.assertIn('fail-fast: false',jobs[name]);self.assertIn('max-parallel: 2',jobs[name])
            self.assertIn('matrix: ${{ fromJSON(needs.prepare.outputs.matrix) }}',jobs[name])
            self.assertIn('QUEUE_RESOURCE_CASE: ${{ matrix.case }}',jobs[name])
            self.assertIn('--case "$QUEUE_RESOURCE_CASE"',jobs[name])
        self.assertIn('EXECUTE_RESULT: ${{ needs.execute.result }}',jobs['aggregate'])
        self.assertIn('VERIFY_RESULT: ${{ needs.verify.result }}',jobs['aggregate'])
        for name,body in jobs.items():
            self.assertIn('ref: ${{ github.sha }}',body);self.assertIn('persist-credentials: false',body)
            self.assertIn('if: ${{ always() }}',body);self.assertIn('retention-days: 90',body)
            self.assertIn('runs-on: ubuntu-24.04',body);self.assertIn('timeout-minutes: 360',body)
        for binding in re.findall(r'^          (?:name|pattern): (v53-queue-resources-.+)$',text,re.M):
            self.assertIn('${{ github.run_id }}-${{ github.run_attempt }}-${{ github.sha }}',binding)
        setup=(w.h.ROOT/'.github/actions/v53-process-setup/action.yml').read_text()
        for name in re.findall(r'uses: (\S+)',text+'\n'+setup):
            self.assertTrue(name.startswith('./') or re.fullmatch(r'[\w-]+/[\w-]+@[0-9a-f]{40}',name),name)
        self.assertIn("java-version: '21.0.12+8.0.LTS'",setup);self.assertIn("python-version: '3.11'",setup)

    def test_plan_is_fixed_to_both_originals_and_never_a_smoke(self):
        from contextlib import redirect_stdout
        output=io.StringIO()
        with patch.object(w,'context',return_value=dict()),patch('sys.argv',['hosted','plan']),redirect_stdout(output):w.main()
        self.assertEqual(dict(include=[dict(case=c,id=c) for c in w.HISTORIES]),json.loads(output.getvalue()))
        self.assertEqual(('source-queue','queue-completion'),w.HISTORIES)
        self.assertEqual('joint-queue-final-64mib',w.selected('queue-completion').PROFILE)
        for name in ('smoke','rehearsal','',True,None):
            with self.assertRaises(ValueError):w.selected(name)


if __name__=='__main__':unittest.main()
