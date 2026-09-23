"""Owned public JVMs, bounded overlapping histories, halt/SIGKILL and published V4.4."""
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import tarfile
import threading
import time
from . import controls, storage_inspector as storage, public_history, public_qualification_evidence as evidence, public_trace
from .storage_harness import ROOT, need, save
from scripts.v50.offline_harness import CORE, REPLICATION

PACKAGE = 'io.github.patricklfdm.generalsearch.'
CUTS = ('READ_CAPTURED', 'READ_RELEASED', 'BEFORE_CLIENT_RESPONSE')


class Worker:
    def __init__(self, root, node, cp, history, generation=1, consumer='qualification'):
        self.root = root
        self.node, self.history, self.generation = node, history, generation
        self.lock = threading.Lock(); self.pending = {}; self.serial = 0; self.startup = queue.Queue(1)
        self.log = (root / (node + '-stderr.log')).open('ab')
        self.consumer = consumer
        self.proc = subprocess.Popen(['java', '-cp', cp, PACKAGE + 'replication.V51PublicWorker', str(root), node[-1], consumer, str(generation)],
                                     cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log, text=True)
        self.reader = threading.Thread(target=self.read, daemon=True); self.reader.start()
        try: need(self.startup.get(timeout=30).get('status') == 'STARTED', 'public startup')
        except BaseException: self.stop(kill=True); raise

    def read(self):
        try:
            for line in self.proc.stdout:
                result = json.loads(line); now = time.monotonic_ns()
                if 'opId' not in result: self.startup.put(result); continue
                with self.lock:
                    future, record = self.pending.pop(result['opId'])
                    if record is not None:
                        record.update(endNanos=now, outcome=result['outcome'])
                        if 'reason' in result: record['reason'] = result['reason']
                        if 'reasonCode' in result: record['reasonCode'] = result['reasonCode']
                        if self.consumer == 'lifecycle': record['response'] = result
                        if result['kind'] == 'read' and result['outcome'] == 'SUCCESS': record['documents'] = result['documents']
                    future.set_result(result)
        finally:
            with self.lock:
                for future, record in self.pending.values():
                    if record is not None: record['disconnectNanos'] = time.monotonic_ns()
                    future.set_result(None)
                self.pending.clear()

    def send(self, kind, **values):
        with self.lock:
            self.serial += 1; identity = f'{self.node}-g{self.generation}-{self.serial}'
            command = dict(opId=identity, kind=kind, **values)
            record = None if kind == 'status' else dict(command, node=self.node, pid=self.proc.pid,
                        generation=self.generation, startNanos=time.monotonic_ns(), endNanos=None, outcome='PENDING')
            if record is not None: self.history.append(record)
            future = concurrent.futures.Future(); self.pending[identity] = future, record
            self.proc.stdin.write(json.dumps(command) + '\n'); self.proc.stdin.flush()
            return future

    def call(self, kind, **values):
        result = self.send(kind, **values).result(timeout=35)
        need(result is not None and result['outcome'] == 'SUCCESS', 'public call failed: ' + str(result)); return result

    def stop(self, kill=False):
        try:
            if self.proc.poll() is None:
                if kill: self.proc.kill()
                else:
                    self.proc.stdin.write('{"kind":"close"}\n'); self.proc.stdin.flush(); self.proc.stdin.close()
            code = self.proc.wait(timeout=35); self.reader.join(timeout=5)
            if not kill: need(code == 0, 'public close failed: ' + str(code))
        finally:
            if self.proc.poll() is None: self.proc.kill(); self.proc.wait(timeout=10)
            self.log.close()
            public_trace.finish(self.root, self.node, self.proc, self.generation)


