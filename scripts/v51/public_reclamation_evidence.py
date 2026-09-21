"""Decode two complete floor sources, real downloads and interrupted retirement bytes."""
import base64
import copy
import json
from pathlib import Path
import struct
import tarfile
from . import runtime_evidence as a, rejoin_evidence as rejoin, public_protocol_evidence as protocol
from .storage_harness import need

SOURCE_FILES = ('accepted.gsr', 'current.gsr', 'generation.gsr', 'proofs.gsr', 'snapshot.gsr')
GENERATION_FILES = ('accepted.gsr', 'proofs.gsr', 'snapshot.gsr', 'generation.gsr')
CUTS = ('FLOOR_BEFORE_WRITE', 'FLOOR_AFTER_FORCE', 'FLOOR_BEFORE_ACK',
        'DELETE_AFTER_FILE', 'DELETE_AFTER_DIRECTORY', 'DELETE_AFTER_ROOT_TRUNCATE')


def authority(row):
    entries = row['authority']
    need(len({f['name'] for f in entries}) == len(entries), 'duplicate observed authority file')
    return {f['name']: a.raw(f['bytes']) for f in entries}


def packet(files, prefix):
    need(all(prefix+name in files for name in SOURCE_FILES), 'incomplete retained recovery source')
    return {'files': [dict(name=name, bytes=base64.b64encode(files[prefix+name]).decode()) for name in SOURCE_FILES]}


def floor_state(files, manifest, node, marker='recovery-floor.gsr'):
    need(marker in files, 'missing durable recovery floor')
    floor = a.f.contextual_frame(files[marker], 'FLOOR', manifest)
    owners = [s['node'] for s in floor['sources']]
    need(floor['node'] == node and len(owners) == 2 and len(set(owners)) == 2 and node in owners, 'floor needs two distinct sources including local')
    for slot in ('floor-a', 'floor-b'):
        prefixes = [f'transfer/{slot}/{owner}/' for owner in owners]
        if not all(prefix+'generation.gsr' in files and files[prefix+'generation.gsr'][16:48].hex() == row['generationDigest']
                   for prefix, row in zip(prefixes, floor['sources'])): continue
        packets = [packet(files, prefix) for prefix in prefixes]
        sources = [rejoin.packet(p, manifest) for p in packets]
        for row, source in zip(floor['sources'], sources):
            need(source['seal']['node'] == row['node'] and source['sealDigest'] == row['generationDigest']
                 and source['snapshotDigest'] == row['snapshotDigest'], 'floor source binding')
            need(len(source['snapshot']['anchors']) == floor['index'] and a.recovery.entry_digest(source['snapshot']) == floor['entryDigest'], 'floor cut mismatch')
        a.recovery.agree(sources[0]['snapshot'], sources[1]['snapshot'], floor['index'])
        selector = a.f.contextual_frame(files['current.gsr'], 'SELECTOR', manifest)
        current = a.f.contextual_frame(files[selector['generation']+'/snapshot.gsr'], 'SNAPSHOT', manifest)
        need(selector['node'] == node and len(current['anchors']) >= floor['index'], 'floor exceeds current generation')
        a.recovery.agree(current, sources[0]['snapshot'], floor['index'])
        return floor, packets, sources
    raise ValueError('floor lacks both exact retained sources')


def downloads(rows, manifest):
    """Only completed, hash-bound downloads in this process can authorize its floor."""
    offers = {}; parts = {}; completed = []
    for row in rows:
        if row['event'] != 'RECEIVED': continue
        message = a.f.wire(a.raw(row['frame']), manifest); p = message['payload']
        request = a.f.wire(a.raw(row['request']), manifest)
        key = row['pid'], message['sender'], p.get('transferId')
        if message['type'] == 'SOURCE_OFFER' and request['payload']['sourceBytes'] == 0:
            offers[key] = (p, message)
        if message['type'] == 'SOURCE_CHUNK' and p['action'] == 'DATA':
            need(key in offers, 'source chunk has no download offer')
            offer, binding = offers[key]
            need(all(message[k] == binding[k] for k in ('epoch', 'incarnationId', 'proposer', 'recipient', 'traceId')), 'source download ballot/session changed')
            own = parts.setdefault(key, {}); chunk = a.raw(p['chunk']); offset = p['offset']
            need(offset not in own or own[offset] == chunk, 'source download retry changed')
            own[offset] = chunk
            if sum(map(len, own.values())) == offer['sourceBytes']:
                data = protocol.ranges(list(own.items()), offer['sourceBytes'])
                need(a.storage.sha(data) == offer['sourceDigest'], 'source download digest')
                value = json.loads(data); source = rejoin.packet(value, manifest)
                need(source['seal']['node'] == message['sender'] and len(source['snapshot']['anchors']) == offer['index'], 'source download owner/cut')
                completed.append(dict(pid=row['pid'], order=row['order'], owner=message['sender'], bytes=data))
    return completed


