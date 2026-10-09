"""Portable replay of one complete owned canonical repetition, never a paid set."""
from pathlib import Path
import uuid
from . import cloud_authority as a, cloud_package as package, cloud_workload_contract as contract
from . import performance_model as m, remote_command as c, remote_collection as parts
from . import guest_owned_canonical as run, guest_evidence, guest_physical_evidence, guest_fault_evidence
from . import guest_three_mode_evidence, performance_semantics, performance_plan, storage_inspector


def admission(root):
    plan=c.read(root/'plan.json');req=plan['request'];sha=a.validate_request(req);member=run.validate_repetition(plan['repetition'])
    service=plan['services']
    m.need(plan['scope']==run.SCOPE and req['member']=='experiment' and service['scope']==run.SCOPE and
           service['status']=='PASS' and service['requestSha256']==sha and service['repetition']==member and
           [(v['mode'],v['cell']) for v in service['tapes']]==list(run.TAPES) and
           [v['case'] for v in service['faults']]==list(run.drill.CASES),'owned canonical complete service set')
    names={run.key(mode,cell) for mode,cell in run.TAPES}|set(run.drill.CASES)
    m.need({p.name for p in root.iterdir()} <= names|{'plan.json','validation.json','source'}|
           {cell+'-timeline.json' for cell in run.CELLS},'owned canonical extra input')
    previous=0;groups=set();directories=set();manifest=None;topology=None
    for cell in run.CELLS:
        row=c.read(root/(cell+'-timeline.json'));start,end=row['startNanos'],row['endNanos']
        ceiling=next(v['seconds'] for v in contract.load()['cells'] if v['name']==cell)
        m.need(row['cell']==cell and row['status']=='PASS' and type(start) is int and type(end) is int and
               previous<=start<end and end-start<=ceiling*10**9,'owned canonical cell order/budget');previous=end
        wanted=[(mode,kind) for mode,kind in run.TAPES if kind==cell]
        m.need([v['mode'] for v in row['tapes']]==[mode for mode,_ in wanted],'owned canonical mode coverage')
        last=start
        for span,(mode,kind) in zip(row['tapes'],wanted):
            m.need(span['status']=='PASS' and type(span['startNanos']) is int and type(span['endNanos']) is int and
                   last<=span['startNanos']<span['endNanos']<=end and
                   span['endNanos']-span['startNanos']<=(300 if cell=='healthy' else ceiling)*10**9,
                   'owned canonical mode order/budget');last=span['endNanos']
        for name in ([run.key(mode,kind) for mode,kind in wanted] or [cell]):
            local=c.read(root/name/'plan.json');configs=local['configs']
            m.need(local['request']==req and configs,'owned canonical mixed request')
            expected_mode=next((mode for mode,kind in wanted if run.key(mode,kind)==name),package.MODES[2])
            if wanted:
                m.need(local['mode']==expected_mode and local['scope']==run.rich.workload.scope(expected_mode,cell),
                       'owned canonical local tape scope')
            else:
                expected_scope='owned-network-faults' if cell in run.drill.network.CASES else run.drill.faults.SCOPE
                m.need(local['case']==cell and local['scope']==expected_scope,'owned canonical local fault scope')
            for cfg in configs:
                guest_evidence.guest.validate(cfg)
                current=(cfg['hosts'],cfg['ports'],str(Path(cfg['root']).parent))
                if topology is None:topology=current
                m.need(current==topology,'owned canonical changed physical topology')
                if wanted:
                    m.need(cfg.get('workload')==dict(cell=cell,preset='canonical',repetition=member),
                           'owned canonical mixed repetition/tape')
                    label=package.bootstrap_directory_name(cfg)
                else:
                    m.need(cfg.get('faultCell')==cell and 'workload' not in cfg,'owned canonical fault configuration');label=cell
                node=cfg['binding']['node']
                m.need(cfg['mode']==expected_mode and cfg['binding']==c.binding(req['source'],req['bundleSha256'],req['attempt'],node) and
                       cfg['groupId']==str(uuid.uuid5(uuid.NAMESPACE_URL,sha+':'+label)) and Path(cfg['root']).name==label,
                       'owned canonical group/package/root binding')
            m.need([cfg['binding']['node'] for cfg in configs]==['node-'+str(n) for n in package.service_nodes(configs[0])] and
                   len({cfg['groupId'] for cfg in configs})==len({cfg['root'] for cfg in configs})==1,
                   'owned canonical member/directory coverage')
            group,path=configs[0]['groupId'],configs[0]['root']
            m.need(group not in groups and path not in directories,'owned canonical reused group/directory')
            groups.add(group);directories.add(path)
            data=(root/name/'package-manifest.json').read_bytes()
            if manifest is None:manifest=data
            m.need(manifest==data and all(cfg['packageManifestSha256']==m.sha(data) for cfg in configs),
                   'owned canonical mixed package')
    m.need(len(groups)==17,'owned canonical seventeen fresh groups')
    return plan


