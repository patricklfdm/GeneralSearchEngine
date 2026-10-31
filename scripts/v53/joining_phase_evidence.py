"""Original-first vote/application/publication force and ACK replay for ADD/REPLACE.

The original semantic chain supplies bytes, never force observations. Bind every
wire response/delivery and each slot's successful force sequence to those bytes.
This does not qualify all request attempts, source transfers, generation cleanup,
activation, or process death; older producer traces lack old-owner send events.
"""
import argparse
import base64
from collections import defaultdict, deque
import json
from pathlib import Path
import shutil
import tempfile

from . import joining_catalog_evidence as semantic
from . import discovered_selection_evidence as exchange
from . import future_retention_evidence as future
from . import joining_source_loss as loss

f, need, sha, disk = semantic.f, semantic.need, semantic.sha, semantic.disk


def exchanges(events, wires, identities, root):
    """One original response per observed delivery, including scoped new owners."""
    positions = defaultdict(deque)
    need(type(events) is list and len(events) <= semantic.collection.HISTORY_ROWS and type(wires) is list and len(wires) <= semantic.collection.HISTORY_ROWS,
         'joining bounded wire observations')
    for at, row in enumerate(events):
        if row.get('event') == 'WIRE_RESPONSE':
            need(set(row) == {'node', 'event', 'request', 'response'}, 'joining response event shape')
            positions[row['request'], row['response']].append((at, row['node']))
        elif row.get('event') == 'BEFORE_RESPONSE_WRITE':
            need(set(row) == {'node', 'scope', 'event', 'request', 'kind', 'response', 'responseKind'},
                 'joining response event shape')
            positions[row['request'], row['response']].append((at, row['node']))
    policy=loss.declaration(events)
    result = []; offered = {}
    for row in wires:
        need(set(row) == {'request', 'response', 'withheld'} and type(row['withheld']) is bool and
             (row['withheld'] is False or policy is not None), 'joining original wire row')
        qraw, araw = [base64.b64decode(row[k], validate=True) for k in ('request', 'response')]
        qh, ah = sha(qraw), sha(araw)
        need(positions[qh, ah], 'joining missing original response')
        at, owner = positions[qh, ah].popleft()
        kind, q = exchange.d.transfer.t.wire(row['request']); answer, a = exchange.d.transfer.t.wire(row['response'])
        sender, peer = q['sender']['node'], q['recipient']['node']
        need(sender != peer and q['sender'] == identities.get(sender) and q['recipient'] == identities.get(peer)
             and owner == peer and q['root'] == root, 'joining wire permanent identity')
        need({k: v for k, v in a.items() if k != 'payload'} ==
             dict({k: v for k, v in q.items() if k != 'payload'}, sender=q['recipient'], recipient=q['sender']),
             'joining wire correlation')
        observed = events[at]
        if 'scope' in observed:
            need(observed['kind'] == kind and observed['responseKind'] == answer, 'joining response event kind')
        value = dict(kind=kind, answer=answer, request=q, response=a, requestHash=qh, responseHash=ah,
                     offered=at, delivered=None)
        if row['withheld']:value['withheld']=True
        need(at not in offered, 'joining duplicate response position'); offered[at] = value; result.append(value)
    need(not any(positions.values()), 'joining unmatched original response')
    available = defaultdict(deque)
    for at, row in enumerate(events):
        if at in offered:
            v = offered[at]
            if not v.get('withheld',False):available[v['request']['sender']['node'], v['answer'], v['responseHash']].append(v)
        if row.get('event') not in ('NETWORK_RECEIVED', 'AFTER_RESPONSE_READ'): continue
        scoped = row['event'] == 'AFTER_RESPONSE_READ'
        need(set(row) == ({'node', 'scope', 'event', 'request', 'kind', 'response', 'responseKind'} if scoped else
                          {'node', 'event', 'kind', 'response'}), 'joining delivery event shape')
        key = row['node'], row['responseKind' if scoped else 'kind'], row['response']
        need(available[key] and available[key][0]['offered'] < at, 'joining delivery without original response')
        value = available[key].popleft()
        if scoped: need(row['request'] == value['requestHash'] and row['kind'] == value['kind'], 'joining delivery request binding')
        value['delivered'] = at
    result=sorted(result, key=lambda v: v['offered']);loss.responses(events,result)
    return result


