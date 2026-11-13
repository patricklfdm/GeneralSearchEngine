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
from . import carried_transition_history as m
from .test_process_toolchain import record


def raw_tree(raw,case):
    if case in m.refusal.CASES:
        from .test_native_application_refusal_capture_history import raw_tree as native
        return native(raw,case)
    if case in m.application.CASES:
        from .test_native_carried_application_capture_history import raw_tree as native
        return native(raw,case)
    if case in m.process.CASES:
        from .test_native_carried_capture_history import raw_tree as native
        return native(raw,case)
    from . import test_remove_retirement_prefixes as fixtures
    raw.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=raw.parent) as temp:
        original,captures,_=fixtures.RemoveRetirementPrefixesTest().fixture(Path(temp))
        shutil.move(original,raw);shutil.move(captures,m.sidecar(raw))
    (raw/'transition-round-result.json').unlink();(raw/'original-plan.gsbp').write_bytes(case.encode())
    index,count,_=m.physical.shape(m.phase(case));entry=b'synthetic entry'
    (raw/f'entry-{index}.gsr').write_bytes(entry)
    result=dict(status='PASS',kind=m.phase(case),oldIndex=index,oldEntry=m.h.digest(entry),activations=count,
                internalReady=True,publicReady=False,originalBudgetSeconds=600)
    m.h.save(raw/'carried-transition-result.json',result)
    path=m.sidecar(raw)/'collection.json';header=m.read(path);header.update(schema=m.prefixes.SCHEMA,profile=m.phase(case),
        resultSha256=m.h.digest((raw/'carried-transition-result.json').read_bytes()));path.write_bytes(m.prefixes.f.canonical(header))


def reports(work,case):
    cls,method,_=m.selected(case);cls=m.PACKAGE+cls;root=work/m.h.MODULE/'target/surefire-reports';root.mkdir(parents=True)
    suite=ET.Element('testsuite',dict(name=cls,tests='1',failures='0',errors='0',skipped='0'))
    ET.SubElement(suite,'testcase',dict(classname=cls,name=method));ET.ElementTree(suite).write(root/'TEST-original.xml')
    return root


def replay(case):
    if case in m.refusal.CASES:
        from .test_native_application_refusal_capture_history import replay as native
        return native(case)
    if case in m.application.CASES:
        from .test_native_carried_application_capture_history import replay as native
        return native(case)
    if case in m.process.CASES:
        from .test_native_carried_capture_history import replay as native
        return native(case)
    kind=m.phase(case);index,count,_=m.physical.shape(kind)
    base=dict(kind=kind,status='PARTIAL',phase3Complete=False,publicReady=False,processDeathQualified=False)
    physical=dict(base,status='PASS',physicalQualified=True,publicationBoundaryQualified=True,internalReady=True,
                  originalEntryPreserved=True,activations=count,publishedSlots=list(range(index,8)),oldEntry='a'*64)
    network=dict(base,physical=physical,observedAttemptsQualified=True,durableActivationAndSlotACKsQualified=True)
    exports=dict(base,precondition=network,observedExportAuthorityQualified=True,completeCopyFloorLifetimesQualified=True)
    retention=dict(base,precondition=exports,retentionRevisionCompositionQualified=True)
    retirement=dict(base,precondition=retention,profile=kind,generations=1,sources=1,borrowedGenerations=1,generationMembers=1,
        callbacks=2,physicalImagePeak=7,transactionChainSha256='b'*64,peerPrecondition={},completeObservedRetirementCallbacksQualified=True,
        transientRetirementBytesQualified=False)
    original=dict(retirement,precondition=retirement,transientRetirementBytesQualified=True,capturedPrefixes=2,sourceCohortQualified=False)
    return dict(original=original,originalPreserved=True,negatives=m.negative_cases(case))


