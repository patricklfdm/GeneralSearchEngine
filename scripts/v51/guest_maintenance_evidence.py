"""Maintenance witnesses: a pinned view across rejoin and a published-core restore."""
from pathlib import Path
import subprocess
from . import performance_model as m, remote_command as c, cloud_package as package
from . import cloud_workload_contract as contract, performance_plan, guest_authority, controls, guest_bootstrap


def check(record, history, traces, rows, obs, collections, configs, bases, manifest,*,request=None):
    from . import native_experiment_timing as timing
    request=request or {}
    leader=record['seedLeader'];own=traces[leader];cut=record['cut']
    def commands(action):return [(q,r) for q,r in rows[leader] if q['command']=='fault' and q['payload'].get('action')==action]
    pins,releases=commands('pin'),commands('release-pin')
    m.need(len(pins)==len(releases)==1,'maintenance pin command coverage')
    (pq,pr),(rq,rr)=pins[0],releases[0]
    pinned=next(h for h in history if h['opId']==pr['result']['opId'])
    m.need(pinned['response']==record['pinnedRead']==rr['result']['response'] and pinned['outcome']=='SUCCESS' and
           pinned['documents']==record['seedRead']['documents'],'maintenance captured view changed')
    m.need(cut in own and cut['event']=='CUT_REACHED' and cut['cut']=='READ_CAPTURED' and cut['mode']=='pause' and
           cut['pid']==pinned['pid']==history[3]['pid'],'maintenance pin witness')
    release=[r for r in own if r['event']=='CUT_RELEASED' and r['cut']=='READ_CAPTURED']
    m.need(len(release)==1 and release[0]['pid']==cut['pid'],'maintenance release witness')
    installed=[r for r in own if r['event']=='REJOIN_INSTALLED' and r['pid']==cut['pid'] and cut['order']<r['order']<release[0]['order']]
    m.need(installed and release[0]['localNanos']-cut['localNanos']<=timing.control(request,'pin',60)*10**9,'maintenance no bounded rejoin while pinned')
    states=commands('pin-state')
    m.need(any(r['result']['cut']==cut and r['result']['installed'] in installed and r['result']['pending'] is True and
               obs[q['commandId']]['endNanos']<=obs[rq['commandId']]['startNanos'] for q,r in states),'maintenance original pending observation')
    rules=[f'node-{a} node-{b} BEFORE_REQUEST_WRITE *' for a in (1,2,3) for b in (1,2,3) if a!=b and leader in (f'node-{a}',f'node-{b}')]
    isolation_ends=[];heal_starts=[];dropped=set()
    for node,seq in rows.items():
        isolated=[(q,r) for q,r in seq if q['command']=='fault' and q['payload']==dict(action='isolate',node=leader)]
        healed=[(q,r) for q,r in seq if q['command']=='fault' and q['payload']==dict(action='heal')]
        m.need(len(isolated)==len(healed)==1,'maintenance isolation coverage')
        iq,ir=isolated[0];hq,hr=healed[0];actual=c.read(collections[node]/'isolation.json')
        m.need(ir['result']=={k:actual[k] for k in ('appliedNanos','rules')} and hr['result']==actual and actual['rules']==rules and
               actual['watchdog'] is False and 0<actual['healedNanos']-actual['appliedNanos']<=timing.control(request,'isolation',60)*10**9,'maintenance isolation/watchdog')
        if any(v['event']=='NETWORK_DROP' and v['rule'] in rules and actual['appliedNanos']<=v['localNanos']<=actual['healedNanos'] for v in traces[node]):dropped.add(node)
        isolation_ends.append(obs[iq['commandId']]['endNanos']);heal_starts.append(obs[hq['commandId']]['startNanos'])
    m.need(leader in dropped and len(dropped)>=2,'maintenance missing bidirectional network drops')
    m.need(any(p['node']!=leader and max(isolation_ends)<=p['startNanos']<=p['endNanos']<=min(heal_starts) and
               all(p[k]['outcome']=='SUCCESS' for k in ('write','read')) for p in record['progress']),'maintenance surviving majority progress')
    m.need(len(record['rejoins'])==1 and record['rejoins'][0]['node']==leader,'maintenance rejoin coverage')
    maintenance=[h for h in history if h['kind'] in ('checkpoint','backup')]
    m.need([h['kind'] for h in maintenance]==['checkpoint','backup'] and all(h['outcome']=='SUCCESS' for h in maintenance),'maintenance operations')
    checkpoint,backup=maintenance
    m.need(pinned['endNanos']<=checkpoint['startNanos']<=checkpoint['endNanos']<=backup['startNanos'] and
           any(r['result']['unpinned'] in own and r['result']['unpinned']['event']=='PERFORMANCE_SAMPLE' and
               r['result']['unpinned']['queues']['pinsBytes']==0 and release[0]['localNanos']<r['result']['unpinned']['localNanos'] and
               obs[q['commandId']]['endNanos']<=checkpoint['startNanos'] for q,r in states if r['result']['unpinned']),'maintenance checkpoint before pin cleanup')
    owner=backup['node'];root=collections[owner];cfg=configs[owner];base=bases[owner]
    restore=[(n,q,r) for n,seq in rows.items() for q,r in seq if q['command']=='restore-backup']
    m.need(len(restore)==1 and restore[0][1]['payload']=={} and restore[0][0]==owner,'maintenance restore coverage')
    _,q,r=restore[0];process=c.read(root/'restore.json')
    m.need(set(guest_authority.inventory(root/'backup'))==set(guest_bootstrap.SOURCE),'maintenance backup inventory')
    m.need(process==r['result']==record['restore'] and c.read(root/'restore-claim.json')==dict(config=cfg,files=guest_authority.inventory(root/'backup')),'maintenance restore original bytes')
    spec=manifest['modes'][package.MODES[0]];cp=':'.join(str(base/n) for n in [*spec['jars'],spec['classes']])
    args=[str(base/'runtime/bin/java'),*contract.load()['environment']['jvmArguments'],'-cp',cp,package.PACKAGE+'admission.V51OwnedFaultRestore',cfg['root']]
    stopped=[r for q,r in rows[owner] if q['command']=='stop-voter'][-1]
    m.need(process['args']==args and process['exitCode']==0 and type(process['pid']) is int and process['pid']>0 and
           process['pid'] not in (backup['pid'],r['process']['pid']) and
           stopped['endedNanos']<=r['startedNanos']<=process['startedNanos']<process['endedNanos']<=r['endedNanos'],'maintenance restore process identity/order')
    restored=c.read(root/'restore.stdout');control=next(v for v in performance_plan.load()['publishedControls']['artifacts'] if v['artifact']=='general-search-engine' and v['version']=='4.4.0')
    m.need(spec['jars']==['artifacts/general-search-engine-4.4.0.jar'] and
           next(v for v in manifest['files'] if v['path']==spec['jars'][0])['sha256']==control['sha256'],'maintenance published control binding')
    m.need(restored==dict(sequence=backup['response']['sequence'],coreSource=str(base/spec['jars'][0]),documents=record['finalReads'][-1]['documents']), 'maintenance restored view mismatch')
    return dict(backup=root/'backup',expected=restored,control=control)


