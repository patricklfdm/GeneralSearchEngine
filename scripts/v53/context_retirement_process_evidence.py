"""Predict exact retained states and replay fresh-owner halt/SIGKILL recovery.

No rerun of Java or use of observed crash bytes as the expected recovery source.
Historical bootstrap/remote observation inputs remain conditional, not new receipts.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import context_retirement_evidence as c
from . import retirement_evidence as r
from . import journal_context_evidence as owner
from . import pending_context_evidence as e

POINTS = r.CUTS[:25] + ('CONTEXT_SOURCE_PARENT_FORCED', 'CONTEXT_ACTIVE_FORCED')


def state(path):
    files, directories = owner.read_snapshot(path)
    return {name: e.info(raw) for name,raw in files.items()} | {name: dict(directory=True) for name in directories}


def trace(path):
    e.need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 1024*1024, 'context process trace capacity/type')
    raw = path.read_bytes(); lines = raw.splitlines(); e.need(raw.endswith(b'\n') and 0 < len(lines) <= 2048, 'context process complete trace')
    rows = [e.parse(line) for line in lines]
    e.need(all(type(row) is dict for row in rows) and b''.join(e.f.canonical(row)+b'\n' for row in rows) == raw, 'context process canonical trace')
    e.need(not any(row.get('event') in owner.ACKS or str(row.get('event')).startswith('APPLY_ACK_') or row.get('event') == 'APPLY_BEFORE_RETURN' for row in rows),
           'context process returned old acknowledgement')
    return rows


def validate(root):
    root = Path(root); names = {mode+'-'+point for mode in ('halt','kill') for point in POINTS}
    e.need(root.is_dir() and not root.is_symlink() and {p.name for p in root.iterdir()} == names|{'reference','inputs.json','receipt.json'}, 'context process case inventory')
    reference = c.validate(root/'reference')
    initial, _ = owner.read_snapshot(root/'reference/initial'); floor_files, _ = owner.read_snapshot(root/'reference/floor')
    before = state(root/'reference/floor'); final = state(root/'reference/retired'); old_slot = reference['oldSlot']; prefix = 'generations/'+old_slot+'/'
    originals = {name.removeprefix(prefix): raw for name,raw in initial.items() if name.startswith(prefix)}
    record = e.f.encode('records','RETIREMENT',dict(root=initial['root.gsr'][16:48].hex(), node='node-1',
        floor=e.digest(floor_files['floor-copies/floor.gsr']), selector=e.digest(initial['selector.gsr']),
        files=[dict(path=prefix+name,size=len(raw),sha256=e.digest(raw)) for name,raw in sorted(originals.items())]))
    e.need(e.digest(record) == reference['retirement'], 'context process original retirement binding')
    steps,_ = r.transaction(before, originals, record, slot=old_slot)
    e.need(steps[-1][1] == final, 'context process projected final state')
    input_path = root/'inputs.json'; receipt_path = root/'receipt.json'
    for path in (input_path,receipt_path):
        e.need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 65536, 'context process metadata type/capacity')
    inputs = e.parse(input_path.read_bytes()); e.exact(inputs, 'observations')
    e.need(type(inputs['observations']) is list and len(inputs['observations']) <= 512, 'context process observation bound')
    for row in inputs['observations']:
        e.exact(row, 'voter storage record parent')
        for key,kind in (('voter','node'),('storage','uuid'),('record','hash'),('parent','hash')): e.f.check_type(row[key],kind,{})
    rows = []
    for mode in ('halt','kill'):
        for point in POINTS:
            name = mode+'-'+point; path = root/name
            e.need(path.is_dir() and not path.is_symlink() and {p.name for p in path.iterdir()} == {'store','crash','recovery-crash','final'}
                   | {label+ext for label in ('fault','recovery','resume') for ext in ('.stdout','.stderr')}, 'context process member inventory')
            for label in ('fault','recovery','resume'):
                stderr = path/(label+'.stderr'); e.need(stderr.is_file() and not stderr.is_symlink() and stderr.stat().st_size == 0, 'context process stderr')
            fault, recovery, resume = [trace(path/(label+'.stdout')) for label in ('fault','recovery','resume')]
            if point.startswith('CONTEXT_'): expected_crash = before; prefix_events = []
            else:
                position = r.cut_position(steps,point); expected_crash = steps[position][1]; prefix_events = [event for event,_ in steps[:position+1]]
            e.need(state(path/'crash') == expected_crash, 'context process exact interrupted physical state')
            e.need(state(path/'recovery-crash') == expected_crash, 'context process second interruption changed bytes')
            e.need(state(path/'final') == state(path/'store') == final, 'context process exact final physical state')
            fault_events = [row['event'] for row in fault if str(row.get('event')).startswith('RETIREMENT_')]
            e.need(fault_events == prefix_events, 'context process force-before-delete trace')
            expected_end = dict(event='AWAITING_KILL',cut=point) if mode == 'kill' else dict(event=point)
            e.need(fault[-1] == expected_end and not any('status' in row for row in fault), 'context process initial death boundary')
            e.need(recovery[-1] == dict(event='CONTEXT_SOURCE_PARENT_FORCED') and not any('status' in row or str(row.get('event')).startswith('RETIREMENT_') for row in recovery),
                   'context process second death boundary')
            rest,_ = r.transaction(expected_crash,originals,record,slot=old_slot)
            e.need([row['event'] for row in resume if str(row.get('event')).startswith('RETIREMENT_')] == [event for event,_ in rest],
                   'context process exact recovery trace')
            e.need(any(row == dict(event='OBSERVED_24') for row in resume), 'context process higher observation absent')
            done = resume[-1]; e.exact(done, 'status pending context peakImages runtimeEnabled')
            e.need(done == dict(status='PASS',pending=e.digest(initial['pending.accept']),context=e.digest(initial['pending.context']),
                               peakImages=done['peakImages'],runtimeEnabled=False) and type(done['peakImages']) is int and 1 <= done['peakImages'] <= 7
                   and done['runtimeEnabled'] is False and sum('status' in row for row in resume) == 1, 'context process completion scope')
            rows.append(dict(case=name,mode=mode,cut=point,status='PASS',exitCodes=[73 if mode=='halt' else 137,73,0]))
    expected = dict(schema='gse-v53-context-retirement-process-v1',status='PASS',cases=rows,expectedCases=54,freshProcesses=162,
        inputsSha256=e.digest(input_path.read_bytes()),historicalBootstrap='conditional-fixture',powerLoss=False,nextCampaign=False)
    e.need(e.f.canonical(e.parse(receipt_path.read_bytes())) == e.f.canonical(expected), 'context process receipt scope/inputs')
    return dict(status='PASS',cases=54,freshProcesses=162,originalFirst=True,scope='actual-local-context-owner',powerLoss=False,
                nextCampaign=False,remoteOwnershipVerified=False,imageSemanticClaim=False)


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    variants = {'missing-case':'context process case inventory', 'changed-crash':'context process exact interrupted physical state',
        'changed-second-crash':'context process second interruption changed bytes', 'changed-final':'context process exact final physical state',
        'wrong-marker':'context process initial death boundary', 'force-order':'context process force-before-delete trace',
        'old-ack':'context process returned old acknowledgement', 'wrong-recovery':'context process second death boundary',
        'false-process':'context process receipt scope/inputs', 'changed-inputs':'context process receipt scope/inputs',
        'linked-crash':'owner context linked/nonregular member', 'bad-reference':'context retirement exact deletion/protected originals'}
    for name, reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-context-process-negative-') as temp:
            moved = Path(temp)/'evidence'; shutil.copytree(root,moved); case = moved/'kill-RETIREMENT_PARENT_FORCED'
            if name == 'missing-case': shutil.rmtree(case)
            elif name in ('changed-crash','changed-second-crash','changed-final'):
                stage = {'changed-crash':'crash','changed-second-crash':'recovery-crash','changed-final':'final'}[name]
                (case/stage/'pending.accept').write_bytes(b'changed')
            elif name in ('wrong-marker','force-order','old-ack','wrong-recovery'):
                path = case/('recovery.stdout' if name=='wrong-recovery' else 'fault.stdout'); rows = [e.parse(line) for line in path.read_bytes().splitlines()]
                if name=='wrong-marker': rows[-1]['cut']='RETIREMENT_FILE_DELETED'
                elif name=='force-order': rows.remove(dict(event='RETIREMENT_SOURCE_FORCED'))
                elif name=='old-ack': rows.insert(0,dict(event='ACCEPT_BEFORE_RETURN'))
                else: rows[-1]['event']='CONTEXT_ACTIVE_FORCED'
                path.write_bytes(b''.join(e.f.canonical(row)+b'\n' for row in rows))
            elif name=='false-process':
                path=moved/'receipt.json'; row=e.parse(path.read_bytes()); row['freshProcesses']=161; path.write_bytes(e.f.canonical(row))
            elif name=='changed-inputs':
                path=moved/'inputs.json'; row=e.parse(path.read_bytes()); row['observations'].reverse(); path.write_bytes(e.f.canonical(row))
            elif name=='linked-crash':
                path=case/'crash/pending.accept'; path.unlink(); path.symlink_to((root/case.name/'crash/pending.accept').resolve())
            else: (moved/'reference/retired/pending.accept').write_bytes(b'changed')
            try: validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong context process negative reason: '+name+': '+str(error)); negatives.append(dict(case=name,reason=reason))
            else: raise ValueError('accepted context process mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-context-process-portable-') as temp:
        moved=Path(temp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'context process portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args()
    print(json.dumps(qualify(args.root),sort_keys=True))
