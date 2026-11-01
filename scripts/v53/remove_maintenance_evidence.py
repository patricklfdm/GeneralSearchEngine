"""Current REMOVE maintenance derived from preceding original physical states.

This projection requires complete governing copies and covered source anchors.
It supplies no network or process-crash authority; enclosing readers must bind
force order and compare the complete resulting original inventories.
"""
import copy
from . import authority_transition_evidence as a
from . import joining_confirmation_evidence as confirmation
from . import peer_observation_evidence as observation
from .joining_same_view_physical import covering_floor

c,d,e,f,need=a.c,a.d,a.e,a.f,a.need
FLOOR=('FLOOR_COPIES_FORCED','FLOOR_AUTHORITY_FORCED','FLOOR_PARENT_FORCED','FLOOR_BEFORE_RETURN')
RETIRE=('RETIREMENT_AUTHORITY_FORCED','RETIREMENT_PARENT_FORCED','RETIREMENT_DELETE_VALIDATED','RETIREMENT_BEFORE_RETURN')
SOURCE=('SOURCE_RETIREMENT_FORCED','SOURCE_RETIREMENT_PARENT_FORCED','JOURNAL_ROTATION_FORCED',
        'JOURNAL_ROTATION_PARENT_FORCED','SOURCE_RETIREMENT_JOURNAL_PRUNED','SOURCE_RETIREMENT_FILE_DELETED','SOURCE_RETIREMENT_BEFORE_RETURN')
RELEASE=('FLOOR_RELEASE_BEFORE_RETURN',)


def boundaries(root,ordinal,voters,before_group,after_group):
    events=d.read(root/'events.json')
    installed=[i for i,v in enumerate(events) if v['event']=='CONTINUOUS_INSTALLED' and v['ordinal']==ordinal]
    need(len(installed)==1 and events[installed[0]]['selection']==e.digest((root/f'selected-{ordinal}.gsr').read_bytes()),
         'continuous installed original selection')
    finishes=[i for i,v in enumerate(events) if v['event']=='DRIVER_PUBLISHED' and v['index']==ordinal+4]
    need(len(finishes)==1 and installed[0]<finishes[0],'REMOVE maintenance original slot lifetime')
    all_points=set(FLOOR+RETIRE+SOURCE+RELEASE)
    for node in voters:
        trace=[v['event'] for v in events[installed[0]:finishes[0]] if v['node']==node]
        need('ACCEPT_CANDIDATE_CREATED' in trace,'REMOVE maintenance original vote')
        before=trace[:trace.index('ACCEPT_CANDIDATE_CREATED')]
        removed=[k for k,v in before_group[node].items() if k.startswith('sources/') and v is not None and k not in after_group[node]]
        need(bool(removed),'REMOVE maintenance original retired source files')
        source=SOURCE[:5]+('SOURCE_RETIREMENT_FILE_DELETED',)*len(removed)+SOURCE[6:]
        need([v for v in before if v in all_points]==list(FLOOR+RETIRE+source+RELEASE),
             'REMOVE maintenance exact pre-slot retirement: '+node)
    if ordinal==1:return
    prior=[i for i,v in enumerate(events) if v['event']=='DRIVER_PUBLISHED' and v['index']==ordinal+3]
    need(len(prior)==1 and prior[0]<installed[0],'REMOVE maintenance original campaign lifetime')
    expected=FLOOR+RETIRE+RELEASE+('PROMISE_FORCED','SOURCE_DIRECTORY_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN',
        'SELECTED_FORCED','INSTALL_PARENT_FORCED','INSTALL_BEFORE_RETURN')
    for node in voters:
        trace=[v['event'] for v in events[prior[0]:installed[0]] if v['node']==node]
        need([v for v in trace if v in all_points|set(expected)]==list(expected),
             'REMOVE maintenance exact pre-grant retirement: '+node)


def maintenance(group,voters):
    result=copy.deepcopy(group)
    for node in voters:
        files=result[node];prefix,members,packet=c.current(files);cap=packet['capsule']
        need(files['pending.accept']==c.EMPTY and not any(k=='applied-end' or k.startswith('applied-end/') for k in files),
             'REMOVE maintenance unsettled publication')
        copies={n:group[n] for n in voters}
        covering_floor(files,copies,node)
        for peer in (node,*(n for n in voters if n!=node)):
            files[d.s.FILE]=observation.observe_same_cut(files[d.s.FILE],group[node],group[peer],defer_renewal=True)
        available=confirmation.endpoints(packet,members.get('ancestry.gsr',b''))
        plan=d.s.r.decode(files[d.s.FILE])['plan']
        for row in plan['peers']:
            for point in [*row.get('renewals',[]),*row['possible']]:
                need(available.get(point['cut']['index'])==point,'REMOVE maintenance retained coverage')
        files={k:v for k,v in files.items() if not k.startswith('generations/') or k==prefix[:-1] or k.startswith(prefix)}
        rows=c.journal(files['grants.gsr'],cap['root'],node)
        promises={v['basisId']:(raw,v) for kind,raw,v in rows if kind=='PROMISE' and v['basisId'] is not None}
        latest=next(v['ballot'] for kind,_,v in reversed(rows) if kind=='PROMISE');retired=set()
        for name,raw in files.items():
            if not name.startswith('sources/') or not name.endswith('/source.gscp'):continue
            identifier=name.split('/')[1];promise,value=promises[identifier]
            if promise==members['promise.gsr'] or value['ballot']==latest:continue
            point=c.anchor(c.p.decode(raw)['capsule'])
            need(value['ballot']['counter']<latest['counter'] and available.get(point['cut']['index'])==point,
                 'REMOVE maintenance source retirement coverage')
            retired.add(identifier)
        kept=[];discard=False
        for kind,raw,value in rows:
            if kind=='PROMISE':discard=value['basisId'] in retired or (retired and value['basisId'] is None
                and raw!=members['promise.gsr'] and value['ballot']!=latest)
            if not discard:kept.append(raw)
        result[node]={k:v for k,v in files.items() if not (k.startswith('sources/') and k.split('/')[1] in retired)}
        result[node]['grants.gsr']=b''.join(kept)
    return result


def merge(group,before,originals):
    packet=c.current(group['node-1'])[2];catalog=f.decode(packet['objects'][packet['capsule']['catalog']],'records','CATALOG')
    identities={v['node']:v for v in catalog['identities']}
    state=d.s.r.decode(before)
    plan=confirmation.merge([d.s.r.decode(raw)['plan'] for raw in [before,*originals]],packet,identities,[])
    return before if plan==state['plan'] else d.s.r.frame(dict(state,revision=state['revision']+1,previous=e.digest(before),plan=plan))
