"""Independent ordering, torn-authority and finite timeout-accounting witnesses."""
import copy
import json
from pathlib import Path
import tarfile
from . import runtime_evidence as a
from .public_promise_evidence import retained_files, sealed_schedule
from .public_pressure_evidence import reservations
from .storage_harness import need

CASES = {'pinned-rebuild', 'partial-leader-accept', 'partial-follower-proof', 'queued-timeouts', 'exchange-timeouts'}


def bounded_sample(sample, *, drained=False):
    for key, limit in {'admissionAvailable':4, 'orderedQueue':4, 'deadlinesQueue':4,
                       'inputsQueue':32, 'inputsRemaining':32, 'completionsQueue':16, 'completionsRemaining':16,
                       'networkQueue':4, 'networkActive':4, 'appQueue':4, 'appActive':1, 'clientsQueue':2, 'clientsActive':1}.items():
        need(type(sample.get(key)) is int and 0 <= sample[key] <= limit, 'unbounded/missing diagnostic: '+key)
    if drained:
        need(sample['admissionAvailable'] == 4 and sample['orderedQueue'] == sample['deadlinesQueue'] == 0, 'public timers/admission not drained')


def rebuild_order(held, installed, queued, query_released, view_released, begin, end):
    rows = (held, installed, queued, query_released, view_released, begin, end)
    need(len({(r['pid'], r['generation']) for r in rows}) == 1, 'borrowed rebuild process')
    need(all(x['order'] < y['order'] for x, y in zip(rows, rows[1:])), 'rebuild replaced a held view or lacked overlap')
    need(queued['id'] == begin['id'] == end['id'] and queued['index'] == begin['index'] == end['index'], 'rebuild work identity changed')


