"""Synthetic execution/admission guards; these tests are not physical evidence."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from . import capacity_completion_run as m
from .test_process_toolchain import record


def reports(work,profile):
    cls,method,_,_=m.selected(profile);cls=m.PACKAGE+cls;root=work/m.h.MODULE/'target/surefire-reports';root.mkdir(parents=True)
    suite=ET.Element('testsuite',dict(name=cls,tests='1',failures='0',errors='0',skipped='0'))
    ET.SubElement(suite,'testcase',dict(classname=cls,name=method));ET.ElementTree(suite).write(root/'TEST-original.xml');return root


def raw_tree(work,profile):
    _,_,directory,suffix=m.selected(profile);parent=work/m.h.MODULE/'target'/directory
    base='run-00000000-0000-0000-0000-000000000001';raw=parent/(base+suffix);raw.mkdir(parents=True)
    if profile=='capacity-231':(parent/base).mkdir()
    m.h.save(raw/'receipt.json',m.gate.receipt(profile));(raw/'synthetic.bin').write_bytes(b'not physical evidence');return raw


def replay(profile):
    first=7*m.gate.PROFILES[profile]-1
    return dict(status='PASS',profile=profile,slots=5,owners=3,campaigns=2,callObservations=93,ownedObservations=54,
                conditionalPrefix=True,originalFirst=True,capacityBoundary=profile=='capacity-231',freshProcesses=False,nativeNetwork=False,
                phase3Complete=False,portableReplay='PASS',resources=resource_summary(profile),
                resourceNegatives=[dict(case=n,status='REJECTED',reason=r) for n,r in m.gate.resources.VARIANTS.items()],negativeCases=[dict(case=n,status='REJECTED',reason=r.format(first=first)) for n,r in m.gate.VARIANTS.items()])


def resource_summary(profile):
    return dict(status='PASS',scope='conditional-owner-accounting-and-publication-storage',ownerLifetimes=len(m.gate.resources.schedule(profile)),
                mutations=1000,eventCheckpoints=2000,publications=15,publicationBoundaries=165,
                maximumObservedReservations=dict(metadata=36*1024**2,staging=256*1024**2,queued=0,leases=7),
                maximumObservedCounts=dict(GENERATION=2,SOURCE=3,APPLICATION=7),
                maximumPublicationStorage=dict(metadata=36*1024**2,staging=256*1024**2,applications=7,sources=3),
                observedAccountingQualified=True,publicationStorageQualified=True,closeIntervalsQualified=True,closeReleasedLeases=500,closeCheckedChanges=500,physicalShutdownOrderQualified=False,
                wholeRuntimeResourcesQualified=False,phase3Complete=False)


class CapacityCompletionRunTest(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.reader=dict(files={'scripts/v53/reader.py':m.h.digest(b'synthetic reader')},sha256='f'*64)
        patched=patch.object(m,'reader_manifest',return_value=self.reader);patched.start();self.addCleanup(patched.stop)
        self.profile='capacity-231';self.path=self.root/'producer';self.producer(self.path,self.profile)
        self.pins=dict(sourceSha256=m.h.digest((self.path/'source.json').read_bytes()),buildSha256=m.h.digest((self.path/'build.json').read_bytes()),
                       toolchainSha256=m.tc.pin((self.path/'toolchain.json').read_bytes()),readerSha256=self.reader['sha256'])

    def source(self,repo,work):
        (work/'scripts/v53').mkdir(parents=True);(work/'scripts/v53/reader.py').write_bytes(b'synthetic reader')
        return dict(head='a'*40,files=self.reader['files'])

    def generated(self,work,profile):
        for name in m.BUILDS:
            p=work/name;p.mkdir(parents=True);(p/'original.class').write_bytes(b'synthetic classes')
        reports(work,profile);return raw_tree(work,profile)

    def producer(self,path,profile):
        work=path/'workspace';source=self.source(None,work);m.h.save(path/'source.json',source)
        raw=self.generated(work,profile);m.h.save(path/'reader.json',self.reader);m.h.save(path/'toolchain.json',record())
        m.h.save(path/'build.json',{n:m.h.inventory(work/n) for n in m.BUILDS});m.h.save(path/'collection.json',m.collect(raw,profile))
        for name in ('execution','collection-execution'):m.h.save(path/(name+'.json'),dict(exit=0))
        m.h.save(path/'receipt.json',dict(schema=m.SCHEMA,status='PARTIAL',profile=profile,executionStatus='PASS',collectionComplete=True,conditionalPrefix=True,
            continuationQualified=False,capacityBoundaryQualified=False,phase3Complete=False,retries=0,execution=dict(exit=0),collectionExecution=dict(exit=0),
            baseHead='a'*40,readerSha256=self.reader['sha256'],command=['mvn',*m.command(profile)],junit=m.junit(work/m.h.MODULE/'target/surefire-reports',profile),
            raw=raw.relative_to(path).as_posix(),**{k+'Sha256':m.h.digest((path/f).read_bytes()) for k,f in
            [('source','source.json'),('build','build.json'),('toolchain','toolchain.json'),('collection','collection.json')]}))

    def edit(self,name,mutate,path=None):
        p=(path or self.path)/name;value=m.read(p);mutate(value);m.h.save(p,value)

    def test_profiles_pin_different_whole_methods_without_retry_or_time_override(self):
        for profile in m.METHODS:
            command=m.command(profile);self.assertEqual('test',command[-1]);self.assertIn('-o',command)
            self.assertEqual(1,sum(v.startswith('-Dtest=') for v in command))
            self.assertFalse(any('retry' in v.lower() or 'timeout' in v.lower() or 'skipTests' in v for v in command))
        self.assertNotEqual(m.command('capacity-231'),m.command('replay-smoke-1'))
        with self.assertRaisesRegex(ValueError,'explicit profile'):m.command('auto')

    def test_collection_never_qualifies_capacity_and_does_not_replay(self):
        with patch.object(m.gate,'qualify',side_effect=AssertionError('must not replay')):
            value=m.collect(m.locate(self.path/'workspace',self.profile),self.profile)
        self.assertEqual('PARTIAL',value['status']);self.assertFalse(value['capacityBoundaryQualified']);self.assertFalse(value['continuationQualified'])

    def test_collector_never_overwrites_evidence_or_writes_into_original(self):
        raw=m.locate(self.path/'workspace',self.profile);output=self.root/'collection.json'
        m.collect_to(output,raw,self.profile);original=output.read_bytes()
        with self.assertRaisesRegex(ValueError,'output already exists'):m.collect_to(output,raw,self.profile)
        self.assertEqual(original,output.read_bytes())
        for path in (raw/'new.json',raw/'receipt.json'):
            with self.assertRaisesRegex(ValueError,'original separation'):m.collect_to(path,raw,self.profile)
        alias=self.root/'alias.json';alias.symlink_to(output)
        with self.assertRaisesRegex(ValueError,'output already exists'):m.collect_to(alias,raw,self.profile)
        self.assertEqual(original,output.read_bytes())

    def test_verifier_output_cannot_be_inserted_into_original_producer(self):
        with self.assertRaisesRegex(ValueError,'verifier original separation'):
            m.verify(self.path/'new',self.path,self.profile,self.pins)
        self.assertFalse((self.path/'new').exists())

    def test_pins_and_unchanged_relocated_originals_are_required(self):
        original=m.member(self.path,self.profile,self.pins)
        moved=self.root/'relocated';shutil.copytree(self.path,moved);copy=m.member(moved,self.profile,self.pins)
        self.assertEqual(original['inventory'],copy['inventory']);self.assertEqual(original['producerReceiptSha256'],copy['producerReceiptSha256'])
        for field in m.PINS:
            pins=dict(self.pins,**{field:'0'*64})
            with self.subTest(field=field),self.assertRaises(ValueError):m.member(self.path,self.profile,pins)

    def test_failed_retried_or_overclaimed_execution_is_rejected(self):
        for field,value in [('status','PASS'),('executionStatus','FAIL'),('retries',1),('retries',False),('conditionalPrefix',False),
                            ('collectionComplete',False),('continuationQualified',True),('capacityBoundaryQualified',True),('phase3Complete',True)]:
            copy=self.root/field;shutil.copytree(self.path,copy);self.edit('receipt.json',lambda v:v.update({field:value}),copy)
            with self.subTest(field=field,value=value),self.assertRaisesRegex(ValueError,'successful unretried producer'):m.member(copy,self.profile,self.pins)
            shutil.rmtree(copy)

    def test_wrong_profile_command_and_boolean_process_exit_are_rejected(self):
        for field,value in [('profile','replay-smoke-1'),('command',['mvn',*m.command('replay-smoke-1')]),('execution',dict(exit=False))]:
            copy=self.root/field;shutil.copytree(self.path,copy);self.edit('receipt.json',lambda v:v.update({field:value}),copy)
            with self.subTest(field=field),self.assertRaises(ValueError):m.member(copy,self.profile,self.pins)

    def test_source_class_reader_tool_and_original_changes_are_rejected(self):
        cases={'source':'workspace/scripts/v53/reader.py','class':'workspace/'+m.BUILDS[0]+'/original.class',
               'reader':'reader.json','tool':'toolchain.json','original':m.read(self.path/'receipt.json')['raw']+'/synthetic.bin'}
        for label,name in cases.items():
            copy=self.root/label;shutil.copytree(self.path,copy)
            if label=='reader':self.edit(name,lambda v:v.update(sha256='0'*64),copy)
            elif label=='tool':self.edit(name,lambda v:v['identity']['binaries'].update({'java/bin/java':'0'*64}),copy)
            else:(copy/name).write_bytes(b'changed')
            with self.subTest(label=label),self.assertRaises(ValueError):m.member(copy,self.profile,self.pins)

    def test_extra_raws_and_nonempty_other_capacity_case_are_rejected(self):
        raw=m.locate(self.path/'workspace',self.profile);other=raw.parent/raw.name.removesuffix('-completion')
        (other/'unexpected').write_bytes(b'other case')
        with self.assertRaisesRegex(ValueError,'unused refusal matrix'):m.member(self.path,self.profile,self.pins)
        (other/'unexpected').unlink();(raw.parent/'run-other-completion').mkdir()
        with self.assertRaisesRegex(ValueError,'single exact original'):m.member(self.path,self.profile,self.pins)

    def test_linked_generated_parent_or_raw_is_rejected(self):
        for label,name in [('classes',m.BUILDS[0]),('raw',str(m.locate(self.path/'workspace',self.profile).relative_to(self.path/'workspace')))]:
            copy=self.root/label;shutil.copytree(self.path,copy);p=copy/'workspace'/name;held=self.root/(label+'-held');p.rename(held);p.symlink_to(held,target_is_directory=True)
            with self.subTest(label=label),self.assertRaises(ValueError):m.member(copy,self.profile,self.pins)

    def test_junit_extra_skipped_flaky_wrong_method_and_failed_tests_are_rejected(self):
        original=self.path/'workspace'/m.h.MODULE/'target/surefire-reports'
        for label in ('extra','skipped','flakyFailure','method','failure'):
            copy=self.root/label;shutil.copytree(original,copy);p=copy/'TEST-original.xml';tree=ET.parse(p);suite=tree.getroot()
            if label=='extra':shutil.copy2(p,copy/'TEST-extra.xml')
            elif label=='skipped':suite.set('skipped','1')
            elif label=='method':suite.find('testcase').set('name','shortConditionalPrefixExercisesTheCompletePhysicalReplayPath')
            else:ET.SubElement(suite.find('testcase'),label)
            tree.write(p)
            with self.subTest(label=label),self.assertRaises(ValueError):m.junit(copy,self.profile)

    def test_physical_reader_failure_is_retained_and_never_turns_into_an_admission(self):
        output=self.root/'failed'
        with patch.object(m.gate,'qualify',side_effect=ValueError('original failure')) as reader:
            with self.assertRaisesRegex(ValueError,'original failure'):m.verify(output,self.path,self.profile,self.pins)
            reader.assert_called_once()
        self.assertEqual('FAIL',m.read(output/'receipt.json')['status'])

    def test_missing_or_changed_negatives_and_inflated_scope_are_rejected(self):
        for label in ('missing','reason','count','scope'):
            result=replay(self.profile)
            if label=='missing':result['negativeCases'].pop()
            elif label=='reason':result['negativeCases'][0]['reason']='unrelated failure'
            elif label=='count':result['ownedObservations']=0
            else:result['phase3Complete']=True
            with patch.object(m.gate,'qualify',return_value=result),self.assertRaisesRegex(ValueError,'complete original/negative replay'):
                m.qualify(self.path,self.profile,self.pins)

    def test_original_mutation_during_replay_is_not_accepted(self):
        def mutate(raw,profile):
            (raw/'synthetic.bin').write_bytes(b'changed');return replay(profile)
        with patch.object(m.gate,'qualify',side_effect=mutate),self.assertRaisesRegex(ValueError,'original collection'):
            m.qualify(self.path,self.profile,self.pins)

    def test_smoke_success_remains_explicitly_not_capacity(self):
        path=self.root/'smoke';profile='replay-smoke-1';self.producer(path,profile)
        with patch.object(m.gate,'qualify',return_value=replay(profile)):
            result=m.qualify(path,profile,self.pins)
        self.assertTrue(result['continuationQualified']);self.assertFalse(result['capacityBoundaryQualified']);self.assertFalse(result['phase3Complete'])
        with self.assertRaises(ValueError):m.member(path,'capacity-231',self.pins)

    def test_capture_invokes_one_declared_test_and_its_recorded_source_collector(self):
        profile='replay-smoke-1';output=self.root/'capture';commands=[]
        def execute(args,work,log,**kwargs):
            commands.append(args);log.write_text('synthetic command')
            if len(commands)==1:self.generated(work,profile)
            else:m.h.save(output/'collection.json',m.collect(m.locate(work,profile),profile))
            return dict(exit=0)
        with patch.object(m.h,'source_copy',side_effect=self.source),patch.object(m.tc,'capture',return_value=record()),patch.object(m.h,'execute',side_effect=execute):
            value=m.capture(output,'mvn',profile)
        self.assertEqual('PARTIAL',value['status']);self.assertEqual(['mvn',*m.command(profile)],commands[0]);self.assertEqual(2,len(commands))
        self.assertIn('scripts.v53.capacity_completion_run',commands[1]);m.member(output,profile,m.read(output/'pins.json'))

    def test_capture_failure_keeps_partial_output_and_does_not_retry(self):
        output=self.root/'failure'
        with patch.object(m.h,'source_copy',side_effect=self.source),patch.object(m.tc,'capture',return_value=record()),patch.object(m.h,'execute',return_value=dict(exit=1)) as executed:
            with self.assertRaisesRegex(ValueError,'Maven failed'):m.capture(output,'mvn',self.profile)
            executed.assert_called_once()
        self.assertEqual('FAIL',m.read(output/'receipt.json')['status']);self.assertTrue((output/'source.json').is_file())


if __name__=='__main__':unittest.main()
