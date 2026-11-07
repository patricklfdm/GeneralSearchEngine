"""Synthetic cohort orchestration; no native/resource qualification credit."""
import copy
import io
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import phase3_resource_cohort as m


class ResourceCohortTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.inputs=self.root/'inputs';self.inputs.mkdir();self.index=self.root/'index.json'
        self.source=dict(head='a'*40,files={'scripts/v53/synthetic.py':m.h.digest(b'synthetic source')})
        self.pins=dict(sourceSha256='a'*64,buildSha256='b'*64,toolchainSha256='c'*64,readerSha256='d'*64)
        self.value=dict(schema=m.INDEX_SCHEMA,source=self.source['head'],members={})
        self.seen=[];self.modules={};self.real=m.adapters()
        for name,(_,profile,_,_) in m.MEMBERS.items():
            path=self.inputs/name;path.mkdir();work=path/'workspace'
            (work/'scripts/v53').mkdir(parents=True);(work/'scripts/v53/synthetic.py').write_bytes(b'synthetic source')
            reports=work/m.h.MODULE/'target/surefire-reports';reports.mkdir(parents=True)
            (reports/'TEST-synthetic.xml').write_bytes(b'synthetic JUnit observation, not a native result')
            raw=path/'raw';raw.mkdir();(raw/'original.bin').write_bytes(name.encode())
            m.h.save(path/'source.json',self.source);m.h.save(path/'receipt.json',dict(status='PARTIAL'))
            self.value['members'][name]=dict(profile=profile,pins=dict(self.pins))
            self.modules[name]=SimpleNamespace(SCHEMA=self.real[name].SCHEMA,
                check_pins=self.check_pins,member=self.member,check_result=self.check_qualification,
                verify=lambda output,path,profile,pins,n=name:self.verify(n,output,path,profile,pins))
        m.h.save(self.index,self.value)
        for p in (patch.object(m,'adapters',return_value=self.modules),
                  patch.object(m.seeds,'checkout_source',side_effect=lambda sha:self.source)):
            p.start();self.addCleanup(p.stop)

    def check_pins(self,pins):
        m.need(type(pins) is dict and set(pins)==set(self.pins) and
               all(m.seeds.shared.m.hash_field(v) for v in pins.values()),'synthetic explicit pins')
        return dict(files=self.source['files'])

    def member(self,path,profile,pins):
        return dict(raw=path/'raw',inventory=m.h.inventory(path/'raw'),
                    producerReceiptSha256=m.h.digest((path/'receipt.json').read_bytes()))

    def check_qualification(self,value,profile):
        m.need(value==dict(synthetic=True,profile=profile),'synthetic owning original and negatives')

    def result(self,name,path,profile,pins):
        _,_,scope,qualified=m.MEMBERS[name];member=self.member(path,profile,pins)
        result=dict(schema=self.real[name].SCHEMA,status='PASS',scope=scope,profile=profile,**pins,
            producerReceiptSha256=member['producerReceiptSha256'],
            rawInventorySha256=m.h.digest(m.h.snapshot.f.canonical(member['inventory'])),
            originalFirst=True,originalPreserved=True,combinedResourcesQualified=False,phase3Complete=False,
            qualification=dict(synthetic=True,profile=profile))
        result[qualified]=True
        if name=='capacity-completion':result.update(continuationQualified=True,historicalPrefixQualified=False)
        if name=='queue-completion':result['queuePressureQualified']=True
        return result

    def verify(self,name,output,path,profile,pins):
        self.seen.append(name);output.mkdir();result=self.result(name,path,profile,pins)
        m.h.save(output/'receipt.json',result);return result

    def run_set(self,output='result',**kwargs):
        with redirect_stdout(io.StringIO()):return m.run(self.index,self.inputs,self.root/output,**kwargs)

    def test_catalogue_requires_actual_full_profiles_and_isolated_queue_is_not_completion(self):
        for name,module in self.real.items():
            module.selected(m.MEMBERS[name][1])
        self.assertEqual('admittedRemoveFinishesAfterRealJointQueuePressure',self.real['queue-completion'].METHOD)
        self.assertEqual('capacity-231',m.MEMBERS['capacity-completion'][1])
        self.assertEqual(5,len(m.MEMBERS));self.assertNotEqual(m.MEMBERS['source-queue'],m.MEMBERS['queue-completion'])

    def test_every_whole_original_replayed_once_and_no_combined_or_phase_claim(self):
        result=self.run_set(expected_common={**self.pins,'repositorySha256':'e'*64})
        self.assertEqual(list(m.MEMBERS),self.seen);self.assertEqual(set(m.MEMBERS),set(result['members']))
        self.assertTrue(result['allSupplementalOriginalsReplayed']);self.assertEqual('PARTIAL',result['status'])
        for key in ('phase3Complete','combinedPeakResourcesQualified','resourceWorkflowExecutionAttested',
                    'historicalCapacityPrefixQualified','frozenScenarioCoverageQualified'):self.assertIs(False,result[key])
        m.unchanged(self.index,self.inputs,self.root/'result',result)

    def test_missing_extra_or_smoke_member_stops_before_first_replay(self):
        for at,kind in enumerate(('missing','extra','smoke')):
            value=copy.deepcopy(self.value)
            if kind=='missing':value['members'].pop('queue-completion')
            elif kind=='extra':value['members']['optional']=copy.deepcopy(value['members']['source-queue'])
            else:value['members']['capacity-completion']['profile']='replay-smoke-1'
            m.h.save(self.index,value)
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.run_set(str(at))
            self.assertEqual([],self.seen)
            self.assertEqual('FAIL',m.seeds.read(self.root/str(at)/'receipt.json')['status'])

    def test_all_pins_checked_before_any_expensive_replay_and_against_history_seed(self):
        for at,key in enumerate(m.COMMON_PINS):
            value=copy.deepcopy(self.value);value['members']['queue-completion']['pins'][key]='e'*64;m.h.save(self.index,value)
            with self.assertRaisesRegex(ValueError,'mixed source/build/tools'):self.run_set(str(at))
        m.h.save(self.index,self.value)
        with self.assertRaisesRegex(ValueError,'differs from history seed'):
            self.run_set('history',expected_common=dict(self.pins,buildSha256='0'*64))
        self.assertEqual([],self.seen)

    def test_source_file_or_manifest_drift_cannot_keep_same_head(self):
        path=self.inputs/'queue-completion'/'workspace/scripts/v53/synthetic.py';path.write_bytes(b'drift')
        with self.assertRaisesRegex(ValueError,'recorded source changed'):self.run_set()
        self.assertEqual([],self.seen)

    def test_changed_source_inventory_rejects_even_with_same_sha_label(self):
        path=self.inputs/'queue-completion';work=path/'workspace/scripts/v53/extra.py';work.write_bytes(b'extra')
        source=copy.deepcopy(self.source);source['files']['scripts/v53/extra.py']=m.h.digest(b'extra');m.h.save(path/'source.json',source)
        with self.assertRaisesRegex(ValueError,'not exact checkout'):self.run_set()
        self.assertEqual([],self.seen)

    def test_owning_failure_preserved_and_never_retried(self):
        def failure(output,path,profile,pins):
            self.seen.append('maximum-image');output.mkdir();m.h.save(output/'receipt.json',dict(status='FAIL'))
            raise ValueError('original maximum-image rejection')
        self.modules['maximum-image'].verify=failure
        with self.assertRaisesRegex(ValueError,'original maximum-image rejection'):self.run_set()
        self.assertEqual(['required-four','maximum-image'],self.seen)
        failure=m.seeds.read(self.root/'result/maximum-image/failure.json')
        self.assertTrue((self.root/'result/maximum-image'/failure['retainedScratch']/'replay/receipt.json').is_file())
        self.assertFalse(m.seeds.read(self.root/'result/receipt.json')['allSupplementalOriginalsReplayed'])

    def test_forged_qualification_or_summed_peak_claim_rejected(self):
        name='queue-completion';before=m.inspect(self.index,self.inputs)['originals'][name]
        base=self.result(name,self.inputs/name,m.MEMBERS[name][1],self.pins)
        for key,value in [('scope','source-queue-component-only'),('phase3Complete',True),
                          ('combinedResourcesQualified',True),('nativeFinalCompleted',1),('queuePressureQualified',False),
                          ('rawInventorySha256','0'*64),('qualification',dict(status='PASS'))]:
            with self.subTest(key=key),self.assertRaises(ValueError):m.check_result(name,dict(base,**{key:value}),self.pins,before)

    def test_prior_pass_receipt_cannot_replace_owning_replay(self):
        (self.inputs/'maximum-image'/'receipt.json').write_text('{"status":"PASS"}')
        self.modules['maximum-image'].check_result=lambda value,profile:(_ for _ in ()).throw(ValueError('missing original negatives'))
        with self.assertRaisesRegex(ValueError,'missing original negatives'):self.run_set()
        self.assertIn('maximum-image',self.seen)

    def test_earlier_original_and_junit_rechecked_after_last_replay(self):
        original=self.modules['queue-completion'].verify
        def changed(output,path,profile,pins):
            result=original(output,path,profile,pins)
            reports=self.inputs/'required-four'/'workspace'/m.h.MODULE/'target/surefire-reports'
            (reports/'TEST-synthetic.xml').write_bytes(b'changed while another original replayed');return result
        self.modules['queue-completion'].verify=changed
        with self.assertRaisesRegex(ValueError,'originals changed during replay'):self.run_set()

    def test_post_observation_rechecks_raw_and_owning_receipts(self):
        result=self.run_set();path=self.root/'result/required-four/receipt.json';raw=path.read_bytes();path.write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError,'owning receipt changed'):m.unchanged(self.index,self.inputs,self.root/'result',result)
        path.write_bytes(raw);(self.inputs/'required-four/raw/original.bin').write_bytes(b'changed original')
        with self.assertRaisesRegex(ValueError,'originals changed after'):m.unchanged(self.index,self.inputs,self.root/'result',result)

    def test_no_overwrite_symlinks_or_input_alias(self):
        result=self.run_set();raw=(self.root/'result/receipt.json').read_bytes()
        with self.assertRaises(FileExistsError):self.run_set()
        self.assertEqual(raw,(self.root/'result/receipt.json').read_bytes())
        with self.assertRaisesRegex(ValueError,'overlaps'):self.run_set('inputs/inside')
        path=self.inputs/'queue-completion';path.rename(self.root/'held');path.symlink_to(self.root/'held')
        with self.assertRaises(ValueError):self.run_set('linked')


if __name__=='__main__':unittest.main()
