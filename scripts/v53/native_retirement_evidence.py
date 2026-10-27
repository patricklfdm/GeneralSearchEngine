"""Reconstruct native cleanup from original bootstrap/votes, never final snapshots.

Only the stable-three carried process matrix is qualified here. Covered-prefix
cleanup, fencing and later publication are separate Java checks. No old voting
observation or checkpoint acknowledgement is created by retirement.
"""
import argparse
import json
import shutil
import struct
import tempfile
from pathlib import Path
from . import native_application_evidence as native
from . import distinct_minority_evidence as carried
from . import covered_staging_evidence as staging

p, e, c, f = native.p, native.e, native.c, native.f
need = e.need
POINTS = ('NATIVE_RETIREMENT_CERTIFICATE_RETAINED', 'REPLAY_APPLICATION_FINISHED',
          'SUPERSEDED_END_RETIREMENT_PREFIX_WRITTEN', 'SUPERSEDED_END_AUTHORITY_FORCED',
          'SUPERSEDED_END_FILE_DELETED', 'STAGED_RETIREMENT_BEFORE_RETURN')


def prepared(root):
    group = p.campaign(root, p.original(root, 3, False), 1)
    applied = {}
    for node in sorted(group):
        files, end, _, _ = native.certified_group(root, group, node)
        applied[node] = dict(files, **{'applied-end': None}, **{'applied-end/'+k: v for k, v in end.items()})
    p.match(root, 'old-applied', applied)
    for row in native.read_json(root/'calls.json'):
        if row['operation'] == 'old-apply':
            native.native_order(row['events'], 1)
    rows = native.read_json(root/'calls.json')
    need([v['node'] for v in rows if v['operation'] == 'old-apply'] == sorted(group),
         'native retirement original applied owners')
    installed, _ = carried.campaign(root, applied, 3, sorted(group), ('PROOF', 'CERTIFICATE'))
    return installed['node-1']


def authority(original):
    frames, _ = c.pending(original['pending.accept'], ('PROOF', 'CERTIFICATE'))
    old_selector = f.decode(frames['SELECTOR'], 'records', 'SELECTOR')
    current = f.decode(original['selector.gsr'], 'records', 'SELECTOR')
    owner = f.decode(original['node.gsr'], 'records', 'NODE')['identity']
    old = {k.removeprefix('generations/'+old_selector['generation']+'/'): v
           for k, v in original.items() if k.startswith('generations/'+old_selector['generation']+'/')}
    rows = c.journal(original['grants.gsr'], current['root'], owner['node'])
    promise, basis, selected = rows[-3:]
    need([r[0] for r in (promise, basis, selected)] == ['PROMISE', 'BASIS', 'SELECTED'],
         'native retirement original selection')
    value = dict(pending=e.digest(original['pending.accept']), oldGeneration=old_selector['digest'],
        selector=e.digest(original['selector.gsr']), generation=current['digest'], promise=e.digest(promise[1]),
        selection=e.digest(selected[1]), basis=e.digest(basis[1]),
        source=e.digest(original['sources/'+basis[2]['basisId']+'/source.gscp']),
        ancestry=e.digest(old.get('ancestry.gsr', b'')), coverage=e.digest(old.get(c.COVERAGE, b'')),
        parentSources=sorted([dict(basis=e.digest(raw), packet=e.digest(original['sources/'+obj['basisId']+'/source.gscp']))
            for kind, raw, obj in rows if kind == 'BASIS'], key=lambda v: v['basis']), floor='')
    end = {k.removeprefix('applied-end/'): v for k, v in original.items() if k.startswith('applied-end/')}
    body = f.canonical(dict(schema='gse-v53-applied-end-retirement/1.3', root=current['root'], node=owner['node'],
        storage=owner['storage'], selector=e.digest(frames['SELECTOR']), plan=e.digest(end['plan.json']),
        authority=value, files=[dict(path=k, type='file', **e.info(v)) for k, v in sorted(end.items())]))
    prefix = struct.pack('>4sHHII', b'GSAT', 1, 3, 0, len(body))
    return prefix+bytes.fromhex(e.digest(prefix+body))+body


