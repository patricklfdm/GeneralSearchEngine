"""Exact read-only context recovery across a later fixture-supplied PROMISE.

The higher frame is explicitly a forced test input, not an enabled PREPARE path.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import context_source_release_evidence as source

e, owner = source.e, source.owner
STAGES = ('initial', 'retired', 'reopened')


def validate(root):
    root=Path(root)
    e.need(root.is_dir() and not root.is_symlink() and {p.name for p in root.iterdir()} == {'reference','receipt.json',*STAGES}, 'context fence evidence inventory')
    source.validate(root/'reference');rows=[]
    for stage in STAGES:
        case=root/stage;original=root/'reference'/('reopened' if stage=='reopened' else 'original-retirement/'+stage)
        e.need(case.is_dir() and not case.is_symlink() and {p.name for p in case.iterdir()} == {'initial','final','fence.gsr','events.json'}, 'context fence case inventory')
        files,dirs=owner.read_snapshot(original);segments,_,binding=e.decode(files['pending.context'])
        backing=e.f.decode(segments[2],'records','PROMISE');fence_path=case/'fence.gsr'
        e.need(fence_path.is_file() and not fence_path.is_symlink() and fence_path.stat().st_size <= 8192, 'context fence frame type/capacity')
        raw=fence_path.read_bytes();fence=e.f.decode(raw,'records','PROMISE')
        expected=dict(backing,ballot=dict(fence['ballot'],counter=22),basisId=fence['basisId'])
        e.need(fence == expected and fence['basisId'] != backing['basisId'] and backing['ballot']['counter'] == 21, 'context fence exact higher promise')
        definition=e.f.decode(files['root.gsr'],'records','ROOT')
        e.need(any(v['node']==fence['ballot']['proposer'] and v['storage']==fence['ballot']['incarnation'] for v in definition['initial']),
               'context fence higher proposer identity')
        e.f.check_type(fence['basisId'],'uuid',{})
        e.need('sources/'+fence['basisId'] not in dirs, 'context fence latest has no source')
        files=dict(files);files['grants.gsr']+=raw
        # Journal replay validates monotonically increasing full frames; the
        # final PROMISE has neither BASIS nor SELECTED. It is never the backing.
        journal=owner.journal(files['grants.gsr'],binding['root'],binding['node'])
        e.need(journal[-1][0]=='PROMISE' and journal[-1][1]==raw
               and any(kind=='PROMISE' and frame==segments[2] for kind,frame,_ in journal)
               and any(kind=='BASIS' and frame==segments[3] for kind,frame,_ in journal), 'context fence exact retained backing')
        for name in ('initial','final'):
            actual,actual_dirs=owner.read_snapshot(case/name)
            e.need(actual==files and actual_dirs==dirs, 'context fence exact '+name+' bytes')
        events=source.load(case/'events.json');e.need(type(events) is list and len(events)<=2048 and all(type(v) is str for v in events), 'context fence events')
        e.need(not any(v in owner.ACKS or v in ('CONTEXT_ACCEPT_BEFORE_RETURN','PROMISE_BEFORE_WRITE','PROMISE_WRITTEN','PROMISE_FORCED') or v.startswith('APPLY_ACK_') for v in events),
               'context fence returned authority')
        e.need(events.count('CONTEXT_SOURCE_PARENT_FORCED')==events.count('CONTEXT_ACTIVE_PARENT_FORCED')==4
               and events.count('CONTEXT_OWNER_BEFORE_RETURN')==4, 'context fence complete reseals')
        rows.append(dict(case=stage,status='PASS'))
    expected=dict(schema='gse-v53-context-durable-fence-v1',status='PASS',cases=rows,promiseInput='forced-fixture-frame',runtimeEnabled=False,newCampaignEnabled=False)
    e.need(e.f.canonical(source.load(root/'receipt.json'))==e.f.canonical(expected), 'context fence receipt scope')
    return dict(status='PASS',stages=3,originalFirst=True,originalOrigin=20,backingBallot=21,latestPromise=22,promiseInput='forced-fixture-frame',
                newCampaignEnabled=False,freshProcesses=False,runtimeEnabled=False)


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    variants={'bad-reference':'context checksum','missing-stage':'context fence evidence inventory',
        'changed-context':'context fence exact final bytes','lost-backing':'context fence exact final bytes',
        'used-latest':'context fence exact final bytes','changed-entry':'context fence exact final bytes',
        'removed-promise':'context fence exact final bytes','false-fence':'context fence exact higher promise',
        'foreign-proposer':'context fence higher proposer identity','foreign-incarnation':'context fence higher proposer identity',
        'old-ack':'context fence returned authority','missing-reseal':'context fence complete reseals','scope':'context fence receipt scope',
        'linked-context':'owner context linked/nonregular member'}
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-context-fence-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved);case=moved/'reopened';final=case/'final'
            if name=='bad-reference':
                p=moved/'reference/original-retirement/initial/pending.context';raw=p.read_bytes();p.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name=='missing-stage':shutil.rmtree(case)
            elif name=='changed-context':(final/'pending.context').write_bytes(b'changed')
            elif name=='lost-backing':next((final/'sources').rglob('source.gscp')).unlink()
            elif name=='changed-entry':(final/'pending.accept').write_bytes(b'changed')
            elif name=='removed-promise':shutil.copyfile(moved/'reference/reopened/grants.gsr',final/'grants.gsr')
            elif name=='used-latest':
                fence=e.f.decode((case/'fence.gsr').read_bytes(),'records','PROMISE');old=next((final/'sources').iterdir());old.rename(old.with_name(fence['basisId']))
            elif name in ('false-fence','foreign-proposer','foreign-incarnation'):
                p=case/'fence.gsr';v=e.f.decode(p.read_bytes(),'records','PROMISE')
                if name=='false-fence':v['ballot']['counter']=23
                elif name=='foreign-proposer':v['ballot']['proposer']='node-7'
                else:v['ballot']['incarnation']='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
                p.write_bytes(e.f.encode('records','PROMISE',v))
            elif name in ('old-ack','missing-reseal'):
                p=case/'events.json';v=source.load(p)
                if name=='old-ack':v.append('ACCEPT_BEFORE_RETURN')
                else:v.remove('CONTEXT_SOURCE_PARENT_FORCED')
                p.write_bytes(e.f.canonical(v))
            elif name=='scope':
                p=moved/'receipt.json';v=source.load(p);v['newCampaignEnabled']=True;p.write_bytes(e.f.canonical(v))
            else:
                p=final/'pending.context';p.unlink();p.symlink_to((root/'reopened/final/pending.context').resolve())
            try:validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong context fence negative: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted context fence mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-context-fence-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'context fence portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args()
    print(json.dumps(qualify(args.root),sort_keys=True))