def force_names():
    names = []
    for phase in ('ACCEPT', 'PROOF', 'CERTIFICATE'):
        names += [phase + suffix for suffix in ('_VALIDATED', '_CANDIDATE_FORCED', '_CANDIDATE_PARENT_FORCED',
                                               '_RENAMED', '_PARENT_FORCED', '_BEFORE_RETURN')]
    return names + ['CERTIFICATE_ACTIVE_FORCED', 'CERTIFICATE_ACTIVE_PARENT_FORCED', 'NATIVE_CERTIFICATE_RETAINED',
        'APPLICATION_AUTHORITY_VALIDATED', 'REPLAY_CLAIM_FORCED', 'REPLAY_BEFORE_APPLICATION', 'REPLAY_APPLICATION_FINISHED',
        'REPLAY_BEFORE_RETURN', 'APPLY_PLAN_FORCED', 'APPLY_IMAGE_FORCED', 'APPLY_END_FORCED', 'APPLY_ACK_FORCED',
        'APPLY_ACK_DIRECTORY_FORCED', 'APPLY_BEFORE_RETURN', 'PUBLICATION_VALIDATED', 'PUBLICATION_SELECTOR_FORCED',
        'PUBLICATION_COVERAGE_VALIDATED', 'PUBLICATION_RETIRED', 'FUTURE_RETENTION_PROMOTED',
        'FUTURE_RETENTION_CLEARED', 'PUBLICATION_BEFORE_RETURN']


def blocks(events, replay):
    result = {}; critical = force_names()
    nodes=(*replay.old,replay.joining)
    need(all(v.get('node') in nodes for v in events if v.get('event') in critical), 'joining slot force unknown owner')
    for node in nodes:
        indices = [i for i, raw in enumerate(replay.phases, 1)
                   if node in [v['voter'] for v in f.decode(raw['CERTIFICATE'], 'records', 'CERTIFICATE')['proofs']]]
        rows = [(i, v) for i, v in enumerate(events) if v.get('node') == node and v.get('event') in critical]
        need([v['event'] for _, v in rows] == critical * len(indices), 'joining exact slot force order: ' + node)
        for ordinal, index in enumerate(indices):
            held = rows[ordinal*len(critical):(ordinal+1)*len(critical)]
            need(all(set(v) == ({'node', 'scope', 'event'} if node == replay.joining else {'node', 'event'}) for _, v in held),
                 'joining force event shape')
            if node == replay.joining: need(all(v['scope'] == 'continuation-owner' for _, v in held), 'joining force owner lifetime')
            result[index, node] = {v['event']: at for at, v in held}
    return result


def control(rows, kind, node, payload, reply, selected, lower, upper):
    matched = [v for v in rows if v['kind'] == kind and v['request']['recipient']['node'] == node and v['request']['payload'] == payload]
    need(0 < len(matched) <= 3, 'joining complete bounded phase control')
    first = matched[0]
    need(all(v['request'] == first['request'] and v['response'] == first['response'] for v in matched),
         'joining identical phase retries')
    answer = 'FUTURE_RETENTION_ACK' if kind == 'FUTURE_RETENTION_INTENT' else kind + '_ACK'
    need(first['request']['sender']['node'] == 'node-1' and first['request']['ballot'] == selected['ballot'] and
         first['request']['view'] == selected['view'] and first['answer'] == answer and first['response']['payload'] == reply,
         'joining original phase ACK')
    need(all(lower < v['offered'] < upper for v in matched) and
         any(v['delivered'] is not None and v['delivered'] < upper for v in matched), 'joining force before delivered phase ACK')
    return matched


def empty_future(raw, files):
    need(len(raw) >= 52, 'joining original empty future ledger')
    length = int.from_bytes(raw[44:48], 'big'); meta = semantic.catalog.parse(raw[48:48+length])
    need(raw == future.frame(meta, {}) and meta == dict(future.initial(files), revision=meta['revision'], previous=meta['previous'])
         and type(meta['revision']) is int and meta['revision'] >= 0, 'joining original empty future ledger')
    return meta


