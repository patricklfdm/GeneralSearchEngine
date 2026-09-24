"""Owned, deadline-bounded local processes for the frozen Phase 6A program."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import select
import signal
import shutil
import tempfile
import socket
import subprocess
import sys
import time
import uuid
import zipfile
from . import performance_plan as plan, performance_model as model, performance_semantics as semantics
from .storage_inspector import inventory
from scripts.v50.offline_harness import CORE, REPLICATION

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'io.github.patricklfdm.generalsearch.'
need = model.need


def save(path, value):
    Path(path).write_bytes(model.canonical(value) + b'\n')


class Run:
    def __init__(self, root, admitted):
        self.root, self.plan = root, admitted
        self.started = time.monotonic_ns()
        self.work_deadline = self.started + 840_000_000_000
        self.deadline = self.work_deadline
        self.workers, self.stages = [], []

    def remaining(self, ceiling=30):
        remaining = min(ceiling, (self.deadline - time.monotonic_ns()) / 1e9)
        need(remaining > 0, 'performance stage deadline')
        return remaining

    @contextmanager
    def stage(self, name):
        record = dict(name=name, startNanos=time.monotonic_ns(), status='FAIL')
        self.stages.append(record)
        save(self.root / 'stages.json', self.stages)
        seconds = next(s['seconds'] for s in self.plan['budgets']['stages'] if s['name'] == name)
        self.deadline = min(self.work_deadline, record['startNanos'] + seconds * 1_000_000_000)
        try:
            yield
            self.remaining()
            record['status'] = 'PASS'
        finally:
            record['endNanos'] = time.monotonic_ns()
            save(self.root / 'stages.json', self.stages)

    def process(self, args, label, directory=None):
        directory = directory or self.root
        prefix = directory / label
        args = list(map(str, args))
        record = dict(args=args, startNanos=time.monotonic_ns())
        with prefix.with_suffix('.stdout').open('xb') as out, prefix.with_suffix('.stderr').open('xb') as err:
            proc = subprocess.Popen(args, cwd=ROOT, stdout=out, stderr=err)
            record['pid'] = proc.pid
            try:
                proc.wait(timeout=self.remaining(90))
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=5)
                record.update(exitCode=proc.returncode, endNanos=time.monotonic_ns())
                save(prefix.with_suffix('.json'), record)
        need(proc.returncode == 0, label + ': ' + prefix.with_suffix('.stderr').read_text()[-5000:])
        need(max(prefix.with_suffix(ext).stat().st_size for ext in ('.stdout', '.stderr')) <= 4 << 20, 'process diagnostic bound')
        return prefix.with_suffix('.stdout').read_bytes()

    def java(self, cp, main, *args):
        return ['java', *self.plan['jvmArguments'], '-cp', cp, PACKAGE + main, *map(str, args)]


class Worker:
    def __init__(self, run, root, node, args):
        self.run, self.root, self.node, self.buffer = run, root, node, b''
        self.path = root / (node + '-process.json')
        self.record = dict(node=node, args=args, startNanos=time.monotonic_ns(), exchanges=[])
        self.stderr = (root / (node + '-stderr.log')).open('xb')
        self.proc = subprocess.Popen(args, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr)
        run.workers.append(self)
        self.record.update(pid=self.proc.pid, linuxStartTicks=Path(f'/proc/{self.proc.pid}/stat').read_text().rsplit(')', 1)[1].split()[19])
        save(self.path, self.record)
        self.record['ready'] = self.receive()
        self.record['readyNanos'] = time.monotonic_ns()
        need(self.record['ready']['status'] == 'STARTED' and self.record['ready']['identity']['pid'] == self.proc.pid, 'worker startup identity')
        save(self.path, self.record)

    def receive(self):
        deadline = time.monotonic() + self.run.remaining()
        while b'\n' not in self.buffer:
            remaining = deadline - time.monotonic()
            need(remaining > 0 and select.select([self.proc.stdout], [], [], max(remaining, 0))[0], 'measurement response timeout')
            data = os.read(self.proc.stdout.fileno(), 65536)
            need(data, 'measurement worker exited: ' + (self.root / (self.node + '-stderr.log')).read_text()[-5000:])
            self.buffer += data
            need(len(self.buffer) <= 4 << 20, 'response byte bound')
        raw, self.buffer = self.buffer.split(b'\n', 1)
        return model.strict_json(raw)

    def command(self, name, **values):
        request = dict(command=name, opId=f'{self.node}-g1-{len(self.record["exchanges"])+1}', **values)
        row = dict(request=request, startNanos=time.monotonic_ns(), outcome='PENDING')
        self.record['exchanges'].append(row)
        save(self.path, self.record)
        self.proc.stdin.write(model.canonical(request) + b'\n')
        self.proc.stdin.flush()
        result = self.receive()
        row.update(endNanos=time.monotonic_ns(), response=result, outcome=result['outcome'])
        save(self.path, self.record)
        need(result['opId'] == request['opId'] and result['command'] == name and result['pid'] == self.proc.pid and result['node'] == self.node,
             'measurement response identity')
        need(result['outcome'] == 'SUCCESS', 'measurement command failed: ' + json.dumps(result))
        return result

    def stop(self, failed=False):
        if 'endNanos' in self.record:
            return
        try:
            if self.proc.poll() is None:
                if failed:
                    self.proc.kill()
                else:
                    self.command('close')
                    self.proc.stdin.close()
            self.proc.wait(timeout=self.run.remaining(10))
            need(failed or self.proc.returncode == 0, 'worker close failed')
        finally:
            if self.proc.poll() is None:
                self.proc.kill()
                self.proc.wait(timeout=5)
            self.record.update(endNanos=time.monotonic_ns(), exitCode=self.proc.returncode, cleanup='reaped', forced=failed)
            save(self.path, self.record)
            self.stderr.close()
            for stream in (self.proc.stdin, self.proc.stdout):
                if not stream.closed:
                    stream.close()


def compile_adapters(run, control_directory):
    java = ROOT / 'scripts/v51/java'
    source = ROOT / 'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/admission'
    common = [source / (n + '.java') for n in ('AdmissionJson', 'AdmissionSemanticModel', 'PerformanceTelemetry')]
    common += [java / (n + '.java') for n in ('V51RichWorkload', 'V51Measurement', 'V51CloudCommands', 'V51CloudJournal')]
    jars = {
        'published-v4.4-local': [control_directory / 'general-search-engine-4.4.0.jar'],
        'published-v5.0-configured': [control_directory / 'general-search-engine-5.0.0.jar', control_directory / 'general-search-engine-replication-5.0.0.jar'],
        'candidate-v5.1-automatic': [CORE, REPLICATION]}
    names = {
        'published-v4.4-local': ['V51MeasuredLocal', 'V51CloudLocal', 'V51CloudJournalCheck'],
        'published-v5.0-configured': ['V51MeasuredConfigured', 'V51ConfiguredObserver', 'V51CloudConfigured'],
        'candidate-v5.1-automatic': ['PublicRuntimeConsumer', 'V51PublicWorker', 'V51MeasuredAutomatic', 'V51PerformanceObserver', 'V51SmallPerformanceConsumer', 'V51CloudAutomatic']}
    result = {}
    retained = run.root / 'artifacts'
    retained.mkdir()
    for mode, originals in jars.items():
        artifacts = []
        for original in originals:
            need(original.is_file() and not original.is_symlink(), 'source artifact type')
            destination = retained / original.name
            shutil.copyfile(original, destination)
            artifacts.append(destination)
        classes = run.root / ('classes-' + mode)
        classes.mkdir()
        for artifact in artifacts:
            need(artifact.is_file() and not artifact.is_symlink(), 'artifact type')
            with zipfile.ZipFile(artifact) as archive:
                need(not any('/V51Measured' in name or '/V51Measurement' in name for name in archive.namelist()), 'test probe packaged in production')
        sources = common + [java / (name + '.java') for name in names[mode]]
        run.process(['javac', '--release', '21', '-proc:none', '-cp', os.pathsep.join(map(str, artifacts)), '-d', classes, *sources], 'compile-' + mode)
        result[mode] = dict(cp=os.pathsep.join(map(str, [*artifacts, classes])),
                           artifacts=[dict(path=str(p), sha256=model.sha(p.read_bytes())) for p in artifacts],
                           classes=inventory(classes), sources={str(p.relative_to(ROOT)): model.sha(p.read_bytes()) for p in sources})
    return result


def group_directory(root):
    root.mkdir()
    sockets = [socket.socket() for _ in range(3)]
    try:
        for sock in sockets:
            sock.bind(('127.0.0.1', 0))
        (root / 'ports.txt').write_text(''.join(str(sock.getsockname()[1]) + '\n' for sock in sockets))
    finally:
        for sock in sockets:
            sock.close()
    (root / 'group-id.txt').write_text(str(uuid.uuid4()) + '\n')


def healthy(run, mode, adapter, source):
    root = run.root / mode
    cp = adapter['cp']
    workers = []
    start = time.monotonic_ns()
    if mode == 'published-v4.4-local':
        root.mkdir()
        workers.append(Worker(run, root, 'local', run.java(cp, 'admission.V51MeasuredLocal', root, 'run', run.root / 'plan.json', source)))
        active = workers[0]
    else:
        workers = [Worker(run, root, 'node-' + str(i), run.java(cp, 'replication.' + ('V51ConfiguredObserver' if mode == 'published-v5.0-configured' else 'V51PerformanceObserver'),
                    root, i, run.root / 'plan.json', source)) for i in (1, 2, 3)]
        active = workers[0] if mode == 'published-v5.0-configured' else None
        if active:
            active.command('activate')
        else:
            while active is None:
                need(time.monotonic_ns() - start < 30_000_000_000, 'automatic startup budget')
                for worker in workers:
                    status = worker.command('status')['status']
                    need(status['state'] != 'FAILED', 'automatic worker failed')
                    if status['state'] == 'LEADER_READY':
                        active = worker
                        break
                if active is None:
                    time.sleep(.05)
    rows, windows = [], []
    for window in ['warmup', *run.plan['localSmoke']['windows']]:
        began = time.monotonic_ns()
        limit = start + 30_000_000_000 if window == 'warmup' else began + 30_000_000_000
        prior_deadline = run.deadline
        run.deadline = min(run.deadline, limit)
        for worker in workers:
            worker.command('configure', window=window)
        for ordinal, call in enumerate(model.program(run.plan), 1):
            if call['window'] != window:
                continue
            result = active.command('call', **{key: call[key] for key in ('window', 'cycle', 'operation')}, ordinal=ordinal)
            need(result['call']['outcome'] == 'SUCCESS', 'healthy operation failed: ' + json.dumps(result))
            rows.append(dict(result['call'], opId=result['opId'], node=active.node, pid=active.proc.pid,
                             resultFile=active.node + '-results.jsonl', processFile=active.node + '-process.json'))
        run.remaining()
        windows.append(dict(window=window, startNanos=began, endNanos=time.monotonic_ns()))
        run.deadline = prior_deadline
    save(root / 'calls.json', rows)
    save(root / 'windows.json', windows)
    # Only local control needs a checkpoint. Replicated export includes one accounted
    # auxiliary automatic barrier; no full-state query is issued against the candidate.
    if mode == 'published-v4.4-local':
        active.command('checkpoint')
    else:
        active.command('backup')
        if mode == 'published-v5.0-configured':
            for worker in workers:
                if worker is not active:
                    active.command('catchup', peer=worker.node)
        else:
            cut = active.command('status')['status']['provenIndex']
            while True:
                states = [w.command('status')['status'] for w in workers]
                need(all(s['state'] != 'FAILED' for s in states), 'healthy retained convergence failed')
                if all(s['provenIndex'] >= cut for s in states):
                    break
                runner_remaining = run.remaining()
                time.sleep(min(.1, runner_remaining))
    for worker in workers:
        worker.stop()
    return dict(mode=mode, active=active.node, processIds=[w.proc.pid for w in workers], calls=len(rows))


def run(output):
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    admitted = plan.load()
    save(root / 'plan.json', admitted)
    runner = Run(root, admitted)
    receipt = dict(schema=admitted['evidenceSchema'], execution=admitted['execution'], paidCloud=False, status='FAIL', modes=[])
    try:
        with runner.stage('preparation'):
            receipt['source'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, timeout=10).strip()
            paths = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT, timeout=10).decode().split('\0')
            save(root / 'source-inventory.json', {p: model.sha((ROOT / p).read_bytes()) for p in sorted(set(paths)) if p and (ROOT / p).is_file()})
            directory = ROOT / 'target/v51-controls'
            receipt['controls'] = model.strict_json(runner.process([sys.executable,'-m','scripts.v51.controls',directory],'resolve-controls'))
            receipt['adapters'] = compile_adapters(runner, directory)
            source = root / 'source'
            runner.process(runner.java(receipt['adapters']['published-v4.4-local']['cp'], 'admission.V51MeasuredLocal',
                                      root, 'prepare', root / 'plan.json', source), 'prepare-source')
            receipt['sourceInventorySha256'] = model.sha((root/'source-inventory.json').read_bytes())
            receipt['sourceBackup'] = semantics.source_backup(source, model.initial(admitted))
            save(root / 'source-before.json', inventory(source))
            for mode in admitted['modes'][1:]:
                target = root / mode
                group_directory(target)
                consumer = 'V51MeasuredConfigured' if mode == 'published-v5.0-configured' else 'V51MeasuredAutomatic'
                runner.process(runner.java(receipt['adapters'][mode]['cp'], 'admission.' + consumer, target, 'setup', root / 'plan.json', source), 'bootstrap-' + mode)
        for mode in admitted['modes']:
            with runner.stage(mode):
                receipt['modes'].append(healthy(runner, mode, receipt['adapters'][mode], source))
                print(json.dumps(dict(mode=mode, status='PASS')), flush=True)
        # The full receipt may only be issued after physical, resource, failover and
        # independent semantic validation. This implementation path fails closed until
        # those validators have accepted the retained execution.
        from .performance_failover import run as failover
        with runner.stage('failover'):
            receipt['failover'] = failover(runner, receipt['adapters']['candidate-v5.1-automatic'])
        from .performance_evidence import validate
        with runner.stage('validation'):
            for mode in admitted['modes'][1:]:
                target = root / ('restore-' + mode)
                target.mkdir()
                runner.process(runner.java(receipt['adapters']['published-v4.4-local']['cp'], 'admission.V51MeasuredLocal',
                                          target, 'restore', root / 'plan.json', root / mode / 'export'), 'restore', target)
            save(root / 'source-after.json', inventory(source))
            save(root / 'execution.json', receipt)
            receipt['validation'] = validate(root)
            from .performance_negatives import run as negatives
            receipt['negativeCases'] = len(negatives(root, runner.remaining))
            # Exercise retention before acceptance; final receipt is packed again below.
            from .performance_bundle import pack, unpack
            archive = root.parent/'qualification.tar.gz'
            pack(root, archive)
            with tempfile.TemporaryDirectory(prefix='v51-evidence-') as temporary:
                unpack(archive, Path(temporary)/'raw')
        receipt['status'] = 'PASS'
    except BaseException as error:
        receipt['failure'] = dict(type=type(error).__name__, message=str(error))
        raise
    finally:
        runner.deadline = min(runner.started + 900_000_000_000, time.monotonic_ns() + 60_000_000_000)
        cleanup_started = time.monotonic_ns()
        cleanup = []
        for worker in runner.workers:
            try:
                worker.stop(failed=True)
            except BaseException as error:
                cleanup.append(str(error))
        receipt['cleanupNanos'] = time.monotonic_ns() - cleanup_started
        receipt['cleanupErrors'] = cleanup
        receipt['elapsedNanos'] = time.monotonic_ns() - runner.started
        if cleanup:
            receipt['status'] = 'FAIL'
        save(root / 'receipt.json', receipt)
        if receipt['status'] != 'PASS':
            save(root / 'failure-members.json', inventory(root))
    need(receipt['status'] == 'PASS' and receipt['elapsedNanos'] <= 900_000_000_000, 'cleanup/whole gate ceiling')
    from .performance_bundle import pack, unpack
    archive = root.parent/'bundle.tar.gz'
    try:
        pack(root, archive)
        with tempfile.TemporaryDirectory(prefix='v51-final-evidence-') as temporary:
            unpack(archive, Path(temporary)/'raw')
        need(time.monotonic_ns()-runner.started <= 900_000_000_000, 'whole gate retention ceiling')
    except BaseException as error:
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)))
        save(root/'receipt.json',receipt)
        raise
    print(json.dumps(dict(status='PASS',execution=admitted['execution'],negativeCases=receipt['negativeCases'],bundle=str(archive))),flush=True)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output')
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(TimeoutError('controller terminated')))
    run(args.output)
