"""Classify an undelivered unused PROMISE in the installation/first-slot gap.

Original event positions are never changed. Full grant maintenance replay still
checks every continuation callback before this reply; none becomes vote authority.
"""
from . import node_grant_maintenance as g

p,n,c,e,f,need=g.p,g.n,g.c,g.e,g.f,g.need


def collect(root,events,entries,sent,boundaries,derived):
    need(len(boundaries)==9,'node late prepare reconciled history scope')
    phases={};limits={};ignored=set();reported=[]
    for ordinal,number in ((0,1),(3,2),(6,3)):
        start,stop=boundaries[ordinal]
        upper=next((i for i in range(stop+1,len(events)) if events[i]['event'].startswith('ROUND_')),None)
        if upper is None or events[upper]['event']!='ROUND_SLOT_BEGIN':continue
        late=[v for v in entries if v['kind']=='PREPARE' and stop<v['offered']<upper]
        if not late:continue
        selected=f.decode((root/f'selected-{number}.gsr').read_bytes(),'records','SELECTED')
        installed=p.net.a.group(root,f'installed-{number}')
        voters={v['voter'] for v in selected['sources']}
        local_promise=p.net.a.frozen(installed['node-1'],selected['ballot'])[0]
        for row in late:
            q=row['request'];peer=q['recipient']['node'];digest=e.digest(f.encode('wire','PREPARE',q))
            attempts=sent.get(digest,[])
            need(q['sender']['node']=='node-1' and peer not in voters and q['ballot']==selected['ballot']
                 and (selected['ballot']['counter'],peer) in derived,
                 'node late prepare unselected maintained owner')
            need(attempts and all(start<v['at']<stop and v['received'] is not None and
                 start<v['received']<stop for v in attempts), 'node late prepare original request interval')
            same=[v for v in entries if v['request']==q]
            basis=p.net.a.frozen(installed[peer],selected['ballot'])[1]
            need(q['payload']==dict(promise=e.digest(local_promise)) and
                 all(v['answer']=='PROMISE' and not v['deliveries'] and
                     v['response']['payload']==dict(basis=e.digest(basis)) for v in same),
                 'node late prepare exact undelivered original grant')
            need(row['offered'] not in limits,'node late prepare duplicate response')
            limits[row['offered']]=(start,stop,upper)
            # These force callbacks are independently consumed by Replay's exact
            # source/floor/release transaction. Other slot work stays forbidden.
            ignored.update(i for i in range(stop+1,row['offered']) if events[i]['node']==peer
                           and events[i]['event'].startswith(g.PREFIXES))
            ignored.add(row['offered'])
            reported.append(dict(node=peer,ballot=selected['ballot']['counter'],response=row['offered'],
                                 installed=stop,slotBegin=upper,delivered=False,authority=False))
        phases[ordinal]=dict(entries=late,upper=upper)
    return dict(phases=phases,limits=limits,events=ignored,reported=reported)


NEGATIVES={
    'late-prepare-invented-delivery':'node late prepare exact undelivered original grant',
    'late-prepare-substituted-basis':'node late prepare exact undelivered original grant',
    'late-release-missing-return':'node grant maintenance complete original callbacks',
}


def mutate(root,name):
    import base64
    raw=root/'history';events=n.read(raw/'events.json');wire=n.read(raw/'wire.json')
    prepare={e.digest(base64.b64decode(v['response'])) for v in wire if n.transfer.t.wire(v['request'])[0]=='PREPARE'}
    candidates=[]
    for stop in (i for i,v in enumerate(events) if v['event']=='ROUND_INSTALLED'):
        upper=next(i for i in range(stop+1,len(events)) if events[i]['event'].startswith('ROUND_'))
        if events[upper]['event']=='ROUND_SLOT_BEGIN':
            candidates.extend(i for i in range(stop+1,upper) if events[i]['event']=='WIRE_RESPONSE' and events[i]['response'] in prepare)
    need(candidates,'late original reply mutation target');at=candidates[0];peer=events[at]['node']
    response=events[at]['response']
    if name=='late-release-missing-return':
        lower=max(i for i in range(at) if events[i]['node']==peer and events[i]['event']=='GRANT_BEFORE_RETURN')
        index=next(i for i in range(lower+1,at) if events[i]['node']==peer and events[i]['event']=='FLOOR_RELEASE_BEFORE_RETURN')
        events.pop(index)
    elif name=='late-prepare-invented-delivery':
        events.insert(at+1,dict(node='node-1',incarnation=2,event='NETWORK_RECEIVED',kind='PROMISE',response=response))
    elif name=='late-prepare-substituted-basis':
        rows=[v for v in wire if e.digest(base64.b64decode(v['response']))==response]
        need(len(rows)==1,'one late original reply')
        value=f.decode(base64.b64decode(rows[0]['response']),'wire','PROMISE');value['payload']['basis']='0'*64
        changed=f.encode('wire','PROMISE',value);rows[0]['response']=base64.b64encode(changed).decode()
        events[at]['response']=e.digest(changed)
    else:raise ValueError(name)
    # The network reader runs before child observation admission and must reject
    # the specific fabricated authority, not count a later transcript mismatch.
    (raw/'events.json').write_bytes(f.canonical(events));(raw/'wire.json').write_bytes(f.canonical(wire))
