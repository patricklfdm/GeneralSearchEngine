"""Conditional native ADD continuation from the original initialized owners.

The archived intermediate ballot 7 has no complete node-2 BASIS/source bytes.
We explicitly project its reclaimed, unselected source out of the boundary;
this is NOT complete physical history qualification. New selected sources,
installations, publications and cold inventories are independently derived.
"""
import argparse
import base64
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import joining_initialization_evidence as init
from . import source_exchange_evidence as exchange
from . import promised_source_evidence as transfer

s, f, disk, need, sha = init.s, init.f, init.disk, init.need, init.sha
t, peers, learner, future, PEERS = init.transition, init.peers, init.learner, init.future, init.PEERS
VOTERS = ('node-1', 'node-2', 'node-4')


def cold_order(events, *, joining='node-4'):
    expected = ['CURRENT_VALIDATED', 'CURRENT_FILES_FORCED', 'CURRENT_GENERATION_FORCED', 'CURRENT_SELECTOR_FORCED', 'CURRENT_DIRECTORY_FORCED']
    expected += ['JOINING_RETENTION_'+name+'_RECOVERY_'+phase for name in ('SEED', 'DONE') for phase in ('FORCED', 'PARENT_FORCED')]
    expected += [prefix+phase for prefix in ('LEARNER_RETENTION_RECOVERY_', 'RETENTION_RECOVERY_') for phase in ('ACTIVE_FORCED', 'PARENT_FORCED')]
    expected += ['FUTURE_RETENTION_RECOVERY_FORCED', 'FUTURE_RETENTION_RECOVERY_PARENT_FORCED', 'ACCEPT_ACTIVE_FORCED', 'ACCEPT_ACTIVE_PARENT_FORCED']
    marked=any(row.get('event','').startswith('JOINING_OWNER_') for row in events)
    if marked:
        from . import joining_owner_close as close
        # Optional observation must describe every original lifetime; never
        # filter unknown/partial markers out of the physical event order.
        close.intervals(events,joining)
        expected += [close.OPEN,'FIXTURE_OPEN_RETURNED',close.BEGIN,close.RETURNED,'FIXTURE_CLOSE_RETURNED']
    else:expected += ['FIXTURE_OPEN_RETURNED', 'FIXTURE_CLOSE_RETURNED']
    need(all(row.get('node') == joining for row in events if row.get('scope') == 'stable-cold-owner'),
         'joining continuation original cold owner')
    need([row['event'] for row in events if row.get('node') == joining and row.get('scope') == 'stable-cold-owner'] == expected,
         'joining continuation original cold reseal order')


def preparation_boundary(root, group):
    """Bind the observed preparation without inventing its missing source."""
    rows = init.s.collection.read_json(Path(root),'wire.json',init.s.collection.WIRE_BYTES)
    need(type(rows) is list and len(rows) <= init.s.collection.HISTORY_ROWS, 'joining continuation bounded preparation trace')
    ballot = init.next_ballot(group['node-1']); cap = disk.current(group['node-1'])[2]['capsule']
    identities = {n:f.decode(v['node.gsr'], 'records', 'NODE')['identity'] for n,v in group.items()}
    prepared = []; originals = []
    for row in rows:
        kind, request = exchange.wire(row['request']); answer, response = exchange.wire(row['response'])
        if kind == 'PREPARE' and request['ballot'] == ballot:
            need(row.get('withheld') is False and answer == 'PROMISE', 'joining continuation original preparation response')
            prepared.append((request, response))
        if answer == 'CHUNK' and response['ballot'] == ballot:
            raw = base64.b64decode(response['payload']['bytes'], validate=True)
            if raw[:4] == b'GSER' and int.from_bytes(raw[8:10], 'big') == f.catalog()['records']['PROMISE']['id']:
                value = f.decode(raw, 'records', 'PROMISE')
                if value['ballot'] == ballot: originals.append((raw, response['trace']))
    need(len(prepared) == len(originals) == 1, 'joining continuation exact intermediate preparation')
    promise, trace = originals[0]; observed = f.decode(promise, 'records', 'PROMISE')
    expected = f.encode('records', 'PROMISE', dict(root=cap['root'], view=s.catalog.authority(cap['root'], cap['cut']['view']),
        ballot=ballot, basisId=observed['basisId']))
    need(promise == expected, 'joining continuation original preparation promise')
    request, response = prepared[0]
    fields = dict(root=cap['root'], view=observed['view'], ballot=ballot, trace=request['trace'], sequence=1)
    need(request == dict(fields, sender=identities['node-1'], recipient=identities['node-2'], payload=dict(promise=sha(promise)))
         and response == dict(fields, sender=identities['node-2'], recipient=identities['node-1'], payload=dict(basis=response['payload']['basis'])),
         'joining continuation preparation correlation')
    session = [{k:row[k] for k in ('request', 'response')} for row in rows if exchange.wire(row['request'])[1]['trace'] == trace]
    transfer.transcript(session, [(sha(promise), promise, 'RECORD')], cap['root'], observed['view'], ballot,
        identities['node-2'], identities['node-1'], 'joining continuation intermediate promise', chunk_bytes=4*1024*1024)
    # Only a digest was returned for node 2. It is an observation, not bytes
    # from which its UUID, frozen ledgers, images or reclamation can be derived.
    return dict(ballot=ballot, oldPeer='node-2', observedBasisSha256=response['payload']['basis'],
        observedProposerPromiseSha256=sha(promise), originalPromiseTransferExchanges=len(session),
        intermediatePreparationPhysicalQualified=False)


