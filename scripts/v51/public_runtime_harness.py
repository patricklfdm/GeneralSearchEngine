"""Public JAR-only admission and three owned JVMs, with independent force/read audits."""
import argparse
import copy
import json
import os
from pathlib import Path
import queue
import subprocess
import tarfile
import threading
import time
import xml.etree.ElementTree as ET
from . import runtime_evidence as authority, storage_inspector as storage, controls
from .storage_harness import ROOT, need, save
from scripts.v50.offline_harness import CORE, REPLICATION


def validate(root, traces=None):
    root = Path(root)
    traces = traces if traces is not None else {
        f'node-{i}': [json.loads(line) for line in (root / f'node-{i}-trace.jsonl').read_text().splitlines()]
        for i in (1, 2, 3)}
    result = authority.validate(root, traces)
    reads = 0
    for rows in traces.values():
        published = {}
        for row in rows:
            if row['event'] == 'PUBLISHED':
                snapshot = authority.f.inspect(authority.raw(row['snapshot']), 'SNAPSHOT')
                proof = authority.f.inspect(authority.raw(snapshot['terminalProof']), 'PROOF')
                published[len(snapshot['anchors'])] = (snapshot, proof)
            if row['event'] == 'READ':
                need(row['index'] == row['before'] + 1 and row['index'] in published, 'read lacks its fresh published barrier')
                snapshot, proof = published[row['index']]
                need(row['epoch'] == proof['epoch'] and row['sequence'] == snapshot['applicationSequence'], 'read fence/sequence')
                _, documents = authority.application(authority.raw(snapshot['application']))
                need(row['documents'] == [dict(id=k, value=v) for k, v in documents.items()], 'read differs from published application')
                # A read must add a NO_OP, rather than borrowing the preceding application write.
                terminal = snapshot['anchors'][-1]['entryDigest']
                entries = [authority.f.inspect(authority.raw(authority.f.inspect(authority.raw(r['record']), 'ACCEPT')['entry']), 'ENTRY')
                           for own in traces.values() for r in own if r['event'] == 'FORCE' and r['kind'] == 'ACCEPT'
                           and authority.f.inspect(authority.raw(r['record']), 'ACCEPT')['entryDigest'] == terminal]
                need(entries and all(e['operation'] == 9 for e in entries), 'read is not a NO_OP')
                reads += 1
    need(reads >= 3, 'missing public read execution')
    return dict(result, execution='public-runtime-real-tcp', publicRuntime=True, reads=reads)


class Worker:
    def __init__(self, root, node, cp):
        self.log = (root / (node + '-stderr.log')).open('ab')
        self.process = subprocess.Popen(['java', '-cp', cp, 'io.github.patricklfdm.generalsearch.replication.V51PublicWorker', str(root), node[-1]],
                                        cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log, text=True)
        self.lines = queue.Queue(4)
        def read():
            for line in self.process.stdout: self.lines.put(line)
        threading.Thread(target=read, daemon=True).start()
        try: need(self.receive()['status'] == 'STARTED', 'public startup')
        except BaseException: self.kill(); raise
    def receive(self, timeout=35): return json.loads(self.lines.get(timeout=timeout))
    def request(self, name, timeout=35, **values):
        self.process.stdin.write(json.dumps(dict(command=name, **values)) + '\n'); self.process.stdin.flush()
        result = self.receive(timeout)
        need(result['command'] == name and type(result['accepted']) is bool, 'public response: ' + json.dumps(result)); return result
    def command(self, name, **values):
        result = self.request(name, **values); need(result['accepted'], 'public command: ' + json.dumps(result)); return result
    def kill(self):
        if self.process.poll() is None: self.process.kill()
        self.process.wait(timeout=10); self.process.stdin.close(); self.log.close()
    def close(self):
        try:
            if self.process.poll() is None:
                self.command('close'); self.process.stdin.close(); self.process.wait(timeout=15)
        finally:
            if self.process.poll() is None: self.kill()
            self.log.close()