def forced_interval(events, node, lower, upper, names, reason, times=1):
    observed = [v['event'] for at, v in enumerate(events) if lower < at < upper and
                v.get('node') == node and v.get('event') in names]
    need(observed == names * times, reason)


def phase_replay(events, rows, replay, physical):
    used = set(); target_count = 0
    for index, parts in enumerate(replay.phases, 1):
        cert = f.decode(parts['CERTIFICATE'], 'records', 'CERTIFICATE'); selected = f.decode(parts['SELECTED'], 'records', 'SELECTED')
        voters = [v['voter'] for v in cert['proofs']]; leader = physical[index, 'node-1']
        ends = {node: replay.owner('applied', index, node) for node in voters}
        pub = {node: replay.owner('published', index, node) for node in voters}
        applied = max(physical[index, node]['APPLY_BEFORE_RETURN'] for node in voters)
        for node in voters:
            own = physical[index, node]
            # Metadata and parent/ancestor ACKs are named by the independently
            # reduced applied end, never by an event's assertion of completion.
            end = ends[node]
            names = ['APPLY_METADATA_FORCED'] * 4
            if 'applied-end/parent-statement.gsr' in end: names.append('APPLY_PARENT_STATEMENT_FORCED')
            names += [f'APPLY_ANCESTOR_{i}_STATEMENT_FORCED' for i in range(6) if f'applied-end/ancestor-{i}-statement.gsr' in end]
            forced_interval(events, node, own['APPLY_PLAN_FORCED'], own['APPLY_IMAGE_FORCED'], names,
                            'joining applied metadata force sequence')
            names = ['APPLY_PARENT_ACK_FORCED'] if 'applied-end/parent-ack.gsr' in end else []
            names += [f'APPLY_ANCESTOR_{i}_ACK_FORCED' for i in range(6) if f'applied-end/ancestor-{i}-ack.gsr' in end]
            forced_interval(events, node, own['APPLY_ACK_FORCED'], own['APPLY_ACK_DIRECTORY_FORCED'], names,
                            'joining applied ancestor ACK force sequence')
            if node == 'node-1': continue
            for phase, key, next_phase in (('ACCEPT', 'acceptance', 'PROOF'), ('PROOF', 'proof', 'CERTIFICATE')):
                receipt = next(v['receipt'] for v in cert['accepts' if phase == 'ACCEPT' else 'proofs'] if v['voter'] == node)
                held = control(rows, phase, node, {key: sha(parts[phase])}, dict(entry=sha(parts['ENTRY']), receipt=receipt),
                    selected, own[phase+'_BEFORE_RETURN'], leader[next_phase+'_VALIDATED'])
                used.update(v['offered'] for v in held)
            payload = dict(certificate=sha(parts['CERTIFICATE']), selection=sha(parts['SELECTED']))
            held = control(rows, 'APPLY', node, payload, dict(payload,
                statement=sha(ends[node]['applied-end/statement.gsr']), acknowledgement=sha(ends[node]['applied-end/ack.gsr'])),
                selected, own['APPLY_BEFORE_RETURN'], leader['PUBLICATION_VALIDATED'])
            used.update(v['offered'] for v in held)
            prefix, _, packet = disk.current(pub[node])
            held = control(rows, 'PUBLISH', node, dict(certificate=sha(parts['CERTIFICATE'])),
                dict(payload, published=disk.anchor(packet['capsule']), generation=sha(pub[node][prefix+'generation.gsr'])),
                selected, own['PUBLICATION_BEFORE_RETURN'], leader['PUBLICATION_VALIDATED'])
            used.update(v['offered'] for v in held)
        # Reconstruct every retained future proof before permitting any PUBLISH.
        parent = disk.anchor(disk.current(ends['node-1'])[2]['capsule'])
        upper = disk.anchor(disk.current(pub['node-1'])[2]['capsule'])
        originals = {}; metadata = {}; current = {}; peer_points = {n: [] for n in voters}
        for node in voters:
            files = ends[node]; local = disk.current(files)[1]
            originals[node] = {k: files['applied-end/'+k] for k in ('selector.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr', 'ack.gsr')}
            originals[node].update({k: local[k] for k in ('promise.gsr', 'selected.gsr')})
            originals[node].update({k.lower()+'.gsr': parts[k] for k in ('ENTRY', 'ACCEPT', 'PROOF')})
            current[node] = files[future.FILE]; metadata[node] = empty_future(current[node], files)
        targets = [node for node in voters if node != 'node-1']; target_count += len(targets); deliveries = []
        future_forces = ['FUTURE_RETENTION_BEFORE_WRITE', 'FUTURE_RETENTION_PREFIX_WRITTEN', 'FUTURE_RETENTION_WRITTEN',
                         'FUTURE_RETENTION_FORCED', 'FUTURE_RETENTION_CANDIDATE_PARENT_FORCED', 'FUTURE_RETENTION_RENAMED',
                         'FUTURE_RETENTION_PARENT_FORCED', 'FUTURE_RETENTION_BEFORE_RETURN']
        for node in voters:
            own = physical[index, node]
            forced_interval(events, node, applied, own['PUBLICATION_VALIDATED'], future_forces,
                            'joining future write/force/rename sequence', len(targets))
            # Clearing is a publication substep, so it ends with CLEARED rather
            # than the standalone recording API's BEFORE_RETURN callback.
            forced_interval(events, node, own['PUBLICATION_RETIRED'], own['PUBLICATION_BEFORE_RETURN'], future_forces[:-1],
                            'joining future promotion force sequence')
            forced_interval(events, node, own['PUBLICATION_VALIDATED'], own['PUBLICATION_SELECTOR_FORCED'],
                ['INSTALL_MANIFEST_FORCED', 'INSTALL_IMAGE_FORCED', 'INSTALL_GENERATION_FORCED', 'INSTALL_SELECTOR_FORCED',
                 'INSTALL_SELECTOR_RENAMED', 'INSTALL_PARENT_FORCED', 'CURRENT_FILES_FORCED', 'CURRENT_GENERATION_FORCED',
                 'CURRENT_SELECTOR_FORCED', 'CURRENT_DIRECTORY_FORCED'], 'joining published generation force sequence')
        for target in targets:
            identity = semantic.catalog.identities(replay.states[index]['identities'])[target]
            intent = dict(selection=sha(parts['SELECTED']), certificate=sha(parts['CERTIFICATE']), peer=identity,
                          lower=parent, parent=parent, upper=upper)
            for node in voters:
                peer_points[node].append(dict(identity=identity, lower=parent))
                meta = metadata[node] = dict(metadata[node], revision=metadata[node]['revision']+1,
                    previous=sha(current[node]), parent=parent, peers=list(peer_points[node]))
                current[node] = future.frame(meta, originals[node])
                forces = [at for at, v in enumerate(events) if v.get('node') == node and v['event'] == 'FUTURE_RETENTION_PARENT_FORCED'
                          and applied < at < physical[index, node]['PUBLICATION_VALIDATED']]
                need(len(forces) == len(targets), 'joining future force count')
                force = forces[targets.index(target)]
                if node == 'node-1': continue
                matching = [v for v in rows if v['kind'] == 'FUTURE_RETENTION_INTENT' and v['request']['recipient']['node'] == node
                            and v['request']['payload'] == intent]
                need(0 < len(matching) <= 3, 'joining original future quorum')
                held = control(rows, 'FUTURE_RETENTION_INTENT', node, intent,
                    dict(intent=sha(f.canonical(intent)), storage='FUTURE', revision=meta['revision'], digest=sha(current[node])),
                    selected, force, min(physical[index, n]['PUBLICATION_VALIDATED'] for n in voters))
                used.update(v['offered'] for v in held)
                deliveries.append(min(v['delivered'] for v in held if v['delivered'] is not None))
        # Empty state after publication must name the last reconstructed proof.
        for node in voters:
            meta = dict(metadata[node], revision=metadata[node]['revision']+1, previous=sha(current[node]), parent=None, peers=[])
            need(pub[node][future.FILE] == future.frame(meta, {}), 'joining exact future proof promotion')
        # Old producer retained every PUBLISH send even though other sends lack
        # observations. A response cannot move this permission boundary later.
        publications = [v for v in rows if v['kind'] == 'PUBLISH' and v['request']['payload'] == dict(certificate=sha(parts['CERTIFICATE']))]
        for publication in publications:
            sends = [at for at, v in enumerate(events) if v.get('event') == 'PUBLICATION_SEND_BOUNDARY'
                     and v.get('node') == 'node-1' and v.get('request') == publication['requestHash']]
            need(sends and all(applied < at < publication['offered'] for at in sends), 'joining original publication send')
            need(all(max(deliveries) < at for at in sends), 'joining publication before delivered future quorum')
            for node in voters:
                forces = [at for at, v in enumerate(events) if v.get('node') == node and v['event'] == 'FUTURE_RETENTION_PARENT_FORCED'
                          and applied < at < physical[index, node]['PUBLICATION_VALIDATED']]
                need(all(max(forces) < at for at in sends), 'joining publication before future quorum')
        need(leader['PUBLICATION_BEFORE_RETURN'] < (physical[index+1, 'node-1']['ACCEPT_VALIDATED'] if index < len(replay.phases) else len(events)),
             'joining completed publication before next slot')
    bound = {'ACCEPT', 'PROOF', 'APPLY', 'PUBLISH', 'FUTURE_RETENTION_INTENT'}
    need(used == {v['offered'] for v in rows if v['kind'] in bound}, 'joining unbound phase exchange')
    return dict(slots=len(replay.phases),ownedSlotTransactions=len(physical),boundPhaseResponses=len(used),futureTargets=target_count)


