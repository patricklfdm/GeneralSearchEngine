"""Reconstruct original old-voter storage from bootstrap through native INTENT.

Publication is composed with fresh grants, frozen source capture, selected ledger
merge and maintenance. The joining owner's custody and later joint activation
remain separate physical gates; no receipt supplies authority for those paths.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import tempfile

from . import joining_publication_evidence as publication
from . import joining_confirmation_evidence as confirmation
from . import peer_observation_evidence as observation
from . import selected_retention_evidence as selected
from . import selected_prefix_evidence as reachable

s = publication.semantic
f, need, sha, disk = s.f, s.need, s.sha, s.disk
PEERS, learner, future = publication.PEERS, publication.learner, publication.phases.future
VOTERS = ('node-1', 'node-2')


def require_coverage(files):
    """Original complete copies must cover every retained obligation."""
    _, members, packet = disk.current(files)
    peer = publication.peers.decode(files[PEERS])['plan']
    retained = learner.decode(files[learner.FILE])['plan']
    confirmation.bind_endpoints(packet, members.get('ancestry.gsr', b''), peer, retained)
    return confirmation.endpoints(packet, members.get('ancestry.gsr', b''))


def maintenance(group):
    """Project observed copies and only superseded, covered local sources."""
    result = copy.deepcopy(group)
    for node in VOTERS:
        files = result[node]; prefix, members, _ = disk.current(group[node])
        need(files['pending.accept'] == disk.EMPTY and not any(name == 'applied-end' or name.startswith('applied-end/') for name in files),
             'joining transition maintenance requires completed publication')
        publication.phases.empty_future(files[future.FILE], files)
        # Copies are the preceding independently derived publications/installs,
        # not manifests accepted merely because their checksums agree.
        for peer in (node, next(n for n in VOTERS if n != node)):
            files[PEERS] = observation.observe_same_cut(files[PEERS], group[node], group[peer], defer_renewal=True)
        available = require_coverage(files)
        files = {name: raw for name, raw in files.items() if not name.startswith('generations/')
                 or name == prefix[:-1] or name.startswith(prefix)}
        active = f.decode(members['basis.gsr'], 'records', 'BASIS')['basisId']
        retired = set()
        for name, raw in list(files.items()):
            if name.startswith('sources/') and name.endswith('/source.gscp'):
                identifier = name.split('/')[1]
                if identifier == active: continue
                point = disk.anchor(disk.p.decode(raw)['capsule'])
                need(available.get(point['cut']['index']) == point, 'joining transition source retirement coverage')
                retired.add(identifier)
        if retired:
            files = {name: raw for name, raw in files.items() if not (name.startswith('sources/') and name.split('/')[1] in retired)}
            rows = disk.journal(files['grants.gsr'], future.initial(files)['root'], node)
            # In this history no accepted tail or still-owned older basis remains.
            kept = rows[-3:]
            need([kind for kind, _, _ in kept] == ['PROMISE', 'BASIS', 'SELECTED'] and
                 kept[0][2]['basisId'] == kept[1][2]['basisId'] == active and
                 kept[2][1] == members['selected.gsr'], 'joining transition retained grant suffix')
            files['grants.gsr'] = b''.join(raw for _, raw, _ in kept)
        result[node] = files
    return result


def applied_end(replay, files, index, node):
    parts = replay.phases[index-1]
    start, _, scope = s.capsules.spans(replay.entries, index)[-1]
    statement = f.encode('records', 'CHECKPOINT', replay.checkpoint(start, index, scope))
    identity = s.catalog.identities(replay.states[index]['identities'])[node]
    def acknowledgement(raw):
        return f.encode('records', 'CHECKPOINT_ACK', dict(root=replay.root, voter=node,
            incarnation=identity['storage'], cut=replay.states[index]['cut'], statement=sha(raw)))
    end = dict(zip(('selector.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr', 'application.image', 'ack.gsr'),
        (files['selector.gsr'], parts['CERTIFICATE'], replay.catalogs[index], statement, replay.image, acknowledgement(statement))))
    required = publication.required_points(replay, files, index)
    labels = {f'ancestor-{ordinal}': at for ordinal, at in enumerate(sorted(at for at in required if start < at < index-1))}
    if start != index-1: labels['parent'] = index-1
    for label, at in labels.items():
        raw = f.encode('records', 'CHECKPOINT', replay.checkpoint(at, index, 'RANGE'))
        end[label+'-statement.gsr'] = raw; end[label+'-ack.gsr'] = acknowledgement(raw)
    end['plan.json'] = f.canonical(dict(schema='gse-v53-applied-end/1.3', root=replay.root, node=node,
        files=[dict(path=name, bytes=len(raw), sha256=sha(raw)) for name, raw in sorted(end.items())]))
    return {'applied-end': None, **{'applied-end/'+name: raw for name, raw in end.items()}}


class History:
    def __init__(self, root, replay):
        self.root, self.replay = Path(root), replay
        self.group = learner.initialize(selected.initialize(replay.original))
        self.group = {n: dict(files, **{future.FILE: future.frame(future.initial(files), {})}) for n, files in self.group.items()}
        self.comparisons = 0; self.expected = {}; self.label = None
        self.match('before-network', self.group)

    def match(self, label, group):
        self.expected, self.label = copy.deepcopy(group), label
        for node, files in group.items():
            need(disk.inventory(self.root/label/node) == files, 'joining exact transition inventory: '+label+': '+node)
            self.comparisons += 1

    def prepared(self, node, files):
        """Optional whole-history comparison of the independently derived grant."""

    def campaign(self, ordinal):
        if ordinal > 1: self.group = maintenance(self.group)
        group = {n: self.group[n] for n in VOTERS}
        current = disk.current(group['node-1'])[2]
        for files in group.values(): require_coverage(files)
        identities = s.catalog.identities(self.replay.states[current['capsule']['cut']['index']]['identities'])
        def merged(before, originals):
            state = publication.peers.decode(before)
            plans = [publication.peers.decode(raw)['plan'] for raw in [before, *originals]]
            points = [a for files in group.values() for a in learner.decode(files[learner.FILE])['plan']['possible']]
            plan = confirmation.merge(plans, current, identities, points)
            return before if state['plan'] == plan else publication.peers.frame(dict(state,
                revision=state['revision']+1, previous=sha(before), plan=plan))
        label = 'installed' if ordinal == 1 else 'installed-'+str(ordinal)
        ancestry = {n: disk.current(files)[1].get('ancestry.gsr', b'') for n, files in group.items()}
        prepared, _, installed = selected.campaign(self.root, group, ordinal+1, label,
            selected_prefix=reachable.prefix, merge_ledgers=merged, retained_ancestry=ancestry)
        for node, files in prepared.items(): self.prepared(node, files)
        self.group.update(installed); self.match(label, self.group)

    def offer(self):
        state = self.replay.states[disk.current(self.group['node-1'])[2]['capsule']['cut']['index']]
        request = next(v['request'] for v in state['results'] if v['request']['number'] == state['active'])
        joining = s.catalog.identities(state['identities'])['node-4']
        for node in VOTERS: self.group[node] = learner.offer(self.group[node], request, joining)

    def slot(self, index):
        self.group = maintenance(self.group)
        applied = copy.deepcopy(self.group); parts = self.replay.phases[index-1]
        for node in VOTERS:
            files = applied[node]; _, members, _ = disk.current(files)
            local = dict(parts, SELECTOR=files['selector.gsr'], PROMISE=members['promise.gsr'], SELECTED=members['selected.gsr'])
            files['pending.accept'] = s.packed_phases(local)
            files.update(applied_end(self.replay, files, index, node))
            publication.publication_members(self.replay, files, index)
        self.match('applied-'+str(index), applied)
        self.group = {node: publication.expected_publication(self.replay, files, index, node) if node in VOTERS else files
                      for node, files in applied.items()}
        self.match('published-'+str(index), self.group)

    def run(self):
        for ordinal in range(1, 5):
            if ordinal == 3: self.offer()
            self.campaign(ordinal)
            self.slot(2*ordinal-1); self.slot(2*ordinal)
        self.offer(); self.slot(9)
        return dict(status='PASS', scope='native-ADD-bootstrap-through-old-voter-INTENT', slots=9,
            campaigns=4, ownerSnapshotComparisons=self.comparisons, throughIntentPhysicalQualified=True,
            completePhysicalQualified=False, forceAndNetworkQualified=False, processDeathQualified=False, phase3Complete=False)


def validate(root):
    root = Path(root); original = s.collection.inventory(root)
    publication.validate(root)
    replay = s.Replay(root)
    for index in range(1, 12): replay.step(index)
    result = History(root, replay).run()
    need(s.collection.inventory(root) == original, 'joining original changed during transition replay')
    return result


NEGATIVES = {
    'installed-extra-member': 'joining exact transition inventory: installed-3: node-2',
    'installed-selection-changed': 'joining exact transition inventory: installed-3: node-2',
    'installed-source-changed': 'joining exact transition inventory: installed-2: node-2',
    'installed-old-generation-lost': 'joining exact transition inventory: installed-2: node-2',
    'installed-peer-debt-erased': 'joining exact transition inventory: installed-2: node-2',
    'installed-learner-offer-erased': 'joining exact transition inventory: installed-3: node-2',
    'installed-future-revision': 'joining exact transition inventory: installed-2: node-2',
    'installed-allocator': 'joining exact transition inventory: installed-4: node-1',
    'installed-grants-truncated': 'selected retention original grant history',
    'installed-offline-owner-changed': 'joining exact transition inventory: installed-4: node-3',
    'applied-peer-revision': 'joining exact transition inventory: applied-6: node-2',
    'applied-peer-debt-erased': 'joining exact transition inventory: applied-6: node-2',
    'applied-learner-obligation-erased': 'joining exact transition inventory: applied-9: node-2',
    'source-retirement-skipped': 'joining exact transition inventory: applied-3: node-2',
    'grant-retirement-skipped': 'joining exact transition inventory: applied-3: node-2',
    'applied-orphan-directory': 'joining exact transition inventory: applied-5: node-2',
    'applied-allocator': 'joining exact transition inventory: applied-8: node-1',
}


def write_inventory(directory, files):
    """Only disposable mutation copies call this writer."""
    shutil.rmtree(directory); directory.mkdir()
    for name, raw in sorted(files.items()):
        path = directory/name
        if raw is None: path.mkdir(parents=True, exist_ok=True)
        else: path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)


def mutate(root, name):
    need(name in NEGATIVES, 'unknown joining transition mutation')
    if name.startswith('installed-'):
        ordinal = 3 if name in ('installed-extra-member','installed-selection-changed','installed-learner-offer-erased') else (
            4 if name in ('installed-allocator','installed-offline-owner-changed') else 2)
        node = 'node-1' if name == 'installed-allocator' else 'node-3' if name == 'installed-offline-owner-changed' else 'node-2'
        directory = root/f'installed-{ordinal}'/node; files = disk.inventory(directory)
        prefix, members, packet = disk.current(files)
        if name in ('installed-extra-member','installed-selection-changed'):
            members = dict(members)
            if name == 'installed-extra-member': members['unreferenced.bin'] = b'forged'
            else:
                value = f.decode(members['selected.gsr'], 'records', 'SELECTED'); value['ballot']['counter'] += 1
                members['selected.gsr'] = f.encode('records', 'SELECTED', value)
            selector, generated = disk.generation(members, packet['capsule'], node, prefix.split('/')[1], None)
            files.update(generated); files['selector.gsr'] = selector
        elif name == 'installed-source-changed':
            basis = f.decode(members['basis.gsr'], 'records', 'BASIS'); key = 'sources/'+basis['basisId']+'/source.gscp'
            source = disk.p.decode(files[key]); objects = dict(source['objects']); objects[sha(b'forged')] = b'forged'
            files[key] = disk.packet_bytes(source['capsule'], objects, source['images'])
        elif name == 'installed-old-generation-lost':
            files = {k:v for k,v in files.items() if not k.startswith('generations/') or k == prefix[:-1] or k.startswith(prefix)}
        elif name == 'installed-peer-debt-erased':
            state = publication.peers.decode(files[PEERS]); state['plan']['peers'][2]['possible'] = [disk.anchor(packet['capsule'])]
            files[PEERS] = publication.peers.frame(state)
        elif name == 'installed-learner-offer-erased': files[learner.FILE] = (root/'before-network'/node/learner.FILE).read_bytes()
        elif name == 'installed-future-revision':
            state = publication.phases.empty_future(files[future.FILE], files); state['revision'] += 1
            files[future.FILE] = future.frame(state, {})
        elif name == 'installed-allocator':
            value = f.decode(files['allocator.gsr'], 'records', 'ALLOCATOR'); value['counter'] += 1
            files['allocator.gsr'] = f.encode('records','ALLOCATOR',value)
        elif name == 'installed-grants-truncated':
            rows = disk.journal(files['grants.gsr'], packet['capsule']['root'], node)
            files['grants.gsr'] = b''.join(raw for _,raw,_ in rows[-3:])
        else: files['pending.accept'] = b'forged offline write'
        write_inventory(directory, files); return
    index = 6 if name in ('applied-peer-revision','applied-peer-debt-erased') else 9 if name == 'applied-learner-obligation-erased' else (
        3 if name in ('source-retirement-skipped','grant-retirement-skipped') else 5 if name == 'applied-orphan-directory' else 8)
    node = 'node-1' if name == 'applied-allocator' else 'node-2'
    directory = root/f'applied-{index}'/node; files = disk.inventory(directory)
    if name in ('applied-peer-revision','applied-peer-debt-erased'):
        state = publication.peers.decode(files[PEERS])
        if name == 'applied-peer-revision': state['revision'] += 1
        else: state['plan']['peers'][0].pop('renewals')
        files[PEERS] = publication.peers.frame(state)
    elif name == 'applied-learner-obligation-erased':
        state = learner.decode(files[learner.FILE]); state['plan']['possible'].pop(0)
        files[learner.FILE] = learner.frame(state)
    elif name in ('source-retirement-skipped','grant-retirement-skipped'):
        installed = disk.inventory(root/'installed-2'/node)
        if name == 'source-retirement-skipped': files.update({k:v for k,v in installed.items() if k.startswith('sources/')})
        else: files['grants.gsr'] = installed['grants.gsr']
    elif name == 'applied-orphan-directory': files['unowned-source'] = None
    else:
        value = f.decode(files['allocator.gsr'], 'records', 'ALLOCATOR'); value['counter'] += 1
        files['allocator.gsr'] = f.encode('records','ALLOCATOR',value)
    # Recompute a fully matching published successor. The previous gate takes
    # this applied state as its input; only the new history rejects its origin.
    replay = s.Replay(root)
    for at in range(1,12): replay.step(at)
    successor = publication.expected_publication(replay, files, index, node)
    write_inventory(directory, files); write_inventory(root/f'published-{index}'/node, successor)


def qualify(root):
    root = Path(root); original = validate(root); results = []
    for name, reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-joining-transition-negative-') as temp:
            changed = Path(temp)/'raw'; shutil.copytree(root, changed); mutate(changed, name)
            publication.validate(changed)
            try: validate(changed)
            except ValueError as error: need(str(error) == reason, 'joining unrelated transition negative: '+name+': '+str(error))
            else: raise ValueError('joining transition mutation accepted: '+name)
        results.append(dict(case=name, status='REJECTED', reason=reason, publicationGate='PASS'))
    return dict(original=original, negatives=results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--qualify', action='store_true'); args = parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root), sort_keys=True))
