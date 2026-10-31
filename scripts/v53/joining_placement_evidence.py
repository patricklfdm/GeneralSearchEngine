"""Derive the original joining placement from the composed old-voter history.

Recorded paths and inode keys are observations, never files opened by replay.
Every payload, generation and ownership record below is reconstructed before
comparison. Retirement, native initialization and full causal replay are later
boundaries, not implied by a complete placed inventory.
"""
import argparse
import base64
import copy
import json
from pathlib import Path, PurePosixPath
import shutil
import struct
import tempfile

from . import joining_transition_evidence as transition
from . import joining_snapshot as snapshot
from . import learner_typed_evidence as typed

s, f, disk, need, sha = transition.s, transition.f, transition.disk, transition.need, transition.sha
MOVES = ('genesis.gsr', 'allocator.gsr', 'grants.gsr', 'pending.accept', 'sources', 'generations', 'selector.gsr')
CUSTODY_ROOTS = ('initialTyped', 'intent', 'operation', 'pendingIntent', 'replica', 'slotTyped',
                 'slots', 'successor', 'successorTyped', 'voterStage')
PRESENT = {'custody', 'initialTyped', 'intent', 'operation', 'pendingIntent', 'placement', 'replica', 'voterStage'}


def encoded(raw): return base64.b64encode(raw).decode()


def metadata_frame(kind, value):
    body = f.canonical(value); header = struct.pack('>4sHHHHI', b'GSLP', 1, 3, kind, 0, len(body))
    return header + bytes.fromhex(sha(header+body)) + body


def inventory(files):
    return [dict(path=name, size=len(raw), sha256=sha(raw)) for name, raw in sorted(files.items()) if raw is not None]


def moved(name): return any(name == part or name.startswith(part+'/') for part in MOVES)


def adopted(original, identity, certificate, root_bytes):
    """The exact dormant joined generation; no selected basis or owned tail."""
    packet = disk.p.decode(original['source.gscp']); cap = packet['capsule']
    value = f.decode(certificate, 'records', 'CERTIFICATE')
    promise = f.encode('records', 'PROMISE', dict(root=cap['root'], view=value['authority'], ballot=value['ballot'], basisId=None))
    allocator = f.encode('records', 'ALLOCATOR', dict(root=cap['root'], node=identity['node'], counter=value['ballot']['counter']))
    members = {'source.gscp': original['source.gscp'], 'promise.gsr': promise, 'adopted-certificate.gsr': certificate,
               **{name: raw for name, raw in original.items() if name.endswith('.image') or name == 'ancestry.gsr'}}
    manifest = dict(root=cap['root'], node=identity['node'], generation='a', cut=cap['cut'], application=cap['application'],
        catalog=cap['catalog'], capsule=sha(packet['capsuleBytes']), promise=sha(promise), basis=None, selection=None,
        ownedTail=None, files=inventory(members))
    members['generation.gsr'] = f.encode('records', 'GENERATION', manifest)
    selector = f.encode('records', 'SELECTOR', dict(root=cap['root'], node=identity['node'], generation='a', digest=sha(members['generation.gsr'])))
    need(packet['objects'].get(sha(root_bytes)) == root_bytes, 'joining placement original ROOT object')
    return {'replica.lock': b'', 'root.gsr': root_bytes, 'genesis.gsr': packet['objects'][cap['initial']],
        'node.gsr': f.encode('records', 'NODE', dict(root=cap['root'], identity=identity)), 'allocator.gsr': allocator,
        'grants.gsr': promise, 'pending.accept': disk.EMPTY, 'selector.gsr': selector, 'sources': None, 'generations': None,
        'generations/a': None, **{'generations/a/'+name: raw for name, raw in members.items()}}


class History(transition.History):
    def __init__(self, root, replay):
        self.sources = {}
        super().__init__(root, replay)

    def match(self, label, group):
        super().match(label, group)
        if label in ('published-4', 'published-8', 'published-9'):
            files = group['node-1']; prefix, _, _ = disk.current(files)
            self.sources[int(label.split('-')[1])] = {name[len(prefix):]: raw for name, raw in files.items() if name.startswith(prefix)}


