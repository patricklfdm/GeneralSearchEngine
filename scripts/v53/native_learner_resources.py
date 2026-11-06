"""Original admitted learner ownership through READY/CANCEL and cold reopen.

Full native authority/retention replay precedes resource observations. Snapshot
bytes, actual transfer identities, forced selection and successful close intervals
bind one continuous original pool. Transient physical maxima are not qualified.
"""
import argparse
import copy
import json
import shutil
import tempfile
from pathlib import Path
from . import learner_cancellation_evidence as c
from . import resource_transitions as t
from . import joining_history_run as h
from .remove_process_matrix import read
from .remove_process_hosted import progress

need=h.need;f=h.snapshot.f
SCHEMA='gse-v53-native-learner-resources-v1'
STAGES=(*c.STAGES,'final-closed')
CLOSES=('initial-cancel','initial-typed','initial-store','resume-cancel','resume-typed','resume-store')


def charge(unit,owner,size):return dict(unit=unit,owner=owner,bytes=size,claimSource='')


def offers(raw,files,wire):
    wanted={('CAPSULE',h.digest(files['source.gscp'])):[]}
    wanted.update({('APPLICATION',h.digest(data)):[] for name,data in files.items() if name.endswith('.image')})
    for row in c.d.read(raw/wire):
        kind,frame=c.t.source.t.t.wire(row['response'])
        if kind=='SOURCE_OFFER':
            v=frame['payload'];key=(v['kind'],v['digest'])
            if key in wanted and v['id'] not in wanted[key]:wanted[key].append(v['id'])
    need(all(len(ids)==1 for ids in wanted.values()),'learner resources exact original transfers')
    return {key:ids[0] for key,ids in wanted.items()}


def derive(raw):
    """The caller must first validate the complete native original."""
    prepared=c.c.inventory(raw/'learner-source-copy');terminal=c.c.inventory(raw/'learner-progress-copy')
    initial=offers(raw,prepared,'learner-source-wire.json');cancel=offers(raw,terminal,'learner-progress-wire.json')
    plan=h.digest((raw/'learner-plan.gslp').read_bytes())
    metadata=lambda files:sum(len(v) for k,v in files.items() if not k.endswith('.image'))
    generation=charge('GENERATION','learner-prepared:'+plan,metadata(prepared))
    base=[charge('MISC','learner-plan',2*t.MIB),generation,charge('APPLICATION','learner-typed-backup',64*t.MIB)]
    first=base+[charge('APPLICATION',initial['APPLICATION',h.digest(v)],len(v)) for k,v in sorted(prepared.items()) if k.endswith('.image')]
    second=[charge('LEARNER',cancel['CAPSULE',h.digest(terminal['source.gscp'])],metadata(terminal))]+[
        charge('APPLICATION',cancel['APPLICATION',h.digest(v)],len(v)) for k,v in sorted(terminal.items()) if k.endswith('.image')]
    cold=base+[charge('APPLICATION','learner-store:'+k,len(v)) for k,v in sorted(prepared.items()) if k.endswith('.image')]
    cold_cancel=[charge('LEARNER','learner-cancellation',metadata(terminal))]+[
        charge('APPLICATION','cancel:'+k,len(v)) for k,v in sorted(terminal.items()) if k.endswith('.image')]
    state=lambda rows:{t.key(v):v for v in rows}
    expected=dict(zip(STAGES,map(state,(first,first+second,[],cold+cold_cancel,[]))))
    snapshots={};usage={}
    for name in c.STAGES:
        snapshot=c.snap.read(raw/name,roots=c.ROOTS,required=c.ROOTS-{'cancellation'})
        usage[name]=snapshot.resources
        physical=sum(len(v) for files in snapshot.files.values() for v in files.values() if v is not None)
        backup=sum(len(v) for k,v in snapshot.files['initial-typed'].items() if k.startswith('backup/') and v is not None)
        misc=sum(len(v) for owner,files in snapshot.files.items() for k,v in files.items() if v is not None and
            not (owner=='replica' and k.startswith('learner/')) and
            not (owner=='initial-typed' and k.startswith('backup/')) and
            not (owner=='cancellation' and k.startswith('source/')))
        need(0<backup<=64*t.MIB and 0<misc<=2*t.MIB,'learner resources physical reserved extents')
        snapshots[name]=dict(physicalBytes=physical,typedBackupBytes=backup,miscBytes=misc,
            inventorySha256=h.digest(f.canonical(h.inventory(raw/name))))
    usage['final-closed']=t.EMPTY
    events={phase:c.d.read(raw/('learner-'+phase+'-events.json')) for phase in ('initial','cancel','resume')}
    selected_sources={'initial':initial['CAPSULE',h.digest(prepared['source.gscp'])],'resume':'learner-store'}
    return expected,usage,events,selected_sources,snapshots


