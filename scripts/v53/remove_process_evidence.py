"""Original-first physical replay of interrupted REMOVE maintenance and continuation.

Derive every observed owner from bootstrap, never from a successful execution
receipt. One complete same-proposer history is not the full Phase 3 matrix.
"""
import argparse
import base64
import copy
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import transition_process_evidence as process
from . import remove_process_run as run
from . import remove_maintenance_evidence as maintenance
from . import remove_retirement_evidence as retirement

a,b,c,d,e,f,need=process.a,process.b,process.c,process.d,process.e,process.f,process.need


def profile_at(root):
    path=Path(root)/'profile.json'
    need(path.is_file() and not path.is_symlink() and path.stat().st_size<=4096,'REMOVE process regular profile')
    profile=e.parse(path.read_bytes())
    need(type(profile) is dict and set(profile)=={'schema','profile','index','point','mode'} and
         all(type(profile[k]) is str for k in ('schema','profile','point','mode')) and
         type(profile['index']) is int,'REMOVE process profile')
    case=','.join(profile[k] for k in ('profile','point','mode'))
    need(profile==run.selected(case),'REMOVE process profile')
    return profile


def layout(root,profile):
    b.selection.layout(root,{'profile.json','process.json','history','native-history.txt','interrupted-worker','resumed-worker'},'REMOVE process')
    b.selection.layout(root/'interrupted-worker',{'stdout','stderr'},'REMOVE interrupted worker')
    b.selection.layout(root/'resumed-worker',{'stdout','stderr','ready.json','ready.gsrp'},'REMOVE resumed worker')
    expected={'original-plan.gsbp','original-application.image','initial','before-network','before-child','interrupted',
              'after-resume','after-close','calls.json','events.json','wire.json','failures.json',
              profile['mode']+'-opened-0',profile['mode']+'-installed-1','resume-opened-0'}
    expected|={'round-1-'+v for v in ('prepared','selected','installed','settled')}
    expected|={f'slot-{n}-{v}' for n in range(1,5) for v in ('accepted','proved','certified','applied','published','settled')}
    expected|={f'{name}-{n}.{ext}' for n in range(1,5) for name,ext in (('entry','gsr'),('payload','bin'))}
    expected|={'resume-installed-'+str(n) for n in range(1,4)}
    expected|={f'resume-{name}-{n}' for name in ('applied','published') for n in range(5,8)}
    b.selection.layout(root/'history',expected,'REMOVE process history')


def install(root,group,raw,stage,*,maintain):
    chosen=f.decode(raw,'records','SELECTED');voters=[v['voter'] for v in chosen['sources']]
    view=c.current(group['node-1'])[2]['capsule']['cut']['view']
    a.x.context.majority(view,voters)
    need('node-1' in voters and voters==sorted(set(voters)),'REMOVE process selected original voters')
    group=process.continuous.reconcile(group,voters)
    if maintain:group=maintenance.maintenance(group,voters)
    previous=f.decode(group['node-1']['allocator.gsr'],'records','ALLOCATOR')['counter']
    need(chosen['ballot']['counter']==previous+1,'REMOVE process fresh original ballot')
    _,_,installed=d.s.campaign(root,{n:group[n] for n in voters},previous+1,stage,selected_prefix=d.slot.prefix,
        merge_ledgers=lambda before,sources:maintenance.merge(group,before,sources))
    group=dict(group,**installed);b.match(root,stage,group)
    need(c.current(group['node-1'])[1]['selected.gsr']==raw,'REMOVE process exact installed selection')
    return group,voters


def governing(group,voters):
    """Local maintenance precedes sending maintenance to the other voters."""
    files=retirement.sources.governing(group['node-1'],{n:group[n] for n in voters},'node-1')
    for peer in voters:
        files[d.s.FILE]=maintenance.observation.observe_same_cut(files[d.s.FILE],group['node-1'],group[peer],defer_renewal=True)
    copies={}
    for node in voters:
        prefix,members,_=c.current(group[node])
        copies[node]=dict(members=members,manifest=group[node][prefix+'generation.gsr'],identity=d.future.identity(group[node]))
    return files,copies


def capacity(state):
    images=sum(name.endswith('.image') for name in state)
    sources=sum(name.startswith('sources/') and name.count('/')==1 and 'directory' in value for name,value in state.items())
    copies=sum(name.startswith('floor-copies/') and name.count('/')==1 and 'directory' in value for name,value in state.items())
    borrowed=int('retirement/source' in state or retirement.images.BINDING in state)
    need(images<=7 and sources+copies+borrowed<=6,'REMOVE process unchanged physical capacity')


