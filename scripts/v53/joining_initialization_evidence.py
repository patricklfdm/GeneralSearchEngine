"""Compose original old-majority preparation with native joining initialization.

All mutable bytes are derived from the preceding bootstrap/placement/retirement
history. Only original request trace IDs, source UUIDs and filesystem identities
are observations. Complete transport causality and process death are later gates.
"""
import argparse
import base64
import copy
import json
from pathlib import Path
import shutil
import tempfile
import uuid

from . import joining_retirement_evidence as retirement
from . import joining_retention_evidence as retention

placement = retirement.placement
transition = placement.transition
s, f, disk, need, sha = placement.s, placement.f, placement.disk, placement.need, placement.sha
peers, learner, future = transition.publication.peers, transition.learner, transition.future
PEERS = transition.PEERS


def confirmed_learner(before, proof, endpoint):
    state = learner.decode(before); plan = copy.deepcopy(state['plan'])
    need(learner.confirmation(proof, state['root'], plan['request'], plan['learner']) == endpoint,
         'joining initialization original learner endpoint')
    query = f.decode(base64.b64decode(proof['query'], validate=True), 'wire', 'LEARNER_HEAD_QUERY')
    need(query['sender'] == state['owner'], 'joining initialization original probe owner')
    at = endpoint['cut']['index']; old = plan['possible']
    need(old and at >= old[0]['cut']['index'], 'joining initialization older learner confirmation')
    need(all(v['cut']['index'] != at or v == endpoint for v in old), 'joining initialization conflicting learner endpoint')
    if 'confirmation' in plan and learner.confirmation(plan['confirmation'], state['root'], plan['request'], plan['learner']) == endpoint:
        return before
    renewals = {v['cut']['index']: v for v in plan.get('renewals', [])}
    for value in old:
        if value['cut']['index'] < at:
            need(value['cut']['index'] not in renewals or renewals[value['cut']['index']] == value,
                 'joining initialization conflicting learner renewal')
            renewals[value['cut']['index']] = value
    plan.update(possible=[endpoint]+[v for v in old if v['cut']['index'] > at], confirmation=proof)
    if renewals: plan['renewals'] = [renewals[n] for n in sorted(renewals)]
    return learner.frame(dict(state, revision=state['revision']+1, previous=sha(before), plan=plan))


def reconcile(before, local, joining):
    """Add the actual installed new voter; retain every old obligation unchanged."""
    state = peers.decode(before); plan = copy.deepcopy(state['plan'])
    _, _, packet = disk.current(local); _, _, actual = disk.current(joining)
    identity = f.decode(joining['node.gsr'], 'records', 'NODE')['identity']
    owner = f.decode(local['node.gsr'], 'records', 'NODE')['identity']
    cap = packet['capsule']; view = cap['cut']['view']
    registry = s.catalog.identities(f.decode(packet['objects'][cap['catalog']], 'records', 'CATALOG')['identities'])
    need(state['owner'] == owner and state['root'] == actual['capsule']['root'] == cap['root']
         and disk.anchor(cap) == disk.anchor(actual['capsule']) and registry.get(identity['node']) == identity,
         'joining initialization exact installed joining copy')
    old = {v['identity']['node']: v for v in plan['peers']}; wanted = set(view['old']) | set(view['new'])
    need(set(old) <= wanted and wanted-set(old) == {identity['node']} and identity['node'] not in view['old']
         and view['operation'] is not None, 'joining initialization exact added voter')
    old[identity['node']] = dict(identity=identity, possible=[disk.anchor(cap)])
    plan.update(view=view, peers=[old[node] for node in sorted(old)])
    return peers.frame(dict(state, revision=state['revision']+1, previous=sha(before), plan=plan))


def next_ballot(files):
    owner = f.decode(files['node.gsr'], 'records', 'NODE')['identity']
    allocator = f.decode(files['allocator.gsr'], 'records', 'ALLOCATOR')
    rows = disk.journal(files['grants.gsr'], allocator['root'], owner['node'])
    counter = max([allocator['counter'], *[v['ballot']['counter'] for _, _, v in rows]])
    need(counter < 2**63-2, 'joining initialization allocator exhausted')
    return dict(counter=counter+1, proposer=owner['node'], incarnation=owner['storage'])