def checkpoint_when_available(worker, output, timeout=30):
    """Only a classified, side-effect-free maintenance capacity rejection can wait."""
    record = dict(status='FAIL', timeoutSeconds=timeout, attempts=[])
    started = time.monotonic(); deadline = started + timeout
    try:
        while True:
            remaining = deadline - time.monotonic()
            need(remaining > 0, 'public checkpoint capacity timeout')
            attempt = dict(startSeconds=time.monotonic() - started); record['attempts'].append(attempt)
            result = worker.request('checkpoint', timeout=remaining)
            attempt.update(endSeconds=time.monotonic() - started, result=result)
            if result['accepted']:
                record['status'] = 'PASS'; return record
            need(result.get('reasonCode') == 'CAPACITY_EXCEEDED' and result.get('outcome') == 'NOT_APPLICABLE',
                 'public checkpoint failed: ' + json.dumps(result))
            time.sleep(min(.25, max(0, deadline - time.monotonic())))
    except BaseException as error:
        record['failure'] = str(error); raise
    finally:
        save(output, record)


def run(output):
    root = Path(output).resolve(); root.mkdir(parents=True, exist_ok=False)
    receipt = dict(status='FAIL', execution='public-runtime-real-tcp', publicRuntime=True, paidCloud=False, cases=[])
    workers = {}
    def command(args, name):
        result = subprocess.run(list(map(str, args)), cwd=ROOT, capture_output=True, text=True, timeout=90)
        (root / (name + '.stdout')).write_text(result.stdout); (root / (name + '.stderr')).write_text(result.stderr)
        need(result.returncode == 0, name + ': ' + result.stderr[-4000:]); return result
    try:
        receipt['head'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        files = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode().split('\0')
        receipt['sourceInventorySha256'] = storage.sha(storage.canonical({p: storage.sha((ROOT / p).read_bytes()) for p in sorted(set(files)) if p and (ROOT / p).is_file()}))
        receipt['jars'] = {p.name: storage.sha(p.read_bytes()) for p in (CORE, REPLICATION)}
        module = ROOT / 'general-search-engine-replication'
        need(all(p.stat().st_mtime_ns <= REPLICATION.stat().st_mtime_ns for p in (module / 'src/main').rglob('*.java')), 'package current runtime sources first')
        report = module / 'target/surefire-reports/TEST-io.github.patricklfdm.generalsearch.replication.V51PublicRuntimeTest.xml'
        suite = ET.parse(report).getroot()
        need(int(suite.attrib['tests']) >= 11 and all(int(suite.attrib.get(k, 0)) == 0 for k in ('failures', 'errors', 'skipped')), 'public runtime Java prerequisites')
        need(report.stat().st_mtime_ns >= (module / 'src/test/java/io/github/patricklfdm/generalsearch/replication/V51PublicRuntimeTest.java').stat().st_mtime_ns, 'stale public test report')
        receipt['javaTests'] = dict(tests=int(suite.attrib['tests']), sha256=storage.sha(report.read_bytes()))
        jars = os.pathsep.join(map(str, (CORE, REPLICATION))); java = ROOT / 'scripts/v51/java'
        classes = root / 'consumer-classes'; classes.mkdir(); bridge = root / 'bridge-classes'; bridge.mkdir()
        json_source = module / 'src/test/java/io/github/patricklfdm/generalsearch/admission/AdmissionJson.java'
        command(['javac', '--release', '21', '-proc:none', '-cp', jars, '-d', classes, json_source, java / 'PublicRuntimeConsumer.java'], 'compile-consumer')
        command(['javac', '--release', '21', '-proc:none', '-cp', jars + os.pathsep + str(classes), '-d', bridge, java / 'V51PublicWorker.java'], 'compile-observer')
        cp = os.pathsep.join(map(str, (CORE, REPLICATION, classes, bridge)))
        command(['java', '-cp', cp, 'io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer', root, 'setup'], 'public-bootstrap')
        for i in (1, 2, 3): workers[f'node-{i}'] = Worker(root, f'node-{i}', cp)
        def leader():
            until = time.monotonic() + 35
            while time.monotonic() < until:
                states = {n: w.command('status') for n, w in workers.items()}
                need(all(s['state'] != 'FAILED' for s in states.values()), 'public runtime failed: ' + json.dumps(states))
                for n, state in states.items():
                    if state['state'] == 'LEADER_READY': return n, workers[n]
                time.sleep(.1)
            raise ValueError('public leader timeout: ' + json.dumps(states))
        old, active = leader(); active.command('add', id=1, value='shared')
        need(active.command('query')['documents'] == [dict(id=1, value='shared')], 'public initial query')
        receipt['cases'].append('public-bootstrap/start/election/mutation/read')
        active.kill(); del workers[old]
        with tarfile.open(root / 'leader-before-reopen.tar.gz', 'w:gz') as archive: archive.add(root / old, arcname=old)
        new, active = leader(); need(new != old and active.command('query')['documents'] == [dict(id=1, value='shared')], 'public failover read')
        active.command('update', id=1, value='updated'); active.command('add', id=2, value='shared')
        expected = [dict(id=1, value='updated'), dict(id=2, value='shared')]
        need(active.command('query')['documents'] == expected, 'public post-failover query')
        workers[old] = Worker(root, old, cp)
        need(workers[old].command('status')['state'] != 'LEADER_READY', 'public retained startup revived leadership')
        active.command('backup')
        receipt['checkpoint'] = checkpoint_when_available(active, root / 'checkpoint-maintenance.json')
        controls.resolve(ROOT / 'target/v51-controls'); control = ROOT / 'target/v51-controls/general-search-engine-4.4.0.jar'
        control_classes = root / 'control-classes'; control_classes.mkdir()
        control_cp = os.pathsep.join(map(str, (control, REPLICATION, control_classes)))
        command(['javac', '--release', '21', '-proc:none', '-cp', control_cp, '-d', control_classes, json_source, java / 'PublicRuntimeConsumer.java'], 'compile-control')
        restored = command(['java', '-cp', control_cp, 'io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer', root, 'control'], 'published-v44-backup')
        need('controlSource=' + str(control) in restored.stderr.splitlines(), 'wrong control artifact')
        need(json.loads(restored.stdout) == dict(sequence=3, documents=expected), 'published V4.4 backup projection')
        receipt['publishedControlSha256'] = storage.sha(control.read_bytes())
        receipt['cases'] += ['leader-sigkill/fresh-election/read', 'retained-public-restart', 'checkpoint', 'backup/published-v44']
    except BaseException as error:
        receipt['failure'] = str(error); raise
    finally:
        cleanup = []
        for worker in workers.values():
            try: worker.close()
            except Exception as error: cleanup.append(str(error))
        if cleanup: receipt['cleanupErrors'] = cleanup
        save(root / 'receipt.json', receipt)
        if cleanup: raise ValueError('owned public worker cleanup: ' + str(cleanup))
    try:
        receipt['validation'] = validate(root)
        receipt['negatives'] = authority.negatives(root)
        original = {f'node-{i}': [json.loads(line) for line in (root / f'node-{i}-trace.jsonl').read_text().splitlines()] for i in (1, 2, 3)}
        for case, key, value in [('borrowed-read-barrier', 'before', -1), ('changed-read-result', 'documents', [])]:
            changed = copy.deepcopy(original); next(r for rows in changed.values() for r in rows if r['event'] == 'READ')[key] = value
            try: validate(root, changed)
            except ValueError as error: receipt['negatives'].append(dict(case=case, status='REJECTED', reason=str(error)))
            else: raise ValueError('public oracle accepted ' + case)
        receipt['status'] = 'PASS'
    except BaseException as error: receipt['failure'] = str(error); raise
    finally: save(root / 'receipt.json', receipt)
    print(json.dumps(receipt['validation']), flush=True)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('output'); args = parser.parse_args(); run(args.output)
