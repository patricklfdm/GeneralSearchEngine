"""Actual admitted learner cold recovery at original-derived staging limits.

Original native authority is replayed first. Each subsequent pool is configured
once, before opening the same original files. Reservation size is not physical
size; this does not qualify whole-runtime maximum pressure or autonomous rejoin.
"""
import argparse
import copy
import json
import re
import shutil
import tempfile
from pathlib import Path
from . import native_learner_resources as n

h,t,c,need=n.h,n.t,n.c,n.need
MODES=('pool-full','packet-short','source-exact')
POINT='LEARNER_CANCEL_BEFORE_RETURN'
STAGES=('before-probe','after-probe','returned','closed')


def derive(raw):
    expected,_,events,_,_=n.derive(raw)
    state=expected['learner-reopened'];terminal=c.c.inventory(raw/'learner-progress-copy')
    steady=sum(v['bytes'] for v in state.values() if v['unit'] in t.STAGING)
    packet=len(terminal['source.gscp']);images={k[:-6]:len(v) for k,v in terminal.items() if k.endswith('.image')}
    snapshot=c.snap.read(raw/'learner-reopened',roots=c.ROOTS,required=c.ROOTS)
    peer=c.e.parse(snapshot.files['cancellation']['cancellation.json'])['peer']
    return dict(state=state,steady=steady,packet=packet,images=images,events=events['resume'],peer=peer),snapshot,terminal


def limit(mode,d):
    need(mode in MODES,'learner byte pressure exact mode')
    return d['steady']+{'pool-full':0,'packet-short':d['packet']-1,'source-exact':d['packet']+sum(d['images'].values())}[mode]


def uuid(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}',value) is not None