def prepare(files, ballot, observed, identifiers):
    """Freeze exact ledgers without selecting, installing or exposing READY."""
    _, members, packet = disk.current(files); cap = packet['capsule']
    owner = f.decode(files['node.gsr'], 'records', 'NODE')['identity']; node = owner['node']
    old = disk.journal(files['grants.gsr'], cap['root'], node)
    actual = disk.journal(observed, cap['root'], node)
    need(actual[:len(old)] == old and [v[0] for v in actual[len(old):]] == ['PROMISE', 'BASIS'],
         'joining initialization exact prepared grant suffix')
    identifier = actual[len(old)][2]['basisId']
    need(type(identifier) is str and str(uuid.UUID(identifier)) == identifier and identifier not in identifiers
         and all(v.get('basisId') != identifier for _, _, v in old) and 'sources/'+identifier not in files,
         'joining initialization fresh original source identity')
    identifiers.add(identifier)
    need(files['pending.accept'] == disk.EMPTY, 'joining initialization preparation has pending tail')
    for name, decoder in ((PEERS, peers.decode), (learner.FILE, learner.decode)):
        state = decoder(files[name])
        need(state['owner'] == owner and state['root'] == cap['root'], 'joining initialization captured ledger owner')
    value = dict(root=cap['root'], view=s.catalog.authority(cap['root'], cap['cut']['view']), ballot=ballot, basisId=identifier)
    promise = f.encode('records', 'PROMISE', value)
    wrapped = [transition.selected.s.wrap(promise, files[PEERS]), learner.wrap(promise, files[learner.FILE])]
    objects = dict(packet['objects'], **{sha(raw): raw for raw in wrapped})
    raw = disk.packet_bytes(cap, objects, packet['images']); frozen = disk.p.decode(raw)
    basis = f.encode('records', 'BASIS', dict(value, voter=node, cut=cap['cut'],
        capsule=sha(frozen['capsuleBytes']), inventory=sha(frozen['indexBytes']), accepted=None))
    need([row[1] for row in actual[len(old):]] == [promise, basis], 'joining initialization exact frozen grant bytes')
    source = 'sources/'+identifier
    result = dict(files, **{'grants.gsr': files['grants.gsr']+promise+basis, source: None, source+'/source.gscp': raw})
    result.update({source+'/'+h+'.image': members[h+'.image'] for h in packet['images']})
    if node == ballot['proposer']:
        result['allocator.gsr'] = f.encode('records', 'ALLOCATOR', dict(root=cap['root'], node=node, counter=ballot['counter']))
    return result, (basis, raw)


def local_order(events, *, joining='node-4'):
    """Bind the derived transaction and grant to their three original scopes."""
    need(type(events) is list and len(events) <= s.collection.HISTORY_ROWS and all(type(row) is dict for row in events),
         'joining initialization event collection bound')
    stages = ('initial-owner', 'retaining-owner', 'repeated-basis-owner')
    need(all(row.get('node') == joining for row in events if row.get('scope') in stages),
         'joining initialization original lifecycle owner')
    rows = {stage: [(index, row['event']) for index, row in enumerate(events)
                   if row.get('node') == joining and row.get('scope') == stage and row['event'] != 'GRANT_CAPTURED'] for stage in stages}
    # A diagnostic copy marker is not a new protocol force boundary. The v2
    # collector binds its bytes separately; all actual callbacks stay exact.
    need(all(rows.values()) and rows[stages[0]][-1][0] < rows[stages[1]][0][0] < rows[stages[1]][-1][0] < rows[stages[2]][0][0],
         'joining initialization original lifecycle order')
    writes = ['JOINING_RETENTION_'+name+'_'+step for name in ('SEED', 'PEERS', 'FUTURE', 'LEARNER', 'DONE')
              for step in ('CREATED', 'PREFIX_WRITTEN', 'WRITTEN', 'FORCED', 'CANDIDATE_PARENT_FORCED', 'RENAMED', 'PARENT_FORCED')]
    writes.append('JOINING_RETENTION_BEFORE_RETURN')
    need([v for _, v in rows['initial-owner'] if v.startswith('JOINING_RETENTION_')] == writes,
         'joining initialization original transaction force order')
    retained_order(events, joining=joining)


