"""Read-only independent local member/set verifier. Never admits cloud/fake results."""
import argparse
import json
import math
from pathlib import Path
import re
import struct
import zipfile
from . import admission_format as f, runtime_format
from .performance_model import OPERATIONS, OP_IDS, INDEXES, blob, digest, encoded, display, schedule, summary

MEMBER_LIMIT, BUNDLE_LIMIT, FILE_LIMIT = 16 << 20, 128 << 20, 2000
STAGES = ('AFTER_LOCAL_ENTRY_FORCE', 'AFTER_ENTRY_QUORUM', 'AFTER_LOCAL_PROOF_FORCE',
          'AFTER_PROOF_QUORUM', 'BEFORE_APPLICATION_PUBLICATION', 'AFTER_APPLICATION_PUBLICATION', 'BEFORE_CLIENT_SUCCESS')


def read(path):
    f.check(path.stat().st_size <= MEMBER_LIMIT, 'JSON member bound')
    def pairs(items):
        value = dict(items)
        f.check(len(value) == len(items), 'duplicate JSON key')
        return value
    value = json.loads(path.read_bytes(), object_pairs_hook=pairs, parse_constant=lambda s: f.check(False, 'nonfinite JSON'))
    def bounded(item, depth=0):
        f.check(depth <= 24, 'JSON depth')
        if isinstance(item, dict):
            for child in item.values(): bounded(child, depth + 1)
        elif isinstance(item, list):
            for child in item: bounded(child, depth + 1)
        elif isinstance(item, float):
            f.check(math.isfinite(item), 'nonfinite JSON')
    bounded(value)
    return value


def inventory(root):
    result = {}; total = 0
    for path in sorted(root.rglob('*')):
        f.check(not path.is_symlink(), 'evidence symlink')
        if not path.is_file() or path == root / 'set.json': continue
        size = path.stat().st_size; total += size
        f.check(size <= MEMBER_LIMIT and total <= BUNDLE_LIMIT and len(result) < FILE_LIMIT, 'evidence bound')
        result[str(path.relative_to(root))] = dict(bytes=size, sha256=digest(path.read_bytes()))
    return result


def validate_plan(plan):
    f.check((plan['schema'], plan['evidenceSchema'], plan['execution'], plan['preset'], plan['protocol']) ==
            ('gse-v50-phase6-plan-v1', 'gse-v50-performance-evidence-v1', 'local-public-runtime-only',
             'v5.0-phase6-local-smoke-v1', 'gse-replication/1.1'), 'plan provenance')
    s = plan['localSmoke']
    f.check([s[k] for k in ('seed', 'corpusDocuments', 'loadBulkElements', 'mutationBulkElements', 'warmupCycles', 'cyclesPerWindow', 'clientConcurrency')] ==
            [17, 64, 16, 4, 1, 2, 1], 'unsupported workload preset')
    f.check(s['windows'] == ['baseline-a', 'instrumented-a', 'instrumented-b', 'baseline-b'] and s['operations'] == list(OPERATIONS), 'workload order')
    f.check(s['offeredRate'] == 'closed-loop' and s['maximumApplicationEntries'] == 72 and s['maximumLogIndex'] == 74 and
            s['maximumRunSeconds'] == 240 and s['maximumWindowSeconds'] == 30, 'workload ceilings')
    f.check(plan['evidenceBounds'] == dict(maxMemberBytes=MEMBER_LIMIT, maxBundleBytes=BUNDLE_LIMIT, maxFiles=FILE_LIMIT,
            maxResponseBytes=4 << 20, maxObservationsPerWindow=4096, maxEncodedAttemptBytesPerWindow=8 << 20), 'evidence ceilings')
    f.check(plan['jvmArguments'] == ['-Xms64m', '-Xmx256m', '-XX:+UseG1GC', '-XX:ActiveProcessorCount=2'], 'JVM preset')
    f.check(plan['publishedControl']['sha256'] == '0219af2998e1f6f782443097b8b4b8d792e45da56535b0c45b1c9fff77dd50e5', 'control pin')
    model = schedule(plan)
    f.check(s['corpusSha256'] == digest(b''.join(blob(encoded(d)) for d in model['initial'])) and s['encodedKeyBytes'] == 4 and
            s['measurementBudgetSeconds'] + s['controlAndSetupBudgetSeconds'] + s['cleanupReserveSeconds'] == s['maximumRunSeconds'], 'corpus/budget freeze')


