"""Public fault matrix: owned TCP partitions, read fencing and mutation crashes."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import time
from . import public_qualification_harness as q, public_qualification_evidence as evidence, public_history
from . import public_fault_evidence as faults, storage_inspector as storage
from .storage_harness import ROOT, need, save
from scripts.v50.offline_harness import CORE, REPLICATION


def rows(root, node):
    # A writer may currently have appended only part of the last JSON line.
    raw = (root / (node + '-trace.jsonl')).read_text()
    return [json.loads(line) for line in raw.split('\n')[:-1]]


def replace(path, text):
    temp = path.with_suffix('.tmp'); temp.write_text(text); temp.replace(path)


def partition(root, isolated=None):
    nodes = [f'node-{i}' for i in (1, 2, 3)]
    replace(root / 'network-blocks.txt', ''.join(f'{a} {b}\n' for a in nodes for b in nodes
                                              if a != b and isolated in (a, b)))


def wait_for(test, message, seconds=40):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = test()
        if result: return result
        time.sleep(.05)
    raise ValueError(message)


def leader(workers):
    def ready():
        statuses = {n: w.call('status') for n, w in workers.items()}
        need(all(s['state'] != 'FAILED' for s in statuses.values()), 'public voter failed: ' + str(statuses))
        return next(((n, workers[n]) for n, s in statuses.items() if s['state'] == 'LEADER_READY'), None)
    return wait_for(ready, 'surviving public majority did not activate')


def fenced(root, cp, boundary):
    root.mkdir(); workers = {}; history = []; receipt = dict(status='FAIL', boundary=boundary)
    # Freeze a longer read deadline into this fixture's public bootstrap policy so
    # the deterministic pause tests epoch fencing, not accidental deadline expiry.
    (root / 'operation-timeout.txt').write_text('60000\n')
    try:
        q.command(['java', '-cp', cp, q.PACKAGE + 'admission.PublicRuntimeConsumer', root, 'setup'], root, 'bootstrap')
        for i in (1, 2, 3): workers[f'node-{i}'] = q.Worker(root, f'node-{i}', cp, history)
        old, active = leader(workers); expected = []
        for i in (1, 2, 3):
            documents = [dict(id=i * 2, value=f'seed-{i}-a'), dict(id=i * 2 + 1, value=f'seed-{i}-b')]
            active.call('addAll', documents=documents); expected += documents
        epoch = active.call('status')['epoch']; held = None; held_id = None
        if boundary:
            replace(root / (old + '-arm.txt'), boundary + '\npause\n')
            held = active.send('read'); held_id = history[-1]['opId']
            wait_for(lambda: any(r['event'] == 'CUT_REACHED' for r in rows(root, old)), 'read did not reach the requested pause')
        partition(root, old); receipt['partitionNanos'] = time.monotonic_ns()
        survivors = {n: w for n, w in workers.items() if n != old}
        new, service = leader(survivors)
        added = [dict(id=20, value='new-majority-a'), dict(id=21, value='new-majority-b')]
        service.call('addAll', documents=added)
        need(service.call('read')['documents'] == expected + added, 'survivor did not publish the majority write')
        if boundary:
            # Permit delayed higher-ballot traffic to reach the paused node. Its
            # public read is still held on the application worker, outside control.
            partition(root)
            wait_for(lambda: any(r['event'] == 'FORCE' and r['kind'] == 'PROMISE' and
                                evidence.authority.f.inspect(evidence.authority.raw(r['record']), 'PROMISE')['epoch'] > epoch
                                for r in rows(root, old)), 'old leader did not force a higher promise')
            partition(root, old)
            (root / (old + '-release')).touch(); result = held.result(timeout=10)
            if boundary == 'READ_CAPTURED':
                need(result is not None and result['outcome'] == 'SUCCESS' and result['documents'] == expected, 'captured overlapping read changed its view')
            else:
                need(result is not None and result['outcome'] == 'NOT_APPLICABLE' and result.get('reasonCode') == 'STALE_EPOCH', 'uncaptured old-epoch read was not fenced')
        denied_read = active.send('read').result(timeout=10)
        denied_write = active.send('addAll', documents=[dict(id=30, value='must-not-appear')]).result(timeout=10)
        need(denied_read is not None and denied_read['outcome'] == 'NOT_APPLICABLE' and denied_read.get('reasonCode') in
             ('NOT_LEADER', 'QUORUM_UNAVAILABLE', 'NOT_READY', 'STALE_EPOCH'), 'isolated leader served a later read')
        need(denied_write is not None and denied_write['outcome'] == 'NOT_SUBMITTED', 'isolated leader admitted a later write')
        receipt['rejections'] = dict(read=denied_read, write=denied_write)
        # Public close, then retained public restart; no controller state repair.
        active.stop(); del workers[old]
        partition(root)
        workers[old] = q.Worker(root, old, cp, history, generation=2)
        for _ in range(3):
            final_node, final = leader(workers)
            result = final.send('read').result(timeout=35)
            if result is not None and result['outcome'] == 'SUCCESS': break
        need(result is not None and result['outcome'] == 'SUCCESS' and result['documents'] == expected + added, 'healed retained group lost public history')
        receipt.update(oldLeader=old, majorityLeader=new, finalLeader=final_node, heldOperation=held_id)
    except BaseException as error:
        receipt['failure'] = str(error); raise
    finally:
        for node in workers: (root / (node + '-release')).touch()
        errors = []
        for worker in workers.values():
            try: worker.stop()
            except Exception as error: errors.append(str(error))
        if errors: receipt['cleanupErrors'] = errors
        save(root / 'history.json', history); save(root / 'receipt.json', receipt)
        need(not errors, 'public fault worker cleanup: ' + str(errors))
    try:
        traces = evidence.traces_at(root)
        need(any(r['event'] == 'NETWORK_DROP' for own in traces.values() for r in own), 'no actual transport drops')
        receipt['history'] = public_history.check(history)
        receipt['physical'] = evidence.physical(root, history)
        receipt['negatives'] = evidence.negatives(root, history)
        if boundary:
            op = next(op for op in history if op['opId'] == held_id)
            own = [r for r in traces[old] if r['generation'] == 1]
            receipt['fence'] = faults.read_fence(own, op, boundary == 'READ_BEFORE_CAPTURE')
            corrupted = copy.deepcopy(own)
            higher = [r for r in corrupted if r['event'] == 'FORCE' and r['kind'] == 'PROMISE' and
                      evidence.authority.f.inspect(evidence.authority.raw(r['record']), 'PROMISE')['epoch'] > epoch]
            corrupted = [r for r in corrupted if r not in higher]
            try: faults.read_fence(corrupted, op, boundary == 'READ_BEFORE_CAPTURE')
            except ValueError as error: receipt['negatives'].append(dict(case='missing-crossing-promise', reason=str(error)))
            else: raise ValueError('fence oracle accepted missing higher promise')
            if boundary == 'READ_CAPTURED':
                # A higher promise can occur between validation and its later, pausable
                # observation. Moving it across validation itself must change the verdict.
                for before_validation in (False, True):
                    changed = copy.deepcopy(traces); own = changed[old]
                    promise = next(r for r in own if r['generation'] == 1 and r['event'] == 'FORCE' and r['kind'] == 'PROMISE'
                                   and evidence.authority.f.inspect(evidence.authority.raw(r['record']), 'PROMISE')['epoch'] > epoch)
                    own.remove(promise)
                    event = 'READ_CAPTURE_VALIDATED' if before_validation else 'READ_CAPTURED'
                    at = next(i for i, r in enumerate(own) if r['generation'] == 1 and r['event'] == event)
                    own.insert(at, promise); counters = {}
                    for r in own:
                        counters[r['pid']] = counters.get(r['pid'], 0) + 1; r['order'] = counters[r['pid']]
                    if before_validation:
                        try: evidence.physical(root, history, changed)
                        except ValueError as error:
                            need('capture after higher promise' in str(error), 'wrong capture negative rejection: ' + str(error))
                            receipt['negatives'].append(dict(case='higher-promise-before-validation', reason=str(error)))
                        else: raise ValueError('oracle admitted capture after higher promise')
                    else:
                        evidence.physical(root, history, changed); receipt['delayedCaptureObservation'] = 'PASS'
        receipt['status'] = 'PASS'
    except BaseException as error: receipt['failure'] = str(error); raise
    finally: save(root / 'receipt.json', receipt)
    return receipt


def run(output, only=None):
    root = Path(output).resolve(); root.mkdir(parents=True, exist_ok=False)
    receipt = dict(status='FAIL', execution='public-fault-matrix-real-tcp', publicRuntime=True, paidCloud=False, cases=[])
    try:
        receipt['head'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        paths = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode().split('\0')
        inventory = {p: storage.sha((ROOT / p).read_bytes()) for p in sorted(set(paths)) if p and (ROOT / p).is_file()}
        save(root / 'source-inventory.json', inventory); receipt['sourceInventorySha256'] = storage.sha(storage.canonical(inventory))
        receipt['jars'] = {p.name: storage.sha(p.read_bytes()) for p in (CORE, REPLICATION)}
        module = ROOT / 'general-search-engine-replication'; java = ROOT / 'scripts/v51/java'
        need(all(p.stat().st_mtime_ns <= REPLICATION.stat().st_mtime_ns for p in (module / 'src/main').rglob('*.java')), 'package current runtime first')
        classes = root / 'consumer'; classes.mkdir(); observer = root / 'observer'; observer.mkdir()
        jars = os.pathsep.join(map(str, (CORE, REPLICATION)))
        q.command(['javac', '--release', '21', '-proc:none', '-cp', jars, '-d', classes,
                   module / 'src/test/java/io/github/patricklfdm/generalsearch/admission/AdmissionJson.java',
                   java / 'PublicRuntimeConsumer.java', java / 'PublicQualificationConsumer.java'], root, 'compile-consumer')
        q.command(['javac', '--release', '21', '-proc:none', '-cp', jars + os.pathsep + str(classes), '-d', observer,
                   java / 'V51PublicWorker.java'], root, 'compile-observer')
        cp = os.pathsep.join(map(str, (CORE, REPLICATION, classes, observer)))
        cases = [(name, None, cut) for name, cut in [('isolated-old-leader', None), ('promise-before-capture', 'READ_BEFORE_CAPTURE'), ('promise-after-capture', 'READ_CAPTURED')]]
        cases += [(mode + '-' + cut.lower(), mode, cut) for mode in ('halt', 'kill') for cut in faults.MUTATION_CUTS]
        need(only is None or only in {name for name, _, _ in cases}, 'unknown selected case')
        receipt['scope'] = 'targeted-case' if only else 'complete-19-case-matrix'
        for name, mode, cut in cases:
            if only and only != name: continue
            case_root = root / name
            result = q.scenario(case_root, cp, cut, mode, mutation_cut=True) if mode else fenced(case_root, cp, cut)
            if mode:
                try:
                    history = json.loads((case_root / 'history.json').read_text())
                    result['milestone'] = faults.mutation_cut(case_root, evidence.traces_at(case_root), history, result['crash'])
                except BaseException as error: result.update(status='FAIL', failure=str(error)); raise
                finally: save(case_root / 'receipt.json', result)
            receipt['cases'].append(dict(name=name, status=result['status'], history=result['history'], physical=result['physical']))
            print(json.dumps(dict(case=name, status=result['status'])), flush=True)
        receipt['status'] = 'PASS'
    except BaseException as error: receipt['failure'] = str(error); raise
    finally: save(root / 'receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('output'); parser.add_argument('--only')
    args = parser.parse_args(); run(args.output, args.only)