def command_intervals(folder,cfg,controller,span):
    node=cfg['binding']['node'];owned=set();previous=span['startNanos'];starts=[];stops=[]
    for row in controller['transcript']:
        q=row['request'];identifier=q['commandId'];original=folder/'commands'/node[-1]/identifier
        m.need(identifier not in owned and c.read(original/'request.json')==dict(config=cfg,request=q) and
               c.read(original/'receipt.json')==row['receipt'],'owned canonical original command receipt')
        observation=c.read(original/'observation.json');start,end=observation['startNanos'],observation['endNanos']
        m.need(type(start) is int and type(end) is int and previous<=start<=end,'owned canonical command order')
        previous=end;owned.add(identifier)
        if q['command'] in ('start-voter','stop-voter','window','fault','backup'):
            m.need(span['startNanos']<=start<=end<=span['endNanos'],'owned canonical command outside tape')
        if q['command']=='start-voter':starts.append(start)
        if q['command']=='stop-voter':
            m.need(row['receipt']['state']=='SUCCEEDED' and row['receipt']['result']=={'stopped':True},'owned canonical voter handoff')
            stops.append(end)
    m.need(len(starts)==len(stops)==1 and starts[0]<=stops[0] and
           owned=={p.name for p in (folder/'commands'/node[-1]).iterdir()},'owned canonical lifecycle coverage')


def tape(root,output,plan,mode,cell,files,budgets,decoded):
    folder=root/run.key(mode,cell);local=c.read(folder/'plan.json');configs=local['configs']
    manifest=(folder/'package-manifest.json').read_bytes()
    service=next(v['receipt'] for v in plan['services']['tapes'] if (v['mode'],v['cell'])==(mode,cell));boot=service['bootstrap']
    m.need(service['status']=='PASS' and service['requestSha256']==a.validate_request(plan['request']) and
           boot['status']=='PASS' and boot['publicBootstrapVerified'] is True and
           boot['identity']['sourceSha256']==plan['services']['sourceSha256'],'owned canonical receiver seed binding')
    span=next(v for v in c.read(root/(cell+'-timeline.json'))['tapes'] if v['mode']==mode)
    execution=c.read(folder/'cell.json')
    m.need(execution['status']=='EXECUTED' and execution['mode']==mode and
           span['startNanos']<=execution['startedNanos']<=execution['endedNanos']<=span['endNanos'],
           'owned canonical original tape interval')
    members=[];logical=[];seen=set();issuers=[]
    for cfg in configs:
        node=cfg['binding']['node'];member=folder/node;controller=c.read(member/'controller.json')
        m.need(controller['config']==cfg,'owned canonical original client binding')
        command_intervals(folder,cfg,controller,span)
        if controller['active']:issuers.append(node)
        replay=output/(run.key(mode,cell)+'-'+node)
        info=parts.unpack(member/'parts',replay,m.sha(m.canonical(cfg['binding'])))
        for name in ('compressedBytes','expandedBytes','files'):budgets[name]+=info[name]
        index=c.read(replay/parts.INDEX)
        budgets['traceBytes']+=sum(v['bytes'] for n,v in index.items() if n.endswith(('.jsonl','.jsonl.gz','.log')))
        m.need(all(budgets[k]<=parts.LIMITS[k] for k in budgets),'owned canonical combined evidence budget')
        replicated=mode in package.MODES[1:]
        logical.append(guest_evidence.validate(replay,cfg,manifest,controller['packageRoot'],controller['transcript'],
            active=controller['active'],healthy=True,physical=replicated,backup=replicated and controller['active'],trace_budget=decoded))
        if replicated:
            stored=replay/'authority'/node;guest_three_mode_evidence.source_binding(stored,mode,files)
            m.need(all(m.sha((stored/(n+'.gsr')).read_bytes())==boot['identity'][n+'Sha256'] for n in ('manifest','genesis')),
                   'owned canonical admitted authority changed')
        members.append(dict(root=replay,controller=controller));seen.add(node)
    m.need({p.name for p in folder.glob('node-*')}==seen and len(issuers)==1 and
           (mode==package.MODES[2] or issuers==[package.control_node(configs[0])]),'owned canonical control placement')
    expected=sum(len(s['calls']) for s in guest_evidence.workload.specs(configs[0]))
    m.need(sum(v['calls'] for v in logical)==expected,'owned canonical frozen call count')
    physical=guest_physical_evidence.validate(members,manifest,backup=True,trace_budget=decoded) if mode in package.MODES[1:] else None
    return dict(mode=mode,cell=cell,calls=expected,issuer=issuers[0],members=logical,physical=physical)


