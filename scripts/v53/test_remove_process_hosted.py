"""Synthetic orchestration/portable metadata checks, never native qualification."""
import copy
import io
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import time
import unittest
from unittest.mock import patch
from . import remove_process_hosted as w
from . import test_remove_process_matrix as fixtures
from .test_process_toolchain import record


class HostedRemoveTest(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.RemoveProcessMatrixTest();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root;self.ctx=dict(kind='synthetic',repository='patricklfdm/GeneralSearchEngine',source='a'*40,
            ref=w.BRANCH,event='push',run='1',attempt='2',workflow=w.WORKFLOW)
        self.case=w.m.KINDS[0];self.portable(self.fixture.paths[self.case])
        self.fixture.pins[2]=w.tc.pin((self.fixture.paths[self.case]/'toolchain.json').read_bytes())
        self.data=self.root/'seed-data';self.data.mkdir()
        shutil.copytree(self.fixture.paths[self.case],self.data/'producer')
        repo=self.data/'repository';repo.mkdir();(repo/'surefire.jar').write_bytes(b'fixture dependency');(repo/'plugin.pom').write_bytes(b'pom')
        self.reader=dict(sha256='f'*64,files={})
        self.addCleanup(patch.stopall);patch.object(w.m,'reader_manifest',return_value=self.reader).start()
        self.seed=dict(schema=w.SCHEMA,context=self.ctx,status='PARTIAL',phase3Complete=False,cases=list(w.m.KINDS),
            **{k+'Sha256':v for k,v in zip(('source','build','toolchain','reader'),self.fixture.pins)},reader=self.reader,
            repositorySha256=w.dependencies(repo))
        w.h.save(self.data/'seed.json',self.seed);self.seed_bundle=self.root/'seed-bundle'
        self.seed_manifest=w.pack(self.data,self.seed_bundle,self.ctx,'seed')

    def portable(self,producer):
        w.h.save(producer/'toolchain.json',record());value=w.m.read(producer/'receipt.json')
        value['toolchainSha256']=w.h.digest((producer/'toolchain.json').read_bytes());w.h.save(producer/'receipt.json',value)

    def raw(self,case=None):
        case=case or self.case;data=self.root/('raw-'+w.m.slug(case));data.mkdir()
        self.fixture.producer(data/'producer',case);self.portable(data/'producer')
        original=w.m.member(data/'producer',case,*w.pins(self.seed)[:3])
        claimed=dict(schema=w.SCHEMA,context=self.ctx,case=case,status='PARTIAL',phase3Complete=False,
            seedArchiveSha256=self.seed_manifest['archiveSha256'],producerReceiptSha256=original['receiptSha256'],originalPlanSha256=original['plan'],
            **{k+'Sha256':v for k,v in zip(('source','build','toolchain','reader'),w.pins(self.seed))})
        w.h.save(data/'hosted-member.json',claimed);bundle=self.root/('bundle-'+w.m.slug(case));w.pack(data,bundle,self.ctx,'raw',case)
        return data,bundle

    def verifier_inputs(self):
        root=self.root/'verifiers';root.mkdir()
        for case in w.m.KINDS:
            member=dict(case=case,status='PASS',phase3Complete=False,qualification=fixtures.RemoveProcessMatrixTest.replay(None,workers=1),
                producerReceiptSha256=w.h.digest(case.encode()+b'receipt'),originalPlanSha256=w.h.digest(case.encode()+b'plan'),
                **{k+'Sha256':v for k,v in zip(('source','build','toolchain','reader'),w.pins(self.seed))})
            value=dict(schema=w.SCHEMA,context=self.ctx,case=case,status='PARTIAL',phase3Complete=False,
                seedArchiveSha256=self.seed_manifest['archiveSha256'],rawArchiveSha256=w.h.digest(case.encode()+b'raw'),
                originalFirstDownloadedReplay=True,member=member)
            directory=root/w.artifact_name(self.ctx,'verified',case);directory.mkdir();w.h.save(directory/'receipt.json',value)
        return root

    def test_seed_roundtrip_preserves_exact_source_classes_dependencies_and_reader(self):
        data,manifest=w.unpack(self.seed_bundle,self.root/'unpack',self.ctx,'seed')
        self.assertEqual(self.seed,w.seed_inputs(data,self.ctx));self.assertEqual(self.seed_manifest,manifest)
        (data/'repository/surefire.jar').write_bytes(b'drift')
        with self.assertRaisesRegex(ValueError,'dependencies'):w.seed_inputs(data,self.ctx)

    def test_seed_source_classes_tools_and_reader_drift_are_rejected(self):
        targets=['producer/workspace/original.java','producer/workspace/target/classes/original.class','producer/toolchain.json','seed.json']
        for i,target in enumerate(targets):
            with self.subTest(target=target):
                data,_=w.unpack(self.seed_bundle,self.root/f'mutated-{i}',self.ctx,'seed');path=data/target
                if target=='seed.json':
                    value=w.m.read(path);value['readerSha256']='d'*64;w.h.save(path,value)
                elif target.endswith('json'):w.h.save(path,dict(exit=0,stdout='different',stderr=''))
                else:path.write_bytes(b'drift')
                with self.assertRaises(ValueError):w.seed_inputs(data,self.ctx)

    def test_current_reader_must_also_match_original_source_bytes(self):
        value=w.m.read(self.data/'seed.json');value['reader']['files']={'original.java':'b'*64}
        w.h.save(self.data/'seed.json',value)
        with patch.object(w.m,'reader_manifest',return_value=value['reader']),self.assertRaisesRegex(ValueError,'recorded source'):
            w.seed_inputs(self.data,self.ctx)

    def test_failure_summary_cannot_show_a_pass(self):
        summary=self.root/'summary.md'
        with patch.object(w,'context',return_value=self.ctx),patch.object(w.tc,'locate',return_value='mvn'), \
             patch.object(w,'prepare',side_effect=ValueError('prepare failure')), \
             patch.dict(os.environ,{'GITHUB_STEP_SUMMARY':str(summary)}), \
             patch('sys.argv',['hosted','prepare','--output',str(self.root/'output')]):
            with self.assertRaisesRegex(ValueError,'prepare failure'):w.main()
        self.assertIn('| Status | `FAIL` |',summary.read_text())
        self.assertIn('| Phase 3 complete | `False` |',summary.read_text())

    def test_archive_binding_rejects_wrong_attempt_source_case_and_kind(self):
        for i,ctx in enumerate((dict(self.ctx,attempt='3'),dict(self.ctx,source='b'*40))):
            with self.assertRaisesRegex(ValueError,'binding'):w.unpack(self.seed_bundle,self.root/f'bad-{i}',ctx,'seed')
        with self.assertRaisesRegex(ValueError,'binding'):w.unpack(self.seed_bundle,self.root/'bad-kind',self.ctx,'raw',self.case)

    def test_archive_hash_and_inventory_drift(self):
        manifest=w.m.read(self.seed_bundle/'manifest.json');manifest['inventory']['files']['seed.json']='b'*64
        w.h.save(self.seed_bundle/'manifest.json',manifest)
        with self.assertRaisesRegex(ValueError,'inventory'):w.unpack(self.seed_bundle,self.root/'bad-inventory',self.ctx,'seed')
        with (self.seed_bundle/'bundle.tar.gz').open('ab') as stream:stream.write(b'trailing drift')
        with self.assertRaisesRegex(ValueError,'digest'):w.unpack(self.seed_bundle,self.root/'bad-digest',self.ctx,'seed')

    def test_archive_rejects_traversal_links_duplicates_and_oversized_headers(self):
        examples=[('../escape',tarfile.REGTYPE,1),('/data/escape',tarfile.REGTYPE,1),('data/../escape',tarfile.REGTYPE,1),
                  ('data/link',tarfile.SYMTYPE,0),('data/link',tarfile.LNKTYPE,0),('data/dev',tarfile.CHRTYPE,0),
                  ('data/huge',tarfile.REGTYPE,257*1024*1024),('data/duplicate',tarfile.REGTYPE,1)]
        for i,(name,kind,size) in enumerate(examples):
            with self.subTest(name=name,kind=kind):
                bundle=self.root/f'hostile-{i}';bundle.mkdir();archive=bundle/'bundle.tar.gz'
                with tarfile.open(archive,'w:gz') as stream:
                    item=tarfile.TarInfo(name);item.type=kind;item.size=size
                    if size>1024:stream.addfile(item)  # Header alone: reject before trying to read content.
                    else:
                        stream.addfile(item,io.BytesIO(b'x'*size))
                        if 'duplicate' in name:stream.addfile(item,io.BytesIO(b'x'*size))
                value=copy.deepcopy(self.seed_manifest);value['archiveSha256']=w.tc.file_hash(archive);w.h.save(bundle/'manifest.json',value)
                with self.assertRaises(ValueError):w.unpack(bundle,self.root/f'extract-{i}',self.ctx,'seed')
        self.assertFalse((self.root/'escape').exists())

    def test_repository_env_restores_original_even_after_failure(self):
        with patch.dict(os.environ,{'MAVEN_OPTS':'original'}):
            with self.assertRaises(RuntimeError):
                with w.repository_env(self.root/'repo'):
                    self.assertIn('-Dmaven.repo.local=',os.environ['MAVEN_OPTS']);raise RuntimeError('failure')
            self.assertEqual('original',os.environ['MAVEN_OPTS'])
        with self.assertRaises(ValueError):
            with w.repository_env(self.root/'with space'):pass

    def test_execution_failure_is_not_retried_and_retains_failed_raw(self):
        with patch.object(w.tc,'capture',return_value=w.m.read(self.data/'producer/toolchain.json')),\
             patch.object(w.m.run,'run',side_effect=ValueError('original failure')) as run:
            with self.assertRaisesRegex(ValueError,'original failure'):w.execute(self.seed_bundle,self.root/'execution','mvn',self.case,self.ctx)
        self.assertEqual(1,run.call_count);self.assertTrue(run.call_args.kwargs['portable_toolchain'])
        data,_=w.unpack(self.root/'execution/artifact',self.root/'failed-raw',self.ctx,'raw',self.case)
        self.assertEqual('FAIL',w.m.read(data/'hosted-member.json')['status'])

    def test_successful_execution_remains_partial_and_preserves_seed(self):
        def produce(output,maven,case,**kwargs):self.fixture.producer(output,case);self.portable(output)
        with patch.object(w.tc,'capture',return_value=w.m.read(self.data/'producer/toolchain.json')),patch.object(w.m.run,'run',side_effect=produce):
            result=w.execute(self.seed_bundle,self.root/'execution','mvn',self.case,self.ctx)
        self.assertEqual('PARTIAL',result['status']);self.assertFalse(result['phase3Complete'])
        self.assertEqual(self.seed,w.seed_inputs(self.data,self.ctx))

    def test_downloaded_original_is_replayed_and_inputs_cannot_change(self):
        _,bundle=self.raw()
        with patch.object(w.m.gate,'qualify',side_effect=fixtures.RemoveProcessMatrixTest.replay) as replay:
            result=w.verify(self.seed_bundle,bundle,self.root/'verify',self.case,self.ctx)
        self.assertEqual(1,replay.call_count);self.assertIn('/verify/original/data/',str(replay.call_args.args[0]))
        self.assertEqual('PARTIAL',result['status']);self.assertTrue(result['originalFirstDownloadedReplay'])
        self.assertEqual(18,len(result['member']['qualification']['negatives']))

    def test_failed_original_cannot_count_as_negative_success(self):
        _,bundle=self.raw()
        with patch.object(w.m.gate,'qualify',side_effect=ValueError('original physical failure')):
            with self.assertRaisesRegex(ValueError,'original physical failure'):w.verify(self.seed_bundle,bundle,self.root/'verify',self.case,self.ctx)
        self.assertEqual('FAIL',w.m.read(self.root/'verify/receipt.json')['status'])

    def test_mixed_source_claim_is_rejected_before_replay(self):
        data,bundle=self.raw();value=w.m.read(data/'hosted-member.json');value['sourceSha256']='b'*64;w.h.save(data/'hosted-member.json',value)
        shutil.rmtree(bundle);w.pack(data,bundle,self.ctx,'raw',self.case)
        with patch.object(w.m.gate,'qualify') as replay,self.assertRaisesRegex(ValueError,'member binding'):
            w.verify(self.seed_bundle,bundle,self.root/'verify',self.case,self.ctx)
        replay.assert_not_called()

    def test_complete_52_synthetic_receipts_remain_scoped_to_remove_matrix(self):
        result=w.aggregate(self.seed_bundle,self.verifier_inputs(),self.root/'aggregate',self.ctx,'success','success')
        self.assertEqual('PASS',result['status']);self.assertEqual(52,result['wholeHistories']);self.assertEqual(936,result['negativeCases'])
        self.assertFalse(result['phase3Complete']);self.assertFalse(result['allMembershipProfilesQualified'])

    def test_missing_extra_failed_jobs_and_partial_rerun_do_not_qualify(self):
        root=self.verifier_inputs();first=root/w.artifact_name(self.ctx,'verified',self.case)
        for index,(execute,verify) in enumerate((('failure','success'),('success','failure'),('cancelled','success'),('success','skipped'))):
            with self.assertRaisesRegex(ValueError,'workflow stage'):w.aggregate(self.seed_bundle,root,self.root/f'state-{index}',self.ctx,execute,verify)
        first.rename(root/'extra')
        with self.assertRaisesRegex(ValueError,'inventory'):w.aggregate(self.seed_bundle,root,self.root/'extra-result',self.ctx,'success','success')
        shutil.rmtree(root/'extra')
        with self.assertRaisesRegex(ValueError,'inventory'):w.aggregate(self.seed_bundle,root,self.root/'missing',self.ctx,'success','success')

    def test_aggregate_rejects_context_pins_negatives_and_reused_original(self):
        root=self.verifier_inputs();path=root/w.artifact_name(self.ctx,'verified',self.case)/'receipt.json';original=w.m.read(path)
        second=w.m.read(root/w.artifact_name(self.ctx,'verified',w.m.KINDS[1])/'receipt.json')
        changes=[lambda v:v['context'].update(attempt='1'),lambda v:v.update(status='FAIL'),lambda v:v.update(phase3Complete=True),
            lambda v:v.update(originalFirstDownloadedReplay=False),lambda v:v.update(seedArchiveSha256='c'*64),
            lambda v:v['member'].update(buildSha256='c'*64),lambda v:v['member']['qualification']['negatives'][0].update(reason='wrong'),
            lambda v:v['member'].update(originalPlanSha256=second['member']['originalPlanSha256']),
            lambda v:v.update(rawArchiveSha256=second['rawArchiveSha256'])]
        for index,change in enumerate(changes):
            with self.subTest(index=index):
                value=copy.deepcopy(original);change(value);w.h.save(path,value)
                with self.assertRaises(ValueError):w.aggregate(self.seed_bundle,root,self.root/f'bad-aggregate-{index}',self.ctx,'success','success')
        w.h.save(path,original)

    def test_context_rejects_unrelated_workflows_events_repos_and_checkout(self):
        env=dict(GITHUB_ACTIONS='true',GITHUB_REPOSITORY=self.ctx['repository'],GITHUB_SHA=self.ctx['source'],GITHUB_REF=w.BRANCH,
            GITHUB_EVENT_NAME='push',GITHUB_RUN_ID='1',GITHUB_RUN_ATTEMPT='2',V53_WORKFLOW_SHA=self.ctx['source'],
            V53_WORKFLOW_REF=self.ctx['repository']+'/'+w.WORKFLOW+'@'+w.BRANCH)
        with patch.dict(os.environ,env,clear=True),patch.object(w.subprocess,'check_output',return_value=self.ctx['source']+'\n'):
            self.assertEqual(dict(self.ctx,kind='github'),w.context())
            for key,value in [('GITHUB_EVENT_NAME','pull_request'),('GITHUB_REF','refs/heads/master'),('GITHUB_REPOSITORY','elsewhere/repo'),
                              ('GITHUB_RUN_ATTEMPT','0'),('V53_WORKFLOW_SHA','b'*40),('V53_WORKFLOW_REF','other')]:
                with patch.dict(os.environ,{key:value}),self.assertRaises(ValueError):w.context()
            with patch.dict(os.environ,{'GITHUB_EVENT_NAME':'workflow_dispatch'}):self.assertEqual('workflow_dispatch',w.context()['event'])
        with patch.dict(os.environ,env,clear=True),patch.object(w.subprocess,'check_output',return_value='b'*40),self.assertRaises(ValueError):w.context()

    def test_progress_reports_and_stops_without_waiting_for_interval(self):
        with patch('builtins.print') as output:
            with w.progress('test',self.case,interval=0.01):time.sleep(0.05)
        self.assertGreater(output.call_count,0);self.assertEqual('test',json.loads(output.call_args.args[0])['stage'])
