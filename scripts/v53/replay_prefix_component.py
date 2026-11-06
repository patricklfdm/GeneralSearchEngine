"""Short real-writer component replay; complete snapshots are conditional inputs.

Unlike native_carried_replay_prefixes this does not admit a protocol history.
It checks the collector/model against real writes without a long process run.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import native_carried_replay_prefixes as p
from . import native_carried_transition_physical as physical


def validate(root,sidecar=None):
    root=Path(root);sidecar=root/'captures' if sidecar is None else Path(sidecar)
    original=p.collection.inventory(root);result=p.shared.g.json_file(root/'result.json')[1]
    p.need(set(result)=={'schema','at','pid','root','protocolAuthority','nativeCarriedProcess'} and
           result['schema']=='gse-v53-replay-prefix-component-v1' and type(result['at']) is int and result['at'] in (5,6) and
           result['protocolAuthority']=='conditional-initial-history' and result['nativeCarriedProcess'] is False,'replay component scope')
    p.need({v.name for v in root.iterdir()}=={'captures','events.json','result.json','before','applied','boundaries.json','resources.json'},
           'replay component inventory')
    raw=(root/'events.json').read_bytes();events=json.loads(raw);header=p.shared.g.json_file(sidecar/'collection.json')[1]
    p.need(set(header)=={'schema','root','life','pid','terminal','eventsSha256','captures','storedBytes'} and header['schema']==p.SCHEMA and
           header['root']==result['root'] and type(header['pid']) is int and type(result['pid']) is int and
           header['pid']==result['pid'] and type(header['life']) is int and header['life']==2 and
           header['terminal']=='CLOSED' and header['eventsSha256']==p.shared.sha(raw),'replay component original header')
    before=physical.c.inventory(root/'before');applied=physical.c.inventory(root/'applied')
    p.need(all(type(row) is dict and set(row)=={'node','event'} and row['node']=='node-1' and type(row['event']) is str for row in events),
           'replay component callback owner')
    physical.f.decode(before['root.gsr'],'records','ROOT')
    p.need(before['root.gsr'][16:48].hex()==result['root'],'replay component original root')
    initial=physical.c.current(before)[2]['capsule']
    final=physical.f.decode(applied['applied-end/catalog.gsr'],'records','CATALOG')
    p.need(initial['root']==final['root']==result['root'] and initial['cut']['index']==result['at'] and
           final['cut']['index']==result['at']+1,'replay component original cut')
    copies,_=p.shared.collect_contents(sidecar,events,header,1,
        lambda node:{key:before[key] for key in ('root.gsr','node.gsr')},
        p.collection.inventory(sidecar),schema=p.CAPTURE_SCHEMA,kinds=p.KINDS)
    plan=p.model.transaction(before,applied)
    observed=[(at,'replay',row) for at,row in enumerate(events) if row['event'].startswith('REPLAY_')]
    p.need(len(plan)==len(observed) and copies.keys()=={at for at,_,_ in observed},'replay component complete coverage')
    for (at,kind,row),(wanted,point,state) in zip(observed,plan):
        p.need((kind,row['event'])==(wanted,point),'replay component original write order')
        captured=copies[at]
        p.need(captured['node']=='node-1' and (captured['kind'],captured['point'])==(wanted,point),'replay component capture binding')
        p.need(p.model.physical(captured['files'])==state,'carried prefix exact original state: '+point)
    _,trace=p.binding.r.read(root/'resources.json')
    boundaries=p.shared.g.json_file(root/'boundaries.json')[1]
    resources=p.binding.bind(trace,events,boundaries,'node-1',closed=True)
    p.need(resources['callbacks']==len(plan),'replay component complete resource binding')
    p.need(p.collection.inventory(root)==original,'replay component original changed')
    return dict(status='PASS',at=result['at'],capturedPrefixes=len(plan),resources=resources,protocolAuthority='conditional-initial-history',
                expectedBytes='conditional-original-certificate-and-input-image',nativeCarriedProcess=False)


def qualify(root):
    root=Path(root);original=validate(root);before=p.collection.inventory(root);negatives=[]
    for name in p.PHYSICAL:
        with tempfile.TemporaryDirectory(prefix='v53-replay-component-negative-') as temp:
            changed=Path(temp);shutil.copytree(root/'captures',changed/'life-2');p.mutate(changed,name)
            try:validate(root,changed/'life-2')
            except ValueError as error:p.need(str(error)==p.NEGATIVES[name],'replay component unrelated negative: '+name+': '+str(error))
            else:raise ValueError('replay component accepted mutation: '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=p.NEGATIVES[name]))
    p.need(before==p.collection.inventory(root),'replay component negative changed original')
    return dict(original=original,negatives=negatives,originalStorageUnchanged=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))
