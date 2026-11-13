"""Four original joint copies, interrupted authority and native reacquisition.

The complete catalog/certificate/checkpoint chain is replayed independently.
Full maintenance retirement and remote export-force causality remain separate
obligations; this component is neither process-death nor Phase 3 admission.
"""
import argparse
import base64
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import joining_catalog_evidence as catalog
from . import generation_copy_evidence as generation
from . import automatic_floor_resume_evidence as resume
from . import joining_placement_evidence as placement
from . import joining_initialization_evidence as initialization
from . import joining_connections

c, f, h, need = catalog.disk, catalog.f, catalog.collection, catalog.need
NODES = ('node-1', 'node-2', 'node-3', 'node-6')
FILES = {'receipt.json', 'proposal.gsr', 'lineage.json', 'originals', 'interrupted', 'after-close',
         'after-reopen', 'resumed-floor', 'after-maintenance', 'interrupted-usage.json',
         'resumed-usage.json', 'floor-events.json', 'maintenance.json'}
SCOPE = dict(schema='gse-v53-joint-floor-recovery-v1', status='PASS', profile='5-REPLACE', node='node-2',
             sameDirectory=True, initialFloor='seed-maintenance-original-copies', recovery='native-tcp',
             processDeath=False, phase3Complete=False)
PARTIAL_CUTS = ('FLOOR_COPY_CREATED', 'FLOOR_MANIFEST_FORCED', 'FLOOR_IMAGE_FORCED', 'FLOOR_MEMBER_FORCED')


def partial_scope(ordinal, cut):
    need(type(ordinal) is int and 1 <= ordinal <= 4 and cut in PARTIAL_CUTS, 'joint floor declared partial writer cut')
    return dict(SCOPE, schema='gse-v53-native-partial-joint-floor-v1', ordinal=ordinal, cut=cut, handoff=True)


def writer_case(scope):
    if type(scope) is dict and scope.get('schema') == 'gse-v53-native-partial-joint-floor-v1':
        expected = partial_scope(scope.get('ordinal'), scope.get('cut'))
        same(scope, expected, 'joint floor bounded scope')
        return scope['ordinal'], scope['cut']
    same(scope, SCOPE, 'joint floor bounded scope')
    return None


def writer_prefix(offered, proposal, scope):
    case = writer_case(scope)
    events, files, writes, directories = generation.floor.transaction(offered, proposal, handoff=case is not None)
    ordinal = 0; at = None
    for i, row in enumerate(events):
        if row['event'] == 'FLOOR_COPY_CREATED': ordinal += 1
        if (case is None and row['event'] == 'FLOOR_COPIES_FORCED' or
                case is not None and ordinal == case[0] and row['event'] == case[1]):
            at = i; break
    need(at is not None, 'joint floor declared writer cut absent')
    return dict(events=[v['event'] for v in events[:at+1]], chargedCopies=ordinal,
        interrupted=dict({name: None for name, index in directories.items() if index <= at},
                         **{name: raw for name, raw in files.items() if writes[name] <= at}),
        completed=dict({name: None for name in directories}, **files))


def read(path):
    path = Path(path)
    maximum = h.WIRE_BYTES if path.name == 'wire.json' else h.EVENT_BYTES if path.name in ('events.json','floor-events.json') else 2*1024**2
    def unique(rows):
        need(len(rows) == len(dict(rows)), 'joint floor duplicate JSON key')
        return dict(rows)
    value = json.loads(h.snapshot.s.regular(path, maximum), object_pairs_hook=unique)
    need(type(value) is not list or len(value) <= h.HISTORY_ROWS, 'joint floor history row capacity')
    for row in value if type(value) is list else [value]:
        encoded = f.canonical(row); need(len(encoded) <= h.ROW_BYTES, 'joint floor history message capacity'); f.parse_budget(encoded)
    return value


def same(actual, expected, reason):
    need(f.canonical(actual) == f.canonical(expected), reason)


