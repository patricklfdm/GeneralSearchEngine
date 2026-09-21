"""Public recovery/lifecycle qualification with owned JVMs and retained failed evidence."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import time
from . import controls, public_history, public_qualification_harness as q, public_qualification_evidence as physical
from . import public_fault_harness as fault, public_recovery_evidence as evidence, storage_inspector as storage
from .storage_harness import ROOT, need, save
from scripts.v50.offline_harness import CORE, REPLICATION

PROCESS_CASES = ('import-halt', 'import-kill', 'cancel-queued', 'cancel-forced', 'close-pinned')
ADMISSION_CASES = ('missing-promise', 'missing-acceptance', 'copied-voter', 'copied-path')
CASES = (*PROCESS_CASES, *ADMISSION_CASES, 'cursor-rebuild')


def archive(root, node):
    before = storage.inventory(root / node); inspected = storage.inspect(root / node)
    path = root / 'before-reopen.tar.gz'
    with tarfile.open(path, 'w:gz') as tar: tar.add(root / node, arcname=node)
    with tarfile.open(path) as tar:
        saved = {m.name.removeprefix(node + '/'): dict(size=m.size, sha256=storage.sha(tar.extractfile(m).read()))
                 for m in tar.getmembers() if m.isfile()}
    need(before == saved, 'pre-reopen archive differs')
    return dict(node=node, inventory=before, inspection=inspected, sha256=storage.sha(path.read_bytes()))


def process_case(root, cp, control_cp, case):
    root.mkdir(); workers = {}; history = []; receipt = dict(status='FAIL', case=case, publicRuntime=True)
    expected = []; initial = []; pending = None
    def worker(node, generation=1): return q.Worker(root, node, cp, history, generation, consumer='lifecycle')
    def cut(node):
        return fault.wait_for(lambda: next((r for r in fault.rows(root, node) if r['event'] == 'CUT_REACHED'), None), 'lifecycle cut not reached')
    def docs(tag): return [dict(id=tag, value=f'tag-{tag}'), dict(id=tag+1, value=f'tag-{tag+1}')]
    try:
        imported = case.startswith('import-')
        if imported:
            result = q.command(['java', '-cp', control_cp, q.PACKAGE + 'admission.PublicImportControl', root], root, 'published-import')
            need('coreSource=' + str(controls_path()) in result.stderr.splitlines(), 'wrong import control')
            reference = json.loads(result.stdout); initial = reference['documents']; expected += initial
            receipt['sourceBackupBefore'] = storage.inventory(root / 'import-backup')
        q.command(['java', '-cp', cp, q.PACKAGE + 'admission.PublicRuntimeConsumer', root, 'setup-import' if imported else 'setup'], root, 'public-bootstrap')
        if imported: receipt['genesis'] = evidence.imported(root, reference)
        for node in ('node-1', 'node-2', 'node-3'): workers[node] = worker(node)
        old, active = fault.leader(workers)
        for tag in (10, 20, 30): active.call('addAll', documents=docs(tag)); expected += docs(tag)
        need(active.call('read')['documents'] == expected, 'initial public projection')
        if imported:
            mode = case.removeprefix('import-')
            fault.replace(root / (old + '-arm.txt'), 'BEFORE_PUBLISH\n' + mode + '\n')
            pending = active.send('addAll', documents=docs(40)); reached = cut(old)
            need(reached['cut'] == 'BEFORE_PUBLISH' and reached['pid'] == active.proc.pid, 'import crash boundary')
            if mode == 'kill': active.proc.kill()
            code = active.proc.wait(timeout=10); need(code == (-9 if mode == 'kill' else 71), 'import crash exit')
            active.stop(kill=True); del workers[old]; need(pending.result(timeout=5) is None, 'lost mutation response fabricated')
            receipt['crash'] = dict(pid=active.proc.pid, mode=mode, exitCode=code, observed=reached)
            receipt['retained'] = archive(root, old)
            new, active = fault.leader(workers); need(new != old, 'old process still leads')
            expected += docs(40)
            need(active.call('read')['documents'] == expected, 'import/uncertain chosen prefix lost at failover')
            active.call('addAll', documents=docs(50)); expected += docs(50)
        elif case.startswith('cancel-'):
            boundary = 'READ_CAPTURED' if case == 'cancel-queued' else 'ACCEPT_AFTER_FORCE'
            fault.replace(root / (old + '-arm.txt'), boundary + '\npause\n')
            held = active.send('read') if case == 'cancel-queued' else None
            if held is not None: cut(old)
            pending = active.send('addAll', documents=docs(40)); target = history[-1]['opId']
            if held is None: cut(old)
            fault.wait_for(lambda: any(r['event'] == 'CLIENT_ENQUEUED' and r['opId'] == target for r in fault.rows(root, old)), 'mutation future not exposed')
            cancelled = active.call('cancel', target=target); need(cancelled['cancelled'] is True, 'future not cancelled')
            need(pending.result(timeout=5)['outcome'] == 'CANCELLED', 'cancelled future returned success')
            (root / (old + '-release')).touch()
            if held is not None: need(held.result(timeout=10)['documents'] == expected, 'pinned read changed during queued cancellation')
            else: expected += docs(40)
            active.call('addAll', documents=docs(50)); expected += docs(50)
            need(active.call('read')['documents'] == expected, 'cancellation effect/drain mismatch')
            receipt['target'] = target
        else:
            fault.replace(root / (old + '-arm.txt'), 'READ_CAPTURED\npause\n')
            held = active.send('read'); target = history[-1]['opId']; cut(old)
            close = active.send('closeHandle').result(timeout=20)
            need(close['outcome'] == 'NOT_APPLICABLE' and close.get('reasonCode') == 'DEADLINE_EXCEEDED', 'close bypassed pinned read')
            duplicate = active.send('duplicateStart').result(timeout=20)
            need(duplicate['outcome'] == 'NOT_APPLICABLE' and duplicate.get('reasonCode') == 'STORAGE_FAILURE', 'close released owned directory')
            denied = active.send('addAll', documents=docs(40)).result(timeout=10)
            need(denied['outcome'] == 'NOT_SUBMITTED' and denied.get('reasonCode') == 'CLOSED', 'closing handle admitted mutation')
            (root / (old + '-release')).touch(); need(held.result(timeout=10)['documents'] == expected, 'close destroyed pinned view')
            active.call('closeHandle'); active.call('closeHandle'); active.call('duplicateStart')
            receipt['target'] = target
        if old in workers:
            workers.pop(old).stop(); receipt['retained'] = archive(root, old)
        workers[old] = worker(old, 2)
        final_node, final = fault.leader(workers)
        need(final.call('read')['documents'] == expected, 'retained public restart changed application')
        receipt.update(oldLeader=old, finalLeader=final_node, expected=expected)
        if imported:
            receipt['sourceBackupAfter'] = storage.inventory(root / 'import-backup')
            need(receipt['sourceBackupBefore'] == receipt['sourceBackupAfter'], 'import source modified')
    except BaseException as error: receipt['failure'] = str(error); raise
    finally:
        for node in workers: (root / (node + '-release')).touch()
        errors = []
        for own in workers.values():
            try: own.stop()
            except Exception as error: errors.append(str(error))
        if errors: receipt['cleanupErrors'] = errors
        save(root / 'history.json', history); save(root / 'receipt.json', receipt)
        need(not errors, 'lifecycle worker cleanup: ' + str(errors))
    try:
        application = [h for h in history if h['kind'] in ('read', 'addAll')]
        receipt['history'] = public_history.check(application, initial_documents=initial)
        traces = physical.traces_at(root)
        receipt['physical'] = physical.physical(root, application, traces)
        receipt['negatives'] = physical.negatives(root, application, initial_documents=initial)
        if not case.startswith('import-'):
            receipt['lifecycle'] = evidence.lifecycle(history, traces, case, receipt['target'])
            receipt['negatives'] += evidence.negatives(history, traces, case, receipt['target'])
        else:
            for name, changed in [('missing-import', dict(reference, documents=[])),
                                  ('changed-import-sequence', dict(reference, sequence=reference['sequence']+1)),
                                  ('reordered-import', dict(reference, documents=initial[::-1]))]:
                try: evidence.imported(root, changed)
                except ValueError as error: receipt['negatives'].append(dict(case=name, status='REJECTED', reason=str(error)))
                else: raise ValueError('import oracle admitted ' + name)
        receipt['status'] = 'PASS'
    except BaseException as error: receipt['failure'] = str(error); raise
    finally: save(root / 'receipt.json', receipt)
    return receipt


def admission_case(root, cp, case):
    root.mkdir(); receipt = dict(status='FAIL', case=case, publicRuntime=True)
    try:
        q.command(['java', '-cp', cp, q.PACKAGE + 'admission.PublicRuntimeConsumer', root, 'setup'], root, 'public-bootstrap')
        target = root / 'node-1'; original = storage.inventory(target)
        if case.startswith('missing-'):
            member = 'promises.gsr' if case == 'missing-promise' else 'accepted.gsr'
            (target / member).rename(root / ('removed-' + member))
        elif case == 'copied-voter':
            target.rename(root / 'retained-node-1'); shutil.copytree(root / 'node-2', target)
        else:
            target = root / 'copied-node-1'; shutil.copytree(root / 'node-1', target)
        before = storage.inventory(target); results = []
        save(root / 'fault-inventory.json', dict(original=original, before=before))
        with tarfile.open(root / 'rejected-authority.tar.gz', 'w:gz') as tar: tar.add(target, arcname=target.name)
        for i in (1, 2):
            args = ['java', '-cp', cp, q.PACKAGE + 'admission.PublicLifecycleConsumer', root, '1', 'probe']
            if case == 'copied-path': args.append(target.name)
            results.append(json.loads(q.command(args, root, f'probe-{i}').stdout))
            need(before == storage.inventory(target), 'failed startup mutated authority')
            save(root / 'probe-results.json', results)
        after = storage.inventory(target)
        receipt.update(original=original, before=before, after=after, attempts=results, validation=evidence.admission(before, after, results), status='PASS')
    except BaseException as error: receipt['failure'] = str(error); raise
    finally: save(root / 'receipt.json', receipt)
    return receipt


def controls_path(): return ROOT / 'target/v51-controls/general-search-engine-4.4.0.jar'


def cursor_case(root, cp, control_cp):
    root.mkdir(); receipt = dict(status='FAIL', case='cursor-rebuild', publicRuntime=True)
    try:
        q.command(['java', '-cp', cp, q.PACKAGE + 'admission.PublicCursorConsumer', root, 'setup'], root, 'public-bootstrap')
        actual = q.command(['java', '-cp', cp, q.PACKAGE + 'admission.PublicCursorConsumer', root, 'candidate'], root, 'candidate')
        baseline = q.command(['java', '-cp', control_cp, q.PACKAGE + 'admission.PublicCursorConsumer', root, 'control'], root, 'published-v44')
        need('coreSource=' + str(CORE) in actual.stderr.splitlines() and 'coreSource=' + str(controls_path()) in baseline.stderr.splitlines(), 'wrong cursor core source')
        candidate, control = json.loads(actual.stdout), json.loads(baseline.stdout)
        receipt.update(candidate=candidate, control=control, validation=evidence.cursors(candidate, control))
        receipt['authority'] = {f'node-{i}': storage.inspect(root / f'node-{i}') for i in (1, 2, 3)}
        receipt['status'] = 'PASS'
    except BaseException as error: receipt['failure'] = str(error); raise
    finally: save(root / 'receipt.json', receipt)
    return receipt


def run(output, only=None):
    root = Path(output).resolve(); root.mkdir(parents=True, exist_ok=False)
    receipt = dict(status='FAIL', execution='public-recovery-lifecycle', paidCloud=False, cases=[], scope='targeted-case' if only else 'complete-10-case-matrix')
    try:
        need(only is None or only in CASES, 'unknown recovery/lifecycle case')
        receipt['head'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        paths = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode().split('\0')
        inventory = {p: storage.sha((ROOT / p).read_bytes()) for p in sorted(set(paths)) if p and (ROOT / p).is_file()}
        save(root / 'source-inventory.json', inventory); receipt['sourceInventorySha256'] = storage.sha(storage.canonical(inventory))
        receipt['jars'] = {p.name: storage.sha(p.read_bytes()) for p in (CORE, REPLICATION)}
        module = ROOT / 'general-search-engine-replication'; java = ROOT / 'scripts/v51/java'
        need(all(p.stat().st_mtime_ns <= REPLICATION.stat().st_mtime_ns for p in (module / 'src/main').rglob('*.java')), 'package current runtime first')
        classes = root / 'consumer'; classes.mkdir(); observer = root / 'observer'; observer.mkdir()
        jars = os.pathsep.join(map(str, (CORE, REPLICATION)))
        json_source = module / 'src/test/java/io/github/patricklfdm/generalsearch/admission/AdmissionJson.java'
        consumers = [java / (name + '.java') for name in ('PublicRuntimeConsumer', 'PublicLifecycleConsumer', 'PublicCursorConsumer')]
        q.command(['javac', '--release', '21', '-proc:none', '-cp', jars, '-d', classes, json_source, *consumers], root, 'compile-consumer')
        q.command(['javac', '--release', '21', '-proc:none', '-cp', jars + os.pathsep + str(classes), '-d', observer, java / 'V51PublicWorker.java'], root, 'compile-observer')
        cp = os.pathsep.join(map(str, (CORE, REPLICATION, classes, observer)))
        controls.resolve(ROOT / 'target/v51-controls'); control = controls_path()
        control_classes = root / 'control'; control_classes.mkdir(); control_cp = os.pathsep.join(map(str, (control, REPLICATION, control_classes)))
        q.command(['javac', '--release', '21', '-proc:none', '-cp', control_cp, '-d', control_classes,
                   json_source, java / 'PublicRuntimeConsumer.java', java / 'PublicImportControl.java', java / 'PublicCursorConsumer.java'], root, 'compile-control')
        receipt['publishedControlSha256'] = storage.sha(control.read_bytes())
        for case in CASES:
            if only and case != only: continue
            if case in PROCESS_CASES: result = process_case(root / case, cp, control_cp, case)
            elif case in ADMISSION_CASES: result = admission_case(root / case, cp, case)
            else: result = cursor_case(root / case, cp, control_cp)
            receipt['cases'].append(dict(case=case, status=result['status'])); print(json.dumps(receipt['cases'][-1]), flush=True)
        receipt['status'] = 'PASS'
    except BaseException as error: receipt['failure'] = str(error); raise
    finally: save(root / 'receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('output'); parser.add_argument('--only')
    args = parser.parse_args(); run(args.output, args.only)
