"""Replay the complete native ADD catalog/certificate/checkpoint chain.

Start at the independently derived public bootstrap. Check every actual applied
vote and resulting catalog before consuming published capsules or joining ACKs.
This is the semantic chain gate, not complete force/network, reclamation or
process-death qualification. No producer PASS field supplies authority.
"""
import argparse
import base64
import copy
import json
from pathlib import Path
import re
import shutil
import struct
import tempfile

from . import bootstrap_publication_evidence as bootstrap
from . import carried_publication_evidence as disk
from . import context_evidence as catalog
from . import capsule_evidence as capsules
from . import joining_snapshot as joining
from . import joining_history_run as collection
from . import bootstrap_revalidation_evidence as images
from . import bootstrap_replay_contract as source_policy
from .ancestry_pruning_evidence import frames

f, need, sha = catalog.f, catalog.need, catalog.sha
CONTROLS = ('RESERVE', 'PREPARE', 'READY', 'SEAL', 'INTENT', 'FINAL')


def phased_certificate(raw, parent, identities, root):
    """Check actual phased bytes and both governing majorities independently."""
    parts, values = disk.pending(raw, ('PROOF', 'CERTIFICATE'))
    entry, accepted, proof, cert = [values[k] for k in ('ENTRY', 'ACCEPT', 'PROOF', 'CERTIFICATE')]
    view = parent['cut']['view']; authority = catalog.authority(root, view)
    eligible = set(view['old']) | set(view['new'])
    ballot = entry['origin']
    need(ballot['proposer'] in eligible and ballot['incarnation'] == identities[ballot['proposer']]['storage'] and
         0 < ballot['counter'] < 2**63-1, 'joining original ballot identity')
    need(entry['root'] == root and entry['authority'] == authority and
         entry['index'] == parent['cut']['index'] + 1 and entry['previous'] == parent['cut']['entry'],
         'joining original governing entry')
    want = dict(root=root, authority=authority, ballot=ballot, index=entry['index'], entry=sha(parts['ENTRY']))
    need(accepted == want and proof == dict(want, accepts=cert['accepts']) and
         cert == dict(proof, proofs=cert['proofs']), 'joining distinct original phases')
    for phase, key in (('ACCEPT', 'accepts'), ('PROOF', 'proofs')):
        names = [v['voter'] for v in cert[key]]; catalog.majority(view, names)
        for witness in cert[key]:
            node = witness['voter']; identity = identities[node]
            need(witness == dict(voter=node, incarnation=identity['storage'], receipt=catalog.digest(dict(
                 root=root, voter=node, incarnation=identity['storage'], phase=phase, record=sha(parts[phase])))),
                 'joining original phased receipt')
    # This whole fixture has one selected fixed set; it does not exercise split
    # ACCEPT/PROOF sets or a carried earlier-ballot entry.
    need([v['voter'] for v in cert['accepts']] == [v['voter'] for v in cert['proofs']], 'joining fixed phase owners')
    selected = values['SELECTED']
    need(selected['root'] == root and selected['view'] == authority and selected['ballot'] == ballot and
         selected['nextEntry'] is None and selected['cut']['index'] <= parent['cut']['index'], 'joining original selection')
    need([v['voter'] for v in selected['sources']] == [v['voter'] for v in cert['accepts']], 'joining selected phase owners')
    return parts, values


def target_nodes(size, kind, required_four=False):
    """Explicit test contract, never inferred from a producer profile label."""
    need(type(required_four) is bool and (not required_four or (size, kind) == (5, 'REPLACE')),
         'joining required-four profile')
    old = ['node-' + str(i) for i in range(1, size+1)]
    departing = 'node-3' if required_four else old[-1]
    return [n for n in old if kind == 'ADD' or n != departing] + ['node-' + str(size+1)]


