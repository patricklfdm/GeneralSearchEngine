"""Original physical replay of a bounded automatic two-campaign history.

PARTIAL is deliberate: reconstruct every retained filesystem snapshot and the
authenticated fence/READY boundaries. Complete transfer and force-order replay
across both campaigns is a separate gate; producer success cannot supply it.
"""
import argparse
import base64
import copy
import json
from pathlib import Path
import shutil
import struct
import tempfile
import uuid
from . import authority_transition_evidence as t

n, b, c, e, f, need = t.d, t.b, t.c, t.e, t.f, t.need
VOTERS = ('node-1', 'node-2')


def unselected_prepare(root, files, ballot):
    """A slow selected peer can leave a real, unused node-3 promise/source.

    Observe only the presence and fresh UUID; derive its full original bytes.
    Neither this unused basis nor its reply may alter the selected pair.
    """
    actual = c.inventory(root/'installed-2/node-3')
    if actual['grants.gsr'] == files['grants.gsr']: return files
    _, members, packet = c.current(files); cap = packet['capsule']
    prior = c.journal(files['grants.gsr'], cap['root'], 'node-3')
    journal = c.journal(actual['grants.gsr'], cap['root'], 'node-3')
    need(journal[:len(prior)] == prior and [row[0] for row in journal[len(prior):]] == ['PROMISE','BASIS'],
         'automatic restart unused capture history')
    identifier = journal[-2][2]['basisId']
    need(str(uuid.UUID(identifier)) == identifier and identifier not in {row[2].get('basisId') for row in prior},
         'automatic restart fresh unused source')
    value = dict(root=cap['root'], view=e.authority(cap['root'], cap['cut']['view']), ballot=ballot, basisId=identifier)
    promise = f.encode('records', 'PROMISE', value); wrapper = n.s.s.wrap(promise, files[n.s.FILE])
    raw = c.packet_bytes(cap, dict(packet['objects'], **{e.digest(wrapper):wrapper}), packet['images']); frozen = e.p.decode(raw)
    basis = f.encode('records', 'BASIS', dict(value, voter='node-3', cut=cap['cut'], capsule=e.digest(frozen['capsuleBytes']),
        inventory=e.digest(frozen['indexBytes']), accepted=None))
    source = 'sources/'+identifier
    return dict(files, **{'grants.gsr':files['grants.gsr']+promise+basis, source:None, source+'/source.gscp':raw},
        **{source+'/'+h+'.image':members[h+'.image'] for h in packet['images']})


def inventory(root):
    need(root.is_dir() and not root.is_symlink(), 'automatic restart regular inventory')
    total = 0
    for count, path in enumerate(root.rglob('*'), 1):
        need(not path.is_symlink() and (path.is_dir() or path.is_file()), 'automatic restart regular inventory')
        if path.is_file(): total += path.stat().st_size
        need(count <= 65536 and total <= 512*e.MIB, 'automatic restart bounded inventory')
    names = {'initial', 'original-plan.gsbp', 'original-application.image', 'before-network',
        'calls.json', 'events.json', 'wire.json', 'failures.json', 'restart-result.json',
        'first-ready', 'after-fence', 'second-ready', 'after-close', 'fence-request.gsw'}
    names |= {f'{label}-{i}' for label in ('applied', 'published') for i in (1, 2, 3)}
    names |= {f'installed-{i}' for i in (1, 2)} | {f'selected-{i}.gsr' for i in (1, 2)}
    b.selection.layout(root, names, 'automatic restart original history')


