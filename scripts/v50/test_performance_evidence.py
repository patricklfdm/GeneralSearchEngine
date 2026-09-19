"""Fast parser/model negatives plus resealed real-runtime evidence negatives."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from . import performance_evidence as e
from .performance_model import schedule
from .offline_harness import ROOT, save

PLAN = ROOT / 'docs/v5x/v5.0/phase6-plan.json'


class PerformanceEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(PLAN.read_bytes())

    def test_rejects_cloud_and_fake(self):
        for execution in ('fake', 'gcp', 'canonical'):
            with self.subTest(execution=execution):
                plan = copy.deepcopy(self.plan); plan['execution'] = execution
                with self.assertRaisesRegex(ValueError, 'provenance'): e.validate_plan(plan)

    def test_rejects_unbounded_workload(self):
        for key in ('corpusDocuments', 'cyclesPerWindow', 'clientConcurrency', 'maximumRunSeconds'):
            with self.subTest(key=key):
                plan = copy.deepcopy(self.plan); plan['localSmoke'][key] *= 100
                with self.assertRaises(ValueError): e.validate_plan(plan)

    def test_rejects_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.json'; path.write_text('{"status":"FAIL","status":"PASS"}')
            with self.assertRaisesRegex(ValueError, 'duplicate'): e.read(path)

    def test_rejects_nonfinite_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.json'; path.write_text('{"duration":NaN}')
            with self.assertRaisesRegex(ValueError, 'nonfinite'): e.read(path)

    def test_rejects_symlink_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'escape').symlink_to(PLAN)
            with self.assertRaisesRegex(ValueError, 'symlink'): e.inventory(Path(tmp))

    def test_rejects_oversize_member_before_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            with (Path(tmp) / 'oversize').open('wb') as stream: stream.truncate(e.MEMBER_LIMIT + 1)
            with self.assertRaisesRegex(ValueError, 'bound'): e.inventory(Path(tmp))

    def test_bulk_counts_and_committed_boundary(self):
        model = schedule(self.plan)
        self.assertEqual((len(model['rows']), len(model['anchors']), model['sequence']), (90, 73, 76))
        self.assertEqual(len(model['documents']), 64)
        self.assertEqual(len([r for r in model['rows'] if r['operation'] == 'ADD_ALL' and r['documents'] == 4]), 9)


def negative_fixtures(source, output):
    """Mutate actual public-JVM evidence, recompute its envelope, then reject semantics."""
    source, output = Path(source), Path(output)
    e.validate(source, PLAN)
    results = []
    def change_json(path, mutate):
        value = e.read(path); mutate(value); save(path, value)
    def leader(path, mutate):
        change_json(path / 'members/node-1.json', mutate)
    def window(m):
        return next(x['response']['measurement'] for x in m['exchanges'] if x['request']['command'] == 'measure')
    def telemetry(m):
        return next(x['response']['telemetry'] for x in m['exchanges'] if x['request']['command'] == 'telemetry' and x['response']['telemetry']['enabled'])
    def force_before_window(m):
        observed = telemetry(m)
        configured = next(x for x in m['exchanges'] if x['request']['command'] == 'configure' and
                          x['request']['window'] == observed['window'])
        force = observed['forces'][0]
        force['startNanos'] = configured['response']['startNanos'] - 1
        force['elapsedNanos'] = force['endNanos'] - force['startNanos']
    cases = {
        'fake-provenance': lambda p: change_json(p / 'set.json', lambda v: v.update(execution='fake')),
        'cloud-relabel': lambda p: change_json(p / 'set.json', lambda v: v.update(execution='gcp')),
        'false-run-duration': lambda p: change_json(p / 'set.json', lambda v: v.update(finishedNanos=v['startedNanos'] + 1)),
        'missing-sample': lambda p: leader(p, lambda v: window(v)['rows'].pop()),
        'forged-success-sequence': lambda p: leader(p, lambda v: window(v)['rows'][0].update(afterSequence=999)),
        'forged-read-answer': lambda p: leader(p, lambda v: window(v)['rows'][-1].update(answerDigest='0' * 64)),
        'negative-latency': lambda p: leader(p, lambda v: window(v)['rows'][0].update(elapsedNanos=-1)),
        'serial-voters': lambda p: change_json(p / 'members/node-3.json', lambda v: v.update(readyNanos=v['finishedNanos'] - 1)),
        'reused-pid': lambda p: change_json(p / 'members/node-3.json', lambda v: v.update(pid=e.read(p / 'members/node-1.json')['pid'])),
        'false-cleanup': lambda p: leader(p, lambda v: v.update(cleanup='still-running')),
        'missing-force': lambda p: leader(p, lambda v: telemetry(v)['forces'].pop()),
        'force-before-window': lambda p: leader(p, force_before_window),
        'success-before-proof': lambda p: leader(p, lambda v: telemetry(v)['events'].__setitem__(0, dict(event='BEFORE_CLIENT_SUCCESS', index=26, nanos=1))),
        'wrong-control-source': lambda p: change_json(p / 'control.json', lambda v: v['result']['identity'].update(coreSource=e.read(p / 'metadata.json')['jars']['core']['path'])),
        'mixed-artifacts': lambda p: change_json(p / 'metadata.json', lambda v: v['jars']['core'].update(sha256=v['jars']['control']['sha256'])),
        'false-aggregate': lambda p: change_json(p / 'measurements.json', lambda v: v['candidate']['baseline-a'].update(requests=999)),
        'missing-member': lambda p: (p / 'members/node-3.json').unlink(),
        'changed-plan': lambda p: change_json(p / 'plan.json', lambda v: v['localSmoke'].update(seed=18)),
        'changed-source-backup': lambda p: next(v for v in (p / 'source').rglob('*') if v.is_file()).write_bytes(b'changed source'),
        'corrupt-authority': lambda p: (p / 'node-3/current.gsr').write_bytes(b'not a selector'),
        'rehashed-wrong-payload': mutate_snapshot,
    }
    with tempfile.TemporaryDirectory(prefix='gse-phase6-negatives-') as tmp:
        target = Path(tmp) / 'case'
        for name, mutate in cases.items():
            shutil.copytree(source, target)
            mutate(target)
            envelope = e.read(target / 'set.json'); envelope['files'] = e.inventory(target); save(target / 'set.json', envelope)
            try:
                e.validate(target, PLAN)
            except (ValueError, KeyError, FileNotFoundError) as error:
                results.append(dict(case=name, status='REJECTED', reason=str(error)))
            else:
                raise AssertionError('semantic negative accepted: ' + name)
            shutil.rmtree(target)
    save(output, dict(status='PASS', cases=results))
    print(json.dumps(dict(semanticNegatives=len(results), status='PASS'), sort_keys=True))


def mutate_snapshot(root):
    """Rewrite all containing checksums so rejection must come from ancestry/semantics."""
    from . import admission_format as f
    path = root / 'node-3'
    selector_raw = (path / 'current.gsr').read_bytes()
    selector = f.record(selector_raw, 10); selector.take(32); selector.text(64)
    selected = path / selector.text(32)
    snapshot_raw = (selected / 'snapshot.gsr').read_bytes()
    body = bytearray(snapshot_raw[48:]); body[52 + 24 + 1 + 32] ^= 1  # First anchor payload digest.
    snapshot = f.framed(8, body); (selected / 'snapshot.gsr').write_bytes(snapshot)
    seal_raw = (selected / 'generation.gsr').read_bytes()
    seal = f.framed(11, seal_raw[48:].replace(snapshot_raw[16:48], snapshot[16:48]))
    (selected / 'generation.gsr').write_bytes(seal)
    (path / 'current.gsr').write_bytes(f.framed(10, selector_raw[48:].replace(seal_raw[16:48], seal[16:48])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path); parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.evidence:
        parser.error('--output is required with --evidence') if not args.output else negative_fixtures(args.evidence, args.output)
    else:
        unittest.main(argv=['performance-evidence'])
