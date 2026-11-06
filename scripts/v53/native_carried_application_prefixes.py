"""Original application-file prefixes ending at a declared ACK-force crash.

The complete application storage/protocol/resource history must pass first.
Expected bytes come from that original, never from the captured sidecar.
This does not qualify recovery's retirement or the other transient families.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import native_carried_application_resources as original
from . import native_carried_completion_prefixes as completion

resources=original.resources;model=completion.model;shared=completion.shared
collection=original.collection;need=original.need;f=resources.f
SCHEMA='gse-v53-carried-application-cut-capture-v1'
CUT='APPLY_ACK_DIRECTORY_FORCED'
KINDS={'application':('APPLY_',)}


def plans(root):
    root=Path(root);directory=root/'resources/life-1'
    index=resources.read(directory,'index.json',16384)
    events=resources.linked(directory,index,'events.json','eventsSha256',32*shared.g.MIB)
    observed=model.observed(events,interrupted_application='node-1')
    end=resources.c.inventory(root/'history/at-cut/node-1')
    initial={k:v for k,v in end.items() if k!='applied-end' and not k.startswith('applied-end/')}
    expected=model.application(initial,end,stop=CUT)
    need(len(observed)==len(expected) and all(row.get('node')=='node-1' and
         (kind,row['event'])==(want,point) for (at,kind,row),(want,point,state) in zip(observed,expected)),
         'application capture exact original write order')
    return [dict(eventIndex=at,node='node-1',kind=kind,point=point,files=state)
            for (at,kind,row),(_,point,state) in zip(observed,expected)]


def replay(root,sidecar,expected=None):
    root,sidecar=Path(root),Path(sidecar);directory=root/'resources/life-1'
    index=resources.read(directory,'index.json',16384)
    inventory=collection.inventory(sidecar,maximum=shared.g.MAXIMUM_BYTES+4096)
    _,header=shared.g.json_file(sidecar/'collection.json')
    fields={'schema','root','life','pid','terminal','eventsSha256','captures','storedBytes','interrupted'}
    need(type(header) is dict and set(header)==fields and header['schema']==SCHEMA and
         type(header['life']) is int and header['life']==1 and type(header['pid']) is int and
         header['terminal']=='CUT_PREFIX' and all(f.canonical(header[k])==f.canonical(index[k])
         for k in ('root','life','pid','terminal','eventsSha256')),'application capture original lifetime binding')
    events=resources.linked(directory,index,'events.json','eventsSha256',32*shared.g.MIB)
    need(events and events[-1].get('node')=='node-1' and events[-1]['event']==CUT and
         f.canonical(header['interrupted'])==f.canonical(dict(node='node-1',point=CUT,eventIndex=len(events)-1)),
         'application capture exact interrupted boundary')
    expected=plans(root) if expected is None else expected
    events=[{k:v for k,v in row.items() if k!='incarnation'} for row in events]
    copies,_=shared.collect_contents(sidecar,events,header,4,
        lambda node:{key:collection.snapshot.s.regular(root/'history/before-network'/node/key,16384)
                     for key in ('root.gsr','node.gsr')},inventory,schema=completion.CAPTURE_SCHEMA,kinds=KINDS)
    need(expected and len({v['eventIndex'] for v in expected})==len(expected) and
         copies.keys()=={v['eventIndex'] for v in expected},'application capture complete callback coverage')
    for row in expected:
        captured=copies[row['eventIndex']]
        need(all(captured[k]==row[k] for k in ('node','kind','point')),'application capture original transaction binding')
        need(model.physical(captured['files'])==row['files'],'application capture exact original state: '+row['point'])
    need(collection.inventory(sidecar,maximum=shared.g.MAXIMUM_BYTES+4096)==inventory,'application capture sidecar changed')
    return dict(status='PARTIAL',life=1,pid=header['pid'],terminal='CUT_PREFIX',capturedPrefixes=len(expected),
        interruptedApplicationBytesQualified=True,postCutTailObserved=False,recoveryTransientBytesQualified=False,
        fullTransientBytesQualified=False,wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)


def validate(root):
    root=Path(root);before=collection.inventory(root)
    need({v.name for v in root.iterdir()}=={'observed','application'},'application capture exact wrapper inventory')
    prerequisite=original.validate(root/'observed')
    result=replay(root/'observed',root/'application')
    need(collection.inventory(root)==before,'application capture original changed')
    return dict(status='PARTIAL',original=prerequisite,application=result,phase3Complete=False)


NEGATIVES={name:shared.NEGATIVES[name] for name in ('missing-copy','duplicate-index','wrong-callback',
    'missing-object','altered-object','extra-object','boolean-size','wrong-owner')}
HEADER={'process-pid':'pid','process-life':'life','process-root':'root','process-terminal':'terminal',
        'process-events':'eventsSha256','boolean-pid':'pid','ordinary-schema':'schema'}
NEGATIVES.update({name:'application capture original lifetime binding' for name in HEADER})
BOUNDARY={'boundary-owner':'node','boundary-point':'point','boundary-index':'eventIndex','boolean-index':'eventIndex'}
NEGATIVES.update({name:'application capture exact interrupted boundary' for name in BOUNDARY})
NEGATIVES['missing-callback']='application capture complete callback coverage'
PHYSICAL={name:completion.PHYSICAL[name] for name in ('application-nonempty-create','application-complete-prefix',
    'application-early-ack','application-outside-end')}
NEGATIVES.update({name:'application capture exact original state: '+point for name,(point,_) in PHYSICAL.items()})


def mutate(sidecar,name):
    sidecar=Path(sidecar);need(name in NEGATIVES,'application capture unknown negative')
    if name in HEADER or name in BOUNDARY:
        path=sidecar/'collection.json';_,header=shared.g.json_file(path)
        if name in HEADER:
            key=HEADER[name]
            header[key]=(True if name=='boolean-pid' else header[key]+1 if key in ('life','pid') else
                         'CLOSED' if key=='terminal' else completion.SCHEMA if key=='schema' else '0'*64)
        else:
            key=BOUNDARY[name];header['interrupted'][key]=(True if name=='boolean-index' else
                header['interrupted'][key]-1 if key=='eventIndex' else 'node-2' if key=='node' else 'APPLY_BEFORE_RETURN')
        path.write_bytes(f.canonical(header));return
    # The existing mutations operate on a life-2 directory. A temporary outer
    # wrapper reuses them without changing any original process/lifetime bytes.
    if name in PHYSICAL or name=='missing-callback':
        with tempfile.TemporaryDirectory(prefix='v53-application-mutation-') as temporary:
            outer=Path(temporary);shutil.copytree(sidecar,outer/'life-2');completion.mutate(outer,name)
            shutil.rmtree(sidecar);shutil.copytree(outer/'life-2',sidecar)
    else:shared.mutate(sidecar,name)


def qualify(root):
    root=Path(root);result=validate(root);before=collection.inventory(root)
    expected=plans(root/'observed');negatives=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-application-prefix-negative-') as temporary:
            changed=Path(temporary)/'application';shutil.copytree(root/'application',changed);mutate(changed,name)
            try:replay(root/'observed',changed,expected)
            except ValueError as error:need(str(error)==reason,'application capture unrelated negative: '+name+': '+str(error))
            else:raise ValueError('application capture accepted negative: '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
        print(json.dumps(dict(stage='application-prefix-negative',case=name,completed=len(negatives),total=len(NEGATIVES))),file=sys.stderr,flush=True)
    need(collection.inventory(root)==before,'application capture qualification changed original')
    return dict(original=result,negatives=negatives,originalStorageUnchanged=True,mutatedPrerequisiteReplayed=False,
        negativePrecondition='complete original application protocol/storage/resource chain; unchanged original derived write plan')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true')
    args=parser.parse_args();print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))