class Placement:
    def __init__(self, root, history):
        self.root, self.history, self.replay = Path(root), history, history.replay
        self.snap = snapshot.read(self.root/'joining-originals-placed', stage='placed')
        need({name for name, row in self.snap.identities.items() if row['present']} == PRESENT, 'joining placement present roots')
        self.expected = {name: {'.': None} for name in PRESENT}
        self.identities = {name: {v['name']: v['identity'] for v in row.get('files', [])} for name, row in self.snap.identities.items()}
        self.state = self.replay.states[9]; self.operation = next(row for row in self.state['results'] if row['request']['number'] == self.state['active'])
        self.request = self.operation['request']; self.joining = s.catalog.identities(self.state['identities'])[self.replay.joining]
        self.peer = s.catalog.identities(self.state['identities'])['node-1']
        prepared = self.replay.states[4]['results'][0]['prepared']
        self.receipt = f.encode('records', 'LEARNER', dict(root=self.replay.root, receipt=dict(root=self.replay.root,
            number=self.request['number'], request=sha(f.canonical(self.request)), identity=self.joining,
            image=prepared['application'], prepared=prepared)))
        descriptor = s.catalog.parse((self.root/'original-plan.gsbp').read_bytes()[48:])['descriptor']
        self.configuration = {key: descriptor[key] for key in ('application', 'core')}
        self.plan = None

    def binding(self, family): return self.snap.identities[family]['path']

    def key(self, family, name='.'):
        need(name in self.identities[family], 'joining placement original identity missing')
        return self.identities[family][name]['key']

    def bytes(self, family, name): return self.snap.member(family, name)

    def fingerprint(self, family, name, raw): return dict(key=self.key(family, name), size=len(raw), sha256=sha(raw))

    def match(self, family):
        actual = {v['name']: None if 'directory' in v['identity'] else self.bytes(family, v['name'])
                  for v in self.snap.identities[family]['files']}
        need(actual == self.expected[family], 'joining placement exact family: '+family)

    def source(self, family, prefix, index):
        self.expected[family][prefix] = None
        self.expected[family].update({prefix+'/'+name: raw for name, raw in self.history.sources[index].items()})

    def original_rows(self, family, prefix, files):
        return [dict(row, key=self.key(family, prefix+row['path'])) for row in inventory(files)]

    def scratch(self, value):
        path = snapshot.path_binding(value)
        for row in self.snap.identities.values():
            other = PurePosixPath(row['path']['path'])
            need(path != other and path not in other.parents and other not in path.parents, 'joining placement scratch overlaps original')
        return value

    def paths(self):
        parent = PurePosixPath(self.binding('operation')['path']).parent
        prefixes = dict(initialTyped='learner-', intent='learner-intent-', pendingIntent='learner-pending-intent-',
            voterStage='learner-voter-', custody='learner-custody-', placement='learner-placement-', retirement='learner-retired-',
            nativeOwner='joined-owner-', slots='learner-slots-', slotTyped='learner-slot-b-', successor='learner-successor-', successorTyped='learner-ready-')
        for family, prefix in prefixes.items():
            need(PurePosixPath(self.binding(family)['path']) == parent/('.gse-v53-'+prefix+self.plan),
                 'joining placement deterministic sidecar path')
            for field in ('parentFileKey', 'fileStoreName', 'fileStoreType'):
                need(self.binding(family)[field] == self.binding('operation')[field], 'joining placement original parent identity')
        for field in ('fileStoreName', 'fileStoreType'):
            need(self.binding('replica')[field] == self.binding('voterStage')[field], 'joining placement atomic move filesystem')

    def preparation(self):
        original = self.history.sources[4]; packet = disk.p.decode(original['source.gscp'])
        plan = dict(schema='gse-v53-learner-plan/1.3', root=encoded(self.replay.root_bytes), learner=self.joining,
            request=self.request, source=self.peer, cut=packet['capsule']['cut'], generation=encoded(original['generation.gsr']),
            files=inventory(original), paths=[self.binding('operation'), self.binding('replica')])
        raw = metadata_frame(1, plan); self.plan = sha(raw); self.paths()
        # The receiver path is an original observation. Its bytes and moved inode
        # set are reconstructed from the governing source and retained inventory.
        old = s.catalog.parse(self.bytes('operation', 'learner-source.gslp')[48:])
        retained = metadata_frame(2, dict(schema='gse-v53-learner-retention/1.3', plan=self.plan,
            staging=self.scratch(old['staging']), directoryKey=self.key('replica', 'learner'),
            files=self.original_rows('replica', 'learner/', original)))
        self.expected['operation'].update({'operation.lock': b'', 'learner.gslp': raw, 'learner-source.gslp': retained})
        self.source('replica', 'learner', 4)
        self.expected['replica'].update({'root.gsr': self.replay.root_bytes,
            'node.gsr': f.encode('records', 'NODE', dict(root=self.replay.root, identity=self.joining)),
            'replica.lock': b'', 'learner-admission.gslp': retained})
        preparation = f.canonical(dict(schema='gse-v53-learner-typed/1.3', plan=self.plan, source=sha(original['source.gscp']),
            receipt=encoded(self.receipt), configuration=self.configuration, path=self.binding('initialTyped'),
            materialization=self.binding('materialization'), directoryKey=self.key('initialTyped')))
        backup = typed.images.image_members(self.replay.image)
        marker = f.canonical(dict(schema='gse-v53-learner-prepared/1.3', root=self.replay.root, identity=self.joining, plan=self.plan,
            typedPlan=sha(preparation), source=sha(original['source.gscp']), receipt=sha(self.receipt),
            location=self.binding('replica')['path']+'/learner'))
        self.expected['initialTyped'].update({'preparation.lock': b'', 'preparation.json': preparation, 'learner.gsr': self.receipt,
            'prepared.json': marker, 'backup': None, **{'backup/'+name: data for name, data in backup.items()}})
        self.match('operation'); self.match('initialTyped')

    def disposition(self, family, index, extra):
        original = self.history.sources[4]; cap = disk.p.decode(original['source.gscp'])['capsule']
        name = 'pending-intent.json' if family == 'pendingIntent' else 'intent.json'
        observed = s.catalog.parse(self.bytes(family, name))
        raw = f.canonical(dict(schema='gse-v53-learner-'+('pending-intent' if family == 'pendingIntent' else 'intent')+'/1.3',
            plan=self.plan, request=self.request, learner=self.joining, anchor=dict(disk.anchor(cap), source=sha(original['source.gscp'])),
            peer=self.peer, path=self.binding(family), staging=self.scratch(observed['staging']), sourceKey=self.key(family, 'source'),
            files=self.original_rows(family, 'source/', self.history.sources[index]), receipt=sha(self.receipt), **extra))
        self.source(family, 'source', index); self.expected[family][name] = raw
        return raw

    def pending_and_intent(self):
        parts = self.replay.phases[8]
        statement = f.encode('records', 'CHECKPOINT', self.replay.checkpoint(8, 9, 'MEMBERSHIP'))
        pending = dict(schema='gse-v53-joining-intent-metadata/1.3', root=self.replay.root, owner=self.peer, learner=self.joining,
            request=self.request, parent=dict(cut=self.replay.states[8]['cut'], catalog=sha(self.replay.catalogs[8]), application=sha(self.replay.image)),
            target=dict(cut=self.state['cut'], catalog=sha(self.replay.catalogs[9]), application=sha(self.replay.image)),
            records={kind: encoded(raw) for kind, raw in dict({k: parts[k] for k in ('ENTRY', 'ACCEPT', 'PROOF', 'CERTIFICATE')},
                CATALOG=self.replay.catalogs[9], CHECKPOINT=statement).items()}, payload=encoded(parts['PAYLOAD']))
        raw = self.disposition('pendingIntent', 8, dict(pending=pending))
        ack = f.encode('records', 'CHECKPOINT_ACK', dict(root=self.replay.root, voter=self.replay.joining, incarnation=self.joining['storage'],
            cut=self.state['cut'], statement=sha(statement)))
        marker = f.canonical(dict(schema='gse-v53-joining-retained-source/1.3', plan=sha(raw), planKey=self.key('pendingIntent', 'pending-intent.json'),
            sourceKey=self.key('pendingIntent', 'source'), receipt=sha(self.receipt), ack=sha(ack), ackKey=self.key('pendingIntent', 'joining-ack.gsr'),
            markerKey=self.key('pendingIntent', 'retained-source.json')))
        self.expected['pendingIntent'].update({'joining-ack.gsr': ack, 'retained-source.json': marker})
        self.link = dict(directory=self.binding('pendingIntent')['path'], directoryKey=self.key('pendingIntent'),
            plan=sha(raw), planKey=self.key('pendingIntent', 'pending-intent.json'), sourceKey=self.key('pendingIntent', 'source'),
            receipt=sha(self.receipt), ack=sha(ack), ackKey=self.key('pendingIntent', 'joining-ack.gsr'),
            marker=sha(marker), markerKey=self.key('pendingIntent', 'retained-source.json'))
        self.disposition('intent', 9, dict(pendingSource=self.link)); self.match('pendingIntent'); self.match('intent')

    def stage(self):
        files = adopted(self.history.sources[9], self.joining, self.replay.phases[8]['CERTIFICATE'], self.replay.root_bytes)
        self.installed = dict(files)
        raw = f.canonical(dict(schema='gse-v53-learner-voter-stage/1.3', plan=self.plan, path=self.binding('voterStage'),
            directoryKey=self.key('voterStage'), replica=self.binding('replica'), receipt=sha(self.receipt),
            source=sha(self.history.sources[9]['source.gscp']), generation=sha(files['generations/a/generation.gsr']),
            promise=sha(files['grants.gsr']), allocator=sha(files['allocator.gsr']), files=inventory(files)))
        files['voter-plan.json'] = raw
        def key(name): return self.key('replica' if moved(name) else 'voterStage', name)
        ready = f.canonical(dict(schema='gse-v53-learner-voter-ready/1.3', plan=sha(raw),
            directories=[dict(path=name, key=key(name)) for name, data in sorted(files.items()) if data is None],
            files=[dict(row, key=key(row['path'])) for row in inventory(files)]))
        files['voter-ready.json'] = ready
        self.expected['replica'].update({name: raw for name, raw in files.items() if moved(name)})
        self.expected['voterStage'].update({name: raw for name, raw in files.items() if not moved(name)})
        self.match('replica'); self.match('voterStage')

    def ownership(self):
        # Reverse only the fixed atomic moves, retaining recorded ORIGINAL keys.
        # Rebuild hashes from derived payloads; custody is not allowed to attest
        # to itself or to introduce an unrelated sidecar into the transaction.
        before = copy.deepcopy(self.expected)
        for name in list(before['replica']):
            if moved(name): before['voterStage'][name] = before['replica'].pop(name)
        roots = []
        for family in CUSTODY_ROOTS:
            row = dict(name=family, path=self.binding(family), present=family in PRESENT)
            if row['present']:
                entries = []
                for name, raw in sorted(before[family].items()):
                    at = 'replica' if family == 'voterStage' and moved(name) else family
                    identity = dict(key=self.key(at, name), directory=True) if raw is None else self.fingerprint(at, name, raw)
                    entries.append(dict(name=name, identity=identity))
                row['files'] = entries
            roots.append(row)
        custody = f.canonical(dict(schema='gse-v53-learner-custody/1.3', plan=self.plan, path=self.binding('custody'),
            receipt=sha(self.receipt), source=sha(self.history.sources[9]['source.gscp']), roots=roots,
            pendingSource=self.link, directoryKey=self.key('custody')))
        self.expected['custody']['custody.json'] = custody; self.match('custody')
        plan = f.canonical(dict(schema='gse-v53-learner-placement/1.3', plan=self.plan, path=self.binding('placement'),
            directoryKey=self.key('placement'), custody=self.fingerprint('custody', 'custody.json', custody), moves=list(MOVES)))
        ready = f.canonical(dict(schema='gse-v53-learner-placed/1.3', plan=sha(plan), planKey=self.key('placement', 'placement.json'),
            custody=sha(custody), moves=list(MOVES)))
        files = self.installed; parts = self.replay.phases[8]
        joined = f.canonical(dict(schema='gse-v53-joined-admission/1.3', root=self.replay.root, identity=self.joining, plan=self.plan,
            replica=self.binding('replica'), materialization=self.binding('materialization'), configuration=sha(f.canonical(self.configuration)),
            preparationSource=sha(self.history.sources[4]['source.gscp']), receipt=encoded(self.receipt),
            sealed={k: self.operation[k] for k in ('request', 'prepared', 'receipt')}, intent=encoded(parts['ENTRY']),
            certificate=encoded(parts['CERTIFICATE']), source=sha(self.history.sources[9]['source.gscp']), cut=self.state['cut'],
            generation=sha(files['generations/a/generation.gsr']), promise=sha(files['grants.gsr']), allocator=sha(files['allocator.gsr']),
            custody=self.fingerprint('custody', 'custody.json', custody), placement=self.fingerprint('placement', 'placed.json', ready),
            recordKey=self.key('placement', 'joined.json')))
        self.expected['placement'].update({'placement.json': plan, 'placed.json': ready, 'joined.json': joined}); self.match('placement')

    def run(self):
        self.preparation(); self.pending_and_intent(); self.stage(); self.ownership()
        return dict(status='PASS', scope='native-'+self.replay.kind+'-original-joining-placement', placedRoots=len(PRESENT),
            comparedFiles=sum(raw is not None for files in self.expected.values() for raw in files.values()),
            oldOwnerSnapshots=self.history.comparisons, joiningPlacementPhysicalQualified=True,
            nativeInitializationQualified=False, completePhysicalQualified=False, forceAndNetworkQualified=False,
            processDeathQualified=False, phase3Complete=False)


