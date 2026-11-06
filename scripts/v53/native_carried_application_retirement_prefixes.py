"""Bind recovered old-end retirement captures to one original two-JVM history."""
import argparse
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
from . import native_carried_application_prefixes as prerequisite
from . import native_carried_application_protocol as protocol
from . import native_application_retirement_files as model
from . import native_carried_retirement_prefixes as r

need=r.need;f=r.f;collection=r.collection;shared=r.shared
SCHEMA='gse-v53-carried-process-application-retirement-capture-v1'
CAPTURE_SCHEMA='gse-v53-carried-application-retirement-capture-v1'


def bind_plan(events,before):
    starts=[i for i,v in enumerate(events) if v['event']=='ROUND_SLOT_BEGIN']
    stops=[i for i,v in enumerate(events) if v['event']=='ROUND_SLOT_COMPLETE']
    need(starts and stops and starts[0]<stops[0],'application retirement original first slot')
    rows=events[starts[0]+1:stops[0]];remaining,cleaned=protocol.retired(rows,before)
    kept={id(row) for row in remaining};consumed={id(row) for row in rows if id(row) not in kept}
    positions={id(row):at for at,row in enumerate(events)};result=[]
    for node,files in before.items():
        if 'applied-end' not in files:continue
        expected=model.transaction(files)
        actual=[row for row in rows if id(row) in consumed and row.get('node')==node]
        need(len(expected)==len(actual) and all(row['event']==point for row,(_,point,_) in zip(actual,expected)),
             'application retirement complete original transaction')
        for row,(kind,point,state) in zip(actual,expected):
            result.append(dict(life=2,eventIndex=positions[id(row)],node=node,kind=kind,point=point,files=state))
        need(expected[-1][2]==model.physical(cleaned[node]),'application retirement original final projection')
    actual=[row['eventIndex'] for row in result]
    need(result and len(actual)==len(set(actual)) and set(actual)=={positions[key] for key in consumed} and
         {i for i,v in enumerate(events) if v['event'].startswith(protocol.RETIREMENT)}==
         {v['eventIndex'] for v in result if v['point'].startswith(protocol.RETIREMENT)},
         'application retirement complete history coverage')
    return sorted(result,key=lambda row:row['eventIndex'])


def plans(observed):
    observed=Path(observed);directory=observed/'resources/life-2'
    index=prerequisite.resources.read(directory,'index.json',16384)
    events=prerequisite.resources.linked(directory,index,'events.json','eventsSha256',32*shared.g.MIB)
    before=protocol.forces.group(observed/'history','life-2-installed-1')
    return bind_plan(events,before)


def replay(observed,sidecar,expected=None):
    expected=plans(observed) if expected is None else expected
    need(expected and all(row['life']==2 for row in expected),'application retirement exact recovery lifetime')
    result=r.lifetime(Path(observed),Path(sidecar),2,expected,schema=SCHEMA,capture_schema=CAPTURE_SCHEMA,kinds=model.KINDS)
    return dict(status='PARTIAL',lifetime=result,retiredApplicationBytesQualified=True,
        postCutTailObserved=False,fullTransientBytesQualified=False,wholeRuntimeResourcesQualified=False,
        cohortAdmitted=False,phase3Complete=False)


def validate(root):
    root=Path(root);before=collection.inventory(root)
    need({v.name for v in root.iterdir()}=={'previous','retirement'},'application retirement wrapper inventory')
    original=prerequisite.validate(root/'previous')
    result=replay(root/'previous/observed',root/'retirement')
    need(collection.inventory(root)==before,'application retirement original changed')
    return dict(status='PARTIAL',original=original,retirement=result,phase3Complete=False)


NEGATIVES={name:r.NEGATIVES[name] for name in ('missing-copy','duplicate-index','wrong-callback','missing-object',
    'altered-object','extra-object','boolean-size','wrong-owner','process-pid','process-life','process-root',
    'process-terminal','process-events','boolean-pid','missing-callback')}
PHYSICAL={
    'certificate-lost':('CERTIFICATE_ACTIVE_FORCED','vote'),
    'selector-reverted':('NATIVE_RETIREMENT_CERTIFICATE_RETAINED','selector'),
    'retirement-nonempty-create':('SUPERSEDED_END_RETIREMENT_CREATED','nonempty'),
    'retirement-complete-prefix':('SUPERSEDED_END_RETIREMENT_PREFIX_WRITTEN','prefix'),
    'retirement-early-rename':('SUPERSEDED_END_RETIREMENT_PARENT_FORCED','rename'),
    'retirement-unbound-authority':('SUPERSEDED_END_AUTHORITY_FORCED','authority'),
    'retirement-early-ack-delete':('SUPERSEDED_END_VALIDATED','ack'),
    'retirement-early-plan-delete':('SUPERSEDED_END_BEFORE_DELETE','plan'),
    'retirement-kept-end':('SUPERSEDED_END_DIRECTORY_DELETED','directory'),
    'retirement-leftover-authority':('SUPERSEDED_END_RETIREMENT_DELETED','marker'),
    'retirement-new-selector-claim':('REPLAY_CLAIM_WRITTEN','claim'),
    'retirement-invented-output':('REPLAY_APPLICATION_FINISHED','output'),
    'retirement-leftover-scratch':('REPLAY_BEFORE_RETURN','scratch'),
    'retirement-final-vote-deleted':('STAGED_RETIREMENT_BEFORE_RETURN','vote'),
}
NEGATIVES.update({name:'carried prefix exact original state: '+point for name,(point,_) in PHYSICAL.items()})


