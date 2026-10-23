"""Original-first replay of same-round local storage snapshots.

Reconstruct every generation from original local phased votes and forced applied
ends. This checks retained-byte provenance and projection, not process force
ordering, power loss, public readiness or a separate core image semantic oracle.
"""
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
from .context_evidence import majority
from .generation_install_evidence import packet_bytes
from .grant_evidence import journal
from .journal_application_evidence import inventory
from .journal_publication_evidence import EMPTY, COVERAGE
from .membership_model import need
from .selected_sources_evidence import cuts

NODES = ('node-1', 'node-2', 'node-3')


def votes(raw, parent):
    need(12 <= len(raw) <= 9*1024*1024 and struct.unpack('>4sHHI', raw[:12]) == (b'GSPV', 1, 3, len(raw)), 'round pending framing')
    offset = 12; frames = {}; values = {}
    for kind in ('SELECTOR', 'PROMISE', 'SELECTED', 'ENTRY', 'ACCEPT', 'PAYLOAD', 'PROOF', 'CERTIFICATE'):
        if kind == 'PAYLOAD':
            need(offset+4 <= len(raw), 'round payload length')
            size = int.from_bytes(raw[offset:offset+4], 'big'); offset += 4
        else:
            need(offset+48 <= len(raw), 'round phase header'); size = 48+int.from_bytes(raw[offset+12:offset+16], 'big')
        need(size <= len(raw)-offset, 'round phase body'); frames[kind] = raw[offset:offset+size]; offset += size
        if kind != 'PAYLOAD': values[kind] = f.decode(frames[kind], 'records', kind)
    need(offset == len(raw), 'round phase exact extent')
    e, a, proof, cert, selected, promise = [values[k] for k in ('ENTRY', 'ACCEPT', 'PROOF', 'CERTIFICATE', 'SELECTED', 'PROMISE')]
    need(e['root'] == a['root'] == selected['root'] == promise['root'] and e['authority'] == a['authority'] == selected['view'] == promise['view'], 'round phase authority')
    need(e['index'] == a['index'] == parent['index']+1 and e['previous'] == parent['entry'] and a['entry'] == digest(frames['ENTRY']), 'round exact next physical slot')
    need(e['origin'] == a['ballot'] == promise['ballot'] == selected['ballot'], 'round immutable ballot')
    need({k: v for k, v in proof.items() if k != 'accepts'} == a and {k: v for k, v in cert.items() if k != 'proofs'} == proof, 'round distinct phased records')
    need(digest(frames['PAYLOAD']) == e['payload'], 'round original payload')
    return frames, values


def current(files):
    selector = f.decode(files['selector.gsr'], 'records', 'SELECTOR'); prefix = 'generations/'+selector['generation']+'/'
    manifest = f.decode(files[prefix+'generation.gsr'], 'records', 'GENERATION')
    members = {k.removeprefix(prefix): v for k, v in files.items() if k.startswith(prefix) and k != prefix+'generation.gsr'}
    need(manifest['files'] == [dict(path=k, size=len(v), sha256=digest(v)) for k, v in sorted(members.items())]
         and selector['digest'] == digest(files[prefix+'generation.gsr'])
         and all(selector[k] == manifest[k] for k in ('root', 'node', 'generation')), 'round original generation inventory')
    packet = p.decode(members['source.gscp']); cap = packet['capsule']
    need(manifest['capsule'] == digest(packet['capsuleBytes']) and all(manifest[k] == cap[k] for k in ('root', 'cut', 'catalog', 'application')), 'round original capsule binding')
    for h, size in packet['images'].items(): need(len(members[h+'.image']) == size and digest(members[h+'.image']) == h, 'round original image')
    return prefix, members, packet


def anchor(cap): return {k: cap[k] for k in ('cut', 'catalog', 'application')}