class Service(t.NativeSlot):
    voters = VOTERS

    def __init__(self, root, group):
        self.root = root; self.group = copy.deepcopy(group); self.active = list(VOTERS)
        self.slot = 0; self.counter = 2; self.first = None; self.documents = []
        self.required = set(); self.observed = set(); self.phases = {}; self.selection_anchor = None
        self.history = f.decode(group['node-1']['root.gsr'], 'records', 'ROOT')['historyId']

    def data_documents(self): return [(100, 'next-slot')]

    def required_anchors(self):
        anchors = super().required_anchors()
        if self.selection_anchor is not None and self.selection_anchor not in anchors:
            anchors.append(self.selection_anchor)
        return sorted(anchors, key=lambda value: value['cut']['index'])

    def campaign(self, number, counter):
        # Source UUIDs are observations; all grant, selected, generation and
        # retention bytes are derived from the preceding original group.
        if number == 2:
            self.group = t.maintenance(self.group, VOTERS)
        _, _, installed = n.s.campaign(self.root, {v: self.group[v] for v in VOTERS},
            counter, f'installed-{number}', selected_prefix=n.slot.prefix)
        self.group = dict(self.group, **installed)
        if number == 2:
            ballot = f.decode(installed['node-1']['allocator.gsr'], 'records', 'ALLOCATOR')
            identity = n.future.identity(installed['node-1'])
            self.group['node-3'] = unselected_prepare(self.root, self.group['node-3'],
                dict(counter=ballot['counter'], proposer='node-1', incarnation=identity['storage']))
        b.match(self.root, f'installed-{number}', self.group)
        _, members, packet = c.current(self.group['node-1'])
        need((self.root/f'selected-{number}.gsr').read_bytes() == members['selected.gsr'], 'automatic restart original selection')
        self.first = None; self.selection_anchor = c.anchor(packet['capsule'])

    def advance(self, kind):
        self.group = t.maintenance(self.group, VOTERS)
        text = b'100:next-slot'
        payload = b'\x01'+struct.pack('>HIII', 1, 1, 4, 100)+struct.pack('>I', len(text))+text if kind == 'DATA' else None
        self.publish(kind, payload)


def lifecycle(root):
    events = n.read(root/'events.json')
    held = [(i, row) for i, row in enumerate(events) if row['event'].startswith('ROUND_')]
    expected = ['INSTALLED', 'SLOT_BEGIN', 'SLOT_COMPLETE', 'BEFORE_READY']*2+['SLOT_BEGIN', 'SLOT_COMPLETE']
    need([v['event'] for _, v in held] == ['ROUND_'+v for v in expected], 'automatic restart lifecycle order')
    campaign = slot = 0; completion = None
    for at, row in held:
        need(set(row) == {'node','event','record','bytes'} and row['node'] == 'node-1', 'automatic restart event owner')
        raw = base64.b64decode(row['bytes'], validate=True)
        need(e.digest(raw) == row['record'], 'automatic restart event digest')
        if row['event'] == 'ROUND_INSTALLED':
            campaign += 1
            chosen = (root/f'selected-{campaign}.gsr').read_bytes(); selected = f.decode(chosen, 'records', 'SELECTED')
            need(raw == chosen, 'automatic restart installed event')
        elif row['event'] == 'ROUND_SLOT_BEGIN':
            slot += 1; entry = f.decode(raw, 'records', 'ENTRY')
            _, _, packet = c.current(c.inventory(root/f'published-{slot}/node-1'))
            need(entry['index'] == slot and entry['kind'] == ('DATA' if slot == 3 else 'BARRIER')
                 and entry['origin'] == selected['ballot'] and e.digest(raw) == packet['capsule']['cut']['entry'],
                 'automatic restart original entry')
        elif row['event'] == 'ROUND_SLOT_COMPLETE':
            ack = f.decode(raw, 'wire', 'PUBLISH_ACK'); files = c.inventory(root/f'published-{slot}/node-1')
            prefix, _, packet = c.current(files); own = n.future.identity(files)
            applied = c.inventory(root/f'applied-{slot}/node-1')
            expected = dict(certificate=e.digest(applied['applied-end/certificate.gsr']), selection=e.digest(chosen),
                published=c.anchor(packet['capsule']), generation=e.digest(files[prefix+'generation.gsr']))
            need(ack['root'] == selected['root'] and ack['view'] == selected['view'] and ack['ballot'] == selected['ballot']
                 and ack['sender'] == ack['recipient'] == own and ack['sequence'] == 1 and ack['payload'] == expected,
                 'automatic restart original completion')
            completion = raw
        else:
            need(slot == campaign and raw == completion, 'automatic restart readiness fresh barrier')
    return events, held


