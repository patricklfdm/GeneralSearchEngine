"""Bounded local public performance probe. Owns only the processes it starts."""
import argparse
import json
import os
from pathlib import Path
import platform
import select
import shutil
import signal
import subprocess
import time
import zipfile
from .admission_format import check
from .leader_harness import ports
from .offline_harness import ROOT, CORE, REPLICATION, PACKAGE, save
from .performance_model import digest, summary
from .performance_evidence import inventory, validate, validate_plan

PLAN = ROOT / 'docs/v5x/v5.0/phase6-plan.json'


def now():
    return time.monotonic_ns()


class Run:
    def __init__(self, root, plan):
        self.root, self.plan = root, plan
        self.start = now()
        self.deadline = self.start + (plan['localSmoke']['maximumRunSeconds'] - plan['localSmoke']['cleanupReserveSeconds']) * 1_000_000_000
        self.workers = []

    def remaining(self, maximum=40):
        seconds = min(maximum, (self.deadline - now()) / 1e9)
        check(seconds > 0, 'local run deadline')
        return seconds

    def process(self, label, args, parsed=False):
        prefix = self.root / 'processes' / label
        prefix.parent.mkdir(parents=True, exist_ok=True)
        started = now()
        with prefix.with_suffix('.stdout').open('wb') as stdout, prefix.with_suffix('.stderr').open('wb') as stderr:
            proc = subprocess.Popen(list(map(str, args)), cwd=ROOT, stdout=stdout, stderr=stderr)
            try:
                proc.wait(timeout=self.remaining())
            finally:
                if proc.poll() is None:
                    proc.kill(); proc.wait(timeout=5)
                receipt = dict(pid=proc.pid, args=list(map(str, args)), startedNanos=started, finishedNanos=now(), exitCode=proc.returncode)
                save(prefix.with_suffix('.json'), receipt)
        check(proc.returncode == 0, label + ': ' + prefix.with_suffix('.stderr').read_text()[-8000:])
        raw = prefix.with_suffix('.stdout').read_bytes()
        check(len(raw) <= self.plan['evidenceBounds']['maxResponseBytes'], 'process output bound')
        return dict(process=receipt, result=json.loads(raw)) if parsed else raw.decode()


