"""Original-first replay of source reclamation authorized by a forced successor.

The admitted mixed chain supplies the original bytes. This is repeated exception
recovery qualification, not a fresh-process or power-loss result.
"""
import argparse
import json
import shutil
import tempfile
from pathlib import Path
from . import covered_context_mixed_evidence as m
from . import source_release_evidence as release
from .retirement_source_process_evidence import same
q, e, c, b = m.q, m.e, m.c, m.b
CUTS = ('SOURCE_RETIREMENT_FORCED', 'SOURCE_RETIREMENT_JOURNAL_PRUNED',
        'SOURCE_RETIREMENT_FILE_DELETED', 'SOURCE_RETIREMENT_DIRECTORY_DELETED')
REASONS = {'plan-missing': 'source retirement loses unresolved ownership',
           'resumed-missing': 'source retirement unresolved ownership',
           'plan-corrupt': 'pending payload hash', 'resumed-corrupt': 'pending payload hash'}


def state(files):
    return {p: dict(directory=True) if raw is None else release.r.entry(raw) for p, raw in files.items()}


def plan(root):
    ref = Path(root)/'reference'
    result = m.clean(ref)
    same((result['size'], result['backup']), (4, False), 'successor recovery reference profile')
    files = c.inventory(ref/'headroom-floors/node-1')
    old = c.current(c.inventory(ref/'mixed-reaccepted/node-1'))[1]
    basis_raw = old['basis.gsr']; basis = e.f.decode(basis_raw, 'records', 'BASIS')
    identifier = basis['basisId']; prefix = 'sources/'+identifier
    packet = e.p.decode(files[prefix+'/source.gscp']); e.p.bind(packet, basis_raw)
    rows = c.journal(files['grants.gsr'], basis['root'], 'node-1')
    promise = [raw for kind, raw, value in rows if kind == 'PROMISE' and value.get('basisId') == identifier]
    e.need(len(promise) == 1 and any(raw == basis_raw for _, raw, _ in rows), 'successor original source journal')
    record = e.f.encode('records', 'RETIREMENT', dict(root=basis['root'], node='node-1',
        floor=e.digest(files['floor-copies/floor.gsr']), selector=e.digest(files['selector.gsr']),
        files=[dict(path=p, size=len(raw), sha256=e.digest(raw)) for p, raw in sorted(files.items()) if p.startswith(prefix+'/')]))
    authority = record+promise[0]+basis_raw+packet['capsuleBytes']
    final = m.mixed.retire_source(files, basis); compact = final['grants.gsr']
    return files, state(files), authority, compact, identifier, state(final)


def advance(initial, authority, compact, identifier, cut=None):
    steps = release.transaction(initial, authority, compact, identifier)
    e.need(bool(steps), 'successor recovery missing transaction')
    if cut is not None:
        matches = [i for i, (event, _) in enumerate(steps) if event == cut]
        e.need(bool(matches), 'successor recovery missing cut'); steps = steps[:matches[0]+1]
    return steps[-1][1], [*q.covered.OPEN, *q.covered.SEAL, *[event for event, _ in steps]]


