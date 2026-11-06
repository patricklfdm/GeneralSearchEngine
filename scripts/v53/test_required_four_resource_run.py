"""Synthetic orchestration guards; these tests confer no native history credit."""
import copy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from . import required_four_resource_run as m
from .test_process_toolchain import record


def replay():
    original=dict(status='PASS',profile=m.PROFILE,nativeBudgetAccountingQualified=True,physicalPeakQualified=False,
                  wholeRuntimeResourcesQualified=False,finalSourceCohortQualified=False,phase3Complete=False,
                  joinedHandoffResources=dict(status='PASS',continuousHandoffQualified=True,phase3Complete=False),
                  joinedFileResources=dict(status='PASS',originalFileCustodyQualified=True,phase3Complete=False))
    return dict(schema=m.gate.SCHEMA,status='PASS',profile=m.PROFILE,original=original,
                negatives={f:[dict(case=n,status='REJECTED',reason=r) for n,r in cases.items()] for f,cases in m.gate.NEGATIVES.items()},
                originalFirst=True,originalPreserved=True,combinedResourcesQualified=False,phase3Complete=False)


class RequiredFourResourceRunTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
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
        raw=work/m.h.MODULE/'target/v53-native-dispatch/run-00000000-0000-0000-0000-000000000001';raw.mkdir(parents=True)
        for name in ('events.json','wire.json','original-plan.gsbp','joining-continuation-result.json','resource-transition-captures/index.json','storage-transfer-captures/index.json'):
            p=raw/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'{}')
        (raw/'synthetic.bin').write_bytes(b'not native evidence');return raw

    def producer(self,path):
        work=path/'workspace';source=self.source(None,work);m.h.save(path/'source.json',source)
        raw=self.generated(work);m.h.save(path/'reader.json',self.reader);m.h.save(path/'toolchain.json',record())
        m.h.save(path/'build.json',{n:m.h.inventory(work/n) for n in m.BUILDS});m.h.save(path/'collection.json',m.collect(raw,m.PROFILE))
        for name in ('execution','collection-execution'):m.h.save(path/(name+'.json'),dict(exit=0))
        m.h.save(path/'receipt.json',dict(schema=m.SCHEMA,status='PARTIAL',profile=m.PROFILE,executionStatus='PASS',collectionComplete=True,
            observedResourcesQualified=False,combinedResourcesQualified=False,phase3Complete=False,retries=0,
            execution=dict(exit=0),collectionExecution=dict(exit=0),baseHead='a'*40,readerSha256=self.reader['sha256'],
            command=['mvn',*m.command(m.PROFILE)],junit=m.junit(work/m.h.MODULE/'target/surefire-reports',m.PROFILE),
            raw=raw.relative_to(path).as_posix(),**{k+'Sha256':m.h.digest((path/f).read_bytes()) for k,f in
            [('source','source.json'),('build','build.json'),('toolchain','toolchain.json'),('collection','collection.json')]}))

    def edit(self,name,mutate,path=None):
        p=(path or self.path)/name;value=m.read(p);mutate(value);m.h.save(p,value)

    def test_exact_method_flags_and_no_short_retry_or_budget_override(self):
        command=m.command(m.PROFILE)
        self.assertEqual('-Dtest='+m.CLASS+'#'+m.METHOD,next(v for v in command if v.startswith('-Dtest=')))
        for option in ('joining.requiredFour','publication.resources','resource.transitions','transport.connections','resource.storage.transfers'):
            self.assertIn('-Dv53.'+option+'=true',command)
        self.assertFalse(any('retry' in v.lower() or 'timeout' in v.lower() or 'skipTests' in v for v in command))
        for wrong in ('stable','5-REPLACE','3-ADD',True):
            with self.assertRaisesRegex(ValueError,'explicit profile'):m.command(wrong)

    def test_collection_has_no_acceptance_and_requires_both_original_sidecars(self):
        raw=m.locate(self.path/'workspace',m.PROFILE)
        with patch.object(m.gate,'qualify',side_effect=AssertionError('no replay in collection')):
            value=m.collect(raw,m.PROFILE)
        self.assertEqual('PARTIAL',value['status']);self.assertFalse(value['observedResourcesQualified'])
        for directory in ('resource-transition-captures','storage-transfer-captures'):
            p=raw/directory/'index.json';data=p.read_bytes();p.unlink()
            with self.assertRaisesRegex(ValueError,'missing capture'):m.collect(raw,m.PROFILE)
            p.write_bytes(data)

    def test_original_and_existing_output_cannot_be_overwritten(self):
        raw=m.locate(self.path/'workspace',m.PROFILE);out=self.root/'collection.json';m.collect_to(out,raw,m.PROFILE)
        with self.assertRaisesRegex(ValueError,'output already exists'):m.collect_to(out,raw,m.PROFILE)
        for output in (raw/'added.json',raw/'events.json'):
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
                            ('observedResourcesQualified',True),('combinedResourcesQualified',True),('phase3Complete',True),
                            ('command',['mvn',*m.command(m.PROFILE)[:-2],'test']),('profile','5-REPLACE'),('execution',dict(exit=False))]):
            copy=self.root/str(i);shutil.copytree(self.path,copy);self.edit('receipt.json',lambda v:v.update({field:value}),copy)
            with self.subTest(field=field),self.assertRaises(ValueError):m.member(copy,m.PROFILE,self.pins)

    def test_source_classes_reader_toolchain_and_raw_are_immutable(self):
        paths=['workspace/scripts/v53/reader.py','workspace/'+m.BUILDS[0]+'/original.class','reader.json','toolchain.json',
               m.read(self.path/'receipt.json')['raw']+'/synthetic.bin']
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

    def test_complete_replay_and_all_exact_negative_families_are_mandatory(self):
        for family in m.gate.NEGATIVES:
            for mutation in ('missing','reason'):
                value=replay()
                if mutation=='missing':value['negatives'][family].pop()
                else:value['negatives'][family][0]['reason']='unrelated error'
                with patch.object(m.gate,'qualify',return_value=value),self.assertRaisesRegex(ValueError,'exact negative families'):
                    m.qualify(self.path,m.PROFILE,self.pins)
        with patch.object(m.gate,'qualify',return_value=replay()):
            value=m.qualify(self.path,m.PROFILE,self.pins)
        self.assertTrue(value['observedResourcesQualified']);self.assertFalse(value['combinedResourcesQualified']);self.assertFalse(value['phase3Complete'])

    def test_original_failure_retained_without_qualification(self):
        out=self.root/'failed'
        with patch.object(m.gate,'qualify',side_effect=ValueError('invalid original')),self.assertRaisesRegex(ValueError,'invalid original'):
            m.verify(out,self.path,m.PROFILE,self.pins)
        self.assertEqual('FAIL',m.read(out/'receipt.json')['status'])

    def test_original_cannot_change_during_replay(self):
        def mutate(raw,progress):
            (raw/'synthetic.bin').write_bytes(b'changed');return replay()
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
        self.assertIn('scripts.v53.required_four_resource_run',commands[1]);m.member(output,m.PROFILE,m.read(output/'pins.json'))

    def test_capture_failure_retains_original_and_never_retries(self):
        output=self.root/'failure'
        with patch.object(m.h,'source_copy',side_effect=self.source),patch.object(m.tc,'capture',return_value=record()),patch.object(m.h,'execute',return_value=dict(exit=1)) as executed:
            with self.assertRaisesRegex(ValueError,'Maven failed'):m.capture(output,'mvn',m.PROFILE)
        executed.assert_called_once();self.assertEqual('FAIL',m.read(output/'receipt.json')['status']);self.assertTrue((output/'source.json').is_file())


if __name__=='__main__':unittest.main()
