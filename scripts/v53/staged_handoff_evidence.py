"""Independent physical replay of superseded private application staging.

Derive old local certificates/ends and their frozen sources before validating the
new selection, retirement and new-round publication. This does not independently
execute the core image codec or establish fsync/power-loss/allocator behaviour.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import struct
import tempfile
from . import carried_publication_evidence as carried
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

STAGES = ('old-certified', 'staged', 'prepared', 'installed', 'retired', 'reaccepted', 'reclaimed', 'published', 'continued', 'fresh')


def snapshot(root, stage, expected):
    path = root/'carried-snapshots'/stage
    need({v.name for v in path.iterdir()} == set(NODES), 'staged complete owner snapshot: '+stage)
    for node in NODES:
        need(inventory(path/node) == expected[node], 'staged exact '+stage+' owner: '+node)
        need(sum(name.endswith('.image') for name in expected[node]) <= 7, 'staged physical image bound')


def old_certificate(root, previous):
    entry_raw = read(root/'entry.gsr'); payload = read(root/'payload.bin')
    _, files, packet = current(previous['node-1']); cap = packet['capsule']; selected = f.decode(files['selected.gsr'], 'records', 'SELECTED')
    need(cap['cut']['index'] == 1 and selected['cut']['index'] == 0 and selected['ballot']['counter'] == 20 and selected['nextEntry'] is None,
         'staged original same-round authority')
    entry = dict(root=cap['root'], authority=selected['view'], index=2, previous=cap['cut']['entry'], origin=selected['ballot'], kind='DATA', payload=digest(payload))
    need(entry_raw == f.encode('records', 'ENTRY', entry), 'staged exact original ENTRY/payload')
    acceptance = dict(root=cap['root'], authority=selected['view'], ballot=selected['ballot'], index=2, entry=digest(entry_raw))
    accept_raw = f.encode('records', 'ACCEPT', acceptance)
    identities = {node: f.decode(previous[node]['node.gsr'], 'records', 'NODE')['identity'] for node in NODES}
    def witnesses(kind, raw):
        return [dict(voter=node, incarnation=identities[node]['storage'], receipt=digest(f.canonical(dict(root=cap['root'], voter=node,
                    incarnation=identities[node]['storage'], phase=kind, record=digest(raw))))) for node in NODES]
    proof = dict(acceptance, accepts=witnesses('ACCEPT', accept_raw)); proof_raw = f.encode('records', 'PROOF', proof)
    certificate = dict(proof, proofs=witnesses('PROOF', proof_raw)); certificate_raw = f.encode('records', 'CERTIFICATE', certificate)
    expected = {}
    for node in NODES:
        _, local, local_packet = current(previous[node]); need(local_packet['capsuleBytes'] == packet['capsuleBytes'], 'staged common old parent')
        first = container([previous[node]['selector.gsr'], local['promise.gsr'], local['selected.gsr'], entry_raw, accept_raw], payload)
        body = first[12:]+proof_raw+certificate_raw; pending = struct.pack('>4sHHI', b'GSPV', 1, 3, len(body)+12)+body
        expected[node] = dict(previous[node], **{'pending.accept': pending})
    snapshot(root, 'old-certified', expected)
    return expected, (entry_raw, payload, accept_raw, proof_raw, certificate_raw)


def original_ends(root, certified, phases):
    _, _, old = current(certified['node-1']); cap = old['capsule']; entry, _, _, _, certificate = phases
    image = read(root/'carried-snapshots/staged/node-1/applied-end/application.image', 64*1024*1024)
    after = copy.deepcopy(f.decode(old['objects'][cap['catalog']], 'records', 'CATALOG'))
    need(after['applicationSequence'] == 42, 'staged original application sequence')
    after.update(cut=dict(after['cut'], index=2, entry=digest(entry)), application=digest(image), applicationSequence=43, lastDataIndex=2)
    catalog = f.encode('records', 'CATALOG', after)
    start = f.decode(old['objects'][cap['items'][0]['statement']], 'records', 'CHECKPOINT')
    statement = dict(start, end=after['cut'], catalogAfter=digest(catalog), applicationAfter=after['application'])
    statement_raw = f.encode('records', 'CHECKPOINT', statement)
    parent = anchor(cap)
    parent_raw = f.encode('records', 'CHECKPOINT', dict(statement, start=parent['cut'], catalogBefore=parent['catalog'], applicationBefore=parent['application']))
    result = {}
    for node in NODES:
        identity = f.decode(certified[node]['node.gsr'], 'records', 'NODE')['identity']
        def ack(raw):
            return f.encode('records', 'CHECKPOINT_ACK', dict(root=cap['root'], voter=node, incarnation=identity['storage'], cut=after['cut'], statement=digest(raw)))
        end = dict(zip(('selector.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr', 'application.image', 'ack.gsr', 'parent-statement.gsr', 'parent-ack.gsr'),
                       (certified[node]['selector.gsr'], certificate, catalog, statement_raw, image, ack(statement_raw), parent_raw, ack(parent_raw))))
        end['plan.json'] = f.canonical(dict(schema='gse-v53-applied-end/1.3', root=cap['root'], node=node,
            files=[dict(path=name, bytes=len(value), sha256=digest(value)) for name, value in sorted(end.items())]))
        result[node] = dict(certified[node], **{'applied-end': None}, **{'applied-end/'+name: value for name, value in end.items()})
    snapshot(root, 'staged', result)
    return result, image


def handoff(root, previous, staged, phases):
    source_packets = {}; histories = {}; prepared = {}; old_bases = {}
    for node in NODES:
        _, local, packet = current(previous[node]); cap = packet['capsule']; old_selected = f.decode(local['selected.gsr'], 'records', 'SELECTED')
        old_bases[node] = f.decode(local['basis.gsr'], 'records', 'BASIS')['basisId']
        objects = dict(packet['objects']); objects.update({digest(raw): raw for raw in phases})
        raw_packet = packet_bytes(cap, objects, packet['images']); source_packets[node] = raw_packet; proposed = p.decode(raw_packet)
        observed = inventory(root/'carried-snapshots/prepared'/node); rows = journal(observed['grants.gsr'], cap['root'], node)
        prior = journal(previous[node]['grants.gsr'], cap['root'], node)
        need(rows[:3] == prior and len(prior) == 3 and [kind for kind, _, _ in rows[3:]] == ['PROMISE', 'BASIS', 'SELECTED'], 'staged old and new exact grants')
        promise, basis, selected = rows[3:]; ballot = dict(old_selected['ballot'], counter=21)
        need(promise[2] == dict(prior[0][2], ballot=ballot, basisId=promise[2]['basisId']) and promise[2]['basisId'] != old_bases[node], 'staged higher original promise')
        need(basis[2] == dict(promise[2], voter=node, cut=cap['cut'], capsule=digest(proposed['capsuleBytes']), inventory=digest(proposed['indexBytes']), accepted=digest(phases[2])),
             'staged certified original local capture')
        source = 'sources/'+basis[2]['basisId']; expected = dict(staged[node], **{'grants.gsr': b''.join(row[1] for row in rows), source: None, source+'/source.gscp': raw_packet})
        expected.update({source+'/'+h+'.image': local[h+'.image'] for h in packet['images']})
        prepared[node] = expected; histories[node] = rows[3:]
    need(len({histories[node][0][2]['basisId'] for node in NODES}) == 3, 'staged distinct source identities')
    snapshot(root, 'prepared', prepared)
    selected = dict(root=cap['root'], view=old_selected['view'], ballot=ballot, cut=cap['cut'], nextEntry=digest(phases[0]),
                    sources=[dict(voter=node, basisId=histories[node][1][2]['basisId'], basisDigest=digest(histories[node][1][1])) for node in NODES])
    selected_raw = f.encode('records', 'SELECTED', selected)
    need(all(histories[node][2][1] == selected_raw for node in NODES), 'staged exact selected set and original entry')
    # All three original sources agree, including the old proof and certificate.
    need(len(set(source_packets.values())) == 1, 'staged certified sources agree')
    raw_packet = source_packets['node-1']; installed = {}; retired = {}; reaccepted = {}; reclaimed = {}
    for node in NODES:
        prefix, local, packet = current(previous[node]); target = 'b' if prefix == 'generations/a/' else 'a'
        files = {'promise.gsr': histories[node][0][1], 'basis.gsr': histories[node][1][1], 'selected.gsr': selected_raw,
                 'selected-sources.gsr': b''.join(histories[n][1][1] for n in NODES), 'source.gscp': raw_packet, 'owned-tail.gsr': phases[2]}
        files.update({h+'.image': local[h+'.image'] for h in packet['images']})
        selector, generation = carried.generation(files, p.decode(raw_packet)['capsule'], node, target, digest(phases[2]))
        expected = dict(prepared[node]); expected.update(generation); expected['selector.gsr'] = selector; installed[node] = expected
        retired[node] = {name: value for name, value in expected.items() if name != 'applied-end' and not name.startswith('applied-end/')}
        acceptance = f.encode('records', 'ACCEPT', dict(f.decode(phases[2], 'records', 'ACCEPT'), ballot=ballot))
        vote = container([selector, files['promise.gsr'], selected_raw, phases[0], acceptance], phases[1])
        reaccepted[node] = dict(retired[node], **{'pending.accept': vote})
        source = 'sources/'+old_bases[node]
        reclaimed[node] = {name: value for name, value in reaccepted[node].items()
                           if name != prefix[:-1] and not name.startswith(prefix) and name != source and not name.startswith(source+'/')}
        reclaimed[node]['grants.gsr'] = b''.join(row[1] for row in histories[node])
    for stage, expected in (('installed', installed), ('retired', retired), ('reaccepted', reaccepted), ('reclaimed', reclaimed)): snapshot(root, stage, expected)
    return reclaimed, histories, old_bases


def fresh(root, continued, histories, old_bases):
    expected = {}
    for node in NODES:
        observed = inventory(root/'carried-snapshots/fresh'/node); _, local, packet = current(continued[node]); cap = packet['capsule']
        rows = journal(observed['grants.gsr'], cap['root'], node)
        need(rows[:3] == histories[node] and [kind for kind, _, _ in rows[3:]] == ['PROMISE', 'BASIS'], 'staged final fresh grant')
        promise, basis = rows[-2:]; ballot = dict(histories[node][0][2]['ballot'], counter=22)
        need(promise[2] == dict(histories[node][0][2], ballot=ballot, basisId=promise[2]['basisId'])
             and promise[2]['basisId'] not in {old_bases[node], histories[node][0][2]['basisId']}, 'staged final fresh identity')
        need(basis[2] == dict(promise[2], voter=node, cut=cap['cut'], capsule=digest(packet['capsuleBytes']), inventory=digest(packet['indexBytes']), accepted=None),
             'staged fresh source cannot resurrect old certified tail')
        source = 'sources/'+basis[2]['basisId']; expected[node] = dict(continued[node], **{'grants.gsr': b''.join(row[1] for row in rows), source: None, source+'/source.gscp': local['source.gscp']})
        expected[node].update({source+'/'+h+'.image': local[h+'.image'] for h in packet['images']})
        need(inventory(root/node) == expected[node], 'staged final retained owner')
    snapshot(root, 'fresh', expected)


def validate(root):
    root = Path(root); receipt = json.loads(read(root/'receipt.json'))
    semantic = dict(schema='gse-v53-staged-handoff-v1', status='PASS', execution='private-staged-application-handoff', historicalBootstrap='conditional-fixture',
                    freshProcesses=False, runtimeEnabled=False, powerLoss=False, entry=digest(read(root/'entry.gsr')), origin=20, acceptBallot=21,
                    selectedCut=1, publishedCut=3, applicationSequence=43)
    bounds = dict(maximumImages=7, maximumMetadata=384*1024*1024, maximumStaging=512*1024*1024)
    need({k: v for k, v in receipt.items() if k not in bounds} == semantic and set(receipt) == set(semantic) | set(bounds), 'staged handoff exact scope/receipt')
    need(all(receipt[k] is False for k in ('freshProcesses', 'runtimeEnabled', 'powerLoss'))
         and all(type(receipt[k]) is int for k in ('origin', 'acceptBallot', 'selectedCut', 'publishedCut', 'applicationSequence')), 'staged handoff scope field types')
    need(all(type(receipt[k]) is int and 0 < receipt[k] <= limit for k, limit in bounds.items()), 'staged producer-observed resource bounds')
    for family, members in (('originals', ('slot-1', 'slot-2', 'slot-3')), ('carried-snapshots', STAGES)):
        directory = root/family
        need(directory.is_dir() and not directory.is_symlink() and {v.name for v in directory.iterdir()} == set(members), 'staged complete original/stage matrix')
        for member in members:
            owners = directory/member
            need(owners.is_dir() and not owners.is_symlink() and {v.name for v in owners.iterdir()} == set(NODES), 'staged complete physical owner matrix')
    _, previous = original_slot(root, 1, None, None)
    certified, phases = old_certificate(root, previous); staged, image = original_ends(root, certified, phases)
    reclaimed, histories, old_bases = handoff(root, previous, staged, phases)
    published, first = carried.publication(root, 2, reclaimed, None)
    for node in NODES:
        original = inventory(root/'originals/slot-2'/node); frames, _ = carried.pending(original['pending.accept'], ('PROOF', 'CERTIFICATE'))
        need(frames['CERTIFICATE'] != phases[-1] and original['applied-end/certificate.gsr'] == frames['CERTIFICATE']
             and original['applied-end/application.image'] == image, 'staged new certificate and identical once-applied result')
    continued, _ = carried.publication(root, 3, published, first); fresh(root, continued, histories, old_bases)
    return dict(status='PASS', nodes=3, oldCertificates=3, derivedStagingRetirements=3, nodePublications=6, oldBallot=20, newBallot=21,
                originalFirst=True, physicalBytes=True, imageSemantics='separate-core-gates', processForceOrder=False,
                resourcePeaks='producer-observed-bounded', freshProcesses=False, runtimeEnabled=False, powerLoss=False)


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    for variant in ('lost-old-proof', 'changed-original-payload', 'missing-old-end-ack', 'changed-old-end-plan', 'old-end-wrong-ancestor',
                    'changed-frozen-certificate', 'changed-selection', 'old-vote-deleted', 'old-source-deleted', 'old-generation-deleted',
                    'staging-retained', 'rewritten-entry-origin', 'old-certificate-reused', 'changed-new-first-coverage', 'resurrected-tail'):
        with tempfile.TemporaryDirectory(prefix='v53-staged-handoff-negative-') as tmp:
            case = Path(tmp)/'evidence'; shutil.copytree(root, case); snaps = case/'carried-snapshots'
            if variant == 'lost-old-proof': (snaps/'old-certified/node-2/pending.accept').write_bytes(EMPTY)
            elif variant == 'changed-original-payload': (case/'payload.bin').write_bytes(b'changed')
            elif variant == 'missing-old-end-ack': (snaps/'staged/node-3/applied-end/ack.gsr').unlink()
            elif variant == 'changed-old-end-plan': (snaps/'staged/node-1/applied-end/plan.json').write_bytes(b'{}')
            elif variant == 'old-end-wrong-ancestor': (snaps/'staged/node-1/applied-end/parent-statement.gsr').write_bytes(b'changed')
            elif variant == 'changed-frozen-certificate':
                owner = snaps/'prepared/node-1'; raw = inventory(owner); root_hash = raw['root.gsr'][16:48].hex(); basis = journal(raw['grants.gsr'], root_hash, 'node-1')[-2][2]
                (owner/'sources'/basis['basisId']/'source.gscp').write_bytes(b'changed')
            elif variant == 'changed-selection':
                owner = snaps/'installed/node-1'; prefix, _, _ = current(inventory(owner)); (owner/prefix/'selected.gsr').write_bytes(b'changed')
            elif variant == 'old-vote-deleted': (snaps/'retired/node-1/pending.accept').write_bytes(EMPTY)
            elif variant == 'old-source-deleted':
                owner = snaps/'retired/node-1'; raw = inventory(owner); root_hash = raw['root.gsr'][16:48].hex(); old = journal(raw['grants.gsr'], root_hash, 'node-1')[1][2]['basisId']; shutil.rmtree(owner/'sources'/old)
            elif variant == 'old-generation-deleted':
                owner = snaps/'retired/node-1'; prefix, _, _ = current(inventory(owner)); shutil.rmtree(owner/('generations/a' if prefix == 'generations/b/' else 'generations/b'))
            elif variant == 'staging-retained': (snaps/'retired/node-1/applied-end').mkdir()
            elif variant == 'rewritten-entry-origin':
                owner = snaps/'reaccepted/node-1/pending.accept'; frames, values = carried.pending(read(owner))
                entry = f.encode('records', 'ENTRY', dict(values['ENTRY'], origin=values['ACCEPT']['ballot'])); accept = f.encode('records', 'ACCEPT', dict(values['ACCEPT'], entry=digest(entry)))
                owner.write_bytes(container([frames[k] for k in ('SELECTOR', 'PROMISE', 'SELECTED')]+[entry, accept], frames['PAYLOAD']))
            elif variant == 'old-certificate-reused':
                (case/'originals/slot-2/node-1/applied-end/certificate.gsr').write_bytes(read(snaps/'staged/node-1/applied-end/certificate.gsr'))
            elif variant == 'changed-new-first-coverage':
                owner = snaps/'continued/node-1'; prefix, _, _ = current(inventory(owner)); (owner/prefix/COVERAGE).write_bytes(b'{}')
            else: (snaps/'fresh/node-1/pending.accept').write_bytes(read(snaps/'old-certified/node-1/pending.accept'))
            try: validate(case)
            except (ValueError, OSError, KeyError, TypeError): negatives.append(variant)
            else: raise ValueError('accepted staged handoff mutation: '+variant)
    with tempfile.TemporaryDirectory(prefix='v53-staged-handoff-portable-') as tmp:
        case = Path(tmp)/'evidence'; shutil.copytree(root, case); need(validate(case) == result, 'staged handoff portable replay')
    return dict(result, negatives=negatives, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); args = parser.parse_args(); print(json.dumps(qualify(args.root), sort_keys=True))
