"""Offline review must reject inconsistent completion, accounting and archives."""
from copy import deepcopy
import tempfile
from pathlib import Path
import stat
import unittest
from unittest.mock import patch
import warnings
import zipfile

from . import native_experiment_review as r, remote_budget
from . import cloud_runner_admission_qualification as fixtures


class NativeExperimentReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frozen = r.admission.workload.load()
        loader = patch.object(r.admission.workload, 'load', side_effect=lambda: deepcopy(frozen))
        loader.start(); cls.addClassCleanup(loader.stop)
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.fixture = fixtures.fixture(Path(cls.temp.name)/'fixture')

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(); self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.plan = deepcopy(self.fixture['value']); self.req = self.plan['resourcePlan']['request']
        self.pins = dict(source=self.req['source'], run=999, attempt=1, request_sha=r.n.validate_request(self.req))
        clock = iter(range(1, 100)); budget = remote_budget.Budget(clock=lambda: next(clock), profile=r.admission.timing.PROFILE)
        for stage in ('preparation', *r.CELLS, 'validation-retention', 'cleanup'):
            with budget.stage(stage): pass
        before = budget.finish(); final = budget.finish()
        resources = dict(status='RESOURCES_PREPARED', requestSha256=self.pins['request_sha'], resources=[
            dict(spec=spec, id=str(i+1), attempted=True) for i, spec in enumerate(r.n.resources(self.req))])
        recorded = dict(status='PASS', scope=r.SCOPE, errors=[], physicalHistoryQualified=True,
                        backupRestoreQualified=True, aggregate={'status':'PASS'})
        self.result = dict(schema=r.n.COMPLETION_SCHEMA, execution=r.n.EXECUTION, status='PASS', errors=[],
            paidCloud=True, engineWorkloadExecuted=True, fullRemoteQualification=False,
            requestSha256=self.pins['request_sha'], qualificationScope=r.SCOPE, retention='VERIFIED', leaseReleased=True,
            evidence=recorded, evidenceSha256=r.m.sha(r.m.canonical(recorded)), budgetBeforeCompletion=before, budget=final,
            cleanup=dict(status='PASS', errors=[], leftovers=[], checks=[dict(name=v['spec']['name'], expectedId=v['id'],
                         absent=True, observed=None) for v in resources['resources']]))
        self.wrapper = dict(schema='gse-v51-runner-experiment-entry-v1', mode='run', status='PASS', source=self.req['source'],
            paidCloud=True, engineWorkloadExecuted=True, fullRemoteQualification=False, result=self.result,
            planSha256=r.m.sha(r.m.canonical(self.plan)), binding=dict(runId=999, runAttempt=1, source=self.req['source'],
                event='workflow_dispatch', workflow='.github/workflows/v51-replication-evidence.yml', role='runner'))
        self.files = {'receipt.json':self.wrapper, 'execution/receipt.json':self.result,
                      'approval.json':self.fixture['approved'], 'handoff/prepared/plan.json':self.plan,
                      'execution/preparation/resources/receipt.json':resources}

    def save(self):
        for name, value in self.files.items():
            path = self.root/name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(r.m.canonical(value))

    def test_historical_plan_can_be_reviewed_without_current_admission(self):
        self.save()
        plan, result = r.metadata(self.root, **self.pins)
        self.assertEqual(self.plan, plan); self.assertEqual(self.result, result)
        with self.assertRaisesRegex(ValueError, 'expiry'):
            r.admission.validate_plan(plan, plan['expiresAt'])

    def test_completion_binding_and_cleanup_negatives(self):
        original = deepcopy(self.files)
        changes = [
            lambda f: f['receipt.json']['binding'].update(runId=1000),
            lambda f: f['receipt.json']['binding'].update(runAttempt=2),
            lambda f: f['receipt.json'].update(source='c'*40),
            lambda f: f['receipt.json'].update(planSha256='a'*64),
            lambda f: f['approval.json'].update(confirmed=False),
            lambda f: f['execution/receipt.json'].update(fullRemoteQualification=True),
            lambda f: f['execution/receipt.json'].update(retention='FAILED'),
            lambda f: f['execution/receipt.json'].update(leaseReleased=False),
            lambda f: f['execution/receipt.json']['cleanup']['checks'].pop(),
            lambda f: f['execution/receipt.json']['cleanup']['checks'][0].update(expectedId='999'),
            lambda f: f['execution/receipt.json']['cleanup']['checks'][0].update(observed={'id':'1'}),
            lambda f: f['execution/receipt.json']['cleanup']['leftovers'].append('resource'),
            lambda f: f['execution/preparation/resources/receipt.json']['resources'][0].update(id='2'),
            lambda f: f['execution/receipt.json']['evidence'].update(backupRestoreQualified=False),
            lambda f: f['execution/receipt.json'].update(evidenceSha256='a'*64),
        ]
        for ordinal, change in enumerate(changes):
            with self.subTest(ordinal=ordinal):
                self.files = deepcopy(original); change(self.files); self.save()
                with self.assertRaises(ValueError): r.metadata(self.root, **self.pins)

    def test_disjoint_budget_negatives(self):
        original = self.result['budget']
        changes = [
            lambda v: v['intervals'][1].update(startNanos=0),
            lambda v: v['intervals'][1].update(endNanos=-1),
            lambda v: v['intervals'][1].update(elapsedNanos=True),
            lambda v: v['intervals'][1].update(elapsedNanos=999),
            lambda v: v['intervals'][1].update(withinBudget=False),
            lambda v: v['intervals'][3].update(category='preparation'),
            lambda v: v['intervals'].pop(1),
            lambda v: v['spentNanos'].update(healthy=0),
            lambda v: v.update(elapsedNanos=1),
        ]
        for ordinal, change in enumerate(changes):
            with self.subTest(ordinal=ordinal):
                value = deepcopy(original); change(value)
                with self.assertRaises(ValueError): r.budget(value, self.plan['timing'])
        timing = deepcopy(self.plan['timing']); timing['limitsSeconds']['healthy'] = 0
        with self.assertRaisesRegex(ValueError, 'limit'): r.budget(original, timing)
        timing = deepcopy(self.plan['timing']); timing['leaseSeconds'] = 0
        with self.assertRaisesRegex(ValueError, 'limit'): r.budget(original, timing)

    def archive(self, extra=()):
        path = self.root/'input.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            for name, value in self.files.items(): archive.writestr(name, r.m.canonical(value))
            archive.writestr(r.PREFIX+'parts.json', b'{}')
            for name, value in extra: archive.writestr(name, value)
        return path

    def test_zip_pin_and_unsafe_members(self):
        link = zipfile.ZipInfo('link'); link.create_system = 3; link.external_attr = (stat.S_IFLNK | 0o777) << 16
        for ordinal, extra in enumerate((('../outside', b'x'), ('/absolute', b'x'), ('bad\\path', b'x'),
                                         ('receipt.json', b'{}'), (link, b'../outside'))):
            with self.subTest(ordinal=ordinal), warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                archive = self.archive([extra]); target = self.root/str(ordinal); target.mkdir()
                with self.assertRaises(ValueError): r.extract(archive, target, r.digest(archive))
                self.assertEqual([], list(target.iterdir()))
        archive = self.archive()
        with self.assertRaisesRegex(ValueError, 'archive digest'): r.extract(archive, self.root/'unused', 'f'*64)
        with patch.dict(r.parts.LIMITS, expandedBytes=1):
            with self.assertRaisesRegex(ValueError, 'archive size'): r.extract(archive, self.root/'unused', r.digest(archive))

    def test_forged_pass_receipts_cannot_replace_original_parts(self):
        archive = self.archive(); output = self.root/'review'
        with patch.object(r.evidence, 'validate') as replay:
            with self.assertRaises(ValueError):
                r.review(archive, output, archive_sha=r.digest(archive), **self.pins)
            replay.assert_not_called()
        result = r.c.read(output/'review.json')
        self.assertEqual('FAIL', result['status']); self.assertFalse(result['ownedExperimentQualified'])

    def test_replay_is_required_and_must_match_original_aggregate(self):
        def unpack(source, target, binding):
            target.mkdir()
            r.c.write_once(target/r.parts.INDEX, {})
            r.c.write_once(target/'plan.json', dict(request=self.req))
            r.c.write_once(target/'validation.json', self.result['evidence'])
            for cell in r.CELLS:
                row = next(v for v in self.result['budget']['intervals'] if v['category'] == cell)
                r.c.write_once(target/(cell+'-timeline.json'), {k:row[k] for k in ('startNanos', 'endNanos')})
            return dict(status='PASS')
        archive = self.archive(); sha = r.digest(archive)
        for ordinal, replay_result in enumerate(({'status':'DIFFERENT'}, {'status':'PASS'})):
            output = self.root/f'review-{ordinal}'
            with patch.object(r.parts, 'unpack', side_effect=unpack), patch.object(r.evidence, 'validate', return_value=replay_result) as replay:
                if ordinal == 0:
                    with self.assertRaisesRegex(ValueError, 'aggregate differs'):
                        r.review(archive, output, archive_sha=sha, **self.pins)
                else:
                    report = r.review(archive, output, archive_sha=sha, **self.pins)
                    self.assertEqual('PASS', report['status'])
                    self.assertFalse(report['paidAdmission']); self.assertFalse(report['fullRemoteQualification'])
                replay.assert_called_once_with(output/'raw', output/'replay', authority=r.n)
            self.assertTrue((output/r.parts.INDEX).is_file()); self.assertFalse((output/'raw'/r.parts.INDEX).exists())
        self.assertEqual(sha, r.digest(archive))

    def test_corrupt_retained_part_rejects_even_with_new_outer_archive_pin(self):
        raw = self.root/'input-raw'; raw.mkdir()
        r.c.write_once(raw/'plan.json', dict(request=self.req))
        binding = r.m.sha(r.m.canonical(dict(scope=r.SCOPE, requestSha256=self.pins['request_sha'])))
        packed = self.root/'packed'; r.parts.pack(raw, packed, binding)
        archive = self.root/'corrupt.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            for name, value in self.files.items(): output.writestr(name, r.m.canonical(value))
            for path in packed.iterdir():
                data = path.read_bytes()
                if path.name.endswith('.bin'): data = bytes([data[0] ^ 1])+data[1:]
                output.writestr(r.PREFIX+path.name, data)
        with patch.object(r.evidence, 'validate') as replay:
            with self.assertRaisesRegex(ValueError, 'part hash'):
                r.review(archive, self.root/'review', archive_sha=r.digest(archive), **self.pins)
            replay.assert_not_called()


if __name__ == '__main__': unittest.main()
