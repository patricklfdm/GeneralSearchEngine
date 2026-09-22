"""Public PREPARE voter crashes: no private election or retained-authority edits."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from . import public_qualification_harness as q, public_qualification_evidence as physical
from . import public_fault_harness as fault, public_recovery_harness as recovery
from . import public_protocol_harness as protocol, public_promise_evidence as evidence
from . import public_history, storage_inspector as storage
from .storage_harness import ROOT, need, save
from scripts.v50.offline_harness import CORE, REPLICATION

CUTS = {'before-write': 'PROMISE_BEFORE_WRITE', 'after-write': 'PROMISE_AFTER_WRITE',
        'after-force': 'PROMISE_AFTER_FORCE', 'before-ack': 'PROMISE_BEFORE_ACK',
        'basis-ack': 'BASIS_BEFORE_ACK', 'before-reply': 'WIRE_BEFORE_RESPONSE_WRITE_PREPARE'}
CASES = tuple(f'{cut}-{mode}' for cut in CUTS for mode in ('halt', 'kill'))


def scenario(root, cp, case):
    root.mkdir(); workers = {}; history = []; expected = []
    boundary, mode = case.rsplit('-', 1); cut = CUTS[boundary]; target = 'node-3'
    receipt = dict(status='FAIL', case=case, publicRuntime=True)
    # Public bootstrap seals a longer election timer on this voter. It still votes,
    # recovers and publishes normally, but the interrupted promise is to a peer.
    (root/'promise-evidence').touch(); (root/'chunk-bytes.txt').write_text('4096\n')
    def start(node, generation=1):
        workers[node] = q.Worker(root, node, cp, history, generation)
        return workers[node]
    def write(active, tag):
        docs = [dict(id=tag+i, value=f'tag-{tag+i}-'+'x'*512) for i in (0, 1)]
        active.call('addAll', documents=docs); expected.extend(docs)
        return history[-1]['opId']
    try:
        q.command(['java', '-cp', cp, q.PACKAGE+'admission.PublicRuntimeConsumer', root, 'setup'], root, 'public-bootstrap')
        for node in protocol.NODES: start(node)
        old, active = fault.leader(workers); need(old != target, 'delayed voter campaigned')
        for tag in (10, 20, 30): write(active, tag)
        protocol.read_after_recovery(workers, expected)
        index = active.call('status')['provenIndex']
        fault.wait_for(lambda: workers[target].call('status')['provenIndex'] >= index, 'promise voter did not retain seed prefix')
        # The prior leader is absent until a read AND write succeed with the
        # restarted voter in the only available two-member majority.
        fault.replace(root/(target+'-arm.txt'), cut+'\n'+mode+'\n')
        active.stop(kill=True); del workers[old]
        reached = fault.wait_for(lambda: next((r for r in fault.rows(root, target) if r['event'] == 'CUT_REACHED'), None), 'promise cut not reached: '+cut)
        victim = workers[target]
        need(reached['cut'] == cut and reached['pid'] == victim.proc.pid, 'wrong promise process cut')
        if mode == 'kill': victim.proc.kill()
        code = victim.proc.wait(timeout=10); need(code == (-9 if mode == 'kill' else 71), 'promise crash exit')
        victim.stop(kill=True); del workers[target]
        receipt['crash'] = dict(node=target, pid=victim.proc.pid, cut=cut, mode=mode, exitCode=code, observed=reached)
        receipt['retained'] = recovery.archive(root, target)
        start(target, 2)
        new, active = protocol.read_after_recovery(workers, expected)
        receipt['postRestartWrite'] = write(active, 50)
        protocol.read_after_recovery(workers, expected)
        start(old, 2)
        final, active = protocol.read_after_recovery(workers, expected)
        receipt.update(oldLeader=old, majorityLeader=new, finalLeader=final, expected=expected)
    except BaseException as error: receipt['failure'] = str(error); raise
    finally:
        errors = []
        for worker in workers.values():
            try: worker.stop()
            except Exception as error: errors.append(str(error))
        if errors: receipt['cleanupErrors'] = errors
        save(root/'history.json', history); save(root/'receipt.json', receipt)
        need(not errors, 'public promise cleanup: '+str(errors))
    try:
        traces = physical.traces_at(root)
        receipt['history'] = public_history.check(history)
        receipt['physical'] = physical.physical(root, history, traces)
        receipt['scenario'] = evidence.validate(root, traces, history, receipt)
        receipt['negatives'] = physical.negatives(root, history)+evidence.negatives(root, traces, history, receipt)
        receipt['status'] = 'PASS'
    except BaseException as error: receipt['failure'] = str(error); raise
    finally: save(root/'receipt.json', receipt)
    return receipt


def run(output, only=None):
    root = Path(output).resolve(); root.mkdir(parents=True, exist_ok=False)
    receipt = dict(status='FAIL', execution='public-promise-crashes', paidCloud=False, cases=[],
                   scope='targeted-case' if only else 'complete-12-case-matrix')
    try:
        need(only is None or only in CASES, 'unknown public promise case')
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
                receipt['cases'].append(dict(case=case, status='FAIL', failure=str(error)))
            print(json.dumps(receipt['cases'][-1]), flush=True)
        need(all(case['status'] == 'PASS' for case in receipt['cases']), 'public promise cases failed: '+
             ', '.join(case['case'] for case in receipt['cases'] if case['status'] != 'PASS'))
        receipt['status'] = 'PASS'
    except BaseException as error: receipt['failure'] = str(error); raise
    finally: save(root/'receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('output'); parser.add_argument('--only')
    args = parser.parse_args(); run(args.output, args.only)
