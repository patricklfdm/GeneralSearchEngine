"""Original-first replay of context-backed predecessor source retirement.

Actual exception cuts are checked against retained byte/force prefixes. This does
not claim process death, next-campaign progress or independent remote ownership.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import context_retirement_evidence as original
from . import journal_context_evidence as owner
from . import source_release_evidence as release

e = owner.e
CUTS = tuple(v for v in release.CUTS if '@' not in v)


def load(path, limit=65536):
    e.need(path.is_file() and not path.is_symlink() and path.stat().st_size <= limit, 'context source metadata type/capacity')
    return e.parse(path.read_bytes())


def state(path):
    files, dirs = owner.read_snapshot(path)
    return {**{p: release.r.entry(raw) for p, raw in files.items()}, **{p: dict(directory=True) for p in dirs}}


def plan(root):
    original.validate(root/'original-retirement')
    files, dirs = owner.read_snapshot(root/'original-retirement/retired')
    segments, _, binding = e.decode(files[owner.ACTIVE])
    rows = owner.journal(files['grants.gsr'], binding['root'], binding['node'])
    e.need([kind for kind, _, _ in rows] == ['PROMISE', 'BASIS', 'SELECTED']*2, 'context source original groups')
    old, backing = rows[1][2]['basisId'], rows[4][2]['basisId']
    e.need(old != backing and segments[2] == rows[3][1] and segments[3] == rows[4][1], 'context source separate backing')
    prefix = 'sources/'+old+'/'
    packet = e.p.decode(files[prefix+'source.gscp'])
    record = e.f.encode('records', 'RETIREMENT', dict(root=binding['root'], node=binding['node'],
        floor=e.digest(files['floor-copies/floor.gsr']), selector=e.digest(files['selector.gsr']),
        files=[dict(path=p, size=len(raw), sha256=e.digest(raw)) for p, raw in sorted(files.items()) if p.startswith(prefix)]))
    authority = record+rows[0][1]+rows[1][1]+packet['capsuleBytes']
    compact = b''.join(raw for _, raw, _ in rows[3:])
    initial = {**{p: release.r.entry(raw) for p, raw in files.items()}, **{p: dict(directory=True) for p in dirs}}
    return initial, authority, compact, old, backing


def selected_events(values):
    e.need(type(values) is list and len(values) <= 2048 and all(type(v) is str for v in values), 'context source events shape')
    e.need(not any(v in owner.ACKS or v.startswith('APPLY_ACK_') or v == 'APPLY_BEFORE_RETURN' for v in values),
           'context source old acknowledgement')
    return [v for v in values if v.startswith(('SOURCE_RETIREMENT_', 'JOURNAL_ROTATION_'))]


def validate(root):
    root = Path(root)
    e.need(root.is_dir() and not root.is_symlink(), 'context source root')
    receipt = load(root/'receipt.json')
    matrix = receipt.get('schema') == 'gse-v53-context-source-release-cuts-v1'
    required = {'original-retirement', 'receipt.json'} | (set(CUTS) if matrix else {'released', 'reopened', 'events.json'})
    e.need({p.name for p in root.iterdir()} == required, 'context source evidence inventory')
    initial, authority, compact, old, backing = plan(root)
    steps = release.transaction(initial, authority, compact, old); final = steps[-1][1]
    if matrix:
        expected = dict(schema='gse-v53-context-source-release-cuts-v1', status='PASS', cuts=list(CUTS),
                        interruptions='injected-IOException', freshProcesses=False, runtimeEnabled=False)
        for cut in CUTS:
            case = root/cut
            e.need(case.is_dir() and not case.is_symlink() and {p.name for p in case.iterdir()} ==
                   {'crash', 'recovery-crash', 'final', 'events.json'}, 'context source cut inventory')
            position = next(i for i, (name, _) in enumerate(steps) if name == cut)
            crash = steps[position][1]
            e.need(state(case/'crash') == crash, 'context source exact interrupted prefix')
            e.need(state(case/'recovery-crash') == crash, 'context source second interruption changed authority')
            e.need(state(case/'final') == final, 'context source exact resumed deletion')
            events = load(case/'events.json'); e.exact(events, 'first recovery resume')
            e.need(selected_events(events['first']) == [name for name, _ in steps[:position+1]], 'context source first force order')
            e.need(selected_events(events['recovery']) == [] and events['recovery'][-1] == 'CONTEXT_SOURCE_PARENT_FORCED',
                   'context source second force order')
            again = release.transaction(crash, authority, compact, old)
            e.need(selected_events(events['resume']) == [name for name, _ in again], 'context source resume force order')
    else:
        expected = dict(schema='gse-v53-context-source-release-v1', status='PASS', predecessor=old, backing=backing,
                        beforeImages=6, afterImages=5, freshProcesses=False, runtimeEnabled=False)
        e.need(state(root/'released') == final, 'context source exact deletion')
        e.need(state(root/'reopened') == final, 'context source reopen changed authority')
        e.need(selected_events(load(root/'events.json')) == [name for name, _ in steps], 'context source clean force order')
    e.need(e.f.canonical(receipt) == e.f.canonical(expected), 'context source receipt scope')
    return dict(status='PASS', cases=len(CUTS) if matrix else 1, originalFirst=True, predecessor=old, backing=backing,
                freshProcesses=False, runtimeEnabled=False, imageSemanticClaim=False, fullOwnerProgress=False)


def qualify(root):
    root = Path(root); result = validate(root); matrix = result['cases'] > 1
    cases = {'bad-original': 'context checksum', 'lost-context': 'context source exact resumed deletion' if matrix else 'context source exact deletion',
        'lost-vote': 'context source exact resumed deletion' if matrix else 'context source exact deletion',
        'lost-backing': 'context source exact resumed deletion' if matrix else 'context source exact deletion',
        'wrong-journal': 'context source exact resumed deletion' if matrix else 'context source exact deletion',
        'kept-source': 'context source exact resumed deletion' if matrix else 'context source exact deletion',
        'changed-recovery': 'context source second interruption changed authority' if matrix else 'context source reopen changed authority',
        'force-order': 'context source first force order' if matrix else 'context source clean force order',
        'old-ack': 'context source old acknowledgement', 'false-process': 'context source receipt scope',
        'linked-context': 'owner context linked/nonregular member'}
    if matrix: cases['wrong-prefix'] = 'context source exact interrupted prefix'
    negatives = []
    for name, reason in cases.items():
        with tempfile.TemporaryDirectory(prefix='v53-context-source-negative-') as tmp:
            moved = Path(tmp)/'evidence'; shutil.copytree(root, moved)
            case = moved/CUTS[0] if matrix else moved
            final = case/'final' if matrix else case/'released'
            if name == 'bad-original':
                path=moved/'original-retirement/initial/pending.context'; raw=path.read_bytes(); path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name in ('lost-context', 'lost-vote', 'wrong-journal'):
                path=final/({'lost-context': 'pending.context', 'lost-vote': 'pending.accept', 'wrong-journal': 'grants.gsr'}[name])
                path.write_bytes(b'changed')
            elif name == 'lost-backing': (final/'sources'/result['backing']/'source.gscp').unlink()
            elif name == 'kept-source': shutil.copytree(moved/'original-retirement/retired/sources'/result['predecessor'], final/'sources'/result['predecessor'])
            elif name in ('changed-recovery', 'wrong-prefix'):
                snapshot = case/('crash' if name == 'wrong-prefix' else 'recovery-crash') if matrix else case/'reopened'
                (snapshot/'pending.accept').write_bytes(b'changed')
            elif name in ('force-order', 'old-ack'):
                path=case/'events.json'; events=load(path); values=events['first'] if matrix else events
                if name == 'force-order': values.remove('SOURCE_RETIREMENT_CREATED')
                else: values.append('ACCEPT_BEFORE_RETURN')
                path.write_bytes(e.f.canonical(events))
            elif name == 'false-process':
                path=moved/'receipt.json'; value=load(path); value['freshProcesses']=True; path.write_bytes(e.f.canonical(value))
            else:
                path=final/'pending.context'; path.unlink(); path.symlink_to((root/'original-retirement/retired/pending.context').resolve())
            try: validate(moved)
            except ValueError as error:
                e.need(str(error) == reason, 'wrong context source negative: '+name+': '+str(error))
                negatives.append(dict(case=name, reason=reason))
            else: raise ValueError('accepted context source mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-context-source-portable-') as tmp:
        moved=Path(tmp)/'evidence'; shutil.copytree(root,moved); e.need(validate(moved)==result, 'context source portable replay')
    return dict(result, negatives=negatives, portableReplay='PASS')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('root'); args=parser.parse_args()
    print(json.dumps(qualify(args.root),sort_keys=True))
