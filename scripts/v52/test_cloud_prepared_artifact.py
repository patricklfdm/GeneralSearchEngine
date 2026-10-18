"""Synthetic original-prepare API/ZIP checks; not paid admission evidence."""
from copy import deepcopy
import io
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile
from . import cloud_prepared_artifact as p
from .test_cloud_prepared import arguments
from .test_cloud_runner_provenance import RunnerFixture, WORKFLOW, at


def fixture():
    args = arguments(); package = b'modeled original input archive'
    args['proof'].update(packageSha256=p.digest(package), packageBytes=len(package))
    plan = p.prepared.prepare(**args); approval = p.prepared.approval_template(plan)
    cfg = dict(schema='gse-v52-preflight-config-v1', provider=args['configuration'], projectNumber=args['project_number'],
               layout=args['resource_layout'], policy=args['ownership_policy'])
    context = dict(schema=p.credentials.SCHEMA, **p.credentials.selection(cfg['provider'], cfg['projectNumber'], 'runner'),
                   source='a'*40, runId=123456, runAttempt=2)
    record = dict(schema=p.SCHEMA, status='PREPARED_NOT_ADMITTED', configurationSha256=p.preflight.configuration(cfg),
        credentialContext=context, planSha256=approval['planSha256'], requestSha256=approval['requestSha256'], preparedAt=1000,
        buildSha256='1'*64, cleanupSha256='2'*64, preflightSha256='3'*64, paidAdmission=False, fullRemoteQualification=False)
    return cfg, args['proof']['source'], {'plan.json':p.encoded(plan), 'approval.json':p.encoded(approval),
        'preparation.json':p.encoded(record), 'inputs.tar.gz':package}


class PrepareFixture(RunnerFixture):
    def __init__(self, files):
        self.files = deepcopy(files); super().__init__({})
        self.record['name'] = p.name(self.chosen); self.rezip()
    def rezip(self, entries=None):
        stream = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
                for name, raw in entries or self.files.items(): archive.writestr(name, raw)
        self.raw = stream.getvalue(); self.record.update(size_in_bytes=len(self.raw), digest='sha256:'+p.digest(self.raw))
        self.data['actions/artifacts/901'] = deepcopy(self.record)
        self.page('actions/runs/123456/artifacts', 'artifacts', [self.record])