def validate(root, *, size=3, kind='ADD'):
    root = Path(root); original = s.collection.inventory(root)
    transition.publication.validate(root, size=size, kind=kind)
    replay = s.Replay(root, size=size, kind=kind)
    for index in range(1, 12): replay.step(index)
    replay.publication_receipts = transition.publication.CheckpointReceipts(root, replay)
    history = History(root, replay); history.run()
    result = Placement(root, history).run()
    need(s.collection.inventory(root) == original, 'joining original changed during placement replay')
    return result


NEGATIVES = {
    'learner-source-replaced': 'joining placement exact family: replica',
    'typed-configuration': 'joining placement exact family: initialTyped',
    'typed-prepared-location': 'joining placement exact family: initialTyped',
    'pending-original-catalog': 'joining placement exact family: pendingIntent',
    'pending-retained-inode': 'joining placement exact family: pendingIntent',
    'intent-old-source': 'joining placement exact family: intent',
    'intent-pending-link': 'joining placement exact family: intent',
    'adopted-certificate': 'joining placement exact family: replica',
    'adopted-ancestry-lost': 'joining placement original identity missing',
    'adopted-manifest-forgery': 'joining placement exact family: replica',
    'premature-peer-ledger': 'joining placement exact family: replica',
    'stage-orphan': 'joining placement exact family: voterStage',
    'moved-inode-replaced': 'joining placement exact family: voterStage',
    'custody-missing-pending': 'joining placement exact family: custody',
    'custody-move-inode': 'joining placement exact family: custody',
    'placement-move-order': 'joining placement exact family: placement',
    'placement-plan-inode': 'joining placement exact family: placement',
    'joined-old-source': 'joining placement exact family: placement',
    'joined-configuration': 'joining placement exact family: placement',
    'joined-record-inode': 'joining placement exact family: placement',
}


