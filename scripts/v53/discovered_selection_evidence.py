"""Original-first installation after heterogeneous REMOVE discovery.

Derive the same-cut maintenance, fresh grants, frozen sources, selection and
installed bytes before accepting their transfers or ACKs. This scoped reader
does not qualify the later BARRIER/DATA slots or autonomous service.
"""
import argparse
import base64
from collections import defaultdict, deque
import copy
import json
from pathlib import Path
import shutil
import tempfile
from . import discovered_transition_evidence as d
from . import native_dispatch_evidence as native

a, c, e, f, need = d.a, d.c, d.e, d.f, d.need
s = a.s
VOTERS = ('node-1', 'node-2', 'node-4')
LEADER = 'node-4'


def maintenance(group):
    """The adopted owner has no selected basis and retains only its new fence."""
    result = copy.deepcopy(group); files = result[LEADER]
    directory, members, packet = c.current(files); cap = packet['capsule']
    need('basis.gsr' not in members and 'adopted-certificate.gsr' in members,
         'discovered selection adopted predecessor')
    old = s.r.decode(files[s.FILE]); voters = set(cap['cut']['view']['old']) | set(cap['cut']['view']['new'])
    plan = dict(old['plan'], view=cap['cut']['view'],
                peers=[v for v in old['plan']['peers'] if v['identity']['node'] in voters])
    need(plan != old['plan'], 'discovered selection original view reconciliation')
    files[s.FILE] = s.r.frame(dict(old, revision=old['revision']+1, previous=e.digest(files[s.FILE]), plan=plan))
    # Original copies are obtained in local-then-known-voter order; STATUS alone
    # cannot narrow the ledger. network() checks both complete original copies.
    for peer in (LEADER, 'node-1', 'node-2'):
        old = s.r.decode(files[s.FILE]); plan = copy.deepcopy(old['plan'])
        anchor = c.anchor(c.current(group[peer])[2]['capsule'])
        need(anchor == c.anchor(cap), 'discovered selection same original floor')
        next(v for v in plan['peers'] if v['identity'] == a.u.identity(group[peer]))['possible'] = [anchor]
        files[s.FILE] = s.r.frame(dict(old, revision=old['revision']+1, previous=e.digest(files[s.FILE]), plan=plan))
    # A completed floor retires the inactive generation and superseded frozen
    # source. The original new promise survives journal rotation.
    result[LEADER] = {k: v for k, v in files.items() if
        (not k.startswith('generations/') or k == directory[:-1] or k.startswith(directory))
        and not k.startswith('sources/')}
    result[LEADER]['grants.gsr'] = members['promise.gsr']
    return result


def physical(root):
    walk, adoptions = d.adopted_history(root)
    before = copy.deepcopy(walk.group); maintained = maintenance(before)
    prepared, chosen, installed = s.campaign(root, {n: maintained[n] for n in VOTERS},
        4, 'node-4-installed', selected_prefix=d.prefix, proposer=LEADER)
    installed = dict(maintained, **installed)
    walk.match('node-4-installed', installed)
    # Unselected owners do not gain voting authority from network failures.
    need(c.inventory(root/'after-close/node-3') == before['node-3'],
         'discovered selection unselected owner unchanged')
    return walk, adoptions, before, maintained, prepared, chosen, installed


def inventory(root):
    need(root.is_dir() and not root.is_symlink(), 'discovered selection regular inventory')
    total = 0
    for count, path in enumerate(root.rglob('*'), 1):
        need(not path.is_symlink() and (path.is_dir() or path.is_file()), 'discovered selection regular inventory')
        if path.is_file(): total += path.stat().st_size
        need(count <= 65536 and total <= 512*e.MIB, 'discovered selection bounded inventory')


def event_boundary(events, node, name):
    found = [i for i, row in enumerate(events) if row.get('node') == node and row.get('event') == name]
    need(len(found) == 1, 'discovered selection exact boundary: '+name)
    return found[0]


