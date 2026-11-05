"""Original-first persistent source accounting mutations with exact rejection reasons."""
import argparse
import copy
import json
from pathlib import Path
import sys

from . import basis_resource_evidence as r, native_resource_evidence as native
from .floor_resource_negatives import recount

NEGATIVES={
    'packet-short':'basis resources exact original source extent',
    'packet-long':'basis resources exact original source extent',
    'image-short':'basis resources exact original source extent',
    'image-long':'basis resources exact original source extent',
    'source-category':'basis resources original source category',
    'source-identity':'basis resources complete source reservation inventory',
    'image-digest-owner':'basis resources unbound source image',
    'reserve-before-capture':'basis resources continuous original owner lifetime',
    'reserve-after-create':'basis resources continuous original owner lifetime',
    'release-before-deletion':'basis resources continuous original owner lifetime',
    'retain-after-clear':'basis resources exact release interval',
    'reopen-before-force':'basis resources continuous original owner lifetime',
    'reopen-after-ready':'basis resources continuous original owner lifetime',
    'source-lifetime-gap':'basis resources exact owner lifetime count',
    'image-lifetime-gap':'basis resources exact owner lifetime count',
    'hidden-owner-reopen':'basis resources exact owner lifetime count',
    'unbound-temporary-image':'basis resources unbound source image',
}


def mutate(data,name):
    plans,events,traces,boundaries=data;r.need(name in NEGATIVES,'basis resources declared negative')
    plan=next(v for v in plans if len(v['segments'])>1) if name.startswith(('reopen-','hidden-')) else next(v for v in plans if v['retired'])
    unit='APPLICATION' if name.startswith('image-') else 'SOURCE'
    key=next(k for k in plan['extents'] if k[0]==unit);node=plan['node'];changes=traces[node]['changes']
    lives=r.lives(traces,plans)[node,key[1]];lease=lives[1] if name.startswith('reopen-') else lives[-1]
    segment=plan['segments'][1] if name.startswith('reopen-') else plan['segments'][-1]
    def at(point,sequence):boundaries[point]['sequence']=sequence
    if name in ('packet-short','packet-long','image-short','image-long','source-category','source-identity','image-digest-owner'):
        for row in changes:
            for charge in row['removed']+row['added']:
                if r.t.key(charge)!=key:continue
                if name.endswith('short'):charge['bytes']-=1
                elif name.endswith('long'):charge['bytes']+=1
                elif name=='source-category':charge['unit']='LEARNER'
                elif name=='source-identity':charge['owner']='foreign-original-source'
                else:charge['owner']=plan['id']+':'+('0'*64 if not key[1].endswith('0'*64) else '1'*64)
    elif name=='reserve-before-capture':at(segment['reserveAfter'],lease['start'])
    elif name=='reserve-after-create':at(segment['reserveBy'],lease['start']-1)
    elif name=='release-before-deletion':at(segment['liveThrough'],lease['end'])
    elif name=='retain-after-clear':at(segment['releaseBy'],lease['end']-1)
    elif name=='reopen-before-force':at(segment['reserveAfter'],lease['start'])
    elif name=='reopen-after-ready':at(segment['reserveBy'],lease['start']-1)
    elif name.endswith('lifetime-gap'):
        seq=lease['start'];value=copy.deepcopy(changes[seq]['added'][0])
        changes[seq+1:seq+1]=[dict(event='RELEASE',removed=[value],added=[]),dict(event='RESERVE',removed=[],added=[value])]
        for point in boundaries:
            if point['node']==node and point['sequence']>seq:point['sequence']+=2
    elif name=='hidden-owner-reopen':
        removed={lives[0]['end'],lives[1]['start']};changes[:]=[v for i,v in enumerate(changes) if i not in removed]
        for point in boundaries:
            if point['node']==node:point['sequence']-=sum(v<=point['sequence'] for v in removed)
    elif name=='unbound-temporary-image':
        value=dict(unit='APPLICATION',owner='00000000-0000-0000-0000-000000000001:'+64*'0',bytes=1,claimSource='')
        r.need(all(value['owner']!=k[1] for p in plans for k in p['extents']),'basis resources negative owner collision')
        changes.extend([dict(event='RESERVE',removed=[],added=[value]),dict(event='RELEASE',removed=[value],added=[])])
    recount(traces,boundaries)


def replay(data,progress=None):
    r.replay(*data);results=[]
    for name,reason in NEGATIVES.items():
        changed=(*data[:2],*copy.deepcopy(data[2:]));mutate(changed,name)
        try:r.replay(*changed)
        except ValueError as error:r.need(str(error)==reason,'basis resources unrelated negative: '+name+': '+str(error))
        else:raise ValueError('basis resources mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
        if progress:progress(dict(case=name,completed=len(results),total=len(NEGATIVES)))
    return results


def qualify(root,progress=None):
    root=Path(root);before=native.collection.inventory(root)
    original=native.validate(root,'5-REPLACE-required-four',progress)
    if progress:progress(dict(stage='original',status='PASS'))
    _,traces,boundaries,events=native.load(root)
    reader=r.maintenance.Replay(root);reader.run()
    results=replay((r.derive(reader),events,traces,boundaries),progress)
    r.need(native.collection.inventory(root)==before,'basis resources qualification changed original')
    return dict(status='PASS',original=original,negatives=results,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');a=p.parse_args()
    progress=lambda row:print(json.dumps(row,sort_keys=True),file=sys.stderr,flush=True)
    print(json.dumps(qualify(a.root,progress),sort_keys=True))
