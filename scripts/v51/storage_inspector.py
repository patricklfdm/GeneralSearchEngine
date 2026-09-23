"""Read-only automatic 1.2 root-ledger oracle; never imports product code or encoders."""
import base64
import hashlib
import json
from pathlib import Path
import struct

from . import format_inspector as f
from . import recovery_inspector as recovery

INITIAL = {'replica.lock', 'manifest.gsr', 'genesis.gsr', 'node.gsr', 'promises.gsr',
           'accepted.gsr', 'proofs.gsr', 'storage-ready.gsr'}
FILES = INITIAL | {'bootstrap-prepared.gsr', 'bootstrap-seal.gsr'}
LEDGERS = {'promises.gsr': ('PROMISE', 4), 'accepted.gsr': ('ACCEPT', 24), 'proofs.gsr': ('PROOF', 6)}


def sha(raw): return hashlib.sha256(raw).hexdigest()
def canonical(v): return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')
def raw(value): return base64.b64decode(value, validate=True)
def ballot(v): return v['epoch'], v['proposer'], v['incarnation']


def inventory(directory):
    result = {}
    for path in sorted(Path(directory).rglob("*")):
        f.need(not path.is_symlink(), 'authority file type')
        if path.is_dir(): continue
        f.need(path.is_file(), 'authority file type')
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b''): digest.update(chunk)
        result[str(path.relative_to(directory))] = {'size': path.stat().st_size, 'sha256': digest.hexdigest()}
    return result


def torn_append(directory, witness):
    """A deliberately quarantined voter is not a valid retained-history report."""
    directory = Path(directory); kind = witness['kind']; relative = Path(witness['path'])
    name = {'ACCEPT': 'accepted.gsr', 'PROOF': 'proofs.gsr'}.get(kind)
    f.need(name is not None and relative.as_posix() in (name, 'generation-a/'+name, 'generation-b/'+name), 'torn journal path/kind')
    before, after = raw(witness['before']), raw(witness['after'])
    f.need(after.startswith(before) and len(after)-len(before) == 64, 'not one exact partial write')
    f.need((directory/relative).read_bytes() == after, 'partial journal changed after failure')
    manifest_bytes = (directory/'manifest.gsr').read_bytes()
    manifest = dict(f.inspect(manifest_bytes, 'MANIFEST'), digest=manifest_bytes[16:48].hex())
    selector = directory/'current.gsr'
    active = f.contextual_frame(selector.read_bytes(), 'SELECTOR', manifest)['generation']+'/' if selector.exists() else ''
    f.need(relative.as_posix() == active+name, 'partial append is not the active journal')
    offset = 0
    while offset < len(before):
        f.need(len(before)-offset >= 48, 'torn pre-failure prefix')
        length = 48+int.from_bytes(before[offset+12:offset+16], 'big', signed=True)
        f.need(48 < length <= len(before)-offset, 'torn pre-failure frame')
        value = f.contextual_frame(before[offset:offset+length], 'JOURNAL' if offset == 0 else kind, manifest)
        if offset == 0: f.need(value['node'] == directory.name and value['recordKind'] == (24 if kind == 'ACCEPT' else 6), 'partial journal identity')
        offset += length
    f.need(offset > 0, 'missing original journal')
    tail = after[offset:]; magic, major, minor, identifier, flags, size = struct.unpack('>4sHHHHi', tail[:16])
    f.need((magic, major, minor, identifier, flags) == (b'GSER', 1, 2, 24 if kind == 'ACCEPT' else 6, 0)
           and 64 < 48+size <= f.load()['records'][kind]['maximum'], 'partial frame not incomplete')
    try: inspect(directory)
    except ValueError as error:
        f.need(str(error) in ('torn ledger body', 'source journal row size'), 'unrelated quarantine cause: '+str(error))
        return dict(status='QUARANTINED', kind=kind, partialBytes=len(tail), reason=str(error))
    raise ValueError('partial write accepted as valid authority')


def inspect_archive(directory, original_path, expected_inventory):
    """Read a displaced, immutable witness; never admit it as live authority."""
    original_path = Path(original_path)
    f.need(not original_path.exists() and not original_path.is_symlink(), 'retired authority still present')
    f.need(bool(expected_inventory) and inventory(directory) == expected_inventory, 'retired inventory changed')
    return _inspect(directory, 8 << 30, 8 << 20, original_path.resolve())


