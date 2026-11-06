"""Original campaign allocation, grant, selection and installation file prefixes.

Require the complete FLOOR/retirement/resource/original-history chain before comparing
writer-held file captures to independent original transaction states.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import native_carried_floor_prefixes as prerequisite
from . import native_carried_retirement_prefixes as r
from . import native_campaign_files as model

need=r.need;f=r.f;collection=r.collection;shared=r.shared
SCHEMA='gse-v53-carried-process-campaign-capture-v1'
CAPTURE_SCHEMA='gse-v53-carried-campaign-capture-v1'
KINDS=model.KINDS


def plans(root):
    history=Path(root)/'history';result=r.forces.process.read(history/'process/result.json');expected=[]
    r.forces.replay(history,result['carriedKind'],result['cut'],campaign_prefixes=expected)
    return expected


def replay(root,campaigns,expected=None):
    campaigns=Path(campaigns);need({v.name for v in campaigns.iterdir()}=={'life-1','life-2'},'carried campaign exact two lifetimes')
    expected=plans(root) if expected is None else expected
    lives=[r.lifetime(root,campaigns/f'life-{life}',life,expected,schema=SCHEMA,capture_schema=CAPTURE_SCHEMA,kinds=KINDS) for life in (1,2)]
    return dict(status='PARTIAL',lifetimes=lives,capturedPrefixes=sum(v['capturedPrefixes'] for v in lives),
        transientCampaignBytesQualified=True,postCutTailObserved=False,fullTransientBytesQualified=False,
        coreScratchInventoryReplay=False,wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)


def validate(root):
    root=Path(root);before=collection.inventory(root)
    need({v.name for v in root.iterdir()}=={'maintenance','campaigns'},'carried campaign wrapper inventory')
    original=prerequisite.validate(root/'maintenance');result=replay(root/'maintenance/prefixes/observed',root/'campaigns')
    need(collection.inventory(root)==before,'carried campaign original changed')
    return dict(status='PARTIAL',original=original,campaigns=result,phase3Complete=False)


NEGATIVES={name:r.NEGATIVES[name] for name in ('missing-copy','duplicate-index','wrong-callback','missing-object',
    'altered-object','extra-object','boolean-size','wrong-owner','process-pid','process-life','process-root',
    'process-terminal','process-events','boolean-pid','missing-callback')}
NEGATIVES['missing-lifetime']='carried campaign exact two lifetimes'
PHYSICAL={
    'allocator-early-rename':'ALLOCATOR_WRITTEN',
    'allocator-counter':'ALLOCATOR_WRITTEN',
    'promise-truncated':'PROMISE_WRITTEN',
    'intent-empty-prefix':'CAPTURE_INTENT_PREFIX_WRITTEN',
    'intent-early-clear':'CAPTURE_INTENT_FORCED',
    'source-directory-missing':'SOURCE_CREATED',
    'packet-full-before-prefix':'SOURCE_PACKET_PREFIX_WRITTEN',
    'image-substitution':'SOURCE_IMAGE_WRITTEN',
    'basis-full-before-prefix':'BASIS_PREFIX_WRITTEN',
    'intent-leftover':'GRANT_BEFORE_RETURN',
    'selected-early':'SELECTED_BEFORE_WRITE',
    'selected-missing':'SELECTED_FORCED',
    'generation-precreated':'INSTALL_RESERVED',
    'manifest-substitution':'INSTALL_MANIFEST_WRITTEN',
    'member-missing':'INSTALL_MEMBER_WRITTEN',
    'selector-early-rename':'INSTALL_SELECTOR_WRITTEN',
    'selector-candidate-leftover':'INSTALL_SELECTOR_RENAMED',
    'retention-substitution':'INSTALL_BEFORE_RETURN',
    'outside-campaign':'ALLOCATOR_BEFORE_WRITE',
}
NEGATIVES.update({name:'carried prefix exact original state: '+point for name,point in PHYSICAL.items()})


def mutate(root,name):
    need(name in NEGATIVES,'carried campaign unknown negative')
    if name not in PHYSICAL:return r.mutate(root,name)
    directory=Path(root)/'life-2';objects=directory/'objects';header_path=directory/'collection.json'
    copies=[(p,shared.g.json_file(p)[1]) for p in sorted(directory.glob('capture-*.json'))]
    path,value=next((p,v) for p,v in copies if v['point']==PHYSICAL[name])
    def contents(copy):return {v['name']:v['identity'] for v in copy['files']}
    values=contents(value)
    def put(key,raw):
        digest=shared.sha(raw);(objects/digest).write_bytes(raw);values[key]=dict(size=len(raw),sha256=digest)
    def read(key):return (objects/values[key]['sha256']).read_bytes()
    def later(point):return next(v for _,v in copies if v['node']==value['node'] and v['eventIndex']>value['eventIndex'] and v['point']==point)
    def prior(point):return next(v for _,v in reversed(copies) if v['node']==value['node'] and v['eventIndex']<value['eventIndex'] and v['point']==point)
    def generation():
        created=value if value['point']=='INSTALL_DIRECTORY_CREATED' else later('INSTALL_DIRECTORY_CREATED') if value['point']=='INSTALL_RESERVED' else prior('INSTALL_DIRECTORY_CREATED')
        before=prior('INSTALL_RESERVED') if value['point']!='INSTALL_RESERVED' else value
        return next(k for k in contents(created).keys()-contents(before).keys() if k.startswith('generations/'))
    if name=='allocator-early-rename':values['allocator.gsr']=values.pop('allocator.pending.gsr')
    elif name=='allocator-counter':
        raw=f.decode(read('allocator.pending.gsr'),'records','ALLOCATOR');raw['counter']+=1;put('allocator.pending.gsr',f.encode('records','ALLOCATOR',raw))
    elif name=='promise-truncated':put('grants.gsr',read('grants.gsr')[:-1])
    elif name=='intent-empty-prefix':put('source.capture.gsr',b'')
    elif name=='intent-early-clear':values.pop('source.capture.gsr')
    elif name=='source-directory-missing':
        before=contents(prior('SOURCE_BEFORE_CREATE'));values.pop(next(k for k in values.keys()-before.keys() if k.startswith('sources/')))
    elif name=='packet-full-before-prefix':
        after=contents(later('SOURCE_PACKET_WRITTEN'));key=next(k for k in values if k.endswith('/source.gscp') and values[k]!=after[k]);values[key]=after[key]
    elif name=='image-substitution':
        created=contents(prior('SOURCE_CREATED'));before=contents(prior('SOURCE_BEFORE_CREATE'))
        source=next(k for k in created.keys()-before.keys() if k.startswith('sources/'))
        key=next(k for k in values if k.startswith(source+'/') and k.endswith('.image'));raw=read(key);put(key,raw[:-1]+bytes([raw[-1]^1]))
    elif name=='basis-full-before-prefix':values['grants.gsr']=contents(later('BASIS_WRITTEN'))['grants.gsr']
    elif name=='intent-leftover':put('source.capture.gsr',b'leftover source authority')
    elif name=='selected-early':values['grants.gsr']=contents(later('SELECTED_WRITTEN'))['grants.gsr']
    elif name=='selected-missing':put('grants.gsr',b'')
    elif name=='generation-precreated':values[generation()]=dict(directory=True)
    elif name=='manifest-substitution':put(generation()+'/generation.gsr',b'foreign generation')
    elif name=='member-missing':values.pop(next(k for k in values if k.startswith(generation()+'/') and not k.endswith('/generation.gsr')))
    elif name=='selector-early-rename':values['selector.gsr']=values.pop('selector.pending.gsr')
    elif name=='selector-candidate-leftover':values['selector.pending.gsr']=values['selector.gsr']
    elif name=='retention-substitution':put(model.LEDGER,b'foreign selected ledger')
    elif name=='outside-campaign':put('pending.accept',b'foreign carried vote')
    value['files']=[dict(name=k,identity=v) for k,v in sorted(values.items())];path.write_bytes(f.canonical(value))
    used={entry['identity']['sha256'] for p in directory.glob('capture-*.json')
          for entry in shared.g.json_file(p)[1]['files'] if 'sha256' in entry['identity']}
    for p in objects.iterdir():
        if p.name not in used:p.unlink()
    _,header=shared.g.json_file(header_path)
    header['storedBytes']=sum(p.stat().st_size for p in directory.rglob('*') if p.is_file() and p!=header_path)
    header_path.write_bytes(f.canonical(header))


def qualify(root):
    root=Path(root);original=validate(root);before=collection.inventory(root);expected=plans(root/'maintenance/prefixes/observed');results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-carried-campaign-negative-') as temp:
            changed=Path(temp)/'campaigns';shutil.copytree(root/'campaigns',changed);mutate(changed,name)
            try:replay(root/'maintenance/prefixes/observed',changed,expected)
            except ValueError as error:need(str(error)==reason,'carried campaign unrelated negative: '+name+': '+str(error))
            else:raise ValueError('carried campaign mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
        print(json.dumps(dict(case=name,completed=len(results),total=len(NEGATIVES))),file=sys.stderr,flush=True)
    need(collection.inventory(root)==before,'carried campaign qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True,mutatedPrerequisiteReplayed=False,
        negativePrecondition='full original retirement/resource/process/storage replay; expected campaign bytes derived from unchanged originals')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))
