"""Synthetic GitHub observations; no hosted CI execution or remote request."""
import base64
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import tempfile
import unittest
from . import cloud_ci as c
from .evidence import encoded

NOW = 1_800_000_000
SOURCE = 'a'*40


def at(value): return datetime.fromtimestamp(value, timezone.utc).isoformat().replace('+00:00', 'Z')


def run(identity=10, attempt=2):
    repo = dict(id=c.credentials.REPOSITORY_ID, full_name=c.credentials.REPOSITORY, owner=dict(id=c.credentials.OWNER_ID))
    return dict(id=identity, run_attempt=attempt, workflow_id=123, head_sha=SOURCE, head_branch='master', path=c.WORKFLOW,
                event='push', status='completed', conclusion='success', repository=deepcopy(repo), head_repository=deepcopy(repo))


def jobs(shape, current):
    result = []
    for index, (name, row) in enumerate(shape['jobs'].items()):
        start = NOW-6000
        steps = [dict(name=step, number=i+1, status='completed', conclusion='success', started_at=at(start+i*2),
                      completed_at=at(start+i*2+1)) for i, step in enumerate(row['steps'])]
        result.append(dict(id=1000+index, run_id=current['id'], run_attempt=current['run_attempt'], head_sha=SOURCE,
            name=name, status='completed', conclusion='success', created_at=at(start-1), started_at=at(start),
            completed_at=at(start+len(steps)*2+10), runner_id=10000+index, runner_name='fixture-'+str(index), steps=steps))
    return result