def lines(path):
    raw = p.t.plans.read(path, 8*e.MIB).decode().splitlines()
    need(all(v.startswith(('EVENT ', 'CUT ', 'RESPONSE ')) for v in raw), 'native retirement worker log')
    return raw, [v[6:] for v in raw if v.startswith('EVENT ')]


def order(events, expected, active):
    staging.no_ack(events)
    need(staging.selected_events(events) == expected, 'native retirement exact force/delete order')
    positions = [i for i, name in enumerate(events) if name == 'NATIVE_RETIREMENT_CERTIFICATE_RETAINED']
    need(len(positions) == int(active), 'native retirement certificate retention count')
    if active:
        i = positions[0]; preceding = events[:i]
        need(len(preceding) >= 2 and preceding[-2:] == ['CERTIFICATE_ACTIVE_FORCED', 'CERTIFICATE_ACTIVE_PARENT_FORCED'],
             'native retirement original certificate force')
        need(not any(v.startswith(('STAGED_', 'SUPERSEDED_')) for v in preceding),
             'native retirement cleanup before certificate force')


def scratch(path, original):
    frames, _ = c.pending(original['pending.accept'], ('PROOF', 'CERTIFICATE'))
    owner = f.decode(original['node.gsr'], 'records', 'NODE')['identity']
    claim = f.canonical(dict(schema='gse-v53-application-replay/1.3', root=native.identity_root(original),
        node=owner['node'], storage=owner['storage'], selector=e.digest(frames['SELECTOR']),
        certificate=e.digest(frames['CERTIFICATE'])))
    image_path = path/'application-replay/work/input'
    p.typed_image(image_path, original['applied-end/application.image'])
    result = {'application-replay': None, 'application-replay/work': None,
              'application-replay/work/input': None, 'application-replay/claim.json': claim}
    result.update({'application-replay/work/input/'+k: v for k, v in c.inventory(image_path).items()})
    return result


def validate(root):
    root = Path(root)
    required = {'original-plan.gsbp', 'original-application.image', 'initial', 'calls.json',
                'entry-1.gsr', 'payload-1.bin', 'certified', 'old-applied'}
    required |= {'round-1-'+s for s in ('prepared', 'selected', 'installed', 'settled')}
    required |= {'slot-1-'+s for s in ('accepted', 'proved', 'certified')}
    required |= {'round-3-'+s for s in ('prepared', 'selected', 'installed')}
    required |= {mode+'-'+point for mode in ('halt', 'kill') for point in POINTS}
    p.selection.layout(root, required, 'native retirement process matrix')
    original = prepared(root); marker = authority(original); final = staging.without_staging(original)
    frames, _ = c.pending(original['pending.accept'], ('PROOF', 'CERTIFICATE'))
    response = 'RESPONSE '+e.digest(frames['CERTIFICATE'])+' 0'
    for mode in ('halt', 'kill'):
        for point in POINTS:
            path = root/(mode+'-'+point)
            p.selection.layout(path, {'worker.log', 'resume.log', 'interrupted', 'recovered', 'result.json'}, 'native retirement case')
            need(native.read_json(path/'result.json') == dict(mode=mode, cut=point, exit=23 if mode == 'halt' else 137, status='PASS'),
                 'native retirement exact process exit')
            raw, events = lines(path/'worker.log')
            need(raw and raw[-1] == 'CUT '+point and events[-1] == point and not any(v.startswith('RESPONSE ') for v in raw),
                 'native retirement interrupted before response')
            if point == POINTS[0]:
                interrupted, expected = dict(original), []
            else:
                interrupted, expected = staging.cleanup(original, marker, point)
            order(events, expected, True)
            actual = c.inventory(path/'interrupted')
            actual_scratch = {k: v for k, v in actual.items() if k == 'application-replay' or k.startswith('application-replay/')}
            need(actual_scratch == (scratch(path/'interrupted', original) if point == 'REPLAY_APPLICATION_FINISHED' else {}),
                 'native retirement exact replay scratch')
            need({k: v for k, v in actual.items() if k not in actual_scratch} == interrupted,
                 'native retirement exact interrupted files')
            recovered, expected = staging.cleanup(interrupted, marker)
            need(recovered == final and c.inventory(path/'recovered') == final, 'native retirement exact recovered files')
            raw, events = lines(path/'resume.log')
            order(events, expected, 'applied-end' in interrupted)
            need(raw and raw[-1] == response and not any(v.startswith(('RESPONSE ', 'CUT ')) for v in raw[:-1]),
                 'native retirement exact unchanged certificate/cut response')
    return dict(status='PASS', processCases=12, freshProcesses=24, liveLockProbes=6,
                callerHistoricalObservations=False, newAcknowledgement=False,
                selectedFutureTransfer=False, automaticDispatch=False, powerLoss=False)


