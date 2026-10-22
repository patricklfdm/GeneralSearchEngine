"""Independent retained-byte checks for the real journal application owner.

Initial provisioning remains a fixture. Verify original physical votes, supplied
receipt bindings, unchanged selector/source bytes and end-force ordering; this is
not a network authentication, public bootstrap or selector-publication gate.
"""
import argparse
import json
from pathlib import Path
import shutil
import struct
import tempfile
from .applied_end_evidence import read, digest, simulate, state, FILES
from .format_fixture import canonical, decode
from .membership_model import need

CUTS = ('APPLICATION_AUTHORITY_VALIDATED', 'REPLAY_CLAIM_PREFIX_WRITTEN', 'REPLAY_APPLICATION_FINISHED',
        'APPLY_PLAN_PREFIX_WRITTEN', 'APPLY_IMAGE_PREFIX_WRITTEN', 'APPLY_END_FORCED',
        'APPLY_ACK_PREFIX_WRITTEN', 'APPLY_ACK_DIRECTORY_FORCED', 'APPLY_BEFORE_RETURN',
        'v41-backup-after-marker-force-v1', 'v41-backup-after-final-rename-v1')


def inventory(root):
    root = Path(root); result = {}; total = 0
    def walk(path, depth):
        nonlocal total
        need(depth <= 4 and path.is_dir() and not path.is_symlink(), 'application evidence directory')
        for child in sorted(path.iterdir()):
            need(len(result) < 256 and not child.is_symlink(), 'application evidence inventory bound')
            name = child.relative_to(root).as_posix()
            if child.is_dir():
                result[name] = None; walk(child, depth+1)
            else:
                value = read(child, 64*1024*1024); total += len(value)
                need(total <= 512*1024*1024, 'application evidence total bound'); result[name] = value
    walk(root, 0); return result


def vote(raw):
    need(12 <= len(raw) <= 9*1024*1024 and struct.unpack('>4sHHI', raw[:12]) == (b'GSPV', 1, 3, len(raw)), 'application pending container')
    offset = 12; frames = {}; values = {}
    def frame(kind):
        nonlocal offset
        need(offset+48 <= len(raw), 'application torn pending frame')
        size = 48+int.from_bytes(raw[offset+12:offset+16], 'big')
        need(size <= len(raw)-offset, 'application pending frame size')
        frames[kind] = raw[offset:offset+size]; values[kind] = decode(frames[kind], 'records', kind); offset += size
    for kind in ('SELECTOR', 'PROMISE', 'SELECTED', 'ENTRY', 'ACCEPT'): frame(kind)
    need(offset+4 <= len(raw), 'application pending payload'); size = int.from_bytes(raw[offset:offset+4], 'big'); offset += 4
    need(size <= len(raw)-offset, 'application pending payload size'); payload = raw[offset:offset+size]; offset += size
    for kind in ('PROOF', 'CERTIFICATE'): frame(kind)
    need(offset == len(raw) and digest(payload) == values['ENTRY']['payload'], 'application pending exact payload')
    entry, accept, proof, cert, selected, promise = [values[k] for k in ('ENTRY', 'ACCEPT', 'PROOF', 'CERTIFICATE', 'SELECTED', 'PROMISE')]
    need(entry['root'] == accept['root'] == selected['root'] == promise['root'] and entry['authority'] == accept['authority'] == selected['view'] == promise['view'], 'application original authority')
    need(entry['index'] == accept['index'] == selected['cut']['index']+1 and entry['previous'] == selected['cut']['entry'] and accept['entry'] == digest(frames['ENTRY']), 'application original slot')
    need(accept['ballot'] == promise['ballot'] == selected['ballot'] == entry['origin'], 'application original ballot')
    need({k: v for k, v in proof.items() if k != 'accepts'} == accept and {k: v for k, v in cert.items() if k != 'proofs'} == proof, 'application original phased records')
    return frames, values