def exchanges(root, events, start, stop, identities):
    """Bind every retained wire row to its actual response event, with no gaps."""
    rows = native.read(root/'wire.json'); positions = defaultdict(deque)
    need(type(rows) is list and 0 < len(rows) < 32768 and type(events) is list and len(events) < 32768,
         'discovered selection bounded network')
    for at, row in enumerate(events):
        if row.get('event') == 'WIRE_RESPONSE': positions[row['request'], row['response']].append((at, row['node']))
    result = []
    for row in rows:
        need(set(row) == {'request', 'response', 'withheld'} and row['withheld'] is False,
             'discovered selection complete wire row')
        request_raw, response_raw = (base64.b64decode(row[k], validate=True) for k in ('request', 'response'))
        qhash, rhash = e.digest(request_raw), e.digest(response_raw)
        need(bool(positions[qhash, rhash]), 'discovered selection response event')
        at, owner = positions[qhash, rhash].popleft()
        if not start < at < stop: continue
        kind, request = d.transfer.t.wire(row['request']); answer, response = d.transfer.t.wire(row['response'])
        sender, peer = request['sender']['node'], request['recipient']['node']
        need(sender in identities and peer in identities and sender != peer and owner == peer
             and request['sender'] == identities[sender] and request['recipient'] == identities[peer],
             'discovered selection permanent wire owners')
        need({k: v for k, v in response.items() if k != 'payload'} ==
             dict({k: v for k, v in request.items() if k != 'payload'}, sender=identities[peer], recipient=identities[sender]),
             'discovered selection wire correlation')
        delivered = [i for i, v in enumerate(events) if at < i < stop and v ==
                     dict(node=sender, event='NETWORK_RECEIVED', kind=answer, response=rhash)]
        result.append(dict(row={k: row[k] for k in ('request', 'response')}, kind=kind, request=request,
                           answer=answer, response=response, offered=at, deliveries=delivered))
    need(not any(positions.values()), 'discovered selection unmatched response event')
    return result


def identical_attempts(entries):
    need(0 < len(entries) <= 3 and all(v['row'] == entries[0]['row'] for v in entries),
         'discovered selection identical bounded attempts')
    need(any(v['deliveries'] for v in entries), 'discovered selection response delivered')
    return min(i for v in entries for i in v['deliveries'])


