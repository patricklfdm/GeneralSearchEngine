"""Replay native activation followed by two continuous stable slots from originals.

Only fresh UUIDs and the typed DATA image are observations. Neither result.json,
wire ACKs nor a Java assertion supplies vote or floor authority. This explicit
sender qualification does not establish autonomous elections or joint consensus.
"""
import argparse
import base64
from collections import defaultdict
import copy
import json
from pathlib import Path
import shutil
import struct
import tempfile
from . import slot_endpoint_evidence as slot
from . import promised_source_evidence as transfer
from . import offline_fixture_image as image

b, c, e, f, need = slot.b, slot.c, slot.e, slot.f, slot.need
s, future = slot.future.s, slot.future.future
read = slot.read
VOTERS = ('node-1', 'node-2')


def prefix_transfers(reference, members, packet, local_members):
    """Only identical original current image bytes may replace an image download.

    Both the older full transfer and the live-image-borrowing implementation are
    replayable. A hash in a remote packet alone never makes a missing image valid.
    The independent physical replay already authenticated both member inventories.
    """
    first = [(reference, members['source.gscp'], 'CAPSULE')]
    images = [(h, members[h+'.image'], 'APPLICATION') for h in sorted(packet['images'])]
    received = [item for item in images if local_members.get(item[0]+'.image') != item[1]]
    return [first+images, first+received]


def current_reference(capsule, scope):
    return e.digest(f.canonical(dict(root=capsule['root'], cut=capsule['cut'], scope=scope)))


def maintenance_prefixes(members, packet, local_members):
    """The packet-only scope is complete only with every exact original image.

    Read-only aliases are derived from the physically replayed remote cut, never
    learned from a received offer. Retain the older whole-prefix representations
    for historical evidence; a narrowed transfer cannot borrow missing bytes.
    """
    variants = prefix_transfers(e.digest(f.canonical(packet['capsule']['cut'])), members, packet, local_members)
    if all(local_members.get(h+'.image') == members[h+'.image'] for h in packet['images']):
        variants.append([(current_reference(packet['capsule'], 'retained-current-packet'), members['source.gscp'], 'CAPSULE')])
    return variants


def maintenance_generations(manifest, members, packet):
    """Both export scopes must deliver the same complete original metadata."""
    tail = [(e.digest(members['ancestry.gsr']), members['ancestry.gsr'], 'RECORD')] if 'ancestry.gsr' in members else []
    tail += [(e.digest(value), value, 'RECORD') for key, value in sorted(members.items())
             if key not in ('generation.gsr', 'source.gscp', 'ancestry.gsr') and not key.endswith('.image')]
    return [[(current_reference(packet['capsule'], scope), manifest, 'RECORD')]+tail
            for scope in ('retained-current-generation', 'retained-current-generation-metadata')]


def activation_attempts(entries):
    """A repeated installation ACK may finish after an earlier socket expired.

    Permit only the existing finite, byte-identical request/response attempts;
    event positions differ but a new trace, source set or ACK cannot substitute.
    """
    need(0 < len(entries) <= 3 and all(v[:4] == entries[0][:4] for v in entries), 'native dispatch activation controls')
    return entries


def maintenance(group, *, confirmed_retention=False):
    """Derive floor observations and inactive-generation retirement."""
    result = dict(group)
    for node in VOTERS:
        files = group[node]; current = c.current(files)[0]
        files = {k: v for k, v in files.items() if not k.startswith('generations/') or k == current[:-1] or k.startswith(current)}
        # Actual collection visits self, then the other original majority member.
        for peer in (node, next(n for n in VOTERS if n != node)):
            if confirmed_retention:
                from .peer_observation_evidence import observe_same_cut
                files[s.FILE] = observe_same_cut(files[s.FILE], group[node], group[peer])
                continue
            previous = s.r.decode(files[s.FILE]); plan = copy.deepcopy(previous['plan'])
            identity = future.identity(group[peer]); anchor = c.anchor(c.current(group[peer])[2]['capsule'])
            next(row for row in plan['peers'] if row['identity'] == identity)['possible'] = [anchor]
            files[s.FILE] = s.r.frame(dict(previous, revision=previous['revision']+1, previous=e.digest(files[s.FILE]), plan=plan))
        result[node] = files
    return result


def physical(root, *, confirmed_retention=False):
    group = s.initialize(b.original(root, 3, False))
    group = {n: dict(v, **{future.FILE: future.frame(future.initial(v), {})}) for n, v in group.items()}
    b.match(root, 'before-network', group)
    _, _, selected = s.campaign(root, {n: group[n] for n in VOTERS}, 2, 'installed', selected_prefix=slot.prefix)
    group = dict(group, **selected); b.match(root, 'installed', group)
    _, initial, packet = c.current(group['node-1'])
    chosen = initial['selected.gsr']; selection = f.decode(chosen, 'records', 'SELECTED')
    need(b.t.plans.read(root/'selected.gsr', 65536) == chosen, 'native dispatch original selection')
    return slots(root, group, selection, confirmed_retention=confirmed_retention)


