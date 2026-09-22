"""Candidate-owned promise and PREPARE crashes through the public runtime."""
import argparse
import time
from . import public_promise_harness as promise, public_candidate_evidence as evidence
from . import public_qualification_harness as q, public_qualification_evidence as physical
from . import public_fault_harness as fault, public_recovery_harness as recovery
from . import public_protocol_harness as protocol, public_history
from .storage_harness import need, save

CUTS = {'before-write': 'PROMISE_BEFORE_WRITE', 'after-write': 'PROMISE_AFTER_WRITE',
        'after-force': 'PROMISE_AFTER_FORCE', 'before-ack': 'PROMISE_BEFORE_ACK',
        'basis-ack': 'BASIS_BEFORE_ACK', 'before-prepare': 'WIRE_BEFORE_REQUEST_WRITE_PREPARE',
        'after-promise': 'WIRE_AFTER_RESPONSE_READ_PREPARE:PROMISE'}
CASES = tuple(f'{cut}-{mode}' for cut in CUTS for mode in ('halt', 'kill'))


def scenario(root, cp, case):
    root.mkdir(); workers = {}; history = []; starts = []; expected = []
    stage, mode = case.rsplit('-', 1); cut = CUTS[stage]
    receipt = dict(status='FAIL', case=case, publicRuntime=True)
    # The same public sealed policy as the peer-promise suite: node 3 votes
    # normally but does not campaign within this bounded scenario.
    (root/'promise-evidence').touch(); (root/'chunk-bytes.txt').write_text('4096\n')
    def start(node, generation=1):
        began = time.monotonic_ns(); worker = q.Worker(root, node, cp, history, generation)
        workers[node] = worker
        starts.append(dict(node=node, generation=generation, pid=worker.proc.pid, startNanos=began, readyNanos=time.monotonic_ns()))
        return worker
    def write(active, tag):
        docs = [dict(id=tag+i, value=f'tag-{tag+i}-'+'x'*512) for i in (0, 1)]
        active.call('addAll', documents=docs); expected.extend(docs)
        return history[-1]['opId']
    try:
        q.command(['java', '-cp', cp, q.PACKAGE+'admission.PublicRuntimeConsumer', root, 'setup'], root, 'public-bootstrap')
        for node in protocol.NODES: start(node)
        old, active = fault.leader(workers); need(old != 'node-3', 'delayed voter campaigned')
        for tag in (10, 20, 30): write(active, tag)
        protocol.read_after_recovery(workers, expected)
        index = active.call('status')['provenIndex']
        target = next(n for n in ('node-1', 'node-2') if n != old)
        fault.wait_for(lambda: all(workers[n].call('status')['provenIndex'] >= index for n in (target, 'node-3')), 'candidate quorum did not retain seed prefix')
        fault.replace(root/(target+'-arm.txt'), cut+'\n'+mode+'\n')
        active.stop(kill=True); del workers[old]
        reached = fault.wait_for(lambda: next((r for r in fault.rows(root, target) if r['event'] == 'CUT_REACHED'), None), 'candidate cut not reached: '+cut)
        victim = workers[target]
        need(reached['cut'] == cut and reached['pid'] == victim.proc.pid, 'wrong candidate process cut')
        if mode == 'kill': victim.proc.kill()
        code = victim.proc.wait(timeout=10); need(code == (-9 if mode == 'kill' else 71), 'candidate crash exit')
        victim.stop(kill=True); del workers[target]
        receipt['crash'] = dict(node=target, pid=victim.proc.pid, cut=cut, mode=mode, exitCode=code, observed=reached)
        receipt['retained'] = recovery.archive(root, target)
        start(target, 2)
        new, active = protocol.read_after_recovery(workers, expected)
        need(new == target, 'restarted candidate did not regain leadership')
        receipt['postRestartWrite'] = write(active, 50)
        protocol.read_after_recovery(workers, expected)
        start(old, 2)
        final, active = protocol.read_after_recovery(workers, expected)
        receipt.update(oldLeader=old, recoveredLeader=new, finalLeader=final, expected=expected)
    except BaseException as error: receipt['failure'] = str(error); raise
    finally:
        errors = []
        for worker in workers.values():
            try: worker.stop()
            except Exception as error: errors.append(str(error))
        if errors: receipt['cleanupErrors'] = errors
        save(root/'worker-starts.json', starts); save(root/'history.json', history); save(root/'receipt.json', receipt)
        need(not errors, 'public candidate cleanup: '+str(errors))
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
    return promise.run_matrix(output, only, cases=CASES, scenario_runner=scenario, execution='public-candidate-crashes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('output'); parser.add_argument('--only')
    args = parser.parse_args(); run(args.output, args.only)