def validate(root):
    root = Path(root)
    b.selection.layout(root, {'reference', 'receipt.json', *CUTS, *REASONS}, 'source successor recovery')
    files, initial, authority, compact, identifier, final = plan(root)
    rows = []
    for cut in CUTS:
        case = root/cut
        b.selection.layout(case, {'first', 'second', 'final', 'events.json'}, 'source successor crash')
        current = initial; traces = []
        for stage, point in [('first', cut), ('second', 'SOURCE_RETIREMENT_JOURNAL_PRUNED'), ('final', None)]:
            current, events = advance(current, authority, compact, identifier, point)
            same(release.s.inventory(case/stage), current, 'successor recovery exact '+stage)
            traces.append(events)
        same(current, final, 'successor recovery final authority')
        same(q.read(case/'events.json'), traces, 'successor recovery exact force order')
        rows.append(dict(case=cut, status='PASS'))
    for name, reason in REASONS.items():
        case = root/name
        b.selection.layout(case, {'invalid', 'refused', 'restored'}, 'source successor refusal')
        invalid = dict(initial)
        if name.startswith('resumed-'):
            invalid, _ = advance(initial, authority, compact, identifier, 'SOURCE_RETIREMENT_JOURNAL_PRUNED')
        damaged = c.EMPTY if name.endswith('-missing') else files['pending.accept'][:-1]+bytes([files['pending.accept'][-1]^1])
        invalid['pending.accept'] = release.r.entry(damaged)
        for stage in ('invalid', 'refused'):
            same(release.s.inventory(case/stage), invalid, 'successor recovery exact '+stage)
        same(release.s.inventory(case/'restored'), final, 'successor recovery exact restored')
    # Producer order is explicit; a boolean cannot masquerade as an integer count.
    for resumed in (False, True):
        for damage in ('missing', 'corrupt'):
            name = ('resumed-' if resumed else 'plan-')+damage
            rows.append(dict(case=name, status='PASS', reason=REASONS[name]))
    same(q.read(root/'receipt.json'), dict(schema='gse-v53-source-successor-recovery-v1', status='PASS', cases=rows,
        interruptions=8, repeatedRefusals=8, publicBootstrap=True, freshProcesses=False, runtimeEnabled=False), 'successor recovery exact receipt')
    return dict(status='PASS', interruptions=8, repeatedRefusals=8, publicBootstrap=True,
                freshProcesses=False, runtimeEnabled=False, powerLoss=False, originalFirst=True)


VARIANTS = {'reference-vote':'admitted exact headroom-floors: node-1',
            'first-vote':'successor recovery exact first', 'second-journal':'successor recovery exact second',
            'final-source':'successor recovery exact final', 'early-delete':'successor recovery exact first',
            'force':'successor recovery exact force order', 'invalid-vote':'successor recovery exact invalid',
            'refusal-write':'successor recovery exact refused', 'restored-vote':'successor recovery exact restored',
            'receipt':'successor recovery exact receipt'}


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    for name, reason in VARIANTS.items():
        with tempfile.TemporaryDirectory(prefix='v53-successor-recovery-negative-') as tmp:
            moved = Path(tmp)/'raw'; shutil.copytree(root, moved); case = moved/CUTS[0]
            if name == 'reference-vote': (moved/'reference/headroom-floors/node-1/pending.accept').write_bytes(c.EMPTY)
            elif name == 'first-vote': (case/'first/pending.accept').write_bytes(c.EMPTY)
            elif name == 'second-journal': (case/'second/grants.gsr').write_bytes(b'')
            elif name == 'final-source': (case/'final/extra').write_bytes(b'undeleted')
            elif name == 'early-delete': next((case/'first/sources').glob('*/source.gscp')).unlink()
            elif name == 'force':
                p = case/'events.json'; value = q.read(p); value[0].remove('SOURCE_RETIREMENT_FORCED'); p.write_bytes(e.f.canonical(value))
            elif name == 'receipt':
                p = moved/'receipt.json'; value = q.read(p); value['publicBootstrap'] = 1; p.write_bytes(e.f.canonical(value))
            else:
                stage = {'invalid-vote':'invalid', 'refusal-write':'refused', 'restored-vote':'restored'}[name]
                (moved/'resumed-corrupt'/stage/'pending.accept').write_bytes(c.EMPTY)
            try: validate(moved)
            except ValueError as error: e.need(str(error) == reason, 'successor wrong negative: '+name+': '+str(error))
            else: raise ValueError('successor mutation accepted: '+name)
            negatives.append(dict(case=name, status='REJECTED', reason=reason))
    with tempfile.TemporaryDirectory(prefix='v53-successor-recovery-portable-') as tmp:
        moved = Path(tmp)/'raw'; shutil.copytree(root, moved); same(validate(moved), result, 'successor portable replay')
    return dict(**result, negatives=negatives, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); args = parser.parse_args()
    print(json.dumps(qualify(args.root), sort_keys=True))
