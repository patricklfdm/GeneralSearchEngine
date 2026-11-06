"""Real archive/owning-seed readers over synthetic bytes; no JVM qualification."""
from contextlib import ExitStack
import copy
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from . import phase3_seed_cohort as c
from .test_process_toolchain import record


class Phase3SeedCohortTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.inputs = self.root/'inputs'; self.inputs.mkdir()
        self.modules = c.adapters(); self.count = 0; self.source_sha = 'a'*40
        self.source_files = {'scripts/v53/fixture.py': b'synthetic reader',
                             'docs/v5x/v5.3/fixture.json': b'synthetic profile contract',
                             'implementation.java': b'synthetic implementation'}
        self.source = dict(head=self.source_sha, files={k:c.h.digest(v) for k,v in self.source_files.items()})
        self.index = dict(schema=c.INDEX_SCHEMA, source=self.source_sha, cohorts={})
        self.data = {}; self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(c, 'checkout_source', return_value=self.source))
        # Every owner uses its actual seed reader and archive implementation.
        # Only the reader manifest is a fixture, with deliberately different sets.
        for i,(name,adapter) in enumerate(self.modules.items()):
            ctx = dict(kind='github', repository='patricklfdm/GeneralSearchEngine', source=self.source_sha,
                       ref=adapter.BRANCH, event='push', workflow=adapter.WORKFLOW, run=str(100+i), attempt='2')
            self.index['cohorts'][name] = ctx
            data = self.root/('data-'+name); data.mkdir(); self.data[name] = data
            producer = data/'producer'; work = producer/'workspace'; work.mkdir(parents=True)
            for filename,raw in self.source_files.items():
                path=work/filename; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(raw)
            c.h.save(producer/'source.json', self.source)
            for filename in c.shared.m.BUILDS:
                path = work/filename; path.mkdir(parents=True); (path/'test.class').write_bytes(b'synthetic class')
            reports=work/c.h.MODULE/'target/surefire-reports';reports.mkdir()
            cls='io.github.patricklfdm.generalsearch.replication.V53BallotAllocatorTest'
            suite=ET.Element('testsuite',dict(name=cls,tests='1',failures='0',errors='0',skipped='0'))
            ET.SubElement(suite,'testcase',dict(classname=cls,name='syntheticTest'))
            ET.ElementTree(suite).write(reports/'TEST-original.xml')
            c.h.save(producer/'build.json', {k:c.h.inventory(work/k) for k in c.shared.m.BUILDS})
            c.h.save(producer/'toolchain.json', record('/host-'+name, 'kernel-'+name))
            repo=data/'repository';repo.mkdir();(repo/'surefire.jar').write_bytes(b'synthetic jar')
            (repo/'dependency.pom').write_bytes(b'synthetic pom')
            files = {'scripts/v53/fixture.py': self.source['files']['scripts/v53/fixture.py']}
            if name in ('profiles','joining-reply-loss'):
                files['docs/v5x/v5.3/fixture.json'] = self.source['files']['docs/v5x/v5.3/fixture.json']
            reader = dict(files=files,sha256=c.h.digest(c.canonical(files)))
            self.stack.enter_context(patch.object(adapter.m,'reader_manifest',return_value=reader))
            field='profiles' if name=='profiles' else 'cases'
            cases=list(adapter.m.PROFILES if name=='profiles' else getattr(adapter.m,'KINDS',getattr(adapter.m,'CASES',())))
            seed = dict(schema=adapter.SCHEMA,context=ctx,status='PARTIAL',phase3Complete=False,
                        reader=reader,readerSha256=reader['sha256'],preparationExecution=dict(exit=0,elapsedSeconds=1),**{field:cases})
            if name=='joining-process':seed['groups']={k:list(v) for k,v in adapter.SHARDS.items()}
            c.h.save(data/'seed.json',seed);self.refresh(name)
        self.index_path=self.root/'index.json';c.h.save(self.index_path,self.index)

    def refresh(self,name):
        """A self-consistent independent preparation, not just a broken hash."""
        data=self.data[name];producer=data/'producer';seed=c.read(data/'seed.json')
        c.h.save(producer/'build.json',{k:c.h.inventory(producer/'workspace'/k) for k in c.shared.m.BUILDS})
        seed.update(sourceSha256=c.h.digest((producer/'source.json').read_bytes()),
                    buildSha256=c.h.digest((producer/'build.json').read_bytes()),
                    toolchainSha256=c.shared.tc.pin((producer/'toolchain.json').read_bytes()),
                    repositorySha256=c.shared.dependencies(data/'repository'))
        c.h.save(data/'seed.json',seed)
        bundle=self.inputs/name
        if bundle.exists():
            (bundle/'manifest.json').unlink();(bundle/'bundle.tar.gz').unlink();bundle.rmdir()
        self.modules[name].pack(data,bundle,self.index['cohorts'][name],'seed')

    def run_gate(self):
        self.count+=1;self.output=self.root/f'audit-{self.count}'
        return c.run(self.index_path,self.inputs,self.output)

    def refused(self,reason):
        with self.assertRaisesRegex(ValueError,reason):self.run_gate()
        receipt=c.read(self.output/'receipt.json')
        self.assertEqual('FAIL',receipt['status']);self.assertFalse(receipt['seedCohortVerified'])
        self.assertFalse(receipt['phase3Complete']);self.assertFalse(receipt['runtimeQualified'])

    def test_all_twelve_real_seed_readers_accept_different_archives_and_reader_sets(self):
        before={n:c.bundle_identity(self.inputs/n) for n in self.modules}
        result=self.run_gate()
        self.assertEqual(('PARTIAL',12,554,0),tuple(result[k] for k in ('status','subsets','plannedHostedHistories','historiesReplayed')))
        self.assertTrue(result['seedCohortVerified']);self.assertFalse(result['workflowExecutionAttested'])
        self.assertFalse(result['runtimeQualified']);self.assertFalse(result['phase3Complete'])
        self.assertEqual(12,len({v['archiveSha256'] for v in result['seeds'].values()}))
        self.assertEqual(2,len({v['readerSha256'] for v in result['seeds'].values()}))
        self.assertEqual(before,{n:c.bundle_identity(self.inputs/n) for n in self.modules})
        self.assertFalse(any(p.name.startswith('unpack-') for p in self.output.iterdir()))
        self.assertTrue((self.output/'profiles/build.json').is_file())

    def test_missing_subset_and_extra_artifact_refuse(self):
        bad=copy.deepcopy(self.index);bad['cohorts'].pop('profiles');c.h.save(self.index_path,bad)
        self.refused('complete subset');c.h.save(self.index_path,self.index)
        (self.inputs/'unexpected').mkdir();self.refused('complete artifact')

    def test_wrong_or_synthetic_context_and_duplicate_runs_refuse(self):
        variants=[('kind','synthetic'),('source','b'*40),('workflow','other.yml'),('attempt',True),
                  ('attempt','0'),('run',self.index['cohorts']['profiles']['run']),('event','pull_request'),
                  ('ref','refs/heads/master'),('unexpected','field')]
        for key,value in variants:
            with self.subTest(key=key,value=value):
                bad=copy.deepcopy(self.index);bad['cohorts']['node-renames'][key]=value
                c.h.save(self.index_path,bad);self.refused('seed cohort')

    def test_dispatch_ref_allowed_but_attempt_must_match_original_archive(self):
        bad=copy.deepcopy(self.index);ctx=bad['cohorts']['profiles']
        ctx.update(event='workflow_dispatch',ref='refs/heads/feat/audit',attempt='3')
        c.validate_index(bad,self.modules);c.h.save(self.index_path,bad)
        self.refused('exact artifact binding')

    def test_same_head_with_self_consistent_changed_or_omitted_source_is_rejected(self):
        for mode in ('changed','missing'):
            name='node-renames';data=self.data[name];source=copy.deepcopy(self.source)
            if mode=='changed':
                (data/'producer/workspace/implementation.java').write_bytes(b'different source')
                source['files']['implementation.java']=c.h.digest(b'different source')
            else:source['files'].pop('implementation.java')
            c.h.save(data/'producer/source.json',source);self.refresh(name)
            self.refused('incomplete/different Git source')

    def test_self_consistent_different_compiled_bytes_refuse(self):
        name='node-renames'
        (self.data[name]/'producer/workspace/target/classes/test.class').write_bytes(b'different compiled source')
        self.refresh(name);self.refused('mixed source/build/tools/dependencies')

    def test_self_consistent_different_tools_refuse(self):
        name='node-renames';value=record();value['identity']['binaries']['java/lib/modules']='b'*64
        c.h.save(self.data[name]/'producer/toolchain.json',value);self.refresh(name)
        self.refused('mixed source/build/tools/dependencies')

    def test_self_consistent_different_dependency_refuses(self):
        name='node-renames';(self.data[name]/'repository/surefire.jar').write_bytes(b'other dependency')
        self.refresh(name);self.refused('mixed source/build/tools/dependencies')

    def test_preparation_failure_or_forged_phase_completion_refuses(self):
        for field,value in (('status','FAIL'),('phase3Complete',True)):
            name='profiles';path=self.data[name]/'seed.json';seed=c.read(path);old=seed[field]
            seed[field]=value;c.h.save(path,seed);self.refresh(name);self.refused('seed scope')
            seed[field]=old;c.h.save(path,seed)

    def test_failed_preparation_and_hidden_test_rerun_cannot_be_relabelled(self):
        name='profiles';path=self.data[name]/'seed.json';seed=c.read(path)
        seed['preparationExecution']['exit']=1;c.h.save(path,seed);self.refresh(name)
        self.refused('preparation execution');seed['preparationExecution']['exit']=0;c.h.save(path,seed)
        report=self.data[name]/'producer/workspace'/c.h.MODULE/'target/surefire-reports/TEST-original.xml'
        suite=ET.parse(report);ET.SubElement(suite.getroot().find('testcase'),'flakyFailure')
        suite.write(report);self.refresh(name);self.refused('preparation unretried test')

    def test_wrong_reader_digest_refuses_at_owning_reader(self):
        name='profiles';path=self.data[name]/'seed.json';seed=c.read(path);seed['readerSha256']='f'*64
        c.h.save(path,seed);self.refresh(name);self.refused('profile matrix pinned reader')

    def test_legacy_version_text_cannot_replace_actual_tool_identity(self):
        name='profiles';c.h.save(self.data[name]/'producer/toolchain.json',dict(exit=0,stdout='claimed tools',stderr=''))
        self.refresh(name);self.refused('process toolchain record')

    def test_duplicate_json_and_linked_archives_refuse(self):
        original=self.index_path.read_bytes();self.index_path.write_bytes(original.replace(b'"source":',b'"source":"bad","source":',1))
        self.refused('duplicate key');self.index_path.write_bytes(original)
        archive=self.inputs/'profiles/bundle.tar.gz';saved=self.root/'original.gz';archive.rename(saved);archive.symlink_to(saved)
        self.refused('linked path')

    def test_drift_of_an_already_inspected_input_is_not_accepted(self):
        inspect=c.inspect_seed
        def mutate(name,*args):
            result=inspect(name,*args)
            if name=='joint-floor-process':
                path=self.inputs/'profiles/manifest.json';path.write_bytes(path.read_bytes()+b'\n')
            return result
        with patch.object(c,'inspect_seed',side_effect=mutate):self.refused('input changed after inspection')

    def test_index_changes_and_late_extra_artifact_refuse(self):
        inspect=c.inspect_seed
        for kind in ('index','artifact'):
            def mutate(name,*args):
                result=inspect(name,*args)
                if name=='joint-floor-process':
                    if kind=='index':self.index_path.write_bytes(self.index_path.read_bytes()+b'\n')
                    else:(self.inputs/'late').mkdir()
                return result
            with patch.object(c,'inspect_seed',side_effect=mutate):self.refused('seed cohort (index/checkout|changed artifact)')

    def test_no_existing_output_overwrite_and_no_input_overlap(self):
        output=self.root/'existing';output.mkdir();(output/'keep').write_text('original')
        with self.assertRaises(FileExistsError):c.run(self.index_path,self.inputs,output)
        self.assertEqual('original',(output/'keep').read_text())
        with self.assertRaisesRegex(ValueError,'overlaps'):c.run(self.index_path,self.inputs,self.inputs/'output')
        with self.assertRaisesRegex(ValueError,'parent traversal'):
            c.run(self.index_path,self.inputs,self.inputs/'missing/../output')


class SeedCheckoutSourceTest(unittest.TestCase):
    def test_git_blobs_match_complete_clean_checkout_and_dirty_or_wrong_head_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def git(*args):return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL)
            git('init');(root/'empty').write_bytes(b'');(root/'binary').write_bytes(b'\x00\x01\nbytes')
            (root/'nested dir').mkdir();(root/'nested dir/a.txt').write_text('example')
            git('add','.');git('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','fixture')
            source=git('rev-parse','HEAD').decode().strip()
            with patch.object(c,'ROOT',root):
                value=c.checkout_source(source)
                self.assertEqual({'empty':c.h.digest(b''),'binary':c.h.digest(b'\x00\x01\nbytes'),
                                  'nested dir/a.txt':c.h.digest(b'example')},value['files'])
                with self.assertRaisesRegex(ValueError,'reader checkout'):c.checkout_source('b'*40)
                (root/'binary').write_bytes(b'drift')
                with self.assertRaisesRegex(ValueError,'dirty checkout'):c.checkout_source(source)


if __name__=='__main__':unittest.main()