def capture(files, ballot, observed_basis, identifiers):
    """Observe one UUID, derive the complete original source and exact BASIS."""
    basis = f.decode(observed_basis, 'records', 'BASIS')
    cap = disk.current(files)[2]['capsule']
    promise = f.encode('records', 'PROMISE', dict(root=cap['root'], view=s.catalog.authority(cap['root'], cap['cut']['view']),
        ballot=ballot, basisId=basis['basisId']))
    return init.prepare(files, ballot, files['grants.gsr']+promise+observed_basis, identifiers)


def reconcile(files):
    """Drop removed identities only under independently derived stable FINAL."""
    files = dict(files); cap = disk.current(files)[2]['capsule']
    state = peers.decode(files[PEERS]); plan = copy.deepcopy(state['plan'])
    if plan['view'] == cap['cut']['view']: return files
    available = t.require_coverage(files)
    for row in plan['peers']:
        for point in [*row.get('renewals', []), *row['possible']]:
            need(available.get(point['cut']['index']) == point, 'joining continuation reconciliation coverage')
    known = {row['identity']['node'] for row in plan['peers']}
    wanted = set(cap['cut']['view']['old']+cap['cut']['view']['new'])
    need(wanted <= known and (known == wanted or cap['cut']['view']['operation'] is None),
         'joining continuation reconciliation identity set')
    plan.update(view=cap['cut']['view'], peers=[row for row in plan['peers'] if row['identity']['node'] in wanted])
    files[PEERS] = peers.frame(dict(state, revision=state['revision']+1, previous=sha(files[PEERS]), plan=plan))
    return files


