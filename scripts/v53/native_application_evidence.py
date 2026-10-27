"""Original-first replay for native certificate application.

Derive public bootstrap, all real phased records, publications and reclamation.
Process cases validate unchanged authority and exact applied-end prefixes; core
replay scratch semantics remain covered by the separate core/application gates.
No witness hash is treated as a new observation by the Java recovery path.
"""
import argparse
import base64
import copy
import json
import shutil
import struct
import tempfile
from pathlib import Path
from . import bootstrap_publication_evidence as p
from . import applied_end_evidence as end_model

e, c, f = p.e, p.c, p.e.f
need = e.need
POINTS = ('NATIVE_CERTIFICATE_RETAINED', 'REPLAY_APPLICATION_FINISHED',
          'APPLY_IMAGE_PREFIX_WRITTEN', 'APPLY_END_FORCED', 'APPLY_ACK_DIRECTORY_FORCED')


def read_json(path):
    return json.loads(p.t.plans.read(path, 8*e.MIB))


def native_order(events, count):
    names = {'NATIVE_CERTIFICATE_RETAINED', 'APPLICATION_AUTHORITY_VALIDATED',
             'APPLY_ACK_DIRECTORY_FORCED', 'APPLY_BEFORE_RETURN'}
    expected = ['NATIVE_CERTIFICATE_RETAINED', 'APPLICATION_AUTHORITY_VALIDATED',
                'APPLY_ACK_DIRECTORY_FORCED', 'APPLY_BEFORE_RETURN']*count
    need([v for v in events if v in names] == expected, 'native application exact force order')
    previous = -1
    for index, event in enumerate(events):
        if event == 'NATIVE_CERTIFICATE_RETAINED':
            segment = events[previous+1:index]
            need('CERTIFICATE_ACTIVE_FORCED' in segment and 'CERTIFICATE_ACTIVE_PARENT_FORCED' in segment
                 and segment.index('CERTIFICATE_ACTIVE_FORCED') < segment.index('CERTIFICATE_ACTIVE_PARENT_FORCED'),
                 'native application original certificate force')
            previous = index


def histories(root):
    names = {f'size-{n}-{s}' for n in (3, 4, 5) for s in ('empty', 'backup')}
    p.selection.layout(root, names, 'native application histories')
    for size in (3, 4, 5):
        for backup in (False, True):
            path = root/f"size-{size}-{'backup' if backup else 'empty'}"
            required = {'original-plan.gsbp', 'original-application.image', 'initial', 'calls.json', 'result.json'}
            required |= {f'round-{r}-{s}' for r in (1, 2) for s in ('prepared', 'selected', 'installed', 'settled')}
            required |= {f'slot-{r}-{s}' for r in (1, 2, 3) for s in ('accepted', 'proved', 'certified', 'applied', 'published', 'settled')}
            required |= {f'entry-{s}.gsr' for s in (1, 2, 3)} | {f'payload-{s}.bin' for s in (1, 2, 3)}
            required |= {f'typed-{s}-node-{n}' for s in (1, 2, 3) for n in range(1, size+1)}
            p.selection.layout(path, required, 'native application member')
            group = p.original(path, size, backup); observations = []
            group = p.campaign(path, group, 1)
            group, first = p.publication(path, group, 1, None, observations)
            group, _ = p.publication(path, group, 2, first, observations)
            group = p.campaign(path, group, 2)
            p.publication(path, group, 3, None, observations)
            p.calls(path, sorted(group))
            for row in read_json(path/'calls.json'):
                if row['operation'].startswith('apply-'):
                    native_order(row['events'], 2)
            for slot in (1, 2, 3):
                for node in group:
                    _, members, packet = c.current(c.inventory(path/f'slot-{slot}-settled'/node))
                    p.typed_image(path/f'typed-{slot}-{node}', members[packet['capsule']['application']+'.image'])
            need(read_json(path/'result.json') == dict(status='PASS', nativeApplication=True, publications=3),
                 'native application history result')


