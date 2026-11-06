"""Exact mutations of original-derived export bindings, never receipt authority."""
import copy
from . import export_allocation_coverage as r

NEGATIVES={
    **{name:'export coverage complete original allocation set' for name in
       ('missing-all','missing-session','missing-direct','missing-probe','missing-one','extra-allocation','foreign-owner','foreign-node')},
    'mismatched-key':'export coverage exact allocation keys',
    'wrong-scope':'export coverage original ownership scope',
    'wrong-role':'export coverage original content identity',
    'wrong-digest':'export coverage original content identity',
    'wrong-bytes':'export coverage original extent and lifetime',
    'shifted-lifetime':'export coverage original extent and lifetime',
    'late-end':'export coverage original extent and lifetime',
    'boolean-bytes':'export coverage exact content binding',
    'unknown-field':'export coverage exact content binding',
    'duplicate-value':'export coverage duplicate allocation proof',
}


def mutate(bindings,name):
    r.need(name in NEGATIVES,'export coverage declared mutation')
    key=sorted(bindings)[0];value=bindings[key]
    if name=='missing-all':bindings.clear()
    elif name in ('missing-session','missing-direct','missing-probe'):
        scope=name.removeprefix('missing-')
        for k in [k for k,v in bindings.items() if v['scope']==scope]:del bindings[k]
    elif name=='missing-one':del bindings[key]
    elif name in ('extra-allocation','foreign-owner','foreign-node'):
        fresh=(key[0]+'-foreign',key[1]) if name=='foreign-node' else (key[0],key[1]+'-foreign')
        r.need(fresh not in bindings,'export coverage negative identity collision')
        bindings[fresh]=dict(value,node=fresh[0],owner=fresh[1])
        if name!='extra-allocation':del bindings[key]
    elif name=='mismatched-key':value['owner']+='-foreign'
    elif name=='wrong-scope':value['scope']=next(v for v in r.SCOPES if v!=value['scope'])
    elif name=='wrong-role':value['role']=next(v for v in sorted(r.exports.ROLES) if v!=value['role'])
    elif name=='wrong-digest':value['binding']=('0' if value['binding'][0]!='0' else '1')+value['binding'][1:]
    elif name=='wrong-bytes':value['bytes']+=1
    elif name=='shifted-lifetime':value['start']+=1;value['end']+=1
    elif name=='late-end':value['end']+=1
    elif name=='boolean-bytes':value['bytes']=True
    elif name=='unknown-field':value['invented']=True
    elif name=='duplicate-value':bindings[sorted(bindings)[1]]=dict(value)


def replay(traces,closes,bindings,progress=None):
    r.replay(traces,closes,bindings)
    r.need({v['scope'] for v in bindings.values()}==set(r.SCOPES),'export coverage all three original scopes required')
    result=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(bindings);mutate(changed,name)
        try:r.replay(traces,closes,changed)
        except ValueError as error:r.need(str(error)==reason,'export coverage unrelated negative: '+name+': '+str(error))
        else:raise ValueError('export coverage accepted mutation: '+name)
        result.append(dict(case=name,status='REJECTED',reason=reason))
        if progress:progress(dict(stage='export-allocation-negatives',case=name,completed=len(result),total=len(NEGATIVES)))
    return result
