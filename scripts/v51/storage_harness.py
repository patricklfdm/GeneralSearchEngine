"""Real JVM authority cuts and independent pre-reopen inspection; no automatic service claim."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time
import xml.etree.ElementTree as ET

from . import storage_inspector as oracle

ROOT = Path(__file__).resolve().parents[2]
WORKER = 'io.github.patricklfdm.generalsearch.replication.V51StorageWorker'
CUTS = ('BEFORE_WRITE', 'WRITE_CHUNK', 'AFTER_WRITE', 'AFTER_FORCE', 'BEFORE_ACK', 'AFTER_ACK')


def save(path, value): path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
def need(value, message):
    if not value: raise ValueError(message)


def events(root): return [json.loads(v) for v in (root / 'events.jsonl').read_text().splitlines()]


def force_order(rows):
    forced = set()
    for row in rows:
        key = row['node'], row['pid'], row['recordSha256']
        if row['stage'].endswith('_AFTER_FORCE'): forced.add(key)
        if row['stage'].endswith('_ACK') and not row['stage'].endswith('_BEFORE_ACK'):
            need(key in forced, 'ACK lacks earlier force of the exact record in the same process')


def bind_events(root, rows):
    """Bind force/receipt telemetry to complete retained records, including setup voters."""
    import struct
    from . import format_inspector as f
    records = {}
    for node in ('node-1', 'node-2', 'node-3'):
        for filename, (kind, _) in oracle.LEDGERS.items():
            with (root / node / filename).open('rb') as stream:
                while True:
                    header = stream.read(48)
                    if len(header) < 48: break
                    size = struct.unpack('>i', header[12:16])[0]
                    need(0 < size <= (8 << 20) - 48, 'event binding frame bound')
                    body = stream.read(size)
                    if len(body) < size: break
                    if struct.unpack('>H', header[8:10])[0] == 3: continue
                    frame = header + body
                    records[node, oracle.sha(frame)] = kind, frame, f.inspect(frame, kind)
    for row in rows:
        forced = row['stage'].endswith('_AFTER_FORCE')
        ack = row['stage'].endswith('_ACK') and not row['stage'].endswith('_BEFORE_ACK')
        if not (forced or ack): continue
        key = row['node'], row['recordSha256']
        need(key in records, 'force/ACK record absent from retained authority')
        kind, frame, value = records[key]
        need(row['stage'].startswith(kind + '_'), 'force record kind')
        if ack and kind != 'PROMISE':
            index = value['index'] if kind == 'PROOF' else f.inspect(oracle.raw(value['entry']), 'ENTRY')['index']
            digest = oracle.sha(frame) if kind == 'PROOF' else value['entryDigest']
            expected = f.receipt(kind + '_ACK', value['manifestDigest'], row['node'], value['epoch'], value['proposer'], value['incarnation'], index, digest)
            need(row['receipt'] == expected, 'returned receipt is not bound to retained force')


def run(output):
    output = Path(output).resolve(); need(not output.exists(), 'fresh evidence directory'); output.mkdir(parents=True)
    from scripts.v50.offline_harness import CORE, REPLICATION
    jars = [CORE, REPLICATION]
    need(all(p.is_file() for p in jars), 'package the current reactor first')
    module = ROOT / 'general-search-engine-replication'
    for source in (module / 'src/main').rglob('*'):
        if source.is_file(): need(source.stat().st_mtime_ns <= REPLICATION.stat().st_mtime_ns, 'production JAR predates sources; package the reactor')
    cp = os.pathsep.join(map(str, [*jars, ROOT / 'general-search-engine-replication/target/test-classes']))
    receipt = dict(schema='gse-v51-storage-evidence-v1', status='RUNNING', execution='automatic-root-ledger-only', publicRuntime=False,
                   head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                   workingTreeDiffSha256=oracle.sha(subprocess.check_output(['git', 'diff', '--binary', 'HEAD'], cwd=ROOT)),
                   jars={p.name: oracle.sha(p.read_bytes()) for p in jars}, cases=[])
    receipt['javaTests'] = []
    for name in ('V51AutomaticRecordsTest', 'V51AutomaticStoreTest'):
        report = module / ('target/surefire-reports/TEST-io.github.patricklfdm.generalsearch.replication.' + name + '.xml')
        suite = ET.parse(report).getroot()
        need(int(suite.attrib['tests']) > 0 and all(int(suite.attrib.get(k, 0)) == 0 for k in ('failures', 'errors', 'skipped')), 'Java storage tests did not pass')
        receipt['javaTests'].append(dict(name=name, tests=int(suite.attrib['tests']), sha256=oracle.sha(report.read_bytes())))
    tracked = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode().split('\0')
    receipt['sourceInventorySha256'] = oracle.sha(oracle.canonical({p: oracle.sha((ROOT / p).read_bytes()) for p in sorted(set(tracked)) if p and (ROOT / p).is_file()}))
    def args(root, *values): return ['java', '-cp', cp, WORKER, str(root), *values]
    try:
        for kind in ('PROMISE', 'ACCEPT', 'PROOF'):
            for method in ('halt', 'kill'):
                for stage in CUTS:
                    root = output / f'{kind.lower()}-{method}-{stage.lower()}'; root.mkdir()
                    cut = kind + '_' + stage
                    setup = subprocess.run(args(root, 'setup', kind), capture_output=True, timeout=30)
                    (root / 'setup.stdout').write_bytes(setup.stdout); (root / 'setup.stderr').write_bytes(setup.stderr)
                    need(setup.returncode == 0, 'fixture setup failed: ' + setup.stderr.decode(errors='replace'))
                    owners = []; handles = []; process = None
                    try:
                        for node in ('node-2', 'node-3'):
                            log = (root / (node + '.stderr')).open('wb'); handles.append(log)
                            owner = subprocess.Popen(args(root, 'hold', node), stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log); owners.append(owner)
                        deadline = time.monotonic() + 20
                        while not all((root / (n + '.owner.jsonl')).exists() for n in ('node-2', 'node-3')):
                            need(all(p.poll() is None for p in owners) and time.monotonic() < deadline, 'concurrent owner admission'); time.sleep(.01)
                        for node, owner in zip(('node-2', 'node-3'), owners):
                            marker = root / (node + '.owner.jsonl')
                            while not marker.read_bytes().endswith(b'\n'):
                                need(time.monotonic() < deadline, 'incomplete owner marker'); time.sleep(.01)
                            need(json.loads(marker.read_text()) == dict(pid=owner.pid, node=node), 'owner PID identity')
                        err = (root / 'worker.stderr').open('wb'); handles.append(err)
                        process = subprocess.Popen(args(root, 'act', 'node-1', kind, cut, method), stdout=subprocess.DEVNULL, stderr=err)
                        deadline = time.monotonic() + 20
                        marker = root / 'barrier.jsonl'
                        while not marker.exists():
                            need(process.poll() is None and time.monotonic() < deadline, 'missing owned JVM cut: ' + cut); time.sleep(.01)
                        # A marker file can become visible before its write has completed.
                        while not marker.read_bytes().endswith(b'\n'):
                            need(time.monotonic() < deadline, 'incomplete cut marker'); time.sleep(.01)
                        need(json.loads(marker.read_text()) == dict(pid=process.pid, cut=cut), 'cut PID identity')
                        need(all(p.poll() is None for p in owners), 'three storage JVMs not concurrent')
                        if method == 'kill': process.kill()
                        code = process.wait(timeout=10); need(code == (97 if method == 'halt' else -9), 'unexpected worker exit')
                        pids = [process.pid, *[p.pid for p in owners]]; need(len(set(pids)) == 3, 'distinct owned processes')
                    finally:
                        if process is not None and process.poll() is None: process.kill(); process.wait(timeout=10)
                        for owner in owners:
                            owner.stdin.close()
                            try: owner.wait(timeout=10)
                            finally:
                                if owner.poll() is None: owner.kill(); owner.wait(timeout=10)
                        for handle in handles: handle.close()
                    need(all(p.returncode == 0 for p in owners), 'surviving owner cleanup')
                    before = {n: oracle.inventory(root / n) for n in ('node-1', 'node-2', 'node-3')}
                    with tarfile.open(root / 'before-reopen.tar.gz', 'w:gz') as archive:
                        for n in before: archive.add(root / n, arcname=n)
                    save(root / 'before-reopen.json', before)
                    rows = events(root); force_order(rows); bind_events(root, rows)
                    if stage in ('AFTER_FORCE', 'BEFORE_ACK', 'AFTER_ACK'):
                        need(any(r['pid'] == process.pid and r['stage'] == kind + '_AFTER_FORCE' for r in rows), 'missing completed force')
                    if stage == 'AFTER_ACK': need(any(r['pid'] == process.pid and r['stage'] == kind + '_ACK' for r in rows), 'missing returned ACK')
                    try: independent = oracle.inspect(root / 'node-1')
                    except ValueError as error: independent = dict(status='REJECT', reason=str(error))
                    expected = 'REJECT' if stage == 'WRITE_CHUNK' else 'PASS'
                    need(independent['status'] == expected, 'unexpected independent crash state')
                    if expected == 'PASS':
                        written = stage != 'BEFORE_WRITE'
                        need(independent['promisedEpoch'] == (2 if kind != 'PROMISE' or written else 1), 'lost promise')
                        need(independent['acceptedThrough'] == int(kind == 'PROOF' or kind == 'ACCEPT' and written), 'lost/phantom acceptance')
                        need(independent['provenThrough'] == int(kind == 'PROOF' and written), 'lost/phantom proof')
                    observed = subprocess.run(args(root, 'inspect', 'node-1'), capture_output=True, timeout=20)
                    (root / 'reopen.stdout').write_bytes(observed.stdout); (root / 'reopen.stderr').write_bytes(observed.stderr)
                    need(observed.returncode == (3 if expected == 'REJECT' else 0), 'product reopen exit')
                    product = json.loads(observed.stdout); need(product['status'] == expected, 'product/independent admission mismatch')
                    if expected == 'PASS':
                        for key in ('promisedEpoch', 'promiseCount', 'acceptedThrough', 'provenThrough', 'applicationSequence', 'retainedBytes', 'manifestDigest', 'acceptedDigests'):
                            need(product[key] == independent[key], 'product/independent authority mismatch: ' + key)
                    need(before == {n: oracle.inventory(root / n) for n in before}, 'reopen changed authority bytes')
                    case = dict(case=root.name, status='PASS', cut=cut, method=method, pids=pids, exitCode=code, independent=independent,
                                archiveSha256=oracle.sha((root / 'before-reopen.tar.gz').read_bytes()), product=product)
                    save(root / 'result.json', case); receipt['cases'].append(case)
                    print(json.dumps(dict(case=root.name, status='PASS')), flush=True)
        receipt['status'] = 'PASS'
    except BaseException as error:
        receipt.update(status='FAIL', failure=str(error)); raise
    finally: save(output / 'receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('output', type=Path)
    run(parser.parse_args().output)