def certified(root, size=3, backup=False, node='node-1'):
    """Derive the first certificate and a named owner's end from original phases."""
    group = p.campaign(root, p.original(root, size, backup), 1)
    need(node in group, 'native application requested original owner')
    owner = node
    _, members, packet = c.current(group['node-1']); cap = packet['capsule']; r = cap['root']
    selected = f.decode(members['selected.gsr'], 'records', 'SELECTED')
    entry = f.encode('records', 'ENTRY', dict(root=r, authority=selected['view'], index=1,
        previous=cap['cut']['entry'], origin=selected['ballot'], kind='BARRIER', payload=e.digest(b'')))
    need(p.t.plans.read(root/'entry-1.gsr', 8192) == entry and p.t.plans.read(root/'payload-1.bin', e.MIB) == b'',
         'native application original requested entry')
    accept = f.encode('records', 'ACCEPT', dict(root=r, authority=selected['view'], ballot=selected['ballot'], index=1, entry=e.digest(entry)))
    ids = {n: f.decode(files['node.gsr'], 'records', 'NODE')['identity']['storage'] for n, files in group.items()}
    def witnesses(raw, phase):
        return [dict(voter=n, incarnation=ids[n], receipt=e.digest(f.canonical(dict(root=r, voter=n,
            incarnation=ids[n], phase=phase, record=e.digest(raw))))) for n in sorted(group)]
    proof = f.encode('records', 'PROOF', dict(f.decode(accept, 'records', 'ACCEPT'), accepts=witnesses(accept, 'ACCEPT')))
    certificate = f.encode('records', 'CERTIFICATE', dict(f.decode(proof, 'records', 'PROOF'), proofs=witnesses(proof, 'PROOF')))
    phases = {}
    for label, extra in [('accepted', []), ('proved', [proof]), ('certified', [proof, certificate])]:
        phases = {}
        for node, files in group.items():
            _, local, _ = c.current(files)
            vote = e.container([files['selector.gsr'], local['promise.gsr'], local['selected.gsr'], entry, accept], b'')+b''.join(extra)
            vote = vote[:8]+struct.pack('>I', len(vote))+vote[12:]
            phases[node] = dict(files, **{'pending.accept': vote})
        p.match(root, 'slot-1-'+label, phases)
    p.match(root, 'certified', phases)
    rows = read_json(root/'calls.json')
    for label, phase in [('accept', 'ACCEPT'), ('proof', 'PROOF'), ('certificate', 'CERTIFICATE')]:
        actual = [row for row in rows if row['operation'] == label+'-1']
        need([row['node'] for row in actual] == sorted(group), 'native application actual original phased owners')
        for row in actual:
            required = [phase+'_CANDIDATE_FORCED', phase+'_PARENT_FORCED', phase+'_BEFORE_RETURN']
            expected = required+([phase+'_BEFORE_RETURN'] if label == 'accept' else [])
            need([v for v in row['events'] if v in required] == expected, 'native application original phase force order')
    after = copy.deepcopy(f.decode(packet['objects'][cap['catalog']], 'records', 'CATALOG'))
    after['cut'] = dict(cap['cut'], index=1, entry=e.digest(entry))
    catalog = f.encode('records', 'CATALOG', after)
    statement = f.encode('records', 'CHECKPOINT', dict(root=r, scope='RANGE', start=cap['cut'], end=after['cut'],
        catalogBefore=cap['catalog'], catalogAfter=e.digest(catalog), applicationBefore=cap['application'], applicationAfter=cap['application']))
    ack = f.encode('records', 'CHECKPOINT_ACK', dict(root=r, voter=owner, incarnation=ids[owner], cut=after['cut'], statement=e.digest(statement)))
    end = dict(zip(('selector.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr', 'application.image', 'ack.gsr'),
        (group[owner]['selector.gsr'], certificate, catalog, statement, members[cap['application']+'.image'], ack)))
    end['plan.json'] = f.canonical(dict(schema='gse-v53-applied-end/1.3', root=r, node=owner,
        files=[dict(path=k, **e.info(v)) for k, v in sorted(end.items())]))
    return phases[owner], end, cap['cut'], after['cut']


def lines(path):
    raw = p.t.plans.read(path, 8*e.MIB).decode().splitlines()
    need(all(line.startswith(('EVENT ', 'CUT ', 'RESULT ')) for line in raw), 'native application worker log')
    return raw, [line[6:] for line in raw if line.startswith('EVENT ')]