def bounded(rows, images, sources):
    need(type(rows) is list and rows, 'joint floor resource rows')
    for row in rows:
        need(type(row) is dict and set(row) == {'event', 'usage'} and type(row['event']) is str,
             'joint floor resource rows')
        v = row['usage']
        need(type(v) is dict and set(v) == {'metadata', 'staging', 'queued', 'leases', 'counts'} and
             all(type(v[k]) is int and v[k] >= 0 for k in ('metadata', 'staging', 'queued', 'leases')) and
             type(v['counts']) is dict and set(v['counts']) <= {'GENERATION', 'SOURCE', 'LEARNER', 'JOURNAL',
                 'CATALOG', 'MISC', 'APPLICATION', 'CONTROL', 'WAITER'} and
             all(type(n) is int and n > 0 for n in v['counts'].values()) and
             v['leases'] == sum(v['counts'].values()) and v['counts'].get('APPLICATION', 0) <= images <= 7 and
             v['counts'].get('SOURCE', 0) <= sources <= 6 and v['metadata'] <= 384 * 1024**2 and
             v['staging'] <= 512 * 1024**2, 'joint floor bounded resource observations')
    need(rows[-1]['usage']['counts'].get('APPLICATION') == images and
         rows[-1]['usage']['counts'].get('SOURCE') == sources, 'joint floor physical originals remain charged')


def delivered_replies(rows, events, identities, root, sent_ids):
    """Qualify connection metadata, rather than strip it to a legacy reply."""
    connected = any('connection' in row for row in rows) or any(
        'connection' in row for row in events if row.get('request') in sent_ids)
    expected = {'request', 'response', 'withheld'} | ({'connection'} if connected else set())
    need(all(set(row) == expected and row['withheld'] is False for row in rows),
         'joint floor delivered original replies')
    if connected:
        # Parent observers use NETWORK_* names; the child uses native names.
        # Include complete invocations (legacy delivery has no request hash).
        connections = {row['connection']['id'] for row in rows}
        connections.update(row['connection']['id'] for row in events
                           if row.get('request') in sent_ids and 'connection' in row)
        observed = [row for row in events if row.get('event') in joining_connections.TRANSPORT and
                    (row.get('request') in sent_ids or row.get('connection', {}).get('id') in connections)]
        result = joining_connections.replay(observed, rows, identities, root)
        need(not result['failed'] and len(result['rows']) == len(rows) and
             all(row['delivered'] is not None for row in result['rows']),
             'joint floor delivered original replies')


