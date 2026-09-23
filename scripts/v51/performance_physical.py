"""Independent rich automatic force/wire/publication/read audit. No product imports."""
from pathlib import Path
from . import performance_model as m, performance_projection as projection
from . import format_inspector as f, storage_inspector as storage, recovery_inspector as recovery

need = m.need
raw = projection.raw


def automatic(root, calls, traces):
    root = Path(root)
    manifest_bytes = (root / 'node-1/manifest.gsr').read_bytes()
    votes = {n: [raw(r['record']) for r in rows if r['event'] == 'FORCE' and r['kind'] == 'ACCEPT'] for n, rows in traces.items()}
    projected = projection.project(manifest_bytes, (root / 'node-1/genesis.gsr').read_bytes(), votes)
    manifest = projected['manifest']
    need(set(traces) == {'node-1', 'node-2', 'node-3'}, 'rich voter coverage')
    reports = {node: storage.inspect(root / node, 64 << 20, 1 << 20) for node in traces}
    need(0 < len(projected['chosen']) <= 192, 'automatic slot ceiling')
    need(all(r['provenThrough'] >= max(projected['chosen']) for r in reports.values()), 'voter missing final durable cut')
    replies, descriptors, parts, selections = set(), {}, {}, {}
    for node, rows in traces.items():
        for row in rows:
            need(row['node'] == node and row['manifestDigest'] == manifest['digest'] and row['groupId'] == manifest['groupId'], 'trace manifest owner')
            if row['event'] == 'FORCE':
                encoded = raw(row['record'])
                f.contextual_frame(encoded, row['kind'], manifest)
                need(len(encoded) <= 16384, 'rich forced record encoding ceiling')
            if row['event'] == 'REPLY':
                replies.add(m.sha(raw(row['frame'])))
            if row['event'] not in ('REPLY', 'RECEIVED'):
                continue
            need(len(raw(row['frame']))<=1<<20 and len(raw(row['request']))<=1<<20, 'automatic frame bound')
            message = f.wire(raw(row['frame']), manifest)
            payload = message['payload']
            basis_records = [payload['basis']] if message['type'] == 'PROMISE' else payload['bases'] if message['type'] == 'SELECTED_OFFER' else []
            for encoded in basis_records:
                value = f.contextual_frame(raw(encoded), 'BASIS', manifest)
                key = value['node'], value['basisId']
                need(key not in descriptors or descriptors[key] == raw(encoded), 'changed frozen basis')
                descriptors[key] = raw(encoded)
            if message['type'] == 'BASIS_CHUNK' and payload['action'] == 'DATA':
                key = message['sender'], payload['basisId']
                chunks = parts.setdefault(key, {})
                need(payload['offset'] not in chunks or chunks[payload['offset']] == raw(payload['chunk']), 'changed transferred basis')
                chunks[payload['offset']] = raw(payload['chunk'])
            if message['type'] == 'SELECTED_OFFER' and payload['response']:
                value = f.contextual_frame(raw(payload['selected']), 'SELECTED', manifest)
                selections[(value['ballot']['epoch'], value['ballot']['incarnation'])] = value
    for selected in selections.values():
        bases = []
        for binding in selected['bases']:
            key = binding['node'], binding['basisId']
            need(key in descriptors and key in parts, 'missing transferred frozen basis')
            image = b''
            for offset, chunk in sorted(parts[key].items()):
                need(offset == len(image), 'basis transfer hole')
                image += chunk
            need(descriptors[key][16:48].hex() == binding['basisDigest'], 'basis descriptor binding')
            bases.append(recovery.basis(descriptors[key], image, manifest))
        recovery.select(selected, bases, manifest)
    expected = {r['opId']: r for r in calls}
    successes, read_barriers, mutations = set(), set(), set()
    publications = 0
    for node, rows in traces.items():
        forced, remote_votes, remote_proofs, published = set(), set(), set(), {}
        own_votes, promise, current, capture, validated = {}, None, None, None, None
        reservation_ids = set()
        for row in rows:
            event = row['event']
            if event == 'TRANSPORT':
                transition, identity = row['transition'], row['reservation']
                if transition.endswith('_ADMITTED'):
                    need(identity > 0 and identity not in reservation_ids, 'duplicate transport reservation')
                    reservation_ids.add(identity)
                elif transition.endswith('_RELEASED'):
                    need(identity in reservation_ids, 'unmatched transport release')
                    reservation_ids.remove(identity)
                else:
                    need(transition.endswith('_REJECTED'), 'unknown transport observation')
            elif event == 'FORCE':
                encoded = raw(row['record'])
                value = f.contextual_frame(encoded, row['kind'], manifest)
                forced.add((row['kind'], m.sha(encoded)))
                if row['kind'] == 'PROMISE':
                    promise = value['epoch'], value['incarnation']
                if row['kind'] == 'ACCEPT':
                    entry = f.contextual_frame(raw(value['entry']), 'ENTRY', manifest)
                    own_votes[(value['epoch'], value['incarnation'], entry['index'], value['entryDigest'])] = row['order']
                if row['kind'] == 'PROOF':
                    need(projected['chosen'].get(value['index']) == value['entryDigest'], 'proof lacks chosen acceptance quorum')
                    if value['proposer'] == node:
                        need(any((v['voter'], value['epoch'], value['incarnation'], value['index'], value['entryDigest']) in remote_votes
                                 for v in value['receipts'] if v['voter'] != node), 'leader proof before remote acceptance')
            elif event in ('REPLY', 'RECEIVED'):
                message = f.wire(raw(row['frame']), manifest)
                request = f.wire(raw(row['request']), manifest)
                payload, kind = message['payload'], message['type']
                need(all(message[k] == request[k] for k in ('traceId', 'eventSequence', 'epoch', 'incarnationId', 'proposer'))
                     and request['sender'] == message['recipient'] and request['recipient'] == message['sender'], 'wire response correlation')
                if event == 'RECEIVED':
                    need(m.sha(raw(row['frame'])) in replies, 'unobserved response owner')
                    if kind == 'COMMIT_PROOF_ACK':
                        remote_proofs.add(payload['proofDigest'])
                    if kind == 'ACCEPT_ACK':
                        remote_votes.add((message['sender'], message['epoch'], message['incarnationId'], payload['index'], payload['entryDigest']))
                elif kind == 'COMMIT_PROOF_ACK':
                    need(('PROOF', payload['proofDigest']) in forced, 'proof reply before own exact force')
                elif kind == 'ACCEPT_ACK':
                    need((message['epoch'], message['incarnationId'], payload['index'], payload['entryDigest']) in own_votes, 'accept reply before own exact force')
            elif event == 'PUBLISHED':
                snapshot = f.contextual_frame(raw(row['snapshot']), 'SNAPSHOT', manifest)
                projection.snapshot(projected, raw(row['snapshot']))
                proof = f.contextual_frame(raw(snapshot['terminalProof']), 'PROOF', manifest)
                digest = m.sha(raw(snapshot['terminalProof']))
                need(('PROOF', digest) in forced and digest in remote_proofs, 'publish before own force and remote proof acknowledgement')
                need((proof['epoch'], proof['incarnation']) in selections, 'publish without independently validated election selection')
                published[len(snapshot['anchors'])] = (snapshot, row['order'])
                publications += 1
            elif event == 'CLIENT_INVOKE':
                need(current is None, 'overlapping single-caller commands')
                current = row
            elif event == 'READ_CAPTURE_VALIDATED':
                need((row['epoch'], f.inspect(raw(published[row['index']][0]['terminalProof']), 'PROOF')['incarnation']) == promise,
                     'read capture after changed promise')
                validated = row
            elif event == 'READ_CAPTURED':
                need(current is not None and validated is not None and capture is None, 'read capture ownership')
                need(all(row[k] == validated[k] for k in ('index', 'sequence', 'epoch')), 'capture validation differs')
                snapshot, order = published[row['index']]
                digest = snapshot['anchors'][-1]['entryDigest']
                entry = projected['entries'][digest]
                proof = f.inspect(raw(snapshot['terminalProof']), 'PROOF')
                vote = (proof['epoch'], proof['incarnation'], proof['index'], digest)
                need(entry['operation'] == 9 and digest not in read_barriers and
                     current['order'] < own_votes.get(vote, -1) < order < row['order'], 'missing/reused/pre-invocation read barrier')
                read_barriers.add(digest)
                capture = dict(row=row, snapshot=snapshot, released=False)
                validated = None
            elif event == 'READ_RELEASED':
                need(capture is not None and all(row[k] == capture['row'][k] for k in ('index', 'sequence', 'epoch')), 'read release cut')
                capture['released'] = True
            elif event == 'CLIENT_RESULT':
                need(current is not None and current['opId'] == row['opId'], 'unmatched command result')
                if row['command'] == 'call':
                    call = expected.get(row['opId'])
                    need(call is not None and row['call']['outcome'] == 'SUCCESS' and call['pid'] == row['pid'] and call['node'] == node, 'unrecorded/failed rich call')
                    need(all(row['call'][k] == call[k] for k in row['call']), 'controller differs from original result')
                    operation = call['operation']
                    if operation in m.OP_IDS:
                        matches = [(i, digest) for i, digest in projected['chosen'].items()
                                   if projected['entries'][digest]['operation'] == m.OP_IDS[operation]
                                   and projected['entries'][digest]['payloadDigest'] == call['payloadSha256']]
                        # Index create/drop payloads intentionally repeat; bind this one by its
                        # exact sequence and the publication inside the invocation interval.
                        matches = [(i, d) for i, d in matches if projected['states'][i].sequence == call['afterSequence']
                                   and i in published and current['order'] < published[i][1] < row['order']]
                        need(len(matches) == 1, 'successful mutation lacks its own publication')
                        mutations.add(matches[0][1])
                        need(capture is None, 'mutation consumed hidden strong read')
                    else:
                        need(capture is not None and capture['released'], 'read result before released capture')
                        state = m.application(raw(capture['snapshot']['application']), capture['snapshot']['applicationSequence'])
                        need(state.answer(operation, call['cycle']) == call['answer'] and state.sequence == call['afterSequence'], 'answer differs from exact captured application')
                    successes.add(row['opId'])
                elif row['command'] == 'backup':
                    need(capture is not None and capture['released'] and row['sequence'] == capture['row']['sequence'], 'backup captured cut')
                else:
                    need(capture is None, 'unaccounted auxiliary barrier')
                current, capture = None, None
        need(not reservation_ids and current is None and capture is None, 'unsettled transport/client capture')
        report = reports[node]
        for index, digest in projected['chosen'].items():
            if report['provenThrough'] >= index:
                need(report['acceptedDigests'][index-1] == digest, 'retained rich prefix changed')
    need(successes == set(expected) and len(mutations) == 72 and len(read_barriers) == 19, 'rich schedule/auxiliary barrier accounting')
    need(all(entry['operation'] == 9 or digest in mutations for digest, entry in projected['entries'].items()), 'extra application mutation')
    need(len(projected['chosen']) - 72 - len(read_barriers) <= 64, 'activation recovery NO_OP allowance')
    return dict(status='PASS', chosen=len(projected['chosen']), mutations=len(mutations), readBarriers=len(read_barriers),
                publications=publications, finalSequence=projected['states'][max(projected['chosen'])].sequence,
                retained={n:dict(provenIndex=r['provenThrough'], bytes=sum(v['size'] for v in storage.inventory(root/n).values())) for n,r in reports.items()})