def maintenance(group, node, retiring=None, *, voters=VOTERS):
    """Conditional projection with exact derived copies, debt and source pins."""
    files = copy.deepcopy(group[node]); prefix, members, packet = disk.current(files)
    cap = packet['capsule']; owner = f.decode(files['node.gsr'], 'records', 'NODE')['identity']
    need(files['pending.accept'] == disk.EMPTY and not any(n == 'applied-end' or n.startswith('applied-end/') for n in files),
         'joining continuation maintenance unsettled authority')
    t.publication.phases.empty_future(files[future.FILE], files)
    files = reconcile(files)
    copies = [node, *[n for n in voters if n != node]]
    s.catalog.majority(cap['cut']['view'], sorted(copies))
    for peer in copies:
        files[PEERS] = t.observation.observe_same_cut(files[PEERS], files, group[peer], defer_renewal=True)
    available = t.require_coverage(files)
    files = {n: raw for n, raw in files.items() if not n.startswith('generations/') or n == prefix[:-1] or n.startswith(prefix)}
    rows = disk.journal(files['grants.gsr'], cap['root'], owner['node'])
    promises = {v['basisId']: (raw, v) for kind, raw, v in rows if kind == 'PROMISE' and v['basisId'] is not None}
    latest = next(v['ballot'] for kind, _, v in reversed(rows) if kind == 'PROMISE')
    retired = set()
    for name, raw in files.items():
        if not name.startswith('sources/') or not name.endswith('/source.gscp'): continue
        identifier = name.split('/')[1]; promise, value = promises[identifier]
        if promise == members['promise.gsr'] or value['ballot'] == latest: continue
        source = disk.p.decode(raw); point = disk.anchor(source['capsule'])
        need(value['ballot']['counter'] < latest['counter'] and available.get(point['cut']['index']) == point,
             'joining continuation source retirement coverage')
        retired.add(identifier)
    if retired and retiring is not None: retiring(node, files, {n:group[n] for n in copies}, retired)
    files = {n: raw for n, raw in files.items() if not (n.startswith('sources/') and n.split('/')[1] in retired)}
    # Remove only complete obsolete source groups. Adopted fences and the
    # current generation's original promise remain pinned.
    kept = []; discard = False
    for kind, raw, value in rows:
        if kind == 'PROMISE':
            discard = value['basisId'] in retired or (retired and value['basisId'] is None
                and raw != members['promise.gsr'] and value['ballot'] != latest)
        if not discard: kept.append(raw)
    files['grants.gsr'] = b''.join(kept)
    return files


def merge_learner(before, originals, packet):
    """Selected original confirmations may discharge covered older debt."""
    state = learner.decode(before); root = state['root']; cap = packet['capsule']
    registry = s.catalog.identities(f.decode(packet['objects'][cap['catalog']], 'records', 'CATALOG')['identities'])
    bound = None; points = {}; proofs = []
    for raw in [before, *originals]:
        value = learner.decode(raw); plan = value['plan']
        need(value['root'] == root, 'joining continuation learner root')
        if plan['request'] is None: continue
        if bound is None: bound = plan
        need((plan['request'], plan['learner']) == (bound['request'], bound['learner']), 'joining continuation learner identity')
        for point in [*plan.get('renewals', []), *plan['possible']]:
            at = point['cut']['index']
            need(at not in points or points[at] == point, 'joining continuation conflicting learner endpoint')
            points[at] = point
        if 'confirmation' in plan:
            proof = plan['confirmation']; point = learner.confirmation(proof, root, plan['request'], plan['learner'])
            query = f.decode(base64.b64decode(proof['query'], validate=True), 'wire', 'LEARNER_HEAD_QUERY')
            need(all(registry.get(query[k]['node']) == query[k] for k in ('sender', 'recipient')),
                 'joining continuation learner confirmation permanent identity')
            proofs.append((-point['cut']['index'], sha(f.canonical(proof)), proof))
    plan = dict(root=root, request=None if bound is None else bound['request'], learner=None if bound is None else bound['learner'], possible=[])
    if proofs:
        negative, _, proof = min(proofs, key=lambda v: v[:2]); plan['confirmation'] = proof
        points = {i:p for i,p in points.items() if i >= -negative}
    plan['possible'] = [points[i] for i in sorted(points)]; learner.plan(plan)
    return before if plan == state['plan'] else learner.frame(dict(state, revision=state['revision']+1, previous=sha(before), plan=plan))


