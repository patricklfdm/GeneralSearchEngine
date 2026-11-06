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
from . import required_four_resource_hosted as w
from . import test_required_four_resource_run as fixtures


class RequiredFourResourceHostedTest(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.RequiredFourResourceRunTest();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root;self.ctx=dict(kind='synthetic',repository='patricklfdm/GeneralSearchEngine',source='a'*40,
            ref=w.BRANCH,event='push',run='7',attempt='2',workflow=w.WORKFLOW)
        self.data=self.root/'seed-data';self.data.mkdir();shutil.copytree(self.fixture.path,self.data/'producer')
        repo=self.data/'repository';repo.mkdir();(repo/'surefire.jar').write_bytes(b'original dependency')
        self.seed=dict(schema=w.SCHEMA,context=self.ctx,status='PARTIAL',profile=w.PROFILE,phase3Complete=False,
                       **self.fixture.pins,reader=self.fixture.reader,repositorySha256=w.shared.dependencies(repo))
        w.h.save(self.data/'seed.json',self.seed);self.bundle=self.root/'seed-bundle'
        self.manifest=w.pack(self.data,self.bundle,self.ctx,'seed')

    def raw(self):
        data=self.root/'raw-data';data.mkdir();shutil.copytree(self.fixture.path,data/'producer')
        original=w.m.member(data/'producer',w.PROFILE,w.pins(self.seed))
        claimed=dict(schema=w.SCHEMA,context=self.ctx,profile=w.PROFILE,status='PARTIAL',phase3Complete=False,
                     seedArchiveSha256=self.manifest['archiveSha256'],producerReceiptSha256=original['producerReceiptSha256'],**w.pins(self.seed))
        w.h.save(data/'hosted-member.json',claimed);bundle=self.root/'raw-bundle';w.pack(data,bundle,self.ctx,'raw');return data,bundle

    def verify(self,bundle,name='verify',result='success'):
        return w.verify(self.bundle,bundle,self.root/name,self.ctx,result)

    def test_seed_requires_exact_source_build_reader_tools_dependencies_and_profile(self):
        self.assertEqual(self.seed,w.seed_inputs(self.data,self.ctx))
        targets=['producer/workspace/scripts/v53/reader.py','producer/workspace/target/classes/original.class',
                 'producer/toolchain.json','repository/surefire.jar','seed.json']
        for i,target in enumerate(targets):
            data,_=w.unpack(self.bundle,self.root/f'bad-{i}',self.ctx,'seed');p=data/target
            if target=='seed.json':
                value=w.m.read(p);value['profile']='replay-smoke-1';w.h.save(p,value)
            else:p.write_bytes(b'changed')
            with self.subTest(target=target),self.assertRaises((ValueError,json.JSONDecodeError)):w.seed_inputs(data,self.ctx)

    def test_wrong_context_kind_profile_archive_bytes_and_extra_files_are_rejected(self):
        for i,field in enumerate(('attempt','source','run','workflow')):
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'binding'):
                w.unpack(self.bundle,self.root/f'ctx-{i}',dict(self.ctx,**{field:'wrong'}),'seed')
        with self.assertRaisesRegex(ValueError,'binding'):w.unpack(self.bundle,self.root/'kind',self.ctx,'raw')
        path=self.bundle/'manifest.json';value=w.m.read(path);value['case']='replay-smoke-1';w.h.save(path,value)
        with self.assertRaisesRegex(ValueError,'binding'):w.unpack(self.bundle,self.root/'profile',self.ctx,'seed')
        w.h.save(path,self.manifest)
        with (self.bundle/'bundle.tar.gz').open('ab') as stream:stream.write(b'changed')
        with self.assertRaisesRegex(ValueError,'digest'):w.unpack(self.bundle,self.root/'bytes',self.ctx,'seed')
        (self.bundle/'extra').write_text('extra')
        with self.assertRaisesRegex(ValueError,'artifact shape'):w.unpack(self.bundle,self.root/'shape',self.ctx,'seed')

    def test_explicit_archive_bound_does_not_change_existing_default(self):
        self.assertEqual(1024**3,w.shared.MAX_BYTES);self.assertEqual(1024**3,w.limit('raw'))
        root=self.root/'bounded';root.mkdir();(root/'a').write_bytes(b'a'*400);(root/'b').write_bytes(b'b'*400)
        bundle=self.root/'bounded-bundle';w.shared.pack(root,bundle,self.ctx,'raw',maximum=1000)
        w.shared.unpack(bundle,self.root/'roundtrip',self.ctx,'raw',maximum=1000)
        with self.assertRaisesRegex(ValueError,'archive capacity'):w.shared.unpack(bundle,self.root/'too-small',self.ctx,'raw',maximum=700)
        with self.assertRaisesRegex(ValueError,'byte capacity'):w.shared.pack(root,self.root/'small-pack',self.ctx,'raw',maximum=700)
        for i,value in enumerate((0,-1,True,None)):
            with self.assertRaisesRegex(ValueError,'explicit byte bound'):w.shared.pack(root,self.root/f'bound-{i}',self.ctx,'raw',maximum=value)
        with self.assertRaisesRegex(ValueError,'separation'):w.pack(root,root/'archive',self.ctx,'raw')

    def test_raw_archive_rejects_links_traversal_duplicates_and_large_files(self):
        for i,(name,kind,size) in enumerate([('../escape',tarfile.REGTYPE,1),('data/link',tarfile.SYMTYPE,0),
                ('data/hard',tarfile.LNKTYPE,0),('data/huge',tarfile.REGTYPE,256*1024*1024+1),('data/duplicate',tarfile.REGTYPE,1)]):
            bundle=self.root/f'hostile-{i}';bundle.mkdir();archive=bundle/'bundle.tar.gz'
            with tarfile.open(archive,'w:gz') as stream:
                item=tarfile.TarInfo(name);item.type=kind;item.size=size
                stream.addfile(item,io.BytesIO(b'x'*size) if size<1024 else None)
                if 'duplicate' in name:stream.addfile(item,io.BytesIO(b'x'))
            manifest=dict(self.manifest,kind='raw',archiveSha256=w.tc.file_hash(archive));w.h.save(bundle/'manifest.json',manifest)
            with self.subTest(name=name),self.assertRaises(ValueError):w.unpack(bundle,self.root/f'extract-{i}',self.ctx,'raw')
        self.assertFalse((self.root/'escape').exists())

    def test_execute_uses_one_full_profile_and_independent_seed_and_keeps_partial(self):
        def capture(output,maven,profile,**kw):
            self.assertEqual(w.PROFILE,profile);self.assertIn('/seed/data/producer',str(kw['source_from']))
            shutil.copytree(self.fixture.path,output)
        with patch.object(w.tc,'capture',return_value=w.m.read(self.data/'producer/toolchain.json')),patch.object(w.m,'capture',side_effect=capture) as call:
            value=w.execute(self.bundle,self.root/'execute','mvn',self.ctx)
        self.assertEqual(1,call.call_count);self.assertEqual('PARTIAL',value['status']);self.assertFalse(value['phase3Complete'])
        data,_=w.unpack(self.root/'execute/artifact',self.root/'downloaded',self.ctx,'raw')
        self.assertEqual(value,w.m.read(data/'hosted-member.json'));self.assertEqual(self.seed,w.seed_inputs(self.data,self.ctx))

    def test_execution_failure_is_retained_without_retry(self):
        with patch.object(w.tc,'capture',return_value=w.m.read(self.data/'producer/toolchain.json')),patch.object(w.m,'capture',side_effect=ValueError('original failure')) as call:
            with self.assertRaisesRegex(ValueError,'original failure'):w.execute(self.bundle,self.root/'execute','mvn',self.ctx)
        self.assertEqual(1,call.call_count)
        data,_=w.unpack(self.root/'execute/artifact',self.root/'downloaded',self.ctx,'raw')
        self.assertEqual('FAIL',w.m.read(data/'hosted-member.json')['status'])

    def test_failed_artifact_retention_preserves_original_error(self):
        with patch.object(w.tc,'capture',return_value=w.m.read(self.data/'producer/toolchain.json')),\
             patch.object(w.m,'capture',side_effect=ValueError('original failure')),patch.object(w,'pack',side_effect=OSError('disk full')):
            with self.assertRaisesRegex(ValueError,'original failure'):w.execute(self.bundle,self.root/'execute','mvn',self.ctx)
        result=w.m.read(self.root/'execute/receipt.json')
        self.assertEqual('original failure',result['failure']['message']);self.assertEqual('disk full',result['artifactFailure']['message'])

    def test_complete_downloaded_replay_qualifies_only_observed_ownership(self):
        _,bundle=self.raw()
        with patch.object(w.m.gate,'qualify',return_value=fixtures.replay()) as call:value=self.verify(bundle)
        self.assertEqual(1,call.call_count);self.assertIn('/verify/original/data/producer/',str(call.call_args.args[0]))
        self.assertEqual('PASS',value['status']);self.assertTrue(value['observedResourcesQualified'])
        self.assertFalse(value['combinedResourcesQualified']);self.assertFalse(value['phase3Complete'])
        self.assertEqual(147,sum(map(len,value['qualification']['qualification']['negatives'].values())))

    def test_wrong_stage_context_pins_profile_seed_and_producer_receipt_are_rejected(self):
        data,bundle=self.raw();path=data/'hosted-member.json';original=w.m.read(path)
        for i,result in enumerate(('failure','skipped','cancelled',None)):
            with self.assertRaisesRegex(ValueError,'execution job required'):self.verify(bundle,'state-'+str(i),result)
        changes=[lambda v:v['context'].update(attempt='3'),lambda v:v.update(status='PASS'),lambda v:v.update(profile='replay-smoke-1'),
                 lambda v:v.update(phase3Complete=True),lambda v:v.update(buildSha256='b'*64),lambda v:v.update(seedArchiveSha256='b'*64),
                 lambda v:v.update(producerReceiptSha256='b'*64)]
        for i,change in enumerate(changes):
            value=copy.deepcopy(original);change(value);w.h.save(path,value);shutil.rmtree(bundle);w.pack(data,bundle,self.ctx,'raw')
            with patch.object(w.m.gate,'qualify',return_value=fixtures.replay()),self.assertRaises(ValueError):self.verify(bundle,'bad-member-'+str(i))

    def test_failed_original_missing_negatives_and_smoke_cannot_qualify(self):
        _,bundle=self.raw()
        with patch.object(w.m.gate,'qualify',side_effect=ValueError('original invalid')):
            with self.assertRaisesRegex(ValueError,'original invalid'):self.verify(bundle,'original')
        for i,value in enumerate((dict(fixtures.replay(),profile='5-REPLACE'),dict(fixtures.replay(),negatives={}))):
            with patch.object(w.m.gate,'qualify',return_value=value),self.assertRaisesRegex(ValueError,'exact negative families|resources qualification scope'):
                self.verify(bundle,'incomplete-'+str(i))
        self.assertEqual('FAIL',w.m.read(self.root/'original/receipt.json')['status'])

    def test_context_and_failed_summary(self):
        env=dict(GITHUB_ACTIONS='true',GITHUB_REPOSITORY=self.ctx['repository'],GITHUB_SHA=self.ctx['source'],GITHUB_REF=w.BRANCH,
                 GITHUB_EVENT_NAME='push',GITHUB_RUN_ID='7',GITHUB_RUN_ATTEMPT='2',V53_WORKFLOW_SHA=self.ctx['source'],
                 V53_WORKFLOW_REF=self.ctx['repository']+'/'+w.WORKFLOW+'@'+w.BRANCH)
        with patch.dict(os.environ,env,clear=True),patch.object(w.shared.subprocess,'check_output',return_value=self.ctx['source']+'\n'):
            self.assertEqual(dict(self.ctx,kind='github'),w.context())
            for key,value in [('GITHUB_EVENT_NAME','pull_request'),('GITHUB_REF','refs/heads/master'),('V53_WORKFLOW_REF','other'),('GITHUB_RUN_ATTEMPT','0')]:
                with patch.dict(os.environ,{key:value}),self.assertRaises(ValueError):w.context()
        summary=self.root/'summary.md'
        with patch.object(w,'context',return_value=self.ctx),patch.object(w.tc,'locate',return_value='mvn'),\
             patch.object(w,'prepare',side_effect=ValueError('prepare failure')),patch.dict(os.environ,{'GITHUB_STEP_SUMMARY':str(summary)}),\
             patch('sys.argv',['hosted','prepare','--output',str(self.root/'unused')]):
            with self.assertRaisesRegex(ValueError,'prepare failure'):w.main()
        self.assertIn('| Status | `FAIL` |',summary.read_text())


