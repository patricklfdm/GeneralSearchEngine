from copy import deepcopy
import base64
import hashlib
import io
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile
from . import cloud_recent_cleanup as recent, cloud_cleanup_bundle as bundle, cloud_cleanup_workflow as workflow
from . import cloud_preflight as f, cloud_authority as a
from . import test_cloud_native_cleanup as native_test
from .test_cloud_ci import Fixture, run, SOURCE, at
from .evidence import encoded,digest,strict

NOW=1800000100


def evidence(*,resources=False,active=False):
    case=native_test.NativeCleanupTest('test_empty_control_pass_is_observation_only_and_does_not_certify_delete_path');case.setUp()
    try:
        if resources or active:case.prepared(active=active)
        case.execute();cfg=deepcopy(case.cfg)
        files={'configuration.json':encoded(cfg)}
        for name in (bundle.FILES-{'configuration.json'})|bundle.OPTIONAL:
            if (case.output/name).exists():files[name]=(case.output/name).read_bytes()
        files['seal.json']=encoded(bundle.seal(files,SOURCE,NOW))
        return cfg,files
    finally:case.doCleanups()


class FixtureCleanup(Fixture):
    def __init__(self,files):
        self.files=deepcopy(files);self.run=run(123456,2);self.run.update(path=workflow.PATH,event='workflow_dispatch')
        steps=[dict(name=name,number=index+1,status='completed',conclusion='success',
                    started_at=at(t),completed_at=at(t+10))
               for index,(name,t) in enumerate(zip(workflow.REQUIRED,(NOW-140,NOW-130,NOW-100,NOW-70,NOW-50)))]
        self.jobs=[dict(id=801,run_id=123456,run_attempt=2,head_sha=SOURCE,name=workflow.JOB,status='completed',conclusion='success',
            started_at=at(NOW-150),completed_at=at(NOW-30),steps=steps)]
        self.data={};self.calls=[];self.queues={};self.downloads=[]
        self.record=dict(id=901,name=recent.name(self.run),expired=False,created_at=at(NOW-50),updated_at=at(NOW-40),expires_at=at(NOW+86400),
            workflow_run=dict(id=123456,repository_id=recent.credentials.REPOSITORY_ID,head_repository_id=recent.credentials.REPOSITORY_ID,
                head_sha=SOURCE,head_branch='master'))
        self.install();self.rezip()

    def install(self):
        self.data['branches/master']=dict(commit=dict(sha=SOURCE))
        self.page('actions/workflows/v52-manual-cleanup.yml/runs?branch=master&head_sha='+SOURCE,'workflow_runs',[self.run])
        self.data['actions/runs/123456']=deepcopy(self.run);self.data['actions/runs/123456/attempts/2']=deepcopy(self.run)
        self.page('actions/runs/123456/attempts/2/jobs','jobs',self.jobs)
        raw=workflow.render().encode()
        self.data['contents/'+workflow.PATH+'?ref='+SOURCE]=dict(type='file',path=workflow.PATH,encoding='base64',size=len(raw),
            sha=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),content=base64.b64encode(raw).decode())

    def rezip(self,entries=None):
        stream=io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',UserWarning)
            with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
                for name,data in (entries or self.files.items()):archive.writestr(name,data)
        self.raw=stream.getvalue();self.record.update(size_in_bytes=len(self.raw),digest='sha256:'+digest(self.raw))
        self.data['actions/artifacts/901']=deepcopy(self.record);self.page('actions/runs/123456/artifacts','artifacts',[self.record])

    def download(self,identity,output,size):
        if identity!=901 or size!=len(self.raw):raise AssertionError('wrong original artifact')
        self.downloads.append(identity);Path(output).write_bytes(self.raw)


class RecentCleanupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.cfg,cls.files=evidence()

    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.client=FixtureCleanup(self.files)
        self.out=self.root/'observed';self.out.mkdir();self.progress={}

    def collect(self):return recent.collect(self.out,self.cfg,SOURCE,self.client,lambda:NOW,self.progress)
    def replay(self,now=NOW):return recent.validate(recent.artifacts.read(self.out/'observation.json'),self.cfg,SOURCE,self.out/'cleanup.zip',now)

    def test_exact_original_cleanup_is_recent_but_not_paid_or_delete_admission(self):
        result=self.collect();self.assertEqual(result,self.replay())
        self.assertEqual('RECENT_CLEANUP_VERIFIED_NOT_ADMITTED',result['status']);self.assertEqual(2,result['runAttempt'])
        self.assertFalse(result['deletionPathExercised']);self.assertFalse(result['paidAdmission']);self.assertFalse(result['effectiveIamQualified'])
        self.assertEqual([901],self.client.downloads);self.assertLessEqual(result['expiresAt'],NOW+900)

    def test_complete_paginated_runs_and_artifacts_are_retained(self):
        rows=[]
        for i in range(205):
            row=deepcopy(self.client.run);row['id']=100+i;row['conclusion']='failure';rows.append(row)
        self.client.page('actions/workflows/v52-manual-cleanup.yml/runs?branch=master&head_sha='+SOURCE,'workflow_runs',rows+[self.client.run])
        records=[dict(id=1000+i,name='unrelated-'+str(i)) for i in range(205)]+[self.client.record]
        self.client.page('actions/runs/123456/artifacts','artifacts',records)
        self.collect();self.assertEqual(2,self.client.calls.count('actions/runs/123456/artifacts?per_page=100&page=3'))

    def test_latest_failed_queued_or_cancelled_run_never_falls_back_to_older_green(self):
        path='actions/workflows/v52-manual-cleanup.yml/runs?branch=master&head_sha='+SOURCE
        for status,conclusion in (('completed','failure'),('completed','cancelled'),('in_progress',None),('queued',None)):
            newer=deepcopy(self.client.run);newer.update(id=123457,status=status,conclusion=conclusion)
            self.client.page(path,'workflow_runs',[self.client.run,newer]);self.client.data['actions/runs/123457']=newer
            with self.assertRaises(ValueError):self.collect()
        self.assertEqual([],self.client.downloads)

    def test_changed_attempt_job_master_or_required_step_rejects(self):
        for mutate in (lambda c:c.data['actions/runs/123456/attempts/2'].update(run_attempt=3),
            lambda c:c.data['branches/master']['commit'].update(sha='f'*40),
            lambda c:c.jobs[0].update(run_attempt=1),
            lambda c:c.jobs[0]['steps'][2].update(conclusion='skipped'),
            lambda c:c.jobs[0]['steps'].reverse()):
            self.client=FixtureCleanup(self.files);mutate(self.client)
            if self.client.jobs[0]['steps'][0]['name']==workflow.UPLOAD:
                # API array ordering is not authoritative; wrong timestamps are.
                self.client.jobs[0]['steps'][0]['started_at']=at(NOW-160)
            self.client.page('actions/runs/123456/attempts/2/jobs','jobs',self.client.jobs)
            with self.assertRaises(ValueError):self.collect()

    def test_exact_attempt_and_upload_interval_artifact_is_required(self):
        for change in (dict(name='v52-cleanup-manual-123456-1'),dict(expired=True),dict(created_at=at(NOW-151)),
                       dict(updated_at=at(NOW)),dict(digest='missing'),dict(expires_at=at(NOW))):
            self.client=FixtureCleanup(self.files);self.client.record.update(change)
            self.client.data['actions/artifacts/901']=deepcopy(self.client.record)
            self.client.page('actions/runs/123456/artifacts','artifacts',[self.client.record])
            with self.assertRaises(ValueError):self.collect()

    def test_artifact_changed_during_download_is_rejected(self):
        self.client.queues['actions/artifacts/901']=[deepcopy(self.client.record),dict(self.client.record,digest='sha256:'+'f'*64)]
        with self.assertRaisesRegex(ValueError,'artifact changed'):self.collect()

    def test_workflow_source_is_checked_as_exact_original_blob(self):
        row=self.client.data['contents/'+workflow.PATH+'?ref='+SOURCE];row['content']=base64.b64encode(b'other workflow').decode()
        with self.assertRaises(ValueError):self.collect()

    def test_modified_zip_missing_files_extra_files_symlinks_and_duplicates_reject(self):
        symlink=zipfile.ZipInfo('receipt.json');symlink.external_attr=(stat.S_IFLNK|0o777)<<16
        for entries in ([(k,v) for k,v in self.files.items() if k!='receipt.json'],list(self.files.items())+[('outside',b'x')],
                        list(self.files.items())+[('receipt.json',b'{}')],
                        [(symlink if k=='receipt.json' else k,v) for k,v in self.files.items()]):
            self.client=FixtureCleanup(self.files);self.client.rezip(entries)
            self.out=self.root/str(len(list(self.root.iterdir())));self.out.mkdir()
            with self.assertRaises(ValueError):self.collect()

    def test_receipt_run_attempt_status_or_native_domain_cannot_be_substituted(self):
        for mutate in (lambda v:v['credentials']['context'].update(runAttempt=1),lambda v:v.update(status='FAIL'),
                       lambda v:v.update(scope='offline-v52-cleanup-only'),lambda v:v.update(paidAdmission=True),
                       lambda v:v.update(failure='copied'),lambda v:v.update(originalRequestSha256='a'*64)):
            files=deepcopy(self.files);value=strict(files['receipt.json']);mutate(value);files['receipt.json']=encoded(value)
            with self.assertRaises(ValueError):bundle.seal({k:v for k,v in files.items() if k!='seal.json'},SOURCE,NOW)

    def test_successful_github_job_with_waiting_lease_is_not_a_ready_cleanup(self):
        _,files=evidence(active=True);self.client=FixtureCleanup(files)
        with self.assertRaisesRegex(ValueError,'not original native PASS'):self.collect()

    def test_original_cleanup_and_fresh_collection_have_independent_ages(self):
        self.collect()
        with self.assertRaises(ValueError):self.replay(NOW+901)
        value=recent.artifacts.read(self.out/'observation.json');value['startedAt']=value['completedAt']=NOW+7200
        with self.assertRaisesRegex(ValueError,'completion stale'):recent.validate(value,self.cfg,SOURCE,self.out/'cleanup.zip',NOW+7200)

    def test_incomplete_or_capped_pagination_is_not_success(self):
        path='actions/workflows/v52-manual-cleanup.yml/runs?branch=master&head_sha='+SOURCE+'&per_page=100&page=1'
        for count in (2,1000):
            self.client.data[path]['total_count']=count
            with self.assertRaises(ValueError):self.collect()
        self.assertEqual([],self.client.downloads)

    def test_native_collector_owns_readonly_client_and_rechecks_source(self):
        out=self.root/'native'
        with patch.object(recent.reads,'source_configuration',return_value=self.cfg),patch.object(recent,'Network',return_value=self.client),patch.object(recent.time,'time',return_value=NOW):
            result=recent.collect_native(SOURCE,out)
        self.assertEqual('RECENT_CLEANUP_VERIFIED_NOT_ADMITTED',result['status'])
        with self.assertRaises(TypeError):recent.collect_native(SOURCE,self.root/'injected',get=self.client.get)
        out=self.root/'changed'
        with patch.object(recent.reads,'source_configuration',side_effect=[self.cfg,dict(self.cfg,projectNumber='999')]),patch.object(recent,'Network',return_value=self.client),patch.object(recent.time,'time',return_value=NOW):
            with self.assertRaisesRegex(ValueError,'source changed'):recent.collect_native(SOURCE,out)
        self.assertFalse((out/'receipt.json').exists());self.assertTrue((out/'failure.json').exists())

    def test_native_client_rejects_mutations_foreign_workflows_and_paths(self):
        client=recent.Network(self.root/'requests')
        client.authorize_path('actions/runs/123456/attempts/2/jobs?per_page=100&page=1')
        for path in ('actions/runs/123456/rerun','actions/runs/123456/cancel','actions/artifacts/901/zip',
                     'actions/workflows/ci.yml/runs?branch=master&head_sha='+SOURCE+'&per_page=100&page=1',
                     'https://evil.invalid','contents/secret?ref='+SOURCE):
            with self.assertRaises(ValueError):client.authorize_path(path)


if __name__=='__main__':unittest.main()
