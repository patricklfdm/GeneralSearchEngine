"""Three-owner context retirement, exact reacceptance, publication and continuation.

Derive every recorded authority from original physical phases and application
ends. Historical bootstrap observations and typed image semantics are separate.
"""
import argparse
import json
from pathlib import Path
import shutil
import struct
import tempfile
from . import staged_handoff_evidence as staged
from . import carried_publication_evidence as carried
from . import pending_context_evidence as context
from .round_storage_evidence import original_slot, current, NODES

f, p, digest, inventory, journal, need = staged.f, staged.p, staged.digest, staged.inventory, staged.journal, staged.need
STAGES = ('old-certified', 'prepared', 'installed', 'context', 'context-floor', 'context-retired',
          'source-retired', 'reaccepted', 'published', 'continued', 'fresh')


def snapshot(root, stage, values):
    directory = root/'carried-snapshots'/stage
    need(directory.is_dir() and not directory.is_symlink() and {p.name for p in directory.iterdir()} == set(NODES), 'context publication owner inventory')
    for node in NODES:
        need(inventory(directory/node) == values[node], 'context publication exact '+stage+': '+node)
        need(sum(n.endswith('.image') for n in values[node]) <= 7, 'context publication physical image bound')


def transfer(root, previous, certified, phases):
    packets = {}; histories = {}; prepared = {}; old_ids = {}
    for node in NODES:
        _, local, packet = current(previous[node]); cap = packet['capsule']
        prior = journal(previous[node]['grants.gsr'], cap['root'], node)
        observed = inventory(root/'carried-snapshots/prepared'/node)
        rows = journal(observed['grants.gsr'], cap['root'], node)
        need(rows[:3] == prior and len(prior) == 3 and [kind for kind, _, _ in rows[3:]] == ['PROMISE', 'BASIS', 'SELECTED'], 'context publication grant groups')
        promise, basis, selected = rows[3:]; old_ids[node] = prior[1][2]['basisId']
        ballot = dict(prior[0][2]['ballot'], counter=21)
        need(promise[2] == dict(prior[0][2], ballot=ballot, basisId=promise[2]['basisId']) and promise[2]['basisId'] != old_ids[node], 'context publication newer original grant')
        objects = dict(packet['objects']); objects.update({digest(raw): raw for raw in phases})
        raw = staged.packet_bytes(cap, objects, packet['images']); data = p.decode(raw); packets[node] = raw
        need(basis[2] == dict(promise[2], voter=node, cut=cap['cut'], capsule=digest(data['capsuleBytes']), inventory=digest(data['indexBytes']), accepted=digest(phases[2])), 'context publication exact local certified capture')
        prefix = 'sources/'+basis[2]['basisId']
        prepared[node] = dict(certified[node], **{'grants.gsr': b''.join(v[1] for v in rows), prefix: None, prefix+'/source.gscp': raw},
                              **{prefix+'/'+h+'.image': local[h+'.image'] for h in packet['images']})
        histories[node] = rows[3:]
    need(len(set(packets.values())) == 1 and len({rows[0][2]['basisId'] for rows in histories.values()}) == 3, 'context publication separate actual sources')
    snapshot(root, 'prepared', prepared)
    selected = f.encode('records', 'SELECTED', dict(root=cap['root'], view=promise[2]['view'], ballot=ballot, cut=cap['cut'], nextEntry=digest(phases[0]),
        sources=[dict(voter=n, basisId=histories[n][1][2]['basisId'], basisDigest=digest(histories[n][1][1])) for n in NODES]))
    need(all(v[2][1] == selected for v in histories.values()), 'context publication exact selection')
    installed = {}; contexts = {}; old_prefixes = {}
    for node in NODES:
        old_prefix, old, old_packet = current(previous[node]); old_prefixes[node] = old_prefix
        slot = 'b' if old_prefix == 'generations/a/' else 'a'
        files = {'promise.gsr': histories[node][0][1], 'basis.gsr': histories[node][1][1], 'selected.gsr': selected,
                 'selected-sources.gsr': b''.join(histories[n][1][1] for n in NODES), 'source.gscp': packets[node], 'owned-tail.gsr': phases[2]}
        files.update({h+'.image': old[h+'.image'] for h in old_packet['images']})
        selector, generation = carried.generation(files, p.decode(packets[node])['capsule'], node, slot, digest(phases[2]))
        installed[node] = dict(prepared[node], **generation, **{'selector.gsr': selector})
        identity = f.decode(previous[node]['node.gsr'], 'records', 'NODE')['identity']
        binding = dict(schema='gse-v53-pending-context/1.3', root=cap['root'], node=node, storage=identity['storage'],
            backingPacket=context.info(packets[node]), vote=context.info(certified[node]['pending.accept']),
            entry=digest(phases[0]), payload=digest(phases[1]), accept=digest(phases[2]), proof=digest(phases[3]), certificate=digest(phases[4]))
        metadata = {n.removeprefix(old_prefix): raw for n, raw in previous[node].items()
                    if n.startswith(old_prefix) and not n.endswith('.image') and not n.endswith('/source.gscp')}
        envelope = struct.pack('>I', len(old_packet['capsuleBytes']))+old_packet['capsuleBytes']+struct.pack('>I',len(old_packet['indexBytes']))+old_packet['indexBytes']
        raw_context = context.encode([f.canonical(binding), previous[node]['selector.gsr'], histories[node][0][1], histories[node][1][1], envelope], metadata)
        context.decode(raw_context)
        rebuilt, _ = context.reconstruct(envelope, p.decode(packets[node]))
        need(rebuilt == old['source.gscp'], 'context publication exact borrowed original')
        contexts[node] = dict(installed[node], **{'pending.context': raw_context})
    snapshot(root, 'installed', installed); snapshot(root, 'context', contexts)
    floors = {}; retired = {}; sources = {}; accepted = {}
    for i, node in enumerate(NODES):
        peers = sorted([node, NODES[(i+1)%3]]); refs = []; copies = {}
        for peer in peers:
            prefix, members, data = current(installed[peer]); raw_manifest = installed[peer][prefix+'generation.gsr']
            manifest = f.decode(raw_manifest, 'records', 'GENERATION')
            need(data['capsule']['cut'] == cap['cut'], 'context publication common governing cut')
            refs.append(dict(voter=peer, generation=digest(raw_manifest), catalog=manifest['catalog'], snapshot=manifest['application']))
            copy_prefix = 'floor-copies/'+digest(raw_manifest)
            copies[copy_prefix] = None
            copies.update({copy_prefix+'/'+n.removeprefix(prefix): raw for n, raw in installed[peer].items() if n.startswith(prefix)})
        context.majority(cap['cut']['view'], peers)
        floor = f.encode('records', 'FLOOR', dict(root=cap['root'], node=node, cut=cap['cut'], sources=refs))
        floors[node] = dict(contexts[node], **{'floor-copies': None, 'floor-copies/floor.gsr': floor, 'floor-copies/proposal.gsr': floor}, **copies)
        old_prefix = old_prefixes[node]
        retired[node] = {n: raw for n, raw in floors[node].items() if n != old_prefix[:-1] and not n.startswith(old_prefix)}
        source = 'sources/'+old_ids[node]
        sources[node] = {n: raw for n, raw in retired[node].items() if n != source and not n.startswith(source+'/')}
        sources[node]['grants.gsr'] = b''.join(row[1] for row in histories[node])
        new_accept = f.encode('records', 'ACCEPT', dict(f.decode(phases[2], 'records', 'ACCEPT'), ballot=ballot))
        vote = staged.container([installed[node]['selector.gsr'], histories[node][0][1], selected, phases[0], new_accept], phases[1])
        accepted[node] = {n: raw for n, raw in sources[node].items() if n not in ('pending.context', 'floor-copies') and not n.startswith('floor-copies/')}
        accepted[node]['pending.accept'] = vote
    for stage, values in [('context-floor',floors),('context-retired',retired),('source-retired',sources),('reaccepted',accepted)]: snapshot(root,stage,values)
    return accepted, histories, old_ids