def recovery_order():
    return ['CURRENT_VALIDATED', 'CURRENT_FILES_FORCED', 'CURRENT_GENERATION_FORCED', 'CURRENT_SELECTOR_FORCED', 'CURRENT_DIRECTORY_FORCED',
        'JOINING_RETENTION_SEED_RECOVERY_FORCED', 'JOINING_RETENTION_SEED_RECOVERY_PARENT_FORCED',
        'JOINING_RETENTION_DONE_RECOVERY_FORCED', 'JOINING_RETENTION_DONE_RECOVERY_PARENT_FORCED',
        'LEARNER_RETENTION_RECOVERY_ACTIVE_FORCED', 'LEARNER_RETENTION_RECOVERY_PARENT_FORCED',
        'RETENTION_RECOVERY_ACTIVE_FORCED', 'RETENTION_RECOVERY_PARENT_FORCED',
        'FUTURE_RETENTION_RECOVERY_FORCED', 'FUTURE_RETENTION_RECOVERY_PARENT_FORCED', 'ACCEPT_ACTIVE_FORCED', 'ACCEPT_ACTIVE_PARENT_FORCED']


def retained_order(events, *, joining):
    """The unchanged two native grant/reopen scopes, after initialization."""
    scopes = ('retaining-owner', 'repeated-basis-owner')
    need(all(row.get('node') == joining for row in events if row.get('scope') in scopes),
         'joining initialization original lifecycle owner')
    rows = {scope: [(i, row['event']) for i, row in enumerate(events)
                   if row.get('scope') == scope and row['event'] != 'GRANT_CAPTURED'] for scope in scopes}
    need(all(rows.values()) and rows[scopes[0]][-1][0] < rows[scopes[1]][0][0],
         'joining initialization original lifecycle order')
    recovery = recovery_order()
    allocator = ['ALLOCATOR_'+step for step in ('BEFORE_WRITE', 'CREATED', 'WRITTEN', 'FORCED', 'RENAMED', 'DIRECTORY_FORCED', 'BEFORE_RETURN')]
    grant = ['CURRENT_BEFORE_CAPTURE', 'PROMISE_BEFORE_WRITE', 'PROMISE_WRITTEN', 'PROMISE_FORCED',
        'CAPTURE_INTENT_CREATED', 'CAPTURE_INTENT_PREFIX_WRITTEN', 'CAPTURE_INTENT_WRITTEN', 'CAPTURE_INTENT_FORCED', 'CAPTURE_INTENT_PARENT_FORCED',
        'SOURCE_BEFORE_CREATE', 'SOURCE_CREATED', 'SOURCE_PACKET_CREATED', 'SOURCE_PACKET_PREFIX_WRITTEN', 'SOURCE_PACKET_WRITTEN', 'SOURCE_PACKET_FORCED',
        'SOURCE_IMAGE_CREATED', 'SOURCE_IMAGE_PREFIX_WRITTEN', 'SOURCE_IMAGE_WRITTEN', 'SOURCE_IMAGE_FORCED',
        'SOURCE_FILES_DIRECTORY_FORCED', 'SOURCE_DIRECTORY_FORCED', 'BASIS_BEFORE_WRITE', 'BASIS_PREFIX_WRITTEN', 'BASIS_WRITTEN', 'BASIS_FORCED',
        'CAPTURE_INTENT_DELETED', 'CAPTURE_INTENT_CLEARED', 'GRANT_BEFORE_RETURN', 'FLOOR_COPY_BEFORE_RETURN']
    for scope, operations, reason in (
        ('retaining-owner', allocator+grant, 'joining initialization original first grant order'),
        ('repeated-basis-owner', ['CURRENT_BEFORE_CAPTURE']+allocator, 'joining initialization original repeated basis order'),
    ):
        # Optional observation wraps the actual journal after recovery and before
        # close. Do not drop arbitrary markers: accept only the exact complete
        # wrapper, retaining every protocol force and its original position.
        # The resource reader separately binds these markers to lease releases.
        actual = [v for _, v in rows[scope]]
        plain = recovery+operations
        observed = recovery+['JOINING_OWNER_OPEN_RETURNED']+operations+[
            'JOINING_OWNER_CLOSE_BEGIN', 'JOINING_OWNER_CLOSE_RETURNED']
        need(actual == plain or actual == observed, reason)