def command(args, root, name, timeout=120):
    result = subprocess.run(list(map(str, args)), cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    (root / (name + '.stdout')).write_text(result.stdout); (root / (name + '.stderr')).write_text(result.stderr)
    need(result.returncode == 0, name + ': ' + result.stderr[-6000:]); return result


RECOVERY_REASONS = frozenset(('NOT_LEADER', 'NOT_READY', 'QUORUM_UNAVAILABLE', 'STALE_EPOCH', 'DEADLINE_EXCEEDED'))
UNCERTAIN_RECOVERY_REASONS = frozenset(('QUORUM_UNAVAILABLE', 'STALE_EPOCH', 'DEADLINE_EXCEEDED'))
WAVE_KINDS = ('addAll', 'read', 'addAll', 'read')


def concurrent_wave(active, documents):
    # Submit all four calls before collecting; never drop a partial wave's results.
    futures = [active.send(kind, **(dict(documents=documents()) if kind == 'addAll' else {}))
               for kind in WAVE_KINDS]
    return [future.result(timeout=35) for future in futures]


def recovered_wave(choose_leader, documents, attempts):
    # READY is only a role hint. Each subsequent wave uses fresh application keys;
    # no uncertain mutation is replayed and every attempt stays in Worker.history.
    # At most 22 calls including setup/crash/final read fit the existing 24-call oracle.
    for _ in range(3):
        node, active = choose_leader()
        responses = concurrent_wave(active, documents)
        attempts.append(dict(node=node, responses=responses))
        for kind, response in zip(WAVE_KINDS, responses):
            need(response is not None and response.get('kind') == kind, 'recovery wave missing/mismatched response: ' + str(response))
            outcome = response.get('outcome'); reason = response.get('reasonCode')
            if outcome == 'SUCCESS': continue
            allowed = (outcome == ('NOT_SUBMITTED' if kind == 'addAll' else 'NOT_APPLICABLE') and reason in RECOVERY_REASONS or
                       kind == 'addAll' and outcome == 'INDETERMINATE' and reason in UNCERTAIN_RECOVERY_REASONS)
            need(allowed, 'unexpected recovery wave failure: ' + str(response))
        if all(response['outcome'] == 'SUCCESS' for response in responses): return node, active
    raise ValueError('public concurrent wave did not recover after three fresh waves: ' + str(responses))


def scenario(root, cp, cut, mode, mutation_cut=False):
    root.mkdir(); workers = {}; history = []; receipt = dict(status='FAIL', cut=cut, mode=mode)
    tag = 0
    def docs():
        nonlocal tag
        tag += 1
        return [dict(id=tag * 2, value=f'operation-{tag}-a'), dict(id=tag * 2 + 1, value=f'operation-{tag}-b')]
    def leader():
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            states = {n: w.call('status')['state'] for n, w in workers.items()}
            need('FAILED' not in states.values(), 'failed voter: ' + str(states))
            for n, state in states.items():
                if state == 'LEADER_READY': return n, workers[n]
            time.sleep(.1)
        raise ValueError('public election timeout: ' + str(states))
    def wave(active):
        for result in concurrent_wave(active, docs):
            need(result is not None and result['outcome'] == 'SUCCESS', 'stable concurrent call failed: ' + str(result))
    try:
        command(['java', '-cp', cp, PACKAGE + 'admission.PublicRuntimeConsumer', root, 'setup'], root, 'bootstrap')
        for i in (1, 2, 3): workers[f'node-{i}'] = Worker(root, f'node-{i}', cp, history)
        old, active = leader()
        for _ in range(3): active.call('addAll', documents=docs())
        wave(active)
        armed = root / (old + '-arm.tmp'); armed.write_text(cut + '\n' + mode + '\n'); armed.replace(root / (old + '-arm.txt'))
        fault_start = time.monotonic_ns()
        pending = active.send('addAll', documents=docs()) if mutation_cut or cut == 'BEFORE_CLIENT_RESPONSE' else active.send('read')
        # The public role hint can race dispatch. Keep this attempt and its structured outcome;
        # never replay an uncertain operation to manufacture a successful write count.
        follower = next(w for n, w in workers.items() if n != old)
        rejected = follower.send('addAll', documents=docs())
        deadline = time.monotonic() + 30; reached = None
        while time.monotonic() < deadline:
            rows = public_trace.live_rows(root, old)
            reached = next((r for r in rows if r['event'] == 'CUT_REACHED'), None)
            if reached: break
            if active.proc.poll() is not None: break
            time.sleep(.02)
        need(reached is not None and reached['cut'] == cut and reached['pid'] == active.proc.pid, 'missing declared process cut')
        if mode == 'kill': active.proc.kill()
        code = active.proc.wait(timeout=10); need(code == (-9 if mode == 'kill' else 71), 'unexpected crash exit')
        active.stop(kill=True); del workers[old]
        need(pending.result(timeout=5) is None, 'crashed call unexpectedly returned')
        rejected.result(timeout=35)
        before = storage.inventory(root / old); inspected = storage.inspect(root / old)
        archive = root / 'before-reopen.tar.gz'
        with tarfile.open(archive, 'w:gz') as tar: tar.add(root / old, arcname=old)
        with tarfile.open(archive) as tar:
            archived = {m.name.removeprefix(old + '/'): dict(size=m.size, sha256=storage.sha(tar.extractfile(m).read())) for m in tar.getmembers() if m.isfile()}
        need(before == archived, 'pre-reopen archive differs')
        receipt['crash'] = dict(pid=active.proc.pid, generation=1, node=old, exitCode=code, requestedCut=cut,
                                faultNanos=fault_start, observed=reached, preReopen=inspected, inventory=before,
                                archiveSha256=storage.sha(archive.read_bytes()))
        receipt['recoveryWaves'] = []
        new, active = recovered_wave(leader, docs, receipt['recoveryWaves'])
        need(new != old, 'manual revival of old leader')
        workers[old] = Worker(root, old, cp, history, generation=2)
        active.call('read')
    except BaseException as error:
        receipt['failure'] = str(error); raise
    finally:
        errors = []
        for worker in workers.values():
            try: worker.stop()
            except Exception as error: errors.append(str(error))
        save(root / 'history.json', history); save(root / 'receipt.json', receipt)
        need(not errors, 'owned worker cleanup failed: ' + str(errors))
    try:
        need(any(a['startNanos'] < b['startNanos'] < a.get('endNanos', 0) for a in history if a.get('endNanos') for b in history), 'no concurrent client intervals')
        receipt['history'] = public_history.check(history)
        receipt['physical'] = evidence.physical(root, history)
        receipt['negatives'] = evidence.negatives(root, history)
        receipt['status'] = 'PASS'
    except BaseException as error: receipt['failure'] = str(error); raise
    finally: save(root / 'receipt.json', receipt)
    return receipt


def run(output):
    root = Path(output).resolve(); root.mkdir(parents=True, exist_ok=False)
    receipt = dict(status='FAIL', execution='public-concurrent-qualification', paidCloud=False, cases=[])
    try:
        receipt['head'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        paths = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode().split('\0')
        inventory = {p: storage.sha((ROOT / p).read_bytes()) for p in sorted(set(paths)) if p and (ROOT / p).is_file()}
        save(root / 'source-inventory.json', inventory); receipt['sourceInventorySha256'] = storage.sha(storage.canonical(inventory))
        receipt['jars'] = {p.name: storage.sha(p.read_bytes()) for p in (CORE, REPLICATION)}
        module = ROOT / 'general-search-engine-replication'; sources = module / 'src/test/java/io/github/patricklfdm/generalsearch/admission'
        need(all(p.stat().st_mtime_ns <= REPLICATION.stat().st_mtime_ns for p in (module / 'src/main').rglob('*.java')), 'package current runtime first')
        java = ROOT / 'scripts/v51/java'; classes = root / 'consumer'; classes.mkdir(); bridge = root / 'observer'; bridge.mkdir()
        jars = os.pathsep.join(map(str, (CORE, REPLICATION)))
        consumer_sources = [sources / 'AdmissionJson.java', sources / 'AdmissionSemanticModel.java',
                            *[java / (n + '.java') for n in ('PublicRuntimeConsumer', 'PublicQualificationConsumer', 'PublicSemanticConsumer')]]
        command(['javac', '--release', '21', '-proc:none', '-cp', jars, '-d', classes, *consumer_sources], root, 'compile-consumer')
        command(['javac', '--release', '21', '-proc:none', '-cp', jars + os.pathsep + str(classes), '-d', bridge, java / 'V51PublicWorker.java'], root, 'compile-observer')
        cp = os.pathsep.join(map(str, (CORE, REPLICATION, classes, bridge)))
        command(['javac', '--release', '21', '-proc:none', '-cp', cp, '-d', classes,
                 java / 'PublicSemanticCheckpointProbe.java'], root, 'compile-checkpoint-probe')
        probe = command(['java', '-cp', cp, PACKAGE + 'admission.PublicSemanticCheckpointProbe',
                         root / 'checkpoint-probe'], root, 'checkpoint-probe')
        receipt['checkpointProbe'] = json.loads(probe.stdout)
        for mode in ('halt', 'kill'):
            for cut in CUTS:
                name = mode + '-' + cut.lower(); result = scenario(root / name, cp, cut, mode)
                receipt['cases'].append(dict(name=name, status=result['status'], history=result['history'], physical=result['physical']))
                print(json.dumps(dict(case=name, status=result['status'])), flush=True)
        controls.resolve(ROOT / 'target/v51-controls'); control = ROOT / 'target/v51-controls/general-search-engine-4.4.0.jar'
        rich = root / 'rich'; rich.mkdir(); sockets = [socket.socket() for _ in range(3)]
        try:
            for s in sockets: s.bind(('127.0.0.1', 0))
            (rich / 'ports.txt').write_text(''.join(str(s.getsockname()[1]) + '\n' for s in sockets))
        finally:
            for s in sockets: s.close()
        candidate = command(['java', '-cp', cp, PACKAGE + 'admission.PublicSemanticConsumer', rich, 'candidate'], rich, 'candidate')
        checkpoint = json.loads((rich / 'checkpoint-maintenance.json').read_text())
        need(checkpoint['status'] == 'PASS' and checkpoint['attempts'][-1]['status'] == 'PASS', 'rich checkpoint never succeeded')
        control_classes = root / 'control'; control_classes.mkdir()
        control_cp = os.pathsep.join(map(str, (control, REPLICATION, control_classes)))
        command(['javac', '--release', '21', '-proc:none', '-cp', control_cp, '-d', control_classes,
                 sources / 'AdmissionJson.java', sources / 'AdmissionSemanticModel.java', java / 'PublicRuntimeConsumer.java', java / 'PublicSemanticConsumer.java'], root, 'compile-control')
        baseline = command(['java', '-cp', control_cp, PACKAGE + 'admission.PublicSemanticConsumer', rich, 'control'], rich, 'published-v44')
        need('coreSource=' + str(control) in baseline.stderr.splitlines() and 'coreSource=' + str(CORE) in candidate.stderr.splitlines(), 'wrong core code source')
        actual, expected = json.loads(candidate.stdout), json.loads(baseline.stdout)
        need(actual['stages'] == expected['stages'] and actual['sequence'] == expected['sequence'] == expected['restoredSequence'], 'published V4.4 rich semantics/sequence')
        need(actual['stages']['recreated'] == expected['restored'], 'published V4.4 restored rich semantics')
        receipt['semantics'] = dict(status='PASS', stages=list(actual['stages']), controlSha256=storage.sha(control.read_bytes()),
                                    controlCoreSource=str(control), candidateCoreSource=str(CORE), richPublicVoters=3, richJvmProcesses=1,
                                    checkpointAttempts=len(checkpoint['attempts']))
        receipt['status'] = 'PASS'
    except BaseException as error: receipt['failure'] = str(error); raise
    finally: save(root / 'receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('output'); args = parser.parse_args(); run(args.output)
