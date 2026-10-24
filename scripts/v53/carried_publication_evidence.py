"""Derive carried-entry installation/publication from actual original local votes and ends."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import struct
import tempfile
from . import format_fixture as f
from . import source_packet as p
from .applied_end_evidence import read, digest
from .generation_install_evidence import packet_bytes
from .grant_evidence import journal
from .journal_application_evidence import inventory
from .journal_publication_evidence import EMPTY, COVERAGE
from .pending_accept_evidence import container
from .round_storage_evidence import original_slot, current, anchor, NODES
from .membership_model import need


def pending(raw, phases=()):
    need(len(raw) >= 12 and struct.unpack('>4sHHI', raw[:12]) == (b'GSPV', 1, 3, len(raw)), 'carried pending framing')
    offset = 12; frames = {}; values = {}
    for kind in ('SELECTOR', 'PROMISE', 'SELECTED', 'ENTRY', 'ACCEPT', 'PAYLOAD', *phases):
        if kind == 'PAYLOAD':
            need(offset+4 <= len(raw), 'carried payload header'); size = int.from_bytes(raw[offset:offset+4], 'big'); offset += 4
        else:
            need(offset+48 <= len(raw), 'carried phase header'); size = 48+int.from_bytes(raw[offset+12:offset+16], 'big')
        need(0 <= size <= len(raw)-offset, 'carried phase extent'); frames[kind] = raw[offset:offset+size]; offset += size
        if kind != 'PAYLOAD': values[kind] = f.decode(frames[kind], 'records', kind)
    need(offset == len(raw) and digest(frames['PAYLOAD']) == values['ENTRY']['payload'], 'carried payload/extent')
    return frames, values


def generation(files, cap, node, slot, tail):
    manifest = dict(root=cap['root'], node=node, generation=slot, cut=cap['cut'], catalog=cap['catalog'], application=cap['application'],
                    capsule=digest(p.decode(files['source.gscp'])['capsuleBytes']), promise=digest(files['promise.gsr']), basis=digest(files['basis.gsr']),
                    selection=digest(files['selected.gsr']), ownedTail=tail, files=[dict(path=k, size=len(v), sha256=digest(v)) for k, v in sorted(files.items())])
    members = dict(files); members['generation.gsr'] = f.encode('records', 'GENERATION', manifest)
    selector = f.encode('records', 'SELECTOR', dict(root=cap['root'], node=node, generation=slot, digest=digest(members['generation.gsr'])))
    return selector, {'generations/'+slot: None, **{'generations/'+slot+'/'+k: v for k, v in members.items()}}


def publication(work, slot, before, first):
    originals = {n: inventory(work/'originals'/('slot-'+str(slot))/n) for n in NODES}
    pref, members, old = current(before['node-1']); cap = old['capsule']; root_hash = cap['root']
    phase, values = pending(originals['node-1']['pending.accept'], ('PROOF', 'CERTIFICATE')); entry = values['ENTRY']; cert = values['CERTIFICATE']
    selected = f.decode(members['selected.gsr'], 'records', 'SELECTED')
    need(entry['kind'] == ('DATA' if slot == 2 else 'BARRIER') and entry['index'] == slot and entry['previous'] == cap['cut']['entry']
         and entry['origin'] == (dict(selected['ballot'], counter=20) if slot == 2 else selected['ballot']), 'carried first/subsequent origin')
    need(slot != 2 or digest(phase['ENTRY']) == selected['nextEntry'], 'carried original selected entry')
    accept = dict(root=root_hash, authority=selected['view'], ballot=selected['ballot'], entry=digest(phase['ENTRY']), index=slot)
    need(values['ACCEPT'] == accept and {k: v for k, v in values['PROOF'].items() if k != 'accepts'} == accept
         and {k: v for k, v in cert.items() if k != 'proofs'} == values['PROOF'], 'carried exact new phased votes')
    identities = {n: f.decode(before[n]['node.gsr'], 'records', 'NODE')['identity'] for n in NODES}
    for label, kind in (('accepts', 'ACCEPT'), ('proofs', 'PROOF')):
        expected = [dict(voter=n, incarnation=identities[n]['storage'], receipt=digest(f.canonical(dict(root=root_hash, voter=n,
            incarnation=identities[n]['storage'], phase=kind, record=digest(phase[kind]))))) for n in NODES]
        need(cert[label] == expected, 'carried actual phased quorum')
    image = originals['node-1']['applied-end/application.image']; after = copy.deepcopy(f.decode(old['objects'][cap['catalog']], 'records', 'CATALOG'))
    after['cut'] = dict(after['cut'], index=slot, entry=digest(phase['ENTRY']))
    if slot == 2: after.update(application=digest(image), applicationSequence=43, lastDataIndex=2)
    else: need(image == members[cap['application']+'.image'] and phase['PAYLOAD'] == b'', 'carried continuation unchanged application')
    catalog = f.encode('records', 'CATALOG', after); start = f.decode(old['objects'][cap['items'][0]['statement']], 'records', 'CHECKPOINT')
    statement = dict(start, end=after['cut'], catalogAfter=digest(catalog), applicationAfter=after['application']); raw_statement = f.encode('records', 'CHECKPOINT', statement)
    lowers = [anchor(cap)] if slot == 2 else [first['parent'], anchor(cap)]; acks = []; groups = [[] for _ in lowers]
    for n in NODES:
        physical = originals[n]; local_phase, _ = pending(physical['pending.accept'], ('PROOF', 'CERTIFICATE')); _, local, _ = current(before[n])
        need(all(local_phase[k] == phase[k] for k in ('ENTRY', 'ACCEPT', 'PAYLOAD', 'PROOF', 'CERTIFICATE'))
             and local_phase['SELECTOR'] == before[n]['selector.gsr'] and local_phase['PROMISE'] == local['promise.gsr'] and local_phase['SELECTED'] == local['selected.gsr'], 'carried original local phase identity')
        need({k: v for k, v in physical.items() if k not in ('pending.accept', 'applied-end') and not k.startswith('applied-end/')}
             == {k: v for k, v in before[n].items() if k != 'pending.accept'}, 'carried original predecessor preserved')
        def ack(raw): return f.encode('records', 'CHECKPOINT_ACK', dict(root=root_hash, voter=n, incarnation=identities[n]['storage'], cut=after['cut'], statement=digest(raw)))
        end = dict(zip(('selector.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr', 'application.image', 'ack.gsr'),
                       (physical['selector.gsr'], phase['CERTIFICATE'], catalog, raw_statement, image, ack(raw_statement))))
        acks.append(end['ack.gsr'])
        for i, lower in enumerate(lowers):
            raw = f.encode('records', 'CHECKPOINT', dict(statement, start=lower['cut'], catalogBefore=lower['catalog'], applicationBefore=lower['application']))
            label = 'parent' if lower == anchor(cap) else 'ancestor-0'; end[label+'-statement.gsr'] = raw; end[label+'-ack.gsr'] = ack(raw); groups[i].append(ack(raw))
        end['plan.json'] = f.canonical(dict(schema='gse-v53-applied-end/1.3', root=root_hash, node=n, files=[dict(path=k, bytes=len(v), sha256=digest(v)) for k, v in sorted(end.items())]))
        need({k.removeprefix('applied-end/'): v for k, v in physical.items() if k.startswith('applied-end/')} == end, 'carried original applied ends')
    objects = {digest(before['node-1'][k]): before['node-1'][k] for k in ('root.gsr', 'genesis.gsr')}
    for raw in (catalog, raw_statement, *acks, *[phase[k] for k in ('ENTRY', 'ACCEPT', 'PAYLOAD', 'PROOF', 'CERTIFICATE')]): objects[digest(raw)] = raw
    ancestry = b''
    for lower, group in zip(lowers, groups):
        raw = f.encode('records', 'CHECKPOINT', dict(statement, start=lower['cut'], catalogBefore=lower['catalog'], applicationBefore=lower['application']))
        ancestry += raw+b''.join(group)
        for value in (raw, *group): objects[digest(value)] = value
    if slot == 2:
        first = dict(parent=anchor(cap), end=dict(cut=after['cut'], catalog=digest(catalog), application=after['application']), certificate=digest(phase['CERTIFICATE']),
                     proof={digest(phase[k]): phase[k] for k in ('ENTRY', 'ACCEPT', 'PAYLOAD', 'PROOF', 'CERTIFICATE')})
    else: objects.update(first['proof'])
    item = dict(kind='RANGE', statement=digest(raw_statement), endorsements=[digest(v) for v in acks], certificate=None, descriptor=None)
    raw_packet = packet_bytes(dict(cap, cut=after['cut'], catalog=digest(catalog), application=after['application'], items=[item]), objects, {after['application']: len(image)})
    coverage = dict(schema='gse-v53-selected-coverage/1.3' if slot == 2 else 'gse-v53-round-coverage/1.3', selection=digest(phase['SELECTED']), parent=anchor(cap), certificate=digest(phase['CERTIFICATE']))
    if slot == 3: coverage.update(first={k: first[k] for k in ('parent', 'end', 'certificate')}, ancestors=[first['parent']])
    projected = {}
    for n in NODES:
        prefix, local, _ = current(before[n]); files = {k: local[k] for k in ('promise.gsr', 'basis.gsr', 'selected.gsr', 'selected-sources.gsr')}
        files.update({'source.gscp': raw_packet, COVERAGE: f.canonical(coverage), 'ancestry.gsr': ancestry, after['application']+'.image': image})
        selector, files = generation(files, p.decode(raw_packet)['capsule'], n, 'b' if prefix == 'generations/a/' else 'a', None)
        expected = {k: v for k, v in before[n].items() if not k.startswith('generations/')}; expected.update(files); expected['selector.gsr'] = selector; expected['pending.accept'] = EMPTY
        need(inventory(work/'carried-snapshots'/('published' if slot == 2 else 'continued')/n) == expected, 'carried exact publication/retirement bytes')
        projected[n] = expected
    return projected, first


def validate_case(work, holders):
    _, previous = original_slot(work, 1, None, None); source_packets = {}; histories = {}; accepted = {}; prepared = {}
    entry_raw = read(work/'entry.gsr'); entry = f.decode(entry_raw, 'records', 'ENTRY'); payload = read(work/'payload.bin'); old_accept = None
    for i, n in enumerate(NODES):
        original = previous[n]; prefix, files, packet = current(original); cap = packet['capsule']; old_selected = f.decode(files['selected.gsr'], 'records', 'SELECTED')
        need(entry == dict(root=cap['root'], authority=old_selected['view'], index=2, previous=cap['cut']['entry'], origin=old_selected['ballot'], kind='DATA', payload=digest(payload)), 'carried original entry')
        old_accept = f.encode('records', 'ACCEPT', dict(root=cap['root'], authority=old_selected['view'], ballot=old_selected['ballot'], index=2, entry=digest(entry_raw)))
        has_vote = i+1 > 3-holders; pending_bytes = container([original['selector.gsr'], files['promise.gsr'], files['selected.gsr'], entry_raw, old_accept], payload) if has_vote else EMPTY
        expected = dict(original, **{'pending.accept': pending_bytes}); need(inventory(work/'carried-snapshots/old-accepted'/n) == expected, 'carried original accepted holders'); accepted[n] = expected
        objects = dict(packet['objects'])
        if has_vote: objects.update({digest(raw): raw for raw in (entry_raw, old_accept, payload)})
        raw_packet = packet_bytes(cap, objects, packet['images']); source_packets[n] = raw_packet; proposed = p.decode(raw_packet)
        physical = inventory(work/'carried-snapshots/prepared'/n); rows = journal(physical['grants.gsr'], cap['root'], n); prior = journal(original['grants.gsr'], cap['root'], n)
        need(rows[:len(prior)] == prior and [k for k, _, _ in rows[len(prior):]] == ['PROMISE', 'BASIS', 'SELECTED'], 'carried new grant history')
        promise, basis, selected = rows[-3:]; ballot = dict(old_selected['ballot'], counter=21)
        need(promise[2] == dict(prior[0][2], ballot=ballot, basisId=promise[2]['basisId']) and promise[2]['basisId'] != prior[0][2]['basisId'], 'carried new original promise')
        need(basis[2] == dict(promise[2], voter=n, cut=cap['cut'], capsule=digest(proposed['capsuleBytes']), inventory=digest(proposed['indexBytes']), accepted=digest(old_accept) if has_vote else None), 'carried new source provenance')
        source = 'sources/'+basis[2]['basisId']; expected.update({'grants.gsr': b''.join(r[1] for r in rows), source: None, source+'/source.gscp': raw_packet})
        expected.update({source+'/'+h+'.image': files[h+'.image'] for h in packet['images']})
        need(physical == expected, 'carried exact prepared bytes'); prepared[n] = expected; histories[n] = rows[-3:]
    _, _, base = current(previous['node-1']); selected = dict(root=cap['root'], view=old_selected['view'], ballot=ballot, cut=cap['cut'], nextEntry=digest(entry_raw),
        sources=[dict(voter=n, basisId=histories[n][1][2]['basisId'], basisDigest=digest(histories[n][1][1])) for n in NODES])
    selected_raw = f.encode('records', 'SELECTED', selected); raw_packet = source_packets['node-3']; next_accept = f.encode('records', 'ACCEPT', dict(f.decode(old_accept, 'records', 'ACCEPT'), ballot=ballot))
    reclaimed = {}
    for n in NODES:
        need(histories[n][2][1] == selected_raw, 'carried actual selected set')
        prefix, local, _ = current(previous[n]); slot = 'b' if prefix == 'generations/a/' else 'a'
        files = {'promise.gsr': histories[n][0][1], 'basis.gsr': histories[n][1][1], 'selected.gsr': selected_raw,
                 'selected-sources.gsr': b''.join(histories[v][1][1] for v in NODES), 'source.gscp': raw_packet, 'owned-tail.gsr': old_accept}
        files.update({h+'.image': local[h+'.image'] for h in base['images']}); selector, installed = generation(files, p.decode(raw_packet)['capsule'], n, slot, digest(old_accept))
        expected = dict(prepared[n]); expected.update(installed); expected['selector.gsr'] = selector
        need(inventory(work/'carried-snapshots/installed'/n) == expected, 'carried exact selected installation')
        expected['pending.accept'] = container([selector, files['promise.gsr'], selected_raw, entry_raw, next_accept], payload)
        need(inventory(work/'carried-snapshots/reaccepted'/n) == expected, 'carried exact new ballot acceptance')
        old_basis = f.decode(local['basis.gsr'], 'records', 'BASIS'); old_source = 'sources/'+old_basis['basisId']
        expected = {k: v for k, v in expected.items() if not k.startswith(prefix) and k != prefix[:-1] and k != old_source and not k.startswith(old_source+'/')}
        expected['grants.gsr'] = b''.join(r[1] for r in histories[n]); need(inventory(work/'carried-snapshots/reclaimed'/n) == expected, 'carried exact authorized maintenance'); reclaimed[n] = expected
    published, first = publication(work, 2, reclaimed, None); continued, _ = publication(work, 3, published, first)
    for n in NODES:
        physical = inventory(work/'carried-snapshots/fresh'/n); prefix, local, packet = current(continued[n]); cap = packet['capsule']
        old_basis = f.decode(current(previous[n])[1]['basis.gsr'], 'records', 'BASIS')
        rows = journal(physical['grants.gsr'], cap['root'], n); need(rows[:3] == histories[n] and [k for k, _, _ in rows[3:]] == ['PROMISE', 'BASIS'], 'carried final fresh journal')
        promise, basis = rows[-2:]; need(promise[2] == dict(histories[n][0][2], ballot=dict(ballot, counter=22), basisId=promise[2]['basisId'])
            and promise[2]['basisId'] not in {histories[n][0][2]['basisId'], old_basis['basisId']}, 'carried final fresh promise')
        need(basis[2] == dict(promise[2], voter=n, cut=cap['cut'], capsule=digest(packet['capsuleBytes']), inventory=digest(packet['indexBytes']), accepted=None), 'carried no resurrected tail')
        source = 'sources/'+basis[2]['basisId']; expected = dict(continued[n]); expected.update({'grants.gsr': b''.join(r[1] for r in rows), source: None, source+'/source.gscp': local['source.gscp']})
        expected.update({source+'/'+h+'.image': local[h+'.image'] for h in packet['images']})
        need(physical == inventory(work/n) == expected, 'carried final owner bytes')
    return digest(entry_raw)


def validate(root):
    root = Path(root); receipt = json.loads(read(root/'receipt.json')); need(receipt['execution'] == 'private-carried-publication' and receipt['expectedCases'] == 3
        and receipt['historicalBootstrap'] == 'conditional-fixture' and receipt['freshProcesses'] is False and receipt['runtimeEnabled'] is False, 'carried execution scope')
    need([r['holders'] for r in receipt['cases']] == [1, 2, 3] and {v.name for v in root.iterdir()} == {'receipt.json', 'holders-1', 'holders-2', 'holders-3'}, 'carried full matrix')
    for row in receipt['cases']:
        entry = validate_case(root/('holders-'+str(row['holders'])), row['holders'])
        need(row == dict(holders=row['holders'], entry=entry, origin=20, acceptBallot=21, selectedCut=1, publishedCut=3, applicationSequence=43, status='PASS'), 'carried exact receipt')
    return dict(status='PASS', cases=3, nodePublications=18, oldBallot=20, newBallot=21, originalFirst=True, physicalBytes=True, runtimeEnabled=False, freshProcesses=False)


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    for variant in ('lost-original-vote', 'changed-original-payload', 'invented-source', 'different-selected-entry', 'lost-old-generation',
                    'rewritten-origin', 'lost-applied-ack', 'changed-first-proof', 'early-clear', 'resurrected-tail'):
        with tempfile.TemporaryDirectory(prefix='v53-carried-negative-') as tmp:
            work = Path(tmp)/'raw'; shutil.copytree(root, work); case = work/'holders-1'; snaps = case/'carried-snapshots'
            if variant == 'lost-original-vote': (snaps/'old-accepted/node-3/pending.accept').write_bytes(EMPTY)
            elif variant == 'changed-original-payload': (case/'payload.bin').write_bytes(b'changed')
            elif variant == 'invented-source':
                src = next((snaps/'prepared/node-1/sources').glob('*/source.gscp')); src.write_bytes(b'changed')
            elif variant == 'different-selected-entry':
                path = snaps/'installed/node-1'; prefix, _, _ = current(inventory(path)); (path/prefix/'selected.gsr').write_bytes(b'changed')
            elif variant == 'lost-old-generation':
                path = snaps/'installed/node-3'; prefix, _, _ = current(inventory(path)); shutil.rmtree(path/('generations/a' if prefix == 'generations/b/' else 'generations/b'))
            elif variant == 'rewritten-origin':
                path = snaps/'reaccepted/node-1/pending.accept'; frames, values = pending(read(path))
                changed = f.encode('records', 'ENTRY', dict(values['ENTRY'], origin=values['ACCEPT']['ballot']))
                vote = f.encode('records', 'ACCEPT', dict(values['ACCEPT'], entry=digest(changed)))
                path.write_bytes(container([frames[k] for k in ('SELECTOR', 'PROMISE', 'SELECTED')]+[changed, vote], frames['PAYLOAD']))
            elif variant == 'lost-applied-ack': (case/'originals/slot-2/node-3/applied-end/ack.gsr').unlink()
            elif variant == 'changed-first-proof':
                path = snaps/'continued/node-1'; prefix, _, _ = current(inventory(path)); (path/prefix/COVERAGE).write_bytes(b'{}')
            elif variant == 'early-clear': (snaps/'reclaimed/node-3/pending.accept').write_bytes(EMPTY)
            else: (snaps/'fresh/node-1/pending.accept').write_bytes(read(snaps/'old-accepted/node-3/pending.accept'))
            try: validate(work)
            except (ValueError, OSError, KeyError, TypeError): negatives.append(variant)
            else: raise ValueError('accepted carried mutation: '+variant)
    with tempfile.TemporaryDirectory(prefix='v53-carried-portable-') as tmp:
        work = Path(tmp)/'raw'; shutil.copytree(root, work); need(validate(work) == result, 'carried portable replay')
    return dict(result, negatives=negatives, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); a = parser.parse_args(); print(json.dumps(qualify(a.root), sort_keys=True))