def validate(root,output):
    root=c.directory(root);output=Path(output);output.mkdir(parents=True,mode=0o700,exist_ok=False)
    parts.inventory(root);plan=admission(root);req=plan['request']
    seed=performance_semantics.source_backup(root/'source',m.initial(performance_plan.load()))
    files={n:dict(bytes=v['size'],sha256=v['sha256']) for n,v in storage_inspector.inventory(root/'source').items()}
    source=m.sha(m.canonical({'source/'+n:v for n,v in files.items()}))
    m.need(plan['services']['sourceSha256']==source,'owned canonical shared seed identity')
    budgets=dict(files=0,expandedBytes=0,compressedBytes=0,traceBytes=0);decoded=[parts.LIMITS['traceBytes']];reports=[]
    for mode,cell in run.TAPES:reports.append(tape(root,output,plan,mode,cell,files,budgets,decoded))
    faults=[]
    for cell in run.drill.CASES:
        receipt=next(v['receipt'] for v in plan['services']['faults'] if v['case']==cell)
        m.need(receipt['status']=='PASS' and receipt['requestSha256']==a.validate_request(req),'owned canonical fault admission')
        span=c.read(root/(cell+'-timeline.json'));original=c.read(root/cell/'receipt.json')
        m.need(span['startNanos']<=original['startNanos']<=original['endNanos']<=span['endNanos'],
               'owned canonical fault outside cell')
        before=budgets['traceBytes']
        faults.append(guest_fault_evidence.replay_case(root/cell,output/cell,req,budgets))
        decoded[0]-=budgets['traceBytes']-before
        m.need(decoded[0]>=0,'owned canonical combined decoded trace budget')
    m.need(sum(v['calls'] for v in reports)==1080 and all(budgets[k]<=parts.LIMITS[k] for k in budgets),
           'owned canonical combined calls/evidence budget')
    return dict(status='PASS',scope=run.SCOPE,repetition=plan['repetition'],cells=list(run.CELLS),tapes=reports,faults=faults,
        calls=1080,sourceBackup=seed,sourceSha256=source,requestSha256=a.validate_request(req),budgets=budgets,
        decodedTraceBytes=parts.LIMITS['traceBytes']-decoded[0],paidCloud=False,fullRemoteQualification=False,ownedCanonicalQualified=True)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('input',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(m.canonical(validate(args.input,args.output)).decode())