def network(root, before, maintained, prepared, chosen, installed):
    events = native.read(root/'events.json')
    start = event_boundary(events, LEADER, 'ROUND_ADOPTED')
    stop = event_boundary(events, LEADER, 'ROUND_INSTALLED')
    need(start < stop, 'discovered selection adoption before installation')
    identities = {n: a.u.identity(files) for n, files in before.items()}
    local = c.current(installed[LEADER])[1]; selected_raw = local['selected.gsr']
    selected = f.decode(selected_raw, 'records', 'SELECTED'); ballot = selected['ballot']; view = selected['view']
    old_ballot = f.decode(c.current(before[LEADER])[1]['promise.gsr'], 'records', 'PROMISE')['ballot']
    row = events[stop]
    need(row == dict(node=LEADER, event='ROUND_INSTALLED', record=e.digest(selected_raw),
                     bytes=base64.b64encode(selected_raw).decode()), 'discovered selection original installed event')
    own_events = {n: [(i, v['event']) for i, v in enumerate(events) if start < i < stop and v['node'] == n] for n in identities}

    def at(node, name):
        found = [i for i, v in own_events[node] if v == name]
        need(len(found) == 1, 'discovered selection one force: '+node+': '+name)
        return found[0]

    # Complete forces and reclamation precede a fresh allocation; the selected
    # majority is installed before ROUND_INSTALLED can admit its first slot.
    floor = at(LEADER, 'FLOOR_PARENT_FORCED')
    s.ordered([v for _, v in own_events[LEADER]], [
        'FLOOR_COPIES_FORCED', 'FLOOR_AUTHORITY_FORCED', 'FLOOR_PARENT_FORCED',
        'FLOOR_BEFORE_RETURN', *(['RETENTION_PARENT_FORCED']*4),
        'RETIREMENT_AUTHORITY_FORCED', 'RETIREMENT_PARENT_FORCED', 'RETIREMENT_DELETE_VALIDATED', 'RETIREMENT_CLEARED',
        'SOURCE_RETIREMENT_FORCED', 'SOURCE_RETIREMENT_PARENT_FORCED', 'JOURNAL_ROTATION_FORCED', 'JOURNAL_ROTATION_PARENT_FORCED',
        'SOURCE_RETIREMENT_JOURNAL_PRUNED', 'SOURCE_RETIREMENT_CLEARED',
        'FLOOR_RELEASE_AUTHORITY_FORCED', 'FLOOR_RELEASE_PARENT_FORCED', 'FLOOR_RELEASE_RELINQUISHED', 'FLOOR_RELEASE_BEFORE_RETURN',
        'ALLOCATOR_DIRECTORY_FORCED', 'PROMISE_FORCED', 'SOURCE_DIRECTORY_FORCED', 'BASIS_FORCED',
        'SELECTED_FORCED', 'INSTALL_SELECTOR_FORCED', 'INSTALL_PARENT_FORCED',
        'RETENTION_PARENT_FORCED', 'SELECTED_RETENTION_COMPLETED', 'INSTALL_BEFORE_RETURN'],
        'discovered selection local maintenance/activation')
    for node in VOTERS:
        for name in ('PROMISE_FORCED', 'SOURCE_DIRECTORY_FORCED', 'BASIS_FORCED', 'SELECTED_FORCED', 'INSTALL_BEFORE_RETURN'):
            at(node, name)
    for node in ('node-3', 'node-5'):
        need(not own_events[node], 'discovered selection no unselected writes')

    entries = exchanges(root, events, start, stop, identities); traces = defaultdict(list); controls = defaultdict(list)
    for entry in entries:
        request = entry['request']
        need(request['root'] == selected['root'] and request['view'] == view and request['ballot'] in (old_ballot, ballot),
             'discovered selection wire authority')
        if entry['kind'] in ('CHUNK', 'TRANSFER_COMMIT'): traces[request['trace']].append(entry)
        else: controls[entry['kind'], request['recipient']['node']].append(entry)

    available = []
    for trace, values in traces.items():
        logical = defaultdict(list)
        for v in values: logical[v['request']['sequence']].append(v)
        need(sorted(logical) == list(range(1, len(logical)+1)), 'discovered selection transfer sequences')
        delivered = [identical_attempts(attempts) for _, attempts in sorted(logical.items())]
        ordered = [logical[i][0] for i in sorted(logical)]
        need(all(delivered[i] < ordered[i+1]['offered'] for i in range(len(ordered)-1)),
             'discovered selection transfer delivery order')
        q = ordered[0]['request']
        available.append(dict(trace=trace, sender=q['sender']['node'], peer=q['recipient']['node'],
            reference=q['payload']['digest'], ballot=q['ballot'], offered=ordered[0]['offered'], delivered=delivered[-1],
            rows=[v['row'] for v in ordered]))

    used_traces = set(traces)

    def consume(reader, peer, variants, expected_ballot, lower, upper):
        references = {v[0][0] for v in variants}
        found = [v for v in available if v['sender'] == reader and v['peer'] == peer and v['reference'] in references]
        need(len(found) == 1, 'discovered selection complete original transfer')
        value = found[0]; available.remove(value)
        need(value['ballot'] == expected_ballot and lower < value['offered'] < value['delivered'] < upper,
             'discovered selection original transfer before authority')
        # Choose a transfer representation by its original reference, never by
        # data learned from the remote offer. Current and packet-only scopes
        # have distinct references; shared references differ only by images.
        matching = [v for v in variants if v[0][0] == value['reference']]
        expected = next((v for v in matching if len(value['rows']) == sum(2+(len(raw)+4*e.MIB-1)//(4*e.MIB) for _, raw, _ in v)), None)
        need(expected is not None, 'discovered selection complete transfer shape')
        d.transfer.transcript(value['rows'], expected, selected['root'], view, expected_ballot,
            identities[reader], identities[peer], 'discovered selection transfer', chunk_bytes=4*e.MIB)
        return value

    for peer in ('node-1', 'node-2'):
        directory, members, packet = c.current(before[peer])
        consume(LEADER, peer, native.maintenance_prefixes(members, packet, c.current(before[LEADER])[1]), old_ballot, start, floor)
        consume(LEADER, peer, native.maintenance_generations(before[peer][directory+'generation.gsr'], members, packet), old_ballot, start, floor)
        entries = controls.pop(('STATUS_PROBE', peer), [])
        delivered = identical_attempts(entries); req = entries[0]['request']; ans = entries[0]['response']
        need(req['sender'] == identities[LEADER] and req['ballot'] == old_ballot and req['sequence'] == 1
             and req['trace'] not in used_traces
             and entries[0]['answer'] == 'STATUS' and ans['payload'] == dict(cut=packet['capsule']['cut'], nonce=req['payload']['nonce'], ready=False)
             and delivered < floor, 'discovered selection maintenance probe')
        used_traces.add(req['trace'])

    def record(files, name):
        raw = c.current(files)[1][name]
        return [(e.digest(raw), raw, 'RECORD')]

    def frozen(peer, reader):
        members = c.current(installed[peer])[1]; basis = f.decode(members['basis.gsr'], 'records', 'BASIS')
        raw = prepared[peer]['sources/'+basis['basisId']+'/source.gscp']; packet = e.p.decode(raw)
        expected = [(e.digest(members[k]), members[k], 'RECORD') for k in ('basis.gsr', 'promise.gsr')]
        variants = native.prefix_transfers(e.digest(packet['capsuleBytes']),
            dict(members, **{'source.gscp': raw}), packet, c.current(maintained[reader])[1])
        return [expected+v for v in variants]

    campaign_trace = None
    for ordinal, peer in enumerate(('node-1', 'node-2'), 1):
        consume(peer, LEADER, [record(installed[LEADER], 'promise.gsr')], ballot,
                at(LEADER, 'BASIS_FORCED'), at(peer, 'PROMISE_FORCED'))
        consume(LEADER, peer, frozen(peer, LEADER), ballot, at(peer, 'BASIS_FORCED'), at(LEADER, 'SELECTED_FORCED'))
        consume(peer, LEADER, [record(installed[LEADER], 'selected.gsr')], ballot,
                at(LEADER, 'SELECTED_FORCED'), at(peer, 'SELECTED_FORCED'))
        for source in VOTERS:
            if source != peer:
                consume(peer, source, frozen(source, peer), ballot, at(source, 'BASIS_FORCED'), at(peer, 'SELECTED_FORCED'))
        for kind, answer, request_payload, response_payload, force in [
            ('PREPARE', 'PROMISE', dict(promise=e.digest(local['promise.gsr'])),
             dict(basis=e.digest(c.current(installed[peer])[1]['basis.gsr'])), 'GRANT_BEFORE_RETURN'),
            ('SELECTED', 'INSTALL_ACK', dict(selection=e.digest(selected_raw)),
             dict(selection=e.digest(selected_raw), cut=selected['cut']), 'INSTALL_BEFORE_RETURN')]:
            entries = controls.pop((kind, peer), []); delivery = identical_attempts(entries)
            trace = entries[0]['request']['trace']
            if campaign_trace is None:
                need(trace not in used_traces, 'discovered selection separate activation trace')
                campaign_trace = trace
            need(all(v['request']['sender'] == identities[LEADER] and v['request']['ballot'] == ballot
                     and v['request']['trace'] == campaign_trace and v['request']['sequence'] == ordinal+(2 if kind == 'SELECTED' else 0)
                     and v['answer'] == answer and v['request']['payload'] == request_payload and v['response']['payload'] == response_payload
                     and at(peer, force) < v['offered'] < stop for v in entries) and delivery < stop,
                 'discovered selection exact control')
        s.ordered([v for _, v in own_events[peer]], ['PROMISE_FORCED', 'SOURCE_DIRECTORY_FORCED', 'BASIS_FORCED',
            'GRANT_BEFORE_RETURN', 'SELECTED_FORCED', 'INSTALL_SELECTOR_FORCED', 'INSTALL_PARENT_FORCED',
            'RETENTION_PARENT_FORCED', 'SELECTED_RETENTION_COMPLETED', 'INSTALL_BEFORE_RETURN'],
            'discovered selection peer activation')
    need(not available and not controls, 'discovered selection no unclassified exchanges')
    return dict(transfers=len(traces), installed=list(VOTERS), ballot=ballot['counter'], boundary=stop)


def inspect(root):
    root = Path(root)
    inventory(root)
    walk, adoptions, before, maintained, prepared, chosen, installed = physical(root)
    observed = network(root, before, maintained, prepared, chosen, installed)
    return dict(status='PARTIAL', scope='original-prelude-adoption-installation', originalFirst=True,
        originalSlots=7, adoptions=adoptions, snapshots=len(walk.snapshots), activation=observed,
        fullHistoryQualified=False, autonomousElection=False, phase3Complete=False)


NEGATIVES = {
    'installed-selector': 'admitted exact node-4-installed: node-2',
    'installed-image': 'admitted exact node-4-installed: node-4',
    'installed-retention': 'admitted exact node-4-installed: node-1',
    'restored-obsolete-source': 'admitted exact node-4-installed: node-4',
    'unselected-owner': 'discovered selection unselected owner unchanged',
    'original-boundary': 'discovered selection original installed event',
    'missing-floor-force': 'discovered selection one force: node-4: FLOOR_PARENT_FORCED',
    'missing-copies-force': 'selected retention force order: discovered selection local maintenance/activation',
    'missing-retirement-force': 'selected retention force order: discovered selection local maintenance/activation',
    'missing-grant-force': 'discovered selection one force: node-2: BASIS_FORCED',
    'missing-install-force': 'selected retention force order: discovered selection peer activation',
    'early-floor': 'discovered selection original transfer before authority',
    'early-selection': 'discovered selection original transfer before authority',
    'missing-delivery': 'discovered selection response delivered',
    'unmatched-response': 'discovered selection unmatched response event',
    'changed-source-bytes': 'discovered selection transfer exact data',
    'foreign-reply-owner': 'discovered selection wire correlation',
    'wrong-install-ack': 'discovered selection exact control',
    'fourth-attempt': 'discovered selection identical bounded attempts',
    'unselected-write': 'discovered selection no unselected writes',
    'linked-original': 'discovered selection regular inventory',
}


def mutate(path, name):
    if name == 'linked-original':
        (path/'linked-original').symlink_to('original-plan.gsbp'); return
    targets = {'installed-selector': 'node-4-installed/node-2/selector.gsr',
        'installed-retention': 'node-4-installed/node-1/'+s.FILE, 'unselected-owner': 'after-close/node-3/allocator.gsr'}
    if name in targets: (path/targets[name]).write_bytes(b'changed'); return
    if name == 'installed-image':
        own = c.inventory(path/'node-4-installed/node-4'); directory, _, packet = c.current(own)
        (path/'node-4-installed/node-4'/directory/(packet['capsule']['application']+'.image')).write_bytes(b'changed'); return
    if name == 'restored-obsolete-source':
        before = c.inventory(path/'node-4-adopted/node-4'); after = c.inventory(path/'node-4-installed/node-4')
        for key in sorted(before.keys()-after.keys()):
            if key.startswith('sources/'):
                target = path/'node-4-installed/node-4'/key
                if before[key] is None: target.mkdir(parents=True, exist_ok=True)
                else: target.write_bytes(before[key])
        return
    events = native.read(path/'events.json'); rows = native.read(path/'wire.json')
    start = event_boundary(events, LEADER, 'ROUND_ADOPTED'); stop = event_boundary(events, LEADER, 'ROUND_INSTALLED')

    def find(node, event):
        return next(v for v in events[start+1:stop] if v['node'] == node and v['event'] == event)

    if name == 'original-boundary':
        value = events[stop]; raw = base64.b64decode(value['bytes']); selected = f.decode(raw, 'records', 'SELECTED')
        selected['ballot']['counter'] += 1; raw = f.encode('records', 'SELECTED', selected)
        value.update(record=e.digest(raw), bytes=base64.b64encode(raw).decode())
    elif name.startswith('missing-') and name.endswith('-force'):
        node, event = {'missing-floor-force': (LEADER, 'FLOOR_PARENT_FORCED'),
            'missing-copies-force': (LEADER, 'FLOOR_COPIES_FORCED'),
            'missing-retirement-force': (LEADER, 'JOURNAL_ROTATION_PARENT_FORCED'),
            'missing-grant-force': ('node-2', 'BASIS_FORCED'),
            'missing-install-force': ('node-2', 'INSTALL_PARENT_FORCED')}[name]
        events.remove(find(node, event))
    elif name in ('early-floor', 'early-selection'):
        # Preserve per-owner force ordering, but move the remote delivered
        # source to after its dependent floor/selection authority.
        upper = find(LEADER, 'FLOOR_PARENT_FORCED' if name == 'early-floor' else 'SELECTED_FORCED')
        limit = events.index(upper)
        delivery = next(v for v in reversed(events[start:limit]) if v['node'] == LEADER and
                        v['event'] == 'NETWORK_RECEIVED' and v['kind'] == 'TRANSFER_COMMIT')
        events.remove(delivery); events.insert(events.index(upper)+1, delivery)
    elif name == 'missing-delivery':
        events.remove(next(v for v in events[start+1:stop] if v['event'] == 'NETWORK_RECEIVED' and v['kind'] == 'TRANSFER_COMMIT'))
    elif name == 'unmatched-response':
        victim = next(v for v in events[start+1:stop] if v['event'] == 'WIRE_RESPONSE')
        rows = [v for v in rows if e.digest(base64.b64decode(v['request'])) != victim['request']]
    elif name == 'unselected-write': events.insert(stop, dict(node='node-3', event='PROMISE_FORCED'))
    else:
        in_scope = {v['response'] for v in events[start+1:stop] if v['event'] == 'WIRE_RESPONSE'}
        wanted = 'CHUNK' if name == 'changed-source-bytes' else 'INSTALL_ACK'
        victim = next(v for v in rows if e.digest(base64.b64decode(v['response'])) in in_scope
                      and d.transfer.t.wire(v['response'])[0] == wanted)
        old = e.digest(base64.b64decode(victim['response'])); kind, response = d.transfer.t.wire(victim['response'])
        if name == 'fourth-attempt':
            attempts = [v for v in rows if v == victim]
            event = next(v for v in events if v['event'] == 'WIRE_RESPONSE' and v['response'] == old)
            for _ in range(4-len(attempts)):
                rows.insert(rows.index(victim), copy.deepcopy(victim)); events.insert(events.index(event), copy.deepcopy(event))
        else:
            if name == 'changed-source-bytes': response['payload'].update(bytes=base64.b64encode(b'changed').decode(), digest=e.digest(b'changed'))
            elif name == 'foreign-reply-owner': response['sender']['storage'] = a.u.identity(c.inventory(path/'node-4-installed/node-5'))['storage']
            else: response['payload']['selection'] = '0'*64
            raw = f.encode('wire', kind, response)
            for row in rows:
                if e.digest(base64.b64decode(row['response'])) == old: row['response'] = base64.b64encode(raw).decode()
            for event in events:
                if event.get('response') == old: event['response'] = e.digest(raw)
    (path/'events.json').write_bytes(f.canonical(events)); (path/'wire.json').write_bytes(f.canonical(rows))


def qualify(root):
    original = inspect(root); negatives = []
    for name, reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-discovered-selection-negative-') as temp:
            path = Path(temp)/'raw'; shutil.copytree(root, path); mutate(path, name)
            try: inspect(path)
            except ValueError as error: need(str(error) == reason, 'discovered selection unrelated negative: '+name+': '+str(error))
            else: raise ValueError('discovered selection accepted negative: '+name)
        negatives.append(dict(case=name, status='REJECTED', reason=reason))
    return dict(original=original, negatives=negatives)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('directory'); parser.add_argument('--qualify', action='store_true'); args = parser.parse_args()
    print(json.dumps((qualify if args.qualify else inspect)(Path(args.directory)), sort_keys=True))
