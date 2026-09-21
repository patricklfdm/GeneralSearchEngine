"""Public two-source reclamation, real process cuts and retained-disk recovery."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from . import public_qualification_harness as q, public_qualification_evidence as physical
from . import public_fault_harness as fault, public_recovery_harness as recovery
from . import public_protocol_harness as protocol, public_history, storage_inspector as storage
from . import public_reclamation_evidence as evidence
from .storage_harness import ROOT, need, save
from scripts.v50.offline_harness import CORE, REPLICATION

CUTS = ('FLOOR_BEFORE_WRITE', 'FLOOR_AFTER_FORCE', 'FLOOR_BEFORE_ACK',
        'DELETE_AFTER_FILE', 'DELETE_AFTER_DIRECTORY', 'DELETE_AFTER_ROOT_TRUNCATE')
CASES = tuple(f'{cut.lower()}-{mode}' for cut in CUTS for mode in ('halt', 'kill'))
READ_REJECTIONS = ('NOT_LEADER', 'NOT_READY', 'QUORUM_UNAVAILABLE', 'STALE_EPOCH', 'DEADLINE_EXCEEDED')


def scenario(root, cp, cut, mode):
    root.mkdir(); (root/'reclamation-evidence').touch()
    history = []; workers = {}; expected = []
    receipt = dict(status='FAIL', publicRuntime=True, case=cut.lower()+'-'+mode, cut=cut, mode=mode)
    def start(node, generation=1):
        workers[node] = q.Worker(root, node, cp, history, generation); return workers[node]
    def docs(tag): return [dict(id=tag+i, value=f'reclamation-{tag+i}') for i in (0, 1)]
    def write(active, tag): active.call('addAll', documents=docs(tag)); expected.extend(docs(tag))
    def read():
        # A restarted voter may advance the ballot between the role hint and a
        # read's dispatch. Keep every rejected call; only reads are retried.
        for _ in range(4):
            node, worker = fault.leader(workers)
            result = worker.send('read').result(timeout=35)
            need(result is not None, 'public read disconnected')
            if result['outcome'] == 'SUCCESS':
                need(result['documents'] == expected, 'reclaimed public history changed')
                return node, worker
            need(result['outcome'] == 'NOT_APPLICABLE' and result.get('reasonCode') in READ_REJECTIONS,
                 'unexpected public read failure: '+str(result))
        raise ValueError('public read did not stabilize after retained restart')
    def floor(node, index):
        return fault.wait_for(lambda: next((r for r in reversed(fault.rows(root, node))
            if r['event'] == 'RECOVERY_FLOOR' and r['index'] >= index), None), 'public recovery floor did not converge')
    try:
        q.command(['java', '-cp', cp, q.PACKAGE+'admission.PublicRuntimeConsumer', root, 'setup'], root, 'public-bootstrap')
        rules = [f'{a} {b} BEFORE_REQUEST_WRITE {kind}' for a in protocol.NODES for b in protocol.NODES
                 if a != b for kind in ('SOURCE_OFFER', 'SOURCE_CHUNK')]
        protocol.network(root, rules)
        for node in protocol.NODES: start(node)
        old, active = fault.leader(workers)
        for tag in (10, 20, 30): write(active, tag)
        old, active = read()
        fault.wait_for(lambda: any(r['event'] == 'NETWORK_DROP' and 'SOURCE_' in r.get('rule', '')
                                  for r in fault.rows(root, old)), 'source block not exercised')
        receipt['blockedThrough'] = {n: fault.rows(root, n)[-1]['order'] for n in workers}
        need(all(not (root/n/'recovery-floor.gsr').exists() for n in workers), 'floor created while all peer sources were blocked')
        initial_cut = active.call('status')['provenIndex']; receipt['seedIndex'] = initial_cut
        if cut != 'DELETE_AFTER_ROOT_TRUNCATE':
            protocol.network(root, [])
            baseline = floor(old, initial_cut); receipt['baseline'] = baseline
            write(active, 40)
        # Root truncation targets the first cleanup, while real root journal rows exist.
        # Other cuts target a subsequent turnover after a complete earlier cleanup.
        fault.replace(root/(old+'-arm.txt'), 'STORAGE_CUT:'+cut+'\n'+mode+'\n')
        pending = None
        if cut == 'DELETE_AFTER_ROOT_TRUNCATE': protocol.network(root, [])
        else:
            pending = active.send('read'); receipt['trigger'] = history[-1]['opId']
        reached = fault.wait_for(lambda: next((r for r in fault.rows(root, old) if r['event'] == 'CUT_REACHED'), None), 'reclamation cut not reached: '+cut)
        need(reached['cut'] == 'STORAGE_CUT:'+cut and reached['pid'] == active.proc.pid, 'wrong reclamation boundary')
        if mode == 'kill': active.proc.kill()
        code = active.proc.wait(timeout=10); need(code == (-9 if mode == 'kill' else 71), 'wrong reclamation exit')
        active.stop(kill=True); del workers[old]
        if pending is not None:
            result = pending.result(timeout=5)
            need(result is None or result['outcome'] == 'SUCCESS' or result['outcome'] == 'NOT_APPLICABLE'
                 and result.get('reasonCode') in READ_REJECTIONS, 'reclamation trigger failed: '+str(result))
        receipt['crash'] = dict(node=old, pid=active.proc.pid, cut='STORAGE_CUT:'+cut, mode=mode, exitCode=code, observed=reached)
        receipt['retained'] = recovery.archive(root, old)
        new, active = read(); write(active, 50)
        start(old, 2)
        # Require the interrupted disk to participate in a subsequent majority.
        active.stop(); del workers[new]
        final, active = read(); write(active, 60)
        start(new, 2); final, active = read()
        final_index = active.call('status')['provenIndex']
        receipt['recoveredFloor'] = floor(old, final_index)
        receipt.update(oldLeader=old, failoverLeader=new, finalLeader=final, expected=expected)
    except BaseException as error: receipt['failure'] = str(error); raise
    finally:
        errors = []
        for worker in workers.values():
            try: worker.stop()
            except Exception as error: errors.append(str(error))
        if errors: receipt['cleanupErrors'] = errors
        save(root/'history.json', history); save(root/'receipt.json', receipt)
        need(not errors, 'public reclamation cleanup: '+str(errors))
    try:
        traces = physical.traces_at(root)
        receipt['history'] = public_history.check(history)
        receipt['physical'] = physical.physical(root, history, traces)
        receipt['reclamation'] = evidence.validate(root, traces, history, receipt)
        receipt['negatives'] = physical.negatives(root, history)+evidence.negatives(root, traces, history, receipt)
        receipt['status'] = 'PASS'
    except BaseException as error: receipt['failure'] = str(error); raise
    finally: save(root/'receipt.json', receipt)
    return receipt


def run(output, only=None):
    root = Path(output).resolve(); root.mkdir(parents=True, exist_ok=False)
    receipt = dict(status='FAIL', execution='public-two-source-reclamation', paidCloud=False, cases=[],
                   scope='targeted-case' if only else 'complete-12-case-matrix')
    try:
        need(only is None or only in CASES, 'unknown reclamation case')
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
        for cut in CUTS:
            for mode in ('halt', 'kill'):
                case = cut.lower()+'-'+mode
                if only and case != only: continue
                try:
                    result = scenario(root/case, cp, cut, mode)
                    receipt['cases'].append(dict(case=case, status=result['status']))
                except Exception as error: receipt['cases'].append(dict(case=case, status='FAIL', failure=str(error)))
                print(json.dumps(receipt['cases'][-1]), flush=True)
        need(all(c['status'] == 'PASS' for c in receipt['cases']), 'reclamation cases failed: '+', '.join(c['case'] for c in receipt['cases'] if c['status'] != 'PASS'))
        receipt['status'] = 'PASS'
    except BaseException as error: receipt['failure'] = str(error); raise
    finally: save(root/'receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('output'); parser.add_argument('--only', choices=CASES)
    args = parser.parse_args(); run(args.output, args.only)
