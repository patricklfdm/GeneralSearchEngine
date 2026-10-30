"""Original physical and lifecycle replay of a native node cold reopen.

The journal identity persists; the instrumented object incarnation does not.
This qualifies a same-process close/open history, not process death or the full
network transcript. Original images and every retained directory are reduced
before considering READY or producer claims.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import struct
import tempfile
import uuid
from . import automatic_restart_evidence as p
from . import election_wait_evidence as wait

n, b, c, e, f, need = p.n, p.b, p.c, p.e, p.f, p.need


def inventory(root):
    from .discovered_selection_evidence import inventory as regular
    regular(root)
    names = {'initial', 'original-plan.gsbp', 'original-application.image', 'before-network',
        'calls.json', 'events.json', 'wire.json', 'node-result.json',
        'first-ready', 'before-reopen', 'second-ready', 'after-close'}
    names |= {f'{label}-{i}' for label in ('applied', 'published') for i in range(1, 5)}
    names |= {f'installed-{i}' for i in (1, 2)} | {f'selected-{i}.gsr' for i in (1, 2)}
    b.selection.layout(root, names, 'node owner original history')


class Service(p.Service):
    def campaign(self, number, counter):
        if number == 2: self.group = p.t.maintenance(self.group, self.voters)
        chosen = (self.root/f'selected-{number}.gsr').read_bytes()
        observed = f.decode(chosen, 'records', 'SELECTED')
        voters = tuple(row['voter'] for row in observed['sources'])
        need(voters in (('node-1', 'node-2'), ('node-1', 'node-3')), 'node owner selected stable majority')
        own = n.future.identity(self.group['node-1']); ballot = dict(counter=counter, proposer='node-1', incarnation=own['storage'])
        frozen = {}; prepared = {}; source_ids = set()
        for node, files in self.group.items():
            actual = c.inventory(self.root/f'installed-{number}'/node)
            if node not in voters and actual['grants.gsr'] == files['grants.gsr']: continue
            _, members, packet = c.current(files); cap = packet['capsule']
            prior = c.journal(files['grants.gsr'], cap['root'], node)
            rows = c.journal(actual['grants.gsr'], cap['root'], node)
            need(rows[:len(prior)] == prior and [v[0] for v in rows[len(prior):]] ==
                 ['PROMISE', 'BASIS']+(['SELECTED'] if node in voters else []), 'node owner exact grant history')
            identifier = rows[len(prior)][2]['basisId']
            need(str(uuid.UUID(identifier)) == identifier and identifier not in source_ids
                 and all(v[2].get('basisId') != identifier for v in prior), 'node owner fresh source identity')
            source_ids.add(identifier)
            value = dict(root=cap['root'], view=e.authority(cap['root'], cap['cut']['view']), ballot=ballot, basisId=identifier)
            promise = f.encode('records', 'PROMISE', value); wrapper = n.s.s.wrap(promise, files[n.s.FILE])
            raw = c.packet_bytes(cap, dict(packet['objects'], **{e.digest(wrapper):wrapper}), packet['images'])
            packet = e.p.decode(raw)
            basis = f.encode('records', 'BASIS', dict(value, voter=node, cut=cap['cut'], capsule=e.digest(packet['capsuleBytes']),
                inventory=e.digest(packet['indexBytes']), accepted=None))
            source = 'sources/'+identifier
            changed = dict(files, **{'grants.gsr':files['grants.gsr']+promise+basis, source:None, source+'/source.gscp':raw},
                **{source+'/'+h+'.image':members[h+'.image'] for h in packet['images']})
            if node == 'node-1': changed['allocator.gsr'] = f.encode('records', 'ALLOCATOR', dict(root=cap['root'], node=node, counter=counter))
            prepared[node] = changed; frozen[node] = dict(promise=promise, basis=basis, packet=packet, wrapper=wrapper, members=members)
        cap = frozen['node-1']['packet']['capsule']
        need(all(frozen[node]['packet']['capsule']['cut']['index'] <= cap['cut']['index'] for node in voters),
             'node owner proposer owns highest source')
        selected = f.encode('records', 'SELECTED', dict(root=cap['root'], view=e.authority(cap['root'], cap['cut']['view']),
            ballot=ballot, cut=cap['cut'], nextEntry=None, sources=[dict(voter=node,
                basisId=f.decode(frozen[node]['basis'], 'records', 'BASIS')['basisId'], basisDigest=e.digest(frozen[node]['basis'])) for node in voters]))
        need(selected == chosen, 'node owner original selection')
        installed = dict(self.group, **prepared)
        for node in voters:
            files = prepared[node]; prefix = c.current(files)[0]; packet = frozen['node-1']['packet']
            intent = n.s.intent(n.future.identity(files), selected, files[n.s.FILE],
                [(frozen[v]['basis'], frozen[v]['packet'], frozen[v]['wrapper']) for v in voters])
            objects = dict(n.slot.prefix(packet, files['root.gsr']), **{e.digest(intent):intent})
            raw = c.packet_bytes(cap, objects, packet['images'])
            members = dict(zip(('promise.gsr', 'basis.gsr'), (frozen[node]['promise'], frozen[node]['basis'])),
                **{'selected.gsr':selected, 'selected-sources.gsr':b''.join(frozen[v]['basis'] for v in voters), 'source.gscp':raw},
                **{h+'.image':frozen['node-1']['members'][h+'.image'] for h in packet['images']})
            selector, generation = c.generation(members, cap, node, 'b' if prefix == 'generations/a/' else 'a', None)
            installed[node] = dict(files, **generation, **{'selector.gsr':selector, 'grants.gsr':files['grants.gsr']+selected,
                n.s.FILE:n.s.merged(files[n.s.FILE], [self.group[v][n.s.FILE] for v in voters])})
        self.group = installed; self.voters = voters; self.active = list(voters)
        b.match(self.root, f'installed-{number}', self.group)
        self.first = None; self.selection_anchor = c.anchor(cap)

    def checkpoint_voters(self, view, node):
        need(node in self.voters, 'node owner checkpoint voter'); return set(self.voters)

    def data_documents(self):
        return [(i, 'node-owner-'+str(i)) for i in range(100, 100+self.slot//2)]

    def advance(self, kind):
        self.group = p.t.maintenance(self.group, self.voters)
        identity = 100+self.slot//2
        text = (str(identity)+':node-owner-'+str(identity)).encode()
        payload = b'\x01'+struct.pack('>HIII', 1, 1, 4, identity)+struct.pack('>I', len(text))+text if kind == 'DATA' else None
        self.publish(kind, payload)


def lifecycle(root, *, process_restart=False):
    events = n.read(root/'events.json')
    need(type(events) is list and len(events) <= 32768, 'node owner bounded events')
    initial = [dict(node=node, incarnation=1, event=event)
        for node in ('node-1', 'node-2', 'node-3') for event in (*wait.REOPEN, 'NODE_OPEN')]
    need(events[:len(initial)] == initial, 'node owner original opens')
    wait.lifecycle(n.read(root/'calls.json'),
        [dict(node=node, event=event) for node in ('node-1', 'node-2', 'node-3') for event in wait.REOPEN],
        ('node-1', 'node-2', 'node-3'))
    marks = [(at, row) for at, row in enumerate(events) if row['event'].startswith(('NODE_', 'ROUND_'))]
    one = ['INSTALLED', 'SLOT_BEGIN', 'SLOT_COMPLETE', 'BEFORE_READY', 'SLOT_BEGIN', 'SLOT_COMPLETE']
    expected = ['NODE_OPEN']*3+['ROUND_'+v for v in one]+['NODE_CRASH' if process_restart else 'NODE_CLOSED', 'NODE_OPEN']+['ROUND_'+v for v in one]+['NODE_CLOSED']
    need([row['event'] for _, row in marks] == expected, 'node owner exact lifecycle order')
    closed_at, reopened_at = marks[9][0], marks[10][0]
    need(events[closed_at+1:reopened_at] == [dict(node='node-1', incarnation=2, event=event) for event in wait.REOPEN],
         'node owner exact cold reopen forces')
    for at, row in enumerate(events):
        need(row.get('node') in ('node-1', 'node-2', 'node-3'), 'node owner original event node')
        need('incarnation' in row or row['event'] in ('FUTURE_QUORUM_COMPLETE', 'PUBLICATION_SEND_BOUNDARY'),
             'node owner event lifetime required')
        if 'incarnation' in row:
            wanted = 2 if row['node'] == 'node-1' and at > closed_at else 1
            need(type(row['incarnation']) is int and row['incarnation'] == wanted, 'node owner lifetime identity')
    for at, row in marks[3:]:
        need(row['node'] == 'node-1' and row['incarnation'] == (1 if at <= closed_at else 2), 'node owner lifecycle owner')
        if row['event'].startswith('NODE_'):
            need(set(row) == {'node', 'event', 'incarnation'}, 'node owner marker shape')
    campaign = slot = 0; completion = None; previous_complete = 0
    for at, row in marks:
        if not row['event'].startswith('ROUND_'): continue
        need(set(row) == {'node', 'event', 'incarnation', 'record', 'bytes'}, 'node owner round shape')
        raw = base64.b64decode(row['bytes'], validate=True)
        need(e.digest(raw) == row['record'], 'node owner event digest')
        if row['event'] == 'ROUND_INSTALLED':
            campaign += 1
            chosen = (root/f'selected-{campaign}.gsr').read_bytes(); selected = f.decode(chosen, 'records', 'SELECTED')
            need(raw == chosen, 'node owner installed selection')
            voters = tuple(source['voter'] for source in selected['sources'])
            for node in voters:
                n.s.ordered([v['event'] for v in events[previous_complete:at] if v['node'] == node],
                    ['PROMISE_FORCED', 'BASIS_FORCED', 'GRANT_BEFORE_RETURN', 'SELECTED_FORCED',
                     'INSTALL_SELECTOR_FORCED', 'INSTALL_PARENT_FORCED', 'INSTALL_BEFORE_RETURN'], 'node owner installation '+node)
        elif row['event'] == 'ROUND_SLOT_BEGIN':
            slot += 1; entry = f.decode(raw, 'records', 'ENTRY')
            _, _, packet = c.current(c.inventory(root/f'published-{slot}/node-1'))
            need(entry['index'] == slot and entry['kind'] == ('DATA' if slot % 2 == 0 else 'BARRIER')
                 and entry['origin'] == selected['ballot'] and e.digest(raw) == packet['capsule']['cut']['entry'],
                 'node owner original entry')
        elif row['event'] == 'ROUND_SLOT_COMPLETE':
            ack = f.decode(raw, 'wire', 'PUBLISH_ACK'); files = c.inventory(root/f'published-{slot}/node-1')
            prefix, _, packet = c.current(files); own = n.future.identity(files)
            applied = c.inventory(root/f'applied-{slot}/node-1')
            expected = dict(certificate=e.digest(applied['applied-end/certificate.gsr']), selection=e.digest(chosen),
                published=c.anchor(packet['capsule']), generation=e.digest(files[prefix+'generation.gsr']))
            need(ack['root'] == selected['root'] and ack['view'] == selected['view'] and ack['ballot'] == selected['ballot']
                 and ack['sender'] == ack['recipient'] == own and ack['sequence'] == 1 and ack['payload'] == expected,
                 'node owner original completion')
            for node in voters:
                n.s.ordered([v['event'] for v in events[previous_complete:at] if v['node'] == node],
                    ['ACCEPT_PARENT_FORCED', 'PROOF_PARENT_FORCED', 'CERTIFICATE_PARENT_FORCED', 'APPLY_ACK_DIRECTORY_FORCED',
                     'PUBLICATION_SELECTOR_FORCED', 'PUBLICATION_BEFORE_RETURN', 'PUBLICATION_ACK_BEFORE_RETURN'], 'node owner publication '+node)
            completion = raw; previous_complete = at
        else:
            need(slot == 2*campaign-1 and raw == completion, 'node owner readiness fresh barrier')


def validate(root, *, process_restart=False):
    need(type(process_restart) is bool, 'node owner process scope')
    root = Path(root); inventory(root)
    group = n.s.initialize(b.original(root, 3, False))
    group = {node: dict(files, **{n.future.FILE:n.future.frame(n.future.initial(files), {})}) for node, files in group.items()}
    b.match(root, 'before-network', group)
    service = Service(root, group); service.campaign(1, 2); service.advance('BARRIER')
    b.match(root, 'first-ready', service.group); service.advance('DATA')
    b.match(root, 'before-reopen', service.group)
    # Explicit close/open preserves storage identity. The next campaign must
    # allocate above the original promise; it cannot restore its cached READY.
    service.campaign(2, 3); service.advance('BARRIER'); b.match(root, 'second-ready', service.group)
    service.advance('DATA'); b.match(root, 'after-close', service.group)
    lifecycle(root, process_restart=process_restart)
    need(n.read(root/'node-result.json') == dict(status='PARTIAL', producerPassed=True, coldReopens=1, barriers=2,
         dataCalls=2, serviceBudgetNanos=180_000_000_000, physicalReplay=False, processRestart=process_restart, phase3Complete=False),
         'node owner producer scope')
    return dict(status='PARTIAL', scope='native-node-process-reopen-physical' if process_restart else 'native-node-cold-reopen-physical', originalFirst=True, physicalReplay=True,
        coldReopens=1, campaigns=2, slots=4, snapshotGroups=16, fullWireReplay=False,
        processRestart=process_restart, publicRuntime=False, phase3Complete=False)


NEGATIVES = {
    'initial-image': ('original-application.image', 'bootstrap original image binding'),
    'first-data': ('applied-2/node-1/applied-end/application.image', 'bootstrap validation image header'),
    'before-reopen': ('before-reopen/node-1/allocator.gsr', 'admitted exact before-reopen: node-1'),
    'second-selector': ('published-3/node-1/selector.gsr', 'admitted exact published-3: node-1'),
    'second-data': ('applied-4/node-3/pending.accept', 'admitted exact applied-4: node-3'),
    'final-extra': ('after-close/node-3/extra', 'admitted exact after-close: node-3'),
    'second-selection': (None, 'node owner original selection'),
    'duplicate-selection': (None, 'node owner selected stable majority'),
    'unused-grant': ('installed-2/node-2/sources/extra', 'admitted exact installed-2: node-2'),
    'missing-ready': (None, 'node owner exact lifecycle order'),
    'stale-ready': (None, 'node owner readiness fresh barrier'),
    'old-owner': (None, 'node owner lifetime identity'),
    'missing-owner': (None, 'node owner event lifetime required'),
    'missing-reopen-force': (None, 'node owner exact cold reopen forces'),
    'missing-install-force': (None, 'selected retention force order: node owner installation node-2'),
    'missing-publication-force': (None, 'selected retention force order: node owner publication node-2'),
    'forged-completion': (None, 'node owner original completion'),
    'forged-scope': (None, 'node owner producer scope'),
}


def mutate(root, name):
    file = NEGATIVES[name][0]
    if file is not None: (root/file).write_bytes(b'changed original'); return
    events = n.read(root/'events.json')
    ready = [row for row in events if row['event'] == 'ROUND_BEFORE_READY']
    if name == 'missing-ready': events.remove(ready[1])
    elif name == 'stale-ready': ready[1].update(record=ready[0]['record'], bytes=ready[0]['bytes'])
    elif name == 'old-owner': ready[1]['incarnation'] = 1
    elif name == 'missing-owner': ready[1].pop('incarnation')
    elif name in ('second-selection', 'duplicate-selection'):
        path = root/'selected-2.gsr'; value = f.decode(path.read_bytes(), 'records', 'SELECTED')
        if name == 'second-selection': value['cut']['entry'] = '0'*64
        else: value['sources'][1] = dict(value['sources'][0])
        path.write_bytes(f.encode('records', 'SELECTED', value))
    elif name == 'forged-completion':
        row = next(v for v in events if v['event'] == 'ROUND_SLOT_COMPLETE')
        ack = f.decode(base64.b64decode(row['bytes']), 'wire', 'PUBLISH_ACK'); ack['payload']['certificate'] = '0'*64
        raw = f.encode('wire', 'PUBLISH_ACK', ack); row.update(record=e.digest(raw), bytes=base64.b64encode(raw).decode())
    elif name in ('missing-reopen-force', 'missing-install-force', 'missing-publication-force'):
        node, event, incarnation = {'missing-reopen-force':('node-1', 'CURRENT_DIRECTORY_FORCED', 2),
            'missing-install-force':('node-2', 'INSTALL_PARENT_FORCED', 1),
            'missing-publication-force':('node-2', 'PUBLICATION_SELECTOR_FORCED', 1)}[name]
        events.remove(next(v for v in events if v['node'] == node and v['event'] == event and v.get('incarnation') == incarnation))
    elif name == 'forged-scope':
        value = n.read(root/'node-result.json'); value['processRestart'] = True
        (root/'node-result.json').write_bytes(f.canonical(value))
    else: raise ValueError('unknown node owner mutation')
    (root/'events.json').write_bytes(f.canonical(events))


def qualify(root):
    root = Path(root); original = validate(root); negatives = []
    for name, (file, reason) in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-node-owner-negative-') as temp:
            path = Path(temp)/'raw'; shutil.copytree(root, path); mutate(path, name)
            try: validate(path)
            except ValueError as error: need(str(error) == reason, 'node owner unrelated negative '+name+': '+str(error))
            else: raise ValueError('node owner accepted negative '+name)
        negatives.append(dict(case=name, status='REJECTED', reason=reason))
    return dict(original=original, negatives=negatives)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--qualify', action='store_true'); args = parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root), sort_keys=True))