def transfer_sessions(root, events, copies, identities, cap, ballot, *, scope='joint-floor-reopened'):
    sent = [v for v in events if v.get('node') == 'node-2' and v.get('scope') == scope and
            v['event'] == 'BEFORE_REQUEST_WRITE']
    received = [v for v in events if v.get('node') == 'node-2' and v.get('scope') == scope and
                v['event'] == 'AFTER_RESPONSE_READ']
    sent_ids = {v['request'] for v in sent}
    rows = read(root/'wire.json')
    rows = [v for v in rows if catalog.sha(base64.b64decode(v['request'], validate=True)) in sent_ids]
    # Every returned reply must have its own observed send and local receive;
    # neither a remote producer label nor a retained packet supplies a delivery.
    need(len(rows) == len(sent) == len(received), 'joint floor complete fresh exchange observations')
    delivered_replies(rows, events, identities, cap['root'], sent_ids)
    used = set(); discovered = set(); peers = {node: [] for node in NODES if node != 'node-2'}
    for row in rows:
        kind, q = generation.t.t.wire(row['request'])
        answer, a = generation.t.t.wire(row['response'])
        request = catalog.sha(base64.b64decode(row['request'], validate=True)); response = catalog.sha(base64.b64decode(row['response'], validate=True))
        sends = [v for v in sent if v['request'] == request]
        reads = [v for v in received if v['request'] == request and v.get('response') == response]
        need(len(sends) == len(reads) == 1 and request not in used and sends[0]['bytes'] == row['request'],
             'joint floor fresh delivery binding')
        used.add(request)
        need(q['sender'] == identities['node-2'] and q['recipient']['node'] in peers and
             q['recipient'] == identities[q['recipient']['node']], 'joint floor original remote identities')
        if kind == 'STATUS_PROBE':
            peer = q['recipient']['node']; view = catalog.catalog.authority(cap['root'], cap['cut']['view'])
            fields = dict(root=cap['root'], view=view, ballot=ballot, trace=q['trace'], sequence=1)
            need(peer not in discovered and answer == 'STATUS' and
                 q == dict(fields, sender=identities['node-2'], recipient=identities[peer], payload={'nonce': q['payload']['nonce']}) and
                 a == dict(fields, sender=identities[peer], recipient=identities['node-2'],
                     payload=dict(nonce=q['payload']['nonce'], cut=cap['cut'], ready=False)), 'joint floor discovery original cut')
            discovered.add(peer)
            continue
        peers[q['recipient']['node']].append({k: row[k] for k in ('request', 'response')})
    need(discovered == set(peers), 'joint floor complete original discovery')
    for node, exchanges in peers.items():
        sessions = generation.sessions(exchanges); members = copies[node]
        prefix = catalog.sha(f.canonical(dict(root=cap['root'], cut=cap['cut'], scope='retained-current-packet')))
        expected = [(prefix, members['source.gscp'], 'CAPSULE')]
        generation.t.transcript(generation.attempts(sessions[0][1]), expected, cap['root'], catalog.catalog.authority(cap['root'], cap['cut']['view']),
            ballot, identities['node-2'], identities[node], 'joint floor packet', chunk_bytes=4*1024**2)
        reference = catalog.sha(f.canonical(dict(root=cap['root'], cut=cap['cut'], scope='retained-current-generation-metadata')))
        expected = [(reference, members['generation.gsr'], 'RECORD')]
        if 'ancestry.gsr' in members: expected.append((catalog.sha(members['ancestry.gsr']), members['ancestry.gsr'], 'RECORD'))
        expected += [(catalog.sha(data), data, 'RECORD') for name, data in sorted(members.items())
                     if name not in ('generation.gsr', 'source.gscp', 'ancestry.gsr') and not name.endswith('.image')]
        generation.t.transcript(generation.attempts(sessions[1][1]), expected, cap['root'], catalog.catalog.authority(cap['root'], cap['cut']['view']),
            ballot, identities['node-2'], identities[node], 'joint floor generation', chunk_bytes=4*1024**2)
    return len(rows)