def prefix_at(steps,point):
    positions=[i for i,(name,_) in enumerate(steps) if name==point]
    need(positions,'REMOVE process reachable original retirement cut')
    # The child dies at the first matching callback. Repeated per-file callbacks
    # cannot be shifted to a later deletion to make an observed state match.
    return positions[0]


def source_interruption(after,point,coverage):
    _,decisions=retirement.source_plans(after,'node-1',coverage)
    need(decisions,'REMOVE process original source retirement absent')
    decision=decisions[0];steps=decision['steps'];at=prefix_at(steps,point);prefix=steps[at][1]
    authority,compact=retirement.sources.decision(after,'node-1',decision['identifier'],coverage=coverage)
    recovery=retirement.sources.observed.release.transaction(prefix,authority,compact,decision['identifier'])
    source='sources/'+decision['identifier']
    recovered={k:v for k,v in after.items() if k!=source and not k.startswith(source+'/')}
    recovered['grants.gsr']=compact
    need((recovery[-1][1] if recovery else prefix)==retirement.physical(recovered),'REMOVE process source final projection')
    return prefix,recovered,recovery,steps[:at+1]


def interruption(root,group,voters,profile):
    files,copies=governing(group,voters)
    after,steps,details=retirement.generation_plan(files,'node-1',copies)
    point=profile['point']
    if point.startswith('RETIREMENT_'):
        at=prefix_at(steps,point);prefix=steps[at][1]
        recovered,recovery,_=retirement.generation_plan(files,'node-1',copies,recover=prefix)
        events=[v for v,_ in steps[:at+1]]
    else:
        _,members,packet=c.current(after)
        coverage=maintenance.confirmation.endpoints(packet,members.get('ancestry.gsr',b''))
        prefix,recovered,recovery,source_steps=source_interruption(after,point,coverage)
        events=[v for v,_ in steps]+[v for v,_ in source_steps]
        for _,state in source_steps:capacity(state)
    for _,state in [*steps,*recovery]:capacity(state)
    capacity(prefix)
    need({p.name for p in (root/'interrupted').iterdir()}==set(group),'REMOVE process interrupted owners')
    for node,original in group.items():
        expected=prefix if node=='node-1' else retirement.physical(original)
        need(retirement.physical(c.inventory(root/'interrupted'/node))==expected,'REMOVE process exact interrupted: '+node)
    cold=dict(group,**{'node-1':recovered});b.match(root,'resume-opened-0',cold)
    # The retained complete floor is released during pre-grant maintenance, not
    # during cold open. Its exact bytes have already been compared above.
    cold['node-1']={k:v for k,v in recovered.items() if k!='floor-copies' and not k.startswith('floor-copies/')}
    return cold,dict(prefixEvents=events,recoveryEvents=[v for v,_ in recovery],**details)


def physical(root,profile=None):
    root=Path(root);profile=profile or profile_at(root);history=root/'history'
    original=a.prelude(history,'INTENT',size=int(profile['profile'][0]))
    b.match(history,'before-child',original.group);b.match(history,profile['mode']+'-opened-0',original.group)
    child=process.trace(root/'interrupted-worker/stdout');resumed=process.trace(root/'resumed-worker/stdout')
    rounds=[v for k,v in child if k=='ROUND']
    need([v['event'] for v in rounds]==['INSTALLED','SLOT_BEGIN'],'REMOVE process interrupted round lifecycle')
    group,voters=install(history,original.group,base64.b64decode(rounds[0]['record'],validate=True),
                         profile['mode']+'-installed-1',maintain=False)
    packet=c.current(group['node-1'])[2];cap=packet['capsule']
    catalog=f.decode(packet['objects'][cap['catalog']],'records','CATALOG');operation=catalog['results'][-1]
    payload=f.canonical(dict(sealed={k:operation[k] for k in ('request','prepared','receipt')}))
    selected=f.decode(base64.b64decode(rounds[0]['record'],validate=True),'records','SELECTED')
    entry=f.encode('records','ENTRY',dict(root=cap['root'],authority=e.authority(cap['root'],cap['cut']['view']),
        index=5,previous=cap['cut']['entry'],origin=selected['ballot'],kind='INTENT',payload=e.digest(payload)))
    need(base64.b64decode(rounds[1]['record'],validate=True)==entry,'REMOVE process interrupted original command')
    group,cut=interruption(history,group,voters,profile)
    model=process.ProcessSlot.__new__(process.ProcessSlot);model.__dict__.update(original.__dict__)
    model.group=group;model.mode='resume';ordinal=0;slots=[]
    for kind,row in resumed:
        if kind!='ROUND':continue
        raw=base64.b64decode(row['record'],validate=True)
        if row['event']=='INSTALLED':
            ordinal+=1;model.group,model.voters=install(history,model.group,raw,'resume-installed-'+str(ordinal),maintain=True)
            model.active=list(model.voters);model.first=None
        elif row['event']=='SLOT_BEGIN':
            entry=f.decode(raw,'records','ENTRY');need(ordinal>0,'REMOVE process slot before installation')
            model.group=maintenance.maintenance(model.group,model.voters);model.requested_entry=raw
            operation=model.state()[3]['results'][-1];command=None
            if entry['kind']=='INTENT':command=dict(sealed={k:operation[k] for k in ('request','prepared','receipt')})
            elif entry['kind']=='FINAL':command=dict(binding=operation['binding'])
            else:need(entry['kind']=='BARRIER','REMOVE process unexpected command')
            model.publish(entry['kind'],command);slots.append(dict(index=entry['index'],kind=entry['kind']))
    need(ordinal==3 and slots==[dict(index=i,kind=k) for i,k in ((5,'INTENT'),(6,'FINAL'),(7,'BARRIER'))],
         'REMOVE process exact continuation slots')
    b.match(history,'after-resume',model.group);b.match(history,'after-close',model.group)
    cap=model.state()[2];catalog=model.state()[3]
    need(cap['cut']['index']==7 and cap['cut']['view']['operation'] is None and catalog['active'] is None and
         catalog['results'][-1]['phase']=='COMPLETED','REMOVE process original completed operation')
    return dict(status='PASS',profile=profile,slots=slots,retirement=cut,
                physicalHistoryQualified=True,processDeathQualified=False,networkQualified=False,phase3Complete=False)


