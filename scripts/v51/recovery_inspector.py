"""Independent read-only recovery oracle; no production or fixture encoder imports."""
import base64
import hashlib
import json
from pathlib import Path

from . import format_inspector as f

GENERATION = {'snapshot.gsr', 'accepted.gsr', 'proofs.gsr', 'generation.gsr'}
OPTIONAL = {'current.gsr', 'current.pending.gsr', 'generation-started.gsr', 'selected.gsr',
            'recovery-floor.gsr', 'recovery-floor.pending.gsr', 'generation-a', 'generation-b', 'basis', 'transfer'}


def raw(v): return base64.b64decode(v, validate=True)
def sha(v): return hashlib.sha256(v).hexdigest()
def digest(v): return v[16:48].hex()
def ballot(v): return v['epoch'], v['proposer'], v['incarnation']


def allowed(parts, directory, voters, required):
    if len(parts) == 1:
        return parts[0] in ({'generation-a', 'generation-b', 'basis', 'transfer'} if directory else
                            required | (OPTIONAL - {'generation-a', 'generation-b', 'basis', 'transfer'}))
    if parts[0] in ('generation-a', 'generation-b'): return not directory and len(parts) == 2 and parts[1] in GENERATION
    if parts[0] == 'basis':
        return parts[1] in voters and (len(parts) == 2 if directory else len(parts) == 3 and parts[2] in {'basis.gsr', 'basis.pending.gsr', 'image.gsr'})
    if parts[0] != 'transfer': return False
    if len(parts) == 2 and not directory: return parts[1] in {'selected.pending.gsr', 'started.pending.gsr', 'transfer.gsr', 'transfer.pending.gsr', 'image.gsr'}
    if parts[1] not in {'selection-a', 'selection-b', 'floor-a', 'floor-b', 'retiring'}: return False
    if directory: return len(parts) == 2 or len(parts) == 3 and parts[1].startswith('floor-') and parts[2] in voters
    if parts[1].startswith('selection-'): return len(parts) == 3 and parts[2] in {f'{k}-{n}.gsr' for k in ('basis', 'image') for n in voters}
    if parts[1] == 'retiring': return len(parts) == 3 and parts[2] in GENERATION | {'current.gsr'}
    return len(parts) == 4 and parts[2] in voters and parts[3] in GENERATION | {'current.gsr'}


def snapshot(frame, manifest):
    v = f.contextual_frame(frame, 'SNAPSHOT', manifest)
    f.need(v['baseSequence'] == manifest['baseSequence'], 'snapshot genesis base')
    epoch, incarnation = 1, f.ZERO
    for a in v['anchors']:
        f.need(a['originEpoch'] >= 2 and a['originIncarnation'] != f.ZERO and a['originEpoch'] >= epoch
               and (a['originEpoch'] != epoch or a['originIncarnation'] == incarnation), 'snapshot origin ancestry')
        epoch, incarnation = a['originEpoch'], a['originIncarnation']
    if v['terminalProof']:
        proof = f.contextual_frame(raw(v['terminalProof']), 'PROOF', manifest)
        f.need(proof['previousDigest'] == (v['anchors'][-2]['entryDigest'] if len(v['anchors']) > 1 else manifest['digest']), 'snapshot predecessor')
    return v


def agree(a, b, through):
    f.need(through <= min(len(a['anchors']), len(b['anchors'])) and a['anchors'][:through] == b['anchors'][:through], 'conflicting proven ancestry')
    if len(a['anchors']) == len(b['anchors']): f.need(a['application'] == b['application'], 'same-cut application image')


def entry_digest(s): return s['anchors'][-1]['entryDigest'] if s['anchors'] else s['manifestDigest']


def tail(s, entry):
    f.need(entry['index'] == len(s['anchors']) + 1 and entry['previousDigest'] == entry_digest(s)
           and entry['previousEpoch'] == (s['anchors'][-1]['originEpoch'] if s['anchors'] else 1), 'recovery tail predecessor')


def basis(descriptor, image, manifest):
    b = f.contextual_frame(descriptor, 'BASIS', manifest); v = f.contextual_frame(image, 'IMAGE', manifest)
    s = snapshot(raw(v['snapshot']), manifest)
    f.need(b['imageDigest'] == digest(image) and b['imageBytes'] == len(image), 'basis image identity')
    f.need(b['files'] == [dict(path='image.gsr', size=len(image), sha256=sha(image))], 'basis image inventory')
    f.need(v['acceptances'] == ([] if b['accepted'] is None else [b['accepted']]), 'basis accepted identity')
    accepted = f.contextual_frame(raw(b['accepted']), 'ACCEPT', manifest) if b['accepted'] else None
    if accepted:
        tail(s, f.contextual_frame(raw(accepted['entry']), 'ENTRY', manifest))
        f.need(accepted['epoch'] <= b['ballot']['epoch'], 'basis accepted ballot')
    return b, s, accepted


