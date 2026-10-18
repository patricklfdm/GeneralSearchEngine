"""Synthetic GitHub API observations; never a deployed or cloud PASS."""
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
from . import cloud_runner_provenance as p
from .test_cloud_member_seal import fixture
from .test_cloud_ci import Fixture, run, at

WORKFLOW = '''name: V5.2 fixture
on:
  workflow_dispatch:
jobs:
  runner:
    name: V5.2 replication runner
    if: ${{ github.ref == 'refs/heads/master' }}
    environment: v52-cloud-benchmark
    runs-on: ubuntu-24.04
    steps:
'''+''.join('      - name: '+v+'\n        run: fixture-only\n' for v in p.REQUIRED)


class RunnerFixture(Fixture):
    def __init__(self, seal):
        self.seal = deepcopy(seal); self.run = run(123456, 2)
        self.run.update(path=p.PATH, event='workflow_dispatch')
        self.jobs = [dict(id=801, run_id=123456, run_attempt=2, head_sha='a'*40, name=p.JOB, status='completed', conclusion='success',
            started_at=at(990), completed_at=at(1130), steps=[dict(name=name, number=i+1, status='completed', conclusion='success',
                started_at=at(start), completed_at=at(end)) for i, (name, start, end) in enumerate(zip(p.REQUIRED, (990, 995, 1000, 1110), (995, 1000, 1110, 1120)))])]
        self.data = {}; self.calls = []; self.queues = {}; self.downloads = []
        self.chosen = dict(runId=123456, runAttempt=2)
        self.record = dict(id=901, name=p.name(self.chosen), expired=False, created_at=at(1110), updated_at=at(1120),
            expires_at=at(10_000_000), workflow_run=dict(id=123456, repository_id=p.credentials.REPOSITORY_ID,
                head_repository_id=p.credentials.REPOSITORY_ID, head_sha='a'*40, head_branch='master'))
        self.install(); self.rezip()
    def install(self):
        self.data['branches/master'] = dict(commit=dict(sha='a'*40))
        self.data['actions/runs/123456/attempts/2'] = deepcopy(self.run)
        self.page('actions/runs/123456/attempts/2/jobs', 'jobs', self.jobs)
        raw = WORKFLOW.encode()
        self.data['contents/'+p.PATH+'?ref='+'a'*40] = dict(type='file', path=p.PATH, encoding='base64', size=len(raw),
            sha=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(), content=base64.b64encode(raw).decode())
    def rezip(self, entries=None):
        stream = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
                for name, data in entries or [('member-seal.json', p.encoded(self.seal))]: archive.writestr(name, data)
        self.raw = stream.getvalue(); self.record.update(size_in_bytes=len(self.raw), digest='sha256:'+p.digest(self.raw))
        self.data['actions/artifacts/901'] = deepcopy(self.record)
        self.page('actions/runs/123456/artifacts', 'artifacts', [self.record])
    def download(self, identity, output, size):
        if identity != 901 or size != len(self.raw): raise AssertionError('wrong original artifact')
        self.downloads.append(identity); Path(output).write_bytes(self.raw)


