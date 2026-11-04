"""Derive native ADD/REPLACE publication inventories from original applied snapshots.

The semantic reader first authenticates commands, catalogs and observed ACKs.
This reader derives the exact next packet, coverage, generation and retention
transition; it never takes those expected bytes from the published snapshot.
Pre-publication activation/maintenance and process cuts remain separate gates.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import tempfile

from . import joining_catalog_evidence as semantic
from . import joining_phase_evidence as phases
from . import admitted_cross_view_evidence as cross
from . import peer_retention_evidence as peers
from . import learner_retention_evidence as learner

f, need, sha, disk = semantic.f, semantic.need, semantic.sha, semantic.disk
PEERS = 'peer-retention.gspr'


class CheckpointReceipts:
    """Use complete delivered original transfers, not published endorsement lists.

    A forced joining ACK may exist without ever being requested by a sufficient
    overlapping majority. Each publisher owns its own successful collection.
    """
    def __init__(self, root, replay, *, old_owner_lifetimes=None):
        from . import joining_transcript as transcript
        events=semantic.collection.read_json(root,'events.json',semantic.collection.EVENT_BYTES)
        wires=semantic.collection.read_json(root,'wire.json',semantic.collection.WIRE_BYTES)
        identities=semantic.catalog.identities(replay.states[-1]['identities'])
        rows=transcript.causal(events,wires,identities,replay.root,transfer_only=True);contents=[]
        self.transport=transcript.transfers(rows,contents=contents)
        self.acks={};self.transfers=0;self.bindings=[];blocks=phases.blocks(events,replay,old_owner_lifetimes=old_owner_lifetimes)
        for (index,node),block in blocks.items():
            lower,upper=block['APPLY_BEFORE_RETURN'],block['PUBLICATION_VALIDATED']
            local=replay.owner('applied',index,node)
            groups={}
            for name,raw in local.items():
                if name.startswith('applied-end/') and (name=='applied-end/ack.gsr' or name.endswith('-ack.gsr')):
                    value=f.decode(raw,'records','CHECKPOINT_ACK',replay.root)
                    need(value['voter']==node and replay.acks.get((value['statement'],node))==raw,'joining publication original local ACK')
                    need(value['statement'] not in groups,'joining publication duplicate local statement')
                    groups[value['statement']]={node:raw}
            for transfer in contents:
                offer,commit=transfer['offer'],transfer['commit'];request=offer['request']
                if request['sender']['node']!=node or not lower<offer['sent']<commit['delivered']<upper:continue
                raw=transfer['raw']
                if transfer['kind']!='RECORD' or len(raw)<10 or int.from_bytes(raw[8:10],'big')!=f.catalog()['records']['CHECKPOINT_ACK']['id']:continue
                value=f.decode(raw,'records','CHECKPOINT_ACK',replay.root);statement=value['statement'];peer=value['voter']
                need(statement in groups and peer==request['recipient']['node'] and peer not in groups[statement]
                     and replay.acks.get((statement,peer))==raw,'joining publication original delivered ACK')
                groups[statement][peer]=raw;self.transfers+=1
                self.bindings.append(dict(index=index,node=node,peer=peer,statement=statement,
                    sent=offer['sent'],committed=commit['delivered'],acknowledgement=sha(raw)))
            for statement,receipts in groups.items():
                semantic.catalog.majority(replay.states[index]['cut']['view'],sorted(receipts))
                self.acks[node,statement]=[receipts[n] for n in sorted(receipts)]

    def get(self,node,statement):
        need((node,statement) in self.acks,'joining publication missing collected statement')
        return self.acks[node,statement]


def anchor(replay, index):
    return dict(cut=replay.states[index]['cut'], catalog=sha(replay.catalogs[index]),
                application=replay.states[index]['application'])


def required_points(replay, files, index):
    """Original obligations, including hidden selected/source/learner endpoints."""
    _, members, packet = disk.current(files)
    selected = f.decode(members['selected.gsr'], 'records', 'SELECTED', replay.root)
    points = [anchor(replay, index-1)]
    for raw in semantic.frames(members['selected-sources.gsr']):
        basis = f.decode(raw, 'records', 'BASIS', replay.root)
        points.append(anchor(replay, basis['cut']['index']))
    if selected['cut']['index'] < index-1:
        points += [anchor(replay, selected['cut']['index']), anchor(replay, selected['cut']['index']+1)]
    for row in peers.decode(files[PEERS])['plan']['peers']:
        points += row.get('renewals', []) + row['possible']
    retained = learner.decode(files[learner.FILE])['plan']
    points += retained.get('renewals', []) + retained['possible']
    for name, raw in files.items():
        if name.startswith('sources/') and name.endswith('/source.gscp'):
            points.append(disk.anchor(disk.p.decode(raw)['capsule']))
    # The complete fixture has retired its governing floor before each slot.
    # Do not silently accept a new, uninterpreted source of obligations.
    need(not any('floor' in name for name in files), 'joining publication unhandled floor')
    unique = {}
    for point in points:
        at = point['cut']['index']
        need(0 <= at < index and point == anchor(replay, at), 'joining publication original obligation')
        unique[at] = point
    need(packet['capsule']['cut'] == replay.states[index-1]['cut'], 'joining publication original parent')
    return unique


def checkpoint_group(replay, start, end, kind, *, node=None):
    raw = f.encode('records', 'CHECKPOINT', replay.checkpoint(start, end, kind))
    receipts=getattr(replay,'publication_receipts',None)
    acknowledgements = receipts.get(node,sha(raw)) if node is not None and receipts is not None else [
        value for (statement, _), value in sorted(replay.acks.items()) if statement == sha(raw)]
    voters = [f.decode(v, 'records', 'CHECKPOINT_ACK', replay.root)['voter'] for v in acknowledgements]
    semantic.catalog.majority(replay.states[end]['cut']['view'], voters)
    return [raw, *acknowledgements]


def original_bridges(replay, members):
    groups = []
    for raw in semantic.frames(members['ancestry.gsr']) if 'ancestry.gsr' in members else ():
        if int.from_bytes(raw[8:10], 'big') == f.catalog()['records']['CHECKPOINT']['id']:
            groups.append([raw])
        else:
            need(groups, 'joining publication original ancestry framing'); groups[-1].append(raw)
    result = {}
    for group in groups:
        value = f.decode(group[0], 'records', 'CHECKPOINT', replay.root)
        start, end = value['start']['index'], value['end']['index']
        expected=f.encode('records','CHECKPOINT',replay.checkpoint(start,end,'RANGE'))
        voters=[f.decode(raw,'records','CHECKPOINT_ACK',replay.root)['voter'] for raw in group[1:]]
        try:semantic.catalog.majority(replay.states[end]['cut']['view'],voters)
        except ValueError as error:raise ValueError('joining publication original ancestry') from error
        need(start not in result and group[0]==expected and all(replay.acks.get((sha(expected),node))==raw for node,raw in zip(voters,group[1:])),
             'joining publication original ancestry')
        result[start] = group
    return result


def publication_members(replay, files, index):
    """Exact new generation members; original published files are never read."""
    _, local, packet = disk.current(files); cap = packet['capsule']
    node=f.decode(files['node.gsr'],'records','NODE',replay.root)['identity']['node']
    parts = replay.phases[index-1]; kind = replay.entries[index-1]['kind']
    membership = kind in ('INTENT', 'FINAL')
    start, _, scope = semantic.capsules.spans(replay.entries, index)[-1]
    retained = list(cap['items'])
    if not membership and retained and retained[-1]['kind'] == 'RANGE': retained.pop()
    objects = {sha(raw): raw for raw in (replay.root_bytes, replay.genesis, replay.catalogs[index])}
    for item in retained: objects.update(cross.retain_item(packet, item))
    current = checkpoint_group(replay, start, index, scope,node=node)
    objects.update({sha(raw): raw for raw in current})
    objects.update({sha(parts[k]): parts[k] for k in ('ENTRY', 'ACCEPT', 'PROOF', 'CERTIFICATE', 'PAYLOAD')})
    descriptor = None
    if membership:
        before = replay.states[index-1]
        operation = next(v for v in before['results'] if v['request']['number'] == before['active'])
        raw = f.canonical({k: operation[k] for k in ('request', 'prepared', 'receipt')})
        descriptor = sha(raw); objects[descriptor] = raw
    item = dict(kind=scope, statement=sha(current[0]), endorsements=[sha(v) for v in current[1:]],
                certificate=sha(parts['CERTIFICATE']) if membership else None, descriptor=descriptor)
    required = required_points(replay, files, index)
    renewed = sorted(at for at in required if start < at < index-1)
    labels = {f'ancestor-{ordinal}': at for ordinal, at in enumerate(renewed)}
    if start != index-1: labels['parent'] = index-1
    observed = {name.removeprefix('applied-end/').removesuffix('-statement.gsr') for name in files
                if name.startswith('applied-end/') and name.endswith('-statement.gsr')}
    need(observed == set(labels), 'joining publication required applied ancestry')
    for label, lower in labels.items():
        need(files['applied-end/'+label+'-statement.gsr'] == checkpoint_group(replay, lower, index, 'RANGE',node=node)[0],
             'joining publication exact applied ancestry')
    original = original_bridges(replay, local)
    bridges = [group for lower, group in original.items() if lower in required and lower <= start]
    # A hidden obligation at a membership boundary keeps its original stable
    # bridge. Never manufacture a new ACK across the membership transition.
    direct = {cap['cut']['index']}
    for old in cap['items']:
        value = f.decode(packet['objects'][old['statement']], 'records', 'CHECKPOINT', replay.root)
        direct.update((value['start']['index'], value['end']['index']))
    need(all(at in original for at in required if at <= start and at not in direct),
         'joining publication missing original bridge')
    bridges += [checkpoint_group(replay, lower, index, 'RANGE',node=node) for lower in labels.values()]
    for group in bridges: objects.update({sha(raw): raw for raw in group})
    selected = f.decode(parts['SELECTED'], 'records', 'SELECTED', replay.root)
    first_index = selected['cut']['index']+1
    coverage = dict(schema='gse-v53-selected-coverage/1.3' if first_index == index else 'gse-v53-round-coverage/1.3',
        selection=sha(parts['SELECTED']), parent=anchor(replay, index-1), certificate=sha(parts['CERTIFICATE']))
    if first_index < index:
        first = replay.phases[first_index-1]
        need(first['SELECTED'] == parts['SELECTED'], 'joining publication original first selection')
        coverage['first'] = dict(parent=anchor(replay, first_index-1), end=anchor(replay, first_index),
                                 certificate=sha(first['CERTIFICATE']))
        objects.update({sha(first[k]): first[k] for k in ('ENTRY', 'ACCEPT', 'PROOF', 'CERTIFICATE', 'PAYLOAD')})
    if renewed: coverage['ancestors'] = [anchor(replay, at) for at in renewed]
    new_cap = dict(cap, **anchor(replay, index), items=retained+[item])
    members = {k: local[k] for k in ('promise.gsr', 'basis.gsr', 'selected.gsr', 'selected-sources.gsr')}
    members.update({'source.gscp': disk.packet_bytes(new_cap, objects, {sha(replay.image): len(replay.image)}),
                    disk.COVERAGE: f.canonical(coverage), sha(replay.image)+'.image': replay.image})
    if bridges: members['ancestry.gsr'] = b''.join(raw for group in bridges for raw in group)
    return new_cap, members


def promoted_ledgers(replay, files, index):
    parts = replay.phases[index-1]
    voters = [v['voter'] for v in f.decode(parts['CERTIFICATE'], 'records', 'CERTIFICATE')['proofs']]
    parent, upper = anchor(replay, index-1), anchor(replay, index)
    local = disk.current(files)[1]
    originals = {k: files['applied-end/'+k] for k in ('selector.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr', 'ack.gsr')}
    originals.update({k: local[k] for k in ('promise.gsr', 'selected.gsr')})
    originals.update({k.lower()+'.gsr': parts[k] for k in ('ENTRY', 'ACCEPT', 'PROOF')})
    future = files[phases.future.FILE]; meta = phases.empty_future(future, files); targets = []
    state = peers.decode(files[PEERS]); plan = copy.deepcopy(state['plan'])
    need(state['root'] == replay.root and state['owner'] == phases.future.identity(files),
         'joining publication peer owner')
    identities = semantic.catalog.identities(replay.states[index]['identities'])
    for node in voters:
        if node == 'node-1': continue
        identity = identities[node]
        targets.append(dict(identity=identity, lower=parent))
        meta = dict(meta, revision=meta['revision']+1, previous=sha(future), parent=parent, peers=list(targets))
        future = phases.future.frame(meta, originals)
        row = next(v for v in plan['peers'] if v['identity'] == identity)
        need(row['possible'] == [parent], 'joining publication original dispatch endpoint')
        row['possible'].append(upper)
    meta = dict(meta, revision=meta['revision']+1, previous=sha(future), parent=None, peers=[])
    return {PEERS: peers.frame(dict(state, revision=state['revision']+1, previous=sha(files[PEERS]), plan=plan)),
            phases.future.FILE: phases.future.frame(meta, {})}


def expected_publication(replay, files, index, node):
    cap, members = publication_members(replay, files, index)
    previous = f.decode(files['selector.gsr'], 'records', 'SELECTOR', replay.root)['generation']
    need(previous in ('a', 'b'), 'joining publication previous generation')
    slot = 'b' if previous == 'a' else 'a'
    need(not any(name == 'generations/'+slot or name.startswith('generations/'+slot+'/') for name in files),
         'joining publication inactive slot not retired')
    selector, generation = disk.generation(members, cap, node, slot, None)
    expected = {name: raw for name, raw in files.items() if name != 'applied-end' and not name.startswith('applied-end/')}
    expected.update(generation); expected.update(promoted_ledgers(replay, files, index))
    expected.update({'selector.gsr': selector, 'pending.accept': disk.EMPTY})
    return expected


def validate(root, *, size=3, kind='ADD'):
    root = Path(root); inventory = semantic.collection.inventory(root)
    original = semantic.validate(root,size=size,kind=kind); replay = semantic.Replay(root,size=size,kind=kind)
    for index in range(1, original['slots']+1): replay.step(index)
    replay.publication_receipts=CheckpointReceipts(root,replay)
    publications = byte_count = 0
    for index, parts in enumerate(replay.phases, 1):
        voters = [v['voter'] for v in f.decode(parts['CERTIFICATE'], 'records', 'CERTIFICATE')['proofs']]
        for node in voters:
            expected = expected_publication(replay, replay.owner('applied', index, node), index, node)
            need(replay.owner('published', index, node) == expected, 'joining exact publication inventory')
            publications += 1; byte_count += sum(len(v) for v in expected.values() if v is not None)
    need(semantic.collection.inventory(root) == inventory, 'joining original changed during publication replay')
    return dict(status='PASS', scope='native-'+kind+'-applied-to-published-inventories', profile=str(size)+'-'+kind, slots=original['slots'],
        publications=publications, comparedBytes=byte_count, collectedCheckpointTransfers=replay.publication_receipts.transfers,
        publicationPhysicalQualified=True,
        completePhysicalQualified=False, forceAndNetworkQualified=False, processDeathQualified=False, phase3Complete=False)


NEGATIVES = {name: 'joining exact publication inventory' for name in (
    'extra-packet-object', 'missing-current-proof-object', 'missing-first-proof-object',
    'coverage-first-parent', 'coverage-selection', 'coverage-ancestor-omitted',
    'membership-ancestry-lost', 'manifest-promise', 'manifest-owned-tail', 'selected-bytes-changed',
    'old-generation-lost', 'old-generation-changed', 'source-changed', 'grant-changed',
    'pending-not-retired', 'applied-end-not-retired', 'orphan-generation-file',
    'peer-revision', 'peer-predecessor', 'peer-possible', 'peer-view-promoted-early',
    'learner-ledger-changed', 'future-predecessor', 'joining-owner-coverage')}
NEGATIVES.update({'required-applied-ancestor-missing': 'joining publication required applied ancestry',
                  'applied-ancestor-order': 'joining publication exact applied ancestry'})


def mutate(root, name):
    """Self-consistent mutations: all still pass the earlier semantic gate."""
    need(name in NEGATIVES, 'unknown joining publication mutation')
    if name in ('required-applied-ancestor-missing', 'applied-ancestor-order'):
        for node in ('node-1', 'node-2'):
            directory = root/'applied-8'/node/'applied-end'
            for suffix in ('statement.gsr', 'ack.gsr'):
                first, second = [directory/f'ancestor-{i}-{suffix}' for i in (0, 1)]
                if name == 'required-applied-ancestor-missing': first.unlink()
                else:
                    a, b = first.read_bytes(), second.read_bytes(); first.write_bytes(b); second.write_bytes(a)
            plan = semantic.catalog.parse((directory/'plan.json').read_bytes())
            plan['files'] = [dict(path=p.name, bytes=p.stat().st_size, sha256=sha(p.read_bytes()))
                             for p in sorted(directory.iterdir()) if p.name != 'plan.json']
            (directory/'plan.json').write_bytes(f.canonical(plan))
        return
    slot = 9 if name == 'peer-view-promoted-early' or name == 'membership-ancestry-lost' else 8 if name in (
        'missing-first-proof-object', 'coverage-first-parent', 'coverage-ancestor-omitted') else 11
    directory = root / f'published-{slot}/node-2'
    if name == 'joining-owner-coverage': directory = root / 'joining-published-11/replica'
    files = disk.inventory(directory); prefix, members, packet = disk.current(files)
    node = f.decode(files['node.gsr'], 'records', 'NODE')['identity']['node']
    generation = prefix.split('/')[1]; members = dict(members)
    if name in ('extra-packet-object', 'missing-current-proof-object', 'missing-first-proof-object'):
        objects = dict(packet['objects'])
        if name == 'extra-packet-object': objects[sha(b'unreferenced')] = b'unreferenced'
        else:
            parts, _ = disk.pending(disk.inventory(root / f'applied-{7 if name == "missing-first-proof-object" else slot}/node-2')['pending.accept'],
                                    ('PROOF', 'CERTIFICATE'))
            objects.pop(sha(parts['CERTIFICATE']))
        members['source.gscp'] = disk.packet_bytes(packet['capsule'], objects, packet['images'])
    elif name in ('coverage-first-parent', 'coverage-selection', 'coverage-ancestor-omitted', 'joining-owner-coverage'):
        coverage = semantic.catalog.parse(members[disk.COVERAGE])
        if name == 'coverage-first-parent': coverage['first']['parent'] = coverage['parent']
        elif name == 'coverage-ancestor-omitted': coverage['ancestors'].pop(0)
        else: coverage['selection'] = '0'*64
        members[disk.COVERAGE] = f.canonical(coverage)
    elif name == 'membership-ancestry-lost':
        members.pop('ancestry.gsr'); (directory/prefix/'ancestry.gsr').unlink()
    elif name == 'selected-bytes-changed':
        value = f.decode(members['selected.gsr'], 'records', 'SELECTED')
        value['ballot']['counter'] += 1; members['selected.gsr'] = f.encode('records', 'SELECTED', value)
    elif name.startswith('manifest-'):
        manifest = f.decode(files[prefix+'generation.gsr'], 'records', 'GENERATION')
        manifest['promise' if name == 'manifest-promise' else 'ownedTail'] = '0'*64
        raw = f.encode('records', 'GENERATION', manifest)
        (directory/prefix/'generation.gsr').write_bytes(raw)
        selector = f.decode(files['selector.gsr'], 'records', 'SELECTOR'); selector['digest'] = sha(raw)
        (directory/'selector.gsr').write_bytes(f.encode('records', 'SELECTOR', selector)); return
    elif name.startswith('old-generation-'):
        old = directory/'generations'/('b' if generation == 'a' else 'a')
        if name.endswith('lost'): shutil.rmtree(old)
        else: (old/'basis.gsr').write_bytes(b'changed original basis')
        return
    elif name == 'source-changed': next((directory/'sources').glob('*/source.gscp')).write_bytes(b'changed source'); return
    elif name == 'grant-changed': (directory/'grants.gsr').write_bytes(b'changed grant'); return
    elif name == 'pending-not-retired':
        (directory/'pending.accept').write_bytes((root/f'applied-{slot}/node-2/pending.accept').read_bytes()); return
    elif name == 'applied-end-not-retired':
        shutil.copytree(root/f'applied-{slot}/node-2/applied-end', directory/'applied-end'); return
    elif name == 'orphan-generation-file': (directory/'generations/unowned').write_bytes(b'orphan'); return
    elif name.startswith('peer-'):
        value = peers.decode(files[PEERS])
        if name == 'peer-revision': value['revision'] += 1
        elif name == 'peer-predecessor': value['previous'] = '0'*64
        elif name == 'peer-possible': next(v for v in value['plan']['peers'] if v['identity']['node'] == 'node-2')['possible'].pop()
        else:
            value['plan']['view'] = packet['capsule']['cut']['view']
            # A self-consistent plan upgrade still does not belong to publication.
            identity = next(v for v in f.decode(packet['objects'][packet['capsule']['catalog']], 'records', 'CATALOG')['identities'] if v['node'] == 'node-4')
            value['plan']['peers'].append(dict(identity=identity, possible=[disk.anchor(packet['capsule'])]))
        (directory/PEERS).write_bytes(peers.frame(value)); return
    elif name == 'learner-ledger-changed':
        value = learner.decode(files[learner.FILE]); value['revision'] += 1
        (directory/learner.FILE).write_bytes(learner.frame(value)); return
    elif name == 'future-predecessor':
        value = phases.empty_future(files[phases.future.FILE], files); value['previous'] = '0'*64
        (directory/phases.future.FILE).write_bytes(phases.future.frame(value, {})); return
    selector, generated = disk.generation(members, disk.p.decode(members['source.gscp'])['capsule'], node, generation, None)
    for filename, raw in generated.items():
        if raw is not None: (directory/filename).write_bytes(raw)
    (directory/'selector.gsr').write_bytes(selector)
    if name == 'joining-owner-coverage':
        # Refresh the copied inventory too: rejection must come from the new
        # physical oracle, not an incidental stale envelope hash.
        inventory = directory.parent/'inventory.json'; rows = semantic.catalog.parse(inventory.read_bytes())
        for row in next(v for v in rows if v['name'] == 'replica')['files']:
            if 'directory' in row['identity']: continue
            raw = (directory/row['name']).read_bytes(); row['identity'].update(size=len(raw), sha256=sha(raw))
        inventory.write_bytes(f.canonical(rows))


def qualify(root):
    root = Path(root); original = validate(root); results = []
    for name, reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-joining-publication-negative-') as temp:
            changed = Path(temp)/'raw'; shutil.copytree(root, changed); mutate(changed, name)
            semantic.validate(changed)  # Demonstrate the new check, not an earlier incidental rejection.
            try: validate(changed)
            except ValueError as error:
                need(str(error) == reason, 'joining unrelated publication negative: '+name+': '+str(error))
            else: raise ValueError('joining publication mutation accepted: '+name)
        results.append(dict(case=name, status='REJECTED', reason=reason, semanticGate='PASS'))
    return dict(original=original, negatives=results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--qualify', action='store_true'); args = parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root), sort_keys=True))
