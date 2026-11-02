"""Original sends, deliveries and force dependencies for whole competition.

Consumes only the states reconstructed by competing_node_evidence. No snapshots
are manufactured as input evidence; transient states are expected-state models.
"""
import base64
import uuid
from collections import defaultdict,deque
from . import automatic_restart_network as net
from . import discovered_selection_evidence as exchange

n,c,e,f,need=net.n,net.c,net.e,net.f,net.need


def intent_sequence(identities,leader,peer):
    # MembershipFutureRetentionQuorum reserves sequence 1 for the local owner,
    # then visits sorted remote voters, regardless of the leader's node name.
    need(leader in identities and peer in identities and peer!=leader,'competing intent original remote owner')
    return sorted(set(identities)-{leader}).index(peer)+2


def raw_sends(events,entries,identities,selected):
    pending=defaultdict(deque);received=defaultdict(deque);by_hash={};sends=defaultdict(list)
    for at,row in enumerate(events):
        kind=row['event']
        if kind=='NETWORK_SEND':
            need(set(row)=={'node','event','request','kind','bytes'},'competing send shape')
            raw=base64.b64decode(row['bytes'],validate=True);frame,request=n.transfer.t.wire(row['bytes']);h=e.digest(raw)
            sender,peer=request['sender']['node'],request['recipient']['node']
            need(h==row['request'] and frame==row['kind'] and sender==row['node'] and sender!=peer
                 and request['sender']==identities.get(sender) and request['recipient']==identities.get(peer)
                 and request['root']==selected['root'] and request['view']==selected['view'],'competing original send binding')
            need(h not in by_hash or by_hash[h]==(frame,request),'competing immutable sends')
            by_hash[h]=(frame,request);sends[h].append(at);need(len(sends[h])<=3,'competing bounded send attempts')
            pending[peer,h].append(at)
        elif kind=='NETWORK_REQUEST':
            need(set(row)=={'node','event','request','kind'},'competing receive shape');h=row['request'];key=row['node'],h
            need(pending[key] and pending[key][0]<at and by_hash[h][0]==row['kind'],'competing request without original send')
            pending[key].popleft();received[key].append(at)
        elif kind=='WIRE_RESPONSE':
            need(set(row)=={'node','event','request','response'},'competing response shape');key=row['node'],row['request']
            need(received[key] and received[key][0]<at,'competing response without original request')
            received[key].popleft()
    for entry in entries:
        h=e.digest(f.encode('wire',entry['kind'],entry['request']))
        need(h in by_hash and by_hash[h]==(entry['kind'],entry['request']),'competing wire without original send')
    net.deliveries(events,entries)
    unanswered={h for (peer,h),rows in [*pending.items(),*received.items()] if rows}
    return by_hash,sends,unanswered