def slots(root, group, selection, *, carried=None, kinds=('BARRIER', 'DATA'), confirmed_retention=False):
    """Replay two complete slots from an independently established installation."""
    chosen = f.encode('records', 'SELECTED', selection)
    states = [copy.deepcopy(group)]; rounds = []; first = None
    identities = {n: future.identity(files) for n, files in group.items()}
    for index, kind in enumerate(kinds, 1):
        before = group
        group = maintenance(group, confirmed_retention=confirmed_retention); states.append(copy.deepcopy(group))
        maintenance_writes = {node: s.r.decode(group[node][s.FILE])['revision'] - s.r.decode(before[node][s.FILE])['revision'] for node in VOTERS}
        retirement_events = {node: [] for node in VOTERS}
        if confirmed_retention and carried is not None and index == 2:
            from .native_source_retirement_evidence import retire_predecessor
            group, retirement_events = retire_predecessor(group, VOTERS)
            states[-1] = copy.deepcopy(group)
        _, local, packet = c.current(group['node-1']); cap = packet['capsule']
        text = b'100:next-slot'; payload = b'\x01'+struct.pack('>HIII', 1, 1, 4, 100)+struct.pack('>I', len(text))+text if kind == 'DATA' else b''
        entry = f.encode('records', 'ENTRY', dict(root=cap['root'], authority=selection['view'], index=index,
            previous=cap['cut']['entry'], origin=selection['ballot'], kind=kind, payload=e.digest(payload)))
        if index == 1 and carried is not None:
            value = f.decode(carried, 'records', 'ENTRY')
            need(dict(value, origin=selection['ballot']) == f.decode(entry, 'records', 'ENTRY')
                 and e.digest(carried) == selection['nextEntry'], 'native dispatch exact carried entry')
            entry = carried
        accept = f.encode('records', 'ACCEPT', dict(root=cap['root'], authority=selection['view'], ballot=selection['ballot'], index=index, entry=e.digest(entry)))
        def receipt(node, phase, raw):
            return f.canonical(dict(root=cap['root'], voter=node, incarnation=identities[node]['storage'], phase=phase, record=e.digest(raw)))
        def witnesses(phase, raw):
            return [dict(voter=n, incarnation=identities[n]['storage'], receipt=e.digest(receipt(n, phase, raw))) for n in VOTERS]
        proof = f.encode('records', 'PROOF', dict(f.decode(accept, 'records', 'ACCEPT'), accepts=witnesses('ACCEPT', accept)))
        certificate = f.encode('records', 'CERTIFICATE', dict(f.decode(proof, 'records', 'PROOF'), proofs=witnesses('PROOF', proof)))
        raw_image = b.t.plans.read(root/f'applied-{index}/node-1/applied-end/application.image', 64*e.MIB)
        root_record = f.decode(group['node-1']['root.gsr'], 'records', 'ROOT')
        image.application(raw_image, root_record['historyId'], 1 if kind == 'DATA' else 0, [(100, 'next-slot')] if kind == 'DATA' else [])
        if kind == 'BARRIER': need(raw_image == local[cap['application']+'.image'], 'native dispatch barrier image')
        catalog = copy.deepcopy(f.decode(packet['objects'][cap['catalog']], 'records', 'CATALOG'))
        catalog['cut'] = dict(cap['cut'], index=index, entry=e.digest(entry))
        if kind == 'DATA': catalog.update(application=e.digest(raw_image), applicationSequence=1, lastDataIndex=index)
        catalog = f.encode('records', 'CATALOG', catalog)
        after = f.decode(catalog, 'records', 'CATALOG'); upper = dict(cut=after['cut'], catalog=e.digest(catalog), application=after['application'])
        start = f.decode(packet['objects'][cap['items'][0]['statement']], 'records', 'CHECKPOINT') if cap['items'] else dict(
            root=cap['root'], scope='RANGE', start=cap['cut'], catalogBefore=cap['catalog'], applicationBefore=cap['application'])
        statement = f.encode('records', 'CHECKPOINT', dict(start, end=after['cut'], catalogAfter=e.digest(catalog), applicationAfter=after['application']))
        lower = f.encode('records', 'CHECKPOINT', dict(f.decode(statement, 'records', 'CHECKPOINT'), start=cap['cut'], catalogBefore=cap['catalog'], applicationBefore=cap['application'])) if index == 2 else None
        applied = dict(group); ends = {}; originals = [entry, accept, proof, certificate, payload]
        for node in VOTERS:
            files = group[node]; _, own, _ = c.current(files)
            vote = e.container([files['selector.gsr'], own['promise.gsr'], chosen, entry, accept], payload)+proof+certificate
            vote = vote[:8]+struct.pack('>I', len(vote))+vote[12:]
            def ack(value): return f.encode('records', 'CHECKPOINT_ACK', dict(root=cap['root'], voter=node, incarnation=identities[node]['storage'], cut=after['cut'], statement=e.digest(value)))
            end = dict(zip(('selector.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr', 'application.image', 'ack.gsr'),
                (files['selector.gsr'], certificate, catalog, statement, raw_image, ack(statement))))
            if lower: end.update({'parent-statement.gsr': lower, 'parent-ack.gsr': ack(lower)})
            end['plan.json'] = f.canonical(dict(schema='gse-v53-applied-end/1.3', root=cap['root'], node=node,
                files=[dict(path=k, **e.info(v)) for k, v in sorted(end.items())]))
            ends[node] = end
            applied[node] = dict(files, **{'pending.accept': vote, 'applied-end': None}, **{'applied-end/'+k: v for k, v in end.items()})
        b.match(root, 'applied-'+str(index), applied); states.append(copy.deepcopy(applied))
        recorded = dict(applied); intent = dict(selection=e.digest(chosen), certificate=e.digest(certificate), peer=identities['node-2'], lower=c.anchor(cap), parent=c.anchor(cap), upper=upper)
        for node in VOTERS:
            files = applied[node]; _, own, _ = c.current(files)
            records = {k: ends[node][k] for k in ('selector.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr', 'ack.gsr')}
            records.update({k: own[k] for k in ('promise.gsr', 'selected.gsr')})
            records.update(dict(zip(('entry.gsr', 'accept.gsr', 'proof.gsr'), originals[:3])))
            metadata = dict(future.initial(files), revision=2*index-1, previous=e.digest(files[future.FILE]), parent=c.anchor(cap), peers=[dict(identity=identities['node-2'], lower=c.anchor(cap))])
            recorded[node] = dict(files, **{future.FILE: future.frame(metadata, records)})
        published = dict(recorded)
        for node in VOTERS:
            published[node], _ = slot.publication(recorded[node], ends[node], ends, list(VOTERS), originals, first, node)
            state = s.r.decode(group[node][s.FILE]); plan = copy.deepcopy(state['plan'])
            next(v for v in plan['peers'] if v['identity'] == identities['node-2'])['possible'].append(upper)
            published[node][s.FILE] = s.r.frame(dict(state, revision=state['revision']+1, previous=e.digest(group[node][s.FILE]), plan=plan))
            published[node][future.FILE] = future.frame(dict(future.initial(group[node]), revision=2*index, previous=e.digest(recorded[node][future.FILE])), {})
        b.match(root, 'published-'+str(index), published); states.append(copy.deepcopy(published))
        receipts = {(node, phase): receipt(node, phase, raw) for node in VOTERS for phase, raw in [('ACCEPT', accept), ('PROOF', proof)]}
        rounds.append(dict(index=index, cap=cap, originals=originals, ends=ends, receipts=receipts, intent=intent, recorded=recorded, published=published, upper=upper, maintenanceWrites=maintenance_writes, retirementEvents=retirement_events))
        if first is None: first = dict(parent=c.anchor(cap), end=upper, certificate=e.digest(certificate), proof={e.digest(v): v for v in originals})
        group = published
    b.match(root, 'after-close', group)
    return states, rounds, selection, identities


