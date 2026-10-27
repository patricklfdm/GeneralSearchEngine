"""Original-first replay of one native selected-slot TCP receiver.

Derive each physical phase from public bootstrap, original grants and wire bytes.
The sender is explicit; no automatic election/slot-loop claim is made here.
"""
import argparse
import base64
from collections import Counter, defaultdict
import copy
import json
from pathlib import Path
import shutil
import struct
import tempfile
from . import native_application_ingress_evidence as application
from . import future_quorum_evidence as future
from .selected_prefix_evidence import prefix

b, c, e, f, need = application.b, application.c, application.e, application.f, application.need
read = application.v.read


def prelude(root, size, kind):
    group = future.s.initialize(b.original(root, size, False))
    group = {n: dict(v, **{future.future.FILE: future.future.frame(future.future.initial(v), {})}) for n, v in group.items()}
    b.match(root, 'retaining-genesis', group)
    prepared, selected, installed = future.s.campaign(root, group, 2, 'round-1-prepared', selected_prefix=prefix)
    for label, states in [('prepared', prepared), ('selected', selected), ('installed', installed)]:
        b.match(root, 'round-1-'+label, states)
    group = b.settled(installed); b.match(root, 'round-1-settled', group)
    first = None
    if kind == 'DATA': group, first = b.publication(root, group, 1, None, [])
    b.match(root, 'before-voting', group)
    return group, first


def publication(files, end, all_ends, quorum, originals, first, node):
    old_prefix, local, packet = c.current(files); cap = packet['capsule']
    catalog = f.decode(end['catalog.gsr'], 'records', 'CATALOG')
    upper = dict(cut=catalog['cut'], catalog=e.digest(end['catalog.gsr']), application=catalog['application'])
    acks = [all_ends[n]['ack.gsr'] for n in quorum]
    values = [files['root.gsr'], files['genesis.gsr'], *originals, end['catalog.gsr'], end['statement.gsr'], *acks]
    ancestry = b''
    if first:
        ancestry = end['parent-statement.gsr']+b''.join(all_ends[n]['parent-ack.gsr'] for n in quorum)
        values += [end['parent-statement.gsr'], *[all_ends[n]['parent-ack.gsr'] for n in quorum], *first['proof'].values()]
    objects = {e.digest(raw): raw for raw in values}
    item = dict(kind='RANGE', statement=e.digest(end['statement.gsr']), endorsements=[e.digest(raw) for raw in acks], certificate=None, descriptor=None)
    source = e.packet_bytes(dict(cap, **upper, items=[item]), objects, {catalog['application']: len(end['application.image'])})
    coverage = dict(schema='gse-v53-round-coverage/1.3' if first else 'gse-v53-selected-coverage/1.3',
                    selection=e.digest(local['selected.gsr']), parent=c.anchor(cap), certificate=e.digest(end['certificate.gsr']))
    if first: coverage['first'] = {k: first[k] for k in ('parent', 'end', 'certificate')}
    members = {k: local[k] for k in ('promise.gsr', 'basis.gsr', 'selected.gsr', 'selected-sources.gsr')}
    members.update({'source.gscp': source, c.COVERAGE: f.canonical(coverage), catalog['application']+'.image': end['application.image']})
    if ancestry: members['ancestry.gsr'] = ancestry
    selector, generation = c.generation(members, e.p.decode(source)['capsule'], node, 'b' if old_prefix == 'generations/a/' else 'a', None)
    result = dict(files, **generation, **{'selector.gsr': selector, 'pending.accept': c.EMPTY})
    return {k: v for k, v in result.items() if k != 'applied-end' and not k.startswith('applied-end/')}, upper