class Fixture:
    def __init__(self, shape):
        self.shape = deepcopy(shape); self.run = run(); self.jobs = jobs(shape, self.run); self.data = {}; self.calls = []
        self.queues = {}; self.install()

    def page(self, path, key, rows):
        for number in range(max(1, (len(rows)+99)//100)):
            self.data[path+('&' if '?' in path else '?')+f'per_page=100&page={number+1}'] = {
                'total_count':len(rows), key:deepcopy(rows[number*100:(number+1)*100])}

    def install(self):
        self.data['branches/master'] = dict(commit=dict(sha=SOURCE))
        for path in (c.WORKFLOW, c.standalone.WORKFLOW):
            self.page('actions/workflows/'+path.rsplit('/',1)[1]+'/runs?branch=master&head_sha='+SOURCE,
                      'workflow_runs', [self.run] if self.run['path'] == path else [])
        self.data['actions/runs/10'] = deepcopy(self.run); self.data['actions/runs/10/attempts/2'] = deepcopy(self.run)
        self.page('actions/runs/10/attempts/2/jobs', 'jobs', self.jobs)
        for path, text in self.shape['sourceFiles'].items():
            raw = text.encode(); self.data['contents/'+path+'?ref='+SOURCE] = dict(type='file', path=path, size=len(raw),
                sha=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(), encoding='base64', content=base64.b64encode(raw).decode())

    def get(self, path):
        self.calls.append(path)
        if self.queues.get(path): return deepcopy(self.queues[path].pop(0))
        return deepcopy(self.data[path])


class FullCiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.shape = c.contract()

    def setUp(self): self.fixture = Fixture(self.shape)

    def observe(self): return c.observe(SOURCE, self.shape, self.fixture.get, lambda:NOW)

    def test_existing_registry_expands_all_current_suites_and_visible_required_steps(self):
        registry = c.suites.check()
        self.assertEqual(set(c.suites.expanded_names(registry)), set(self.shape['jobs']))
        self.assertEqual(8, sum(row['id'].startswith('v52-') for row in self.shape['jobs'].values()))
        self.assertEqual(8, sum(row['id'].startswith('python-v52-') for row in self.shape['jobs'].values()))
        self.assertIn(c.BUILD_STEP, self.shape['jobs'][c.BUILD]['steps'])
        self.assertNotIn('Validate documentation-only contract changes', self.shape['jobs']['Change scope']['steps'])

    def test_complete_exact_master_full_ci_is_only_a_prerequisite(self):
        value = self.observe(); proof = c.validate(value, SOURCE, self.shape, NOW)
        self.assertEqual('FULL_CI_VERIFIED_NOT_ADMITTED', proof['status']); self.assertFalse(proof['paidAdmission'])
        self.assertEqual(len(self.shape['jobs']), proof['jobs']); self.assertEqual(2, proof['attempt'])
        self.assertEqual(2, self.fixture.calls.count('actions/runs/10/attempts/2/jobs?per_page=100&page=1'))

    def test_push_manual_and_schedule_full_ci_are_valid_without_accepting_prs(self):
        for event in c.EVENTS:
            self.fixture.run['event'] = event; self.fixture.install(); self.observe()
        self.fixture.run['event'] = 'pull_request'; self.fixture.install()
        with self.assertRaisesRegex(ValueError, 'no exact-master'): self.observe()

    def test_failed_cancelled_pending_or_docs_run_never_falls_back_to_older_green(self):
        path = 'actions/workflows/ci.yml/runs?branch=master&head_sha='+SOURCE
        for status, conclusion in (('completed', 'failure'), ('completed', 'cancelled'), ('queued', None), ('in_progress', None)):
            old = run(9); self.fixture.run.update(status=status, conclusion=conclusion); self.fixture.install()
            self.fixture.page(path, 'workflow_runs', [old, self.fixture.run])
            with self.assertRaisesRegex(ValueError, 'not completed green'): self.observe()

    def test_any_missing_duplicate_skipped_or_wrong_attempt_job_rejects(self):
        original = self.observe()
        for change in (lambda v:v['jobs'].pop(), lambda v:v['jobs'].append(v['jobs'][0]),
                       lambda v:v['jobs'][0].update(conclusion='skipped'), lambda v:v['jobs'][0].update(run_attempt=1),
                       lambda v:v['jobs'][0].update(run_id=True), lambda v:v['jobs'][0].update(head_sha='f'*40),
                       lambda v:v['jobs'][0].update(id=v['jobs'][1]['id'])):
            value = deepcopy(original); change(value)
            with self.assertRaises(ValueError): c.validate(value, SOURCE, self.shape, NOW)

    def test_integration_which_skips_whole_canonical_cannot_admit_cloud(self):
        value = self.observe()
        for job in value['jobs']:
            if self.shape['jobs'][job['name']]['id'] == 'v51-owned-canonical': job['conclusion'] = 'skipped'
        with self.assertRaisesRegex(ValueError, 'failed/skipped'): c.validate(value, SOURCE, self.shape, NOW)

    def test_successful_job_cannot_hide_skipped_or_missing_verification_step(self):
        original = self.observe()
        for key, val in (('conclusion','skipped'), ('status','in_progress'), ('number',True), ('started_at',at(NOW+1))):
            value = deepcopy(original); job = next(v for v in value['jobs'] if v['name'] == 'V5.2 measurement consumers')
            step = next(s for s in job['steps'] if s['name'] == 'Verify complete V5.2 consumers qualification')
            step[key] = val
            with self.assertRaises(ValueError): c.validate(value, SOURCE, self.shape, NOW)
        value = deepcopy(original); value['jobs'][0]['steps'].pop()
        with self.assertRaisesRegex(ValueError, 'step missing'): c.validate(value, SOURCE, self.shape, NOW)

    def test_duplicate_named_steps_and_duplicate_step_numbers_reject(self):
        for same_number in (False, True):
            value = self.observe(); step = deepcopy(value['jobs'][0]['steps'][0])
            if not same_number: step['number'] = 999
            value['jobs'][0]['steps'].append(step)
            with self.assertRaisesRegex(ValueError, 'duplicate'): c.validate(value, SOURCE, self.shape, NOW)

    def test_fork_wrong_owner_workflow_or_source_rejects(self):
        original = self.observe()
        for change in (lambda r:r['head_repository'].update(id=1), lambda r:r['repository'].update(id=True),
                       lambda r:r['repository']['owner'].update(id=1), lambda r:r.update(path='.github/workflows/other.yml'),
                       lambda r:r.update(head_sha='f'*40), lambda r:r.update(head_branch='other')):
            value = deepcopy(original); change(value['run'])
            with self.assertRaises(ValueError): c.validate(value, SOURCE, self.shape, NOW)

    def test_unrelated_repository_metadata_does_not_change_execution_identity(self):
        value = self.observe()
        value['runAfter']['repository'].update(stargazers_count=123, updated_at=at(NOW))
        value['runAttempt']['head_repository'].update(size=321)
        value['runsAfter'][0]['repository'].update(description='updated project description')
        c.validate(value, SOURCE, self.shape, NOW)

    def test_source_files_git_blob_digest_and_encoding_are_independent(self):
        original = self.observe(); path = c.WORKFLOW
        for key, val in (('content',base64.b64encode(b'replacement').decode()), ('size',True), ('sha','f'*40),
                         ('encoding','none'), ('path','other'), ('type','symlink')):
            value = deepcopy(original); value['sourceContents'][path][key] = val
            with self.assertRaises(ValueError): c.validate(value, SOURCE, self.shape, NOW)
        value = deepcopy(original); del value['sourceContents'][path]
        with self.assertRaisesRegex(ValueError, 'source file inventory'): c.validate(value, SOURCE, self.shape, NOW)

    def test_master_move_before_or_during_collection_rejects(self):
        self.fixture.data['branches/master'] = dict(commit=dict(sha='f'*40))
        with self.assertRaisesRegex(ValueError, 'not current master'): self.observe()
        self.fixture.queues['branches/master'] = [dict(commit=dict(sha=SOURCE)), dict(commit=dict(sha='f'*40))]
        with self.assertRaisesRegex(ValueError, 'master/source moved'): self.observe()

    def test_newer_run_appearing_during_observation_rejects(self):
        path = 'actions/workflows/ci.yml/runs?branch=master&head_sha='+SOURCE+'&per_page=100&page=1'
        self.fixture.queues[path] = [deepcopy(self.fixture.data[path]), dict(total_count=2, workflow_runs=[run(11), run()])]
        with self.assertRaisesRegex(ValueError, 'latest run changed'): self.observe()

    def test_attempt_changes_and_exact_attempt_endpoint_disagreement_reject(self):
        for key in ('runAfter', 'runAttempt', 'run'):
            value = self.observe(); value[key]['run_attempt'] = 3
            with self.assertRaisesRegex(ValueError, 'run/attempt changed|latest run changed'): c.validate(value, SOURCE, self.shape, NOW)

    def test_job_steps_changing_between_inventory_reads_reject(self):
        path = 'actions/runs/10/attempts/2/jobs?per_page=100&page=1'; changed = deepcopy(self.fixture.data[path])
        changed['jobs'][0]['steps'][0]['conclusion'] = 'failure'
        self.fixture.queues[path] = [self.fixture.data[path], changed]
        with self.assertRaisesRegex(ValueError, 'execution changed'): self.observe()

    def test_pagination_crosses_multiple_pages_and_selects_latest_not_first(self):
        rows = [run(100+i) for i in range(205)]; self.fixture.page('custom', 'rows', rows)
        self.assertEqual(rows, c.pages(self.fixture.get, 'custom', 'rows'))
        self.assertEqual(304, c.latest(list(reversed(rows)), SOURCE)['id'])
        self.assertEqual(['custom?per_page=100&page='+str(i) for i in (1,2,3)], self.fixture.calls)

    def test_pagination_rejects_short_pages_count_drift_duplicate_ids_and_search_cap(self):
        rows = [run(100+i) for i in range(101)]
        for mutate in (lambda d:d['custom?per_page=100&page=1']['rows'].pop(),
                       lambda d:d['custom?per_page=100&page=2'].update(total_count=100),
                       lambda d:d['custom?per_page=100&page=2']['rows'][0].update(id=100),
                       lambda d:d['custom?per_page=100&page=1'].update(total_count=True)):
            self.fixture.page('custom','rows',rows); mutate(self.fixture.data)
            with self.assertRaises(ValueError): c.pages(self.fixture.get, 'custom', 'rows')
        path = 'actions/workflows/ci.yml/runs?branch=master&head_sha='+SOURCE+'&per_page=100&page=1'
        self.fixture.data[path]['total_count'] = 1000
        with self.assertRaises(ValueError): c.listing(self.fixture.get, SOURCE)

    def test_job_timestamps_need_zones_order_and_no_future(self):
        for key, val in (('started_at',at(NOW+1)), ('completed_at',at(NOW+1)), ('started_at','2026-01-01T00:00:00')):
            value = self.observe(); value['jobs'][0][key] = val
            with self.assertRaises(ValueError): c.validate(value, SOURCE, self.shape, NOW)


class BuildAdmissionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.shape=c.contract()

    def setUp(self):self.f=Fixture(self.shape)

    def observe(self):return c.observe(SOURCE,self.shape,self.f.get,lambda:NOW,require_full=False)

    def validate(self,value):return c.validate(value,SOURCE,self.shape,NOW,require_full=False)

    def test_temporary_cloud_policy_does_not_claim_full_ci(self):
        self.assertFalse(c.REQUIRE_FULL_CI)
        for status,conclusion in (('in_progress',None),('completed','failure'),('completed','cancelled')):
            self.f.run.update(status=status,conclusion=conclusion)
            self.f.jobs=[job for job in self.f.jobs if job['name']==c.BUILD]
            self.f.install();proof=self.validate(self.observe())
            self.assertEqual('BUILD_CI_VERIFIED_NOT_ADMITTED',proof['status'])
            self.assertEqual(1,proof['jobs']);self.assertFalse(proof['fullCiRequired'])
            self.assertFalse(proof['paidAdmission']);self.assertFalse(proof['fullRemoteQualification'])

    def test_unrelated_jobs_and_overall_result_can_change_during_collection(self):
        self.f.run.update(status='in_progress',conclusion=None);self.f.install()
        completed=dict(self.f.run,status='completed',conclusion='failure')
        self.f.queues['actions/runs/10']=[self.f.run,completed]
        path='actions/runs/10/attempts/2/jobs?per_page=100&page=1'
        changed=deepcopy(self.f.data[path])
        for job in changed['jobs']:
            if job['name']!=c.BUILD:job.update(status='in_progress',conclusion=None,completed_at=None)
        self.f.queues[path]=[self.f.data[path],changed]
        self.validate(self.observe())

    def test_missing_failed_skipped_unfinished_or_replaced_build_still_rejects(self):
        original=self.observe()
        for change in (
            lambda v:v.update(jobs=[j for j in v['jobs'] if j['name']!=c.BUILD]),
            lambda v:next(j for j in v['jobs'] if j['name']==c.BUILD).update(conclusion='failure'),
            lambda v:next(j for j in v['jobs'] if j['name']==c.BUILD).update(conclusion='skipped'),
            lambda v:next(j for j in v['jobs'] if j['name']==c.BUILD).update(status='in_progress'),
            lambda v:next(j for j in v['jobs'] if j['name']==c.BUILD)['steps'].pop(),
            lambda v:next(j for j in v['jobsAfter'] if j['name']==c.BUILD).update(id=999999),
        ):
            value=deepcopy(original);change(value)
            with self.assertRaises(ValueError):self.validate(value)

    def test_source_attempt_repository_and_latest_run_bindings_still_reject(self):
        original=self.observe()
        for change in (
            lambda v:v.update(masterAfter='f'*40),
            lambda v:v['runAfter'].update(run_attempt=3),
            lambda v:v['runAttempt'].update(head_sha='f'*40),
            lambda v:v['run']['repository'].update(id=1),
            lambda v:v['run'].update(event='pull_request'),
            lambda v:v['runsAfter'].append(run(11)),
            lambda v:v['sourceContents'][c.WORKFLOW].update(sha='f'*40),
        ):
            value=deepcopy(original);change(value)
            with self.assertRaises(ValueError):self.validate(value)

    def test_manual_build_appearing_while_observing_ci_changes_selected_source(self):
        path='actions/workflows/v52-cloud-build.yml/runs?branch=master&head_sha='+SOURCE+'&per_page=100&page=1'
        manual=dict(run(11),path=c.standalone.WORKFLOW,event='workflow_dispatch',workflow_id=456)
        self.f.queues[path]=[dict(total_count=0,workflow_runs=[]),dict(total_count=1,workflow_runs=[manual])]
        with self.assertRaisesRegex(ValueError,'latest run changed'):self.observe()


class StandaloneBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.shape=c.contract()

    def setUp(self):
        self.f=Fixture(self.shape)
        self.f.run.update(path=c.standalone.WORKFLOW,event='workflow_dispatch',workflow_id=456)
        self.f.jobs=jobs(dict(jobs=self.shape['standaloneJobs']),self.f.run);self.f.install()

    def observe(self):return c.observe(SOURCE,self.shape,self.f.get,lambda:NOW,require_full=False)

    def test_manual_build_without_any_normal_ci_run_is_verified(self):
        proof=c.validate(self.observe(),SOURCE,self.shape,NOW,require_full=False)
        self.assertEqual(c.standalone.WORKFLOW,proof['workflow']);self.assertEqual(1,proof['jobs'])
        self.assertFalse(proof['fullCiRequired']);self.assertFalse(proof['paidAdmission'])

    def test_manual_build_has_priority_even_over_newer_ci(self):
        self.f.page('actions/workflows/ci.yml/runs?branch=master&head_sha='+SOURCE,'workflow_runs',[run(20)])
        self.assertEqual(10,self.observe()['run']['id'])

    def test_failed_manual_build_cannot_fall_back_to_green_ci(self):
        self.f.run['conclusion']='failure';self.f.jobs[0]['conclusion']='failure';self.f.install()
        self.f.page('actions/workflows/ci.yml/runs?branch=master&head_sha='+SOURCE,'workflow_runs',[run(20)])
        with self.assertRaisesRegex(ValueError,'failed/skipped'):self.observe()

    def test_pending_skipped_missing_or_incomplete_producer_rejects(self):
        original=self.observe()
        for change in (lambda v:v.update(jobs=[]),
                       lambda v:v['jobs'][0].update(status='in_progress',conclusion=None),
                       lambda v:v['jobs'][0].update(conclusion='skipped'),
                       lambda v:v['jobs'][0]['steps'].pop()):
            value=deepcopy(original);change(value)
            with self.assertRaises(ValueError):c.validate(value,SOURCE,self.shape,NOW,require_full=False)

    def test_new_manual_run_during_collection_rejects(self):
        path='actions/workflows/v52-cloud-build.yml/runs?branch=master&head_sha='+SOURCE+'&per_page=100&page=1'
        self.f.queues[path]=[deepcopy(self.f.data[path]),dict(total_count=2,workflow_runs=[self.f.run,dict(self.f.run,id=11)])]
        with self.assertRaisesRegex(ValueError,'latest run changed'):self.observe()

    def test_source_repository_event_attempt_and_workflow_substitution_reject(self):
        original=self.observe()
        for change in (lambda v:v['run'].update(head_branch='branch'),
                       lambda v:v['run'].update(event='push'),lambda v:v['run'].update(event='pull_request'),
                       lambda v:v['run']['head_repository'].update(id=99),
                       lambda v:v['runAfter'].update(run_attempt=3),
                       lambda v:v['runAttempt'].update(path=c.WORKFLOW),
                       lambda v:v['sourceContents'][c.standalone.WORKFLOW].update(sha='f'*40)):
            value=deepcopy(original);change(value)
            with self.assertRaises(ValueError):c.validate(value,SOURCE,self.shape,NOW,require_full=False)

    def test_full_policy_never_uses_manual_build_in_place_of_ci(self):
        with self.assertRaisesRegex(ValueError,'no exact-master'):
            c.observe(SOURCE,self.shape,self.f.get,lambda:NOW,require_full=True)
        with self.assertRaises(ValueError):c.validate(self.observe(),SOURCE,self.shape,NOW)

    def test_both_producer_lists_are_completely_paginated(self):
        path='actions/workflows/v52-cloud-build.yml/runs?branch=master&head_sha='+SOURCE
        rows=[dict(self.f.run,id=100+i) for i in range(205)]
        self.f.page(path,'workflow_runs',rows)
        self.f.page('actions/workflows/ci.yml/runs?branch=master&head_sha='+SOURCE,'workflow_runs',[run()])
        result=c.listing(self.f.get,SOURCE,require_full=False)
        self.assertEqual(206,len(result));self.assertEqual(304,c.latest(result,SOURCE,require_full=False)['id'])
        self.assertIn(path+'&per_page=100&page=3',self.f.calls)

    def test_workflow_contract_keeps_original_build_tests_and_uploads(self):
        workflow=c.standalone.render();self.assertEqual(workflow,c.suites.read(c.ROOT,c.standalone.WORKFLOW))
        self.assertIn("if: ${{ github.ref == 'refs/heads/master' }}",workflow)
        self.assertIn('  workflow_dispatch:',workflow);self.assertEqual(4,workflow.count('retention-days: 90'))
        for forbidden in ('  push:','  pull_request:','  schedule:','id-token:', 'environment:', '-DskipTests', 'self-hosted'):
            self.assertNotIn(forbidden,workflow)
        self.assertIn('clean package',workflow)
        self.assertEqual(self.shape['jobs'][c.BUILD]['steps'],self.shape['standaloneJobs'][c.standalone.JOB]['steps'])

    def test_workflow_drift_cannot_silently_drop_tests_or_grant_cloud_access(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'.github/workflows').mkdir(parents=True)
            (root/c.WORKFLOW).write_text(c.suites.read(c.ROOT,c.WORKFLOW))
            for old,new in (('clean package','clean package -DskipTests'),('contents: read','id-token: write'),
                            ('retention-days: 90','retention-days: 1')):
                (root/c.standalone.WORKFLOW).write_text(c.standalone.render().replace(old,new))
                with self.assertRaisesRegex(ValueError,'workflow changed'):c.standalone.contract(root)


if __name__ == '__main__': unittest.main()