def discovery_controls(root, entries, events, selection, identities):
    """This exact stable history has two read-only probes before any new grant.

    Their correlation fence and cuts come from physically validated pre-network
    files, not STATUS. Later maintenance and every voting frame retain the actual
    selected ballot. This is not a general heterogeneous adoption validator.
    """
    original = {node: c.inventory(root/'before-network'/node) for node in identities}
    promises = [value for kind, _, value in c.journal(original['node-1']['grants.gsr'], selection['root'], 'node-1') if kind=='PROMISE']
    need(len(promises)==1, 'native discovery original fence')
    fence = promises[0]
    peers = sorted(set(identities)-{'node-1'})
    need(len(entries)==len(peers) and [v[1]['recipient']['node'] for v in entries]==peers,
         'native discovery complete known scan')
    first_write = next((i for i, row in enumerate(events) if row['node']=='node-1' and row['event']=='ALLOCATOR_BEFORE_WRITE'), None)
    need(first_write is not None, 'native discovery before grant')
    previous = -1; traces = set()
    for (_, request, answer, response, at), peer in zip(entries, peers):
        need(request['sender']==identities['node-1'] and request['ballot']==fence['ballot'] and request['view']==fence['view']
             and request['sequence']==1 and request['trace'] not in traces, 'native discovery original fence')
        traces.add(request['trace']); cut = c.current(original[peer])[2]['capsule']['cut']
        need(answer=='STATUS' and response['payload']==dict(cut=cut,nonce=request['payload']['nonce'],ready=False),
             'native discovery original status')
        digest = e.digest(f.encode('wire', answer, response))
        delivered = [i for i, row in enumerate(events) if row==dict(node='node-1',event='NETWORK_RECEIVED',kind='STATUS',response=digest)]
        need(len(delivered)==1 and previous < at < delivered[0] < first_write, 'native discovery before grant')
        previous = delivered[0]


def round_maintenance_boundary(events, begin):
    """The serialized owner may maintain READY copies before allocating slot 2.

    Use its completed first publication boundary, never a guessed floor count.
    The caller binds the completion to the independently replayed original ACK.
    """
    completed = [i for i, ev in enumerate(events) if ev['event'] == 'ROUND_SLOT_COMPLETE']
    need(len(completed) == 2 and begin[0] < completed[0] < begin[1] < completed[1],
         'native dispatch serialized round boundaries')
    return completed[0]


def round_publication_boundary(events, begin, first, selection, identity):
    at = round_maintenance_boundary(events, begin); row = events[at]
    need(set(row) == {'node','event','record','bytes'} and row['node'] == 'node-1', 'round local event owner')
    raw = base64.b64decode(row['bytes'], validate=True)
    need(e.digest(raw) == row['record'], 'round event digest')
    ack = f.decode(raw, 'wire', 'PUBLISH_ACK')
    directory, _, _ = c.current(first['published']['node-1'])
    expected = dict(certificate=e.digest(first['originals'][3]), selection=e.digest(f.encode('records','SELECTED',selection)),
                    published=first['upper'], generation=e.digest(first['published']['node-1'][directory+'generation.gsr']))
    need(ack['root']==selection['root'] and ack['view']==selection['view'] and ack['ballot']==selection['ballot']
         and ack['sender']==ack['recipient']==identity and ack['sequence']==1 and ack['payload']==expected,
         'round original publication acknowledgement')
    return at