def validate(root):
    root = Path(root); result = read(root/'result.json'); size, kind = result.get('size'), result.get('kind')
    need(size in (3, 4, 5) and kind in ('BARRIER', 'DATA'), 'slot receiver profile')
    group, first = prelude(root, size, kind); names = sorted(group); target = names[-1]
    _, local, packet = c.current(group['node-1']); cap = packet['capsule']; selected = f.decode(local['selected.gsr'], 'records', 'SELECTED')
    identities = {n: future.future.identity(v) for n, v in group.items()}
    text = b'456:native-payload-'+b'x'*1024
    payload = b'\x01'+struct.pack('>HIII', 1, 1, 4, 456)+struct.pack('>I', len(text))+text if kind == 'DATA' else b''
    entry = f.encode('records', 'ENTRY', dict(root=cap['root'], authority=selected['view'], index=cap['cut']['index']+1,
        previous=cap['cut']['entry'], origin=selected['ballot'], kind=kind, payload=e.digest(payload)))
    accept = f.encode('records', 'ACCEPT', dict(root=cap['root'], authority=selected['view'], ballot=selected['ballot'], index=cap['cut']['index']+1, entry=e.digest(entry)))
    def receipt(n, phase, raw): return f.canonical(dict(root=cap['root'], voter=n, incarnation=identities[n]['storage'], phase=phase, record=e.digest(raw)))
    def witnesses(phase, raw): return [dict(voter=n, incarnation=identities[n]['storage'], receipt=e.digest(receipt(n, phase, raw))) for n in names]
    proof = f.encode('records', 'PROOF', dict(f.decode(accept, 'records', 'ACCEPT'), accepts=witnesses('ACCEPT', accept)))
    certificate = f.encode('records', 'CERTIFICATE', dict(f.decode(proof, 'records', 'PROOF'), proofs=witnesses('PROOF', proof)))
    for name, raw in [('entry.gsr', entry), ('payload.bin', payload), ('proof.gsr', proof), ('certificate.gsr', certificate)]:
        need(b.t.plans.read(root/name, 8*e.MIB) == raw, 'slot receiver original record '+name)
    need(result == dict(status='PASS', size=size, kind=kind, certificate=e.digest(certificate)), 'slot receiver exact result scope')
    phases = {}
    for label, extra in [('after-accept', b''), ('after-proof', proof), ('certified', proof+certificate)]:
        phases = {}
        for n, files in group.items():
            _, own, _ = c.current(files)
            vote = e.container([files['selector.gsr'], own['promise.gsr'], own['selected.gsr'], entry, accept], payload)+extra
            vote = vote[:8]+struct.pack('>I', len(vote))+vote[12:]; phases[n] = dict(files, **{'pending.accept': vote})
        if label != 'certified': b.match(root, label, phases)
    ends = application.ends(root, dict(cap=cap, selected=selected, certificate=certificate, proof=proof, voting=dict(kind=kind),
        local=local, packet=packet, group=group, certified=phases, identities=identities))
    applied = {}
    for n, files in phases.items():
        need(c.inventory(root/('end-'+n)) == ends[n], 'slot receiver exact typed end')
        applied[n] = dict(files, **{'applied-end': None}, **{'applied-end/'+k: v for k, v in ends[n].items()})
    b.match(root, 'after-application', applied)
    upper_catalog = f.decode(ends[target]['catalog.gsr'], 'records', 'CATALOG')
    upper = dict(cut=upper_catalog['cut'], catalog=e.digest(ends[target]['catalog.gsr']), application=upper_catalog['application'])
    ledger = future.s.r.decode(group['node-1'][future.s.FILE])
    lower = next(v['possible'][0] for v in ledger['plan']['peers'] if v['identity'] == identities[target])
    logical = dict(selection=e.digest(local['selected.gsr']), certificate=e.digest(certificate), peer=identities[target], lower=lower, parent=c.anchor(cap), upper=upper)
    intent = e.digest(f.canonical(logical)); retained = {}; recorded = {}
    for n, files in applied.items():
        _, members, _ = c.current(files)
        original = {k: ends[n][k] for k in ('selector.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr', 'ack.gsr')}
        original.update({k: members[k] for k in ('promise.gsr', 'selected.gsr')})
        original.update({'entry.gsr': entry, 'accept.gsr': accept, 'proof.gsr': proof})
        metadata = dict(future.future.initial(files), revision=1, previous=e.digest(files[future.future.FILE]), parent=c.anchor(cap), peers=[dict(identity=identities[target], lower=lower)])
        retained[n] = future.future.frame(metadata, original); recorded[n] = dict(files, **{future.future.FILE: retained[n]})
    b.match(root, 'recorded-quorum', recorded)
    events = read(root/'events.json'); rows = read(root/'wire.json'); traces = defaultdict(list); controls = Counter(); published_acks = []; future_replies = {}; requests = {}; stamps = Counter()
    content = {e.digest(raw): raw for raw in (entry, accept, proof, certificate)}
    if payload: content[e.digest(payload)] = payload
    references = {h: h for h in content}; receipt_owner = {}; receipt_force = {}; checkpoint_hashes = set()
    for n in names:
        for phase, raw in [('ACCEPT', accept), ('PROOF', proof)]:
            raw = receipt(n, phase, raw); h = e.digest(raw); content[h] = raw
            references[h] = e.digest(f.canonical(dict(schema='gse-v53-vote-observation/1.3', receipt=h))); receipt_owner[h] = n; receipt_force[h] = phase+'_PARENT_FORCED'
        for k in ('ack.gsr', 'parent-ack.gsr'):
            if k in ends[n]:
                raw = ends[n][k]; h = e.digest(raw); content[h] = raw; references[h] = h; receipt_owner[h] = n
                receipt_force[h] = 'APPLY_ACK_DIRECTORY_FORCED'; checkpoint_hashes.add(h)
    for row in rows:
        need(set(row) == {'request', 'response', 'withheld'} and row['withheld'] is False, 'slot receiver successful wire shape')
        command, request = application.v.transfer.wire(row['request']); response_kind, response = application.v.transfer.wire(row['response'])
        sender, receiver = request['sender']['node'], request['recipient']['node']
        need(sender in names and receiver in names and sender != receiver and request['sender'] == identities[sender] and request['recipient'] == identities[receiver]
             and request['root'] == cap['root'] and request['view'] == selected['view'] and request['ballot'] == selected['ballot'], 'slot receiver original wire authority')
        need({k: v for k, v in response.items() if k != 'payload'} == dict({k: v for k, v in request.items() if k != 'payload'}, sender=request['recipient'], recipient=request['sender']), 'slot receiver wire correlation')
        if command in ('CHUNK', 'TRANSFER_COMMIT'): traces[request['trace']].append((command, request, response_kind, response)); continue
        need(sender == 'node-1' and response_kind == ('FUTURE_RETENTION_ACK' if command == 'FUTURE_RETENTION_INTENT' else command+'_ACK'), 'slot receiver control sender/kind')
        if command in ('ACCEPT', 'PROOF', 'APPLY'):
            controls[(receiver, command)] += 1
            previous = requests.setdefault((receiver, command), row['request'])
            need(previous == row['request'] and controls[(receiver, command)] <= 3, 'slot receiver bounded identical delivery')
            if command == 'APPLY':
                expected = dict(certificate=e.digest(certificate), selection=e.digest(local['selected.gsr']))
                ack = dict(expected, statement=e.digest(ends[receiver]['statement.gsr']), acknowledgement=e.digest(ends[receiver]['ack.gsr']))
                forces = ['CERTIFICATE_PARENT_FORCED', 'NATIVE_CERTIFICATE_RETAINED', 'APPLY_ACK_DIRECTORY_FORCED', 'APPLY_BEFORE_RETURN', 'APPLICATION_ACK_BEFORE_RETURN']
            else:
                raw = accept if command == 'ACCEPT' else proof
                expected = {('acceptance' if command == 'ACCEPT' else 'proof'): e.digest(raw)}
                ack = dict(entry=e.digest(entry), receipt=e.digest(receipt(receiver, command, raw))); forces = [command+'_PARENT_FORCED', command+'_ACK_BEFORE_RETURN']
            need(request['sequence'] == 1 and request['payload'] == expected and response['payload'] == ack, 'slot receiver exact phased ACK')
            stamp = dict(node=receiver, event='WIRE_RESPONSE', request=e.digest(base64.b64decode(row['request'])), response=e.digest(base64.b64decode(row['response'])))
            at = [i for i, event in enumerate(events) if event == stamp]; key = (stamp['request'], stamp['response']); index = stamps[key]; stamps[key] += 1
            need(len(at) > index, 'slot receiver unique response event')
            future.s.ordered([v['event'] for v in events[:at[index]] if v['node'] == receiver], forces, 'slot phase '+command)
        elif command == 'FUTURE_RETENTION_INTENT':
            need(request['payload'] == logical and response['payload'] == dict(intent=intent, storage='FUTURE', revision=1, digest=e.digest(retained[receiver])), 'slot receiver exact future ACK')
            future_replies[e.digest(base64.b64decode(row['response']))] = receiver
        elif command == 'PUBLISH':
            need(receiver == target and request['payload'] == dict(certificate=e.digest(certificate)), 'slot receiver exact publication request')
            prior = requests.setdefault((receiver, command), row['request']); need(prior == row['request'], 'slot receiver bounded identical publication')
            published_acks.append(response['payload'])
        else: raise ValueError('slot receiver unexpected control')
    need(set(controls) == {(n, k) for n in names[1:] for k in ('ACCEPT', 'PROOF', 'APPLY')}, 'slot receiver complete phased controls')
    need(len(future_replies) == size-1 and 1 <= len(published_acks) <= 3, 'slot receiver complete future/publication controls')
    observed = Counter(); checkpoint_arrivals = []
    for trace in traces.values():
        command, request, reply_kind, offer = trace[0]; a, z = request['payload'], offer['payload']; h = z['digest']; tid = a['id']
        need(h in content and (command, reply_kind) == ('CHUNK', 'SOURCE_OFFER') and a == dict(id=tid, action='REQUEST', offset=0, digest=references[h], bytes='')
             and z == dict(id=tid, kind='RECORD', digest=h, bytes=len(content[h])), 'slot receiver original transfer offer')
        need(h not in receipt_owner or receipt_owner[h] == request['recipient']['node'], 'slot receiver original receipt owner')
        if h in receipt_owner:
            stamp = dict(node=receipt_owner[h], event='WIRE_RESPONSE', request=e.digest(f.encode('wire', command, request)), response=e.digest(f.encode('wire', reply_kind, offer)))
            positions = [i for i, v in enumerate(events) if v == stamp]
            need(positions and any(v['node'] == receipt_owner[h] and v['event'] == receipt_force[h] for v in events[:positions[0]]), 'slot receiver original receipt force')
        raw = content[h]; offset = 0
        for index, (command, sent, reply_kind, reply) in enumerate(trace):
            need(sent['sender'] == request['sender'] and sent['recipient'] == request['recipient'] and sent['sequence'] == index+1, 'slot receiver transfer sequence')
            a, z = sent['payload'], reply['payload']
            if index == 0: continue
            if index == len(trace)-1:
                need((command, reply_kind) == ('TRANSFER_COMMIT', 'TRANSFER_COMMIT') and a == z == dict(id=tid, digest=h) and offset == len(raw), 'slot receiver complete transfer')
            else:
                part = base64.b64decode(z['bytes'], validate=True)
                need((command, reply_kind) == ('CHUNK', 'CHUNK') and a == dict(id=tid, action='REQUEST', offset=offset, digest=h, bytes='') and
                     z == dict(id=tid, action='DATA', offset=offset, digest=e.digest(part), bytes=base64.b64encode(part).decode()) and 0 < len(part) <= 4*e.MIB and part == raw[offset:offset+len(part)], 'slot receiver original transfer bytes'); offset += len(part)
        need(len(trace) >= 3, 'slot receiver complete transfer'); observed[(request['sender']['node'], request['recipient']['node'], h)] += 1
        if h in checkpoint_hashes:
            final_kind, final_response = trace[-1][2:]
            delivered = dict(node=target, event='NETWORK_RECEIVED', kind=final_kind, response=e.digest(f.encode('wire', final_kind, final_response)))
            positions = [i for i, v in enumerate(events) if v == delivered]
            need(len(positions) == 1, 'slot receiver actual checkpoint delivery'); checkpoint_arrivals.append(positions[0])
    quorum = names[:size//2]+[target]; wanted = Counter()
    for n in names[1:]:
        for raw in (accept, entry, proof, certificate): wanted[(n, 'node-1', e.digest(raw))] += 1
        if payload: wanted[(n, 'node-1', e.digest(payload))] += 1
        wanted[(n, 'node-1', e.digest(receipt('node-1', 'ACCEPT', accept)))] += 1
        for peer in names:
            if peer == n: continue
            wanted[(n, peer, e.digest(receipt(peer, 'ACCEPT', accept)))] += 2
            wanted[(n, peer, e.digest(receipt(peer, 'PROOF', proof)))] += 1
        for phase, raw in [('ACCEPT', accept), ('PROOF', proof)]: wanted[('node-1', n, e.digest(receipt(n, phase, raw)))] += 1
    expected_receipts = []
    for key, statement in [('ack.gsr', 'statement.gsr')]+([('parent-ack.gsr', 'parent-statement.gsr')] if kind == 'DATA' else []):
        for n in quorum:
            if n == target: continue
            wanted[(target, n, e.digest(ends[n][key]))] += 1
            expected_receipts.append(dict(node=target, event='PUBLICATION_CHECKPOINT_RECEIVED', statement=ends[target][statement].hex(), ack=ends[n][key].hex()))
    need(observed == wanted, 'slot receiver complete original observations')
    need(read(root/'checkpoint-receipts.json') == expected_receipts, 'slot receiver exact checkpoint receipts')
    quorum_rows = [(i, v) for i, v in enumerate(events) if v['event'] == 'FUTURE_QUORUM_COMPLETE']
    send_rows = [(i, v) for i, v in enumerate(events) if v['event'] == 'PUBLICATION_SEND_BOUNDARY']
    selector = [i for i, v in enumerate(events) if v['event'] == 'PUBLICATION_SELECTOR_FORCED']
    need(len(quorum_rows) == len(selector) == 1 and len(published_acks) <= len(send_rows) <= 3 and
         quorum_rows[0][0] < send_rows[0][0] < selector[0] and len({v['request'] for _, v in send_rows}) == 1,
         'slot receiver recording before dispatch')
    need(checkpoint_arrivals and all(i < selector[0] for i in checkpoint_arrivals), 'slot receiver checkpoint delivery before selector')
    at, row = quorum_rows[0]; voters = row['voters']
    need(voters == sorted(set(voters)) and 'node-1' in voters and len(voters) == size//2+1 and set(voters) <= set(names), 'slot receiver governing quorum')
    delivered = {future_replies[v['response']] for v in events[:at] if v['event'] == 'NETWORK_RECEIVED' and v.get('response') in future_replies}
    need(set(voters)-{'node-1'} <= delivered, 'slot receiver original quorum delivery')
    for n in voters: future.s.ordered([v['event'] for v in events[:at] if v['node'] == n], ['FUTURE_RETENTION_FORCED', 'FUTURE_RETENTION_PARENT_FORCED'], 'slot governing force')
    final = dict(recorded)
    final[target], _ = publication(recorded[target], ends[target], ends, quorum, [entry, accept, proof, certificate, payload], first, target)
    previous = future.s.r.decode(group[target][future.s.FILE]); plan = copy.deepcopy(previous['plan'])
    next(v for v in plan['peers'] if v['identity'] == identities[target])['possible'].append(upper)
    final[target][future.s.FILE] = future.s.r.frame(dict(previous, revision=previous['revision']+1, previous=e.digest(group[target][future.s.FILE]), plan=plan))
    final[target][future.future.FILE] = future.future.frame(dict(future.future.initial(group[target]), revision=2, previous=e.digest(retained[target])), {})
    b.match(root, 'after-slot', final)
    generation_prefix = c.current(final[target])[0]; generation = final[target][generation_prefix+'generation.gsr']
    need(all(v == dict(certificate=e.digest(certificate), selection=e.digest(local['selected.gsr']), published=upper, generation=e.digest(generation)) for v in published_acks), 'slot receiver durable publication ACK')
    future.s.ordered([v['event'] for v in events if v['node'] == target], ['PUBLICATION_SELECTOR_FORCED', 'RETENTION_PARENT_FORCED', 'FUTURE_RETENTION_PROMOTED', 'FUTURE_RETENTION_CLEARED', 'PUBLICATION_BEFORE_RETURN', 'PUBLICATION_ACK_BEFORE_RETURN'], 'slot publication force')
    return dict(status='PASS', size=size, kind=kind, controls=sum(controls.values()), transfers=sum(observed.values()), published=target, autonomous=False, phase3Complete=False)


def qualify(root):
    original = validate(root); results = []
    variants = [('vote', 'after-proof/node-2/pending.accept', 'admitted exact after-proof: node-2'),
        ('image', 'end-node-2/ack.gsr', 'slot receiver exact typed end'),
        ('retention', 'recorded-quorum/node-1/'+future.future.FILE, 'admitted exact recorded-quorum: node-1'),
        ('published', 'after-slot/'+original['published']+'/selector.gsr', 'admitted exact after-slot: '+original['published']),
        ('certificate', 'certificate.gsr', 'slot receiver original record certificate.gsr'),
        ('ordering', 'events.json', 'slot receiver recording before dispatch'),
        ('original-force', 'events.json', 'slot receiver original receipt force'),
        ('checkpoint-arrival', 'events.json', 'slot receiver actual checkpoint delivery'),
        ('missing-transfer', 'wire.json', 'slot receiver complete transfer'),
        ('missing-receipt', 'checkpoint-receipts.json', 'slot receiver exact checkpoint receipts')]
    for name, relative, reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-slot-negative-') as temp:
            dest = Path(temp)/'raw'; shutil.copytree(root, dest); path = dest/relative
            if name == 'ordering': path.write_text(json.dumps([v for v in read(path) if v['event'] != 'PUBLICATION_SEND_BOUNDARY']))
            elif name == 'original-force':
                rows = read(path); pos = next(i for i, v in enumerate(rows) if v['node'] == 'node-1' and v['event'] == 'PROOF_PARENT_FORCED'); rows.pop(pos); path.write_text(json.dumps(rows))
            elif name == 'checkpoint-arrival':
                rows = read(path); pos = max(i for i, v in enumerate(rows) if v['node'] == original['published'] and v['event'] == 'NETWORK_RECEIVED' and v.get('kind') == 'TRANSFER_COMMIT'); rows.pop(pos); path.write_text(json.dumps(rows))
            elif name == 'missing-transfer':
                rows = read(path); rows.pop(next(i for i, row in enumerate(rows) if application.v.transfer.wire(row['request'])[0] == 'TRANSFER_COMMIT')); path.write_text(json.dumps(rows))
            elif name == 'missing-receipt': path.write_text('[]')
            else: path.write_bytes(b'changed original')
            try: validate(dest)
            except ValueError as error: need(str(error) == reason, 'slot receiver unrelated negative '+name+': '+str(error))
            else: raise ValueError('slot receiver accepted negative '+name)
            results.append(dict(case=name, status='REJECTED', reason=reason))
    return dict(original=original, negatives=results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--negative', action='store_true'); args = parser.parse_args()
    print(json.dumps((qualify if args.negative else validate)(args.root), sort_keys=True))