OPEN=('CURRENT_VALIDATED','CURRENT_FILES_FORCED','CURRENT_GENERATION_FORCED','CURRENT_SELECTOR_FORCED',
      'CURRENT_DIRECTORY_FORCED','RETENTION_RECOVERY_ACTIVE_FORCED','RETENTION_RECOVERY_PARENT_FORCED',
      'FUTURE_RETENTION_RECOVERY_FORCED','FUTURE_RETENTION_RECOVERY_PARENT_FORCED',
      'ACCEPT_ACTIVE_FORCED','ACCEPT_ACTIVE_PARENT_FORCED')


def lifecycle(root,profile,result):
    core={k:profile[k] for k in ('index','point','mode')}
    process.process_outcome(d.read(root/'process.json'),core)
    child=process.trace(root/'interrupted-worker/stdout');resumed=process.trace(root/'resumed-worker/stdout')
    need([v for k,v in child if k=='OPEN']==[profile['mode']] and (root/'interrupted-worker/stderr').read_bytes()==b'',
         'REMOVE process complete interrupted output')
    cut=dict(index=5,event=profile['point'])
    need(child[-2:]==[('STORE',cut),('CUT',cut)] and sum(k=='CUT' for k,v in child)==1 and
         not any(k in ('READY','CLOSED','SLOT') for k,v in child),'REMOVE process exact interrupted boundary')
    need([v for k,v in child if k=='SNAPSHOT']==[profile['mode']+'-opened-0',profile['mode']+'-installed-1'],
         'REMOVE process interrupted snapshots')
    for rows,mode,expected in ((child,profile['mode'],list(OPEN)),
                                (resumed,'resume',list(OPEN)+result['retirement']['recoveryEvents'])):
        at=next(i for i,(k,v) in enumerate(rows) if k=='SNAPSHOT')
        need(rows[:at]==[('STORE',dict(event=v,index=0)) for v in expected] and
             rows[at:at+2]==[('SNAPSHOT',mode+'-opened-0'),('OPEN',mode)],'REMOVE process cold-open recovery order')
    stores=[v for k,v in child if k=='STORE' and v['event'].startswith(retirement.PREFIXES)]
    need(stores==[dict(event=v,index=5) for v in result['retirement']['prefixEvents']],
         'REMOVE process exact interruption force order')
    store_names=[v['event'] for k,v in child if k=='STORE']
    d.s.ordered(store_names,['PROMISE_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN','SELECTED_FORCED',
        'INSTALL_PARENT_FORCED','INSTALL_BEFORE_RETURN',*maintenance.FLOOR], 'REMOVE process floor before retirement')
    need(not any(v.startswith('FLOOR_RELEASE_') for v in store_names),'REMOVE process unreleased governing floor')
    process.lifecycle(root,core,interrupted_retirement=True)