def replay(backup, expected, control, output):
    """Decode the retained export again through the pinned published V4.4 API."""
    import shutil
    from .performance_harness import ROOT
    output.mkdir();shutil.copytree(backup,output/'backup')
    controls.resolve(ROOT/'target/v51-published-controls')
    jar=ROOT/'target/v51-published-controls'/('general-search-engine-'+control['version']+'.jar')
    m.need(jar.is_file() and m.sha(jar.read_bytes())==control['sha256'],'maintenance replay published JAR binding')
    classes=output/'classes';classes.mkdir()
    source=ROOT/'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/admission/AdmissionJson.java'
    commands=[['javac','--release','21','-proc:none','-cp',str(jar),'-d',str(classes),str(source),str(ROOT/'scripts/v51/java/V51OwnedFaultRestore.java')],
              ['java','-Xmx512m','-XX:ActiveProcessorCount=2','-cp',str(jar)+':'+str(classes),package.PACKAGE+'admission.V51OwnedFaultRestore',str(output)]]
    for i,cmd in enumerate(commands):
        result=subprocess.run(cmd,capture_output=True,timeout=60)
        (output/f'{i}.stdout').write_bytes(result.stdout);(output/f'{i}.stderr').write_bytes(result.stderr)
        m.need(result.returncode==0,'maintenance independent restore: '+result.stderr.decode()[-2000:])
    got=m.strict_json(result.stdout)
    m.need(got==dict(expected,coreSource=str(jar)),'maintenance independent backup bytes differ')
    return dict(status='PASS',sequence=got['sequence'],documents=len(got['documents']))
