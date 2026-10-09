"""Portable owned fault replay: original receipts, local clocks and physical bytes."""
from copy import deepcopy
from pathlib import Path
import uuid
from . import performance_model as m, remote_command as c, remote_collection as parts
from . import cloud_authority as a, cloud_package as package, cloud_guest as guest, guest_evidence
from . import guest_authority, storage_inspector as storage, format_inspector as f
from . import public_qualification_evidence as physical, public_history, remote_fault_evidence as faults
from . import cloud_workload_contract as contract, performance_plan as plan
from .guest_fault_service import CASES, QUICK_CASES, RULES
from .guest_network_evidence import CASES as NETWORK_CASES
from .guest_fault_recovery import CASES as RECOVERY_CASES


def package_binding(manifest, req):
    # Package inventory hashes file bytes, unlike the canonical plan contract.
    m.need(manifest['source']==req['source'] and manifest['workloadSha256']==m.sha(contract.PLAN.read_bytes()),'owned fault package source/plan')


def capacity_reply(row):
    if row['event']!='REPLY':return False
    frame=m.strict_json(faults.a.raw(row['frame'])[48:])
    return frame['type']=='REJECT' and frame['payload'].get('reason')=='CAPACITY_EXCEEDED'


def logical_bounds(history, traces, chosen):
    m.need(chosen<=512,'owned fault logical slot bound')
    noops=set()
    for rows in traces.values():
        for row in rows:
            if row['event']=='FORCE' and row['kind']=='ACCEPT':
                vote=f.inspect(faults.a.raw(row['record']),'ACCEPT');entry=f.inspect(faults.a.raw(vote['entry']),'ENTRY')
                if entry['operation']==9:noops.add(vote['entryDigest'])
    m.need(len(noops)-sum(h['kind'] in ('read','backup') for h in history)<=64 and sum(h['kind']=='backup' for h in history)<=8 and all(h['kind'] in ('read','addAll','checkpoint','backup') for h in history),
           'owned fault activation/auxiliary barrier ceiling')


class Location:
    def __init__(self, root, configs, indexes):self.root,self.configs,self.indexes=root,configs,indexes
    def inspect(self, directory, maximum_bytes=64<<20, maximum_frame=1<<20):
        node=Path(directory).name
        m.need(Path(directory)==self.root/node and node in self.configs,'owned fault inspection owner')
        expected={k:dict(size=v['bytes'],sha256=v['sha256']) for k,v in self.indexes[node].items()}
        m.need(storage.inventory(directory)==expected,'owned fault relocated authority changed')
        return storage._inspect(directory,maximum_bytes,maximum_frame,Path(self.configs[node]['root'])/node)


