"""Synthetic provenance/orchestration checks, never native qualification."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import copy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from . import process_joint_cohort as m
from .test_process_toolchain import record


def replay(case):
    ordinal,_,_=m.process.selected(case)
    flags=dict(status='PARTIAL',phase3Complete=False,processDeathQualified=False)
    physical=dict(prefix=dict(flags,status='PASS',profile='5-REPLACE',throughIntentPhysicalQualified=True),
        continuation=dict(flags,profile='5-REPLACE',finalCut=11),governingFloors=1,sourceRetirementPrefixes=1,sourceRetirementTransactions=1)
    recovery=dict(flags,sameScratchRecoveryChecked=True,liveWriterResourcesQualified=False,discardedFiles=4-ordinal)
    focused=dict(flags,case=case,nativeHistoryQualified=False,processBoundaryChecked=True,interruptedBytesChecked=True,
                 scratchRetained=True,scratchRecovery=recovery)
    ledgers={name:dict(status='PASS',phase3Complete=False,chainSha256='a'*64,**{flag:True}) for name,flag in
        [('peers','peerLedgerCompositionQualified'),('learner','learnerLedgerCompositionQualified'),
         ('future','futureLedgerCompositionQualified'),('ballot','ballotForceQualified')]}
    original=dict(flags,case=case,precondition=focused,physical=physical,network=dict(slots=11,committedTransfers=3,transferSessions=4,rejectedTransferAttempts=1),
        exports=dict(flags),controls=dict(flags,status='PASS',observedControlExportsQualified=True,observedLearnerRetentionQualified=True,
        observedCommittedContents=3,observedContentSessions=3),maintenance=dict(flags,status='PASS',maintenanceForceQualified=True),ledgers=ledgers,
        wholePhysicalNetworkLedgerReplayChecked=True,
        outstanding=['expanded-process-negative-matrix','remaining-transfer-publication-resources','final-source-process-matrix'])
    return dict(original=original,negatives=m.negative_cases(case),originalPreserved=True)


class ProcessJointCohortTest(unittest.TestCase):
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
        m.h.save(path/'source.json',dict(head='a'*40,files=self.reader['files']));m.h.save(path/'reader.json',self.reader)
        for name in m.BUILDS:
            directory=work/name;directory.mkdir(parents=True);(directory/'original.class').write_bytes(b'synthetic classes')
        m.h.save(path/'build.json',{name:m.h.inventory(work/name) for name in m.BUILDS});m.h.save(path/'toolchain.json',record())
        reports=work/m.h.MODULE/'target/surefire-reports';reports.mkdir(parents=True)
        suite=ET.Element('testsuite',dict(name=m.process.CLASS,tests='1',failures='0',errors='0',skipped='0'))
        ET.SubElement(suite,'testcase',dict(classname=m.process.CLASS,name=m.process.METHOD));ET.ElementTree(suite).write(reports/'TEST-original.xml')
        raw=work/m.h.MODULE/'target/v53-native-dispatch/run-00000000-0000-0000-0000-000000000001'
        side=raw/'joint-floor-recovery';side.mkdir(parents=True)
        for name in m.process.floor.FILES|{'process','scratch-recovery'}:
            if name.endswith(('.json','.gsr')):(side/name).write_bytes(b'{}')
            else:(side/name).mkdir()
        m.h.save(side/'receipt.json',m.process.scope(case,scratch_recovery=True))
        (raw/'source-retirement-captures').mkdir();(raw/'original-plan.gsbp').write_bytes(case.encode())
        m.h.save(path/'collection.json',m.process.collect(raw,case))
        for name in ('execution','collection-execution'):m.h.save(path/(name+'.json'),dict(exit=0))
        m.h.save(path/'receipt.json',dict(schema=m.process.EXECUTION_SCHEMA,status='PARTIAL',executionStatus='PASS',case=case,collectionComplete=True,
            nativeHistoryQualified=False,processDeathQualified=False,phase3Complete=False,retries=0,execution=dict(exit=0),collectionExecution=dict(exit=0),
            baseHead='a'*40,readerSha256=self.reader['sha256'],command=['mvn',*m.process.command(case)],junit=m.process.junit(reports),
            raw=raw.relative_to(path).as_posix(),captures=(raw/'source-retirement-captures').relative_to(path).as_posix(),
            **{k+'Sha256':m.h.digest((path/f).read_bytes()) for k,f in [('source','source.json'),('build','build.json'),('toolchain','toolchain.json'),('collection','collection.json')]}))

    def raw(self,path=None):
        path=self.path if path is None else path;return path/m.read(path/'receipt.json')['raw']
    def receipt(self,**changes):
        v=m.read(self.path/'receipt.json');v.update(changes);m.h.save(self.path/'receipt.json',v)
    def member(self):return m.member(self.path,self.case,*self.pins)
    def aggregate(self,paths=None,**kwargs):
        with patch.object(m,'ProcessPoolExecutor',ThreadPoolExecutor):return m.aggregate(self.paths if paths is None else paths,*self.pins,**kwargs)

    def test_exact_32_cut_matrix_and_predeclared_1544_negative_results(self):
        self.assertEqual(32,len(set(m.CASES)));self.assertEqual(1544,sum(len(m.negative_cases(k)) for k in m.CASES))
        for case in m.CASES:
            ordinal,cut,mode=m.process.selected(case);self.assertIn(mode,('halt','kill'));self.assertIn(cut,m.process.floor.PARTIAL_CUTS)
            self.assertEqual(46 if ordinal==4 else 49,len(m.negative_cases(case)));m.check_result(replay(case),case)
            args=m.process.command(case);self.assertEqual('-Dv53.native.process.joint='+case,args[-2])
            self.assertFalse(any('retry' in v.lower() for v in args))

    def test_portable_member_keeps_exact_source_build_and_original(self):
        original=self.member();dest=self.root/'relocated';shutil.copytree(self.path,dest);got=m.member(dest,self.case,*self.pins)
        self.assertEqual({k:v for k,v in original.items() if k!='raw'},{k:v for k,v in got.items() if k!='raw'})

    def test_source_compiled_bytes_reader_and_portable_tools_cannot_drift(self):
        for name,reason in [('workspace/scripts/v53/reader.py','recorded source changed'),('workspace/target/classes/original.class','original compiled bytes')]:
            path=self.path/name;before=path.read_bytes();path.write_bytes(b'changed')
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,reason):self.member()
            path.write_bytes(before)
        self.receipt(readerSha256='0'*64)
        with self.assertRaisesRegex(ValueError,'reader belongs'):self.member()
        self.receipt(readerSha256=self.reader['sha256']);value=m.read(self.path/'toolchain.json');value['identity']['binaries']['java/lib/modules']='b'*64
        m.h.save(self.path/'toolchain.json',value);self.receipt(toolchainSha256=m.h.digest((self.path/'toolchain.json').read_bytes()))
        with self.assertRaisesRegex(ValueError,'portable toolchain'):self.member()

    def test_portable_host_metadata_is_not_binary_identity(self):
        m.h.save(self.path/'toolchain.json',record('/other-host','another-kernel'));self.receipt(toolchainSha256=m.h.digest((self.path/'toolchain.json').read_bytes()));self.member()

    def test_partial_failed_retried_or_overclaimed_producers_and_extra_args_refuse(self):
        before=(self.path/'receipt.json').read_bytes()
        for change in [dict(status='PASS'),dict(executionStatus='FAIL'),dict(collectionComplete=False),dict(retries=True),dict(retries=1),
                       dict(nativeHistoryQualified=True),dict(processDeathQualified=True),dict(phase3Complete=True),
                       dict(command=['mvn',*m.process.command(self.case),'-Dtest=other']),dict(raw='../foreign'),dict(captures='../other'),
                       dict(execution=dict(exit=True)),dict(collectionExecution=dict(exit=1))]:
            self.receipt(**change)
            with self.subTest(change=change),self.assertRaises(ValueError):self.member()
            (self.path/'receipt.json').write_bytes(before)

    def test_legacy_v1_cannot_enter_new_cohort(self):
        raw=self.raw();m.h.save(raw/'joint-floor-recovery/receipt.json',m.process.scope(self.case));(raw/'joint-floor-recovery/scratch-recovery').rmdir()
        with self.assertRaisesRegex(ValueError,'requires v2'):self.member()

    def test_junit_extra_retry_and_boolean_receipt_refuse(self):
        directory=self.path/'workspace'/m.h.MODULE/'target/surefire-reports';path=directory/'TEST-original.xml'
        value=m.read(self.path/'receipt.json')['junit'];value['tests']=True;self.receipt(junit=value)
        with self.assertRaisesRegex(ValueError,'JUnit receipt'):self.member()
        self.receipt(junit=m.process.junit(directory));tree=ET.parse(path);ET.SubElement(tree.getroot().find('testcase'),'flakyFailure');tree.write(path)
        with self.assertRaisesRegex(ValueError,'unretried passing'):self.member()
        (directory/'TEST-another.xml').write_bytes(path.read_bytes())
        with self.assertRaisesRegex(ValueError,'exact JUnit report'):self.member()

    def test_symlink_extra_original_and_changed_collection_refuse(self):
        raw=self.raw();(raw/'link').symlink_to('original-plan.gsbp')
        with self.assertRaisesRegex(ValueError,'linked member'):self.member()
        (raw/'link').unlink();(raw.parent/'extra').mkdir()
        with self.assertRaisesRegex(ValueError,'exactly one original'):self.member()
        (raw.parent/'extra').rmdir();(raw/'original-plan.gsbp').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'original collection'):self.member()

    def test_missing_alias_and_duplicated_original_plan_cannot_fill_matrix(self):
        with self.assertRaisesRegex(ValueError,'complete 32'):self.aggregate({self.case:self.path})
        with self.assertRaisesRegex(ValueError,'distinct producers'):self.aggregate(dict.fromkeys(m.CASES,self.path))
        other=self.paths[m.CASES[1]];raw=self.raw(other);(raw/'original-plan.gsbp').write_bytes((self.raw()/'original-plan.gsbp').read_bytes())
        m.h.save(other/'collection.json',m.process.collect(raw,m.CASES[1]));value=m.read(other/'receipt.json')
        value['collectionSha256']=m.h.digest((other/'collection.json').read_bytes());m.h.save(other/'receipt.json',value)
        with self.assertRaisesRegex(ValueError,'distinct original histories'):self.aggregate()

    def test_complete_matrix_replays_once_and_failed_case_does_not_stop_other_validation(self):
        for failed in (None,self.case):
            def result(raw,case):
                if case==failed:raise ValueError('original failed')
                return replay(case)
            with patch.object(m,'replay',side_effect=result) as reader:got=self.aggregate(workers=4)
            self.assertEqual(32,reader.call_count);self.assertEqual('FAIL' if failed else 'PASS',got['status'])
            self.assertEqual(32,got['nativeCases']);self.assertEqual(1495 if failed else 1544,got['negativeCases'])
            self.assertEqual(failed is None,got['declaredJointFloorProcessHistoriesQualified'])
            for key in ('phase3Complete','processDeathQualified','combinedPeakResourcesQualified','allMembershipProfilesQualified','powerLossQualified'):
                self.assertIs(False,got[key])
            if failed:self.assertEqual('original failed',got['cases'][0]['failure']['message'])

    def test_pruned_or_relabelled_negatives_missing_layers_and_scope_inflation_refuse(self):
        edits=[lambda v:v['negatives'].pop(),lambda v:v['negatives'][0].update(reason='other'),lambda v:v.update(originalPreserved=False),
               lambda v:v['original'].update(phase3Complete=True),lambda v:v['original'].update(processDeathQualified=True),
               lambda v:v['original'].update(case=m.CASES[1]),lambda v:v['original'].update(outstanding=[]),
               lambda v:v['original']['physical']['continuation'].update(finalCut=True),
               lambda v:v['original']['network'].update(slots=True),lambda v:v['original']['ledgers'].pop('ballot'),
               lambda v:v['original']['ledgers']['peers'].update(peerLedgerCompositionQualified=False),
               lambda v:v['original']['precondition']['scratchRecovery'].update(discardedFiles=True),
               lambda v:v['original']['precondition']['scratchRecovery'].update(discardedFiles=0),
               lambda v:v['original']['precondition']['scratchRecovery'].update(liveWriterResourcesQualified=True)]
        for i,edit in enumerate(edits):
            value=replay(self.case);edit(value)
            with self.subTest(edit=i),self.assertRaises(ValueError):m.check_result(value,self.case)

    def test_changed_original_and_invalid_worker_count_refuse(self):
        def changed(raw,case):(raw/'changed').write_bytes(b'bad');return replay(case)
        with patch.object(m,'replay',side_effect=changed),self.assertRaisesRegex(ValueError,'original collection'):
            m.qualify_member(self.path,self.case,*self.pins)
        for n in (False,0,5):
            with self.assertRaisesRegex(ValueError,'replay workers'):self.aggregate(workers=n)

    def test_whole_original_must_pass_before_any_negative_suite(self):
        with patch.object(m.history,'validate',side_effect=ValueError('bad original')),patch.object(m.process,'qualify') as p,\
             patch.object(m.history,'qualify') as c,patch.object(m.scratch,'qualify') as s:
            with self.assertRaisesRegex(ValueError,'^bad original$'):m.replay(self.raw(),self.case)
            for run in (p,c,s):run.assert_not_called()

    def test_three_negative_suites_bind_same_unmodified_composed_original(self):
        wanted=replay(self.case);original=wanted['original'];precondition=original['precondition']
        def qualified(suite,original):
            return dict(original=original,negatives=[{k:v for k,v in row.items() if k!='suite'} for row in wanted['negatives'] if row['suite']==suite])
        for different in (False,True):
            original_process=copy.deepcopy(precondition)
            if different:original_process['case']=m.CASES[1]
            with patch.object(m.history,'validate',return_value=original),\
                 patch.object(m.process,'qualify',return_value=qualified('process',original_process)),\
                 patch.object(m.history,'qualify',return_value=qualified('composition',original)),\
                 patch.object(m.scratch,'qualify',return_value=qualified('scratch',precondition)):
                if different:
                    with self.assertRaisesRegex(ValueError,'original stage drift'):m.replay(self.raw(),self.case)
                else:self.assertEqual(wanted,m.replay(self.raw(),self.case))


if __name__=='__main__':unittest.main()
