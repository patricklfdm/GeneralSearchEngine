"""Original control application scratch file prefixes through carried group death and reopening."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import native_carried_ledger_prefixes as prerequisite
from . import native_carried_retirement_prefixes as r
from . import native_replay_files as model
from . import replay_resource_binding as binding
from . import native_carried_resource_evidence as resource

need=r.need;f=r.f;collection=r.collection;shared=r.shared
SCHEMA='gse-v53-carried-process-replay-capture-v1'
CAPTURE_SCHEMA='gse-v53-carried-replay-capture-v1'
KINDS=model.KINDS


def plans(root):
    history=Path(root)/'history';result=r.forces.process.read(history/'process/result.json');expected=[]
    r.forces.replay(history,result['carriedKind'],result['cut'],replay_prefixes=expected)
    return expected


def replay(root,replay,expected=None):
    replay=Path(replay);need({v.name for v in replay.iterdir()}=={'life-1','life-2'},'carried replay exact two lifetimes')
    expected=plans(root) if expected is None else expected
    lives=[r.lifetime(root,replay/f'life-{life}',life,expected,schema=SCHEMA,capture_schema=CAPTURE_SCHEMA,kinds=KINDS) for life in (1,2)]
    resources=[]
    for life in (1,2):
        directory=Path(root)/f'resources/life-{life}'
        events=resource.read(directory,'events.json',32*1024*1024)
        boundaries=resource.read(directory,'boundaries.json',32*1024*1024)
        membership_starts=binding.native_membership_starts(events)
        for node in r.forces.process.NODES:
            _,trace=binding.r.read(directory/(node+'.json'))
            resources.append(dict(life=life,node=node,**binding.bind(trace,events,boundaries,node,closed=life==2,
                membership_starts=membership_starts)))
    return dict(status='PARTIAL',resources=resources,lifetimes=lives,capturedPrefixes=sum(v['capturedPrefixes'] for v in lives),
        controlScratchBytesQualified=True,postCutTailObserved=False,fullTransientBytesQualified=False,
        controlReplayCallbackInventoryQualified=True,coreScratchInventoryReplay=False,internalCoreWritesObserved=False,
        supportedRecords=['INTENT','FINAL','BARRIER'],wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)


def validate(root):
    root=Path(root);before=collection.inventory(root)
    need({v.name for v in root.iterdir()}=={'previous','replay'},'carried replay wrapper inventory')
    original=prerequisite.validate(root/'previous')
    result=replay(root/'previous/previous/previous/previous/maintenance/prefixes/observed',root/'replay')
    need(collection.inventory(root)==before,'carried replay original changed')
    return dict(status='PARTIAL',original=original,replay=result,phase3Complete=False)


NEGATIVES={name:r.NEGATIVES[name] for name in ('missing-copy','duplicate-index','wrong-callback','missing-object',
    'altered-object','extra-object','boolean-size','wrong-owner','process-pid','process-life','process-root',
    'process-terminal','process-events','boolean-pid','missing-callback')}
NEGATIVES['missing-lifetime']='carried replay exact two lifetimes'
PHYSICAL={
    'nonempty-claim-create':('REPLAY_CLAIM_CREATED','claim'),
    'complete-claim-prefix':('REPLAY_CLAIM_PREFIX_WRITTEN','complete'),
    'early-input':('REPLAY_BEFORE_APPLICATION','early'),
    'missing-input':('REPLAY_APPLICATION_FINISHED','missing'),
    'changed-input':('REPLAY_APPLICATION_FINISHED','input'),
    'unexpected-output':('REPLAY_APPLICATION_FINISHED','output'),
    'early-claim-delete':('REPLAY_DELETED','delete'),
    'leftover-directory':('REPLAY_BEFORE_RETURN','directory'),
    'outside-scratch':('REPLAY_RESERVED','outside'),
}
NEGATIVES.update({name:'carried prefix exact original state: '+point for name,(point,_) in PHYSICAL.items()})


def mutate(root,name):
    need(name in NEGATIVES,'carried replay unknown negative')
    if name not in PHYSICAL:return r.mutate(root,name)
    directory=Path(root)/'life-2';objects=directory/'objects';header_path=directory/'collection.json'
    copies=[(p,shared.g.json_file(p)[1]) for p in sorted(directory.glob('capture-*.json'))]
    point,change=PHYSICAL[name];path,value=next((p,v) for p,v in copies if v['point']==point)
    values={v['name']:v['identity'] for v in value['files']};prefix=model.DIRECTORY
    def put(key,raw):
        digest=shared.sha(raw);(objects/digest).write_bytes(raw);values[key]=dict(size=len(raw),sha256=digest)
    if change=='claim':put(prefix+'/claim.json',b'nonempty')
    elif change=='complete':
        later=next(v for _,v in copies if v['node']==value['node'] and v['eventIndex']>value['eventIndex'] and v['point']=='REPLAY_CLAIM_WRITTEN')
        values[prefix+'/claim.json']=next(v['identity'] for v in later['files'] if v['name']==prefix+'/claim.json')
    elif change=='early':values[prefix+'/work']=dict(directory=True)
    elif change=='missing':del values[prefix+'/work/input/gse-backup-manifest']
    elif change=='input':put(prefix+'/work/input/gse-backup-checkpoint',b'foreign image')
    elif change=='output':values[prefix+'/work/output']=dict(directory=True)
    elif change=='delete':del values[prefix+'/claim.json']
    elif change=='directory':values[prefix]=dict(directory=True)
    elif change=='outside':put('grants.gsr',b'foreign journal')
    value['files']=[dict(name=k,identity=v) for k,v in sorted(values.items())];path.write_bytes(f.canonical(value))
    used={entry['identity']['sha256'] for p in directory.glob('capture-*.json')
          for entry in shared.g.json_file(p)[1]['files'] if 'sha256' in entry['identity']}
    for p in objects.iterdir():
        if p.name not in used:p.unlink()
    _,header=shared.g.json_file(header_path)
    header['storedBytes']=sum(p.stat().st_size for p in directory.rglob('*') if p.is_file() and p!=header_path)
    header_path.write_bytes(f.canonical(header))


def qualify(root):
    root=Path(root);original=validate(root);before=collection.inventory(root)
    observed=root/'previous/previous/previous/previous/maintenance/prefixes/observed';expected=plans(observed);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-carried-replay-negative-') as temp:
            changed=Path(temp)/'replay';shutil.copytree(root/'replay',changed);mutate(changed,name)
            try:replay(observed,changed,expected)
            except ValueError as error:need(str(error)==reason,'carried replay unrelated negative: '+name+': '+str(error))
            else:raise ValueError('carried replay mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
        print(json.dumps(dict(case=name,completed=len(results),total=len(NEGATIVES))),file=sys.stderr,flush=True)
    need(collection.inventory(root)==before,'carried replay qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True,mutatedPrerequisiteReplayed=False,
        negativePrecondition='complete original ledger/completion/vote/campaign/maintenance/resource/process chain; independent unchanged replay plan')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))
