"""Read-only source/provider boundary; incomplete evidence cannot authorize a run."""
from copy import deepcopy
from pathlib import Path
import json
import os
import re
import subprocess
import tempfile
import unittest
from unittest.mock import Mock
from . import cloud_ci as ci, cloud_preflight as p, cloud_preflight_qualification as q
from . import cloud_authority as a, cloud_fake, cloud_http, performance_model as m
from . import cloud_native_authority as n


def native_fixture(cost=1_000_000):
    req=n.request('a'*40,'d'*64,'e'*64,'c'*32,'b'*32,'experiment',now=10001,guest_access_sha256='f'*64)
    return req,None,dict(previousCostMicrousd=0,maximumCostMicrousd=cost)


class PreflightTest(unittest.TestCase):
    def setUp(self):self.cfg,self.github,self.provider=q.fixture()
    def evaluate(self,**kwargs):return p.evaluate(self.cfg,q.SOURCE,self.github,self.provider,now=kwargs.get('now',q.NOW))
    def blocked(self,check):
        value=self.evaluate();self.assertEqual(value['status'],'BLOCKED');self.assertEqual(value['checks'][check]['status'],'BLOCKED');return value
    def test_all_observations_pass_but_paid_and_remote_admission_stay_closed(self):
        result=self.evaluate();self.assertEqual(result['status'],'OBSERVATIONS_READY')
        self.assertFalse(result['paidAdmission']);self.assertFalse(result['fullRemoteQualification']);self.assertTrue(result['pending'])
        req,_,approval=cloud_fake.fixture()
        with self.assertRaises(ValueError):a.admit(req,result,approval,q.NOW)
    def test_every_ci_job_must_execute_at_exact_attempt(self):
        original=deepcopy(self.github)
        for i in range(len(self.github['observations']['jobs'])):
            for mutation in ({'conclusion':'skipped'},{'conclusion':'failure'},{'run_attempt':1},{'head_sha':'b'*40}):
                self.github=deepcopy(original);self.github['observations']['jobs'][i].update(mutation)
                with self.subTest(i=i,mutation=mutation):self.blocked('exactSourceCI')
    def test_ci_missing_duplicate_extra_jobs(self):
        rows=self.github['observations']['jobs']
        for changed in (rows[:-1],rows+[rows[0]],rows[:-1]+[rows[0]]):
            self.github['observations']['jobs']=changed;self.blocked('exactSourceCI')
    def test_owned_step_success_cannot_be_inferred_from_job_success(self):
        job=next(j for j in self.github['observations']['jobs'] if j['name']==ci.OWNED_JOB)
        job['steps'][0]['conclusion']='skipped';self.blocked('exactSourceCI')
    def test_source_workflow_and_configuration_are_bound(self):
        obs=self.github['observations']
        for key in ('masterBefore','masterAfter','workflowSha256','configurationSha256'):
            old=obs[key];obs[key]='c'*len(old)
            with self.subTest(key=key):self.blocked('exactSourceCI')
            obs[key]=old
    def test_pr_fork_and_changed_attempt_rejected(self):
        obs=self.github['observations'];original=deepcopy(obs)
        for mutation in ({'event':'pull_request'},{'head_branch':'other'},{'status':'in_progress'},{'path':a.RUNNER_WORKFLOW}):
            obs['run'].update(mutation);obs['runAfter'].update(mutation);self.blocked('exactSourceCI')
            self.github['observations']=obs=deepcopy(original)
        obs['runAfter']['run_attempt']=3;self.blocked('exactSourceCI')
        self.github['observations']=deepcopy(original)
        self.github['observations']['run']['repository']['id']=123;self.blocked('exactSourceCI')
    def test_future_job_and_stale_observations(self):
        self.github['observations']['jobs'][0]['completed_at']='2099-01-01T00:00:00Z';self.blocked('exactSourceCI')
        self.setUp();self.provider['startedAt']=q.NOW-901;self.blocked('provider')
        self.setUp();self.github['completedAt']=q.NOW+1;self.blocked('exactSourceCI')
    def test_expiry_does_not_renew_after_partial_collection(self):
        result=self.evaluate();self.assertEqual(result['expiresAt'],q.NOW+890)
        self.assertEqual(self.evaluate(now=q.NOW+890)['status'],'BLOCKED')
    def test_provider_collection_is_get_only_in_separate_namespace(self):
        transport=q.Http(self.cfg,self.provider['observations']);api=cloud_http.Api(transport=transport,tokens=lambda t:'fake',clock=lambda:1)
        result=p.collect_provider(self.cfg,api=api,who=lambda:self.cfg['observerServiceAccount'],wall=lambda:q.NOW)
        self.assertEqual(len(transport.requests),9)
        self.assertTrue(all(r['method']=='GET' for r in transport.requests))
        self.assertTrue(all('v5.0' not in r['url'] for r in transport.requests))
        self.assertEqual(result['execution'],'offline-preflight-fixture')
    def test_provider_errors_do_not_retain_credentials(self):
        def fail(*args,**kwargs):raise ValueError('secret-example-token')
        api=Mock(offline=False,clock=lambda:1)
        api.call.side_effect=fail
        value=p.collect_provider(self.cfg,api=api,who=fail,wall=lambda:q.NOW)
        self.assertNotIn('secret-example-token',json.dumps(value));self.assertEqual(len(value['observations']),10)
    def test_http_status_remains_actionable_without_retaining_body(self):
        api=Mock(offline=False,clock=lambda:1);api.call.side_effect=cloud_http.ApiError(403,'GET')
        self.provider=p.collect_provider(self.cfg,api=api,who=lambda:self.cfg['observerServiceAccount'],wall=lambda:q.NOW)
        result=self.blocked('image');self.assertIn('HTTP 403',result['checks']['image']['reason'])
    def test_boolean_observation_times_are_rejected(self):
        self.provider['startedAt']=True;self.blocked('provider')
    def test_changed_or_deprecated_image_blocks(self):
        for change in ({'id':'1'},{'status':'PENDING'},{'architecture':'ARM64'},{'deprecated':{'state':'DEPRECATED'}}):
            self.setUp();self.provider['observations']['image'].update(change);self.blocked('image')
    def test_compute_resource_id_is_distinct_from_project_number(self):
        project=self.provider['observations']['project']
        project.update(id='5021569533786003310',name=self.cfg['provider']['project'])
        for host in ('compute.googleapis.com','www.googleapis.com'):
            with self.subTest(host=host):
                project['selfLink']='https://'+host+'/compute/v1/projects/'+project['name']
                self.assertNotEqual(project['id'],self.cfg['projectNumber'])
                self.assertEqual(self.evaluate()['status'],'OBSERVATIONS_READY')
    def test_compute_project_name_and_self_link_must_match(self):
        base='https://compute.googleapis.com/compute/v1/projects/'+self.cfg['provider']['project']
        for change in ({'name':'other-project'},{'selfLink':base+'-other'},
                       {'selfLink':base.replace('compute.googleapis.com','example.com')},
                       {'selfLink':None}):
            with self.subTest(change=change):
                self.setUp()
                self.provider['observations']['project'].update(id=self.cfg['projectNumber'],selfLink=base)
                self.provider['observations']['project'].update(change)
                self.blocked('topology')
        self.setUp();self.provider['observations']['project'].pop('selfLink',None);self.blocked('topology')
    def test_compute_resource_id_must_still_be_numeric(self):
        for value in ('', 'invalid', True, None):
            with self.subTest(value=value):
                self.setUp();self.provider['observations']['project']['id']=value;self.blocked('topology')
    def test_bucket_project_number_binding_remains_required(self):
        self.provider['observations']['bucket']['projectNumber']='123456789'
        self.blocked('storagePolicy')
    def test_disabled_private_google_access_remains_actionable(self):
        self.provider['observations']['subnetwork']['privateIpGoogleAccess']=False
        result=self.blocked('topology')
        self.assertIn('Private Google Access',result['checks']['topology']['reason'])
        self.assertIn('us-west4/default',result['checks']['topology']['reason'])
    def test_nan_bool_missing_and_duplicate_quota_rejected(self):
        for change in ({'limit':float('nan')},{'usage':True},{'limit':23}):
            self.setUp();self.provider['observations']['region']['quotas'][0].update(change);self.blocked('quota')
        self.setUp();rows=self.provider['observations']['region']['quotas'];rows.append(rows[0]);self.blocked('quota')
        self.setUp();self.provider['observations']['region']['quotas'].pop();self.blocked('quota')
    def test_lease_even_expired_never_counts_as_absent(self):
        req,_,_=native_fixture();lease=n.lease(req,req['createdAt'])
        self.provider['observations']['lease']=[8,lease];self.blocked('controlState')
        self.assertLess(lease['expiresAt']+lease['graceSeconds'],q.NOW)
    def test_missing_ledger_does_not_reset_pending_or_failed_attempts(self):
        req,_,approval=native_fixture();ledger=n.reserve(n.empty_ledger(),req,approval)
        self.provider['observations']['ledger']=[1,ledger];self.blocked('controlState')
        ledger=n.finish(ledger,req,dict(requestSha256=n.validate_request(req),status='FAIL'))
        self.provider['observations']['ledger']=[2,ledger]
        self.assertEqual(self.evaluate()['checks']['controlState']['detail']['previousCostMicrousd'],1_000_000)
        self.provider['observations']['ledger']={'error':'denied'};self.blocked('controlState')
    def test_foreign_ledger_and_exhausted_budget(self):
        self.provider['observations']['ledger']=[1,{'schema':'gse-v50-budget-v1','reservations':[]}];self.blocked('controlState')
        req,_,approval=native_fixture(cost=200_000_000)
        ledger=n.finish(n.reserve(n.empty_ledger(),req,approval),req,dict(requestSha256=n.validate_request(req),status='FAIL'))
        self.provider['observations']['ledger']=[1,ledger];self.blocked('controlState')
    def test_preflight_retains_charges_and_reports_200_dollar_ceiling(self):
        for cost in (100_000_000,199_999_999):
            with self.subTest(cost=cost):
                req,_,approval=native_fixture(cost=cost)
                ledger=n.finish(n.reserve(n.empty_ledger(),req,approval),req,dict(requestSha256=n.validate_request(req),status='FAIL'))
                self.provider['observations']['ledger']=[1,ledger]
                result=self.evaluate()['checks']['controlState']
                self.assertEqual('PASS',result['status'])
                self.assertEqual(dict(previousCostMicrousd=cost,budgetMicrousd=200_000_000,leaseAbsent=True),result['detail'])
    def test_fake_ledger_cannot_replace_native_control_state(self):
        self.provider['observations']['ledger']=[1,a.empty_ledger()]
        self.blocked('controlState')
    def test_storage_hold_lock_and_early_deletion_block(self):
        for change in ({'defaultEventBasedHold':True},{'retentionPolicy':{'retentionPeriod':'2592000'}},
                       {'lifecycle':{'rule':[{'action':{'type':'Delete'},'condition':{'age':29}}]}},
                       {'lifecycle':{'rule':[{'action':{'type':'Delete'},'condition':{'isLive':False}}]}}):
            self.setUp();self.provider['observations']['bucket'].update(change);self.blocked('storagePolicy')
    def test_observer_config_cannot_reuse_v50_identity_or_change_frozen_shape(self):
        for name in ('observerServiceAccount','observerWifProvider'):
            cfg=deepcopy(self.cfg);cfg[name]=cfg[name].replace('v51','v50')
            with self.assertRaises(ValueError):p.configuration(cfg)
        self.cfg['provider']['machineType']='n2-standard-16'
        with self.assertRaises(ValueError):p.configuration(self.cfg)
    def test_dispatch_checks_all_repository_and_workflow_claims(self):
        env=dict(GITHUB_REPOSITORY=ci.REPOSITORY,GITHUB_REPOSITORY_ID=str(ci.REPOSITORY_ID),GITHUB_REPOSITORY_OWNER_ID=str(ci.OWNER_ID),
                 GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_REF='refs/heads/master',GITHUB_WORKFLOW_REF=ci.REPOSITORY+'/'+a.RUNNER_WORKFLOW+'@refs/heads/master',GITHUB_SHA=q.SOURCE)
        self.assertEqual(p.identity(self.cfg,env)['serviceAccount'],self.cfg['observerServiceAccount'])
        for key in env:
            with self.subTest(key=key),self.assertRaises(ValueError):p.identity(self.cfg,dict(env,**{key:'untrusted'}))
    def test_summary_escapes_dynamic_text_and_shows_bounds(self):
        r=self.evaluate();r['checks']['example']=dict(status='BLOCKED',reason='<script>|\ntext')
        s=p.summary(r,self.cfg);self.assertNotIn('<script>',s);self.assertIn('&#124;',s)
        for text in ('24 vCPU','450 GiB','paid admission remains closed','200; reservations never reset'):self.assertIn(text,s)