def fence(root, before, after, events, held):
    raw = (root/'fence-request.gsw').read_bytes(); request = f.decode(raw, 'wire', 'HEARTBEAT')
    ids = {node: n.future.identity(files) for node, files in before.items()}
    _, _, packet = c.current(before['node-2']); cap = packet['capsule']
    allocator = f.decode(after['node-2']['allocator.gsr'], 'records', 'ALLOCATOR')
    ballot = dict(counter=allocator['counter'], proposer='node-2', incarnation=ids['node-2']['storage'])
    need(request == dict(root=cap['root'], view=e.authority(cap['root'], cap['cut']['view']), ballot=ballot,
         sender=ids['node-2'], recipient=ids['node-1'], trace=request['trace'], sequence=1,
         payload=dict(cut=cap['cut'], activated=False)), 'automatic restart original fence')
    answer = f.encode('wire', 'HEARTBEAT_ACK', dict(request, sender=ids['node-1'], recipient=ids['node-2'], payload=dict(cut=cap['cut'])))
    rows = [row for row in n.read(root/'wire.json') if row['request'] == base64.b64encode(raw).decode()]
    need(rows == [dict(request=base64.b64encode(raw).decode(), response=base64.b64encode(answer).decode(), withheld=False)],
         'automatic restart exact fence reply')
    stamp = dict(node='node-1', event='WIRE_RESPONSE', request=e.digest(raw), response=e.digest(answer))
    response = [i for i, event in enumerate(events) if event == stamp]
    delivered = dict(node='node-2', event='NETWORK_RECEIVED', kind='HEARTBEAT_ACK', response=e.digest(answer))
    arrivals = [i for i, event in enumerate(events) if event == delivered]
    lower, upper = held[3][0], held[4][0]
    need(len(response) == len(arrivals) == 1 and lower < response[0] < arrivals[0] < upper,
         'automatic restart delivered fence between rounds')
    n.s.ordered([v['event'] for v in events[lower:response[0]] if v['node'] == 'node-2'],
        ['ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN'], 'automatic restart fence allocation')


def validate(root):
    root = Path(root); inventory(root)
    group = n.s.initialize(b.original(root, 3, False))
    group = {node: dict(files, **{n.future.FILE:n.future.frame(n.future.initial(files), {})}) for node, files in group.items()}
    b.match(root, 'before-network', group)
    service = Service(root, group); service.campaign(1, 2); service.advance('BARRIER')
    b.match(root, 'first-ready', service.group); before = copy.deepcopy(service.group)
    files = service.group['node-2']; allocator = f.decode(files['allocator.gsr'], 'records', 'ALLOCATOR')
    # The peer observed ballot 2 during PREPARE; a real reservation must exceed
    # both that observed counter and its own durable allocator.
    files['allocator.gsr'] = f.encode('records', 'ALLOCATOR', dict(allocator, counter=max(allocator['counter'], 2)+1))
    b.match(root, 'after-fence', service.group); after = copy.deepcopy(service.group)
    service.campaign(2, 4); service.advance('BARRIER'); b.match(root, 'second-ready', service.group)
    service.advance('DATA'); b.match(root, 'after-close', service.group)
    events, held = lifecycle(root); fence(root, before, after, events, held)
    need(n.read(root/'restart-result.json') == dict(status='PARTIAL', producerPassed=True, rounds=2, barriers=2,
         dataCalls=1, originalBudgetNanos=300_000_000_000, physicalReplay=False, phase3Complete=False), 'automatic restart producer scope')
    return dict(status='PARTIAL', scope='automatic-two-campaign-physical-replay', physicalReplay=True,
        campaigns=2, slots=3, snapshotGroups=14, nativeFence=True, fullWireReplay=False,
        processRestart=False, publicRuntime=False, phase3Complete=False)


