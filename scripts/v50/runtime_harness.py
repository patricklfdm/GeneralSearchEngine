"""Public 1.1 engine gate: isolated consumers, three owned JVMs, real cuts, pinned V4.4 oracle."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import tarfile
import time
import xml.etree.ElementTree as ET
from . import admission_format as f, runtime_format
from .leader_harness import ports
from .offline_harness import ROOT, CORE, REPLICATION, PACKAGE, save
from .recovery_harness import CONTROL_SHA

CUTS = ('AFTER_LOCAL_ENTRY_FORCE', 'AFTER_ENTRY_QUORUM', 'AFTER_LOCAL_PROOF_FORCE', 'AFTER_PROOF_QUORUM',
        'BEFORE_APPLICATION_PUBLICATION', 'AFTER_APPLICATION_PUBLICATION', 'BEFORE_CLIENT_SUCCESS',
        'AFTER_RECOVERY_STAGE_CREATE', 'AFTER_RECOVERY_SNAPSHOT_FILE_FORCE', 'AFTER_RECOVERY_ENTRIES_FORCE',
        'AFTER_RECOVERY_PROOFS_FORCE', 'BEFORE_RECOVERY_POINTER_PUBLISH', 'AFTER_RECOVERY_POINTER_RENAME', 'AFTER_RECOVERY_POINTER_FORCE')


def checked(args, evidence, timeout=40):
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.with_suffix('.stdout').write_text(result.stdout); evidence.with_suffix('.stderr').write_text(result.stderr)
    f.check(result.returncode == 0, 'process failed: ' + ' '.join(map(str, args)) + '\n' + result.stderr)
    return result


class Worker:
    def __init__(self, group, ordinal, cut=''):
        self.group, self.ordinal = group, ordinal
        group.generations[ordinal] += 1
        self.evidence = group.root / 'evidence' / f'node-{ordinal}-{group.generations[ordinal]}'
        self.evidence.mkdir(parents=True)
        self.stderr = (self.evidence / 'stderr.log').open('w'); self.control = (self.evidence / 'control.jsonl').open('w')
        args = ['java', '-cp', group.classpath, '-Dgse.runtime.evidence=' + str(self.evidence), '-Dgse.runtime.cut=' + cut,
                PACKAGE + 'replication.V50PublicRuntimeWorker', *group.args(ordinal)]
        self.process = subprocess.Popen(args, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr, text=True, bufsize=1)
        self.started = time.monotonic_ns()
        try:
            ready = self.receive(); f.check(ready['ready'] and ready['pid'] == self.process.pid and ready['node'] == f'node-{ordinal}', 'worker identity')
        except BaseException:
            self.close(True); raise

    def send(self, command, **values):
        message = dict(command=command, **values)
        self.control.write(json.dumps(dict(direction='request', value=message)) + '\n'); self.control.flush()
        self.process.stdin.write(json.dumps(message) + '\n'); self.process.stdin.flush()

    def receive(self):
        ready, _, _ = select.select([self.process.stdout], [], [], 25)
        f.check(ready, 'public worker timeout: ' + str(self.evidence))
        line = self.process.stdout.readline()
        f.check(line, 'public worker exited: ' + (self.evidence / 'stderr.log').read_text())
        message = json.loads(line); self.control.write(json.dumps(dict(direction='response', value=message)) + '\n'); self.control.flush()
        return message

    def command(self, name, accepted=True, **values):
        self.send(name, **values); result = self.receive()
        f.check(result['command'] == name and result['accepted'] == accepted, 'public command outcome: ' + json.dumps(result))
        return result

    def close(self, kill=False):
        try:
            if self.process.poll() is None:
                if kill: self.process.kill()
                else: self.command('close')
            code = self.process.wait(timeout=10)
            f.check(code == (-9 if kill else 0), 'unexpected owned process exit')
        finally:
            if self.process.poll() is None: self.process.kill(); self.process.wait(timeout=10)
            save(self.evidence / 'process.json', dict(pid=self.process.pid, exitCode=self.process.returncode,
                    startedNanos=self.started, finishedNanos=time.monotonic_ns()))
            self.stderr.close(); self.control.close(); self.process.stdin.close(); self.process.stdout.close()


class Group:
    def __init__(self, root, classpath, minor):
        self.root, self.classpath, self.minor = root, classpath, minor
        self.ports = ','.join(map(str, ports())); self.workers = {}; self.generations = {i: 0 for i in range(1, 4)}

    def args(self, ordinal): return [str(self.root), str(ordinal), self.ports, str(self.minor)]

    def offline(self, command, *extra):
        result = checked(['java', '-cp', self.classpath, PACKAGE + 'admission.PublicRuntimeConsumer', *self.args(0), command, *map(str, extra)],
                self.root / 'evidence' / ('offline-' + command + '-' + '-'.join(map(str, extra))))
        return json.loads(result.stdout)

    def start(self, ordinal, cut=''): self.workers[ordinal] = Worker(self, ordinal, cut)
    def start_all(self, cut=''):
        for i in range(1, 4): self.start(i, cut if i == 1 else '')
        f.check(all(w.process.poll() is None for w in self.workers.values()), 'three JVMs not concurrent')
    def stop(self, ordinal, kill=False):
        worker = self.workers.pop(ordinal, None)
        if worker: worker.close(kill)
    def close(self):
        failures = []
        for i in list(self.workers):
            try: self.stop(i)
            except Exception as error: failures.append(str(error))
        f.check(not failures, 'owned process cleanup: ' + '; '.join(failures))
    def command(self, command, **values): return self.workers[1].command(command, **values)

    def capture(self, label):
        f.check(not self.workers, 'inspection requires all owners closed')
        output = self.root / 'evidence' / label; output.mkdir()
        inventory = {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for i in range(1, 4) for p in (self.root / f'node-{i}').rglob('*') if p.is_file()}
        with tarfile.open(output / 'before-reopen.tar.gz', 'w:gz') as archive:
            for i in range(1, 4): archive.add(self.root / f'node-{i}', arcname=f'node-{i}')
        save(output / 'sha256.json', inventory)
        reports = [runtime_format.inspect(self.root / f'node-{i}', torn=True) for i in range(1, 4)]
        for a in reports:
            for b in reports:
                common = min(a['committed'], b['committed']); f.check(a['anchors'][:common] == b['anchors'][:common], 'conflicting proven public history')
        g = f.genesis((self.root / 'node-1/genesis.gsr').read_bytes()); m = f.manifest((self.root / 'node-1/manifest.gsr').read_bytes(), g)
        frames = list((self.root / 'evidence').glob('node-*/wire-*.bin'))
        for wire in frames: f.wire(wire.read_bytes(), m)
        f.check(all(hashlib.sha256((self.root / name).read_bytes()).hexdigest() == digest for name, digest in inventory.items()), 'oracle mutated bytes')
        save(output / 'independent.json', dict(nodes=reports, wireFrames=len(frames)))
        return reports


def run(workspace, artifact, only=None):
    workspace, artifact = workspace.resolve(), artifact.resolve()
    f.check(not workspace.exists(), 'evidence target must be absent'); workspace.mkdir(parents=True)
    f.check(hashlib.sha256(artifact.read_bytes()).hexdigest() == CONTROL_SHA, 'published control checksum')
    receipt = dict(schema='gse-v50-public-runtime-evidence-v1', status='RUNNING', cases=[], controlJarSha256=CONTROL_SHA,
                   coreJarSha256=hashlib.sha256(CORE.read_bytes()).hexdigest(), replicationJarSha256=hashlib.sha256(REPLICATION.read_bytes()).hexdigest())
    sources = ROOT / 'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/admission'
    candidate = workspace / 'public-classes'; worker = workspace / 'fault-classes'; control = workspace / 'control-classes'
    for path in (candidate, worker, control): path.mkdir()
    cp = os.pathsep.join(map(str, (CORE, REPLICATION)))
    names = ('AdmissionJson', 'AdmissionSemanticModel', 'OfflineApplication', 'PublicRuntimeWorkload', 'PublicRuntimeConsumer')
    checked(['javac', '--release', '21', '-proc:none', '-cp', cp, '-d', str(candidate), *[str(sources / (n + '.java')) for n in names]], workspace / 'consumer-compile')
    cp += os.pathsep + str(candidate)
    checked(['javac', '--release', '21', '-proc:none', '-cp', cp, '-d', str(worker), str(sources.parent / 'replication/V50PublicRuntimeWorker.java')], workspace / 'worker-compile')
    checked(['javac', '--release', '21', '-proc:none', '-cp', os.pathsep.join(map(str, (artifact, REPLICATION, candidate))), '-d', str(control),
             *[str(sources / (n + '.java')) for n in ('AdmissionJson', 'AdmissionSemanticModel', 'PublicRuntimeWorkload', 'AdmissionV44Control')]], workspace / 'control-compile')
    cp += os.pathsep + str(worker)
    def oracle(command, root, minor, source=None):
        root.mkdir(parents=True, exist_ok=True)
        args = ['java', '-cp', os.pathsep.join(map(str, (artifact, control, REPLICATION, candidate))), PACKAGE + 'admission.AdmissionV44Control', command, str(root), str(minor)]
        if source: args.append(str(source))
        result = checked(args, root / 'evidence' / ('control-' + command))
        f.check('controlSource=' + str(artifact) in result.stderr.splitlines(), 'oracle core code source')
        return json.loads(result.stdout)
    def passed(name, **details):
        row = dict(case=name, status='PASS', **details); receipt['cases'].append(row)
        print(json.dumps({k: v for k, v in row.items() if k != 'independent'}), flush=True)
    try:
        receipt['sourceSha'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        receipt['workingTreeDiffSha256'] = hashlib.sha256(subprocess.check_output(['git', 'diff', '--binary', 'HEAD'], cwd=ROOT)).hexdigest()
        names = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).split(b'\0')
        inventory = [[name.decode(), hashlib.sha256((ROOT / name.decode()).read_bytes()).hexdigest()]
                     for name in sorted(set(names) - {b''}) if (ROOT / name.decode()).is_file()]
        receipt['sourceInventorySha256'] = hashlib.sha256(json.dumps(inventory, separators=(',', ':')).encode()).hexdigest()
        receipt['java'] = []
        if only is None:
            for path in (ROOT / 'src/main', ROOT / 'general-search-engine-replication/src/main'):
                jar = CORE if path == ROOT / 'src/main' else REPLICATION
                f.check(all(p.stat().st_mtime_ns <= jar.stat().st_mtime_ns for p in path.rglob('*') if p.is_file()), 'JAR predates production sources')
            for test in ('admission.V50PublicRuntimeTest', 'replication.V50PublicLifecycleTest', 'replication.V50OfflineFixtureAgreementTest', 'replication.V50PublicApiInventoryTest'):
                report = ROOT / ('general-search-engine-replication/target/surefire-reports/TEST-' + PACKAGE + test + '.xml')
                suite = ET.parse(report).getroot()
                f.check(int(suite.attrib['tests']) > 0 and all(int(suite.attrib.get(k, 0)) == 0 for k in ('failures', 'errors', 'skipped')), 'Java gate not executed: ' + test)
                f.check(all(p.stat().st_mtime_ns <= report.stat().st_mtime_ns for p in (ROOT / 'general-search-engine-replication/src').rglob('*') if p.is_file()), 'Java report predates source: ' + test)
                receipt['java'].append(dict(test=test, tests=int(suite.attrib['tests']), sha256=hashlib.sha256(report.read_bytes()).hexdigest()))
        for minor in range(3):
            if only == 'crash': break
            root = workspace / f'roundtrip-{minor}'; expected = oracle('create', root, minor)
            group = Group(root, cp, minor); decision = group.offline('bootstrap')
            try:
                group.start_all()
                for w in group.workers.values():
                    s = w.command('status'); f.check(s['applicationSequence'] == expected['sequence'] and s['appliedIndex'] == 0 and s['state'] == 'CATCHING_UP', 'startup admitted public work')
                f.check(group.workers[2].command('report', accepted=False)['reason'] == 'NOT_CONFIGURED_LEADER', 'follower read admission')
                group.workers[2].command('checkpoint'); first = group.command('activate')
                f.check(group.command('activate')['incarnation'] == first['incarnation'], 'READY activation minted epoch')
                f.check(group.command('report')['semantics'] == expected['semantics'], 'import differs from published control')
                group.command('workload'); expected = oracle('continue', root / 'continued-control', minor)
                f.check(group.command('report')['semantics'] == expected['semantics'], 'all search overloads differ from published control')
                for i in (2, 3): group.command('catchup', peer=f'node-{i}')
                for w in group.workers.values(): w.command('checkpoint')
                exported = group.command('backup', target='export')
                f.check(exported['backupHistory'] == decision['history'] and exported['backupSequence'] == expected['sequence'], 'group backup history/sequence')
                restored = oracle('restore', root / 'restored-control', minor, root / 'export'); f.check(restored == expected, 'published backup restore differs')
                group.stop(2); group.stop(3)
                group.command('backup', target='isolated-export'); group.command('checkpoint')
                refused = group.command('checkpoint', accepted=False); f.check(refused['reason'] == 'CAPACITY_EXCEEDED', 'third local checkpoint deleted retained source')
                group.command('add', accepted=False, id=90)
                f.check(group.command('report')['semantics'] == expected['semantics'], 'quorum loss revoked committed reads')
                f.check(group.command('checkpoint', accepted=False)['reason'] == 'CONFLICTING_HISTORY', 'checkpoint dropped unresolved suffix')
                group.close(); reports = group.capture('isolated-before-reopen')
                group.start_all(); group.command('activate')
                f.check(group.command('report')['semantics'] == expected['semantics'], 'recovery lost acknowledged state')
                group.close(); group.capture('recovered')
                if minor == 2:
                    (root / 'node-3').rename(root / 'lost-node-3'); group.offline('replace', 3, 1)
                    group.start_all(); group.command('activate'); group.command('catchup', peer='node-3'); group.close(); group.capture('follower-replacement')
                    (root / 'node-1').rename(root / 'lost-node-1'); group.offline('replace', 1, 2)
                    group.start(1); group.start(2)
                    f.check(group.command('activate', accepted=False)['reason'] == 'CONFLICTING_HISTORY', 'replacement activated without reconstruction')
                    f.check(group.command('reconstruct', accepted=False)['reason'] == 'QUORUM_UNAVAILABLE', 'replacement accepted one survivor')
                    group.start(3); group.command('reconstruct')
                    f.check(group.command('report')['semantics'] == expected['semantics'], 'leader replacement semantics')
                    group.close(); group.capture('leader-replacement')
                passed('public-roundtrip-' + str(minor), sequence=expected['sequence'], independent=reports)
            finally: group.close()
        if only != 'roundtrip':
            for message in ('APPEND', 'COMMIT_PROOF', 'SNAPSHOT_CHUNK', 'SNAPSHOT_INSTALL'):
                root = workspace / ('lost-' + message.lower()); baseline = oracle('create', root, 2)
                group = Group(root, cp, 2); group.offline('bootstrap')
                try:
                    group.start_all(); group.command('activate')
                    if message.startswith('SNAPSHOT'):
                        group.close(); (root / 'node-3').rename(root / 'lost-node-3'); group.offline('replace', 3, 1)
                        group.start_all(); group.command('activate')
                        (group.workers[3].evidence / 'lose-response').write_text(message)
                        group.command('catchup', peer='node-3'); expected_sequence = baseline['sequence']
                    else:
                        for i in (2, 3): (group.workers[i].evidence / 'lose-response').write_text(message)
                        added = group.command('add', id=50); expected_sequence = baseline['sequence'] + 1
                        f.check(added['applicationSequence'] == expected_sequence and added['lastLogIndex'] == 2, 'lost response duplicated application entry')
                    group.close(); reports = group.capture('after-lost-response')
                    f.check(max(r['sequence'] for r in reports) == expected_sequence, 'lost response changed sequence')
                    attempts = list((root / 'evidence').glob('node-*/lost-*.txt'))
                    f.check(attempts and any(p.read_text().strip().endswith(' 2') for p in attempts), 'lost response did not retry')
                    passed('lost-' + message.lower(), sequence=expected_sequence, attempts=len(attempts))
                finally: group.close()
            for cut in CUTS:
                root = workspace / cut.lower(); baseline = oracle('create', root, 2)
                group = Group(root, cp, 2); group.offline('bootstrap')
                try:
                    group.start_all(cut); group.command('activate')
                    leader = group.workers[1]; (leader.evidence / 'armed').write_text('armed\n')
                    leader.send('checkpoint' if 'RECOVERY' in cut else 'add', id=50)
                    deadline = time.monotonic() + 20
                    while not (leader.evidence / 'barrier').exists() and leader.process.poll() is None and time.monotonic() < deadline: time.sleep(.01)
                    f.check((leader.evidence / 'barrier').read_text().splitlines() == [str(leader.process.pid), cut], 'owned barrier missing')
                    group.stop(1, True); group.close(); reports = group.capture('before-reopen')
                    protected = max(r['sequence'] for r in reports)
                    group.start_all(); recovered = group.command('activate')
                    f.check(recovered['applicationSequence'] == protected and protected >= baseline['sequence'], 'recovery lost proven application prefix')
                    group.close(); group.capture('after-reopen'); passed(cut, sequence=protected, killedPid=leader.process.pid)
                finally: group.close()
        receipt['status'] = 'PASS'
    except BaseException as error:
        receipt['status'] = 'FAIL'; receipt['failure'] = str(error)
        raise
    finally:
        save(workspace / 'receipt.json', receipt)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('workspace', type=Path); parser.add_argument('--control-jar', type=Path, required=True)
    parser.add_argument('--only', choices=('roundtrip', 'crash'))
    args = parser.parse_args(); run(args.workspace, args.control_jar, args.only)
