"""Independent remote member, timing, lifecycle and five-topology set validation."""
import argparse
import ipaddress
from pathlib import Path
import tempfile
from .cloud_common import canonical, plan, read, require, sha, validate_inventory
from .cloud_presets import ORDER, validate_request
from .cloud_workload_io import inventory, unpack
from .cloud_workload_plan import PLAN_SHA256, read_plan
from .cloud_remote_guest import SCHEMA, EXECUTION


def provenance(root,qualification):
    document=read(root/'hosts.json',16<<20);env=read(root/'set.json',16<<20);meta=read(root/'metadata.json',16<<20)
    require(document['schema']=='gse-v50-remote-workload-hosts-v1' and document['qualification'] is qualification,
            'remote provenance execution boundary')
    request=document['request'];validate_request(request)
    require(document['plan']==plan() and meta['head']==request['source'],'remote source/runner identity')
    bundle=read(root/'remote-bundle.json',16<<20)
    require(bundle['schema']==SCHEMA and bundle['execution']==EXECUTION and bundle['workloadPlanSha256']==PLAN_SHA256 and
            bundle['inputs']==meta['inputs'] and bundle['source']==meta['head'] and bundle['dirty'] is meta['dirty'], 'remote artifact provenance')
    require(env['execution']==('local-remote-workload-only' if qualification else 'gcp-cloud-workload') and
            env['preset']==('local-qualification' if qualification else request['profile']),'remote profile identity')
    if not qualification:
        require(meta['dirty'] is False and meta['javaExecutable']=='/opt/gse-v50/jre/bin/java','clean cloud artifact required')
    hosts=document['hosts'];require(len(hosts)==3,'three remote voters required')
    ids=set();boots=set();addresses=[]
    for node,host in enumerate(hosts,1):
        vm=host['instance'];facts=host['facts'];distribution=host['distribution']
        require(vm['kind']=='instances' and vm['node']==node and vm['name']==request['owner']+f'-n{node}', 'remote voter identity')
        require(vm['id'] not in ids,'duplicate VM namespace');ids.add(vm['id']);boots.add(facts['bootId'])
        require(distribution['installed'] is True and distribution['manifest']==facts['bundle']==bundle and
                distribution['bundleSha256']==request['bundleSha256'] and facts['qualification'] is qualification,
                'remote bundle distribution')
        require('21.0.12+8' in facts['java'],'guest Java pin')
        if not qualification:
            observed=vm['observation'];p=document['plan']
            require(str(observed['id'])==vm['id'] and observed['labels']['gse-owner']==request['owner'] and
                    observed['labels']['gse-source']==request['source'],'VM ownership/source')
            require(observed['zone'].endswith('/zones/'+p['zone']) and observed['machineType'].endswith('/machineTypes/'+p['machineType']) and
                    not observed.get('serviceAccounts') and observed['scheduling']['instanceTerminationAction']=='DELETE' and
                    int(observed['scheduling']['maxRunDuration']['seconds'])==5400,'VM shape/watchdog')
            interfaces=observed['networkInterfaces'];require(len(interfaces)==1 and not interfaces[0].get('accessConfigs'),'private network shape')
            address=ipaddress.ip_address(interfaces[0]['networkIP'])
            require(address.is_private and not address.is_loopback and not address.is_link_local,'private nonlocal peer')
            addresses.append(str(address)+':9700')
            require('initialMount' in host and (node==1 or 'runtimeMount' in host),'missing volume attachment receipt')
            for key in ('initialMount','runtimeMount'):
                if key not in host:continue
                mount=host[key];rows=mount['filesystems']
                require(len(rows)==1 and rows[0]['fstype']=='ext4' and rows[0]['target']==f'/mnt/gse-v50/volume-{node}', 'remote volume placement')
                expected_host=hosts[0]['instance']['id'] if key=='initialMount' else vm['id']
                require(mount['instanceId']==expected_host and mount['diskName']==request['owner']+f'-n{node}-data' and
                        mount['diskId']==host['initialMount']['diskId'] and
                        mount['attachment']['source'].endswith('/disks/'+mount['diskName']) and mount['attachment']['autoDelete'] is True,'initial disk attachment identity')
        members=[read(p,16<<20) for p in sorted((root/'members').glob(f'node-{node}-*.json'))]
        require(members and sorted(m['generation'] for m in members)==list(range(1,len(members)+1)) and len(members)<=32,'complete JVM generation set')
        for member in members:
            label=f'node-{node}-{member["generation"]}.json';receipt=read(root/'workers'/label);stop=read(root/'stops'/label)
            require(receipt==dict(owner=request['owner'],node=node,generation=member['generation'],pid=member['pid'],
                startTicks=member['linuxStartTicks'],args=member['args'],bootId=facts['bootId']),'remote PID/start-tick binding')
            require(member['instanceId']==vm['id'] and member['bootId']==facts['bootId'] and member['linuxStartTicks']!='0','member VM namespace')
            require(all(stop[k]==v for k,v in receipt.items()) and stop['status']==('KILLED' if member['forced'] else 'EXITED'),'remote process termination proof')
            require(member['args'][-4]==document['endpoints'] and member['args'][-2].endswith('/'+member['streams']),'remote peer/stream binding')
            if not qualification:require(member['args'][-6]=='/mnt/gse-v50' and member['args'][-3]=='/opt/gse-v50/workload.json','sealed remote root')
    if not qualification:
        require(len(boots)==3 and len(set(addresses))==3 and document['endpoints']==','.join(addresses),'three distinct guest namespaces')
    return document


