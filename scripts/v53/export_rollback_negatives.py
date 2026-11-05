"""Exact failed-constructor cleanup negatives; original must pass first."""
import copy
from . import export_rollback_evidence as r
from . import direct_export_negatives as direct

BASE={
 'missing-begin':'control close original rollback return',
 'duplicate-begin':'control close original rollback invocation',
 'missing-return':'control close incomplete rollback',
 'wrong-call':'control close original rollback return',
 'return-before-release':'control close rollback release before return',
 'foreign-request':'export rollback original request allocation',
 'wrong-extent':'export rollback original metadata extent',
 'late-call-start':'export rollback original operation interval',
 'early-call-end':'export rollback original operation interval',
 'boolean-boundary':'export rollback original operation boundaries',
 'unobserved-pair':'export rollback complete observed calls',
}


def mutate(traces,closes,cases,case):
    plan=r.expectation(cases[0]);node=plan['node'];value=closes[node];rows=value['rows']
    begin=next(row for row in rows if row['event']=='EXPORT_ROLLBACK_BEGIN');name=begin['owner']
    returned=next(row for row in rows if row['event']=='EXPORT_ROLLBACK_RETURNED' and row['owner']==name)
    life=r.close.allocations(traces[node])[name]
    if case=='missing-begin':rows.remove(begin);direct.renumber(value)
    elif case=='duplicate-begin':rows.insert(rows.index(begin),copy.deepcopy(begin));direct.renumber(value)
    elif case=='missing-return':rows.remove(returned);direct.renumber(value)
    elif case=='wrong-call':returned['call']=-1
    elif case=='return-before-release':returned['resourceSequence']=life['end']-1
    elif case=='foreign-request':
        replacement=name.replace(plan['requestDigest'],'e'*64)
        for row in traces[node]['changes']:
            for charge in row['added']+row['removed']:
                if charge['owner']==name:charge['owner']=replacement
        begin['owner']=returned['owner']=replacement
    elif case=='wrong-extent':
        for row in traces[node]['changes']:
            for charge in row['added']+row['removed']:
                if charge['owner']==name:charge['bytes']+=1
        direct.recount(traces[node])
    elif case=='late-call-start':cases[0]['before']=life['start']
    elif case=='early-call-end':cases[0]['after']=life['end']-1
    elif case=='boolean-boundary':cases[0]['before']=True
    elif case=='unobserved-pair':rows.remove(begin);rows.remove(returned);direct.renumber(value)
    elif case=='missing-child':begin['children']=[]
    elif case=='child-after-parent':
        child=r.close.allocations(traces[node])[begin['children'][0]];changes=traces[node]['changes']
        first,last=child['end'],life['end'];changes[first],changes[last]=changes[last],changes[first]
        changes[first]['sequence']=first;changes[last]['sequence']=last
        begin['resourceSequence']=first-1;direct.recount(traces[node])
    else:raise ValueError('export rollback unknown negative')


def replay(traces,closes,cases):
    original=r.replay(traces,closes,cases);negative=dict(BASE)
    if r.expectation(cases[0])['children']:
        negative['missing-child']='export rollback exact owned group'
        negative['child-after-parent']='control close rollback child release order'
    results=[]
    for case,reason in negative.items():
        changed=copy.deepcopy((traces,closes,cases));mutate(*changed,case)
        try:r.replay(*changed)
        except ValueError as error:r.need(str(error)==reason,'export rollback unrelated rejection: '+case+': '+str(error))
        else:raise ValueError('export rollback negative accepted: '+case)
        results.append(dict(case=case,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)