def validate(root, *, size=3, kind='ADD'):
    root = Path(root); inventory = semantic.collection.inventory(root); chain = semantic.validate(root,size=size,kind=kind)
    replay = semantic.Replay(root,size=size,kind=kind)
    for index in range(1, chain['slots']+1): replay.step(index)
    events = semantic.collection.read_json(root, 'events.json', semantic.collection.EVENT_BYTES)
    wires = semantic.collection.read_json(root, 'wire.json', semantic.collection.WIRE_BYTES)
    identities = semantic.catalog.identities(replay.states[-1]['identities'])
    rows = exchanges(events, wires, identities, replay.root)
    result = phase_replay(events, rows, replay, blocks(events, replay))
    need(semantic.collection.inventory(root) == inventory, 'joining original history changed during phase replay')
    return dict(status='PASS',scope='native-'+kind+'-forced-slot-phases-and-delivered-ACKs',profile=str(size)+'-'+kind,**result,
        wireResponses=len(rows),deliveredResponses=sum(v['delivered'] is not None for v in rows),
        completePhysicalQualified=False,forceAndNetworkQualified=False,processDeathQualified=False,phase3Complete=False)


NEGATIVES = {
    'accept-force-missing': 'joining exact slot force order: node-2',
    'proof-parent-force-missing': 'joining exact slot force order: node-2',
    'apply-ack-force-missing': 'joining exact slot force order: node-2',
    'apply-metadata-force-missing': 'joining applied metadata force sequence',
    'publication-before-retirement': 'joining exact slot force order: node-2',
    'joining-owner-force-missing': 'joining exact slot force order: node-4',
    'joining-wrong-owner-lifetime': 'joining force owner lifetime',
    'duplicate-delivery': 'joining delivery without original response',
    'missing-wire-response': 'joining unmatched original response',
    'missing-response-event': 'joining missing original response',
    'accept-ack-before-force': 'joining force before delivered phase ACK',
    'publish-before-future-delivery': 'joining publication before delivered future quorum',
    'future-parent-force-missing': 'joining future write/force/rename sequence',
    'future-file-force-missing': 'joining future write/force/rename sequence',
    'generation-parent-force-missing': 'joining published generation force sequence',
    'future-promotion-bytes': 'joining exact future proof promotion',
    'future-ack-wrong-digest': 'joining original phase ACK',
}


