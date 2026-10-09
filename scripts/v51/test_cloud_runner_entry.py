from contextlib import ExitStack
from copy import deepcopy
import inspect
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_runner_entry as e, cloud_runner_admission_qualification as q
from . import test_cloud_runner_prepared as prepared_tests
from . import performance_model as m, remote_command as c


def options(f, mode):
    env=dict(f['env'],GITHUB_RUN_ATTEMPT='1',RUNNER_EXPERIMENT=mode,RUNNER_STORAGE_REQUEST='',RUNNER_STORAGE_CONFIRMATION='')
    env.update(RUNNER_EXPERIMENT_QUOTE='',RUNNER_PREPARED_RUN='',RUNNER_EXPERIMENT_CONFIRMATION='')
    if mode=='prepare':env['RUNNER_EXPERIMENT_QUOTE']=m.canonical(dict(prices=f['value']['prices'],maximumCostMicrousd=q.COST,sequence='d'*32)).decode()
    if mode=='run':env.update(RUNNER_PREPARED_RUN='444',RUNNER_EXPERIMENT_CONFIRMATION=f['approved']['planSha256'])
    return env


class EntryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frozen=e.admission.workload.load();loader=patch.object(e.admission.workload,'load',side_effect=lambda:deepcopy(frozen))
        loader.start();cls.addClassCleanup(loader.stop)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.f=q.fixture(self.root/'input')
        guest=e.guest_setup.generate(self.root/'keys','b'*32);self.secret=(self.root/'keys/identity').read_text()
        v=self.f['value'];self.f['value']=e.admission.plan(self.f['cfg'],v['artifacts'],guest,v['prices'],None,
            sequence='d'*32,now=self.f['clock'].wall(),maximum_cost=q.COST)
        self.f['approved']=e.admission.approval_template(self.f['value']);self.f['approved']['confirmed']=True
        self.env=options(self.f,'prepare');self.env['RUNNER_TEMP']=str(self.root)
        self.binding=e.precheck.identity(self.f['cfg'],self.env,q.pq.SOURCE,q.pq.SOURCE)

    def call(self, mode, output='entry'):
        fn=e.prepare_network if mode=='prepare' else e.run_network
        return fn(self.f['cfg'],self.env,q.pq.SOURCE,q.pq.SOURCE,self.f['preflight'],self.f['root'],self.root/output,self.secret)

    def dependencies(self, stack):
        stack.enter_context(patch.object(e.time,'time',side_effect=self.f['clock'].wall))
        current=stack.enter_context(patch.object(e,'current',return_value=(self.binding,dict(expiresAt=self.f['clock'].wall()+500),self.f['github'])))
        stack.enter_context(patch.object(e.admission.build,'binding',return_value=self.f['binding']))
        original=e.admission.artifacts.verify
        stack.enter_context(patch.object(e.admission.artifacts,'verify',side_effect=lambda root,github,binding:original(root,github,binding,controls=self.f['controls'])))
        stack.enter_context(patch.object(e.ci,'github',side_effect=lambda key:deepcopy(self.f['data'][key])))
        def collect(root, github):
            Path(root).mkdir(parents=True)
            for name in ('build.zip','package.zip','artifacts.json','build-job.json'):shutil.copyfile(self.f['originals']/name,Path(root)/name)
        stack.enter_context(patch.object(e.admission.artifacts,'collect',side_effect=collect))
        return current

    def setup_run(self):
        self.env=options(self.f,'run');self.env['RUNNER_TEMP']=str(self.root)
        _,archive,data=prepared_tests.producing_fixture(self.f,self.root/'producer');self.f['data'].update(data)
        self.f['clock'].sleep(3)
        return archive

    def test_default_mode_is_read_only_and_partial_inputs_fail(self):
        env=options(self.f,'off');self.assertEqual('off',e.selection(env))
        for field,value in (('RUNNER_EXPERIMENT_QUOTE','{}'),('RUNNER_PREPARED_RUN','444'),('RUNNER_EXPERIMENT_CONFIRMATION','a'*64)):
            with self.subTest(field=field),self.assertRaises(ValueError):e.selection(dict(env,**{field:value}))

    def test_prepare_run_require_exclusive_precheck_and_first_attempt(self):
        for mode in ('prepare','run'):
            env=options(self.f,mode);self.assertEqual(mode,e.selection(env))
            for field,value in (('RUNNER_PERMISSION_PRECHECK','false'),('RUNNER_STORAGE_REQUEST','a'*64),
                ('RUNNER_STORAGE_CONFIRMATION','b'*64),('GITHUB_RUN_ATTEMPT','2')):
                with self.subTest(mode=mode,field=field),self.assertRaises(ValueError):e.selection(dict(env,**{field:value}))

    def test_prepare_quote_closed_fields_and_run_id_are_not_commands(self):
        env=options(self.f,'prepare')
        for text in ('{}','{"sequence":"a","sequence":"b"}','x'*16385):
            with self.assertRaises(ValueError):e.selection(dict(env,RUNNER_EXPERIMENT_QUOTE=text))
        env=options(self.f,'run')
        for value in ('222','../444','444;echo sentinel','0','-1'):
            with self.assertRaises(ValueError):e.selection(dict(env,RUNNER_PREPARED_RUN=value))

    def test_guard_rejects_non_master_identity_before_any_network(self):
        for field,value in (('GITHUB_REF','refs/heads/feature'),('GITHUB_SHA','b'*40),('GITHUB_JOB','observations')):
            with patch.object(e.ci,'github') as network,self.assertRaises(ValueError):
                e.guard(self.f['cfg'],dict(self.env,**{field:value}),q.pq.SOURCE,q.pq.SOURCE)
            network.assert_not_called()

    def test_private_key_is_temporary_owned_and_removed_even_on_error(self):
        seen=[]
        with self.assertRaisesRegex(ValueError,'synthetic stop'):
            with e.private_key(self.secret,self.root) as (key,public):
                self.assertEqual(0o600,key.stat().st_mode&0o777);seen.append(key)
                self.assertEqual(self.f['value']['resourcePlan']['guestAccess']['publicKey'],public)
                raise ValueError('synthetic stop')
        self.assertFalse(seen[0].parent.exists())
        for value in ('','secret sentinel','x'*4097):
            with self.assertRaises(ValueError):
                with e.private_key(value,self.root):self.fail('bad private key admitted')

    def test_private_directory_cannot_be_inside_uploaded_evidence(self):
        root=self.root/'evidence';root.mkdir();(root/'private').mkdir()
        for parent in (root,root/'private'):
            with self.assertRaises(ValueError):e.secret_parent({'RUNNER_TEMP':str(parent)},root)
        self.assertEqual(self.root,e.secret_parent({'RUNNER_TEMP':str(self.root)},root))

    def test_current_precheck_expiry_is_checked_after_ci_reads(self):
        expires=self.f['clock'].wall()+1
        with patch.object(e.precheck,'collect_jobs',return_value={}),\
             patch.object(e.storage,'check_inputs',return_value=dict(expiresAt=expires)),\
             patch.object(e.ci,'collect',return_value=self.f['github']),\
             patch.object(e.time,'time',return_value=expires),self.assertRaisesRegex(ValueError,'expired during CI'):
            e.current(self.f['cfg'],self.env,q.pq.SOURCE,q.pq.SOURCE,self.f['preflight'],self.f['root'])

    def test_prepare_collects_original_archives_without_owner_or_control_mutation(self):
        with ExitStack() as stack,patch.object(e.owned,'run_native') as owner:
            current=self.dependencies(stack);result=self.call('prepare')
        self.assertEqual('PREPARED',result['status'],result);self.assertFalse(result['paidCloud']);owner.assert_not_called()
        self.assertEqual(2,current.call_count)
        root=self.root/'entry/prepared';value=e.prepared.validate(root,q.pq.SOURCE,result['preparation']['planSha256'],now=self.f['clock'].wall())
        self.assertEqual(self.f['value']['artifacts'],value['artifacts']);self.assertEqual(q.COST,value['resourcePlan']['reservation']['maximumCostMicrousd'])
        self.assertFalse(c.read(root/'approval-template.json')['confirmed'])
        for file in (self.root/'entry').rglob('*'):
            if file.is_file():self.assertNotIn(self.secret.encode(),file.read_bytes())
        self.assertFalse(list(self.root.glob('v51-experiment-key-*')))

    def test_prepare_ci_drift_does_not_publish_a_valid_preparation(self):
        with ExitStack() as stack:
            current=self.dependencies(stack)
            one=current.return_value;current.side_effect=[one,(one[0],dict(expiresAt=1),one[2])]
            result=self.call('prepare')
        self.assertEqual('BLOCKED',result['status']);self.assertEqual('freshness',result['failure']['phase'])
        self.assertFalse((self.root/'entry/prepared/receipt.json').exists())

    def test_confirmed_run_passes_only_original_plan_archives_and_matching_key_once(self):
        archive=self.setup_run();calls=[]
        def owner(*args):
            calls.append(args);self.assertTrue(Path(args[-2]).is_file())
            self.assertEqual(self.f['value'],args[6]);self.assertEqual(self.f['approved'],args[7])
            self.assertEqual('originals',Path(args[8]).name)
            return dict(status='PASS',paidCloud=True,engineWorkloadExecuted=True,fullRemoteQualification=False)
        # collect's default fetch is frozen at function definition; patch the
        # underlying read-only downloader subprocess through this explicit wrapper.
        collect=e.prepared.collect
        with ExitStack() as stack:
            self.dependencies(stack)
            stack.enter_context(patch.object(e.prepared,'collect',side_effect=lambda *args,**kwargs:
                collect(*args,**kwargs,get=e.ci.github,fetch=lambda _,path:shutil.copyfile(archive,path))))
            executed=stack.enter_context(patch.object(e.owned,'run_native',side_effect=owner));result=self.call('run')
        self.assertEqual('PASS',result['status'],result);self.assertTrue(result['paidCloud']);executed.assert_called_once()
        self.assertFalse(Path(calls[0][-2]).exists())

    def test_expired_preparation_or_changed_private_key_stops_before_owner(self):
        archive=self.setup_run();collect=e.prepared.collect
        for label in ('wrong-key','expired'):
            if label=='wrong-key':
                e.guest_setup.generate(self.root/'other-key','c'*32);self.secret=(self.root/'other-key/identity').read_text()
            else:self.f['clock'].sleep(900)
            with ExitStack() as stack,patch.object(e.owned,'run_native') as owner:
                self.dependencies(stack)
                stack.enter_context(patch.object(e.prepared,'collect',side_effect=lambda *args,**kwargs:
                    collect(*args,**kwargs,get=e.ci.github,fetch=lambda _,path:shutil.copyfile(archive,path))))
                result=self.call('run',label)
            self.assertEqual('BLOCKED',result['status']);self.assertFalse(result['paidCloud']);owner.assert_not_called()

    def test_native_failure_is_not_retried_or_reported_as_unpaid(self):
        self.setup_run()
        with ExitStack() as stack:
            self.dependencies(stack)
            stack.enter_context(patch.object(e.prepared,'collect',return_value=(self.root,self.f['value'],self.f['approved'])))
            run=stack.enter_context(patch.object(e.owned,'run_native',side_effect=ValueError('credential-bearing sentinel')))
            result=self.call('run')
        self.assertEqual('FAIL',result['status']);self.assertIsNone(result['paidCloud']);run.assert_called_once()
        self.assertNotIn('credential-bearing',str(result))

    def test_public_network_entries_have_no_credential_or_backend_override(self):
        for fn in (e.prepare_network,e.run_network):
            self.assertEqual(('cfg','env','source','checkout','preflight','precheck_root','output','secret'),tuple(inspect.signature(fn).parameters))
        self.assertIn("os.environ.pop(SECRET,'')",inspect.getsource(e.main))

    def test_summary_reports_unstarted_failed_and_successful_execution_without_full_claim(self):
        root=self.root/'summary';self.assertIn('NOT_STARTED_OR_INTERRUPTED',e.summary(root));root.mkdir()
        c.write_once(root/'receipt.json',dict(status='FAIL',mode='run',source=q.pq.SOURCE,
            failure=dict(phase='key',type='<bad>|value'),result=dict(status='FAIL',paidCloud=True,
            cleanup=dict(status='PASS'),leaseReleased=False,retention='INCOMPLETE',engineWorkloadExecuted=True,
            errors=[dict(phase='validation',type='ValueError')],budget=dict(spentNanos={'healthy':1000000000}))))
        text=e.summary(root)
        for value in ('INCOMPLETE','Full Phase 6 qualification | False','Lease released | False','&lt;bad&gt;&#124;value','Time accounting'):
            self.assertIn(value,text)
        self.assertNotIn('<bad>',text)

    def test_summary_reports_preparation_owner_cleanup_without_claiming_workload_success(self):
        root=self.root/'summary';root.mkdir()
        c.write_once(root/'receipt.json',dict(status='FAIL',mode='run',source=q.pq.SOURCE,
            result=dict(status='FAIL',paidCloud=True,engineWorkloadExecuted=False,cleanup=None,retention='INCOMPLETE',
                leaseReleased=False,preparation=dict(ownerRecovery=dict(cleanup=dict(status='PASS'),retention='VERIFIED',leaseReleased=True)))))
        text=e.summary(root)
        for value in ('Status | FAIL','Cleanup | PASS','Evidence retention | VERIFIED','Lease released | True','Engine workload | False'):
            self.assertIn(value,text)

    def test_summary_reports_first_runtime_failure_even_without_outer_receipt(self):
        root=self.root/'summary';(root/'execution').mkdir(parents=True)
        result=dict(status='FAIL',errors=[dict(phase='execution',type='ValueError',cell='healthy',
            code='RUNTIME_RESOURCE_SCOPE',detail='private-secret',message='private-secret'),
            dict(phase='validation-retention',type='ValueError',code='RUNTIME_QUALIFICATION_FAILED')])
        c.write_once(root/'execution/receipt.json',result)
        for wrapped in (False,True):
            if wrapped:c.write_once(root/'receipt.json',dict(status='FAIL',mode='run',result=result))
            text=e.summary(root)
            for value in ('Failure phase | execution','Failure cell | healthy','Failure code | RUNTIME_RESOURCE_SCOPE',
                          'RUNTIME_QUALIFICATION_FAILED',e.diagnostics.detail('RUNTIME_RESOURCE_SCOPE')):
                self.assertIn(value,text)
            self.assertNotIn('private-secret',text)

    def test_failure_codes_only_expose_known_static_messages(self):
        self.assertEqual('PLAN_CHANGED_OR_EXPIRED',e.failure('handoff',ValueError('Runner plan drift/expiry'))['code'])
        value=e.failure('handoff',ValueError('https://provider.example/token?secret=sentinel'))
        self.assertEqual('UNCLASSIFIED',value['code']);self.assertNotIn('sentinel',str(value))

    def test_summary_shows_guest_deadline_and_distinguishes_owner_recovery_time(self):
        root=self.root/'summary';root.mkdir()
        c.write_once(root/'receipt.json',dict(status='FAIL',result=dict(budget=dict(spentNanos={'preparation':819000000000}),
            preparation=dict(elapsedSeconds=552,failure=dict(phase='guest-setup',type='ValueError',code='PREPARATION_DEADLINE',
                operation=dict(node='node-3',kind='package',action='part',index=5)),
                ownerRecovery=dict(elapsedSeconds=267,cleanup=dict(status='PASS'),leaseReleased=True,retention='VERIFIED')))))
        text=e.summary(root)
        for value in ('PREPARATION_DEADLINE','node-3','package','Preparation elapsed (s) | 552',
                      'Owner failure recovery elapsed (s) | 267','includes immediate owner recovery','Cleanup | PASS'):
            self.assertIn(value,text)

    def test_summary_shows_reviewed_limits_and_separate_preparation_phases(self):
        root=self.root/'summary';(root/'handoff/prepared').mkdir(parents=True)
        c.write_once(root/'handoff/prepared/plan.json',self.f['value'])
        c.write_once(root/'receipt.json',dict(mode='run',result=dict(preparation=dict(timings=[
            dict(phase='resources',elapsedSeconds=494.186),dict(phase='guest-setup',elapsedSeconds=700)]))))
        text=e.summary(root)
        for value in ('900 / 3600 / 14400 / 1800','12000 / 2400','owned-experiment-v2',
                      'Preparation phases','resources | 494.186','guest-setup | 700',
                      'approval window gates the first lease mutation'):
            self.assertIn(value,text)

    def test_workflow_guards_default_inputs_identity_secret_and_order(self):
        raw=e.workflow.workflow().decode();job=e.workflow.JOB
        self.assertIn("default: 'off'",raw);self.assertIn("options: ['off', prepare, run]",raw)
        self.assertEqual(2,raw.count('V51_EXPERIMENT_SSH_KEY: ${{ secrets.V51_EXPERIMENT_SSH_KEY }}'))
        self.assertLess(job.index('cloud_runner_entry guard'),job.index('google-github-actions/auth@'))
        self.assertLess(job.index('cloud_runner_precheck report'),job.index('cloud_runner_entry prepare'))
        self.assertLess(job.index('cloud_runner_precheck report'),job.index('cloud_runner_entry run'))
        self.assertIn("success() && inputs.runner_experiment == 'run'",raw)
        self.assertIn('timeout --signal=TERM --kill-after=60s "${guard_seconds}s"',raw)
        for seconds in (15000,16500,20100):self.assertIn('guard_seconds='+str(seconds),raw)
        for bad in (raw.replace("default: 'off'","default: 'run'"),raw.replace("success() && inputs.runner_experiment == 'run'",'always()'),
            raw.replace('path: target/v51-experiment\n','path: /tmp\n'),raw.replace("version: '582.0.0'","version: 'latest'")):
            with self.assertRaises(ValueError):e.workflow.workflow(bad)


if __name__=='__main__':unittest.main()