def require_download(packets, node, row, completed):
    remote = [p for p in packets if a.f.inspect(a.raw(next(f['bytes'] for f in p['files'] if f['name'] == 'generation.gsr')), 'GENERATION')['node'] != node]
    need(len(remote) == 1, 'floor remote source count')
    data = a.storage.canonical(remote[0])
    need(any(d['pid'] == row['pid'] and d['order'] < row['order'] and d['bytes'] == data for d in completed),
         'floor lacks an earlier complete peer download in the same process')


def journal_rows(data, kind, manifest):
    result = []; offset = 0
    while offset < len(data):
        need(len(data)-offset >= 48, 'torn retirement journal')
        size = struct.unpack('>i', data[offset+12:offset+16])[0]+48
        need(48 < size <= len(data)-offset, 'retirement journal frame bound')
        value = a.f.contextual_frame(data[offset:offset+size], 'JOURNAL' if offset == 0 else kind, manifest)
        if offset: result.append(value)
        offset += size
    need(offset > 0, 'empty retirement journal')
    return result


def retirement_bound(files, prefix, floor, snapshot, manifest):
    for name, kind in (('accepted.gsr', 'ACCEPT'), ('proofs.gsr', 'PROOF')):
        for row in journal_rows(files[prefix+name], kind, manifest):
            value = a.f.contextual_frame(a.raw(row['entry']), 'ENTRY', manifest) if kind == 'ACCEPT' else row
            index = value['index']; need(index <= floor['index'], 'deleted history exceeds durable floor')
            if kind == 'PROOF': need(value['entryDigest'] == snapshot['anchors'][index-1]['entryDigest'], 'retired proof conflicts with durable snapshot')


def truncated_journal(before, after, kind, manifest):
    need(journal_rows(before, kind, manifest) and not journal_rows(after, kind, manifest),
         'root journal was not actually truncated')
    header_size = struct.unpack('>i', before[12:16])[0]+48
    need(after == before[:header_size], 'root journal truncation changed its original header')


