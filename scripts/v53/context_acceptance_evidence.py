"""Exact context-to-current voting transition, floor cleanup and repeated exceptions.

Original generation/source retirement is independently validated first. This
checks bytes and force events, not remote/network ownership or power-loss.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import context_source_release_evidence as source
from . import floor_release_evidence as floor
from . import pending_accept_evidence as accept

e, owner = source.e, source.owner
CUTS = ('CONTEXT_ACCEPT_VALIDATED', 'ACCEPT_CANDIDATE_CREATED', 'ACCEPT_PREFIX_WRITTEN',
        'ACCEPT_CANDIDATE_WRITTEN', 'ACCEPT_CANDIDATE_FORCED', 'ACCEPT_CANDIDATE_PARENT_FORCED',
        'ACCEPT_RENAMED', 'ACCEPT_PARENT_FORCED', 'ACCEPT_ACTIVE_FORCED', 'ACCEPT_ACTIVE_PARENT_FORCED',
        'CONTEXT_ACCEPT_SUCCESSOR_FORCED', 'CONTEXT_REDUNDANT_DELETED', 'CONTEXT_REDUNDANT_PARENT_FORCED',
        'CONTEXT_ACCEPT_CLEARED', *floor.CUTS[:11], 'CONTEXT_ACCEPT_BEFORE_RETURN')


def plan(root):
    original = root/'original-source-release'
    source.validate(original)
    files, dirs = owner.read_snapshot(original/'reopened')
    prefix, installed, packet = e.current(files)
    old, values = e.votes(files['pending.accept'], packet['capsule']['cut'])
    promise = e.f.decode(installed['promise.gsr'], 'records', 'PROMISE')
    selected = e.f.decode(installed['selected.gsr'], 'records', 'SELECTED')
    e.need(promise['ballot']['counter'] == 21 and values['ENTRY']['origin']['counter'] == 20
           and selected['nextEntry'] == e.digest(old['ENTRY']), 'context acceptance exact carried origin')
    new_accept = e.f.encode('records', 'ACCEPT', dict(values['ACCEPT'], ballot=promise['ballot']))
    vote = e.container([files['selector.gsr'], installed['promise.gsr'], installed['selected.gsr'], old['ENTRY'], new_accept], old['PAYLOAD'])
    record = e.f.encode('records', 'RETIREMENT', dict(root=promise['root'], node='node-1',
        floor=e.digest(files['floor-copies/floor.gsr']), selector=e.digest(files['selector.gsr']),
        files=[dict(path=n, size=len(raw), sha256=e.digest(raw)) for n, raw in sorted(files.items()) if n.startswith('floor-copies/')]))
    state = {**{n: source.release.r.entry(raw) for n, raw in files.items()}, **{n: dict(directory=True) for n in dirs}}
    return state, vote, record


def transition(initial, vote, release_record, *, acknowledge):
    state = dict(initial); steps = []
    def event(name): steps.append((name, dict(state)))
    if owner.ACTIVE in state:
        event('CONTEXT_ACCEPT_VALIDATED')
        if state[accept.ACTIVE] != accept.info(vote) or accept.NEXT in state:
            if accept.NEXT not in state: state[accept.NEXT] = accept.info(b''); event('ACCEPT_CANDIDATE_CREATED')
            offset = state[accept.NEXT]['bytes']; middle = offset+(len(vote)-offset)//2
            state[accept.NEXT] = accept.info(vote[:middle]); event('ACCEPT_PREFIX_WRITTEN')
            state[accept.NEXT] = accept.info(vote); event('ACCEPT_CANDIDATE_WRITTEN'); event('ACCEPT_CANDIDATE_FORCED'); event('ACCEPT_CANDIDATE_PARENT_FORCED')
            state[accept.ACTIVE] = state.pop(accept.NEXT); event('ACCEPT_RENAMED'); event('ACCEPT_PARENT_FORCED')
        event('ACCEPT_ACTIVE_FORCED'); event('ACCEPT_ACTIVE_PARENT_FORCED'); event('CONTEXT_ACCEPT_SUCCESSOR_FORCED')
        state.pop(owner.ACTIVE); event('CONTEXT_REDUNDANT_DELETED'); event('CONTEXT_REDUNDANT_PARENT_FORCED'); event('CONTEXT_ACCEPT_CLEARED')
        released = floor.transaction(state, release_record); steps += released
        if released: state = released[-1][1]
        if acknowledge: event('CONTEXT_ACCEPT_BEFORE_RETURN')
    else:
        released = floor.transaction(state, release_record); steps += released
        if released: state = released[-1][1]
        if acknowledge: event('ACCEPT_BEFORE_RETURN')
    return steps


def selected(values):
    e.need(type(values) is list and len(values) <= 4096 and all(type(v) is str for v in values), 'context acceptance events shape')
    forbidden = owner.ACKS-{'ACCEPT_BEFORE_RETURN'}
    e.need(not any(v in forbidden or v.startswith('APPLY_ACK_') or v == 'APPLY_BEFORE_RETURN' for v in values), 'context acceptance unrelated acknowledgement')
    return [v for v in values if v.startswith(('CONTEXT_ACCEPT_', 'ACCEPT_', 'CONTEXT_REDUNDANT_', 'FLOOR_RELEASE_'))]


def validate(root):
    root = Path(root)
    e.need(root.is_dir() and not root.is_symlink() and {p.name for p in root.iterdir()} ==
           {'original-source-release', 'receipt.json'} | {f'case-{i:02d}' for i in range(len(CUTS))}, 'context acceptance evidence inventory')
    initial, vote, release_record = plan(root)
    first = transition(initial, vote, release_record, acknowledge=True); final = first[-1][1]; rows = []
    for i, cut in enumerate(CUTS):
        case = root/f'case-{i:02d}'
        e.need(case.is_dir() and not case.is_symlink() and {p.name for p in case.iterdir()} == {'first', 'second', 'final', 'events.json'}, 'context acceptance case inventory')
        index = next(n for n, (name, _) in enumerate(first) if name == cut); crash = first[index][1]
        e.need(source.state(case/'first') == crash, 'context acceptance exact first prefix')
        # Reopen returns no ACK. If no successor prefix exists yet, the explicit
        # request is required again; otherwise recovery derives only that prefix.
        second_steps = transition(crash, vote, release_record, acknowledge=False) if owner.ACTIVE in crash else [('ACCEPT_ACTIVE_FORCED', crash)]
        stop = next(n for n, (name, _) in enumerate(second_steps) if name == 'ACCEPT_ACTIVE_FORCED')
        second = second_steps[stop][1]
        e.need(source.state(case/'second') == second, 'context acceptance exact second prefix')
        e.need(source.state(case/'final') == final, 'context acceptance exact final authority')
        events = source.load(case/'events.json', 1024*1024); e.exact(events, 'first second resumed')
        e.need(selected(events['first']) == [name for name, _ in first[:index+1]], 'context acceptance first force order')
        e.need(selected(events['second']) == [name for name, _ in second_steps[:stop+1]], 'context acceptance second force order')
        # With context present, automatic completion precedes the ordinary active
        # vote re-seal; otherwise ordinary re-seal precedes any floor cleanup.
        sealing = list(accept.SEAL)
        cleanup = [name for name, _ in transition(second, vote, release_record, acknowledge=False)]
        expected = cleanup+sealing if owner.ACTIVE in second else sealing+cleanup
        expected += ['ACCEPT_BEFORE_RETURN']*2
        e.need(selected(events['resumed']) == expected, 'context acceptance resume force order')
        rows.append(dict(case=case.name, cut=cut, status='PASS'))
    expected = dict(schema='gse-v53-context-acceptance-v1', status='PASS', cases=rows,
                    freshProcesses=False, runtimeEnabled=False, sourceRetirement=True)
    e.need(e.f.canonical(source.load(root/'receipt.json')) == e.f.canonical(expected), 'context acceptance receipt scope')
    return dict(status='PASS', cases=len(CUTS), originalFirst=True, entryOrigin=20, acceptBallot=21,
                freshProcesses=False, runtimeEnabled=False, laterCampaigns=False, imageSemanticClaim=False)


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    cases = {'bad-original': 'context checksum', 'changed-first': 'context acceptance exact first prefix',
        'changed-second': 'context acceptance exact second prefix', 'wrong-vote': 'context acceptance exact final authority',
        'kept-context': 'context acceptance exact final authority', 'kept-floor': 'context acceptance exact final authority',
        'lost-source': 'context acceptance exact final authority', 'changed-selector': 'context acceptance exact final authority',
        'first-force': 'context acceptance first force order', 'second-force': 'context acceptance second force order',
        'resume-force': 'context acceptance resume force order', 'old-proof-ack': 'context acceptance unrelated acknowledgement',
        'scope': 'context acceptance receipt scope', 'linked-source': 'owner context linked/nonregular member'}
    for name, reason in cases.items():
        with tempfile.TemporaryDirectory(prefix='v53-context-accept-negative-') as tmp:
            moved=Path(tmp)/'evidence'; shutil.copytree(root,moved); case=moved/'case-00'; final=case/'final'
            if name == 'bad-original':
                path=moved/'original-source-release/original-retirement/initial/pending.context'; raw=path.read_bytes(); path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name in ('changed-first','changed-second','wrong-vote'):
                path=case/({'changed-first':'first','changed-second':'second','wrong-vote':'final'}[name])/'pending.accept'; path.write_bytes(b'changed')
            elif name == 'kept-context': shutil.copyfile(moved/'original-source-release/reopened/pending.context', final/'pending.context')
            elif name == 'kept-floor': shutil.copytree(moved/'original-source-release/reopened/floor-copies',final/'floor-copies')
            elif name == 'lost-source': next((final/'sources').rglob('source.gscp')).unlink()
            elif name == 'changed-selector': (final/'selector.gsr').write_bytes(b'changed')
            elif name in ('first-force','second-force','resume-force','old-proof-ack'):
                path=case/'events.json'; events=source.load(path); group={'first-force':'first','second-force':'second','resume-force':'resumed','old-proof-ack':'resumed'}[name]
                if name == 'old-proof-ack': events[group].append('PROOF_BEFORE_RETURN')
                else: events[group].remove(selected(events[group])[0])
                path.write_bytes(e.f.canonical(events))
            elif name == 'scope':
                path=moved/'receipt.json'; value=source.load(path);value['freshProcesses']=True;path.write_bytes(e.f.canonical(value))
            else:
                path=next((final/'sources').rglob('source.gscp')); rel=path.relative_to(final);path.unlink();path.symlink_to((root/'case-00/final'/rel).resolve())
            try: validate(moved)
            except ValueError as error:
                e.need(str(error)==reason, 'wrong context acceptance negative: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else: raise ValueError('accepted context acceptance mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-context-accept-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'context acceptance portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args()
    print(json.dumps(qualify(args.root),sort_keys=True))
