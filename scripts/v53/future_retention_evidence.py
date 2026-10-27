"""Replay local future-retention transactions from original bootstrap and votes.

No Java result, claimed endpoint or stored GSFT checksum supplies authority. The
original campaign, certificate, actual end, publication and every retained byte
are derived before comparing interrupted/recovered inventories. This qualifies a
local prerequisite, not quorum permission, selection propagation or dispatch.
"""
import argparse
import copy
import json
import shutil
import struct
import tempfile
from pathlib import Path
from . import native_application_evidence as n
from . import selected_retention_evidence as s

p, c, f, e, need = n.p, n.c, n.f, n.e, n.need
FILE, NEXT = 'future-retention.gsft', 'future-retention.next.gsft'
RECORDS = ('selector.gsr', 'promise.gsr', 'selected.gsr', 'entry.gsr', 'accept.gsr',
           'proof.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr', 'ack.gsr')
RECORD_POINTS = ('FUTURE_RETENTION_PREFIX_WRITTEN', 'FUTURE_RETENTION_FORCED',
                 'FUTURE_RETENTION_RENAMED', 'FUTURE_RETENTION_BEFORE_RETURN')
PUBLISH_POINTS = ('PUBLICATION_SELECTOR_FORCED', 'RETENTION_PREFIX_WRITTEN', 'RETENTION_RENAMED',
                  'FUTURE_RETENTION_PREFIX_WRITTEN', 'FUTURE_RETENTION_RENAMED')


def frame(metadata, records):
    body = s.part(f.canonical(metadata))+struct.pack('>I', len(records))
    need(not records or set(records) == set(RECORDS), 'future exact original record inventory')
    for name in RECORDS if records else ():
        body += s.part(records[name])
    need(len(body)+44 <= 3*e.MIB, 'future private record capacity')
    return struct.pack('>IHHI', 0x47534654, 1, 3, 44+len(body))+bytes.fromhex(e.digest(body))+body


def identity(files):
    return f.decode(files['node.gsr'], 'records', 'NODE')['identity']


def initial(files):
    return dict(root=n.identity_root(files), owner=identity(files), revision=0,
                previous=None, parent=None, peers=[])


def prelude(root, *, selected_prefix=None):
    group = s.initialize(p.original(root, 3, False))
    group = {node: dict(files, **{FILE: frame(initial(files), {})}) for node, files in group.items()}
    p.match(root, 'retaining-genesis', group)
    prepared, chosen, installed = s.campaign(root, group, 2, 'round-1-prepared', selected_prefix=selected_prefix)
    for name, value in [('prepared', prepared), ('selected', chosen), ('installed', installed)]:
        p.match(root, 'round-1-'+name, value)
    group = p.settled(installed); p.match(root, 'round-1-settled', group)
    before, ends = {}, {}
    for node in sorted(group):
        original, end, _, _ = n.certified_group(root, group, node)
        ends[node] = end
        before[node] = dict(original, **{'applied-end': None}, **{'applied-end/'+k: v for k, v in end.items()})
    p.match(root, 'before-future', before)
    rows = n.read_json(root/'calls.json')
    for phase, required in [('initialize-retention', ['RETENTION_PARENT_FORCED', 'FUTURE_RETENTION_FORCED', 'FUTURE_RETENTION_PARENT_FORCED']),
            ('prepare-1', ['PROMISE_FORCED', 'SOURCE_DIRECTORY_FORCED', 'BASIS_FORCED', 'GRANT_BEFORE_RETURN']),
            ('select-1', ['SELECTED_FORCED', 'SELECTED_BEFORE_RETURN']),
            ('install-1', ['INSTALL_GENERATION_FORCED', 'INSTALL_SELECTOR_FORCED', 'INSTALL_PARENT_FORCED', 'INSTALL_BEFORE_RETURN']),
            ('initial-apply', ['NATIVE_CERTIFICATE_RETAINED', 'APPLY_ACK_DIRECTORY_FORCED', 'APPLY_BEFORE_RETURN'])]:
        actual = [row for row in rows if row['operation'] == phase]
        need([row['node'] for row in actual] == sorted(group), 'future original owner calls: '+phase)
        for row in actual:
            s.ordered(row['events'], required, phase)
            if phase == 'initial-apply': n.native_order(row['events'], 1)
    return group, before, ends