def mutate(root, name):
    events = semantic.collection.read_json(root, 'events.json', semantic.collection.EVENT_BYTES)
    wires = semantic.collection.read_json(root, 'wire.json', semantic.collection.WIRE_BYTES)
    def at(event, node='node-2'):
        return next(i for i, row in enumerate(events) if row.get('node') == node and row.get('event') == event)
    missing = {'accept-force-missing': 'ACCEPT_CANDIDATE_FORCED', 'proof-parent-force-missing': 'PROOF_PARENT_FORCED',
               'apply-ack-force-missing': 'APPLY_ACK_FORCED', 'apply-metadata-force-missing': 'APPLY_METADATA_FORCED',
               'future-parent-force-missing': 'FUTURE_RETENTION_PARENT_FORCED',
               'future-file-force-missing': 'FUTURE_RETENTION_FORCED'}
    if name in missing: events.pop(at(missing[name]))
    elif name == 'joining-owner-force-missing': events.pop(at('CERTIFICATE_PARENT_FORCED', 'node-4'))
    elif name == 'joining-wrong-owner-lifetime': events[at('PROOF_PARENT_FORCED', 'node-4')]['scope'] = 'stable-cold-owner'
    elif name == 'generation-parent-force-missing':
        start = at('PUBLICATION_VALIDATED'); i = next(i for i,v in enumerate(events) if i > start and
            v.get('node') == 'node-2' and v.get('event') == 'INSTALL_PARENT_FORCED'); events.pop(i)
    elif name == 'publication-before-retirement':
        row = events.pop(at('PUBLICATION_SELECTOR_FORCED')); events.insert(at('PUBLICATION_RETIRED')+1, row)
    elif name == 'duplicate-delivery':
        i = at('NETWORK_RECEIVED', 'node-1'); events.insert(i+1, dict(events[i]))
    elif name == 'missing-wire-response': wires.pop(0)
    elif name == 'missing-response-event': events.pop(at('WIRE_RESPONSE', 'node-1'))
    elif name == 'accept-ack-before-force':
        raw = next(v for v in wires if exchange.d.transfer.t.wire(v['request'])[0] == 'ACCEPT')
        digest = sha(base64.b64decode(raw['response']))
        i = next(i for i, v in enumerate(events) if v.get('event') == 'WIRE_RESPONSE' and v['response'] == digest)
        row = events.pop(i); events.insert(at('ACCEPT_BEFORE_RETURN'), row)
    elif name == 'publish-before-future-delivery':
        row = events.pop(at('PUBLICATION_SEND_BOUNDARY', 'node-1'))
        i = next(i for i, v in enumerate(events) if v.get('event') == 'NETWORK_RECEIVED' and v.get('kind') == 'FUTURE_RETENTION_ACK')
        events.insert(i, row)
    elif name == 'future-promotion-bytes':
        path = root / 'published-1/node-1' / future.FILE; path.write_bytes(b'changed'); return
    elif name == 'future-ack-wrong-digest':
        row = next(v for v in wires if exchange.d.transfer.t.wire(v['response'])[0] == 'FUTURE_RETENTION_ACK')
        raw = base64.b64decode(row['response']); kind, value = exchange.d.transfer.t.wire(row['response']); old = sha(raw)
        value['payload']['digest'] = '0'*64; raw = f.encode('wire', kind, value)
        row['response'] = base64.b64encode(raw).decode()
        for event in events:
            if event.get('response') == old: event['response'] = sha(raw)
    else: raise ValueError('unknown joining phase mutation: ' + name)
    (root/'events.json').write_bytes(f.canonical(events)); (root/'wire.json').write_bytes(f.canonical(wires))


def qualify(root):
    root = Path(root); original = validate(root); results = []
    for name, reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-joining-phase-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root, changed);mutate(changed, name)
            try: validate(changed)
            except ValueError as error: need(str(error) == reason, 'joining unrelated phase negative: ' + name + ': ' + str(error))
            else: raise ValueError('joining phase mutation accepted: ' + name)
        results.append(dict(case=name, status='REJECTED', reason=reason))
    return dict(original=original, negatives=results)


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root),sort_keys=True))
