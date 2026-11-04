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
from . import automatic_history as m
from .test_process_toolchain import record


def raw_tree(raw,case):
    raw.mkdir(parents=True)
    if case=='reply-revocation':
        names=m.histories(case)
        m.h.save(raw/'receipt.json',dict(schema=m.replies.SCHEMA,status='PASS',publicRuntime=False,phase3Complete=False,
            cases=[dict(case=name,size=n,boundary=b,fault=f) for name,(n,b,f) in zip(names,m.replies.CASES)]))
        for name,(n,b,f) in zip(names,m.replies.CASES):
            source=raw/name/'source';source.mkdir(parents=True);(source/'original-plan.gsbp').write_bytes((case+name).encode())
            m.h.save(raw/name/'result.json',dict(size=n,boundary=b,fault=f,status='PASS'))
    else:
        (raw/'original-plan.gsbp').write_bytes(case.encode())
        if case=='competition':
            for name in ('failure.txt','close-failure.txt'):(raw/name).write_bytes(b'')
            m.h.save(raw/'result.json',dict(status='PARTIAL',producerPassed=True,nodes=3,automaticOwners=3,defaultBounds=True,physicalReplay=False,phase3Complete=False))
        else:
            m.h.save(raw/'restart-result.json',dict(status='PARTIAL',producerPassed=True,rounds=2,barriers=2,dataCalls=1,originalBudgetNanos=m.restart.BUDGET,physicalReplay=False,phase3Complete=False))
            (raw/'events.json').write_bytes(b'[]');side=m.sidecar(raw,case);side.mkdir()
            m.h.save(side/m.restart.CAPTURE,dict(schema=m.restart.SCHEMA,producerPassed=True,ownerDrained=True,captureFailure='',observationFailure='',
                eventsSha256=m.h.digest((raw/'events.json').read_bytes()),planSha256=m.h.digest((raw/'original-plan.gsbp').read_bytes())))
            (side/m.restart.OBSERVATIONS).write_bytes(b'[]')


def reports(work,case):
    cls,method,_=m.selected(case);cls=m.PACKAGE+cls;root=work/m.h.MODULE/'target/surefire-reports';root.mkdir(parents=True)
    suite=ET.Element('testsuite',dict(name=cls,tests='1',failures='0',errors='0',skipped='0'))
    ET.SubElement(suite,'testcase',dict(classname=cls,name=method));ET.ElementTree(suite).write(root/'TEST-original.xml')
    return root


from .test_automatic_history_replay import result as replay


