"""Independent M02/M03 schedules and gates, after physical/lifecycle validation."""
from . import measurement_minimum as controller,measurement_model as model,token
from scripts.v51 import runtime_evidence as physical,rejoin_evidence as rejoin,recovery_inspector as recovery
from .evidence import need


def schedule(history,scenario,observed,plan):
    need(plan==controller.profile(plan.get('case')) and scenario['case']==plan['case'] and
         scenario['family']==plan['family'] and scenario['stage']=='observed','minimum changed/incomplete scenario')
    calls={c['opId']:c for c in history};need(len(calls)==len(history),'minimum duplicate command')
    def call(identity,kind,node):
        c=calls.get(identity);need(c is not None and c['kind']==kind and c['node']==node,'minimum command target/kind');return c
    leader=scenario['leader'];target=scenario['readTarget'];nodes={'node-1','node-2','node-3'}
    need(leader in nodes and target==(leader if plan['family']=='M03' else sorted(nodes-{leader})[-1]),'minimum changed frozen target')
    need(set(scenario['baseline'])==set(scenario['floorProbes'])==nodes,'minimum preparation voter set')
    initial=call(scenario['initialRead'],'read',leader)
    need(initial.get('setupToken') is True and initial['query']==model.query(0) and initial['outcome']=='SUCCESS' and
         initial['response']['sequence']==4,'minimum setup strong cut')
    issued=token.decode(physical.raw(initial['response']['token']))
    updates=[call(i,'update',leader) for i in scenario['setupUpdates']]
    program=[c['document'] for c in model.program() if c['kind']=='update']
    need(len(updates)==3 and [c['document'] for c in updates]==program[:3] and all(c['outcome']=='SUCCESS' for c in updates) and
         all(a['endNanos']<b['startNanos'] for a,b in zip(updates,[*updates[1:],initial])),'minimum setup update order')
    baseline=scenario['baselineStatus'];held=scenario['heldStatus'];base_call=call(baseline['opId'],'status',target)
    held_call=call(held['opId'],'status',target);baseline_index=baseline['publishedIndex']
    need(base_call['response']==baseline and held_call['response']==held and baseline['sequence']==held['sequence']==4 and
         baseline_index==held['publishedIndex']>=issued['index'] and baseline['state']==held['state']==('LEADER_READY' if target==leader else 'FOLLOWER'),
         'minimum changed baseline/held publication')
    bound=token.decode(physical.raw(scenario['minimum']))
    need(all(bound[k]==issued[k] for k in ('version','groupId','historyId','manifestDigest')) and
         bound['index']==baseline_index+{'below':-1,'equal':0,'above':1}[plan['relation']],'minimum changed bound relation/domain')
    baseline_probe=call(scenario['baselineProbe'],'probe',target);gate=call(scenario['admittedProbe'],'probe',target)
    need(base_call['endNanos']<baseline_probe['startNanos'] and gate['endNanos']<=scenario['gateNanos']<held_call['startNanos'],
         'minimum gate controller order')
    n=plan['readCount'];rows=observed['operations'];expected=n+(plan['family']=='M03')+plan['releaseUpdate']
    need(len(rows)==expected and observed.get('drained') is True and observed['unobserved']==0 and
         observed['drainStartNanos']<=observed['drainEndNanos'],'minimum incomplete offered ledger')
    read_calls=[];ids=set();previous=baseline_probe['endNanos']
    for ordinal,row in enumerate(rows):
        expected_kind='read' if ordinal<n else 'excess' if plan['family']=='M03' and ordinal==n else 'release-update'
        need(row['kind']==expected_kind and (row.get('ordinal')==ordinal if ordinal<n else 'ordinal' not in row) and
             row['status']=='DISPATCHED' and row['completionStatus']=='OBSERVED' and row['opId'] not in ids,'minimum missing/retried offer')
        ids.add(row['opId']);c=call(row['opId'],'update' if expected_kind=='release-update' else 'read',leader if expected_kind=='release-update' else target)
        need(previous<row['offerNanos']<=c['startNanos']<=row['submittedNanos']<=observed['drainStartNanos'] and
             c['endNanos']<=observed['drainEndNanos'] and row['response']==c['response'],'minimum offered response/clock binding')
        previous=row['submittedNanos']
        if expected_kind!='release-update':
            need(c['query']==model.query(ordinal) and c.get('minimum')==scenario['minimum'] and not c.get('setupToken'),'minimum changed offered read')
            if ordinal<n:read_calls.append(c)
        else:need(c['document']==program[3] and c['outcome']=='SUCCESS','minimum changed/failed progress write')
    need([c['opId'] for c in read_calls]==scenario['readOps'] and rows[n-1]['submittedNanos']<gate['startNanos'],
         'minimum admission gate precedes offered calls')
    expected_business=ids|{c['opId'] for c in updates}|{initial['opId']}
    need({c['opId'] for c in history if c['kind'] in ('read','update')}==expected_business,'minimum undeclared business call')
    if plan['family']=='M03':
        excess=call(scenario['excessRead'],'read',target);rejected=call(scenario['rejectedProbe'],'probe',target)
        need(excess['opId']==rows[n]['opId'] and excess['outcome']=='NOT_APPLICABLE' and excess['response'].get('reasonCode')=='CAPACITY_EXCEEDED' and
             held_call['endNanos']<excess['startNanos']<excess['endNanos']<rejected['startNanos'],'minimum missing excess capacity rejection')
        need(all(c['outcome']=='SUCCESS' for c in read_calls),'minimum saturation waiter failed')
    elif plan['relation']=='above' and plan['parameters']['waitTimeoutMillis']==0:
        need(all(c['outcome']=='REJECTED' and c['response'].get('reasonCode')=='PROGRESS_NOT_REACHED' for c in read_calls),
             'minimum zero-wait rejection coverage')
    else:
        need({c['query']['kind'] for c in read_calls if c['outcome']=='SUCCESS'}==set(model.KINDS),'minimum successful query coverage')
    if plan['releaseUpdate']:
        release=call(scenario['releaseUpdate'],'update',leader)
        need(release['opId']==rows[-1]['opId'] and scenario['gateNanos']+plan['releaseDelayNanos']<=scenario['releaseOfferNanos']<=rows[-1]['offerNanos'] and
             (rejected if plan['family']=='M03' else held_call)['endNanos']<release['startNanos'],'minimum progress release preceded gate/delay')
    else:need('releaseUpdate' not in scenario and 'releaseOfferNanos' not in scenario,'minimum undeclared progress release')
    final=call(scenario['finalProbe'],'probe',target)
    need(observed['drainEndNanos']<final['startNanos'],'minimum final probe before drain')
    for node in nodes:
        controls=[c for c in history if c['node']==node and c['kind'].startswith('sample-')]
        need([c['kind'] for c in controls]==['sample-start','sample-stop'] and all(c['outcome']=='SUCCESS' for c in controls) and
             controls[0]['endNanos']<rows[0]['offerNanos'] and final['endNanos']<controls[-1]['startNanos'],
             'minimum sampled resource coverage')
    return dict(calls=calls,leader=leader,target=target,nodes=nodes,initial=initial,issued=issued,updates=updates,
                base_call=base_call,held_call=held_call,baseline_index=baseline_index,bound=bound,baseline_probe=baseline_probe,
                gate=gate,n=n,read_calls=read_calls,release=release if plan['releaseUpdate'] else None,
                rejected=rejected if plan['family']=='M03' else None)


