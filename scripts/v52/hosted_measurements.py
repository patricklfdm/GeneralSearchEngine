"""Branch-only hosted M01-M04 driver. No paid cloud, workload retries or resume."""
import argparse
from contextlib import AbstractContextManager
import json
import os
from pathlib import Path
import shutil
import threading
import time
from . import hosted_measurement_contract as c
from . import measurement_machine as machine, measurement_runtime as runtime, measurement_bundle as bundle
from . import measurement_m01 as m01, measurement_m01_evidence as m01_evidence
from . import measurement_minimum as minimum, measurement_minimum_evidence as minimum_evidence
from . import measurement_recovery as recovery, measurement_recovery_evidence as recovery_evidence
from . import measurement_identity as identity
from .evidence import need, encoded

ROOT = c.ROOT


def read(path):
    path = Path(path)
    return identity.metadata(path.parent, path.name, 16 << 20, label='hosted')


def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_bytes(encoded(value) + b'\n'); temporary.replace(path)


class Progress(AbstractContextManager):
    """A quiet long replay still emits elapsed time, phase and free space every minute."""
    def __init__(self, root, interval=60):
        self.root, self.interval = Path(root), interval
        self.started = self.phase_started = time.monotonic()
        self.state = dict(stage='starting', member=None, completed=0)
        self.stop = threading.Event(); self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.heartbeat, daemon=True)

    def emit(self):
        with self.lock:
            value = dict(self.state, elapsedSeconds=round(time.monotonic()-self.started, 1),
                         phaseSeconds=round(time.monotonic()-self.phase_started, 1),
                         freeGiB=round(shutil.disk_usage(self.root).free/(1 << 30), 2), pid=os.getpid())
            save(self.root/'progress.json', value)
            print(json.dumps(value, sort_keys=True), flush=True)

    def stage(self, stage, member=None, completed=0):
        with self.lock:
            self.state = dict(stage=stage, member=member, completed=completed)
            self.phase_started = time.monotonic()
        self.emit()

    def heartbeat(self):
        while not self.stop.wait(self.interval):
            self.emit()

    def __enter__(self):
        self.emit(); self.thread.start(); return self

    def __exit__(self, kind, value, tb):
        self.stop.set(); self.thread.join()
        self.stage('FAILED' if kind else 'finished', completed=self.state['completed'])


def source():
    actual = machine.clean_source(ROOT)
    need(actual['source'] == os.environ['GITHUB_SHA'], 'hosted checkout differs from event')
    return actual


def load_plan(build):
    plan, manifest = read(build/'plan.json'), read(build/'manifest.json')
    c.validate_plan(plan, source(), c.context(), manifest)
    need(bundle.sha_file(build/'build.tar.gz') == plan['buildArchiveSha256'], 'hosted build archive drift')
    return plan


def current_environment(root):
    env = machine.environment(root)
    # Keep image metadata as observations, not a cross-runner equality assertion.
    env['runner'] = {key: os.environ.get(key) for key in ('RUNNER_NAME', 'RUNNER_OS', 'RUNNER_ARCH', 'ImageOS', 'ImageVersion')}
    return env


def prepare_plan(build, output, progress):
    actual, run = source(), c.context()
    manifest = read(build/'manifest.json')
    need(manifest['schema'] == machine.build.SCHEMA and manifest['binding'] == actual and
         bundle.sha_file(build/'build.tar.gz') == manifest['archiveSha256'], 'hosted missing current build')
    files = {v['path']: v for v in manifest['files']}
    for path in machine.build.layout(ROOT)[:2]:
        need(bundle.sha_file(ROOT/path) == files[path]['sha256'], 'hosted current JAR differs from bundle')
    compiled = {}
    for family, mode in [('published', 'published-v51-legacy-strong'), ('candidate', 'candidate-minimum')]:
        progress.stage('compile-frozen-consumer', family)
        binding, _, _ = runtime.prepare(output/family, mode, m01_repetition=1)
        need({k: binding[k] for k in actual} == actual and {k: binding[k] for k in run} == run,
             'hosted source/attempt changed during preparation')
        compiled[family] = {k: binding[k] for k in ('artifacts', 'classes')}
    plan = dict(schema=c.SCHEMA, status='FROZEN_BEFORE_MEASUREMENTS', paidCloud=False, binding=actual,
                identity=run, contract=c.contract(), compiled=compiled, buildManifestSha256=c.hash_value(manifest),
                buildArchiveSha256=manifest['archiveSha256'])
    c.validate_plan(plan, source(), c.context(), manifest)
    need(not (build/'plan.json').exists(), 'hosted plan already exists')
    controls = build/'published-controls'; controls.mkdir()
    for name in compiled['published']['artifacts']:
        shutil.copyfile(ROOT/'target/v52-controls'/name, controls/name)
    save(build/'plan.json', plan)
    return dict(status='PREPARED', qualifiedMeasurement=False, paidCloud=False, planSha256=c.hash_value(plan))