def timings(root,profile):
    plan=read_plan();reserved=plan['profiles'][profile]['reservationsSeconds'];env=read(root/'set.json',16<<20)
    timing=read(root/'timing.json');cells=read(root/'cells.json',16<<20)
    control=read(root/'control.json',16<<20)['process'];restore=read(root/'restore.json',16<<20)['process']
    control_ns=control['finishedNanos']-control['startedNanos']+restore['finishedNanos']-restore['startedNanos']
    require(0<control_ns<=reserved[1]*10**9,'published control reservation')
    setup=timing['warmupStartedNanos']-env['startedNanos']-(control['finishedNanos']-control['startedNanos'])
    require(0<setup<=reserved[0]*10**9,'provisioning/startup reservation')
    overhead=0;previous=timing['warmupFinishedNanos']
    for cell,spec in zip(cells,plan['profiles'][profile]['cells']):
        require(cell['startedNanos']>=previous,'overlapping cell/control intervals')
        overhead+=cell['startedNanos']-previous;previous=cell['finishedNanos']
        elapsed=cell['finishedNanos']-cell['startedNanos'];budget=spec['seconds']*10**9
        if spec['name'] in ('healthy','sustained'):
            windows=cell['details'].get('windows',[cell['details']['window']] if 'window' in cell['details'] else [])
            active=sum(w['calls']*w['intervalNanos'] for w in windows)
            require(active==budget==cell['measurementNanos'] and 0<=cell['controlOverheadNanos']<=elapsed-active and
                    elapsed-active-cell['controlOverheadNanos']<10**9,'measurement/control accounting')
            overhead+=elapsed-active
        else:require(budget<=elapsed<=budget+10**9,'elapsed cloud cell budget')
    warmup=timing['warmupFinishedNanos']-timing['warmupStartedNanos']
    require(0<warmup and warmup+overhead<=reserved[2]*10**9,'candidate warmup/control reservation')
    tail=env['finishedNanos']-cells[-1]['finishedNanos']-(restore['finishedNanos']-restore['startedNanos'])
    require(0<tail<=(reserved[4]+reserved[5])*10**9,'collection/cleanup reservation')


