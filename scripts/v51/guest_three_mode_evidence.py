"""Portable replay of all owned healthy modes and their controller handoff order."""
from pathlib import Path
import uuid
from scripts.v50 import admission_format as old
from . import cloud_authority as a, cloud_package as package, performance_model as m
from . import remote_command as c, remote_collection as parts, guest_evidence, guest_physical_evidence
from . import performance_semantics, performance_plan, storage_inspector as storage, format_inspector as fmt
from .guest_owned_three_mode import SCOPE


def timeline(value):
    m.need(value['status']=='PASS' and [v['mode'] for v in value['modes']]==list(package.MODES),'three-mode complete ordered timeline')
    times=[value['startNanos'],value['endNanos'],*(v[k] for v in value['modes'] for k in ('startNanos','endNanos'))]
    m.need(all(type(v) is int and v>=0 for v in times),'three-mode timeline timestamp')
    previous=value['startNanos']
    for row in value['modes']:
        m.need(row['status']=='PASS' and previous<=row['startNanos']<=row['endNanos']<=value['endNanos'] and
               row['endNanos']-row['startNanos']<=300*10**9,'three-mode overlap/mode budget')
        previous=row['endNanos']
    m.need(0<=value['endNanos']-value['startNanos']<=900*10**9,'three-mode healthy budget')


def source_binding(root, mode, files):
    raw=(root/'genesis.gsr').read_bytes()
    if mode==package.MODES[2]:
        source=[dict(path=n,kind=1,size=v['bytes'],sha256=v['sha256']) for n,v in sorted(files.items())]
        genesis=fmt.inspect(raw,'GENESIS')
        m.need(genesis['source']=='VERIFIED_V44_BACKUP' and genesis['sourceDigest']==m.sha(m.canonical(source)), 'three-mode automatic source bytes')
    else:
        reader=old.Reader(old.genesis(raw)['source']);source=old.source(reader);reader.end()
        m.need(source[0]==1 and source[3]==[(n,1,v['bytes'],bytes.fromhex(v['sha256'])) for n,v in sorted(files.items())],
               'three-mode configured source bytes')