def prepare_member(case, name, spec):
    if spec['family'] == 'M01':
        binding, cp, _ = runtime.prepare(case, spec['mode'], m01_repetition=spec['profile']['repetition']); owner = m01
    elif spec['family'] in ('M02', 'M03'):
        binding, cp, _ = minimum.prepare(case, name); owner = minimum
    else:
        binding, cp, _ = recovery.prepare(case, name); owner = recovery
    return binding, cp, owner


def replay(case, binding, spec, output):
    validator = {'M01': m01_evidence, 'M02': minimum_evidence, 'M03': minimum_evidence, 'M04': recovery_evidence}[spec['family']]
    return validator.replay(case, binding, output)


def member_identity(case):
    raw = (case/'node-1/manifest.gsr').read_bytes()
    manifest = m01_evidence.physical.f.inspect(raw, 'MANIFEST')
    return dict(domain={k: manifest[k] for k in ('groupId', 'historyId')}, manifestSha256=c.digest(raw))


def check_original(plan, name, result):
    family = plan['contract']['members'][name]['family']
    prefix = {'M01': 'm01', 'M02': 'minimum', 'M03': 'minimum', 'M04': 'recovery'}[family]
    need(result['status'] == 'PASS' and result['execution'] == prefix+'-member-physical-replay' and
         result['qualifiedMeasurement'] is False and result['paidCloud'] is False and
         result['negatives'] == plan['contract']['negativeRules'][name], 'hosted original replay/negatives')
    return prefix


def check_machine(plan, freeze, output):
    need(source() == plan['binding'] and c.context() == plan['identity'], 'hosted live source/attempt drift')
    need(current_environment(output) == freeze['environment'], 'hosted runner changed during shard')


def prime_controls(build, plan):
    destination = ROOT/'target/v52-controls'; destination.mkdir(parents=True, exist_ok=True)
    for name, sha in plan['compiled']['published']['artifacts'].items():
        path = build/'published-controls'/name
        need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 64 << 20 and
             bundle.sha_file(path) == sha, 'hosted published control changed')
        target = destination/name
        need(not target.exists() and not target.is_symlink(), 'hosted existing published control')
        shutil.copyfile(path, target)


def run_shard(build, output, shard, progress):
    plan = load_plan(build)
    prime_controls(build, plan)
    need(shard in c.shards(), 'hosted unknown shard')
    freeze = dict(schema=c.SCHEMA, status='FROZEN_BEFORE_MEASUREMENTS', paidCloud=False, shard=shard,
                  identity=plan['identity'], binding=plan['binding'], planSha256=c.hash_value(plan),
                  environment=current_environment(output), storageRoot=str(output), createdUnixNs=time.time_ns())
    c.validate_freeze(plan, freeze, shard); save(output/'frozen-runner.json', freeze)
    record = dict(schema=c.SCHEMA, kind='execution', status='RUNNING', paidCloud=False, qualifiedMeasurement=False,
                  shard=shard, planSha256=c.hash_value(plan), freezeSha256=c.hash_value(freeze),
                  identity=plan['identity'], members={})
    save(output/'receipt.json', record)
    try:
        for name in c.shards()[shard]:
            spec = plan['contract']['members'][name]; case = output/'histories'/name
            check_machine(plan, freeze, output)
            need(shutil.disk_usage(output).free >= machine.MINIMUM_FREE_BYTES, 'hosted insufficient free storage before history')
            progress.stage('preparation', name, len(record['members']))
            started = time.time_ns()
            binding, cp, owner = prepare_member(case, name, spec)
            c.check_binding(plan, freeze, name, binding)
            progress.stage('original-workload', name, len(record['members']))
            owner.execute_prepared(case, binding, cp)
            check_machine(plan, freeze, output)
            runtime.save(case/bundle.INDEX, bundle.members(case))
            progress.stage('original-physical-replay', name, len(record['members']))
            result = replay(case, binding, spec, output/'original-validation'/name)
            check_original(plan, name, result)
            progress.stage('pack-history', name, len(record['members']))
            archive = output/'packages'/(name+'.tar.gz'); archive.parent.mkdir(exist_ok=True)
            index = bundle.pack(case, archive)
            record['members'][name] = dict(binding=binding, result=result, startedUnixNs=started,
                finishedUnixNs=time.time_ns(), archiveSha256=bundle.sha_file(archive), archiveBytes=archive.stat().st_size,
                inventorySha256=c.hash_value(index), **member_identity(case))
            check_machine(plan, freeze, output)
            save(output/'receipt.json', record)
            # Only stopped, successfully replayed bytes already in an immutable
            # full archive are removed. Failed raw histories are retained.
            shutil.rmtree(case)
            progress.stage('history-complete', name, len(record['members']))
        record['status'] = 'PARTIAL'
        return record
    except BaseException as error:
        record.update(status='FAIL', failure=dict(type=type(error).__name__, message=str(error))); raise
    finally:
        save(output/'receipt.json', record)


