"""Direct-owner evidence mutations, with original physical inputs unchanged."""
import argparse
import copy
import json
from pathlib import Path
from . import native_resource_evidence as a
from . import direct_export_evidence as r
from . import resource_transitions as resources

NEGATIVES={
    'missing-acquisition':'control close original direct call',
    'duplicate-acquisition':'control close original direct acquisition',
    'missing-close-begin':'control close direct release before return',
    'missing-return':'control close incomplete direct cleanup',
    'unobserved-local-owner':'session export unclaimed allocation',
    'wrong-close-call':'control close original direct call',
    'wrong-source-phase':'direct export original content/cohort',
    'changed-original-digest':'direct export original content/cohort',
    'changed-original-extent':'direct export original content extent',
    'late-acquisition':'direct export original activation lifetime',
    'return-before-release':'control close direct release before return',
    'boolean-resource-point':'control close exact ordered row',
}


def renumber(value):
    calls={}
    for seq,row in enumerate(value['rows']):
        row['sequence']=seq
        if row['event']=='ATTACHED':row['call']=seq
        elif row['event'] in ('BEGIN','EXPORT_ROLLBACK_BEGIN','PROBE_BORROW_ACQUIRED') or row['event'] in r.close.DIRECT_EVENTS and r.close.DIRECT_EVENTS[row['event']][1]=='ACQUIRED':
            calls[row['owner']]=seq;row['call']=seq
        else:row['call']=calls.get(row['owner'],-1)
    value['observations']=len(value['rows'])


def recount(trace):
    state={};limits=tuple(trace[k] for k in ('metadataLimit','stagingLimit','queueLimit'))
    for change in trace['changes']:
        for value in change['removed']:del state[resources.key(value)]
        for value in change['added']:state[resources.key(value)]=value
        change['usage']=resources.usage(state,limits)
    trace['current']=copy.deepcopy(trace['changes'][-1]['usage'])


def mutate(traces,closes,name):
    node=next(n for n,value in closes.items() if any(v['event']=='ACTIVATION_BORROW_ACQUIRED' for v in value['rows']))
    value=closes[node];rows=value['rows'];acquired=next(v for v in rows if v['event']=='ACTIVATION_BORROW_ACQUIRED')
    owner=acquired['owner'];begin=next(v for v in rows if v['owner']==owner and v['event'].endswith('CLOSE_BEGIN'))
    returned=next(v for v in rows if v['owner']==owner and v['event'].endswith('RETURNED'))
    if name in ('missing-acquisition','missing-close-begin','missing-return'):
        rows.remove({'missing-acquisition':acquired,'missing-close-begin':begin,'missing-return':returned}[name]);renumber(value)
    elif name=='duplicate-acquisition':rows.insert(acquired['sequence']+1,copy.deepcopy(acquired));renumber(value)
    elif name=='unobserved-local-owner':value['rows']=[v for v in rows if v['owner']!=owner];renumber(value)
    elif name=='wrong-close-call':begin['call']=-1
    elif name=='wrong-source-phase':
        for row in rows:
            if row['owner']==owner:row['event']=row['event'].replace('ACTIVATION','SELECTED')
    elif name=='changed-original-digest':
        new=owner.replace(owner[len('source-export-'):len('source-export-')+64],'d'*64)
        for row in rows:
            if row['owner']==owner:row['owner']=new
        for change in traces[node]['changes']:
            for value in change['added']+change['removed']:
                if value['owner']==owner:value['owner']=new
    elif name=='changed-original-extent':
        for change in traces[node]['changes']:
            for value in change['added']+change['removed']:
                if value['owner']==owner:value['bytes']+=1
        recount(traces[node])
    elif name=='late-acquisition':
        acquired['resourceSequence']=begin['resourceSequence'];rows.sort(key=lambda v:v['resourceSequence']);renumber(value)
    elif name=='return-before-release':
        returned['resourceSequence']=r.close.allocations(traces[node])[owner]['end']-1
        rows.sort(key=lambda v:v['resourceSequence']);renumber(value)
    elif name=='boolean-resource-point':acquired['resourceSequence']=True
    else:raise AssertionError(name)


def replay(traces,closes,expected):
    original=r.replay(traces,closes,expected);results=[]
    for name,reason in NEGATIVES.items():
        altered=copy.deepcopy((traces,closes));mutate(*altered,name)
        try:r.replay(*altered,expected)
        except ValueError as error:
            r.need(str(error)==reason,f'direct export negative {name}: {error}')
            results.append(dict(case=name,status='REJECT',reason=str(error)))
        else:raise ValueError('direct export negative accepted: '+name)
    return dict(original=original,negatives=results)


def validate(root,profile='stable'):
    r.need(profile in ('stable','5-REPLACE-required-four'),'direct export original profile')
    root=Path(root);before=a.collection.inventory(root)
    original=a.validate(root,profile,control_closes=True,export_ownership=True,direct_exports=True)
    index,traces,boundaries,events=a.load(root);closes=r.close.load(root,index)
    if profile=='stable':
        states,rounds,selection,_=r.native.physical(root,confirmed_retention=True)
        expected=r.derive(states,rounds,selection,events,boundaries)
    else:
        from . import required_four_direct_exports as required
        reader=required.floors.maintenance.Replay(root);reader.run()
        r.need(reader.events==events,'direct export original event input')
        expected=required.derive(reader,boundaries)
    result=replay(traces,closes,expected)
    if profile!='stable':result['original']['scope']='required-four-native-direct-export-ownership'
    r.need(a.collection.inventory(root)==before,'direct export original changed')
    return dict(status='PASS',profile=profile,precondition=original,**result,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--profile',choices=('stable','5-REPLACE-required-four'),default='stable');args=p.parse_args()
    print(json.dumps(validate(args.root,args.profile),sort_keys=True))