def bind(mode,d,trace,rows,events,probe,result):
    states=n.states(trace);limits=(384*t.MIB,limit(mode,d),64*t.MIB)
    need(tuple(trace[k] for k in ('metadataLimit','stagingLimit','queueLimit'))==limits,'learner byte pressure original-derived limits')
    expected=dict(status='PARTIAL',mode=mode,steadyStagingBytes=d['steady'],stagingLimit=limits[1],packetBytes=d['packet'],
                  imageBytes=sum(d['images'].values()),sameOriginalColdRecovery=True,wholeRuntimeResourcesQualified=False,phase3Complete=False)
    need(n.f.canonical(result)==n.f.canonical(expected),'learner byte pressure exact result')
    need(events==d['events'],'learner byte pressure original force order')
    need(type(rows) is list and 1<=len(rows)<=4096,'learner byte pressure bounded boundaries')
    previous=0
    for i,row in enumerate(rows):
        need(type(row) is dict and set(row)=={'ordinal','kind','name','point','sequence','usage'} and type(row['ordinal']) is int and
             row['ordinal']==i and type(row['sequence']) is int and previous<=row['sequence']<len(states) and
             all(type(row[k]) is str for k in ('kind','name','point')),'learner byte pressure exact boundary')
        previous=row['sequence'];t.same_usage(row['usage'],trace['changes'][previous]['usage'])
    callbacks=[v for v in rows if v['kind']=='CALLBACK']
    need([v['point'] for v in callbacks]==events and all(v['name']=='resume' for v in callbacks),
         'learner byte pressure exact callbacks')
    labels=[('POOL','start',''),('PROBE_BEGIN',mode,POINT)]
    if mode=='source-exact':labels.append(('PROBE_COMPLETE',mode,''))
    labels += [('PROBE_RETURN',mode,POINT),('SNAPSHOT','returned','')]
    for name in ('resume-cancel','resume-typed','resume-store'):
        labels += [('CLOSE_BEGIN',name,''),('CLOSE_RETURN',name,'')]
    labels.append(('SNAPSHOT','closed',''))
    need([(v['kind'],v['name'],v['point']) for v in rows if v['kind']!='CALLBACK']==labels and rows[0]['sequence']==0,
         'learner byte pressure complete lifetime')
    markers={(v['kind'],v['name']):v for v in rows if v['kind']!='CALLBACK'}
    begin=markers['PROBE_BEGIN',mode];end=markers['PROBE_RETURN',mode]
    need(callbacks[-1]['point']==POINT and callbacks[-1]['ordinal']+1==begin['ordinal'] and callbacks[0]['ordinal']>0,
         'learner byte pressure original callback placement')
    need(type(probe) is list and len(probe)==1 and type(probe[0]) is dict,'learner byte pressure one receiver')
    probe=probe[0]
    need(set(probe)=={'transfer','session','source','scratch','images','outcome','reason','scratchRemoved'} and
         uuid(probe['transfer']) and uuid(probe['session']) and probe['source']==d['peer'] and
         probe['scratchRemoved'] is True,'learner byte pressure original receiver binding')
    c.snap.original_path(probe['scratch'])
    state=d['state'];base={k:v for k,v in state.items() if not (k[0]=='LEARNER' or k[1].startswith('cancel:'))}
    for row in (begin,end,markers['SNAPSHOT','returned']):
        need(states[row['sequence']]==state,'learner byte pressure unchanged admitted owners')
    if mode!='source-exact':
        need(probe['outcome']=='REJECTED' and probe['reason']=='shared staging capacity' and probe['images']==[],
             'learner byte pressure specific rejection')
        changes=trace['changes'][begin['sequence']+1:end['sequence']+1]
        need(len(changes)==2 and [v['event'] for v in changes]==['RESERVE','RELEASE'] and
             changes[0]['added']==changes[1]['removed'] and len(changes[0]['added'])==1 and
             changes[0]['added'][0]['unit']=='CONTROL' and changes[0]['added'][0]['bytes']==4096 and
             changes[0]['added'][0]['owner'].startswith('received-records-'),'learner byte pressure refusal cleanup')
    else:
        need(probe['outcome']=='ACCEPTED' and probe['reason']=='' and type(probe['images']) is list and
             len(probe['images'])==len(d['images']) and all(type(v) is dict and set(v)=={'transfer','digest','bytes'} and
             uuid(v['transfer']) and type(v['bytes']) is int for v in probe['images']) and
             {v['digest']:v['bytes'] for v in probe['images']}==d['images'] and
             len({probe['transfer'],*(v['transfer'] for v in probe['images'])})==len(d['images'])+1,
             'learner byte pressure complete source binding')
        complete=markers['PROBE_COMPLETE',mode];observed=states[complete['sequence']]
        controls=[v for v in observed.values() if v['unit']=='CONTROL']
        need(len(controls)==1 and controls[0]['bytes']==4096 and controls[0]['owner'].startswith('received-records-'),
             'learner byte pressure original receiver control')
        added=[controls[0],n.charge('SOURCE',probe['transfer'],d['packet'])]+[
            n.charge('APPLICATION',v['transfer'],v['bytes']) for v in probe['images']]
        need(observed==state|{t.key(v):v for v in added} and complete['usage']['staging']==limits[1],
             'learner byte pressure exact complete source')
        changes=trace['changes'][begin['sequence']+1:end['sequence']+1]
        need(len(changes)==2*len(added) and
             all(v['event']=='RESERVE' for v in trace['changes'][begin['sequence']+1:complete['sequence']+1]) and
             all(v['event']=='RELEASE' for v in trace['changes'][complete['sequence']+1:end['sequence']+1]),
             'learner byte pressure exact receiver lifetime')
    generation=next(v for v in base.values() if v['unit']=='GENERATION')
    commits=[v for v in trace['changes'] if v['event']=='GENERATION_COMMIT']
    before=[v for v in callbacks if v['point']=='LEARNER_PREPARED_BEFORE_SELECT']
    after=[v for v in callbacks if v['point']=='LEARNER_PREPARED_BEFORE_RETURN']
    need(len(commits)==len(before)==len(after)==1 and before[0]['sequence']<commits[0]['sequence']<=after[0]['sequence'] and
         commits[0]['added']==[generation] and
         states[before[0]['sequence']].get(t.key(generation))==dict(generation,bytes=0,claimSource='learner-store'),
         'learner byte pressure forced generation handoff')
    last=markers['CLOSE_BEGIN','resume-store']['sequence']
    need(all(all(s.get(k)==v for k,v in base.items()) for s in states[commits[0]['sequence']:last+1]),
         'learner byte pressure continuous selected owners')
    adopted=[v for v in callbacks if v['point']=='LEARNER_CANCEL_ACTIVE_PLAN_FORCED']
    need(len(adopted)==1 and all(all(s.get(k)==v for k,v in state.items()) for s in
         states[adopted[0]['sequence']:markers['CLOSE_BEGIN','resume-cancel']['sequence']+1]),
         'learner byte pressure continuous terminal owners')
    for label,wanted_before,wanted_after in (('cancel',state,base),('typed',base,base),('store',base,{})):
        lo=markers['CLOSE_BEGIN','resume-'+label]['sequence'];hi=markers['CLOSE_RETURN','resume-'+label]['sequence']
        need(states[lo]==wanted_before and states[hi]==wanted_after and all(v['event']=='RELEASE' for v in trace['changes'][lo+1:hi+1]),
             'learner byte pressure exact close intervals')
    need(markers['SNAPSHOT','closed']['sequence']==len(states)-1 and not states[-1],'learner byte pressure final closed')
    return dict(status='PARTIAL',mode=mode,stagingLimit=limits[1],steadyStagingBytes=d['steady'],
        packetBytes=d['packet'],imageBytes=sum(d['images'].values()),
        receiver=probe['outcome'],closeIntervals=3,transitions=len(states),sameOriginalColdRecovery=True,
        wholeRuntimeResourcesQualified=False,phase3Complete=False)