def validate_input(plan, input_root, shard):
    freeze, receipt = read(input_root/'frozen-runner.json'), read(input_root/'receipt.json')
    c.validate_freeze(plan, freeze, shard)
    need(receipt['schema'] == c.SCHEMA and receipt['kind'] == 'execution' and receipt['status'] == 'PARTIAL' and
         receipt['qualifiedMeasurement'] is False and receipt['paidCloud'] is False and receipt['shard'] == shard and
         receipt['planSha256'] == c.hash_value(plan) and receipt['freezeSha256'] == c.hash_value(freeze) and
         receipt['identity'] == plan['identity'], 'hosted producer receipt identity/completion')
    need(set(receipt['members']) == set(c.shards()[shard]), 'hosted missing/extra shard history')
    need({p.name for p in (input_root/'packages').iterdir()} == {n+'.tar.gz' for n in c.shards()[shard]},
         'hosted missing/extra archive')
    for name, member in receipt['members'].items():
        c.check_binding(plan, freeze, name, member['binding'])
        need(type(member['startedUnixNs']) is int and type(member['finishedUnixNs']) is int and
             freeze['createdUnixNs'] <= member['startedUnixNs'] < member['finishedUnixNs'], 'hosted history before freeze')
        path = input_root/'packages'/(name+'.tar.gz')
        need(not path.is_symlink() and path.is_file() and 0 < path.stat().st_size <= bundle.LIMITS['compressed'] and
             path.stat().st_size == member['archiveBytes'] and bundle.sha_file(path) == member['archiveSha256'],
             'hosted archive changed')
        check_original(plan, name, member['result'])
    return freeze, receipt


def verify_shard(build, inputs, output, shard, progress):
    plan = load_plan(build); freeze, producer = validate_input(plan, inputs, shard)
    record = dict(schema=c.SCHEMA, kind='independent-replay', status='RUNNING', paidCloud=False, qualifiedMeasurement=False,
                  identity=plan['identity'], planSha256=c.hash_value(plan), shard=shard, freeze=freeze,
                  producerReceiptSha256=c.hash_value(producer), members={})
    save(output/'receipt.json', record)
    try:
        for name in c.shards()[shard]:
            member = producer['members'][name]; binding = member['binding']; spec = plan['contract']['members'][name]
            need(shutil.disk_usage(output).free >= machine.MINIMUM_FREE_BYTES, 'hosted insufficient free storage before replay')
            progress.stage('unpack-retained-history', name, len(record['members']))
            case = bundle.unpack(inputs/'packages'/(name+'.tar.gz'), output/'downloaded'/name)
            need(c.hash_value(bundle.inventory(case)) == member['inventorySha256'], 'hosted downloaded inventory changed')
            need(member_identity(case) == {k: member[k] for k in ('domain', 'manifestSha256')}, 'hosted downloaded domain changed')
            progress.stage('independent-physical-replay', name, len(record['members']))
            result = replay(case, binding, spec, output/'validation'/name)
            prefix = check_original(plan, name, result)
            need(result == member['result'], 'hosted original/downloaded replay drift')
            need(c.hash_value(bundle.inventory(case)) == member['inventorySha256'], 'hosted history changed during replay')
            record['members'][name] = dict(status='PASS', execution=prefix+'-portable-member', qualifiedMeasurement=False,
                paidCloud=False, binding=binding, result=result,
                **{k: member[k] for k in ('domain', 'manifestSha256', 'inventorySha256', 'archiveSha256', 'archiveBytes')})
            save(output/'receipt.json', record)
            shutil.rmtree(case)  # The producer artifact retains the complete immutable archive.
            progress.stage('history-verified', name, len(record['members']))
        need(source() == plan['binding'], 'hosted verifier source changed')
        record['status'] = 'PARTIAL'
        return record
    except BaseException as error:
        record.update(status='FAIL', failure=dict(type=type(error).__name__, message=str(error))); raise
    finally:
        save(output/'receipt.json', record)