def resource_samples(own, killed, authority_limit=64<<20):
    samples=[r for r in own if r['event']=='PERFORMANCE_SAMPLE']
    m.need(samples and samples[0]['boundary']=='start' and (killed or samples[-1]['boundary']=='closed'),'owned fault sampling boundaries')
    m.need(sum(r['boundary']=='periodic' for r in samples)>=max(0,(samples[-1]['localNanos']-samples[0]['localNanos'])//10**9-1),'owned fault periodic samples')
    for row in samples:
        q=row['queues']
        m.need(0<row['heapUsedBytes']<=row['heapMaxBytes']<=512<<20 and row['VmRSSBytes']>0 and row['threads']>0 and
               0<=row['retainedBytes']<=128<<20 and 0<=row['localNanos']-row['samplingStartNanos']<=9600*10**6,'owned fault resource bounds')
        for key,bound in [('orderedQueue',4),('deadlinesQueue',4),('inputsQueue',32),('completionsQueue',16),('networkQueue',4),('appQueue',4),('clientsQueue',2),
                          ('queuedBytes',64<<20),('authorityDiskBytes',authority_limit),('transferDiskBytes',64<<20),('maintenancePending',1),('pinsBytes',64<<20),('stagingBytes',64<<20),('admissionAvailable',4),('inboundAvailable',8)]:
            m.need(type(q[key]) is int and 0<=q[key]<=bound,'owned fault queue/byte bound '+key)
        m.need(len(q['outboundAvailable'])==3 and {v['node'] for v in q['outboundAvailable']}==set(faults.NODES) and all(type(v['available']) is int and 0<=v['available']<=2 for v in q['outboundAvailable']),'owned fault outbound permits')
        m.need(all(type(row[k]) is int and row[k]>=0 for k in ('gcCount','gcMillis','cpuNanos')) and
               all(type(v) is int and v>=0 for v in row['processIo'].values()),'owned fault missing resource counters')
        if row['boundary']=='closed':m.need(q['queuedBytes']==0 and q['admissionAvailable']==4 and q['inboundAvailable']==8 and q['maintenancePending']==0 and all(v['available']==2 for v in q['outboundAvailable']),'owned fault undrained reservations')


def member(root, cfg, manifest, base, transcript, traces, *, timing_profile=None):
    rows,service=guest_evidence.commands(root,cfg,transcript,physical=True)
    m.need(all(r['state']=='SUCCEEDED' for _,r in rows),'owned fault failed original command')
    starts=[(q,r) for q,r in rows if q['command']=='start-voter' or q['command']=='fault' and q['payload']=={'action':'restart'}]
    stops=[(q,r) for q,r in rows if q['command']=='stop-voter']
    prepares=[(q,r) for q,r in rows if q['command']=='prepare-cell']
    m.need(len(prepares)==1 and prepares[0][0]['payload']=={} and prepares[0][1]['result']==c.read(root/'fault-prepared.json') and
           c.read(root/'fault-prepare-claim.json')==cfg,'owned fault bootstrap receipt')
    prepared=prepares[0][1]['result'];node=cfg['binding']['node']
    m.need(prepared['source']=='EMPTY' and prepared['node']==node and prepared['groupId']==cfg['groupId'],'owned fault bootstrap scope')
    for file in ('manifest','genesis'):
        m.need(m.sha((root/'authority'/node/(file+'.gsr')).read_bytes())==prepared[file+'Sha256'],'owned fault bootstrap bytes changed')
    m.need(len(starts)==len(stops) and len(starts) in (1,2),'owned fault lifecycle coverage')
    env=contract.load()['environment'];spec=manifest['modes'][package.MODES[2]];files={v['path']:v for v in manifest['files']}
    expected=dict(contract.load()['replicationBounds'],**{k:v for k,v in contract.load()['automaticPolicy'].items() if k!='applyTo'})
    expected.update({k:contract.load()['application'][k] for k in ('maxDocuments','maxBulkElements','maxEncodedKeyBytes','maxEncodedDocumentBytes','checkpointWalBytes','maxRetainedBytes','maxDerivedStateBytes')})
    cell=next(v for v in contract.load()['cells'] if v['name']==cfg['faultCell'])
    expected['maxEncodedDocumentBytes']=cell.get('maxEncodedDocumentBytes',4096)
    if cfg['faultCell']=='minority-capacity' and node=='node-3':expected['maxRetainedLogBytes']=128<<10
    processes={};exchanges={};previous=prepares[0][1]['endedNanos']
    for gen,((startq,start),(stopq,stop)) in enumerate(zip(starts,stops),1):
        identity=c.read(root/f'{node}-g{gen}-jvm.json');closed=c.read(root/f'{node}-g{gen}-stop.json');pid=identity['pid'];killed=stopq['payload'].get('forced')
        m.need(startq['payload']==({} if gen==1 else {'action':'restart'}) and start['result']==dict(status='STARTED',identity=identity) and
               stop['result']==closed==dict(identity,exitCode=-9 if killed else 0,forced=killed,readerReaped=True),'owned fault process/exit identity')
        m.need(type(pid) is int and pid>0 and identity['node']==node and identity['generation']==gen and
               identity['bootId']==service['bootId'] and identity['startTicks'].isdigit() and pid!=service['pid'],'owned fault OS process identity')
        m.need(previous<=start['startedNanos']<=start['endedNanos']<=stop['startedNanos']<=stop['endedNanos'],'owned fault local lifecycle order')
        previous=stop['endedNanos']
        cp=':'.join(str(base/n) for n in [*spec['jars'],spec['classes']])
        tail=[timing_profile] if timing_profile is not None else []
        m.need(identity['args']==[str(base/'runtime/bin/java'),*env['jvmArguments'],'-cp',cp,package.PACKAGE+'replication.V51PublicWorker',cfg['root'],node[-1],'remote-fault',str(gen),*tail],'owned fault JVM argv')
        own=[r for r in traces if r['pid']==pid]
        m.need(own and [r['order'] for r in own]==list(range(1,len(own)+1)) and all(r['generation']==gen for r in own),'owned fault trace continuity')
        settings=[r for r in own if r['event']=='FAULT_CONFIGURATION']
        m.need(len(settings)==1 and all(settings[0].get(k)==v for k,v in expected.items()),'owned fault sealed configuration')
        loaded=[r for r in own if r['event']=='PERFORMANCE_IDENTITY'];m.need(len(loaded)==1,'owned fault loaded identity')
        loaded=loaded[0]
        m.need(loaded['javaMajor']==21 and loaded['processors']==2 and loaded['javaVendor']==env['javaVendor'] and
               loaded['javaRuntime']==env['javaRuntime'] and loaded['jvmArguments']==env['jvmArguments'] and
               loaded['planFileSha256']==m.sha(plan.PLAN.read_bytes()) and loaded['cloudPlanSha256']==contract.PLAN_SHA256,'owned fault environment/plan identity')
        for key,path in zip(('core','replication'),spec['jars']):m.need(loaded[key+'Source']==str(base/path) and loaded[key+'Sha256']==files[path]['sha256'],'owned fault loaded JAR binding')
        resource_samples(own,killed,expected['maxRetainedLogBytes'])
        processes[node,pid]=gen
        original=c.read(root/f'{node}-g{gen}-exchanges.json')
        m.need(len(original)<=2000,'owned fault exchange count')
        for row in original:
            request=row['request'];response=row.get('response');opid=request['opId']
            if response is None and row['outcome']=='PENDING':
                m.need(killed and cfg['faultCell'] in ('entry-chosen','proof-quorum') and 'failure' not in row and
                       type(row.get('disconnectNanos')) is int and stop['startedNanos']<=row['disconnectNanos']<=stop['endedNanos'] and
                       opid not in exchanges,'owned fault unexplained disconnected exchange')
                invokes=[r for r in own if r['event']=='CLIENT_INVOKE' and r.get('opId')==opid]
                m.need(len(invokes)==1 and all(invokes[0].get(k)==v for k,v in request.items()) and
                       not any(r['event'] in ('CLIENT_SUCCESS','CLIENT_FAILURE') and r.get('opId')==opid for r in own),
                       'owned fault disconnected invocation/response')
                exchanges[opid]=row;continue
            m.need(opid not in exchanges and row['outcome']!='PENDING' and 'failure' not in row and response is not None and
                   row['outcome']==response['outcome'] and all(response.get(k)==v for k,v in request.items()),'owned fault incomplete/duplicate exchange')
            exchanges[opid]=row
            for event in ('CLIENT_INVOKE','CLIENT_SUCCESS' if row['outcome']=='SUCCESS' else 'CLIENT_FAILURE'):
                witnesses=[r for r in own if r['event']==event and r.get('opId')==opid]
                m.need(len(witnesses)==1 and all(witnesses[0].get(k)==v for k,v in (request if event=='CLIENT_INVOKE' else response).items()),'owned fault exchange trace binding')
        commands=[r for q,r in rows if q['command']=='fault' and q['payload'].get('action') in ('status','call','release-pin') and r['result']['identity']==identity]
        pending=[(q,r) for q,r in rows if q['command']=='fault' and q['payload'].get('action')=='start-target' and r['result']['identity']==identity]
        m.need(len(pending)<=1 and len(commands)+len(pending)==len(original) and
               {r['result']['response']['opId'] for r in commands}|{r['result']['request']['opId'] for q,r in pending}=={r['request']['opId'] for r in original},'owned fault original exchange coverage')
        for q,r in pending:
            request=r['result']['request'];row=exchanges[request['opId']]
            m.need(cfg['faultCell'] in ('entry-chosen','proof-quorum') and killed and row['request']==request and row['outcome']=='PENDING' and
                   request==dict(kind='addAll',opId=request['opId'],intentId=q['payload']['intentId'],documents=faults.expected_documents(40,512)) and
                   q['payload']==dict(action='start-target',intentId=request['intentId'])==c.read(root/'target-claim.json') and
                   start['endedNanos']<=r['startedNanos']<=row['startNanos']<=r['endedNanos']<=stop['startedNanos'],'owned fault target original submission')
        for r in commands:
            row=exchanges[r['result']['response']['opId']]
            m.need(r['result']['response']==row['response'] and start['endedNanos']<=r['startedNanos']<=r['endedNanos']<=stop['startedNanos'],'owned fault response/lifetime')
    m.need(set((node,r['pid']) for r in traces)==set(processes),'owned fault undeclared process')
    return rows,processes,exchanges


def replay_case(raw, scratch, req, budgets, *, authority=a):
    from . import native_experiment_timing as timing
    authority.validate_request(req)
    record=c.read(raw/'receipt.json');history=c.read(raw/'history.json');case=record['case'];source=c.read(raw/'plan.json')
    scope='owned-network-faults' if case in NETWORK_CASES else 'owned-experiment-leader-loss-no-quorum'
    m.need(case in (*CASES,*NETWORK_CASES,*RECOVERY_CASES) and source['request']==req and source['case']==case and source['scope']==scope and
           record['status']=='EXECUTED' and record['seconds']==timing.cell(req,case) and not record['cleanupErrors'] and
           0<record['endNanos']-record['startNanos']<=record['seconds']*10**9,'owned fault case completion/budget')
    m.need(len(source['configs'])==3 and [v['binding']['node'] for v in source['configs']]==list(faults.NODES),'owned fault members')
    manifest_raw=(raw/'package-manifest.json').read_bytes();manifest=m.strict_json(manifest_raw)
    package_binding(manifest,req)
    joint=scratch/'joint';joint.mkdir(parents=True);traces={};configs={};indexes={};processes={};rows={};observations={};collections={};allcalls={};bases={}
    group=str(uuid.uuid5(uuid.NAMESPACE_URL,authority.validate_request(req)+':'+case))
    for cfg in source['configs']:
        guest.validate(cfg);node=cfg['binding']['node'];configs[node]=cfg
        m.need(cfg['binding']==c.binding(req['source'],req['bundleSha256'],req['attempt'],node) and cfg['packageManifestSha256']==m.sha(manifest_raw) and
               cfg['faultCell']==case and cfg['groupId']==group,'owned fault request/package/group binding')
        folder=raw/node;ctl=c.read(folder/'controller.json');m.need(ctl['config']==cfg,'owned fault controller config')
        replay=scratch/node;info=parts.unpack(folder/'parts',replay,m.sha(m.canonical(cfg['binding'])))
        for key in ('compressedBytes','expandedBytes','files'):budgets[key]+=info[key]
        index=c.read(replay/parts.INDEX);guest_evidence.retained(replay,c.read(folder/'parts/parts.json'),cfg['binding'])
        budgets['traceBytes']+=sum(v['bytes'] for n,v in index.items() if n.endswith(('.jsonl','.jsonl.gz','.log')))
        m.need(all(budgets[k]<=parts.LIMITS[k] for k in budgets),'owned fault combined evidence budget')
        m.need(c.read(replay/'plan.json')==plan.load() and c.read(replay/'cloud-plan.json')==contract.load() and
               (replay/'cell.txt').read_text()==case+'\n','owned fault retained plan/cell')
        collections[node]=replay
        guest_authority.capture(replay/'authority',node,joint/node)
        indexes[node]={k[len('authority/'+node+'/'):]:v for k,v in index.items() if k.startswith('authority/'+node+'/')}
        from . import public_trace
        traces[node]=public_trace.fault_rows(replay,node)
        bases[node]=Path(ctl['packageRoot'])
        rows[node],pids,exchanges=member(replay,cfg,manifest,Path(ctl['packageRoot']),ctl['transcript'],traces[node],
            timing_profile=timing.PROFILE if timing.selected(req) else None);processes.update(pids)
        previous=0
        for q,r in rows[node]:
            path=raw/'commands'/node[-1]/q['commandId']
            m.need(c.read(path/'request.json')==dict(config=cfg,request=q) and c.read(path/'receipt.json')==r,'owned fault original controller receipt')
            obs=c.read(path/'observation.json');m.need(previous<=obs['startNanos']<=obs['endNanos'],'owned fault controller interval');previous=obs['endNanos']
            observations[q['commandId']]=obs
            if q['command'] not in ('prepare-cell','collect'):
                m.need(record['startNanos']<=obs['startNanos']<=obs['endNanos']<=record['endNanos'],'owned fault command outside cell')
            if q['command']=='fault' and q['payload'].get('action')=='start-target':
                opid=r['result']['request']['opId'];m.need(opid not in allcalls,'owned duplicate target ID');allcalls[opid]=(q,r,obs)
            elif q['command']=='fault' and q['payload'].get('action') in ('call','release-pin'):
                response=r['result']['response'];opid=response['opId'];m.need(opid not in allcalls,'owned fault duplicate public ID')
                if q['payload']['action']=='release-pin':
                    pinq,pinr=next((qq,rr) for qq,rr in rows[node] if qq['command']=='fault' and qq['payload'].get('action')=='pin')
                    m.need(pinr['result']['opId']==opid and pinr['result']['identity']==r['result']['identity'],'owned pin original identity')
                    obs=dict(startNanos=observations[pinq['commandId']]['startNanos'],endNanos=obs['endNanos'])
                    allcalls[opid]=(pinq,r,obs)
                else:allcalls[opid]=(q,r,obs)
        m.need({p.name for p in (raw/'commands'/node[-1]).iterdir()}=={q['commandId'] for q,_ in rows[node]},'owned fault controller command coverage')
    m.need(len({(cfg['groupId'],tuple(cfg['hosts']),tuple(cfg['ports'])) for cfg in configs.values()})==1,'owned fault topology disagreement')
    m.need(len({(m.sha((joint/n/'manifest.gsr').read_bytes()),m.sha((joint/n/'genesis.gsr').read_bytes())) for n in configs})==1,'owned fault genesis disagreement')
    genesis=f.inspect((joint/'node-1/genesis.gsr').read_bytes(),'GENESIS')
    m.need(genesis['source']=='EMPTY' and genesis['baseSequence']==0 and faults.a.application(faults.a.raw(genesis['application']))==([dict(analyzer='',field='value',kind='equality')],{}),'owned fault nonempty genesis')
    decoded=f.inspect((joint/'node-1/manifest.gsr').read_bytes(),'MANIFEST')
    cfg=configs['node-1'];m.need(decoded['groupId']==group and decoded['members']==[dict(node=f'node-{i+1}',host=host,port=port) for i,(host,port) in enumerate(zip(cfg['hosts'],cfg['ports']))],'owned fault physical endpoints')
    first_starts=[observations[q['commandId']] for seq in rows.values() for q,r in seq if q['command']=='start-voter']
    final_stops=[observations[[q for q,r in seq if q['command']=='stop-voter'][-1]['commandId']] for seq in rows.values()]
    m.need(len(first_starts)==len(final_stops)==3 and max(v['endNanos'] for v in first_starts)<=history[0]['startNanos'] and
           history[-1]['endNanos']<=min(v['startNanos'] for v in final_stops),'owned fault concurrent voter lifetime')
    m.need(len(allcalls)==len(history) and set(allcalls)=={h['opId'] for h in history},'owned fault complete public history')
    for h in history:
        q,r,obs=allcalls[h['opId']];identity=r['result']['identity']
        if q['payload']['action']=='start-target':
            stopq,stop=next((q,r) for q,r in rows[h['node']] if q['command']=='stop-voter' and r['result']['pid']==identity['pid'])
            stopped=observations[stopq['commandId']]
            m.need(h['outcome']=='PENDING' and h['endNanos'] is None and 'response' not in h and
                   h['node']==identity['node'] and h['pid']==identity['pid'] and h['generation']==identity['generation'] and
                   r['result']['request']==dict(kind=h['kind'],opId=h['opId'],intentId=h['intentId'],documents=h['documents']) and
                   h['startNanos']<=obs['startNanos']<=obs['endNanos']<=stopped['startNanos']<=stopped['endNanos']<=h['disconnectNanos'],
                   'owned fault disconnected history binding')
            continue
        response=r['result']['response']
        m.need(h['response']==response and h['outcome']==response['outcome'] and h['node']==identity['node'] and
               h['pid']==identity['pid'] and h['generation']==identity['generation'] and h['intentId']==q['payload']['intentId'] and
               h['kind']==q['payload'].get('kind','read') and h['startNanos']<=obs['startNanos']<=obs['endNanos']<=h['endNanos'],'owned fault public response binding')
        if 'documents' in response:m.need(h['documents']==response['documents'],'owned fault history documents changed')
    location=Location(joint,configs,indexes)
    def maintenance(rr,hh,tt,rrows):
        from . import guest_maintenance_evidence as maintenance
        return maintenance.check(rr,hh,tt,rrows,observations,collections,configs,bases,manifest,request=req)
    result=check_case(record,history,traces,joint,location,processes,rows,observations,collections,maintenance,request=req)
    if case=='maintenance':
        from .guest_maintenance_evidence import replay
        evidence=maintenance(record,history,traces,rows)
        result['backupRestore']=replay(**evidence,output=scratch/'backup-replay')
    negatives=[]
    variants=('missing-kill-or-isolation','wrong-refusal-or-rejoin','late-progress','stale-read','missing-proof','missing-invocation')
    if case=='maintenance':variants+=('missing-pin-install','missing-release','missing-unpin','changed-pinned-view')
    if case in NETWORK_CASES:
        variants+=('missing-network-observation','wrong-network-direction','early-release','outside-network-hold')
        if case.startswith('asymmetric-'):variants+=('missing-reverse','outside-reverse-hold')
        if case=='isolated-old-leader':variants+=('missing-fence',)
    if case in RECOVERY_CASES:
        variants+=('missing-seed-rejoin','missing-retained-restart')
        if case in ('entry-chosen','proof-quorum','interrupted-transfer'):variants+=('missing-durable-cut',)
        if case in ('entry-chosen','proof-quorum'):variants+=('fabricated-target-response','missing-target-quorum')
        if case in ('interrupted-transfer','minority-capacity'):variants+=('missing-isolation-observation','missing-recipient-heartbeat','recipient-campaigned')
        if case=='interrupted-transfer':variants+=('missing-transfer-chunks','wrong-transfer-recipient')
        if case=='minority-capacity':variants+=('missing-capacity-reply','changed-capacity-accounting','missing-prepare-barrier')
    for name in variants:
        rr,hh,tt=deepcopy(record),deepcopy(history),deepcopy(traces)
        rrows=deepcopy(rows)
        if name=='missing-kill-or-isolation':
            for node in rrows:
                for q,r in rrows[node]:
                    if q['command']=='stop-voter' and q['payload'].get('forced'):q['payload']['forced']=False
                    if q['command']=='stop-voter' and q['payload'].get('retain'):q['payload']['retain']=False
                    if q['command']=='fault' and q['payload'].get('action')=='isolate':q['payload']['action']='status'
        elif name=='wrong-refusal-or-rejoin':
            if case in ('leader-loss','maintenance',*NETWORK_CASES,*RECOVERY_CASES) and case!='minority-capacity':rr['rejoins']=[]
            else:rr['refusals']=[]
        elif name=='late-progress':rr['progress'][0]['endNanos']=rr['faultStartNanos']+(timing.control(req,'progress',60)+1)*10**9
        elif name=='stale-read':hh[-1]['documents']=[]
        elif name=='missing-proof':tt={n:[v for v in seq if not(v['event']=='FORCE' and v['kind']=='PROOF')] for n,seq in tt.items()}
        elif name=='missing-pin-install':tt={n:[v for v in seq if v['event']!='REJOIN_INSTALLED'] for n,seq in tt.items()}
        elif name=='missing-release':tt={n:[v for v in seq if v['event']!='CUT_RELEASED'] for n,seq in tt.items()}
        elif name=='missing-unpin':tt={n:[v for v in seq if not(v['event']=='PERFORMANCE_SAMPLE' and v['queues']['pinsBytes']==0)] for n,seq in tt.items()}
        elif name=='changed-pinned-view':rr['pinnedRead']['documents']=[]
        elif name=='missing-network-observation':tt={n:[v for v in seq if v['event'] not in ('NETWORK_DROP','SLOW_FORCE_BEGIN')] for n,seq in tt.items()}
        elif name=='wrong-network-direction':
            for seq in tt.values():
                for v in seq:
                    if v['event']=='NETWORK_DROP':v['barrier']='WRONG_DIRECTION'
                    if v['event']=='SLOW_FORCE_BEGIN':v['delayMillis']=1
        elif name=='early-release':
            ready=next(v['controllerNanos'] for v in rr['events'] if v['event']=='network-ready')
            next(v for v in rr['events'] if v['event']=='network-heal-request')['controllerNanos']=ready+10**9
        elif name=='missing-reverse':tt[rr['seedLeader']]=[v for v in tt[rr['seedLeader']] if v['event']!='REPLY']
        elif name=='outside-network-hold':
            for seq in tt.values():
                for v in seq:
                    if v['event'] in ('NETWORK_DROP','SLOW_FORCE_BEGIN','SLOW_FORCE_END'):v['localNanos']=0
        elif name=='outside-reverse-hold':
            for v in tt[rr['seedLeader']]:
                if v['event']=='REPLY':v['localNanos']=0
        elif name=='missing-fence':tt[rr['seedLeader']]=[v for v in tt[rr['seedLeader']] if not(v['event']=='FORCE' and v['kind']=='PROMISE')]
        elif name=='missing-seed-rejoin':rr['seedRejoins']=[]
        elif name=='missing-retained-restart':
            for node in rrows:rrows[node]=[(q,r) for q,r in rrows[node] if not(q['command']=='fault' and q['payload']=={'action':'restart'})]
        elif name=='missing-durable-cut':tt={n:[v for v in seq if v['event']!='CUT_REACHED'] for n,seq in tt.items()}
        elif name=='fabricated-target-response':next(v for v in hh if v['outcome']=='PENDING')['outcome']='SUCCESS'
        elif name=='missing-target-quorum':
            tt={n:[v for v in seq if not(n!=rr['seedLeader'] and v['event']=='FORCE' and v['kind']=='ACCEPT')] for n,seq in tt.items()}
        elif name=='missing-isolation-observation':tt={n:[v for v in seq if v['event']!='NETWORK_DROP'] for n,seq in tt.items()}
        elif name=='missing-transfer-chunks':tt={n:[v for v in seq if v['event']!='WIRE_BEFORE_REQUEST_WRITE_SNAPSHOT_CHUNK'] for n,seq in tt.items()}
        elif name=='wrong-transfer-recipient':rr['targetNode']=rr['seedLeader']
        elif name=='missing-recipient-heartbeat':
            node=rr.get('targetNode','node-3');tt[node]=[v for v in tt[node] if v!=rr['recipientHeartbeat']]
        elif name=='recipient-campaigned':
            row=dict(rr['recipientHeartbeat'],event='CAMPAIGN_BEGIN');tt[rr.get('targetNode','node-3')].append(row)
        elif name=='missing-capacity-reply':tt['node-3']=[v for v in tt['node-3'] if not capacity_reply(v)]
        elif name=='changed-capacity-accounting':rr['rejection']['requested']=0
        elif name=='missing-prepare-barrier':
            for node in rrows:rrows[node]=[(q,r) for q,r in rrows[node] if not(q['command']=='fault' and q['payload']=={'action':'prepare-direction'})]
        else:tt={n:[v for v in seq if not(v['event']=='CLIENT_INVOKE' and v.get('opId')==hh[-1]['opId'])] for n,seq in tt.items()}
        try:check_case(rr,hh,tt,joint,location,processes,rrows,observations,collections,maintenance,request=req)
        except ValueError as error:negatives.append(dict(case=name,status='REJECTED',reason=str(error)))
        else:raise ValueError('owned fault negative admitted: '+name)
    return dict(case=case,status='PASS',calls=len(history),result=result,negatives=negatives)


def check_case(record, history, traces, root, location, processes, rows, obs, collections, maintenance=None,*,request=None):
    from . import native_experiment_timing as timing
    request=request or {}
    faults.schedule(history,record,progress_seconds=timing.control(request,'progress',60))
    requests=[v for v in record['events'] if v['event']=='fault-request']
    m.need(len(requests)==1 and requests[0]['node']==record['seedLeader'] and requests[0]['controllerNanos']==record['faultStartNanos'] and
           history[3]['endNanos']<=record['faultStartNanos'],'owned fault seed/fault timing')
    seed=history[3];own=traces[seed['node']]
    callback=next(v for v in own if v['event']=='READ_CALLBACK' and v['opId']==seed['opId'])
    capture=max((v for v in own if v['pid']==callback['pid'] and v['event']=='READ_CAPTURE_VALIDATED' and v['order']<callback['order']),key=lambda v:v['order'])
    leader=record['seedLeader'];case=record['case'];kills=[(n,q,r) for n,seq in rows.items() for q,r in seq if q['command']=='stop-voter' and q['payload']=={'forced':True}]
    if case=='leader-loss':
        m.need(len(kills)==1 and kills[0][0]==leader and len(processes)==4,'owned fault wrong killed voter')
        _,q,r=kills[0];exitobs=obs[q['commandId']]
        m.need(r['result']['pid']==seed['pid'] and r['result']['exitCode']==-9 and record['faultStartNanos']<=exitobs['startNanos'],'owned fault seed leader SIGKILL')
        restarts=[(q,r) for q,r in rows[leader] if q['command']=='fault' and q['payload']=={'action':'restart'}]
        m.need(len(restarts)==1,'owned fault retained restart missing')
        restart=obs[restarts[0][0]['commandId']]
        m.need(any(p['node']!=leader and exitobs['endNanos']<=p['startNanos']<=p['endNanos']<=restart['startNanos'] and
                   all(p[k]['outcome']=='SUCCESS' for k in ('write','read')) for p in record['progress']),'owned fault no surviving-majority progress before restart')
        crash=collections[leader]/'crash'/leader;index=c.read(crash.parent/'inventory.json')
        m.need(parts.inventory(crash)==index,'owned fault crash archive inventory')
        for name in ('manifest.gsr','node.gsr','genesis.gsr','bootstrap-seal.gsr','bootstrap-prepared.gsr'):
            m.need((crash/name).read_bytes()==(root/leader/name).read_bytes(),'owned fault restart changed authority identity')
        m.need(len(record['rejoins'])==1 and record['rejoins'][0]['node']==leader and restart['endNanos']<=record['rejoins'][0]['startNanos'],'owned fault missing retained rejoin')
    elif case in RECOVERY_CASES:
        from .guest_recovery_evidence import check
        check(record,history,traces,root,rows,obs,collections,processes)
    elif case=='maintenance':
        m.need(not kills and len(processes)==3,'owned maintenance unexpected crash')
        maintenance(record,history,traces,rows)
    elif case in NETWORK_CASES:
        from .guest_network_evidence import check
        m.need(not kills and len(processes)==3,'owned network unexpected crash')
        check(record,history,traces,root,rows,obs,collections,capture)
    else:
        m.need(not kills and len(processes)==3,'owned fault unexpected crash')
        ready=[v for v in record['events'] if v['event']=='isolated-all'];heal=[v for v in record['events'] if v['event']=='heal-request']
        m.need(len(ready)==len(heal)==1 and 15*10**9<=heal[0]['controllerNanos']-ready[0]['controllerNanos']<=timing.control(request,'hold-controller',17)*10**9,'owned fault all-node hold interval')
        for node,seq in rows.items():
            isolated=[(q,r) for q,r in seq if q['command']=='fault' and q['payload']=={'action':'isolate'}]
            healed=[(q,r) for q,r in seq if q['command']=='fault' and q['payload']=={'action':'heal'}]
            m.need(len(isolated)==len(healed)==1,'owned fault isolation/heal coverage')
            iq,ir=isolated[0];hq,hr=healed[0];actual=c.read(collections[node]/'isolation.json')
            m.need(ir['result']=={k:actual[k] for k in ('appliedNanos','rules')} and hr['result']==actual and
                   actual['rules']==RULES and actual['watchdog'] is False and 15*10**9<=actual['healedNanos']-actual['appliedNanos']<=timing.control(request,'isolation',17)*10**9,
                   'owned fault guest hold/watchdog')
            m.need(obs[iq['commandId']]['endNanos']<=ready[0]['controllerNanos']<=heal[0]['controllerNanos']<=obs[hq['commandId']]['startNanos'],'owned fault isolation controller barrier')
            drops=[v for v in traces[node] if v['event']=='NETWORK_DROP']
            m.need(drops and all(v['rule'] in RULES for v in drops) and any(actual['appliedNanos']<=v['localNanos']<=actual['healedNanos'] for v in drops),'owned fault actual network drops')
        m.need(len(record['refusals'])==2 and [r['kind'] for r in record['refusals']]==['addAll','read'],'owned fault conservative refusal pair')
        for r in record['refusals']:
            h=next(v for v in history if v['opId']==r['opId'])
            m.need(h['node']==leader and ready[0]['controllerNanos']<=h['startNanos']<=h['endNanos']<=heal[0]['controllerNanos'] and h['outcome']!='SUCCESS','owned fault refusal outside isolation')
        healed_at=max(obs[q['commandId']]['endNanos'] for seq in rows.values() for q,r in seq if q['command']=='fault' and q['payload']=={'action':'heal'})
        m.need(all(p['startNanos']>=healed_at for p in record['progress']),'owned fault progress before heal')
        m.need({v['node'] for v in record['rejoins']}==set(faults.NODES),'owned fault rejoin coverage')
    progress=next(p for p in record['progress'] if all(p[k]['outcome']=='SUCCESS' for k in ('write','read')))
    read=progress['read'];progress_rows=traces[progress['node']]
    callback=next(v for v in progress_rows if v['event']=='READ_CALLBACK' and v['opId']==read['opId'])
    cut=max((v for v in progress_rows if v['pid']==callback['pid'] and v['event']=='READ_CAPTURE_VALIDATED' and v['order']<callback['order']),key=lambda v:v['order'])
    for join in record['rejoins']:
        observed=[(q,r) for q,r in rows[join['node']] if q['command']=='fault' and q['payload']=={'action':'status'} and r['result']['response']==join['observed']]
        m.need(join['through']>=cut['index'] and len(observed)==1 and
               join['startNanos']<=obs[observed[0][0]['commandId']]['startNanos']<=obs[observed[0][0]['commandId']]['endNanos']<=join['endNanos'],'owned fault original rejoin observation')
        m.need(0<=join['endNanos']-join['startNanos']<=timing.control(request,'rejoin',60)*10**9 and join['observed']['provenIndex']>=join['through'] and
               location.inspect(root/join['node'])['provenThrough']>=join['through'],'owned fault durable rejoin')
    m.need(all(join['endNanos']<=history[-1]['startNanos'] for join in record['rejoins']),'owned fault final read before rejoin')
    logical=[h for h in history if h['kind'] in ('read','addAll')]
    proof=physical.physical(root,logical,traces,process_generations=processes,evidence_location=location,require_restart=case in ('leader-loss',*RECOVERY_CASES))
    logical_bounds(history,traces,proof['chosen'])
    return dict(history=public_history.check(logical),physical=proof,seedEpoch=capture['epoch'])


def validate(raw, scratch, *, cases=QUICK_CASES, scope='owned-experiment-leader-loss-no-quorum'):
    from .guest_owned_drill import CASES as DRILL_CASES, SCOPE as DRILL_SCOPE
    raw=Path(raw);scratch=Path(scratch);scratch.mkdir(parents=True,exist_ok=False)
    request=c.read(raw/'plan.json');req=request['request'];a.validate_request(req)
    m.need((tuple(cases),scope) in ((QUICK_CASES,'owned-experiment-leader-loss-no-quorum'),(('maintenance',),'owned-maintenance-experiment'),
           (NETWORK_CASES,'owned-network-faults'),(DRILL_CASES,DRILL_SCOPE)) and request['scope']==scope and req['member']=='experiment','owned fault aggregate scope')
    parts.inventory(raw);results=[];last=None;budgets={k:0 for k in ('compressedBytes','expandedBytes','files','traceBytes')}
    for case in cases:
        cell=raw/case
        if last is not None:m.need(last<=c.read(cell/'receipt.json')['startNanos'],'owned fault overlapping cells')
        results.append(replay_case(cell,scratch/case,req,budgets));last=c.read(cell/'receipt.json')['endNanos']
    return dict(status='PASS',cells=results,budgets=budgets,paidCloud=False,fullRemoteQualification=False,physicalHistoryQualified=True)