def validate(directory):
    root = Path(directory); inventory = h.inventory(root); side = root/'joint-floor-recovery'
    need(side.is_dir() and not side.is_symlink() and {p.name for p in side.iterdir()} == FILES, 'joint floor exact sidecar inventory')
    scope = read(side/'receipt.json'); case = writer_case(scope)
    need({p.name for p in (side/'originals').iterdir()} == set(NODES), 'joint floor original owners')
    originals = {n: c.inventory(side/'originals'/n) for n in NODES}
    copies = {}; refs = []; identities = {}; cap = None
    for node, files in originals.items():
        prefix, members, packet = c.current(files)
        copies[node] = dict(members, **{'generation.gsr': files[prefix+'generation.gsr']})
        identities[node] = f.decode(files['node.gsr'], 'records', 'NODE')['identity']
        need(identities[node]['node'] == node, 'joint floor original identity')
        if cap is None: cap = packet['capsule']
        need(packet['capsule']['cut'] == cap['cut'] and packet['capsule']['catalog'] == cap['catalog'] and
             packet['capsule']['application'] == cap['application'], 'joint floor original common cut')
        refs.append(dict(voter=node, generation=catalog.sha(copies[node]['generation.gsr']), catalog=cap['catalog'], snapshot=cap['application']))
    need(cap['cut']['view']['old'] == ['node-'+str(i) for i in range(1, 6)] and
         cap['cut']['view']['new'] == ['node-1', 'node-2', 'node-3', 'node-4', 'node-6'], 'joint floor real replacement view')
    catalog.catalog.majority(cap['cut']['view'], list(NODES))
    proposal = f.encode('records', 'FLOOR', dict(root=cap['root'], node='node-2', cut=cap['cut'], sources=refs))
    need((side/'proposal.gsr').read_bytes() == proposal, 'joint floor exact original proposal')
    offered = {catalog.sha(m['generation.gsr']): m for m in copies.values()}
    writer = writer_prefix(offered, proposal, scope)
    complete = dict(originals['node-2'], **writer['completed'])
    interrupted = dict(originals['node-2'], **writer['interrupted'])
    for name in ('interrupted', 'after-close', 'after-reopen'):
        need(c.inventory(side/name) == interrupted, 'joint floor exact interrupted originals: '+name)
    need(c.inventory(side/'resumed-floor') == complete, 'joint floor exact resumed inventory')
    image_count = sum(n.endswith('.image') for n in complete)
    source_count = len(copies) + sum(n.startswith('sources/') and n.count('/') == 1 and v is None for n,v in complete.items())
    initial = read(side/'interrupted-usage.json'); resumed = read(side/'resumed-usage.json')
    # The reservation is charged at directory creation even if no body/image
    # has been written yet. Missing later copies cannot create phantom charges.
    missing = len(copies)-writer['chargedCopies']
    need(all(sum(name.endswith('.image') for name in members) == 1 for members in copies.values()),
         'joint floor one original image per copy')
    bounded(initial, image_count-missing, source_count-missing); bounded(resumed, image_count, source_count)
    need([v['event'] for v in initial] == ['FLOOR_COPY_BEFORE_RETURN', *writer['events']], 'joint floor interrupted force order')
    captured = read(side/'floor-events.json'); native = read(root/'events.json')
    need(captured and captured == native[:len(captured)] and captured[-1]['event'] == 'FLOOR_BEFORE_RETURN' and
         captured[-1].get('node') == 'node-2' and captured[-1].get('scope') == 'joint-floor-reopened', 'joint floor native event prefix')
    # Storage-only callbacks have no request/response fields. Cold-open checks
    # are retained too; no fresh grant may precede the original floor.
    storage = [v['event'] for v in captured if v.get('scope') == 'joint-floor-reopened' and v.get('node') == 'node-2' and 'request' not in v]
    need(storage == [v['event'] for v in resumed], 'joint floor complete resource event observations')
    expected = sum((resume.resume_events(copies[n]) for n in ('node-6','node-1','node-3','node-2')), [])
    expected += [v['event'] for v in generation.floor.transaction(offered, proposal, handoff=True)[0]]
    need([v for v in storage if v.startswith('FLOOR_') and v != 'FLOOR_COPY_BEFORE_RETURN'] == expected,
         'joint floor resumed force order')
    need(not any(v.startswith(('PROMISE_', 'BASIS_', 'SELECTED_', 'INSTALL_')) for v in storage), 'joint floor before fresh grant')
    lineage = read(side/'lineage.json'); need(type(lineage) is dict and set(lineage) == {'root','node','replica','application','cut'} and
        lineage['root'] == cap['root'] and lineage['node'] == 'node-2' and lineage['cut'] == cap['cut'] and
        all(type(lineage[k]) is str and Path(lineage[k]).is_absolute() for k in ('replica','application')) and
        lineage['replica'] != lineage['application'], 'joint floor original lineage')
    maintenance = read(side/'maintenance.json')
    need(type(maintenance) is dict and set(maintenance) == {'status','originalDeadlineNanos','startedNanos','budgetNanos','before','after'} and
         maintenance['status'] == 'PASS' and maintenance['before'] == maintenance['after'] == cap['cut'] and
         type(maintenance['startedNanos']) is int and type(maintenance['budgetNanos']) is int and maintenance['budgetNanos'] == 720_000_000_000 and
         maintenance['originalDeadlineNanos'] == maintenance['startedNanos']+maintenance['budgetNanos'], 'joint floor unchanged maintenance budget and cut')
    journal = c.journal(originals['node-2']['grants.gsr'], cap['root'], 'node-2')
    ballot = next(value['ballot'] for kind,raw,value in reversed(journal) if kind == 'PROMISE')
    exchanges = transfer_sessions(root, captured, copies, identities, cap, ballot)
    semantic = catalog.validate(root, size=5, kind='REPLACE')
    replay = catalog.Replay(root, size=5, kind='REPLACE')
    for index in range(1, semantic['slots']+1): replay.step(index)
    reopened_at = next(i for i,v in enumerate(captured) if v.get('node') == 'node-2' and v.get('scope') == 'joint-floor-reopened')
    replay.publication_receipts = placement.transition.publication.CheckpointReceipts(root, replay,
        old_owner_lifetimes={'node-2': (reopened_at, 'joint-floor-reopened')})
    history = placement.History(root, replay); prefix_result = history.run()
    joined = placement.Placement(root, history); placement_result = joined.run()
    derived = dict(history.group, **{'node-6': joined.expected['replica']})
    for node in NODES:
        prefix, members, _ = c.current(derived[node])
        need(copies[node] == dict(members, **{'generation.gsr': derived[node][prefix+'generation.gsr']}),
             'joint floor independently derived original generation: '+node)
    confirmed = copy.deepcopy(history.group)
    initialization.confirm_old_learners(root, joined, confirmed, replay=replay, voters=history.voters)
    need(originals['node-2'] == confirmed['node-2'], 'joint floor independently derived interrupted owner')
    intent_index = semantic['controls'].index('INTENT')+1
    need(cap['cut']['index'] == intent_index and c.current(c.inventory(root/f'published-{intent_index}/node-2'))[2]['capsule']['cut'] == cap['cut'],
         'joint floor admitted INTENT cut')
    for name in ('after-maintenance',):
        actual = c.inventory(side/name)
        need(not any(n.startswith('floor-copies') for n in actual) and c.current(actual)[2]['capsule']['cut'] == cap['cut'], 'joint floor maintenance observation')
    need(c.current(c.inventory(root/'after-close/node-2'))[2]['capsule']['cut']['index'] == semantic['slots'], 'joint floor required voter completed barrier')
    need(h.inventory(root) == inventory, 'joint floor original changed')
    result = dict(status='PASS', scope='joint-floor-storage-and-catalog-chain', profile='5-REPLACE', originalCopies=4,
        physicalImages=image_count, retainedSources=source_count, freshExchanges=exchanges, semanticChain=semantic,
        originalPrefix=prefix_result, joiningPlacement=placement_result,
        remoteExportForceQualified=False, fullMaintenanceReplayQualified=False, processDeathQualified=False, phase3Complete=False)
    if case is not None:
        result['partialWriter'] = dict(ordinal=case[0], cut=case[1], handoff=True,
            initialImages=image_count-missing, initialSources=source_count-missing)
    return result


