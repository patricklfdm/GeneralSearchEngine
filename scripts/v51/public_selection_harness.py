"""Public frozen-quorum selection and delayed exchanges across real elections."""
import argparse
import json
import time
from . import public_qualification_harness as q, public_qualification_evidence as physical
from . import public_fault_harness as fault, public_protocol_harness as protocol
from . import public_promise_harness as matrix, public_recovery_harness as recovery
from . import public_history, storage_inspector as storage
from .storage_harness import need, save

CASES = ('duplicate-prepare', 'higher-ballot-accept', 'higher-ballot-proof',
         'hidden-proof', 'lagging-candidate', 'epoch-during-basis')
CUTS = {'higher-ballot-accept': 'WIRE_AFTER_RESPONSE_READ_ACCEPT',
        'higher-ballot-proof': 'WIRE_AFTER_RESPONSE_READ_COMMIT_PROOF',
        'hidden-proof': 'WIRE_BEFORE_REQUEST_WRITE_COMMIT_PROOF',
        'epoch-during-basis': 'WIRE_BEFORE_RESPONSE_WRITE_BASIS_CHUNK:continuation'}


def scenario(root, cp, case):
    root.mkdir(); workers = {}; history = []; expected = []; starts = []
    receipt = dict(case=case, status='FAIL', publicRuntime=True)
    (root/'promise-evidence').touch(); (root/'selection-evidence').touch()
    (root/'chunk-bytes.txt').write_text('4096\n')
    def start(node, generation=1):
        began = time.monotonic_ns(); worker = q.Worker(root, node, cp, history, generation)
        workers[node] = worker
        starts.append(dict(node=node, generation=generation, pid=worker.proc.pid,
                           startNanos=began, readyNanos=time.monotonic_ns()))
        return worker
    def docs(tag): return [dict(id=tag+i, value=f'tag-{tag+i}-'+'x'*512) for i in (0, 1)]
    def write(active, tag):
        active.call('addAll', documents=docs(tag)); expected.extend(docs(tag)); return history[-1]['opId']
    def read(group=None): return protocol.read_after_recovery(workers if group is None else group, expected)
    def arm(node): fault.replace(root/(node+'-arm.txt'), CUTS[case]+'\npause\n')
    def reached(node):
        row = fault.wait_for(lambda: next((r for r in fault.rows(root, node) if r['event']=='CUT_REACHED'), None), 'selection pause not reached')
        need(row['cut']==CUTS[case] and row['pid']==workers[node].proc.pid, 'selection pause identity')
        receipt['pause'] = row
        return row
    def stopped(node):
        workers.pop(node).stop(); receipt['retained'] = recovery.archive(root, node)
    def higher(node, epoch):
        return fault.wait_for(lambda: next((r for r in fault.rows(root, node) if r['event']=='FORCE' and r['kind']=='PROMISE'
                              and storage.f.inspect(storage.raw(r['record']), 'PROMISE')['epoch']>epoch), None), 'higher promise not forced')
    try:
        q.command(['java', '-cp', cp, q.PACKAGE+'admission.PublicRuntimeConsumer', root, 'setup'], root, 'public-bootstrap')
        # Select node-3 as the original write peer before introducing the lagging
        # candidate. Otherwise isolating that candidate can remove the fixed quorum.
        for node in (('node-1', 'node-3') if case=='lagging-candidate' else protocol.NODES): start(node)
        old, active = fault.leader(workers); receipt['oldLeader'] = old
        need(old!='node-3', 'delayed voter campaigned')
        for tag in (10, 20, 30): write(active, tag)
        read(); index = active.call('status')['provenIndex']
        if case=='lagging-candidate': start('node-2')
        fault.wait_for(lambda: all(w.call('status')['provenIndex']>=index for w in workers.values()), 'selection seed prefix not retained')
        receipt['seedIndex'] = index
        candidate = next(n for n in ('node-1', 'node-2') if n!=old)
        receipt['candidate'] = candidate
        if case=='duplicate-prepare':
            (root/'node-3-lose-promise').touch(); stopped(old)
            fault.wait_for(lambda: any(r['event']=='PROMISE_REPLY_LOST' for r in fault.rows(root, 'node-3')), 'PROMISE reply not lost')
            new, active = read(); need(new==candidate, 'unexpected replacement candidate')
        elif case in ('higher-ballot-accept', 'higher-ballot-proof', 'hidden-proof'):
            arm(old); pending = active.send('addAll', documents=docs(40)); receipt['heldOperation'] = history[-1]['opId']
            cut = reached(old)
            boundary = next(r for r in reversed(fault.rows(root, old)) if r['order']<cut['order'] and r['event']==CUTS[case])
            request = json.loads(storage.raw(boundary['request'])[48:]); receipt['oldEpoch'] = request['epoch']
            fault.partition(root, old); expected.extend(docs(40))
            new, service = read({n:w for n,w in workers.items() if n!=old})
            receipt['majorityRead'] = history[-1]['opId']; receipt['majorityWrite'] = write(service, 50)
            fault.partition(root)
            receipt['higherPromise'] = higher(old, request['epoch'])
            (root/(old+'-release')).touch()
            result = pending.result(timeout=35)
            need(result is not None and result['outcome']=='INDETERMINATE', 'crossed mutation outcome: '+str(result))
            read(); stopped(old)
        elif case=='lagging-candidate':
            fault.partition(root, candidate)
            receipt['laggingIndex'] = workers[candidate].call('status')['provenIndex']
            receipt['advancedWrite'] = write(active, 40)
            through = active.call('status')['provenIndex']
            fault.wait_for(lambda: workers['node-3'].call('status')['provenIndex']>=through, 'advanced peer lacks acknowledged write')
            receipt['advancedIndex'] = through
            stopped(old); fault.partition(root)
            new, active = read(); need(new==candidate, 'lagging candidate did not lead')
        else:
            arm('node-3'); stopped(old); cut = reached('node-3')
            boundary = next(r for r in reversed(fault.rows(root, 'node-3')) if r['order']<cut['order'] and r['event']=='WIRE_BEFORE_RESPONSE_WRITE_BASIS_CHUNK')
            request = json.loads(storage.raw(boundary['request'])[48:]); receipt['oldEpoch'] = request['epoch']
            # Retire this incomplete download by ordinary election traffic. The
            # source's control dispatcher remains live while one wire reply waits.
            protocol.network(root, [f'{candidate} node-3 BEFORE_REQUEST_WRITE BASIS_CHUNK',
                                    f'{candidate} {old} BEFORE_REQUEST_WRITE PREPARE'])
            start(old, 2)
            receipt['higherPromise'] = higher('node-3', request['epoch'])
            (root/'node-3-release').touch(); protocol.network(root, [])
            new, active = read()
        receipt['recoveredLeader'] = new
        if old not in workers: start(old, 2)
        final, active = read(); receipt['laterWrite'] = write(active, 70)
        read(); receipt['finalRead'] = history[-1]['opId']; receipt['expected'] = expected
    except BaseException as error: receipt['failure'] = str(error); raise
    finally:
        fault.partition(root); protocol.network(root, [])
        for node in protocol.NODES: (root/(node+'-release')).touch()
        errors = []
        for worker in workers.values():
            try: worker.stop()
            except Exception as error: errors.append(str(error))
        save(root/'worker-starts.json', starts); save(root/'history.json', history); save(root/'receipt.json', receipt)
        need(not errors, 'selection cleanup: '+str(errors))
    try:
        from . import public_selection_evidence as evidence
        traces = physical.traces_at(root)
        receipt['history'] = public_history.check(history)
        receipt['physical'] = physical.physical(root, history, traces)
        receipt['selection'] = evidence.validate(root, traces, history, receipt)
        receipt['negatives'] = physical.negatives(root, history)+evidence.negatives(root, traces, history, receipt)
        receipt['status'] = 'PASS'
    except BaseException as error: receipt['failure'] = str(error); raise
    finally: save(root/'receipt.json', receipt)
    return receipt


def run(output, only=None):
    return matrix.run_matrix(output, only, cases=CASES, scenario_runner=scenario, execution='public-selection-recovery')


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('output'); p.add_argument('--only'); a=p.parse_args(); run(a.output, a.only)