def network(root, states, rounds, selection, identities, *, carried_first=False, discovery=False, confirmed_retention=False, precommand_maintenance=False):
    events = read(root/'events.json'); rows = read(root/'wire.json'); content = {}; refs = defaultdict(set)
    need(type(events) is list and len(events) < 32768 and type(rows) is list and 0 < len(rows) < 32768, 'native dispatch bounded traces')
    def add(node, raw, kind='RECORD', reference=None):
        if not raw: return
        h = e.digest(raw); content[node, h] = raw; refs[node, h].add((reference or h, kind))
    for group in states:
        for node, files in group.items():
            for name, raw in files.items():
                if raw is None or not raw: continue
                if name.endswith('source.gscp'):
                    packet = e.p.decode(raw); add(node, raw, 'CAPSULE', e.digest(packet['capsuleBytes']))
                    add(node, raw, 'CAPSULE', e.digest(f.canonical(packet['capsule']['cut'])))
                    for value in packet['objects'].values(): add(node, value)
                else: add(node, raw, 'APPLICATION' if name.endswith('.image') else 'RECORD')
            directory, members, packet = c.current(files)
            add(node, files[directory+'generation.gsr'], reference=e.digest(f.canonical(dict(root=selection['root'], cut=packet['capsule']['cut'], scope='retained-current-generation'))))
            add(node, members['source.gscp'], 'CAPSULE', current_reference(packet['capsule'], 'retained-current-packet'))
            add(node, files[directory+'generation.gsr'], reference=current_reference(packet['capsule'], 'retained-current-generation-metadata'))
            for _, raw, _ in c.journal(files['grants.gsr'], selection['root'], node): add(node, raw)
    for round in rounds:
        for node in VOTERS:
            for value in round['originals']: add(node, value)
        for (node, _), value in round['receipts'].items():
            add(node, value, reference=e.digest(f.canonical(dict(schema='gse-v53-vote-observation/1.3', receipt=e.digest(value)))))
    traces = defaultdict(list); controls = defaultdict(list); response_positions = defaultdict(list); probes = []
    for i, event in enumerate(events):
        if event['event'] == 'WIRE_RESPONSE': response_positions[event['request'], event['response']].append(i)
    for row in rows:
        need(set(row) == {'request','response','withheld'} and row['withheld'] is False, 'native dispatch successful wire row')
        kind, request = transfer.t.wire(row['request']); answer, response = transfer.t.wire(row['response'])
        sender, target = request['sender']['node'], request['recipient']['node']
        initial_probe = discovery and kind=='STATUS_PROBE' and request['ballot']!=selection['ballot']
        need(sender in identities and target in identities and sender != target and request['sender'] == identities[sender] and request['recipient'] == identities[target]
             and request['root'] == selection['root'] and request['view'] == selection['view']
             and (initial_probe or request['ballot'] == selection['ballot']), 'native dispatch wire authority')
        need({k:v for k,v in response.items() if k != 'payload'} == dict({k:v for k,v in request.items() if k != 'payload'}, sender=request['recipient'], recipient=request['sender']), 'native dispatch wire correlation')
        key = (e.digest(base64.b64decode(row['request'], validate=True)), e.digest(base64.b64decode(row['response'], validate=True)))
        need(response_positions[key], 'native dispatch response event'); at = response_positions[key].pop(0)
        entry = (kind, request, answer, response, at)
        if initial_probe: probes.append(entry)
        elif kind in ('CHUNK','TRANSFER_COMMIT'): traces[request['trace']].append((row, entry))
        else: controls[kind].append(entry)
    need(not any(response_positions.values()), 'native dispatch unmatched response event')
    if discovery: discovery_controls(root, probes, events, selection, identities)
    transfers = []
    for trace in traces.values():
        logical = {}
        for row, decoded in trace:
            sequence = decoded[1]['sequence']; logical.setdefault(sequence, []).append((row, decoded))
        ordered = []
        for sequence, attempts in sorted(logical.items()):
            need(sequence == len(ordered)+1 and len(attempts) <= 3 and all(row == attempts[0][0] for row, _ in attempts), 'native dispatch identical transfer retries')
            ordered.append(attempts[0])
        first = ordered[0][1][1]; sender, peer = first['sender']['node'], first['recipient']['node']; expected = []
        for _, (kind, request, answer, response, _) in ordered:
            if answer != 'SOURCE_OFFER': continue
            h = response['payload']['digest']; reference = request['payload']['digest']; offered_kind = response['payload']['kind']
            need((peer, h) in content and (reference, offered_kind) in refs[peer, h], 'native dispatch original transfer offer')
            expected.append((reference, content[peer, h], offered_kind))
        transfer.transcript([{k:row[k] for k in ('request','response')} for row, _ in ordered], expected,
            selection['root'], selection['view'], selection['ballot'], identities[sender], identities[peer], 'native dispatch transfer', chunk_bytes=4*e.MIB)
        last = ordered[-1][1]; digest = e.digest(f.encode('wire', last[2], last[3]))
        delivered = [i for i, ev in enumerate(events) if ev == dict(node=sender, event='NETWORK_RECEIVED', kind=last[2], response=digest)]
        need(delivered, 'native dispatch transfer delivered')
        transfers.append(dict(sender=sender, peer=peer, first=first['payload']['digest'], objects=expected, offered=ordered[0][1][4], delivered=min(delivered)))
    _, installed, _ = c.current(states[0]['node-1']); chosen = installed['selected.gsr']
    _, remote, _ = c.current(states[0]['node-2'])
    for kind, answer, sent, response in [('PREPARE','PROMISE',dict(promise=e.digest(installed['promise.gsr'])),dict(basis=e.digest(remote['basis.gsr']))),
            ('SELECTED','INSTALL_ACK',dict(selection=e.digest(chosen)),dict(selection=e.digest(chosen), cut=selection['cut']))]:
        for _, req, ans, reply, at in activation_attempts(controls.pop(kind, [])):
            need(req['sender'] == identities['node-1'] and req['recipient'] == identities['node-2'] and ans == answer and req['payload'] == sent and reply['payload'] == response, 'native dispatch activation controls')
            s.ordered([ev['event'] for ev in events[:at] if ev['node'] == 'node-2'], ['PROMISE_FORCED','BASIS_FORCED'] + (['INSTALL_SELECTOR_FORCED','INSTALL_BEFORE_RETURN'] if kind == 'SELECTED' else []), 'native activation before ACK')
    def original_transfer(reader, peer, expected, before_event):
        found = [v for v in transfers if v['sender'] == reader and v['peer'] == peer and v['first'] == expected[0][0]]
        at = next(i for i, ev in enumerate(events) if ev['node'] == reader and ev['event'] == before_event)
        need(len(found) == 1 and found[0]['objects'] == expected and found[0]['delivered'] < at, 'native dispatch original activation delivery')
    for reader, peer, name, before_event in [('node-2','node-1','promise.gsr','PROMISE_FORCED'), ('node-2','node-1','selected.gsr','INSTALL_SELECTOR_FORCED')]:
        raw = c.current(states[0][peer])[1][name]
        original_transfer(reader, peer, [(e.digest(raw),raw,'RECORD')], before_event)
    for reader, peer, before_event in [('node-1','node-2','SELECTED_FORCED'), ('node-2','node-1','INSTALL_SELECTOR_FORCED')]:
        members = c.current(states[0][peer])[1]; basis = f.decode(members['basis.gsr'], 'records', 'BASIS')
        source = states[0][peer]['sources/'+basis['basisId']+'/source.gscp']; packet = e.p.decode(source)
        expected = [(e.digest(members[k]),members[k],'RECORD') for k in ('basis.gsr','promise.gsr')]
        expected.append((e.digest(packet['capsuleBytes']),source,'CAPSULE'))
        original_transfer(reader, peer, expected, before_event)
    probes = controls.pop('STATUS_PROBE', []); need(len(probes) == 4, 'native dispatch original floor discovery')
    for _, req, answer, reply, _ in probes:
        need(answer == 'STATUS' and req['sequence'] == 1 and reply['payload']['nonce'] == req['payload']['nonce'] and reply['payload']['ready'] is False and
             reply['payload']['cut'] in [round['cap']['cut'] for round in rounds], 'native dispatch original floor discovery')
    begin = [i for i, ev in enumerate(events) if ev['event'] == 'SLOT_BEGIN']
    need(len(begin) == 2 and [events[i].get('index') for i in begin] == [1,2], 'native dispatch slot boundaries')
    need(all(v[4] > begin[0] for entries in controls.values() for v in entries), 'native dispatch control before first slot')
    windows = list(begin)
    if precommand_maintenance:
        need(not carried_first, 'native dispatch stable precommand maintenance only')
        windows[1] = round_publication_boundary(events, begin, rounds[0], selection, identities['node-1'])
    for round, start, stop, before in zip(rounds, windows, windows[1:]+[len(events)], (states[0], states[3])):
        index = round['index']; entry, accept, proof, certificate, _ = round['originals']
        part = events[start:stop]
        mutation_forces = {'ACCEPT_PARENT_FORCED','PROOF_PARENT_FORCED','CERTIFICATE_PARENT_FORCED',
                           'APPLY_ACK_DIRECTORY_FORCED','FUTURE_RETENTION_PARENT_FORCED','PUBLICATION_SELECTOR_FORCED'}
        need(not any(ev['event'] in mutation_forces for ev in events[start:begin[index-1]]),
             'native dispatch mutation before slot admission')
        for node in VOTERS:
            own = [(i+start, ev) for i, ev in enumerate(part) if ev['node'] == node]
            names = [ev['event'] for _, ev in own]
            count = round['maintenanceWrites'][node] if confirmed_retention else 2
            need(type(count) is int and 0 <= count <= 2, 'native dispatch bounded original observations')
            required = ['FLOOR_PARENT_FORCED','FLOOR_BEFORE_RETURN'] + ['RETENTION_PARENT_FORCED']*count + [
                'RETIREMENT_DELETE_VALIDATED','RETIREMENT_CLEARED','FLOOR_RELEASE_RELINQUISHED','FLOOR_RELEASE_BEFORE_RETURN',
                'ACCEPT_PARENT_FORCED','PROOF_PARENT_FORCED','CERTIFICATE_PARENT_FORCED','APPLY_ACK_DIRECTORY_FORCED',
                'FUTURE_RETENTION_PARENT_FORCED','PUBLICATION_SELECTOR_FORCED','FUTURE_RETENTION_PROMOTED','PUBLICATION_BEFORE_RETURN']
            if carried_first and index == 1:
                required.remove('ACCEPT_PARENT_FORCED'); required.insert(0, 'ACCEPT_PARENT_FORCED')
            s.ordered(names, required, 'native dispatch slot '+str(index)+' '+node)
            if confirmed_retention:
                first, last = names.index('FLOOR_BEFORE_RETURN'), names.index('RETIREMENT_DELETE_VALIDATED')
                need([v for v in names[first:last] if v.startswith('RETENTION_')] == list(s.r.POINTS)*count,
                     'native dispatch exact observation writes')
                source_events = round['retirementEvents'][node]
                need([v for v in names if v.startswith(('SOURCE_RETIREMENT_', 'JOURNAL_ROTATION_'))] == source_events,
                     'native dispatch exact source retirement')
                if source_events:
                    s.ordered(names, ['RETIREMENT_BEFORE_RETURN', *source_events, 'FLOOR_RELEASE_AUTHORITY_CREATED'],
                              'native source retirement after generation before floor release')
            need(names.count('FLOOR_PARENT_FORCED') == names.count('PUBLICATION_SELECTOR_FORCED') == 1, 'native dispatch one floor/publication per slot')
            floor_at = next(i for i, ev in own if ev['event'] == 'FLOOR_PARENT_FORCED')
            peer = next(n for n in VOTERS if n != node); directory, members, packet = c.current(before[peer]); cap = packet['capsule']
            for allowed in (maintenance_prefixes(members, packet, c.current(before[node])[1]),
                            maintenance_generations(before[peer][directory+'generation.gsr'], members, packet)):
                references = {objects[0][0] for objects in allowed}
                matched = [t for t in transfers if t['sender'] == node and t['peer'] == peer and t['first'] in references]
                need(len(matched) == 1 and matched[0]['objects'] in allowed and start < matched[0]['delivered'] < floor_at, 'native dispatch complete copies before floor')
        for kind, raw in [('ACCEPT',accept),('PROOF',proof),('APPLY',certificate),('FUTURE_RETENTION_INTENT',certificate),('PUBLISH',certificate)]:
            selected_rows = [v for v in controls[kind] if start < v[4] < stop]
            need(1 <= len(selected_rows) <= 3, 'native dispatch bounded complete slot controls')
            need(all(v[4] > begin[index-1] for v in selected_rows), 'native dispatch controls after slot admission')
            first_request = selected_rows[0][1]
            for _, req, ans, reply, at in selected_rows:
                need(req == first_request and req['sender'] == identities['node-1'] and req['recipient'] == identities['node-2'], 'native dispatch identical control retries')
                if kind in ('ACCEPT','PROOF'):
                    expected = {('acceptance' if kind == 'ACCEPT' else 'proof'): e.digest(raw)}
                    result = dict(entry=e.digest(entry), receipt=e.digest(round['receipts']['node-2', kind])); required = [kind+'_PARENT_FORCED',kind+'_ACK_BEFORE_RETURN']
                elif kind == 'APPLY':
                    expected = dict(certificate=e.digest(certificate), selection=e.digest(chosen)); result = dict(expected, statement=e.digest(round['ends']['node-2']['statement.gsr']), acknowledgement=e.digest(round['ends']['node-2']['ack.gsr']))
                    required = ['CERTIFICATE_PARENT_FORCED','APPLY_ACK_DIRECTORY_FORCED','APPLICATION_ACK_BEFORE_RETURN']
                elif kind == 'FUTURE_RETENTION_INTENT':
                    expected = round['intent']; result = dict(intent=e.digest(f.canonical(expected)), storage='FUTURE', revision=2*index-1, digest=e.digest(round['recorded']['node-2'][future.FILE])); required = ['FUTURE_RETENTION_PARENT_FORCED','FUTURE_RETENTION_ACK_BEFORE_RETURN']
                else:
                    expected = dict(certificate=e.digest(certificate)); directory, _, _ = c.current(round['published']['node-2'])
                    result = dict(certificate=e.digest(certificate), selection=e.digest(chosen), published=round['upper'], generation=e.digest(round['published']['node-2'][directory+'generation.gsr'])); required = ['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_ACK_BEFORE_RETURN']
                need(ans == ('FUTURE_RETENTION_ACK' if kind == 'FUTURE_RETENTION_INTENT' else kind+'_ACK') and req['payload'] == expected and reply['payload'] == result, 'native dispatch exact control ACK')
                s.ordered([ev['event'] for ev in events[start:at] if ev['node'] == 'node-2'], required, 'native dispatch '+kind+' ACK')
        quorum = [(i+start, ev) for i, ev in enumerate(part) if ev['event'] == 'FUTURE_QUORUM_COMPLETE']
        sends = [i+start for i, ev in enumerate(part) if ev['event'] == 'PUBLICATION_SEND_BOUNDARY']
        need(len(quorum) == 1 and quorum[0][1]['voters'] == list(VOTERS) and quorum[0][1]['index'] == index and sends and quorum[0][0] < min(sends), 'native dispatch quorum before send')
        ack_rows = [v for v in controls['FUTURE_RETENTION_INTENT'] if start < v[4] < stop]
        ack_hashes = {e.digest(f.encode('wire', v[2], v[3])) for v in ack_rows}
        for node in VOTERS:
            need(any(ev['node'] == node and ev['event'] == 'FUTURE_RETENTION_PARENT_FORCED' for ev in events[start:quorum[0][0]]), 'native dispatch local quorum force')
        need(any(ev['event'] == 'NETWORK_RECEIVED' and ev.get('response') in ack_hashes for ev in events[start:quorum[0][0]]), 'native dispatch recording quorum delivered')
        # Receipt transfers must be from their permanent owners, never inferred from ACKs.
        for (node, phase), raw in round['receipts'].items():
            reader = next(n for n in VOTERS if n != node)
            found = [t for t in transfers if t['sender'] == reader and t['peer'] == node and any(value == raw for _, value, _ in t['objects'])]
            force = next(i+start for i, ev in enumerate(part) if ev['node'] == node and ev['event'] == phase+'_PARENT_FORCED')
            dependent = next(i+start for i, ev in enumerate(part) if ev['node'] == reader and ev['event'] == ('PROOF' if phase == 'ACCEPT' else 'CERTIFICATE')+'_PARENT_FORCED')
            need(found and any(force < t['offered'] < t['delivered'] < dependent for t in found), 'native dispatch original voter receipts')
        for node in VOTERS:
            peer = next(n for n in VOTERS if n != node)
            at = next(i+start for i, ev in enumerate(part) if ev['node'] == node and ev['event'] == 'PUBLICATION_SELECTOR_FORCED')
            for key in ('ack.gsr',) + (('parent-ack.gsr',) if index == 2 else ()):
                raw = round['ends'][peer][key]; found = [t for t in transfers if t['sender'] == node and t['peer'] == peer and t['objects'] == [(e.digest(raw),raw,'RECORD')]]
                force = next(i+start for i, ev in enumerate(part) if ev['node'] == peer and ev['event'] == 'APPLY_ACK_DIRECTORY_FORCED')
                need(len(found) == 1 and force < found[0]['offered'] < found[0]['delivered'] < at, 'native dispatch original checkpoint before publication')
    need(set(controls) == {'ACCEPT','PROOF','APPLY','FUTURE_RETENTION_INTENT','PUBLISH'}, 'native dispatch unexpected controls')
    return len(transfers)