def duration(value):
    f.check(all(type(value[k]) is int for k in ('startNanos', 'endNanos', 'elapsedNanos')) and
            value['endNanos'] > value['startNanos'] and value['elapsedNanos'] == value['endNanos'] - value['startNanos'], 'monotonic duration')


def resources(value):
    f.check(0 < value['heapUsedBytes'] <= value['heapMaxBytes'] <= 256 << 20 and
            0 < value['VmRSSBytes'] <= value['VmHWMBytes'], 'memory sample')
    f.check(all(type(value[k]) is int and value[k] >= 0 for k in ('gcCount', 'gcMillis', 'cpuNanos')), 'resource counters')
    f.check(all(type(v) is int and v >= 0 for v in value['processIo'].values()), 'IO counters')


def windows(values, plan, model):
    f.check([v['window'] for v in values] == ['warmup', *plan['localSmoke']['windows']], 'measurement windows')
    previous = None
    for window in values:
        duration(window); resources(window['resources'])
        f.check(window['elapsedNanos'] <= plan['localSmoke']['maximumWindowSeconds'] * 1_000_000_000, 'window deadline')
        if previous is not None: f.check(previous <= window['startNanos'], 'overlapping windows')
        expected = [r for r in model['rows'] if r['window'] == window['window']]
        f.check(len(expected) == len(window['rows']), 'missing/extra operation samples')
        previous = window['startNanos']
        for row, wanted in zip(window['rows'], expected):
            duration(row)
            f.check(previous <= row['startNanos'] < row['endNanos'] <= window['endNanos'], 'row timing/order')
            previous = row['endNanos']
            f.check({k: row[k] for k in wanted if k != 'window'} == {k: v for k, v in wanted.items() if k != 'window'}, 'operation semantics/accounting')
        previous = window['endNanos']


def identity(value, receipt, metadata, plan, plan_sha, jar):
    f.check(value['pid'] == receipt['pid'] and value['planSha256'] == plan_sha and
            value['coreSource'] == metadata['jars'][jar]['path'] and value['jvmArguments'] == plan['jvmArguments'] and
            value['availableProcessors'] == 2 and value['os'] == 'Linux' and value['javaRuntime'].startswith('21'), 'runtime identity')
    f.check(receipt['exitCode'] == 0 and receipt['startedNanos'] < receipt['finishedNanos'], 'process lifetime/exit')
    args = receipt['args']
    f.check(args[:5] == [metadata.get('javaExecutable', 'java'), *plan['jvmArguments']] and args[5] == '-cp', 'process JVM flags')
    expected_jars = [metadata['jars'][jar]['path']] if jar == 'control' else [metadata['jars'][n]['path'] for n in ('core', 'replication')]
    entries = args[6].split(':')
    f.check(entries[:-1] == expected_jars and entries[-1].endswith('/classes-' + ('control' if jar == 'control' else 'candidate')), 'isolated runtime classpath')


def member(root, node, metadata, plan, plan_sha):
    m = read(root / 'members' / (node + '.json'))
    f.check(m['schema'] == 'gse-v50-performance-member-v1' and m['node'] == node and m['ready']['node'] == node and
            m['ready']['ready'] is True and m['cleanup'] == 'reaped' and m['forced'] is False and
            m['linuxStartTicks'].isdigit(), 'member provenance/cleanup')
    identity(m['ready']['identity'], m, metadata, plan, plan_sha, 'core')
    prior = m['readyNanos']
    f.check(m['startedNanos'] < prior < m['finishedNanos'], 'member ready lifetime')
    for e in m['exchanges']:
        f.check(prior <= e['sentNanos'] < e['receivedNanos'] < m['finishedNanos'], 'command chronology')
        prior = e['receivedNanos']; r = e['response']; q = e['request']; duration(r); resources(r['resources'])
        f.check(q['command'] == r['command'] and r['accepted'] is (q['command'] != 'no-quorum'), 'command outcome')
        s = r['status']
        f.check({p['node'] for p in r['peers']} == {'node-1', 'node-2', 'node-3'} - {node} and
                all(0 <= p['appliedIndex'] <= p['durableIndex'] <= 74 and 0 <= p['matchIndex'] <= p['durableIndex'] for p in r['peers']), 'peer observation bounds')
        f.check(0 <= s['pendingClients'] <= plan['replicationBounds']['maxPendingClientOperations'] and
                0 <= s['retainedBytes'] <= plan['application']['maxRetainedBytes'] and 0 <= s['walBytes'] <= plan['application']['maxRetainedBytes'], 'observed storage/queue bounds')
    f.check(m['exchanges'][-1]['request']['command'] == 'close' and m['exchanges'][-1]['response']['status']['pendingClients'] == 0, 'close settlement')
    common = ['configure', 'telemetry'] * 4 + ['configure', 'checkpoint', 'close']
    expected_commands = ['activate', 'measure'] + ['configure', 'measure', 'telemetry'] * 4 + ['configure', 'semantic', 'catchup', 'catchup', 'checkpoint', 'backup', 'no-quorum', 'semantic', 'close'] if node == 'node-1' else common
    f.check([e['request']['command'] for e in m['exchanges']] == expected_commands, 'member command schedule')
    return m