class PreparedArtifactTest(unittest.TestCase):
    def setUp(self):
        self.cfg, self.source, self.files = fixture(); self.client = PrepareFixture(self.files)
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root = Path(temp.name)
    def collect(self, now=1200):
        output = self.root/str(len(list(self.root.iterdir()))); output.mkdir()
        return p.collect(output, self.cfg, self.source, self.client.chosen, WORKFLOW, self.client, lambda:now)
    def test_exact_original_prepare_is_not_approval_or_resource_admission(self):
        files, receipt = self.collect()
        self.assertEqual(self.files, files); self.assertEqual('PREPARED_ARTIFACT_VERIFIED_NOT_ADMITTED', receipt['status'])
        self.assertFalse(receipt['paidAdmission']); self.assertFalse(p.strict(files['approval.json'])['confirmed'])
        self.assertEqual([901], self.client.downloads)
    def test_expired_plan_or_confirmed_approval_forged_package_or_configuration_reject(self):
        with self.assertRaises(ValueError): self.collect(now=5000)
        for name, mutate in (
            ('approval.json', lambda v:v.update(confirmed=True)),
            ('plan.json', lambda v:v['configuration'].update(project='another-project')),
            ('preparation.json', lambda v:v['credentialContext'].update(runAttempt=3)),
            ('preparation.json', lambda v:v.update(planSha256='f'*64)),
            ('preparation.json', lambda v:v.update(paidAdmission=True))):
            files = deepcopy(self.files); value = p.strict(files[name]); mutate(value); files[name] = p.encoded(value)
            self.client = PrepareFixture(files)
            with self.subTest(name=name), self.assertRaises(ValueError): self.collect()
        self.client = PrepareFixture(dict(self.files, **{'inputs.tar.gz':b'changed'}))
        with self.assertRaisesRegex(ValueError, 'package bytes'): self.collect()
    def test_wrong_attempt_failed_original_and_wrong_upload_interval_reject(self):
        for changes in (dict(run_attempt=3), dict(conclusion='failure'), dict(head_branch='branch')):
            self.client = PrepareFixture(self.files); self.client.data['actions/runs/123456/attempts/2'].update(changes)
            with self.assertRaises(ValueError): self.collect()
        for change in (dict(name='v52-prepared-123456-3'), dict(created_at=at(1109)), dict(expired=True)):
            self.client = PrepareFixture(self.files); self.client.record.update(change); self.client.rezip()
            with self.assertRaises(ValueError): self.collect()
    def test_missing_extra_duplicate_symlink_traversal_inventory_rejects(self):
        link = zipfile.ZipInfo('plan.json'); link.external_attr = (stat.S_IFLNK|0o777)<<16
        for entries in ([(k,v) for k,v in self.files.items() if k!='approval.json'], list(self.files.items())+[('private-key',b'secret')],
                        list(self.files.items())+[('plan.json',self.files['plan.json'])],
                        [(link if k=='plan.json' else k,v) for k,v in self.files.items()],
                        [('../plan.json' if k=='plan.json' else k,v) for k,v in self.files.items()]):
            self.client = PrepareFixture(self.files); self.client.rezip(entries)
            with self.assertRaises(ValueError): self.collect()
    def test_original_run_jobs_artifact_or_workflow_cannot_change_mid_collection(self):
        for path, value in (('actions/artifacts/901', dict(self.client.record, digest='sha256:'+'f'*64)),
                            ('actions/runs/123456/attempts/2', dict(self.client.run, run_attempt=3))):
            self.client = PrepareFixture(self.files); self.client.queues[path] = [deepcopy(self.client.data[path]), value]
            with self.assertRaises(ValueError): self.collect()
        self.client = PrepareFixture(self.files)
        self.client.data['contents/'+p.origin.PATH+'?ref='+'a'*40]['sha'] = 'f'*40
        with self.assertRaises(ValueError): self.collect()
    def test_complete_paginated_inventory_and_missing_page_reject(self):
        records = [dict(id=2000+i, name='unrelated-'+str(i)) for i in range(205)]+[self.client.record]
        self.client.page('actions/runs/123456/artifacts', 'artifacts', records); self.collect()
        self.assertEqual(2, self.client.calls.count('actions/runs/123456/artifacts?per_page=100&page=3'))
        self.client.data['actions/runs/123456/artifacts?per_page=100&page=1']['total_count'] += 1
        with self.assertRaises(ValueError): self.collect()
    def test_native_collector_exports_only_validated_files_and_rechecks_source(self):
        with patch.object(p.reads, 'source_configuration', return_value=self.cfg), patch.object(p.inputs, 'checkout', return_value=self.source), \
             patch.object(p.origin, 'contract', return_value=WORKFLOW), patch.object(p, 'Network', return_value=self.client), patch.object(p.time, 'time', return_value=1200):
            result = p.collect_native('a'*40, self.client.chosen, self.root/'native')
        self.assertEqual('PREPARED_ARTIFACT_VERIFIED_NOT_ADMITTED', result['status'])
        self.assertEqual(set(p.LIMITS), {v.name for v in (self.root/'native/files').iterdir()})
        with patch.object(p.reads, 'source_configuration', side_effect=[self.cfg,dict(self.cfg,projectNumber='999')]), \
             patch.object(p.inputs, 'checkout', return_value=self.source), patch.object(p.origin, 'contract', return_value=WORKFLOW), \
             patch.object(p, 'Network', return_value=self.client), patch.object(p.time, 'time', return_value=1200):
            with self.assertRaisesRegex(ValueError, 'source changed'): p.collect_native('a'*40, self.client.chosen, self.root/'changed')
        self.assertFalse((self.root/'changed/files').exists()); self.assertTrue((self.root/'changed/failure.json').exists())


if __name__ == '__main__': unittest.main()
