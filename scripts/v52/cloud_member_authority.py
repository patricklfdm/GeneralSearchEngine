"""Independent retained authority correlation; never current cloud admission.

The caller supplies the separately selected request, exact source/build binding
and source-controlled configuration. No field in retained JSON is its own oracle.
"""
from copy import deepcopy
import os
from pathlib import Path
import uuid
from . import cloud_authority as a,cloud_inputs as inputs,cloud_artifacts as artifacts
from . import cloud_ci as ci,cloud_preflight as preflight,cloud_prepared as prepared
from . import cloud_recent_cleanup as recent,cloud_access as access,cloud_identity as identity
from . import cloud_guest_identity as guest,cloud_volume_guest as volume
from . import remote_host_domains as domains,remote_voter_ssh_evidence as routes,remote_host as host
from . import remote_python_receiver as python,remote_java_receiver as java_image
from . import cloud_suite as suite,cloud_native_runner as runner
from .evidence import need,encoded,digest


def resource_claim(request,value):
    a.fields(value,'schema requestSha256 startedAt source attempt nodes firewalls','retained resource claim')
    need(type(value['nodes']) is dict and set(value['nodes'])==set(domains.topology.NODES),'V5.2 retained claim nodes')
    lease=a.lease(request,value['startedAt']);lease['phase']='ACTIVE'
    rows=[*value['firewalls'],*[row for node in domains.topology.NODES for row in value['nodes'][node]['identity']['resources']]]
    need(len(rows)==13 and len({row['spec']['name'] for row in rows})==13,'V5.2 retained resource inventory')
    by_name={row['spec']['name']:row for row in rows}
    need(set(by_name)=={row['spec']['name'] for row in lease['resources']},'V5.2 retained resource names')
    lease['resources']=[deepcopy(by_name[row['spec']['name']]) for row in lease['resources']]
    need(a.resource_claim(lease)==value,'V5.2 retained original resource claim changed')
    return lease


def guest_records(value,request,cfg,claim):
    a.fields(value,'provider guests','retained guests');nodes=set(domains.topology.NODES)
    need(type(value['provider']) is dict and type(value['guests']) is dict and
         set(value['provider'])==set(value['guests'])==nodes,'V5.2 retained guest inventory')
    addresses=set();boots=set();keys=set()
    for node in domains.topology.NODES:
        g=guest.validate(value['guests'][node]);own=claim['nodes'][node];rows=own['identity']['resources']
        vm=next(row for row in rows if row['spec']['kind']=='instance')
        boot=next(row for row in rows if row['spec']['purpose']=='boot')
        data=next(row for row in rows if row['spec']['purpose']=='data')
        need(g['instanceId']==vm['id'] and g['user']==request['guestAccess']['user'],'V5.2 retained guest owner')
        row=value['provider'][node];key=access.ed25519(row['hostKey'])
        alias=access.alias(claim['requestSha256'],node,vm['id'])
        facts=dict(instanceId=vm['id'],instance=vm['spec']['name'],privateAddress=g['privateAddress'],
            bootDiskId=boot['id'],dataDiskId=data['id'],dataDiskGiB=data['spec']['sizeGiB'])
        expected=dict(schema=identity.SCHEMA,execution='native-v52-provider-observation',paidCloud=True,
            requestSha256=claim['requestSha256'],resourceClaimSha256=digest(encoded(claim)),
            resourceIdentitySha256=own['resourceIdentitySha256'],node=node,source=claim['source'],
            attempt=claim['attempt'],configurationSha256=request['configurationSha256'],
            guestAccessSha256=digest(encoded(request['guestAccess'])),project=cfg['project'],zone=cfg['zone'],
            facts=facts,hostKey=key,alias=alias,sshHostPinSha256=digest((alias+' '+key+'\n').encode()),guestObserved=False)
        need(row==expected,'V5.2 retained provider/guest correlation')
        addresses.add(g['privateAddress']);boots.add(g['bootId']);keys.add(key)
    need(len(addresses)==len(boots)==len(keys)==3,'V5.2 retained independent guests')
    return value