def validate(root, traces, history, receipt):
    root = Path(root); case = receipt['case']; need(case in CASES, 'unknown lifecycle case')
    manifest = sealed_schedule(root, 'node-3'); leader = receipt['leader']; calls = {op['opId']:op for op in history}
    need(len(calls) == len(history), 'duplicate lifecycle call')
    def frame(encoded, kind): return a.frame(encoded, kind, manifest)
    def wire(encoded): return a.f.wire(a.raw(encoded), manifest)
    def one(node, event, opid=None):
        matches = [r for r in traces[node] if r['event'] == event and (opid is None or r.get('opId') == opid)]
        need(len(matches) == 1, 'missing/duplicate '+event); return matches[0]
    def sampled(value):
        matches = [r for rows in traces.values() for r in rows if r['event'] == 'LIFECYCLE_SAMPLE' and r['opId'] == value['opId']]
        need(len(matches) == 1 and matches[0]['sample'] == value['sample'], 'diagnostic sample not observed')
        bounded_sample(value['sample']); return matches[0]
    seal = a.f.inspect((root/'node-1/bootstrap-seal.gsr').read_bytes(), 'SEAL')
    plan = a.f.inspect(a.raw(a.f.inspect(a.raw(seal['receipt']), 'RECEIPT')['plan']), 'PLAN')
    need(all(t['bounds']['maxPendingClientOperations'] == 4 and t['bounds']['requestTimeoutMillis'] == 1200
             and t['policy']['operationTimeoutMillis'] == 9600 for t in plan['targets']), 'changed sealed limits/deadlines')
    accounting = {n:reservations(rows, wire, 1<<20) for n,rows in traces.items()}
    for op in history:
        begin = one(op['node'], 'CLIENT_INVOKE', op['opId'])
        finish = one(op['node'], 'CLIENT_SUCCESS' if op['outcome'] == 'SUCCESS' else 'CLIENT_FAILURE', op['opId'])
        need(begin['pid'] == finish['pid'] == op['pid'] and begin['generation'] == finish['generation'] == op['generation']
             and begin['order'] < finish['order'] and finish['outcome'] == op['outcome']
             and finish.get('reasonCode') == op.get('reasonCode'), 'public lifecycle interval/outcome binding')
    for key, kind in (('resumedWrite','addAll'), ('resumedRead','read'), ('afterRestartRead','read')):
        op = calls[receipt[key]]; need(op['kind'] == kind and op['outcome'] == 'SUCCESS', 'missing recovered public service')
    need(calls[receipt['afterRestartRead']]['documents'] == receipt['expected'], 'wrong final projection')
    restart = receipt['retained']['node']; retained_files(root, restart, receipt['retained'])
    starts = [r for r in traces[restart] if r['event'] == 'STARTED']
    need(len(starts) == 2 and {r['generation'] for r in starts} == {1, 2} and starts[0]['pid'] != starts[1]['pid'], 'missing retained healthy restart')
    sampled(receipt['baseline']); sampled(receipt['drained']); bounded_sample(receipt['drained']['sample'], drained=True)

    if case == 'pinned-rebuild':
        opid = receipt['heldRead']; op = calls[opid]; held = one(leader, 'QUERY_HELD', opid)
        released = one(leader, 'QUERY_HELD_RELEASED', opid); installed = receipt['installed']; queued = receipt['queuedRebuild']
        need(installed in traces[leader] and installed['event'] == 'REJOIN_INSTALLED'
             and queued in traces[leader] and queued['event'] == 'RECONSTRUCT_QUEUED', 'missing overlapping snapshot/rebuild')
        index = len(frame(installed['snapshot'], 'SNAPSHOT')['anchors'])
        before = [r for r in traces[leader] if r['pid'] == op['pid'] and r['event'] == 'READ_CAPTURED' and r['order'] < held['order']]
        need(before and index > before[-1]['index'] and queued['index'] >= index, 'rebuild did not advance pinned application cut')
        chosen = lambda event: [r for r in traces[leader] if r['event'] == event and r['pid'] == op['pid'] and r.get('id') == queued['id']]
        begin, end = chosen('RECONSTRUCT_BEGIN'), chosen('RECONSTRUCT_END')
        need(len(begin) == len(end) == 1, 'reconstruction did not complete once')
        views = [r for r in traces[leader] if r['event'] == 'READ_RELEASED' and r['pid'] == op['pid'] and held['order'] < r['order'] < begin[0]['order']]
        need(len(views) == 1, 'missing pinned view release')
        rebuild_order(held, installed, queued, released, views[0], begin[0], end[0])
        need(not any(r['pid'] == op['pid'] and held['order'] < r['order'] < views[0]['order']
                     and r['event'] in ('RECONSTRUCT_BEGIN', 'PUBLISHED') for r in traces[leader]), 'application changed during pinned callback')
        need(op['outcome'] == 'SUCCESS' and op['documents'] == receipt['oldDocuments'], 'old pinned projection changed')
        _, docs = a.application(a.raw(frame(installed['snapshot'], 'SNAPSHOT')['application']))
        write = calls[receipt['majorityWrite']]
        need(write['outcome'] == 'SUCCESS' and write['node'] != leader and all(docs.get(d['id']) == d['value'] for d in write['documents']), 'installed image lacks new majority write')
        recovered = calls[receipt['rebuiltRead']]
        need(recovered['node'] == leader and recovered['outcome'] == 'SUCCESS' and all(d in recovered['documents'] for d in write['documents']), 'rebuilt old voter never served new prefix')
        sampled(receipt['heldSample']); need(receipt['heldSample']['sample']['appQueue'] > 0 and receipt['heldSample']['sample']['appActive'] == 1, 'rebuild was not waiting for application worker')
        detail = dict(oldIndex=before[-1]['index'], installedIndex=index, rebuiltIndex=queued['index'])
    elif case.startswith('partial-'):
        target = receipt['target']; partial = receipt['partial']; need(one(target, 'PARTIAL_WRITE_FAILURE') == partial, 'borrowed partial-write witness')
        kind = 'ACCEPT' if case == 'partial-leader-accept' else 'PROOF'
        need(partial['kind'] == kind and (target == leader) == (kind == 'ACCEPT'), 'wrong partial-write site')
        op = calls[receipt['failedWrite']]; need(op['node'] == leader and op['outcome'] == 'INDETERMINATE', 'ambiguous I/O incorrectly classified')
        if target == leader:
            invocation = one(leader, 'CLIENT_INVOKE', op['opId']); failure = one(leader, 'CLIENT_FAILURE', op['opId'])
            need(invocation['order'] < partial['order'] < failure['order'], 'partial write outside mutation interval')
        need(a.storage.inventory(root/target) == receipt['quarantinedInventory'], 'quarantine bytes changed')
        archive = root/'quarantined.tar.gz'; need(a.storage.sha(archive.read_bytes()) == receipt['quarantinedArchiveSha256'], 'quarantine archive hash')
        with tarfile.open(archive) as tar:
            saved = {m.name.removeprefix(target+'/'):dict(size=m.size, sha256=a.storage.sha(tar.extractfile(m).read())) for m in tar.getmembers() if m.isfile()}
        need(saved == receipt['quarantinedInventory'], 'quarantine archive inventory')
        probes = receipt['probes']; need(len(probes) == 2 and len({v['pid'] for v in probes}|{partial['pid']}) == 3, 'missing separate rejected restarts')
        for i, probe in enumerate(probes, 1):
            need(probe == json.loads((root/f'quarantine-probe-{i}.stdout').read_text()) and probe['state'] == 'FAILED'
                 and probe['outcome'] == 'NOT_APPLICABLE' and probe['reasonCode'] in ('INTEGRITY_FAILURE','STORAGE_FAILURE'), 'torn voter resumed or wrong startup rejection')
            need(json.loads((root/f'quarantine-probe-{i}-inventory.json').read_text()) == saved, 'rejected restart changed quarantine inventory')
        rejected = [op for op in history if op['node'] == target and op.get('reasonCode') == 'STORAGE_FAILURE' and op['opId'] != receipt['failedWrite']]
        need({op['kind'] for op in rejected} == {'read','addAll'} and all(op['outcome'] == ('NOT_SUBMITTED' if op['kind'] == 'addAll' else 'NOT_APPLICABLE') for op in rejected), 'failed voter did not reject later public work')
        need(not any(r['order'] > partial['order'] and r['pid'] == partial['pid'] and r['event'] in ('FORCE','PUBLISHED') for r in traces[target]), 'quarantined voter continued authority/publication')
        read = calls[receipt['survivingRead']]; need(read['node'] != target and read['outcome'] == 'SUCCESS', 'surviving majority unavailable')
        need(all((d in read['documents']) == (kind == 'PROOF') for d in op['documents']), 'partial I/O chosen boundary changed')
        if kind == 'PROOF':
            tail = a.raw(partial['after'])[len(a.raw(partial['before'])):]
            requests = [wire(r['request']) for r in traces[target] if r['event'] == 'REPLY' and r['pid'] == partial['pid'] and r['order'] > partial['order']]
            proofs = [a.raw(req['payload']['proof']) for req in requests if req['type'] == 'COMMIT_PROOF' and a.raw(req['payload']['proof']).startswith(tail)]
            need(proofs and all(value == proofs[0] for value in proofs), 'partial proof lacks exact incoming frame')
            proof = a.f.contextual_frame(proofs[0], 'PROOF', manifest)
            need(any(r['event'] == 'FORCE' and r['kind'] == 'PROOF' and a.raw(r['record']) == proofs[0] for r in traces[leader]), 'leader never forced the hidden complete proof')
            entries = [frame(frame(r['record'], 'ACCEPT')['entry'], 'ENTRY') for r in traces[leader] if r['event'] == 'FORCE' and r['kind'] == 'ACCEPT']
            need(any(entry['index'] == proof['index'] and entry['operation'] == 4 and
                     [dict(id=k,value=v) for k,v in a.documents_command(a.raw(entry['payload']))] == op['documents'] for entry in entries), 'partial proof belongs to another client value')
        detail = a.storage.torn_append(root/target, partial)
    elif case == 'queued-timeouts':
        opid = receipt['heldRead']; held = one(leader, 'QUERY_HELD', opid); released = one(leader, 'QUERY_HELD_RELEASED', opid)
        need(calls[opid]['outcome'] == 'SUCCESS' and len(receipt['waves']) == 3, 'missing repeated queued deadlines')
        ids = []; previous = held['order']
        for wave in receipt['waves']:
            need(len(wave['operations']) == 3, 'incomplete timeout wave'); ids.extend(wave['operations'])
            full = sampled(wave['full']); drained = sampled(wave['drained'])
            need(previous < full['order'] < drained['order'] < released['order'], 'overlapping/missing timeout wave')
            need(wave['full']['pending'] == 4 and wave['full']['sample']['orderedQueue'] == wave['full']['sample']['deadlinesQueue'] == 3, 'wave did not occupy bounded queue/timers')
            need(wave['drained']['pending'] == 1 and wave['drained']['sample']['admissionAvailable'] == 3
                 and wave['drained']['sample']['orderedQueue'] == wave['drained']['sample']['deadlinesQueue'] == 0, 'expired queue retained resources')
            for identity in wave['operations']:
                op = calls[identity]; begin = one(leader, 'CLIENT_INVOKE', identity); end = one(leader, 'CLIENT_FAILURE', identity)
                need(op['outcome'] == 'NOT_SUBMITTED' and op.get('reasonCode') == 'DEADLINE_EXCEEDED'
                     and previous < begin['order'] < end['order'] < drained['order']
                     and end['localNanos']-begin['localNanos'] >= 9600_000_000, 'queued timeout did not reach sealed deadline')
            previous = drained['order']
        need(len(set(ids)) == 9 and not any(r['event'] == 'ARGUMENT_TOUCHED' for r in traces[leader]), 'queued arguments executed or writes replayed')
        detail = dict(waves=3, expiredCalls=9)
    else:
        need(len(receipt['rounds']) == 3 and receipt['quorumPeer'] != 'node-3', 'timeout schedule lacks independent service quorum')
        previous = 0
        for cycle in receipt['rounds']:
            held, released = cycle['held'], cycle['released']; req = wire(held['request'])
            need(held in traces['node-3'] and held['event'] == 'PRESSURE_HELD' and held['barrier'] == 'BEFORE_RESPONSE_WRITE'
                 and req['sender'] == leader and req['recipient'] == 'node-3' and req['type'] == 'AUTHORITY_STATUS_PROBE', 'wrong timeout hold')
            need(released in traces[leader] and released['event'] == 'TRANSPORT' and released['transition'] == 'OUTBOUND_RELEASED'
                 and released['request'] == held['request'], 'timeout reservation not released')
            admitted = [r for r in traces[leader] if r['event'] == 'TRANSPORT' and r['transition'] == 'OUTBOUND_ADMITTED'
                        and r['pid'] == released['pid'] and r['reservation'] == released['reservation']]
            need(len(admitted) == 1 and previous < admitted[0]['order'] < released['order']
                 and released['localNanos']-admitted[0]['localNanos'] >= 1200_000_000, 'request did not time out within actual reservation')
            sample = sampled(cycle['sample']); need(sample['order'] > released['order'], 'queue sample predates timeout')
            op = calls[cycle['write']]; need(op['node'] == leader and op['outcome'] == 'SUCCESS', 'majority did not serve after timeout')
            previous = released['order']
        detail = dict(rounds=3)
    return dict(status='PASS', accounting=accounting, details=detail)


