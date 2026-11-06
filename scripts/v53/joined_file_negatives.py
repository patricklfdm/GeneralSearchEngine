"""Original-first qualification of actual file/custody mappings; no workload retries."""
import argparse
import copy
import json
from pathlib import Path
import sys
from . import joined_file_resources as r
from . import native_resource_evidence as native
from . import required_four_maintenance as maintenance

NEGATIVES={
    'missing-owner':'storage transfer complete original owners',
    'missing-switch':'storage transfer complete switch coverage',
    'duplicate-switch':'storage transfer complete switch coverage',
    'wrong-sequence':'storage transfer exact ordered switch',
    'boolean-sequence':'storage transfer exact ordered switch',
    'truncated':'storage transfer complete recorder',
    'failed':'storage transfer complete recorder',
    'wrong-length':'storage transfer complete recorder',
    'missing-pair':'storage transfer exact resulting state',
    'foreign-predecessor':'storage transfer live predecessor',
    'foreign-successor':'storage transfer exact resulting state',
    'changed-extent':'storage transfer exact preserved extent',
    'equal-image-successor-swap':'joined files exact predecessor successor pairs',
}


def mutate(data,name):
    plan,events,traces,boundaries,captured=data;node=plan['node'];value=captured[node]
    r.need(name in NEGATIVES,'joined files declared mutation')
    if name=='missing-owner':del captured[node];return
    if name=='missing-switch':value['rows'].clear();return
    if name=='duplicate-switch':value['rows'].append(copy.deepcopy(value['rows'][0]));return
    if name in ('truncated','failed'):value[name]=True;return
    if name=='wrong-length':value['transitions']+=1;return
    row=value['rows'][0];moves=row['moves']
    if name=='wrong-sequence':row['resourceSequence']+=1
    elif name=='boolean-sequence':row['resourceSequence']=True
    elif name=='missing-pair':moves.pop()
    elif name=='foreign-predecessor':moves[-1]['before']['owner']+='-absent'
    elif name=='foreign-successor':moves[-1]['after']['owner']+='-absent'
    elif name=='changed-extent':moves[0]['after']['bytes']+=1
    elif name=='equal-image-successor-swap':
        pair=next(((a,b) for i,a in enumerate(moves) for b in moves[i+1:] if
                   a['before']['unit']==b['before']['unit']=='APPLICATION' and
                   a['before']['bytes']==b['before']['bytes']),None)
        r.need(pair is not None,'joined files original lacks distinct equal-size images')
        a,b=pair;a['after'],b['after']=b['after'],a['after']


def replay(data,progress=None):
    r.replay(*data);result=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(data);mutate(changed,name)
        try:r.replay(*changed)
        except ValueError as error:r.need(str(error)==reason,'joined files unrelated rejection: '+name+': '+str(error))
        else:raise ValueError('joined files accepted mutation: '+name)
        result.append(dict(case=name,status='REJECTED',reason=reason))
        if progress:progress(dict(stage='joined-file-negatives',case=name,completed=len(result),total=len(NEGATIVES)))
    return result


def qualify(root,progress=None):
    root=Path(root);before=native.collection.inventory(root)
    original=native.validate(root,'5-REPLACE-required-four',progress,joined_files=True)
    binding=original.get('joinedFileResources')
    r.need(original.get('status')=='PASS' and type(binding) is dict and binding.get('status')=='PASS' and
           binding.get('originalFileCustodyQualified') is True,'joined files complete original qualification')
    if progress:progress(dict(stage='original',status='PASS'))
    index,traces,boundaries,events=native.load(root)
    physical=r.handoff.original(root);reader=maintenance.Replay(root);reader.run()
    plan=r.derive(physical.owner,reader)
    data=(plan,events,traces,boundaries,r.transfers.load(root,index))
    result=replay(data,progress)
    r.need(native.collection.inventory(root)==before,'joined files qualification changed original')
    return dict(status='PASS',original=original,negatives=result,mapping=plan,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');a=p.parse_args()
    progress=lambda row:print(json.dumps(row,sort_keys=True),file=sys.stderr,flush=True)
    print(json.dumps(qualify(a.root,progress),sort_keys=True))