def unselected_rejections(failures):
    need(type(failures) is list and len(failures) <= 6 and all(set(row) == {'node','kind','request','failure'} and row['node'] == 'node-3' and row['kind'] == 'FUTURE_RETENTION_INTENT' and row['failure'] == 'java.lang.IllegalArgumentException: higher ballot observed; fresh campaign required' for row in failures), 'native dispatch bounded unselected rejection')


def validate(root, *, discovery=False, rejection_check=None, confirmed_retention=False, precommand_maintenance=False):
    root = Path(root)
    b.selection.layout(root, {'initial','original-plan.gsbp','original-application.image','before-network','installed',
        'applied-1','published-1','applied-2','published-2','after-close','calls.json','events.json','wire.json','failures.json','result.json','selected.gsr'}, 'native dispatch case inventory')
    states, rounds, selected, identities = physical(root, confirmed_retention=confirmed_retention)
    calls = read(root/'calls.json')
    need([(row['node'], row['operation']) for row in calls] == [(n,'initialize-retention') for n in sorted(identities)], 'native dispatch bootstrap owner calls')
    for row in calls:
        s.ordered(row['events'], ['RETENTION_PARENT_FORCED','FUTURE_RETENTION_PARENT_FORCED'], 'native dispatch initialization')
    failures = read(root/'failures.json')
    (unselected_rejections if rejection_check is None else rejection_check)(failures)
    transfers = network(root, states, rounds, selected, identities, discovery=discovery, confirmed_retention=confirmed_retention, precommand_maintenance=precommand_maintenance)
    need(read(root/'result.json') == dict(status='PASS', slots=2, network=True, autonomous=False), 'native dispatch scope')
    result = dict(status='PASS', slots=2, selected=2, transfers=transfers, autonomous=False, phase3Complete=False)
    if discovery: result['discoveryPeers']=2
    if confirmed_retention: result['retentionSemantics']='original-copy-confirmation'
    return result


