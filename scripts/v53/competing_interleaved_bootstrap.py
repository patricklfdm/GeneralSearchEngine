"""Derive overlapping bootstrap grants, local installs and maintenance.

Every owner is reduced in its original order. Final/captured copies only compare
against derived bytes. Background work on the unselected owner may finish after
ROUND_INSTALLED; it never contributes to the winning pair or its client slots.
"""
import copy
from . import competing_campaign_prefix as prefix
from . import node_grant_maintenance as maintenance

p,f,disk,need,sha=prefix.p,prefix.f,prefix.disk,prefix.need,prefix.sha
WIRE={'NETWORK_SEND','NETWORK_REQUEST','NETWORK_RECEIVED','WIRE_RESPONSE'}


def needed(r):
    stop=min((i for i,v in enumerate(r.events) if v['event']=='INSTALL_RESERVED'),default=len(r.events))
    return any(v['capturedEvent']>=stop for v in r.by_basis.values())


def floor(r,group,lower,start,end):
    node=r.events[start]['node'];m=maintenance
    own=[v for v in r.rows if v['request']['sender']['node']==node and lower<v['sent']<=end]
    phase=m.p.net.a.Phase(r.events,own,lower,end+1,r.identities)
    probes=[v for v in own if v['kind']=='STATUS_PROBE']
    need(len(probes)==1,'competing continuation floor probe')
    ballot=probes[0]['request']['ballot'];peer=probes[0]['request']['recipient']['node'];voters=(node,peer)
    cap=[v for v in r.by_basis.values() if v['node']==node and v['ballot']==ballot]
    need(len(cap)==1,'competing continuation floor original ballot')
    if cap[0]['capturedEvent']>start:
        need(any(v['kind']=='PREPARE' and v['request']['recipient']['node']==node and v['request']['ballot']==ballot
                 and v['received'] is not None and v['received']<lower for v in r.attempts),
             'competing continuation floor incoming authority')
    held=m.covering_floor(group[node],{v:group[v] for v in voters},node)
    copies={}
    for v in voters:
        path,members,packet=disk.current(group[v]);manifest=group[v][path+'generation.gsr']
        copies[v]=dict(node=v,members=members,manifest=manifest,packet=packet,identity=r.identities[v])
    originals={sha(v['manifest']):dict(v['members'],**{'generation.gsr':v['manifest']}) for v in copies.values()}
    events,_,_,_=m.floor.transaction(originals,held['floor-copies/floor.gsr'],handoff=True)
    expected=['FLOOR_COPY_BEFORE_RETURN']*2+[v['event'] for v in events]
    current=disk.current(held)[0]
    if any(k.startswith('generations/') and not k.startswith(current) and k!=current[:-1] for k in held):
        for peer in voters:
            before=held[p.n.s.FILE]
            held[p.n.s.FILE]=p.observation.observe_same_cut(before,group[node],group[peer])
            if held[p.n.s.FILE]!=before:expected+=list(p.n.s.r.POINTS)
        held,steps,_=m.retirement.generation_plan(held,node,copies)
        expected += [point for point,_ in steps]
    _,members,packet=disk.current(held)
    available=m.retirement.r.peer.t.confirmation.endpoints(packet,members.get('ancestry.gsr',b''))
    held,decisions=m.retirement.source_plans(held,node,available)
    expected += [point for decision in decisions for point,_ in decision['steps']]
    record=f.encode('records','RETIREMENT',dict(root=packet['capsule']['root'],node=node,
        floor=sha(held['floor-copies/floor.gsr']),selector=sha(held['selector.gsr']),
        files=[dict(path=k,size=len(v),sha256=sha(v)) for k,v in sorted(held.items()) if k.startswith('floor-copies/') and v is not None]))
    released=m.release.transaction(m.retirement.physical(held),record)
    after={k:v for k,v in held.items() if k!='floor-copies' and not k.startswith('floor-copies/')}
    need(released[-1][1]==m.retirement.physical(after),'competing continuation released bytes')
    expected += [point for point,_ in released]
    actual=[v for v in r.events[lower+1:end+1] if v.get('node')==node and v['event'].startswith(m.PREFIXES)]
    need(actual==[dict(node=node,event=v) for v in expected],'competing continuation exact floor callbacks')
    need(all(v['delivered'] is not None and lower<v['sent']<v['received']<v['offered']<v['delivered']<start for v in own),
         'competing continuation floor delivered before reservation')
    m.transfers(phase,group,node,voters,ballot,lower,end+1)
    network=phase.finish();traces=network.pop('_traces')
    need(not traces&r.maintenance_traces,'competing continuation reused floor trace');r.maintenance_traces.update(traces)
    detail=dict(node=node,voters=list(voters),start=start,end=end,retiredSources=len(decisions),forceCallbacks=len(expected),network=network,
                decisions=[{k:v for k,v in d.items() if k!='steps'} for d in decisions])
    return after,detail


