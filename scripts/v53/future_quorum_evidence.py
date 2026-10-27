"""Replay native future-target quorum recording, not automatic publication.

Derive every original vote/application/proof from public bootstrap before using
wire receipts. Exact old sources remain inputs; recorded snapshots are outputs.
"""
import argparse
import base64
import json
import shutil
import tempfile
import uuid
from pathlib import Path
from . import future_retention_evidence as future
from .selected_prefix_evidence import prefix

n, s, p, c, f, e, need = future.n, future.s, future.p, future.c, future.f, future.e, future.need


def read(path):
    return json.loads(p.t.plans.read(Path(path), 8*e.MIB))


POINTS = ('FUTURE_RETENTION_PREFIX_WRITTEN', 'FUTURE_RETENTION_FORCED', 'FUTURE_RETENTION_RENAMED',
          'FUTURE_RETENTION_PARENT_FORCED', 'FUTURE_RETENTION_ACK_BEFORE_RETURN')


def prelude(root, size, *, suffix=()):
    group = s.initialize(p.original(root, size, False))
    group = {node: dict(files, **{future.FILE: future.frame(future.initial(files), {})}) for node, files in group.items()}
    p.match(root, 'retaining-genesis', group)
    prepared, selected, installed = s.campaign(root, group, 2, 'round-1-prepared', selected_prefix=prefix)
    for label, states in [('prepared', prepared), ('selected', selected), ('installed', installed)]:
        p.match(root, 'round-1-'+label, states)
    group = p.settled(installed); p.match(root, 'round-1-settled', group)
    before, ends = {}, {}
    for node in sorted(group):
        certified, end, _, _ = n.certified_group(root, group, node)
        ends[node] = end
        before[node] = dict(certified, **{'applied-end': None}, **{'applied-end/'+k: v for k, v in end.items()})
    p.match(root, 'before-endpoint', before)
    rows = read(root/'calls.json'); names = sorted(group)
    expected = [(node, 'initialize-retention') for node in names]+[('node-1', 'allocate-1')]
    expected += [(node, phase+'-1') for phase in ('prepare', 'select', 'install') for node in names]
    expected += [(node, 'round-1-settled-'+phase) for phase in ('copy', 'maintain') for node in names]
    expected += [('node-1', 'entry-1')]+[(node, phase+'-1') for phase in ('accept', 'proof', 'certificate') for node in names]
    expected += [('node-1', 'apply-1')]
    need([(v['node'], v['operation']) for v in rows] == expected+list(suffix), 'future quorum original calls')
    for row in rows:
        required = {'initialize-retention': ['RETENTION_FORCED', 'RETENTION_PARENT_FORCED', 'FUTURE_RETENTION_FORCED', 'FUTURE_RETENTION_PARENT_FORCED'],
                    'prepare-1': ['PROMISE_FORCED', 'SOURCE_DIRECTORY_FORCED', 'BASIS_FORCED', 'GRANT_BEFORE_RETURN'],
                    'select-1': ['SELECTED_FORCED', 'SELECTED_BEFORE_RETURN'],
                    'install-1': ['INSTALL_GENERATION_FORCED', 'INSTALL_SELECTOR_FORCED', 'INSTALL_PARENT_FORCED', 'INSTALL_BEFORE_RETURN']}
        s.ordered(row['events'], required.get(row['operation'], []), 'future quorum '+row['operation'])
    return before, ends


def pending(files, end, peer):
    _, members, packet = c.current(files); cap = packet['capsule']; selected = f.decode(members['selected.gsr'], 'records', 'SELECTED')
    certificate = f.decode(end['certificate.gsr'], 'records', 'CERTIFICATE')
    proof = dict(certificate); del proof['proofs']; accept = dict(proof); del accept['accepts']
    entry = f.encode('records', 'ENTRY', dict(root=cap['root'], authority=selected['view'], index=1,
        previous=cap['cut']['entry'], origin=selected['ballot'], kind='BARRIER', payload=e.digest(b'')))
    originals = {name: end[name] for name in ('selector.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr', 'ack.gsr')}
    originals.update({name: members[name] for name in ('promise.gsr', 'selected.gsr')})
    originals.update({'entry.gsr': entry, 'accept.gsr': f.encode('records', 'ACCEPT', accept), 'proof.gsr': f.encode('records', 'PROOF', proof)})
    parent = c.anchor(cap)
    metadata = dict(future.initial(files), revision=1, previous=e.digest(files[future.FILE]), parent=parent,
                    peers=[dict(identity=peer, lower=parent)])
    return future.frame(metadata, originals)