NEGATIVES = {
    'extra-file': 'context selection native dispatch case inventory inventory',
    'original-selection': 'native dispatch original selection',
    'installed-selector': 'admitted exact installed: node-2',
    'old-generation': 'admitted exact applied-1: node-1',
    'first-vote': 'admitted exact applied-1: node-2',
    'second-vote': 'admitted exact applied-2: node-2',
    'first-ack': 'admitted exact applied-1: node-2',
    'second-ack': 'admitted exact applied-2: node-2',
    'peer-observation': 'admitted exact applied-2: node-1',
    'future-proof': 'admitted exact published-1: node-1',
    'final-selector': 'admitted exact published-2: node-2',
    'unselected-change': 'admitted exact after-close: node-3',
    'scope': 'native dispatch scope',
    'source-bytes': 'native dispatch transfer exact data',
    'missing-commit': 'native dispatch transfer incomplete transcript',
    'reply-identity': 'native dispatch wire correlation',
    'control-ack': 'native dispatch exact control ACK',
    'floor-force': 'selected retention force order: native dispatch slot 1 node-1',
    'premature-floor': 'native dispatch complete copies before floor',
    'missing-delivery': 'native dispatch transfer delivered',
    'late-activation-delivery': 'native dispatch original activation delivery',
    'missing-quorum': 'native dispatch quorum before send',
    'wrong-quorum': 'native dispatch quorum before send',
    'premature-send': 'native dispatch quorum before send',
    'initialization': 'selected retention force order: native dispatch initialization',
    'maintenance-packet-reference': 'native dispatch original transfer offer',
    'maintenance-generation-reference': 'native dispatch original transfer offer',
}


