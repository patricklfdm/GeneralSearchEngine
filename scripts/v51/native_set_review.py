"""Independent raw review and first baseline registration for the frozen continuation.

This entry accepts only the specifically authorized image-continuation batch.
It cannot authorize other mixed-source sets. Every invocation replays all five
original archives; supplied PASS summaries never replace raw validation.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from datetime import datetime
from pathlib import Path
import zipfile

from . import native_image_continuation as continuation, native_member_review as member
from . import cloud_native_authority as n, performance_model as m, remote_command as c

SCHEMA = 'gse-v51-native-set-review-v1'
REGISTRY_SCHEMA = 'gse-v51-cloud-baseline-registry-v1'
NAME = 'v5.1-automatic-leadership-cloud'
MEMBERS = (*continuation.INHERITED, *continuation.REMAINING)


def retained(root, replay, rows):
    """Bind the independently replayed archive to immutable cloud record hashes."""
    completion = continuation.record(rows['completion.json'])
    inventory = continuation.record(rows['owned-experiment/manifest.json'])
    evidence = continuation.record(rows['owned-experiment/evidence.json'])
    result = c.read(replay/'originals/execution/receipt.json')
    m.need(all(result.get(k) == v for k, v in completion.items()) and result['evidence'] == evidence,
           'set archive/cloud completion differs')
    prefix = n.a.PREFIX+'attempts/'+completion['requestSha256']+'/owned-experiment/'
    with zipfile.ZipFile(root/'experiment.zip') as archive:
        expected = {}
        for name, info in inventory['files'].items():
            m.need(name.startswith(prefix), 'set retention prefix')
            suffix = name[len(prefix):]
            if suffix == 'evidence.json':
                raw = m.canonical(evidence)
            else:
                if suffix.startswith('parts/'):
                    path = member.old.PREFIX+suffix[len('parts/'):]
                else:
                    m.need(suffix.startswith('metadata/'), 'set unexpected retained object')
                    path = 'execution/retention-metadata/parts/'+suffix[len('metadata/'):]
                m.need(archive.getinfo(path).file_size == info['bytes'] <= member.parts.LIMITS['partBytes'],
                       'set retained object size')
                raw = archive.read(path)
            m.need(len(raw) == info['bytes'] and m.sha(raw) == info['sha256'], 'set retained object digest')
            expected[suffix] = info
        actual = {'evidence.json'}
        for path in archive.namelist():
            for directory, label in ((member.old.PREFIX, 'parts/'), ('execution/retention-metadata/parts/', 'metadata/')):
                if path.startswith(directory) and not path.endswith('/'):
                    actual.add(label+path[len(directory):])
        m.need(actual == set(expected), 'set retention complete inventory')
    return {key: rows[key]['sha256'] for key in continuation.RECORDS}


def distribution(values):
    values = sorted(values); m.need(values and all(type(v) is int and v >= 0 for v in values), 'latency samples')
    return dict(samples=len(values), totalNanos=sum(values), **{
        f'p{p}Nanos': values[(len(values)*p+99)//100-1] for p in (50, 95, 99)})


def measurements(output, aggregate):
    """Derive distributions only from the just-validated original JVM exchanges."""
    results = []
    for tape in aggregate['tapes']:
        mode, cell, issuer = (tape[k] for k in ('mode', 'cell', 'issuer'))
        folder = output/'replay'/(member.canonical.run.key(mode, cell)+'-'+issuer)
        node = 'local' if mode == 'published-v4.4-local' else issuer
        calls = [v for v in c.read(folder/(node+'-exchanges.json'))
                 if v['request']['command'] == 'call' and v['request']['window'] != 'warmup']
        groups = {}
        for row in calls:
            call = row['response']['call']; window = call['window']
            key = (window, call['operation']); groups.setdefault(key, []).append(row)
        windows = {}
        for (window, operation), rows in sorted(groups.items()):
            windows.setdefault(window, {})[operation] = dict(
                api=distribution([v['response']['call']['apiEndNanos']-v['response']['call']['apiStartNanos'] for v in rows]),
                guestDriverRoundTrip=distribution([v['endNanos']-v['startNanos'] for v in rows]))
        ratios = {}
        if cell == 'healthy':
            for operation in m.OPERATIONS:
                a = [r['response']['call'] for r in calls if r['request']['window'].startswith('baseline-') and r['request']['operation'] == operation]
                b = [r['response']['call'] for r in calls if r['request']['window'].startswith('instrumented-') and r['request']['operation'] == operation]
                total_a = sum(v['apiEndNanos']-v['apiStartNanos'] for v in a)
                total_b = sum(v['apiEndNanos']-v['apiStartNanos'] for v in b)
                m.need(len(a) == len(b) == 12 and total_a > 0, 'canonical ABBA samples')
                ratios[operation] = dict(baselineSamples=len(a), instrumentedSamples=len(b),
                    meanInstrumentedToBaselinePpm=total_b*1_000_000//total_a)
        raw = output/'raw'/member.canonical.run.key(mode, cell)
        controller = []
        for file in sorted((raw/'commands').glob('*/*/request.json')):
            req = c.read(file)['request']
            if req['command'] == 'window':
                span = c.read(file.with_name('observation.json'))
                controller.append(dict(node=file.parents[1].name, commandId=req['commandId'],
                    elapsedNanos=span['endNanos']-span['startNanos']))
        results.append(dict(mode=mode, cell=cell, issuer=issuer, measuredCalls=len(calls), windows=windows,
            instrumentedToBaseline=ratios, controllerWindowCommands=controller,
            resources=[dict(node=v['node'], **v['resources']) for v in tape['members']]))
    return results


def review_member(args):
    inputs, output, name, selected, observed = args
    row = member.review(inputs/name, output/name, name, request_sha=selected['requestSha256'],
        progress=lambda value: print(m.canonical(dict(value, member=name)).decode(), flush=True))
    m.need(row['source'] == selected['source'] and row['sequence'] == selected['sequence'], 'set replay identity')
    if name in continuation.INHERITED:
        m.need(row['runId'] == continuation.policy()['inherited'][name]['runId'], 'set inherited producing run')
    row['records'] = retained(inputs/name, output/name, observed)
    aggregate = c.read(output/name/'aggregate.json')
    if name.startswith('canonical-'):
        row['measurements'] = measurements(output/name, aggregate)
        row['richCalls'] = aggregate['calls']
        row['faultCalls'] = sum(v['calls'] for v in aggregate['faults'])
        row['negativeCases'] = sum(len(v['negatives']) for v in aggregate['faults']) + sum(
            len(v['physical']['negatives']) for v in aggregate['tapes'] if v['physical'] is not None)
    elif name == 'failure-drill':
        row['faultCalls'] = sum(v['calls'] for v in aggregate['cells'])
        row['negativeCases'] = sum(len(v['negatives']) for v in aggregate['cells'])
    run = c.read(inputs/name/'run.json')
    row.update(startedAt=run['created_at'], finishedAt=run['updated_at'])
    print(m.canonical(dict(member=name, status='RAW_REPLAY_PASS')).decode(), flush=True)
    return row


def review(inputs, output, observations, prepared, source, *, workers=1):
    m.need(type(workers) is int and 1 <= workers <= 3, 'review worker bound')
    inputs = c.directory(inputs); output = Path(output).absolute()
    output.parent.mkdir(parents=True, exist_ok=True); c.directory(output.parent); output.mkdir(mode=0o700)
    base = dict(schema=SCHEMA, name=NAME, source=source, scope='authorized-native-continuation-set',
                paidCloud=False, paidAdmission=False, ledgerModified=False, workloadsExecuted=False)
    try:
        observed = c.read(Path(observations)); batch = continuation.review(observed, source, prepared)
        m.need(batch['status'] == 'PASS' and batch['batchComplete'] and batch['missing'] == [], 'complete batch required')
        c.write_once(output/'completion-review.json', batch)
        c.write_once(output/'observations.json', observed)
        selected = {v['member']: v for v in batch['members']}
        m.need(set(selected) == set(MEMBERS), 'set exact members')
        tasks = [(inputs, output, name, selected[name], observed['members'][name]) for name in MEMBERS]
        if workers == 1:
            members = [review_member(task) for task in tasks]
        else:
            # Separate interpreters actually parallelize CPU-heavy trace replay;
            # spawned processes also isolate validator scratch/runtime state.
            with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn')) as pool:
                members = list(pool.map(review_member, tasks))
        chronological = sorted(members, key=lambda row: row['startedAt'])
        m.need(all(datetime.fromisoformat(a['finishedAt']) <= datetime.fromisoformat(b['startedAt'])
                   for a, b in zip(chronological, chronological[1:])), 'overlapping native runs')
        total, attempts = n.inspect_ledger(observed['ledger'])
        report = dict(base, status='PASS', fullRemoteQualification=True, sequence=batch['sequence'],
            policySha256=batch['policySha256'], observationsSha256=batch['observationsSha256'],
            payloadSha256=continuation.policy()['payloadSha256'], members=members,
            recordedCostMicrousd=total, budgetMode='soft',
            historicalFailures=[dict(requestSha256=sha, source=v['request']['source'], sequence=v['request']['sequence'],
                                     member=v['request']['member']) for sha,v in attempts.items() if v['status'] == 'FAIL'])
    except Exception as error:
        c.write_once(output/'review.json', dict(base, status='FAIL', fullRemoteQualification=False,
                                              failure=dict(type=type(error).__name__, message=str(error))))
        raise
    c.write_once(output/'review.json', report, maximum=4 << 20)
    return report


def entry(review):
    """Compact integrity check only; registration calls the raw review above."""
    m.need(review['schema'] == SCHEMA and review['name'] == NAME and review['status'] == 'PASS' and
           review['fullRemoteQualification'] is True and review['scope'] == 'authorized-native-continuation-set', 'set review scope')
    rows = review['members']
    m.need([v['member'] for v in rows] == list(MEMBERS) and len({v['runId'] for v in rows}) == 5 and
           len({v['requestSha256'] for v in rows}) == 5 and
           all(v['status'] == 'PASS' and v['rawEvidenceReplayed'] is True for v in rows), 'set review completeness')
    frozen = continuation.policy()
    m.need(review['policySha256'] == m.sha(m.canonical(frozen)) and review['payloadSha256'] == frozen['payloadSha256'] and
           review['sequence'] == frozen['sequence'], 'set review frozen policy')
    for row in rows:
        name = row['member']; inherited = name in continuation.INHERITED
        m.need(row['source'] == (frozen['oldSource'] if inherited else review['source']) and
               row['sequence'] == (frozen['oldSequence'] if inherited else frozen['sequence']) and
               row['cells'] == member.timing.allocation(name)['cells'], 'set review member identity')
        if inherited:
            pin = frozen['inherited'][name]
            m.need(row['runId'] == pin['runId'] and row['requestSha256'] == pin['requestSha256'] and
                   row['records'] == pin['records'], 'set review inherited pin')
        for key in ('archiveSha256', 'requestSha256', 'aggregateSha256', 'planSha256', 'evidenceSha256'):
            n.a.digest(row[key])
    return dict(name=NAME, scope=review['scope'], measuredSources=sorted({v['source'] for v in rows}),
                measuredSequences=sorted({v['sequence'] for v in rows}), memberCount=5, canonicalCount=3,
                reviewSha256=m.sha(m.canonical(review)), policySha256=review['policySha256'], payloadSha256=review['payloadSha256'])


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('review'); run.add_argument('inputs', type=Path); run.add_argument('--output', type=Path, required=True)
    run.add_argument('--source', required=True); run.add_argument('--observations', type=Path, required=True)
    run.add_argument('--prepared', action='append', default=[]); run.add_argument('--workers', type=int, default=1)
    run.add_argument('--registry', type=Path)
    check = sub.add_parser('check'); check.add_argument('--review', type=Path, required=True); check.add_argument('--registry', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'check':
        value = c.read(args.registry); expected = entry(c.read(args.review, maximum=4 << 20))
        m.need(value == dict(schema=REGISTRY_SCHEMA, baselines=[expected]), 'baseline registry differs')
    else:
        pairs = [v.split('=', 1) for v in args.prepared]
        m.need(all(len(v) == 2 for v in pairs) and len(dict(pairs)) == len(pairs), 'prepared argument inventory')
        if args.registry is not None:
            m.need(not args.registry.exists(), 'baseline already registered; no overwrite')
        value = review(args.inputs, args.output, args.observations, dict(pairs), args.source, workers=args.workers)
        if args.registry is not None:
            c.write_once(args.registry, dict(schema=REGISTRY_SCHEMA, baselines=[entry(value)]))
    print(m.canonical(dict(status='PASS', command=args.command, name=NAME)).decode())


if __name__ == '__main__': main()
