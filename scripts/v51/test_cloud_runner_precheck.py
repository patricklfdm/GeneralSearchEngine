"""Synthetic same-run evidence and configuration tests; no live cloud claims."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from . import cloud_runner_precheck as r, cloud_runner_review as review, cloud_preflight as p
from . import cloud_permissions as permissions, cloud_preflight_qualification as q
from . import cloud_identity_qualification as iq, cloud_cleanup_deployment as deployment
from . import test_cloud_recent_cleanup as recent, performance_model as m
from .remote_command import read, write_once


def at(value):return datetime.fromtimestamp(value,timezone.utc).isoformat()


def permission_files(cfg, env, root, role, now):
    binding=permissions.identity(cfg,env,role=role,source=q.SOURCE,checkout=q.SOURCE)
    plan=permissions.plan(cfg,role)
    observed=dict(binding,execution='workflow-permission-probes',startedAt=now,completedAt=now,
                  credentialExchangeCompleted=True,planSha256=m.sha(m.canonical(plan)),
                  observations={k:(dict(image=deepcopy(v['expectedImage'])) if k == 'image' else dict(permissions=v['required']))
                                for k,v in plan.items()})
    root.mkdir()
    for name,value in [('binding',binding),('observations',observed),('receipt',permissions.evaluate(cfg,binding,observed,now=now))]:
        write_once(root/(name+'.json'),value)


def fixture(root):
    cfg,_,cleanup,files,old=recent.fixture();delta=q.NOW-old-60
    def rebase(v):
        if isinstance(v,dict):
            return {k:q.SOURCE if k in ('source','head_sha') else
                    v[k]+delta if k in ('startedAt','completedAt','checkedAt','observedAt') else
                    at(r.ci.timestamp(v[k])+delta) if k in ('started_at','completed_at') else rebase(v[k]) for k in v}
        if isinstance(v,list):return [rebase(i) for i in v]
        return v
    cleanup=rebase(cleanup);files=rebase(files)
    obs=files['permissions/observations.json']
    files['permissions/receipt.json']=permissions.evaluate(cfg,files['permissions/binding.json'],obs,now=obs['completedAt'])
    preflight=root/'preflight';preflight.mkdir();cr=preflight/'cleanup';cr.mkdir()
    recent.pack(cr,cleanup,files);write_once(cr/'observations.json',cleanup)
    _,github,provider=q.fixture(cfg);provider['execution']='read-only-provider-observations'
    write_once(preflight/'github.json',github);write_once(preflight/'provider.json',provider)
    chosen=permissions.selected(cfg,'runner')
    env=dict(GITHUB_ACTIONS='true',GITHUB_REPOSITORY=r.ci.REPOSITORY,GITHUB_REPOSITORY_ID=str(r.ci.REPOSITORY_ID),
             GITHUB_REPOSITORY_OWNER_ID=str(r.ci.OWNER_ID),GITHUB_REF='refs/heads/master',GITHUB_EVENT_NAME='workflow_dispatch',
             GITHUB_WORKFLOW_REF=chosen['claims']['workflow_ref'],GITHUB_WORKFLOW_SHA=q.SOURCE,GITHUB_SHA=q.SOURCE,
             GITHUB_JOB='run',PERMISSION_ENVIRONMENT=chosen['environment'],RUNNER_PERMISSION_PRECHECK='true',
             GITHUB_RUN_ID='222',GITHUB_RUN_ATTEMPT='2')
    observer=dict(env,GITHUB_JOB='observations');permission_files(cfg,observer,preflight/'permissions','observer',q.NOW-2)
    receipt=p.report(cfg,q.SOURCE,preflight,observer,now=q.NOW)
    m.need(receipt['status']=='OBSERVATIONS_READY','fixture observer preflight');write_once(preflight/'preflight.json',receipt)
    repo=dict(id=r.ci.REPOSITORY_ID,full_name=r.ci.REPOSITORY,owner=dict(id=r.ci.OWNER_ID))
    run=dict(id=222,run_attempt=2,head_sha=q.SOURCE,head_branch='master',path=r.a.RUNNER_WORKFLOW,
             event='workflow_dispatch',status='in_progress',conclusion=None,repository=repo,head_repository=deepcopy(repo))
    job=dict(name='observations',run_id=222,run_attempt=2,head_sha=q.SOURCE,status='completed',conclusion='success',
             started_at=at(q.NOW-20),completed_at=at(q.NOW+1),
             steps=[dict(name=name,status='completed',conclusion='success') for name in r.OBSERVER_STEPS])
    jobs=dict(total_count=1,jobs=[job])
    data={'actions/runs/222':run,'actions/runs/222/attempts/2':deepcopy(run),
          'actions/runs/222/attempts/2/jobs?per_page=100':jobs}
    return cfg,env,preflight,data


class RunnerPrecheckTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.cfg,self.env,self.preflight,self.data=fixture(self.root)
        self.binding=r.identity(self.cfg,self.env,q.SOURCE,q.SOURCE);self.now=q.NOW+2
    def get(self,path):return deepcopy(self.data[path])
    def bound(self):return r.bind(self.cfg,self.env,q.SOURCE,q.SOURCE,self.preflight,self.root/'identity',get=self.get,wall=lambda:self.now)
    def finish(self):return r.finish(self.cfg,self.env,q.SOURCE,q.SOURCE,self.preflight,self.root,get=self.get,wall=lambda:self.now)
    def prerequisite(self):return r.prerequisites(self.cfg,self.env,self.binding,self.preflight,self.data['actions/runs/222/attempts/2/jobs?per_page=100'],now=self.now)

    def test_optional_binding_queries_exact_same_attempt_before_emitting_identity(self):
        value=self.bound();self.assertEqual('BOUND',value['status'])
        self.assertEqual('runner',value['binding']['role']);self.assertFalse(value['paidAdmission'])
        self.assertFalse(value['prerequisites']['cleanup']['scheduleRequired'])
        with self.assertRaises(FileExistsError):self.bound()

    def test_wrong_mode_job_source_ref_role_and_attempt_fail_before_github(self):
        for key in ('RUNNER_PERMISSION_PRECHECK','GITHUB_JOB','GITHUB_REF','GITHUB_SHA','GITHUB_WORKFLOW_REF','GITHUB_RUN_ATTEMPT'):
            env=dict(self.env,**{key:'wrong'});get=Mock()
            with self.subTest(key=key),self.assertRaises(ValueError):
                r.bind(self.cfg,env,q.SOURCE,q.SOURCE,self.preflight,self.root/'identity',get=get)
            get.assert_not_called()
        with self.assertRaises(ValueError):r.identity(self.cfg,self.env,q.SOURCE,'b'*40)

    def test_skipped_failed_missing_wrong_attempt_and_future_observer_job_block(self):
        key='actions/runs/222/attempts/2/jobs?per_page=100';original=deepcopy(self.data[key])
        for change in (lambda j:j.update(conclusion='skipped'),lambda j:j.update(run_attempt=1),
                       lambda j:j.update(head_sha='b'*40),lambda j:j['steps'].pop(),
                       lambda j:j['steps'][0].update(conclusion='failure'),
                       lambda j:j.update(completed_at=at(self.now+1))):
            self.data[key]=deepcopy(original);change(self.data[key]['jobs'][0])
            with self.assertRaises(ValueError):self.prerequisite()

    def test_waiting_for_environment_cannot_renew_expired_observer_evidence(self):
        self.now=q.NOW+900
        with self.assertRaisesRegex(ValueError,'expired'):self.prerequisite()

    def test_artifact_tamper_and_other_attempt_permission_evidence_block(self):
        path=self.preflight/'permissions/binding.json';value=read(path);value['runAttempt']=1
        path.write_bytes(m.canonical(value))
        with self.assertRaisesRegex(ValueError,'receipt changed'):self.prerequisite()

    def test_same_run_summary_without_raw_inputs_cannot_pass(self):
        (self.preflight/'provider.json').unlink()
        with self.assertRaisesRegex(ValueError,'receipt changed'):self.prerequisite()

    def test_offline_observation_cannot_pass_even_with_recomputed_summary(self):
        path=self.preflight/'provider.json';v=read(path);v['execution']='offline-preflight-fixture';path.write_bytes(m.canonical(v))
        value=p.report(self.cfg,q.SOURCE,self.preflight,dict(self.env,GITHUB_JOB='observations'),now=q.NOW)
        (self.preflight/'preflight.json').write_bytes(m.canonical(value))
        with self.assertRaisesRegex(ValueError,'offline'):self.prerequisite()

    def test_rerun_during_github_collection_is_not_another_attempts_success(self):
        reads=0
        def get(path):
            nonlocal reads
            result=self.get(path)
            if path=='actions/runs/222':
                reads+=1
                if reads>1:result['run_attempt']=3
            return result
        with self.assertRaises(ValueError):r.collect_jobs(self.binding,get)

    def test_complete_diagnostic_report_requires_actual_runner_permission_evidence(self):
        self.bound();permission_files(self.cfg,self.env,self.root/'permissions','runner',self.now)
        result=self.finish();self.assertEqual('PRECHECK_PASS',result['status'],result)
        for k in permissions.BOUNDARY:self.assertIs(result[k],False)
        self.assertTrue((self.root/'summary.md').exists())

    def test_missing_auth_or_permission_output_retains_blocked_diagnostics(self):
        self.bound();result=self.finish();self.assertEqual('BLOCKED',result['status'])
        self.assertEqual('runner-permissions',result['failure']['phase']);self.assertFalse(result['paidAdmission'])

    def test_changed_binding_is_rejected_in_final_report(self):
        self.bound();path=self.root/'identity/binding.json';v=read(path);v['role']='observer';path.write_bytes(m.canonical(v))
        result=self.finish();self.assertEqual('BLOCKED',result['status']);self.assertEqual('identity',result['failure']['phase'])

    def test_late_final_github_response_cannot_extend_original_expiry(self):
        self.bound();permission_files(self.cfg,self.env,self.root/'permissions','runner',self.now)
        calls=0
        def wall():
            nonlocal calls
            calls+=1
            return self.now if calls<3 else q.NOW+900
        value=r.finish(self.cfg,self.env,q.SOURCE,q.SOURCE,self.preflight,self.root,get=self.get,wall=wall)
        self.assertEqual('BLOCKED',value['status'])


class RunnerReviewTest(unittest.TestCase):
    def setUp(self):self.cfg=read(p.CONFIG);self.source=q.SOURCE
    def state(self,enabled,schedule):
        v=iq.fixture(self.cfg);o=v['observations']
        for key,on in (('runner',enabled),('manual',True),('schedule',schedule)):
            for obj in (o[key+':account'],o[key+':pool'],o[key+':providers'][0]):obj['disabled']=not on
        return v

    def test_schedule_state_is_optional_but_all_explicit_policies_are_checked(self):
        for enabled in (True,False):
            for schedule in (True,False):
                value=self.state(enabled,schedule);original=deepcopy(value)
                result=review.evaluate(self.cfg,'enabled' if enabled else 'disabled',value,now=iq.NOW)
                self.assertEqual('CONFIGURATION_MATCH',result['status'],result);self.assertEqual(original,value)
                self.assertEqual(17,len(result['checks']))
                for key in permissions.BOUNDARY:self.assertIs(result[key],False)

    def test_partial_enable_unavailable_reads_and_permission_drift_block(self):
        for enabled in (True,False):
            state='enabled' if enabled else 'disabled'
            for key in ('runner','manual','schedule'):
                v=self.state(enabled,True);v['observations'][key+':account']['disabled']=not v['observations'][key+':account']['disabled']
                self.assertEqual('BLOCKED',review.evaluate(self.cfg,state,v,now=iq.NOW)['status'])
            for name,mutate in list(iq.mutations().items())[3:]:
                with self.subTest(state=state,name=name):
                    value=self.state(enabled,True);mutate(value['observations'])
                    self.assertEqual('BLOCKED',review.evaluate(self.cfg,state,value,now=iq.NOW)['status'])

    def test_enabled_default_false_supported_and_old_cleanup_audit_stays_closed(self):
        v=self.state(True,False)
        for key in ('runner','manual'):
            for obj in (v['observations'][key+':account'],v['observations'][key+':pool'],v['observations'][key+':providers'][0]):obj.pop('disabled')
        self.assertEqual('CONFIGURATION_MATCH',review.evaluate(self.cfg,'enabled',v,now=iq.NOW)['status'])
        self.assertEqual('BLOCKED',deployment.evaluate(self.cfg,'manual',v,now=iq.NOW)['status'])

    def test_review_has_only_runner_commands_and_no_executor(self):
        commands=deployment.identity_commands(self.cfg,'runner');self.assertEqual(3,len(commands['enable']))
        self.assertEqual('providers',commands['enable'][0][3]);self.assertEqual('enable',commands['enable'][-1][3])
        self.assertEqual('disable',commands['disable'][0][3])
        self.assertNotIn('manual-cleanup',str(commands));self.assertNotIn('set-iam',str(commands))
        self.assertEqual({'manual','schedule'},set(deployment.commands(self.cfg)))

    def test_review_manifest_and_rehashed_payload_drift_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'review';v=review.generate(self.cfg,self.source,root)
            self.assertEqual(v,review.validate(self.cfg,self.source,root))
            (root/'commands.json').write_text('{}\n');v['files']['commands.json']=m.sha(b'{}\n')
            (root/'review.json').write_bytes(m.canonical(v))
            with self.assertRaisesRegex(ValueError,'payload drift'):review.validate(self.cfg,self.source,root)
            with self.assertRaises(ValueError):review.generate(self.cfg,self.source,Path(tmp)/'.github/review')

    def test_installed_workflow_freezes_default_observer_and_optional_runner(self):
        raw=review.workflow().decode()
        self.assertIn('default: false',raw);self.assertIn('needs: observations',raw)
        for changed in (raw.replace('default: false','default: true'),raw.replace('needs: observations','needs: []'),
                        raw.replace('cloud_preflight report','cloud_preflight provider'),
                        raw.replace('--role runner','--role observer')):
            with self.assertRaises(ValueError):review.workflow(changed)
        self.assertLess(review.JOB.index('cloud_runner_precheck identity'),review.JOB.index('google-github-actions/auth@'))
        self.assertIn('v51-preflight-${{ github.run_id }}-${{ github.run_attempt }}',review.JOB)
        for forbidden in ('gcloud compute','cloud_runner run','cloud_entry','gh workflow run','cloud_fixture','cloud_object_probes'):
            self.assertNotIn(forbidden,raw)


if __name__=='__main__':unittest.main()
