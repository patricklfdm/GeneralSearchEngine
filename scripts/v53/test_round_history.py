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
from . import round_history as m
from .test_process_toolchain import record


def raw_tree(raw,case):
    raw.mkdir(parents=True);(raw/'original-plan.gsbp').write_bytes(case.encode())
    old=m.phase(case)
    if old:
        (raw/'carried-phase.txt').write_text(old);(raw/'entry-1.gsr').write_bytes(b'synthetic entry')
        m.h.save(raw/'carried-result.json',dict(status='PASS',carried=m.h.digest(b'synthetic entry'),slots=2,publicReady=False))
    else:m.h.save(raw/'result.json',dict(status='PASS',slots=2,network=True,autonomous=False))
    if case.startswith('round-'):m.h.save(raw/'round-result.json',dict(status='PASS',mode='carried-applied' if old else 'stable',internalReady=True,publicReady=False))


def reports(work,case):
    cls,method,_=m.selected(case);cls=m.PACKAGE+cls;root=work/m.h.MODULE/'target/surefire-reports';root.mkdir(parents=True)
    suite=ET.Element('testsuite',dict(name=cls,tests='1',failures='0',errors='0',skipped='0'))
    ET.SubElement(suite,'testcase',dict(classname=cls,name=method));ET.ElementTree(suite).write(root/'TEST-original.xml')
    return root


def replay(case):
    old=m.phase(case)
    original=dict(status='PASS',slots=2,selected=2,transfers=1,retentionSemantics='original-copy-confirmation',phase3Complete=False)
    if old:original.update(phase=old,voters=3,automaticElection=False,publicReady=False)
    else:original.update(autonomous=False)
    if case=='round-discovered':original['discoveryPeers']=2
    if case.startswith('round-'):original=dict(status='PASS',mode='carried-applied' if old else 'stable',slots=2,original=original,internalReady=True,publicReady=False,phase3Complete=False)
    return dict(original=original,originalPreserved=True,negatives=m.negative_cases(case))