def mutate(sidecar,name):
    sidecar=Path(sidecar);need(name in NEGATIVES,'application retirement unknown negative')
    if name not in PHYSICAL:
        with tempfile.TemporaryDirectory(prefix='v53-application-retirement-mutation-') as temporary:
            outer=Path(temporary);shutil.copytree(sidecar,outer/'life-2');r.mutate(outer,name)
            shutil.rmtree(sidecar);shutil.copytree(outer/'life-2',sidecar)
        return
    objects=sidecar/'objects';header_path=sidecar/'collection.json'
    copies=[(p,shared.g.json_file(p)[1]) for p in sorted(sidecar.glob('capture-*.json'))]
    point,change=PHYSICAL[name];path,value=next((p,v) for p,v in copies if v['point']==point)
    values={v['name']:v['identity'] for v in value['files']}
    def put(key,raw):
        digest=shared.sha(raw);(objects/digest).write_bytes(raw);values[key]=dict(size=len(raw),sha256=digest)
    def at(point,key):
        found=next(v for _,v in copies if v['node']==value['node'] and v['point']==point)
        return next(v['identity'] for v in found['files'] if v['name']==key)
    marker='applied-end/retirement.gsat'
    if change=='vote':del values['pending.accept']
    elif change=='selector':values['selector.gsr']=values['applied-end/selector.gsr']
    elif change=='nonempty':put(marker+'.next',b'unexpected prefix')
    elif change=='prefix':values[marker+'.next']=at('SUPERSEDED_END_RETIREMENT_WRITTEN',marker+'.next')
    elif change=='rename':values[marker]=values.pop(marker+'.next')
    elif change=='authority':
        raw=(objects/values[marker]['sha256']).read_bytes();body=json.loads(raw[48:]);body['authority']['selection']='0'*64
        encoded=f.canonical(body);header=struct.pack('>4sHHII',b'GSAT',1,3,0,len(encoded))
        put(marker,header+bytes.fromhex(shared.sha(header+encoded))+encoded)
    elif change=='ack':del values['applied-end/ack.gsr']
    elif change=='plan':del values['applied-end/plan.json']
    elif change=='directory':values['applied-end']=dict(directory=True)
    elif change=='marker':values[marker]=at('SUPERSEDED_END_AUTHORITY_FORCED',marker)
    elif change=='claim':
        key='application-replay/claim.json';body=json.loads((objects/values[key]['sha256']).read_bytes())
        body['selector']=values['selector.gsr']['sha256'];put(key,f.canonical(body))
    elif change=='output':values['application-replay/work/output']=dict(directory=True)
    elif change=='scratch':values['application-replay']=dict(directory=True)
    value['files']=[dict(name=k,identity=v) for k,v in sorted(values.items())];path.write_bytes(f.canonical(value))
    used={entry['identity']['sha256'] for p in sidecar.glob('capture-*.json')
          for entry in shared.g.json_file(p)[1]['files'] if 'sha256' in entry['identity']}
    for p in objects.iterdir():
        if p.name not in used:p.unlink()
    _,header=shared.g.json_file(header_path)
    header['storedBytes']=sum(p.stat().st_size for p in sidecar.rglob('*') if p.is_file() and p!=header_path)
    header_path.write_bytes(f.canonical(header))


def qualify(root):
    root=Path(root);original=validate(root);before=collection.inventory(root)
    observed=root/'previous/observed';expected=plans(observed);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-application-retirement-negative-') as temporary:
            changed=Path(temporary)/'retirement';shutil.copytree(root/'retirement',changed);mutate(changed,name)
            try:replay(observed,changed,expected)
            except ValueError as error:need(str(error)==reason,'application retirement unrelated negative: '+name+': '+str(error))
            else:raise ValueError('application retirement accepted negative: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
        print(json.dumps(dict(stage='application-retirement-negative',case=name,completed=len(results),total=len(NEGATIVES))),file=sys.stderr,flush=True)
    need(collection.inventory(root)==before,'application retirement qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True,mutatedPrerequisiteReplayed=False,
        negativePrecondition='complete original application/resource/interrupted-file chain; independent unchanged retirement plan')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true')
    args=parser.parse_args();print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))