def confirm_old_learners(root, owner, group, *, replay, voters):
    """Derive the pre-seed learner ledgers from the original head exchanges."""
    wire = s.catalog.parse((root/'joining-head-wire.json').read_bytes())
    need(type(wire) is list and len(wire) == len(voters), 'joining initialization original head exchange count')
    cap = disk.p.decode(owner.history.sources[8]['source.gscp'])['capsule']; traces = set()
    for node, row in zip(voters, wire):
        need(type(row) is dict and set(row) == {'request', 'response'}, 'joining initialization head exchange shape')
        query = f.decode(base64.b64decode(row['request'], validate=True), 'wire', 'LEARNER_HEAD_QUERY')
        trace = query['trace']; need(str(uuid.UUID(trace)) == trace and trace not in traces, 'joining initialization original head trace')
        traces.add(trace)
        identity = f.decode(group[node]['node.gsr'], 'records', 'NODE')['identity']
        request = dict(root=replay.root, view=owner.request['expected'],
            ballot=dict(counter=1, proposer=owner.joining['node'], incarnation=owner.joining['storage']),
            trace=trace, sequence=1, sender=identity, recipient=owner.joining, payload=dict(request=owner.request))
        response = dict(request, sender=owner.joining, recipient=identity,
            payload=dict(request=sha(f.canonical(owner.request)), endpoint=disk.anchor(cap)))
        proof = dict(query=placement.encoded(f.encode('wire', 'LEARNER_HEAD_QUERY', request)),
                     ack=placement.encoded(f.encode('wire', 'LEARNER_HEAD_ACK', response)))
        need(row == dict(request=proof['query'], response=proof['ack']), 'joining initialization exact original head exchange')
        files = group[node]
        files[learner.FILE] = confirmed_learner(files[learner.FILE], proof, disk.anchor(cap))
        need((root/('joining-confirmed-'+node+'.json')).read_bytes() == f.canonical(learner.decode(files[learner.FILE])['plan']),
             'joining initialization exact confirmed learner plan')