class ProvenanceTest(unittest.TestCase):
    def setUp(self):
        self.args = fixture(); self.seal = p.seal.create(**self.args); self.client = RunnerFixture(self.seal)
        self.chosen = self.client.chosen; temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.output = self.root/'observation'; self.output.mkdir()
    def collect(self, now=1200):
        self.output = self.root/('observation-'+str(len(list(self.root.iterdir())))); self.output.mkdir()
        return p.collect(self.output, self.args['cfg'], self.args['source'], self.args['request'], self.chosen,
                         WORKFLOW, self.client, lambda:now)
    def test_exact_attempt_collects_original_seal_without_latest_fallback(self):
        value = self.collect(); self.assertEqual('ORIGINAL_RUNNER_VERIFIED_NOT_QUALIFIED', value['status'])
        self.assertEqual(self.seal, value['seal']); self.assertFalse(value['fullRemoteQualification'])
        self.assertEqual([901], self.client.downloads)
        self.assertEqual(2, self.client.calls.count('actions/runs/123456/attempts/2'))
        self.assertFalse(any('/workflows/' in v or v == 'actions/runs/123456' for v in self.client.calls if not v.startswith('contents/')))
    def test_old_completed_member_is_valid_but_current_collection_cannot_be_stale(self):
        self.collect(now=900000)
        value = p.artifacts.read(self.output/'observation.json')
        with self.assertRaises(ValueError): p.validate(value, self.args['cfg'], self.args['source'], self.args['request'], self.chosen,
            self.output/'runner.zip', WORKFLOW, 900901)
    def test_failed_cancelled_running_wrong_source_attempt_or_repo_reject(self):
        for changes in (dict(conclusion='failure'), dict(conclusion='cancelled'), dict(status='in_progress'),
                        dict(head_sha='f'*40), dict(head_branch='topic'), dict(run_attempt=3), dict(event='push'), dict(path='.github/workflows/ci.yml')):
            self.client = RunnerFixture(self.seal); self.client.data['actions/runs/123456/attempts/2'].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError): self.collect()
            self.assertEqual([], self.client.downloads)
    def test_required_step_skipped_missing_reordered_or_foreign_job_reject(self):
        for mutate in (lambda j:j.update(run_attempt=1), lambda j:j.update(name='other'), lambda j:j['steps'].pop(),
                       lambda j:j['steps'][2].update(conclusion='skipped'), lambda j:j['steps'][2].update(started_at=at(994))):
            self.client = RunnerFixture(self.seal); mutate(self.client.jobs[0]); self.client.install()
            with self.assertRaises(ValueError): self.collect()
    def test_wrong_upload_attempt_expiry_digest_or_original_step_reject(self):
        for changes in (dict(name='v52-runner-123456-3'), dict(expired=True), dict(digest='missing'),
                        dict(created_at=at(1100)), dict(updated_at=at(1121)), dict(expires_at=at(1200))):
            self.client = RunnerFixture(self.seal); self.client.record.update(changes)
            self.client.data['actions/artifacts/901'] = deepcopy(self.client.record)
            self.client.page('actions/runs/123456/artifacts', 'artifacts', [self.client.record])
            with self.subTest(changes=changes), self.assertRaises(ValueError): self.collect()
    def test_complete_pagination_and_duplicate_or_truncated_inventory(self):
        records = [dict(id=2000+i, name='other-'+str(i)) for i in range(205)]+[self.client.record]
        self.client.page('actions/runs/123456/artifacts', 'artifacts', records); self.collect()
        self.assertEqual(2, self.client.calls.count('actions/runs/123456/artifacts?per_page=100&page=3'))
        self.client.data['actions/runs/123456/artifacts?per_page=100&page=1']['total_count'] += 1
        with self.assertRaises(ValueError): self.collect()
    def test_mutated_job_artifact_or_exact_source_bytes_during_collection_reject(self):
        for path, changed in (('actions/artifacts/901', dict(self.client.record, digest='sha256:'+'f'*64)),
                              ('actions/runs/123456/attempts/2', dict(self.client.run, conclusion='failure'))):
            self.client = RunnerFixture(self.seal); self.client.queues[path] = [deepcopy(self.client.data[path]), changed]
            with self.assertRaises(ValueError): self.collect()
        self.client = RunnerFixture(self.seal); self.client.data['contents/'+p.PATH+'?ref='+'a'*40]['sha'] = 'f'*40
        with self.assertRaises(ValueError): self.collect()
    def test_zip_rejects_duplicates_secrets_traversal_links_or_wrong_record(self):
        data = p.encoded(self.seal); link = zipfile.ZipInfo('member-seal.json'); link.external_attr = (stat.S_IFLNK|0o777)<<16
        for entries in ([('member-seal.json', data), ('private-key', b'secret')], [('member-seal.json', data)]*2,
                        [('../member-seal.json', data)], [(link, data)], [('member-seal.json', b'{}')]):
            self.client = RunnerFixture(self.seal); self.client.rezip(entries)
            with self.assertRaises((ValueError, KeyError)): self.collect()
    def test_resealed_wrong_original_invocation_or_execution_time_reject(self):
        for mutate in (lambda s:s['credentialContext'].update(runAttempt=3), lambda s:s.update(startedAt=999),
                       lambda s:s.update(completedAt=1111), lambda s:s.update(status='PASS')):
            seal = deepcopy(self.seal); mutate(seal); self.client = RunnerFixture(seal)
            with self.assertRaises(ValueError): self.collect()
    def test_actual_contract_requires_manual_master_environment_and_ordered_unconditional_steps(self):
        path = self.root/p.PATH; path.parent.mkdir(parents=True)
        path.write_text(WORKFLOW); self.assertEqual(WORKFLOW, p.contract(self.root))
        for old, new in (('workflow_dispatch:', 'push:'), ('v52-cloud-benchmark', 'other'),
                         ("github.ref == 'refs/heads/master'", 'true'), ('  runner:', '  other:'),
                         ('        run: fixture-only', '        if: always()\n        run: fixture-only')):
            path.write_text(WORKFLOW.replace(old, new))
            with self.assertRaises(ValueError): p.contract(self.root)
    def test_native_factory_owns_readonly_clients_and_rechecks_source(self):
        with patch.object(p.reads, 'source_configuration', return_value=self.args['cfg']), \
             patch.object(p.artifacts.inputs, 'checkout', return_value=self.args['source']), \
             patch.object(p, 'contract', return_value=WORKFLOW), patch.object(p, 'Network', return_value=self.client), \
             patch.object(p.time, 'time', return_value=1200):
            value = p.collect_native('a'*40, self.args['request'], self.chosen, self.root/'native')
        self.assertEqual(self.seal, value['seal'])
        with self.assertRaises(TypeError): p.collect_native('a'*40, self.args['request'], self.chosen, self.root/'injected', get=self.client.get)
        with patch.object(p.reads, 'source_configuration', side_effect=[self.args['cfg'], dict(self.args['cfg'], projectNumber='999')]), \
             patch.object(p.artifacts.inputs, 'checkout', return_value=self.args['source']), \
             patch.object(p, 'contract', return_value=WORKFLOW), patch.object(p, 'Network', return_value=self.client), \
             patch.object(p.time, 'time', return_value=1200):
            with self.assertRaisesRegex(ValueError, 'source changed'):
                p.collect_native('a'*40, self.args['request'], self.chosen, self.root/'changed')
        self.assertFalse((self.root/'changed/receipt.json').exists())
        self.assertTrue((self.root/'changed/failure.json').exists())
    def test_network_rejects_latest_runs_discovery_mutations_or_arbitrary_urls(self):
        client = p.Network(self.root/'requests')
        client.authorize_path('actions/runs/123456/attempts/2/jobs?per_page=100&page=1')
        for path in ('actions/runs/123456', 'actions/runs/123456/rerun', 'actions/runs/123456/cancel',
                     'actions/artifacts/901/zip', 'https://other.invalid', 'actions/workflows/ci.yml/runs'):
            with self.assertRaises(ValueError): client.authorize_path(path)


if __name__ == '__main__': unittest.main()
