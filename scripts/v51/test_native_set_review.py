"""Offline acceptance rejects incomplete sets, altered raw inputs and false warnings."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from . import native_set_review as s, native_member_review as r, remote_budget
from . import cloud_runner_admission_qualification as fixtures
from . import test_native_image_continuation as records


class MetadataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frozen = r.old.admission.workload.load()
        loader = patch.object(r.old.admission.workload, 'load', side_effect=lambda: deepcopy(frozen))
        loader.start(); cls.addClassCleanup(loader.stop)
        cls.tmp = tempfile.TemporaryDirectory(); cls.addClassCleanup(cls.tmp.cleanup)
        cls.original_plan = fixtures.fixture(Path(cls.tmp.name)/'fixture')['value']

    def fixture(self, name):
        old = self.original_plan; stage = old['resourcePlan']; req = stage['request']
        plan = r.old.admission.plan(old['configuration'], old['artifacts'], stage['guestAccess'],
            dict(old['prices'], pricedThroughSeconds=45000), None, sequence=req['sequence'], now=req['createdAt'],
            maximum_cost=250_000_000, member=name, order='any-order', soft_budget=True)
        req = plan['resourcePlan']['request']; clock = [0]
        allocation = r.timing.validate(req); b = remote_budget.Budget(clock=lambda: clock[0], profile=allocation['profile'])
        for cell in ('preparation', *allocation['cells'], 'validation-retention', 'cleanup'):
            with b.stage(cell):
                # A genuine soft overrun must be retained, not changed to zero.
                clock[0] += (allocation['limitsSeconds'][cell]+1)*10**9
        before = b.finish(); final = b.finish()
        scope = 'owned-complete-'+allocation['preset']; sha = r.n.validate_request(req)
        recorded = dict(status='PASS', scope=scope, cells=allocation['cells'], errors=[],
                        physicalHistoryQualified=True, backupRestoreQualified=name != 'failure-drill', aggregate={})
        resources = dict(status='RESOURCES_PREPARED', requestSha256=sha,
            resources=[dict(spec=v, id=str(i+1), attempted=True) for i,v in enumerate(r.n.resources(req))])
        result = dict(schema=r.n.COMPLETION_SCHEMA, execution=r.n.EXECUTION, status='PASS', errors=[],
            paidCloud=True, engineWorkloadExecuted=True, fullRemoteQualification=False, requestSha256=sha,
            qualificationScope=scope, retention='VERIFIED', leaseReleased=True, evidence=recorded,
            evidenceSha256=r.m.sha(r.m.canonical(recorded)), budgetBeforeCompletion=before, budget=final,
            cleanup=dict(status='PASS', errors=[], leftovers=[], checks=[dict(name=v['spec']['name'],
                expectedId=v['id'], absent=True, observed=None) for v in resources['resources']]))
        plan_sha = r.m.sha(r.m.canonical(plan))
        wrapper = dict(schema='gse-v51-runner-experiment-entry-v1', mode='run', status='PASS', source=req['source'],
            paidCloud=True, engineWorkloadExecuted=True, fullRemoteQualification=False, result=result, preparedRun=98,
            planSha256=plan_sha, binding=dict(runId=99, runAttempt=1, source=req['source'], event='workflow_dispatch',
                workflow='.github/workflows/v51-replication-evidence.yml', role='runner'))
        approval = r.old.admission.approval_template(plan); approval['confirmed'] = True
        files = dict(zip(r.old.CONTROL, (wrapper, result, approval, plan, resources)))
        return files, dict(source=req['source'], run=99, attempt=1, request_sha=sha, member=name)

    def save(self, root, files):
        for name, value in files.items():
            path = root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(r.m.canonical(value))

    def test_all_presets_keep_soft_overruns_and_expired_approval_is_not_renewed(self):
        for name in r.timing.MEMBERS:
            with self.subTest(member=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); files, pins = self.fixture(name); self.save(root, files)
                plan, result = r.old.metadata(root, **pins)
                self.assertTrue(result['budget']['warnings'])
                self.assertFalse(all(v['withinBudget'] for v in result['budget']['intervals']))
                with self.assertRaisesRegex(ValueError, 'expiry'):
                    r.old.admission.validate_plan(plan, plan['expiresAt'])

    def test_warning_accounting_cannot_hide_overrun_or_fake_within_budget(self):
        files, _ = self.fixture('canonical-1'); value = files['execution/receipt.json']['budget']
        plan = files['handoff/prepared/plan.json']; cells = plan['timing']['cells']
        changes = [lambda v:v.update(warnings=[]), lambda v:v['warnings'].append(v['warnings'][0]),
                   lambda v:v['intervals'][1].update(withinBudget=True),
                   lambda v:v['intervals'][1].update(elapsedNanos=0),
                   lambda v:v['intervals'][1].update(category='control'),
                   lambda v:v.update(mode='hard'), lambda v:v.update(status='FAIL')]
        for change in changes:
            mutated = deepcopy(value); change(mutated)
            with self.assertRaises(ValueError):r.old.budget(mutated, plan['timing'], cells=cells)

    def test_member_scope_and_cleanup_failures_are_never_softened(self):
        for name in ('experiment', 'failure-drill', 'canonical-3'):
            files, pins = self.fixture(name)
            mutations = [lambda f:f['execution/receipt.json']['evidence']['cells'].pop(),
                lambda f:f['execution/receipt.json'].update(retention='FAIL'),
                lambda f:f['execution/receipt.json']['cleanup']['checks'][0].update(expectedId='999'),
                lambda f:f['receipt.json']['binding'].update(runId=100)]
            for mutation in mutations:
                with tempfile.TemporaryDirectory() as temp:
                    modified = deepcopy(files); mutation(modified); self.save(Path(temp), modified)
                    with self.assertRaises(ValueError):r.old.metadata(Path(temp), **pins)
            with tempfile.TemporaryDirectory() as temp:
                self.save(Path(temp), files)
                with self.assertRaisesRegex(ValueError, 'member'):
                    r.old.metadata(Path(temp), **dict(pins, member='canonical-2'))

    def test_full_preset_dispatch_uses_actual_independent_validators(self):
        for name in r.timing.MEMBERS:
            with patch.object(r.canonical, 'validate', return_value='canonical') as canonical, \
                 patch.object(r.faults, 'validate', return_value='drill') as drill, \
                 patch.object(r.experiment, 'validate', return_value='experiment') as experiment:
                result = r.replay('raw', 'out', name)
                self.assertEqual(1, canonical.call_count+drill.call_count+experiment.call_count)
                self.assertEqual('canonical' if name.startswith('canonical') else 'drill' if name=='failure-drill' else name, result)

    def test_canonical_archive_binds_repetition_and_requires_identical_raw_replay(self):
        files, pins = self.fixture('canonical-1')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); raw = root/'raw'; raw.mkdir()
            plan = files['handoff/prepared/plan.json']; req = plan['resourcePlan']['request']
            result = files['execution/receipt.json']
            r.c.write_once(raw/'plan.json', dict(request=req)); r.c.write_once(raw/'validation.json', result['evidence'])
            for cell in plan['timing']['cells']:
                span = next(v for v in result['budget']['intervals'] if v['category']==cell)
                r.c.write_once(raw/(cell+'-timeline.json'), {k:span[k] for k in ('startNanos','endNanos')})
            binding = r.m.sha(r.m.canonical(dict(scope='owned-complete-canonical', repetition=1,
                                               requestSha256=pins['request_sha'])))
            r.parts.pack(raw, root/'parts', binding)
            with zipfile.ZipFile(root/'experiment.zip', 'w') as z:
                for name, value in files.items():z.writestr(name, r.m.canonical(value))
                for file in (root/'parts').iterdir():z.writestr(r.old.PREFIX+file.name, file.read_bytes())
            sha = r.old.digest(root/'experiment.zip')
            for index, aggregate in enumerate(({'forged':'PASS'}, {})):
                with patch.object(r, 'provenance', return_value=(dict(head_sha=pins['source'], id=99), dict(id=1), sha)), \
                     patch.object(r, 'replay', return_value=aggregate) as replay:
                    if index==0:
                        with self.assertRaisesRegex(ValueError, 'aggregate differs'):
                            r.review(root, root/f'out-{index}', 'canonical-1', request_sha=pins['request_sha'])
                    else:
                        self.assertTrue(r.review(root, root/f'out-{index}', 'canonical-1', request_sha=pins['request_sha'])['rawEvidenceReplayed'])
                    replay.assert_called_once()


class SetReviewTest(unittest.TestCase):
    def test_registered_review_keeps_original_provenance_and_complete_set(self):
        docs = Path(__file__).resolve().parents[2]/'docs/v5x/v5.1'
        review = r.c.read(docs/'phase6-cloud-review.json')
        registry = r.c.read(docs/'cloud-benchmark-baselines.json')
        provenance = r.c.read(docs/'phase6-cloud-provenance.json')
        self.assertEqual(dict(schema=s.REGISTRY_SCHEMA, baselines=[s.entry(review)]), registry)
        self.assertEqual(provenance['reviewSha256'], registry['baselines'][0]['reviewSha256'])
        self.assertEqual(provenance['observationsSha256'], review['observationsSha256'])
        self.assertEqual(list(s.MEMBERS), [v['member'] for v in provenance['members']])
        self.assertTrue(provenance['leaseObservedAbsent'])
        for row, pin in zip(review['members'], provenance['members']):
            for key in ('source', 'sequence', 'requestSha256', 'preparedRun', 'runAttempt', 'artifactId'):
                self.assertEqual(row[key], pin[key])
            self.assertEqual(row['runId'], pin['run'])
            self.assertEqual(row['archiveSha256'], pin['sha256'])
            self.assertEqual(row['records'], {k:v['sha256'] for k,v in pin['records'].items()})
        changes = [lambda v:v['members'].pop(), lambda v:v['members'].reverse(),
            lambda v:v['members'][1].update(runId=v['members'][0]['runId']),
            lambda v:v['members'][0].update(source=v['source']),
            lambda v:v['members'][2].update(sequence=s.continuation.policy()['oldSequence']),
            lambda v:v['members'][3].update(rawEvidenceReplayed=False),
            lambda v:v['members'][4]['cells'].pop(), lambda v:v.update(payloadSha256='0'*64),
            lambda v:v.update(fullRemoteQualification=False)]
        for change in changes:
            value = deepcopy(review); change(value)
            with self.assertRaises(ValueError):s.entry(value)
        # Changing a descriptive result also changes the registry digest, even
        # though this compact check does not repeat the independent raw replay.
        changed = deepcopy(review); changed['members'][0]['stageSeconds']['healthy'] += 1
        self.assertNotEqual(registry['baselines'][0], s.entry(changed))

    def test_producing_api_identity_and_success_cannot_be_substituted(self):
        source = 'a'*40
        run = dict(id=99, run_attempt=1, head_branch='master', head_sha=source,
            event='workflow_dispatch', status='completed', conclusion='success',
            repository=dict(full_name=r.ci.REPOSITORY, id=r.ci.REPOSITORY_ID),
            path='.github/workflows/v51-replication-evidence.yml')
        jobs = dict(total_count=2, jobs=[dict(name=name, run_id=99, run_attempt=1,
            head_sha=source, conclusion='success', steps=[]) for name in
            ('observations', 'Runner precheck and approved execution')])
        jobs['jobs'][1]['steps'] = [dict(name=name, conclusion='success') for name in
            ('Run exact approved native V5.1 experiment', 'Retain native experiment evidence including failures')]
        listing = dict(total_count=1, artifacts=[dict(id=77, name='v51-experiment-99-1',
            size_in_bytes=3, digest='sha256:'+r.m.sha(b'zip'), workflow_run=dict(id=99,
            head_sha=source, head_branch='master', repository_id=r.ci.REPOSITORY_ID,
            head_repository_id=r.ci.REPOSITORY_ID))])
        original = {'run.json':run, 'jobs.json':jobs, 'artifacts.json':listing}
        changes = [lambda v:v['run.json'].update(event='pull_request'),
            lambda v:v['run.json'].update(run_attempt=2),
            lambda v:v['run.json']['repository'].update(id=1),
            lambda v:v['jobs.json']['jobs'][1].update(head_sha='b'*40),
            lambda v:v['jobs.json']['jobs'][1]['steps'][1].update(conclusion='skipped'),
            lambda v:v['artifacts.json']['artifacts'][0]['workflow_run'].update(id=100),
            lambda v:v['artifacts.json']['artifacts'][0].update(size_in_bytes=4)]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'experiment.zip').write_bytes(b'zip')
            def save(values):
                for key,value in values.items():(root/key).write_bytes(r.m.canonical(value))
            save(original); self.assertEqual(r.m.sha(b'zip'), r.provenance(root, 'canonical-1')[2])
            for change in changes:
                value = deepcopy(original); change(value); save(value)
                with self.assertRaises(ValueError):r.provenance(root, 'canonical-1')

    def test_partial_completion_cannot_invoke_or_replace_raw_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); r.c.write_once(root/'observations.json', {})
            with patch.object(s.continuation, 'review', return_value=dict(status='PARTIAL', batchComplete=False)), \
                 patch.object(s.member, 'review') as raw:
                with self.assertRaisesRegex(ValueError, 'complete batch'):
                    s.review(root, root/'output', root/'observations.json', {}, 'a'*40)
                raw.assert_not_called()
                self.assertFalse(r.c.read(root/'output/review.json')['fullRemoteQualification'])

    def test_raw_failure_is_retained_and_cannot_register(self):
        f, obs, _ = records.fixture(); chosen = [dict(member=name, requestSha256='c'*64) for name in s.MEMBERS]
        batch = dict(status='PASS', batchComplete=True, missing=[], members=chosen)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); r.c.write_once(root/'obs.json', obs)
            with patch.object(s.continuation, 'review', return_value=batch), \
                 patch.object(s.member, 'review', side_effect=ValueError('bad raw proof')) as raw:
                with self.assertRaisesRegex(ValueError, 'bad raw proof'):
                    s.review(root, root/'output', root/'obs.json', {}, 'a'*40)
                self.assertGreaterEqual(raw.call_count, 1)
                self.assertEqual('FAIL', r.c.read(root/'output/review.json')['status'])
                self.assertFalse((root/'registry.json').exists())

    def test_retained_cloud_parts_must_match_archive_bytes_and_complete_inventory(self):
        f, obs, _ = records.fixture(); rows = obs['members']['failure-drill']
        completion = rows['completion.json']['value']; evidence = rows['owned-experiment/evidence.json']['value']
        prefix = r.n.a.PREFIX+'attempts/'+completion['requestSha256']+'/owned-experiment/'
        blobs = {'parts/parts.json':b'parts', 'parts/part-0000.bin':b'original', 'metadata/parts.json':b'metadata',
                 'evidence.json':r.m.canonical(evidence)}
        inventory = rows['owned-experiment/manifest.json']['value']
        inventory['files'] = {prefix+k:dict(bytes=len(v), sha256=r.m.sha(v)) for k,v in blobs.items()}
        rows['owned-experiment/manifest.json'] = records.wrapped(inventory)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); replay = root/'replay'; file = replay/'originals/execution/receipt.json'
            file.parent.mkdir(parents=True); file.write_bytes(r.m.canonical(completion))
            def write(changed=None, extra=False):
                with zipfile.ZipFile(root/'experiment.zip', 'w') as z:
                    for name, data in blobs.items():
                        if name=='evidence.json':continue
                        path=(r.old.PREFIX+name[6:] if name.startswith('parts/') else 'execution/retention-metadata/parts/'+name[9:])
                        z.writestr(path, changed if name=='parts/part-0000.bin' and changed is not None else data)
                    if extra:z.writestr(r.old.PREFIX+'part-0001.bin', b'extra')
            write(); self.assertEqual(set(s.continuation.RECORDS), set(s.retained(root, replay, rows)))
            write(b'tampered')
            with self.assertRaisesRegex(ValueError, 'digest'):s.retained(root, replay, rows)
            write(extra=True)
            with self.assertRaisesRegex(ValueError, 'inventory'):s.retained(root, replay, rows)
            write(); file.write_bytes(r.m.canonical(dict(completion, status='FAIL')))
            with self.assertRaisesRegex(ValueError, 'completion'):s.retained(root, replay, rows)

    def test_no_overwrite_registration_is_checked_before_expensive_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = Path(temp)/'registry.json'; registry.write_text('original')
            with patch('sys.argv', ['review', 'review', temp, '--output', temp+'/out', '--source', 'a'*40,
                                   '--observations', temp+'/observations', '--registry', str(registry)]), \
                 patch.object(s, 'review') as replay:
                with self.assertRaisesRegex(ValueError, 'already registered'):s.main()
                replay.assert_not_called(); self.assertEqual('original', registry.read_text())

    def test_percentiles_use_nearest_rank_and_original_sample_count(self):
        result = s.distribution([100, 10, 20, 30])
        self.assertEqual(dict(samples=4, totalNanos=160, p50Nanos=20, p95Nanos=100, p99Nanos=100), result)
        with self.assertRaises(ValueError):s.distribution([])
        with self.assertRaises(ValueError):s.distribution([True])


if __name__ == '__main__': unittest.main()
