import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from . import measurement_machine as m,measurement_cohort as cohort
from .test_measurement_m01_set import fixtures as m01_fixtures


def fixture():
    expected,results=m01_fixtures();first=next(iter(expected.values()));actual={k:first[k] for k in ('source','checkoutSha256','java')}
    compiled={}
    for family,name in [('published','published-v51-legacy-strong-r1'),('candidate','candidate-minimum-r1')]:
        compiled[family]={k:copy.deepcopy(expected[name][k]) for k in ('artifacts','classes')}
    value=dict(schema=m.SCHEMA,status='FROZEN_BEFORE_MEASUREMENTS',paidCloud=False,implementation=actual,contract=m.contract(),environment={},
        storageRoot='/fixture',compiled=compiled,build=dict(binding=actual,manifestSha256='c'*64,archiveSha256='d'*64),createdUnixSeconds=1)
    for index,(name,spec) in enumerate(value['contract']['members'].items()):
        if name not in expected:
            plan=spec['profile'];family=spec['family'];jars=copy.deepcopy(compiled['candidate'])
            expected[name]=dict(actual,mode=spec['mode'],measurementProfile=plan,programSha256=m.model.PLAN_SHA,run='local',attempt=1,
                                readParameters=plan.get('parameters',m.options.parameters()),**jars)
            reads=4 if family=='M04' else 1+plan['readCount']+(family=='M03');updates=4 if family=='M04' else 3+plan['releaseUpdate']
            body=dict(status='PASS',qualifiedMeasurement=False,paidCloud=False,case=name,ledger=dict(outcomes={'read':{'SUCCESS':reads},'update':{'SUCCESS':updates}}),
                      execution='recovery-member-physical-replay' if family=='M04' else 'minimum-member-physical-replay')
            results[name]=dict(status='PASS',execution='recovery-portable-member' if family=='M04' else 'minimum-portable-member',
                qualifiedMeasurement=False,paidCloud=False,result=body)
        expected[name]['origin']='/fixture/histories/'+name;results[name]['binding']=copy.deepcopy(expected[name])
        results[name]['domain']=dict(groupId='group-'+str(index),historyId='history-'+str(index));results[name]['manifestSha256']=str(index)
        results[name]['result']['negatives']=copy.deepcopy(value['contract']['negativeRules'][name])
    return value,actual,expected,results