def install(files, sources, selection):
    """Derive selected retention intent, reachable packet and generation bytes."""
    chosen = f.decode(selection, 'records', 'SELECTED'); names = sorted(sources)
    need([v['voter'] for v in chosen['sources']] == names, 'joining continuation exact selected cohort')
    s.catalog.majority(chosen['cut']['view'], names)
    owner = f.decode(files['node.gsr'], 'records', 'NODE')['identity']; node = owner['node']
    prefix, old, _ = disk.current(files); basis, raw = sources[node]; packet = disk.p.decode(sources[chosen['ballot']['proposer']][1])
    need(chosen['cut'] == packet['capsule']['cut'] and chosen['nextEntry'] is None, 'joining continuation selected original cut')
    peer_rows = []; learner_rows = []; peer_raw = []; learner_raw = []
    for n in names:
        b, data = sources[n]; p = disk.p.decode(data); value = f.decode(b, 'records', 'BASIS')
        ref = next(v for v in chosen['sources'] if v['voter'] == n)
        need(ref == dict(voter=n, basisId=value['basisId'], basisDigest=sha(b)), 'joining continuation selected source binding')
        pw, ps = init.retention.source(p, value, 0x47535250, 65536)
        lw, ls = init.retention.source(p, value, 0x47534c46, 32768)
        peer_rows.append((b, p, pw)); learner_rows.append((b, p, lw))
        peer_raw.append(peers.frame(ps)); learner_raw.append(learner.frame(ls))
    objects = t.reachable.prefix(packet, files['root.gsr'])
    for value in (t.selected.intent(owner, selection, files[PEERS], peer_rows), learner.intent(owner, selection, files[learner.FILE], learner_rows)):
        objects[sha(value)] = value
    promise = next(raw for kind, raw, value in reversed(disk.journal(files['grants.gsr'], chosen['root'], node)) if kind == 'PROMISE')
    members = {'promise.gsr': promise, 'basis.gsr': basis, 'selected.gsr': selection,
        'selected-sources.gsr': b''.join(sources[n][0] for n in names),
        'source.gscp': disk.packet_bytes(packet['capsule'], objects, packet['images'])}
    members.update({h+'.image': old[h+'.image'] for h in packet['images']})
    points = [p for row in peers.decode(files[PEERS])['plan']['peers'] for p in [*row.get('renewals', []), *row['possible']]]
    local_learner = learner.decode(files[learner.FILE])['plan']
    points += [*local_learner.get('renewals', []), *local_learner['possible']]
    points += [disk.anchor(disk.p.decode(raw)['capsule']) for name, raw in files.items()
               if name.startswith('sources/') and name.endswith('/source.gscp')]
    required = {p['cut']['index'] for p in points}
    # The already derived ancestry groups retain only locally required lower
    # endpoints. The adopted joining owner need not inherit old voters' debts.
    groups = []
    for raw in s.frames(old['ancestry.gsr']) if old.get('ancestry.gsr') else ():
        if int.from_bytes(raw[8:10], 'big') == f.catalog()['records']['CHECKPOINT']['id']: groups.append([raw])
        else:
            need(groups, 'joining continuation orphan ancestry'); groups[-1].append(raw)
    ancestry = b''.join(raw for rows in groups if f.decode(rows[0], 'records', 'CHECKPOINT')['start']['index'] in required for raw in rows)
    if ancestry: members['ancestry.gsr'] = ancestry
    selector, generation = disk.generation(members, packet['capsule'], node, 'b' if prefix == 'generations/a/' else 'a', None)
    state = peers.decode(files[PEERS]); registry = s.catalog.identities(f.decode(packet['objects'][packet['capsule']['catalog']], 'records', 'CATALOG')['identities'])
    points = [p for raw in [files[learner.FILE], *learner_raw] for p in learner.decode(raw)['plan']['possible']]
    plan = t.confirmation.merge([peers.decode(raw)['plan'] for raw in [files[PEERS], *peer_raw]], packet, registry, points)
    merged = files[PEERS] if plan == state['plan'] else peers.frame(dict(state, revision=state['revision']+1, previous=sha(files[PEERS]), plan=plan))
    return dict(files, **generation, **{'selector.gsr': selector, 'grants.gsr': files['grants.gsr']+selection,
        PEERS: merged, learner.FILE: merge_learner(files[learner.FILE], learner_raw, packet)})