def project_slot(root, slot, first, previous):
    originals = {n: inventory(root/'originals'/('slot-'+str(slot))/n) for n in NODES}
    prefix, members, old = current(originals['node-1']); cap = old['capsule']; root_hash = cap['root']
    phase, values = votes(originals['node-1']['pending.accept'], cap['cut']); entry, cert = values['ENTRY'], values['CERTIFICATE']
    need(cap['cut']['index'] == slot-1 and entry['kind'] == ('BARRIER' if slot % 2 == 0 else 'DATA'), 'round complete alternating workload')
    need(values['SELECTED']['cut']['index'] == 0 and values['SELECTED']['nextEntry'] is None and values['SELECTED']['ballot']['counter'] == 20, 'round original selection')
    need(originals['node-1']['selector.gsr'] == phase['SELECTOR'], 'round vote original selector')
    before = f.decode(old['objects'][cap['catalog']], 'records', 'CATALOG', root_hash)
    image = originals['node-1']['applied-end/application.image']; after = copy.deepcopy(before)
    after['cut'] = dict(before['cut'], index=slot, entry=digest(phase['ENTRY']))
    if entry['kind'] == 'DATA': after.update(application=digest(image), applicationSequence=before['applicationSequence']+1, lastDataIndex=slot)
    else: need(image == members[cap['application']+'.image'] and phase['PAYLOAD'] == b'', 'round BARRIER exact application')
    catalog = f.encode('records', 'CATALOG', after)
    if slot == 1:
        need(cap['items'] == [] and before['applicationSequence'] == 41, 'round initial conditional fixture')
        first = dict(parent=anchor(cap), end=dict(cut=after['cut'], catalog=digest(catalog), application=after['application']), certificate=digest(phase['CERTIFICATE']),
                     proof={digest(phase[k]): phase[k] for k in ('ENTRY', 'ACCEPT', 'PROOF', 'CERTIFICATE', 'PAYLOAD')})
        start = dict(root=root_hash, scope='RANGE', start=cap['cut'], catalogBefore=cap['catalog'], applicationBefore=cap['application'])
    else:
        need(len(cap['items']) == 1 and cap['items'][0]['kind'] == 'RANGE', 'round bounded range')
        start = f.decode(old['objects'][cap['items'][0]['statement']], 'records', 'CHECKPOINT', root_hash)
    statement = dict(start, end=after['cut'], catalogAfter=digest(catalog), applicationAfter=after['application'])
    raw_statement = f.encode('records', 'CHECKPOINT', statement)
    lowers = [] if slot == 1 else [anchor(cap)] if slot == 2 else [first['end'], anchor(cap)]
    extra = [] if slot <= 2 else [first['end']]
    identities = {}; end_acks = []; bridge_acks = [[] for _ in lowers]; end_files = {}
    for n, physical in originals.items():
        pref, local, packet = current(physical); local_phase, local_values = votes(physical['pending.accept'], cap['cut'])
        need(packet['capsuleBytes'] == old['capsuleBytes'] and all(local_phase[k] == phase[k] for k in ('ENTRY', 'ACCEPT', 'PROOF', 'CERTIFICATE', 'PAYLOAD')), 'round original voters agree')
        need(local_phase['SELECTOR'] == physical['selector.gsr'] and all(local[k.lower()+'.gsr'] == local_phase[k] for k in ('PROMISE', 'SELECTED')), 'round actual local vote authority')
        identity = f.decode(physical['node.gsr'], 'records', 'NODE', root_hash)['identity']; identities[n] = identity['storage']; need(identity['node'] == n == local_values['SELECTOR']['node'] and local_values['SELECTOR']['root'] == root_hash, 'round voter identity')
        root_value = f.decode(physical['root.gsr'], 'records', 'ROOT'); need(identity in root_value['initial'] and physical['root.gsr'][16:48].hex() == root_hash, 'round original root owner')
        need(old['objects'][root_value['genesis']] == physical['genesis.gsr'], 'round original genesis')
        original_grants = journal(physical['grants.gsr'], root_hash, n)
        if slot == 1:
            need(len(original_grants) == 4 and original_grants[0][0] == 'PROMISE' and original_grants[0][2]['ballot']['counter'] == 10, 'round bootstrap prior promise')
            original_grants = original_grants[1:]
        need([k for k, _, _ in original_grants] == ['PROMISE', 'BASIS', 'SELECTED'], 'round immutable original journal')
        for kind, raw, _ in original_grants: need(local[kind.lower()+'.gsr'] == raw, 'round journal/generation originals')
        basis = original_grants[1][2]; source_prefix = 'sources/'+basis['basisId']+'/'
        frozen = p.decode(physical[source_prefix+'source.gscp']); p.bind(frozen, local['basis.gsr'])
        need(cuts(local['selected-sources.gsr'], local_values['SELECTED']) == [basis['cut']]*3 and basis['cut']['index'] == 0, 'round original selected sources')
        if previous:
            immutable = {k: v for k, v in physical.items() if k not in ('pending.accept', 'applied-end') and not k.startswith('applied-end/')}
            need(immutable == {k: v for k, v in previous[n].items() if k != 'pending.accept'}, 'round previous exact publication retained')
        def ack(raw): return f.encode('records', 'CHECKPOINT_ACK', dict(root=root_hash, voter=n, incarnation=identity['storage'], cut=after['cut'], statement=digest(raw)))
        end = dict(zip(('selector.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr', 'application.image', 'ack.gsr'),
                       (physical['selector.gsr'], phase['CERTIFICATE'], catalog, raw_statement, image, ack(raw_statement))))
        end_acks.append(end['ack.gsr'])
        for i, lower in enumerate(lowers):
            raw = f.encode('records', 'CHECKPOINT', dict(statement, start=lower['cut'], catalogBefore=lower['catalog'], applicationBefore=lower['application']))
            label = 'parent' if lower == anchor(cap) else 'ancestor-0'
            end[label+'-statement.gsr'] = raw; end[label+'-ack.gsr'] = ack(raw); bridge_acks[i].append(ack(raw))
        end['plan.json'] = f.canonical(dict(schema='gse-v53-applied-end/1.3', root=root_hash, node=n,
            files=[dict(path=k, bytes=len(v), sha256=digest(v)) for k, v in sorted(end.items())]))
        need({k.removeprefix('applied-end/'): v for k, v in physical.items() if k.startswith('applied-end/')} == end, 'round exact original forced end')
        end_files[n] = end
        raw_common = b''.join(originals[v]['generations/'+f.decode(originals[v]['selector.gsr'], 'records', 'SELECTOR')['generation']+'/basis.gsr'] for v in NODES)
        need(local['selected-sources.gsr'] == raw_common, 'round all original selected physical voters')
    majority(cap['cut']['view'], list(identities)); majority(after['cut']['view'], list(identities))
    for label, kind in (('accepts', 'ACCEPT'), ('proofs', 'PROOF')):
        witnesses = [dict(voter=n, incarnation=s, receipt=digest(f.canonical(dict(root=root_hash, voter=n, incarnation=s, phase=kind, record=digest(phase[kind]))))) for n, s in sorted(identities.items())]
        need(cert[label] == witnesses, 'round exact original phased quorum')
    objects = {digest(originals['node-1'][k]): originals['node-1'][k] for k in ('root.gsr', 'genesis.gsr')}
    for raw in (catalog, raw_statement, *end_acks, *[phase[k] for k in ('ENTRY', 'ACCEPT', 'PROOF', 'CERTIFICATE', 'PAYLOAD')]): objects[digest(raw)] = raw
    ancestry = b''
    for lower, acknowledgements in zip(lowers, bridge_acks):
        raw = f.encode('records', 'CHECKPOINT', dict(statement, start=lower['cut'], catalogBefore=lower['catalog'], applicationBefore=lower['application']))
        for frame in (raw, *acknowledgements): objects[digest(frame)] = frame; ancestry += frame
    if slot > 1: objects.update(first['proof'])
    item = dict(kind='RANGE', statement=digest(raw_statement), endorsements=[digest(v) for v in end_acks], certificate=None, descriptor=None)
    packet = packet_bytes(dict(cap, cut=after['cut'], catalog=digest(catalog), application=after['application'], items=[item]), objects, {after['application']: len(image)})
    coverage = dict(schema='gse-v53-selected-coverage/1.3' if slot == 1 else 'gse-v53-round-coverage/1.3', selection=digest(phase['SELECTED']), parent=anchor(cap), certificate=digest(phase['CERTIFICATE']))
    if slot > 1: coverage['first'] = {k: first[k] for k in ('parent', 'end', 'certificate')}
    if extra: coverage['ancestors'] = extra
    result = {}
    for n, physical in originals.items():
        pref, local, _ = current(physical); slot_name = 'b' if pref == 'generations/a/' else 'a'; new_prefix = 'generations/'+slot_name+'/'
        files = {k: local[k] for k in ('promise.gsr', 'basis.gsr', 'selected.gsr', 'selected-sources.gsr')}
        files.update({'source.gscp': packet, COVERAGE: f.canonical(coverage), after['application']+'.image': image})
        if ancestry: files['ancestry.gsr'] = ancestry
        manifest = dict(root=root_hash, node=n, generation=slot_name, cut=after['cut'], catalog=digest(catalog), application=after['application'],
            capsule=digest(p.decode(packet)['capsuleBytes']), promise=digest(files['promise.gsr']), basis=digest(files['basis.gsr']), selection=digest(files['selected.gsr']), ownedTail=None,
            files=[dict(path=k, size=len(v), sha256=digest(v)) for k, v in sorted(files.items())])
        files['generation.gsr'] = f.encode('records', 'GENERATION', manifest)
        expected = {k: v for k, v in physical.items() if k not in ('pending.accept', 'applied-end') and not k.startswith(('generations/', 'applied-end/'))}
        expected[new_prefix[:-1]] = None; expected.update({new_prefix+k: v for k, v in files.items()})
        if slot == 1: expected['grants.gsr'] = b''.join(raw for _, raw, _ in journal(physical['grants.gsr'], root_hash, n)[1:])
        expected['pending.accept'] = EMPTY; expected['selector.gsr'] = f.encode('records', 'SELECTOR', dict(root=root_hash, node=n, generation=slot_name, digest=digest(files['generation.gsr'])))
        need(sum(k.endswith('.image') for k in expected) == 2 and len(objects) <= 25 and len(files[COVERAGE]) <= 4096, 'round bounded physical lifetime')
        result[n] = expected
    return first, result, end_files