def validate(root):
    root = Path(root)
    need(root.is_dir() and not root.is_symlink(), 'context publication root')
    for name, members in [('carried-snapshots',STAGES),('originals',('slot-1','slot-2','slot-3'))]:
        directory = root/name
        need(directory.is_dir() and not directory.is_symlink() and {v.name for v in directory.iterdir()} == set(members), 'context publication stage inventory')
    _, previous = original_slot(root,1,None,None)
    certified, phases = staged.old_certificate(root,previous)
    accepted, histories, old_ids = transfer(root,previous,certified,phases)
    published, first = carried.publication(root,2,accepted,None)
    continued, _ = carried.publication(root,3,published,first)
    staged.fresh(root,continued,histories,old_ids)
    expected = dict(schema='gse-v53-context-publication-v1', status='PASS', nodes=3, entryOrigin=20, acceptBallot=21,
                    publishedCut=3, applicationSequence=43, freshProcesses=False, runtimeEnabled=False)
    receipt = json.loads(staged.read(root/'receipt.json'))
    need(f.canonical(receipt) == f.canonical(expected), 'context publication receipt scope')
    return dict(status='PASS', nodes=3, nodePublications=6, originalFirst=True, physicalBytes=True,
                entryOrigin=20, acceptBallot=21, publishedCut=3, applicationSequence=43,
                imageSemantics='separate-core-producer', processForceOrder=False, freshProcesses=False, runtimeEnabled=False)


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    stages = [('old-certified','staged exact old-certified owner: node-1'),
              *[(stage,'context publication exact '+stage+': node-1') for stage in STAGES[1:8]],
              ('published','carried exact publication/retirement bytes'),('continued','carried exact publication/retirement bytes'),
              ('fresh','staged exact fresh owner: node-1')]
    for stage, reason in stages:
        with tempfile.TemporaryDirectory(prefix='v53-context-publication-negative-') as tmp:
            moved = Path(tmp)/'evidence'; shutil.copytree(root,moved)
            # A protected local field must survive every cut, including after publication.
            path=moved/'carried-snapshots'/stage/'node-1/allocator.gsr'; path.write_bytes(b'changed')
            try: validate(moved)
            except ValueError as error:
                need(str(error)==reason, 'wrong context publication negative: '+stage+': '+str(error)); negatives.append(dict(case=stage,reason=reason))
            else: raise ValueError('accepted context publication mutation: '+stage)
    for name in ('bad-original','new-origin','lost-context-source','changed-context','kept-context','lost-application-ack','false-process'):
        with tempfile.TemporaryDirectory(prefix='v53-context-publication-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved);snaps=moved/'carried-snapshots'
            if name == 'bad-original':
                (moved/'originals/slot-1/node-1/applied-end/ack.gsr').write_bytes(b'changed');reason='round exact original forced end'
            elif name == 'new-origin':
                path=snaps/'reaccepted/node-1/pending.accept';frames,values=carried.pending(path.read_bytes())
                entry=f.encode('records','ENTRY',dict(values['ENTRY'],origin=values['ACCEPT']['ballot']))
                acceptance=f.encode('records','ACCEPT',dict(values['ACCEPT'],entry=digest(entry)))
                path.write_bytes(staged.container([frames[k] for k in ('SELECTOR','PROMISE','SELECTED')]+[entry,acceptance],frames['PAYLOAD']))
                reason='context publication exact reaccepted: node-1'
            elif name == 'lost-context-source':
                path=snaps/'source-retired/node-1'; next((path/'sources').rglob('source.gscp')).unlink();reason='context publication exact source-retired: node-1'
            elif name == 'changed-context':
                (snaps/'context-retired/node-1/pending.context').write_bytes(b'changed');reason='context publication exact context-retired: node-1'
            elif name == 'kept-context':
                shutil.copyfile(snaps/'source-retired/node-1/pending.context',snaps/'reaccepted/node-1/pending.context');reason='context publication exact reaccepted: node-1'
            elif name == 'lost-application-ack':
                (moved/'originals/slot-2/node-1/applied-end/ack.gsr').write_bytes(b'changed');reason='carried original applied ends'
            else:
                path=moved/'receipt.json';v=json.loads(path.read_bytes());v['freshProcesses']=True;path.write_bytes(f.canonical(v));reason='context publication receipt scope'
            try: validate(moved)
            except ValueError as error:
                need(str(error)==reason,'wrong context publication negative: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted context publication mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-context-publication-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);need(validate(moved)==result,'context publication portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');a=parser.parse_args();print(json.dumps(qualify(a.root),sort_keys=True))
