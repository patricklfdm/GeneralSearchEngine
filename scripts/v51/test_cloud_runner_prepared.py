from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from . import cloud_runner_prepared as p, cloud_runner_admission_qualification as q
from . import performance_model as m, remote_command as c


def public_fixture(f, root):
    root=Path(root);(root/'originals').mkdir(parents=True)
    for key in p.FILES:
        if key.startswith('originals/'):shutil.copyfile(f['originals']/Path(key).name,root/key)
    binding=dict(source=q.pq.SOURCE,runId=444,runAttempt=1)
    p.save(root,f['value'],binding,now=f['clock'].wall())
    return root


def producing_fixture(f, root):
    now=f['clock'].wall();public=public_fixture(f,Path(root)/'public');archive=Path(root)/'prepared.zip'
    with zipfile.ZipFile(archive,'w') as out:
        for key in sorted(p.FILES):out.writestr(key,(public/key).read_bytes())
    run=deepcopy(f['data']['actions/runs/222'])
    run.update(id=444,run_attempt=1,status='completed',conclusion='success')
    run['path']=p.a.RUNNER_WORKFLOW
    jobs=dict(total_count=2,jobs=[dict(name=name,run_id=444,run_attempt=1,head_sha=q.pq.SOURCE,
        status='completed',conclusion='success',started_at=q.pre.at(now-5),completed_at=q.pre.at(now+2),
        steps=[dict(name=label,status='completed',conclusion='success',started_at=q.pre.at(lo),completed_at=q.pre.at(hi))
               for label,lo,hi in ((p.STEP,now-4,now),(p.UPLOAD,now,now+2))])
        for name in ('observations',p.workflow.RUNNER_JOB_NAME)])
    record=dict(id=555,name=p.name(444),expired=False,size_in_bytes=archive.stat().st_size,digest='sha256:'+m.sha(archive.read_bytes()),
        created_at=q.pre.at(now+1),updated_at=q.pre.at(now+1),workflow_run=dict(id=444,head_sha=q.pq.SOURCE,
            head_branch='master',repository_id=p.ci.REPOSITORY_ID,head_repository_id=p.ci.REPOSITORY_ID))
    data={'actions/runs/444':run,'actions/runs/444/attempts/1':deepcopy(run),
        'actions/runs/444/attempts/1/jobs?per_page=100':jobs,
        'actions/runs/444/artifacts?per_page=100':dict(total_count=1,artifacts=[record]),'actions/artifacts/555':record}
    return public,archive,data


class PreparedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frozen=p.admission.workload.load();loader=patch.object(p.admission.workload,'load',side_effect=lambda:deepcopy(frozen))
        loader.start();cls.addClassCleanup(loader.stop)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.f=q.fixture(self.root/'input');self.public,self.archive,self.data=producing_fixture(self.f,self.root/'producer')
        self.now=self.f['clock'].wall()+3;self.sha=self.f['approved']['planSha256']

    def collect(self, name='download',get=None):
        def fetch(identity,path):
            self.assertEqual(555,identity);shutil.copyfile(self.archive,path)
        return p.collect(self.root/name,q.pq.SOURCE,444,self.sha,now=self.now,
            get=get or (lambda key:deepcopy(self.data[key])),fetch=fetch)

    def rezip(self, change):
        with zipfile.ZipFile(self.archive) as z:rows=[(row,z.read(row.filename)) for row in z.infolist()]
        with zipfile.ZipFile(self.archive,'w') as z:
            change(z,rows)
        record=self.data['actions/artifacts/555'];record.update(size_in_bytes=self.archive.stat().st_size,
                                                              digest='sha256:'+m.sha(self.archive.read_bytes()))

    def test_original_public_handoff_and_explicit_digest_approval(self):
        root,value,approved=self.collect()
        self.assertEqual(self.f['value'],value);self.assertEqual(self.f['approved'],approved)
        self.assertFalse(c.read(root/'approval-template.json')['confirmed'])
        self.assertTrue((root.parent/'provenance.json').is_file())
        self.assertEqual(set(p.FILES),{v.relative_to(root).as_posix() for v in root.rglob('*') if v.is_file()})
        self.assertFalse(any(b'PRIVATE KEY' in v.read_bytes() for v in root.rglob('*.json')))

    def test_latest_and_attempt_api_may_differ_in_irrelevant_fields(self):
        self.data['actions/runs/444/attempts/1']['api_only_field']='not an authority claim'
        self.collect()

    def test_wrong_source_failed_run_rerun_and_foreign_repository_rejected(self):
        original=deepcopy(self.data)
        for field,value in (('head_sha','b'*40),('run_attempt',2),('conclusion','failure'),('event','push'),
                            ('path','.github/workflows/ci.yml'),('head_branch','branch')):
            self.data=deepcopy(original);self.data['actions/runs/444'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.collect('bad-'+field)
        self.data=deepcopy(original);self.data['actions/runs/444']['repository']['id']=1
        with self.assertRaises(ValueError):self.collect('foreign')

    def test_missing_or_failed_producing_steps_and_wrong_time_rejected(self):
        original=deepcopy(self.data)
        for i,change in enumerate((lambda j:j['steps'].clear(),lambda j:j['steps'][0].update(conclusion='failure'),
            lambda j:j.update(run_attempt=2),lambda j:j.update(head_sha='b'*40),
            lambda j:j['steps'][1].update(started_at=q.pre.at(self.now-10)))):
            self.data=deepcopy(original);change(self.data['actions/runs/444/attempts/1/jobs?per_page=100']['jobs'][1])
            with self.subTest(i=i),self.assertRaises(ValueError):self.collect('step-'+str(i))

    def test_artifact_source_expiry_digest_time_and_duplicates_rejected(self):
        original=deepcopy(self.data)
        for i,change in enumerate((lambda d:d['actions/artifacts/555'].update(expired=True),
            lambda d:d['actions/artifacts/555'].update(digest='sha256:'+'0'*64),
            lambda d:d['actions/artifacts/555']['workflow_run'].update(id=445),
            lambda d:d['actions/artifacts/555'].update(created_at=q.pre.at(self.now-20)),
            lambda d:d['actions/runs/444/artifacts?per_page=100'].update(total_count=2))):
            self.data=deepcopy(original);change(self.data)
            with self.subTest(i=i),self.assertRaises(ValueError):self.collect('artifact-'+str(i))

    def test_changed_producer_or_metadata_after_download_rejected(self):
        for i,key in enumerate(('actions/artifacts/555','actions/runs/444')):
            counts={}
            def get(path):
                counts[path]=counts.get(path,0)+1;value=deepcopy(self.data[path])
                if path==key and (key.endswith('555') or counts[path]>1):value['unexpected']='changed'
                return value
            with self.assertRaises(ValueError):self.collect('changed-'+str(i),get=get)

    def test_unknown_private_file_duplicate_and_zip_traversal_rejected(self):
        original=self.archive.read_bytes()
        for i,name in enumerate(('private-key','../outside','originals/../plan.json','plan.json')):
            self.archive.write_bytes(original)
            def change(z,rows):
                for row,raw in rows:z.writestr(row,raw)
                z.writestr(name,b'secret sentinel')
            with self.assertWarns(UserWarning) if name=='plan.json' else nullcontext():self.rezip(change)
            with self.assertRaises(ValueError):self.collect('zip-'+str(i))

    def test_symlink_or_special_zip_member_rejected(self):
        def change(z,rows):
            for row,raw in rows:
                if row.filename=='plan.json':row.external_attr=(stat.S_IFLNK|0o777)<<16
                z.writestr(row,raw)
        self.rezip(change)
        with self.assertRaises(ValueError):self.collect()

    def test_changed_plan_or_template_or_receipt_rejected_even_with_fresh_zip_digest(self):
        def change(z,rows):
            for row,raw in rows:
                if row.filename=='approval-template.json':raw=m.canonical(dict(m.strict_json(raw),confirmed=True))
                z.writestr(row,raw)
        self.rezip(change)
        with self.assertRaises(ValueError):self.collect()

    def test_expiry_and_wrong_confirmation_never_renew(self):
        self.now=self.f['value']['expiresAt']
        with self.assertRaises(ValueError):self.collect('expired')
        self.now=self.f['clock'].wall()+3;self.sha='0'*64
        with self.assertRaises(ValueError):self.collect('wrong-digest')

    def test_local_inventory_rejects_extra_files_and_symlinks(self):
        extra=self.public/'ssh-key';extra.write_text('private sentinel')
        with self.assertRaises(ValueError):p.validate(self.public,q.pq.SOURCE,self.sha,now=self.now)
        extra.unlink();(self.public/'plan.json').unlink();(self.public/'plan.json').symlink_to(self.f['root']/'preflight.json')
        with self.assertRaises(ValueError):p.validate(self.public,q.pq.SOURCE,self.sha,now=self.now)


if __name__=='__main__':unittest.main()
