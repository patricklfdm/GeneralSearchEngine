"""Synthetic orchestration guards, not native transport acceptance evidence."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import copy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from . import transfer_history as m
from .test_process_toolchain import record


def raw_tree(raw,case):
    raw.mkdir(parents=True);m.h.save(raw/'receipt.json',m.fixture(case))
    for name in m.histories(case):
        home=raw/name;source=home if case=='tcp-lifetimes' else home/'history'
        source.mkdir(parents=True);(source/'original-plan.gsbp').write_bytes((case+'/'+name).encode())
        if case=='tcp-lifetimes':
            for name in m.faults.CASES:
                directory=home/'cases'/name;directory.mkdir(parents=True)
                m.h.save(directory/'result.json',dict(case=name,status='PASS'))


def reports(work,case):
    cls,method,_=m.selected(case);cls=m.PACKAGE+cls;root=work/m.h.MODULE/'target/surefire-reports';root.mkdir(parents=True)
    suite=ET.Element('testsuite',dict(name=cls,tests='1',failures='0',errors='0',skipped='0'))
    ET.SubElement(suite,'testcase',dict(classname=cls,name=method));ET.ElementTree(suite).write(root/'TEST-original.xml')
    return root


def replay(case):
    if case=='tcp-lifetimes':
        original=dict(status='PASS',scope='original-public-bootstrap-TCP-transfer-faults',profiles=[dict(size=n,cases=[dict(case=k) for k in m.faults.CASES]) for n in (3,4,5)],
            cases=27,faultInjectionClock='explicit-offset; not measured elapsed time',resourceCounts='source-bound observations',
            processDeathQualified=False,allMembershipProfilesQualified=False,phase3Complete=False)
    else:
        original=dict(status='PASS',scope='original-donor-TCP-halt-SIGKILL-reopen',cases=[dict(profile=v,status='PASS',originalSourcePreserved=True) for v in m.process.PROFILES],
            processes=36,interruptedReplies=18,transferProcessQualified=True,allMembershipProfilesQualified=False,
            completePhysicalQualified=False,forceAndNetworkQualified=False,phase3Complete=False,powerLossQualified=False)
    return dict(original=original,originalPreserved=True,negatives=[dict(case=k,status='REJECTED',reason=v) for k,v in m.READERS[case].NEGATIVES])


class TransferHistoryTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.reader=dict(files={'scripts/v53/reader.py':m.h.digest(b'synthetic reader')},sha256='f'*64)
        self.stack=ExitStack();self.addCleanup(self.stack.close);self.stack.enter_context(patch.object(m,'reader_manifest',return_value=self.reader))
        self.paths={k:self.root/k for k in m.CASES}
        for case,path in self.paths.items():self.producer(path,case)
        self.case=m.CASES[0];self.path=self.paths[self.case]
        self.pins=[m.h.digest((self.path/name).read_bytes()) for name in ('source.json','build.json')]+[m.tc.pin((self.path/'toolchain.json').read_bytes()),self.reader['sha256']]

    def producer(self,path,case):
        work=path/'workspace';(work/'scripts/v53').mkdir(parents=True);(work/'scripts/v53/reader.py').write_bytes(b'synthetic reader')
        m.h.save(path/'source.json',dict(head='a'*40,files=self.reader['files']))
        for name in m.BUILDS:
            directory=work/name;directory.mkdir(parents=True);(directory/'original.class').write_bytes(b'synthetic classes')
        m.h.save(path/'build.json',{name:m.h.inventory(work/name) for name in m.BUILDS});m.h.save(path/'toolchain.json',record())
        jr=m.junit(reports(work,case),case);raw=work/m.h.MODULE/('target/'+m.selected(case)[2]+'/run-00000000-0000-0000-0000-000000000001')
        raw_tree(raw,case);m.h.save(path/'collection.json',m.collect(raw,case))
        for name in ('execution','collection-execution'):m.h.save(path/(name+'.json'),dict(exit=0))
        m.h.save(path/'receipt.json',dict(schema=m.SCHEMA,status='PARTIAL',executionStatus='PASS',case=case,collectionComplete=True,
            nativeHistoryQualified=False,phase3Complete=False,retries=0,execution=dict(exit=0),collectionExecution=dict(exit=0),
            baseHead='a'*40,readerSha256=self.reader['sha256'],command=['mvn',*m.command(case)],junit=jr,raw=raw.relative_to(path).as_posix(),
            **{k+'Sha256':m.h.digest((path/f).read_bytes()) for k,f in [('source','source.json'),('build','build.json'),('toolchain','toolchain.json'),('collection','collection.json')]}))

    def raw(self,path=None):
        path=self.path if path is None else path;return path/m.read(path/'receipt.json')['raw']
    def receipt(self,**changes):
        v=m.read(self.path/'receipt.json');v.update(changes);m.h.save(self.path/'receipt.json',v)
    def member(self):return m.member(self.path,self.case,*self.pins)
    def aggregate(self,paths=None,**kwargs):
        with patch.object(m,'ProcessPoolExecutor',ThreadPoolExecutor):return m.aggregate(self.paths if paths is None else paths,*self.pins,**kwargs)

    def test_catalogue_uses_complete_native_methods_without_retry_or_case_filter(self):
        self.assertEqual((3,18),tuple(len(m.histories(k)) for k in m.CASES))
        for case,(cls,method,_) in m.METHODS.items():
            text=(m.h.ROOT/m.h.MODULE/('src/test/java/'+m.PACKAGE.replace('.','/')+cls+'.java')).read_text()
            self.assertIn('void '+method+'()',text)
            args=m.command(case);self.assertEqual(1,sum(v.startswith('-Dtest=') for v in args))
            self.assertFalse(any('retry' in v.lower() or 'timeout' in v.lower() or '.case=' in v for v in args))
        for value in ('other','',False):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'exact case'):m.command(value)

    def test_collection_is_only_bounded_inventory_not_authority_replay(self):
        with patch.object(m.faults,'validate') as validator:result=m.collect(self.raw(),self.case)
        validator.assert_not_called();self.assertEqual('PARTIAL',result['status']);self.assertFalse(result['nativeHistoryQualified'])

    def test_missing_profile_case_failed_scope_and_extra_files_reject(self):
        raw=self.raw();saved=(raw/'receipt.json').read_bytes();v=m.read(raw/'receipt.json');v['phase3Complete']=True;m.h.save(raw/'receipt.json',v)
        with self.assertRaisesRegex(ValueError,'producer fixture'):m.collect(raw,self.case)
        (raw/'receipt.json').write_bytes(saved);case=raw/'stable-3/cases/lost-offer/result.json';m.h.save(case,dict(case='lost-offer',status='FAIL'))
        with self.assertRaisesRegex(ValueError,'failed service case'):m.collect(raw,self.case)
        m.h.save(case,dict(case='lost-offer',status='PASS'));(raw/'stable-3/cases/extra').mkdir()
        with self.assertRaisesRegex(ValueError,'continuous service cases'):m.collect(raw,self.case)
        (raw/'extra').mkdir()
        with self.assertRaisesRegex(ValueError,'complete original directories'):m.collect(raw,self.case)

    def test_relocation_preserves_exact_provenance(self):
        original=self.member();dest=self.root/'relocated';shutil.copytree(self.path,dest);got=m.member(dest,self.case,*self.pins)
        self.assertEqual({k:v for k,v in original.items() if k!='raw'},{k:v for k,v in got.items() if k!='raw'})

    def test_source_classes_reader_and_tool_drift_refuse(self):
        for name,reason in [('workspace/scripts/v53/reader.py','recorded source changed'),('workspace/target/classes/original.class','original compiled bytes')]:
            path=self.path/name;before=path.read_bytes();path.write_bytes(b'changed')
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,reason):self.member()
            path.write_bytes(before)
        self.receipt(readerSha256='0'*64)
        with self.assertRaisesRegex(ValueError,'reader belongs'):self.member()
        self.receipt(readerSha256=self.reader['sha256']);value=m.read(self.path/'toolchain.json');value['identity']['binaries']['java/lib/modules']='b'*64
        m.h.save(self.path/'toolchain.json',value);self.receipt(toolchainSha256=m.h.digest((self.path/'toolchain.json').read_bytes()))
        with self.assertRaisesRegex(ValueError,'portable toolchain'):self.member()

    def test_host_diagnostics_do_not_change_portable_tool_identity(self):
        m.h.save(self.path/'toolchain.json',record('/other-host','another-kernel'));self.receipt(toolchainSha256=m.h.digest((self.path/'toolchain.json').read_bytes()));self.member()

    def test_failed_retried_overclaimed_or_changed_commands_cannot_admit(self):
        before=(self.path/'receipt.json').read_bytes()
        for value in [dict(status='PASS'),dict(executionStatus='FAIL'),dict(retries=True),dict(retries=1),dict(nativeHistoryQualified=True),
                      dict(command=['mvn',*m.command(self.case),'-Dv53.transfer.process.case=3-CHUNK-kill']),dict(raw='../foreign')]:
            self.receipt(**value)
            with self.subTest(value=value),self.assertRaises(ValueError):self.member()
            (self.path/'receipt.json').write_bytes(before)

    def test_execution_and_junit_receipts_require_original_nonboolean_counts(self):
        self.receipt(collectionExecution=dict(exit=True))
        with self.assertRaisesRegex(ValueError,'successful process receipts'):self.member()
        self.receipt(collectionExecution=dict(exit=0));value=m.read(self.path/'receipt.json')['junit'];value['tests']=True;self.receipt(junit=value)
        with self.assertRaisesRegex(ValueError,'JUnit receipt'):self.member()

    def test_extra_or_retried_junit_reports_refuse(self):
        directory=self.path/'workspace'/m.h.MODULE/'target/surefire-reports';path=directory/'TEST-original.xml';tree=ET.parse(path)
        ET.SubElement(tree.getroot().find('testcase'),'flakyFailure');tree.write(path)
        with self.assertRaisesRegex(ValueError,'unretried passing'):self.member()
        (directory/'TEST-another.xml').write_bytes(path.read_bytes())
        with self.assertRaisesRegex(ValueError,'exact JUnit report'):self.member()

    def test_linked_originals_and_extra_runs_refuse(self):
        raw=self.raw();(raw/'link').symlink_to('receipt.json')
        with self.assertRaisesRegex(ValueError,'linked member'):self.member()
        (raw/'link').unlink();(raw.parent/'extra-run').mkdir()
        with self.assertRaisesRegex(ValueError,'exactly one original'):self.member()

    def test_missing_pair_aliases_and_reused_bootstraps_refuse(self):
        with self.assertRaisesRegex(ValueError,'complete matrix pair'):self.aggregate({self.case:self.path})
        with self.assertRaisesRegex(ValueError,'distinct producers'):self.aggregate(dict.fromkeys(m.CASES,self.path))
        other=self.paths['process-recovery'];raw=self.raw(other);source=raw/(m.histories('process-recovery')[0]+'/history/original-plan.gsbp')
        source.write_bytes((self.raw()/'stable-3/original-plan.gsbp').read_bytes());m.h.save(other/'collection.json',m.collect(raw,'process-recovery'))
        value=m.read(other/'receipt.json');value['collectionSha256']=m.h.digest((other/'collection.json').read_bytes());m.h.save(other/'receipt.json',value)
        with self.assertRaisesRegex(ValueError,'distinct complete original'):self.aggregate()

    def test_complete_pair_replays_originals_once_and_preserves_scope(self):
        with patch.object(m.faults,'qualify',return_value=replay('tcp-lifetimes')) as first,patch.object(m.process,'qualify',return_value=replay('process-recovery')) as second:
            result=self.aggregate(workers=2)
        first.assert_called_once();second.assert_called_once();self.assertEqual('PASS',result['status'])
        self.assertEqual(45,result['nativeCases']);self.assertEqual(21,result['wholeOwnershipHistories'])
        self.assertEqual(sum(len(v.NEGATIVES) for v in m.READERS.values()),result['negativeCases'])
        for key in ('phase3Complete','combinedPeakResourcesQualified','autonomousCompetitionQualified','completePhysicalQualified','powerLossQualified'):
            self.assertIs(False,result[key])

    def test_failure_is_retained_while_other_original_still_checked(self):
        with patch.object(m.faults,'qualify',side_effect=ValueError('original failed')) as first,patch.object(m.process,'qualify',return_value=replay('process-recovery')) as second:
            result=self.aggregate(workers=2)
        first.assert_called_once();second.assert_called_once();self.assertEqual('FAIL',result['status'])
        self.assertEqual('original failed',result['cases'][0]['failure']['message']);self.assertEqual('PASS',result['cases'][1]['status'])

    def test_missing_negatives_profiles_or_inflated_scope_never_pass(self):
        for case in m.CASES:
            changes=[lambda v:v['negatives'].pop(),lambda v:v['negatives'][0].update(reason='other'),lambda v:v.update(originalPreserved=False),
                     lambda v:v['original'].update(phase3Complete=True),lambda v:v['original'].update(allMembershipProfilesQualified=True)]
            changes.append(lambda v:v['original']['profiles' if case=='tcp-lifetimes' else 'cases'].pop())
            for change in changes:
                value=replay(case);change(value)
                with self.subTest(case=case),self.assertRaises(ValueError):m.check_result(value,case)

    def test_mutation_during_replay_and_bad_workers_refuse(self):
        def changed(raw):(raw/'changed').write_bytes(b'bad');return replay(self.case)
        with patch.object(m.faults,'qualify',side_effect=changed),self.assertRaises(ValueError):m.qualify_member(self.path,self.case,*self.pins)
        for n in (False,0,3):
            with self.assertRaisesRegex(ValueError,'replay workers'):self.aggregate(workers=n)

    def test_capture_uses_frozen_collector_one_command_and_preserves_source(self):
        output=self.root/'capture';commands=[]
        def execute(args,work,log,**kwargs):
            commands.append(args);log.write_text('synthetic capture\n')
            if args[0]=='mvn':
                for name in m.BUILDS:
                    p=work/name;p.mkdir(parents=True);(p/'original.class').write_bytes(b'synthetic classes')
                reports(work,self.case);raw_tree(work/m.h.MODULE/('target/'+m.selected(self.case)[2]+'/run-00000000-0000-0000-0000-000000000002'),self.case)
            else:
                self.assertEqual(['-B','-m','scripts.v53.transfer_history','collect'],args[1:5]);m.h.save(Path(args[5]),m.collect(Path(args[-1]),self.case))
            return dict(exit=0)
        with patch.object(m.tc,'capture',return_value=record()),patch.object(m.h,'execute',side_effect=execute):result=m.capture(output,'mvn',self.case,self.path)
        self.assertEqual(2,len(commands));self.assertEqual('PARTIAL',result['status']);self.assertFalse(result['nativeHistoryQualified'])
        m.member(output,self.case,*self.pins)

    def test_capture_failure_retains_partial_files_without_retry(self):
        output=self.root/'failure'
        def fail(args,work,log,**kwargs):log.write_text('failure\n');(work/'retained-failure').write_bytes(b'original');return dict(exit=1)
        with patch.object(m.tc,'capture',return_value=record()),patch.object(m.h,'execute',side_effect=fail) as execute:
            with self.assertRaisesRegex(ValueError,'Maven failed'):m.capture(output,'mvn',self.case,self.path)
        execute.assert_called_once();self.assertEqual('FAIL',m.read(output/'receipt.json')['status']);self.assertTrue((output/'workspace/retained-failure').is_file())
        with self.assertRaises(FileExistsError):m.capture(output,'mvn',self.case,self.path)

    def test_missing_reader_is_rejected_before_native_execution(self):
        self.reader['files']['missing.py']='a'*64
        with patch.object(m.h,'execute') as execute:
            with self.assertRaisesRegex(ValueError,'reader belongs to source'):m.capture(self.root/'old','mvn',self.case,self.path)
        execute.assert_not_called()


if __name__=='__main__':unittest.main()