def validate(history,scenario,observed,traces,manifest,plan):
    context=schedule(history,scenario,observed,plan)
    calls=context['calls'];leader=context['leader'];target=context['target'];nodes=context['nodes'];initial=context['initial']
    issued=context['issued'];base_call=context['base_call'];held_call=context['held_call'];baseline_index=context['baseline_index']
    bound=context['bound'];baseline_probe=context['baseline_probe'];gate=context['gate'];n=context['n'];read_calls=context['read_calls']
    release=context['release'];rejected=context['rejected']
    def call(identity,kind,node):
        c=calls.get(identity);need(c is not None and c['kind']==kind and c['node']==node,'minimum command target/kind');return c
    # Replay only compact metadata. General authority admission bounds the raw
    # observations before this pass; physical/lifecycle checks remain mandatory.
    streams={};floors={}
    for node,values in traces.items():
        invocations={};admitted={};settled={};captures={};responses={};starts={};latest=None;count=0;last_floor=None
        for row in values:
            event=row['event'];identity=row.get('opId')
            if event in ('APPLICATION_RESTORED','PUBLISHED','LOCAL_PUBLISHED'):
                image=recovery.snapshot(physical.raw(row['snapshot']),manifest);latest=(len(image['anchors']),image['applicationSequence'])
            elif event=='REPLICA_READ_INVOKED':invocations[row['readId']]=row
            elif event=='REPLICA_READ_ADMITTED':
                count+=1;admitted[invocations[row['readId']]['opId']]=dict(order=row['order'],publication=latest)
            elif event=='REPLICA_READ_SETTLING':settled[invocations[row['readId']]['opId']]=dict(order=row['order'],publication=latest)
            elif event=='REPLICA_READ_CAPTURE_VALIDATED':captures[invocations[row['readId']]['opId']]=row
            elif event=='RECOVERY_FLOOR':last_floor=row
            elif event=='CLIENT_INVOKE':starts[identity]=dict(order=row['order'],publication=latest,admissions=count)
            elif event in ('CLIENT_SUCCESS','CLIENT_FAILURE'):
                responses[identity]=dict(order=row['order'],publication=latest,admissions=count,row=row)
                if identity==scenario['floorProbes'][node]['opId']:floors[node]=last_floor
        streams[node]=dict(starts=starts,responses=responses,admitted=admitted,settled=settled,captures=captures)
    def event_of(c,key):return streams[c['node']][key][c['opId']]
    for node in nodes:
        prepared=scenario['baseline'][node];c=call(prepared['opId'],'status',node)
        need(c['response']==prepared and initial['endNanos']<c['startNanos'] and c['endNanos']<base_call['startNanos'] and
             prepared['sequence']==4 and prepared['publishedIndex']>=issued['index'],'minimum preparation ledger')
        floor_call=call(scenario['floorProbes'][node]['opId'],'probe',node);floor=floors.get(node)
        need(floor_call['response']==scenario['floorProbes'][node] and c['endNanos']<floor_call['startNanos']<floor_call['endNanos']<base_call['startNanos'] and
             floor is not None and floor['index']>=issued['index'] and floor['order']<event_of(floor_call,'responses')['order'],
             'minimum missing baseline recovery floor')
        need(floor_call['response']['queues']['recoveryFloorObserved']==floor['index'],'minimum fabricated recovery floor counter')
        own=rejoin.packet(floor['local'],manifest);peer=rejoin.packet(floor['remote'],manifest)
        need(own['seal']['node']==node and peer['seal']['node'] in nodes-{node} and
             own['snapshot']==peer['snapshot'] and len(own['snapshot']['anchors'])==floor['index'],'minimum baseline floor source identity')
    for c in (base_call,held_call):
        need(event_of(c,'starts')['publication']==event_of(c,'responses')['publication']==(baseline_index,4),'minimum baseline lacks physical publication')
    target_stream=streams[target];base_seen=event_of(baseline_probe,'responses');gate_seen=event_of(gate,'responses')
    expected_admissions={c['opId'] for c in read_calls}|({initial['opId']} if target==leader else set())
    need(set(target_stream['admitted'])==expected_admissions,'minimum undeclared/missing target admissions')
    for c in (baseline_probe,gate):
        seen=event_of(c,'responses');need(c['response']['queues']['readAdmissionsObserved']==seen['admissions'],'minimum fabricated admission counter')
    need(gate_seen['admissions']-base_seen['admissions']==n and all(base_seen['order']<target_stream['admitted'][c['opId']]['order']<gate_seen['order'] and
         target_stream['admitted'][c['opId']]['publication']==(baseline_index,4) for c in read_calls),'minimum admission relation/gate')
    for c in read_calls:
        identity=c['opId'];settled=target_stream['settled'][identity]
        if c['response'].get('reasonCode')=='PROGRESS_NOT_REACHED':
            need(settled['publication']==(baseline_index,4) and baseline_index<bound['index'] and identity not in target_stream['captures'],
                 'minimum zero-wait rejection lacks below-bound cut')
        if plan['family']=='M03':
            need(settled['order']>event_of(release,'starts')['order'] and
                 target_stream['captures'][identity]['order']>event_of(release,'starts')['order'],'minimum waiter escaped saturation before write')
    if plan['family']=='M03':
        for c in (gate,rejected):
            v=c['response']['queues'];need(v['admissionAvailable']==1 and v['readsOwned']==v['readsWaiting']==v['readsAlarms']==n and
                 v['readsCaptured']==v['readsSettling']==0,'minimum saturation queue gate')
    return dict(status='PASS',execution='minimum-schedule-gates-only',qualifiedMeasurement=False,
                case=plan['case'],reads=n,excessReads=int(plan['family']=='M03'),releaseUpdates=int(plan['releaseUpdate']),baselineIndex=baseline_index,minimumIndex=bound['index'])
