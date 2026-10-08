"""Independent original-command, retained-authority and real-cut drill checks."""
from . import performance_model as m, remote_command as c, remote_collection as parts
from . import remote_fault_evidence as reference, runtime_evidence as a
from .guest_fault_recovery import CUTS

NODES=('node-1','node-2','node-3')


def recipient_path(r, own, isolation, manifest):
    """A live, unchanged recipient must acknowledge the source while data is held."""
    heartbeat=r['recipientHeartbeat'];end=r['cut'] if r['case']=='interrupted-transfer' else r['rejection']
    target=r['targetNode'] if r['case']=='interrupted-transfer' else 'node-3'
    m.need(heartbeat in own and heartbeat['event']=='REPLY' and heartbeat['pid']==end['pid'] and
           isolation['appliedNanos']<heartbeat['localNanos']<isolation['healedNanos']<end['localNanos'],
           'owned recovery heartbeat outside data isolation')
    request=a.f.wire(a.raw(heartbeat['request']),manifest);reply=a.f.wire(a.raw(heartbeat['frame']),manifest)
    m.need(request['type']=='HEARTBEAT' and reply['type']=='HEARTBEAT_ACK' and
           request['sender']==reply['recipient']==r['seedLeader'] and request['recipient']==reply['sender']==target and
           request['traceId']==reply['traceId'] and request['epoch']==reply['epoch'] and
           request['incarnationId']==reply['incarnationId'] and
           request['payload']['activated'] is True and request['payload']['provenIndex']>=r['sourceFloor']['index'] and
           reply['payload']['provenIndex']<r['sourceFloor']['index'] and
           reply['payload']['sequence']==request['payload']['sequence'], 'owned recovery heartbeat does not bind live source')
    campaigns=[v for v in own if v['pid']==end['pid'] and v['event']=='CAMPAIGN_BEGIN']
    before=[v for v in campaigns if v['localNanos']<isolation['appliedNanos']]
    m.need(r['recipientCampaign']==(before[-1] if before else None) and
           not any(isolation['appliedNanos']<=v['localNanos']<=end['localNanos'] for v in campaigns),
           'owned recovery recipient campaigned before intended fault')


