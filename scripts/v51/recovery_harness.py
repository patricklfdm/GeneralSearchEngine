"""Three-owned-JVM recovery cuts; archives and independent inspection precede reopen."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time
import xml.etree.ElementTree as ET

from . import storage_inspector as oracle
from .storage_harness import ROOT, WORKER, need, save

RECOVERY_WORKER = WORKER.replace('V51StorageWorker', 'V51RecoveryWorker')
CASES = {
    'BASIS': ('PROMISE_AFTER_FORCE', 'BASIS_IMAGE_WRITE_CHUNK', 'BASIS_IMAGE_AFTER_FORCE', 'BASIS_AFTER_FORCE', 'BASIS_AFTER_ACK'),
    'SELECTED': ('SELECTED_IMAGE_AFTER_FORCE', 'SELECTED_BASIS_AFTER_FORCE', 'SELECTED_WRITE_CHUNK', 'SELECTED_AFTER_FORCE', 'SELECTED_AFTER_RENAME', 'SELECTED_AFTER_ACK'),
    'INSTALL': ('GENERATION_SNAPSHOT_WRITE_CHUNK', 'GENERATION_SNAPSHOT_AFTER_FORCE', 'GENERATION_ACCEPTED_AFTER_FORCE', 'GENERATION_SEAL_WRITE_CHUNK', 'GENERATION_SEAL_AFTER_FORCE', 'SELECTOR_AFTER_FORCE', 'SELECTOR_AFTER_RENAME', 'STARTED_WRITE_CHUNK', 'STARTED_AFTER_FORCE', 'INSTALL_AFTER_ACK'),
    'FLOOR': ('FLOOR_SOURCE_AFTER_FORCE', 'FLOOR_WRITE_CHUNK', 'FLOOR_AFTER_FORCE', 'FLOOR_AFTER_RENAME', 'FLOOR_AFTER_ACK'),
    'DELETE': ('RETIREMENT_AFTER_FORCE', 'DELETE_AFTER_FILE', 'DELETE_AFTER_DIRECTORY', 'DELETE_AFTER_ROOT_TRUNCATE', 'DELETE_AFTER_ACK'),
    'TRANSFER': ('TRANSFER_DATA_AFTER_WRITE', 'TRANSFER_DATA_AFTER_FORCE', 'TRANSFER_PROGRESS_AFTER_FORCE', 'TRANSFER_PROGRESS_AFTER_RENAME', 'TRANSFER_AFTER_ACK'),
}


def wait_marker(path, process, seconds=20):
    deadline = time.monotonic() + seconds
    while not path.exists() or not path.read_bytes().endswith(b'\n'):
        need(time.monotonic() < deadline and process.poll() is None, 'worker stopped before barrier: ' + str(path))
        time.sleep(.01)
    return json.loads(path.read_text())


def witness(rows, action, inventory):
    need(rows and rows[-1]['files'] == inventory, 'last causal cut differs from retained files')
    ack = [r for r in rows if r['stage'] == action + '_ACK']
    if not ack or action == 'DELETE': return
    forced_stage, final_file = {
        'BASIS': ('BASIS_AFTER_FORCE', 'basis/node-1/basis.gsr'),
        'SELECTED': ('SELECTED_AFTER_FORCE', 'selected.gsr'),
        'INSTALL': ('SELECTOR_AFTER_FORCE', 'current.gsr'),
        'FLOOR': ('FLOOR_AFTER_FORCE', 'recovery-floor.gsr'),
        'TRANSFER': ('TRANSFER_PROGRESS_AFTER_FORCE', 'transfer/transfer.gsr'),
    }[action]
    digest = ack[-1]['files'][final_file]['sha256']
    need(any(r['stage'] == forced_stage and r['pid'] == ack[-1]['pid'] and
             any(v['sha256'] == digest for v in r['files'].values()) for r in rows[:rows.index(ack[-1])]), 'ACK lacks force of exact published bytes')


def run(output):
    from scripts.v50.offline_harness import CORE, REPLICATION
    output = Path(output).resolve(); need(not output.exists(), 'fresh recovery evidence'); output.mkdir(parents=True)
    jars = [CORE, REPLICATION]; need(all(p.is_file() for p in jars), 'package current reactor first')
    module = ROOT / 'general-search-engine-replication'
    need(all(p.stat().st_mtime_ns <= REPLICATION.stat().st_mtime_ns for p in (module / 'src/main').rglob('*') if p.is_file()), 'JAR predates sources')
    cp = os.pathsep.join(map(str, [*jars, module / 'target/test-classes']))
    receipt = dict(schema='gse-v51-recovery-evidence-v1', status='RUNNING', execution='automatic-recovery-storage-only', publicRuntime=False,
                   head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                   workingTreeDiffSha256=oracle.sha(subprocess.check_output(['git', 'diff', '--binary', 'HEAD'], cwd=ROOT)),
                   jars={p.name: oracle.sha(p.read_bytes()) for p in jars}, cases=[])
    tracked = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode().split('\0')
    receipt['sourceInventorySha256'] = oracle.sha(oracle.canonical({p: oracle.sha((ROOT / p).read_bytes()) for p in sorted(set(tracked)) if p and (ROOT / p).is_file()}))
    report = module / 'target/surefire-reports/TEST-io.github.patricklfdm.generalsearch.replication.V51AutomaticRecoveryTest.xml'
    suite = ET.parse(report).getroot(); need(int(suite.attrib['tests']) >= 15 and all(int(suite.attrib.get(k, 0)) == 0 for k in ('failures', 'errors', 'skipped')), 'Java recovery tests')
    receipt['javaTests'] = dict(tests=int(suite.attrib['tests']), sha256=oracle.sha(report.read_bytes()))
    def args(worker, root, *values): return ['java', '-cp', cp, worker, str(root), *values]
    try:
        for action, cuts in CASES.items():
            for method in ('halt', 'kill'):
                for cut in cuts:
                    root = output / (method + '-' + cut.lower()); root.mkdir()
                    setup = subprocess.run(args(RECOVERY_WORKER, root, 'setup', action), capture_output=True, timeout=30)
                    (root / 'setup.stderr').write_bytes(setup.stderr); need(setup.returncode == 0, 'recovery setup failed: ' + setup.stderr.decode(errors='replace'))
                    owners, handles, process = [], [], None
                    try:
                        for n in ('node-2', 'node-3'):
                            log = (root / (n + '.stderr')).open('wb'); handles.append(log)
                            p = subprocess.Popen(args(WORKER, root, 'hold', n), stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log); owners.append(p)
                            need(wait_marker(root / (n + '.owner.jsonl'), p) == dict(pid=p.pid, node=n), 'owner PID')
                        log = (root / 'worker.stderr').open('wb'); handles.append(log)
                        process = subprocess.Popen(args(RECOVERY_WORKER, root, 'act', action, cut, method), stdout=subprocess.DEVNULL, stderr=log)
                        need(wait_marker(root / 'barrier.jsonl', process) == dict(pid=process.pid, cut=cut), 'cut PID')
                        need(all(p.poll() is None for p in owners), 'three owners must overlap')
                        if method == 'kill': process.kill()
                        code = process.wait(timeout=10); need(code == (97 if method == 'halt' else -9), 'owned cut exit')
                        pids = [process.pid, *[p.pid for p in owners]]; need(len(set(pids)) == 3, 'three distinct JVMs')
                    finally:
                        if process is not None and process.poll() is None: process.kill(); process.wait(timeout=10)
                        for p in owners:
                            p.stdin.close()
                            try: p.wait(timeout=10)
                            finally:
                                if p.poll() is None: p.kill(); p.wait(timeout=10)
                        for h in handles: h.close()
                    need(all(p.returncode == 0 for p in owners), 'owner cleanup')
                    before = {n: oracle.inventory(root / n) for n in ('node-1', 'node-2', 'node-3')}
                    save(root / 'before-reopen.json', before)
                    with tarfile.open(root / 'before-reopen.tar.gz', 'w:gz') as archive:
                        for n in before: archive.add(root / n, arcname=n)
                    rows = [json.loads(line) for line in (root / 'events.jsonl').read_text().splitlines()]
                    for row in rows: row["files"] = {v["path"]: {k: v[k] for k in ("size", "sha256")} for v in row["files"]}
                    witness(rows, action, before['node-1'])
                    independent = oracle.inspect(root / 'node-1')
                    result = subprocess.run(args(WORKER, root, 'inspect', 'node-1'), capture_output=True, timeout=20)
                    (root / 'reopen.stderr').write_bytes(result.stderr); (root / 'reopen.stdout').write_bytes(result.stdout)
                    need(result.returncode == 0, 'product recovery rejection: ' + result.stdout.decode(errors='replace'))
                    product = json.loads(result.stdout)
                    for key in ('promisedEpoch', 'promiseCount', 'acceptedThrough', 'provenThrough', 'applicationSequence', 'retainedBytes', 'manifestDigest', 'acceptedDigests'):
                        need(independent[key] == product[key], 'product/independent recovery mismatch: ' + key)
                    need(independent['promisedEpoch'] == (5 if action in ('SELECTED', 'INSTALL') else 2), 'lost promised epoch')
                    need(independent['provenThrough'] == (0 if action in ('BASIS', 'TRANSFER') else 1), 'lost or invented proof')
                    need(independent['acceptedThrough'] == (2 if action in ('SELECTED', 'INSTALL') else independent['provenThrough']), 'selected value replaced a local vote')
                    need(before == {n: oracle.inventory(root / n) for n in before}, 'reopen rewrote recovery files')
                    case = dict(case=root.name, status='PASS', action=action, cut=cut, method=method, pids=pids, exitCode=code,
                                independent=independent, product=product, archiveSha256=oracle.sha((root / 'before-reopen.tar.gz').read_bytes()))
                    save(root / 'result.json', case); receipt['cases'].append(case)
                    print(json.dumps(dict(case=root.name, status='PASS')), flush=True)
        receipt['status'] = 'PASS'
    except BaseException as error:
        receipt.update(status='FAIL', failure=str(error)); raise
    finally: save(output / 'receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('output', type=Path); run(parser.parse_args().output)
