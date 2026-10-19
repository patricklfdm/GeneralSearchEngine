"""Closed M04 schedule and physical fault gates, without cross-clock subtraction."""
from scripts.v51 import runtime_evidence as physical,recovery_inspector as recovery,rejoin_evidence as rejoin
from . import measurement_recovery as controller,measurement_model as model,measurement_trace as trace,token,measurement_generations as generations
from .evidence import need


def schedule(history,scenario,plan):
    need(type(history) is list and 0<len(history)<=4*4096,'recovery command ledger bound')
    need(plan==controller.profile(plan.get('case')) and scenario['case']==plan['case'] and
         scenario['family']=='M04' and scenario['stage']=='observed','recovery changed/incomplete scenario')
    calls={c['opId']:c for c in history};need(len(calls)==len(history),'recovery duplicate command')
    def call(identity,kind,node,generation=1):
        c=calls.get(identity)
        need(c is not None and c['kind']==kind and c['node']==node and c['generation']==generation and c['outcome']=='SUCCESS',
             'recovery changed/failed command target')
        need(type(c['startNanos']) is int and type(c['endNanos']) is int and c['startNanos']<c['endNanos'],
             'recovery command clock')
        return c
    def response(value,kind,node,generation=1):
        c=call(value['opId'],kind,node,generation);need(c['response']==value,'recovery copied response differs');return c
    leader=scenario['leader'];need(leader in generations.NODES,'recovery leader identity')
    initial=call(scenario['initialRead'],'read',leader)
    issued=token.decode(physical.raw(initial['response']['token']))
    need(initial.get('setupToken') is True and 'minimum' not in initial and initial['query']==model.query(0) and
         initial['response']['sequence']==4 and scenario['carriedToken']==initial['response']['token'],'recovery initial strong token')
    program=[c['document'] for c in model.program() if c['kind']=='update']
    updates=[call(identity,'update',leader) for identity in scenario['setupUpdates']]
    need(len(updates)==3 and [c['document'] for c in updates]==program[:3] and
         all(a['endNanos']<b['startNanos'] for a,b in zip(updates,[*updates[1:],initial])),'recovery setup update order')
    need(set(scenario['initialStatus'])==set(scenario['baseline'])==set(scenario['baselineFloors'])==generations.NODES,
         'recovery preparation voter set')
    fault=scenario['killIssuedNanos'] if plan['case']==controller.CASES[0] else scenario['partitionNanos']
    for node in sorted(generations.NODES):
        ready=response(scenario['initialStatus'][node],'status',node)
        need(ready['endNanos']<updates[0]['startNanos'] and (ready['response']['state']=='LEADER_READY')==(node==leader),
             'recovery initial leader observation')
        baseline=response(scenario['baseline'][node],'status',node);floor=response(scenario['baselineFloors'][node],'probe',node)
        need(initial['endNanos']<baseline['startNanos']<baseline['endNanos']<floor['startNanos']<floor['endNanos']<fault and
             baseline['response']['sequence']==4 and baseline['response']['publishedIndex']>=issued['index'] and
             floor['response']['queues']['recoveryFloorObserved']>=issued['index'],'recovery baseline/floor order')
    reads=[initial]
    if plan['case']==controller.CASES[0]:
        successor=scenario['successor'];need(successor in generations.NODES-{leader},'recovery successor identity')
        crash=scenario['crash'];need(crash['node']==leader and crash['generation']==1 and crash['exitCode']==-9,'recovery owned crash identity')
        need(set(scenario['successorStatus'])==generations.NODES-{leader},'recovery survivor set')
        for node,value in scenario['successorStatus'].items():
            c=response(value,'status',node)
            need(scenario['exitObservedNanos']<c['startNanos']<c['endNanos']<=scenario['readyObservedNanos'] and
                 (value['state']=='LEADER_READY')==(node==successor),'recovery successor activation order')
        write=call(scenario['progressWrite'],'update',successor)
        strong=call(scenario['successorStrong'],'read',successor);minimum=call(scenario['successorMinimum'],'read',successor)
        last=call(scenario['restartedMinimum'],'read',leader,2);recovered=response(scenario['recovered']['status'],'status',leader,2)
        keys=('killIssuedNanos','exitObservedNanos','readyObservedNanos','writeObservedNanos','strongObservedNanos',
              'minimumObservedNanos','restartIssuedNanos','restartStartedNanos','restartedReadObservedNanos')
        values=[scenario[k] for k in keys]
        need(all(type(v) is int and v>0 for v in values) and all(a<b for a,b in zip(values,values[1:])),
             'recovery crash/restart milestone order')
        need(scenario['readyObservedNanos']<write['startNanos']<write['endNanos']<=scenario['writeObservedNanos']<strong['startNanos'] and
             strong['endNanos']<=scenario['strongObservedNanos']<minimum['startNanos'] and minimum['endNanos']<=scenario['minimumObservedNanos'] and
             scenario['restartStartedNanos']<recovered['startNanos']<recovered['endNanos']<last['startNanos']<last['endNanos']<=scenario['restartedReadObservedNanos'],
             'recovery original response milestone binding')
        reads.extend((strong,minimum,last));target=leader
        need(minimum.get('minimum')==last.get('minimum')==scenario['carriedToken'],'recovery changed carried token')
        need(all(c['endNanos']<fault for c in history if c['node']==leader and c['generation']==1) and
             all(c['startNanos']>scenario['restartStartedNanos'] for c in history if c['node']==leader and c['generation']==2),
             'recovery calls cross owned crash/reopen boundary')
        milestones={key:scenario[key]-scenario['exitObservedNanos'] for key in ('readyObservedNanos','writeObservedNanos','strongObservedNanos','minimumObservedNanos','restartedReadObservedNanos')}
    else:
        target=scenario['target'];need(target in generations.NODES-{leader},'recovery snapshot target identity')
        selected=call(scenario['selectedProbe'],'probe',leader);status=call(scenario['selectedStatus'],'status',leader)
        mask=selected['response']['queues']['selectedVotersObserved']
        need(mask in (3,5,6) and mask&(1<<(int(leader[-1])-1)) and not mask&(1<<(int(target[-1])-1)) and
             selected['response']['queues']['selectedEpochObserved']==status['response']['epoch'] and status['response']['state']=='LEADER_READY',
             'recovery target belongs to selected pair')
        isolated=response(scenario['isolatedStatus'],'status',target);held=response(scenario['heldStatus'],'status',target)
        write=call(scenario['progressWrite'],'update',leader);strong=call(scenario['laterStrong'],'read',leader)
        later_index=token.decode(physical.raw(strong['response']['token']))['index']
        need(selected['endNanos']<status['startNanos']<status['endNanos']<fault<isolated['startNanos']<isolated['endNanos']<write['startNanos'] and
             held['response']['sequence']==4 and held['response']['publishedIndex']<later_index and held['endNanos']<scenario['healIssuedNanos']<=scenario['healCompletedNanos'],
             'recovery partition/held publication order')
        need(set(scenario['sourceFloors'])==generations.NODES-{target},'recovery source floor pair')
        for node,value in scenario['sourceFloors'].items():
            c=response(value,'probe',node)
            need(strong['endNanos']<c['startNanos']<c['endNanos']<held['startNanos'] and value['queues']['recoveryFloorObserved']>=later_index,
                 'recovery source floor before progress')
        recovered=response(scenario['installed']['status'],'status',target);installed=response(scenario['installed']['probe'],'probe',target)
        need(scenario['healCompletedNanos']<recovered['startNanos']<recovered['endNanos']<installed['startNanos']<installed['endNanos']<=scenario['publicationObservedNanos'] and
             recovered['response']['state']=='FOLLOWER' and installed['response']['queues']['snapshotInstalledIndexObserved']>=later_index,
             'recovery missing follower snapshot observation')
        old=call(scenario['oldMinimum'],'read',target);new=call(scenario['newMinimum'],'read',target)
        need(scenario['publicationObservedNanos']<old['startNanos'] and new['endNanos']<=scenario['minimumObservedNanos'] and
             old.get('minimum')==scenario['carriedToken'] and new.get('minimum')==strong['response']['token'],'recovery snapshot carried token order')
        reads.extend((strong,old,new));milestones={key:scenario[key]-scenario['healCompletedNanos'] for key in ('publicationObservedNanos','minimumObservedNanos')}
    need(write['document']==program[3] and initial['endNanos']<write['startNanos']<write['endNanos']<reads[1]['startNanos'],
         'recovery changed progress write')
    need([c['query'] for c in reads]==[model.query(i) for i in range(4)] and
         all(a['endNanos']<b['startNanos'] for a,b in zip(reads,reads[1:])) and reads[1].get('setupToken') is True and
         all(not c.get('setupToken') and 'minimum' in c for c in reads[2:]) and
         all(c['response']['sequence']==5 for c in reads[1:]),'recovery changed/read query sequence')
    later_index=token.decode(physical.raw(reads[1]['response']['token']))['index']
    need(recovered['response']['publishedIndex']>=later_index and recovered['response']['sequence']==5,'recovery target publication below progress')
    expected={c['opId'] for c in [*updates,write,*reads]}
    need(len(expected)==8 and {c['opId'] for c in history if c['kind'] in ('read','update')}==expected,'recovery undeclared business call')
    starts=[c['opId'] for c in history if c['kind']=='sample-start'];stops=[c['opId'] for c in history if c['kind']=='sample-stop']
    need(starts==scenario['sampleStarts'] and stops==scenario['sampleStops'] and not any(c['kind']=='sample-mark' for c in history),
         'recovery changed sample ledger')
    return dict(calls=calls,leader=leader,target=target,initial=initial,issued=issued,initialIndex=issued['index'],laterIndex=later_index,
                reads=reads,write=write,milestones=milestones,fault=fault,recovered=recovered)