def read_mode(root,mode,d,snapshot,terminal,plan,pid):
    need({p.name for p in root.iterdir()}=={'resources','events.json','probe.json','result.json',*STAGES}|({'received'} if mode=='source-exact' else set()),
         'learner byte pressure exact mode inventory')
    folder=root/'resources'
    need({p.name for p in folder.iterdir()}=={'trace.json','boundaries.json','index.json'},'learner byte pressure exact sidecars')
    need(n.f.canonical(n.read(folder/'index.json'))==n.f.canonical(dict(schema=n.SCHEMA,status='PARTIAL',pid=pid,planSha256=plan,
         wholeRuntimeResourcesQualified=False,phase3Complete=False)),'learner byte pressure original index')
    _,trace=t.read(folder/'trace.json');rows=n.read(folder/'boundaries.json');events=n.read(root/'events.json')
    probe=n.read(root/'probe.json');result=n.read(root/'result.json');value=(mode,d,trace,rows,events,probe,result)
    summary=bind(*value)
    for stage in STAGES:
        current=c.snap.read(root/stage,roots=c.ROOTS,required=c.ROOTS)
        need(current.files==snapshot.files and current.identities==snapshot.identities,'learner byte pressure unchanged original files')
        t.same_usage(current.resources,t.EMPTY if stage=='closed' else t.usage(d['state'],(384*t.MIB,limit(mode,d),64*t.MIB)))
    if mode=='source-exact':
        need(c.c.inventory(root/'received')=={k:v for k,v in terminal.items() if k=='source.gscp' or k.endswith('.image')},
             'learner byte pressure exact received original bytes')
    return summary,value


def validate(root):
    root=Path(root);before=h.inventory(root)
    need({p.name for p in root.iterdir()}=={'original','pressure'},'learner byte pressure complete wrapper')
    original,_=n.validate(root/'original')
    raw=root/'original/original';d,snapshot,terminal=derive(raw)
    need({p.name for p in (root/'pressure').iterdir()}==set(MODES),'learner byte pressure complete modes')
    index=n.read(root/'original/resources/index.json');summaries=[];values=[]
    for mode in MODES:
        summary,value=read_mode(root/'pressure'/mode,mode,d,snapshot,terminal,index['planSha256'],index['pid'])
        summaries.append(summary);values.append(value)
    need(before==h.inventory(root),'learner byte pressure original changed')
    return dict(status='PARTIAL',original=original,modes=summaries,wholeRuntimeResourcesQualified=False,phase3Complete=False),values


NEGATIVES={
    'limit-drift':'learner byte pressure original-derived limits',
    'wrong-reason':'learner byte pressure specific rejection',
    'missing-probe':'learner byte pressure complete lifetime',
    'wrong-source':'learner byte pressure original receiver binding',
    'missing-force':'learner byte pressure original force order',
    'early-close':'learner byte pressure exact close intervals',
    'foreign-transfer':'learner byte pressure exact complete source',
    'false-completion':'learner byte pressure exact result',
    'base-release-gap':'learner byte pressure continuous selected owners',
    'terminal-release-gap':'learner byte pressure continuous terminal owners',
}
PHYSICAL_NEGATIVES={
    'changed-original-inode':'learner byte pressure unchanged original files',
    'changed-received-packet':'learner byte pressure exact received original bytes',
}