def check(r, history, traces, root, rows, obs, collections, processes):
    case=r['case'];old=r['seedLeader'];starts=[];stops=[];files={}
    for node,seq in rows.items():
        for q,receipt in seq:
            observation=obs[q['commandId']]
            if q['command']=='start-voter' or q['command']=='fault' and q['payload']=={'action':'restart'}:
                identity=receipt['result']['identity']
                starts.append(dict(node=node,pid=identity['pid'],generation=identity['generation'],
                    startNanos=observation['startNanos'],readyNanos=observation['endNanos']))
            if q['command']=='stop-voter':
                result=receipt['result'];kill=q['payload']['forced']
                stops.append(dict(node=node,pid=result['pid'],generation=result['generation'],kill=kill,
                    startNanos=observation['startNanos'],endNanos=observation['endNanos'],exitCode=result['exitCode']))
                if kill or q['payload'].get('retain'):
                    archive=collections[node]/'crash'/node;index=c.read(archive.parent/'inventory.json')
                    m.need(parts.inventory(archive)==index,'owned recovery archive inventory')
                    m.need(result['generation']==1 and any(qq['command']=='fault' and qq['payload']=={'action':'restart'} and
                           observation['endNanos']<=obs[qq['commandId']]['startNanos'] for qq,_ in seq),'owned recovery archive/restart binding')
                    for name in ('manifest.gsr','node.gsr','genesis.gsr','bootstrap-seal.gsr','bootstrap-prepared.gsr'):
                        m.need((archive/name).read_bytes()==(root/node/name).read_bytes(),'owned recovery retained identity changed')
                    files[node,1]={name:(archive/name).read_bytes() for name in index}
    m.need(len(starts)==len(stops)==len(processes),'owned recovery process coverage')
    restarts=[s for s in starts if s['generation']==2]
    expected=3 if case=='group-restart' else 2 if case=='minority-capacity' else 1
    m.need(len(restarts)==expected and len(files)==expected,'owned recovery retained restart count')
    if case=='group-restart':
        m.need(not any(s['kill'] for s in stops) and len(r['rejoins'])==3 and
               {v['node'] for v in r['rejoins']}==set(NODES),'owned group restart/rejoin coverage')
    elif case!='minority-capacity':
        target=r['targetNode'] if case=='interrupted-transfer' else old
        m.need(restarts[0]['node']==target and len(r['rejoins'])==1 and r['rejoins'][0]['node']==target and
               restarts[0]['readyNanos']<=r['rejoins'][0]['startNanos'],'owned recovery target/rejoin')
    else:m.need(not r['rejoins'],'bounded voter cannot claim complete rejoin')

    seed_rows=traces[old]
    callback=next(v for v in seed_rows if v['event']=='READ_CALLBACK' and v['opId']==r['seedRead']['opId'])
    captured=max((v for v in seed_rows if v['pid']==callback['pid'] and v['event']=='READ_CAPTURE_VALIDATED' and v['order']<callback['order']),key=lambda v:v['order'])
    m.need(r['seedThrough']>=captured['index'],'owned recovery seed floor below acknowledged read')
    seeds=r['seedRejoins']
    m.need(len(seeds)==3 and {v['node'] for v in seeds}==set(NODES),'owned recovery seed rejoin coverage')
    def join_original(join):
        found=[q for q,receipt in rows[join['node']] if q['command']=='fault' and q['payload']=={'action':'status'} and
               receipt['result']['response']==join['observed'] and
               join['startNanos']<=obs[q['commandId']]['startNanos']<=obs[q['commandId']]['endNanos']<=join['endNanos']]
        m.need(len(found)==1 and 0<=join['endNanos']-join['startNanos']<=60*10**9 and
               join['observed']['provenIndex']>=join['through'],'owned recovery original rejoin')
    for join in seeds:
        join_original(join)
        m.need(history[3]['endNanos']<=join['startNanos']<=join['endNanos']<=r['faultStartNanos'] and
               join['through']==r['seedThrough'],'owned recovery seed floor timing')
    if case in CUTS:
        cut=r['cut'];node=cut['node'];own=traces[node]
        arms=[(q,v) for q,v in rows[node] if q['command']=='fault' and q['payload']=={'action':'arm-cut'}]
        observed=[v['result']['cut'] for q,v in rows[node] if q['command']=='fault' and q['payload']=={'action':'observe-recovery'}]
        m.need(len(arms)==1 and arms[0][1]['result']==dict(cut=CUTS[case],identity=next(v['result']['identity'] for q,v in rows[node] if q['command']=='start-voter')) and
               c.read(collections[node]/'cut-claim.json')=={'action':'arm-cut'} and cut in own and cut in observed,
               'owned recovery original armed/observed cut')
        crash=next(s for s in stops if s['kill'])
        m.need(r['faultStartNanos']<=obs[arms[0][0]['commandId']]['startNanos']<=obs[arms[0][0]['commandId']]['endNanos']<=crash['startNanos'],
               'owned recovery cut controller order')
        if case!='interrupted-transfer':
            m.need(any(p['node']!=old and crash['endNanos']<=p['startNanos']<=p['endNanos']<=restarts[0]['startNanos'] and
                       all(p[k]['outcome']=='SUCCESS' for k in ('write','read')) for p in r['progress']), 'owned recovery surviving progress before restart')
    if case in ('interrupted-transfer','minority-capacity'):
        target=r['targetNode'] if case=='interrupted-transfer' else 'node-3'
        large=[h for h in history if h['kind']=='addAll' and h['documents']==reference.expected_documents(40,4096 if case=='interrupted-transfer' else 20000)]
        m.need(len(large)==1 and large[0]['outcome']=='SUCCESS','owned recovery large target missing')
        floor=r['sourceFloor']
        m.need(floor in traces[old] and floor['event']=='RECOVERY_FLOOR' and floor['index']>r['seedThrough'] and
               any(q['command']=='fault' and q['payload']=={'action':'observe-recovery'} and v['result']['floor']==floor
                   for q,v in rows[old]),'owned recovery original exportable floor')
        encoded=(root/'node-1/manifest.gsr').read_bytes();manifest=dict(a.f.inspect(encoded,'MANIFEST'),digest=encoded[16:48].hex())
        # Independent closed traffic policy. Heartbeats keep the intended
        # transfer/capacity recipient alive while mutation/recovery is withheld.
        types=('PREPARE','BASIS_CHUNK','SELECTED_OFFER','ACCEPT','COMMIT_PROOF','COMMIT_ADVANCE',
               'SNAPSHOT_OFFER','SNAPSHOT_CHUNK','REJOIN_INSTALL','SNAPSHOT_ABORT','SOURCE_OFFER','SOURCE_CHUNK')
        expected_rules=[f'{x} {y} BEFORE_REQUEST_WRITE {kind}' for x in NODES for y in NODES
                        if x!=y and target in (x,y) for kind in types]
        held_drops=[]
        for node,seq in rows.items():
            injected=[(q,v) for q,v in seq if q['command']=='fault' and q['payload']==dict(action='isolate',node=target)]
            healed=[(q,v) for q,v in seq if q['command']=='fault' and q['payload']==dict(action='heal')]
            m.need(len(injected)==len(healed)==1,'owned recovery isolation coverage')
            iq,ir=injected[0];hq,hr=healed[0];actual=c.read(collections[node]/'isolation.json')
            m.need(ir['result']==dict(node=target,rules=expected_rules,appliedNanos=actual['appliedNanos']) and
                   hr['result']==actual and actual['watchdog'] is False and actual['rules']==expected_rules and
                   0<actual['healedNanos']-actual['appliedNanos']<=60*10**9,'owned recovery guest isolation/watchdog')
            m.need(obs[iq['commandId']]['endNanos']<=large[0]['startNanos']<=large[0]['endNanos']<=obs[hq['commandId']]['startNanos'],
                   'owned recovery target outside isolation')
            drops=[v for v in traces[node] if v['event']=='NETWORK_DROP']
            held_drops.extend(v for v in drops if v['rule'] in expected_rules and actual['appliedNanos']<=v['localNanos']<=actual['healedNanos'])
            for drop in drops:
                frame=a.f.wire(a.raw(drop['request']),manifest)
                rule=f"{frame['sender']} {frame['recipient']} BEFORE_REQUEST_WRITE "
                # Capacity's initial PREPARE-only barrier is independently checked below.
                m.need(drop['rule'] in (expected_rules if case!='minority-capacity' else expected_rules+
                       [f'{x} {y} BEFORE_REQUEST_WRITE PREPARE' for x in NODES for y in NODES if x!=y and 'node-3' in (x,y)]) and
                       drop['node']==frame['sender'] and drop['barrier']=='BEFORE_REQUEST_WRITE' and
                       drop['rule'] in (rule+'*',rule+frame['type']),
                       'owned recovery actual isolation direction')
        m.need(held_drops,'owned recovery missing actual isolation observation')
        isolation=c.read(collections[target]/'isolation.json')
        recipient_path(r,traces[target],isolation,manifest)
        heal=next(q for q,_ in rows[target] if q['command']=='fault' and q['payload']=={'action':'heal'})
        m.need(any(q['command']=='fault' and q['payload']=={'action':'observe-recovery'} and
                   v['result']['heartbeat']==r['recipientHeartbeat'] and
                   obs[q['commandId']]['endNanos']<=obs[heal['commandId']]['startNanos'] for q,v in rows[target]),
               'owned recovery original heartbeat observation before heal')
        if case=='interrupted-transfer':
            selected=r['selected'];m.need(selected in traces[old] and selected['event']=='PROMISE_QUORUM','owned transfer original selected pair')
            pair={b['node'] for b in a.f.inspect(a.raw(selected['selected']),'SELECTED')['bases']}
            m.need(pair==set(NODES)-{target},'owned transfer must target nonselected voter')
            join_original(r['transferRejoin'])
            m.need(r['transferRejoin']['node']==target and r['transferRejoin']['through']>=floor['index'] and
                   restarts[0]['readyNanos']<=r['transferRejoin']['startNanos'] and
                   r['transferRejoin']['endNanos']<=r['progress'][0]['startNanos'],'owned partial transfer completion before progress')
        else:
            for node,seq in rows.items():
                began=[(q,v) for q,v in seq if q['command']=='fault' and q['payload']=={'action':'prepare-direction'}]
                healed=[(q,v) for q,v in seq if q['command']=='fault' and q['payload']=={'action':'heal-direction'}]
                m.need(len(began)==len(healed)==1,'owned bounded PREPARE coverage')
                actual=c.read(collections[node]/'prepare-isolation.json')
                expected=[f'{x} {y} BEFORE_REQUEST_WRITE PREPARE' for x in NODES for y in NODES if x!=y and 'node-3' in (x,y)]
                m.need(began[0][1]['result']==dict(appliedNanos=actual['appliedNanos'],rules=expected) and
                       healed[0][1]['result']==actual and actual['watchdog'] is False and
                       0<actual['healedNanos']-actual['appliedNanos']<=60*10**9 and
                       obs[began[0][0]['commandId']]['endNanos']<=min(v['startNanos'] for v in starts) and
                       max(v['readyNanos'] for v in starts if v['generation']==1)<=obs[healed[0][0]['commandId']]['startNanos']<=
                       obs[healed[0][0]['commandId']]['endNanos']<=history[0]['startNanos'],'owned bounded PREPARE original barrier')
    translated=dict(r,starts=starts,stops=stops)
    reference.fault_facts(root,translated,history,traces,files)