def select(selected, bases, manifest):
    f.need(len(bases) == 2 and len({b[0]['node'] for b in bases}) == 2 and
           selected['ballot']['proposer'] in {b[0]['node'] for b in bases}, 'prepare quorum')
    f.need(all(b[0]['ballot'] == selected['ballot'] for b in bases), 'mixed prepare ballots')
    prefix = max((b[1] for b in bases), key=lambda s: len(s['anchors'])); cut = len(prefix['anchors']); chosen = None
    for descriptor, image, accepted in bases:
        agree(prefix, image, len(image['anchors']))
        if not accepted: continue
        entry = f.contextual_frame(raw(accepted['entry']), 'ENTRY', manifest)
        if entry['index'] <= cut: continue
        tail(prefix, entry)
        if chosen is None or accepted['epoch'] > chosen['epoch']: chosen = accepted
        elif accepted['epoch'] == chosen['epoch']:
            f.need(ballot(accepted) == ballot(chosen) and accepted['entry'] == chosen['entry'], 'equal-ballot conflicting values')
    f.need(selected['prefixIndex'] == cut and selected['prefixDigest'] == entry_digest(prefix), 'selected proven prefix')
    f.need(selected['nextEntry'] == (chosen['entry'] if chosen else None) and
           selected['sourceBallot'] == ({k: chosen[k] for k in ('epoch', 'proposer', 'incarnation')} if chosen else None), 'highest accepted selection')
    return prefix


def read_selection(directory, manifest):
    path = directory / 'selected.gsr'
    if not path.exists(): return None, None
    selected = f.contextual_frame(path.read_bytes(), 'SELECTED', manifest)
    f.need([b['node'] for b in selected['bases']] == sorted(b['node'] for b in selected['bases']), 'ordered selected bases')
    for slot in ('selection-a', 'selection-b'):
        bases = []
        for b in selected['bases']:
            desc = directory / 'transfer' / slot / f"basis-{b['node']}.gsr"
            image = desc.with_name(f"image-{b['node']}.gsr")
            if not desc.is_file() or not image.is_file() or digest(desc.read_bytes()) != b['basisDigest']: break
            item = basis(desc.read_bytes(), image.read_bytes(), manifest)
            f.need(item[0]['basisId'] == b['basisId'] and item[0]['node'] == b['node'], 'selected basis identity'); bases.append(item)
        if len(bases) == 2: return selected, select(selected, bases, manifest)
    f.need(False, 'selected basis inventory incomplete')


def source(directory, manifest, selector_raw=None):
    selector = f.contextual_frame(selector_raw if selector_raw is not None else (directory / 'current.gsr').read_bytes(), 'SELECTOR', manifest)
    seal_raw = (directory / 'generation.gsr').read_bytes(); seal = f.contextual_frame(seal_raw, 'GENERATION', manifest)
    snapshot_raw = (directory / 'snapshot.gsr').read_bytes(); s = snapshot(snapshot_raw, manifest)
    f.need(selector['node'] == seal['node'] and selector['generationDigest'] == digest(seal_raw), 'source selector')
    f.need(seal['snapshotDigest'] == digest(snapshot_raw) and seal['prefixIndex'] == len(s['anchors']), 'source snapshot')
    f.need(sorted(x['path'] for x in seal['files']) == ['accepted.gsr', 'proofs.gsr', 'snapshot.gsr'], 'source inventory')
    for item in seal['files']:
        data = (directory / item['path']).read_bytes(); size = item['size']
        f.need(size <= len(data) and (item['path'] != 'snapshot.gsr' or size == len(data)) and sha(data[:size]) == item['sha256'], 'source inventory hash')
    suffix = {}
    for name, kind in [('accepted.gsr', 24), ('proofs.gsr', 6)]:
        suffix[kind] = []
        data = (directory / name).read_bytes(); size = int.from_bytes(data[12:16], 'big', signed=True) + 48
        f.need(48 < size <= len(data), 'source journal size')
        journal = f.contextual_frame(data[:size], 'JOURNAL', manifest)
        f.need(journal['node'] == seal['node'] and journal['recordKind'] == kind, 'source journal identity')
        offset = size
        while offset < len(data):
            f.need(len(data) - offset >= 48, 'torn source journal')
            size = int.from_bytes(data[offset+12:offset+16], 'big', signed=True) + 48
            f.need(48 < size <= len(data) - offset, 'source journal row size')
            suffix[kind].append(f.contextual_frame(data[offset:offset+size], 'ACCEPT' if kind == 24 else 'PROOF', manifest)); offset += size
    base = len(s['anchors']); last = base; proven = base; accepted = {}; voted = {}
    previous, epoch = entry_digest(s), s['anchors'][-1]['originEpoch'] if base else 1
    for row in suffix[24]:
        entry = f.contextual_frame(raw(row['entry']), 'ENTRY', manifest); index = entry['index']
        f.need(index > base and index in (last, last + 1), 'source acceptance order')
        if index == last: f.need(row['epoch'] > accepted[index]['epoch'], 'source acceptance ballot')
        else:
            f.need(entry['previousDigest'] == previous and entry['previousEpoch'] == epoch, 'source acceptance predecessor'); last += 1
        previous, epoch = row['entryDigest'], entry['originEpoch']; accepted[index] = row; voted[index, row['epoch']] = row
    for row in suffix[6]:
        index = row['index']; f.need(index == proven + 1 and index <= last, 'source proof prefix')
        accepted_row = voted.get((index, row['epoch']))
        f.need(accepted_row is not None and ballot(accepted_row) == ballot(row) and
               accepted_row['entryDigest'] == row['entryDigest'] == accepted[index]['entryDigest'], 'source proof acceptance')
        f.need(f.inspect(raw(accepted_row['entry']), 'ENTRY')['previousDigest'] == row['previousDigest'], 'source proof predecessor'); proven += 1
    f.need(last <= proven + 1, 'source unresolved slots')
    return dict(selector=selector, seal=seal, snapshot=s, sealDigest=digest(seal_raw), snapshotDigest=digest(snapshot_raw))


