"""Fixture API data and subprocess tests, with no GitHub/GCP calls or Java runs."""
from copy import deepcopy
from contextlib import redirect_stdout
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

    def use_standalone(self):
        for run in (self.run,self.original_run):
            run.update(path=ci.standalone.WORKFLOW,event='workflow_dispatch',workflow_id=456)
        for job in (self.current,self.origin):job['name']=ci.standalone.JOB
        self.jobs=[self.current];self.install()
        if self.origin['run_attempt'] != self.run['run_attempt']:
            self.data['actions/runs/10/attempts/1']=deepcopy(self.original_run)
            self.page('actions/runs/10/attempts/1/jobs','jobs',[self.origin])

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

    def test_standalone_original_and_carried_attempt_artifacts_replay(self):
        for carried in (True,False):
            root=self.root/str(carried);root.mkdir();self.f=ArtifactFixture(self.shape,root,carried=carried)
            self.out=root/'out';self.f.use_standalone();proof=self.collect()
            self.assertEqual(ci.standalone.WORKFLOW,proof['ci']['workflow'])
            self.assertEqual(1 if carried else 2,proof['producer']['attempt'])
            self.assertEqual(proof,self.replay());self.assertEqual([501],self.f.downloads)
            for path in self.f.calls:p.allowed_path(path)

    def test_standalone_producer_cannot_borrow_original_attempt_from_ci(self):
        self.f.use_standalone()
        self.f.data['actions/runs/10/attempts/1']['path']=ci.WORKFLOW
        with self.assertRaises(ValueError):self.collect()
        self.assertEqual([],self.f.downloads)

    def test_standalone_artifact_digest_failure_is_not_retried_or_substituted(self):
        self.f.use_standalone();self.f.raw=self.f.raw[:-1]+bytes([self.f.raw[-1]^1])
        with self.assertRaisesRegex(ValueError,'ZIP bytes'):self.collect()
        self.assertEqual([501],self.f.downloads)

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
                         ('event','pull_request'), ('status','invalid')):
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
        with self.assertRaisesRegex(ValueError, 'selection changed|run/attempt changed'): self.collect()
        self.assertEqual([501], self.f.downloads)

    def test_current_build_artifact_is_accepted_while_full_ci_is_running(self):
        root=self.root/'unfinished';root.mkdir();self.f=ArtifactFixture(self.shape,root,carried=False)
        self.f.run.update(status='in_progress',conclusion=None);self.f.install()
        result=self.collect()
        self.assertFalse(result['ci']['fullCiRequired']);self.assertEqual(1,result['ci']['jobs'])
        self.assertEqual('BUILD_CI_VERIFIED_NOT_ADMITTED',result['ci']['status'])
        self.assertEqual(result,self.replay());self.assertEqual([501],self.f.downloads)

    def test_full_ci_failure_does_not_block_original_successful_build(self):
        self.f.run.update(conclusion='failure');self.f.install()
        for job in self.f.jobs:
            if job['name']!=ci.BUILD:job['conclusion']='failure'
        self.f.install();self.assertEqual('BUILD_PROVENANCE_VERIFIED_NOT_ADMITTED',self.collect()['status'])

    def test_full_ci_finishing_during_artifact_download_is_not_identity_drift(self):
        self.f.run.update(status='in_progress',conclusion=None);self.f.install()
        original=self.f.download
        def download(*args):
            original(*args);self.f.run.update(status='completed',conclusion='failure');self.f.install()
        self.f.download=download
        self.assertEqual(1,self.collect()['ci']['jobs'])

    def test_restoring_full_ci_policy_rejects_unfinished_or_failed_full_run(self):
        for status,conclusion in (('in_progress',None),('completed','failure')):
            self.f.run.update(status=status,conclusion=conclusion);self.f.install()
            self.out=self.root/status
            with patch.object(ci,'REQUIRE_FULL_CI',True),self.assertRaisesRegex(ValueError,'not completed green'):self.collect()
        self.assertEqual([],self.f.downloads)

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
        self.assertEqual(p.MAX_JSON, commands[0][1]); self.assertTrue(0 < commands[0][2] <= 30)
        self.assertEqual('repos/'+ci.credentials.REPOSITORY+'/actions/artifacts/501/zip', commands[1][0][-1])
        self.assertEqual(7, commands[1][1]); self.assertTrue(0 < commands[1][2] <= 300)

    def test_native_http_failure_retains_subphase_and_closed_request_details(self):
        error = p.GitHubReadError('HTTP_REJECTED', 503)
        error.request = dict(kind='jobs', attempts=3, ordinal=7, stop='attempt-limit')
        with patch.object(p.inputs, 'checkout', return_value=binding()), \
             patch.object(p.Network, 'get', side_effect=error):
            with self.assertRaises(p.GitHubReadError): p.collect_native(SOURCE, self.out)
        result = p.public_failure(p.read(self.out/'failure.json'))
        self.assertEqual('full-ci', result['phase']); self.assertEqual(503, result['httpStatus'])
        self.assertEqual(error.request, result['request'])
        self.assertEqual(ci.__name__, result['checkSite']['module'])
        self.assertFalse((self.out/'receipt.json').exists())

    def test_diagnostic_write_failure_does_not_replace_original_collection_error(self):
        with patch.object(p.inputs, 'checkout', side_effect=ValueError('original-failure')), \
             patch.object(p, 'save', side_effect=OSError('private-disk-error')), redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(ValueError, 'original-failure'): p.collect_native(SOURCE, self.out)
        self.assertEqual('v52GitHubDiagnosticRetention=FAIL\n',output.getvalue())


class NetworkRetryTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name); self.client = p.Network(self.root/'reads')
        self.clock = 100.; self.waits = []; self.calls = []; self.output = io.StringIO()
        self.actions = []
        for name, value in (('monotonic', lambda:self.clock), ('sleep', self.sleep)):
            patched = patch.object(p.time, name, side_effect=value); patched.start(); self.addCleanup(patched.stop)
        patched = patch.object(p, 'bounded_command', side_effect=self.command)
        patched.start(); self.addCleanup(patched.stop)
        redirected = redirect_stdout(self.output); redirected.__enter__(); self.addCleanup(redirected.__exit__, None, None, None)

    def sleep(self, delay): self.waits.append(delay); self.clock += delay

    def command(self, args, path, maximum, timeout):
        self.calls.append((args, maximum, timeout))
        delay, raw, error = self.actions.pop(0); self.clock += delay
        Path(path).write_bytes(raw)
        if error is not None: raise error

    def fail(self, status=503, delay=0):
        return (delay, b'partial-private-response', p.GitHubReadError('HTTP_REJECTED', status))

    def test_transient_get_retry_retains_every_attempt_and_one_original_deadline(self):
        self.actions = [self.fail(delay=5), self.fail(502, delay=3), (0, b'{"ok":true}', None)]
        self.assertEqual({'ok':True}, self.client.get('actions/runs/10'))
        self.assertEqual([1,2], self.waits); self.assertEqual([30,24,19], [v[2] for v in self.calls])
        self.assertEqual(3, self.client.calls)
        self.assertEqual(b'partial-private-response', (self.client.output/'001.json').read_bytes())
        for index in (1,2,3):
            receipt = p.read(self.client.output/f'{index:03}-request.json')
            self.assertEqual(index, receipt['attempt']); self.assertEqual('GET', receipt['method'])
            self.assertEqual('actions/runs/10', receipt['path'])
        self.assertNotIn('private-response', self.output.getvalue())
        self.assertNotIn('actions/runs/10', self.output.getvalue())
        self.assertTrue(all(args[args.index('--method')+1]=='GET' for args,_,_ in self.calls))

    def test_transport_failure_can_retry_but_never_more_than_three_attempts(self):
        self.actions = [(0,b'',p.GitHubReadError('TRANSPORT')) for _ in range(3)]
        with self.assertRaises(p.GitHubReadError) as caught: self.client.get('branches/master')
        self.assertEqual('attempt-limit', caught.exception.request['stop'])
        self.assertEqual(3, caught.exception.request['attempts']); self.assertEqual([1,2], self.waits)
        self.assertEqual(3,len(self.calls))

    def test_terminal_http_errors_and_unknown_failures_do_not_retry(self):
        for code in (401,403,404,409,422,501,505):
            self.actions = [self.fail(code)]
            with self.subTest(code=code), self.assertRaises(p.GitHubReadError) as caught:
                self.client.get('actions/artifacts/501')
            self.assertEqual(code,caught.exception.http_status); self.assertEqual('terminal',caught.exception.request['stop'])
        for reason in ('PROCESS_FAILED','START_FAILED','BYTE_BOUND','STDERR_BOUND'):
            self.actions = [(0,b'',p.GitHubReadError(reason))]
            with self.assertRaises(p.GitHubReadError): self.client.get('branches/master')
        self.assertEqual([],self.waits); self.assertEqual(11,len(self.calls))

    def test_read_timeout_and_rate_limit_recover_inside_original_deadline(self):
        self.actions=[self.fail(408),self.fail(429),(0,b'{"ok":true}',None)]
        self.assertEqual({'ok':True},self.client.get('branches/master'))
        self.assertEqual(3,len(self.calls));self.assertEqual([1,2],self.waits)

    def test_exhausted_original_deadline_does_not_sleep_or_launch_again(self):
        self.actions = [self.fail(delay=29.5)]
        with self.assertRaises(p.GitHubReadError) as caught: self.client.get('branches/master')
        self.assertEqual('deadline',caught.exception.request['stop']); self.assertEqual([],self.waits)
        self.assertEqual(1,len(self.calls))

    def test_owned_timeout_is_terminal_even_if_it_returns_early(self):
        self.actions = [(1,b'',p.GitHubReadError('DEADLINE'))]
        with self.assertRaises(p.GitHubReadError) as caught: self.client.get('branches/master')
        self.assertEqual('deadline',caught.exception.request['stop']); self.assertEqual([],self.waits)

    def test_success_returned_after_the_shared_deadline_is_rejected(self):
        self.actions=[(31,b'{"ok":true}',None)]
        with self.assertRaises(p.GitHubReadError) as caught:self.client.get('branches/master')
        self.assertEqual('V52_GITHUB_DEADLINE',caught.exception.code);self.assertEqual([],self.waits)

    def test_each_retry_counts_toward_the_global_call_bound(self):
        self.client.calls = 255; self.actions = [self.fail()]
        with self.assertRaises(p.GitHubReadError) as caught: self.client.get('branches/master')
        self.assertEqual('call-limit',caught.exception.request['stop']); self.assertEqual(256,self.client.calls)
        with self.assertRaises(p.GitHubReadError): self.client.get('branches/master')
        self.assertEqual(1,len(self.calls)); self.assertEqual([],self.waits)

    def test_invalid_json_is_not_retried_even_after_a_transient_error(self):
        self.actions = [self.fail(), (0,b'{"broken":',None)]
        with self.assertRaises(p.GitHubReadError) as caught: self.client.get('branches/master')
        self.assertEqual('V52_GITHUB_JSON_INVALID',caught.exception.code)
        self.assertEqual(2,len(self.calls)); self.assertEqual([1],self.waits)

    def test_download_retries_never_append_partial_bytes_or_replace_an_existing_file(self):
        self.actions = [(2,b'bad',p.GitHubReadError('TRANSPORT')), (0,b'original',None)]
        target = self.root/'original.zip'; self.client.download(501,target,8)
        self.assertEqual(b'original',target.read_bytes()); self.assertEqual(b'bad',(self.client.output/'001.zip').read_bytes())
        self.assertEqual([300,297],[v[2] for v in self.calls]); self.assertEqual([1],self.waits)
        with self.assertRaises(FileExistsError): self.client.download(501,target,8)
        self.assertEqual(2,len(self.calls)); self.assertEqual(b'original',target.read_bytes())

    def test_short_successful_download_and_invalid_path_fail_without_retry(self):
        self.actions = [(0,b'short',None)]; target = self.root/'original.zip'
        with self.assertRaises(p.GitHubReadError) as caught: self.client.download(501,target,8)
        self.assertEqual('V52_GITHUB_INCOMPLETE',caught.exception.code); self.assertFalse(target.exists())
        with self.assertRaises(ValueError): self.client.get('actions/runs/10/rerun')
        self.assertEqual(1,len(self.calls)); self.assertEqual([],self.waits)