class GitHubCollectionTest(unittest.TestCase):
    def setUp(self):self.cfg,self.g,self.provider=q.fixture();self.data=q.github_api(self.g);self.paths=[]
    def get(self,path):self.paths.append(path);return deepcopy(self.data[path])
    def test_only_exact_attempt_endpoint_with_readback(self):
        workflow=(ci.ROOT/ci.WORKFLOW).read_text();r=ci.collect(q.SOURCE,self.get)
        self.assertEqual(ci.check(r,q.SOURCE,q.NOW,workflow)['jobs'],len(ci.expected_jobs(workflow)))
        self.assertEqual(self.paths.count('actions/runs/12'),2);self.assertIn('actions/runs/12/attempts/2/jobs?per_page=100&page=1',self.paths)
    def test_newer_failed_run_is_not_hidden_by_older_success(self):
        key=next(k for k in self.data if '/runs?branch=' in k)
        run=deepcopy(self.g['observations']['run']);run.update(id=13,conclusion='failure');self.data[key]['workflow_runs'].append(run)
        self.data['actions/runs/13']=run
        self.data['actions/runs/13/attempts/2/jobs?per_page=100&page=1']=self.data['actions/runs/12/attempts/2/jobs?per_page=100&page=1']
        r=ci.collect(q.SOURCE,self.get);self.assertEqual(r['run']['id'],13)
        with self.assertRaises(ValueError):ci.check(r,q.SOURCE,q.NOW,(ci.ROOT/ci.WORKFLOW).read_text())
    def test_incomplete_or_changed_pagination_rejected(self):
        key='actions/runs/12/attempts/2/jobs?per_page=100&page=1';self.data[key]['total_count']=30
        self.data['actions/runs/12/attempts/2/jobs?per_page=100&page=2']=dict(total_count=31,jobs=[])
        with self.assertRaisesRegex(ValueError,'pagination'):ci.collect(q.SOURCE,self.get)
    def test_new_ci_during_read_cannot_leave_a_ready_snapshot(self):
        key=next(k for k in self.data if '/runs?branch=' in k);reads=0
        def get(path):
            nonlocal reads
            value=self.get(path)
            if path==key:
                reads+=1
                if reads==2:value['workflow_runs'][0]['id']=13
            return value
        with self.assertRaisesRegex(ValueError,'new CI run'):ci.collect(q.SOURCE,get)
    def test_rerun_during_collection_is_rejected_after_readback(self):
        reads=0
        def get(path):
            nonlocal reads
            value=self.get(path)
            if path=='actions/runs/12':
                reads+=1
                if reads==2:value['run_attempt']=3
            return value
        value=ci.collect(q.SOURCE,get)
        with self.assertRaisesRegex(ValueError,'changed during'):ci.check(value,q.SOURCE,q.NOW,(ci.ROOT/ci.WORKFLOW).read_text())
    def test_source_content_is_verified(self):
        key='contents/'+ci.WORKFLOW+'?ref='+q.SOURCE;self.data[key]['size']+=1
        with self.assertRaisesRegex(ValueError,'byte count'):ci.collect(q.SOURCE,self.get)
    def test_unknown_matrix_or_missing_display_name_rejected(self):
        text=(ci.ROOT/ci.WORKFLOW).read_text()
        for altered in (text.replace('    name: Required\n',''),text.replace('automatic-concurrent]', 'extra-shard]')):
            with self.assertRaises(ValueError):ci.expected_jobs(altered)