class AutomaticHistoryTest(unittest.TestCase):
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
            baseHead='a'*40,readerSha256=self.reader['sha256'],command=['mvn',*m.command(case)],junit=jr,raw=raw.relative_to(path).as_posix(),captures=m.sidecar(raw,case).relative_to(path).as_posix() if m.sidecar(raw,case) else None,
            **{k+'Sha256':m.h.digest((path/f).read_bytes()) for k,f in [('source','source.json'),('build','build.json'),('toolchain','toolchain.json'),('collection','collection.json')]}))

    def raw(self,path=None):
        path=self.path if path is None else path;return path/m.read(path/'receipt.json')['raw']
    def receipt(self,**changes):
        v=m.read(self.path/'receipt.json');v.update(changes);m.h.save(self.path/'receipt.json',v)
    def member(self):return m.member(self.path,self.case,*self.pins)
    def aggregate(self,paths=None,**kwargs):
        with patch.object(m,'ProcessPoolExecutor',ThreadPoolExecutor):return m.aggregate(self.paths if paths is None else paths,*self.pins,**kwargs)

    def test_catalogue_uses_complete_native_methods_without_retry_or_case_filter(self):
        self.assertEqual((1,1,48),tuple(len(m.histories(k)) for k in m.CASES))
        for case,(cls,method,_) in m.METHODS.items():
            text=(m.h.ROOT/m.h.MODULE/('src/test/java/'+m.PACKAGE.replace('.','/')+cls+'.java')).read_text()
            self.assertIn('void '+method+'()',text)
            args=m.command(case);self.assertEqual(1,sum(v.startswith('-Dtest=') for v in args))
            self.assertFalse(any('retry' in v.lower() or 'timeout' in v.lower() or '.case=' in v for v in args))
        for value in ('other','',False):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'exact case'):m.command(value)

    def test_legacy_reply_capture_cannot_supply_new_resource_qualification(self):
        raw=self.raw(self.paths['reply-revocation']);receipt=m.read(raw/'receipt.json')
        receipt['schema']='gse-v53-transfer-reply-lifetime-v1';m.h.save(raw/'receipt.json',receipt)
        with self.assertRaisesRegex(ValueError,'automatic complete reply producer'):
            m.collect(raw,'reply-revocation')

    def test_collection_is_only_bounded_inventory_not_authority_replay(self):
        with patch.object(m,'replay') as validator:result=m.collect(self.raw(),self.case)
        validator.assert_not_called();self.assertEqual('PARTIAL',result['status']);self.assertFalse(result['nativeHistoryQualified'])

    def test_producer_failure_scope_and_missing_attachment_refuse(self):
        raw=self.raw();saved=(raw/'result.json').read_bytes();value=m.read(raw/'result.json');value['producerPassed']=False;m.h.save(raw/'result.json',value)
        with self.assertRaisesRegex(ValueError,'exact producer result'):m.collect(raw,self.case)
        (raw/'result.json').write_bytes(saved);(raw/'failure.txt').write_bytes(b'failed')
        with self.assertRaisesRegex(ValueError,'producer failure'):m.collect(raw,self.case)
        restart=self.raw(self.paths['higher-ballot-restart']);capture=m.sidecar(restart,'higher-ballot-restart')/m.restart.CAPTURE
        value=m.read(capture);value['eventsSha256']='f'*64;m.h.save(capture,value)
        with self.assertRaisesRegex(ValueError,'complete producer attachment'):m.collect(restart,'higher-ballot-restart')

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

    def test_missing_group_aliases_and_reused_bootstraps_refuse(self):
        with self.assertRaisesRegex(ValueError,'complete three histories'):self.aggregate({self.case:self.path})
        with self.assertRaisesRegex(ValueError,'distinct producers'):self.aggregate(dict.fromkeys(m.CASES,self.path))
        other=self.paths['reply-revocation'];raw=self.raw(other);source=raw/m.histories('reply-revocation')[0]/'source/original-plan.gsbp'
        source.write_bytes((self.raw()/'original-plan.gsbp').read_bytes());m.h.save(other/'collection.json',m.collect(raw,'reply-revocation'))
        value=m.read(other/'receipt.json');value['collectionSha256']=m.h.digest((other/'collection.json').read_bytes());m.h.save(other/'receipt.json',value)
        with self.assertRaisesRegex(ValueError,'distinct complete original'):self.aggregate()

    def test_complete_three_groups_replay_once_and_keep_scope(self):
        with patch.object(m,'replay',side_effect=lambda raw,case:replay(case)) as gate:result=self.aggregate(workers=3)
        self.assertEqual(3,gate.call_count);self.assertEqual('PASS',result['status']);self.assertEqual(50,result['wholeOwnershipHistories'])
        self.assertEqual(156,result['negativeCases']);self.assertEqual(3,result['executionGroups'])
        for key in ('phase3Complete','combinedPeakResourcesQualified','fullLifecycleQualified','completeExportLifetimesQualified'):
            self.assertIs(False,result[key])

    def test_failure_is_retained_and_other_groups_still_replayed(self):
        def gate(raw,case):
            if case=='competition':raise ValueError('original failed')
            return replay(case)
        with patch.object(m,'replay',side_effect=gate) as validator:result=self.aggregate(workers=3)
        self.assertEqual(3,validator.call_count);self.assertEqual('FAIL',result['status'])
        self.assertEqual('original failed',result['cases'][0]['failure']['message'])
        self.assertEqual(['FAIL','PASS','PASS'],[v['status'] for v in result['cases']])

    def test_mutation_during_replay_and_bad_workers_refuse(self):
        def changed(raw,case):(raw/'changed').write_bytes(b'bad');return replay(case)
        with patch.object(m,'replay',side_effect=changed),self.assertRaises(ValueError):m.qualify_member(self.path,self.case,*self.pins)
        for n in (False,0,4):
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
                self.assertEqual(['-B','-m','scripts.v53.automatic_history','collect'],args[1:5]);m.h.save(Path(args[5]),m.collect(Path(args[-1]),self.case))
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