class MeasurementMachineTest(unittest.TestCase):
    def test_exact_28_histories_frozen_contract_and_whole_counts(self):
        value,actual,expected,results=fixture();m.validate_plan(value)
        result=cohort.validate_results(value,actual,expected,results)
        self.assertTrue(result['qualifiedMeasurement']);self.assertFalse(result['hostedAcceptance']);self.assertFalse(result['cloudAcceptance'])
        self.assertEqual((28,27373,2745,2700),tuple(result[k] for k in ('histories','originalReads','originalUpdates','nominalM01Seconds')))
        self.assertEqual(439,sum(len(v) for v in value['contract']['negativeRules'].values()))

    def test_frozen_bounds_profiles_outcomes_and_negatives_cannot_drift(self):
        for change in (lambda v:v['contract']['execution'].__setitem__('businessRetries',1),
                       lambda v:v['contract']['execution'].__setitem__('concurrentHistories',2),
                       lambda v:v['contract']['evidence']['bundle'].__setitem__('expanded',100),
                       lambda v:next(iter(v['contract']['negativeRules'].values())).pop(),
                       lambda v:v['contract']['members'].pop('m03-p65')):
            value,*_=fixture();value=copy.deepcopy(value);change(value)
            with self.assertRaisesRegex(ValueError,'execution contract changed'):m.validate_plan(value)
        value,*_=fixture();value['compiled']['published']['artifacts']['general-search-engine-5.1.0.jar']='0'*64
        with self.assertRaisesRegex(ValueError,'published controls changed'):m.validate_plan(value)

    def test_missing_histories_mixed_source_attempt_build_and_freshness_fail(self):
        for fault,reason in [('missing','incomplete full cohort'),('source','source/profile'),('attempt','mixed run/attempt'),
                             ('artifact','artifact/consumer drift'),('reuse','reused domain/history'),('negative','exact negatives'),
                             ('count','original call counts'),('execution','portable execution identity')]:
            value,actual,expected,results=copy.deepcopy(fixture());name='follower-snapshot-carried-token'
            if fault=='missing':results.pop(name)
            if fault=='source':expected[name]['source']='f'*40
            if fault=='attempt':expected[name]['attempt']=2;results[name]['binding']['attempt']=2
            if fault=='artifact':expected[name]['classes']['consumer/Fixture.class']='f'*64
            if fault=='reuse':results[name]['domain']['groupId']=next(iter(results.values()))['domain']['groupId']
            if fault=='negative':results[name]['result']['negatives'].pop()
            if fault=='count':results[name]['result']['ledger']['outcomes']['read']['SUCCESS']=3
            if fault=='execution':results[name]['execution']='synthetic-success'
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,reason):cohort.validate_results(value,actual,expected,results)

    def test_failed_execution_is_not_retried_and_retains_partial_receipt(self):
        value,actual,expected,_=fixture();launched=[]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);value['storageRoot']=str(root)
            def prepare(case,mode,m01_repetition):
                case.mkdir();name=case.name;b=copy.deepcopy(expected[name]);b['origin']=str(case);return b,'unused','unused'
            def execute(case,binding,cp):launched.append(case.name);raise ValueError('original history failed')
            with patch.object(m,'admit',return_value=(value,actual)),patch.object(m,'verify_launch'),\
                 patch.object(cohort.runtime,'prepare',side_effect=prepare),patch.object(cohort.m01,'execute_prepared',side_effect=execute),\
                 patch.object(cohort.shutil,'disk_usage',return_value=type('Disk',(),{'free':100<<30})()),patch.object(cohort,'replay_member') as replay:
                with self.assertRaisesRegex(ValueError,'original history failed'):cohort.run()
            self.assertEqual(1,len(launched));replay.assert_not_called();receipt=json.loads((root/'cohort.json').read_bytes())
            self.assertEqual('FAIL',receipt['status']);self.assertEqual([],receipt['completed']);self.assertEqual('original history failed',receipt['failure']['message'])

    def test_exact_git_parent_and_archived_checkout_prevent_self_referential_or_mixed_freeze(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            def git(*args):return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.DEVNULL).decode().strip()
            def commit():
                git('add','.');git('-c','user.name=MeasurementFixture','-c','user.email=measurement@example.invalid','commit','-qm','fixture')
                return git('rev-parse','HEAD')
            git('init','-q');(root/'source.txt').write_text('original\n');script=root/'script.sh';script.write_text('exit 0\n');script.chmod(0o755)
            parent=commit();value,_,_,_=fixture();java=value['implementation']['java'];implementation=m.committed_binding(root,parent,java)
            value['implementation']=implementation;value['build']['binding']=implementation
            plan=root/m.PLAN;plan.parent.mkdir(parents=True);plan.write_bytes(m.encoded(value)+b'\n');source=commit();actual=m.committed_binding(root,source,java)
            self.assertEqual(actual,m.verify_launch(value,actual,root))
            expected=[['script.sh',True,m.digest(script.read_bytes())],['source.txt',False,m.digest((root/'source.txt').read_bytes())]]
            self.assertEqual(m.build.digest(m.build.encoded(expected)),implementation['checkoutSha256'])
            wrong=dict(actual,checkoutSha256='f'*64)
            with self.assertRaisesRegex(ValueError,'checkout binding differs'):m.verify_launch(value,wrong,root)
            (root/'source.txt').write_text('changed\n');later=commit();later_binding=m.committed_binding(root,later,java)
            with self.assertRaisesRegex(ValueError,'freeze parent changed'):m.verify_launch(value,later_binding,root)


if __name__=='__main__':unittest.main()