def state(directory, manifest, node, genesis):
    directory = Path(directory); active = directory
    initial = dict(manifestDigest=manifest['digest'], baseSequence=manifest['baseSequence'], applicationSequence=manifest['baseSequence'],
                   anchors=[], application=genesis['application'], terminalProof=None)
    current = None
    if (directory / 'current.gsr').exists():
        selector_raw = (directory / 'current.gsr').read_bytes(); selector = f.contextual_frame(selector_raw, 'SELECTOR', manifest)
        f.need(selector['node'] == node, 'selector voter'); active = directory / selector['generation']
        current = source(active, manifest, selector_raw); initial = current['snapshot']
        if current['seal']['selectedDigest'] is not None: f.need((directory / 'selected.gsr').is_file(), 'generation lost selection')
        if (directory / 'generation-started.gsr').exists():
            started = f.contextual_frame((directory / 'generation-started.gsr').read_bytes(), 'STARTED', manifest)
            f.need(started['node'] == node, 'started voter')
    else: f.need(not (directory / 'generation-started.gsr').exists() and not (directory / 'recovery-floor.gsr').exists(), 'lost generation selector')
    if not initial['anchors']: f.need(initial['application'] == genesis['application'], 'genesis application image')
    selected, selected_snapshot = read_selection(directory, manifest)
    floor = directory / 'recovery-floor.gsr'
    if floor.exists():
        value = f.contextual_frame(floor.read_bytes(), 'FLOOR', manifest)
        f.need(value['node'] == node and current is not None and value['index'] <= len(initial['anchors']), 'floor prefix/voter')
        verified = False
        for slot in ('floor-a', 'floor-b'):
            sources = []
            for s in value['sources']:
                directory_source = directory / 'transfer' / slot / s['node']
                seal = directory_source / 'generation.gsr'
                if not seal.is_file() or digest(seal.read_bytes()) != s['generationDigest']: break
                source_value = source(directory_source, manifest)
                f.need(source_value['seal']['node'] == s['node'] and source_value['snapshotDigest'] == s['snapshotDigest'], 'floor source identity')
                f.need(len(source_value['snapshot']['anchors']) == value['index'] and entry_digest(source_value['snapshot']) == value['entryDigest'], 'floor source cut')
                agree(initial, source_value['snapshot'], value['index']); sources.append(source_value)
            if len(sources) == 2:
                agree(sources[0]['snapshot'], sources[1]['snapshot'], value['index']); verified = True; break
        f.need(verified, 'floor complete source inventory unavailable')
    return active, initial, selected, selected_snapshot


def frozen_acceptances(directory, selected, manifest):
    if selected is None: return []
    result = []
    for b in selected['bases']:
        for slot in ('selection-a', 'selection-b'):
            path = directory / 'transfer' / slot / f"basis-{b['node']}.gsr"
            if path.is_file() and digest(path.read_bytes()) == b['basisDigest']:
                value = f.contextual_frame(path.read_bytes(), 'BASIS', manifest)
                if value['accepted']: result.append(value['accepted'])
    return result