def run(r):
    from . import competing_campaign_publication as pub
    selections=r.choices();r.grant_requests()
    rounds=[(i,v) for i,v in enumerate(r.events) if v['event']=='ROUND_INSTALLED']
    need(len(rounds)==1,'competing continuation one activated round')
    at,row=rounds[0];chosen,selected=p.record(row,'records','SELECTED')
    voters={v['voter'] for v in selected['sources']}
    limits={n:at if n in voters else max([at]+[v['capturedEvent'] for v in r.by_basis.values() if v['node']==n])+1 for n in r.initial}
    need(all(v['capturedEvent']<limits[v['node']] for v in r.by_basis.values()) and
         all(v['forced']<at for v in r.bindings),'competing continuation bootstrap boundaries')
    installs=[];spans=[];actions=[];covered=set()
    for i,event in enumerate(r.events):
        node=event.get('node');point=event['event']
        if node not in limits or i>=limits[node]:continue
        if point=='INSTALL_RESERVED':
            end=next(j for j in range(i+1,limits[node]) if r.events[j]==dict(node=node,event='INSTALL_BEFORE_RETURN'))
            bound=max((v for v in r.bindings if v['node']==node and v['forced']<i),key=lambda v:v['forced'])
            installs.append(dict(node=node,start=i,end=end,selection=bound['selection'],bound=bound))
            actions.extend(((i,'install-start',installs[-1]),(end,'install-end',installs[-1])))
        elif point=='FLOOR_RESERVED':
            end=next(j for j in range(i+1,len(r.events)) if r.events[j]==dict(node=node,event='FLOOR_RELEASE_BEFORE_RETURN'))
            copies=[j for j in range(i) if r.events[j]==dict(node=node,event='FLOOR_COPY_BEFORE_RETURN')]
            need(len(copies)>=2,'competing continuation complete floor copies');lower=copies[-2]-1
            span=dict(node=node,start=i,end=end,lower=lower);spans.append(span)
            actions.extend(((lower+1,'floor-start',span),(end,'floor-end',span)))
    need(len(installs)==3 and len(spans)==2 and len(r.by_basis)==5 and len(r.selections)==2,
         'competing continuation unsupported physical shape')
    opened=[(i,v) for i,v in enumerate(r.events[:min(v['start'] for v in installs)]) if v['event']=='NODE_OPEN']
    need([v for _,v in opened]==[dict(node=n,event='NODE_OPEN') for n in sorted(r.initial)],'competing continuation opened owners')
    end=opened[-1][0];p.wait.lifecycle(p.n.read(r.root/'calls.json'),[v for v in r.events[:end+1] if v['event']!='NODE_OPEN'],r.initial)
    covered.update(range(end+1));tx=prefix.ballot.allocations(r.events[:at],tuple(r.initial),None)
    actions += [(v['end'],'allocate',v) for v in tx]
    actions += [(v['returnEvent'],'grant',v) for v in r.by_basis.values()]
    actions += [(v['capturedEvent'],'compare',v) for v in r.by_basis.values()]
    actions += [(v['forced'],'select',v) for v in r.bindings]
    group=copy.deepcopy(r.initial);identifiers=set();r.allocations=[];r.transactions=[];r.maintenance_traces=set();r.generation_changes=[]
    for pos,kind,value in sorted(actions,key=lambda v:v[0]):
        node=value['node'];files=group[node]
        if kind=='allocate':
            old=f.decode(files['allocator.gsr'],'records','ALLOCATOR');journal=disk.journal(files['grants.gsr'],old['root'],node)
            counter=max(old['counter'],*[v['ballot']['counter'] for _,_,v in journal])+1
            need(counter<=2**63-2,'competing continuation allocator capacity')
            files['allocator.gsr']=f.encode('records','ALLOCATOR',dict(old,counter=counter))
            r.allocations.append(dict(value,ballot=dict(counter=counter,proposer=node,incarnation=r.identities[node]['storage'])))
        elif kind=='grant':
            if value['ballot']['proposer']==node:
                need(f.decode(files['allocator.gsr'],'records','ALLOCATOR')['counter']==value['ballot']['counter'],'competing continuation local reservation')
            group[node]=prefix.prepare(files,value['ballot'],value['basis'],identifiers)
        elif kind=='compare':need(files==r.original[value['basisSha256']],'competing continuation exact captured files: '+node)
        elif kind=='select':
            files['grants.gsr']+=r.selections[value['selection']]['raw'];disk.journal(files['grants.gsr'],selected['root'],node)
        elif kind=='install-start':
            value['files']=pub.selected_install(group,r.selections[value['selection']]['raw'],owners=(node,))[node]
            path,members,_=disk.current(value['files']);full=dict(members,**{'generation.gsr':value['files'][path+'generation.gsr']})
            pub.installs.interval(r.events,node,None,value['bound']['forced'],value['end']+1,full,
                                 ['SELECTED_BEFORE_RETURN'],'competing continuation installation writes')
            covered.update(j for j in range(value['bound']['forced']+1,value['end']+1) if r.events[j].get('node')==node and
                           (r.events[j]['event'].startswith(('INSTALL_','CURRENT_')) or r.events[j]['event']=='SELECTED_BEFORE_RETURN'))
        elif kind=='install-end':
            group[node]=value['files'];r.generation_changes.append(dict(node=node,end=pos,files=copy.deepcopy(group[node])))
        elif kind=='floor-start':value['group']=copy.deepcopy(group)
        elif kind=='floor-end':
            group[node],detail=floor(r,value['group'],value['lower'],value['start'],pos);r.transactions.append(detail)
            covered.update(j for j in range(value['lower']+1,pos+1) if r.events[j].get('node')==node and r.events[j]['event'].startswith(maintenance.PREFIXES))
    # Capture collection and choices independently bind these callback ranges.
    for cap in r.by_basis.values():
        covered.update(j for j in range(r.starts[cap['basisSha256']],cap['capturedEvent']+1) if r.events[j].get('node')==cap['node'] and
                       (r.events[j]['event'] in set(prefix.ballot.PROMISE)|{'CURRENT_BEFORE_CAPTURE','GRANT_BEFORE_RETURN',prefix.g.EVENT} or
                        prefix.collection.network.capture_callback(r.events[j]['event'])))
    for v in tx:covered.update(j for j in range(v['start'],v['end']+1) if r.events[j].get('node')==v['node'] and r.events[j]['event'] in prefix.ballot.WRITES)
    for bound in r.bindings:
        covered.update(j for j in range(bound['lower']+1,bound['forced']+2) if r.events[j].get('node')==bound['node'] and r.events[j]['event'] in prefix.selection_writes.WRITES)
    need(all(i in covered or v['event'] in WIRE for i,v in enumerate(r.events) if v.get('node') in limits and i<limits[v['node']]),
         'competing continuation unmodeled owner work')
    r.group=group;r.stop=at;r.interleaved=True;r.continuation_covered=covered
    r.bootstrap_offers={v['offered'] for v in r.rows if v['sent']<at and v['kind']!='HEARTBEAT'}
    # Includes the delayed unselected PROMISE, whose request preceded activation.
    need(all(v['request']['trace'] in r.maintenance_traces or v['kind'] in ('PREPARE','SELECTED','STATUS_PROBE','CHUNK','TRANSFER_COMMIT')
             for v in r.rows if v['offered'] in r.bootstrap_offers),'competing continuation response kind')
    return dict(status='PARTIAL',scope='competing-overlapped-bootstrap',precondition=dict(status='PARTIAL',scope='competing-bootstrap-campaign-prefix',
        precondition=r.precondition,capturedGrants=len(r.by_basis),competingBallots=2,distinctSelections=2,selectionWrites=selections,
        phase3Complete=False),transactions=r.transactions,installations=len(installs),capturedComparisons=len(r.by_basis),phase3Complete=False)