class Initialization:
    def __init__(self, root, handoff):
        self.root, self.handoff = Path(root), handoff
        self.owner = handoff.owner; self.replay = self.owner.replay
        self.voters = self.owner.history.voters
        self.group = copy.deepcopy(self.owner.history.group)
        self.joined = copy.deepcopy(handoff.expected['replica'])
        self.identifiers = set(); self.originals = []

    def prepared(self, node, files):
        """Optional original capture comparison, never a source of expected bytes."""

    def maintain(self, copies):
        self.group = transition.maintenance(self.group, voters=self.voters)

    def confirmations(self):
        confirm_old_learners(self.root, self.owner, self.group, replay=self.replay, voters=self.voters)

    def old_preparation(self):
        for node in self.voters:
            files = self.group[node]; files[PEERS] = reconcile(files[PEERS], files, self.joined)
            if node == 'node-1':
                need((self.root/'joining-floor-reconciled.json').read_bytes() == f.canonical(peers.decode(files[PEERS])['plan']),
                     'joining initialization exact reconciled peer plan')
        copies = {n: self.group[n] for n in self.voters}; copies[self.replay.joining] = self.joined
        view = disk.current(self.joined)[2]['capsule']['cut']['view']; s.catalog.majority(view, sorted(copies))
        for node in self.voters:
            files = self.group[node]
            for original in copies.values():
                files[PEERS] = transition.observation.observe_same_cut(files[PEERS], files, original, defer_renewal=True)
        self.maintain(copies)
        ballot = next_ballot(self.group['node-1'])
        for node in self.voters:
            actual = disk.inventory(self.root/'before-joint-continuation'/node)
            self.group[node], source = prepare(self.group[node], ballot, actual['grants.gsr'], self.identifiers)
            self.prepared(node, self.group[node])
            self.originals.append(source)
            for suffix, raw in zip(('gsr', 'gscp'), source):
                need((self.root/('joining-retention-'+node+'.'+suffix)).read_bytes() == raw,
                     'joining initialization exact retained old source: '+node)
        for node, files in self.group.items():
            need(disk.inventory(self.root/'before-joint-continuation'/node) == files,
                 'joining initialization exact old prepared inventory: '+node)

    def initial_current(self, prefix, members):
        for name, raw in [('generation.gsr', self.joined[prefix+'generation.gsr']),
                          ('capsule.gscp', members['source.gscp']), ('ancestry.gsr', members['ancestry.gsr'])]:
            need((self.root/('joining-early-'+name)).read_bytes() == raw, 'joining initialization exact early joining copy')

    def initialize(self):
        prefix, members, current = disk.current(self.joined)
        self.initial_current(prefix, members)
        ancestry = [disk.current(self.group[n])[1].get('ancestry.gsr', b'') for n in self.voters]
        seed, initial = retention.derive(current, self.owner.joining, self.originals, confirmed_peers=True, source_ancestry=ancestry)
        need((self.root/'joining-retention-seed.json').read_bytes() == seed, 'joining initialization exact derived seed')
        for name, value in [('peers', peers.decode(initial[PEERS])['plan']), ('learner', learner.decode(initial[learner.FILE])['plan'])]:
            need((self.root/('joining-retention-'+name+'.json')).read_bytes() == f.canonical(value),
                 'joining initialization exact derived plan: '+name)
        # The handoff's native/joined records were independently derived before
        # this transaction check; none of their observed claims is an input root.
        retention.transaction(self.handoff.snap, seed, initial)
        self.joined.update(initial)
        self.joined.update({name: self.handoff.snap.member('replica', name) for name in (retention.DECISION, retention.DONE)})

    def grant_and_reopen(self):
        ballot = next_ballot(self.joined)
        observed = self.handoff.snap.member('replica', 'grants.gsr')
        self.joined, source = prepare(self.joined, ballot, observed, self.identifiers)
        self.prepared(self.owner.joining['node'], self.joined)
        need((self.root/'joining-native-basis.gsr').read_bytes() == source[0], 'joining initialization exact native basis')
        # Reopening the same promise preserves its source and grant bytes. The
        # fixture then reserves one more counter, without another PREPARE.
        reserved = next_ballot(self.joined)
        self.joined['allocator.gsr'] = f.encode('records', 'ALLOCATOR', dict(root=self.replay.root,
            node=self.owner.joining['node'], counter=reserved['counter']))
        self.handoff.expected['replica'] = self.joined
        for family, files in self.handoff.expected.items():
            actual = {name: None if 'directory' in identity else self.handoff.snap.member(family, name)
                      for name, identity in self.handoff.ids[family].items()}
            need(actual == files, 'joining initialization exact native family: '+family)

    def check_order(self, events):
        local_order(events, joining=self.replay.joining)

    def run(self):
        self.confirmations(); self.old_preparation(); self.initialize(); self.grant_and_reopen()
        # An aggregate trace is bounded by the collection contract, not the
        # much smaller parser budget for one protocol message.
        self.check_order(s.collection.read_json(self.root, 'events.json', s.collection.EVENT_BYTES))
        return dict(status='PASS', scope='native-'+self.replay.kind+'-original-joining-initialization', oldOwnerSnapshots=self.owner.history.comparisons+len(self.group),
            nativeFamilies=len(self.handoff.expected), comparedNativeFiles=sum(raw is not None for files in self.handoff.expected.values() for raw in files.values()),
            originalHeadExchanges=len(self.voters), preparedOldSources=len(self.originals), initializedLedgers=3,
            joiningInitializationPhysicalQualified=True, joiningInitializationLocalOrderQualified=True, completePhysicalQualified=False,
            forceAndNetworkQualified=False, processDeathQualified=False, phase3Complete=False)