def storage_records(value,request,claim,guests):
    a.fields(value,'records python java javaDescriptor','retained storage')
    nodes=set(domains.topology.NODES)
    need(all(type(value[k]) is dict and set(value[k])==nodes for k in ('records','python','java')),
         'V5.2 retained storage inventory')
    descriptor=java_image.descriptor(value['javaDescriptor'])
    for node in domains.topology.NODES:
        observed=guests['provider'][node];facts=observed['facts'];g=guests['guests'][node]
        req=volume.validate(dict(schema=volume.SCHEMA,source=claim['source'],requestSha256=claim['requestSha256'],
            resourceClaimSha256=digest(encoded(claim)),resourceIdentitySha256=observed['resourceIdentitySha256'],
            attempt=claim['attempt'],node=int(node[-1]),instanceId=facts['instanceId'],diskId=facts['dataDiskId'],
            bootDiskId=facts['bootDiskId'],sizeGiB=facts['dataDiskGiB'],bootSizeGiB=request['layout']['bootDiskGiB'],
            guest=g,publicKey=request['guestAccess']['publicKey']))
        answer=value['records'][node]
        a.fields(answer,'schema requestSha256 budgetSha256 action state startup readiness process','retained volume')
        need(answer['schema']=='gse-v52-volume-answer-v1' and answer['requestSha256']==volume.digest(req) and
             answer['action']=='check' and answer['state']=='SUCCEEDED' and answer['process'] is None,
             'V5.2 retained volume outcome')
        a.hex_value(answer['budgetSha256']);startup=answer['startup'];mounted=volume.replay(startup,req)
        ready=answer['readiness'];a.fields(ready,'startupSha256 volume observation','retained mount readiness')
        need(ready['startupSha256']==volume.digest(startup) and ready['volume']==mounted and
             volume.mounted(ready['observation'],startup['before'],req)==mounted,'V5.2 retained mount readiness')
        py=value['python'][node];java=value['java'][node]
        a.fields(py,'schema descriptorSha256 root host filesSha256','retained Python installation')
        a.fields(java,'schema descriptorSha256 root host filesSha256 java','retained Java installation')
        need(py['schema']==python.RECEIPT and Path(py['root']).name.startswith('python-'),
             'V5.2 retained Python installation')
        for sha in (Path(py['root']).name[7:],py['descriptorSha256'],py['filesSha256']):a.hex_value(sha)
        need(java['schema']==java_image.RECEIPT and java['descriptorSha256']==digest(encoded(descriptor)) and
             java['filesSha256']==digest(encoded(descriptor['files'])) and java['java']==descriptor['source']['java'] and
             Path(java['root']).name=='java-'+descriptor['sha256'],'V5.2 retained Java installation')
        for receipt in (py,java):
            own=host.validate_pin(receipt['host'])
            need(all(own[k]==g[k] for k in ('bootId','uid')) and Path(receipt['root']).parent==Path(volume.MOUNT) and
                 mounted['majorMinor']==str(os.major(own['parentDevice']))+':'+str(os.minor(own['parentDevice'])),
                 'V5.2 retained installation data volume')
        need(java['host']==py['host'],'V5.2 retained Java/Python original directory')
    return value


def placement(name,source,request,cfg,claim,guests,retained):
    history=digest(encoded([claim['requestSha256'],name]));transport=retained['remoteVoterTransport']
    routes.binding(transport)
    need(transport['execution']==routes.BOUND_EXECUTION,'V5.2 retained private SSH scope')
    for node,route in transport['nodes'].items():
        row=guests['provider'][node]
        need(route['host']=='127.0.0.1' and route['user']==request['guestAccess']['user'] and
             route['alias']==row['alias'] and route['hostPinSha256']==row['sshHostPinSha256'],
             'V5.2 retained original SSH route')
    expected=dict(source,remoteTopology=dict(schema=domains.topology.SCHEMA,placement='owned-private-hosts',
        groupId=str(uuid.UUID(hex=history[:32])),members=[dict(node=n,host=guests['guests'][n]['privateAddress'],port=cfg['port'])
            for n in domains.topology.NODES]),
        remoteHostDomains=dict(schema=domains.SCHEMA,source=claim['source'],attempt=claim['attempt'],
            leaseSha256=digest(encoded(claim)),nodes={n:dict(resourceIdentitySha256=guests['provider'][n]['resourceIdentitySha256'],
                privateAddress=guests['guests'][n]['privateAddress'],bootId=guests['guests'][n]['bootId'],uid=guests['guests'][n]['uid'],
                sshHostPinSha256=guests['provider'][n]['sshHostPinSha256']) for n in domains.topology.NODES}),
        remoteVoterTransport=deepcopy(transport))
    need(expected==retained,'V5.2 retained original placement changed');domains.routes(expected)
    return expected,{node:str(Path(volume.MOUNT)/('history-'+history)/node) for node in domains.topology.NODES}