def selected_state(root, node, plan, model):
    path = root / node
    report = runtime_format.inspect(path)
    f.check((report['base'], report['sequence'], report['committed'], report['snapshotIndex']) == (4, model['sequence'], 73, 73), 'proven final boundary')
    f.check(report['lastIndex'] == (74 if node == 'node-1' else 73), 'indeterminate tail boundary')
    g = f.genesis((path / 'genesis.gsr').read_bytes()); g['raw'] = (path / 'genesis.gsr').read_bytes()
    f.check(g['documents'] == [(struct.pack('>i', d[0]), encoded(d)) for d in model['initial']] and g['indexes'] == INDEXES, 'independent seeded genesis')
    manifest_raw = (path / 'manifest.gsr').read_bytes(); manifest = f.manifest(manifest_raw, g)
    seal = f.record((path / 'bootstrap-seal.gsr').read_bytes(), 20); seal.text(64)
    receipt = f.record(seal.blob(f.META), 19)
    descriptor, _ = f.plan(receipt.blob(f.META), manifest, g, manifest_raw)
    f.check(descriptor['application']['snapshot'] == plan['application']['snapshot'] and descriptor['application']['planner'] == 'FORCE_SCAN', 'resolved application configuration')
    for replica in descriptor['replicas']:
        f.check(replica['replicationBounds'] == plan['replicationBounds'], 'resolved replication bounds')
        mat = replica['materialization']
        f.check(mat['storageIdentity'] == plan['application']['storageIdentity'] and mat['codecId'] == plan['application']['codec'] and
                mat['codecVersion'] == plan['application']['codecVersion'] and mat['schemaIdentity'] == plan['application']['schema'], 'resolved storage identity')
        f.check(all(v == plan['application'][k] for k, v in mat['bounds'].items()), 'resolved storage bounds')
    selector = f.record((path / 'current.gsr').read_bytes(), 10); selector.take(32); selector.text(64)
    selected = path / selector.text(32)
    r = f.record((selected / 'snapshot.gsr').read_bytes(), 8, f.IMAGE); r.take(48)
    anchors = []
    for _ in range(r.count(1_000_000, 89)):
        r.take(24); op = r.number('B'); r.take(32); anchors.append((op, r.take(32).hex()))
    r.blob(f.META); app = r.blob(); r.end()
    indexes, docs = f.application(app)
    f.check(anchors == model['anchors'], 'independent operation payload ancestry')
    f.check(indexes == INDEXES and docs == [(struct.pack('>i', d[0]), encoded(d)) for d in model['documents']], 'independent final snapshot')
    return report