class DiagnosticTest(unittest.TestCase):
    def test_cli_http_and_network_classification_is_closed(self):
        for status in (408,429,500,502,503,504,401,403,404,501):
            for raw in (f'gh: private-server-detail (HTTP {status})\n', f'gh: HTTP {status}\n'):
                error=p.command_error(raw.encode(),1)
                self.assertEqual(status,error.http_status)
                self.assertEqual(status in (408,429,500,502,503,504),error.retryable)
                self.assertNotIn('private',str(error))
        self.assertTrue(p.command_error(b'Get "private-url": connection reset by peer',1).retryable)
        for raw in (b'gh: denied (HTTP 403)\nconnection reset by peer', b'gh: HTTP 403\ngh: HTTP 503',
                    b'gh: private error', b'x509: certificate signed by unknown authority'):
            self.assertFalse(p.command_error(raw,1).retryable)
        self.assertFalse(p.command_error(b'connection reset by peer',4).retryable)

    def test_public_projection_drops_unknown_fields_and_malformed_details(self):
        value=dict(status='FAIL',phase='full-ci',code='V52_PROVENANCE_FULL_CI_REJECTED',
            reasonCode='V52_GITHUB_HTTP_REJECTED',httpStatus=503,
            request=dict(kind='jobs',stop='attempt-limit',attempts=3,ordinal=7,url='private-url'),
            checkSite=dict(module=ci.__name__,line=123,secret='private-token'),stderr='private-stderr')
        projected=p.public_failure(value)
        self.assertEqual(503,projected['httpStatus']); self.assertNotIn('private',str(projected))
        self.assertIsNone(p.public_failure(dict(value,phase='private-phase')))
        invalid=dict(value,reasonCode='private-code',httpStatus=True,
                     request=dict(value['request'],attempts=True),checkSite=dict(module='private-module',line=1))
        self.assertEqual({'phase':value['phase'],'code':value['code']},p.public_failure(invalid))


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

    def test_real_cli_failure_extracts_status_without_retaining_stderr(self):
        script='import sys;print("body");print("gh: private-token (HTTP 503)",file=sys.stderr);sys.exit(1)'
        with self.assertRaises(p.GitHubReadError) as caught:
            p.bounded_command([sys.executable,'-c',script],self.path,100,2)
        self.assertEqual(503,caught.exception.http_status); self.assertTrue(caught.exception.retryable)
        self.assertNotIn('private-token',str(caught.exception)); self.assertEqual(b'body\n',self.path.read_bytes())
        self.assertEqual([self.path],list(self.path.parent.iterdir()))

    def test_stderr_flood_is_bounded_and_owned_process_reaped(self):
        children=[]; original=p.subprocess.Popen
        def launch(*args,**kwargs):
            child=original(*args,**kwargs);children.append(child);return child
        with patch.object(p.subprocess,'Popen',side_effect=launch):
            with self.assertRaises(p.GitHubReadError) as caught:
                p.bounded_command([sys.executable,'-c','import sys,time;sys.stderr.write("x"*100000);time.sleep(10)'],
                                  self.path,100,2)
        self.assertEqual('V52_GITHUB_STDERR_BOUND',caught.exception.code)
        self.assertFalse(caught.exception.retryable);self.assertIsNotNone(children[0].returncode)
        self.assertTrue(children[0].stdout.closed);self.assertTrue(children[0].stderr.closed)

    def test_both_pipes_are_drained_without_deadlock(self):
        script='import sys;sys.stderr.write("private"*1000);sys.stdout.write("ok")'
        p.bounded_command([sys.executable,'-c',script],self.path,2,2)
        self.assertEqual(b'ok',self.path.read_bytes())


if __name__ == '__main__': unittest.main()
