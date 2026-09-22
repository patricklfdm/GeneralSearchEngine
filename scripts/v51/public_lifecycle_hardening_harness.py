"""Public pinned recovery, partial I/O quarantine and repeated timeout accounting."""
import argparse
import json
import tarfile
import time
from . import public_qualification_harness as q, public_qualification_evidence as physical
from . import public_fault_harness as fault, public_protocol_harness as protocol
from . import public_promise_harness as matrix, public_recovery_harness as recovery
from . import public_history, storage_inspector as storage
from .storage_harness import need, save

CASES = ('pinned-rebuild', 'partial-leader-accept', 'partial-follower-proof', 'queued-timeouts', 'exchange-timeouts')


def scenario(root, cp, case):
    root.mkdir(); workers = {}; history = []; expected = []
    receipt = dict(status='FAIL', case=case, publicRuntime=True)
    for marker in ('promise-evidence', 'pressure-evidence', 'lifecycle-evidence'): (root/marker).touch()
    (root/'bounds-profile.txt').write_text('backpressure\n'); (root/'chunk-bytes.txt').write_text('4096\n')
    def start(node, generation=1):
        workers[node] = q.Worker(root, node, cp, history, generation, consumer='backpressure'); return workers[node]
    def docs(tag): return [dict(id=tag+i, value=f'tag-{tag+i}-'+'x'*512) for i in (0, 1)]
    def write(active, tag):
        active.call('addAll', documents=docs(tag)); expected.extend(docs(tag)); return history[-1]['opId']
    def read(group=None): return protocol.read_after_recovery(workers if group is None else group, expected)
    def rows(node, event): return [r for r in fault.rows(root, node) if r['event'] == event]
    def sample(active):
        value = active.call('status'); need('sample' in value, 'missing read-only diagnostic probe'); return value
    def stopped(node):
        workers.pop(node).stop(); receipt['retained'] = recovery.archive(root, node)
    def release():
        fault.partition(root); protocol.network(root, []); fault.replace(root/'pressure-rules.txt', '')
        (root/'query-release').touch(); (root/'pressure-release').touch()
        for node in protocol.NODES: (root/(node+'-release')).touch()
    try:
        q.command(['java', '-cp', cp, q.PACKAGE+'admission.PublicRuntimeConsumer', root, 'setup'], root, 'public-bootstrap')
        if case == 'exchange-timeouts':
            protocol.network(root, [f'{n} node-3 BEFORE_REQUEST_WRITE PREPARE' for n in ('node-1', 'node-2')])
        for node in protocol.NODES: start(node)
        old, active = fault.leader(workers); need(old != 'node-3', 'delayed voter campaigned'); receipt['leader'] = old
        protocol.network(root, [])
        for tag in (10, 20, 30): write(active, tag)
        read(); receipt['baseline'] = sample(active)
        index = active.call('status')['provenIndex']
        fault.wait_for(lambda: all(w.call('status')['provenIndex'] >= index for w in workers.values()), 'seed not retained')
        proof = next(r['record'] for r in reversed(rows(old, 'FORCE')) if r['kind'] == 'PROOF')
        peer = next(v['voter'] for v in storage.f.inspect(storage.raw(proof), 'PROOF')['receipts'] if v['voter'] != old)
        receipt['seedProof'] = proof; receipt['quorumPeer'] = peer
        if case == 'pinned-rebuild':
            held = active.send('read', hold=True); receipt['heldRead'] = history[-1]['opId']; receipt['oldDocuments'] = list(expected)
            fault.wait_for(lambda: rows(old, 'QUERY_HELD'), 'read callback not held')
            fault.partition(root, old)
            _, service = read({n:w for n,w in workers.items() if n != old})
            receipt['majorityWrite'] = write(service, 40); read({n:w for n,w in workers.items() if n != old})
            fault.partition(root)
            receipt['installed'] = fault.wait_for(lambda: next((r for r in rows(old, 'REJOIN_INSTALLED')
                if len(storage.f.inspect(storage.raw(r['snapshot']), 'SNAPSHOT')['anchors']) > index), None), 'new snapshot not installed while read held')
            # Stop the new leader so the old voter must reconstruct its installed
            # image for a natural campaign while its old callback still owns the app worker.
            stopped(service.node)
            receipt['queuedRebuild'] = fault.wait_for(lambda: next((r for r in rows(old, 'RECONSTRUCT_QUEUED')
                if r['order'] > receipt['installed']['order'] and r['index'] > index), None), 'rebuild not queued behind callback')
            receipt['heldSample'] = sample(active)
            need(not held.done(), 'pinned read finished before controller release')
            (root/'query-release').touch(); result = held.result(timeout=15)
            need(result and result['outcome'] == 'SUCCESS' and result['documents'] == receipt['oldDocuments'], 'rebuild changed pinned read')
            read(); receipt['rebuiltRead'] = history[-1]['opId']
        elif case.startswith('partial-'):
            target = old if case == 'partial-leader-accept' else peer; kind = 'ACCEPT' if target == old else 'PROOF'
            receipt['target'] = target; fault.replace(root/(target+'-partial-write.txt'), kind+'\n')
            pending = active.send('addAll', documents=docs(40)); receipt['failedWrite'] = history[-1]['opId']
            receipt['partial'] = fault.wait_for(lambda: next(iter(rows(target, 'PARTIAL_WRITE_FAILURE')), None), 'partial I/O failure not reached')
            result = pending.result(timeout=20)
            need(result and result['outcome'] == 'INDETERMINATE', 'partial mutation was not conservative: '+str(result))
            for command, values in (('addAll', dict(documents=docs(90))), ('read', {})):
                denied = workers[target].send(command, **values).result(timeout=20)
                need(denied and denied.get('reasonCode') == 'STORAGE_FAILURE' and denied['outcome'] == ('NOT_SUBMITTED' if command == 'addAll' else 'NOT_APPLICABLE'), 'quarantined handle still admitted calls')
            workers.pop(target).stop(); receipt['quarantinedInventory'] = storage.inventory(root/target)
            with tarfile.open(root/'quarantined.tar.gz', 'w:gz') as archive: archive.add(root/target, arcname=target)
            receipt['quarantinedArchiveSha256'] = storage.sha((root/'quarantined.tar.gz').read_bytes())
            receipt['probes'] = []
            for attempt in (1, 2):
                probe = q.command(['java', '-cp', cp, q.PACKAGE+'admission.PublicLifecycleConsumer', root, target[-1], 'probe'], root, f'quarantine-probe-{attempt}')
                receipt['probes'].append(json.loads(probe.stdout))
                inventory = storage.inventory(root/target); save(root/f'quarantine-probe-{attempt}-inventory.json', inventory)
                need(inventory == receipt['quarantinedInventory'], 'rejected public restart changed authority')
            if kind == 'PROOF': expected.extend(docs(40))
            # The damaged voter is deliberately excluded from service coordination,
            # and separately checked as quarantined by the byte and public oracles.
            _, active = read(); receipt['survivingRead'] = history[-1]['opId']
        elif case == 'queued-timeouts':
            held = active.send('read', hold=True); receipt['heldRead'] = history[-1]['opId']
            fault.wait_for(lambda: rows(old, 'QUERY_HELD'), 'query did not pin application')
            receipt['waves'] = []
            for wave in range(3):
                futures = []; ids = []
                for i in range(3):
                    futures.append(active.send('addAll', documents=docs(100+wave*10+i*2), poison=True)); ids.append(history[-1]['opId'])
                fault.wait_for(lambda: active.call('status')['pending'] == 4, 'timeout wave did not fill admission')
                full = sample(active)
                for future in futures:
                    value = future.result(timeout=20)
                    need(value and value['outcome'] == 'NOT_SUBMITTED' and value.get('reasonCode') == 'DEADLINE_EXCEEDED', 'queued timeout outcome')
                drained = fault.wait_for(lambda: (v if (v:=sample(active))['pending'] == 1 and v['sample']['orderedQueue'] == v['sample']['deadlinesQueue'] == 0 else None), 'expired queue/timer retained')
                receipt['waves'].append(dict(operations=ids, full=full, drained=drained))
            (root/'query-release').touch(); need(held.result(timeout=10)['documents'] == expected, 'timeout waves changed pinned view')
        else:
            need(peer != 'node-3', 'timeout target is active quorum peer'); receipt['rounds'] = []
            for cycle in range(3):
                (root/'pressure-release').unlink(missing_ok=True)
                old_holds = len(rows('node-3', 'PRESSURE_HELD'))
                fault.replace(root/'pressure-rules.txt', f'{old} node-3 BEFORE_RESPONSE_WRITE AUTHORITY_STATUS_PROBE\n')
                held = fault.wait_for(lambda: next(iter(rows('node-3', 'PRESSURE_HELD')[old_holds:]), None), 'maintenance reply not held')
                request = held['request']
                released = fault.wait_for(lambda: next((r for r in rows(old, 'TRANSPORT') if r['transition'] == 'OUTBOUND_RELEASED' and r.get('request') == request), None), 'timed-out outbound reservation not released')
                fault.replace(root/'pressure-rules.txt', ''); (root/'pressure-release').touch()
                fault.wait_for(lambda: len(rows('node-3', 'PRESSURE_RELEASED')) == len(rows('node-3', 'PRESSURE_HELD')), 'server holds did not drain')
                receipt['rounds'].append(dict(held=held, released=released, sample=sample(active)))
                receipt['rounds'][-1]['write'] = write(active, 40+cycle*10); read()
        final, active = read(); receipt['resumedWrite'] = write(active, 80); read(); receipt['resumedRead'] = history[-1]['opId']
        receipt['drained'] = fault.wait_for(lambda: (v if (v:=sample(active))['pending'] == 0 and v['sample']['orderedQueue'] == v['sample']['deadlinesQueue'] == 0 else None), 'final admission/timer leak')
        if 'retained' not in receipt: stopped(final)
        restart = receipt['retained']['node']; start(restart, 2); read(); receipt['afterRestartRead'] = history[-1]['opId']; receipt['expected'] = expected
    except BaseException as error: receipt['failure'] = str(error); raise
    finally:
        release(); errors = []
        for worker in workers.values():
            try: worker.stop()
            except Exception as error: errors.append(str(error))
        save(root/'history.json', history); save(root/'receipt.json', receipt)
        need(not errors, 'lifecycle cleanup: '+str(errors))
    try:
        from . import lifecycle_hardening_evidence as evidence
        traces = physical.traces_at(root); tails = {receipt['target']: receipt['partial']} if case.startswith('partial-') else None
        receipt['history'] = public_history.check(history)
        receipt['physical'] = physical.physical(root, history, traces, rejected_tails=tails)
        receipt['scenario'] = evidence.validate(root, traces, history, receipt)
        receipt['negatives'] = physical.negatives(root, history, rejected_tails=tails)+evidence.negatives(root, traces, history, receipt)
        receipt['status'] = 'PASS'
    except BaseException as error: receipt['failure'] = str(error); raise
    finally: save(root/'receipt.json', receipt)
    return receipt


def run(output, only=None):
    return matrix.run_matrix(output, only, cases=CASES, scenario_runner=scenario, execution='public-lifecycle-hardening',
                             consumer_sources=('PublicBackpressureConsumer.java', 'PublicLifecycleConsumer.java'))


if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('output'); p.add_argument('--only'); a=p.parse_args(); run(a.output, a.only)