VARIANTS = {
    'original-certificate': 'admitted exact slot-1-certified: node-1',
    'old-applied-end': 'admitted exact old-applied: node-1',
    'installed-choice': 'admitted exact round-3-installed: node-1',
    'early-response': 'native retirement interrupted before response',
    'missing-force': 'native retirement original certificate force',
    'forged-retirement': 'native retirement exact interrupted files',
    'deleted-original': 'native retirement exact interrupted files',
    'replay-claim': 'native retirement exact replay scratch',
    'recovered-original': 'native retirement exact recovered files',
    'old-ack': 'covered staging emitted old ACK',
    'recovery-force': 'native retirement exact force/delete order',
    'published-cut': 'native retirement exact unchanged certificate/cut response',
}


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    for name, reason in VARIANTS.items():
        with tempfile.TemporaryDirectory(prefix='v53-native-retirement-negative-') as temp:
            changed = Path(temp)/'raw'; shutil.copytree(root, changed)
            case = changed/'halt-SUPERSEDED_END_AUTHORITY_FORCED'
            if name == 'original-certificate':
                (changed/'slot-1-certified/node-1/pending.accept').write_bytes(b'corrupt')
            elif name == 'old-applied-end':
                (changed/'old-applied/node-1/applied-end/ack.gsr').write_bytes(b'corrupt')
            elif name == 'installed-choice':
                (changed/'round-3-installed/node-1/generations/a/owned-tail.gsr').write_bytes(b'corrupt')
            elif name == 'early-response':
                path = case/'worker.log'; path.write_bytes(path.read_bytes()+b'RESPONSE premature\n')
            elif name == 'missing-force':
                path = case/'worker.log'; path.write_text(path.read_text().replace('EVENT CERTIFICATE_ACTIVE_PARENT_FORCED\n', ''))
            elif name == 'forged-retirement':
                path = case/'interrupted/applied-end/retirement.gsat'; body = json.loads(path.read_bytes()[48:])
                body['authority']['generation'] = '0'*64; body = f.canonical(body)
                prefix = struct.pack('>4sHHII', b'GSAT', 1, 3, 0, len(body))
                path.write_bytes(prefix+bytes.fromhex(e.digest(prefix+body))+body)
            elif name == 'deleted-original':
                (case/'interrupted/pending.accept').unlink()
            elif name == 'replay-claim':
                (changed/'halt-REPLAY_APPLICATION_FINISHED/interrupted/application-replay/claim.json').write_bytes(b'{}')
            elif name == 'recovered-original':
                (case/'recovered/pending.accept').write_bytes(c.EMPTY)
            elif name == 'old-ack':
                path = case/'resume.log'; path.write_text('EVENT APPLY_ACK_DIRECTORY_FORCED\n'+path.read_text())
            elif name == 'recovery-force':
                path = case/'resume.log'; path.write_text(path.read_text().replace('EVENT SUPERSEDED_END_AUTHORITY_FORCED\n', ''))
            elif name == 'published-cut':
                path = case/'resume.log'; text = path.read_text(); path.write_text(text.rsplit(' 0\n', 1)[0]+' 1\n')
            try:
                validate(changed)
            except ValueError as error:
                need(str(error) == reason, 'native retirement negative wrong reason: '+name+': '+str(error))
            else:
                raise ValueError('native retirement accepted mutation: '+name)
            negatives.append(dict(case=name, status='REJECTED', reason=reason))
    return dict(result, negatives=negatives)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--qualify', action='store_true')
    args = parser.parse_args(); print(json.dumps((qualify if args.qualify else validate)(args.root), sort_keys=True))