def processes(root):
    required = {'original-plan.gsbp', 'original-application.image', 'initial', 'calls.json', 'entry-1.gsr', 'payload-1.bin', 'certified'}
    required |= {'round-1-'+s for s in ('prepared', 'selected', 'installed', 'settled')}
    required |= {'slot-1-'+s for s in ('accepted', 'proved', 'certified')}
    required |= {mode+'-'+point for mode in ('halt', 'kill') for point in POINTS}
    p.selection.layout(root, required, 'native application process matrix')
    original, end, published, applied = certified(root)
    for mode in ('halt', 'kill'):
        for point in POINTS:
            path = root/(mode+'-'+point)
            p.selection.layout(path, {'worker.log', 'resume.log', 'interrupted', 'recovered', 'result.json'}, 'native application process')
            need(read_json(path/'result.json') == dict(mode=mode, cut=point, exit=23 if mode == 'halt' else 137),
                 'native application process exit')
            raw, events = lines(path/'worker.log')
            need(raw[-1] == 'CUT '+point and events[-1] == point and not any(v.startswith('RESULT ') for v in raw),
                 'native application interrupted before response')
            if point.startswith('APPLY_'):
                partial, exists, expected = end_model.simulate(end, {}, False, point)
                need([v for v in events if v.startswith('APPLY_')] == [v['event'] for v in expected],
                     'native application interrupted force order')
            else:
                partial, exists = {}, False
            interrupted = c.inventory(path/'interrupted')
            need({k: v for k, v in interrupted.items() if not k.startswith('application-replay') and not k.startswith('applied-end')} == original,
                 'native application original authority preservation')
            need({k.removeprefix('applied-end/'): v for k, v in interrupted.items() if k.startswith('applied-end/')} == partial
                 and ('applied-end' in interrupted) == exists, 'native application exact interrupted end')
            scratch = {k: v for k, v in interrupted.items() if k.startswith('application-replay')}
            if point == 'REPLAY_APPLICATION_FINISHED':
                identity = f.decode(original['node.gsr'], 'records', 'NODE')['identity']
                claim = f.canonical(dict(schema='gse-v53-application-replay/1.3', root=identity_root(original),
                    node=identity['node'], storage=identity['storage'], selector=e.digest(original['selector.gsr']),
                    certificate=e.digest(end['certificate.gsr'])))
                p.typed_image(path/'interrupted/application-replay/work/input', end['application.image'])
                expected_scratch = {'application-replay': None, 'application-replay/work': None,
                    'application-replay/work/input': None, 'application-replay/claim.json': claim}
                expected_scratch.update({'application-replay/work/input/'+k: v for k, v in c.inventory(path/'interrupted/application-replay/work/input').items()})
                need(scratch == expected_scratch, 'native application exact original replay claim')
            else:
                need(not scratch, 'native application unexpected replay scratch')
            expected_final = dict(original, **{'applied-end': None}, **{'applied-end/'+k: v for k, v in end.items()})
            need(c.inventory(path/'recovered') == expected_final, 'native application exact recovered files')
            resumed, recovered_events = lines(path/'resume.log'); native_order(recovered_events, 2)
            need(not any(v.startswith(('CUT ', 'RESULT ')) for v in resumed[:-1]) and resumed[-1].startswith('RESULT '),
                 'native application recovery result position')
            actual = json.loads(resumed[-1][7:])
            need(actual == dict(certificate=e.digest(end['certificate.gsr']), catalog=e.digest(end['catalog.gsr']),
                 application=e.digest(end['application.image']), published=published, applied=applied,
                 ack=base64.b64encode(end['ack.gsr']).decode()), 'native application exact recovered result')
            _, _, first = end_model.simulate(end, partial, exists)
            _, _, second = end_model.simulate(end, end, True)
            need([v for v in recovered_events if v.startswith('APPLY_')] == [v['event'] for v in first+second],
                 'native application duplicate force order')


def identity_root(original):
    return f.decode(original['selector.gsr'], 'records', 'SELECTOR')['root']


def validate(root):
    root = Path(root); p.selection.layout(root, {'histories', 'process'}, 'native application root')
    histories(root/'histories'); processes(root/'process')
    return dict(status='PASS', histories=6, nodePublications=72, processCases=10, freshJvms=20,
                callerPhasedObservations=False, automaticDispatch=False, futureRetention=False,
                independentReplayScratchSemantics=False, powerLoss=False)


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    variants = {
        'certificate': 'admitted exact slot-2-certified: node-1',
        'applied-end': 'admitted exact slot-2-applied: node-2',
        'native-force': 'native application original certificate force',
        'early-reply': 'native application interrupted before response',
        'interrupted-end': 'native application exact interrupted end',
        'recovered-selector': 'native application exact recovered files',
        'recovery-force': 'native application exact force order',
        'published-cut': 'native application exact recovered result',
    }
    for name, reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-native-application-negative-') as temp:
            target = Path(temp)/'raw'; shutil.copytree(root, target)
            history = target/'histories/size-3-empty'; process = target/'process/halt-APPLY_END_FORCED'
            if name == 'certificate':
                (history/'slot-2-certified/node-1/pending.accept').write_bytes(b'corrupt')
            elif name == 'applied-end':
                (history/'slot-2-applied/node-2/applied-end/ack.gsr').write_bytes(b'corrupt')
            elif name == 'native-force':
                path = history/'calls.json'; rows = read_json(path)
                row = next(v for v in rows if v['operation'] == 'apply-1')
                row['events'] = [v for v in row['events'] if v != 'CERTIFICATE_ACTIVE_PARENT_FORCED']
                path.write_bytes(f.canonical(rows))
            elif name == 'early-reply':
                path = process/'worker.log'; path.write_bytes(path.read_bytes()+b'RESULT {}\n')
            elif name == 'interrupted-end':
                (process/'interrupted/applied-end/ack.gsr').write_bytes((process/'recovered/applied-end/ack.gsr').read_bytes())
            elif name == 'recovered-selector':
                (process/'recovered/selector.gsr').write_bytes(b'wrong')
            elif name == 'recovery-force':
                path = process/'resume.log'; path.write_bytes(path.read_bytes().replace(b'EVENT APPLY_ACK_DIRECTORY_FORCED\n', b''))
            else:
                path = process/'resume.log'; rows = path.read_text().splitlines(); value = json.loads(rows[-1][7:]); value['published'] = value['applied']
                rows[-1] = 'RESULT '+json.dumps(value); path.write_text('\n'.join(rows)+'\n')
            try:
                validate(target)
            except ValueError as error:
                need(str(error) == reason, 'native application wrong negative: '+name+': '+str(error))
                negatives.append(dict(case=name, status='REJECT', reason=reason))
            else:
                raise ValueError('native application mutation accepted: '+name)
    return dict(**result, negatives=negatives)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--qualify', action='store_true')
    args = parser.parse_args(); print(json.dumps((qualify if args.qualify else validate)(args.root), sort_keys=True))