def mutate(root, name):
    paths = {'extra-file': 'extra', 'original-selection': 'selected.gsr', 'installed-selector': 'installed/node-2/selector.gsr',
        'old-generation': 'applied-1/node-1/extra-generation', 'first-vote': 'applied-1/node-2/pending.accept',
        'second-vote': 'applied-2/node-2/pending.accept', 'first-ack': 'applied-1/node-2/applied-end/ack.gsr',
        'second-ack': 'applied-2/node-2/applied-end/ack.gsr', 'peer-observation': 'applied-2/node-1/'+s.FILE,
        'future-proof': 'published-1/node-1/'+future.FILE, 'final-selector': 'published-2/node-2/selector.gsr',
        'unselected-change': 'after-close/node-3/allocator.gsr'}
    if name in paths: (root/paths[name]).write_bytes(b'changed original'); return
    if name == 'scope':
        path = root/'result.json'; value = read(path); value['autonomous'] = True; path.write_text(json.dumps(value)); return
    if name == 'initialization':
        path = root/'calls.json'; value = read(path); value[0]['events'].remove('RETENTION_PARENT_FORCED'); path.write_text(json.dumps(value)); return
    path = root/'events.json'; events = read(path)
    if name in ('maintenance-packet-reference', 'maintenance-generation-reference'):
        _, _, packet = c.current(c.inventory(root/'installed/node-2')); cap = packet['capsule']
        references = ({e.digest(f.canonical(cap['cut'])), current_reference(cap, 'retained-current-packet')}
                      if name == 'maintenance-packet-reference' else
                      {current_reference(cap, scope) for scope in ('retained-current-generation', 'retained-current-generation-metadata')})
        wire_path = root/'wire.json'; rows = read(wire_path)
        original = next(row['request'] for row in rows if transfer.t.wire(row['response'])[0] == 'SOURCE_OFFER'
                        and transfer.t.wire(row['request'])[1]['payload']['digest'] in references)
        kind, request = transfer.t.wire(original); request['payload']['digest'] = '0'*64
        changed = f.encode('wire', kind, request); before = e.digest(base64.b64decode(original)); after = e.digest(changed)
        for row in rows:
            if row['request'] == original: row['request'] = base64.b64encode(changed).decode()
        for event in events:
            if event['event'] == 'WIRE_RESPONSE' and event['request'] == before: event['request'] = after
        wire_path.write_text(json.dumps(rows))
    elif name in ('source-bytes','missing-commit','reply-identity','control-ack'):
        wire_path = root/'wire.json'; rows = read(wire_path)
        wanted = {'source-bytes':'CHUNK', 'missing-commit':'TRANSFER_COMMIT', 'reply-identity':'PROMISE', 'control-ack':'ACCEPT_ACK'}[name]
        row = next(v for v in rows if transfer.t.wire(v['response'])[0] == wanted)
        before = e.digest(base64.b64decode(row['response'])); req_hash = e.digest(base64.b64decode(row['request']))
        kind, response = transfer.t.wire(row['response'])
        if name == 'missing-commit':
            rows.remove(row); events.remove(next(ev for ev in events if ev['event'] == 'WIRE_RESPONSE' and ev['request'] == req_hash and ev['response'] == before))
        else:
            if name == 'source-bytes': response['payload'].update(bytes=base64.b64encode(b'changed').decode(), digest=e.digest(b'changed'))
            elif name == 'reply-identity': response['sender'] = response['recipient']
            else: response['payload']['receipt'] = '0'*64
            changed = f.encode('wire',kind,response); row['response'] = base64.b64encode(changed).decode()
            stamp = next(ev for ev in events if ev['event'] == 'WIRE_RESPONSE' and ev['request'] == req_hash and ev['response'] == before); stamp['response'] = e.digest(changed)
        wire_path.write_text(json.dumps(rows))
    elif name == 'missing-delivery':
        ev = next(v for v in events if v['event'] == 'NETWORK_RECEIVED' and v['kind'] == 'TRANSFER_COMMIT'); events.remove(ev)
    elif name == 'late-activation-delivery':
        ev = next(v for v in events if v['node'] == 'node-2' and v['event'] == 'NETWORK_RECEIVED' and v['kind'] == 'TRANSFER_COMMIT'); events.remove(ev)
        events.insert(next(i for i,v in enumerate(events) if v['event'] == 'SLOT_BEGIN'), ev)
    elif name in ('missing-quorum','wrong-quorum','premature-send'):
        pos = next(i for i, v in enumerate(events) if v['event'] == 'FUTURE_QUORUM_COMPLETE')
        if name == 'missing-quorum': events.pop(pos)
        elif name == 'wrong-quorum': events[pos]['voters'] = ['node-1']
        else:
            item = events.pop(next(i for i, v in enumerate(events) if v['event'] == 'PUBLICATION_SEND_BOUNDARY')); events.insert(pos, item)
    elif name in ('floor-force','premature-floor'):
        pos = next(i for i,v in enumerate(events) if v['node'] == 'node-1' and v['event'] == 'FLOOR_PARENT_FORCED'); item = events.pop(pos)
        if name == 'premature-floor': events.insert(next(i for i,v in enumerate(events) if v['event'] == 'SLOT_BEGIN')+1, item)
    else: raise ValueError('unknown native dispatch mutation')
    path.write_text(json.dumps(events))


def qualify(root, *, discovery=False, confirmed_retention=False, precommand_maintenance=False):
    options = {}
    if discovery: options['discovery'] = True
    if confirmed_retention: options['confirmed_retention'] = True
    if precommand_maintenance: options['precommand_maintenance'] = True
    original = validate(root, **options); results = []
    cases = dict(NEGATIVES, **DISCOVERY_NEGATIVES) if discovery else NEGATIVES
    if confirmed_retention: cases = dict(cases, **OBSERVATION_NEGATIVES)
    if precommand_maintenance: cases = dict(cases, **PRECOMMAND_NEGATIVES)
    for name, reason in cases.items():
        with tempfile.TemporaryDirectory(prefix='v53-native-dispatch-negative-') as temp:
            dest = Path(temp)/'raw'; shutil.copytree(root, dest)
            if name in PRECOMMAND_NEGATIVES: mutate_precommand(dest, name)
            elif name in OBSERVATION_NEGATIVES: mutate_observation(dest, name, precommand_maintenance=precommand_maintenance)
            else: (mutate_discovery if name in DISCOVERY_NEGATIVES else mutate)(dest, name)
            try: validate(dest, **options)
            except ValueError as error: need(str(error) == reason, 'native dispatch unrelated negative '+name+': '+str(error))
            else: raise ValueError('native dispatch accepted negative '+name)
            results.append(dict(case=name, status='REJECTED', reason=reason))
    return dict(original=original, negatives=results)


PRECOMMAND_NEGATIVES = {
    'precommand-missing-completion': 'native dispatch serialized round boundaries',
    'precommand-extra-completion': 'native dispatch serialized round boundaries',
    'precommand-forged-completion': 'round original publication acknowledgement',
    'precommand-missing-floor': 'selected retention force order: native dispatch slot 2 node-1',
    'precommand-extra-floor': 'native dispatch one floor/publication per slot',
    'precommand-premature-floor': 'native dispatch complete copies before floor',
    'precommand-late-completion': 'native dispatch one floor/publication per slot',
    'precommand-early-mutation': 'native dispatch mutation before slot admission',
    'precommand-early-control': 'native dispatch controls after slot admission',
}


def mutate_precommand(root, name):
    path=root/'events.json';events=read(path)
    begins=[i for i,v in enumerate(events) if v['event']=='SLOT_BEGIN']
    at=round_maintenance_boundary(events,begins)
    floor=next(i for i in range(at+1,len(events)) if events[i]['node']=='node-1' and events[i]['event']=='FLOOR_PARENT_FORCED')
    if name=='precommand-missing-completion':events.pop(at)
    elif name=='precommand-extra-completion':events.insert(at,dict(events[at]))
    elif name=='precommand-forged-completion':
        row=events[at];value=f.decode(base64.b64decode(row['bytes']),'wire','PUBLISH_ACK')
        value['payload']['certificate']='0'*64;raw=f.encode('wire','PUBLISH_ACK',value)
        row.update(record=e.digest(raw),bytes=base64.b64encode(raw).decode())
    elif name=='precommand-missing-floor':events.pop(floor)
    elif name=='precommand-extra-floor':events.insert(floor,dict(events[floor]))
    elif name=='precommand-premature-floor':events.insert(at+1,events.pop(floor))
    elif name=='precommand-late-completion':
        # Preserve the valid original ACK bytes but move the claimed completion
        # past the next floor force; the extra first-slot floor rejects.
        row=events.pop(at);events.insert(floor,row)
    elif name=='precommand-early-mutation':
        pos=next(i for i in range(begins[1]+1,len(events)) if events[i]['node']=='node-1' and events[i]['event']=='ACCEPT_PARENT_FORCED')
        events.insert(begins[1],events.pop(pos))
    elif name=='precommand-early-control':
        rows=read(root/'wire.json')
        answers={e.digest(base64.b64decode(row['response'])) for row in rows if transfer.t.wire(row['request'])[0]=='ACCEPT'}
        pos=next(i for i in range(begins[1]+1,len(events)) if events[i]['event']=='WIRE_RESPONSE' and events[i]['response'] in answers)
        events.insert(begins[1],events.pop(pos))
    else:raise ValueError('unknown precommand mutation')
    path.write_text(json.dumps(events))