def mutate(root, name):
    """Disposable copies only; update the inventory to pass the earlier gate."""
    need(name in NEGATIVES, 'unknown joining placement mutation')
    path = Path(root)/'joining-originals-placed'
    def change_json(relative, edit):
        file = path/relative; value = s.catalog.parse(file.read_bytes()); edit(value); file.write_bytes(f.canonical(value))
    if name == 'learner-source-replaced':
        file = path/'replica/learner/promise.gsr'; value = f.decode(file.read_bytes(), 'records', 'PROMISE')
        value['ballot']['counter'] += 1; file.write_bytes(f.encode('records', 'PROMISE', value))
    elif name == 'typed-configuration':
        change_json('initialTyped/preparation.json', lambda v: v['configuration']['core'].update(codecVersion=2))
    elif name == 'typed-prepared-location':
        change_json('initialTyped/prepared.json', lambda v: v.update(location=v['location']+'-copy'))
    elif name == 'pending-original-catalog':
        change_json('pendingIntent/pending-intent.json', lambda v: v['pending']['target'].update(catalog='0'*64))
    elif name == 'pending-retained-inode':
        change_json('pendingIntent/retained-source.json', lambda v: v.update(ackKey='copied-inode'))
    elif name == 'intent-old-source':
        (path/'intent/source/source.gscp').write_bytes((path/'pendingIntent/source/source.gscp').read_bytes())
    elif name == 'intent-pending-link':
        change_json('intent/intent.json', lambda v: v['pendingSource'].update(sourceKey='copied-inode'))
    elif name == 'adopted-certificate':
        file = path/'replica/generations/a/adopted-certificate.gsr'; value = f.decode(file.read_bytes(), 'records', 'CERTIFICATE')
        value['ballot']['counter'] += 1; file.write_bytes(f.encode('records', 'CERTIFICATE', value))
    elif name == 'adopted-ancestry-lost': (path/'replica/generations/a/ancestry.gsr').unlink()
    elif name == 'adopted-manifest-forgery':
        file = path/'replica/generations/a/generation.gsr'; value = f.decode(file.read_bytes(), 'records', 'GENERATION')
        value['promise'] = '0'*64; raw = f.encode('records', 'GENERATION', value); file.write_bytes(raw)
        selector = path/'replica/selector.gsr'; value = f.decode(selector.read_bytes(), 'records', 'SELECTOR'); value['digest'] = sha(raw)
        selector.write_bytes(f.encode('records', 'SELECTOR', value))
        change_json('placement/joined.json', lambda v: v.update(generation=sha(raw)))
        change_json('voterStage/voter-plan.json', lambda v: v.update(generation=sha(raw)))
    elif name == 'premature-peer-ledger': (path/'replica/peer-retention.gspr').write_bytes(b'uninitialized peer ledger')
    elif name == 'stage-orphan': (path/'voterStage/unowned.bin').write_bytes(b'foreign')
    elif name == 'moved-inode-replaced': pass  # Mutate the original identity observation below.
    elif name == 'custody-missing-pending':
        change_json('custody/custody.json', lambda v: v.update(roots=[r for r in v['roots'] if r['name'] != 'pendingIntent']))
    elif name == 'custody-move-inode':
        def moved_key(v):
            row = next(r for r in v['roots'] if r['name'] == 'voterStage')
            next(r for r in row['files'] if r['name'] == 'generations/a')['identity']['key'] = 'copied-inode'
        change_json('custody/custody.json', moved_key)
    elif name == 'placement-move-order':
        change_json('placement/placement.json', lambda v: v.update(moves=list(reversed(v['moves']))))
    elif name == 'placement-plan-inode':
        change_json('placement/placed.json', lambda v: v.update(planKey='copied-inode'))
    elif name == 'joined-old-source':
        change_json('placement/joined.json', lambda v: v.update(source=v['preparationSource']))
    elif name == 'joined-configuration':
        change_json('placement/joined.json', lambda v: v.update(configuration='0'*64))
    elif name == 'joined-record-inode':
        change_json('placement/joined.json', lambda v: v.update(recordKey='copied-inode'))
    rows = s.catalog.parse((path/'inventory.json').read_bytes())
    for row in rows:
        if not row['present']: continue
        files = []
        for member in row['files']:
            file = path/row['name']/member['name']
            if not file.exists(): continue
            if file.is_file(): member['identity'].update(size=file.stat().st_size, sha256=sha(file.read_bytes()))
            if name == 'moved-inode-replaced' and row['name'] == 'replica' and member['name'] == 'generations/a':
                member['identity']['key'] = 'copied-original-directory-inode'
            files.append(member)
        extra = 'peer-retention.gspr' if name == 'premature-peer-ledger' and row['name'] == 'replica' else (
            'unowned.bin' if name == 'stage-orphan' and row['name'] == 'voterStage' else None)
        if extra:
            data = (path/row['name']/extra).read_bytes()
            files.append(dict(name=extra, identity=dict(key='negative-extra-original', size=len(data), sha256=sha(data))))
        row['files'] = sorted(files, key=lambda v: v['name'])
    (path/'inventory.json').write_bytes(f.canonical(rows))


def qualify(root):
    root = Path(root); original = validate(root); results = []
    for name, reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-joining-placement-negative-') as temp:
            copied = Path(temp)/'raw'; shutil.copytree(root, copied); mutate(copied, name)
            transition.validate(copied)
            try: validate(copied)
            except ValueError as error: need(str(error) == reason, 'joining unrelated placement negative: '+name+': '+str(error))
            else: raise ValueError('joining placement mutation accepted: '+name)
        results.append(dict(case=name, status='REJECTED', reason=reason, transitionGate='PASS'))
    return dict(original=original, negatives=results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--qualify', action='store_true'); args = parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root), sort_keys=True))