def original_slot(root, slot, first, previous):
    first, result, _ = project_slot(root, slot, first, previous)
    for n in NODES:
        actual = inventory(root/'snapshots'/('round-0' if slot == 1 else 'slot-'+str(slot))/n)
        need(actual == result[n], 'round exact publication/retirement bytes')
    return first, result


def validate(root):
    root = Path(root); receipt = json.loads(read(root/'receipt.json'))
    need(receipt['status'] == 'PASS' and receipt['slots'] == 13 and receipt['sameBallot'] is True and receipt['applicationSequence'] == 48
         and receipt['freshProcesses'] is False and receipt['publicReady'] is False, 'round scope/inventory')
    need({v.name for v in (root/'originals').iterdir()} == {'slot-'+str(i) for i in range(1, 14)}, 'round complete original slots')
    first = None; previous = None
    for slot in range(1, 14): first, previous = original_slot(root, slot, first, previous)
    need(inventory(root/'before-fresh-prepare') == previous['node-1'] and all(inventory(root/n) == previous[n] for n in NODES[1:]), 'round terminal owners')
    fresh = inventory(root/'node-1')
    # New PREPARE is checked from its actual journal/source, without treating the old BASIS as a new cut.
    root_hash = fresh['root.gsr'][16:48].hex(); grants = journal(fresh['grants.gsr'], root_hash, 'node-1'); basis = grants[-1][2]
    need([v[0] for v in grants] == ['PROMISE', 'BASIS', 'SELECTED', 'PROMISE', 'BASIS'] and basis['ballot']['counter'] == 21 and basis['cut']['index'] == 13 and basis['accepted'] is None, 'round fresh capture')
    source = fresh['sources/'+basis['basisId']+'/source.gscp']; p.bind(p.decode(source), grants[-1][1]); need(source == current(previous['node-1'])[1]['source.gscp'], 'round fresh exact source')
    return dict(status='PASS', slots=13, nodePublications=39, sameBallot=True, originalFirst=True, physicalBytes=True, processForceOrder=False, imageSemantics='separate-core-gates')


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    for variant in ('missing-original-slot', 'missing-original-proof', 'missing-first-certificate', 'changed-first-coverage', 'changed-next-coverage', 'changed-ancestor-end', 'changed-original-source', 'missing-peer-end', 'retained-old-generation', 'retained-covered-vote', 'false-ready'):
        with tempfile.TemporaryDirectory(prefix='v53-round-negative-') as tmp:
            case = Path(tmp)/'evidence'; shutil.copytree(root, case)
            orig = case/'originals/slot-3/node-1'; final = case/'snapshots/slot-3/node-1'; sel = f.decode(read(final/'selector.gsr'), 'records', 'SELECTOR'); gen = final/'generations'/sel['generation']
            if variant == 'missing-original-slot': shutil.rmtree(case/'originals/slot-7')
            elif variant == 'missing-original-proof': (orig/'pending.accept').write_bytes(EMPTY)
            elif variant == 'missing-first-certificate': (case/'originals/slot-1/node-2/pending.accept').write_bytes(EMPTY)
            elif variant in ('changed-first-coverage', 'changed-next-coverage'):
                value = json.loads(read(gen/COVERAGE)); value['first' if variant == 'changed-first-coverage' else 'parent'] = {}; (gen/COVERAGE).write_bytes(f.canonical(value))
            elif variant == 'changed-ancestor-end': (orig/'applied-end/ancestor-0-statement.gsr').write_bytes(b'')
            elif variant == 'changed-original-source': (next((orig/'sources').iterdir())/'source.gscp').write_bytes(b'')
            elif variant == 'missing-peer-end': (case/'originals/slot-3/node-3/applied-end/ack.gsr').unlink()
            elif variant == 'retained-old-generation': (final/'generations/obsolete').mkdir()
            elif variant == 'retained-covered-vote': (final/'pending.accept').write_bytes(read(orig/'pending.accept'))
            else:
                receipt = json.loads(read(case/'receipt.json')); receipt['publicReady'] = True; (case/'receipt.json').write_bytes(f.canonical(receipt))
            try: validate(case)
            except (ValueError, OSError, KeyError, TypeError): negatives.append(variant)
            else: raise ValueError('accepted round mutation: '+variant)
    with tempfile.TemporaryDirectory(prefix='v53-round-portable-') as tmp:
        case = Path(tmp)/'evidence'; shutil.copytree(root, case); need(validate(case) == result, 'round portable replay')
    return dict(result, negatives=negatives, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); args = parser.parse_args(); print(json.dumps(qualify(args.root), sort_keys=True))
