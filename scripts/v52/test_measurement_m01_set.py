import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import measurement_m01_set as s,measurement_model as model,measurement_m01 as m


def fixtures():
    controls=json.loads((model.PLAN.parent/'published-controls.json').read_text())
    artifacts={v['artifact']+'-'+v['version']+'.jar':v['sha256'] for v in controls['artifacts']}
    expected={};members={}
    for index,(mode,repetition) in enumerate(s.MEMBERS):
        jars=artifacts if mode.startswith('published') else {k:v for k,v in artifacts.items() if k.endswith('-4.4.0.jar')}
        if not mode.startswith('published'):jars=dict(jars,**{'general-search-engine-5.2.0-SNAPSHOT.jar':'1'*64,'general-search-engine-replication-5.2.0-SNAPSHOT.jar':'2'*64})
        key=s.name(mode,repetition);binding=dict(mode=mode,measurementProfile=m.profile(mode,repetition),programSha256=model.PLAN_SHA,
            readParameters=s.options.parameters(),
            source='a'*40,checkoutSha256='b'*64,java={'java.runtime.version':'21-test','java.vendor':'test'},run='local',attempt=1,
            origin='/fixture/'+key,artifacts=dict(jars),classes={'consumer/Fixture.class':'3'*64})
        expected[key]=binding
        members[key]=dict(status='PASS',execution='m01-portable-member',qualifiedMeasurement=False,paidCloud=False,binding=copy.deepcopy(binding),
            domain=dict(groupId='group-'+str(index),historyId='history-'+str(index)),manifestSha256=str(index),
            result=dict(status='PASS',mode=mode,repetition=repetition,execution='m01-member-physical-replay',qualifiedMeasurement=False,paidCloud=False,
                        windows=dict(offered=1980,completed=1980),ledger=dict(outcomes={'read':{'SUCCESS':1801},'update':{'SUCCESS':180}})))
    return expected,members