class RequiredFourResourceWorkflowTest(unittest.TestCase):
    def test_opt_in_indivisible_three_job_pipeline_pins_artifacts_tools_and_failure_retention(self):
        text=(w.h.ROOT/w.WORKFLOW).read_text();jobs={n:b for n,b in re.findall(r'^  (prepare|execute|verify):\n(.*?)(?=^  \w+:|\Z)',text,re.M|re.S)}
        self.assertEqual({'prepare','execute','verify'},set(jobs));self.assertIn('branches: [experiment/v53-required-four-resources]',text)
        event=text.split('\non:\n',1)[1].split('\npermissions:',1)[0]
        self.assertEqual({'workflow_dispatch','push'},set(re.findall(r'^  ([a-z_]+):',event,re.M)))
        self.assertEqual('  contents: read',text.split('permissions:\n',1)[1].split('\n\n',1)[0])
        self.assertNotRegex(text,r'matrix:|secrets\.|id-token:|continue-on-error:|retry|replay-smoke')
        self.assertIn('cancel-in-progress: false',text);self.assertIn('needs: prepare',jobs['execute'])
        self.assertIn('needs: [prepare, execute]',jobs['verify']);self.assertIn('EXECUTE_RESULT: ${{ needs.execute.result }}',jobs['verify'])
        self.assertIn("needs.prepare.result == 'success'",jobs['verify'])
        for body in jobs.values():
            self.assertIn('runs-on: ubuntu-24.04',body);self.assertIn('ref: ${{ github.sha }}',body)
            self.assertIn('persist-credentials: false',body);self.assertIn('if: ${{ always() }}',body);self.assertIn('retention-days: 90',body)
        for binding in re.findall(r'^          name: (v53-required-four-resources-.+)$',text,re.M):
            self.assertIn('${{ github.run_id }}-${{ github.run_attempt }}-${{ github.sha }}',binding)
        setup=(w.h.ROOT/'.github/actions/v53-process-setup/action.yml').read_text()
        for name in re.findall(r'uses: (\S+)',text+'\n'+setup):
            self.assertTrue(name.startswith('./') or re.fullmatch(r'[\w-]+/[\w-]+@[0-9a-f]{40}',name),name)
        self.assertIn("java-version: '21.0.12+8.0.LTS'",setup);self.assertIn("python-version: '3.11'",setup)