def validate_raw(root,*,qualification=False):
    root=Path(root);document=provenance(root,qualification)
    if not qualification:
        timings(root,document['request']['profile'])
        exchanges=[e for p in (root/'members').glob('*.json') for e in read(p,16<<20)['exchanges']]
        for cell in read(root/'cells.json',16<<20):
            if cell['name'] not in ('unavailable','slow','incremental','snapshot'):continue
            selected=sorted((e for e in exchanges if cell['startedNanos']<=e['sentNanos']<=cell['finishedNanos']),key=lambda e:e['sentNanos'])
            updates=[e for e in selected if e['request']['command']=='update']
            mode='slow' if cell['name']=='slow' else 'block-node-3'
            enabled=next(e for e in selected if e['request']==dict(command='fault',mode=mode))
            healed=next(e for e in selected if e['request']==dict(command='fault',mode='none'))
            require(len(updates)==10 and all(e['response']['accepted'] is True and e['request']['id']==5 for e in updates) and
                    healed['sentNanos']-enabled['receivedNanos']>=10*10**9,'ten-second fault interval and successful background writes')
            require(all(b['sentNanos']-a['sentNanos']>=10**9 for a,b in zip(updates,updates[1:])),'fault background burst')
            if cell['name']!='slow':
                d=cell['details'];require(d['before']['commitIndex']==d['during']['commitIndex'],'isolated follower advanced')
    from .cloud_workload_evidence import validate_raw as semantics
    result=semantics(root,remote=True,qualification=qualification)
    artifacts={k:v['sha256'] for k,v in read(root/'metadata.json',16<<20)['jars'].items()}
    return dict(result,remoteBundle=True,requestSha256=sha(canonical(document['request'])),
                profile=document['request']['profile'],repetition=document['request']['repetition'],artifactSha256=artifacts,
                resources=[dict(node=h['instance']['node'],instanceId=h['instance']['id'],
                    initialDiskId=h['initialMount'].get('diskId')) for h in document['hosts']])


def validate_bundle(bundle,*,qualification=False):
    bundle=Path(bundle);before=inventory(bundle)
    with tempfile.TemporaryDirectory(prefix='gse-remote-inspect-') as temp:
        raw=Path(temp)/'raw';unpack(bundle,raw);result=validate_raw(raw,qualification=qualification)
    require(inventory(bundle)==before,'remote verifier changed evidence');return result