def pending(before, ends):
    files = before['node-1']; _, local, packet = c.current(files); end = ends['node-1']
    certificate = f.decode(end['certificate.gsr'], 'records', 'CERTIFICATE')
    proof = dict(certificate); del proof['proofs']
    accept = dict(proof); del accept['accepts']
    # ENTRY is the original first BARRIER, never a reconstructed remote receipt.
    cap = packet['capsule']; selected = f.decode(local['selected.gsr'], 'records', 'SELECTED')
    entry = f.encode('records', 'ENTRY', dict(root=cap['root'], authority=selected['view'], index=1,
        previous=cap['cut']['entry'], origin=selected['ballot'], kind='BARRIER', payload=e.digest(b'')))
    originals = {name: end[name] for name in ('selector.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr', 'ack.gsr')}
    originals.update({name: local[name] for name in ('promise.gsr', 'selected.gsr')})
    originals.update({'entry.gsr': entry, 'accept.gsr': f.encode('records', 'ACCEPT', accept),
                      'proof.gsr': f.encode('records', 'PROOF', proof)})
    parent = c.anchor(cap); metadata = dict(initial(files), revision=1, previous=e.digest(files[FILE]), parent=parent,
            peers=[dict(identity=identity(before['node-2']), lower=parent)])
    active = frame(metadata, originals)
    return dict(files, **{FILE: active}), metadata, originals


def published(group, before, ends, retained, metadata, originals):
    files = retained; prefix, local, packet = c.current(files); cap = packet['capsule']; end = ends['node-1']
    catalog = f.decode(end['catalog.gsr'], 'records', 'CATALOG')
    upper = dict(cut=catalog['cut'], catalog=e.digest(end['catalog.gsr']), application=catalog['application'])
    acks = [ends[node]['ack.gsr'] for node in sorted(ends)]
    values = [files[k] for k in ('root.gsr', 'genesis.gsr')]
    values += [originals[k] for k in ('entry.gsr', 'accept.gsr', 'proof.gsr', 'certificate.gsr')]
    values += [b'', end['catalog.gsr'], end['statement.gsr'], *acks]
    objects = {e.digest(raw): raw for raw in values}
    item = dict(kind='RANGE', statement=e.digest(end['statement.gsr']), endorsements=[e.digest(raw) for raw in acks], certificate=None, descriptor=None)
    source = e.packet_bytes(dict(cap, **upper, items=[item]), objects, {catalog['application']: len(end['application.image'])})
    coverage = dict(schema='gse-v53-selected-coverage/1.3', selection=e.digest(local['selected.gsr']), parent=c.anchor(cap), certificate=e.digest(end['certificate.gsr']))
    members = {k: local[k] for k in ('promise.gsr', 'basis.gsr', 'selected.gsr', 'selected-sources.gsr')}
    members.update({'source.gscp': source, c.COVERAGE: f.canonical(coverage), catalog['application']+'.image': end['application.image']})
    selector, generation = c.generation(members, e.p.decode(source)['capsule'], 'node-1', 'b' if prefix == 'generations/a/' else 'a', None)
    switched = dict(files, **generation, **{'selector.gsr': selector})
    retired = {k: v for k, v in switched.items() if k != 'applied-end' and not k.startswith('applied-end/')}
    retired['pending.accept'] = c.EMPTY
    ledger = s.r.decode(files[s.FILE]); plan = copy.deepcopy(ledger['plan']); plan['peers'][1]['possible'].append(upper)
    merged = s.r.frame(dict(ledger, revision=ledger['revision']+1, previous=e.digest(files[s.FILE]), plan=plan))
    cleared = frame(dict(metadata, revision=2, previous=e.digest(files[FILE]), parent=None, peers=[]), {})
    completed = dict(retired, **{s.FILE: merged, FILE: cleared})
    return switched, retired, completed


