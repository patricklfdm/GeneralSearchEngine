"""Synthetic GitHub/archive fixtures, not real identity or cloud qualification."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import zipfile
from . import cloud_recent_cleanup as r, cloud_preflight as p, cloud_permissions as permissions
from . import test_cloud_cleanup_observation as o, performance_model as m


def fixture(trigger='manual', case='no-lease'):
    model, _, _ = o.fixture(case, trigger)
    cfg = model['cfg']; source = model['source']; binding = model['binding']
    run = model['observed_run']['before']; now = model['receipt']['checkedAt']+2
    env = r.context(cfg, source, trigger, run)
    pb = permissions.identity(cfg, env, role=trigger, source=source, checkout=source)
    plan = permissions.plan(cfg, trigger)
    obs = dict(pb, execution='workflow-permission-probes', startedAt=now-3, completedAt=now-3,
               credentialExchangeCompleted=True, planSha256=m.sha(m.canonical(plan)),
               observations={k:dict(permissions=v['required']) for k,v in plan.items()})
    files = dict(zip(r.FILES, [binding, binding, model['receipt'], pb, obs,
                             permissions.evaluate(cfg, pb, obs, now=now-3)]))
    artifact = dict(id=88, name=f"v51-cleanup-{trigger}-{run['id']}-{run['run_attempt']}", expired=False,
                    workflow_run=dict(id=run['id'], head_sha=source, head_branch='master',
                                      repository_id=r.ci.REPOSITORY_ID, head_repository_id=r.ci.REPOSITORY_ID))
    listing = dict(total_count=1, workflow_runs=[run])
    value = dict(schema='gse-v51-recent-cleanup-v1', source=source, trigger=trigger,
                 configurationSha256=p.configuration(cfg), startedAt=now, completedAt=now,
                 runsBefore=deepcopy(listing), runsAfter=deepcopy(listing), run=model['observed_run'], artifact=artifact)
    return cfg, source, value, files, now


def pack(root, value, files, *, extra=None):
    path = root/'cleanup.zip'
    with zipfile.ZipFile(path, 'w') as z:
        for name, content in files.items():z.writestr(name, m.canonical(content))
        if extra is not None:z.writestr(extra, '{}')
    value['artifact'].update(size_in_bytes=path.stat().st_size, digest='sha256:'+m.sha(path.read_bytes()))
    return path


class RecentCleanupTest(unittest.TestCase):
    def setUp(self):
        self.cfg,self.source,self.value,self.files,self.now=fixture()
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def validate(self):
        return r.validate(self.cfg,self.source,self.value,pack(self.root,self.value,self.files),now=self.now)

    def test_manual_pass_suffices_without_any_schedule_record(self):
        result=self.validate();self.assertEqual('PASS',result['status'])
        self.assertFalse(result['detail']['scheduleRequired']);self.assertFalse(result['detail']['paidAdmission'])
        self.assertNotIn('schedule',m.canonical(self.value).decode())

    def test_both_triggers_and_expired_release_are_supported_independently(self):
        for trigger in ('manual','schedule'):
            for case in ('no-lease','expired-manual'):
                self.cfg,self.source,self.value,self.files,self.now=fixture(trigger,case)
                self.assertEqual('PASS',self.validate()['status'])

    def test_waiting_or_failed_reconciliation_cannot_count_as_pass(self):
        for status in ('WAITING','FAIL'):
            self.files['reconciliation/receipt.json']['status']=status
            with self.assertRaises(ValueError):self.validate()

    def test_latest_failed_or_waiting_run_cannot_hide_behind_older_success(self):
        for status in ('failure','in_progress'):
            newer=deepcopy(self.value['runsBefore']['workflow_runs'][0]);newer['id']+=1
            if status=='failure':newer['conclusion']='failure'
            else:newer.update(status=status,conclusion=None)
            listing=dict(total_count=2,workflow_runs=[self.value['run']['before'],newer])
            self.assertEqual(newer,r.latest(listing,self.source))
            self.value['runsBefore']=self.value['runsAfter']=listing
            with self.assertRaises(ValueError):self.validate()

    def test_failed_skipped_missing_duplicate_steps_block(self):
        original=deepcopy(self.value['run']['jobs'])
        for change in ('failure','skipped','missing','duplicate'):
            self.value['run']['jobs']=deepcopy(original);steps=self.value['run']['jobs']['jobs'][0]['steps']
            if change=='missing':steps.pop()
            elif change=='duplicate':steps.append(steps[0])
            else:steps[0]['conclusion']=change
            with self.assertRaises(ValueError):self.validate()

    def test_source_attempt_and_repository_drift_block(self):
        original=deepcopy(self.value)
        mutations=[lambda v:v.update(source='0'*40),
                   lambda v:v['run']['after'].update(run_attempt=3),
                   lambda v:v['run']['attempt']['repository'].update(id=1),
                   lambda v:v['runsAfter']['workflow_runs'][0].update(id=2),
                   lambda v:v['artifact']['workflow_run'].update(head_sha='0'*40),
                   lambda v:v['artifact'].update(name='wrong',expired=True)]
        for change in mutations:
            self.value=deepcopy(original);change(self.value)
            with self.assertRaises(ValueError):self.validate()

    def test_cleanup_two_hour_bound_and_observation_freshness(self):
        start=self.now
        self.now=start+899;self.assertEqual('PASS',self.validate()['status'])
        self.now=start+900
        with self.assertRaises(ValueError):self.validate()
        self.value.update(startedAt=start+7200,completedAt=start+7200);self.now=start+7200
        with self.assertRaisesRegex(ValueError,'completion stale'):self.validate()
        self.now=start;self.value.update(startedAt=start-2,completedAt=start)
        with self.assertRaisesRegex(ValueError,'completion stale/future'):self.validate()

    def test_expiry_is_capped_by_original_cleanup_completion(self):
        end=r.ci.timestamp(self.value['run']['jobs']['jobs'][0]['completed_at'])
        self.now=end+7199;self.value.update(startedAt=self.now,completedAt=self.now)
        self.assertEqual(end+7200,self.validate()['detail']['expiresAt'])
        self.now=end+7200
        with self.assertRaisesRegex(ValueError,'completion stale'):self.validate()

    def test_offline_failed_or_forged_permission_receipt_rejected(self):
        original=deepcopy(self.files)
        changes=[lambda f:f['permissions/observations.json'].update(execution='offline-permission-probes'),
                 lambda f:f['permissions/observations.json']['observations']['project'].update(permissions=[]),
                 lambda f:f['permissions/receipt.json'].update(status='BLOCKED'),
                 lambda f:f['permissions/binding.json'].update(runAttempt=88),
                 lambda f:f['permissions/observations.json'].update(startedAt=self.now-800)]
        for change in changes:
            self.files=deepcopy(original);change(self.files)
            with self.assertRaises(ValueError):self.validate()

    def test_cleanup_execution_identity_and_absence_cannot_be_forged(self):
        self.cfg,self.source,self.value,self.files,self.now=fixture(case='expired-manual')
        original=deepcopy(self.files)
        for change in (lambda v:v.update(execution='offline-native-cleanup-entry'),
                       lambda v:v.update(cleanupReady=True),lambda v:v.update(credentialExchangeCompleted=False),
                       lambda v:v['reconciliation'].update(leaseReleased=False),
                       lambda v:v['reconciliation']['cleanup'].update(leftovers=['still present']),
                       lambda v:v['reconciliation']['cleanup']['checks'][0].update(absent=False)):
            self.files=deepcopy(original);change(self.files['reconciliation/receipt.json'])
            with self.assertRaises(ValueError):self.validate()

    def test_archive_hash_missing_files_duplicates_and_unsafe_paths(self):
        archive=pack(self.root,self.value,self.files)
        with self.assertRaisesRegex(ValueError,'digest mismatch'):r.contents(archive,'0'*64)
        for extra in ('../outside','/absolute','permissions\\escape'):
            archive=pack(self.root,self.value,self.files,extra=extra)
            with self.assertRaisesRegex(ValueError,'unsafe'):r.contents(archive,self.value['artifact']['digest'][7:])
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            archive=pack(self.root,self.value,self.files,extra='permissions/binding.json')
        with self.assertRaisesRegex(ValueError,'inventory'):r.contents(archive,self.value['artifact']['digest'][7:])
        self.files.pop('permissions/binding.json')
        with self.assertRaisesRegex(ValueError,'missing evidence'):self.validate()

    def test_saved_archive_tamper_and_metadata_size_mismatch_block(self):
        from .remote_command import write_once
        archive=pack(self.root,self.value,self.files)
        self.value['artifact']['size_in_bytes']+=1
        with self.assertRaisesRegex(ValueError,'size mismatch'):
            r.validate(self.cfg,self.source,self.value,archive,now=self.now)
        self.value['artifact']['size_in_bytes']-=1
        write_once(self.root/'observations.json',self.value)
        raw=archive.read_bytes();archive.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
        self.assertIn('digest mismatch',r.check_saved(self.cfg,self.source,self.root,now=self.now)['reason'])

    def test_missing_or_failed_collection_is_blocked_with_actionable_reason(self):
        result=r.check_saved(self.cfg,self.source,self.root,now=self.now)
        self.assertEqual('BLOCKED',result['status']);self.assertIn('manual PASS',result['reason'])
        self.value['failure']=dict(type='TimeoutError')
        with self.assertRaises(ValueError):self.validate()

    def api(self):
        run=self.value['run'];binding=self.files['identity/binding.json'];rid=binding['runId'];attempt=binding['runAttempt']
        query=f'actions/workflows/v51-manual-cleanup.yml/runs?branch=master&head_sha={self.source}&per_page=100'
        data={query:self.value['runsBefore'],f'actions/runs/{rid}':run['after'],
              f'actions/runs/{rid}/attempts/{attempt}':run['attempt'],
              f'actions/runs/{rid}/attempts/{attempt}/jobs?per_page=100':run['jobs'],
              f'actions/runs/{rid}/artifacts?per_page=100':dict(total_count=1,artifacts=[self.value['artifact']]),
              'actions/artifacts/88':self.value['artifact']}
        return query,data

    def test_collection_queries_only_manual_and_replays_downloaded_archive(self):
        payload=pack(self.root,self.value,self.files).read_bytes();query,data=self.api();paths=[]
        def get(path):paths.append(path);return deepcopy(data[path])
        def fetch(identifier,path):self.assertEqual(88,identifier);path.write_bytes(payload)
        out=self.root/'collected'
        result=r.collect(self.cfg,self.source,out,get=get,fetch=fetch,wall=lambda:self.now)
        self.assertEqual('PASS',result['status'],result);self.assertEqual(2,paths.count(query))
        self.assertFalse(any('expired-cleanup' in path for path in paths))
        self.assertEqual(result,r.check_saved(self.cfg,self.source,out,now=self.now))

    def test_rerun_new_run_and_artifact_change_during_download_block(self):
        payload=pack(self.root,self.value,self.files).read_bytes()
        for kind in ('rerun','new-run','artifact'):
            query,data=self.api();data=deepcopy(data);downloaded=False
            def fetch(identifier,path):
                nonlocal downloaded
                path.write_bytes(payload);downloaded=True
            def get(path):
                result=deepcopy(data[path])
                if downloaded:
                    if kind in ('new-run','rerun') and path==query:
                        result['workflow_runs'][0]['id' if kind=='new-run' else 'run_attempt']+=1
                    if kind=='artifact' and path=='actions/artifacts/88':result['digest']='sha256:'+'0'*64
                return result
            result=r.collect(self.cfg,self.source,self.root/kind,get=get,fetch=fetch,wall=lambda:self.now)
            self.assertEqual('BLOCKED',result['status'],(kind,result))

    def test_collector_retains_sanitized_failure_without_throwing_before_report(self):
        def get(path):raise ValueError('do not retain credential body')
        out=self.root/'failed';result=r.collect(self.cfg,self.source,out,get=get,wall=lambda:self.now)
        self.assertEqual('BLOCKED',result['status']);self.assertNotIn('credential body',(out/'observations.json').read_text())

    def test_report_requires_cleanup_and_preserves_original_expiry(self):
        import contextlib
        import io
        from unittest.mock import patch
        from .remote_command import read, write_once
        from . import cloud_preflight_qualification as q
        cfg,github,provider=q.fixture()
        baseline=p.evaluate(cfg,q.SOURCE,github,provider,now=q.NOW)
        configuration=self.root/'configuration.json';write_once(configuration,self.cfg)
        original_identity=permissions.identity
        def observer_only(cfg,env,**kwargs):
            return {} if kwargs['role']=='observer' else original_identity(cfg,env,**kwargs)
        for available in (False,True):
            out=self.root/str(available);out.mkdir()
            if available:
                cleanup=out/'cleanup';cleanup.mkdir()
                pack(cleanup,self.value,self.files);write_once(cleanup/'observations.json',self.value)
            with patch('sys.argv',['preflight','report','--source',self.source,'--output',str(out)]),\
                 patch.object(p,'CONFIG',configuration),\
                 patch.object(p.subprocess,'check_output',return_value=self.source+'\n'),\
                 patch.object(p,'evaluate',return_value=deepcopy(baseline)),\
                 patch.object(permissions,'identity',side_effect=observer_only),\
                 patch.object(permissions,'check_saved',return_value=dict(status='PASS')),\
                 patch.object(p.time,'time',return_value=self.now),contextlib.redirect_stdout(io.StringIO()):
                if available:p.main()
                else:
                    with self.assertRaises(SystemExit) as error:p.main()
                    self.assertEqual(2,error.exception.code)
            result=read(out/'preflight.json')
            self.assertEqual('OBSERVATIONS_READY' if available else 'BLOCKED',result['status'])
            if available:self.assertEqual(self.now+900,result['expiresAt'])
            self.assertFalse(result['paidAdmission'])


if __name__=='__main__':unittest.main()