def activation(history,events,entries,identities,stop):
    leader=history.proposer;peer=next(v for v in history.voters if v!=leader);ballot=history.selected['ballot']
    phase=net.Phase(events,entries,-1,stop,identities);allocation=phase.at(leader,'ALLOCATOR_BEFORE_WRITE')
    previous=-1;old=f.decode(c.current(history.initial[leader])[1]['promise.gsr'],'records','PROMISE')['ballot']
    for candidate in sorted(set(identities)-{leader}):
        previous=phase.probe(leader,candidate,old,c.current(history.initial[candidate])[2]['capsule']['cut'],previous,allocation)
    local_promise,_,_,_=net.frozen(history.installed[leader],ballot)
    for node in history.voters:
        phase.ordered(node,['PROMISE_FORCED','SOURCE_DIRECTORY_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN',
            'SELECTED_FORCED','SELECTED_BEFORE_RETURN','INSTALL_SELECTOR_FORCED','INSTALL_PARENT_FORCED','INSTALL_BEFORE_RETURN'])
    phase.ordered(leader,['ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN','PROMISE_FORCED'])
    local_selected=phase.at(leader,'SELECTED_FORCED');promise,basis,raw,packet=net.frozen(history.installed[peer],ballot)
    phase.transfer(peer,leader,net.record(local_promise),ballot,phase.at(leader,'BASIS_FORCED'),phase.at(peer,'PROMISE_FORCED'))
    delivery,trace,_=phase.control('PREPARE',leader,peer,dict(promise=e.digest(local_promise)),'PROMISE',dict(basis=e.digest(basis)),ballot,
        phase.at(peer,'GRANT_BEFORE_RETURN'),local_selected)
    phase.transfer(leader,peer,[[(e.digest(basis),basis,'RECORD'),(e.digest(promise),promise,'RECORD'),
        (e.digest(packet['capsuleBytes']),raw,'CAPSULE')]],ballot,delivery,local_selected)
    phase.transfer(peer,leader,net.record(history.chosen),ballot,local_selected,phase.at(peer,'SELECTED_FORCED'))
    promise,basis,raw,packet=net.frozen(history.installed[leader],ballot)
    phase.transfer(peer,leader,[[(e.digest(basis),basis,'RECORD'),(e.digest(promise),promise,'RECORD'),
        (e.digest(packet['capsuleBytes']),raw,'CAPSULE')]],ballot,phase.at(leader,'BASIS_FORCED'),phase.at(peer,'SELECTED_FORCED'))
    delivered,_,_=phase.control('SELECTED',leader,peer,dict(selection=e.digest(history.chosen)),'INSTALL_ACK',
        dict(selection=e.digest(history.chosen),cut=history.selected['cut']),ballot,phase.at(peer,'INSTALL_BEFORE_RETURN'),
        phase.at(leader,'INSTALL_SELECTOR_FORCED'),sequence=2,trace=trace)
    return phase.finish()


def maintenance(phase,history,index,owner,ballot,upper):
    before=history.snapshots[f'before-{index}'];maintained=history.snapshots[f'maintained-{index}'];peer=next(v for v in history.voters if v!=owner)
    floor=phase.at(owner,'FLOOR_PARENT_FORCED')
    count=n.s.r.decode(maintained[owner][n.s.FILE])['revision']-n.s.r.decode(before[owner][n.s.FILE])['revision']
    phase.ordered(owner,['FLOOR_COPIES_FORCED','FLOOR_AUTHORITY_FORCED','FLOOR_PARENT_FORCED','FLOOR_BEFORE_RETURN',
        *(['RETENTION_PARENT_FORCED']*count),'RETIREMENT_DELETE_VALIDATED','RETIREMENT_CLEARED','FLOOR_RELEASE_RELINQUISHED','FLOOR_RELEASE_BEFORE_RETURN'])
    first,last=phase.at(owner,'FLOOR_BEFORE_RETURN'),phase.at(owner,'RETIREMENT_DELETE_VALIDATED')
    need([v['event'] for v in phase.events[first:last] if v['node']==owner and v['event'].startswith('RETENTION_')]==list(n.s.r.POINTS)*count,
         'competing exact observation forces')
    need(phase.start<floor<upper,'competing floor before slot work')
    prefix,members,packet=c.current(before[peer])
    phase.probe(owner,peer,ballot,packet['capsule']['cut'],phase.start,floor)
    phase.transfer(owner,peer,n.maintenance_prefixes(members,packet,c.current(before[owner])[1]),ballot,phase.start,floor)
    phase.transfer(owner,peer,n.maintenance_generations(before[peer][prefix+'generation.gsr'],members,packet),ballot,phase.start,floor)


