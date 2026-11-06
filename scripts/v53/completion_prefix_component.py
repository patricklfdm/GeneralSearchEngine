"""Short real-writer component replay; complete snapshots are conditional inputs.

Unlike native_carried_completion_prefixes this does not admit a protocol history.
It checks the collector/model against real writes without a long process run.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import native_carried_completion_prefixes as p
from . import native_carried_transition_physical as physical


def validate(root,sidecar=None):
    root=Path(root);sidecar=root/'captures' if sidecar is None else Path(sidecar)
    original=p.collection.inventory(root);result=p.shared.g.json_file(root/'result.json')[1]
    p.need(set(result)=={'schema','at','pid','root','protocolAuthority','nativeCarriedProcess'} and
           result['schema']=='gse-v53-completion-prefix-component-v1' and type(result['at']) is int and result['at'] in (0,5,6) and
           result['protocolAuthority']=='conditional-initial-history' and result['nativeCarriedProcess'] is False,'completion component scope')
    p.need({v.name for v in root.iterdir()}=={'captures','events.json','result.json','before','applied','published'},
           'completion component inventory')
    raw=(root/'events.json').read_bytes();events=json.loads(raw);header=p.shared.g.json_file(sidecar/'collection.json')[1]
    p.need(set(header)=={'schema','root','life','pid','terminal','eventsSha256','captures','storedBytes'} and header['schema']==p.SCHEMA and
           header['root']==result['root'] and type(header['pid']) is int and type(result['pid']) is int and
           header['pid']==result['pid'] and type(header['life']) is int and header['life']==2 and
           header['terminal']=='CLOSED' and header['eventsSha256']==p.shared.sha(raw),'completion component original header')
    before=physical.c.inventory(root/'before');applied=physical.c.inventory(root/'applied');published=physical.c.inventory(root/'published')
    p.need(all(type(row) is dict and set(row)=={'node','event'} and row['node']=='node-1' and type(row['event']) is str for row in events),
           'completion component callback owner')
    physical.f.decode(before['root.gsr'],'records','ROOT')
    p.need(before['root.gsr'][16:48].hex()==result['root'],'completion component original root')
    initial=physical.c.current(before)[2]['capsule'];final=physical.c.current(published)[2]['capsule']
    p.need(initial['root']==final['root']==result['root'] and initial['cut']['index']==result['at'] and
           final['cut']['index']==result['at']+1,'completion component original cut')
    copies,_=p.shared.collect_contents(sidecar,events,header,1,
        lambda node:{key:before[key] for key in ('root.gsr','node.gsr')},
        p.collection.inventory(sidecar),schema=p.CAPTURE_SCHEMA,kinds=p.KINDS)
    plan=p.model.application(before,applied)+p.model.publication(applied,published)
    observed=p.model.observed(events)
    p.need(len(plan)==len(observed) and copies.keys()=={at for at,_,_ in observed},'completion component complete coverage')
    for (at,kind,row),(wanted,point,state) in zip(observed,plan):
        p.need((kind,row['event'])==(wanted,point),'completion component original write order')
        captured=copies[at]
        p.need(captured['node']=='node-1' and (captured['kind'],captured['point'])==(wanted,point),'completion component capture binding')
        p.need(p.model.physical(captured['files'])==state,'carried prefix exact original state: '+point)
    p.need(p.collection.inventory(root)==original,'completion component original changed')
    return dict(status='PASS',at=result['at'],capturedPrefixes=len(plan),protocolAuthority='conditional-initial-history',
                expectedBytes='conditional-complete-snapshots',nativeCarriedProcess=False)


def qualify(root):
    root=Path(root);original=validate(root);before=p.collection.inventory(root);negatives=[]
    for name in p.PHYSICAL:
        with tempfile.TemporaryDirectory(prefix='v53-completion-component-negative-') as temp:
            changed=Path(temp);shutil.copytree(root/'captures',changed/'life-2');p.mutate(changed,name)
            try:validate(root,changed/'life-2')
            except ValueError as error:p.need(str(error)==p.NEGATIVES[name],'completion component unrelated negative: '+name+': '+str(error))
            else:raise ValueError('completion component accepted mutation: '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=p.NEGATIVES[name]))
    p.need(before==p.collection.inventory(root),'completion component negative changed original')
    return dict(original=original,negatives=negatives,originalStorageUnchanged=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))