def states(trace):
    t.replay(trace);current={};result=[]
    for row in trace['changes']:
        for v in row['removed']:del current[t.key(v)]
        for v in row['added']:current[t.key(v)]=v
        result.append(dict(current))
    return result


def bind(trace,rows,expected,usages,events,selected_sources):
    observed=states(trace)
    need((trace['metadataLimit'],trace['stagingLimit'],trace['queueLimit'])==(384*t.MIB,512*t.MIB,64*t.MIB),
         'learner resources original limits')
    need(type(rows) is list and 1<=len(rows)<=4096,'learner resources complete boundaries')
    previous=0
    for i,row in enumerate(rows):
        need(type(row) is dict and set(row)=={'ordinal','kind','name','point','sequence','usage'} and
             type(row['ordinal']) is int and row['ordinal']==i and type(row['sequence']) is int and
             previous<=row['sequence']<len(observed) and all(type(row[k]) is str for k in ('kind','name','point')),
             'learner resources exact boundary')
        previous=row['sequence'];t.same_usage(row['usage'],trace['changes'][previous]['usage'])
    markers=[(v['kind'],v['name']) for v in rows if v['kind']!='CALLBACK']
    wanted=[('POOL','start'),('SNAPSHOT',STAGES[0]),('SNAPSHOT',STAGES[1])]
    for name in CLOSES[:3]:wanted.extend((('CLOSE_BEGIN',name),('CLOSE_RETURN',name)))
    wanted.extend((('SNAPSHOT',STAGES[2]),('SNAPSHOT',STAGES[3])))
    for name in CLOSES[3:]:wanted.extend((('CLOSE_BEGIN',name),('CLOSE_RETURN',name)))
    wanted.append(('SNAPSHOT',STAGES[4]))
    need(markers==wanted and all(v['point']=='' for v in rows if v['kind']!='CALLBACK') and rows[0]['sequence']==0,
         'learner resources complete lifetime markers')
    positions={(v['kind'],v['name']):v for v in rows if v['kind']!='CALLBACK'}
    for phase,low,high in (('initial',('POOL','start'),('SNAPSHOT',STAGES[0])),
                            ('cancel',('SNAPSHOT',STAGES[0]),('SNAPSHOT',STAGES[1])),
                            ('resume',('SNAPSHOT',STAGES[2]),('SNAPSHOT',STAGES[3]))):
        selected=[v for v in rows if v['kind']=='CALLBACK' and v['name']==phase]
        need([v['point'] for v in selected]==events[phase] and all(positions[low]['ordinal']<v['ordinal']<positions[high]['ordinal'] for v in selected),
             'learner resources original callback order')
    need(sum(v['kind']=='CALLBACK' for v in rows)==sum(map(len,events.values())),'learner resources complete callbacks')
    for name in STAGES:
        row=positions['SNAPSHOT',name];state=observed[row['sequence']]
        t.same_usage(row['usage'],usages[name])
        need(state==expected[name],'learner resources original stage owners')
    for name in CLOSES:
        before=positions['CLOSE_BEGIN',name]['sequence'];after=positions['CLOSE_RETURN',name]['sequence']
        a,b=observed[before],observed[after]
        prefix='initial' if name.startswith('initial') else 'resume'
        retained=expected[STAGES[0]] if prefix=='initial' else {k:v for k,v in expected[STAGES[3]].items() if
            not (k[0]=='LEARNER' or k[1].startswith('cancel:'))}
        wanted_after={} if name.endswith('store') else retained
        need(b==wanted_after and (a==retained if not name.endswith('cancel') else a==expected[STAGES[1] if prefix=='initial' else STAGES[3]]),
             'learner resources exact successful close')
        need(all(row['event']=='RELEASE' for row in trace['changes'][before+1:after+1]),'learner resources close release only')
    # Every original base lease survives every intermediate change, not merely
    # equal totals before and after a release/reacquire gap.
    for phase,start in (('initial',STAGES[0]),('resume',STAGES[3])):
        low=positions['SNAPSHOT',start]['sequence'];high=positions['CLOSE_BEGIN',phase+'-store']['sequence']
        base=expected[STAGES[0]] if phase=='initial' else {k:v for k,v in expected[STAGES[3]].items() if not (k[0]=='LEARNER' or k[1].startswith('cancel:'))}
        need(all(all(state.get(k)==v for k,v in base.items()) for state in observed[low:high+1]),
             'learner resources continuous original ownership')
    commits=[]
    generation=next(v for v in expected[STAGES[0]].values() if v['unit']=='GENERATION')
    for phase in ('initial','resume'):
        before=[v for v in rows if v['kind']=='CALLBACK' and v['name']==phase and v['point']=='LEARNER_PREPARED_BEFORE_SELECT']
        after=[v for v in rows if v['kind']=='CALLBACK' and v['name']==phase and v['point']=='LEARNER_PREPARED_BEFORE_RETURN']
        need(len(before)==len(after)==1,'learner resources original generation selection')
        lo,hi=before[0]['sequence'],after[0]['sequence'];claim=observed[lo].get(t.key(generation))
        need(claim==dict(generation,bytes=0,claimSource=selected_sources[phase]),'learner resources original generation claim')
        selected=[row for row in trace['changes'][lo+1:hi+1] if row['event']=='GENERATION_COMMIT']
        need(len(selected)==1 and selected[0]['added']==[generation] and observed[hi].get(t.key(generation))==generation,
             'learner resources forced generation handoff')
        commits.extend(row['sequence'] for row in selected)
    need(commits==[r['sequence'] for r in trace['changes'] if r['event']=='GENERATION_COMMIT'],
         'learner resources exact two selections')
    for phase,start,commit in zip(('initial','resume'),(STAGES[1],STAGES[3]),commits):
        base=expected[STAGES[0]] if phase=='initial' else {k:v for k,v in expected[start].items()
            if not (k[0]=='LEARNER' or k[1].startswith('cancel:'))}
        end=positions['CLOSE_BEGIN',phase+'-store']['sequence']
        need(all(all(state.get(k)==v for k,v in base.items()) for state in observed[commit:end+1]),
             'learner resources continuous selected ownership')
        terminal={k:v for k,v in expected[start].items() if k not in base}
        adopted=[v for v in rows if v['kind']=='CALLBACK' and v['name']==('cancel' if phase=='initial' else 'resume')
                 and v['point']=='LEARNER_CANCEL_ACTIVE_PLAN_FORCED']
        need(len(adopted)==1,'learner resources original cancellation adoption')
        begin=adopted[0]['sequence'];end=positions['CLOSE_BEGIN',phase+'-cancel']['sequence']
        need(begin<=end and all(all(state.get(k)==v for k,v in terminal.items()) for state in observed[begin:end+1]),
             'learner resources continuous cancellation ownership')
    return dict(status='PARTIAL',boundaries=len(rows),callbacks=sum(map(len,events.values())),closeIntervals=len(CLOSES),
        transitions=len(observed),generationSelections=commits,continuousOwnershipQualified=True,originalTransferBindingQualified=True,
        explicitCloseIntervalsQualified=True,wholeRuntimeResourcesQualified=False,transientPhysicalBytesQualified=False,phase3Complete=False)