NEGATIVES = {
    'scope': 'joint floor bounded scope', 'proposal': 'joint floor exact original proposal',
    'premature-authority': 'joint floor exact interrupted originals: interrupted',
    'closed-original': 'joint floor exact interrupted originals: after-close',
    'reopened-original': 'joint floor exact interrupted originals: after-reopen',
    'lost-original': 'joint floor exact resumed inventory', 'lost-authority': 'joint floor exact resumed inventory',
    'invented-headroom': 'joint floor physical originals remain charged', 'resource-overflow': 'joint floor bounded resource observations',
    'missing-force': 'joint floor interrupted force order', 'event-prefix': 'joint floor native event prefix',
    'lineage': 'joint floor original lineage', 'budget': 'joint floor unchanged maintenance budget and cut',
    'lost-exchange': 'joint floor complete fresh exchange observations',
    'changed-packet': 'joint floor packet exact data',
    'legacy-generation-route': 'joint floor generation original offer',
    'consistent-extra-allocation': 'joint floor independently derived interrupted owner',
}
PARTIAL_NEGATIVES = {
    'partial-ordinal': 'joint floor exact interrupted originals: interrupted',
    'partial-cut': 'joint floor exact interrupted originals: interrupted',
    'partial-handoff': 'joint floor bounded scope',
}


