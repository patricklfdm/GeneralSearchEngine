"""Coherent negative replay of original multi-session resource bindings."""
import copy
from . import native_source_resources as r
from .floor_resource_negatives import recount

NEGATIVES={
    'request-size':'native source resources original buffer extent',
    'response-size':'native source resources original buffer extent',
    'session-size':'native source resources original buffer extent',
    'trace-size':'native source resources trace extent',
    'request-binding':'native source resources request coverage',
    'response-binding':'native source resources original response/cache coverage',
    'session-binding':'native source resources original response/cache coverage',
    'trace-binding':'native source resources original response/cache coverage',
    'mixed-legacy':'native source resources mixed legacy owners',
    'downgraded-legacy':'native source resources required original bindings absent',
    'request-copy-size':'native source resources original transport copy',
    'response-after-session-close':'native source resources original response/cache coverage',
    'response-before-read':'native source resources first response allocation',
    'cache-size':'native source resources completed cache extent',
    'cache-after-response-release':'native source resources original response/cache coverage',
    'unobserved-buffer':'native source resources unobserved source reservations',
    'unexpected-growth':'native source resources unexpected growth',
}


def mutate(data,name):
    events,wires,traces,points,ids,root=data;lives,_,_=r.scan(traces)
    role={'request':'source-request','response':'source-response','session':'source-session','trace':'transfer-trace'}.get(name.split('-')[0])
    if role:
        key,life=next((k,v) for k,v in lives.items() if v['role']==role);rows=traces[life['node']]['changes']
    if name.endswith('-size') and name not in ('cache-size','request-copy-size') or name.endswith('-binding'):
        for row in rows:
            for charge in row['removed']+row['added']:
                if charge['owner']!=life['owner']:continue
                if name.endswith('-binding'):charge['owner']=charge['owner'].replace(life['binding'],'0'*64)
                elif role!='transfer-trace' or charge['bytes']==1024:charge['bytes']+=1
    elif name in ('mixed-legacy','downgraded-legacy'):
        selected=[next(iter(lives))] if name=='mixed-legacy' else list(lives)
        rename={k[1]:v['role']+'-'+r.OWNER.fullmatch(k[1])[3] for k,v in lives.items() if k in selected}
        for trace in traces.values():
            for row in trace['changes']:
                for charge in row['removed']+row['added']:charge['owner']=rename.get(charge['owner'],charge['owner'])
    elif name=='request-copy-size':
        at=next(i for i,e in enumerate(events) if e['event'] in r.network.SENDS and e['kind']=='CHUNK')
        node=events[at]['node'];owner='transport-request-send-'+events[at]['connection']['id']
        for row in traces[node]['changes']:
            for charge in row['removed']+row['added']:
                if charge['owner']==owner:charge['bytes']+=1
    elif name in ('response-after-session-close','response-before-read'):
        net=r.network.replay(events,wires,ids,root);row=next(v for v in net['rows'] if v['answer']=='SOURCE_OFFER');node=row['request']['recipient']['node']
        if name=='response-after-session-close':
            meta=next(v for v in lives.values() if v['node']==node and v['role']=='source-session' and v['binding']==r.component.binding(row['request']))
            points[row['offered']]['sequence']=meta['end']
        else:
            response=next(v for v in lives.values() if v['node']==node and v['role']=='source-response' and v['binding']==row['requestHash'])
            points[row['received']]['sequence']=response['start']
    elif name in ('cache-size','cache-after-response-release'):
        life=next(v for v in lives.values() if v['role']=='transfer-trace' and v['growth']);rows=traces[life['node']]['changes'];pos=life['growth'][0][0]
        if name=='cache-size':
            for i,row in enumerate(rows[pos:],pos):
                for charge in ([] if i==pos else row['removed'])+row['added']:
                    if charge['owner']==life['owner']:charge['bytes']+=1
        else:rows[pos],rows[pos+1]=rows[pos+1],rows[pos]
    elif name=='unobserved-buffer':
        c=dict(unit='CONTROL',owner='source-request-'+'0'*64+'-00000000-0000-0000-0000-000000000099',bytes=1,claimSource='')
        traces['node-1']['changes'].extend([dict(event='RESERVE',removed=[],added=[c]),dict(event='RELEASE',removed=[c],added=[])])
    elif name=='unexpected-growth':
        life=next(v for v in lives.values() if v['role']=='source-request');rows=traces[life['node']]['changes'];pos=life['start']
        c=copy.deepcopy(rows[pos]['added'][0]);grown=dict(c,bytes=c['bytes']+1)
        rows.insert(pos+1,dict(event='CONTROL_GROW',removed=[c],added=[grown]))
        for row in rows[pos+2:]:
            for charge in row['removed']+row['added']:
                if charge['owner']==c['owner']:charge['bytes']+=1
        for point in points:
            if point['node']==life['node'] and point['sequence']>pos:point['sequence']+=1
    recount(traces,points)


def replay(data):
    original=r.replay(*data);results=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(data);mutate(changed,name)
        try:r.replay(*changed)
        except ValueError as error:r.need(str(error)==reason,'native source unrelated negative: '+name+': '+str(error))
        else:raise ValueError('native source accepted negative: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)
