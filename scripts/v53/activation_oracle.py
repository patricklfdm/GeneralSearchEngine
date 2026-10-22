"""Cross-slot root-promise and activation observer, independent of Engine state."""
from itertools import combinations

from . import ballot_model as b
from . import transition_model as t
from .membership_model import NODES


def safe(ok,message):
    if not ok:raise b.SafetyViolation(message)


def check(record):
    root,old=record['root'],tuple(record['old']);events=record['events']
    transitions=record['input']+[e['detail'] for e in events if e['event']=='transition']
    chain_audit=t.check_history(root,old,transitions)
    prefixes={n:() for n in NODES};promises={n:None for n in NODES};bound={};bases={}
    counters={n:0 for n in NODES}
    for event in record['input']:
        if event['event']=='install-force':prefixes[event['node']]=event['chain']
        if event['event']!='slot':continue
        detail=event['detail']
        if detail['event']=='start':
            ballot=detail['ballot'];counters[ballot.proposer]=max(counters[ballot.proposer],ballot.counter)
        if detail['event']=='promise-force':
            msg=detail['message'];node=msg.voter
            if promises[node] is None or msg.ballot>promises[node]:
                promises[node]=msg.ballot;bound[node]=msg.context
                bases[node]=b.Message('prepare-ack',node,msg.ballot,msg.context,accepted=detail['accepted'])
    for node,chain in prefixes.items():
        if chain:
            cert=max(chain,key=lambda c:c.ballot)
            if promises[node] is None or cert.ballot>promises[node]:
                promises[node]=cert.ballot;bound[node]=cert.authority;bases.pop(node,None)
    fences=dict(promises);allocations={};reserved={};used=set();alive=set(NODES);starts={};dead=set()
    grants={};freezing={};fetched=set();selecting={};selections={};installing={};installed={};acks={}
    pending_publications={};certificates=set();ready={};publications=0;ready_count=0
    pending_prefixes={}

    def view(node):
        left=right=old;operation='';generation=0;parent=t.digest(dict(root=root,voters=old))
        for cert in prefixes[node]:
            entry=t.Entry.read(cert.value)
            if operation:left=right;operation=''
            elif entry.kind=='INTENT':right=entry.target;operation=entry.operation;generation+=1
            parent=cert.entry_id
        return t.Authority(root,len(prefixes[node])+1,parent,generation,left,right,operation)

    def current(ballot):
        node=ballot.proposer
        safe(ballot in starts and ballot not in dead and node in alive and
             promises[node]==fences[node]==ballot and bound[node]==starts[ballot][0],'fenced campaign event')

    def decision_valid(decision):
        authority,ballot=decision.authority,decision.ballot;current(ballot)
        rows=decision.bases;owners={row.voter for row in rows}
        family=(set(a)|set(z) for a in combinations(authority.old,len(authority.old)//2+1)
                for z in combinations(authority.new,len(authority.new)//2+1))
        safe(len(rows)==len(owners) and owners<=authority.voters and ballot.proposer in owners and
             any(q<=owners for q in family),'selected quorum/local basis missing')
        safe(starts[ballot][0]==authority and all(row in fetched and row.kind=='prepare-ack' and
             row.ballot==ballot and row.context==authority for row in rows),'unfetched/mixed selected sources')
        tails=[row.accepted for row in rows if row.accepted]
        expected=starts[ballot][1]
        if tails:
            maximum=max(v.ballot for v in tails);values={v.value for v in tails if v.ballot==maximum}
            safe(len(values)==1,'ambiguous selected tail');expected=values.pop()
        safe(decision.value==expected,'selection discarded highest accepted value')

    for event in events:
        kind=event['event']
        if kind=='allocate-stage':
            node,ballot=event['node'],event['ballot'];observed=event['observed']
            limit=max([counters[node]]+[x.counter for x in (promises[node],fences[node],observed) if x])
            safe(node in alive and node not in allocations and node not in reserved and
                 ballot.proposer==node and ballot.counter>limit,'unsafe ballot allocation')
            allocations[node]=ballot
        elif kind=='allocate-force':
            node,ballot=event['node'],event['ballot']
            safe(allocations.pop(node,None)==ballot,'unprepared allocator force');counters[node]=ballot.counter;reserved[node]=ballot
        elif kind=='start':
            ballot,authority=event['ballot'],event['authority'];node=ballot.proposer
            safe(node in alive and reserved.pop(node,None)==ballot and ballot not in used,'campaign before durable allocation')
            safe(view(node)==authority and node in authority.voters and node not in pending_prefixes and
                 node not in grants and node not in freezing,'campaign without available local authority')
            used.add(ballot);starts[ballot]=(authority,event['value']);ready.pop(node,None)
        elif kind=='observe':
            node,ballot=event['node'],event['ballot']
            safe(fences[node] is None or ballot>fences[node],'observation regressed');fences[node]=ballot;ready.pop(node,None)
        elif kind=='grant-stage':
            node,ballot,authority=event['node'],event['ballot'],event['authority']
            safe(node in alive and node not in grants and node not in freezing and node not in pending_prefixes and view(node)==authority and
                 fences[node]==ballot and (promises[node] is None or ballot>promises[node]),'same-ballot basis resampling')
            grants[node]=(authority,ballot)
        elif kind=='grant-force':
            node,ballot,authority=event['node'],event['ballot'],event['authority']
            safe(grants.pop(node,None)==(authority,ballot) and fences[node]==ballot,'unprepared/fenced root grant')
            promises[node]=ballot;bound[node]=authority;bases.pop(node,None);freezing[node]=(authority,ballot)
        elif kind=='basis-ready':
            node,row=event['node'],event['basis']
            safe(freezing.pop(node,None)==(row.context,row.ballot) and bases.get(node)==row,'basis not forced')
        elif kind=='basis-fetch':
            node,row=event['node'],event['basis'];current(row.ballot)
            safe(node in alive and promises[node]==fences[node]==row.ballot and bases.get(node)==row,'fetched stale/unavailable source')
            fetched.add(row)
        elif kind=='selection-stage':
            decision=event['decision'];decision_valid(decision);ballot=decision.ballot
            safe(ballot not in selecting and (ballot not in selections or selections[ballot]==decision),'changed selected quorum in same ballot')
            selecting[ballot]=decision
        elif kind=='selection-force':
            decision=event['decision'];current(decision.ballot)
            safe(selecting.pop(decision.ballot,None)==decision,'unprepared selected force');selections[decision.ballot]=decision
        elif kind=='install-stage':
            node,decision=event['node'],event['decision'];current(decision.ballot)
            safe(selections.get(decision.ballot)==decision and node in decision.owners and node in alive and
                 promises[node]==fences[node]==decision.ballot and bases.get(node) in decision.bases and
                 node not in installing,'install substituted source/selection')
            installing[node]=decision
        elif kind=='install-force':
            node,decision=event['node'],event['decision']
            safe(installing.pop(node,None)==decision and promises[node]==fences[node]==decision.ballot,'unprepared/fenced install')
            installed[(node,decision.ballot)]=decision
        elif kind=='install-ack':
            node,decision=event['node'],event['decision'];current(decision.ballot)
            safe(node in alive and promises[node]==fences[node]==decision.ballot and
                 installed.get((node,decision.ballot))==decision,'unforced/stale install ACK')
            acks.setdefault(decision.ballot,set()).add(node)
        elif kind=='transition':
            row=event['detail']
            if row['event']=='install-stage':pending_prefixes[row['node']]=row['chain']
            if row['event']=='install-force':
                node=row['node'];safe(node not in freezing and node not in grants,'prefix crossed incomplete basis')
                safe(all(promises[node] is not None and c.ballot<=promises[node] for c in row['chain']),
                     'prefix exceeds durable root promise')
                pending_prefixes.pop(node,None)
                prefixes[node]=row['chain']
            if row['event']=='certificate':certificates.add(row['certificate'])
            if row['event']!='slot':continue
            detail=row['detail'];action=detail['event'];msg=detail.get('message')
            if action in ('stage','promise-force','accept-force','proof-force'):
                node=msg.voter
                safe(node in alive and promises[node]==fences[node]==msg.ballot and bound[node]==msg.context,
                     'vote crossed global promise')
                if msg.kind!='prepare':
                    decision=installed.get((node,msg.ballot))
                    safe(decision is not None and decision.value==msg.value,'vote without selected installation')
            if action=='promise-force':
                safe(freezing.get(msg.voter)==(msg.context,msg.ballot),'basis without root grant')
                bases[msg.voter]=b.Message('prepare-ack',msg.voter,msg.ballot,msg.context,accepted=detail['accepted'])
            if action=='send' and msg.kind in ('accept','proof'):
                current(msg.ballot);decision=selections.get(msg.ballot)
                safe(decision is not None and acks.get(msg.ballot)==set(decision.owners) and msg.voter in decision.owners,
                     'write before complete selected installation')
            if action=='send' and msg.kind=='prepare' and msg.voter!=msg.ballot.proposer:
                own=bases.get(msg.ballot.proposer)
                safe(own is not None and own.ballot==msg.ballot,'remote prepare before own frozen basis')
        elif kind=='publication-stage':
            ballot,cert=event['ballot'],event['certificate'];current(ballot)
            safe(cert in certificates and cert.ballot==ballot and prefixes[ballot.proposer][-1]==cert,
                 'publication without forced certified prefix')
            pending_publications[ballot]=cert
        elif kind=='published':
            ballot,cert=event['ballot'],event['certificate'];current(ballot)
            safe(pending_publications.pop(ballot,None)==cert,'publication without matching pending image')
            fresh=t.Entry.read(cert.value)==t.Entry('BARRIER',payload='activation:'+t.digest(ballot))
            safe(event['ready']==(fresh and not view(ballot.proposer).operation),'ready without current-ballot barrier publication')
            publications+=1
            if event['ready']:ready[ballot.proposer]=ballot;ready_count+=1
        elif kind=='adoption-force':
            node,cert=event['node'],event['certificate']
            safe(node in alive and cert in pending_prefixes.get(node,()) and
                 (promises[node] is None or cert.ballot>promises[node]) and fences[node]>=cert.ballot,
                 'unverified/regressing adoption floor')
            promises[node]=cert.ballot;bound[node]=cert.authority;bases.pop(node,None)
        elif kind=='sync':ready.pop(event['node'],None)
        elif kind=='crash':
            node=event['node'];safe(node in alive,'duplicate crash');alive.remove(node)
            allocations.pop(node,None);reserved.pop(node,None);grants.pop(node,None);freezing.pop(node,None);installing.pop(node,None)
            pending_prefixes.pop(node,None)
            ready.pop(node,None);fences[node]=promises[node]
            for ballot in starts:
                if ballot.proposer==node:dead.add(ballot);pending_publications.pop(ballot,None);selecting.pop(ballot,None)
        elif kind=='restart':
            node=event['node'];safe(node not in alive and event['promise']==promises[node] and
                 event['counter']==counters[node] and event['ready'] is None,'restart lost root state or restored READY')
            alive.add(node)
        else:raise b.SafetyViolation('unknown activation event')
    return dict(events=len(events),transitionEvents=chain_audit['events'],publications=publications,
                activations=ready_count,campaigns=len(starts))