def payload(before, ends):
    _, members, packet = c.current(before['node-1']); cap = packet['capsule']
    selected = f.decode(members['selected.gsr'], 'records', 'SELECTED')
    catalog = f.decode(ends['node-1']['catalog.gsr'], 'records', 'CATALOG')
    value = dict(selection=e.digest(members['selected.gsr']), certificate=e.digest(ends['node-1']['certificate.gsr']),
                 peer=future.identity(before[sorted(before)[-1]]), lower=c.anchor(cap), parent=c.anchor(cap),
                 upper=dict(cut=catalog['cut'], catalog=e.digest(ends['node-1']['catalog.gsr']), application=catalog['application']))
    return cap, selected, value


def acknowledgement(raw, sent, intent, retained):
    expected = dict(sent, sender=sent['recipient'], recipient=sent['sender'],
                    payload=dict(intent=intent, storage='FUTURE', revision=1, digest=e.digest(retained)))
    need(f.decode(raw, 'wire', 'FUTURE_RETENTION_ACK') == expected, 'future quorum exact native acknowledgement')


def processes(root):
    root = Path(root); cases = [(mode, point) for mode in ('halt', 'kill') for point in POINTS]
    suffix = []
    for mode, _ in cases:
        if mode == 'kill': suffix.append(('node-3', 'lock-probe'))
        suffix.append(('node-3', 'reopen-after-ack'))
    before, ends = prelude(root, 3, suffix=suffix); p.match(root, 'crash-ready', before)
    cap, selected, logical = payload(before, ends); intent = e.digest(f.canonical(logical))
    sent = f.decode(p.t.plans.read(root/'request.gsrp', 32768), 'wire', 'FUTURE_RETENTION_INTENT')
    expected = dict(root=cap['root'], view=selected['view'], ballot=selected['ballot'], sender=future.identity(before['node-1']),
                    recipient=future.identity(before['node-3']), trace=sent['trace'], sequence=1, payload=logical)
    need(str(uuid.UUID(sent['trace'])) == sent['trace'] and sent == expected, 'future process original request')
    retained = pending(before['node-3'], ends['node-3'], future.identity(before['node-3']))
    final = dict(before['node-3'], **{future.FILE: retained})
    need({path.name for path in root.iterdir() if path.name.startswith(('halt-', 'kill-'))} ==
         {mode+'-'+point for mode, point in cases}, 'future process complete cuts')
    results = []
    for mode, point in cases:
        path = root/(mode+'-'+point)
        p.selection.layout(path, {'worker.log', 'resume.log', 'interrupted', 'recovered', 'result.json'}, 'future ACK process')
        need(read(path/'result.json') == dict(mode=mode, cut=point, exit=23 if mode == 'halt' else 137), 'future process exact exit')
        lines, events = future.worker(path/'worker.log')
        need(lines[-1] == 'CUT '+point and events[-1] == point and sum(v.startswith('CUT ') for v in lines) == 1
             and not any(v.startswith('RESPONSE ') for v in lines), 'future process interrupted response')
        n.native_order(events, 1)
        required = ['FUTURE_RETENTION_BEFORE_WRITE', 'FUTURE_RETENTION_PREFIX_WRITTEN']
        if point != POINTS[0]: required += ['FUTURE_RETENTION_FORCED']
        if point in POINTS[2:]: required += ['FUTURE_RETENTION_CANDIDATE_PARENT_FORCED', 'FUTURE_RETENTION_RENAMED']
        if point in POINTS[3:]: required += ['FUTURE_RETENTION_PARENT_FORCED']
        if point == POINTS[4]: required += ['FUTURE_RETENTION_ACK_BEFORE_RETURN']
        s.ordered(events, required, 'future ACK original force')
        interrupted = dict(before['node-3'] if point in POINTS[:2] else final)
        if point in POINTS[:2]: interrupted[future.NEXT] = retained[:len(retained)//2] if point == POINTS[0] else retained
        need(c.inventory(path/'interrupted') == interrupted, 'future ACK exact interrupted files')
        need(c.inventory(path/'recovered') == final, 'future ACK exact recovered files')
        resumed, steps = future.worker(path/'resume.log')
        need(resumed[-1].startswith('RESPONSE ') and sum(v.startswith('RESPONSE ') for v in resumed) == 1
             and not any(v.startswith('CUT ') for v in resumed), 'future ACK recovered response position')
        acknowledgement(base64.b64decode(resumed[-1][9:], validate=True), sent, intent, retained)
        n.native_order(steps, 1)
        required = ['FUTURE_RETENTION_FORCED', 'FUTURE_RETENTION_PARENT_FORCED'] if point in POINTS[:2] else [
            'FUTURE_RETENTION_RECOVERY_FORCED', 'FUTURE_RETENTION_RECOVERY_PARENT_FORCED']
        s.ordered(steps, required+['FUTURE_RETENTION_ACK_BEFORE_RETURN'], 'future ACK resume force')
        need(steps.count('FUTURE_RETENTION_ACK_BEFORE_RETURN') == 2 and
             steps.count('FUTURE_RETENTION_BEFORE_WRITE') == (1 if point in POINTS[:2] else 0), 'future ACK exact duplicate')
        results.append(dict(mode=mode, cut=point, status='PASS'))
    final_group = dict(before, **{'node-3': final}); p.match(root, 'after-endpoint', final_group)
    events = read(root/'endpoint-events.json'); need([row['node'] for row in events] == sorted(before), 'future process original owners')
    for row in events: n.native_order(row['events'], 1)
    return dict(status='PASS', cases=results, processCases=len(results), freshProcesses=2*len(results), lockProbes=5,
                nativeReceiver=True, automaticDispatch=False, powerLoss=False, phase3Complete=False)


def qualify_processes(root):
    root = Path(root); original = processes(root); negatives = []
    cut = 'kill-FUTURE_RETENTION_FORCED'
    variants = [('original-certificate', 'certified/node-1/pending.accept', 'admitted exact certified: node-1'),
                ('partial-proof', cut+'/interrupted/'+future.NEXT, 'future ACK exact interrupted files'),
                ('recovered-proof', cut+'/recovered/'+future.FILE, 'future ACK exact recovered files'),
                ('force', cut+'/worker.log', 'selected retention force order: future ACK original force'),
                ('response', cut+'/resume.log', 'future quorum exact native acknowledgement'),
                ('duplicate', cut+'/resume.log', 'future ACK exact duplicate')]
    for name, relative, reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-future-ACK-negative-') as temp:
            target = Path(temp)/'raw'; shutil.copytree(root, target); path = target/relative; raw = path.read_bytes()
            if name == 'force': changed = raw.replace(b'EVENT FUTURE_RETENTION_BEFORE_WRITE\n', b'', 1)
            elif name == 'duplicate': changed = raw.replace(b'EVENT FUTURE_RETENTION_ACK_BEFORE_RETURN\n', b'', 1)
            elif name == 'response':
                lines = raw.decode().splitlines(); value = f.decode(base64.b64decode(lines[-1][9:], validate=True), 'wire', 'FUTURE_RETENTION_ACK')
                value['payload']['digest'] = 'f'*64
                lines[-1] = 'RESPONSE '+base64.b64encode(f.encode('wire', 'FUTURE_RETENTION_ACK', value)).decode()
                changed = ('\n'.join(lines)+'\n').encode()
            else: changed = raw[:-1]+bytes([raw[-1]^1])
            need(changed != raw, 'future ACK ineffective mutation'); path.write_bytes(changed)
            try: processes(target)
            except ValueError as error: need(str(error) == reason, 'future ACK wrong rejection: '+name+': '+str(error))
            else: raise ValueError('future ACK mutation accepted: '+name)
        negatives.append(dict(case=name, status='REJECTED', reason=reason))
    return dict(original=original, negatives=negatives)


def validate(root):
    root = Path(root); size = len(list((root/'before-endpoint').iterdir())); need(size in (3, 4, 5), 'future quorum stable size')
    before, ends = prelude(root, size); names = sorted(before); identities = {node: future.identity(files) for node, files in before.items()}
    target = names[-1]; retained = {node: pending(files, ends[node], identities[target]) for node, files in before.items()}
    final = {node: dict(files, **{future.FILE: retained[node]}) for node, files in before.items()}
    p.match(root, 'recorded-quorum', final); p.match(root, 'after-endpoint', final)
    _, members, packet = c.current(before['node-1']); cap = packet['capsule']; selected = f.decode(members['selected.gsr'], 'records', 'SELECTED')
    catalog = f.decode(ends['node-1']['catalog.gsr'], 'records', 'CATALOG')
    payload = dict(selection=e.digest(members['selected.gsr']), certificate=e.digest(ends['node-1']['certificate.gsr']),
                   peer=identities[target], lower=c.anchor(cap), parent=c.anchor(cap),
                   upper=dict(cut=catalog['cut'], catalog=e.digest(ends['node-1']['catalog.gsr']), application=catalog['application']))
    intent = e.digest(f.canonical(payload)); result = read(root/'quorum.json')
    need(set(result) == {'intent', 'voters', 'requests', 'lostAck'} and result['intent'] == intent, 'future quorum result identity')
    need(result['lostAck'] is (size == 3), 'future quorum loss profile')
    voters = result['voters']; need(voters == sorted(set(voters)) and 'node-1' in voters and set(voters) <= set(names)
            and len(voters) == size//2+1, 'future quorum governing majority')
    wire = read(root/'wire.json'); replies, attempts, traces = {}, {}, set()
    for row in wire:
        request = base64.b64decode(row['request'], validate=True); response = base64.b64decode(row['response'], validate=True)
        sent = f.decode(request, 'wire', 'FUTURE_RETENTION_INTENT'); node = sent['recipient']['node']
        need(node in names[1:] and sent['sequence'] in (1, int(node[5:])), 'future quorum request recipient/sequence')
        expected = dict(root=cap['root'], view=selected['view'], ballot=selected['ballot'], sender=identities['node-1'],
                        recipient=identities[node], trace=sent['trace'], sequence=sent['sequence'], payload=payload)
        need(sent == expected, 'future quorum exact native request')
        reply = dict(expected, sender=identities[node], recipient=identities['node-1'],
                     payload=dict(intent=intent, storage='FUTURE', revision=1, digest=e.digest(retained[node])))
        need(f.decode(response, 'wire', 'FUTURE_RETENTION_ACK') == reply, 'future quorum exact native acknowledgement')
        if sent['sequence'] != 1:
            attempts.setdefault(node, []).append(e.digest(request)); traces.add(sent['trace']); replies[e.digest(response)] = node
    need(len(traces) == 1 and [v['node'] for v in result['requests']] == names[1:] and
         all(set(v) == {'node', 'digests'} for v in result['requests']), 'future quorum request inventory')
    for request_row in result['requests']:
        node, hashes = request_row['node'], request_row['digests']
        need(1 <= len(hashes) <= 3 and len(set(hashes)) == 1, 'future quorum exact bounded retries')
        need(all(h == hashes[0] for h in attempts.get(node, [])), 'future quorum retry frame changed')
    if size == 3:
        need(voters == ['node-1', 'node-3'] and 'node-2' not in attempts and len(attempts.get('node-3', [])) == 2,
             'future quorum lost ACK/target voter history')
    timeline = read(root/'timeline.json'); completions = [i for i, row in enumerate(timeline) if row['event'] == 'FUTURE_QUORUM_COMPLETE']
    need(len(completions) == 1, 'future quorum completion boundary'); prior = timeline[:completions[0]]
    events = read(root/'endpoint-events.json'); need([row['node'] for row in events] == names, 'future quorum actual owners')
    for row in events:
        node, steps = row['node'], row['events']; n.native_order(steps, 1)
        need(steps.count('FUTURE_RETENTION_BEFORE_WRITE') == 1 and 'PUBLICATION_SELECTOR_FORCED' not in steps,
             'future quorum duplicate rewrite/publication')
        s.ordered(steps, ['APPLY_BEFORE_RETURN', 'FUTURE_RETENTION_FORCED', 'FUTURE_RETENTION_PARENT_FORCED', 'FUTURE_RETENTION_ACK_BEFORE_RETURN'], node)
        if node in voters:
            own = [v['event'] for v in prior if v['node'] == node]
            s.ordered(own, ['FUTURE_RETENTION_FORCED', 'FUTURE_RETENTION_PARENT_FORCED', 'FUTURE_RETENTION_ACK_BEFORE_RETURN']+
                      ([] if node == 'node-1' else ['FUTURE_ACK_RECEIVED']), 'future quorum before completion '+node)
            if node != 'node-1':
                deliveries = [v for v in prior if v['node'] == node and v['event'] == 'FUTURE_ACK_RECEIVED']
                need(deliveries and all(replies.get(v['digest']) == node for v in deliveries), 'future quorum actual received acknowledgement')
    return dict(status='PASS', size=size, lostAck=result['lostAck'], voters=voters, exchanges=len(wire),
                governingFutureRecording=True, automaticDispatch=False, phase3Complete=False)


def qualify(root):
    root = Path(root); original = validate(root); negatives = []
    reasons = {'original-certificate': 'admitted exact certified: node-1', 'local-proof': 'admitted exact recorded-quorum: node-1',
               'target-proof': 'admitted exact recorded-quorum: node-'+str(original['size']),
               'wire-target': 'future quorum exact native request', 'ack-owner': 'future quorum exact native acknowledgement',
               'force': 'selected retention force order: future quorum before completion node-1',
               'received-ack': 'selected retention force order: future quorum before completion '+original['voters'][1],
               'quorum': 'future quorum governing majority', 'retry': 'future quorum exact bounded retries'}
    for name in ('original-certificate', 'local-proof', 'target-proof', 'wire-target', 'ack-owner', 'force', 'received-ack', 'quorum', 'retry'):
        with tempfile.TemporaryDirectory(prefix='v53-future-quorum-negative-') as temp:
            target = Path(temp)/'raw'; shutil.copytree(root, target)
            if name in ('original-certificate', 'local-proof', 'target-proof'):
                path = target/({'original-certificate':'certified/node-1/pending.accept', 'local-proof':'recorded-quorum/node-1/'+future.FILE,
                                'target-proof':'recorded-quorum/node-'+str(original['size'])+'/'+future.FILE}[name])
                raw = path.read_bytes(); path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name in ('wire-target', 'ack-owner'):
                path = target/'wire.json'; values = read(path); field, kind = ('request','FUTURE_RETENTION_INTENT') if name == 'wire-target' else ('response','FUTURE_RETENTION_ACK')
                value = f.decode(base64.b64decode(values[0][field]), 'wire', kind)
                if name == 'wire-target': value['payload']['upper']['application'] = 'f'*64
                else: value['payload']['digest'] = 'f'*64
                values[0][field] = base64.b64encode(f.encode('wire', kind, value)).decode(); path.write_text(json.dumps(values))
            elif name in ('force', 'received-ack'):
                path = target/'timeline.json'; values = read(path)
                victim = next(v for v in values if v['event'] == ('FUTURE_RETENTION_FORCED' if name == 'force' else 'FUTURE_ACK_RECEIVED')
                              and v['node'] == ('node-1' if name == 'force' else original['voters'][1]))
                values.remove(victim); path.write_text(json.dumps(values))
            else:
                path = target/'quorum.json'; value = read(path)
                if name == 'quorum': value['voters'] = ['node-1']
                else: value['requests'][0]['digests'].append('f'*64)
                path.write_text(json.dumps(value))
            try: validate(target)
            except ValueError as error:
                need(str(error) == reasons[name], 'future quorum wrong rejection: '+name+': '+str(error))
                negatives.append(dict(case=name, status='REJECTED', reason=str(error)))
            else: raise ValueError('future quorum mutation accepted: '+name)
    return dict(original=original, negatives=negatives)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--qualify', action='store_true'); parser.add_argument('--processes', action='store_true')
    args = parser.parse_args(); check = (qualify_processes if args.qualify else processes) if args.processes else (qualify if args.qualify else validate)
    print(json.dumps(check(args.root), sort_keys=True))