def activation(r,published,stop):
    from . import competing_activation_network as a
    rows=[v for v in r.rows if v['offered'] in r.bootstrap_offers and v['request']['trace'] not in r.maintenance_traces]
    upper=max(v['offered'] for v in rows)+1
    phase=a.net.net.Phase(r.events,rows,-1,upper,r.identities);lost=[]
    for allocation in r.allocations:
        node=allocation['node'];ballot=allocation['ballot'];lower=-1
        prior=f.decode(disk.current(r.initial[node])[1]['promise.gsr'],'records','PROMISE')['ballot']
        for peer in sorted(set(r.initial)-{node}):
            cut=disk.current(r.initial[peer])[2]['capsule']['cut']
            lower=phase.probe(node,peer,prior,cut,lower,allocation['start'])
        local=next(v for v in r.by_basis.values() if v['node']==node and v['ballot']==ballot)
        choice=next(v for v in r.selections.values() if v['value']['ballot']==ballot)
        own=next(v for v in r.bindings if v['node']==node and v['selection']==sha(choice['raw']))
        campaign=[v for v in r.attempts if v['kind'] in ('PREPARE','SELECTED') and v['request']['ballot']==ballot]
        need([v['request']['sequence'] for v in campaign]==list(range(1,len(campaign)+1)) and
             len({v['request']['trace'] for v in campaign})==1,'competing continuation campaign sequence')
        trace=campaign[0]['request']['trace']
        for remote in [v for v in r.by_basis.values() if v['node']!=node and v['ballot']==ballot]:
            peer=remote['node'];bound=next((v for v in r.bindings if v['node']==peer and v['selection']==sha(choice['raw'])),None)
            request=next(v for v in campaign if v['kind']=='PREPARE' and v['request']['recipient']['node']==peer)
            start=a.point(r,remote,'CURRENT_BEFORE_CAPTURE')
            value=phase.transfer(peer,node,a.net.net.record(local['promise']),ballot,request['received'],start)
            a.delivered_before(value,request['received'],start,'competing continuation incoming promise delivery')
            replies=phase.take('PREPARE',node,peer)
            need(len(replies)==1,'competing continuation exact prepare response');reply=replies[0]
            need(reply['request']==request['request'] and reply['answer']=='PROMISE' and
                 reply['response']['payload']==dict(basis=remote['basisSha256']) and
                 request['received']<start<remote['returnEvent']<reply['offered'],
                 'competing continuation prepare authority')
            if bound is None:
                need(reply['delivered'] is None and reply['offered']>stop and
                     peer not in {v['voter'] for v in choice['value']['sources']},
                     'competing continuation unused late grant')
                lost.append(reply['offered']);continue
            need(reply['delivered'] is not None and reply['offered']<reply['delivered']<own['forced'],
                 'competing continuation selected promise delivery')
            value=phase.transfer(node,peer,a.original_source(r,remote,node),ballot,reply['delivered'],own['forced'])
            a.delivered_before(value,reply['delivered'],min(own['forced'],a.end_of_source(r,remote)),
                               'competing continuation selected basis delivery')
            selection_start=max(i for i,v in enumerate(r.events[:bound['forced']]) if v==dict(node=peer,event='SELECTED_BEFORE_WRITE'))
            request=next(v for v in campaign if v['kind']=='SELECTED')
            for variants,begin in ((a.net.net.record(choice['raw']),own['forced']),
                                   (a.original_source(r,local,peer),local['capturedEvent'])):
                value=phase.transfer(peer,node,variants,ballot,begin,selection_start)
                a.delivered_before(value,max(begin,request['received']),min(selection_start,a.end_of_source(r,local)),
                                   'competing continuation remote choice delivery')
            replies=phase.take('SELECTED',node,peer)
            need(len(replies)==1,'competing continuation exact install response');reply=replies[0]
            installed=next(v for v in r.generation_changes if v['node']==peer and
                disk.current(v['files'])[1]['selected.gsr']==choice['raw'])
            need(reply['request']==request['request'] and reply['answer']=='INSTALL_ACK' and
                 reply['response']['payload']==dict(selection=sha(choice['raw']),cut=choice['value']['cut']) and
                 own['forced']<request['sent']<request['received']<selection_start<installed['end']<reply['offered'],
                 'competing continuation installed response authority')
            if reply['delivered'] is None:
                higher=[v for v in r.attempts if v['kind']=='PREPARE' and v['request']['recipient']['node']==node and
                        v['received'] is not None and v['received']<reply['offered'] and
                        prefix.journal.order(v['request']['ballot'])>prefix.journal.order(ballot)]
                need(higher and not any(v['node']==node and disk.current(v['files'])[1]['selected.gsr']==choice['raw']
                                       for v in r.generation_changes),'competing continuation lost install fenced')
                lost.append(reply['offered'])
            else:
                need(any(v['node']==node and disk.current(v['files'])[1]['selected.gsr']==choice['raw']
                         for v in r.generation_changes),'competing continuation ACK without matching local install')
                local_start=next(i for i,v in enumerate(r.events) if i>own['forced'] and v==dict(node=node,event='INSTALL_RESERVED'))
                need(reply['offered']<reply['delivered']<local_start<stop,'competing continuation winning install delivery')
        need(trace not in phase.used,'competing continuation distinct campaign trace');phase.used.add(trace)
    summary=phase.finish();traces=summary.pop('_traces')
    attempts=[v for v in r.attempts if v['sent']<stop and v['kind']!='HEARTBEAT']
    need({v['sent'] for v in attempts}=={v['sent'] for v in r.rows if v['offered'] in r.bootstrap_offers},
         'competing continuation complete original attempts')
    need(len(lost)==2 and all(v['offered'] in lost or v['delivered'] is not None and
             v['sent']<v['received']<v['offered']<v['delivered'] for v in r.rows if v['offered'] in r.bootstrap_offers),
         'competing continuation delivered response inventory')
    need(not traces&r.maintenance_traces and not (traces|r.maintenance_traces)&
         {v['request']['trace'] for v in r.rows if v['offered'] not in r.bootstrap_offers},
         'competing continuation disjoint campaign traces')
    covered=summary['exchanges']+sum(v['network']['exchanges'] for v in r.transactions)
    net=published['publicationNetwork']
    need(covered==len(r.bootstrap_offers) and covered+net['exchanges']+net['heartbeat']['responses']==len(r.rows),
         'competing continuation complete exchange coverage')
    return dict(status='PARTIAL',scope='competing-bootstrap-original-activation-network',precondition=published,
        campaigns=len(r.allocations),activation=summary,pregrantLosses=[],interleavedBootstrap=True,
        undeliveredOriginalResponses=len(lost),wholeHistoryExchanges=len(r.rows),wholeHistoryAttempts=len(r.attempts),
        originalActivationNetworkQualified=True,fullNetworkQualified=True,completeExportLifetimesQualified=False,
        processDeathQualified=False,finalSourceCohortQualified=False,phase3Complete=False)


