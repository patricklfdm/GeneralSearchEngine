"""Original-first, coherent floor accounting mutations; physical bytes stay fixed."""
import argparse
import copy
import json
from pathlib import Path
import sys

from . import floor_resource_evidence as r
from . import native_resource_evidence as native

NEGATIVES={
    'copy-metadata-short':'floor resources exact live copy extents',
    'copy-metadata-long':'floor resources exact live copy extents',
    'copy-image-short':'floor resources exact live copy extents',
    'copy-image-long':'floor resources exact live copy extents',
    'copy-owner':'floor resources exact live copy extents',
    'image-ordinal':'floor resources exact live copy extents',
    'copy-lifetime-gap':'floor resources complete copy release interval',
    'pin-metadata-short':'floor resources continuous original pin coverage',
    'pin-owner':'floor resources continuous original pin coverage',
    'pin-lifetime-gap':'floor resources continuous original pin coverage',
    'unbound-temporary-copy':'floor resources unbound copy reservation',
}


def recount(traces,boundaries):
    for value in traces.values():
        state={};limits=tuple(value[k] for k in ('metadataLimit','stagingLimit','queueLimit'))
        for seq,row in enumerate(value['changes']):
            row['sequence']=seq
            for v in row['removed']:state.pop(r.t.key(v))
            for v in row['added']:state[r.t.key(v)]=v
            for field in ('removed','added'):row[field].sort(key=r.t.order_key)
            row['usage']=r.t.usage(state,limits)
        value['transitions']=len(value['changes']);value['current']=copy.deepcopy(value['changes'][-1]['usage'])
    for point in boundaries:point['usage']=copy.deepcopy(traces[point['node']]['changes'][point['sequence']]['usage'])


def mutate(data,name):
    floors,events,traces,boundaries=data
    r.need(name in NEGATIVES,'floor resources declared negative')
    floor=next(v for v in floors if v['pin']) if name.startswith('pin-') else next(v for v in floors if v['network'])
    node=floor['node'];rows=traces[node]['changes']
    required=floor['pin'] if name.startswith('pin-') else floor['copies'][0]
    unit='APPLICATION' if 'image' in name else 'GENERATION' if name.startswith('pin-') else 'SOURCE'
    key=next(k for k in required if k[0]==unit)
    if name=='unbound-temporary-copy':
        value=dict(unit='SOURCE',owner='floor:unbound',bytes=1,claimSource='')
        rows.extend([dict(event='RESERVE',removed=[],added=[value]),dict(event='RELEASE',removed=[value],added=[])])
    elif name.endswith('lifetime-gap'):
        seq=boundaries[floor['start']]['sequence'];state={}
        for row in rows[:seq+1]:
            for value in row['removed']:state.pop(r.t.key(value))
            for value in row['added']:state[r.t.key(value)]=value
        value=state[key]
        rows[seq+1:seq+1]=[dict(event='RELEASE',removed=[value],added=[]),dict(event='RESERVE',removed=[],added=[value])]
        for point in boundaries:
            if point['node']==node and point['sequence']>seq:point['sequence']+=2
    else:
        for row in rows:
            for value in row['removed']+row['added']:
                if r.t.key(value)!=key:continue
                if name.endswith('short'):value['bytes']-=1
                elif name.endswith('long'):value['bytes']+=1
                else:value['owner']+=':wrong'
    recount(traces,boundaries)


def replay(data,progress=None):
    r.replay(*data);results=[]
    for name,reason in NEGATIVES.items():
        # Original floor authority and events are never mutated. Only the
        # collected journals/checkpoints are copied and coherently forged.
        changed=(*data[:2],*copy.deepcopy(data[2:]));mutate(changed,name)
        try:r.replay(*changed)
        except ValueError as error:r.need(str(error)==reason,'floor resources unrelated negative: '+name+': '+str(error))
        else:raise ValueError('floor resources mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
        if progress:progress(dict(case=name,completed=len(results),total=len(NEGATIVES)))
    return results


def qualify(root,progress=None):
    root=Path(root);before=native.collection.inventory(root)
    original=native.validate(root,'5-REPLACE-required-four',progress)
    if progress:progress(dict(stage='original',status='PASS'))
    _,traces,boundaries,events=native.load(root)
    reader=r.maintenance.Replay(root);reader.run()
    result=replay((r.plans(reader),events,traces,boundaries),progress)
    r.need(native.collection.inventory(root)==before,'floor resources qualification changed original')
    return dict(original=original,negatives=result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');args=parser.parse_args()
    progress=lambda row:print(json.dumps(row,sort_keys=True),file=sys.stderr,flush=True)
    print(json.dumps(qualify(args.root,progress),sort_keys=True))