def validate_case(root, row):
    root = Path(root); need(row['mode'] in ('halt', 'kill') and row['cut'] in CUTS and row['status'] == 'PASS', 'application case identity')
    original = inventory(root/'original'); final = inventory(root/'final')
    need(inventory(root/'node-1') == final, 'application final owner bytes')
    need({n: v for n, v in final.items() if n != 'applied-end' and not n.startswith('applied-end/')} == original, 'application original selector/source preservation')
    own_frames, own_values = vote(original['pending.accept']); cert = own_values['CERTIFICATE']; root_hash = cert['root']; original_cut = own_values['SELECTED']['cut']
    seen = {}; observations = json.loads(read(root/'observations.json'))
    for node in ('node-1', 'node-2', 'node-3'):
        files = original if node == 'node-1' else inventory(root/node)
        need('pending.accept' in files, 'application missing actual local vote'); frames, values = vote(files['pending.accept'])
        identity = decode(files['node.gsr'], 'records', 'NODE', root_hash)['identity']; need(identity['node'] == node, 'application local vote identity')
        need(all(frames[k] == own_frames[k] for k in ('ENTRY', 'ACCEPT', 'PROOF', 'CERTIFICATE')) and frames['SELECTOR'] == files['selector.gsr'], 'application actual original local vote')
        seen[node] = identity['storage']
    need(set(observations) == {'accepts', 'proofs'}, 'application observation phases')
    for label, phase in (('accepts', 'ACCEPT'), ('proofs', 'PROOF')):
        expected = [dict(voter=n, storage=s, record=digest(own_frames[phase]), parent=digest(canonical(original_cut))) for n, s in sorted(seen.items())]
        need(observations[label] == expected, 'application observations differ from actual local votes')
        witnesses = [dict(voter=n, incarnation=s, receipt=digest(canonical(dict(root=root_hash, voter=n, incarnation=s, phase=phase, record=digest(own_frames[phase]))))) for n, s in sorted(seen.items())]
        need(cert[label] == witnesses and all(len(set(seen)&set(original_cut['view'][k])) > len(original_cut['view'][k])//2 for k in ('old', 'new')), 'application exact phased quorum')
    end = state(root/'final/applied-end'); need(set(end) == set(FILES), 'application complete end inventory'); plan = json.loads(end['plan.json'])
    need(canonical(plan) == end['plan.json'], 'application canonical end plan')
    need(plan['schema'] == 'gse-v53-applied-end/1.3' and plan['root'] == root_hash and plan['node'] == 'node-1', 'application exact end owner')
    need(plan['files'] == [dict(path=n, sha256=digest(v), bytes=len(v)) for n, v in sorted(end.items()) if n != 'plan.json'], 'application end file inventory')
    need(end['selector.gsr'] == original['selector.gsr'] and end['certificate.gsr'] == own_frames['CERTIFICATE'], 'application exact forced authority')
    catalog = decode(end['catalog.gsr'], 'records', 'CATALOG', root_hash); statement = decode(end['statement.gsr'], 'records', 'CHECKPOINT', root_hash)
    ack = decode(end['ack.gsr'], 'records', 'CHECKPOINT_ACK', root_hash)
    need(catalog['cut'] == statement['end'] == ack['cut'] and statement['start'] == original_cut and catalog['cut']['entry'] == cert['entry'] and catalog['cut']['index'] == cert['index'], 'application exact projected cut')
    need(statement['catalogAfter'] == digest(end['catalog.gsr']) and statement['applicationAfter'] == catalog['application'] == digest(end['application.image']) and ack['statement'] == digest(end['statement.gsr']), 'application exact projected hashes')
    need(ack['voter'] == 'node-1' and ack['incarnation'] == seen['node-1'] and row['ack'] == digest(end['ack.gsr']), 'application exact returned acknowledgement')
    need(statement['applicationBefore'] == digest(read(root/'base.image', 64*1024*1024)) and catalog['applicationSequence'] == 42, 'application base/result sequence')
    current = {}; exists = False
    for label, point, snapshot, mode in (('fault', row['cut'], 'crash', row['mode']), ('recovery-fault', 'APPLY_IMAGE_PREFIX_WRITTEN', 'recovery-crash', 'halt'), ('resume', None, 'final', None)):
        files = inventory(root/snapshot)
        need({n: v for n, v in files.items() if not any(n == p or n.startswith(p+'/') for p in ('applied-end', 'application-replay'))} == original, 'application original authority changed during recovery')
        lines = read(root/(label+'.stdout')).splitlines(); need(read(root/(label+'.stderr')) == b'', 'application process stderr')
        rows = [json.loads(line.removeprefix(b'GSE_BARRIER_READY=')) for line in lines]
        need(not any('status' in v for v in rows[:-1]) and (mode is None or not any('status' in v for v in rows)), 'application early success')
        events = [v['event'] for v in rows if 'event' in v]
        need('APPLICATION_AUTHORITY_VALIDATED' in events and events.index('CERTIFICATE_ACTIVE_PARENT_FORCED') < events.index('APPLICATION_AUTHORITY_VALIDATED'), 'application local certificate force order')
        if point and point.startswith('v41-'): need(rows[-1]['barrierId'] == point, 'application core crash cut')
        elif point:
            need(events[-1] == ('AWAITING_KILL' if mode == 'kill' else point), 'application crash cut')
            if mode == 'kill': need(rows[-1] == dict(event='AWAITING_KILL', cut=point) and events[-2] == point, 'application kill handshake')
        if 'APPLY_VALIDATED' in events:
            stop = point if point and point.startswith('APPLY_') else None
            current, exists, expected = simulate(end, current, exists, stop)
            actual = [v for v in rows if v.get('event', '').startswith('APPLY_')]
            need(actual == expected, 'application exact end force order')
            need(events.index('REPLAY_BEFORE_RETURN') < events.index('APPLY_VALIDATED'), 'application replay before acknowledgement')
        actual = {n.removeprefix('applied-end/'): v for n, v in files.items() if n.startswith('applied-end/')}
        need(actual == current and ('applied-end' in files) == exists, 'application exact interrupted end bytes')
        if mode is None:
            need(rows[-1] == dict(status='PASS', ack=row['ack'], image=catalog['application'], sequence=42, selectedIndex=0) and events[-1] == 'FLOOR_COPY_BEFORE_RETURN', 'application success does not publish selector')
    return dict(case=root.name, status='PASS')


def validate(path):
    path = Path(path); receipt = json.loads(read(path/'receipt.json'))
    need(receipt['expectedCases'] == 22 and receipt['freshJvms'] == 66 and receipt['phasedObservations'] == 'actual-local-owners' and receipt['bootstrap'] == 'private-fixture' and receipt['selectorPublication'] is False and receipt['powerLoss'] is False, 'application qualification scope')
    need([(r['mode'], r['cut']) for r in receipt['cases']] == [(m, c) for m in ('halt', 'kill') for c in CUTS], 'application complete case matrix')
    need({p.name for p in path.iterdir()} == {'receipt.json'} | {r['mode']+'-'+r['cut'] for r in receipt['cases']}, 'application evidence root inventory')
    for row in receipt['cases']: validate_case(path/(row['mode']+'-'+row['cut']), row)
    return dict(status='PASS', cases=22, freshJvms=66, selectorPublication=False, phasedObservations='actual-local-owners')


def qualify(path):
    path = Path(path); result = validate(path); row = json.loads(read(path/'receipt.json'))['cases'][0]; original = path/(row['mode']+'-'+row['cut']); negatives = []
    for name in ('missing-vote', 'changed-observation', 'changed-selector', 'changed-end', 'changed-crash', 'early-success', 'missing-force'):
        with tempfile.TemporaryDirectory(prefix='v53-application-negative-') as temp:
            copy = Path(temp)/original.name; shutil.copytree(original, copy)
            if name == 'missing-vote': (copy/'node-2/pending.accept').unlink()
            elif name == 'changed-observation': (copy/'observations.json').write_bytes(b'{}')
            elif name == 'changed-selector': (copy/'crash/selector.gsr').write_bytes(b'changed')
            elif name == 'changed-end': (copy/'final/applied-end/application.image').write_bytes(b'changed')
            elif name == 'changed-crash':
                (copy/'crash/applied-end').mkdir(); (copy/'crash/applied-end/ack.gsr').write_bytes((copy/'final/applied-end/ack.gsr').read_bytes())
            elif name == 'early-success': (copy/'fault.stdout').write_bytes((copy/'resume.stdout').read_bytes())
            else:
                p = copy/'resume.stdout'; p.write_bytes(p.read_bytes().replace(canonical(dict(event='APPLY_END_FORCED'))+b'\n', b''))
            try: validate_case(copy, row)
            except (ValueError, OSError, KeyError) as error: negatives.append(dict(case=name, status='REJECT', reason=str(error)))
            else: raise ValueError('application mutation accepted: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-application-portable-') as temp:
        copy = Path(temp)/'replay'; shutil.copytree(path, copy); need(validate(copy) == result, 'application portable replay')
    return dict(**result, negatives=negatives, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('path'); args = parser.parse_args(); print(json.dumps(qualify(args.path), sort_keys=True))
