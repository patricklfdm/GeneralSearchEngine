"""Original-first negative replay of native resource/event observations."""
import argparse
import copy
import json
from pathlib import Path

from . import native_resource_evidence as evidence

NEGATIVES={
    'missing-owner':'native resources original complete identities',
    'foreign-identity':'native resources original complete identities',
    'foreign-root':'native resources original complete identities',
    'omitted-boundary':'native resources complete event boundaries',
    'duplicate-boundary':'native resources exact event sequence',
    'foreign-boundary-owner':'native resources exact event sequence',
    'outside-sequence':'native resources exact event sequence',
    'forged-boundary-usage':'resource transitions derived usage',
    'late-registration':'native resources exact event sequence',
    'widened-limit':'native resources original limits',
    'truncated-journal':'resource transitions incomplete observation',
    'failed-journal':'resource transitions incomplete observation',
    'missing-transition':'resource transitions exact event sequence',
    'foreign-release':'resource transitions original removed charge',
    'live-close':'resource transitions outstanding charges at close',
}


def mutate(data,name):
    index,traces,boundaries,events=data;node=index['owners'][0]['identity']['node']
    trace=traces[node]
    if name=='missing-owner':index['owners'].pop();return
    if name=='foreign-identity':index['owners'][0]['identity']['storage']='00000000-0000-0000-0000-ffffffffffff'
    elif name=='foreign-root':index['root']='0'*64
    elif name=='omitted-boundary':boundaries.pop()
    elif name=='duplicate-boundary':boundaries[1]=copy.deepcopy(boundaries[0])
    elif name=='foreign-boundary-owner':boundaries[0]['node']='node-foreign'
    elif name=='outside-sequence':boundaries[0]['sequence']=262144
    elif name=='forged-boundary-usage':boundaries[0]['usage']['metadata']+=1
    elif name=='late-registration':index['owners'][0]['registeredAt']=next(i for i,v in enumerate(events) if v['node']==node)+1
    elif name=='widened-limit':trace['stagingLimit']+=1
    elif name=='truncated-journal':trace['truncated']=True
    elif name=='failed-journal':trace['failed']=True
    elif name=='missing-transition':trace['changes'][1]['sequence']+=1
    elif name=='foreign-release':
        row=next(v for v in trace['changes'] if v['event']=='RELEASE');row['removed'][0]['owner']='not-the-original-owner'
    elif name=='live-close':
        evidence.need(trace['changes'][-1]['event']=='RELEASE','native resources close mutation applicability')
        trace['changes'].pop();trace['transitions']-=1;trace['current']=copy.deepcopy(trace['changes'][-1]['usage'])
    else:raise ValueError('unknown native resource negative')


def replay(data,identities,root):
    # The unmodified observations must pass before any mutation may count.
    evidence.replay(*data,identities,root);result=[]
    for name,reason in NEGATIVES.items():
        value=copy.deepcopy(data);mutate(value,name)
        try:evidence.replay(*value,identities,root)
        except ValueError as error:
            evidence.need(str(error)==reason,'native resources unexpected negative: '+name+': '+str(error))
            result.append(dict(case=name,status='REJECTED',reason=reason))
        else:raise ValueError('native resources accepted negative: '+name)
    return result


def qualify(directory,profile='stable',progress=None):
    root=Path(directory);before=evidence.collection.inventory(root)
    original=evidence.validate(root,profile,progress);data=evidence.load(root)
    # These identities are usable only after the full original entry above has
    # checked them against independently derived disk owners.
    identities={v['identity']['node']:copy.deepcopy(v['identity']) for v in data[0]['owners']}
    cases=replay(data,identities,data[0]['root'])
    evidence.need(evidence.collection.inventory(root)==before,'native resources negative original changed')
    return dict(status='PASS',original=original,negativeCases=cases,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root')
    p.add_argument('--profile',choices=('stable','5-REPLACE-required-four'),default='stable');a=p.parse_args()
    print(json.dumps(qualify(a.root,a.profile),sort_keys=True))