def validate(root, *, size=3, kind='ADD'):
    root = Path(root); original = s.collection.inventory(root)
    transition.publication.validate(root, size=size, kind=kind)
    replay = s.Replay(root, size=size, kind=kind)
    for index in range(1, 12): replay.step(index)
    replay.publication_receipts = transition.publication.CheckpointReceipts(root, replay)
    history = placement.History(root, replay); history.run()
    owner = placement.Placement(root, history); owner.run()
    handoff = retirement.Retirement(root, owner); handoff.run()
    result = Initialization(root, handoff).run()
    need(s.collection.inventory(root) == original, 'joining original changed during initialization replay')
    return result


NEGATIVES = {
    'head-wrong-endpoint': 'joining initialization exact original head exchange',
    'head-foreign-owner': 'joining initialization exact original head exchange',
    'confirmed-learner-debt-lost': 'joining initialization exact confirmed learner plan',
    'reconcile-old-debt-lost': 'joining initialization exact reconciled peer plan',
    'old-peer-ledger-debt-lost': 'joining initialization exact old prepared inventory: node-1',
    'old-learner-ledger-debt-lost': 'joining initialization exact old prepared inventory: node-2',
    'old-premature-selection': 'joining initialization exact prepared grant suffix',
    'old-reused-source-id': 'joining initialization fresh original source identity',
    'old-changed-frozen-packet': 'joining initialization exact frozen grant bytes',
    'old-retained-source-removed': 'joining initialization exact old prepared inventory: node-1',
    'old-standalone-source-changed': 'joining initialization exact retained old source: node-2',
    'early-copy-changed': 'joining initialization exact early joining copy',
    'seed-changed': 'joining initialization exact derived seed',
    'initialized-peer-missing': 'joining derivation exact initial ledger: peer-retention.gspr',
    'initialized-learner-debt-lost': 'joining derivation exact initial ledger: learner-retention.gslr',
    'initialization-decision-changed': 'joining derivation exact original decision',
    'native-adopted-promise-changed': 'joining initialization exact prepared grant suffix',
    'native-new-promise-changed': 'joining initialization exact frozen grant bytes',
    'native-standalone-basis-changed': 'joining initialization exact native basis',
    'native-source-image-changed': 'joining initialization exact native family: replica',
    'native-extra-allocation': 'joining initialization exact native family: replica',
    'native-orphan-file': 'joining initialization exact native family: replica',
    'initialization-force-missing': 'joining initialization original transaction force order',
    'first-grant-force-reordered': 'joining initialization original first grant order',
    'repeated-basis-rewritten': 'joining initialization original repeated basis order',
    'reopen-before-initialization': 'joining initialization original lifecycle order',
}