def validate(root):
    root=Path(root);before=h.inventory(root)
    need({p.name for p in root.iterdir()}=={'original','resources'},'learner resources complete wrapper')
    original=c.validate(root/'original',retained_learners=True,current_retention=True)
    folder=root/'resources';need({p.name for p in folder.iterdir()}=={'trace.json','boundaries.json','index.json'},'learner resources exact sidecars')
    index=read(folder/'index.json')
    need(type(index) is dict and set(index)=={'schema','status','pid','planSha256','wholeRuntimeResourcesQualified','phase3Complete'} and
         index['schema']==SCHEMA and index['status']=='PARTIAL' and type(index['pid']) is int and index['pid']>0 and
         index['planSha256']==h.digest((root/'original/learner-plan.gslp').read_bytes()) and
         index['wholeRuntimeResourcesQualified'] is False and index['phase3Complete'] is False,'learner resources original index')
    _,trace=t.read(folder/'trace.json');rows=read(folder/'boundaries.json');expected,usages,events,sources,snapshots=derive(root/'original')
    resources=bind(trace,rows,expected,usages,events,sources);resources['snapshots']=snapshots
    need(h.inventory(root)==before,'learner resources original changed')
    return dict(status='PARTIAL',original=original,resources=resources,phase3Complete=False), (trace,rows,expected,usages,events,sources)