def applied_voter(before, after, kind, node, end):
    """A governing FINAL voter may cease to be an end-checkpoint voter."""
    voting = node in set(after['cut']['view']['old']) | set(after['cut']['view']['new'])
    need(voting or (kind == 'FINAL' and node in before['cut']['view']['old'] and
                    node not in before['cut']['view']['new']), 'joining nonvoting FINAL owner')
    need(('ack.gsr' in end) == voting, 'joining applied end voting eligibility')
    need(voting or not any(n.endswith('-ack.gsr') or n.endswith('-statement.gsr') for n in end),
         'joining departing ancestor endorsement')
    return voting


class Replay:
    def __init__(self, root, *, size=3, kind='ADD', required_four=False, bootstrap_source='EMPTY'):
        need((size,kind) in ((3,'ADD'),(4,'ADD'),(3,'REPLACE'),(4,'REPLACE'),(5,'REPLACE')), 'joining replay profile')
        # The caller declares its source contract; do not infer authority from
        # a producer's plan or receipt. Existing cohort entries still require EMPTY.
        self.bootstrap_source = source_policy.check(bootstrap_source)
        self.size, self.kind = size, kind
        self.joining = 'node-' + str(size+1)
        self.old = tuple('node-' + str(i) for i in range(1,size+1))
        self.offline = self.old[size//2+1:]
        self.targets = target_nodes(size, kind, required_four)
        self.path = Path(root); self.original = bootstrap.original(self.path, size, bootstrap_source=='VERIFIED_DURABLE_BACKUP')
        _, members, packet = disk.current(self.original['node-1'])
        self.root = packet['capsule']['root']; self.root_bytes = self.original['node-1']['root.gsr']
        self.genesis = self.original['node-1']['genesis.gsr']
        self.image = members[packet['capsule']['application'] + '.image']
        self.states = [f.decode(packet['objects'][packet['capsule']['catalog']], 'records', 'CATALOG', self.root)]
        self.catalogs = [packet['objects'][packet['capsule']['catalog']]]
        self.entries, self.phases, self.acks = [], [], {}
        self.selections = {}; self.sources = {}; self.snapshots = {}; self.placed = None
        self.nonvoting = set()

    def placed_snapshot(self):
        if self.placed is None: self.placed = joining.read(self.path / 'joining-originals-placed', stage='placed')
        return self.placed

    def owner(self, phase, index, node):
        key = phase, index, node
        if key not in self.snapshots:
            if node == self.joining:
                path = self.path / f'joining-{phase}-{index}'
                joining.read(path); path /= 'replica'
            else:
                need(node in self.old, 'joining observed phase owner')
                path = self.path / f'{phase}-{index}' / node
            self.snapshots[key] = disk.inventory(path)
        return self.snapshots[key]

    def checkpoint(self, start, end, kind):
        before, after = self.states[start], self.states[end]
        return dict(root=self.root, scope=kind, start=before['cut'], end=after['cut'],
                    catalogBefore=sha(self.catalogs[start]), catalogAfter=sha(self.catalogs[end]),
                    applicationBefore=before['application'], applicationAfter=after['application'])

    def ack(self, statement, node, raw):
        value = f.decode(statement, 'records', 'CHECKPOINT', self.root)
        state = self.states[value['end']['index']]; registry = catalog.identities(state['identities'])
        need(node in set(state['cut']['view']['old']) | set(state['cut']['view']['new']), 'joining ACK eligible end')
        expected = f.encode('records', 'CHECKPOINT_ACK', dict(root=self.root, voter=node,
            incarnation=registry[node]['storage'], cut=state['cut'], statement=sha(statement)))
        need(raw == expected, 'joining original checkpoint ACK')
        key = sha(statement), node
        need(key not in self.acks or self.acks[key] == raw, 'joining conflicting checkpoint observation')
        self.acks[key] = raw

    def packet(self, packet, through):
        cap, objects = packet['capsule'], packet['objects']; state = self.states[through]
        need(cap['root'] == self.root and cap['initial'] == sha(self.genesis) and cap['cut'] == state['cut'] and
             cap['catalog'] == sha(self.catalogs[through]) and cap['application'] == sha(self.image) and
             objects.get(sha(self.root_bytes)) == self.root_bytes and objects.get(sha(self.genesis)) == self.genesis and
             objects[cap['catalog']] == self.catalogs[through] and packet['images'] == {sha(self.image): len(self.image)},
             'joining derived capsule endpoints')
        intervals = capsules.spans(self.entries, through)
        need(len(cap['items']) == len(intervals), 'joining capsule membership coverage')
        for item, (start, end, kind) in zip(cap['items'], intervals):
            statement = f.encode('records', 'CHECKPOINT', self.checkpoint(start, end, kind))
            need(item['kind'] == kind and item['statement'] == sha(statement) and objects.get(sha(statement)) == statement,
                 'joining exact capsule checkpoint')
            voters = []
            for h in item['endorsements']:
                raw = objects[h]; value = f.decode(raw, 'records', 'CHECKPOINT_ACK', self.root); node = value['voter']
                need(self.acks.get((sha(statement), node)) == raw, 'joining checkpoint lacks original applied ACK')
                voters.append(node)
            catalog.majority(self.states[end]['cut']['view'], voters)
            if kind == 'RANGE':
                need(item['certificate'] is None and item['descriptor'] is None, 'joining hidden membership proof')
            else:
                phase = self.phases[end-1]
                need(item['certificate'] == sha(phase['CERTIFICATE']), 'joining original membership certificate')
                for name in ('ENTRY', 'ACCEPT', 'PROOF', 'CERTIFICATE', 'PAYLOAD'):
                    need(objects.get(sha(phase[name])) == phase[name], 'joining original membership phase bytes')
                prior = self.states[start]
                row = next(v for v in prior['results'] if v['request']['number'] == prior['active'])
                descriptor = f.canonical({k: row[k] for k in ('request', 'prepared', 'receipt')})
                need(item['descriptor'] == sha(descriptor) and objects.get(sha(descriptor)) == descriptor,
                     'joining original sealed descriptor')

    def selected(self, files, members, parts, values, node, before):
        selected = values['SELECTED']; cut = selected['cut']['index']
        need(cut < len(self.states) and selected['cut'] == self.states[cut]['cut'], 'joining selected original cut')
        need(parts['SELECTOR'] == files['selector.gsr'] and parts['PROMISE'] == members['promise.gsr'] and
             parts['SELECTED'] == members['selected.gsr'], 'joining local selected phase binding')
        original_bases = frames(members['selected-sources.gsr'])
        need(len(original_bases) == len(selected['sources']), 'joining complete selected bases')
        source_cuts = []
        for raw, row in zip(original_bases, selected['sources']):
            basis = f.decode(raw, 'records', 'BASIS', self.root)
            at = basis['cut']['index']
            need(row == dict(voter=basis['voter'], basisId=basis['basisId'], basisDigest=sha(raw)) and
                 basis['ballot'] == selected['ballot'] and basis['view'] == selected['view'] and
                 basis['accepted'] is None and 0 <= at < len(self.states) and basis['cut'] == self.states[at]['cut'],
                 'joining selected original basis')
            source_cuts.append(at)
            if basis['voter'] == node:
                source = files['sources/' + basis['basisId'] + '/source.gscp']
                packet = disk.p.decode(source); disk.p.bind(packet, raw); self.packet(packet, at)
                promise = {k: basis[k] for k in ('root', 'view', 'ballot', 'basisId')}
                need(parts['PROMISE'] == f.encode('records', 'PROMISE', promise) and
                     any(record == raw for _, record, _ in disk.journal(files['grants.gsr'], self.root, node)),
                     'joining owned original basis')
                observed = (node, raw, source)
                need(basis['basisId'] not in self.sources or self.sources[basis['basisId']] == observed,
                     'joining reused source identity')
                self.sources[basis['basisId']] = observed
        need(cut == max(source_cuts), 'joining selected highest original prefix')
        ballot = f.canonical(selected['ballot'])
        need(ballot not in self.selections or self.selections[ballot] == parts['SELECTED'], 'joining same-ballot selection drift')
        self.selections[ballot] = parts['SELECTED']
        journal = disk.journal(files['grants.gsr'], self.root, node)
        need(any(raw == parts['SELECTED'] for _, raw, _ in journal), 'joining original installed journal selection')
        need(files['root.gsr'] == self.root_bytes and f.decode(files['node.gsr'], 'records', 'NODE', self.root)['identity'] ==
             catalog.identities(before['identities'])[node], 'joining original permanent owner')

    def typed(self, receipt):
        placed = self.placed_snapshot()
        need(placed.member('initialTyped', 'learner.gsr') == f.encode('records', 'LEARNER', dict(root=self.root, receipt=receipt)),
             'joining actual typed receipt')
        for name, raw in images.image_members(self.image).items():
            need(placed.member('initialTyped', 'backup/' + name) == raw, 'joining actual typed image')

    def step(self, index):
        before = self.states[-1]; registry = catalog.identities(before['identities'])
        first = self.owner('applied', index, 'node-1')
        parts, values = phased_certificate(first['pending.accept'], before, registry, self.root)
        entry, cert = values['ENTRY'], values['CERTIFICATE']; kind = entry['kind']
        need(kind == 'BARRIER' or kind in CONTROLS, 'joining original control profile')
        payload = None if kind == 'BARRIER' else catalog.parse(parts['PAYLOAD'])
        if kind == 'BARRIER': need(parts['PAYLOAD'] == b'', 'joining empty barrier')
        else: f.check_type(payload, {'object': f.catalog()['commands'][kind]}, f.catalog()['types'])
        if kind == 'RESERVE':
            need(payload['request']['kind'] == self.kind and payload['request']['number'] == 1 and
                 [v['node'] for v in payload['request']['target']] == self.targets,
                 'joining exact native membership profile')
        after = catalog.reduce_catalog(before, sha(self.catalogs[-1]), kind, payload, sha(parts['ENTRY']), self.root)
        if kind == 'READY': self.typed(payload['receipt'])
        voters = [v['voter'] for v in cert['proofs']]
        for node in voters:
            files = self.owner('applied', index, node); _, members, packet = disk.current(files)
            self.packet(packet, index-1)
            local, original = phased_certificate(files['pending.accept'], before, registry, self.root)
            need(all(local[k] == parts[k] for k in ('ENTRY', 'ACCEPT', 'PROOF', 'CERTIFICATE', 'PAYLOAD')),
                 'joining original owned phases')
            self.selected(files, members, local, original, node, before)
        self.states.append(after); self.catalogs.append(f.encode('records', 'CATALOG', after))
        self.entries.append(entry); self.phases.append(parts)
        start, _, scope = capsules.spans(self.entries, index)[-1]
        statement = f.encode('records', 'CHECKPOINT', self.checkpoint(start, index, scope))
        for node in voters:
            files = self.owner('applied', index, node)
            end = {k.removeprefix('applied-end/'): v for k, v in files.items() if k.startswith('applied-end/')}
            expected = dict(zip(('selector.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr', 'application.image'),
                (files['selector.gsr'], parts['CERTIFICATE'], self.catalogs[-1], statement, self.image)))
            need(all(end.get(k) == raw for k, raw in expected.items()), 'joining independently reduced applied end')
            voting = applied_voter(before, after, kind, node, end)
            if not voting: self.nonvoting.add((index, node))
            need(set(end) >= set(expected) | {'plan.json'}, 'joining complete applied end')
            if voting: self.ack(statement, node, end['ack.gsr'])
            extra = set(end) - set(expected) - {'ack.gsr', 'plan.json'}
            prefixes = {name.removesuffix('-statement.gsr') for name in extra if name.endswith('-statement.gsr')}
            need(all(p == 'parent' or re.fullmatch(r'ancestor-[0-5]', p) for p in prefixes) and
                 extra == {p + suffix for p in prefixes for suffix in ('-statement.gsr', '-ack.gsr')},
                 'joining applied ancestor inventory')
            need(('parent' in prefixes) == (start != index-1), 'joining immediate parent checkpoint')
            seen = set()
            for prefix in sorted(prefixes):
                raw = end[prefix + '-statement.gsr']; lower = f.decode(raw, 'records', 'CHECKPOINT', self.root)['start']['index']
                need(start < lower < index and lower not in seen and (prefix != 'parent' or lower == index-1) and
                     raw == f.encode('records', 'CHECKPOINT', self.checkpoint(lower, index, 'RANGE')),
                     'joining original ancestor endpoints')
                seen.add(lower); self.ack(raw, node, end[prefix + '-ack.gsr'])
            plan = dict(schema='gse-v53-applied-end/1.3', root=self.root, node=node,
                        files=[dict(path=k, bytes=len(raw), sha256=sha(raw)) for k, raw in sorted(end.items()) if k != 'plan.json'])
            need(end['plan.json'] == f.canonical(plan), 'joining applied end original inventory')
        if kind == 'INTENT':
            raw = joining.s.regular(self.path / 'joining-forced-ack.gsr', 8192)
            need(raw == self.placed_snapshot().member('pendingIntent', 'joining-ack.gsr'), 'joining retained pending ACK bytes')
            self.ack(statement, self.joining, raw)
        for node in voters:
            files = self.owner('published', index, node); _, members, packet = disk.current(files)
            self.packet(packet, index)
            need(members[sha(self.image) + '.image'] == self.image and files['root.gsr'] == self.root_bytes and
                 f.decode(files['node.gsr'], 'records', 'NODE', self.root)['identity'] ==
                 catalog.identities(after['identities'])[node], 'joining published unchanged application/identity')
        # The offline old voter never supplies an invented vote or newer end.
        for node in self.offline:
            need(self.owner('applied', index, node) == disk.inventory(self.path / 'before-network' / node) and
                 self.owner('published', index, node) == self.owner('applied', index, node), 'joining offline voter changed')
        return kind


def lifecycle(root, replay):
    rows = collection.read_json(root, 'events.json', collection.EVENT_BYTES)
    need(type(rows) is list and all(type(v) is dict for v in rows), 'joining original round events')
    rows = [v for v in rows if str(v.get('event', '')).startswith(('ROUND_', 'JOINING_ROUND_'))]
    selected = pending = complete = None; installed = []; started = []; ready = []
    for row in rows:
        need(set(row) == {'node', 'event', 'record', 'bytes'} and row['node'] == 'node-1', 'joining original round owner')
        raw = base64.b64decode(row['bytes'], validate=True)
        need(sha(raw) == row['record'], 'joining original round record')
        event = row['event'].removeprefix('JOINING_').removeprefix('ROUND_')
        if event == 'INSTALLED':
            need(pending is None and raw in replay.selections.values(), 'joining observed original installation')
            selected = raw; complete = None; installed.append(sha(raw))
        elif event == 'SLOT_BEGIN':
            value = f.decode(raw, 'records', 'ENTRY', replay.root); index = value['index']
            need(pending is None and 1 <= index <= len(replay.entries) and raw == replay.phases[index-1]['ENTRY'] and
                 selected == replay.phases[index-1]['SELECTED'], 'joining observed original slot')
            pending = index; complete = None; started.append(index)
        elif event == 'SLOT_COMPLETE':
            need(pending is not None, 'joining completion without original slot')
            index = pending; packet = replay.owner('published', index, 'node-1'); prefix, _, cap = disk.current(packet)
            original = f.decode(selected, 'records', 'SELECTED', replay.root)
            identity = catalog.identities(replay.states[index]['identities'])['node-1']
            value = f.decode(raw, 'wire', 'PUBLISH_ACK', replay.root)
            need(value['view'] == original['view'] and value['ballot'] == original['ballot'] and
                 value['sender'] == value['recipient'] == identity and value['sequence'] == 1 and
                 value['payload'] == dict(certificate=sha(replay.phases[index-1]['CERTIFICATE']), selection=sha(selected),
                     published=disk.anchor(cap['capsule']), generation=sha(packet[prefix + 'generation.gsr'])),
                 'joining original publication completion')
            complete = raw; pending = None
        elif event == 'BEFORE_READY':
            need(pending is None and complete is not None and raw == complete and started and
                 replay.entries[started[-1]-1]['kind'] == 'BARRIER' and
                 replay.states[started[-1]]['cut']['view']['operation'] is None, 'joining readiness before stable barrier')
            ready.append(started[-1]); complete = None
        else: raise ValueError('joining unexpected round event')
    need(pending is None and installed == [sha(v) for v in replay.selections.values()] and
         started == [i for i, e in enumerate(replay.entries, 1) if e['kind'] not in ('SEAL', 'INTENT')] and
         ready == [i for i, e in enumerate(replay.entries, 1) if e['kind'] == 'BARRIER'],
         'joining complete round lifecycle')
    return ready


def validate(root, *, size=3, kind='ADD', required_four=False, bootstrap_source='EMPTY'):
    source_args = source_policy.options(bootstrap_source)
    root = Path(root); original = collection.inventory(root)
    indices = sorted(int(p.name.removeprefix('applied-')) for p in root.iterdir() if re.fullmatch(r'applied-[1-9][0-9]*', p.name))
    need(1 <= len(indices) <= 64 and indices == list(range(1, len(indices)+1)), 'joining complete consecutive applied history')
    need(sorted(p.name for p in root.iterdir() if re.fullmatch(r'published-[1-9][0-9]*', p.name)) ==
         sorted('published-' + str(i) for i in indices), 'joining complete publication history')
    replay = Replay(root,size=size,kind=kind,required_four=required_four,**source_args); kinds = [replay.step(i) for i in indices]
    need(tuple(k for k in kinds if k != 'BARRIER') == CONTROLS and kinds[0] == kinds[-1] == 'BARRIER' and
         kinds[-2] == 'FINAL' and kinds[kinds.index('INTENT')+1] == 'FINAL', 'joining complete control order')
    final = replay.states[-1]
    need(final['active'] is None and final['results'][0]['phase'] == 'COMPLETED' and
         final['cut']['view']['old'] == final['cut']['view']['new'] == replay.targets,
         'joining final stable view')
    for node in replay.old[:size//2+1]:
        files=disk.inventory(root/'after-close'/node); packet=disk.current(files)[2]
        last=max(i for i,phase in enumerate(replay.phases,1) if node in
                 [v['voter'] for v in f.decode(phase['CERTIFICATE'],'records','CERTIFICATE',replay.root)['proofs']])
        through=packet['capsule']['cut']['index']
        need(last<=through<=len(indices),'joining closed owner publication regressed')
        need(f.decode(files['node.gsr'],'records','NODE',replay.root)['identity']==
             catalog.identities(final['identities'])[node],'joining closed original identity')
        replay.packet(packet,through)
    for node in replay.offline:
        need(disk.inventory(root/'after-close'/node)==disk.inventory(root/'before-network'/node),'joining offline voter changed')
    stable = joining.read(root / 'joining-originals-stable-cold')
    cold = disk.inventory(stable.root / 'replica')
    need(cold['root.gsr'] == replay.root_bytes and f.decode(cold['node.gsr'], 'records', 'NODE', replay.root)['identity'] ==
         catalog.identities(final['identities'])[replay.joining], 'joining retaining cold identity')
    replay.packet(disk.current(cold)[2], len(indices)); ready = lifecycle(root, replay)
    need(collection.inventory(root) == original, 'joining original history changed during replay')
    return source_policy.receipt(dict(status='PASS', scope='native-'+kind+'-catalog-certificate-checkpoint-chain', slots=len(indices), controls=kinds,
        profile=str(size)+'-'+kind+('-required-four' if required_four else ''), selections=len(replay.selections), checkpointObservations=len(replay.acks), internalReadyCuts=ready, semanticChainQualified=True,
        publicReady=False,
        completePhysicalQualified=False, forceAndNetworkQualified=False, processDeathQualified=False, phase3Complete=False),bootstrap_source)


NEGATIVES = {
    'missing-applied-slot': 'joining complete consecutive applied history',
    'entry-parent': 'joining original governing entry',
    'proof-receipt': 'joining original phased receipt',
    'duplicate-accepts': 'quorum identity/order',
    'learner-votes-before-intent': 'quorum identity/order',
    'joint-old-majority-only': 'both governing majorities',
    'ready-wrong-revision': 'ready exact prepared identity',
    'final-wrong-binding': 'final binding',
    'changed-applied-catalog': 'joining independently reduced applied end',
    'joint-checkpoint-old-majority-only': 'both governing majorities',
    'hidden-membership-boundary': 'joining capsule membership coverage',
    'duplicate-checkpoint-ack': 'quorum identity/order',
    'offline-voter-changed': 'joining offline voter changed',
    'missing-final-ready': 'joining complete round lifecycle',
    'ready-before-barrier': 'joining readiness before stable barrier',
}


def packed_phases(parts):
    raw = disk.container([parts[k] for k in ('SELECTOR', 'PROMISE', 'SELECTED', 'ENTRY', 'ACCEPT')], parts['PAYLOAD'])
    raw += parts['PROOF'] + parts['CERTIFICATE']
    return raw[:8] + struct.pack('>I', len(raw)) + raw[12:]


def change_payload(parts, payload):
    values = {k: f.decode(parts[k], 'records', k) for k in ('ENTRY', 'ACCEPT', 'PROOF', 'CERTIFICATE')}
    parts['PAYLOAD'] = f.canonical(payload); values['ENTRY']['payload'] = sha(parts['PAYLOAD'])
    parts['ENTRY'] = f.encode('records', 'ENTRY', values['ENTRY']); values['ACCEPT']['entry'] = sha(parts['ENTRY'])
    parts['ACCEPT'] = f.encode('records', 'ACCEPT', values['ACCEPT'])
    def witnesses(phase, original):
        return [dict(voter=v['voter'], incarnation=v['incarnation'], receipt=catalog.digest(dict(
            root=values['ENTRY']['root'], voter=v['voter'], incarnation=v['incarnation'], phase=phase, record=sha(parts[phase])))) for v in original]
    proof = dict(values['ACCEPT'], accepts=witnesses('ACCEPT', values['PROOF']['accepts']))
    parts['PROOF'] = f.encode('records', 'PROOF', proof)
    parts['CERTIFICATE'] = f.encode('records', 'CERTIFICATE', dict(proof, proofs=witnesses('PROOF', values['CERTIFICATE']['proofs'])))


def mutate(root, name):
    if name in ('missing-final-ready', 'ready-before-barrier'):
        rows = collection.read_json(root, 'events.json', collection.EVENT_BYTES)
        ready = next(v for v in rows if v.get('event') == 'JOINING_ROUND_BEFORE_READY'); rows.remove(ready)
        if name == 'ready-before-barrier':
            before = next(i for i, v in enumerate(rows) if v.get('event') == 'JOINING_ROUND_SLOT_BEGIN')
            rows.insert(before, ready)
        (root / 'events.json').write_bytes(f.canonical(rows)); return
    by_kind = {}
    for path in root.glob('applied-*/node-1/pending.accept'):
        parts, values = disk.pending(path.read_bytes(), ('PROOF', 'CERTIFICATE'))
        by_kind.setdefault(values['ENTRY']['kind'], []).append((values['ENTRY']['index'], path))
    first = min(by_kind['BARRIER'])
    kind = 'FINAL' if name in ('joint-old-majority-only', 'final-wrong-binding') else 'READY' if name == 'ready-wrong-revision' else None
    index, path = min(by_kind[kind]) if kind else first
    if name == 'missing-applied-slot':
        shutil.rmtree(root / ('applied-' + str(min(by_kind['PREPARE'])[0]))); return
    if name == 'changed-applied-catalog':
        (path.parent / 'applied-end/catalog.gsr').write_bytes(b'changed'); return
    if name == 'offline-voter-changed':
        (root / f'applied-{index}/node-3/pending.accept').write_bytes(b'changed'); return
    if name in ('joint-checkpoint-old-majority-only', 'hidden-membership-boundary', 'duplicate-checkpoint-ack'):
        index = min(by_kind['INTENT'])[0]; directory = root / f'published-{index}/node-1'
        files = disk.inventory(directory); prefix, members, packet = disk.current(files)
        cap = copy.deepcopy(packet['capsule']); item = cap['items'][-1]
        if name == 'hidden-membership-boundary': cap['items'].pop()
        elif name == 'duplicate-checkpoint-ack': item['endorsements'].append(item['endorsements'][0])
        else: item['endorsements'] = [h for h in item['endorsements'] if f.decode(packet['objects'][h], 'records', 'CHECKPOINT_ACK')['voter'] != 'node-4']
        members = dict(members, **{'source.gscp': disk.packet_bytes(cap, packet['objects'], packet['images'])})
        manifest = f.decode(files[prefix + 'generation.gsr'], 'records', 'GENERATION')
        selector, generated = disk.generation(members, disk.p.decode(members['source.gscp'])['capsule'], 'node-1', manifest['generation'], manifest['ownedTail'])
        for file, data in generated.items():
            if data is not None: (directory / file).write_bytes(data)
        (directory / 'selector.gsr').write_bytes(selector); return
    parts, values = disk.pending(path.read_bytes(), ('PROOF', 'CERTIFICATE'))
    if name in ('ready-wrong-revision', 'final-wrong-binding'):
        payload = catalog.parse(parts['PAYLOAD'])
        if name == 'ready-wrong-revision': payload['receipt']['prepared']['revision'] += 1
        else: payload['binding'] = '0' * 64
        change_payload(parts, payload)
    elif name == 'entry-parent':
        values['ENTRY']['previous'] = '0' * 64; parts['ENTRY'] = f.encode('records', 'ENTRY', values['ENTRY'])
    elif name == 'proof-receipt':
        values['CERTIFICATE']['proofs'][0]['receipt'] = '0' * 64
        parts['CERTIFICATE'] = f.encode('records', 'CERTIFICATE', values['CERTIFICATE'])
    else:
        accepts = copy.deepcopy(values['PROOF']['accepts'])
        if name == 'duplicate-accepts': accepts.append(copy.deepcopy(accepts[0]))
        elif name == 'learner-votes-before-intent': accepts[-1]['voter'] = 'node-4'
        elif name == 'joint-old-majority-only': accepts = [v for v in accepts if v['voter'] != 'node-4']
        else: raise ValueError('unknown joining mutation: ' + name)
        values['PROOF']['accepts'] = values['CERTIFICATE']['accepts'] = accepts
        parts['PROOF'] = f.encode('records', 'PROOF', values['PROOF'])
        parts['CERTIFICATE'] = f.encode('records', 'CERTIFICATE', values['CERTIFICATE'])
    path.write_bytes(packed_phases(parts))


def qualify(root):
    root = Path(root); original = validate(root); results = []
    for name, reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-joining-catalog-negative-') as temp:
            changed = Path(temp) / 'raw'; shutil.copytree(root, changed); mutate(changed, name)
            try: validate(changed)
            except ValueError as error: need(str(error) == reason, 'joining unrelated negative: ' + name + ': ' + str(error))
            else: raise ValueError('joining mutation accepted: ' + name)
        results.append(dict(case=name, status='REJECTED', reason=reason))
    return dict(original=original, negatives=results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--qualify', action='store_true'); args = parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root), sort_keys=True))