OBSERVATION_NEGATIVES = {
    'genesis-invented-revision': 'admitted exact applied-1: node-1',
    'confirmation-bytes': 'admitted exact applied-2: node-1',
    'confirmation-missing': 'admitted exact applied-2: node-1',
    'confirmation-forgotten-renewal': 'admitted exact applied-2: node-1',
    'confirmation-stale-endpoint': 'admitted exact applied-2: node-1',
    'confirmation-revision-chain': 'admitted exact applied-2: node-1',
    'genesis-invented-force': 'native dispatch exact observation writes',
    'observation-missing-force': 'native dispatch exact observation writes',
    'observation-force-order': 'native dispatch exact observation writes',
    'observation-extra-write': 'native dispatch exact observation writes',
}


def mutate_observation(root, name, *, precommand_maintenance=False):
    if name == 'genesis-invented-revision':
        path=root/'applied-1/node-1'/s.FILE; raw=path.read_bytes(); value=s.r.decode(raw)
        value.update(revision=value['revision']+1,previous=e.digest(raw));path.write_bytes(s.r.frame(value));return
    if name.startswith('confirmation-'):
        path=root/'applied-2/node-1'/s.FILE; value=s.r.decode(path.read_bytes())
        row=next(v for v in value['plan']['peers'] if v['identity']['node']=='node-2')
        if name=='confirmation-bytes':
            record=f.decode(base64.b64decode(row['confirmation'],validate=True),'records','GENERATION')
            record['generation']='b' if record['generation']=='a' else 'a'
            row['confirmation']=base64.b64encode(f.encode('records','GENERATION',record)).decode()
        elif name=='confirmation-missing':del row['confirmation']
        elif name=='confirmation-forgotten-renewal':del row['renewals']
        elif name=='confirmation-stale-endpoint':row['possible']=row['renewals'][:1]
        elif name=='confirmation-revision-chain':value['previous']='f'*64
        else:raise ValueError('unknown observation mutation')
        path.write_bytes(s.r.frame(value));return
    path=root/'events.json';events=read(path);begins=[i for i,v in enumerate(events) if v['event']=='SLOT_BEGIN']
    if precommand_maintenance: begins[1]=round_maintenance_boundary(events,begins)
    first=begins[0] if name=='genesis-invented-force' else begins[1]
    floor=next(i for i in range(first,len(events)) if events[i]['node']=='node-1' and events[i]['event']=='FLOOR_BEFORE_RETURN')
    if name=='genesis-invented-force':events.insert(floor+1,dict(node='node-1',event='RETENTION_PARENT_FORCED'))
    else:
        force=next(i for i in range(floor+1,len(events)) if events[i]['node']=='node-1' and events[i]['event']=='RETENTION_FORCED')
        parent=next(i for i in range(force+1,len(events)) if events[i]['node']=='node-1' and events[i]['event']=='RETENTION_PARENT_FORCED')
        if name=='observation-missing-force':events.pop(force)
        elif name=='observation-force-order':events[force],events[parent]=events[parent],events[force]
        elif name=='observation-extra-write':events[parent+1:parent+1]=[dict(node='node-1',event=v) for v in s.r.POINTS]
        else:raise ValueError('unknown observation mutation')
    path.write_text(json.dumps(events))


DISCOVERY_NEGATIVES = {
    'discovery-fence': 'native discovery original fence',
    'discovery-cut': 'native discovery original status',
    'discovery-delivery': 'native discovery before grant',
    'discovery-missing': 'native discovery complete known scan',
}


def mutate_discovery(root, name):
    rows = read(root/'wire.json'); events = read(root/'events.json')
    selected = f.decode((root/'selected.gsr').read_bytes(), 'records', 'SELECTED')
    row = next(v for v in rows if (lambda pair: pair[0]=='STATUS_PROBE' and pair[1]['ballot']!=selected['ballot'])(transfer.t.wire(v['request'])))
    _, request = transfer.t.wire(row['request']); _, response = transfer.t.wire(row['response'])
    old_request, old_response = (e.digest(base64.b64decode(row[key],validate=True)) for key in ('request','response'))
    if name=='discovery-delivery':
        delivered = next(v for v in events if v['event']=='NETWORK_RECEIVED' and v.get('response')==old_response)
        events.remove(delivered);events.append(delivered)
    elif name=='discovery-missing':
        rows.remove(row)
        events = [v for v in events if not (v['event']=='WIRE_RESPONSE' and v['request']==old_request)
                  and not (v['event']=='NETWORK_RECEIVED' and v.get('response')==old_response)]
    else:
        if name=='discovery-fence':
            request['ballot']['counter']+=100;response['ballot']=copy.deepcopy(request['ballot'])
        elif name=='discovery-cut':response['payload']['cut']['entry']='0'*64
        else:raise ValueError('unknown discovery mutation')
        raw_request=f.encode('wire','STATUS_PROBE',request);raw_response=f.encode('wire','STATUS',response)
        row.update(request=base64.b64encode(raw_request).decode(),response=base64.b64encode(raw_response).decode())
        for event in events:
            if event['event']=='WIRE_RESPONSE' and event['request']==old_request:
                event.update(request=e.digest(raw_request),response=e.digest(raw_response))
            elif event['event']=='NETWORK_RECEIVED' and event.get('response')==old_response:event['response']=e.digest(raw_response)
    (root/'wire.json').write_text(json.dumps(rows));(root/'events.json').write_text(json.dumps(events))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--negative', action='store_true'); parser.add_argument('--discovery',action='store_true'); parser.add_argument('--confirmed-retention',action='store_true'); args = parser.parse_args()
    print(json.dumps((qualify if args.negative else validate)(args.root,discovery=args.discovery,confirmed_retention=args.confirmed_retention), sort_keys=True))