def slot(history,events,entries,identities,start,stop,index,sends):
    leader=history.proposer;peer=next(v for v in history.voters if v!=leader);ballot=history.selected['ballot'];selected=history.selected
    before=history.snapshots[f'before-{index}'];applied=history.snapshots[f'slot-{index}-applied'];published=history.snapshots[f'slot-{index}-published']
    frames,_=c.pending(applied[leader]['pending.accept'],('PROOF','CERTIFICATE'))
    phase=net.Phase(events,entries,start,stop,identities)
    need(all(v['request']['ballot']==ballot and v['request']['sender']['node'] in history.voters
         and v['request']['recipient']['node'] in history.voters for v in phase.entries),'competing slot authority')
    for node in history.voters:
        maintenance(phase,history,index,node,ballot,phase.at(node,'ACCEPT_PARENT_FORCED'))
        phase.ordered(node,['ACCEPT_PARENT_FORCED','PROOF_PARENT_FORCED','CERTIFICATE_PARENT_FORCED','APPLY_ACK_DIRECTORY_FORCED',
            'FUTURE_RETENTION_PARENT_FORCED','PUBLICATION_SELECTOR_FORCED','FUTURE_RETENTION_PROMOTED','PUBLICATION_BEFORE_RETURN'])
    def observed(node,kind):return f.canonical(dict(root=selected['root'],voter=node,incarnation=identities[node]['storage'],phase=kind,record=e.digest(frames[kind])))
    for kind in ('ACCEPT','ENTRY')+(('PAYLOAD',) if index==2 else ()):
        phase.transfer(peer,leader,net.record(frames[kind]),ballot,phase.at(leader,'ACCEPT_PARENT_FORCED'),phase.at(peer,'ACCEPT_PARENT_FORCED'))
    phase.transfer(peer,leader,net.record(observed(leader,'ACCEPT'),True),ballot,phase.at(leader,'ACCEPT_PARENT_FORCED'),phase.at(peer,'ACCEPT_PARENT_FORCED'))
    phase.transfer(leader,peer,net.record(observed(peer,'ACCEPT'),True),ballot,phase.at(peer,'ACCEPT_PARENT_FORCED'),phase.at(leader,'PROOF_PARENT_FORCED'))
    phase.transfer(peer,leader,net.record(frames['PROOF']),ballot,phase.at(leader,'PROOF_PARENT_FORCED'),phase.at(peer,'PROOF_PARENT_FORCED'))
    phase.transfer(peer,leader,net.record(observed(leader,'ACCEPT'),True),ballot,phase.at(peer,'ACCEPT_PARENT_FORCED'),phase.at(peer,'PROOF_PARENT_FORCED'))
    phase.transfer(leader,peer,net.record(observed(peer,'PROOF'),True),ballot,phase.at(peer,'PROOF_PARENT_FORCED'),phase.at(leader,'CERTIFICATE_PARENT_FORCED'))
    phase.transfer(peer,leader,net.record(frames['CERTIFICATE']),ballot,phase.at(leader,'CERTIFICATE_PARENT_FORCED'),phase.at(peer,'CERTIFICATE_PARENT_FORCED'))
    for kind in ('ACCEPT','PROOF'):
        phase.transfer(peer,leader,net.record(observed(leader,kind),True),ballot,phase.at(peer,'PROOF_PARENT_FORCED'),phase.at(peer,'CERTIFICATE_PARENT_FORCED'))
    for node in history.voters:
        other=next(v for v in history.voters if v!=node)
        for name,raw in applied[other].items():
            if name.startswith('applied-end/') and name.endswith('ack.gsr'):
                phase.transfer(node,other,net.record(raw),ballot,phase.at(other,'APPLY_ACK_DIRECTORY_FORCED'),phase.at(node,'PUBLICATION_SELECTOR_FORCED'))
    for kind,key in (('ACCEPT','acceptance'),('PROOF','proof')):
        phase.control(kind,leader,peer,{key:e.digest(frames[kind])},kind+'_ACK',dict(entry=e.digest(frames['ENTRY']),receipt=e.digest(observed(peer,kind))),
            ballot,phase.at(peer,kind+'_PARENT_FORCED'),phase.at(leader,('PROOF' if kind=='ACCEPT' else 'CERTIFICATE')+'_PARENT_FORCED'))
    certificate=e.digest(frames['CERTIFICATE']);payload=dict(certificate=certificate,selection=e.digest(history.chosen))
    phase.control('APPLY',leader,peer,payload,'APPLY_ACK',dict(payload,statement=e.digest(applied[peer]['applied-end/statement.gsr']),
        acknowledgement=e.digest(applied[peer]['applied-end/ack.gsr'])),ballot,phase.at(peer,'APPLY_ACK_DIRECTORY_FORCED'),phase.recording(leader))
    parent=c.anchor(c.current(before[leader])[2]['capsule']);upper=c.anchor(c.current(published[leader])[2]['capsule'])
    intent=dict(selection=e.digest(history.chosen),certificate=certificate,peer=identities[peer],lower=parent,parent=parent,upper=upper)
    recorded={}
    for node in history.voters:
        files=applied[node];local=c.current(files)[1];records={k:files['applied-end/'+k] for k in ('selector.gsr','certificate.gsr','catalog.gsr','statement.gsr','ack.gsr')}
        records.update({k:local[k] for k in ('promise.gsr','selected.gsr')});records.update({k.lower()+'.gsr':frames[k] for k in ('ENTRY','ACCEPT','PROOF')})
        recorded[node]=n.future.frame(dict(n.future.initial(files),revision=index*2-1,previous=e.digest(files[n.future.FILE]),parent=parent,
            peers=[dict(identity=identities[peer],lower=parent)]),records)
    quorum=phase.at(leader,'SLOT_FUTURE_QUORUM_COMPLETE')
    need(phase.recording(leader)<quorum,'competing local future force before quorum')
    _,trace,_=phase.control('FUTURE_RETENTION_INTENT',leader,peer,intent,'FUTURE_RETENTION_ACK',
        dict(intent=e.digest(f.canonical(intent)),storage='FUTURE',revision=index*2-1,digest=e.digest(recorded[peer])),
        ballot,phase.recording(peer),quorum,sequence=intent_sequence(identities,leader,peer))
    prefix,_,packet=c.current(published[peer])
    _,_,rows=phase.control('PUBLISH',leader,peer,dict(certificate=certificate),'PUBLISH_ACK',dict(certificate=certificate,selection=e.digest(history.chosen),
        published=c.anchor(packet['capsule']),generation=e.digest(published[peer][prefix+'generation.gsr'])),ballot,
        phase.at(peer,'PUBLICATION_BEFORE_RETURN'),phase.at(leader,'PUBLICATION_SELECTOR_FORCED'),sequence=len(identities)+1,trace=trace)
    for row in rows:
        h=e.digest(f.encode('wire','PUBLISH',row['request']))
        need(all(quorum<at<stop for at in sends[h]),'competing every publication send after quorum')
    result=phase.finish();result['_intent']=intent;result['_intentTrace']=trace;return result


