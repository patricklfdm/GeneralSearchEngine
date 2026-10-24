"""Original-byte replay of protected-context recovery after repeated process death.

Uses admitted originals, not producer receipts, to derive each interrupted store.
The case matrix covers process termination, not power loss or maximal capacity.
"""
import argparse
import json
import shutil
import tempfile
from pathlib import Path
from . import covered_context_evidence as q
from .retirement_source_process_evidence import same, read, trace

e, c, t, selection = q.e, q.c, q.t, q.b.selection
CUTS = q.CUTS


def original(root):
    paths = {'original-plan.gsbp', 'original-application.image', 'initial', 'profile.json',
             'entry.gsr', 'payload.bin', 'calls.json', 'observations.json', 'initial-votes',
             'contexts', 'original-retired', 'majority-reaccepted', 'advanced-selected',
             'original-proved', 'original-certified', 'typed-1-node-2', 'typed-1-node-3'}
    for counter, stages in ((1, ('prepared', 'selected', 'installed', 'settled')),
                            (3, ('prepared', 'selected', 'installed')), (4, ('prepared', 'selected'))):
        paths |= {f'round-{counter}-{stage}' for stage in stages}
    paths |= {'slot-1-'+stage for stage in ('accepted', 'proved', 'certified', 'applied', 'published', 'settled')}
    selection.layout(root, paths, 'context process originals')
    profile, names, majority, before, after, observed = q.prefix(root)
    same(profile, dict(size=3, backup=False, phase='CERTIFICATE'), 'context process original profile')
    q.calls(root, profile, names, majority, False); q.covered.observations(root, observed)
    for node in majority:
        _, members, packet = c.current(c.inventory(root/'slot-1-settled'/node))
        q.b.typed_image(root/('typed-1-'+node), members[packet['capsule']['application']+'.image'])
    return before['node-1'], after['node-1']


def force_trace(rows, expected, death, cut, returned):
    peak = None
    if returned:
        e.need(bool(rows), 'context process missing return'); result = rows[-1]; rows = rows[:-1]
        e.exact(result, 'status peakImages runtimeEnabled')
        e.need(type(result['peakImages']) is int and 0 < result['peakImages'] <= 7, 'context process result scope')
        same(result, dict(status='PASS', peakImages=result['peakImages'], runtimeEnabled=False), 'context process result scope')
        peak = result['peakImages']
    if death == 'kill':
        e.need(bool(rows) and rows[-1] == dict(event='AWAITING_KILL', cut=cut), 'context process kill handshake')
        rows = rows[:-1]
    for row in rows:
        e.exact(row, 'event'); e.need(type(row['event']) is str, 'context process event type')
    same(rows, [dict(event=v) for v in expected], 'context process exact force/death order')
    return peak


def validate(root):
    root = Path(root)
    selection.layout(root, {'reference', 'inputs.json', 'receipt.json'} |
                     {mode+'-'+cut for mode in ('halt', 'kill') for cut in CUTS}, 'context process')
    initial, installed = original(root/'reference')
    raw = t.plans.read(root/'inputs.json', e.MIB); inputs = e.parse(raw); e.exact(inputs, 'targets observations')
    plan = t.plans.decode(t.plans.read(root/'reference/original-plan.gsbp', 2*e.MIB),
                          t.plans.read(root/'reference/original-application.image', 64*e.MIB), details=True, size=3, source='EMPTY')
    paths = plan['plan']['descriptor']['paths']
    targets = [dict(node=paths[1+2*i]['path'], materialization=paths[2+2*i]['path']) for i in range(3)]
    same(inputs['targets'], targets, 'context process admitted paths')
    same(inputs['observations'], read(root/'reference/observations.json'), 'context process original observations')
    results = []; peaks = []
    for mode in ('halt', 'kill'):
        for cut in CUTS:
            name = mode+'-'+cut; case = root/name
            members = {'first', 'second', 'final'} | {label+ext for label in ('fault', 'recovery', 'resume') for ext in ('.stdout', '.stderr', '.exit.json')}
            if mode == 'kill': members |= {'lock.stdout', 'lock.stderr', 'lock.exit.json'}
            selection.layout(case, members, 'context process case')
            first, _ = q.transaction(initial, installed, cut)
            second = 'CONTEXT_SOURCE_PARENT_FORCED' if cut in CUTS[:2] else 'CONTEXT_SETTLEMENT_EMPTY_FORCED' if 'pending.context' in first else 'ACCEPT_ACTIVE_FORCED'
            state = initial
            for stage, label, point, death in (('first', 'fault', cut, mode), ('second', 'recovery', second, 'halt'), ('final', 'resume', None, 'none')):
                e.need(t.plans.read(case/(label+'.stderr'), e.MIB) == b'', 'context process stderr')
                state, events = q.transaction(state, installed, point)
                e.need(c.inventory(case/stage) == state, 'context process exact '+stage+' snapshot')
                e.need(sum(k.endswith('.image') for k in state) <= 7, 'context process image count')
                peak = force_trace(trace(case/(label+'.stdout')), events, death, point, stage == 'final')
                if peak is not None: peaks.append(peak)
                same(read(case/(label+'.exit.json')),
                     dict(exitCode=73 if death == 'halt' else 137 if death == 'kill' else 0, cut=point or 'none', mode=death),
                     'context process exact '+stage+' exit')
            e.need(state == installed, 'context process final installation')
            if mode == 'kill':
                e.need(t.plans.read(case/'lock.stderr', e.MIB) == b'', 'context process lock stderr')
                same(trace(case/'lock.stdout'), [dict(event='LOCK_HELD', path=targets[0]['node']+'/replica.lock')], 'context process lock probe')
                same(read(case/'lock.exit.json'), dict(exitCode=0), 'context process lock exit')
            results.append(dict(case=name, mode=mode, cut=cut, second=second, status='PASS', exitCodes=[73 if mode == 'halt' else 137, 73, 0]))
    same(read(root/'receipt.json'), dict(schema='gse-v53-covered-context-process-v1', status='PASS', cases=results,
         freshProcesses=66, lockProbes=11, inputsSha256=e.digest(raw), publicBootstrap=True, powerLoss=False, runtimeEnabled=False), 'context process exact receipt')
    return dict(status='PASS', cases=22, freshProcesses=66, lockProbes=11, peakImages=max(peaks),
                publicBootstrap=True, powerLoss=False, publicRuntime=False, maximalCapacity=False, originalFirst=True,
                independentImageSemantics=False)