NEGATIVES = {
    'initial-image': ('original-application.image', 'bootstrap original image binding'),
    'first-selection': ('selected-1.gsr', 'automatic restart original selection'),
    'fence-allocator': ('after-fence/node-2/allocator.gsr', 'admitted exact after-fence: node-2'),
    'fence-write': ('after-fence/node-1/allocator.gsr', 'admitted exact after-fence: node-1'),
    'second-selection': ('selected-2.gsr', 'automatic restart original selection'),
    'unused-source': ('installed-2/node-3/sources/extra', 'admitted exact installed-2: node-3'),
    'second-vote': ('applied-2/node-2/pending.accept', 'admitted exact applied-2: node-2'),
    'second-selector': ('published-2/node-1/selector.gsr', 'admitted exact published-2: node-1'),
    'third-ancestry': ('published-3/node-2/ancestry.gsr', 'admitted exact published-3: node-2'),
    'third-vote': ('applied-3/node-1/pending.accept', 'admitted exact applied-3: node-1'),
    'final-extra': ('after-close/node-3/extra', 'admitted exact after-close: node-3'),
    'missing-ready': (None, 'automatic restart lifecycle order'),
    'stale-ready': (None, 'automatic restart readiness fresh barrier'),
    'fence-cut': (None, 'automatic restart original fence'),
    'missing-fence-reply': (None, 'automatic restart exact fence reply'),
    'late-fence-delivery': (None, 'automatic restart delivered fence between rounds'),
    'missing-allocation-force': (None, 'selected retention force order: automatic restart fence allocation'),
    'forged-scope': (None, 'automatic restart producer scope'),
}


def mutate(root, name):
    file = NEGATIVES[name][0]
    if file is not None: (root/file).write_bytes(b'changed original'); return
    events = n.read(root/'events.json')
    ready = [row for row in events if row['event'] == 'ROUND_BEFORE_READY']
    request = (root/'fence-request.gsw').read_bytes(); digest = e.digest(request)
    response = next(row for row in events if row['event'] == 'WIRE_RESPONSE' and row.get('request') == digest)['response']
    if name == 'missing-ready': events.remove(ready[1])
    elif name == 'stale-ready': ready[1].update(record=ready[0]['record'], bytes=ready[0]['bytes'])
    elif name == 'fence-cut':
        value = f.decode(request, 'wire', 'HEARTBEAT'); value['payload']['cut']['index'] += 1
        (root/'fence-request.gsw').write_bytes(f.encode('wire', 'HEARTBEAT', value))
    elif name == 'missing-fence-reply':
        rows = n.read(root/'wire.json'); rows = [row for row in rows if row['request'] != base64.b64encode(request).decode()]
        (root/'wire.json').write_bytes(f.canonical(rows))
    elif name == 'late-fence-delivery':
        row = next(row for row in events if row['event'] == 'NETWORK_RECEIVED' and row.get('response') == response)
        events.remove(row); events.append(row)
    elif name == 'missing-allocation-force':
        start = events.index(ready[0]); at = next(i for i in range(start+1, len(events)) if events[i] == dict(node='node-2', event='ALLOCATOR_DIRECTORY_FORCED'))
        events.pop(at)
    elif name == 'forged-scope':
        value = n.read(root/'restart-result.json'); value['phase3Complete'] = True
        (root/'restart-result.json').write_bytes(f.canonical(value))
    else: raise ValueError('unknown automatic restart mutation')
    (root/'events.json').write_bytes(f.canonical(events))


def qualify(root):
    root = Path(root); original = validate(root); negatives = []
    for name, (file, reason) in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-automatic-restart-negative-') as temp:
            path = Path(temp)/'raw'; shutil.copytree(root, path); mutate(path, name)
            try: validate(path)
            except ValueError as error: need(str(error) == reason, 'automatic restart unrelated negative '+name+': '+str(error))
            else: raise ValueError('automatic restart accepted negative '+name)
        negatives.append(dict(case=name, status='REJECTED', reason=reason))
    return dict(original=original, negatives=negatives)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('root'); p.add_argument('--qualify', action='store_true'); a = p.parse_args()
    print(json.dumps((qualify if a.qualify else validate)(a.root), sort_keys=True))