class MeasurementM01SetTest(unittest.TestCase):
    def test_cloud_invocations_must_be_independently_selected_and_local_default_stays_strict(self):
        values,members=fixtures();invocations={}
        for key,binding in values.items():
            invocation=dict(run=str(100+binding['measurementProfile']['repetition']),attempt=2)
            binding.update(invocation);members[key]['binding'].update(invocation);invocations[key]=invocation
        with self.assertRaisesRegex(ValueError,'mixed source'):s.validate_results(members,values)
        result=s.validate_results(members,values,invocations=invocations)
        self.assertEqual(15,result['histories']);self.assertNotIn('run',result['cohort'])
        key=next(iter(values));values[key]['attempt']+=1
        with self.assertRaisesRegex(ValueError,'original admitted invocation'):s.bindings(values,invocations=invocations)
        for wrong in ({},dict(invocations,extra={'run':'1','attempt':1}),dict(invocations,**{key:{'run':'1','attempt':True}})):
            with self.assertRaisesRegex(ValueError,'admitted invocation map'):s.bindings(values,invocations=wrong)

    def test_full_set_counts_original_offers_and_does_not_claim_complete_measurement(self):
        expected,members=fixtures();result=s.validate_results(members,expected)
        self.assertEqual(15,result['histories']);self.assertEqual(29700,result['completedOfferedCalls'])
        self.assertEqual(27000,result['offeredReadCalls']);self.assertEqual(2700,result['offeredUpdateCalls']);self.assertEqual(15,result['setupStrongReads'])
        self.assertEqual(2700,result['nominalOfferedSeconds']);self.assertFalse(result['qualifiedMeasurement']);self.assertFalse(result['paidCloud'])

    def test_missing_extra_or_substituted_modes_and_repetitions_fail(self):
        for change,reason in (
            (lambda v:v.pop(next(iter(v))),'member set'),
            (lambda v:v.__setitem__('extra',next(iter(v.values()))),'member set'),
            (lambda v:next(iter(v.values()))['measurementProfile'].__setitem__('repetition',2),'member identity')):
            values,_=fixtures();change(values)
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):s.bindings(values)

    def test_source_checkout_jvm_run_attempt_and_artifact_drift_reject(self):
        for field,value,reason in (('source','c'*40,'mixed source'),('checkoutSha256','c'*64,'mixed source'),('java',{},'mixed source'),
                                  ('run','other','mixed source'),('attempt',2,'mixed source'),('attempt',True,'attempt shape')):
            values,_=fixtures();values[s.name(model.MODES[-1],3)][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,reason):s.bindings(values)
        for field,key in (('artifacts','general-search-engine-5.2.0-SNAPSHOT.jar'),('classes','consumer/Fixture.class')):
            values,_=fixtures();values[s.name(model.MODES[-1],3)][field][key]='4'*64
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'mixed artifact'):s.bindings(values)
        values,_=fixtures();next(iter(values.values()))['artifacts']['general-search-engine-5.1.0.jar']='4'*64
        with self.assertRaisesRegex(ValueError,'published control'):s.bindings(values)

    def test_reused_origin_group_history_and_manifest_are_not_fresh_repetitions(self):
        expected,members=fixtures();first,second=list(expected)[:2];expected[second]['origin']=expected[first]['origin']
        with self.assertRaisesRegex(ValueError,'member origin'):s.bindings(expected)
        for field in ('groupId','historyId','manifestSha256'):
            expected,members=fixtures()
            if field=='manifestSha256':members[second][field]=members[first][field]
            else:members[second]['domain'][field]=members[first]['domain'][field]
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'reused history'):s.validate_results(members,expected)

    def test_member_completion_and_binding_are_required_after_replay(self):
        for change in (lambda v:v.__setitem__('status','PARTIAL'),lambda v:v['binding'].__setitem__('attempt',2),
                       lambda v:v['result']['windows'].__setitem__('completed',1979)):
            expected,members=fixtures();change(next(iter(members.values())))
            with self.assertRaisesRegex(ValueError,'member replay|result identity/count'):s.validate_results(members,expected)

    def test_mixed_source_is_rejected_before_any_expensive_replay(self):
        values,_=fixtures();values[s.name(model.MODES[-1],3)]['attempt']=2
        with patch.object(s,'portable_member') as replay,self.assertRaisesRegex(ValueError,'mixed source'):
            s.replay_set({},values,'unused')
        replay.assert_not_called()

    def test_raw_relocated_results_and_complete_negatives_must_match(self):
        for problem,reason in (('different','relocated result'),('missing','incomplete negative')):
            with self.subTest(problem=problem),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);source=root/'source';source.mkdir();(source/'node-1').mkdir();(source/'node-1/manifest.gsr').write_bytes(b'fixture')
                scenario=dict(initialRead='node-1-g1-1',leader='node-1');(source/'scenario.json').write_bytes(s.encoded(scenario))
                mode=model.MODES[-1];cases=s.evidence.negative_cases(mode,scenario['initialRead'],scenario['leader'])
                result=dict(status='PASS',negatives=[dict(case=v[0],status='REJECTED',reason=v[4]) for v in cases])
                if problem=='missing':result['negatives'].pop()
                other=copy.deepcopy(result)
                if problem=='different':other['negatives'][0]['reason']='unrelated error'
                with patch.object(s.evidence,'replay',side_effect=[result,other]),self.assertRaisesRegex(ValueError,reason):
                    s.portable_member(source,{'mode':mode},root/'out')
                receipt=json.loads((root/'out/receipt.json').read_text());self.assertEqual('FAIL',receipt['status'])
                self.assertTrue((root/'out/history.tar.gz').is_file());self.assertTrue((root/'out/relocated/node-1/manifest.gsr').is_file())

    def test_failed_member_preserves_prior_receipts_without_replaying_it(self):
        expected,members=fixtures();keys=list(expected);inputs={key:'/fixture/'+key for key in keys};calls=[]
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'output'
            def replay(source,binding,path):
                key=Path(source).name;calls.append(key)
                if len(calls)==3:raise ValueError('retained member failure')
                path.mkdir();(path/'receipt.json').write_bytes(s.encoded(members[key]));return members[key]
            with patch.object(s,'portable_member',side_effect=replay),self.assertRaisesRegex(ValueError,'retained member failure'):
                s.replay_set(inputs,expected,output)
            self.assertEqual(keys[:3],calls)
            receipt=json.loads((output/'receipt.json').read_text());self.assertEqual(keys[:2],receipt['completedMembers'])
            self.assertTrue(all((output/key/'receipt.json').is_file() for key in keys[:2]))


if __name__=='__main__':unittest.main()
