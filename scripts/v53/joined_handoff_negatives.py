"""Original-first handoff mutations; original physical files remain unchanged."""
import argparse
import copy
import json
from pathlib import Path
import sys

from . import joined_handoff_resources as r
from . import native_resource_evidence as native
from .floor_resource_negatives import recount

NEGATIVES = {
    'predecessor-byte-short': 'joined resources exact predecessor extents',
    'custody-owner-alias': 'joined resources exact custody extents',
    'native-byte-short': 'joined resources exact native extents',
    'native-image-owner': 'joined resources exact native extents',
    'missing-custody-force': 'joined resources original custody force order',
    'missing-custody-parent-force': 'joined resources original custody force order',
    'custody-before-force': 'joined resources atomic transfer after force',
    'native-before-force': 'joined resources continuous predecessor ownership',
    'predecessor-lifetime-gap': 'joined resources continuous predecessor ownership',
    'native-lifetime-gap': 'joined resources native ownership through open',
    'split-native-replacement': 'joined resources atomic replace after force',
    'missing-force': 'joined resources unique original lifecycle point',
    'foreign-force-owner': 'joined resources unique original lifecycle point',
    'reordered-force': 'joined resources force and handoff order',
    'missing-deletion': 'joined resources exact original deletion window',
    'missing-delete-force': 'joined resources exact original deletion window',
    'missing-completion-force': 'joined resources exact original deletion window',
    'deletion-before-decision': 'joined resources exact original deletion window',
    'hidden-replacement': 'joined resources unbound storage handoff',
}


def mutate(data, name):
    plan, events, traces, boundaries = data
    r.need(name in NEGATIVES, 'joined resources declared mutation')
    node=plan['node']; rows=traces[node]['changes']; points=r.positions(events,node)
    seq=[boundaries[i]['sequence'] for i in points]
    def insert(at, changes):
        rows[at:at]=changes
        for b in boundaries:
            if b['node']==node and b['sequence']>=at:b['sequence']+=len(changes)
    def adjust(key, action):
        for row in rows:
            for value in row['removed']+row['added']:
                if r.t.key(value)==key:action(value)
    if name in ('predecessor-byte-short','native-byte-short','native-image-owner','custody-owner-alias'):
        row=rows[seq[1]] if name.startswith(('predecessor','custody')) else rows[seq[7]]
        values=row['removed'] if name.startswith('predecessor') else row['added']
        if name=='predecessor-byte-short':
            value=next(v for v in values if v['owner']=='learner-voter-stage')
            counterpart=next(v for v in row['added'] if v['unit']==value['unit'] and v['bytes']==value['bytes'])
            keys=(r.t.key(value),r.t.key(counterpart))
            for key in keys:adjust(key,lambda v:v.update(bytes=v['bytes']-1))
        else:
            value=next(v for v in values if v['unit']==('APPLICATION' if name=='native-image-owner' else 'GENERATION'))
            adjust(r.t.key(value), (lambda v:v.update(owner=v['owner']+'-foreign')) if 'owner' in name else
                   (lambda v:v.update(bytes=v['bytes']-1)))
    elif name=='custody-before-force':
        for i,v in enumerate(events):
            if v.get('scope')=='custody':boundaries[i]['sequence']=seq[1]
    elif name=='native-before-force':boundaries[points[6]]['sequence']=seq[7]
    elif name.endswith('lifetime-gap'):
        at=seq[1] if name.startswith('predecessor') else seq[7]
        value=copy.deepcopy(rows[at]['added'][0])
        insert(at+1,[dict(event='RELEASE',removed=[value],added=[]),dict(event='RESERVE',removed=[],added=[value])])
        # Later callbacks see restored totals; only the complete mutation
        # history reveals the gap. The first callback stays before release.
        after=points[1] if name.startswith('predecessor') else points[7]
        for i,b in enumerate(boundaries):
            if i>after and b['node']==node and b['sequence']==at:b['sequence']=at+2
    elif name=='split-native-replacement':
        row=rows[seq[7]]; old=copy.deepcopy(row['removed']); new=copy.deepcopy(row['added'])
        replacement=[dict(event='RELEASE',removed=[v],added=[]) for v in old]
        replacement += [dict(event='RESERVE',removed=[],added=[v]) for v in new]
        rows[seq[7]:seq[7]+1]=replacement
        for b in boundaries:
            if b['node']==node and b['sequence']>=seq[7]:b['sequence']+=len(replacement)-1
    elif name=='missing-force':events[points[6]]['event']='UNOBSERVED_FORCE'
    elif name in ('missing-custody-force','missing-custody-parent-force'):
        point='LEARNER_CUSTODY_'+('FORCED' if name=='missing-custody-force' else 'PARENT_FORCED')
        next(v for v in events if v['node']==node and v['event']==point)['event']='UNOBSERVED_CUSTODY_FORCE'
    elif name=='foreign-force-owner':events[points[6]]['node']='foreign-node'
    elif name=='reordered-force':events[points[5]],events[points[6]]=events[points[6]],events[points[5]]
    elif name in ('missing-deletion','missing-delete-force','missing-completion-force'):
        point={'missing-deletion':'DELETED:0','missing-delete-force':'DELETE_FORCED:0',
               'missing-completion-force':'FORCED:retired.json'}[name]
        next(v for v in events if v['node']==node and v['event']=='JOINED_RETIREMENT_'+point)['event']='MISSING_DELETE'
    elif name=='deletion-before-decision':
        at=next(i for i,v in enumerate(events) if v['node']==node and v['event']=='JOINED_RETIREMENT_BEFORE_DELETE:0')
        events[at],events[points[3]]=events[points[3]],events[at]
    elif name=='hidden-replacement':rows.append(dict(event='REPLACE',removed=[],added=[]))
    recount(traces,boundaries)


def replay(data, progress=None):
    r.replay(*data); results=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(data);mutate(changed,name)
        try:r.replay(*changed)
        except ValueError as error:
            r.need(str(error)==reason, 'joined resources unrelated rejection: '+name+': '+str(error))
        else:raise ValueError('joined resources accepted mutation: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
        if progress:progress(dict(stage='handoff-negatives',case=name,completed=len(results),total=len(NEGATIVES)))
    return results


def qualify(root, progress=None):
    root=Path(root);before=native.collection.inventory(root)
    original=native.validate(root,'5-REPLACE-required-four',progress)
    if progress:progress(dict(stage='original',status='PASS'))
    _,traces,boundaries,events=native.load(root)
    data=(r.derive(root),events,traces,boundaries)
    result=replay(data,progress)
    r.need(native.collection.inventory(root)==before,'joined resources qualification changed original')
    return dict(status='PASS',original=original,negatives=result,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');a=p.parse_args()
    progress=lambda row:print(json.dumps(row,sort_keys=True),file=sys.stderr,flush=True)
    print(json.dumps(qualify(a.root,progress),sort_keys=True))