def heartbeats(history,events,entries,sends,by_hash,held):
    leader=history.proposer;ballot=history.selected['ballot'];selected=history.selected
    def cut_at(node,at):
        stages=[history.installed]
        for index in (1,2):
            matches=[i for i,v in enumerate(events) if v['node']==node and v['event']=='PUBLICATION_BEFORE_RETURN']
            if len(matches)>=index and matches[index-1]<at:stages.append(history.snapshots[f'slot-{index}-published'])
        return c.current(stages[-1][node])[2]['capsule']['cut']
    traces=defaultdict(dict);answered=0;last_completion=held[-1][0]
    for h,(kind,q) in by_hash.items():
        if kind!='HEARTBEAT':continue
        owner,peer=q['sender']['node'],q['recipient']['node'];first=sends[h][0]
        need(owner==leader and peer!=leader and q['ballot']==ballot
             and q['sequence']==sorted(set(history.initial)-{leader}).index(peer)+1 and first>held[0][0]
             and q['payload']==dict(cut=cut_at(leader,first),activated=True),'competing heartbeat installed current source')
        need(peer not in traces[q['trace']],'competing immutable heartbeat peer');traces[q['trace']][peer]=q
        replies=[v for v in entries if v['kind']=='HEARTBEAT' and v['request']==q]
        for row in replies:
            need(row['answer']=='HEARTBEAT_ACK' and row['response']['payload']==dict(cut=cut_at(peer,row['offered'])),
                 'competing heartbeat original reply cut')
            answered+=1
        need(replies or first>last_completion,'competing unfinished heartbeat only after client completion')
    samples=sorted(traces.items(),key=lambda item:min(sends[e.digest(f.encode('wire','HEARTBEAT',v))][0] for v in item[1].values()))
    contacts=0
    for ordinal,(trace,peers) in enumerate(samples):
        payloads=[v['payload'] for v in peers.values()]
        need(all(v==payloads[0] for v in payloads),'competing immutable heartbeat sample')
        first=min(sends[e.digest(f.encode('wire','HEARTBEAT',v))][0] for v in peers.values())
        if first>last_completion:continue
        upper=(min(sends[e.digest(f.encode('wire','HEARTBEAT',v))][0] for v in samples[ordinal+1][1].values())
               if ordinal+1<len(samples) else len(events))
        responding={leader}|{v['request']['recipient']['node'] for v in entries if v['kind']=='HEARTBEAT'
            and v['request']['trace']==trace and any(first<at<upper for at in v['deliveries'])}
        view=selected['cut']['view']
        need(all(len(responding&set(view[side]))>len(view[side])//2 for side in ('old','new')),
             'competing original heartbeat contact before continuation')
        contacts+=1
    return dict(samples=len(traces),responses=answered,completedContacts=contacts,_traces=set(traces))


def validate(root,history,events,held):
    identities={v:n.future.identity(files) for v,files in history.initial.items()}
    entries=exchange.exchanges(root,events,-1,len(events),identities)
    by_hash,sends,unanswered=raw_sends(events,entries,identities,history.selected)
    nonheartbeat=[v for v in entries if v['kind']!='HEARTBEAT']
    results=[activation(history,events,nonheartbeat,identities,held[0][0])]
    for index,(start,stop) in enumerate(((held[0][0],held[2][0]),(held[2][0],held[5][0])),1):
        results.append(slot(history,events,nonheartbeat,identities,start,stop,index,sends))
    need(sum(v['exchanges'] for v in results)==len(nonheartbeat),'competing full network coverage')
    unused=next(v for v in identities if v not in history.voters);allowed=set()
    for result,index in zip(results[1:],(1,2)):
        request=dict(root=history.selected['root'],view=history.selected['view'],ballot=history.selected['ballot'],sender=identities[history.proposer],
            recipient=identities[unused],trace=result.pop('_intentTrace'),sequence=intent_sequence(identities,history.proposer,unused),payload=result.pop('_intent'))
        h=e.digest(f.encode('wire','FUTURE_RETENTION_INTENT',request))
        need(h in by_hash and by_hash[h]==('FUTURE_RETENTION_INTENT',request) and 1<=len(sends[h])<=3,'competing original unused intent')
        start,stop=(held[1][0],held[2][0]) if index==1 else (held[4][0],held[5][0])
        need(all(start<at<stop for at in sends[h]),'competing unused intent original slot')
        need(not any(v['request']==request for v in entries),'competing unused intent cannot acknowledge')
        allowed.add(h)
    need(all(h in allowed or by_hash[h][0]=='HEARTBEAT' for h in unanswered),'competing unclassified unanswered request')
    heartbeat=heartbeats(history,events,entries,sends,by_hash,held)
    traces=set()
    for result in [*results,heartbeat]:
        own=result.pop('_traces');need(not traces.intersection(own),'competing unique phase traces');traces.update(own)
    need(all(str(uuid.UUID(v))==v and uuid.UUID(v).int!=0 for v in traces),'competing fresh trace identities')
    return dict(status='PASS',exchanges=len(entries),sends=sum(map(len,sends.values())),transfers=sum(v['transfers'] for v in results),
        unansweredIntents=len(allowed),heartbeat=heartbeat,phases=results)
