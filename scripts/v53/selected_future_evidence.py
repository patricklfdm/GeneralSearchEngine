"""Original-first replay of every future proof in a selected installation plan.

Derive the real bootstrap, votes, applied ends, local future intentions and grants
before comparing the complete proposed generations. No proposal or stored checksum
is an installation receipt. Native handoff is qualified separately by
inherited_future_evidence; this reader retains the earlier proposal-only scope.
"""
import argparse
import json
import shutil
import tempfile
import uuid
from pathlib import Path
from . import future_source_evidence as source

u, s = source.u, source.u.s
p, c, f, e, need = u.p, u.c, u.f, u.e, u.need


def pending(files, end, peer):
    _, local, packet = c.current(files)
    certificate = f.decode(end['certificate.gsr'], 'records', 'CERTIFICATE')
    proof = dict(certificate); del proof['proofs']
    accept = dict(proof); del accept['accepts']
    cap = packet['capsule']; selected = f.decode(local['selected.gsr'], 'records', 'SELECTED')
    entry = f.encode('records', 'ENTRY', dict(root=cap['root'], authority=selected['view'], index=1,
        previous=cap['cut']['entry'], origin=selected['ballot'], kind='BARRIER', payload=e.digest(b'')))
    originals = {name: end[name] for name in ('selector.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr', 'ack.gsr')}
    originals.update({name: local[name] for name in ('promise.gsr', 'selected.gsr')})
    originals.update({'entry.gsr': entry, 'accept.gsr': f.encode('records', 'ACCEPT', accept),
                      'proof.gsr': f.encode('records', 'PROOF', proof)})
    parent = c.anchor(cap)
    metadata = dict(u.initial(files), revision=1, previous=e.digest(files[u.FILE]), parent=parent,
                    peers=[dict(identity=u.identity(peer), lower=parent)])
    return u.frame(metadata, originals), originals


def original_sources(root, *, selected_prefix=None):
    """Derive the shared native prelude; callers validate their own later inventory."""
    root = Path(root)
    _, before, ends = u.prelude(root, selected_prefix=selected_prefix)
    one, original_one = pending(before['node-1'], ends['node-1'], before['node-2'])
    two, original_two = pending(before['node-2'], ends['node-2'], before['node-3'])
    first = dict(before, **{'node-1': dict(before['node-1'], **{u.FILE: one})})
    p.match(root, 'pending-future', first)
    group = dict(first, **{'node-2': dict(before['node-2'], **{u.FILE: two})})
    p.match(root, 'two-futures', group)
    originals = {'node-1': original_one, 'node-2': original_two, 'node-3': original_one}
    future = {'node-1': one, 'node-2': two}
    names = sorted(group); proposer = u.identity(group['node-3'])
    ballot = dict(counter=3, proposer='node-3', incarnation=proposer['storage'])
    identifiers = set(); prepared, sources, grants = {}, {}, {}
    for node, files in group.items():
        _, local, packet = c.current(files); cap = packet['capsule']
        actual = c.inventory(root/'proposal-sources'/node)
        old = c.journal(files['grants.gsr'], cap['root'], node)
        history = c.journal(actual['grants.gsr'], cap['root'], node)
        need(history[:len(old)] == old and [v[0] for v in history[len(old):]] == ['PROMISE', 'BASIS'],
             'selected future original grant history')
        identifier = history[len(old)][2]['basisId']
        need(str(uuid.UUID(identifier)) == identifier and identifier not in identifiers
             and all(v[2].get('basisId') != identifier for v in old), 'selected future fresh source identity')
        identifiers.add(identifier)
        value = dict(root=cap['root'], view=e.authority(cap['root'], cap['cut']['view']), ballot=ballot, basisId=identifier)
        promise = f.encode('records', 'PROMISE', value)
        wrapper = source.wrapper(promise, files[s.FILE], future[node]) if node in future else s.s.wrap(promise, files[s.FILE])
        objects = dict(packet['objects'])
        for name in ('entry.gsr', 'accept.gsr', 'proof.gsr', 'certificate.gsr'):
            objects[e.digest(originals[node][name])] = originals[node][name]
        objects[e.digest(b'')] = b''; objects[e.digest(wrapper)] = wrapper
        if node in future: objects[e.digest(future[node])] = future[node]
        raw = c.packet_bytes(cap, objects, packet['images']); frozen = s.p.decode(raw)
        basis = f.encode('records', 'BASIS', dict(value, voter=node, cut=cap['cut'],
            capsule=e.digest(frozen['capsuleBytes']), inventory=e.digest(frozen['indexBytes']), accepted=e.digest(originals[node]['accept.gsr'])))
        s.p.bind(frozen, basis); directory = 'sources/'+identifier
        changed = dict(files, **{'grants.gsr': files['grants.gsr']+promise+basis, directory: None, directory+'/source.gscp': raw})
        for h in packet['images']: changed[directory+'/'+h+'.image'] = local[h+'.image']
        if node == 'node-3': changed['allocator.gsr'] = f.encode('records', 'ALLOCATOR', dict(root=cap['root'], node=node, counter=3))
        prepared[node], sources[node], grants[node] = changed, (basis, frozen, wrapper), (promise, basis)
    p.match(root, 'proposal-sources', prepared)
    return group, prepared, sources, grants, future, original_one, ballot