def validate(root, output, *, authority=a):
    root=c.directory(root);output=Path(output);output.mkdir(mode=0o700)
    parts.inventory(root)  # Bound raw controller inputs, not just extracted guests.
    plan=c.read(root/'plan.json');req=plan['request'];sha=authority.validate_request(req)
    m.need(plan['scope']==SCOPE and req['member']=='experiment','three-mode replay scope')
    services=plan['services']
    m.need(services['status']=='PASS' and services['requestSha256']==sha and
           [v['mode'] for v in services['modes']]==list(package.MODES),'three-mode admitted mode set')
    m.need({p.name for p in root.iterdir()} <= {'plan.json','source','timeline.json','validation.json',*package.MODES},'three-mode extra root input')
    timing=c.read(root/'timeline.json');timeline(timing)
    seed=performance_semantics.source_backup(root/'source',m.initial(performance_plan.load()))
    files={n:dict(bytes=v['size'],sha256=v['sha256']) for n,v in storage.inventory(root/'source').items()}
    source_sha=m.sha(m.canonical({'source/'+n:v for n,v in files.items()}))
    m.need(services['sourceSha256']==source_sha,'three-mode shared source identity')
    reports=[];manifest_bytes=None;groups=set();roots=set();budgets=dict(files=0,expandedBytes=0,compressedBytes=0,traceBytes=0)
    for mode,span,service in zip(package.MODES,timing['modes'],services['modes']):
        folder=root/mode;local=c.read(folder/'plan.json');configs=local['configs']
        m.need(local['request']==req and local['mode']==mode and [v['binding']['node'] for v in configs]==
               ['node-'+str(n) for n in package.experiment_nodes(mode)],'three-mode request/member set')
        manifest=(folder/'package-manifest.json').read_bytes()
        if manifest_bytes is None:manifest_bytes=manifest
        m.need(manifest_bytes==manifest,'three-mode package build changed')
        group=configs[0]['groupId'];path=configs[0]['root']
        m.need(group==str(uuid.uuid5(uuid.NAMESPACE_URL,sha+':'+mode)) and group not in groups and path not in roots,
               'three-mode reused group/directory');groups.add(group);roots.add(path)
        boot=service['receipt']['bootstrap']
        m.need(service['receipt']['status']=='PASS' and service['receipt']['requestSha256']==sha and boot['status']=='PASS' and
               boot['publicBootstrapVerified'] is True and boot['identity']['sourceSha256']==source_sha,'three-mode receiver source binding')
        cell=c.read(folder/'cell.json')
        m.need(cell['status']=='EXECUTED' and cell['mode']==mode and span['startNanos']<=cell['startedNanos']<=cell['endedNanos']<=span['endNanos'],
               'three-mode cell interval')
        members=[];logical=[];seen=set()
        for cfg in configs:
            node=cfg['binding']['node'];number=node.removeprefix('node-');member=folder/node
            controller=c.read(member/'controller.json')
            m.need(controller['config']==cfg and cfg['mode']==mode and cfg['packageManifestSha256']==m.sha(manifest) and
                   cfg['binding']==c.binding(req['source'],req['bundleSha256'],req['attempt'],node), 'three-mode original client binding')
            owned={};previous=span['startNanos'];stops=[];starts=[]
            for row in controller['transcript']:
                q=row['request'];command=q['command'];identifier=q['commandId'];original=folder/'commands'/number/identifier
                m.need(identifier not in owned and c.read(original/'request.json')==dict(config=cfg,request=q) and
                       c.read(original/'receipt.json')==row['receipt'],'three-mode original command receipt')
                observation=c.read(original/'observation.json');start,end=observation['startNanos'],observation['endNanos']
                m.need(type(start) is int and type(end) is int and previous<=start<=end,'three-mode controller command order')
                previous=end;owned[identifier]=True
                if command in ('start-voter','stop-voter','window','fault','backup'):
                    m.need(span['startNanos']<=start<=end<=span['endNanos'],'three-mode command outside mode interval')
                if command=='stop-voter':
                    m.need(row['receipt']['state']=='SUCCEEDED' and row['receipt']['result']=={'stopped':True},'three-mode failed voter handoff')
                    stops.append(end)
                if command=='start-voter':starts.append(start)
            m.need(len(starts)==len(stops)==1 and starts[0]<=stops[0] and set(owned)=={p.name for p in (folder/'commands'/number).iterdir()},
                   'three-mode lifecycle coverage')
            seen.add(node)
            replay=output/(mode+'-'+node)
            info=parts.unpack(member/'parts',replay,m.sha(m.canonical(cfg['binding'])))
            budgets['compressedBytes']+=info['compressedBytes'];budgets['expandedBytes']+=info['expandedBytes'];budgets['files']+=info['files']
            index=c.read(replay/parts.INDEX)
            budgets['traceBytes']+=sum(v['bytes'] for n,v in index.items() if n.endswith(('.jsonl','.jsonl.gz','.log')))
            m.need(all(budgets[k]<=parts.LIMITS[k] for k in budgets),'three-mode combined evidence budget')
            replicated=mode in package.MODES[1:]
            logical.append(guest_evidence.validate(replay,cfg,manifest,controller['packageRoot'],controller['transcript'],
                active=controller['active'],healthy=True,physical=replicated,backup=replicated and controller['active']))
            if replicated:
                stored=replay/'authority'/node;source_binding(stored,mode,files)
                m.need(m.sha((stored/'manifest.gsr').read_bytes())==boot['identity']['manifestSha256'] and
                       m.sha((stored/'genesis.gsr').read_bytes())==boot['identity']['genesisSha256'],'three-mode admitted authority changed')
            members.append(dict(root=replay,controller=controller))
        m.need({p.name for p in folder.glob('node-*')}==seen,'three-mode extra member')
        m.need(sum(v['calls'] for v in logical)==90,'three-mode frozen calls')
        physical=guest_physical_evidence.validate(members,manifest,backup=True) if mode in package.MODES[1:] else None
        reports.append(dict(mode=mode,calls=90,members=logical,physical=physical))
    return dict(status='PASS',scope=SCOPE,paidCloud=False,fullRemoteQualification=False,calls=270,sourceBackup=seed,
        requestSha256=sha,sourceSha256=source_sha,packageManifestSha256=m.sha(manifest_bytes),modes=reports,budgets=budgets)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();print(m.canonical(validate(args.input,args.output)).decode())