class ObserverProposalTest(unittest.TestCase):
    def test_only_read_roles_and_exact_control_objects_are_proposed(self):
        from .cloud_observer_setup import proposal
        cfg,_,_=q.fixture();v=proposal(cfg)
        self.assertFalse(v['applied']);self.assertNotIn('gse-github',v['provider'])
        self.assertTrue(all(permission.endswith('.get') for role in v['roles'].values() for permission in role['includedPermissions']))
        condition=v['controlCondition']['expression']
        self.assertIn(a.LEASE,condition);self.assertIn(a.LEDGER,condition);self.assertNotIn('startsWith',condition)
        for key in ('repository_id','repository_owner_id','event_name','workflow_ref','environment','ref'):
            self.assertIn('assertion.'+key+" == '",v['providerCondition'])
    def test_generated_review_commands_parse_and_never_execute(self):
        from .cloud_observer_setup import write
        cfg,_,_=q.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'proposal';write(root,cfg)
            text=(root/'APPLY.md').read_text();shell=text.split('```bash\n')[1].split('```')[0]
            result=subprocess.run(['bash','-n'],input=shell.encode(),capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertNotIn('update-oidc',shell);self.assertNotIn('roles/editor',shell)
            with self.assertRaises(FileExistsError):write(root,cfg)


class WorkflowTest(unittest.TestCase):
    def test_dedicated_entries_are_manual_and_have_no_write_commands(self):
        for filename in ('v51-replication-foundation.yml','v51-replication-evidence.yml'):
            body=(ci.ROOT/'.github/workflows'/filename).read_text()
            self.assertIn('  workflow_dispatch:',body);self.assertNotIn('  schedule:',body)
            self.assertIn('ref: ${{ github.sha }}',body);self.assertIn('persist-credentials: false',body)
            self.assertIn('if: ${{ always()',body);self.assertNotIn('continue-on-error',body)
            for forbidden in ('cloud_entry','cloud_runner run','gcloud compute','gcloud storage','gh workflow run'):self.assertNotIn(forbidden,body)
        foundation=(ci.ROOT/'.github/workflows/v51-replication-foundation.yml').read_text()
        self.assertNotIn('id-token:',foundation);self.assertNotIn('google-github-actions/auth',foundation)
    def test_cloud_ci_requires_each_preflight_lane_without_maven(self):
        from scripts.test_ci_changes import FULL_GATES
        text=(ci.ROOT/ci.WORKFLOW).read_text()
        for key,lane in (('cloud-preflight-tests','admission'),('cloud-cleanup-fixture-tests','cleanup'),('cloud-storage-tests','storage')):
            # Use the same explicit-job boundary as the CI inventory parser.
            body=re.split(r'^  [\w-]+:\n',text.split('\n  '+key+':\n')[1],maxsplit=1,flags=re.M)[0]
            self.assertIn('run: scripts/verify-v51-phase6-cloud-preflight.sh --lane '+lane,body)
            self.assertNotIn('./mvnw',body);self.assertNotIn('id-token:',body)
            self.assertIn('needs.'+key+'.result',text)
        self.assertIn('name: v51-cloud-preflight-${{ github.sha }}',text)
        self.assertEqual(len(ci.expected_jobs(text)),len(FULL_GATES)+4)
    def test_observer_permissions_run_after_auth_and_before_report(self):
        text=(ci.ROOT/'.github/workflows/v51-replication-evidence.yml').read_text()
        self.assertLess(text.index('google-github-actions/auth@'),text.index('cloud_permissions --role observer'))
        self.assertLess(text.index('cloud_permissions --role observer'),text.index('cloud_preflight report'))
        self.assertIn('PERMISSION_ENVIRONMENT: v51-cloud-benchmark',text)
        self.assertIn('cat target/v51-preflight/permissions/summary.md',text)
    def test_report_missing_auth_retains_blocked_receipt_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ci.ROOT,text=True).strip()
            result=subprocess.run([os.sys.executable,'-m','scripts.v51.cloud_preflight','report','--source',sha,'--output',tmp],cwd=ci.ROOT,capture_output=True)
            self.assertEqual(result.returncode,2,result.stderr)
            receipt=json.loads((Path(tmp)/'preflight.json').read_text());self.assertEqual(receipt['status'],'BLOCKED')
            self.assertTrue((Path(tmp)/'summary.md').exists());self.assertFalse(receipt['resourcesCreated'])


if __name__=='__main__':unittest.main()