class Continuation:
    def __init__(self, root, initialization):
        self.root, self.initialization = Path(root), initialization
        self.replay = initialization.replay
        self.joining = self.replay.joining
        self.voters = (*initialization.voters, self.joining)
        self.group = copy.deepcopy(initialization.group); self.group[self.joining] = copy.deepcopy(initialization.joined)
        self.identifiers = set(initialization.identifiers); self.comparisons = 0

    def prepared(self, node, files):
        """Optional complete producer capture; the historical reader has none."""

    def maintenance(self, group, node):
        return maintenance(group, node, voters=self.voters)

    def actual(self, label, node):
        if node != self.joining: return disk.inventory(self.root/label/node)
        joining = 'joining-originals-continuation' if label == 'after-close' else 'joining-'+label.removeprefix('continuation-')
        return disk.inventory(self.root/joining/'replica')

    def match(self, label):
        for node, files in self.group.items():
            actual = self.actual(label, node)
            expected = {k:v for k,v in files.items() if k != '.'}
            need(actual == expected, 'joining continuation exact inventory: '+label+': '+node)
            self.comparisons += 1
        self.joining_snapshot('joining-originals-continuation' if label == 'after-close' else 'joining-'+label.removeprefix('continuation-'))

    def joining_snapshot(self, label):
        snap = init.placement.snapshot.read(self.root/label)
        expected = dict(self.initialization.handoff.expected, replica=self.group[self.joining])
        need({n for n,v in snap.identities.items() if v['present']} == set(expected), 'joining continuation family inventory')
        for family, files in expected.items():
            actual = {v['name']:None if 'directory' in v['identity'] else snap.member(family, v['name'])
                      for v in snap.identities[family]['files']}
            need(actual == files, 'joining continuation exact family: '+label+': '+family)
            if family != 'replica':
                need(snap.identities[family] == self.initialization.handoff.snap.identities[family],
                     'joining continuation immutable original identity')

    def campaign(self, cut, counter):
        sources = {}; label = 'continuation-installed-'+str(cut)
        ballot = dict(counter=counter, proposer='node-1', incarnation=f.decode(self.group['node-1']['node.gsr'], 'records', 'NODE')['identity']['storage'])
        for node in self.voters:
            observed = disk.current(self.actual(label, node))[1]['basis.gsr']
            self.group[node], sources[node] = capture(self.group[node], ballot, observed, self.identifiers)
            self.prepared(node, self.group[node])
        selected = self.replay.phases[cut]['SELECTED']
        maintained = {node: self.maintenance(self.group, node) for node in self.voters}
        for node in self.voters:
            self.group[node] = install(maintained[node], sources, selected)
        self.match(label)
        for node in self.voters:
            need((self.root/f'continuation-grants-{cut}-{node}.gsr').read_bytes() == self.group[node]['grants.gsr'],
                 'joining continuation exact standalone grants')

    def slot(self, index):
        # All selected owners complete maintenance before application. Copies
        # refer to complete preceding generations, never a claimed endpoint.
        for node in self.voters: self.group[node] = self.maintenance(self.group, node)
        parts = self.replay.phases[index-1]
        for node in self.voters:
            files = self.group[node]; local = disk.current(files)[1]
            files['pending.accept'] = s.packed_phases(dict(parts, SELECTOR=files['selector.gsr'], PROMISE=local['promise.gsr'], SELECTED=local['selected.gsr']))
            files.update(t.applied_end(self.replay, files, index, node))
        self.match('applied-'+str(index))
        for node in self.voters: self.group[node] = t.publication.expected_publication(self.replay, self.group[node], index, node)
        self.match('published-'+str(index))

    def run(self):
        # Counter 7 belongs to the separately observed but incompletely retained
        # preparation. Counter 8 is a fresh selected activation, not its reuse.
        boundary = preparation_boundary(self.root, self.group)
        need(boundary['ballot']['counter'] == 7, 'joining continuation original preparation counter')
        self.campaign(9, 8); self.slot(10)
        for node in VOTERS: self.group[node] = self.maintenance(self.group, node)
        self.campaign(10, 9); self.slot(11)
        self.match('after-close')
        self.joining_snapshot('joining-originals-stable-cold')
        cold_order(json.loads((self.root/'events.json').read_bytes()))
        return dict(status='PASS', scope='native-ADD-conditional-joint-continuation', ownerSnapshotComparisons=self.comparisons,
            selectedInstallations=2, publications=2, finalCut=11, coldSnapshots=2, preparationBoundary=boundary,
            conditionalContinuationQualified=True, intermediatePreparationPhysicalQualified=False,
            completePhysicalQualified=False, forceAndNetworkQualified=False, processDeathQualified=False, phase3Complete=False)


