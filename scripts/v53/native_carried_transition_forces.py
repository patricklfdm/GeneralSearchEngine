"""Original carried-context storage callbacks across both group lifetimes.

Require the complete snapshot reducer first. Derive maintenance transactions
from those original members, including the source-only campaign path. Callback
observations do not replace transient byte captures or TCP/export authority.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import native_carried_transition_physical as physical
from . import carried_transition_retirement as retirement
from . import floor_evidence as floor
from . import floor_release_evidence as release
from . import applied_end_evidence as applied
from . import allocator_evidence as allocator
from . import native_campaign_files as campaign_files
from . import native_vote_files as vote_files
from . import native_completion_files as completion_files
from . import native_replay_files as replay_files

p=physical;process=p.process;native=process.process
c,d,e,f,need=p.c,p.d,p.e,p.f,p.need
MAINTENANCE=('FLOOR_','RETIREMENT_','SOURCE_RETIREMENT_','JOURNAL_ROTATION_')
LEDGER=('BEFORE_WRITE','PREFIX_WRITTEN','WRITTEN','FORCED','CANDIDATE_PARENT_FORCED','RENAMED','PARENT_FORCED')
GRANTS=('ALLOCATOR_','PROMISE_','CAPTURE_INTENT_','SOURCE_BEFORE_','SOURCE_CREATED','SOURCE_PACKET_',
        'SOURCE_IMAGE_','SOURCE_FILES_','SOURCE_DIRECTORY_','BASIS_','GRANT_','SELECTED_')
TRACKED=GRANTS+MAINTENANCE+('INSTALL_','ACCEPT_','PROOF_','CERTIFICATE_','APPLY_','PUBLICATION_','COVERED_',
        'RETENTION_','FUTURE_RETENTION_','REPLAY_','NATIVE_CERTIFICATE_RETAINED','APPLICATION_AUTHORITY_VALIDATED',
        'APPLICATION_ACK_BEFORE_RETURN')


def group(root,name):return {node:c.inventory(root/name/node) for node in process.NODES}


def names(rows,node):return [v['event'] for v in rows if v.get('node')==node]


def exact(names_,prefixes,expected,reason):
    need([v for v in names_ if v.startswith(prefixes)]==list(expected),reason)


def successors(source,tail,files,node,cap):
    """An unresolved old tail survives only under the installed exact vote."""
    old=f.decode(source['objects'][tail],'records','ACCEPT')
    if old['index']<=cap['cut']['index']:
        retirement.s.sources.published_tail(source,tail,files,node,cap);return
    frames,_=p.data.pending(files);_,members,packet=c.current(files)
    chosen=f.decode(members['selected.gsr'],'records','SELECTED')
    need(frames and frames['SELECTOR']==files['selector.gsr'] and frames['PROMISE']==members['promise.gsr'] and
         frames['SELECTED']==members['selected.gsr'] and chosen['nextEntry']==e.digest(frames['ENTRY']) and
         chosen['cut']==cap['cut'] and frames['ACCEPT']==f.encode('records','ACCEPT',dict(root=chosen['root'],
             authority=chosen['view'],ballot=chosen['ballot'],index=cap['cut']['index']+1,entry=e.digest(frames['ENTRY']))) and
         f.decode(frames['ENTRY'],'records','ENTRY')['kind'] in p.t.KINDS,
         'transition forces exact source successor')
    entry=f.decode(source['objects'][old['entry']],'records','ENTRY')
    need(old['entry']==e.digest(frames['ENTRY']) and all(packet['objects'].get(h)==source['objects'][h]
         for h in (tail,old['entry'],entry['payload'])),'transition forces retained source tail')


def floor_steps(initial,rows,files,writes,directories,*,peer_ledger=None):
    """Project original floor writes/forces without reading captured bytes."""
    state=retirement.s.physical(initial);steps=[]
    if peer_ledger is not None:state[d.s.FILE]=dict(bytes=len(peer_ledger),sha256=e.digest(peer_ledger))
    for at,row in enumerate(rows):
        state.update({name:dict(directory=True) for name,index in directories.items() if index==at})
        state.update({name:dict(bytes=len(files[name]),sha256=e.digest(files[name])) for name,index in writes.items() if index==at})
        steps.append((row['event'],dict(state)))
    return steps


def maintenance(group_,node,*,campaign=False,prefixes=None,floor_prefixes=None,floor_peer_ledger=None):
    """Project every FLOOR, generation/source retirement and release callback."""
    expected=p.maintain(group_,(node,),campaign=campaign)[node]
    if expected==group_[node]:return [],dict(generations=0,sources=0,borrowed=0)
    voters=p.floors.floor_voters(group_,node);files=p.floors.covering_floor(group_[node],{n:group_[n] for n in voters},node)
    copies={}
    for peer in voters:
        prefix,members,_=c.current(group_[peer]);manifest=group_[peer][prefix+'generation.gsr']
        copies[peer]=dict(members=dict(members,**{'generation.gsr':manifest}),manifest=manifest,identity=d.future.identity(group_[peer]))
    floor_rows,floor_files,writes,directories=floor.transaction({e.digest(v['manifest']):v['members'] for v in copies.values()},
                                      files['floor-copies/floor.gsr'],handoff=True)
    if floor_prefixes is not None:
        # The snapshot reducer reconciles a changed view before projecting the
        # whole maintenance result. Runtime persists that peer change only after
        # FLOOR_BEFORE_RETURN; creation still owns the original preceding ledger.
        ledger=group_[node][d.s.FILE] if floor_peer_ledger is None else floor_peer_ledger
        steps=floor_steps(group_[node],floor_rows,floor_files,writes,directories,peer_ledger=ledger)
        need(steps[-1][1]==retirement.s.physical(dict(files,**{d.s.FILE:ledger})),'transition forces complete floor projection')
        floor_prefixes.extend(('floor',point,state) for point,state in steps)
    events=[v['event'] for v in floor_rows];_,members,packet=c.current(files)
    for peer in (node,*(n for n in voters if n!=node)):
        if c.anchor(c.current(group_[peer])[2]['capsule'])==c.anchor(packet['capsule']):
            files[d.s.FILE]=p.t.maintenance.observation.observe_same_cut(files[d.s.FILE],group_[node],group_[peer],defer_renewal=True)
    prefix=c.current(files)[0];generations=borrowed=0
    if any(k.startswith('generations/') and k!=prefix[:-1] and not k.startswith(prefix) for k in files):
        pending=files['pending.accept'] if files['pending.accept']!=c.EMPTY else None
        files,steps,details=retirement.generation_plan(files,node,copies,pending)
        if prefixes is not None:prefixes.extend(('generation',point,state) for point,state in steps)
        events.extend(v[0] for v in steps);generations=1;borrowed=int(details['borrowedImages'])
    available=p.t.maintenance.confirmation.endpoints(packet,members.get('ancestry.gsr',b''))
    removed=sorted({k.split('/')[1] for k in files if k.startswith('sources/') and k not in expected})
    for identifier in removed:
        authority,compact=retirement.s.sources.decision(files,node,identifier,coverage=available,
            allow_published_tail=True,tail_check=successors if campaign else None)
        steps=retirement.s.sources.observed.release.transaction(retirement.s.physical(files),authority,compact,identifier)
        if prefixes is not None:prefixes.extend(('source',point,state) for point,state in steps)
        events.extend(v[0] for v in steps);prefix='sources/'+identifier
        files={k:v for k,v in files.items() if k!=prefix and not k.startswith(prefix+'/')};files['grants.gsr']=compact
        need(steps[-1][1]==retirement.s.physical(files),'transition forces source projection')
    floor_raw=files['floor-copies/floor.gsr'];cap=packet['capsule']
    authority=f.encode('records','RETIREMENT',dict(root=cap['root'],node=node,floor=e.digest(floor_raw),
        selector=e.digest(files['selector.gsr']),files=[dict(path=k,size=len(v),sha256=e.digest(v))
            for k,v in sorted(files.items()) if k.startswith('floor-copies/') and v is not None]))
    steps=release.transaction(retirement.s.physical(files),authority);events.extend(v[0] for v in steps)
    if floor_prefixes is not None:floor_prefixes.extend(('floor-release',point,state) for point,state in steps)
    need(steps[-1][1]==retirement.s.physical(expected),'transition forces final maintenance projection')
    return events,dict(generations=generations,sources=len(removed),borrowed=borrowed)


def maintenance_order(rows,node,expected):
    actual=[v for v in names(rows,node) if v.startswith(MAINTENANCE) and v!='FLOOR_COPY_BEFORE_RETURN']
    need(actual==expected,'transition forces exact maintenance callbacks')


def floor_point(point):return point.startswith('FLOOR_') and point!='FLOOR_COPY_BEFORE_RETURN'


def bind_prefixes(rows,node,expected,collector,*,floors=False):
    if collector is None:return
    actual=[v for v in rows if v.get('node')==node and
            (floor_point(v['event']) if floors else v['event'].startswith(retirement.s.PREFIXES))]
    need(len(actual)==len(expected),'transition forces complete retirement prefix count')
    for event,(kind,point,state) in zip(actual,expected):
        need(event['event']==point,'transition forces original retirement prefix boundary')
        collector.append((event,kind,state))


def ledger_order(rows,node,before,after):
    count=d.s.r.decode(after)['revision']-d.s.r.decode(before)['revision']
    need(count>=0,'transition forces monotonic peer ledger')
    exact(names(rows,node),tuple('RETENTION_'+v for v in LEDGER),['RETENTION_'+v for v in LEDGER]*count,
          'transition forces exact peer ledger writes')


def install_events(files,*,returned=True):
    _,members,packet=c.current(files)
    events=['INSTALL_RESERVED','INSTALL_DIRECTORY_CREATED','INSTALL_MANIFEST_WRITTEN','INSTALL_MANIFEST_FORCED']
    for name in sorted(members):
        prefix='INSTALL_IMAGE' if name.endswith('.image') else 'INSTALL_MEMBER'
        events.extend((prefix+'_WRITTEN',prefix+'_FORCED'))
    events+=['INSTALL_GENERATION_FORCED','INSTALL_SELECTOR_WRITTEN','INSTALL_SELECTOR_FORCED',
             'INSTALL_SELECTOR_RENAMED','INSTALL_PARENT_FORCED']
    if returned:events.append('INSTALL_BEFORE_RETURN')
    return events


def grant_events(images):
    return ['PROMISE_BEFORE_WRITE','PROMISE_WRITTEN','PROMISE_FORCED',
        *('CAPTURE_INTENT_'+v for v in ('CREATED','PREFIX_WRITTEN','WRITTEN','FORCED','PARENT_FORCED')),
        'SOURCE_BEFORE_CREATE','SOURCE_CREATED',
        *('SOURCE_PACKET_'+v for v in ('CREATED','PREFIX_WRITTEN','WRITTEN','FORCED')),
        *[point for _ in range(images) for point in ('SOURCE_IMAGE_CREATED','SOURCE_IMAGE_PREFIX_WRITTEN','SOURCE_IMAGE_WRITTEN','SOURCE_IMAGE_FORCED')],
        'SOURCE_FILES_DIRECTORY_FORCED','SOURCE_DIRECTORY_FORCED','BASIS_BEFORE_WRITE','BASIS_PREFIX_WRITTEN','BASIS_WRITTEN','BASIS_FORCED',
        'CAPTURE_INTENT_DELETED','CAPTURE_INTENT_CLEARED','GRANT_BEFORE_RETURN']


def bind_votes(rows,node,plan,collector):
    if collector is None:return
    actual=[row for row in rows if row.get('node')==node and row['event'] in vote_files.POINTS]
    need(len(actual)==len(plan),'transition forces complete vote prefix count')
    for row,(kind,point,state) in zip(actual,plan):
        need(row['event']==point,'transition forces original vote prefix boundary')
        collector.append((row,kind,state))


def cold(rows,before,*,vote_prefixes=None):
    for node,files in before.items():
        end=next(i for i,v in enumerate(rows) if v.get('node')==node and v['event']=='NODE_OPEN')
        events=names(rows[:end],node);frames,phases=p.data.pending(files)
        active=phases[-1] if phases else 'ACCEPT'
        expected=['RETENTION_RECOVERY_ACTIVE_FORCED','RETENTION_RECOVERY_PARENT_FORCED',
            'FUTURE_RETENTION_RECOVERY_FORCED','FUTURE_RETENTION_RECOVERY_PARENT_FORCED',active+'_ACTIVE_FORCED',active+'_ACTIVE_PARENT_FORCED']
        if frames['SELECTOR']!=files['selector.gsr']:
            expected += ['ACCEPT_'+v for v in ('VALIDATED','CANDIDATE_CREATED','PREFIX_WRITTEN','CANDIDATE_WRITTEN',
                'CANDIDATE_FORCED','CANDIDATE_PARENT_FORCED','RENAMED','PARENT_FORCED','BEFORE_RETURN')]
        exact(events,TRACKED,
              expected,'transition forces cold exact recovery')
        if vote_prefixes is not None:
            plan=vote_files.transaction(files,p.vote(files,frames['ENTRY'],frames['PAYLOAD']),'ACCEPT') if frames['SELECTOR']!=files['selector.gsr'] else []
            bind_votes(rows[:end],node,plan,vote_prefixes)


def campaign(rows,before,installed,*,prefixes=None,floor_prefixes=None,campaign_prefixes=None):
    chosen=f.decode(c.current(installed['node-1'])[1]['selected.gsr'],'records','SELECTED')
    voters=[v['voter'] for v in chosen['sources']]
    touched=[n for n in before if n in voters or before[n]['grants.gsr']!=installed[n]['grants.gsr']]
    reconciled=p.t.t.reconcile(before,touched);stats=[]
    maintained=p.maintain(reconciled,touched,campaign=True) if campaign_prefixes is not None else None
    observed=campaign_files.observed(rows) if campaign_prefixes is not None else None
    for node in before:
        local=[] if prefixes is not None else None
        floors=[] if floor_prefixes is not None else None
        events=names(rows,node);expected,detail=maintenance(reconciled,node,campaign=True,prefixes=local,
            floor_prefixes=floors,floor_peer_ledger=before[node][d.s.FILE]) if node in touched else ([],{})
        exact(events,('ACCEPT_','PROOF_','CERTIFICATE_','APPLY_','PUBLICATION_','COVERED_','FUTURE_RETENTION_','REPLAY_'),[],
              'transition forces campaign cannot execute a slot')
        maintenance_order(rows,node,expected);stats.append(detail)
        bind_prefixes(rows,node,local,prefixes)
        bind_prefixes(rows,node,floors,floor_prefixes,floors=True)
        ledger_order(rows,node,before[node][d.s.FILE],installed[node][d.s.FILE])
        exact(events,('ALLOCATOR_',),list(allocator.CUTS) if node=='node-1' else [],'transition forces campaign allocator')
        if node in touched:
            _,members,packet=c.current(installed[node]);basis=f.decode(members['basis.gsr'],'records','BASIS')
            if node not in voters:
                journal=c.journal(installed[node]['grants.gsr'],packet['capsule']['root'],node);basis=journal[-1][2]
            source=e.p.decode(installed[node]['sources/'+basis['basisId']+'/source.gscp'])
            grants=grant_events(len(source['images']))
        else:grants=[]
        exact(events,('PROMISE_','CAPTURE_INTENT_','SOURCE_BEFORE_','SOURCE_CREATED','SOURCE_PACKET_',
              'SOURCE_IMAGE_','SOURCE_FILES_','SOURCE_DIRECTORY_','BASIS_','GRANT_'),grants,'transition forces complete original grant')
        exact(events,('SELECTED_BEFORE_','SELECTED_WRITTEN','SELECTED_FORCED'),
              ['SELECTED_BEFORE_WRITE','SELECTED_WRITTEN','SELECTED_FORCED','SELECTED_BEFORE_RETURN'] if node in voters else [],
              'transition forces original selection')
        exact(events,('INSTALL_',),install_events(installed[node]) if node in voters else [],'transition forces complete installation')
        critical=[]
        if expected:critical+=['FLOOR_BEFORE_RETURN','FLOOR_RELEASE_BEFORE_RETURN']
        if node=='node-1':critical+=['ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN']
        if node in touched:critical+=['PROMISE_BEFORE_WRITE','BASIS_FORCED','GRANT_BEFORE_RETURN']
        if node in voters:critical+=['SELECTED_FORCED','INSTALL_PARENT_FORCED','INSTALL_BEFORE_RETURN']
        native.ordered(events,critical,'transition forces campaign durable order')
        if campaign_prefixes is not None:
            plan=campaign_files.transaction(maintained[node],installed[node],node,node in voters) if node in touched else []
            actual=[(kind,row) for _,kind,row in observed if row.get('node')==node]
            need(len(actual)==len(plan),'transition forces complete campaign prefix count')
            for (kind,row),(expected_kind,point,state) in zip(actual,plan):
                need((kind,row['event'])==(expected_kind,point),'transition forces original campaign prefix boundary')
                campaign_prefixes.append((row,kind,state))
    return stats


def vote_events(phase,*,renamed=False):
    return [phase+'_'+v for v in ('VALIDATED','CANDIDATE_CREATED','PREFIX_WRITTEN','CANDIDATE_WRITTEN',
        'CANDIDATE_FORCED','CANDIDATE_PARENT_FORCED','RENAMED')]+([] if renamed else [phase+'_PARENT_FORCED',phase+'_BEFORE_RETURN'])


def vote_order(events,phase,*,renamed=False,ack=False):
    # A received idempotent ACK can recur only after the one complete original
    # write; a duplicate write/force is not silently discarded.
    suffix=phase+'_ACK_BEFORE_RETURN'
    # Only application reopens a retained certificate within this slot. Cold
    # ACCEPT/PROOF recovery belongs before NODE_OPEN, never to a fresh vote.
    active=('CERTIFICATE_ACTIVE_FORCED','CERTIFICATE_ACTIVE_PARENT_FORCED') if phase=='CERTIFICATE' else ()
    actual=[v for v in events if v.startswith(phase+'_') and v not in active]
    expected=vote_events(phase,renamed=renamed)
    need(actual[:len(expected)]==expected and (all(v==suffix for v in actual[len(expected):]) if ack else len(actual)==len(expected))
         and (not ack or len(actual)>len(expected)),'transition forces exact '+phase+' write and ACK')


def publication_order(events,applied_files,published,peer,count):
    end={k.removeprefix('applied-end/'):v for k,v in applied_files.items() if k.startswith('applied-end/')}
    _,_,writes=applied.simulate(end,{},False)
    exact(events,('APPLY_',),[v['event'] for v in writes],'transition forces complete applied end')
    native.retirement.native.native_order(events,1)
    exact(events,('CERTIFICATE_ACTIVE_',),['CERTIFICATE_ACTIVE_FORCED','CERTIFICATE_ACTIVE_PARENT_FORCED'],
          'transition forces applied certificate force')
    exact(events,('INSTALL_',),install_events(published,returned=False),'transition forces published generation')
    expected=['PUBLICATION_VALIDATED',*install_events(published,returned=False),
        'PUBLICATION_SELECTOR_FORCED','PUBLICATION_COVERAGE_VALIDATED','COVERED_END_VALIDATED']
    for _ in sorted(end):expected+=['COVERED_END_BEFORE_DELETE','COVERED_END_FILE_DELETED']
    expected+=['COVERED_END_BEFORE_DIRECTORY_DELETE','COVERED_END_DIRECTORY_DELETED',
        *('COVERED_VOTE_'+v for v in ('CANDIDATE_CREATED','PREFIX_WRITTEN','CANDIDATE_WRITTEN','CANDIDATE_FORCED',
            'CANDIDATE_PARENT_FORCED','RENAMED','PARENT_FORCED')),'PUBLICATION_RETIRED','FUTURE_RETENTION_PROMOTED',
        'FUTURE_RETENTION_CLEARED','PUBLICATION_BEFORE_RETURN']
    observed=[v for v in events if v.startswith(('INSTALL_','COVERED_','PUBLICATION_')) and v not in
              ('PUBLICATION_SEND_BOUNDARY','PUBLICATION_ACK_BEFORE_RETURN') or v in ('FUTURE_RETENTION_PROMOTED','FUTURE_RETENTION_CLEARED')]
    need(observed==expected,'transition forces publication and cleanup order')
    ack='PUBLICATION_ACK_BEFORE_RETURN'
    need(ack in events and events.index(ack)>events.index('PUBLICATION_BEFORE_RETURN'),
         'transition forces publication ACK after return')
    if peer:
        need('APPLICATION_ACK_BEFORE_RETURN' in events and events.index('APPLY_BEFORE_RETURN')<
             events.index('APPLICATION_ACK_BEFORE_RETURN')<events.index('PUBLICATION_VALIDATED'),
             'transition forces application ACK after return')
    else:need('APPLICATION_ACK_BEFORE_RETURN' not in events,'transition forces local application has no peer ACK')
    native.ordered(events,['ACCEPT_PARENT_FORCED','PROOF_PARENT_FORCED','CERTIFICATE_PARENT_FORCED',
        'NATIVE_CERTIFICATE_RETAINED','APPLICATION_AUTHORITY_VALIDATED','REPLAY_CLAIM_FORCED',
        'REPLAY_BEFORE_APPLICATION','REPLAY_APPLICATION_FINISHED','REPLAY_BEFORE_RETURN',
        'APPLY_VALIDATED','APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN','PUBLICATION_VALIDATED',
        'PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN'],'transition forces complete slot durable order')
    force_set=tuple('FUTURE_RETENTION_'+v for v in LEDGER)
    exact(events,force_set,list(force_set)*count,'transition forces exact future ledger writes')
    # The complete retention protocol/returned receipt bytes remain a network
    # obligation. These local callback groups cannot precede their own force.
    pending=0;completed=0
    for event in events:
        if event=='FUTURE_RETENTION_PARENT_FORCED':pending+=1
        elif event=='FUTURE_RETENTION_BEFORE_RETURN':
            need(pending>0,'transition forces future ACK before force');pending-=1;completed+=1
        elif event=='FUTURE_RETENTION_ACK_BEFORE_RETURN':
            need(completed>0,'transition forces future ACK before force');completed-=1
    need(pending==1 and completed==0,'transition forces future completion/clear count')


def slot_votes(rows,before,accepting,applied_group,published,voters,first,point,collector):
    if collector is None:return
    maintained=before if point=='ACCEPT_RENAMED' else p.maintain(accepting if first else before,
        ('node-1',) if point=='PROOF_RENAMED' else voters)
    for node in before:
        plan=[]
        if node in voters and (point!='ACCEPT_RENAMED' or node=='node-1'):
            frames,_=p.data.pending((published if point else applied_group)[node])
            state=dict(before[node] if first else maintained[node])
            raw=vote_files.phase_bytes(frames,'ACCEPT')
            plan+=vote_files.transaction(state,raw,'ACCEPT',renamed=point=='ACCEPT_RENAMED')
            if point!='ACCEPT_RENAMED' and (point!='PROOF_RENAMED' or node=='node-1'):
                state=dict(maintained[node]);state[vote_files.ACTIVE]=raw
                raw=vote_files.phase_bytes(frames,'PROOF')
                plan+=vote_files.transaction(state,raw,'PROOF',renamed=point=='PROOF_RENAMED')
                if point is None:
                    state[vote_files.ACTIVE]=raw
                    plan+=vote_files.transaction(state,vote_files.phase_bytes(frames,'CERTIFICATE'),'CERTIFICATE')
        bind_votes(rows,node,plan,collector)


def slot_completions(rows,before,applied_group,published,voters,collector):
    if collector is None:return
    # Replay the same original future-ACK chain used by the physical reducer.
    # Applied snapshots precede these ledgers; published snapshots follow them.
    walk=p.NativeSlot.__new__(p.NativeSlot);walk.applied=applied_group;walk.voters=voters;walk.group=before
    walk.entry=p.data.pending(applied_group['node-1'])[0]['ENTRY'];ledgers={}
    need(walk.publication_group(copy.deepcopy(published),before_local_cleanup=ledgers)==published,
         'transition forces original publication ledgers')
    actual=completion_files.observed(rows)
    for node in before:
        plan=[]
        if node in voters:
            applied_files=applied_group[node]
            initial={k:v for k,v in applied_files.items() if k!='applied-end' and not k.startswith('applied-end/')}
            plan=completion_files.application(initial,applied_files)
            plan+=completion_files.publication(dict(applied_files,**ledgers[node]),published[node])
        found=[(kind,row) for _,kind,row in actual if row.get('node')==node]
        need(len(found)==len(plan),'transition forces complete completion prefix count')
        for (kind,row),(wanted,point,state) in zip(found,plan):
            need((kind,row['event'])==(wanted,point),'transition forces original completion prefix boundary')
            collector.append((row,kind,state))


def slot_replays(rows,applied_group,voters,collector):
    if collector is None:return
    for node,files in applied_group.items():
        plan=[]
        if node in voters:
            initial={k:v for k,v in files.items() if k!='applied-end' and not k.startswith('applied-end/')}
            plan=replay_files.transaction(initial,files)
        actual=[row for row in rows if row.get('node')==node and row['event'].startswith('REPLAY_')]
        need(len(actual)==len(plan),'transition forces complete replay prefix count')
        for row,(kind,point,state) in zip(actual,plan):
            need(row['event']==point,'transition forces original replay prefix boundary')
            collector.append((row,kind,state))


def slot(rows,before,applied_group,published,*,first,point=None,prefixes=None,floor_prefixes=None,vote_prefixes=None,completion_prefixes=None,replay_prefixes=None):
    chosen=f.decode(c.current(before['node-1'])[1]['selected.gsr'],'records','SELECTED')
    voters=[v['voter'] for v in chosen['sources']];stats=[]
    accepting=copy.deepcopy(before)
    if first:
        for node in voters:
            if point=='ACCEPT_RENAMED' and node!='node-1':continue
            files=before[node];packet=c.current(files)[2]
            entry=packet['objects'][chosen['nextEntry']];payload=packet['objects'][f.decode(entry,'records','ENTRY')['payload']]
            accepting[node]['pending.accept']=p.vote(files,entry,payload)
    for node in before:
        events=names(rows,node)
        exact(events,GRANTS,[],'transition forces slot cannot create a campaign')
        maintained=node in voters and (point is None or point=='PROOF_RENAMED' and node=='node-1')
        local=[] if prefixes is not None else None
        floors=[] if floor_prefixes is not None else None
        expected,detail=maintenance(accepting if first else before,node,prefixes=local,floor_prefixes=floors) if maintained else ([],{})
        maintenance_order(rows,node,expected);stats.append(detail)
        bind_prefixes(rows,node,local,prefixes)
        bind_prefixes(rows,node,floors,floor_prefixes,floors=True)
        if node not in voters or point=='ACCEPT_RENAMED' and node!='node-1':
            exact(events,('ACCEPT_','PROOF_','CERTIFICATE_','APPLY_','INSTALL_','PUBLICATION_','COVERED_',
                  'RETENTION_','FUTURE_RETENTION_','REPLAY_'),[],
                  'transition forces untouched slot owner');continue
        vote_order(events,'ACCEPT',renamed=point=='ACCEPT_RENAMED',ack=node!='node-1')
        if point=='ACCEPT_RENAMED':
            exact(events,('PROOF_','CERTIFICATE_','APPLY_','INSTALL_','PUBLICATION_','COVERED_',
                  'RETENTION_','FUTURE_RETENTION_','REPLAY_'),[],
                  'transition forces interrupted accept has no successor');continue
        if point=='PROOF_RENAMED' and node!='node-1':
            exact(events,('PROOF_','CERTIFICATE_','APPLY_','INSTALL_','PUBLICATION_','COVERED_',
                  'RETENTION_','FUTURE_RETENTION_','REPLAY_'),[],
                  'transition forces peer proof not dispatched');continue
        vote_order(events,'PROOF',renamed=point=='PROOF_RENAMED',ack=node!='node-1')
        if expected:
            critical=['ACCEPT_PARENT_FORCED','FLOOR_BEFORE_RETURN','FLOOR_RELEASE_BEFORE_RETURN','PROOF_VALIDATED'] if first else [
                      'FLOOR_BEFORE_RETURN','FLOOR_RELEASE_BEFORE_RETURN','ACCEPT_VALIDATED']
            native.ordered(events,critical,'transition forces vote maintenance boundary')
        if point=='PROOF_RENAMED':
            exact(events,('CERTIFICATE_','APPLY_','INSTALL_','PUBLICATION_','COVERED_','FUTURE_RETENTION_','REPLAY_'),[],
                  'transition forces interrupted proof has no application');continue
        vote_order(events,'CERTIFICATE')
        publication_order(events,applied_group[node],published[node],node!='node-1',len(voters))
        ledger_order(rows,node,before[node][d.s.FILE],published[node][d.s.FILE])
    if point is None:
        quorums=[i for i,v in enumerate(rows) if v['event']=='FUTURE_QUORUM_COMPLETE']
        sends=[i for i,v in enumerate(rows) if v['event']=='PUBLICATION_SEND_BOUNDARY']
        need(len(quorums)==len(voters)-1 and len(sends)>=len(voters)-1 and max(quorums)<min(sends),
             'transition forces all future quorums before publish')
    else:
        for node in before:ledger_order(rows,node,before[node][d.s.FILE],published[node][d.s.FILE])
    if point is None:
        slot_completions(rows,before,applied_group,published,voters,completion_prefixes)
        slot_replays(rows,applied_group,voters,replay_prefixes)
    slot_votes(rows,before,accepting,applied_group,published,voters,first,point,vote_prefixes)
    return stats


def replay(root,kind,point,*,prefixes=None,floor_prefixes=None,campaign_prefixes=None,vote_prefixes=None,completion_prefixes=None,replay_prefixes=None):
    root=Path(root);result=process.read(root/'process/result.json');children=native.children(result,kind=kind)
    lives,_,_,_,_=process.observations(root,result,children);index,_,_=p.t.shape(kind);stats=[]
    for life,rows in enumerate(lives,1):
        collected=[] if prefixes is not None else None
        floors=[] if floor_prefixes is not None else None
        campaigns=[] if campaign_prefixes is not None else None
        votes=[] if vote_prefixes is not None else None
        completions=[] if completion_prefixes is not None else None
        replays=[] if replay_prefixes is not None else None
        cold(rows,group(root,'before-network' if life==1 else 'before-reopen'),vote_prefixes=votes)
        start=max(i for i,v in enumerate(rows) if v['event']=='NODE_OPEN')
        covered=set(range(start+1))
        marks=[(i,v['event']) for i,v in enumerate(rows) if v['event'].startswith('ROUND_')]
        before=group(root,f'life-{life}-opened');ordinal=0;slot_start=None
        for at,event in marks:
            if event=='ROUND_INSTALLED':
                ordinal+=1;installed=group(root,f'life-{life}-installed-{ordinal}')
                stats+=campaign(rows[start+1:at],before,installed,prefixes=collected,floor_prefixes=floors,campaign_prefixes=campaigns)
                covered.update(range(start+1,at))
            elif event=='ROUND_SLOT_BEGIN':slot_start=at
            elif event=='ROUND_SLOT_COMPLETE':
                published=group(root,f'life-2-published-{index+ordinal-1}')
                stats+=slot(rows[slot_start+1:at],installed,group(root,f'life-2-applied-{index+ordinal-1}'),published,first=ordinal==1,prefixes=collected,floor_prefixes=floors,vote_prefixes=votes,completion_prefixes=completions,replay_prefixes=replays)
                covered.update(range(slot_start+1,at))
                before=published;start=at
        if life==1:
            stats+=slot(rows[slot_start+1:],installed,None,group(root,'at-cut'),first=True,point=point,prefixes=collected,floor_prefixes=floors,vote_prefixes=votes,completion_prefixes=completions,replay_prefixes=replays)
            covered.update(range(slot_start+1,len(rows)))
        for at,row in enumerate(rows):
            if row['event'].startswith(TRACKED) and row['event']!='FLOOR_COPY_BEFORE_RETURN':
                need(at in covered,'transition forces storage callback outside operation')
                if row['event']!='PUBLICATION_SEND_BOUNDARY':
                    need(set(row)=={'node','event','incarnation'},'transition forces callback shape')
        for target,parts,is_floor in ((prefixes,collected,False),(floor_prefixes,floors,True)):
            if target is None:continue
            positions={id(row):at for at,row in enumerate(rows)};used=[positions[id(row)] for row,_,_ in parts]
            need(len(set(used))==len(used) and set(used)=={at for at,row in enumerate(rows) if
                 (floor_point(row['event']) if is_floor else row['event'].startswith(retirement.s.PREFIXES))},
                 'transition forces unbound retirement prefix')
            target.extend(dict(life=life,eventIndex=positions[id(row)],node=row['node'],point=row['event'],kind=kind_,files=state)
                for row,kind_,state in sorted(parts,key=lambda v:positions[id(v[0])]))
        if campaign_prefixes is not None:
            positions={id(row):at for at,row in enumerate(rows)};used=[positions[id(row)] for row,_,_ in campaigns]
            need(len(set(used))==len(used) and set(used)=={at for at,_,_ in campaign_files.observed(rows)},
                 'transition forces unbound campaign prefix')
            campaign_prefixes.extend(dict(life=life,eventIndex=positions[id(row)],node=row['node'],point=row['event'],kind=kind_,files=state)
                for row,kind_,state in sorted(campaigns,key=lambda v:positions[id(v[0])]))
        if vote_prefixes is not None:
            positions={id(row):at for at,row in enumerate(rows)};used=[positions[id(row)] for row,_,_ in votes]
            need(len(set(used))==len(used) and set(used)=={at for at,row in enumerate(rows) if row['event'] in vote_files.POINTS},
                 'transition forces unbound vote prefix')
            vote_prefixes.extend(dict(life=life,eventIndex=positions[id(row)],node=row['node'],point=row['event'],kind=kind_,files=state)
                for row,kind_,state in sorted(votes,key=lambda v:positions[id(v[0])]))
        if completion_prefixes is not None:
            positions={id(row):at for at,row in enumerate(rows)};used=[positions[id(row)] for row,_,_ in completions]
            need(len(set(used))==len(used) and set(used)=={at for at,_,_ in completion_files.observed(rows)},
                 'transition forces unbound completion prefix')
            completion_prefixes.extend(dict(life=life,eventIndex=positions[id(row)],node=row['node'],point=row['event'],kind=kind_,files=state)
                for row,kind_,state in sorted(completions,key=lambda v:positions[id(v[0])]))
        if replay_prefixes is not None:
            positions={id(row):at for at,row in enumerate(rows)};used=[positions[id(row)] for row,_,_ in replays]
            need(len(set(used))==len(used) and set(used)=={at for at,row in enumerate(rows) if row['event'].startswith('REPLAY_')},
                 'transition forces unbound replay prefix')
            replay_prefixes.extend(dict(life=life,eventIndex=positions[id(row)],node=row['node'],point=row['event'],kind=kind_,files=state)
                for row,kind_,state in sorted(replays,key=lambda v:positions[id(v[0])]))
    return dict(status='PARTIAL',scope='carried-transition-storage-callbacks',coldOwners=8,
        campaigns=1+p.t.shape(kind)[1],generationRetirements=sum(v.get('generations',0) for v in stats),
        sourceRetirements=sum(v.get('sources',0) for v in stats),observedStorageCallbacks=True,
        transientBytesCaptured=False,coreScratchInventoryReplay=False,fullWireReplay=False,fullForceReplay=False,phase3Complete=False)


def validate(root):
    root=Path(root);before=process.collection.inventory(root);original=p.validate(root)
    result=replay(root,original['physical']['kind'],original['physical']['cut'])
    need(process.collection.inventory(root)==before,'transition forces original changed')
    return dict(original=original,forces=result,status='PARTIAL',phase3Complete=False)


OMISSIONS={
    'cold-force':('ACCEPT_ACTIVE_FORCED','transition forces cold exact recovery'),
    'allocator-force':('ALLOCATOR_FORCED','transition forces campaign allocator'),
    'promise-force':('PROMISE_FORCED','transition forces complete original grant'),
    'capture-force':('CAPTURE_INTENT_FORCED','transition forces complete original grant'),
    'source-force':('SOURCE_PACKET_FORCED','transition forces complete original grant'),
    'basis-force':('BASIS_FORCED','transition forces complete original grant'),
    'selection-force':('SELECTED_FORCED','transition forces original selection'),
    'install-member-force':('INSTALL_MEMBER_FORCED','transition forces complete installation'),
    'floor-copy-force':('FLOOR_COPY_DIRECTORY_FORCED','transition forces exact maintenance callbacks'),
    'floor-parent-force':('FLOOR_PARENT_FORCED','transition forces exact maintenance callbacks'),
    'retirement-borrow-force':('RETIREMENT_BORROW_FORCED','transition forces exact maintenance callbacks'),
    'source-delete':('SOURCE_RETIREMENT_FILE_DELETED','transition forces exact maintenance callbacks'),
    'journal-force':('JOURNAL_ROTATION_FORCED','transition forces exact maintenance callbacks'),
    'release-authority-force':('FLOOR_RELEASE_AUTHORITY_FORCED','transition forces exact maintenance callbacks'),
    'retention-force':('RETENTION_FORCED','transition forces exact peer ledger writes'),
    'accept-force':('ACCEPT_CANDIDATE_FORCED','transition forces exact ACCEPT write and ACK'),
    'proof-force':('PROOF_CANDIDATE_FORCED','transition forces exact PROOF write and ACK'),
    'certificate-force':('CERTIFICATE_CANDIDATE_FORCED','transition forces exact CERTIFICATE write and ACK'),
    'applied-metadata-force':('APPLY_METADATA_FORCED','transition forces complete applied end'),
    'applied-ack-force':('APPLY_ACK_DIRECTORY_FORCED','transition forces complete applied end'),
    'replay-claim-force':('REPLAY_CLAIM_FORCED','transition forces complete slot durable order'),
    'covered-vote-force':('COVERED_VOTE_CANDIDATE_FORCED','transition forces publication and cleanup order'),
    'future-force':('FUTURE_RETENTION_CANDIDATE_PARENT_FORCED','transition forces exact future ledger writes'),
}
NEGATIVES={name:reason for name,(_,reason) in OMISSIONS.items()}
NEGATIVES.update({
    'early-accept-ack':'transition forces exact ACCEPT write and ACK',
    'early-publication-ack':'transition forces publication ACK after return',
    'early-journal-rename':'transition forces exact maintenance callbacks',
    'duplicate-delete':'transition forces exact maintenance callbacks',
    'duplicate-applied-delete':'transition forces publication and cleanup order',
    'invented-cold-ack':'transition forces cold exact recovery',
    'unbound-delete':'transition forces storage callback outside operation',
    'callback-extra-field':'transition forces callback shape',
})


def mutate(root,name):
    def edit(lives):
        messages=lives[0] if name in ('cold-force','invented-cold-ack') else lives[1]
        def at(point,node=None):
            start=next(i for i,v in enumerate(messages) if v['action']=='event' and v['value']['event']=='ROUND_SLOT_BEGIN') \
                if name in ('accept-force','proof-force','certificate-force','early-accept-ack') else -1
            return next(i for i,v in enumerate(messages) if v['action']=='event' and
                        i>start and v['value']['event']==point and (node is None or v['value']['node']==node))
        if name in OMISSIONS:messages.pop(at(OMISSIONS[name][0]))
        elif name in ('early-accept-ack','early-publication-ack','early-journal-rename'):
            point,before={'early-accept-ack':('ACCEPT_ACK_BEFORE_RETURN','ACCEPT_PARENT_FORCED'),
                'early-publication-ack':('PUBLICATION_ACK_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN'),
                'early-journal-rename':('JOURNAL_ROTATION_RENAMED','JOURNAL_ROTATION_FORCED')}[name]
            row=messages.pop(at(point));messages.insert(at(before,row['value']['node']),row)
        elif name in ('duplicate-delete','duplicate-applied-delete'):
            point='SOURCE_RETIREMENT_FILE_DELETED' if name=='duplicate-delete' else 'COVERED_END_FILE_DELETED'
            index=at(point);messages.insert(index,copy.deepcopy(messages[index]))
        elif name=='invented-cold-ack':
            messages.insert(at('NODE_OPEN'),dict(action='event',value=dict(node='node-1',incarnation=1,event='APPLY_ACK_DIRECTORY_FORCED')))
        elif name=='unbound-delete':
            messages.insert(-1,dict(action='event',value=dict(node='node-1',incarnation=2,event='SOURCE_RETIREMENT_FILE_DELETED')))
        elif name=='callback-extra-field':messages[at('ALLOCATOR_FORCED')]['value']['claimedSafe']=True
        else:raise ValueError('unknown transition forces mutation')
    native.rewrite_lives(Path(root),edit)


def qualify(root):
    root=Path(root);before=process.collection.inventory(root);original=validate(root);results=[]
    protected=lambda value:{k:v for k,v in value['files'].items() if k not in
        ('events.json','process/life-1.jsonl','process/life-2.jsonl')}
    with tempfile.TemporaryDirectory(prefix='v53-transition-forces-') as temp:
        for name,reason in NEGATIVES.items():
            changed=Path(temp)/name;shutil.copytree(root,changed);mutate(changed,name)
            after=process.collection.inventory(changed)
            need(protected(before)==protected(after) and before['directories']==after['directories'],
                 'transition forces negative changed original storage')
            try:validate(changed)
            except ValueError as error:need(str(error)==reason,'transition forces wrong negative '+name+': '+str(error))
            else:raise ValueError('transition forces accepted negative '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason));shutil.rmtree(changed)
            print(json.dumps(dict(stage='force-negative',case=name,completed=len(results),total=len(NEGATIVES))),file=sys.stderr,flush=True)
    need(process.collection.inventory(root)==before,'transition forces qualification changed original')
    return dict(original=original,negatives=results,originalStorageAndWireUnchanged=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))
