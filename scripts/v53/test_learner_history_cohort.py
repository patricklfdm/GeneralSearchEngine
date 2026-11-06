"""Synthetic provenance/runner guards, never a substitute for native replay."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, redirect_stdout
import copy
import io
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from . import learner_history_cohort as m
from .test_process_toolchain import record


def fixture(case):
    common = dict(status='PASS',voter=False,publicReady=False,phase3Complete=False,independentReplayQualified=False)
    if case == 'alternating-slots':
        return dict(common,scope='native-alternating-learner-slots',installedThirdRevision=True,selectedThirdRevision=True,
                    seedRetired=True,lastRevision=6,testBudgetSeconds=900,cycles=[dict(revision=i) for i in (4,5,6)])
    return dict(common,scope='native-learner-cancellation',liveCore=False,testBudgetSeconds=600)


def history(raw,case):
    raw.mkdir(parents=True); wrapper=raw;raw=m.run.original(raw,case);raw.mkdir(parents=True,exist_ok=True)
    (raw/'original-plan.gsbp').write_bytes(case.encode())
    if case=='retained-cancellation':
        from .test_native_learner_resources import observations
        observed=observations();folder=wrapper/'original/resources';folder.mkdir();(raw/'learner-plan.gslp').write_bytes(b'synthetic plan')
        (folder/'trace.json').write_bytes(m.h.snapshot.f.canonical(observed[0]));m.h.save(folder/'boundaries.json',observed[1])
        (folder/'index.json').write_bytes(m.h.snapshot.f.canonical(dict(schema=m.run.resources.SCHEMA,status='PARTIAL',pid=1,
            planSha256=m.h.digest(b'synthetic plan'),wholeRuntimeResourcesQualified=False,phase3Complete=False)))
        from .test_native_learner_byte_pressure import observation
        for mode in m.run.pressure.MODES:
            folder=wrapper/'pressure'/mode;sidecars=folder/'resources';sidecars.mkdir(parents=True)
            value=observation(mode)
            (sidecars/'trace.json').write_bytes(m.h.snapshot.f.canonical(value[2]))
            (sidecars/'boundaries.json').write_bytes(m.h.snapshot.f.canonical(value[3]));shutil.copyfile(wrapper/'original/resources/index.json',sidecars/'index.json')
            m.h.save(folder/'events.json',value[4]);m.h.save(folder/'probe.json',value[5]);(folder/'result.json').write_bytes(m.h.snapshot.f.canonical(value[6]))
            for stage in m.run.pressure.STAGES:(folder/stage).mkdir()
            if mode=='source-exact':(folder/'received').mkdir()
    for name in ('events','wire','calls','failures'):
        (raw/(name+'.json')).write_bytes(m.h.snapshot.f.canonical([] if name == 'failures' else [dict(synthetic=True)]))
    (raw/m.run.RESULTS[case]).write_bytes(m.h.snapshot.f.canonical(fixture(case)))


def reports(work,case):
    reports = work/m.h.MODULE/'target/surefire-reports'; reports.mkdir(parents=True)
    cls,method = m.run.selected(case); cls = m.run.PACKAGE+cls
    suite = ET.Element('testsuite',dict(name=cls,tests='1',failures='0',errors='0',skipped='0'))
    ET.SubElement(suite,'testcase',dict(classname=cls,name=method))
    ET.ElementTree(suite).write(reports/'TEST-original.xml'); return reports


def replay(case):
    original = dict(status='PASS',physicalQualification=True,forceOrderQualified=True,processDeathQualified=False,phase3Complete=False)
    if case == 'alternating-slots':
        original.update(scope='native-six-revision-learner-history',revisions=6,snapshots=25,exchanges=200,
                        learnerAcquisitionQualified=True,selectedHeadQualified=True,fullNetworkQualification=False)
    else:
        original.update(scope='native-learner-cancellation',coldReopenQualified=True,autonomous=False,
                        renewalHistory=dict(campaigns=4,slots=8),learnerRetention=dict(quorums=2,forcedUpdates=4,sourceExposures=2,wireACKs=2,failedAttempts=0),
                        acquisition=dict(exchanges=31,originalFiles=9,peer='node-1'),progress=dict(exchanges=28,originalFiles=9,peer='node-1'))
    result=dict(original=original,negatives=[dict(case=k,status='REJECTED',reason=v) for k,v in m.negative_cases(case).items()])
    if case=='retained-cancellation':
        from .test_native_learner_resources import observations
        resources=m.run.resources.bind(*observations())
        resources['snapshots']={name:dict(physicalBytes=100,typedBackupBytes=10,miscBytes=20,inventorySha256='a'*64) for name in m.run.cancellation.STAGES}
        from .test_native_learner_byte_pressure import observation
        result.update(resources=resources,originalPreserved=True,bytePressure=[m.run.pressure.bind(*observation(mode)) for mode in m.run.pressure.MODES])
    return result


class LearnerHistoryCohortTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        self.reader = dict(files={'scripts/v53/reader.py':m.h.digest(b'synthetic reader')},sha256='f'*64)
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        for module in (m,m.run): self.stack.enter_context(patch.object(module,'reader_manifest',return_value=self.reader))
        # Tiny synthetic provenance fixtures have no actual native physical trees.
        for module in (m.run.cycles,m.run.cancellation): self.stack.enter_context(patch.object(module,'inventory'))
        self.paths = {case:self.root/case for case in m.KINDS}
        for case,path in self.paths.items(): self.producer(path,case)
        self.case = m.KINDS[0]; self.path = self.paths[self.case]
        self.pins = [m.h.digest((self.path/name).read_bytes()) for name in ('source.json','build.json')]+[
            m.tc.pin((self.path/'toolchain.json').read_bytes()),self.reader['sha256']]

    def producer(self,path,case):
        work = path/'workspace'; (work/'scripts/v53').mkdir(parents=True)
        (work/'scripts/v53/reader.py').write_bytes(b'synthetic reader')
        m.h.save(path/'source.json',dict(head='a'*40,files=self.reader['files']))
        for name in m.BUILDS:
            directory = work/name; directory.mkdir(parents=True); (directory/'original.class').write_bytes(b'synthetic classes')
        m.h.save(path/'build.json',{name:m.h.inventory(work/name) for name in m.BUILDS})
        m.h.save(path/'toolchain.json',record()); junit = m.run.junit(reports(work,case),case)
        raw = work/m.h.MODULE/'target'/m.run.directory(case)/'run-00000000-0000-0000-0000-000000000001'; history(raw,case)
        m.h.save(path/'collection.json',m.run.collect(raw,case)); m.h.save(path/'execution.json',dict(exit=0))
        m.h.save(path/'receipt.json',dict(schema=m.run.SCHEMA,status='PARTIAL',executionStatus='PASS',case=case,
            collectionComplete=True,nativeHistoryQualified=False,phase3Complete=False,retries=0,
            execution=dict(exit=0),collectionExecution=dict(exit=0),baseHead='a'*40,readerSha256=self.reader['sha256'],
            command=['mvn',*m.run.command(case)],junit=junit,raw=raw.relative_to(path).as_posix(),
            **{key+'Sha256':m.h.digest((path/file).read_bytes()) for key,file in
               (('source','source.json'),('build','build.json'),('toolchain','toolchain.json'),('collection','collection.json'))}))

    def raw(self,path=None):
        path = self.path if path is None else path
        return path/m.read(path/'receipt.json')['raw']

    def receipt(self,**changes):
        value = m.read(self.path/'receipt.json'); value.update(changes); m.h.save(self.path/'receipt.json',value)

    def member(self): return m.member(self.path,self.case,*self.pins)

    def matrix(self,paths=None,**kwargs):
        with patch.object(m,'ProcessPoolExecutor',ThreadPoolExecutor):
            return m.validate(self.paths if paths is None else paths,*self.pins,**kwargs)

    def test_two_declared_whole_native_methods_and_exact_74_negatives(self):
        self.assertEqual((12,62),tuple(len(m.negative_cases(case)) for case in m.KINDS))
        for case,(cls,method) in m.run.METHODS.items():
            source = m.h.ROOT/m.h.MODULE/('src/test/java/'+m.run.PACKAGE.replace('.','/')+cls+'.java')
            self.assertIn('void '+method+'()',source.read_text())
            self.assertEqual(1,sum(v.startswith('-Dtest=') for v in m.run.command(case)))
            self.assertFalse(any('timeout' in v.lower() or 'retry' in v.lower() for v in m.run.command(case)))

    def test_collection_is_partial_and_does_not_read_native_authority(self):
        with patch.object(m.run.cycles,'validate') as validator:
            result = m.run.collect(self.raw(),self.case)
        validator.assert_not_called(); self.assertEqual('PARTIAL',result['status'])
        self.assertIs(False,result['nativeHistoryQualified']); self.assertIs(False,result['phase3Complete'])

    def test_collection_rejects_missing_final_cancel_result_and_missing_observations(self):
        result = self.raw()/m.run.RESULTS[self.case]; result.unlink()
        with self.assertRaises((ValueError,FileNotFoundError)): m.run.collect(self.raw(),self.case)
        result.write_bytes(m.h.snapshot.f.canonical(fixture(self.case)))
        (self.raw()/'wire.json').write_bytes(b'[]')
        with self.assertRaisesRegex(ValueError,'observation containers'): m.run.collect(self.raw(),self.case)

    def test_fixture_scope_or_budget_cannot_be_relaxed(self):
        for case in m.KINDS:
            for mutate in (lambda v:v.update(phase3Complete=True),lambda v:v.update(testBudgetSeconds=3600),
                           lambda v:v.update(status='FAIL'),lambda v:v.update(independentReplayQualified=True)):
                value = fixture(case); mutate(value)
                with self.subTest(case=case),self.assertRaisesRegex(ValueError,'fixture scope'): m.run.fixture(value,case)
        value = fixture('alternating-slots'); value['cycles'].pop()
        with self.assertRaisesRegex(ValueError,'six-revision fixture'): m.run.fixture(value,'alternating-slots')

    def test_relocating_an_original_does_not_change_admission(self):
        old = self.member(); destination = self.root/'download'; shutil.copytree(self.path,destination)
        got = m.member(destination,self.case,*self.pins)
        self.assertEqual({k:v for k,v in old.items() if k != 'raw'},{k:v for k,v in got.items() if k != 'raw'})

    def test_source_build_reader_and_tool_drift_reject_before_replay(self):
        files = [('workspace/scripts/v53/reader.py','recorded source changed'),
                 ('workspace/target/classes/original.class','original built bytes')]
        for name,reason in files:
            path = self.path/name; original = path.read_bytes(); path.write_bytes(b'changed')
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,reason): self.member()
            path.write_bytes(original)
        self.receipt(readerSha256='0'*64)
        with self.assertRaisesRegex(ValueError,'reader belongs'): self.member()
        self.receipt(readerSha256=self.reader['sha256'])
        tools = m.read(self.path/'toolchain.json'); tools['identity']['binaries']['java/lib/modules'] = 'b'*64
        m.h.save(self.path/'toolchain.json',tools); self.receipt(toolchainSha256=m.h.digest((self.path/'toolchain.json').read_bytes()))
        with self.assertRaisesRegex(ValueError,'portable toolchain'): self.member()

    def test_reader_must_exist_in_original_source_not_only_have_a_receipt_hash(self):
        self.reader['files']['new-reader.py'] = 'a'*64
        with self.assertRaisesRegex(ValueError,'reader belongs to producer source'): self.member()

    def test_host_diagnostics_can_differ_with_identical_tools(self):
        m.h.save(self.path/'toolchain.json',record('/another-host','another-kernel'))
        self.receipt(toolchainSha256=m.h.digest((self.path/'toolchain.json').read_bytes()))
        self.member()

    def test_retries_failed_or_qualified_producer_labels_are_not_admission(self):
        original = (self.path/'receipt.json').read_bytes()
        for changes in (dict(retries=1),dict(retries=False),dict(executionStatus='FAIL'),dict(nativeHistoryQualified=True),
                        dict(phase3Complete=True),dict(collectionComplete=False)):
            self.receipt(**changes)
            with self.subTest(changes=changes),self.assertRaisesRegex(ValueError,'unretried whole history'): self.member()
            (self.path/'receipt.json').write_bytes(original)

    def test_altered_command_and_faked_collection_reject(self):
        self.receipt(command=['mvn',*m.run.command(self.case),'-Dtest=SomeOtherTest'])
        with self.assertRaisesRegex(ValueError,'exact whole command'): self.member()
        self.receipt(command=['mvn',*m.run.command(self.case)])
        collection = m.read(self.path/'collection.json'); collection['nativeHistoryQualified'] = True
        m.h.save(self.path/'collection.json',collection); self.receipt(collectionSha256=m.h.digest((self.path/'collection.json').read_bytes()))
        with self.assertRaisesRegex(ValueError,'recollected original'): self.member()

    def test_boolean_numeric_aliases_do_not_match_collected_records(self):
        collection = m.read(self.path/'collection.json'); collection['nativeHistoryQualified'] = 0
        m.h.save(self.path/'collection.json',collection); self.receipt(collectionSha256=m.h.digest((self.path/'collection.json').read_bytes()))
        with self.assertRaisesRegex(ValueError,'recollected original'): self.member()
        m.h.save(self.path/'collection.json',m.run.collect(self.raw(),self.case))
        self.receipt(collectionSha256=m.h.digest((self.path/'collection.json').read_bytes()))
        junit = m.read(self.path/'receipt.json')['junit']; junit['tests'] = True; self.receipt(junit=junit)
        with self.assertRaisesRegex(ValueError,'exact JUnit receipt'): self.member()

    def test_flaky_rerun_and_wrong_method_junit_refuse(self):
        path = self.path/'workspace'/m.h.MODULE/'target/surefire-reports/TEST-original.xml'; original = path.read_bytes()
        for tag in ('flakyFailure','rerunFailure','skipped'):
            root = ET.fromstring(original); ET.SubElement(root.find('testcase'),tag); ET.ElementTree(root).write(path)
            with self.subTest(tag=tag),self.assertRaisesRegex(ValueError,'unretried test'): self.member()
        path.write_bytes(original); root = ET.fromstring(original); root.find('testcase').set('name','anotherMethod'); ET.ElementTree(root).write(path)
        with self.assertRaisesRegex(ValueError,'unretried test'): self.member()

    def test_links_and_extra_history_refuse(self):
        raw = self.raw(); (raw/'linked').symlink_to('original-plan.gsbp')
        with self.assertRaisesRegex(ValueError,'linked member'): self.member()
        (raw/'linked').unlink(); (raw.parent/'other-run').mkdir()
        with self.assertRaisesRegex(ValueError,'exact original history directory'): self.member()

    def test_complete_pair_runs_each_original_first_once_and_retains_partial_scope(self):
        progress = []
        with patch.object(m.run.cycles,'qualify',return_value=replay('alternating-slots')) as cycles, \
             patch.object(m,'replay_cancellation',return_value=replay('retained-cancellation')) as cancel:
            result = self.matrix(workers=2,progress=progress.append)
        cycles.assert_called_once(); cancel.assert_called_once_with(self.raw(self.paths['retained-cancellation']))
        self.assertEqual(2,len(progress)); self.assertEqual(74,result['negativeCases']); self.assertEqual('PASS',result['status'])
        self.assertIs(True,result['declaredLearnerHistoryPairQualified'])
        for key in ('phase3Complete','allMembershipProfilesQualified','processDeathQualified','fullNetworkQualification','combinedPeakResourcesQualified'):
            self.assertIs(False,result[key])

    def test_missing_alias_and_duplicate_original_cannot_fill_pair(self):
        with self.assertRaisesRegex(ValueError,'complete pair'): self.matrix({self.case:self.path})
        with self.assertRaisesRegex(ValueError,'distinct producer directories'): self.matrix(dict.fromkeys(m.KINDS,self.path))
        other = self.paths['retained-cancellation']; (m.run.original(self.raw(other),'retained-cancellation')/'original-plan.gsbp').write_bytes(self.case.encode())
        m.h.save(other/'collection.json',m.run.collect(self.raw(other),'retained-cancellation'))
        receipt = m.read(other/'receipt.json'); receipt['collectionSha256'] = m.h.digest((other/'collection.json').read_bytes()); m.h.save(other/'receipt.json',receipt)
        with self.assertRaisesRegex(ValueError,'distinct original histories'): self.matrix()

    def test_failure_is_retained_and_other_history_still_checked_without_retry(self):
        with patch.object(m.run.cycles,'qualify',side_effect=ValueError('invalid original')) as cycles, \
             patch.object(m,'replay_cancellation',return_value=replay('retained-cancellation')) as cancel:
            result = self.matrix(workers=2)
        cycles.assert_called_once(); cancel.assert_called_once(); self.assertEqual('FAIL',result['status'])
        self.assertEqual('invalid original',result['cases'][0]['failure']['message'])
        self.assertEqual('PASS',result['cases'][1]['status']); self.assertIs(False,result['declaredLearnerHistoryPairQualified'])

    def test_missing_or_unrelated_negative_and_overclaimed_original_reject(self):
        for case in m.KINDS:
            for mutate in (lambda v:v['negatives'].pop(),lambda v:v['negatives'][0].update(reason='unrelated'),
                           lambda v:v['original'].update(phase3Complete=True),lambda v:v['original'].update(processDeathQualified=True)):
                value = replay(case); mutate(value)
                with self.subTest(case=case),self.assertRaises(ValueError): m.check_result(value,case)
        value = replay('retained-cancellation'); value['original']['learnerRetention']['quorums'] = 1
        with self.assertRaisesRegex(ValueError,'retention rounds'): m.check_result(value,'retained-cancellation')

    def test_cancellation_requires_original_resource_sidecars(self):
        path=self.raw(self.paths['retained-cancellation']);sidecar=path/'original/resources/index.json'
        saved=sidecar.read_bytes();sidecar.unlink()
        with self.assertRaisesRegex(ValueError,'complete original resource wrapper'):m.run.collect(path,'retained-cancellation')
        sidecar.write_bytes(saved);value=m.read(sidecar);value['planSha256']='0'*64
        sidecar.write_bytes(m.h.snapshot.f.canonical(value))
        with self.assertRaisesRegex(ValueError,'resource capture index'):m.run.collect(path,'retained-cancellation')

    def test_old_cancellation_method_cannot_be_used_for_resource_admission(self):
        path=self.paths['retained-cancellation'];receipt=m.read(path/'receipt.json')
        receipt['command']=[v if not v.startswith('-Dtest=') else '-Dtest=V53LearnerCancellationQualification#nativeReadyCancellationRetainsItsPreparedAncestorAndColdReopensWithoutVoting' for v in receipt['command']]
        m.h.save(path/'receipt.json',receipt)
        with self.assertRaisesRegex(ValueError,'exact whole command'):m.member(path,'retained-cancellation',*self.pins)

    def test_missing_or_foreign_pressure_mode_is_not_collected(self):
        path=self.raw(self.paths['retained-cancellation']);folder=path/'pressure/pool-full'
        saved=m.read(folder/'resources/index.json');changed=dict(saved,pid=2)
        (folder/'resources/index.json').write_bytes(m.h.snapshot.f.canonical(changed))
        with self.assertRaisesRegex(ValueError,'original byte pressure index'):m.run.collect(path,'retained-cancellation')
        (folder/'resources/index.json').write_bytes(m.h.snapshot.f.canonical(saved))
        (folder/'result.json').unlink()
        with self.assertRaisesRegex(ValueError,'complete byte pressure mode'):m.run.collect(path,'retained-cancellation')

    def test_old_resources_only_method_cannot_fill_byte_pressure_slot(self):
        path=self.paths['retained-cancellation'];receipt=m.read(path/'receipt.json')
        receipt['command']=[v if not v.startswith('-Dtest=') else '-Dtest=V53NativeLearnerResourcesQualification#admittedCancellationAndColdReopenPreserveOriginalResourceLifetimes' for v in receipt['command']]
        m.h.save(path/'receipt.json',receipt)
        with self.assertRaisesRegex(ValueError,'exact whole command'):m.member(path,'retained-cancellation',*self.pins)

    def test_pressure_summary_cannot_drop_mode_drift_budget_or_claim_whole_runtime(self):
        changes=(lambda v:v.pop('bytePressure'),lambda v:v['bytePressure'].pop(),
            lambda v:v['bytePressure'][0].update(wholeRuntimeResourcesQualified=True),
            lambda v:v['bytePressure'][1].update(stagingLimit=v['bytePressure'][1]['stagingLimit']+1),
            lambda v:v['bytePressure'][1].update(packetBytes=16),
            lambda v:v['bytePressure'][2].update(receiver='REJECTED'),
            lambda v:v['bytePressure'][0].update(closeIntervals=2),
            lambda v:v['bytePressure'][0].update(transitions=True))
        for change in changes:
            value=replay('retained-cancellation');change(value)
            with self.subTest(value=value),self.assertRaises(ValueError):m.check_result(value,'retained-cancellation')

    def test_missing_forged_or_overclaimed_resource_summary_never_aggregates(self):
        mutations=(lambda v:v.pop('resources'),lambda v:v.update(originalPreserved=False),
            lambda v:v['resources'].update(wholeRuntimeResourcesQualified=True),
            lambda v:v['resources'].update(closeIntervals=5),lambda v:v['resources'].update(callbacks=True),
            lambda v:v['resources'].update(continuousOwnershipQualified=False),
            lambda v:v['resources'].update(generationSelections=[2,2]),
            lambda v:v['resources']['snapshots'].pop('learner-closed'),
            lambda v:v['resources']['snapshots']['learner-prepared'].update(typedBackupBytes=1000),
            lambda v:v['original'].update(renewalHistory=dict(campaigns=1,slots=5)))
        for mutation in mutations:
            value=replay('retained-cancellation');mutation(value)
            with self.subTest(value=value),self.assertRaises(ValueError):m.check_result(value,'retained-cancellation')

    def test_cancellation_adapter_preserves_all_original_negative_suites(self):
        base=replay('retained-cancellation')
        negatives=[dict(suite=suite,case=name,status='REJECTED',reason=reason) for suite,cases in (
            ('byte-pressure',m.run.pressure.NEGATIVES),('byte-physical',m.run.pressure.PHYSICAL_NEGATIVES),
            ('original-resource-observations',m.run.resources.NEGATIVES),('original-original-history',dict(m.run.cancellation.NEGATIVES,**m.retention.NEGATIVES)),
            ('original-renewal-history',m.run.resources.HISTORY_NEGATIVES)) for name,reason in cases.items()]
        value=dict(original=dict(status='PARTIAL',original=dict(status='PARTIAL',original=base['original'],resources=base['resources'],phase3Complete=False),
            modes=base['bytePressure'],wholeRuntimeResourcesQualified=False,phase3Complete=False),
            negatives=negatives,originalPreserved=True,phase3Complete=False)
        with patch.object(m.run.pressure,'qualify',return_value=value) as qualify:
            got=m.replay_cancellation('/synthetic');m.check_result(got,'retained-cancellation')
            qualify.assert_called_once_with('/synthetic');self.assertEqual(base,got)
            value['negatives'][0]['suite']='original-history'
            with self.assertRaisesRegex(ValueError,'complete resource negative suites'):m.replay_cancellation('/synthetic')

    def test_original_mutation_during_replay_is_rejected(self):
        def changed(raw):
            (raw/'events.json').write_bytes(b'[]'); return replay(self.case)
        with patch.object(m.run.cycles,'qualify',side_effect=changed),self.assertRaises(ValueError):
            m.qualify_member(self.path,self.case,*self.pins)

    def test_worker_limit_rejects_boolean_zero_and_excess(self):
        for workers in (False,0,3):
            with self.subTest(workers=workers),self.assertRaisesRegex(ValueError,'replay workers'): self.matrix(workers=workers)

    def test_capture_uses_frozen_collector_and_one_native_command(self):
        output = self.root/'captured'; commands = []
        def execute(args,work,log,**kwargs):
            commands.append(args); log.write_text('synthetic capture\n')
            if args[0] == 'mvn':
                for name in m.BUILDS:
                    p = work/name; p.mkdir(parents=True); (p/'original.class').write_bytes(b'synthetic classes')
                reports(work,self.case); history(work/m.h.MODULE/'target/v53-native-dispatch/run-00000000-0000-0000-0000-000000000002',self.case)
            else:
                self.assertEqual(['-B','-m','scripts.v53.learner_history_run'],args[1:4])
                m.h.save(Path(args[4]),m.run.collect(Path(args[-1]),self.case))
            return dict(exit=0)
        with patch.object(m.run.tc,'capture',return_value=record()),patch.object(m.h,'execute',side_effect=execute),redirect_stdout(io.StringIO()):
            result = m.run.run(output,'mvn',self.case,source_from=self.path)
        self.assertEqual(2,len(commands)); self.assertEqual('PARTIAL',result['status']); self.assertEqual(0,result['retries'])
        self.assertEqual('PASS',result['executionStatus']); self.assertIs(False,result['nativeHistoryQualified'])
        m.member(output,self.case,*self.pins)

    def test_capture_failure_keeps_log_and_raw_and_never_collects_or_retries(self):
        output = self.root/'failed-capture'
        def failed(args,work,log,**kwargs):
            log.write_text('original deadline failure\n'); (work/'original-failed-bytes').write_bytes(b'failure'); return dict(exit=1)
        with patch.object(m.run.tc,'capture',return_value=record()),patch.object(m.h,'execute',side_effect=failed) as execute,redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError,'Maven failed'): m.run.run(output,'mvn',self.case,source_from=self.path)
        execute.assert_called_once(); self.assertEqual(b'failure',(output/'workspace/original-failed-bytes').read_bytes())
        self.assertEqual('FAIL',m.read(output/'receipt.json')['status']); self.assertFalse((output/'collection.json').exists())
        with self.assertRaises(FileExistsError): m.run.run(output,'mvn',self.case,source_from=self.path)

    def test_old_source_is_rejected_before_running_maven(self):
        self.reader['files']['new-reader.py'] = 'a'*64
        with patch.object(m.h,'execute') as execute,redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError,'reader belongs to source'):
                m.run.run(self.root/'old-source','mvn',self.case,source_from=self.path)
        execute.assert_not_called()


if __name__ == '__main__': unittest.main()