VARIANTS = {
    'original-context': 'admitted exact contexts: node-1',
    'original-floor': 'admitted exact original-retired: node-1',
    'first-context': 'context process exact first snapshot',
    'second-vote': 'context process exact second snapshot',
    'final-source': 'context process exact final snapshot',
    'cleanup-force': 'context process exact force/death order',
    'old-ack': 'context process exact force/death order',
    'kill-handshake': 'context process kill handshake',
    'peak-images': 'context process result scope',
    'runtime': 'context process result scope',
    'exit-code': 'context process exact first exit',
    'exit-cut': 'context process exact second exit',
    'stderr': 'context process stderr',
    'lock-path': 'context process lock probe',
    'lock-exit': 'context process lock exit',
    'lock-stderr': 'context process lock stderr',
    'receipt': 'context process exact receipt',
    'admitted-path': 'context process admitted paths',
    'observations': 'context process original observations',
    'missing-case': 'context selection context process inventory',
}


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    for name, reason in VARIANTS.items():
        with tempfile.TemporaryDirectory(prefix='v53-context-process-negative-') as temp:
            moved = Path(temp)/'raw'; shutil.copytree(root, moved); case = moved/'halt-CONTEXT_SETTLEMENT_VALIDATED'
            if name == 'original-context': (moved/'reference/contexts/node-1/pending.context').write_bytes(b'changed')
            elif name == 'original-floor': (moved/'reference/original-retired/node-1/floor-copies/floor.gsr').write_bytes(b'changed')
            elif name == 'first-context': (case/'first/pending.context').unlink()
            elif name == 'second-vote': (case/'second/pending.accept').write_bytes(b'changed')
            elif name == 'final-source': next((case/'final/sources').glob('*/source.gscp')).unlink()
            elif name == 'missing-case': shutil.rmtree(case)
            elif name in ('stderr', 'lock-stderr'):
                if name == 'lock-stderr': case = moved/'kill-CONTEXT_SETTLEMENT_VALIDATED'
                (case/('lock.stderr' if name == 'lock-stderr' else 'fault.stderr')).write_bytes(b'error')
            elif name in ('receipt', 'admitted-path', 'observations', 'exit-code', 'exit-cut', 'lock-exit'):
                if name == 'lock-exit': case = moved/'kill-CONTEXT_SETTLEMENT_VALIDATED'
                path = moved/'receipt.json' if name == 'receipt' else moved/'inputs.json' if name in ('admitted-path', 'observations') else case/('lock.exit.json' if name == 'lock-exit' else 'recovery.exit.json' if name == 'exit-cut' else 'fault.exit.json')
                value = read(path)
                if name == 'receipt': value['publicBootstrap'] = 1
                elif name == 'admitted-path': value['targets'][0]['node'] += '/other'
                elif name == 'observations': value['observations'].pop()
                elif name == 'exit-cut': value['cut'] = 'none'
                else: value['exitCode'] = 2
                path.write_bytes(e.f.canonical(value))
            else:
                if name in ('kill-handshake', 'lock-path'): case = moved/'kill-CONTEXT_SETTLEMENT_VALIDATED'
                path = case/('lock.stdout' if name == 'lock-path' else 'resume.stdout' if name in ('peak-images', 'runtime') else 'fault.stdout')
                rows = trace(path)
                if name == 'cleanup-force': rows.remove(dict(event='CONTEXT_SETTLEMENT_VALIDATED'))
                elif name == 'old-ack': rows.append(dict(event='APPLY_BEFORE_RETURN'))
                elif name == 'kill-handshake': rows.pop()
                elif name == 'lock-path': rows[0]['path'] += '/other'
                elif name == 'peak-images': rows[-1]['peakImages'] = 8
                elif name == 'runtime': rows[-1]['runtimeEnabled'] = True
                path.write_bytes(b''.join(e.f.canonical(row)+b'\n' for row in rows))
            try: validate(moved)
            except ValueError as error: e.need(str(error) == reason, 'context process negative wrong reason: '+name+': '+str(error))
            else: raise ValueError('context process mutation accepted: '+name)
            negatives.append(dict(case=name, status='REJECTED', reason=reason))
    return dict(**result, negatives=negatives)


def portable(root):
    result = qualify(root)
    with tempfile.TemporaryDirectory(prefix='v53-context-process-portable-') as temp:
        target = Path(temp)/'evidence'; shutil.copytree(root, target)
        same(qualify(target), result, 'context process portable result')
    return dict(**result, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--qualify', action='store_true'); parser.add_argument('--portable', action='store_true'); args = parser.parse_args()
    print(json.dumps((portable if args.portable else qualify if args.qualify else validate)(args.root), sort_keys=True))
