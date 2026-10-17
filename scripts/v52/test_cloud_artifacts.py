"""Fixture API data and subprocess tests, with no GitHub/GCP calls or Java runs."""
from copy import deepcopy
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile
from . import cloud_artifacts as p, cloud_ci as ci
from .test_cloud_ci import Fixture, NOW, SOURCE, at
from .test_cloud_inputs import binding, shared
from .evidence import encoded, digest, strict


class ArtifactFixture(Fixture):
    def __init__(self, shape, root, *, carried=True):
        super().__init__(shape); self.downloads = []; self.root = root; directory = root/'shared'; directory.mkdir()
        shared(directory); self.zip_files = {name:(directory/name).read_bytes() for name in ('manifest.json', 'build.tar.gz')}
        self.current = next(job for job in self.jobs if job['name'] == ci.BUILD)
        self.origin = deepcopy(self.current); self.original_run = deepcopy(self.run)
        if carried:
            self.origin['run_attempt'] = 1; self.original_run.update(run_attempt=1, conclusion='failure')
            self.current['id'] += 100000; self.current['created_at'] = at(ci.stamp(self.current['completed_at'])+30)
        self.install()
        upload = next(step for step in self.current['steps'] if step['name'] == ci.UPLOAD_STEP)
        self.record = dict(id=501, name=p.BUILD_PREFIX+SOURCE+'-attempt-'+str(self.origin['run_attempt']),
            expired=False, created_at=upload['started_at'], updated_at=upload['completed_at'], expires_at=at(NOW+86400),
            workflow_run=dict(id=10, repository_id=ci.credentials.REPOSITORY_ID, head_repository_id=ci.credentials.REPOSITORY_ID,
                              head_sha=SOURCE, head_branch='master'))
        self.rezip(list(self.zip_files.items()))
        attempt = self.origin['run_attempt']
        if carried:
            self.data[f'actions/runs/10/attempts/{attempt}'] = deepcopy(self.original_run)
            self.page(f'actions/runs/10/attempts/{attempt}/jobs','jobs',[self.origin])

    def rezip(self, entries):
        buffer = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
                for name, raw in entries: archive.writestr(name, raw)
        self.raw = buffer.getvalue(); self.record.update(size_in_bytes=len(self.raw), digest='sha256:'+digest(self.raw))
        self.data['actions/artifacts/501'] = deepcopy(self.record); self.page('actions/runs/10/artifacts','artifacts',[self.record])

    def download(self, identity, output, size):
        self.downloads.append(identity); assert identity == 501 and size == len(self.raw)
        with Path(output).open('xb') as stream: stream.write(self.raw)


class ArtifactTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.shape = ci.contract()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup); self.root = Path(self.temporary.name)
        self.f = ArtifactFixture(self.shape, self.root); self.out = self.root/'observed'

    def collect(self):
        self.out.mkdir(); return p._collect(self.out, SOURCE, self.shape, binding(), self.f, lambda:NOW)

    def replay(self): return p.replay(self.out, SOURCE, self.shape, binding(), now=NOW)

    def observation(self): return ci.observe(SOURCE, self.shape, self.f.get, lambda:NOW)

    def test_carried_success_from_a_failed_prior_attempt_is_original_not_a_rebuilt_job(self):
        result = self.collect()
        self.assertEqual('BUILD_PROVENANCE_VERIFIED_NOT_ADMITTED', result['status']); self.assertFalse(result['paidAdmission'])
        self.assertEqual(1, result['producer']['attempt']); self.assertEqual(2, result['ci']['attempt'])
        self.assertNotEqual(result['producer']['jobId'], result['producer']['acceptedJobId'])
        self.assertEqual([501], self.f.downloads); self.assertEqual(result, self.replay())
        self.assertEqual(self.f.raw, (self.out/'build.zip').read_bytes())

    def test_current_attempt_build_and_same_id_carry_are_supported(self):
        self.f.current['id'] = self.f.origin['id']; self.f.install()
        self.f.page('actions/runs/10/attempts/1/jobs','jobs',[self.f.origin]); self.collect()
        self.out = self.root/'current'; new_root = self.root/'new'; new_root.mkdir()
        self.f = ArtifactFixture(self.shape, new_root, carried=False)
        result = self.collect(); self.assertEqual(2, result['producer']['attempt'])

    def test_original_artifact_and_producing_job_can_be_on_later_pages(self):
        rows = [dict(id=10000+i, name='unrelated-'+str(i)) for i in range(204)]+[self.f.record]
        self.f.page('actions/runs/10/artifacts', 'artifacts', rows)
        jobs = [dict(id=20000+i, name='other-job-'+str(i)) for i in range(100)]+[self.f.origin]
        self.f.page('actions/runs/10/attempts/1/jobs', 'jobs', jobs)
        self.collect()
        self.assertEqual([501], self.f.downloads)
        self.assertEqual(2, self.f.calls.count('actions/runs/10/artifacts?per_page=100&page=3'))
        self.assertIn('actions/runs/10/attempts/1/jobs?per_page=100&page=2', self.f.calls)

    def test_replaced_current_execution_cannot_select_an_older_green_artifact(self):
        self.f.current['started_at'] = at(NOW-50); self.f.current['completed_at'] = at(NOW-1)
        # Keep step times consistent with the new run; the old artifact is outside it.
        for index, step in enumerate(self.f.current['steps']):
            step.update(started_at=at(NOW-50+index*2), completed_at=at(NOW-49+index*2))
        self.f.install()
        with self.assertRaisesRegex(ValueError, 'artifact missing/ambiguous'): self.collect()
        self.assertEqual([], self.f.downloads)

    def test_carried_copy_requires_same_runner_original_steps_and_execution_times(self):
        observation = self.observation(); record = self.f.record
        for key, val in (('id',True), ('runner_id',99), ('runner_name','other'), ('created_at',at(NOW)),
                         ('started_at',at(NOW-5000)), ('steps',[])):
            original = dict(deepcopy(self.f.origin), **{key:val})
            with self.assertRaises(ValueError): p.producer(self.f.original_run, original, record, observation, self.shape, NOW)
        wrong = deepcopy(observation); p.current_job(wrong)['created_at'] = at(NOW-10000)
        with self.assertRaisesRegex(ValueError, 'carried'): p.producer(self.f.original_run, self.f.origin, record, wrong, self.shape, NOW)

    def test_same_id_carry_cannot_ignore_changed_steps(self):
        observation = self.observation(); p.current_job(observation)['id'] = self.f.origin['id']
        old = deepcopy(self.f.origin); old['steps'][0]['name'] = 'substitute'
        with self.assertRaises(ValueError): p.producer(self.f.original_run, old, self.f.record, observation, self.shape, NOW)

    def test_original_attempt_run_is_bound_even_if_its_overall_conclusion_failed(self):
        observation = self.observation()
        for key, val in (('id',11), ('run_attempt',2), ('head_sha','f'*40), ('workflow_id',999),
                         ('event','pull_request'), ('status','in_progress')):
            wrong = dict(self.f.original_run, **{key:val})
            with self.assertRaises(ValueError): p.producer(wrong, self.f.origin, self.f.record, observation, self.shape, NOW)

    def test_artifact_identity_expiry_digest_future_attempt_and_upload_window_reject(self):
        observation = self.observation()
        for key, val in (('expired',True), ('expired',0), ('expires_at',at(NOW)), ('digest',''), ('size_in_bytes',True),
                         ('name',p.BUILD_PREFIX+SOURCE+'-attempt-3'), ('created_at',at(NOW-7000)),
                         ('updated_at',at(NOW)), ('id',True)):
            wrong = dict(self.f.record, **{key:val})
            with self.assertRaises(ValueError): p.metadata(wrong, observation, NOW)
        for key, val in (('head_sha','f'*40), ('id',11), ('repository_id',1), ('head_repository_id',True), ('head_branch','branch')):
            wrong = deepcopy(self.f.record); wrong['workflow_run'][key] = val
            with self.assertRaises(ValueError): p.metadata(wrong, observation, NOW)

    def test_fractional_artifact_time_is_correlated_at_job_timestamp_precision(self):
        observation = self.observation(); record = deepcopy(self.f.record)
        end = ci.stamp(record['updated_at']); record['updated_at'] = at(end+.7)
        p.metadata(record, observation, NOW)
        record['updated_at'] = at(end+1)
        with self.assertRaisesRegex(ValueError, 'outside original upload'): p.metadata(record, observation, NOW)

    def test_missing_and_ambiguous_artifacts_fail_before_download(self):
        for rows in ([], [self.f.record, dict(self.f.record, id=502)]):
            self.f.page('actions/runs/10/artifacts','artifacts',rows); self.out = self.root/('out-'+str(len(rows)))
            with self.assertRaisesRegex(ValueError, 'missing/ambiguous'): self.collect()
        self.assertEqual([], self.f.downloads)

    def test_artifact_metadata_change_after_download_rejects_and_preserves_original_zip(self):
        changed = dict(self.f.record, expired=True)
        self.f.queues['actions/artifacts/501'] = [self.f.record, changed]
        with self.assertRaisesRegex(ValueError, 'metadata changed'): self.collect()
        self.assertEqual(self.f.raw, (self.out/'build.zip').read_bytes())

    def test_new_full_run_or_failed_rerun_after_download_invalidates_whole_collection(self):
        path = 'actions/runs/10'; changed = dict(self.f.run, run_attempt=3, conclusion='failure')
        self.f.queues[path] = [self.f.run, self.f.run, changed]
        with self.assertRaisesRegex(ValueError, 'not completed green'): self.collect()
        self.assertEqual([501], self.f.downloads)

    def test_zip_hash_size_symlink_and_original_extracted_bytes_are_independent(self):
        self.collect(); path = self.out/'build.zip'; original = path.read_bytes()
        path.write_bytes(original+b'changed')
        with self.assertRaisesRegex(ValueError, 'ZIP bytes'): self.replay()
        path.write_bytes(original); (self.out/'build/manifest.json').write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'extracted build'): self.replay()
        path.unlink(); path.symlink_to(self.root/'shared/build.tar.gz')
        with self.assertRaisesRegex(ValueError, 'file type'): self.replay()

    def test_rehashed_unsafe_zip_inventory_cannot_become_inputs(self):
        observation = self.observation(); items = list(self.f.zip_files.items())
        link = zipfile.ZipInfo('manifest.json'); link.create_system = 3; link.external_attr = (stat.S_IFLNK|0o777)<<16
        for entries in (items+[('../escape',b'x')], [items[0],items[0]], [items[0]],
                        [('other',b'x'),items[1]], [(link,b'link'),items[1]]):
            self.f.rezip(entries); path = self.root/'bad.zip'; path.write_bytes(self.f.raw)
            with self.assertRaises(ValueError): p.zip_contents(path, self.f.record, observation, NOW)
        self.assertFalse((self.root.parent/'escape').exists())

    def test_original_zip_cannot_substitute_build_source_even_if_outer_digest_is_updated(self):
        files = dict(self.f.zip_files); manifest = strict(files['manifest.json']); manifest['binding']['source'] = 'f'*40
        files['manifest.json'] = encoded(manifest); self.f.rezip(list(files.items()))
        with self.assertRaisesRegex(ValueError, 'original build binding/layout'): self.collect()

    def test_edited_producer_job_and_failed_collection_marker_reject_replay(self):
        self.collect(); path = self.out/'producer-job.json'; job = strict(path.read_bytes()); job['runner_id'] = 999
        path.write_bytes(encoded(job))
        with self.assertRaisesRegex(ValueError, 'job observation changed'): self.replay()
        (self.out/'failure.json').write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'collection failed'): self.replay()

    def test_request_path_allowlist_is_repository_scoped_get_only(self):
        for path in ('branches/master', 'actions/runs/10', 'actions/runs/10/attempts/2', 'actions/artifacts/501',
                     'actions/runs/10/artifacts?per_page=100&page=2', 'contents/'+ci.WORKFLOW+'?ref='+SOURCE): p.allowed_path(path)
        for path in ('../outside', 'actions/runs/10/rerun', 'actions/artifacts/501/zip', 'actions/runs/10/cancel',
                     'https://evil.invalid', 'branches/other', 'contents/secret?ref='+SOURCE,
                     'actions/runs/10/artifacts?per_page=100&page=1&x=y'):
            with self.assertRaises(ValueError): p.allowed_path(path)
        command = p.Network.command('branches/master')
        self.assertEqual('GET', command[command.index('--method')+1]); self.assertEqual('github.com', command[command.index('--hostname')+1])
        self.assertEqual('repos/'+ci.credentials.REPOSITORY+'/branches/master', command[-1])

    def test_read_path_requires_literal_workflow_filename(self):
        for name in ('ci-yml', 'ci/yml', 'ciXyml'):
            with self.assertRaisesRegex(ValueError, 'outside scope'):
                p.allowed_path('actions/workflows/'+name+'/runs?branch=master&head_sha='+SOURCE+'&per_page=100&page=1')

    def test_native_factory_rechecks_source_and_uses_fixed_client_without_injection(self):
        with patch.object(p.inputs, 'checkout', return_value=binding()) as source, patch.object(p, 'Network', return_value=self.f) as client, \
             patch.object(p.time, 'time', return_value=NOW):
            result = p.collect_native(SOURCE, self.out)
        self.assertEqual('native-v52-github-read-only', result['execution']); self.assertFalse(result['paidAdmission'])
        self.assertEqual(2, source.call_count); client.assert_called_once_with(self.out/'requests')
        with self.assertRaises(TypeError): p.collect_native(SOURCE, self.root/'injected', get=self.f.get)

    def test_native_factory_final_source_change_retains_failure_without_success_receipt(self):
        with patch.object(p.inputs, 'checkout', side_effect=[binding(), dict(binding(), checkoutSha256='f'*64)]), \
             patch.object(p, 'Network', return_value=self.f), patch.object(p.time, 'time', return_value=NOW):
            with self.assertRaisesRegex(ValueError, 'source changed'): p.collect_native(SOURCE, self.out)
        self.assertTrue((self.out/'failure.json').is_file()); self.assertFalse((self.out/'receipt.json').exists())
        self.assertEqual('V52_PROVENANCE_FINAL_SOURCE_REJECTED', strict((self.out/'failure.json').read_bytes())['code'])
        with self.assertRaisesRegex(ValueError, 'collection failed'): self.replay()

    def test_initial_source_failure_is_retained_without_constructing_network_client(self):
        with patch.object(p.inputs, 'checkout', side_effect=ValueError('private diagnostic secret')), patch.object(p, 'Network') as client:
            with self.assertRaises(ValueError): p.collect_native(SOURCE, self.out)
        client.assert_not_called(); failure = (self.out/'failure.json').read_text()
        self.assertNotIn('private diagnostic secret', failure)
        self.assertEqual('V52_PROVENANCE_SOURCE_REJECTED', strict(failure)['code'])

    def test_fixed_network_retains_bounded_raw_json_and_never_uses_api_supplied_download_url(self):
        client = p.Network(self.root/'reads'); commands = []
        def command(args, path, maximum, timeout):
            commands.append((args, maximum, timeout))
            Path(path).write_bytes(b'archive' if args[-1].endswith('/zip') else b'{"test":1}')
        with patch.object(p, 'bounded_command', side_effect=command):
            self.assertEqual({'test':1}, client.get('actions/runs/10'))
            client.download(501, self.root/'original.zip', 7)
        self.assertEqual('GET', strict((self.root/'reads/001-request.json').read_bytes())['method'])
        self.assertEqual(p.MAX_JSON, commands[0][1]); self.assertEqual(30, commands[0][2])
        self.assertEqual('repos/'+ci.credentials.REPOSITORY+'/actions/artifacts/501/zip', commands[1][0][-1])
        self.assertEqual((7, 300), commands[1][1:])


class BoundedReadTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup); self.path = Path(self.temporary.name)/'out'

    def test_streamed_success_owns_one_process_and_refuses_overwrite(self):
        command = [sys.executable, '-c', 'print("ok",end="")']
        p.bounded_command(command, self.path, 2, 2); self.assertEqual(b'ok', self.path.read_bytes())
        with self.assertRaises(FileExistsError): p.bounded_command(command, self.path, 2, 2)

    def test_byte_limit_and_nonzero_exit_preserve_partial_bytes_and_fail(self):
        with self.assertRaisesRegex(ValueError, 'byte bound'):
            p.bounded_command([sys.executable, '-c', 'print("x"*100000)'], self.path, 8, 2)
        self.assertLessEqual(self.path.stat().st_size, 8); self.path.unlink()
        with self.assertRaisesRegex(ValueError, 'read failed'):
            p.bounded_command([sys.executable, '-c', 'import sys;print("partial");sys.exit(2)'], self.path, 100, 2)
        self.assertEqual(b'partial\n', self.path.read_bytes())

    def test_read_deadline_kills_owned_process(self):
        with self.assertRaisesRegex(ValueError, 'read deadline'):
            p.bounded_command([sys.executable, '-c', 'import time;time.sleep(10)'], self.path, 10, .05)


if __name__ == '__main__': unittest.main()