def inspect(directory, maximum_bytes=8 << 30, maximum_frame=8 << 20):
    return _inspect(directory, maximum_bytes, maximum_frame, Path(directory).resolve())


def _inspect(directory, maximum_bytes, maximum_frame, admitted_path):
    directory = Path(directory)
    f.need(not any(p.is_symlink() for p in (directory, *directory.parents)), 'authority symlink')
    before = inventory(directory)
    f.need(FILES <= set(before) and before['replica.lock']['size'] == 0, 'authority inventory')
    f.need(sum(v['size'] for v in before.values()) <= maximum_bytes, 'retained byte capacity')
    for name in FILES - set(LEDGERS):
        f.need(before[name]['size'] <= (f.MAX_IMAGE if name == 'genesis.gsr' else 65536), 'metadata byte capacity')
    manifest_raw = (directory / 'manifest.gsr').read_bytes()
    manifest = dict(f.inspect(manifest_raw, 'MANIFEST'), digest=manifest_raw[16:48].hex())
    voters = [m['node'] for m in manifest['members']]
    for path in directory.rglob('*'):
        f.need(recovery.allowed(path.relative_to(directory).parts, path.is_dir(), voters, FILES | {'bootstrap-binding.gsr'}), 'unknown authority inventory')
    def record(name, kind): return f.contextual_frame((directory / name).read_bytes(), kind, manifest)
    node = record('node.gsr', 'NODE')['node']
    ready = record('storage-ready.gsr', 'READY')
    f.need(ready['node'] == node and ready['genesisDigest'] == manifest['genesisDigest'], 'ready identity')
    seal = record('bootstrap-seal.gsr', 'SEAL')
    f.need(seal['node'] == node, 'local seal')
    receipt = f.inspect(raw(seal['receipt']), 'RECEIPT')
    plan_raw = raw(receipt['plan']); plan = f.inspect(plan_raw, 'PLAN')
    f.need(raw(plan['manifest']) == manifest_raw and raw(plan['genesis']) == (directory / 'genesis.gsr').read_bytes(), 'sealed genesis/manifest')
    genesis = f.inspect(raw(plan['genesis']), 'GENESIS')
    f.need(all(genesis[k] == manifest[k] for k in ('groupId', 'historyId', 'baseSequence', 'schemaDigest', 'indexesDigest')), 'genesis identity')
    target = plan['targets'][voters.index(node)]
    f.need(target['authorityPath'] == str(admitted_path), 'copied/stale seal path')
    preparations = [f.inspect(raw(v), 'PREPARED') for v in receipt['preparations']]
    f.need((directory / 'bootstrap-prepared.gsr').read_bytes() == raw(receipt['preparations'][voters.index(node)]), 'local preparation')
    for t, p in zip(plan['targets'], preparations):
        f.need(p['inventoryDigest'] == sha(canonical(t['files'])), 'preparation inventory digest')
        names = [v['path'] for v in t['files']]
        f.need(names in (sorted(INITIAL), sorted(INITIAL | {'bootstrap-binding.gsr'})), 'ordered initial inventory')
    for item in target['files']:
        name, size = item['path'], item['size']
        f.need(size <= f.MAX_IMAGE and (before[name]['size'] >= size if name in LEDGERS else before[name]['size'] == size), 'missing initial authority')
        with (directory / name).open('rb') as stream: prefix = stream.read(size)
        f.need(sha(prefix) == item['sha256'], 'initial authority bytes')

    active, snapshot, selected, selected_snapshot = recovery.state(directory, manifest, node, genesis)
    base = len(snapshot["anchors"])

    def rows(filename):
        kind, identifier = LEDGERS[filename]
        with ((directory if filename == 'promises.gsr' else active) / filename).open('rb') as stream:
            first = True
            while True:
                header = stream.read(48)
                if not header: break
                f.need(len(header) == 48, 'torn ledger header')
                size = struct.unpack('>i', header[12:16])[0]
                f.need(0 < size <= maximum_frame - 48, 'ledger frame bound')
                body = stream.read(size); f.need(len(body) == size, 'torn ledger body')
                frame = header + body
                value = f.contextual_frame(frame, 'JOURNAL' if first else kind, manifest)
                if first:
                    f.need(value['recordKind'] == identifier and value['node'] == node, 'journal identity')
                    first = False
                else: yield value, frame[16:48].hex()
            f.need(not first, 'absent journal header')

    grants = {}; highest = 0
    for value, digest in rows('promises.gsr'):
        f.need(len(grants) < 10000 and (value['epoch'] == 1 if not grants else value['epoch'] > highest), 'promise history')
        highest = value['epoch']; grants[highest] = ballot(value)
    f.need(grants, 'missing genesis promise')
    if snapshot['terminalProof']:
        f.need(f.inspect(raw(snapshot['terminalProof']), 'PROOF')['epoch'] <= highest, 'snapshot exceeds root promise')
    if selected: f.need(selected['ballot']['epoch'] <= highest, 'selection exceeds root promise')
    accepted = {}; accepted_count = 0; replacements = []
    for value, digest in rows('accepted.gsr'):
        accepted_count += 1; f.need(accepted_count <= 1010000, 'acceptance row capacity')
        entry_raw = raw(value['entry']); entry = f.contextual_frame(entry_raw, 'ENTRY', manifest)
        index = entry['index']; identity = entry_raw[16:48].hex()
        f.need(grants.get(value['epoch']) == ballot(value), 'acceptance promise binding')
        f.need(index <= 1000000 and index in (base + len(accepted), base + len(accepted) + 1), 'acceptance slot order')
        old = accepted.get(index)
        if old:
            f.need(value['epoch'] > old['highestBallot'], 'conflicting acceptance ballot')
            if identity != old['digest']: replacements.append((value, entry))
        else:
            previous = accepted.get(index - 1)
            anchor = snapshot['anchors'][-1] if base else None
            f.need(entry['previousDigest'] == (previous['digest'] if previous else anchor['entryDigest'] if anchor else manifest['digest'])
                   and entry['previousEpoch'] == (previous['originEpoch'] if previous else anchor['originEpoch'] if anchor else 1), 'accepted prefix')
        accepted[index] = dict(digest=identity, originEpoch=entry['originEpoch'], operation=entry['operation'],
                               previousDigest=entry['previousDigest'], frame=raw(value['entry']), acceptance=value, ballots=old['ballots'] if old else {})
        accepted[index]['highestBallot'] = value['epoch']; accepted[index]['ballots'][value['epoch']] = ballot(value)
    proven = base; sequence = snapshot['applicationSequence']
    for value, digest in rows('proofs.gsr'):
        index = value['index']; f.need(index == proven + 1 and index in accepted, 'proof prefix')
        entry = accepted[index]
        f.need(value['entryDigest'] == entry['digest'] and value['previousDigest'] == entry['previousDigest']
               and entry['ballots'].get(value['epoch']) == ballot(value), 'proof acceptance binding')
        proven = index; sequence += entry['operation'] <= 8
        f.need(sequence <= (1 << 63) - 1, 'application sequence exhaustion')
    f.need(base + len(accepted) <= proven + 1, 'multiple unresolved accepted slots')
    frozen = [f.contextual_frame(raw(v), 'ACCEPT', manifest) for v in recovery.frozen_acceptances(directory, selected, manifest)]
    for value, entry in replacements:
        if entry['index'] <= proven: continue
        latest = accepted[entry['index']]['acceptance']
        f.need(latest in frozen or selected is not None and selected['ballot'] == {k: latest[k] for k in ('epoch', 'proposer', 'incarnation')}
               and entry['index'] == selected['prefixIndex'] + 1 and latest['entry'] == selected['nextEntry'], 'conflicting acceptance lacks selected authority')
    if selected_snapshot:
        through = min(proven, len(selected_snapshot['anchors']))
        for i in range(1, through + 1):
            d = snapshot['anchors'][i-1]['entryDigest'] if i <= base else accepted[i]['digest']
            f.need(d == selected_snapshot['anchors'][i-1]['entryDigest'], 'selection conflicts with local prefix')
        if through == base == len(selected_snapshot['anchors']): recovery.agree(snapshot, selected_snapshot, through)
    f.need(before == inventory(directory), 'inspection changed authority')
    return dict(status='PASS', execution='automatic-root-ledger-only', node=node, promisedEpoch=highest,
                promiseCount=len(grants), acceptedThrough=base + len(accepted), provenThrough=proven,
                applicationSequence=sequence, retainedBytes=sum(v['size'] for v in before.values()),
                manifestDigest=manifest['digest'], acceptedDigests=[a['entryDigest'] for a in snapshot['anchors']] + [v['digest'] for v in accepted.values()])