def mutate(root, name, *, size=3, kind='ADD'):
    need(name in NEGATIVES, 'unknown joining initialization mutation')
    from .joining_profile_evidence import topology
    _, _, old, new = topology(str(size)+'-'+kind)
    joining = new[-1]
    root = Path(root); native = root/'joining-originals-native'; node1 = root/'before-joint-continuation/node-1'
    node2 = root/'before-joint-continuation/node-2'; replica = native/'replica'
    def json_edit(path, action):
        value = s.catalog.parse(path.read_bytes()); action(value); path.write_bytes(f.canonical(value))
    def ledger(path, module, action):
        value = module.decode(path.read_bytes()); action(value); path.write_bytes(module.frame(value))
    def grants(path, action):
        rows = disk.journal(path.read_bytes(), f.decode((path.parent/'node.gsr').read_bytes(), 'records', 'NODE')['root'], path.parent.name if path.parent != replica else joining)
        values = [(kind, value) for kind, _, value in rows]; action(values)
        path.write_bytes(b''.join(f.encode('records', kind, value) for kind, value in values))
    if name.startswith('head-'):
        def change(value):
            field, kind = ('response', 'LEARNER_HEAD_ACK') if name == 'head-wrong-endpoint' else ('request', 'LEARNER_HEAD_QUERY')
            frame = f.decode(base64.b64decode(value[0][field]), 'wire', kind)
            if name == 'head-wrong-endpoint': frame['payload']['endpoint']['cut']['index'] = 4
            else: frame['sender']['port'] += 1
            value[0][field] = placement.encoded(f.encode('wire', kind, frame))
        json_edit(root/'joining-head-wire.json', change)
    elif name == 'confirmed-learner-debt-lost': json_edit(root/'joining-confirmed-node-1.json', lambda v: v.pop('renewals'))
    elif name == 'reconcile-old-debt-lost': json_edit(root/'joining-floor-reconciled.json', lambda v: v['peers'][0].pop('renewals'))
    elif name == 'old-peer-ledger-debt-lost': ledger(node1/PEERS, peers, lambda v: v['plan']['peers'][0].pop('renewals'))
    elif name == 'old-learner-ledger-debt-lost': ledger(node2/learner.FILE, learner, lambda v: v['plan'].pop('renewals'))
    elif name == 'old-premature-selection':
        def select(values):
            basis = values[-1][1]; sources = []
            for node, directory in [(n, root/'before-joint-continuation'/n) for n in old[:size//2+1]]+[(joining, replica)]:
                raw = next(raw for kind, raw, _ in reversed(disk.journal((directory/'grants.gsr').read_bytes(), basis['root'], node)) if kind == 'BASIS')
                value = f.decode(raw, 'records', 'BASIS'); sources.append(dict(voter=node, basisId=value['basisId'], basisDigest=sha(raw)))
            values.append(('SELECTED', dict(root=basis['root'], view=basis['view'], ballot=basis['ballot'], cut=basis['cut'], nextEntry=None, sources=sources)))
        grants(node1/'grants.gsr', select)
    elif name == 'old-reused-source-id':
        def reuse(v):
            for _, value in v[-2:]: value['basisId'] = v[0][1]['basisId']
        grants(node1/'grants.gsr', reuse)
    elif name == 'old-changed-frozen-packet':
        def alter(values):
            value = values[-1][1]; path = node1/'sources'/value['basisId']/'source.gscp'; packet = disk.p.decode(path.read_bytes())
            extra = f.encode('records', 'ALLOCATOR', dict(root=value['root'], node='node-1', counter=123))
            raw = disk.packet_bytes(packet['capsule'], dict(packet['objects'], **{sha(extra): extra}), packet['images']); path.write_bytes(raw)
            changed = disk.p.decode(raw); value.update(capsule=sha(changed['capsuleBytes']), inventory=sha(changed['indexBytes']))
        grants(node1/'grants.gsr', alter)
    elif name == 'old-retained-source-removed':
        identifier = disk.journal((node1/'grants.gsr').read_bytes(), f.decode((node1/'node.gsr').read_bytes(), 'records', 'NODE')['root'], 'node-1')[0][2]['basisId']
        shutil.rmtree(node1/'sources'/identifier)
    elif name == 'old-standalone-source-changed': (root/'joining-retention-node-2.gscp').write_bytes(b'changed packet')
    elif name == 'early-copy-changed': (root/'joining-early-generation.gsr').write_bytes(b'changed generation')
    elif name == 'seed-changed': json_edit(root/'joining-retention-seed.json', lambda v: v['sources'].reverse())
    elif name == 'initialized-peer-missing': ledger(replica/PEERS, peers, lambda v: v['plan']['peers'].pop(2))
    elif name == 'initialized-learner-debt-lost': ledger(replica/learner.FILE, learner, lambda v: v['plan']['possible'].pop(0))
    elif name == 'initialization-decision-changed':
        path = replica/retention.DECISION; body = path.read_bytes()[44:]; path.write_bytes(retention.framed(0x47534a52, body+b'x'))
    elif name in ('native-adopted-promise-changed', 'native-new-promise-changed'):
        def change_promise(values):
            if name == 'native-adopted-promise-changed': values[0][1]['ballot']['counter'] -= 1
            else:
                for _, value in values[-2:]: value['ballot']['counter'] += 1
        grants(replica/'grants.gsr', change_promise)
    elif name == 'native-standalone-basis-changed':
        path = root/'joining-native-basis.gsr'; value = f.decode(path.read_bytes(), 'records', 'BASIS'); value['ballot']['counter'] += 1
        path.write_bytes(f.encode('records', 'BASIS', value))
    elif name == 'native-source-image-changed': next((replica/'sources').glob('*/*.image')).write_bytes(b'changed image')
    elif name == 'native-extra-allocation':
        path = replica/'allocator.gsr'; value = f.decode(path.read_bytes(), 'records', 'ALLOCATOR'); value['counter'] += 1
        path.write_bytes(f.encode('records', 'ALLOCATOR', value))
    elif name == 'native-orphan-file': (replica/'unowned.bin').write_bytes(b'unowned')
    elif name in ('initialization-force-missing', 'first-grant-force-reordered', 'repeated-basis-rewritten', 'reopen-before-initialization'):
        def change_events(events):
            def at(scope, event): return next(i for i, v in enumerate(events) if v.get('scope') == scope and v.get('event') == event)
            if name == 'initialization-force-missing': events.pop(at('initial-owner', 'JOINING_RETENTION_DONE_PARENT_FORCED'))
            elif name == 'first-grant-force-reordered':
                a, b = at('retaining-owner', 'BASIS_FORCED'), at('retaining-owner', 'SOURCE_DIRECTORY_FORCED'); events[a], events[b] = events[b], events[a]
            elif name == 'repeated-basis-rewritten':
                pos = at('repeated-basis-owner', 'CURRENT_BEFORE_CAPTURE'); events.insert(pos+1, dict(node=joining, scope='repeated-basis-owner', event='BASIS_FORCED'))
            else:
                row = events.pop(at('repeated-basis-owner', 'CURRENT_VALIDATED')); events.insert(at('initial-owner', 'JOINING_RETENTION_BEFORE_RETURN'), row)
        path = root/'events.json'; events = json.loads(path.read_bytes()); change_events(events); path.write_bytes(f.canonical(events))
    rows = s.catalog.parse((native/'inventory.json').read_bytes())
    for row in rows:
        for member in row.get('files', []):
            path = native/row['name']/member['name']
            if path.is_file(): member['identity'].update(size=path.stat().st_size, sha256=sha(path.read_bytes()))
        if name == 'native-orphan-file' and row['name'] == 'replica':
            raw = (replica/'unowned.bin').read_bytes()
            row['files'].append(dict(name='unowned.bin', identity=dict(key='negative-unowned-inode', size=len(raw), sha256=sha(raw))))
            row['files'].sort(key=lambda v: v['name'])
    (native/'inventory.json').write_bytes(f.canonical(rows))


def qualify(root):
    root = Path(root); original = validate(root); results = []
    for name, reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-joining-initialization-negative-') as temp:
            copied = Path(temp)/'raw'; shutil.copytree(root, copied); mutate(copied, name)
            retirement.validate(copied)
            try: validate(copied)
            except ValueError as error: need(str(error) == reason, 'joining unrelated initialization negative: '+name+': '+str(error))
            else: raise ValueError('joining initialization mutation accepted: '+name)
        results.append(dict(case=name, status='REJECTED', reason=reason, retirementGate='PASS'))
    return dict(original=original, negatives=results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--qualify', action='store_true'); args = parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root), sort_keys=True))