def validate(root):
    root=Path(root);state=read(root/'completion.json',16<<20)
    require(state['schema']=='gse-v50-cloud-lifecycle-v1' and state['execution']=='gcp-owned-runtime' and
            state['status']=='PASS' and not state['errors'] and state['retention']=='VERIFIED' and state['plan']==plan(), 'real complete cloud lifecycle required')
    spec=validate_request(state['request']);rows=state['resources'];validate_inventory(state['plan'],state['request'],rows)
    require(len(rows)==13+len(spec['replacementNodes']) and all(r['attempted'] and r['insertFinished'] and
            r['id']==str(r['observation']['id']) for r in rows),'complete physical resource set')
    cleanup=state['cleanup']
    require(cleanup['status']=='PASS' and not cleanup['leftovers'] and cleanup['checks']==[
        dict(name=r['name'],expectedId=r['id'],observedId=None,absent=True) for r in rows],'complete absent-resource read-backs')
    require(len({r['requestId'] for r in rows})==len(rows) and len({(r['kind'],r['id']) for r in rows})==len(rows), 'unique resource/create identities')
    files=read(root/'workload-evidence/parts.json',16<<20)['files']
    for node in spec['replacementNodes']:
        old=next(r for r in rows if r['name']==state['request']['owner']+f'-n{node}-data')
        new=next(r for r in rows if r['name']==old['name']+'-g2')
        require(old['retired']['absent'] is True and old['retired']['expectedId']==old['id'] and old['id']!=new['id'] and
                new['replacementReceipt']['diskId']==new['id'] and new['replacementReceipt']['sourceNode']==(1 if node==3 else 2) and
                new['mountReceipt']['diskId']==new['id'],'physical replacement ownership/source')
        expected=old['retired']['preserved']['files']
        retained={k.removeprefix(f'lost-node-{node}/'):{n:v[n] for n in ('bytes','sha256')} for k,v in files.items() if k.startswith(f'lost-node-{node}/')}
        require(expected==retained and old['retired']['preserved']['path']==f'lost-node-{node}','replacement pre-loss diagnostics')
        for mount,host in ((new['mountReceipt'],node),(new['replacementReceipt']['mount'],1 if node==3 else 2)):
            instance=next(r for r in rows if r['kind']=='instances' and r['node']==host)
            require(mount['diskId']==new['id'] and mount['diskName']==new['name'] and
                    mount['instanceId']==instance['id'] and
                    len(mount['filesystems'])==1 and mount['filesystems'][0]['fstype']=='ext4' and
                    mount['filesystems'][0]['target']==f'/mnt/gse-v50/volume-{node}' and
                    mount['attachment']['source'].endswith('/disks/'+new['name']) and mount['attachment']['autoDelete'] is True,
                    'replacement mount identity')
        public=new['replacementReceipt']['publicReceipt']
        require(public['result']==dict(replacement=node,source=(1 if node==3 else 2)) and
                public['process']['exitCode']==0 and public['process']['args'][-4:]==['replace',str(node),str(1 if node==3 else 2),'volumes'],
                'public replacement admission')
    result=validate_bundle(root/'workload-evidence')
    expected_resources=[dict(node=node,
        instanceId=next(r['id'] for r in rows if r['kind']=='instances' and r['node']==node),
        initialDiskId=next(r['id'] for r in rows if r['name']==state['request']['owner']+f'-n{node}-data')) for node in (1,2,3)]
    require(result['resources']==expected_resources,'lifecycle/guest resource identity')
    require(result==state['probeValidation'] and result['requestSha256']==sha(canonical(state['request'])),'lifecycle/workload binding')
    from .cloud_preflight import admission
    approval=read(root/'approval.json');receipt=read(root/'preflight.json',16<<20)
    admission(state['plan'],receipt,state['request'],approval,now=state['startedAt'])
    reservation=state['budgetReservation']['reservations'][-1]
    require(reservation['requestSha256']==result['requestSha256'] and reservation['approvalSha256']==sha(canonical(approval)), 'retained cost approval binding')
    return dict(result,cleanup='PASS',retention='VERIFIED')


def validate_set(roots):
    require(len(roots)==len(ORDER),'complete experiment/drill/three-canonical set required')
    values=[validate(Path(p)) for p in roots];requests=[read(Path(p)/'completion.json',16<<20)['request'] for p in roots]
    require([(r['profile'],r['repetition']) for r in requests]==list(ORDER),'cloud set order')
    require(len({r['sequence'] for r in requests})==len({r['source'] for r in requests})==1 and
            len({r['owner'] for r in requests})==5,'cloud set source/namespace identity')
    require(all(v['artifactSha256']==values[0]['artifactSha256'] for v in values),'cloud set artifact drift')
    states=[read(Path(p)/'completion.json',16<<20) for p in roots]
    require(all(a['finishedAt']<=b['startedAt'] for a,b in zip(states,states[1:])),'overlapping cloud topologies')
    ceiling=read_plan()['resources']['maximumCompleteSequenceMicrousd']
    require(sum(v['maximumCostMicrousd'] for v in states[-1]['budgetReservation']['reservations'])<=ceiling,'cloud set cost ceiling')
    return dict(status='PASS',execution='gcp-cloud-workload-set',source=requests[0]['source'],sequence=requests[0]['sequence'],members=values)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('evidence',type=Path,nargs='+');p.add_argument('--set',action='store_true')
    a=p.parse_args();print(validate_set(a.evidence) if a.set else validate(a.evidence[0]))