NEGATIVES={
    'lost-install-delivered':'competing continuation ACK without matching local install',
    'late-grant-delivered':'competing continuation unused late grant',
    'lost-install-selection':'competing continuation installed response authority',
    'late-grant-basis':'competing continuation prepare authority',
    'prepare-sequence':'competing continuation campaign sequence',
    'missing-floor-force':'competing continuation exact floor callbacks',
    'missing-install-force':'competing continuation installation writes',
    'unknown-owner-work':'competing continuation unmodeled owner work',
    'missing-selected-basis-delivery':'competing continuation selected promise delivery',
    'missing-higher-fence':'competing continuation lost install fenced',
}


def qualify(root):
    from pathlib import Path
    from . import competing_export_evidence as exports
    root=Path(root);before=prefix.collection.h.inventory(root)
    reader=exports.Replay(root);original=reader.run();r=reader.replay
    need(getattr(r,'interleaved',False),'competing continuation qualification shape')
    results=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(r)
        if name in ('missing-floor-force','missing-install-force','unknown-owner-work'):
            points={'missing-floor-force':('FLOOR_AUTHORITY_FORCED','FLOOR_AUTHORITY_WRITTEN'),
                    'missing-install-force':('INSTALL_MANIFEST_FORCED','INSTALL_MANIFEST_WRITTEN'),
                    'unknown-owner-work':('NETWORK_SEND','UNMODELED_WORK')}
            point,replacement=points[name]
            next(v for v in changed.events if v['event']==point)['event']=replacement
            def replay():return run(changed)
        else:
            if name=='prepare-sequence':
                next(v for v in changed.attempts if v['kind']=='PREPARE')['request']['sequence']+=10
            elif name=='missing-higher-fence':
                old=next(v for v in changed.rows if v['kind']=='SELECTED' and v['delivered'] is None)
                changed.attempts=[v for v in changed.attempts if not (v['kind']=='PREPARE' and
                    v['request']['recipient']==old['request']['sender'] and v['received'] is not None and v['received']<old['offered'])]
            else:
                target=next(v for v in changed.rows if v['kind']==('SELECTED' if name.startswith('lost-install') else 'PREPARE') and
                    (v['delivered'] is not None if name=='missing-selected-basis-delivery' else v['delivered'] is None))
                if name.endswith('delivered'):target['delivered']=target['offered']+1
                elif name.endswith('selection'):target['response']['payload']['selection']='0'*64
                elif name.endswith('basis'):target['response']['payload']['basis']='0'*64
                else:target['delivered']=None
            def replay():return activation(changed,original['precondition']['precondition'],reader.activation_at)
        try:replay()
        except ValueError as error:need(str(error)==reason,'competing continuation unrelated negative: '+name+': '+str(error))
        else:raise ValueError('competing continuation mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    need(prefix.collection.h.inventory(root)==before,'competing continuation original changed')
    return dict(original=original,negativeScope='copied-derived-claims-after-complete-original-replay',negatives=results)