def validate(root):
    root=Path(root);before=run.h.inventory(root);profile=profile_at(root);layout(root,profile)
    # Non-selected peers can reject FUTURE_RETENTION_INTENT while the selected
    # quorum completes. Preserve these diagnostics; this reader does not claim
    # complete control/transfer-network qualification.
    failures=d.read(root/'history/failures.json')
    need(type(failures) is list and len(failures)<=32768,'REMOVE process bounded network diagnostics')
    result=physical(root,profile);lifecycle(root,profile,result)
    need(run.h.inventory(root)==before,'REMOVE process original changed')
    return dict(result,scope='same-proposer-REMOVE-retirement-recovery',processDeathQualified=True,
                publicationAcknowledgementsQualified=True,activationAcknowledgementsQualified=False,
                unqualifiedNetworkDiagnostics=len(failures),networkDiagnosticsSha256=e.digest(f.canonical(failures)))


NEGATIVES={
    'extra-file':'context selection REMOVE process inventory',
    'interrupted-authority':'REMOVE process exact interrupted: node-1',
    'interrupted-peer':'REMOVE process exact interrupted: node-2',
    'recovered-selector':'admitted exact resume-opened-0: node-1',
    'recovered-peer':'admitted exact resume-opened-0: node-2',
    'recovered-floor':'admitted exact resume-opened-0: node-1',
    'completed-selector':'admitted exact after-resume: node-1',
    'closed-selector':'admitted exact after-close: node-1',
    'same-worker':'transition process distinct original workers',
    'wrong-exit':'transition process distinct original workers',
    'false-lock':'transition process distinct original workers',
    'premature-ready':'REMOVE process exact interrupted boundary',
    'wrong-cut':'REMOVE process exact interrupted boundary',
    'wrong-command':'REMOVE process interrupted original command',
    'missing-cold-force':'REMOVE process cold-open recovery order',
    'missing-retirement-force':'REMOVE process exact interruption force order',
    'missing-floor-force':'selected retention force order: REMOVE process floor before retirement',
    'early-floor-release':'REMOVE process unreleased governing floor',
    'missing-reactivation':'REMOVE process slot before installation',
    'missing-proposer-force':'selected retention force order: transition original proposer 7',
    'missing-peer-force':'selected retention force order: transition original peer node-2',
    'missing-remote-ack':'transition process original remote acknowledgement',
    'wrong-local-ack':'transition process original local acknowledgement',
    'wrong-ready-ack':'transition process readiness after barrier',
    'wrong-ready-result':'transition process exact readiness result',
    'missing-open-snapshot':'REMOVE process interrupted snapshots',
    'missing-published-snapshot':'transition process exact observation boundaries',
}