def validate(root, expected_plan, *, cloud=False):
    root = Path(root); expected_plan = Path(expected_plan)
    plan = read(root / 'plan.json'); validate_plan(plan)
    f.check((root / 'plan.json').read_bytes() == expected_plan.read_bytes(), 'unreviewed plan')
    psha = digest(expected_plan.read_bytes()); model = schedule(plan)
    envelope = read(root / 'set.json')
    if cloud:
        from .cloud_evidence import hosts
        hosts(root)
    execution = 'gcp-public-admission-probe-only' if cloud else plan['execution']
    schema = 'gse-v50-cloud-probe-v1' if cloud else plan['evidenceSchema']
    preset = 'v5.0-three-vm-admission-probe-v1' if cloud else plan['preset']
    f.check((envelope['schema'], envelope['execution'], envelope['preset'], envelope['protocol'], envelope['planSha256']) ==
            (schema, execution, preset, plan['protocol'], psha), 'set provenance')
    f.check(envelope['members'] == ['node-1', 'node-2', 'node-3'], 'member set')
    original = inventory(root); f.check(envelope['files'] == original, 'member inventory/checksum')
    f.check(0 < envelope['finishedNanos'] - envelope['startedNanos'] <= (5100 if cloud else plan['localSmoke']['maximumRunSeconds']) * 1_000_000_000, 'run deadline')
    metadata = read(root / 'metadata.json')
    f.check(inventory(root / 'source') == metadata['sourceBackup'], 'immutable source backup changed')
    f.check(re.fullmatch('[0-9a-f]{40}', metadata['head']) and type(metadata['dirty']) is bool and
            metadata['execution'] == execution and metadata['bootId'] and metadata['filesystem'] and metadata['maven'], 'source/host provenance')
    with zipfile.ZipFile(root / 'source-inputs.zip') as archive:
        names = archive.namelist()
        f.check(len(names) == len(set(names)) and set(names) == set(metadata['inputs']) and
                sum(i.file_size for i in archive.infolist()) <= BUNDLE_LIMIT, 'source inventory bound')
        f.check(all(not n.startswith('/') and '..' not in Path(n).parts and digest(archive.read(n)) == metadata['inputs'][n] for n in names), 'source input binding')
        f.check(archive.read('docs/v5x/v5.0/phase6-plan.json') == expected_plan.read_bytes(), 'source plan binding')
    f.check(set(metadata['jars']) == {'core', 'replication', 'control'}, 'artifact set')
    for name, jar in metadata['jars'].items():
        f.check(name in ('core', 'replication', 'control') and digest((root / 'artifacts' / (name + '.jar')).read_bytes()) == jar['sha256'], 'artifact binding')
        with zipfile.ZipFile(root / 'artifacts' / (name + '.jar')) as archive:
            f.check(not any('/admission/' in n or 'PerformanceWorker' in n for n in archive.namelist()), 'probe leaked into production artifact')
    f.check(metadata['jars']['control']['sha256'] == plan['publishedControl']['sha256'], 'loaded control artifact')
    control, restore = read(root / 'control.json'), read(root / 'restore.json')
    for value, label in ((control, 'control-measure'), (restore, 'control-restore')):
        identity(value['result']['identity'], value['process'], metadata, plan, psha, 'control')
        f.check(value['process'] == read(root / 'processes' / (label + '.json')) and
                value['result'] == read(root / 'processes' / (label + '.stdout')), 'control process binding')
    windows(control['result']['windows'], plan, model)
    members = [member(root, n, metadata, plan, psha) for n in envelope['members']]
    f.check(cloud or len({m['pid'] for m in members}) == 3, 'three distinct JVMs')
    f.check(control['process']['finishedNanos'] < min(m['startedNanos'] for m in members) and
            max(m['finishedNanos'] for m in members) < restore['process']['startedNanos'], 'control isolation')
    f.check(envelope['startedNanos'] <= control['process']['startedNanos'] and
            restore['process']['finishedNanos'] <= envelope['finishedNanos'], 'set lifetime binding')
    leader = members[0]
    exchanges = leader['exchanges']
    measured = [e for e in exchanges if e['request']['command'] == 'measure']
    f.check(max(m['readyNanos'] for m in members) < measured[0]['sentNanos'] and
            measured[-1]['receivedNanos'] < min(m['finishedNanos'] for m in members), 'three-voter healthy overlap')
    candidate = [e['response']['measurement'] for e in measured]; windows(candidate, plan, model)
    for e in measured:
        w, request = e['response']['measurement'], e['request']
        f.check(request['window'] == w['window'] and request['firstCycle'] == w['rows'][0]['cycle'] and
                request['cycles'] * len(OPERATIONS) == len(w['rows']), 'measurement request binding')
        f.check(e['response']['startNanos'] <= w['startNanos'] < w['endNanos'] <= e['response']['endNanos'] and
                e['response']['status']['sequence'] == w['rows'][-1]['afterSequence'], 'measurement publication')
    for m in members:
        observations = [e['response']['telemetry'] for e in m['exchanges'] if e['request']['command'] == 'telemetry']
        configurations = [e for e in m['exchanges'] if e['request']['command'] == 'configure']
        captures = [e for e in m['exchanges'] if e['request']['command'] == 'telemetry']
        f.check([o['window'] for o in observations] == plan['localSmoke']['windows'], 'telemetry coverage')
        for o, w, configured, captured in zip(observations, candidate[1:], configurations, captures):
            enabled = o['window'].startswith('instrumented')
            f.check(configured['request'] == dict(command='configure', window=o['window'], enabled=enabled), 'telemetry configuration')
            start, end = configured['response']['startNanos'], captured['response']['endNanos']
            f.check(all(start <= v['startNanos'] < v['endNanos'] <= end for v in o['forces']) and
                    all(start <= v['nanos'] <= end for v in o['events']), 'member observation window')
            f.check(o['enabled'] is enabled and len(o['forces']) <= 4096 and len(o['events']) <= 4096 and
                    0 <= o['wireAttempts'] <= 4096 and 0 <= o['encodedAttemptBytes'] <= 8 << 20, 'telemetry bounds')
            if not enabled:
                f.check(not o['forces'] and not o['events'] and o['wireAttempts'] == o['encodedAttemptBytes'] == 0, 'disabled telemetry')
            else:
                for force in o['forces']: duration(force)
                f.check(o['wireAttempts'] > 0 and o['encodedAttemptBytes'] > 0, 'missing wire observations')
                if m is leader:
                    mutating = [r for r in w['rows'] if r['operation'] in OP_IDS]
                    f.check(len(o['forces']) == 2 * len(mutating), 'missing force samples')
                    for row in mutating:
                        index = row['afterSequence'] - 4 + 1
                        stages = [e for e in o['events'] if e['index'] == index and e['event'] in STAGES]
                        f.check([e['event'] for e in stages] == list(STAGES) and
                                row['startNanos'] <= min(e['nanos'] for e in stages) and max(e['nanos'] for e in stages) <= row['endNanos'] and
                                [e['nanos'] for e in stages] == sorted(e['nanos'] for e in stages), 'success before quorum/publication')
                        forces = [v for v in o['forces'] if row['startNanos'] <= v['startNanos'] < v['endNanos'] <= row['endNanos']]
                        f.check([v['kind'] for v in forces] == ['ENTRY', 'PROOF'], 'force-to-call timing')
    semantics = [e['response']['semantic'] for e in exchanges if e['request']['command'] == 'semantic']
    expected_semantic = control['result']['semantic']
    f.check(len(semantics) == 2 and semantics == [expected_semantic] * 2 and restore['result']['semantic'] == expected_semantic, 'V4 exported/committed semantic equality')
    f.check(expected_semantic['sequence'] == model['sequence'] and expected_semantic['report']['documents'] == [display(d) for d in model['documents']], 'independent application equality')
    failures = [e['response'] for e in exchanges if e['request']['command'] == 'no-quorum']
    fault = next(e for e in exchanges if e['request']['command'] == 'no-quorum')
    f.check(max(m['finishedNanos'] for m in members[1:]) < fault['sentNanos'], 'fault member shutdown')
    f.check(len(failures) == 1 and failures[0]['reason'] == 'QUORUM_UNAVAILABLE' and
            failures[0]['status']['sequence'] == model['sequence'] and failures[0]['status']['commitIndex'] == 73, 'no-quorum classification')
    reports = [selected_state(root, n, plan, model) for n in envelope['members']]
    f.check(all(r['manifest'] == reports[0]['manifest'] and r['anchors'][:73] == reports[0]['anchors'][:73] for r in reports), 'conflicting topology history')
    f.check(read(root / 'measurements.json') == summary(candidate, control['result']['windows']), 'forged measurement aggregate')
    f.check(inventory(root) == original, 'validator modified evidence')
    return dict(status='PASS', execution=execution, nodes=3, applicationSequence=model['sequence'],
                committedThrough=73, measuredRequests=80, durableSuccess=64, noQuorumIndeterminate=1,
                sourceHead=metadata['head'], sourceDirty=metadata['dirty'], planSha256=psha)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path); parser.add_argument('--plan', required=True, type=Path)
    args = parser.parse_args(); print(json.dumps(validate(args.evidence, args.plan), sort_keys=True))
