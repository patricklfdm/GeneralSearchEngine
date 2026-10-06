from copy import deepcopy
from pathlib import Path
import shutil
import stat
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile
from . import cloud_runner_artifacts as a, cloud_runner_admission_qualification as q
from . import performance_model as m
from .remote_command import read


class RunnerArtifactsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Unit mutations concern archives, not repeated frozen-plan construction.
        # The separate process qualification uses the unpatched contract loader.
        frozen = q.r.workload.load()
        loader = patch.object(q.r.workload, 'load', side_effect=lambda:deepcopy(frozen))
        loader.start(); cls.addClassCleanup(loader.stop)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.f = q.fixture(Path(self.tmp.name)/'inputs'); self.root = self.f['originals']
        self.records = read(self.root/'artifacts.json')

    def verify(self, **kwargs):
        return a.verify(self.root, self.f['github'], self.f['binding'], controls=self.f['controls'], **kwargs)

    def rewrite(self, kind, entries):
        path = self.root/(kind+'.zip')
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zip:
                for key, value in entries: zip.writestr(key, value)
        self.records[kind].update(size_in_bytes=path.stat().st_size, digest='sha256:'+m.sha(path.read_bytes()))
        (self.root/'artifacts.json').write_bytes(m.canonical(self.records))

    def members(self, kind):
        with zipfile.ZipFile(self.root/(kind+'.zip')) as zip:
            return {name:zip.read(name) for name in zip.namelist()}

    def test_original_bytes_binding_and_relocation(self):
        self.assertEqual(self.f['value']['artifacts'], self.verify())
        copy = Path(self.tmp.name)/'relocated'; shutil.copytree(self.root, copy)
        self.assertEqual(self.verify(), a.verify(copy, self.f['github'], self.f['binding'], controls=self.f['controls']))
        # The default verifier must use real, source-controlled published pins.
        with self.assertRaisesRegex(ValueError, 'published controls'):
            a.verify(copy, self.f['github'], self.f['binding'])

    def test_original_zip_tamper_size_and_link_fail(self):
        path = self.root/'package.zip'; raw = path.read_bytes()
        for data in (raw+b'changed', raw[:-1]+bytes([raw[-1]^1])):
            path.write_bytes(data)
            with self.assertRaises(ValueError): self.verify()
        path.unlink(); path.symlink_to(self.root/'build.zip')
        with self.assertRaises(ValueError): self.verify()

    def test_metadata_rejects_other_attempt_source_job_and_receipt_window(self):
        for kind in ('build','package'):
            for change in (lambda v:v.update(expired=True), lambda v:v.update(digest=''),
                lambda v:v.update(name='v51-guest-package-'+q.pq.SOURCE),
                lambda v:v['workflow_run'].update(head_sha='b'*40),
                lambda v:v['workflow_run'].update(repository_id=1),
                lambda v:v.update(created_at=q.pre.at(q.pq.NOW-70)),
                lambda v:v.update(updated_at=q.pre.at(q.pq.NOW))):
                value = deepcopy(self.records[kind]); change(value)
                with self.subTest(kind=kind, value=value), self.assertRaises(ValueError):
                    a.metadata(kind, value, self.f['github'])
            for change in (lambda j:j.update(run_attempt=1), lambda j:j.update(conclusion='failure'),
                           lambda j:j['steps'].clear()):
                github = deepcopy(self.f['github']); change(next(j for j in github['jobs'] if j['name'] == a.JOBS[kind]))
                with self.assertRaises(ValueError): a.metadata(kind, self.records[kind], github)

    def test_unsafe_zip_duplicate_link_and_failure_marker_rejected_even_if_digest_matches(self):
        original = self.members('package'); link = zipfile.ZipInfo('link')
        link.create_system = 3; link.external_attr = (stat.S_IFLNK|0o777) << 16
        for key in ('../escape','/absolute','x/../../escape','x\\escape','x//','./receipt.json',link,'failure.json','receipt.json'):
            self.rewrite('package', [*original.items(), (key,b'x')])
            with self.subTest(key=key), self.assertRaises(ValueError): self.verify()
        self.assertFalse((self.root.parent/'escape').exists())

    def test_required_files_and_expansion_limit(self):
        original = self.members('build')
        self.rewrite('build', [('other', b'{}')])
        with self.assertRaisesRegex(ValueError, 'required file'): self.verify()
        self.rewrite('build', [*original.items(), ('too-large', b'x'*16385)])
        with patch.object(a,'MAX_BYTES',16384), self.assertRaisesRegex(ValueError, 'inventory/failure'): self.verify()

    def test_package_receipt_cannot_be_relabelled_as_another_build_or_paid_execution(self):
        original = self.members('package')
        for key, value in [('buildManifestSha256','f'*64),('dirty',True),('source','b'*40),
            ('archiveBytes',1),('checks',[]),('payloadBytes',1),('paidCloud',True),('engineWorkloadExecuted',True)]:
            files = dict(original); receipt = m.strict_json(files['receipt.json']); receipt[key] = value
            files['receipt.json'] = m.canonical(receipt); self.rewrite('package', files.items())
            with self.subTest(key=key), self.assertRaises(ValueError): self.verify()

    def test_manifest_candidate_and_workload_drift_survive_outer_rehash_checks(self):
        package = self.f['root']/'guest'; original = {p:p.read_bytes() for p in package.rglob('*') if p.is_file()}
        manifest = read(package/'manifest.json')
        for label in ('candidate','workload','manifest'):
            for path, content in original.items(): path.write_bytes(content)
            value = deepcopy(manifest)
            if label == 'candidate': (package/value['modes'][a.package.MODES[2]]['jars'][0]).write_bytes(b'other candidate')
            if label == 'workload':
                (package/'workload.json').write_bytes(b'{}'); value['workloadSha256'] = m.sha(b'{}')
            value['files'] = a.package.inventory(package)
            (package/'manifest.json').write_bytes(m.canonical(value))
            with tarfile.open(self.root/'changed.tar.gz','w:gz') as tar:
                for path in sorted(original): tar.add(path, arcname=path.relative_to(package).as_posix(), recursive=False)
            files = self.members('package'); archive = (self.root/'changed.tar.gz').read_bytes()
            files['guest.tar.gz'] = archive
            files['package/manifest.json'] = b'{}' if label == 'manifest' else m.canonical(value)
            receipt = m.strict_json(files['receipt.json']); receipt.update(archiveSha256=m.sha(archive),archiveBytes=len(archive),
                payloadFiles=len(value['files']), payloadBytes=sum(v['size'] for v in value['files']))
            files['receipt.json'] = m.canonical(receipt); self.rewrite('package', files.items())
            with self.subTest(label=label), self.assertRaises((ValueError,KeyError)): self.verify()

    def test_separately_trusted_checkout_and_java_binding(self):
        for key, value in [('source','b'*40),('checkoutSha256','d'*64),('java',{})]:
            binding = dict(self.f['binding'], **{key:value})
            with self.assertRaises(ValueError): a.verify(self.root, self.f['github'], binding, controls=self.f['controls'])

    def test_build_archive_and_unproven_old_attempt_are_not_verification_inputs(self):
        files = self.members('build'); files['build.tar.gz'] += b'changed'
        self.rewrite('build', files.items())
        with self.assertRaisesRegex(ValueError,'original build'): self.verify()
        record = deepcopy(self.records['build']); record['name'] = record['name'].replace('attempt-2','attempt-1')
        with self.assertRaisesRegex(ValueError,'producing attempt'):
            a.check_build_job(read(self.root/'build-job.json'),record,self.f['github'])

    def test_partial_ci_rerun_can_reuse_only_the_identical_original_build_job(self):
        self.records['build']['name'] = self.records['build']['name'].replace('attempt-2','attempt-1')
        origin = read(self.root/'build-job.json'); origin['run_attempt'] = 1
        (self.root/'artifacts.json').write_bytes(m.canonical(self.records))
        (self.root/'build-job.json').write_bytes(m.canonical(origin))
        self.f['data']['actions/runs/12/attempts/1/jobs?per_page=100&page=1'] = dict(total_count=1,jobs=[deepcopy(origin)])
        self.assertEqual(origin,a.collect_build_job(self.records['build'],self.f['github'],lambda p:deepcopy(self.f['data'][p])))
        self.assertEqual(dict(attempt=1,jobId=origin['id'],acceptedJobId=origin['id']),self.verify()['buildProducer'])
        for key, value in [('id',99999),('started_at',q.pre.at(q.pq.NOW-1000)),('head_sha','f'*40),('steps',[])]:
            changed = dict(origin,**{key:value}); (self.root/'build-job.json').write_bytes(m.canonical(changed))
            with self.subTest(key=key), self.assertRaisesRegex(ValueError,'producing job changed'): self.verify()

    def test_github_carried_check_run_copy_preserves_original_execution(self):
        current = next(j for j in self.f['github']['jobs'] if j['name'] == a.JOBS['build'])
        current.update(created_at=q.pre.at(q.pq.NOW-20),runner_id=765,runner_name='hosted-fixture')
        origin = dict(deepcopy(current),id=9876,run_attempt=1,created_at=q.pre.at(q.pq.NOW-301))
        record = dict(self.records['build'],name=self.records['build']['name'].replace('attempt-2','attempt-1'))
        self.assertEqual(origin,a.check_build_job(origin,record,self.f['github']))
        for key,value in [('created_at',q.pre.at(q.pq.NOW-100)),('runner_id',999),('runner_name','other'),
                          ('started_at',q.pre.at(q.pq.NOW-250))]:
            old = current[key]; current[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError,'producing job changed'):
                a.check_build_job(origin,record,self.f['github'])
            current[key] = old

    def test_collect_keeps_original_zip_and_rechecks_metadata(self):
        def get(path): return deepcopy(self.f['data'][path])
        def fetch(identity, path): shutil.copyfile(self.root/('build.zip' if identity == 101 else 'package.zip'), path)
        target = Path(self.tmp.name)/'download'
        self.assertEqual(self.records, a.collect(target, self.f['github'], get=get, fetch=fetch))
        self.assertEqual(self.verify(), a.verify(target, self.f['github'], self.f['binding'], controls=self.f['controls']))
        self.f['data']['actions/artifacts/102']['expired'] = True
        with self.assertRaisesRegex(ValueError, 'changed during download'):
            a.collect(Path(self.tmp.name)/'changed', self.f['github'], get=get, fetch=fetch)

    def test_collect_duplicate_missing_truncated_inventory_rejected(self):
        key = 'actions/runs/12/artifacts?per_page=100&page=1'; original = deepcopy(self.f['data'][key])
        for data in [dict(total_count=2,artifacts=[original['artifacts'][0]]*2),dict(total_count=2,artifacts=[]),
                     dict(total_count=2,artifacts=[dict(v,name='unrelated-'+str(v['id'])) for v in original['artifacts']])]:
            self.f['data'][key] = data
            with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
                a.collect(Path(tmp)/'out',self.f['github'],get=lambda p:deepcopy(self.f['data'][p]),fetch=lambda *args:None)


if __name__ == '__main__': unittest.main()