def mutate(root,name):
    root=Path(root)
    def change_json(path,change):
        value=d.read(path);change(value);path.write_bytes(f.canonical(value))
    paths={'interrupted-peer':'interrupted/node-2/selector.gsr','recovered-selector':'resume-opened-0/node-1/selector.gsr',
           'recovered-peer':'resume-opened-0/node-2/selector.gsr','recovered-floor':'resume-opened-0/node-1/floor-copies/floor.gsr',
           'completed-selector':'after-resume/node-1/selector.gsr','closed-selector':'after-close/node-1/selector.gsr'}
    if name=='extra-file':(root/'extra').write_bytes(b'extra');return
    if name=='interrupted-authority':
        path=root/'history/interrupted/node-1'
        path=next((path/p for p in ('retirement/images.json','retirement/proposal.gsr','retirement/retirement.gsr',
                                  'sources.retirement.gsr') if (path/p).is_file()),path/'selector.gsr')
        path.write_bytes(path.read_bytes()+b'changed');return
    if name in paths:
        path=root/'history'/paths[name];path.write_bytes(path.read_bytes()+b'changed');return
    if name in ('same-worker','wrong-exit','false-lock'):
        def change(v):
            if name=='same-worker':v['resumePid']=v['childPid']
            elif name=='wrong-exit':v['exit']=0
            else:v['liveLockRefused']=not v['liveLockRefused']
        change_json(root/'process.json',change);return
    if name=='wrong-ready-ack':(root/'resumed-worker/ready.gsrp').write_bytes(b'changed');return
    if name=='wrong-ready-result':change_json(root/'resumed-worker/ready.json',lambda v:v.update(state='FOLLOWER'));return
    if name=='missing-peer-force':
        path=root/'history/events.json';rows=d.read(path)
        path.write_bytes(f.canonical([v for v in rows if not(v['node']=='node-2' and v['event']=='PUBLICATION_SELECTOR_FORCED')]));return
    child=name in {'premature-ready','wrong-cut','wrong-command','missing-retirement-force','missing-floor-force','early-floor-release','missing-open-snapshot'}
    path=root/('interrupted-worker' if child else 'resumed-worker')/'stdout';rows=process.trace(path)
    def remove(predicate):
        at=next(i for i,(k,v) in enumerate(rows) if predicate(k,v));rows.pop(at)
    if name=='premature-ready':rows.append(('READY','premature'))
    elif name=='wrong-cut':rows[-1]=('CUT',dict(event='RETIREMENT_CLEARED',index=5))
    elif name=='wrong-command':
        at=next(i for i,(k,v) in enumerate(rows) if k=='ROUND' and v['event']=='SLOT_BEGIN')
        k,row=rows[at];value=f.decode(base64.b64decode(row['record']),'records','ENTRY');value['payload']='0'*64
        rows[at]=(k,dict(row,record=base64.b64encode(f.encode('records','ENTRY',value)).decode()))
    elif name=='missing-cold-force':remove(lambda k,v:k=='STORE' and v['event']=='CURRENT_SELECTOR_FORCED')
    elif name=='missing-retirement-force':remove(lambda k,v:k=='STORE' and v['event']=='RETIREMENT_OLD_FILES_FORCED')
    elif name=='missing-floor-force':remove(lambda k,v:k=='STORE' and v['event']=='FLOOR_AUTHORITY_FORCED')
    elif name=='early-floor-release':rows.insert(-2,('STORE',dict(event='FLOOR_RELEASE_BEFORE_RETURN',index=5)))
    elif name=='missing-reactivation':remove(lambda k,v:k=='ROUND' and v['event']=='INSTALLED')
    elif name=='missing-proposer-force':
        rows=[(k,v) for k,v in rows if not(k=='STORE' and v==dict(event='PROOF_PARENT_FORCED',index=7))]
    elif name=='missing-remote-ack':
        rows=[(k,v) for k,v in rows if not(k=='AFTER_RESPONSE_READ' and
              int.from_bytes(base64.b64decode(v['request'])[8:10],'big')==f.catalog()['wire']['PUBLISH']['id'])]
    elif name=='wrong-local-ack':
        at=next(i for i,(k,v) in enumerate(rows) if k=='ROUND' and v['event']=='SLOT_COMPLETE')
        k,row=rows[at];ack=f.decode(base64.b64decode(row['record']),'wire','PUBLISH_ACK');ack['payload']['generation']='0'*64
        rows[at]=(k,dict(row,record=base64.b64encode(f.encode('wire','PUBLISH_ACK',ack)).decode()))
    elif name=='missing-open-snapshot':remove(lambda k,v:k=='SNAPSHOT' and v.endswith('-opened-0'))
    elif name=='missing-published-snapshot':remove(lambda k,v:k=='SNAPSHOT' and v=='resume-published-7')
    else:raise ValueError('REMOVE process unknown negative: '+name)
    path.write_text(''.join(k+' '+(v if type(v) is str else f.canonical(v).decode('ascii'))+'\n' for k,v in rows))


def negative(root,name):
    with tempfile.TemporaryDirectory(prefix='v53-remove-process-negative-') as temp:
        changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,name)
        try:validate(changed)
        except ValueError as error:need(str(error)==NEGATIVES[name],'REMOVE process unrelated negative: '+name+': '+str(error))
        else:raise ValueError('REMOVE process mutation accepted: '+name)
    return dict(case=name,status='REJECTED',reason=NEGATIVES[name])


def qualify(root,*,workers=1):
    need(type(workers) is int and 1<=workers<=4,'REMOVE process replay workers')
    root=Path(root);original=validate(root);before=run.h.inventory(root);outcomes=[]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        pending={pool.submit(negative,root,name):name for name in NEGATIVES}
        for task in as_completed(pending):
            name=pending[task]
            try:result=task.result()
            except Exception as error:result=dict(case=name,status='FAIL',failure=str(error),type=type(error).__name__)
            outcomes.append(result);print(json.dumps(dict(result,completed=len(outcomes),total=len(pending))),file=sys.stderr,flush=True)
    need(run.h.inventory(root)==before,'REMOVE process negative changed original')
    need(all(v['status']=='REJECTED' for v in outcomes),'REMOVE process negative matrix failed')
    return dict(original=original,negatives=sorted(outcomes,key=lambda v:v['case']),negativePrecondition='full-original-first')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true')
    parser.add_argument('--workers',type=int,default=1);args=parser.parse_args()
    print(json.dumps(qualify(args.root,workers=args.workers) if args.qualify else validate(args.root),sort_keys=True))
