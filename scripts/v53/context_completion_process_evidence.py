"""Original-first physical replay of fresh-owner source/context completion.

Each observed prefix is compared to a model derived from original authority,
never promoted into its own expected recovery state. Process death is not power loss.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import context_acceptance_evidence as a

source, e, owner = a.source, a.e, a.owner
SOURCE_POINTS = (*source.CUTS, 'SOURCE_RETIREMENT_FILE_DELETED@2')
POINTS = (*SOURCE_POINTS, *a.CUTS, 'FLOOR_RELEASE_FILE_DELETED@2', 'FLOOR_RELEASE_FILE_DELETED@4')
PREFIXES = ('SOURCE_RETIREMENT_', 'JOURNAL_ROTATION_', 'CONTEXT_ACCEPT_', 'ACCEPT_', 'CONTEXT_REDUNDANT_', 'FLOOR_RELEASE_')


def plan(root):
    reference = root/'reference'
    source.validate(reference)
    initial, authority, compact, predecessor, backing = source.plan(reference)
    released = source.release.transaction(initial, authority, compact, predecessor)[-1][1]
    files, _ = owner.read_snapshot(reference/'reopened')
    _, installed, packet = e.current(files)
    old, values = e.votes(files['pending.accept'], packet['capsule']['cut'])
    promise = e.f.decode(installed['promise.gsr'], 'records', 'PROMISE')
    selected = e.f.decode(installed['selected.gsr'], 'records', 'SELECTED')
    e.need(promise['ballot']['counter'] == 21 and values['ENTRY']['origin']['counter'] == 20
           and selected['nextEntry'] == e.digest(old['ENTRY']), 'completion exact carried origin')
    accepted = e.f.encode('records', 'ACCEPT', dict(values['ACCEPT'], ballot=promise['ballot']))
    vote = e.container([files['selector.gsr'], installed['promise.gsr'], installed['selected.gsr'], old['ENTRY'], accepted], old['PAYLOAD'])
    release_record = e.f.encode('records', 'RETIREMENT', dict(root=promise['root'], node='node-1',
        floor=e.digest(files['floor-copies/floor.gsr']), selector=e.digest(files['selector.gsr']),
        files=[dict(path=n, size=len(raw), sha256=e.digest(raw)) for n, raw in sorted(files.items()) if n.startswith('floor-copies/')]))
    return initial, authority, compact, predecessor, released, vote, accepted, release_record


def trace(path):
    e.need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 1024*1024, 'completion trace type/capacity')
    raw = path.read_bytes(); lines = raw.splitlines()
    e.need(raw.endswith(b'\n') and 0 < len(lines) <= 4096, 'completion complete trace')
    rows = [e.parse(line) for line in lines]
    e.need(all(type(row) is dict for row in rows) and b''.join(e.f.canonical(row)+b'\n' for row in rows) == raw, 'completion canonical trace')
    forbidden = owner.ACKS-{'ACCEPT_BEFORE_RETURN'}
    e.need(not any(row.get('event') in forbidden or str(row.get('event')).startswith('APPLY_ACK_') or row.get('event') == 'APPLY_BEFORE_RETURN' for row in rows),
           'completion unrelated acknowledgement')
    return rows


def events(rows):
    return [row['event'] for row in rows if str(row.get('event')).startswith(PREFIXES)]


def stop(steps, point):
    parts = point.split('@'); ordinal = int(parts[1]) if len(parts) == 2 else 1
    return [i for i, (event, _) in enumerate(steps) if event == parts[0]][ordinal-1]


def validate(root):
    root = Path(root); names = {mode+'-'+point for mode in ('halt','kill') for point in POINTS}
    e.need(root.is_dir() and not root.is_symlink() and {p.name for p in root.iterdir()} == names|{'reference','inputs.json','receipt.json'}, 'completion case inventory')
    initial, authority, compact, predecessor, released, vote, accepted, release_record = plan(root)
    final = a.transition(released, vote, release_record, acknowledge=True)[-1][1]
    inputs = source.load(root/'inputs.json'); e.exact(inputs, 'observations')
    e.need(type(inputs['observations']) is list and len(inputs['observations']) <= 512, 'completion observation bound')
    for row in inputs['observations']:
        e.exact(row, 'voter storage record parent')
        for key, kind in (('voter','node'),('storage','uuid'),('record','hash'),('parent','hash')): e.f.check_type(row[key],kind,{})
    receipt_rows = []
    for mode in ('halt','kill'):
        for point in POINTS:
            name = mode+'-'+point; case = root/name; source_case = point in SOURCE_POINTS
            e.need(case.is_dir() and not case.is_symlink() and {p.name for p in case.iterdir()} == {'store','crash','recovery-crash','final'}
                   | {label+ext for label in ('fault','recovery','resume') for ext in ('.stdout','.stderr')}, 'completion member inventory')
            for label in ('fault','recovery','resume'):
                path=case/(label+'.stderr'); e.need(path.is_file() and not path.is_symlink() and path.stat().st_size == 0, 'completion stderr')
            fault, recovery, resume = [trace(case/(label+'.stdout')) for label in ('fault','recovery','resume')]
            first = source.release.transaction(initial,authority,compact,predecessor) if source_case else a.transition(released,vote,release_record,acknowledge=True)
            index = stop(first,point); crash = first[index][1]
            e.need(source.state(case/'crash') == crash, 'completion exact first physical prefix')
            e.need(events(fault) == [event for event,_ in first[:index+1]], 'completion first force order')
            marker = dict(event='AWAITING_KILL',cut=point) if mode == 'kill' else dict(event=point.split('@')[0])
            e.need(fault[-1] == marker and sum(row == dict(event='OPEN_RETURNED') for row in fault) == 1
                   and not any('status' in row or row.get('event') == 'RETURNED_ACCEPT' for row in fault), 'completion first death boundary')
            # No ACCEPT acknowledgement escapes either interrupted attempt. The
            # second process can complete source deletion before forcing the new vote.
            second_steps = source.release.transaction(crash,authority,compact,predecessor) if source_case else []
            after_source = second_steps[-1][1] if second_steps else crash
            second_steps += a.transition(after_source,vote,release_record,acknowledge=False) if owner.ACTIVE in after_source else [('ACCEPT_ACTIVE_FORCED',after_source)]
            index = stop(second_steps,'ACCEPT_ACTIVE_FORCED'); second = second_steps[index][1]
            e.need(source.state(case/'recovery-crash') == second, 'completion exact second physical prefix')
            e.need(events(recovery) == [event for event,_ in second_steps[:index+1]], 'completion second force order')
            e.need(recovery[-1] == dict(event='ACCEPT_ACTIVE_FORCED') and not any('status' in row or row.get('event') == 'RETURNED_ACCEPT' for row in recovery),
                   'completion second death boundary')
            e.need(source.state(case/'final') == source.state(case/'store') == final, 'completion exact final authority')
            cleanup = [event for event,_ in a.transition(second,vote,release_record,acknowledge=False)]
            sealing = list(a.accept.SEAL)
            expected = (cleanup+sealing if owner.ACTIVE in second else sealing+cleanup)+['ACCEPT_BEFORE_RETURN']*2
            e.need(events(resume) == expected, 'completion resume force order')
            # Automatic reopen must never claim an ACK; only the two explicit
            # exact calls after open may return the forced successor identity.
            returned = dict(event='RETURNED_ACCEPT',record=e.digest(accepted))
            public_rows = [row for row in resume if row.get('event') in ('OPEN_RETURNED','RETURNED_ACCEPT','ACCEPT_BEFORE_RETURN','CONTEXT_ACCEPT_BEFORE_RETURN')]
            e.need(public_rows == [dict(event='OPEN_RETURNED'),dict(event='ACCEPT_BEFORE_RETURN'),returned,dict(event='ACCEPT_BEFORE_RETURN'),returned],
                   'completion recovery acknowledgement ordering')
            done = resume[-1]; e.exact(done, 'status accept peakImages runtimeEnabled')
            e.need(done == dict(status='PASS',accept=e.digest(accepted),peakImages=done['peakImages'],runtimeEnabled=False)
                   and type(done['peakImages']) is int and 6 <= done['peakImages'] <= 7 and sum('status' in row for row in resume) == 1, 'completion result scope/capacity')
            receipt_rows.append(dict(case=name,mode=mode,cut=point,sourceRetirement=source_case,status='PASS',exitCodes=[73 if mode=='halt' else 137,73,0]))
    expected = dict(schema='gse-v53-context-completion-process-v1',status='PASS',cases=receipt_rows,expectedCases=86,freshProcesses=258,lockProbes=43,
        inputsSha256=e.digest((root/'inputs.json').read_bytes()),historicalBootstrap='conditional-fixture',powerLoss=False,runtimeEnabled=False)
    e.need(e.f.canonical(source.load(root/'receipt.json')) == e.f.canonical(expected), 'completion receipt scope/inputs')
    return dict(status='PASS',cases=86,freshProcesses=258,lockProbes=43,originalFirst=True,entryOrigin=20,acceptBallot=21,
                powerLoss=False,runtimeEnabled=False,laterCampaigns=False,imageSemanticClaim=False)


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    variants={'missing-case':'completion case inventory','bad-original':'context checksum',
        'first-prefix':'completion exact first physical prefix','second-prefix':'completion exact second physical prefix',
        'final-vote':'completion exact final authority','kept-context':'completion exact final authority','kept-floor':'completion exact final authority',
        'lost-source':'completion exact final authority','first-force':'completion first force order','second-force':'completion second force order',
        'resume-force':'completion resume force order','wrong-marker':'completion first death boundary','old-ack':'completion unrelated acknowledgement',
        'premature-return':'completion recovery acknowledgement ordering','wrong-return':'completion recovery acknowledgement ordering',
        'capacity':'completion result scope/capacity','scope':'completion receipt scope/inputs','inputs':'completion receipt scope/inputs',
        'linked-source':'owner context linked/nonregular member'}
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-context-completion-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved);case=moved/'kill-ACCEPT_PREFIX_WRITTEN'
            if name=='missing-case':shutil.rmtree(case)
            elif name=='bad-original':
                p=moved/'reference/original-retirement/initial/pending.context';raw=p.read_bytes();p.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name in ('first-prefix','second-prefix','final-vote'):
                p=case/({'first-prefix':'crash','second-prefix':'recovery-crash','final-vote':'final'}[name])/'pending.accept';p.write_bytes(b'changed')
            elif name=='kept-context':shutil.copyfile(moved/'reference/reopened/pending.context',case/'final/pending.context')
            elif name=='kept-floor':shutil.copytree(moved/'reference/reopened/floor-copies',case/'final/floor-copies')
            elif name=='lost-source':next((case/'final/sources').rglob('source.gscp')).unlink()
            elif name in ('scope','inputs'):
                p=moved/('receipt.json' if name=='scope' else 'inputs.json');row=source.load(p)
                if name=='scope':row['freshProcesses']=257
                else:row['observations'].reverse()
                p.write_bytes(e.f.canonical(row))
            elif name=='linked-source':
                p=next((case/'final/sources').rglob('source.gscp'));rel=p.relative_to(case/'final');p.unlink();p.symlink_to((root/case.name/'final'/rel).resolve())
            else:
                label={'first-force':'fault','second-force':'recovery','wrong-marker':'fault'}.get(name,'resume');p=case/(label+'.stdout')
                rows=[e.parse(line) for line in p.read_bytes().splitlines()]
                if name in ('first-force','second-force','resume-force'):rows.remove(dict(event=events(rows)[0]))
                elif name=='wrong-marker':rows[-1]['cut']='ACCEPT_RENAMED'
                elif name=='old-ack':rows.insert(0,dict(event='PROOF_BEFORE_RETURN'))
                elif name=='premature-return':
                    row=next(row for row in rows if row.get('event')=='RETURNED_ACCEPT');rows.remove(row);rows.insert(0,row)
                elif name=='wrong-return':next(row for row in rows if row.get('event')=='RETURNED_ACCEPT')['record']='0'*64
                else:rows[-1]['peakImages']=8
                p.write_bytes(b''.join(e.f.canonical(row)+b'\n' for row in rows))
            try:validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong completion negative: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted completion mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-context-completion-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'completion portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args()
    print(json.dumps(qualify(args.root),sort_keys=True))