def worker(path):
    lines = p.t.plans.read(path, 8*e.MIB).decode().splitlines()
    need(all(line.startswith(('EVENT ', 'COLLECT ', 'CUT ', 'RESPONSE ')) for line in lines), 'future worker log shape')
    return lines, [line[6:] for line in lines if line.startswith('EVENT ')]


def crash(path, action, mode, point, before, retained, switched, retired, completed):
    p.selection.layout(path, {'worker.log', 'resume.log', 'interrupted', 'recovered', 'result.json'}, 'future process evidence')
    need(n.read_json(path/'result.json') == dict(status='PASS', action=action, mode=mode, cut=point, exit=23 if mode == 'halt' else 137), 'future process exact exit')
    lines, events = worker(path/'worker.log')
    need(lines[-1] == 'CUT '+point and events[-1] == point and len([v for v in lines if v.startswith('CUT ')]) == 1
         and not any(v.startswith('RESPONSE ') for v in lines), 'future interrupted before response')
    if action == 'record':
        n.native_order(events, 1)
        expected = dict(before if point in RECORD_POINTS[:2] else retained)
        if point in RECORD_POINTS[:2]:
            raw = retained[FILE]; expected[NEXT] = raw[:len(raw)//2] if point == RECORD_POINTS[0] else raw
        required = ['FUTURE_RETENTION_PREFIX_WRITTEN']
        if point != RECORD_POINTS[0]: required += ['FUTURE_RETENTION_FORCED']
        if point in RECORD_POINTS[2:]: required += ['FUTURE_RETENTION_CANDIDATE_PARENT_FORCED', 'FUTURE_RETENTION_RENAMED']
        if point == RECORD_POINTS[3]: required += ['FUTURE_RETENTION_PARENT_FORCED', 'FUTURE_RETENTION_BEFORE_RETURN']
        s.ordered(events, required, 'future record')
        final = retained
    else:
        n.native_order(events, 1); s.ordered(events, ['PUBLICATION_SELECTOR_FORCED'], 'future covering selector')
        expected = dict(switched if point == PUBLISH_POINTS[0] else retired)
        if point == PUBLISH_POINTS[1]: expected[s.NEXT] = completed[s.FILE][:len(completed[s.FILE])//2]
        if point in PUBLISH_POINTS[2:]: expected[s.FILE] = completed[s.FILE]
        if point == PUBLISH_POINTS[3]: expected[NEXT] = completed[FILE][:len(completed[FILE])//2]
        if point == PUBLISH_POINTS[4]: expected[FILE] = completed[FILE]
        if point in PUBLISH_POINTS[3:]: s.ordered(events, ['RETENTION_PARENT_FORCED', 'FUTURE_RETENTION_PROMOTED'], 'future merge before clear')
        final = completed
    need(c.inventory(path/'interrupted') == expected, 'future exact interrupted files')
    need(c.inventory(path/'recovered') == final, 'future exact recovered files')
    resumed, recovery = worker(path/'resume.log')
    need(resumed[-1].startswith('RESPONSE ') and sum(v.startswith('RESPONSE ') for v in resumed) == 1
         and not any(v.startswith('CUT ') for v in resumed), 'future recovered response position')
    ledger = s.r.decode(final[s.FILE]); published_cut = c.current(final)[2]['capsule']['cut']
    expected_response = dict(pending=action == 'record', revision=1 if action == 'record' else 2,
            digest=e.digest(final[FILE]), plan=ledger['plan'], peerRevision=ledger['revision'], published=published_cut)
    need(json.loads(resumed[-1][9:]) == expected_response, 'future exact recovered response')
    if action == 'record':
        n.native_order(recovery, 1)
        s.ordered(recovery, ['FUTURE_RETENTION_FORCED', 'FUTURE_RETENTION_PARENT_FORCED', 'FUTURE_RETENTION_BEFORE_RETURN']
                  if point in RECORD_POINTS[:2] else ['FUTURE_RETENTION_RECOVERY_FORCED', 'FUTURE_RETENTION_RECOVERY_PARENT_FORCED'], 'future record resume')
    elif point in PUBLISH_POINTS[:4]:
        s.ordered(recovery, ['FUTURE_RETENTION_PROMOTED', 'FUTURE_RETENTION_FORCED', 'FUTURE_RETENTION_PARENT_FORCED', 'FUTURE_RETENTION_CLEARED'], 'future publication resume')
    else:
        s.ordered(recovery, ['FUTURE_RETENTION_RECOVERY_FORCED', 'FUTURE_RETENTION_RECOVERY_PARENT_FORCED'], 'future cleared resume')
    return dict(action=action, mode=mode, cut=point, status='PASS')


def validate(root):
    root = Path(root)
    cases = [(action, mode, point) for action, points in [('record', RECORD_POINTS), ('publish', PUBLISH_POINTS)]
             for mode in ('halt', 'kill') for point in points]
    required = {'original-plan.gsbp', 'original-application.image', 'initial', 'retaining-genesis',
                'calls.json', 'nodes.json', 'entry-1.gsr', 'payload-1.bin', 'certified', 'before-future', 'pending-future'}
    required |= {'round-1-'+name for name in ('prepared', 'selected', 'installed', 'settled')}
    required |= {'slot-1-'+name for name in ('accepted', 'proved', 'certified')}
    p.selection.layout(root, required | {'-'.join(case) for case in cases}, 'future complete process matrix')
    group, before, ends = prelude(root)
    retained, metadata, originals = pending(before, ends)
    p.match(root, 'pending-future', dict(before, **{'node-1': retained}))
    switched, retired, completed = published(group, before, ends, retained, metadata, originals)
    results = [crash(root/'-'.join(case), *case, before['node-1'], retained, switched, retired, completed) for case in cases]
    return dict(status='PASS', cases=results, processCases=len(results), freshProcesses=2*len(results),
                localFutureRetention=True, selectionPropagation=False, governingQuorum=False,
                automaticDispatch=False, powerLoss=False, phase3Complete=False)


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    record = 'record-kill-FUTURE_RETENTION_FORCED'; publish = 'publish-halt-FUTURE_RETENTION_PREFIX_WRITTEN'
    variants = [('initial', 'retaining-genesis/node-1/'+FILE, 'admitted exact retaining-genesis: node-1'),
        ('certificate', 'certified/node-1/pending.accept', 'admitted exact certified: node-1'),
        ('target-proof', 'pending-future/node-1/'+FILE, 'admitted exact pending-future: node-1'),
        ('partial-proof', record+'/interrupted/'+NEXT, 'future exact interrupted files'),
        ('recovered-proof', record+'/recovered/'+FILE, 'future exact recovered files'),
        ('promoted-ledger', publish+'/recovered/'+s.FILE, 'future exact recovered files'),
        ('clear-candidate', publish+'/interrupted/'+NEXT, 'future exact interrupted files'),
        ('publication-selector', publish+'/recovered/selector.gsr', 'future exact recovered files'),
        ('force-order', record+'/worker.log', 'selected retention force order: future record'),
        ('response', record+'/resume.log', 'future exact recovered response')]
    for name, relative, reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-future-negative-') as temp:
            target = Path(temp)/'raw'; shutil.copytree(root, target); path = target/relative; raw = path.read_bytes()
            if name == 'force-order': raw = raw.replace(b'EVENT FUTURE_RETENTION_PREFIX_WRITTEN\n', b'', 1)
            elif name == 'response': raw = raw.replace(b'"pending":true', b'"pending":false', 1)
            else: raw = raw[:-1]+bytes([raw[-1]^1])
            need(raw != path.read_bytes(), 'future ineffective evidence mutation'); path.write_bytes(raw)
            try: validate(target)
            except ValueError as error: need(str(error) == reason, f'future wrong negative reason: {name}: {error}')
            else: raise ValueError('future negative accepted: '+name)
        negatives.append(dict(case=name, status='REJECTED', reason=reason))
    return dict(result, negatives=negatives)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--qualify', action='store_true')
    args = parser.parse_args(); print(json.dumps((qualify if args.qualify else validate)(args.root), sort_keys=True))