def aggregate_records(plan, records):
    need(set(records) == set(c.shards()), 'hosted incomplete verifier set')
    results, expected, machines = {}, {}, {}
    boots = set()
    for shard in c.shards():
        value = records[shard]
        need(value['schema'] == c.SCHEMA and value['kind'] == 'independent-replay' and value['status'] == 'PARTIAL' and
             value['qualifiedMeasurement'] is False and value['paidCloud'] is False and value['shard'] == shard and
             value['identity'] == plan['identity'] and value['planSha256'] == c.hash_value(plan) and
             c.sha(value['producerReceiptSha256']), 'hosted verifier source/attempt/status')
        freeze = c.validate_freeze(plan, value['freeze'], shard)
        boot = freeze['environment']['bootId']
        need(boot not in boots, 'hosted reused runner'); boots.add(boot)
        need(set(value['members']) == set(c.shards()[shard]), 'hosted verifier incomplete shard')
        machines[shard] = freeze
        for name, result in value['members'].items():
            binding = result['binding']; c.check_binding(plan, freeze, name, binding)
            need(all(c.sha(result[k]) for k in ('inventorySha256', 'archiveSha256', 'manifestSha256')) and
                 type(result['archiveBytes']) is int and 0 < result['archiveBytes'] <= bundle.LIMITS['compressed'],
                 'hosted verifier archive identity')
            expected[name] = binding; results[name] = result
    result = c.validate_results(plan, expected, results)
    result['runners'] = machines
    result['verificationReceipts'] = {key: c.hash_value(value) for key, value in records.items()}
    return result


def aggregate(build, inputs, output, progress):
    need(os.environ.get('MEASURE_RESULT') == 'success' and os.environ.get('VERIFY_RESULT') == 'success',
         'hosted execution/replay jobs incomplete or failed')
    plan = load_plan(build)
    # Only the six separately uploaded verifier artifacts of this run/attempt
    # are accepted, never producer PASS files or another workflow's receipts.
    directories = {shard: 'v52-hosted-verified-' + plan['identity']['run'] + '-' + str(plan['identity']['attempt']) + '-' + plan['binding']['source'] + '-' + shard for shard in c.shards()}
    need({p.name for p in inputs.iterdir()} == set(directories.values()), 'hosted aggregate input directories')
    progress.stage('complete-set-cross-check')
    records = {shard: read(inputs/directory/'receipt.json') for shard, directory in directories.items()}
    result = aggregate_records(plan, records)
    progress.stage('aggregate-complete', completed=result['histories'])
    return result


def write_summary(output, result, action, shard):
    lines = ['# V5.2 hosted measurements', '', f'- Stage: `{action}` / `{shard or "all"}`',
             f'- Result: **{result.get("status", "FAIL")}**',
             f'- Commit: `{os.environ.get("GITHUB_SHA", "unknown")}`',
             f'- Run / attempt: `{os.environ.get("GITHUB_RUN_ID", "?")}` / `{os.environ.get("GITHUB_RUN_ATTEMPT", "?")}`',
             '- Scope: 28 whole histories, 6 runner groups, no GCP; this is not protected full CI.',
             '- Frozen M01 windows: 60 s warmup + 120 s measurement; 15 histories = 2700 s offered time.',
             '- Expected original calls: 27373 reads + 2745 updates; 439 negatives at each location.',
             '- No automatic workload retry. Missing or mixed attempts cannot qualify.', '']
    if result.get('failure'):
        lines += ['## Failure', '', '```json', json.dumps(result['failure'], ensure_ascii=False), '```', '']
    members = result.get('members', {})
    if members:
        lines += ['| History | State | Archive bytes |', '| --- | --- | ---: |']
        for name, value in members.items():
            lines.append(f'| {name} | {value.get("status", "original replay complete")} | {value.get("archiveBytes", 0)} |')
    text = '\n'.join(lines)+'\n'; (output/'summary.md').write_text(text)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream: stream.write(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'run', 'verify', 'aggregate'])
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--inputs', type=Path)
    parser.add_argument('--shard', choices=list(c.shards()))
    args = parser.parse_args()
    # Fresh directory is mandatory. A failed invocation cannot overwrite its evidence.
    output = args.output.resolve()
    for path in (args.build, args.inputs):
        if path is not None:
            path = path.resolve()
            need(output != path and output not in path.parents and path not in output.parents, 'hosted output overlaps inputs')
    output.mkdir(parents=True, exist_ok=False)
    result = dict(status='FAIL', qualifiedMeasurement=False, paidCloud=False)
    try:
        c.context()
        need((args.shard is not None) == (args.action in ('run', 'verify')), 'hosted shard argument')
        need((args.inputs is not None) == (args.action in ('verify', 'aggregate')), 'hosted inputs argument')
        with Progress(output) as progress:
            if args.action == 'prepare': result = prepare_plan(args.build, output, progress)
            elif args.action == 'run': result = run_shard(args.build, output, args.shard, progress)
            elif args.action == 'verify': result = verify_shard(args.build, args.inputs, output, args.shard, progress)
            else: result = aggregate(args.build, args.inputs, output, progress)
    except BaseException as error:
        result['failure'] = dict(type=type(error).__name__, message=str(error)); raise
    finally:
        # Do not overwrite the detailed incremental receipt on failure.
        save(output/'result.json', result); write_summary(output, result, args.action, args.shard)


if __name__ == '__main__':
    main()