class Worker:
    def __init__(self, run, ordinal, args):
        self.run, self.ordinal = run, ordinal
        self.path = run.root / 'members' / f'node-{ordinal}.json'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stderr = self.path.with_suffix('.stderr').open('wb')
        self.receipt = dict(schema='gse-v50-performance-member-v1', node=f'node-{ordinal}', args=args,
                            startedNanos=now(), exchanges=[])
        self.buffer = b''
        self.process = subprocess.Popen(args, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr)
        run.workers.append(self)  # Cleanup owns it even if startup/identity validation fails.
        self.receipt['pid'] = self.process.pid
        self.receipt['linuxStartTicks'] = Path(f'/proc/{self.process.pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
        save(self.path, self.receipt)
        self.receipt['ready'] = self.receive()
        self.receipt['readyNanos'] = now()
        check(self.receipt['ready']['identity']['pid'] == self.process.pid, 'ready process identity')
        save(self.path, self.receipt)

    def receive(self):
        deadline = now() + int(self.run.remaining(30) * 1e9)
        while b'\n' not in self.buffer:
            wait = (deadline - now()) / 1e9
            check(wait > 0 and select.select([self.process.stdout], [], [], max(0, wait))[0], 'worker response timeout')
            chunk = os.read(self.process.stdout.fileno(), 65536)
            check(chunk, 'worker exited: ' + self.path.with_suffix('.stderr').read_text()[-8000:])
            self.buffer += chunk
            check(len(self.buffer) <= self.run.plan['evidenceBounds']['maxResponseBytes'], 'worker response bound')
        line, self.buffer = self.buffer.split(b'\n', 1)
        return json.loads(line)

    def command(self, name, accepted=True, **values):
        request = dict(command=name, **values)
        exchange = dict(sentNanos=now(), request=request)
        self.receipt['exchanges'].append(exchange); save(self.path, self.receipt)
        self.process.stdin.write(json.dumps(request).encode() + b'\n'); self.process.stdin.flush()
        result = self.receive()
        exchange.update(receivedNanos=now(), response=result); save(self.path, self.receipt)
        check(result['command'] == name and result['accepted'] == accepted, 'command failed: ' + json.dumps(result))
        return result

    def close(self, failed=False):
        if 'finishedNanos' in self.receipt:
            return
        try:
            if self.process.poll() is None and not failed:
                self.command('close')
            if self.process.poll() is None and failed:
                self.process.kill()
            self.process.wait(timeout=5)
        finally:
            if self.process.poll() is None:
                self.process.kill(); self.process.wait(timeout=5)
            self.receipt.update(finishedNanos=now(), exitCode=self.process.returncode, cleanup='reaped', forced=failed)
            save(self.path, self.receipt)
            self.stderr.close(); self.process.stdin.close(); self.process.stdout.close()
        if not failed:
            check(self.process.returncode == 0, 'worker close failed')


def source_inputs():
    paths = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode().split('\0')
    return {p: digest((ROOT / p).read_bytes()) for p in sorted(set(paths)) if p and (ROOT / p).is_file() and
            (p.startswith(('src/', 'general-search-engine-replication/src/', 'scripts/', '.github/workflows/', '.mvn/'))
             or p.endswith('pom.xml') or p in ('mvnw', 'docs/v5x/v5.0/phase6-plan.json'))}


def run(root, control, *, volume_layout=False, java_executable='java'):
    root = root.resolve(); control = control.resolve()
    check(not root.exists(), 'fresh evidence directory required'); root.mkdir(parents=True)
    raw_plan = PLAN.read_bytes(); plan = json.loads(raw_plan); validate_plan(plan)
    (root / 'plan.json').write_bytes(raw_plan)
    run = Run(root, plan)
    success = False
    try:
        check(digest(control.read_bytes()) == plan['publishedControl']['sha256'], 'published control checksum')
        inputs = source_inputs()
        with zipfile.ZipFile(root / 'source-inputs.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
            for name in inputs:
                archive.write(ROOT / name, name)
        artifacts = root / 'artifacts'; artifacts.mkdir()
        jars = {}
        for name, path in [('core', CORE), ('replication', REPLICATION), ('control', control)]:
            target = artifacts / (name + '.jar'); shutil.copyfile(path, target)
            jars[name] = dict(path=str(target), sha256=digest(target.read_bytes()))
        metadata = dict(head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                        dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)), inputs=inputs,
                        jars=jars, platform=platform.platform(), bootId=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                        machineId='local-owned-processes', execution='local-public-runtime-only',
                        javaExecutable=java_executable, volumeLayout=volume_layout,
                        filesystem=run.process('filesystem', ['findmnt', '-J', '-T', str(root), '-o', 'TARGET,SOURCE,FSTYPE,OPTIONS,SIZE']),
                        java=run.process('java-version', ['java', '--version']),
                        javac=run.process('javac-version', ['javac', '--version']),
                        maven=run.process('maven-version', [str(ROOT / 'mvnw'), '--version']))
        save(root / 'metadata.json', metadata)
        sources = ROOT / 'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch'
        common = [sources / 'admission' / (n + '.java') for n in ('AdmissionJson', 'AdmissionSemanticModel', 'PerformanceTelemetry', 'PerformanceWorkload')]
        candidate = root / 'classes-candidate'; candidate.mkdir()
        oracle = root / 'classes-control'; oracle.mkdir()
        cp = os.pathsep.join(jars[n]['path'] for n in ('core', 'replication'))
        run.process('compile-public', ['javac', '--release', '21', '-cp', cp, '-d', candidate, *common, sources / 'admission/V50PerformanceConsumer.java'])
        cp += os.pathsep + str(candidate)
        run.process('compile-observer', ['javac', '--release', '21', '-cp', cp, '-d', candidate, sources / 'replication/V50PerformanceWorker.java'])
        run.process('compile-control', ['javac', '--release', '21', '-cp', jars['control']['path'], '-d', oracle, *common, sources / 'admission/V50PerformanceControl.java'])
        control_cp = jars['control']['path'] + os.pathsep + str(oracle)
        java = [java_executable, *plan['jvmArguments']]
        control_args = [*java, '-cp', control_cp, PACKAGE + 'admission.V50PerformanceControl']
        control_result = run.process('control-measure', [*control_args, 'measure', root, root / 'plan.json'], True)
        save(root / 'control.json', control_result)
        metadata['sourceBackup'] = inventory(root / 'source')
        save(root / 'metadata.json', metadata)
        endpoints = ','.join(map(str, ports()))
        if volume_layout:
            endpoints = ','.join('127.0.0.1:' + p for p in endpoints.split(','))
            for i in range(1, 4): (root / ('volume-' + str(i))).mkdir()
        def args(i):
            return [str(root), str(i), endpoints, str(root / 'plan.json')] + (['volumes'] if volume_layout else [])
        run.process('bootstrap', [*java, '-cp', cp, PACKAGE + 'admission.V50PerformanceConsumer', *args(0)], True)
        for i in range(1, 4):
            Worker(run, i, [*java, '-cp', cp, PACKAGE + 'replication.V50PerformanceWorker', *args(i)])
        leader, second, third = run.workers
        leader.command('activate')
        windows = [leader.command('measure', window='warmup', firstCycle=0, cycles=plan['localSmoke']['warmupCycles'])['measurement']]
        cycle = plan['localSmoke']['warmupCycles']
        for name in plan['localSmoke']['windows']:
            for worker in run.workers:
                worker.command('configure', window=name, enabled=name.startswith('instrumented'))
            windows.append(leader.command('measure', window=name, firstCycle=cycle, cycles=plan['localSmoke']['cyclesPerWindow'])['measurement'])
            for worker in run.workers:
                worker.command('telemetry')
            cycle += plan['localSmoke']['cyclesPerWindow']
        for worker in run.workers:
            worker.command('configure', window='disabled', enabled=False)
        semantic = leader.command('semantic')['semantic']
        for peer in ('node-2', 'node-3'):
            leader.command('catchup', peer=peer)
        for worker in run.workers:
            worker.command('checkpoint')
        leader.command('backup')
        second.close(); third.close()
        leader.command('no-quorum', accepted=False)
        check(leader.command('semantic')['semantic'] == semantic, 'failed write changed committed reads')
        leader.close()
        if volume_layout:
            # Inspect a quiescent copy at the conventional evidence path; sealed
            # provenance retains the actual bootstrap/attach directory bindings.
            for i in range(1, 4): shutil.copytree(root / ('volume-' + str(i)) / ('node-' + str(i)), root / ('node-' + str(i)))
        restored = run.process('control-restore', [*control_args, 'restore', root, root / 'plan.json'], True)
        save(root / 'restore.json', restored)
        check(inventory(root / 'source') == metadata['sourceBackup'], 'immutable source backup changed')
        check(source_inputs() == inputs, 'source inputs changed during probe')
        save(root / 'measurements.json', summary(windows, control_result['result']['windows']))
        save(root / 'set.json', dict(schema='gse-v50-performance-evidence-v1', execution='local-public-runtime-only',
                                    preset=plan['preset'], protocol=plan['protocol'], planSha256=digest(raw_plan),
                                    startedNanos=run.start, finishedNanos=now(), members=['node-1', 'node-2', 'node-3'],
                                    files=inventory(root)))
        result = validate(root, PLAN)
        save(root.parent / (root.name + '-validation.json'), result)
        print(json.dumps(result, sort_keys=True), flush=True)
        success = True
    finally:
        cleanup_errors = []
        for worker in run.workers:
            try:
                worker.close(failed=not success)
            except Exception as error:
                cleanup_errors.append(str(error))
        if not success:
            save(root / 'failure.json', dict(status='FAIL', cleanup=[w.receipt for w in run.workers],
                                            cleanupErrors=cleanup_errors, finishedNanos=now()))
        check(not cleanup_errors, 'owned cleanup failed: ' + '; '.join(cleanup_errors))


if __name__ == '__main__':
    def interrupted(signum, frame):
        raise RuntimeError('local probe interrupted: ' + str(signum))
    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path); parser.add_argument('--control-jar', required=True, type=Path)
    parser.add_argument('--volume-layout', action='store_true'); parser.add_argument('--java', default='java')
    args = parser.parse_args(); run(args.workspace, args.control_jar, volume_layout=args.volume_layout, java_executable=args.java)
