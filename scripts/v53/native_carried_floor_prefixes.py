"""Original complete-copy FLOOR creation and release bytes through group death.

Require the complete retirement/resource/original-history chain before comparing
writer-held file captures to independent original transaction states.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import native_carried_retirement_prefixes as r

need=r.need;f=r.f;collection=r.collection;shared=r.shared
SCHEMA='gse-v53-carried-process-floor-capture-v1'
CAPTURE_SCHEMA='gse-v53-carried-floor-capture-v1'
KINDS={'floor':r.forces.floor.CUTS+('FLOOR_COPY_HANDED_OFF','FLOOR_LOCAL_ORIGINAL_FORCED',
    'FLOOR_LOCAL_SELECTOR_WRITTEN','FLOOR_LOCAL_SELECTOR_FORCED','FLOOR_LOCAL_PARENT_FORCED'),
    'floor-release':('FLOOR_RELEASE_',)}


def plans(root):
    history=Path(root)/'history';result=r.forces.process.read(history/'process/result.json');expected=[]
    r.forces.replay(history,result['carriedKind'],result['cut'],floor_prefixes=expected)
    return expected


def replay(root,floors,expected=None):
    floors=Path(floors);need({v.name for v in floors.iterdir()}=={'life-1','life-2'},'carried floor exact two lifetimes')
    expected=plans(root) if expected is None else expected
    lives=[r.lifetime(root,floors/f'life-{life}',life,expected,schema=SCHEMA,capture_schema=CAPTURE_SCHEMA,kinds=KINDS) for life in (1,2)]
    return dict(status='PARTIAL',lifetimes=lives,capturedPrefixes=sum(v['capturedPrefixes'] for v in lives),
        transientFloorBytesQualified=True,postCutTailObserved=False,fullTransientBytesQualified=False,
        coreScratchInventoryReplay=False,wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)


def validate(root):
    root=Path(root);before=collection.inventory(root)
    need({v.name for v in root.iterdir()}=={'prefixes','floors'},'carried floor wrapper inventory')
    original=r.validate(root/'prefixes');result=replay(root/'prefixes/observed',root/'floors')
    need(collection.inventory(root)==before,'carried floor original changed')
    return dict(status='PARTIAL',original=original,floors=result,phase3Complete=False)


NEGATIVES={name:r.NEGATIVES[name] for name in ('missing-copy','duplicate-index','wrong-callback','missing-object',
    'altered-object','extra-object','boolean-size','wrong-owner','process-pid','process-life','process-root',
    'process-terminal','process-events','boolean-pid','missing-callback')}
NEGATIVES['missing-lifetime']='carried floor exact two lifetimes'
PHYSICAL={
    'proposal-substitution':'FLOOR_PROPOSAL_WRITTEN',
    'early-authority':'FLOOR_PROPOSAL_FORCED',
    'wrong-generation':'FLOOR_MANIFEST_WRITTEN',
    'image-bytes':'FLOOR_IMAGE_WRITTEN',
    'handoff-file-removed':'FLOOR_COPY_HANDED_OFF',
    'release-authority':'FLOOR_RELEASE_AUTHORITY_WRITTEN',
    'early-file-delete':'FLOOR_RELEASE_PARENT_FORCED',
    'late-file-delete':'FLOOR_RELEASE_FILE_DELETED',
    'release-before-authority':'FLOOR_RELEASE_AUTHORITY_CREATED',
    'release-leftover':'FLOOR_RELEASE_BEFORE_RETURN',
    'outside-floor':'FLOOR_RESERVED',
}
NEGATIVES.update({name:'carried prefix exact original state: '+point for name,point in PHYSICAL.items()})


def mutate(root,name):
    need(name in NEGATIVES,'carried floor unknown negative')
    if name not in PHYSICAL:return r.mutate(root,name)
    directory=Path(root)/'life-2';objects=directory/'objects';header_path=directory/'collection.json'
    copies=[(p,shared.g.json_file(p)[1]) for p in sorted(directory.glob('capture-*.json'))]
    path,value=next((p,v) for p,v in copies if v['point']==PHYSICAL[name])
    values={v['name']:v['identity'] for v in value['files']}
    def put(key,raw):
        digest=shared.sha(raw);(objects/digest).write_bytes(raw);values[key]=dict(size=len(raw),sha256=digest)
    def read(key):return (objects/values[key]['sha256']).read_bytes()
    def from_copy(copy):return {v['name']:v['identity'] for v in copy['files']}
    if name=='proposal-substitution':
        key='floor-copies/proposal.gsr';record=f.decode(read(key),'records','FLOOR');record['root']='0'*64
        put(key,f.encode('records','FLOOR',record))
    elif name=='early-authority':
        later=next(v for _,v in copies if v['node']==value['node'] and v['eventIndex']>value['eventIndex'] and v['point']=='FLOOR_AUTHORITY_WRITTEN')
        values['floor-copies/floor.gsr']=from_copy(later)['floor-copies/floor.gsr']
    elif name=='wrong-generation':put(next(k for k in values if k.startswith('floor-copies/') and k.endswith('/generation.gsr')),b'wrong copied generation')
    elif name=='image-bytes':
        key=next(k for k in values if k.startswith('floor-copies/') and k.endswith('.image'));raw=read(key)
        put(key,raw[:-1]+bytes([raw[-1]^1]))
    elif name=='handoff-file-removed':values.pop(next(k for k in values if k.startswith('floor-copies/') and k.endswith('.image')))
    elif name=='release-authority':
        key='floor-copies/release.gsr';record=f.decode(read(key),'records','RETIREMENT');record['selector']='0'*64
        put(key,f.encode('records','RETIREMENT',record))
    elif name=='early-file-delete':values.pop(next(k for k in values if k.startswith('floor-copies/') and k.count('/')==2))
    elif name=='late-file-delete':
        prior=next(v for _,v in reversed(copies) if v['node']==value['node'] and v['eventIndex']<value['eventIndex'] and v['point']=='FLOOR_RELEASE_PARENT_FORCED')
        old=from_copy(prior);key=next(k for k in old if k.startswith('floor-copies/') and k.count('/')==2 and k not in values)
        values[key]=old[key]
    elif name=='release-before-authority':values.pop('floor-copies/floor.gsr')
    elif name=='release-leftover':values['floor-copies']=dict(directory=True)
    elif name=='outside-floor':put('grants.gsr',b'altered original journal')
    value['files']=[dict(name=k,identity=v) for k,v in sorted(values.items())];path.write_bytes(f.canonical(value))
    used={entry['identity']['sha256'] for p in directory.glob('capture-*.json')
          for entry in shared.g.json_file(p)[1]['files'] if 'sha256' in entry['identity']}
    for p in objects.iterdir():
        if p.name not in used:p.unlink()
    _,header=shared.g.json_file(header_path)
    header['storedBytes']=sum(p.stat().st_size for p in directory.rglob('*') if p.is_file() and p!=header_path)
    header_path.write_bytes(f.canonical(header))


def qualify(root):
    root=Path(root);original=validate(root);before=collection.inventory(root);expected=plans(root/'prefixes/observed');results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-carried-floor-negative-') as temp:
            changed=Path(temp)/'floors';shutil.copytree(root/'floors',changed);mutate(changed,name)
            try:replay(root/'prefixes/observed',changed,expected)
            except ValueError as error:need(str(error)==reason,'carried floor unrelated negative: '+name+': '+str(error))
            else:raise ValueError('carried floor mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
        print(json.dumps(dict(case=name,completed=len(results),total=len(NEGATIVES))),file=sys.stderr,flush=True)
    need(collection.inventory(root)==before,'carried floor qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True,mutatedPrerequisiteReplayed=False,
        negativePrecondition='full original retirement/resource/process/storage replay; expected FLOOR bytes derived from unchanged originals')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))
