"""Read-only promise/crash oracle over journals, wire bytes and public histories."""
import copy
from pathlib import Path
import struct
import tarfile
from . import runtime_evidence as a
from .public_protocol_evidence import crash_rows
from .storage_harness import need

# Independent expected schedule; never accept a caller-supplied boundary as truth.
BOUNDARIES = {'before-write': 'PROMISE_BEFORE_WRITE', 'after-write': 'PROMISE_AFTER_WRITE',
              'after-force': 'PROMISE_AFTER_FORCE', 'before-ack': 'PROMISE_BEFORE_ACK',
              'basis-ack': 'BASIS_BEFORE_ACK', 'before-reply': 'WIRE_BEFORE_RESPONSE_WRITE_PREPARE'}


def journal(data, manifest, node):
    rows = []; offset = 0
    while offset < len(data):
        need(len(data)-offset >= 48, 'torn promise header')
        size = struct.unpack('>i', data[offset+12:offset+16])[0]
        need(0 < size <= 65536-48 and offset+48+size <= len(data), 'torn/oversized promise frame')
        encoded = data[offset:offset+48+size]
        value = a.f.contextual_frame(encoded, 'JOURNAL' if offset == 0 else 'PROMISE', manifest)
        if offset == 0: need(value['node'] == node and value['recordKind'] == 4, 'promise journal identity')
        else:
            need(len(rows) < 10000 and (value['epoch'] == 1 if not rows else value['epoch'] > rows[-1][1]['epoch']), 'promise order/reused epoch')
            rows.append((encoded, value))
        offset += len(encoded)
    need(rows, 'missing initial promise')
    return rows


def extension(before, retained, final, written):
    need(retained.startswith(before) and final.startswith(retained), 'promise prefix forgotten or rewritten')
    need(len(retained) > len(before) if written else retained == before, 'wrong promise write boundary')


def sealed_schedule(root, node):
    """Read the actual admitted PLAN; election policy is not in BOOTSTRAP_BINDING."""
    manifest_raw = (root/node/'manifest.gsr').read_bytes()
    manifest = dict(a.f.inspect(manifest_raw, 'MANIFEST'), digest=manifest_raw[16:48].hex())
    seal = a.f.contextual_frame((root/node/'bootstrap-seal.gsr').read_bytes(), 'SEAL', manifest)
    admitted = a.f.inspect(a.raw(seal['receipt']), 'RECEIPT')
    plan = a.f.inspect(a.raw(admitted['plan']), 'PLAN')
    need(a.raw(plan['manifest']) == manifest_raw, 'promise bootstrap manifest binding')
    replicas = plan['targets']
    need(replicas[2]['policy']['minElectionTimeoutMillis'] == 600000
         and replicas[2]['policy']['maxElectionTimeoutMillis'] == 601200
         and all(v['policy']['minElectionTimeoutMillis'] == 3600 for v in replicas[:2]), 'promise election schedule not sealed')
    return manifest


