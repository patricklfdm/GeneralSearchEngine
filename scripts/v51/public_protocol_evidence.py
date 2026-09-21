"""Independent public schedule checks, in addition to history/chosen-prefix oracles."""
import json
from pathlib import Path
import tarfile
from . import runtime_evidence as a
from .storage_harness import need


def ranges(parts, length):
    """Require an exact observed prefix; duplicate retries must carry identical bytes."""
    chunks = {}
    for offset, data in parts:
        need(offset >= 0 and data, 'empty/negative transfer range')
        need(offset not in chunks or chunks[offset] == data, 'changed transfer retry')
        chunks[offset] = data
    result = b''
    for offset, data in sorted(chunks.items()):
        if offset >= length: break
        need(offset == len(result) and len(data) <= length-offset, 'transfer gap/overlap')
        result += data
    need(len(result) == length, 'missing interrupted transfer prefix')
    return result


def crash_rows(traces, crash):
    rows = [r for r in traces[crash['node']] if r['pid'] == crash['pid']]
    cut = [r for r in rows if r['event'] == 'CUT_REACHED']
    need(len(cut) == 1 and cut[0] == crash['observed'] and cut[0]['cut'] == crash['cut']
         and cut[0]['mode'] == crash['mode'], 'missing/mismatched protocol crash cut')
    need(crash['mode'] in ('kill', 'halt') and crash['exitCode'] == (-9 if crash['mode'] == 'kill' else 71), 'wrong process termination')
    need(any(r['event'] == 'STARTED' and r['pid'] != crash['pid'] and r['generation'] == 2
             for r in traces[crash['node']]), 'missing retained public restart')
    before = [r for r in rows if r['order'] < cut[0]['order']]
    event, _, detail = crash['cut'].partition(':')
    need(before and before[-1]['event'] == event and (not detail or before[-1].get('cut') == detail),
         'crash marker lacks its exact observed boundary')
    return before


def tail_decision(selections, encoded_entry, owner, preserved):
    need(any((s['nextEntry'] == encoded_entry if preserved else s['nextEntry'] is None)
             and ((owner in {b['node'] for b in s['bases']}) == preserved) for s in selections),
         'minority selection does not match its actual frozen quorum')