def validate(root):
    root = Path(root); original = s.collection.inventory(root)
    t.publication.validate(root)
    replay = s.Replay(root)
    for index in range(1, 12): replay.step(index)
    history = init.placement.History(root, replay); history.run()
    owner = init.placement.Placement(root, history); owner.run()
    handoff = init.retirement.Retirement(root, owner); handoff.run()
    initialization = init.Initialization(root, handoff); initialization.run()
    result = Continuation(root, initialization).run()
    need(s.collection.inventory(root) == original, 'joining original changed during continuation replay')
    return result


NEGATIVES = {
    'preparation-correlation-changed': ('wire.json', 'correlation', 'joining continuation preparation correlation'),
    'joint-orphan': ('continuation-installed-9/node-1', 'orphan', 'joining continuation exact inventory: continuation-installed-9: node-1'),
    'joint-peer-revision': ('continuation-installed-9/node-1', 'peer', 'joining continuation exact inventory: continuation-installed-9: node-1'),
    'joint-learner-confirmation-lost': ('continuation-installed-9/node-2', 'learner', 'joining continuation exact inventory: continuation-installed-9: node-2'),
    'joint-inactive-generation-lost': ('continuation-installed-9/node-2', 'inactive', 'joining continuation exact inventory: continuation-installed-9: node-2'),
    'joint-source-image-changed': ('joining-installed-9/replica', 'image', 'joining continuation exact inventory: continuation-installed-9: node-4'),
    'joint-extra-allocation': ('joining-installed-9/replica', 'allocator', 'joining continuation exact inventory: continuation-installed-9: node-4'),
    'joint-offline-owner-changed': ('continuation-installed-9/node-3', 'allocator', 'joining continuation exact inventory: continuation-installed-9: node-3'),
    'joint-obsolete-source-retained': ('continuation-installed-9/node-1', 'obsolete', 'joining continuation exact inventory: continuation-installed-9: node-1'),
    'stable-peer-revision': ('continuation-installed-10/node-2', 'peer', 'joining continuation exact inventory: continuation-installed-10: node-2'),
    'stable-adopted-fence-lost': ('joining-installed-10/replica', 'adoption', 'joining continuation exact inventory: continuation-installed-10: node-4'),
    'stable-future-revision': ('continuation-installed-10/node-1', 'future', 'joining continuation exact inventory: continuation-installed-10: node-1'),
    'stable-orphan': ('joining-installed-10/replica', 'orphan', 'joining continuation exact inventory: continuation-installed-10: node-4'),
    'standalone-grant-changed': ('continuation-grants-9-node-2.gsr', 'standalone', 'joining continuation exact standalone grants'),
    'final-orphan': ('after-close/node-1', 'orphan', 'joining continuation exact inventory: after-close: node-1'),
    'final-extra-allocation': ('joining-originals-continuation/replica', 'allocator', 'joining continuation exact inventory: after-close: node-4'),
    'cold-extra-allocation': ('joining-originals-stable-cold/replica', 'allocator', 'joining continuation exact family: joining-originals-stable-cold: replica'),
    'cold-peer-revision': ('joining-originals-stable-cold/replica', 'peer', 'joining continuation exact family: joining-originals-stable-cold: replica'),
    'cold-future-revision': ('joining-originals-stable-cold/replica', 'future', 'joining continuation exact family: joining-originals-stable-cold: replica'),
    'cold-immutable-file-changed': ('joining-originals-stable-cold/retirement', 'immutable', 'joining continuation exact family: joining-originals-stable-cold: retirement'),
    'cold-original-key-changed': ('joining-originals-stable-cold', 'key', 'joining continuation immutable original identity'),
    'cold-force-omitted': ('events.json', 'force', 'joining continuation original cold reseal order'),
}


