"""Synthetic orchestration guards; these tests confer no native history credit."""
import copy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from . import maximum_transition_run as m
from .test_process_toolchain import record


def replay():
    return dict(status='PASS',mode='maximum',imageBytes=m.gate.maximum.NATIVE_MAXIMUM,slots=10,
        removalComplete=True,publicRuntime=False,maximumBytes=True,admittedLearner=False,
        fullMetadataPressure=False,phase3Complete=False,negativeScope='original-first-receiver-components',
        peak=dict(metadata=35*1024**2,staging=7*m.gate.maximum.NATIVE_MAXIMUM+4096,queued=0,leases=16,
                  counts=dict(APPLICATION=7,GENERATION=2,SOURCE=5,JOURNAL=1,MISC=1)),
        negativeCases=[dict(case=n,status='REJECTED',reason='maximum transition exact receiver refusal') for n in m.gate.NEGATIVE_NAMES])


class MaximumTransitionRunTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        capacity=patch('scripts.v53.maximum_transition_capacity.check',return_value={'status':'SYNTHETIC'});capacity.start();self.addCleanup(capacity.stop)
        self.reader=dict(files={'scripts/v53/reader.py':m.h.digest(b'synthetic reader')},sha256='f'*64)
        p=patch.object(m,'reader_manifest',return_value=self.reader);p.start();self.addCleanup(p.stop)
        self.path=self.root/'producer';self.producer(self.path)
        self.pins={k+'Sha256':m.h.digest((self.path/(k+'.json')).read_bytes()) for k in ('source','build')}
        self.pins.update(toolchainSha256=m.tc.pin((self.path/'toolchain.json').read_bytes()),readerSha256=self.reader['sha256'])

    def source(self,repo,work):
        (work/'scripts/v53').mkdir(parents=True);(work/'scripts/v53/reader.py').write_bytes(b'synthetic reader')
        return dict(head='a'*40,files=self.reader['files'])

    def generated(self,work):
        for name in m.BUILDS:
            p=work/name;p.mkdir(parents=True);(p/'original.class').write_bytes(b'synthetic classes')
        reports=work/m.h.MODULE/'target/surefire-reports';reports.mkdir()
        cls=m.PACKAGE+m.CLASS;suite=ET.Element('testsuite',dict(name=cls,tests='1',failures='0',errors='0',skipped='0'))
        ET.SubElement(suite,'testcase',dict(classname=cls,name=m.METHOD));ET.ElementTree(suite).write(reports/'TEST-original.xml')
        raw=work/m.h.MODULE/'target/v53-maximum-transition/run-00000000-0000-0000-0000-000000000001';raw.mkdir(parents=True)
        for name in ('source-backup','publication','seven-image-floor','typed-final','receiver-refused'):(raw/name).mkdir()
        for name in ('calibration.image','source.image','peak.json','receiver.json'):(raw/name).write_bytes(b'synthetic')
        m.h.save(raw/'receipt.json',dict(schema='gse-v53-maximum-transition-v1',status='PASS',mode='maximum',
            imageBytes=m.gate.maximum.NATIVE_MAXIMUM,finalValueBytes=12,slots=10,voters=4,generation=1,peakImages=7,publicRuntime=False,phase3Complete=False))
        (raw/'publication/synthetic.bin').write_bytes(b'not native evidence');return raw


    def producer(self,path):
        work=path/'workspace';source=self.source(None,work);m.h.save(path/'source.json',source)
        raw=self.generated(work);m.h.save(path/'reader.json',self.reader);m.h.save(path/'toolchain.json',record())
        m.h.save(path/'build.json',{n:m.h.inventory(work/n) for n in m.BUILDS});m.h.save(path/'collection.json',m.collect(raw,m.PROFILE))
        for name in ('execution','collection-execution'):m.h.save(path/(name+'.json'),dict(exit=0))
        m.h.save(path/'receipt.json',dict(schema=m.SCHEMA,status='PARTIAL',profile=m.PROFILE,executionStatus='PASS',collectionComplete=True,
            maximumImageTransitionQualified=False,combinedResourcesQualified=False,phase3Complete=False,retries=0,
            execution=dict(exit=0),collectionExecution=dict(exit=0),baseHead='a'*40,readerSha256=self.reader['sha256'],
            command=['mvn',*m.command(m.PROFILE)],junit=m.junit(work/m.h.MODULE/'target/surefire-reports',m.PROFILE),
            raw=raw.relative_to(path).as_posix(),**{k+'Sha256':m.h.digest((path/f).read_bytes()) for k,f in
            [('source','source.json'),('build','build.json'),('toolchain','toolchain.json'),('collection','collection.json')]}))

    def edit(self,name,mutate,path=None):
        p=(path or self.path)/name;value=m.read(p);mutate(value);m.h.save(p,value)

    def test_exact_method_flags_and_no_short_retry_or_budget_override(self):
        command=m.command(m.PROFILE)
        self.assertEqual('-Dtest='+m.CLASS+'#'+m.METHOD,next(v for v in command if v.startswith('-Dtest=')))
        self.assertIn('-DargLine=-Xmx4g',command)
        self.assertFalse(any('retry' in v.lower() or 'timeout' in v.lower() or 'skipTests' in v for v in command))
        for wrong in ('diagnostic','replay-smoke-1','5-REPLACE',True):
            with self.assertRaisesRegex(ValueError,'explicit profile'):m.command(wrong)

    def test_collection_has_no_acceptance_and_requires_maximum_shape(self):
        raw=m.locate(self.path/'workspace',m.PROFILE)
        with patch.object(m.gate,'qualify',side_effect=AssertionError('no replay in collection')):value=m.collect(raw,m.PROFILE)
        self.assertEqual('PARTIAL',value['status']);self.assertFalse(value['maximumImageTransitionQualified'])
        for name in ('calibration.image','receiver.json'):
            path=raw/name;data=path.read_bytes();path.unlink()
            with self.assertRaises(ValueError):m.collect(raw,m.PROFILE)
            path.write_bytes(data)
        original=m.read(raw/'receipt.json')
        for key,value in [('mode','diagnostic'),('status','DIAGNOSTIC'),('imageBytes',881),('slots',9),('finalValueBytes',True)]:
            m.h.save(raw/'receipt.json',dict(original,**{key:value}))
            with self.assertRaises(ValueError):m.collect(raw,m.PROFILE)
        m.h.save(raw/'receipt.json',original)

    def test_original_and_existing_output_cannot_be_overwritten(self):
        raw=m.locate(self.path/'workspace',m.PROFILE);out=self.root/'collection.json';m.collect_to(out,raw,m.PROFILE)
        with self.assertRaisesRegex(ValueError,'output already exists'):m.collect_to(out,raw,m.PROFILE)
        for output in (raw/'added.json',raw/'receiver.json'):
            with self.assertRaisesRegex(ValueError,'original separation'):m.collect_to(output,raw,m.PROFILE)
        with self.assertRaisesRegex(ValueError,'original separation'):m.verify(self.path/'added',self.path,m.PROFILE,self.pins)

    def test_exact_pins_and_relocation_without_source_substitution(self):
        first=m.member(self.path,m.PROFILE,self.pins);copy=self.root/'relocated';shutil.copytree(self.path,copy)
        second=m.member(copy,m.PROFILE,self.pins)
        self.assertEqual(first['inventory'],second['inventory']);self.assertEqual(first['producerReceiptSha256'],second['producerReceiptSha256'])
        for name in m.PINS:
            with self.subTest(name=name),self.assertRaises(ValueError):m.member(copy,m.PROFILE,dict(self.pins,**{name:'0'*64}))

    def test_failed_retried_shortened_or_inflated_producer_is_rejected(self):
        for i,(field,value) in enumerate([('status','PASS'),('executionStatus','FAIL'),('retries',1),('retries',False),('collectionComplete',False),
                            ('maximumImageTransitionQualified',True),('combinedResourcesQualified',True),('phase3Complete',True),
                            ('command',['mvn',*m.command(m.PROFILE)[:-2],'test']),('profile','5-REPLACE'),('execution',dict(exit=False))]):
            copy=self.root/str(i);shutil.copytree(self.path,copy);self.edit('receipt.json',lambda v:v.update({field:value}),copy)
            with self.subTest(field=field),self.assertRaises(ValueError):m.member(copy,m.PROFILE,self.pins)

    def test_source_classes_reader_toolchain_and_raw_are_immutable(self):
        paths=['workspace/scripts/v53/reader.py','workspace/'+m.BUILDS[0]+'/original.class','reader.json','toolchain.json',
               m.read(self.path/'receipt.json')['raw']+'/publication/synthetic.bin']
        for i,name in enumerate(paths):
            copy=self.root/str(i);shutil.copytree(self.path,copy);(copy/name).write_bytes(b'{}')
            with self.subTest(name=name),self.assertRaises(ValueError):m.member(copy,m.PROFILE,self.pins)

    def test_extra_history_and_linked_generated_parents_are_rejected(self):
        raw=m.locate(self.path/'workspace',m.PROFILE);(raw.parent/'extra').mkdir()
        with self.assertRaisesRegex(ValueError,'single exact original'):m.member(self.path,m.PROFILE,self.pins)
        (raw.parent/'extra').rmdir()
        for i,name in enumerate((m.BUILDS[0],str(raw.relative_to(self.path/'workspace')))):
            copy=self.root/str(i);shutil.copytree(self.path,copy);p=copy/'workspace'/name;held=self.root/('held-'+str(i));p.rename(held);p.symlink_to(held)
            with self.assertRaises(ValueError):m.member(copy,m.PROFILE,self.pins)

    def test_junit_requires_one_exact_unretried_complete_test(self):
        original=self.path/'workspace'/m.h.MODULE/'target/surefire-reports'
        for label in ('extra','skipped','flakyFailure','rerunFailure','method','failure'):
            copy=self.root/label;shutil.copytree(original,copy);p=copy/'TEST-original.xml';tree=ET.parse(p);suite=tree.getroot()
            if label=='extra':shutil.copy2(p,copy/'TEST-extra.xml')
            elif label=='skipped':suite.set('skipped','1')
            elif label=='method':suite.find('testcase').set('name','shorterPrefix')
            else:ET.SubElement(suite.find('testcase'),label)
            tree.write(p)
            with self.subTest(label=label),self.assertRaises(ValueError):m.junit(copy,m.PROFILE)

    def test_complete_replay_and_all_exact_negatives_are_mandatory(self):
        for mutation in ('missing','reason','reordered'):
            value=replay()
            if mutation=='missing':value['negativeCases'].pop()
            elif mutation=='reason':value['negativeCases'][0]['reason']='unrelated error'
            else:value['negativeCases'].reverse()
            with patch.object(m.gate,'qualify',return_value=value),self.assertRaisesRegex(ValueError,'exact negatives'):
                m.qualify(self.path,m.PROFILE,self.pins)
        for key,value in [('mode','diagnostic'),('maximumBytes',False),('publicRuntime',True),('phase3Complete',True),('slots',9)]:
            with self.assertRaises(ValueError):m.check_result(dict(replay(),**{key:value}),m.PROFILE)
        for key,value in [('metadata',1),('staging',7*m.gate.maximum.NATIVE_MAXIMUM-1),('leases',True),('queued',1),('counts',{})]:
            result=replay();result['peak'][key]=value
            with self.assertRaisesRegex(ValueError,'original peak scope'):m.check_result(result,m.PROFILE)
        with patch.object(m.gate,'qualify',return_value=replay()):value=m.qualify(self.path,m.PROFILE,self.pins)
        self.assertTrue(value['maximumImageTransitionQualified']);self.assertFalse(value['combinedResourcesQualified']);self.assertFalse(value['phase3Complete'])

    def test_original_failure_retained_without_qualification(self):
        out=self.root/'failed'
        with patch.object(m.gate,'qualify',side_effect=ValueError('invalid original')),self.assertRaisesRegex(ValueError,'invalid original'):
            m.verify(out,self.path,m.PROFILE,self.pins)
        self.assertEqual('FAIL',m.read(out/'receipt.json')['status'])

    def test_original_cannot_change_during_replay(self):
        def mutate(raw):
            (raw/'publication/synthetic.bin').write_bytes(b'changed');return replay()
        with patch.object(m.gate,'qualify',side_effect=mutate),self.assertRaisesRegex(ValueError,'original collection'):
            m.qualify(self.path,m.PROFILE,self.pins)

    def test_capture_uses_one_whole_test_and_source_bound_collector(self):
        output=self.root/'capture';commands=[]
        def execute(args,work,log,**kwargs):
            commands.append(args);log.write_text('synthetic execution')
            if len(commands)==1:self.generated(work)
            else:m.h.save(output/'collection.json',m.collect(m.locate(work,m.PROFILE),m.PROFILE))
            return dict(exit=0)
        with patch.object(m.h,'source_copy',side_effect=self.source),patch.object(m.tc,'capture',return_value=record()),patch.object(m.h,'execute',side_effect=execute):
            result=m.capture(output,'mvn',m.PROFILE)
        self.assertEqual('PARTIAL',result['status']);self.assertEqual(2,len(commands));self.assertEqual(['mvn',*m.command(m.PROFILE)],commands[0])
        self.assertIn('scripts.v53.maximum_transition_run',commands[1]);m.member(output,m.PROFILE,m.read(output/'pins.json'))

    def test_capture_failure_retains_original_and_never_retries(self):
        output=self.root/'failure'
        with patch.object(m.h,'source_copy',side_effect=self.source),patch.object(m.tc,'capture',return_value=record()),patch.object(m.h,'execute',return_value=dict(exit=1)) as executed:
            with self.assertRaisesRegex(ValueError,'Maven failed'):m.capture(output,'mvn',m.PROFILE)
        executed.assert_called_once();self.assertEqual('FAIL',m.read(output/'receipt.json')['status']);self.assertTrue((output/'source.json').is_file())

    def test_capacity_failure_happens_before_source_copy_or_execution(self):
        output=self.root/'capacity-failed'
        with patch('scripts.v53.maximum_transition_capacity.check',side_effect=ValueError('capacity unavailable')),patch.object(m.h,'source_copy') as source,patch.object(m.h,'execute') as execute:
            with self.assertRaisesRegex(ValueError,'capacity unavailable'):m.capture(output,'mvn',m.PROFILE)
            source.assert_not_called();execute.assert_not_called()
        self.assertEqual('FAIL',m.read(output/'receipt.json')['status'])


if __name__=='__main__':unittest.main()