def gates(history,scenario,plan,traces,processes,manifest):
    context=schedule(history,scenario,plan);calls=context['calls'];floors={};installed={};selected={};events={};drops=[];campaigns=[]
    for process in processes:
        node=process['node'];configs=[];last_floor=None;last_install=None;last_selection=None;latest=None
        for row in generations.rows(traces,process,processes):
            event=row['event']
            if event=='FAULT_CONFIGURATION':
                need(not configs,'recovery fault configuration observation');configs.append({k:v for k,v in row.items() if k not in trace.META})
            if event in ('APPLICATION_RESTORED','PUBLISHED','LOCAL_PUBLISHED'):
                snapshot=recovery.snapshot(physical.raw(row['snapshot']),manifest);latest=(len(snapshot['anchors']),snapshot['applicationSequence'])
            if event=='RECOVERY_FLOOR':last_floor=row
            if event=='REJOIN_INSTALLED':last_install=row
            if event=='PROMISE_QUORUM':last_selection=row
            if event=='CAMPAIGN_BEGIN':campaigns.append(row)
            if event in ('CLIENT_INVOKE','CLIENT_SUCCESS'):
                events[row['opId'],event]=dict(row=row,publication=latest)
                if event=='CLIENT_SUCCESS':floors[row['opId']]=last_floor;installed[row['opId']]=last_install;selected[row['opId']]=last_selection
            if event=='NETWORK_DROP':
                request=physical.f.wire(physical.raw(row['request']),manifest)
                need(plan['case']==controller.CASES[1] and row['barrier'] in ('BEFORE_REQUEST_WRITE','AFTER_RESPONSE_READ') and
                     request['sender']==node and scenario['target'] in (request['sender'],request['recipient']),
                     'recovery undeclared network drop');drops.append(row)
        need(configs==[dict(plan['faultParameters'],enabled=True)],'recovery fault configuration observation')
    def floor_check(value,minimum):
        c=calls[value['opId']];floor=floors.get(c['opId'])
        need(floor is not None and floor['index']==value['queues']['recoveryFloorObserved']>=minimum,
             'recovery fabricated floor counter')
        own=rejoin.packet(floor['local'],manifest);peer=rejoin.packet(floor['remote'],manifest)
        need(own['seal']['node']==c['node'] and peer['seal']['node'] in generations.NODES-{c['node']} and
             own['snapshot']==peer['snapshot'] and len(own['snapshot']['anchors'])==floor['index'],'recovery floor source identity')
    for node,value in scenario['baselineFloors'].items():floor_check(value,context['initialIndex'])
    for node,value in scenario['baseline'].items():
        captured=events[value['opId'],'CLIENT_SUCCESS']['publication']
        need(captured==(value['publishedIndex'],4),'recovery baseline lacks physical publication')
    recovered=context['recovered'];value=recovered['response']
    need(events[value['opId'],'CLIENT_SUCCESS']['publication']==(value['publishedIndex'],5),'recovery restored status lacks physical publication')
    if plan['case']==controller.CASES[1]:
        for value in scenario['sourceFloors'].values():floor_check(value,context['laterIndex'])
        p=calls[scenario['selectedProbe']];selection=selected.get(p['opId'])
        need(selection is not None,'recovery missing selected pair')
        chosen=physical.frame(selection['selected'],'SELECTED',manifest)
        mask=sum(1<<(int(b['node'][-1])-1) for b in chosen['bases']);observed=p['response']['queues']
        need(mask==observed['selectedVotersObserved'] and chosen['ballot']['epoch']==observed['selectedEpochObserved'],
             'recovery fabricated selected pair')
        probe=scenario['installed']['probe'];install=installed.get(probe['opId'])
        need(install is not None and len(recovery.snapshot(physical.raw(install['snapshot']),manifest)['anchors'])==probe['queues']['snapshotInstalledIndexObserved'] and
             events[scenario['heldStatus']['opId'],'CLIENT_SUCCESS']['row']['order']<install['order']<events[scenario['oldMinimum'],'CLIENT_INVOKE']['row']['order'],
             'recovery missing/reordered physical snapshot install')
        need(drops,'recovery partition has no dropped frame')
        need(events[scenario['heldStatus']['opId'],'CLIENT_SUCCESS']['publication']==(scenario['heldStatus']['publishedIndex'],4),
             'recovery isolated target did not physically lag')
    else:
        successor=scenario['successor'];initial_epoch=scenario['initialStatus'][context['leader']]['epoch']
        observed=[r for r in campaigns if r['node']==successor and r['generation']==1]
        need(observed,'recovery successor lacks campaign observation')
        # Report controller observation bounds for detection. The JVM event is
        # independently correlated, but its clock is never subtracted from SIGKILL.
        campaign=observed[-1];statuses=[c for c in history if c['node']==successor and c['kind']=='status' and
            c['startNanos']>scenario['exitObservedNanos'] and events[c['opId'],'CLIENT_SUCCESS']['row']['order']>campaign['order'] and
            c['response']['epoch']>initial_epoch]
        need(statuses,'recovery campaign lacks controller observation')
        context['milestones']['campaignDetectedByNanos']=min(c['endNanos'] for c in statuses)-scenario['exitObservedNanos']
        quorum=next((r for r in traces[successor] if r['event']=='PROMISE_QUORUM' and r['order']>campaign['order']),None)
        need(quorum is not None,'recovery successor lacks selected quorum')
        context['campaignToQuorumNanos']=quorum['localNanos']-campaign['localNanos']
    return dict(status='PASS',case=plan['case'],reads=4,updates=4,initialIndex=context['initialIndex'],laterIndex=context['laterIndex'],
                droppedFrames=len(drops),controllerMilestonesNanos=context['milestones'],campaignToQuorumNanos=context.get('campaignToQuorumNanos'),
                clockSemantics='controller milestones from observed exit/heal; JVM campaign-to-quorum separate; no cross-origin subtraction')