def validate(root, traces, history, receipt):
    root = Path(root); crash = receipt['crash']; node = crash['node']; cut = receipt['cut']
    need(cut in CUTS and crash['cut'] == 'STORAGE_CUT:'+cut, 'wrong reclamation scenario cut')
    encoded = (root/'node-1/manifest.gsr').read_bytes()
    manifest = dict(a.f.inspect(encoded, 'MANIFEST'), digest=encoded[16:48].hex())
    for own, rows in traces.items():
        blocked = [r for r in rows if r['generation'] == 1 and r['order'] <= receipt['blockedThrough'][own]]
        need(not any(r['event'] == 'RECOVERY_FLOOR' or r['event'] == 'STORAGE_CUT' and
                     (r['cut'].startswith('FLOOR_') or r['cut'].startswith('DELETE_')) for r in blocked), 'reclamation without an available second source')
    need(any(r['event'] == 'NETWORK_DROP' and 'SOURCE_' in r.get('rule', '')
             and r['order'] <= receipt['blockedThrough'][node] for r in traces[node] if r['generation'] == 1), 'peer source block not observed')
    before = protocol.crash_rows(traces, crash); boundary = before[-1]
    need('authority' in boundary, 'missing authority at reclamation boundary')
    captured = authority(boundary)
    archive = root/'before-reopen.tar.gz'
    need(a.storage.sha(archive.read_bytes()) == receipt['retained']['sha256'], 'pre-reopen archive changed')
    with tarfile.open(archive) as tar:
        files = {m.name.removeprefix(node+'/'): tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
        directories = {m.name.removeprefix(node+'/') for m in tar.getmembers() if m.isdir()}
    need({p: dict(size=len(v), sha256=a.storage.sha(v)) for p, v in files.items()} == receipt['retained']['inventory'], 'archive inventory changed')
    need(captured and all(files.get(p) == v for p, v in captured.items()), 'archived bytes differ from interrupted boundary')

    completed = downloads(traces[node], manifest)
    floor_events = [r for r in before if r['event'] == 'STORAGE_CUT' and r['cut'] == 'FLOOR_BEFORE_ACK']
    need(floor_events, 'missing observed durable floor publication')
    # Check every publication before the interruption against its own prior download.
    for row in floor_events:
        observed = authority(row)
        _, packets, _ = floor_state(observed, manifest, node)
        require_download(packets, node, row, completed)
    floor, packets, sources = floor_state(files, manifest, node)
    publication = floor_events[-1]
    need(authority(publication)['recovery-floor.gsr'] == files['recovery-floor.gsr'], 'floor publication differs from durable marker')
    if cut == 'FLOOR_AFTER_FORCE':
        pending, pending_packets, _ = floor_state(files, manifest, node, 'recovery-floor.pending.gsr')
        need(pending['index'] >= floor['index'] and files['recovery-floor.pending.gsr'] != files['recovery-floor.gsr'], 'pending floor incorrectly treated as committed')
        require_download(pending_packets, node, boundary, completed)
    elif cut == 'FLOOR_BEFORE_WRITE':
        need('recovery-floor.pending.gsr' not in files, 'before-write cut contains new pending floor')
    if cut.startswith('DELETE_'):
        baseline = authority(publication)
        need(files['promises.gsr'] == baseline['promises.gsr'], 'reclamation changed root promise history')
        selector = a.f.contextual_frame(files['current.gsr'], 'SELECTOR', manifest)
        active = selector['generation']; inactive = 'generation-b' if active == 'generation-a' else 'generation-a'
        # Current generation files remain byte-identical across physical retirement.
        need(all(files[active+'/'+name] == baseline[active+'/'+name] for name in GENERATION_FILES), 'reclamation changed active generation')
        if cut in ('DELETE_AFTER_FILE', 'DELETE_AFTER_DIRECTORY'):
            retired = rejoin.packet(packet(files, 'transfer/retiring/'), manifest)
            need(retired['selector']['generation'] == inactive and len(retired['snapshot']['anchors']) <= floor['index'], 'wrong retired generation/floor')
            a.recovery.agree(sources[0]['snapshot'], retired['snapshot'], len(retired['snapshot']['anchors']))
            retirement_bound(files, 'transfer/retiring/', floor, sources[0]['snapshot'], manifest)
            expected_missing = {'accepted.gsr'} if cut == 'DELETE_AFTER_FILE' else set(GENERATION_FILES)
            need({name for name in GENERATION_FILES if inactive+'/'+name not in files} == expected_missing, 'wrong physical deletion boundary')
            need((inactive in directories) == (cut == 'DELETE_AFTER_FILE'), 'wrong physical directory deletion boundary')
            for name in GENERATION_FILES:
                need(files['transfer/retiring/'+name] == baseline[inactive+'/'+name], 'retirement evidence changed old bytes')
                if name not in expected_missing: need(files[inactive+'/'+name] == baseline[inactive+'/'+name], 'undeleted old generation changed')
        else:
            truncated_journal(baseline['accepted.gsr'], files['accepted.gsr'], 'ACCEPT', manifest)
            need(files['proofs.gsr'] == baseline['proofs.gsr'], 'root truncation crossed second journal boundary')
            retirement_bound(baseline, '', floor, sources[0]['snapshot'], manifest)
    # Require a fresh post-restart floor, backed by a download in the reopened JVM.
    recovered = receipt['recoveredFloor']
    need(recovered in traces[node] and recovered['generation'] == 2 and recovered['index'] > floor['index'], 'missing advanced post-restart recovery floor')
    later = [r for r in traces[node] if r['pid'] == recovered['pid'] and r['order'] < recovered['order']
             and r['event'] == 'STORAGE_CUT' and r['cut'] == 'FLOOR_BEFORE_ACK']
    need(later, 'recovered floor lacks publication')
    later_floor, later_packets, _ = floor_state(authority(later[-1]), manifest, node)
    need(later_floor['index'] == recovered['index'], 'post-restart floor cut changed')
    require_download(later_packets, node, later[-1], completed)
    return dict(status='PASS', cut=cut, floor=floor['index'], owners=[s['node'] for s in floor['sources']],
                recoveredFloor=recovered['index'], completedDownloads=len(completed), durablePublications=len(floor_events))


def negatives(root, traces, history, receipt):
    node = receipt['crash']['node']; results = []
    for name in ('missing-peer-download', 'missing-floor-publication', 'missing-crash-boundary', 'missing-restart', 'changed-source-file', 'duplicate-source-owner'):
        changed = copy.deepcopy(traces)
        if name == 'missing-peer-download':
            changed[node] = [r for r in changed[node] if r['event'] != 'RECEIVED' or json.loads(a.raw(r['frame'])[48:])['type'] != 'SOURCE_CHUNK']
        elif name == 'missing-floor-publication':
            changed[node] = [r for r in changed[node] if r['event'] != 'STORAGE_CUT' or r['cut'] != 'FLOOR_BEFORE_ACK']
        elif name == 'missing-crash-boundary': changed[node] = [r for r in changed[node] if r['event'] != 'CUT_REACHED']
        elif name == 'missing-restart': changed[node] = [r for r in changed[node] if r['event'] != 'STARTED' or r['generation'] != 2]
        else:
            row = next(r for r in changed[node] if r['event'] == 'STORAGE_CUT' and r['cut'] == 'FLOOR_BEFORE_ACK')
            files = {f['name']: f['bytes'] for f in row['authority']}; floor = a.f.inspect(a.raw(files['recovery-floor.gsr']), 'FLOOR')
            local = node; remote = next(s['node'] for s in floor['sources'] if s['node'] != node)
            for slot in ('floor-a', 'floor-b'):
                path = f'transfer/{slot}/{remote}/generation.gsr'
                if path in files and a.raw(files[path])[16:48].hex() == next(s['generationDigest'] for s in floor['sources'] if s['node'] == remote):
                    suffix = 'snapshot.gsr' if name == 'changed-source-file' else 'generation.gsr'
                    path = f'transfer/{slot}/{remote}/{suffix}'
                    files[path] = files[f'transfer/{slot}/{local}/generation.gsr']
                    break
            row['authority'] = [dict(name=p, bytes=v) for p, v in files.items()]
        try: validate(root, changed, history, receipt)
        except ValueError as error: results.append(dict(case=name, status='REJECTED', reason=str(error)))
        else: raise ValueError('reclamation oracle admitted '+name)
    return results