def negative_cases(directory):
    case = writer_case(read(Path(directory)/'joint-floor-recovery/receipt.json'))
    return dict(NEGATIVES, **(PARTIAL_NEGATIVES if case is not None else {}))


def mutate(root, name):
    need(name in NEGATIVES or name in PARTIAL_NEGATIVES, 'joint floor declared mutation'); side = root/'joint-floor-recovery'
    if name in PARTIAL_NEGATIVES:
        path = side/'receipt.json'; value = read(path); case = writer_case(value)
        need(case is not None, 'joint floor partial mutation requires original partial case')
        if name == 'partial-ordinal': value['ordinal'] = case[0] % 4 + 1
        elif name == 'partial-cut': value['cut'] = PARTIAL_CUTS[(PARTIAL_CUTS.index(case[1])+1) % len(PARTIAL_CUTS)]
        else: value['handoff'] = False
        h.save(path, value); return
    if name == 'proposal': (side/'proposal.gsr').write_bytes(b'changed'); return
    if name == 'premature-authority': (side/'interrupted/floor-copies/floor.gsr').write_bytes((side/'proposal.gsr').read_bytes()); return
    if name in ('closed-original','reopened-original'):
        (side/('after-close' if name == 'closed-original' else 'after-reopen')/'unexpected').write_bytes(b'changed'); return
    if name == 'lost-original': next((side/'resumed-floor/floor-copies').glob('*/generation.gsr')).unlink(); return
    if name == 'lost-authority': (side/'resumed-floor/floor-copies/floor.gsr').unlink(); return
    if name == 'consistent-extra-allocation':
        path = side/'originals/node-2/allocator.gsr'; value = f.decode(path.read_bytes(), 'records', 'ALLOCATOR')
        value['counter'] += 1; changed = f.encode('records', 'ALLOCATOR', value)
        for directory in ('originals/node-2', 'interrupted', 'after-close', 'after-reopen', 'resumed-floor'):
            (side/directory/'allocator.gsr').write_bytes(changed)
        return
    if name == 'legacy-generation-route':
        captured = read(side/'floor-events.json'); sent = {v['request'] for v in captured if v.get('node') == 'node-2' and
            v.get('scope') == 'joint-floor-reopened' and v['event'] == 'BEFORE_REQUEST_WRITE'}
        wire = read(root/'wire.json')
        row = next(v for v in wire if catalog.sha(base64.b64decode(v['request'], validate=True)) in sent and
                   generation.t.t.wire(v['response'])[0] == 'SOURCE_OFFER' and generation.t.t.wire(v['response'])[1]['payload']['kind'] == 'RECORD')
        old_bytes = row['request']; old = catalog.sha(base64.b64decode(old_bytes, validate=True))
        kind, value = generation.t.t.wire(old_bytes); proposal = f.decode((side/'proposal.gsr').read_bytes(), 'records', 'FLOOR')
        value['payload']['digest'] = catalog.sha(f.canonical(dict(root=proposal['root'], cut=proposal['cut'], scope='retained-current-generation')))
        encoded = f.encode('wire', kind, value); row['request'] = base64.b64encode(encoded).decode(); new = catalog.sha(encoded)
        for path in (side/'floor-events.json', root/'events.json'):
            events = read(path)
            for event in events:
                if event.get('request') == old: event['request'] = new
                if event.get('bytes') == old_bytes: event['bytes'] = row['request']
            h.save(path, events)
        h.save(root/'wire.json', wire); return
    if name in ('lost-exchange', 'changed-packet'):
        captured = read(side/'floor-events.json'); sent = {v['request'] for v in captured if v.get('node') == 'node-2' and
            v.get('scope') == 'joint-floor-reopened' and v['event'] == 'BEFORE_REQUEST_WRITE'}
        wire = read(root/'wire.json')
        at = next(i for i,v in enumerate(wire) if catalog.sha(base64.b64decode(v['request'], validate=True)) in sent and
                  generation.t.t.wire(v['response'])[0] == 'CHUNK')
        if name == 'lost-exchange': wire.pop(at)
        else:
            row = wire[at]; raw = base64.b64decode(row['response'], validate=True); old = catalog.sha(raw)
            kind, value = generation.t.t.wire(row['response']); payload = value['payload']
            chunk = bytearray(base64.b64decode(payload['bytes'], validate=True)); chunk[-1] ^= 1
            payload['bytes'] = base64.b64encode(chunk).decode(); payload['digest'] = catalog.sha(chunk)
            encoded = f.encode('wire', kind, value); row['response'] = base64.b64encode(encoded).decode(); new = catalog.sha(encoded)
            for path in (side/'floor-events.json', root/'events.json'):
                events = read(path)
                for event in events:
                    if event.get('response') == old: event['response'] = new
                h.save(path, events)
        h.save(root/'wire.json', wire); return
    filename = {'scope':'receipt','invented-headroom':'resumed-usage','resource-overflow':'resumed-usage','missing-force':'interrupted-usage',
                'event-prefix':'floor-events','lineage':'lineage','budget':'maintenance'}[name]
    path = side/(filename+'.json'); value = read(path)
    if name == 'scope': value['phase3Complete'] = True
    elif name == 'invented-headroom':
        value[-1]['usage']['counts']['APPLICATION'] -= 1; value[-1]['usage']['leases'] -= 1
    elif name == 'resource-overflow':
        value[-1]['usage']['counts']['APPLICATION'] = 8; value[-1]['usage']['leases'] = sum(value[-1]['usage']['counts'].values())
    elif name == 'missing-force': value.pop(-1)
    elif name == 'event-prefix': value.pop(0)
    elif name == 'lineage': value['replica'] = 'relative'
    elif name == 'budget': value['originalDeadlineNanos'] += 1
    h.save(path, value)


def qualify(directory, progress=None):
    root = Path(directory); before = h.inventory(root); original = validate(root); negatives = []
    if progress: progress(dict(stage='original', status='PASS', profile='5-REPLACE'))
    for name, reason in negative_cases(root).items():
        with tempfile.TemporaryDirectory(prefix='v53-joint-floor-negative-') as tmp:
            changed = Path(tmp)/'raw'; shutil.copytree(root, changed); mutate(changed, name)
            try: validate(changed)
            except ValueError as error: need(str(error) == reason, 'joint floor unrelated rejection: '+name+': '+str(error))
            else: raise ValueError('joint floor accepted mutation: '+name)
            negatives.append(dict(case=name, status='REJECTED', reason=reason))
            if progress: progress(negatives[-1])
    need(h.inventory(root) == before, 'joint floor original changed')
    return dict(original=original, negatives=negatives)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('root'); p.add_argument('--qualify', action='store_true'); a = p.parse_args()
    result = qualify(a.root, lambda row: print(json.dumps(row, sort_keys=True), file=sys.stderr, flush=True)) if a.qualify else validate(a.root)
    print(json.dumps(result, sort_keys=True))