class CarriedTransitionHistoryTest(unittest.TestCase):
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
            baseHead='a'*40,readerSha256=self.reader['sha256'],command=['mvn',*m.command(case)],junit=jr,raw=raw.relative_to(path).as_posix(),captures=m.capture_path(raw,case,path),
            **{k+'Sha256':m.h.digest((path/f).read_bytes()) for k,f in [('source','source.json'),('build','build.json'),('toolchain','toolchain.json'),('collection','collection.json')]}))

    def raw(self,path=None):
        path=self.path if path is None else path;return path/m.read(path/'receipt.json')['raw']
    def receipt(self,**changes):
        v=m.read(self.path/'receipt.json');v.update(changes);m.h.save(self.path/'receipt.json',v)
    def member(self):return m.member(self.path,self.case,*self.pins)
    def aggregate(self,paths=None,**kwargs):
        with patch.object(m,'ProcessPoolExecutor',ThreadPoolExecutor):return m.aggregate(self.paths if paths is None else paths,*self.pins,**kwargs)

    def test_catalogue_uses_complete_native_methods_without_retry_or_case_filter(self):
        self.assertEqual(16,len(m.CASES));self.assertEqual((1,)*16,tuple(len(m.histories(k)) for k in m.CASES))
        for case,(cls,method,_) in m.METHODS.items():
            text=(m.h.ROOT/m.h.MODULE/('src/test/java/'+m.PACKAGE.replace('.','/')+cls+'.java')).read_text()
            self.assertIn('void '+method+'()',text)
            args=m.command(case);self.assertEqual(1,sum(v.startswith('-Dtest=') for v in args))
            self.assertEqual(m.adapter(case) is None,'-Dv53.transport.connections=true' in args)
            self.assertFalse(any('retry' in v.lower() or 'timeout' in v.lower() or '.case=' in v for v in args))
        for value in ('other','',False):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'exact case'):m.command(value)

    def test_collection_is_only_bounded_inventory_not_authority_replay(self):
        with patch.object(m,'replay') as validator:result=m.collect(self.raw(),self.case)
        validator.assert_not_called();self.assertEqual('PARTIAL',result['status']);self.assertFalse(result['nativeHistoryQualified'])

    def test_wrong_carried_result_and_cross_kind_or_ordinary_collection_reject(self):
        raw=self.raw();path=raw/'carried-transition-result.json';before=path.read_bytes()
        for changes in (dict(kind='FINAL'),dict(activations=True),dict(internalReady=False),dict(publicReady=True)):
            value=m.read(path);value.update(changes);m.h.save(path,value)
            with self.assertRaisesRegex(ValueError,'producer scope'):m.collect(raw,self.case)
            path.write_bytes(before)
        m.h.save(raw/'transition-round-result.json',{})
        with self.assertRaisesRegex(ValueError,'unexpected ordinary result'):m.collect(raw,self.case)


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
        with self.assertRaisesRegex(ValueError,'complete declared histories'):self.aggregate({self.case:self.path})
        with self.assertRaisesRegex(ValueError,'distinct producers'):self.aggregate(dict.fromkeys(m.CASES,self.path))
        other=self.paths['final'];raw=self.raw(other);source=raw/'original-plan.gsbp'
        source.write_bytes((self.raw()/'original-plan.gsbp').read_bytes());m.h.save(other/'collection.json',m.collect(raw,'final'))
        value=m.read(other/'receipt.json');value['collectionSha256']=m.h.digest((other/'collection.json').read_bytes());m.h.save(other/'receipt.json',value)
        with self.assertRaisesRegex(ValueError,'distinct complete original'):self.aggregate()

    def test_complete_two_histories_replay_once_and_preserve_scope(self):
        with patch.object(m,'replay',side_effect=lambda raw,case:replay(case)) as reader:result=self.aggregate(workers=4)
        self.assertEqual(16,reader.call_count);self.assertEqual('PASS',result['status'])
        self.assertEqual(16,result['nativeCases']);self.assertEqual(16,result['wholeOwnershipHistories']);self.assertEqual(3922,result['negativeCases'])
        for key in ('phase3Complete','combinedPeakResourcesQualified','autonomousCompetitionQualified','completePhysicalQualified','powerLossQualified','processDeathQualified'):
            self.assertIs(False,result[key])

    def test_failure_is_retained_while_other_originals_still_checked(self):
        def failed(raw,case):
            if case==self.case:raise ValueError('original failed')
            return replay(case)
        with patch.object(m,'replay',side_effect=failed) as reader:result=self.aggregate(workers=4)
        self.assertEqual(16,reader.call_count);self.assertEqual('FAIL',result['status'])
        self.assertEqual('original failed',result['cases'][0]['failure']['message']);self.assertTrue(all(v['status']=='PASS' for v in result['cases'][1:]))

    def test_missing_negatives_stages_or_inflated_scope_never_pass(self):
        for case in ('intent','final'):
            changes=[lambda v:v['negatives'].pop(),lambda v:v['negatives'][0].update(reason='other'),lambda v:v.update(originalPreserved=False),
                     lambda v:v['original'].update(phase3Complete=True),lambda v:v['original'].update(allMembershipProfilesQualified=True),
                     lambda v:v['original'].update(capturedPrefixes=True),lambda v:v['original'].update(capturedPrefixes=3),
                     lambda v:v['original'].update(kind='BARRIER'),lambda v:v['original'].update(physicalImagePeak=8),
                     lambda v:v['original'].update(sourceCohortQualified=True),lambda v:v['original'].update(transientRetirementBytesQualified=False),
                     lambda v:v['original'].update(precondition={})]
            for change in changes:
                value=replay(case);change(value)
                with self.subTest(case=case),self.assertRaises(ValueError):m.check_result(value,case)
            for stage in m.STAGES:
                value=replay(case);m.original_chain(value['original'])[stage]['phase3Complete']=True
                with self.subTest(stage=stage),self.assertRaises(ValueError):m.check_result(value,case)


    def test_mutation_during_replay_and_bad_workers_refuse(self):
        def changed(raw,case):(raw/'changed').write_bytes(b'bad');return replay(self.case)
        with patch.object(m,'replay',side_effect=changed),self.assertRaises(ValueError):m.qualify_member(self.path,self.case,*self.pins)
        for n in (False,0,5):
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
                self.assertEqual(['-B','-m','scripts.v53.carried_transition_history','collect'],args[1:5]);m.h.save(Path(args[5]),m.collect(Path(args[-1]),self.case))
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

    def test_process_capture_uses_the_same_frozen_collector_and_provenance_gate(self):
        self.case='final-proof-kill'
        self.test_capture_uses_frozen_collector_one_command_and_preserves_source()

    def test_all_application_axes_use_the_frozen_collector_and_exact_source_gate(self):
        for case in (*m.application.CASES,*m.refusal.CASES):
            self.case=case
            with self.subTest(case=case):
                self.test_capture_uses_frozen_collector_one_command_and_preserves_source()
            # Each test producer is independent; preserve it before the next case.
            (self.root/'capture').rename(self.root/('capture-'+case))

    def test_previous_fourteen_histories_cannot_form_a_v5_cohort(self):
        old={k:v for k,v in self.paths.items() if k not in m.refusal.CASES}
        self.assertEqual(14,len(old))
        with self.assertRaisesRegex(ValueError,'complete declared histories'):self.aggregate(old)

    def test_old_catalogue_schemas_cannot_satisfy_the_expanded_catalogue(self):
        for version in (1,2,3,4):
            self.receipt(schema=f'gse-v53-carried-transition-history-execution-v{version}')
            with self.assertRaisesRegex(ValueError,'successful unretried producer'):self.member()

    def test_native_member_rejects_external_sidecar_and_mixed_axes(self):
        self.case='final-proof-kill';self.path=self.paths[self.case]
        self.member();self.receipt(captures='external-sidecar')
        with self.assertRaisesRegex(ValueError,'exact captures path'):self.member()
        self.receipt(captures=None)
        path=self.raw()/m.process.OBSERVED/'history/process/result.json'
        value=m.read(path);value['mode']='halt';m.h.save(path,value)
        with self.assertRaisesRegex(ValueError,'producer scope'):self.member()

    def test_complete_original_failure_stops_before_any_negative(self):
        with patch.object(m.prefixes,'validate',side_effect=ValueError('bad original')) as original,patch.object(m.physical,'qualify') as negatives:
            with self.assertRaisesRegex(ValueError,'bad original'):m.replay(self.raw(),self.case)
        original.assert_called_once();negatives.assert_not_called()

    def test_sidecar_drift_missing_and_alias_are_not_recoverable_from_callbacks(self):
        raw=self.raw();sidecar=m.sidecar(raw);path=sidecar/'collection.json';before=path.read_bytes();value=m.read(path)
        path.write_bytes(m.prefixes.f.canonical(dict(value,profile='FINAL')))
        with self.assertRaisesRegex(ValueError,'collection header'):self.member()
        path.write_bytes(before);other=self.root/'captured';sidecar.rename(other);sidecar.symlink_to(other,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'collection root'):self.member()
        sidecar.unlink();other.rename(sidecar);self.receipt(captures='somewhere-else')
        with self.assertRaisesRegex(ValueError,'exact captures path'):self.member()

    def test_missing_reader_is_rejected_before_native_execution(self):
        self.reader['files']['missing.py']='a'*64
        with patch.object(m.h,'execute') as execute:
            with self.assertRaisesRegex(ValueError,'reader belongs to source'):m.capture(self.root/'old','mvn',self.case,self.path)
        execute.assert_not_called()

    def test_all_six_actual_reader_interfaces_are_composed_without_dropping_guards(self):
        original=replay(self.case);chain=m.original_chain(original['original']);order=[]
        with ExitStack() as stack:
            first=stack.enter_context(patch.object(m.prefixes,'validate',return_value=copy.deepcopy(original['original'])))
            for stage,reader in zip(m.STAGES,(m.physical,m.network,m.exports,m.retention,m.retirement,m.prefixes)):
                def qualify(*args,stage=stage):
                    self.assertEqual(1,first.call_count);order.append(stage)
                    self.assertEqual((self.raw(),m.sidecar(self.raw()),'INTENT') if stage=='prefixes' else (self.raw(),'INTENT'),args)
                    negatives=[{k:v for k,v in row.items() if k!='suite'} for row in original['negatives'] if row['suite']==stage]
                    return dict(original=copy.deepcopy(chain[stage]),negatives=negatives)
                stack.enter_context(patch.object(reader,'qualify',side_effect=qualify))
            got=m.replay(self.raw(),self.case)
        self.assertEqual(list(m.STAGES),order);self.assertEqual(original,got);self.assertEqual(305,len(got['negatives']))

    def test_different_stage_original_cannot_borrow_a_passing_prefix(self):
        original=replay(self.case)
        with patch.object(m.prefixes,'validate',return_value=original['original']),patch.object(m.physical,'qualify',return_value=dict(original={},negatives=[])),patch.object(m.network,'qualify') as later:
            with self.assertRaisesRegex(ValueError,'original stage drift: physical'):m.replay(self.raw(),self.case)
        later.assert_not_called()

    def test_prefix_sidecar_changes_during_replay_are_detected(self):
        def changed(raw,case):
            (m.sidecar(raw)/'changed').write_bytes(b'not original');return replay(case)
        with patch.object(m,'replay',side_effect=changed),self.assertRaises(ValueError):
            m.qualify_member(self.path,self.case,*self.pins)


if __name__=='__main__':unittest.main()
