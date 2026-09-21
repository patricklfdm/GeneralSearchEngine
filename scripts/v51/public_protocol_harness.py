"""Public campaigns, minority tails and interrupted recovery on owned TCP JVMs."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from . import public_qualification_harness as q, public_qualification_evidence as physical
from . import public_fault_harness as fault, public_recovery_harness as recovery
from . import public_history, public_protocol_evidence as evidence, storage_inspector as storage
from .storage_harness import ROOT, need, save
from scripts.v50.offline_harness import CORE, REPLICATION

NODES = ('node-1', 'node-2', 'node-3')
NETWORK = ('competing-campaigns', 'asymmetric-requests', 'asymmetric-responses')
TAILS = ('minority-discarded', 'minority-selected')
RECOVERY = ('basis', 'snapshot-progress', 'snapshot-selector')
CASES = (*NETWORK, *TAILS, *(f'{kind}-{mode}' for kind in RECOVERY for mode in ('halt', 'kill')))
CUTS = {'basis': 'WIRE_BEFORE_RESPONSE_WRITE_BASIS_CHUNK:continuation',
        'snapshot-progress': 'STORAGE_CUT:TRANSFER_PROGRESS_BEFORE_ACK',
        'snapshot-selector': 'STORAGE_CUT:SELECTOR_BEFORE_ACK'}


def network(root, rules):
    fault.replace(root / 'network-rules.txt', ''.join(rule + '\n' for rule in rules))


def own_campaigns(root):
    result = {}
    for node in NODES:
        result[node] = [r for r in fault.rows(root, node) if r['event'] == 'FORCE' and r['kind'] == 'PROMISE'
                       and storage.f.inspect(storage.raw(r['record']), 'PROMISE')['proposer'] == node]
    return result if all(result.values()) and all(any(r['event'] == 'NETWORK_DROP' for r in fault.rows(root, n)) for n in NODES) else None


def directional_observed(root):
    rows = fault.rows(root, 'node-1')
    return any(r['event'] == 'NETWORK_DROP' for r in rows) and any(
        r['event'] == 'REPLY' and json.loads(storage.raw(r['frame'])[48:])['type'] != 'REJECT' for r in rows)


def scenario(root, cp, case):
    root.mkdir(); workers = {}; history = []; expected = []
    receipt = dict(status='FAIL', case=case, publicRuntime=True)
    (root / 'chunk-bytes.txt').write_text('4096\n')
    def start(node, generation=1):
        workers[node] = q.Worker(root, node, cp, history, generation)
        return workers[node]
    def write(active, tag):
        docs = [dict(id=tag+i, value=f'tag-{tag+i}-' + 'x'*512) for i in (0, 1)]
        active.call('addAll', documents=docs); expected.extend(docs)
    def read(active): need(active.call('read')['documents'] == expected, 'public protocol projection changed')
    def arm(node, cut, mode): fault.replace(root / (node + '-arm.txt'), cut + '\n' + mode + '\n')
    def crash(node, cut, mode):
        active = workers[node]
        reached = fault.wait_for(lambda: next((r for r in fault.rows(root, node) if r['event'] == 'CUT_REACHED'), None), 'public protocol cut not reached: ' + cut)
        need(reached['cut'] == cut and reached['pid'] == active.proc.pid, 'wrong protocol process cut')
        if mode == 'kill': active.proc.kill()
        code = active.proc.wait(timeout=10); need(code == (-9 if mode == 'kill' else 71), 'protocol crash exit')
        active.stop(kill=True); del workers[node]
        receipt['crash'] = dict(node=node, pid=active.proc.pid, cut=cut, mode=mode, exitCode=code, observed=reached)
        receipt['retained'] = recovery.archive(root, node)
    try:
        q.command(['java', '-cp', cp, q.PACKAGE + 'admission.PublicRuntimeConsumer', root, 'setup'], root, 'public-bootstrap')
        rules = []
        if case == 'competing-campaigns':
            rules = [f'{a} {b} BEFORE_REQUEST_WRITE *' for a in NODES for b in NODES if a != b]
        elif case in NETWORK:
            barrier = 'BEFORE_REQUEST_WRITE' if case == 'asymmetric-requests' else 'AFTER_RESPONSE_READ'
            rules = [f'node-1 {peer} {barrier} *' for peer in NODES if peer != 'node-1']
        network(root, rules); receipt['rules'] = rules
        snapshot = case.startswith('snapshot-')
        for node in NODES[:2] if snapshot else NODES: start(node)
        if case == 'competing-campaigns':
            fault.wait_for(lambda: own_campaigns(root), 'isolated voters did not campaign')
            receipt['isolatedThrough'] = {node: fault.rows(root, node)[-1]['order'] for node in NODES}
            network(root, [])
        elif case in NETWORK:
            # A directed graph need not permit the selected pair's two-way basis fetch.
            # Establish actual traffic in both directions, then heal before requiring progress.
            fault.wait_for(lambda: directional_observed(root), 'directional fault/reverse traffic never exercised')
            receipt['faultThrough'] = {node: fault.rows(root, node)[-1]['order'] for node in NODES}
            network(root, [])
        old, active = fault.leader(workers)
        for tag in (10, 20, 30): write(active, tag)
        read(active)
        if case in NETWORK:
            active.stop(); del workers[old]; receipt['retained'] = recovery.archive(root, old)
            start(old, 2)
        elif case in TAILS:
            # Local ACCEPT is durable; no transport send for this value can precede this cut.
            arm(old, 'ACCEPT_AFTER_FORCE', 'kill')
            docs = [dict(id=40+i, value=f'minority-{40+i}') for i in (0, 1)]
            pending = active.send('addAll', documents=docs); receipt['target'] = history[-1]['opId']
            crash(old, 'ACCEPT_AFTER_FORCE', 'kill')
            need(pending.result(timeout=5) is None, 'interrupted minority mutation returned a response')
            if case == 'minority-selected':
                removed = next(iter(workers)); workers.pop(removed).stop()
                network(root, [f'{a} {b} BEFORE_REQUEST_WRITE *' for a in NODES for b in NODES if a != b and removed in (a, b)])
                start(old, 2); expected.extend(docs)
                new, active = fault.leader(workers); read(active); write(active, 50)
                network(root, []); start(removed, 2)
            else:
                new, active = fault.leader(workers); read(active); write(active, 50)
                start(old, 2)
            receipt['selectedLeader'] = new
        else:
            kind, mode = case.rsplit('-', 1); cut = CUTS[kind]
            if kind == 'basis':
                index = active.call('status')['provenIndex']
                # A stale third voter may still export a one-chunk genesis basis.
                # Choose an actual proven-prefix holder before interrupting its continuation.
                target = fault.wait_for(lambda: next((n for n, w in workers.items() if n != old
                                        and w.call('status')['provenIndex'] >= index), None), 'no follower retained the multichunk basis')
                arm(target, cut, mode)
                active.stop(kill=True); del workers[old]
                # This first stopped node remains absent until the interrupted survivor recovers.
            else:
                # Wait for the stable proven cut to become an exportable source, so the
                # requested partial-transfer cut cannot hit an earlier tiny activation image.
                index = active.call('status')['provenIndex']
                fault.wait_for(lambda: any(r['event'] == 'RECOVERY_FLOOR' and r['index'] >= index
                                          for r in fault.rows(root, old)), 'stable snapshot source not retained')
                target = 'node-3'; arm(target, cut, mode); start(target)
            crash(target, cut, mode); start(target, 2)
            if kind != 'basis':
                active.stop(); del workers[old]
            new, active = fault.leader(workers); read(active); write(active, 50)
            start(old, 2)
        final, active = fault.leader(workers); read(active)
        receipt.update(oldLeader=old, finalLeader=final, expected=expected)
    except BaseException as error: receipt['failure'] = str(error); raise
    finally:
        errors = []
        for worker in workers.values():
            try: worker.stop()
            except Exception as error: errors.append(str(error))
        if errors: receipt['cleanupErrors'] = errors
        save(root / 'history.json', history); save(root / 'receipt.json', receipt)
        need(not errors, 'public protocol worker cleanup: ' + str(errors))
    try:
        traces = physical.traces_at(root)
        receipt['history'] = public_history.check(history)
        receipt['physical'] = physical.physical(root, history, traces)
        receipt['scenario'] = evidence.validate(root, traces, history, receipt)
        receipt['negatives'] = physical.negatives(root, history) + evidence.negatives(root, traces, history, receipt)
        receipt['status'] = 'PASS'
    except BaseException as error: receipt['failure'] = str(error); raise
    finally: save(root / 'receipt.json', receipt)
    return receipt


def run(output, only=None):
    root = Path(output).resolve(); root.mkdir(parents=True, exist_ok=False)
    receipt = dict(status='FAIL', execution='public-protocol-recovery', paidCloud=False, cases=[],
                   scope='targeted-case' if only else 'complete-11-case-matrix')
    try:
        need(only is None or only in CASES, 'unknown public protocol case')
        receipt['head'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        paths = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode().split('\0')
        inventory = {p: storage.sha((ROOT/p).read_bytes()) for p in sorted(set(paths)) if p and (ROOT/p).is_file()}
        save(root/'source-inventory.json', inventory); receipt['sourceInventorySha256'] = storage.sha(storage.canonical(inventory))
        receipt['jars'] = {p.name: storage.sha(p.read_bytes()) for p in (CORE, REPLICATION)}
        module = ROOT/'general-search-engine-replication'; java = ROOT/'scripts/v51/java'
        need(all(p.stat().st_mtime_ns <= REPLICATION.stat().st_mtime_ns for p in (module/'src/main').rglob('*.java')), 'package current runtime first')
        classes = root/'consumer'; classes.mkdir(); observer = root/'observer'; observer.mkdir()
        jars = os.pathsep.join(map(str, (CORE, REPLICATION)))
        sources = [module/'src/test/java/io/github/patricklfdm/generalsearch/admission/AdmissionJson.java',
                   java/'PublicRuntimeConsumer.java', java/'PublicQualificationConsumer.java']
        q.command(['javac', '--release', '21', '-proc:none', '-cp', jars, '-d', classes, *sources], root, 'compile-consumer')
        q.command(['javac', '--release', '21', '-proc:none', '-cp', jars+os.pathsep+str(classes), '-d', observer, java/'V51PublicWorker.java'], root, 'compile-observer')
        cp = os.pathsep.join(map(str, (CORE, REPLICATION, classes, observer)))
        for case in CASES:
            if only and case != only: continue
            try:
                result = scenario(root/case, cp, case)
                receipt['cases'].append(dict(case=case, status=result['status']))
            except Exception as error:
                # Each case owns fresh processes/directories. Retain every failed receipt
                # and exercise the remaining schedules before failing the complete gate.
                receipt['cases'].append(dict(case=case, status='FAIL', failure=str(error)))
            print(json.dumps(receipt['cases'][-1]), flush=True)
        need(all(case['status'] == 'PASS' for case in receipt['cases']), 'public protocol cases failed: ' +
             ', '.join(case['case'] for case in receipt['cases'] if case['status'] != 'PASS'))
        receipt['status'] = 'PASS'
    except BaseException as error: receipt['failure'] = str(error); raise
    finally: save(root/'receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('output'); parser.add_argument('--only')
    args = parser.parse_args(); run(args.output, args.only)