def negatives(root, traces, history, receipt):
    changes = [('missing-restart', lambda r:r['event'] == 'STARTED' and r['generation'] == 2),
               ('missing-accounting-release', lambda r:r['event'] == 'TRANSPORT' and r['transition'].endswith('_RELEASED')),
               ('missing-queue-samples', lambda r:r['event'] == 'LIFECYCLE_SAMPLE')]
    case = receipt['case']
    if case == 'pinned-rebuild':
        changes += [(f'missing-{event.lower()}', lambda r,event=event:r['event'] == event)
                    for event in ('REJOIN_INSTALLED','RECONSTRUCT_QUEUED','RECONSTRUCT_BEGIN','RECONSTRUCT_END','READ_RELEASED')]
    elif case.startswith('partial-'): changes.append(('missing-partial-write', lambda r:r['event'] == 'PARTIAL_WRITE_FAILURE'))
    else: changes.append(('missing-held-work', lambda r:r['event'] == ('QUERY_HELD' if case == 'queued-timeouts' else 'PRESSURE_HELD')))
    result = []
    for name, remove in changes:
        altered = {n:[r for r in rows if not remove(r)] for n, rows in traces.items()}
        try: validate(root, altered, history, receipt)
        except ValueError as error: result.append(dict(case=name, status='REJECTED', reason=str(error)))
        else: raise ValueError('lifecycle oracle admitted '+name)
    altered = copy.deepcopy(receipt); altered['expected'] = []
    try: validate(root, traces, history, altered)
    except ValueError as error: result.append(dict(case='changed-final-projection', status='REJECTED', reason=str(error)))
    else: raise ValueError('lifecycle oracle admitted changed-final-projection')
    return result
