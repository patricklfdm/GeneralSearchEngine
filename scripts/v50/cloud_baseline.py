"""Offline Phase 6 review and append-only registration from all five raw bundles."""
import argparse
import json
from pathlib import Path
import re
import tempfile

from .cloud_common import canonical, plan, prefix, read, require, save, sha
from .cloud_presets import sequence_order
from .cloud_remote_evidence import validate_set
from .cloud_workload_evidence import measurements, stream
from .cloud_workload_io import sha_file, unpack
from .cloud_workload_plan import PLAN_SHA256, read_plan

BASELINE = 'v5.0.0-replicated-cloud'
REVIEW_SCHEMA = 'gse-v50-cloud-baseline-review-v1'
REGISTRY_SCHEMA = 'gse-v50-cloud-baseline-registry-v1'


def percentiles(values):
    values = sorted(values)
    require(bool(values), 'empty measurement sample')
    return dict(samples=len(values), **{
        f'p{p}Nanos': values[(len(values) * p + 99) // 100 - 1] for p in (50, 95, 99)})


def baseline_operations(root, directory):
    calls = [r for r in stream(root / directory, 'calls')
             if r['window'] in ('baseline-a', 'baseline-b')]
    return {op: dict(percentiles(r['endNanos'] - r['startNanos'] for r in calls if r['operation'] == op),
                     documents=sum(r['documents'] for r in calls if r['operation'] == op))
            for op in sorted({r['operation'] for r in calls})}


def resource_summary(root):
    """Sampled peaks by voter; process counters restart with each JVM generation."""
    result = {}
    for node in (1, 2, 3):
        samples = [r for directory in sorted((root / 'streams').glob(f'node-{node}-*'))
                   for r in stream(directory, 'resources')]
        require(bool(samples), 'missing voter resource samples')
        processes = [r['process'] for r in samples]
        runtimes = [r['runtime'] for r in samples]
        result[str(node)] = dict(
            samples=len(samples),
            heapUsedBytes=max(r['heapUsedBytes'] for r in processes),
            rssBytes=max(r['VmRSSBytes'] for r in processes),
            retainedLogBytes=max(r['retainedLogBytes'] for r in runtimes),
            pendingClients=max(r['pendingClients'] for r in runtimes),
            writerQueue=max(r['observer']['writerQueue'] for r in runtimes),
            peerInFlight=max((p['inFlight'] for r in runtimes for p in r['observer']['peers'].values()), default=0),
            peerQueued=max((p['queued'] for r in runtimes for p in r['observer']['peers'].values()), default=0),
            queuedBytes=max(r['observer']['queuedBytes'] for r in runtimes),
            maximumJvmCpuNanos=max(r['cpuNanos'] for r in processes),
            maximumJvmGcCount=max(r['gcCount'] for r in processes),
            maximumJvmGcMillis=max(r['gcMillis'] for r in processes))
    return result


def build_review(roots):
    roots = [Path(p) for p in roots]
    validated = validate_set(roots)  # Always revalidate raw bytes, never a claimed PASS JSON.
    members = []
    for root, result in zip(roots, validated['members']):
        state = read(root / 'completion.json', 16 << 20)
        request = state['request']
        with tempfile.TemporaryDirectory(prefix='gse-v50-baseline-') as temporary:
            raw = Path(temporary) / 'raw'
            unpack(root / 'workload-evidence', raw)
            measured = measurements(raw)
            operations = {label: baseline_operations(raw, directory) for label, directory in
                          [('candidate', 'streams/node-1-1'), ('control', 'control-streams')]}
            forces = list(stream(raw / 'streams/node-1-1', 'forces'))
            force_timings = {kind: percentiles(r['endNanos'] - r['startNanos'] for r in forces if r['kind'] == kind)
                             for kind in sorted({r['kind'] for r in forces})}
            cells = [{k: v for k, v in cell.items() if k != 'details'} for cell in read(raw / 'cells.json')]
            peaks = resource_summary(raw)
        members.append(dict(
            profile=request['profile'], repetition=request['repetition'], preparedRun=request['runId'],
            owner=request['owner'], completionSha256=sha_file(root / 'completion.json'),
            partsSha256=sha_file(root / 'workload-evidence/parts.json'),
            evidenceUri='gs://' + state['plan']['bucket'] + '/' + prefix(state['plan'], request),
            startedAt=state['startedAt'], finishedAt=state['finishedAt'],
            validation=result, measurements=measured, baselineOperations=operations,
            leaderForceTimings=force_timings, resources=peaks, cells=cells))
    last = read(roots[-1] / 'completion.json', 16 << 20)
    workload = read_plan()
    return dict(schema=REVIEW_SCHEMA, name=BASELINE, status=validated['status'], execution=validated['execution'],
                source=validated['source'], sequence=validated['sequence'], sequenceOrder=validated['sequenceOrder'],
                suite=workload['suite'], preset=workload['preset'], workloadPlanSha256=PLAN_SHA256,
                runnerPlanSha256=sha(canonical(plan())), artifactSha256=validated['members'][0]['artifactSha256'],
                reservedMicrousd=sum(v['maximumCostMicrousd'] for v in last['budgetReservation']['reservations']),
                members=members)


def review_entry(review):
    """Check a compact review for registry integrity; this is not raw validation."""
    require(set(review) == {'schema', 'name', 'status', 'execution', 'source', 'sequence', 'sequenceOrder',
            'suite', 'preset', 'workloadPlanSha256', 'runnerPlanSha256', 'artifactSha256', 'reservedMicrousd', 'members'},
            'review fields')
    workload = read_plan()
    require(review['schema'] == REVIEW_SCHEMA and review['name'] == BASELINE and review['status'] == 'PASS' and
            review['execution'] == 'gcp-cloud-workload-set', 'complete cloud review required')
    require(review['suite'] == workload['suite'] and review['preset'] == workload['preset'] and
            review['workloadPlanSha256'] == PLAN_SHA256 and review['runnerPlanSha256'] == sha(canonical(plan())),
            'review plan identity')
    require(isinstance(review['source'], str) and re.fullmatch('[0-9a-f]{40}', review['source']) and
            isinstance(review['sequence'], str) and re.fullmatch('[0-9a-f]{32}', review['sequence']), 'review source/sequence')
    require(type(review['reservedMicrousd']) is int and 0 < review['reservedMicrousd'] <=
            workload['resources']['maximumCompleteSequenceMicrousd'], 'review cost ceiling')
    members = review['members']
    require(isinstance(members, list) and len(members) == 5 and
            sequence_order(members) == review['sequenceOrder'] and
            len({m['owner'] for m in members}) == len({m['completionSha256'] for m in members}) == 5,
            'complete distinct ordered review members')
    require(set(review['artifactSha256']) == {'core', 'replication', 'control'} and
            review['artifactSha256']['control'] == workload['publishedControl']['sha256'], 'review artifacts')
    digests = list(review['artifactSha256'].values())
    previous_finish = 0
    for member in members:
        digests.extend([member['completionSha256'], member['partsSha256']])
        require(type(member['repetition']) is int and type(member['startedAt']) is int and
                type(member['finishedAt']) is int and previous_finish <= member['startedAt'] < member['finishedAt'],
                'review topology chronology')
        previous_finish = member['finishedAt']
        value = member['validation']
        require(value['status'] == value['cleanup'] == 'PASS' and value['retention'] == 'VERIFIED' and
                value['execution'] == 'gcp-cloud-workload' and value['sourceHead'] == review['source'] and
                value['sourceDirty'] is False and value['artifactSha256'] == review['artifactSha256'] and
                value['profile'] == member['profile'] and value['repetition'] == member['repetition'] and
                value['planSha256'] == PLAN_SHA256, 'review member identity/status')
        expected = [v['name'] for v in workload['profiles'][member['profile']]['cells']]
        require([c['name'] for c in member['cells']] == expected and
                value['cells'] == len(expected) and all(c['status'] == 'PASS' for c in member['cells']), 'review cells')
    require(all(isinstance(v, str) and re.fullmatch('[0-9a-f]{64}', v) for v in digests), 'review digest')
    return dict(name=BASELINE, suite=review['suite'], preset=review['preset'], sourceCommit=review['source'],
                sequence=review['sequence'], sequenceOrder=review['sequenceOrder'], memberCount=5, canonicalCount=3,
                reviewSha256=sha(canonical(review)), workloadPlanSha256=PLAN_SHA256,
                artifactSha256=review['artifactSha256'])


def check_registry(registry, review):
    require(set(registry) == {'schema', 'baselines'} and registry['schema'] == REGISTRY_SCHEMA and
            isinstance(registry['baselines'], list), 'registry schema')
    expected = review_entry(review)
    require(registry['baselines'] in ([], [expected]), 'registry identity or duplicate baseline')
    return registry


def register(roots, review_path, registry_path):
    # Refuse duplicates before the costly offline pass. No force/overwrite option.
    reviewed = read(review_path, 16 << 20)
    registry_path = Path(registry_path)
    registry = read(registry_path) if registry_path.exists() else dict(schema=REGISTRY_SCHEMA, baselines=[])
    check_registry(registry, reviewed)
    require(not registry['baselines'], 'baseline already registered')
    regenerated = build_review(roots)
    require(regenerated == reviewed, 'raw evidence differs from reviewed result')
    registry['baselines'].append(review_entry(regenerated))
    save(registry_path, registry)
    return registry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    review = commands.add_parser('review')
    review.add_argument('evidence', type=Path, nargs=5)
    review.add_argument('--output', type=Path, required=True)
    registration = commands.add_parser('register')
    registration.add_argument('evidence', type=Path, nargs=5)
    registration.add_argument('--review', type=Path, required=True)
    registration.add_argument('--registry', type=Path, required=True)
    check = commands.add_parser('check')
    check.add_argument('--review', type=Path, required=True)
    check.add_argument('--registry', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'review':
        require(not args.output.exists(), 'review output already exists')
        value = build_review(args.evidence)
        review_entry(value)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as output:
            output.write(json.dumps(value, sort_keys=True, indent=2) + '\n')
    elif args.command == 'register':
        register(args.evidence, args.review, args.registry)
    else:
        value = check_registry(read(args.registry), read(args.review, 16 << 20))
        require(len(value['baselines']) == 1, 'baseline not registered')
    print(json.dumps(dict(status='PASS', command=args.command, name=BASELINE)))


if __name__ == '__main__':
    main()