def validate(root):
    root = Path(root)
    required = {'original-plan.gsbp', 'original-application.image', 'initial', 'retaining-genesis',
                'calls.json', 'entry-1.gsr', 'payload-1.bin', 'certified', 'before-future', 'pending-future',
                'two-futures', 'proposal-sources', 'after-proposal', 'proposed-node-1', 'proposed-node-3'}
    required |= {'round-1-'+name for name in ('prepared', 'selected', 'installed', 'settled')}
    required |= {'slot-1-'+name for name in ('accepted', 'proved', 'certified')}
    p.selection.layout(root, required, 'selected future original inventory')
    group, prepared, sources, grants, future, original_one, ballot = original_sources(root)
    names = sorted(group)
    p.match(root, 'after-proposal', prepared)
    # The actual proposer wins this equal-prefix tie and has NO future proof.
    # Both exact obligations therefore come from other selected originals.
    longest = sources['node-3'][1]; cap = longest['capsule']
    selected = f.encode('records', 'SELECTED', dict(root=cap['root'], view=e.authority(cap['root'], cap['cut']['view']),
        ballot=ballot, cut=cap['cut'], nextEntry=e.digest(original_one['entry.gsr']),
        sources=[dict(voter=n, basisId=f.decode(grants[n][1], 'records', 'BASIS')['basisId'], basisDigest=e.digest(grants[n][1])) for n in names]))
    need(all(e.digest(raw) not in longest['objects'] for raw in future.values()), 'selected future longest unexpectedly owns proof')
    for node in ('node-1', 'node-3'):
        intent = s.intent(u.identity(group[node]), selected, group[node][s.FILE], [sources[n] for n in names])
        objects = dict(longest['objects'], **{e.digest(raw): raw for raw in future.values()}, **{e.digest(intent): intent})
        packet = c.packet_bytes(cap, objects, longest['images'])
        _, local, _ = c.current(group[node])
        members = dict(zip(('promise.gsr', 'basis.gsr'), grants[node]), **{'source.gscp': packet,
            'selected.gsr': selected, 'selected-sources.gsr': b''.join(grants[n][1] for n in names),
            'owned-tail.gsr': original_one['accept.gsr']})
        for h in longest['images']: members[h+'.image'] = local[h+'.image']
        selector, files = c.generation(members, s.p.decode(packet)['capsule'], node, 'a', e.digest(original_one['accept.gsr']))
        wanted = {k.removeprefix('generations/a/'): v for k, v in files.items() if v is not None}
        wanted['proposed-selector.gsr'] = selector
        need(c.inventory(root/('proposed-'+node)) == wanted, 'selected future exact proposed generation: '+node)
        need(len(packet) <= 32*e.MIB and len(intent) <= 8*e.MIB, 'selected future materialization capacity')
    calls = u.n.read_json(root/'calls.json')
    allocation=[row for row in calls if row['operation']=='allocate-proposal']
    need(len(allocation)==1 and allocation[0]['node']=='node-3','selected future original allocation')
    s.ordered(allocation[0]['events'],['ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN'],
              'selected future allocation')
    for op, nodes in [('record-future', ['node-1']), ('second-future', ['node-2']), ('capture-proposal', names)]:
        rows = [row for row in calls if row['operation'] == op]
        need([row['node'] for row in rows] == nodes, 'selected future original calls: '+op)
        required = (['NATIVE_CERTIFICATE_RETAINED', 'APPLY_BEFORE_RETURN', 'FUTURE_RETENTION_FORCED',
                     'FUTURE_RETENTION_PARENT_FORCED', 'FUTURE_RETENTION_BEFORE_RETURN'] if op != 'capture-proposal' else
                    ['PROMISE_FORCED', 'SOURCE_DIRECTORY_FORCED', 'BASIS_FORCED', 'GRANT_BEFORE_RETURN'])
        for row in rows: s.ordered(row['events'], required, 'selected future '+op)
    proposals = [row for row in calls if row['operation'] == 'proposal']
    need([row['node'] for row in proposals] == ['node-1', 'node-3'] and
         all(not any(event.startswith(('SELECTED_', 'INSTALL_')) for event in row['events']) for row in proposals),
         'selected future proposal changed native authority')
    return dict(status='PASS', originalFutureProofs=2, proposedGenerations=2,
                nonLongestProofs=True, durableInstallation=False, automaticDispatch=False, phase3Complete=False)


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    variants = [('bootstrap', 'retaining-genesis/node-1/'+u.FILE, 'admitted exact retaining-genesis: node-1'),
        ('certificate', 'certified/node-1/pending.accept', 'admitted exact certified: node-1'),
        ('applied', 'before-future/node-2/applied-end/ack.gsr', 'admitted exact before-future: node-2'),
        ('first-future', 'pending-future/node-1/'+u.FILE, 'admitted exact pending-future: node-1'),
        ('second-future', 'two-futures/node-2/'+u.FILE, 'admitted exact two-futures: node-2'),
        ('grant', 'proposal-sources/node-3/grants.gsr', 'grant basis binding'),
        ('source-owner', 'proposal-sources/node-2/'+s.FILE, 'admitted exact proposal-sources: node-2'),
        ('native-unchanged', 'after-proposal/node-1/'+u.FILE, 'admitted exact after-proposal: node-1'),
        ('proof-copy', 'proposed-node-3/source.gscp', 'selected future exact proposed generation: node-3'),
        ('selected-tail', 'proposed-node-1/owned-tail.gsr', 'selected future exact proposed generation: node-1'),
        ('selector', 'proposed-node-1/proposed-selector.gsr', 'selected future exact proposed generation: node-1'),
        ('force-order', 'calls.json', 'selected retention force order: selected future second-future')]
    for name, relative, reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-selected-future-negative-') as temp:
            copied = Path(temp)/'raw'; shutil.copytree(root, copied); path = copied/relative; original = path.read_bytes()
            if name == 'force-order':
                rows = json.loads(original)
                next(row for row in rows if row['operation'] == 'second-future')['events'].remove('FUTURE_RETENTION_FORCED')
                changed = json.dumps(rows).encode()
            elif name == 'grant':
                # A syntactically valid but non-native new ballot is not accepted.
                files = c.inventory(copied/'proposal-sources/node-3')
                old = c.journal(original, u.n.identity_root(files), 'node-3'); kind, raw, value = old[-2]
                value = dict(value, ballot=dict(value['ballot'], counter=4))
                changed = original.replace(raw, f.encode('records', kind, value), 1)
            else: changed = original[:-1]+bytes([original[-1]^1])
            need(changed != original, 'selected future ineffective mutation'); path.write_bytes(changed)
            try: validate(copied)
            except ValueError as error:
                expected = reason or 'admitted exact proposal-sources: node-3'
                need(str(error) == expected, f'selected future wrong rejection: {name}: {error}')
            else: raise ValueError('selected future accepted mutation: '+name)
            negatives.append(dict(case=name, status='REJECTED', reason=expected))
    return dict(result, negatives=negatives)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--negative', action='store_true')
    args = parser.parse_args(); print(json.dumps((qualify if args.negative else validate)(args.root), sort_keys=True))


if __name__ == '__main__': main()