def replay(root,value,request,source,cfg):
    """Pure original-observation replay; performs no provider/GitHub request."""
    root=Path(root);a.validate_request(request,domain='native');inputs.identity(source);preflight.configuration(cfg)
    a.fields(value,'schema request configuration plan approval inputs build observations recentCleanup claim guestIdentity placements storage',
             'retained member authority')
    need(value['schema']=='gse-v52-native-member-authority-v1' and value['request']==request and value['configuration']==cfg and
         value['inputs']['source']==source and request['selection']['binding']['source']==source['source'],
         'V5.2 retained external authority binding')
    selected=request['selection'];plan=value['plan'];observations=value['observations'];now=observations['completedAt']
    need(observations['execution']=='native-v52-provider-observations','V5.2 retained provider scope')
    pre=preflight.evaluate(cfg,source['source'],'runner',observations,now=now)
    need(pre['status']=='PREFLIGHT_OBSERVED_NOT_ADMITTED','V5.2 retained original preflight')
    ledger=observations['controlAfter']['ledger'];baseline=runner.ledger_baseline(ledger)
    prepared.review(plan,value['approval'],digest(encoded(plan)),current_inputs=value['inputs'],current_configuration=cfg['provider'],
        project_number=cfg['projectNumber'],current_ledger=baseline,active_lease=observations['controlAfter']['lease'],now=now)
    need(plan['request']==request and request['layout']==cfg['layout'] and request['policy']==cfg['policy'],
         'V5.2 retained original plan/configuration')
    built=artifacts.replay(root/'provenance',source['source'],ci.contract(),source,now=now)
    need(built==value['build'] and built['buildBinding']==source and
         built['buildManifestSha256']==value['inputs']['buildManifestSha256'],'V5.2 retained build provenance')
    roots=[f'target/general-search-engine-{inputs.VERSION}.jar',
        f'{inputs.build.MODULE}/target/general-search-engine-replication-{inputs.VERSION}.jar',inputs.build.CLASSES,inputs.build.REPORTS]
    raw,candidate=inputs.build_files(root/'provenance/build',source,roots);controls,pins=inputs.controls(ci.ROOT)
    proof,files=inputs.verify_archive(root/'inputs.tar.gz',source,raw,controls,candidate,pins,include_files=True)
    need(proof==value['inputs'],'V5.2 retained original package')
    clean=recent.validate(artifacts.read(root/'recent-cleanup/observation.json'),cfg,source['source'],root/'recent-cleanup/cleanup.zip',now)
    need(clean==value['recentCleanup'] and pre['credentialContext']['runId']!=clean['runId'],
         'V5.2 retained original cleanup provenance')
    lease=resource_claim(request,value['claim']);claim=value['claim']
    guests=guest_records(value['guestIdentity'],request,cfg['provider'],claim)
    storage=storage_records(value['storage'],request,claim,guests)
    need(storage['javaDescriptor']['source']==source,'V5.2 retained installed Java source')
    need(type(value['placements']) is dict and set(value['placements'])==set(selected['member']['histories']),
         'V5.2 retained whole member placement inventory')
    bindings={};paths={}
    for name in selected['member']['histories']:
        bindings[name],paths[name]=placement(name,source,request,cfg['provider'],claim,guests,value['placements'][name])
    return dict(lease=lease,placements=bindings,roots=paths,files=files,storage=storage,preflight=pre)