def mutate(value,name):
    mode,d,trace,rows,events,probe,result=value
    if name=='limit-drift':trace['stagingLimit']+=1
    elif name=='wrong-reason':probe[0]['reason']='resource ownership/count'
    elif name=='missing-probe':rows[:]=[v for v in rows if v['kind']!='PROBE_RETURN']
    elif name=='wrong-source':probe[0]['source']={}
    elif name=='missing-force':events.pop(0)
    elif name=='early-close':
        before=next(v for v in rows if (v['kind'],v['name'])==('CLOSE_BEGIN','resume-cancel'))
        after=next(v for v in rows if (v['kind'],v['name'])==('CLOSE_RETURN','resume-cancel'))
        after.update(sequence=before['sequence'],usage=copy.deepcopy(before['usage']))
    elif name=='foreign-transfer':probe[0]['transfer']='00000000-0000-0000-0000-000000000000'
    elif name=='false-completion':result['phase3Complete']=True
    elif name in ('base-release-gap','terminal-release-gap'):
        point='LEARNER_PREPARED_BEFORE_RETURN' if name=='base-release-gap' else 'LEARNER_CANCEL_ACTIVE_PLAN_FORCED'
        marker=next(v for v in rows if v['kind']=='CALLBACK' and v['point']==point)
        at=marker['sequence']+1;unit='GENERATION' if name=='base-release-gap' else 'LEARNER'
        held=next(v for v in d['state'].values() if v['unit']==unit)
        trace['changes'][at:at]=[dict(event='RELEASE',removed=[copy.deepcopy(held)],added=[]),
                                 dict(event='RESERVE',removed=[],added=[copy.deepcopy(held)])]
        state={};limits=tuple(trace[k] for k in ('metadataLimit','stagingLimit','queueLimit'))
        for i,row in enumerate(trace['changes']):
            for v in row['removed']:del state[t.key(v)]
            for v in row['added']:state[t.key(v)]=v
            row.update(sequence=i,usage=t.usage(state,limits))
        for row in rows:
            if row['ordinal']>marker['ordinal']:row['sequence']+=2
        trace.update(transitions=len(trace['changes']),current=copy.deepcopy(trace['changes'][-1]['usage']))
    else:raise ValueError('unknown learner byte pressure negative: '+name)
    for i,row in enumerate(rows):row['ordinal']=i


def qualify(root):
    root=Path(root);before=h.inventory(root);original,values=validate(root);negatives=[]
    for name,reason in NEGATIVES.items():
        value=copy.deepcopy(values[2 if name=='foreign-transfer' else 0]);mutate(value,name)
        negatives.append(dict(suite='byte-pressure',**n.rejected(lambda:bind(*value),reason,name)))
    for name,reason in PHYSICAL_NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-learner-byte-negative-') as temp:
            copied=Path(temp)/'mode';shutil.copytree(root/'pressure/source-exact',copied)
            if name=='changed-original-inode':
                path=copied/'after-probe/original-identities.json';data=n.read(path)
                data['operation']['members']['.']['key']='foreign-original';path.write_bytes(n.f.canonical(data))
            else:(copied/'received/source.gscp').write_bytes(b'foreign')
            raw=root/'original/original';d,snapshot,terminal=derive(raw);index=n.read(root/'original/resources/index.json')
            negatives.append(dict(suite='byte-physical',**n.rejected(lambda:read_mode(copied,'source-exact',d,snapshot,terminal,
                index['planSha256'],index['pid']),reason,name)))
    base=n.qualify(root/'original');need(base['original']==original['original'],'learner byte pressure original replay drift')
    negatives += [dict(row,suite='original-'+row['suite']) for row in base['negatives']]
    need(before==h.inventory(root),'learner byte pressure original changed')
    return dict(original=original,negatives=negatives,originalPreserved=True,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--output',required=True);p.add_argument('--qualify',action='store_true');a=p.parse_args()
    output=Path(a.output);output.mkdir(parents=True,exist_ok=False);result=dict(status='FAIL',phase3Complete=False)
    try:
        with n.progress('native-learner-byte-pressure',None):result=qualify(a.root) if a.qualify else validate(a.root)[0]
    except BaseException as error:result['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:h.save(output/'qualification.json',result)
    print(json.dumps(result,sort_keys=True))