def retained_files(root, node, retained):
    archive = root/'before-reopen.tar.gz'
    need(a.storage.sha(archive.read_bytes()) == retained['sha256'], 'pre-reopen archive identity')
    with tarfile.open(archive) as tar:
        files = {m.name.removeprefix(node+'/'): tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
    need({p: dict(size=len(data), sha256=a.storage.sha(data)) for p, data in files.items()} == retained['inventory'], 'pre-reopen archive inventory')
    need(files['manifest.gsr'] == (root/node/'manifest.gsr').read_bytes(), 'pre-reopen manifest changed')
    return files


def validate(root, traces, history, receipt):
    root = Path(root); stage, mode = receipt['case'].rsplit('-', 1); crash = receipt['crash']; node = crash['node']
    need(stage in BOUNDARIES and crash['cut'] == BOUNDARIES[stage] and crash['mode'] == mode and node == 'node-3', 'wrong promise scenario')
    before = crash_rows(traces, crash)
    manifest = sealed_schedule(root, node)
    files = retained_files(root, node, receipt['retained'])
    previous = next((r for r in reversed(before) if r['event'] == 'PROMISE_BEFORE_WRITE'), None)
    need(previous is not None, 'missing pre-write journal observation')
    initial = a.raw(previous['journal']); retained = files['promises.gsr']; final = (root/node/'promises.gsr').read_bytes()
    old = journal(initial, manifest, node); saved = journal(retained, manifest, node); later = journal(final, manifest, node)
    extension(initial, retained, final, stage != 'before-write')
    need(len(saved) == len(old)+(stage != 'before-write'), 'crash appended multiple promises')
    old_bytes, old_promise = old[-1]; last_bytes, last = saved[-1]
    need(any(r['event'] == 'FORCE' and r['kind'] == 'PROMISE' and a.raw(r['record']) == old_bytes
             and r['order'] < previous['order'] for r in before), 'missing prior durable promise')
    forced = [r for r in before if r['event'] == 'FORCE' and r['kind'] == 'PROMISE'
              and a.raw(r['record']) == last_bytes and r['order'] > previous['order']]
    need(bool(forced) == (stage not in ('before-write', 'after-write')), 'promise force ordering at crash')
    if stage != 'before-reply': need(a.raw(before[-1]['journal']) == retained, 'observed cut journal differs from retained bytes')
    requests = []
    for owner, rows in traces.items():
        for row in rows:
            if row['event'] != 'WIRE_BEFORE_REQUEST_WRITE_PREPARE': continue
            req = a.f.wire(a.raw(row['request']), manifest)
            if req['recipient'] == node and req['epoch'] > old_promise['epoch']:
                need(owner == req['sender'] == req['proposer'] and owner != node, 'promise requester identity')
                requests.append(req)
    need(requests, 'missing public peer campaign')
    if stage != 'before-write':
        need(any((r['epoch'], r['proposer'], r['incarnationId']) == a.storage.ballot(last) for r in requests), 'written promise has no matching peer request')
    frozen = []
    if stage in ('basis-ack', 'before-reply'):
        for path, data in files.items():
            if not (path.startswith('basis/') and path.endswith('/basis.gsr')): continue
            basis = a.f.contextual_frame(data, 'BASIS', manifest)
            if a.storage.ballot(basis['ballot']) != a.storage.ballot(last): continue
            a.recovery.basis(data, files[path.removesuffix('basis.gsr')+'image.gsr'], manifest)
            need(basis['node'] == node, 'frozen basis voter identity'); frozen.append(data)
        need(len(frozen) == 1, 'missing exact frozen promise basis')
    if stage == 'before-reply':
        req = a.f.wire(a.raw(before[-1]['request']), manifest); response = a.f.wire(a.raw(before[-1]['frame']), manifest)
        need(req['type'] == 'PREPARE' and response['type'] == 'PROMISE' and response['sender'] == req['recipient'] == node
             and response['recipient'] == req['sender']
             and all(response[k] == req[k] for k in ('traceId', 'eventSequence', 'epoch', 'proposer', 'incarnationId'))
             and a.raw(response['payload']['basis']) == frozen[0], 'reply is not the forced frozen promise')
    if stage != 'before-write':
        for rows in traces.values():
            for row in rows:
                if row['event'] != 'RECEIVED': continue
                response = a.f.wire(a.raw(row['frame']), manifest)
                # A retransmitted reply from generation 2 is permitted. The same
                # exact request must have a matching post-restart reply observation.
                if response['type'] != 'PROMISE' or response['sender'] != node or response['epoch'] != last['epoch']: continue
                need(any(r['event'] == 'REPLY' and r['generation'] == 2 and r['request'] == row['request'] and r['frame'] == row['frame']
                         for r in traces[node]), 'promise reply escaped the pre-response crash')
    for row in traces[node]:
        if row['generation'] != 2 or row['event'] != 'FORCE' or row['kind'] != 'PROMISE': continue
        value = a.f.contextual_frame(a.raw(row['record']), 'PROMISE', manifest)
        need(value['epoch'] >= last['epoch'] and (value['epoch'] != last['epoch'] or value == last), 'restarted voter forgot or reused a promise')
    op = next((v for v in history if v['opId'] == receipt['postRestartWrite']), None)
    need(op is not None and op['kind'] == 'addAll' and op['outcome'] == 'SUCCESS', 'missing post-restart public write')
    votes = []
    for row in traces[node]:
        if row['generation'] != 2 or row['event'] != 'FORCE' or row['kind'] != 'ACCEPT': continue
        vote = a.f.contextual_frame(a.raw(row['record']), 'ACCEPT', manifest)
        entry = a.f.contextual_frame(a.raw(vote['entry']), 'ENTRY', manifest)
        if entry['operation'] == 4 and [dict(id=k, value=v) for k, v in a.documents_command(a.raw(entry['payload']))] == op['documents']:
            need(vote['epoch'] >= last['epoch'], 'new public write used a stale promise'); votes.append(vote)
    need(votes, 'restarted promise voter did not join the write quorum')
    need(any(r['event'] == 'FORCE' and r['kind'] == 'PROOF' and r['generation'] == 2
             and any(a.f.inspect(a.raw(r['record']), 'PROOF')['entryDigest'] == v['entryDigest'] for v in votes)
             for r in traces[node]), 'restarted promise voter did not prove the new write')
    return dict(status='PASS', priorEpoch=old_promise['epoch'], retainedEpoch=last['epoch'], finalEpoch=later[-1][1]['epoch'],
                written=stage != 'before-write', forced=bool(forced), frozenBasis=bool(frozen), restartedVoter=node)


def negatives(root, traces, history, receipt):
    stage = receipt['case'].rsplit('-', 1)[0]; node = receipt['crash']['node']; pid = receipt['crash']['pid']
    removals = [('missing-cut', lambda r: r['event'] == 'CUT_REACHED'),
                ('missing-boundary', lambda r: r['event'] == receipt['crash']['cut']),
                ('missing-prewrite', lambda r: r['event'] == 'PROMISE_BEFORE_WRITE'),
                ('missing-restart', lambda r: r['event'] == 'STARTED' and r['generation'] == 2),
                ('missing-promise-forces', lambda r: r['event'] == 'FORCE' and r['kind'] == 'PROMISE' and r['pid'] == pid),
                ('missing-restarted-votes', lambda r: r['event'] == 'FORCE' and r['kind'] == 'ACCEPT' and r['generation'] == 2)]
    changes = []
    for name, remove in removals:
        changed = copy.deepcopy(traces); changed[node] = [r for r in changed[node] if not remove(r)]
        changes.append((name, changed, receipt))
    changed = copy.deepcopy(receipt); changed['retained']['sha256'] = '0'*64
    changes.append(('wrong-archive', traces, changed))
    changed = copy.deepcopy(receipt); changed['case'] = ('after-write' if stage == 'before-write' else 'before-write')+'-'+receipt['crash']['mode']
    changes.append(('wrong-scenario', traces, changed))
    changed = copy.deepcopy(traces)
    for row in changed[node]:
        if row['event'] == 'PROMISE_BEFORE_WRITE': row['journal'] = ''
    changes.append(('missing-journal-bytes', changed, receipt))
    results = []
    for name, changed, claim in changes:
        try: validate(root, changed, history, claim)
        except ValueError as error: results.append(dict(case=name, status='REJECTED', reason=str(error)))
        else: raise ValueError('promise oracle admitted '+name)
    return results