NEGATIVES={
    'truncated':'resource transitions incomplete observation',
    'limits':'learner resources original limits',
    'missing-close':'learner resources complete lifetime markers',
    'extra-close':'learner resources complete lifetime markers',
    'missing-callback':'learner resources original callback order',
    'reordered-callback':'learner resources original callback order',
    'foreign-transfer':'learner resources original stage owners',
    'foreign-cold-owner':'learner resources original stage owners',
    'foreign-generation-source':'learner resources original generation claim',
    'changed-usage':'resource transitions derived usage',
    'early-close-return':'learner resources exact successful close',
    'late-close-begin':'learner resources exact successful close',
    'release-reacquire-gap':'learner resources continuous original ownership',
    'terminal-release-gap':'learner resources continuous cancellation ownership',
    'unforced-handoff':'learner resources original generation claim',
}


def mutate(value,name):
    """Copied in-memory observations only; no original file is rewritten."""
    trace,rows,expected,usages,events,sources=value
    def marker(kind,label):return next(v for v in rows if (v['kind'],v['name'])==(kind,label))
    def move(row,sequence):row.update(sequence=sequence,usage=copy.deepcopy(trace['changes'][sequence]['usage']))
    if name=='truncated':trace['truncated']=True
    elif name=='limits':trace['stagingLimit']+=1
    elif name=='missing-close':rows.remove(marker('CLOSE_RETURN','initial-cancel'))
    elif name=='extra-close':rows.append(copy.deepcopy(rows[-2]))
    elif name in ('missing-callback','reordered-callback'):
        i=next(i for i,v in enumerate(rows) if v['kind']=='CALLBACK')
        if name=='missing-callback':rows.pop(i)
        else:rows[i]['point'],rows[i+1]['point']=rows[i+1]['point'],rows[i]['point']
    elif name in ('foreign-transfer','foreign-cold-owner','foreign-generation-source'):
        if name=='foreign-generation-source':old=sources['initial']
        elif name=='foreign-cold-owner':old=next(v['owner'] for v in expected[STAGES[3]].values() if v['owner'].startswith('learner-store:'))
        else:old=next(v['owner'] for v in expected[STAGES[0]].values() if v['unit']=='APPLICATION' and v['owner']!='learner-typed-backup')
        for row in trace['changes']:
            for field in ('removed','added'):
                for v in row[field]:
                    if v['owner']==old:v['owner']='foreign-original'
                    if v['claimSource']==old:v['claimSource']='foreign-original'
                row[field].sort(key=t.order_key)
    elif name=='changed-usage':marker('SNAPSHOT',STAGES[0])['usage']['metadata']+=1
    elif name=='early-close-return':move(marker('CLOSE_RETURN','initial-cancel'),marker('CLOSE_BEGIN','initial-cancel')['sequence'])
    elif name=='late-close-begin':move(marker('CLOSE_BEGIN','initial-cancel'),marker('CLOSE_RETURN','initial-cancel')['sequence'])
    elif name=='unforced-handoff':
        row=next(v for v in rows if v['kind']=='CALLBACK' and v['name']=='initial' and v['point']=='LEARNER_PREPARED_BEFORE_SELECT')
        end=next(v for v in rows if v['kind']=='CALLBACK' and v['name']=='initial' and v['point']=='LEARNER_PREPARED_BEFORE_RETURN')
        move(row,end['sequence'])
    elif name in ('release-reacquire-gap','terminal-release-gap'):
        if name=='release-reacquire-gap':
            at=marker('SNAPSHOT',STAGES[0])['sequence']+1
            held=next(v for v in expected[STAGES[0]].values() if v['unit']=='GENERATION')
        else:
            adopted=next(v for v in rows if v['kind']=='CALLBACK' and v['name']=='cancel'
                         and v['point']=='LEARNER_CANCEL_ACTIVE_PLAN_FORCED')
            at=adopted['sequence']+1
            held=next(v for v in expected[STAGES[1]].values() if v['unit']=='LEARNER')
        inserted=[dict(event='RELEASE',removed=[copy.deepcopy(held)],added=[]),dict(event='RESERVE',removed=[],added=[copy.deepcopy(held)])]
        trace['changes'][at:at]=inserted;state={};limits=tuple(trace[k] for k in ('metadataLimit','stagingLimit','queueLimit'))
        for i,row in enumerate(trace['changes']):
            for v in row['removed']:del state[t.key(v)]
            for v in row['added']:state[t.key(v)]=v
            row.update(sequence=i,usage=t.usage(state,limits))
        for row in rows:
            if row['sequence']>=at or (name=='terminal-release-gap' and row['ordinal']>adopted['ordinal']):row['sequence']+=2
        trace['transitions']=len(trace['changes']);trace['current']=copy.deepcopy(trace['changes'][-1]['usage'])
    else:raise ValueError('unknown learner resources negative: '+name)
    for i,row in enumerate(rows):row['ordinal']=i