def validate(root, traces, history, receipt):
    root = Path(root); case = receipt['case']
    encoded = (root/'node-1/manifest.gsr').read_bytes()
    manifest = dict(a.f.inspect(encoded, 'MANIFEST'), digest=encoded[16:48].hex())
    def wire(row, key='frame'): return a.f.wire(a.raw(row[key]), manifest)
    replies = [(node, row, wire(row), wire(row, 'request')) for node, rows in traces.items()
               for row in rows if row['event'] == 'REPLY']
    if case == 'competing-campaigns':
        epochs = {}
        for node, rows in traces.items():
            scoped = [r for r in rows if r['generation'] == 1 and r['order'] <= receipt['isolatedThrough'][node]]
            promises = [a.f.inspect(a.raw(r['record']), 'PROMISE') for r in scoped if r['event'] == 'FORCE' and r['kind'] == 'PROMISE']
            own = [p['epoch'] for p in promises if p['proposer'] == node and p['epoch'] > 1]
            need(own and any(r['event'] == 'NETWORK_DROP' for r in scoped), 'missing isolated self campaign/drop')
            need(not any(r['event'] in ('PUBLISHED', 'READ_CAPTURED') for r in scoped), 'isolated voter published without quorum')
            epochs[node] = max(own)
        need(len(set(epochs.values())) == 3, 'competing campaign ballots not distinct')
        return dict(status='PASS', campaigns=epochs)
    if case.startswith('asymmetric-'):
        barrier = 'BEFORE_REQUEST_WRITE' if case == 'asymmetric-requests' else 'AFTER_RESPONSE_READ'
        drops = [r for r in traces['node-1'] if r['event'] == 'NETWORK_DROP' and r['generation'] == 1
                 and r['order'] <= receipt['faultThrough']['node-1']]
        need(drops, 'missing directional drops')
        for row in drops:
            req = wire(row, 'request')
            need(req['sender'] == 'node-1' and req['recipient'] != 'node-1' and row['barrier'] == barrier
                 and row['rule'] in receipt['rules'], 'wrong directed fault')
            if barrier == 'AFTER_RESPONSE_READ':
                need(any(own['request'] == row['request'] for _, own, _, _ in replies), 'lost response without actual peer execution')
        need(any(node == 'node-1' and row['generation'] == 1 and row['order'] <= receipt['faultThrough'][node]
                 and response['type'] != 'REJECT' and req['sender'] != node and req['recipient'] == node
                 for node, row, response, req in replies), 'reverse network direction not exercised')
        return dict(status='PASS', direction='node-1 -> peers', barrier=barrier, dropped=len(drops))

    expected = {'minority-discarded': 'ACCEPT_AFTER_FORCE', 'minority-selected': 'ACCEPT_AFTER_FORCE'}
    for mode in ('halt', 'kill'):
        expected.update({f'basis-{mode}': 'WIRE_BEFORE_RESPONSE_WRITE_BASIS_CHUNK:continuation',
                         f'snapshot-progress-{mode}': 'STORAGE_CUT:TRANSFER_PROGRESS_BEFORE_ACK',
                         f'snapshot-selector-{mode}': 'STORAGE_CUT:SELECTOR_BEFORE_ACK'})
    crash = receipt['crash']
    need(case in expected and crash['cut'] == expected[case], 'wrong boundary for declared scenario')
    before = crash_rows(traces, crash)
    archive = root/'before-reopen.tar.gz'
    need(a.storage.sha(archive.read_bytes()) == receipt['retained']['sha256'], 'pre-reopen archive identity')
    with tarfile.open(archive) as tar:
        files = {m.name.removeprefix(crash['node']+'/'): tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
    need({p: dict(size=len(data), sha256=a.storage.sha(data)) for p, data in files.items()} == receipt['retained']['inventory'], 'pre-reopen archive inventory')
    if case.startswith('minority-'):
        op = next(op for op in history if op['opId'] == receipt['target'])
        need(op['outcome'] == 'PENDING' and op['pid'] == crash['pid'], 'minority response was not uncertain')
        votes = []
        for node, rows in traces.items():
            for row in rows:
                if row['event'] != 'FORCE' or row['kind'] != 'ACCEPT': continue
                vote = a.f.inspect(a.raw(row['record']), 'ACCEPT'); entry = a.f.inspect(a.raw(vote['entry']), 'ENTRY')
                if entry['operation'] == 4 and [dict(id=k, value=v) for k, v in a.documents_command(a.raw(entry['payload']))] == op['documents']:
                    votes.append((node, row, vote, entry))
        original = [v for v in votes if v[0] == crash['node'] and v[1] in before]
        need(len(original) == 1, 'missing exact minority force')
        _, _, vote, entry = original[0]; epoch = vote['epoch']; digest = vote['entryDigest']
        need({node for node, _, v, _ in votes if v['epoch'] == epoch} == {crash['node']}, 'tail already had an entry quorum')
        report = receipt['retained']['inspection']
        need(report['acceptedThrough'] == entry['index'] == report['provenThrough']+1, 'tail is not longer than proven prefix')
        selected = []
        for _, _, response, _ in replies:
            if response['type'] == 'SELECTED_OFFER' and response['payload']['response']:
                value = a.f.inspect(a.raw(response['payload']['selected']), 'SELECTED')
                if value['ballot']['epoch'] > epoch and value['prefixIndex'] == entry['index']-1: selected.append(value)
        need(selected, 'no later selection at minority slot')
        final = next(op for op in reversed(history) if op['kind'] == 'read' and op['outcome'] == 'SUCCESS')
        preserved = case == 'minority-selected'
        need(all((d in final['documents']) == preserved for d in op['documents']), 'wrong minority tail result')
        tail_decision(selected, vote['entry'], crash['node'], preserved)
        if preserved:
            need(any(s['nextEntry'] == vote['entry'] for s in selected), 'retained minority was not selected from frozen bases')
            higher = {(v['epoch'], v['incarnation']): {n for n, _, w, _ in votes if (w['epoch'], w['incarnation']) == (v['epoch'], v['incarnation'])}
                      for _, _, v, _ in votes if v['epoch'] > entry['originEpoch']}
            need(any(len(nodes) >= 2 for nodes in higher.values()), 'missing higher-acceptance quorum for original entry')
        else:
            need(all(v['epoch'] == epoch for _, _, v, _ in votes), 'discarded minority was reaccepted')
            replacements = {}
            for node, rows in traces.items():
                for row in rows:
                    if row['event'] != 'FORCE' or row['kind'] != 'ACCEPT': continue
                    later = a.f.inspect(a.raw(row['record']), 'ACCEPT'); replacement = a.f.inspect(a.raw(later['entry']), 'ENTRY')
                    if replacement['index'] == entry['index'] and later['epoch'] > epoch and later['entryDigest'] != digest:
                        replacements.setdefault((later['epoch'], later['incarnation'], later['entryDigest']), set()).add(node)
            need(any(len(nodes) >= 2 for nodes in replacements.values()), 'minority slot not superseded by an actual quorum')
        return dict(status='PASS', index=entry['index'], originEpoch=entry['originEpoch'], entryDigest=digest, preserved=preserved)

    if case.startswith('basis-'):
        boundary = next((r for r in reversed(before) if r['event'] == 'WIRE_BEFORE_RESPONSE_WRITE_BASIS_CHUNK'), None)
        need(boundary is not None, 'missing interrupted basis request')
        req = wire(boundary, 'request'); p = req['payload']; need(p['offset'] > 0, 'basis never transferred a prefix')
        parts = [(response['payload']['offset'], a.raw(response['payload']['chunk'])) for node, row, response, request in replies
                 if node == crash['node'] and row['pid'] == crash['pid'] and row['order'] < crash['observed']['order']
                 and response['type'] == 'BASIS_CHUNK' and response['payload']['basisId'] == p['basisId']]
        prefix = ranges(parts, p['offset'])
        # The source can itself be the candidate: its own descriptor is advertised in
        # SELECTED_OFFER, not a PROMISE response, and the install reply has not happened
        # at this cut. Bind to the exact pre-crash frozen descriptor AND image instead.
        frozen = []
        for path, data in files.items():
            if path.startswith('basis/') and path.endswith('/basis.gsr'):
                b = a.f.contextual_frame(data, 'BASIS', manifest)
                if b['basisId'] == p['basisId']:
                    image = files[path.removesuffix('basis.gsr')+'image.gsr']
                    a.recovery.basis(data, image, manifest)
                    need(b['node'] == crash['node'] and b['imageBytes'] > len(prefix) and image[:len(prefix)] == prefix,
                         'interrupted basis prefix differs from frozen source')
                    frozen.append(b)
        need(len(frozen) == 1, 'missing incomplete frozen basis binding')
        return dict(status='PASS', kind='basis', interruptedBytes=len(prefix), basisId=p['basisId'])

    meta = a.f.contextual_frame(files['transfer/transfer.gsr'], 'TRANSFER', manifest)
    received = meta['receivedBytes']; total = meta['imageBytes']
    partial = case.startswith('snapshot-progress-')
    need(0 < received < total if partial else 0 < received == total, 'wrong snapshot interruption boundary')
    chunks = []
    for rows in traces.values():
        for row in rows:
            if row['event'] != 'WIRE_BEFORE_REQUEST_WRITE_SNAPSHOT_CHUNK': continue
            req = wire(row, 'request'); p = req['payload']
            if p['transferId'] == meta['transferId'] and req['recipient'] == crash['node']:
                need(req['sender'] == req['proposer'] == meta['ballot']['proposer']
                     and req['epoch'] == meta['ballot']['epoch']
                     and req['incarnationId'] == meta['ballot']['incarnation'], 'snapshot transfer ballot changed')
                chunks.append((p['offset'], a.raw(p['chunk'])))
    prefix = ranges(chunks, received)
    need(files['transfer/image.gsr'][:received] == prefix, 'durable snapshot bytes differ from actual transfer')
    if not partial:
        image = a.f.contextual_frame(files['transfer/image.gsr'], 'IMAGE', manifest)
        need(files['transfer/image.gsr'][16:48].hex() == meta['imageDigest'], 'snapshot image digest')
        selector = a.f.contextual_frame(files['current.gsr'], 'SELECTOR', manifest)
        need(a.raw(image['snapshot']) == files[selector['generation']+'/snapshot.gsr'], 'selector did not install exact transferred snapshot')
    return dict(status='PASS', kind='snapshot', receivedBytes=received, imageBytes=total, partial=partial)


def negatives(root, traces, history, receipt):
    case = receipt['case']; changes = []
    if case == 'competing-campaigns':
        changes = [('missing-self-promises', lambda r: r['event'] == 'FORCE' and r['kind'] == 'PROMISE')]
    elif case.startswith('asymmetric-'):
        changes = [('missing-directional-drop', lambda r: r['event'] == 'NETWORK_DROP'),
                   ('missing-peer-replies', lambda r: r['event'] == 'REPLY')]
    else:
        event = receipt['crash']['cut'].split(':')[0]
        changes = [('missing-crash-cut', lambda r: r['event'] == 'CUT_REACHED'),
                   ('missing-observed-boundary', lambda r: r['event'] == event),
                   ('missing-restart', lambda r: r['event'] == 'STARTED' and r['generation'] == 2)]
        if case.startswith('minority-'):
            changes.append(('missing-selection', lambda r: r['event'] == 'REPLY' and json.loads(a.raw(r['frame'])[48:])['type'] == 'SELECTED_OFFER'))
        elif case.startswith('basis-'):
            changes.append(('missing-basis-prefix', lambda r: r['event'] == 'REPLY' and json.loads(a.raw(r['frame'])[48:])['type'] == 'BASIS_CHUNK'))
        else: changes.append(('missing-snapshot-prefix', lambda r: r['event'] == 'WIRE_BEFORE_REQUEST_WRITE_SNAPSHOT_CHUNK'))
    results = []
    for name, remove in changes:
        changed = {n: [r for r in rows if not remove(r)] for n, rows in traces.items()}
        try: validate(root, changed, history, receipt)
        except ValueError as error: results.append(dict(case=name, status='REJECTED', reason=str(error)))
        else: raise ValueError('public protocol oracle admitted ' + name)
    return results