def mutate(root, name):
    relative, action, _ = NEGATIVES[name]; path = root/relative
    if action == 'orphan': (path/'unexpected.bin').write_bytes(b'not owned')
    elif action in ('allocator', 'peer', 'future', 'learner'):
        file = {'allocator':'allocator.gsr', 'peer':PEERS, 'future':future.FILE, 'learner':learner.FILE}[action]; p = path/file
        if action == 'allocator':
            value = f.decode(p.read_bytes(), 'records', 'ALLOCATOR'); value['counter'] += 1
            p.write_bytes(f.encode('records', 'ALLOCATOR', value))
        elif action in ('peer', 'learner'):
            decoder = peers if action == 'peer' else learner; value = decoder.decode(p.read_bytes())
            if action == 'peer': value['revision'] += 1
            else: value['plan'].pop('confirmation')
            p.write_bytes(decoder.frame(value))
        else:
            value = t.publication.phases.empty_future(p.read_bytes(), disk.inventory(path)); value['revision'] += 1
            p.write_bytes(future.frame(value, {}))
    elif action == 'inactive':
        prefix = disk.current(disk.inventory(path))[0]
        target = path/'generations'/('b' if prefix == 'generations/a/' else 'a')
        shutil.rmtree(target)
    elif action == 'image': next((path/'sources').glob('*/*.image')).write_bytes(b'changed retained image')
    elif action == 'obsolete':
        before = disk.inventory(root/'before-joint-continuation/node-1'); rows = disk.journal(before['grants.gsr'], disk.current(before)[2]['capsule']['root'], 'node-1')
        identifier = rows[-1][2]['basisId']; shutil.copytree(root/'before-joint-continuation/node-1/sources'/identifier, path/'sources'/identifier)
    elif action == 'adoption':
        p = path/'grants.gsr'; rows = list(s.frames(p.read_bytes())); p.write_bytes(b''.join(rows[1:]))
    elif action == 'standalone': path.write_bytes(path.read_bytes()+b'changed')
    elif action == 'immutable':
        p = next(v for v in sorted(path.iterdir()) if v.is_file() and not v.name.endswith('.lock')); p.write_bytes(p.read_bytes()+b'changed')
    elif action == 'force':
        rows = json.loads(path.read_bytes()); at = next(i for i,v in enumerate(rows) if v.get('scope') == 'stable-cold-owner' and v['event'] == 'CURRENT_FILES_FORCED')
        rows.pop(at); path.write_bytes(f.canonical(rows))
    elif action == 'correlation':
        rows = json.loads(path.read_bytes())
        for row in rows:
            kind, value = exchange.wire(row['request'])
            if kind == 'PREPARE' and value['ballot']['counter'] == 7:
                for field in ('request', 'response'):
                    kind, value = exchange.wire(row[field]); value['sequence'] += 1
                    row[field] = base64.b64encode(f.encode('wire', kind, value)).decode()
        path.write_bytes(f.canonical(rows))
    native = root/relative.split('/')[0]
    if (native/'inventory.json').exists():
        rows = json.loads((native/'inventory.json').read_bytes())
        for family in rows:
            for entry in family.get('files', []):
                p = native/family['name']/entry['name']
                if p.is_file(): entry['identity'].update(size=p.stat().st_size, sha256=sha(p.read_bytes()))
            if action == 'key' and family['name'] == 'retirement': family['files'][0]['identity']['key'] = 'changed-original-key'
            if action == 'orphan' and family['name'] == 'replica':
                p = path/'unexpected.bin'; family['files'].append(dict(name=p.name, identity=dict(key='negative-orphan', size=p.stat().st_size, sha256=sha(p.read_bytes()))))
                family['files'].sort(key=lambda v:v['name'])
        (native/'inventory.json').write_bytes(f.canonical(rows))


def qualify(root, progress=None):
    root = Path(root); original = validate(root); results = []
    if progress: progress(dict(stage='original', status='PASS'))
    for name, (_, _, reason) in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-joining-continuation-negative-') as temp:
            copied = Path(temp)/'raw'; shutil.copytree(root, copied); mutate(copied, name)
            init.validate(copied)
            try: validate(copied)
            except ValueError as error: need(str(error) == reason, 'joining unrelated continuation negative: '+name+': '+str(error))
            else: raise ValueError('joining continuation mutation accepted: '+name)
        results.append(dict(case=name, status='REJECTED', reason=reason, initializationGate='PASS'))
        if progress: progress(results[-1])
    return dict(original=original, negatives=results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--qualify', action='store_true'); args = parser.parse_args()
    result = qualify(args.root, lambda row: print(json.dumps(row, sort_keys=True), file=sys.stderr, flush=True)) if args.qualify else validate(args.root)
    print(json.dumps(result, sort_keys=True))