HISTORY_NEGATIVES={
    'missing-renewal-selection':'context selection learner cancellation inventory',
    'foreign-renewal-selection':'learner typed original renewal selection',
    'changed-renewal-voter':'admitted exact installed-3: node-1',
    'changed-renewal-publication':'admitted exact published-7: node-1',
}


def mutate_history(root,name):
    if name=='missing-renewal-selection':(root/'selected-3.gsr').unlink()
    elif name=='foreign-renewal-selection':(root/'selected-3.gsr').write_bytes((root/'selected-2.gsr').read_bytes())
    elif name=='changed-renewal-voter':(root/'installed-3/node-1/selector.gsr').write_bytes(b'foreign')
    elif name=='changed-renewal-publication':(root/'published-7/node-1/selector.gsr').write_bytes(b'foreign')
    else:raise ValueError('unknown learner resources history negative: '+name)


def rejected(action,reason,name):
    try:action()
    except ValueError as error:need(str(error)==reason,'learner resources unrelated negative: '+name+': '+str(error))
    else:raise ValueError('learner resources accepted negative: '+name)
    return dict(case=name,status='REJECTED',reason=reason)


def qualify(root):
    root=Path(root);before=h.inventory(root)
    original,observations=validate(root);negatives=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(observations);mutate(changed,name)
        negatives.append(dict(suite='resource-observations',**rejected(lambda:bind(*changed),reason,name)))
    # Full original authority and sidecars already passed before ANY negative.
    base=c.qualify(root/'original',retained_learners=True,current_retention=True)
    need(base['original']==original['original'],'learner resources original replay drift')
    negatives += [dict(suite='original-history',**row) for row in base['negatives']]
    for name,reason in HISTORY_NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-learner-resources-negative-') as temp:
            copied=Path(temp)/'original';shutil.copytree(root/'original',copied);mutate_history(copied,name)
            negatives.append(dict(suite='renewal-history',**rejected(lambda:c.validate(copied,retained_learners=True,current_retention=True),reason,name)))
    need(before==h.inventory(root),'learner resources original changed')
    return dict(original=original,negatives=negatives,originalPreserved=True,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--output',required=True);p.add_argument('--qualify',action='store_true');a=p.parse_args()
    output=Path(a.output);output.mkdir(parents=True,exist_ok=False);result=dict(status='FAIL',phase3Complete=False)
    try:
        with progress('native-learner-resources',None):result=qualify(a.root) if a.qualify else validate(a.root)[0]
    except BaseException as error:result['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:h.save(output/'qualification.json',result)
    print(json.dumps(result,sort_keys=True))
