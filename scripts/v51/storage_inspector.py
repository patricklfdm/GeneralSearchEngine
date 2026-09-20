"""Read-only automatic 1.2 root-ledger oracle; never imports product code or encoders."""
import base64
import hashlib
import json
from pathlib import Path
import struct

from . import format_inspector as f

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
    for path in sorted(Path(directory).iterdir()):
        f.need(path.is_file() and not path.is_symlink(), 'authority file type')
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b''): digest.update(chunk)
        result[path.name] = {'size': path.stat().st_size, 'sha256': digest.hexdigest()}
    return result


def inspect(directory, maximum_bytes=8 << 30, maximum_frame=8 << 20):
    directory = Path(directory)
    f.need(not any(p.is_symlink() for p in (directory, *directory.parents)), 'authority symlink')
    before = inventory(directory)
    f.need(set(before) == FILES and before['replica.lock']['size'] == 0, 'authority inventory')
    f.need(sum(v['size'] for v in before.values()) <= maximum_bytes, 'retained byte capacity')
    for name in FILES - set(LEDGERS):
        f.need(before[name]['size'] <= (f.MAX_IMAGE if name == 'genesis.gsr' else 65536), 'metadata byte capacity')
    manifest_raw = (directory / 'manifest.gsr').read_bytes()
    manifest = dict(f.inspect(manifest_raw, 'MANIFEST'), digest=manifest_raw[16:48].hex())
    voters = [m['node'] for m in manifest['members']]
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
    f.need(target['authorityPath'] == str(directory.resolve()), 'copied/stale seal path')
    preparations = [f.inspect(raw(v), 'PREPARED') for v in receipt['preparations']]
    f.need((directory / 'bootstrap-prepared.gsr').read_bytes() == raw(receipt['preparations'][voters.index(node)]), 'local preparation')
    for t, p in zip(plan['targets'], preparations):
        f.need(p['inventoryDigest'] == sha(canonical(t['files'])), 'preparation inventory digest')
        names = [v['path'] for v in t['files']]
        f.need(names == sorted(INITIAL), 'ordered initial inventory')
    for item in target['files']:
        name, size = item['path'], item['size']
        f.need(size <= f.MAX_IMAGE and (before[name]['size'] >= size if name in LEDGERS else before[name]['size'] == size), 'missing initial authority')
        with (directory / name).open('rb') as stream: prefix = stream.read(size)
        f.need(sha(prefix) == item['sha256'], 'initial authority bytes')

    def rows(filename):
        kind, identifier = LEDGERS[filename]
        with (directory / filename).open('rb') as stream:
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
    accepted = {}; accepted_count = 0
    for value, digest in rows('accepted.gsr'):
        accepted_count += 1; f.need(accepted_count <= 1010000, 'acceptance row capacity')
        entry_raw = raw(value['entry']); entry = f.contextual_frame(entry_raw, 'ENTRY', manifest)
        index = entry['index']; identity = entry_raw[16:48].hex()
        f.need(grants.get(value['epoch']) == ballot(value), 'acceptance promise binding')
        f.need(index <= 1000000 and index in (len(accepted), len(accepted) + 1), 'acceptance slot order')
        if index in accepted:
            old = accepted[index]
            f.need(value['epoch'] > old['highestBallot'] and identity == old['digest'], 'conflicting acceptance')
        else:
            previous = accepted.get(index - 1)
            f.need(entry['previousDigest'] == (previous['digest'] if previous else manifest['digest'])
                   and entry['previousEpoch'] == (previous['originEpoch'] if previous else 1), 'accepted prefix')
            accepted[index] = dict(digest=identity, originEpoch=entry['originEpoch'], operation=entry['operation'],
                                   previousDigest=entry['previousDigest'], ballots={})
        accepted[index]['highestBallot'] = value['epoch']; accepted[index]['ballots'][value['epoch']] = ballot(value)
    proven = 0; sequence = manifest['baseSequence']
    for value, digest in rows('proofs.gsr'):
        index = value['index']; f.need(index == proven + 1 and index in accepted, 'proof prefix')
        entry = accepted[index]
        f.need(value['entryDigest'] == entry['digest'] and value['previousDigest'] == entry['previousDigest']
               and entry['ballots'].get(value['epoch']) == ballot(value), 'proof acceptance binding')
        proven = index; sequence += entry['operation'] <= 8
        f.need(sequence <= (1 << 63) - 1, 'application sequence exhaustion')
    f.need(len(accepted) <= proven + 1, 'multiple unresolved accepted slots')
    f.need(before == inventory(directory), 'inspection changed authority')
    return dict(status='PASS', execution='automatic-root-ledger-only', node=node, promisedEpoch=highest,
                promiseCount=len(grants), acceptedThrough=len(accepted), provenThrough=proven,
                applicationSequence=sequence, retainedBytes=sum(v['size'] for v in before.values()),
                manifestDigest=manifest['digest'], acceptedDigests=[v['digest'] for v in accepted.values()])
