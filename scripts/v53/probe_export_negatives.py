"""Exact negatives for declared probe ownership, with unmodified replay first."""
import copy
from . import probe_export_evidence as r
from . import direct_export_negatives as direct

BASE={
 'missing-acquisition':'control close original probe call',
 'duplicate-acquisition':'control close original probe acquisition',
 'missing-close-begin':'control close probe release before return',
 'missing-return':'control close incomplete probe cleanup',
 'wrong-call':'control close original probe call',
 'return-before-release':'control close probe release before return',
 'foreign-binding':'probe export original allocation binding',
 'wrong-extent':'probe export original extent',
 'late-acquisition':'probe export original body interval',
 'late-call-start':'probe export original allocation binding',
 'boolean-boundary':'probe export original operation boundaries',
 'unobserved-probe':'probe export complete observed cohort',
}


def mutate(traces,closes,plans,case):
    plan=plans[0];node=plan['node'];value=closes[node];rows=value['rows']
    acquired=next(row for row in rows if row['event']=='PROBE_BORROW_ACQUIRED');name=acquired['owner']
    begin=next(row for row in rows if row['event']=='PROBE_BORROW_CLOSE_BEGIN' and row['owner']==name)
    returned=next(row for row in rows if row['event']=='PROBE_BORROW_RETURNED' and row['owner']==name)
    life=r.close.allocations(traces[node])[name]
    if case=='missing-acquisition':rows.remove(acquired);direct.renumber(value)
    elif case=='duplicate-acquisition':rows.insert(rows.index(acquired),copy.deepcopy(acquired));direct.renumber(value)
    elif case=='missing-close-begin':rows.remove(begin);direct.renumber(value)
    elif case=='missing-return':rows.remove(returned);direct.renumber(value)
    elif case=='wrong-call':returned['call']=-1
    elif case=='return-before-release':
        begin['resourceSequence']=min(begin['resourceSequence'],life['end']-1);returned['resourceSequence']=life['end']-1
    elif case=='foreign-binding':
        replacement=name.replace(plan['binding'],'e'*64)
        for row in traces[node]['changes']:
            for charge in row['added']+row['removed']:
                if charge['owner']==name:charge['owner']=replacement
        acquired['owner']=begin['owner']=returned['owner']=replacement
    elif case=='wrong-extent':
        for row in traces[node]['changes']:
            for charge in row['added']+row['removed']:
                if charge['owner']==name:charge['bytes']+=1
        direct.recount(traces[node])
    elif case=='late-acquisition':
        acquired['resourceSequence']=plan['through']+1;begin['resourceSequence']=max(begin['resourceSequence'],acquired['resourceSequence'])
    elif case=='late-call-start':plan['before']=life['start']
    elif case=='boolean-boundary':plan['before']=True
    elif case=='unobserved-probe':
        rows.remove(acquired);rows.remove(begin);rows.remove(returned);direct.renumber(value)
    elif case=='missing-child':acquired['children']=[]
    elif case=='child-after-parent':
        child=r.close.allocations(traces[node])[acquired['children'][0]];changes=traces[node]['changes']
        first,last=child['end'],life['end'];changes[first],changes[last]=changes[last],changes[first]
        changes[first]['sequence']=first;changes[last]['sequence']=last;direct.recount(traces[node])
    else:raise ValueError('probe export unknown negative')


def replay(traces,closes,plans):
    original=r.replay(traces,closes,plans);negative=dict(BASE)
    if plans[0]['children']:
        negative['missing-child']='control close original probe group'
        negative['child-after-parent']='control close probe child release order'
    results=[]
    for case,reason in negative.items():
        changed=copy.deepcopy((traces,closes,plans));mutate(*changed,case)
        try:r.replay(*changed)
        except ValueError as error:r.need(str(error)==reason,'probe export unrelated rejection: '+case+': '+str(error))
        else:raise ValueError('probe export negative accepted: '+case)
        results.append(dict(case=case,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)