class RoundHistoryTest(unittest.TestCase):
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
        self.assertEqual(7,len(m.CASES));self.assertEqual((1,)*7,tuple(len(m.histories(k)) for k in m.CASES))
        for case,(cls,method,_) in m.METHODS.items():
            text=(m.h.ROOT/m.h.MODULE/('src/test/java/'+m.PACKAGE.replace('.','/')+cls+'.java')).read_text()
            self.assertIn('void '+method+'()',text)
            args=m.command(case);self.assertEqual(1,sum(v.startswith('-Dtest=') for v in args))
            self.assertFalse(any('retry' in v.lower() or 'timeout' in v.lower() or '.case=' in v for v in args))
        for value in ('other','',False):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'exact case'):m.command(value)

    def test_collection_is_only_bounded_inventory_not_authority_replay(self):
        with patch.object(m,'replay') as validator:result=m.collect(self.raw(),self.case)
        validator.assert_not_called();self.assertEqual('PARTIAL',result['status']);self.assertFalse(result['nativeHistoryQualified'])

    def test_wrong_carried_phase_result_or_unexpected_lifecycle_reject(self):
        raw=self.raw();path=raw/'carried-phase.txt';before=path.read_text();path.write_text('APPLIED')
        with self.assertRaisesRegex(ValueError,'exact carried phase'):m.collect(raw,self.case)
        path.write_text(before);value=m.read(raw/'carried-result.json');m.h.save(raw/'carried-result.json',dict(value,publicReady=True))
        with self.assertRaisesRegex(ValueError,'carried producer scope'):m.collect(raw,self.case)
        m.h.save(raw/'carried-result.json',value);m.h.save(raw/'round-result.json',{})
        with self.assertRaisesRegex(ValueError,'unexpected lifecycle'):m.collect(raw,self.case)

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
        with self.assertRaisesRegex(ValueError,'complete seven histories'):self.aggregate({self.case:self.path})
        with self.assertRaisesRegex(ValueError,'distinct producers'):self.aggregate(dict.fromkeys(m.CASES,self.path))
        other=self.paths['slot-proof'];raw=self.raw(other);source=raw/'original-plan.gsbp'
        source.write_bytes((self.raw()/'original-plan.gsbp').read_bytes());m.h.save(other/'collection.json',m.collect(raw,'slot-proof'))
        value=m.read(other/'receipt.json');value['collectionSha256']=m.h.digest((other/'collection.json').read_bytes());m.h.save(other/'receipt.json',value)
        with self.assertRaisesRegex(ValueError,'distinct complete original'):self.aggregate()

    def test_complete_seven_histories_replay_once_and_preserve_scope(self):
        with patch.object(m,'replay',side_effect=lambda raw,case:replay(case)) as reader:result=self.aggregate(workers=4)
        self.assertEqual(7,reader.call_count);self.assertEqual('PASS',result['status'])
        self.assertEqual(7,result['nativeCases']);self.assertEqual(7,result['wholeOwnershipHistories']);self.assertEqual(287,result['negativeCases'])
        for key in ('phase3Complete','combinedPeakResourcesQualified','autonomousCompetitionQualified','completePhysicalQualified','powerLossQualified','processDeathQualified'):
            self.assertIs(False,result[key])

    def test_failure_is_retained_while_other_originals_still_checked(self):
        def failed(raw,case):
            if case==self.case:raise ValueError('original failed')
            return replay(case)
        with patch.object(m,'replay',side_effect=failed) as reader:result=self.aggregate(workers=4)
        self.assertEqual(7,reader.call_count);self.assertEqual('FAIL',result['status'])
        self.assertEqual('original failed',result['cases'][0]['failure']['message']);self.assertTrue(all(v['status']=='PASS' for v in result['cases'][1:]))

    def test_missing_negatives_profiles_or_inflated_scope_never_pass(self):
        for case in m.CASES:
            changes=[lambda v:v['negatives'].pop(),lambda v:v['negatives'][0].update(reason='other'),lambda v:v.update(originalPreserved=False),
                     lambda v:v['original'].update(phase3Complete=True),lambda v:v['original'].update(allMembershipProfilesQualified=True)]
            changes.append(lambda v:v['original'].update(slots=True))
            for change in changes:
                value=replay(case);change(value)
                with self.subTest(case=case),self.assertRaises(ValueError):m.check_result(value,case)

    def test_mutation_during_replay_and_bad_workers_refuse(self):
        def changed(raw,case):(raw/'changed').write_bytes(b'bad');return replay(self.case)
        with patch.object(m,'replay',side_effect=changed),self.assertRaises(ValueError):m.qualify_member(self.path,self.case,*self.pins)
        for n in (False,0,5):
            with self.assertRaisesRegex(ValueError,'replay workers'):self.aggregate(workers=n)

    def test_round_replay_requires_underlying_physical_and_lifecycle_negatives(self):
        for case in ('round-stable','round-discovered','round-carried'):
            expected=replay(case);root=self.raw(self.paths[case]);reader=m.carried if m.phase(case) else m.dispatch
            physical=dict(original=expected['original']['original'],negatives=[{k:v for k,v in row.items() if k!='suite'} for row in expected['negatives'] if row['suite']=='physical'])
            life=dict(original=expected['original'],negatives=[{k:v for k,v in row.items() if k!='suite'} for row in expected['negatives'] if row['suite']=='lifecycle'])
            options=dict(confirmed_retention=True)
            if case=='round-discovered':options['discovery']=True
            with patch.object(m.rounds,'qualify',return_value=life) as a,patch.object(reader,'qualify',return_value=physical) as b:
                result=m.replay(root,case)
            a.assert_called_once_with(root,**options);self.assertEqual(dict(options,**({'precommand_maintenance':True} if not m.phase(case) else {})),b.call_args.kwargs)
            self.assertNotEqual(root,b.call_args.args[0]);self.assertTrue((root/'round-result.json').is_file())
            self.assertEqual(expected,result);m.check_result(result,case)
        self.assertTrue(any(v['case']=='discovery-missing' and v['suite']=='physical' for v in m.negative_cases('round-discovered')))

    def test_original_failure_precedes_secondary_replay_or_mutation(self):
        with patch.object(m.rounds,'qualify',side_effect=ValueError('original broken')),patch.object(m.dispatch,'qualify') as physical:
            with self.assertRaisesRegex(ValueError,'original broken'):m.replay(self.raw(self.paths['round-stable']),'round-stable')
        physical.assert_not_called()

    def test_physical_derivation_disagreement_refuses_lifecycle_pass(self):
        case='round-stable';value=replay(case);bad=copy.deepcopy(value['original']['original']);bad['transfers']+=1
        with patch.object(m.rounds,'qualify',return_value=dict(original=value['original'],negatives=[])),patch.object(m.dispatch,'qualify',return_value=dict(original=bad,negatives=[])):
            with self.assertRaisesRegex(ValueError,'identical physical derivation'):m.replay(self.raw(self.paths[case]),case)

    def test_capture_uses_frozen_collector_one_command_and_preserves_source(self):
        output=self.root/'capture';commands=[]
        def execute(args,work,log,**kwargs):
            commands.append(args);log.write_text('synthetic capture\n')
            if args[0]=='mvn':
                for name in m.BUILDS:
                    p=work/name;p.mkdir(parents=True);(p/'original.class').write_bytes(b'synthetic classes')
                reports(work,self.case);raw_tree(work/m.h.MODULE/('target/'+m.selected(self.case)[2]+'/run-00000000-0000-0000-0000-000000000002'),self.case)
            else:
                self.assertEqual(['-B','-m','scripts.v53.round_history','collect'],args[1:5]);m.h.save(Path(args[5]),m.collect(Path(args[-1]),self.case))
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
