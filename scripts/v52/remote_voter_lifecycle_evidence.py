"""Portable lifecycle/export binding, supplemental to unchanged physical replay."""
from pathlib import Path
from . import remote_voter as v,remote_voter_guest as guest,remote_voter_ssh_evidence as ssh
from .evidence import need,digest,encoded


def configuration(config,preparation,root):
    need(type(config) is dict and set(config)==v.scope.fields(config) and
         config['schema']==v.SCHEMA and config['execution']=='local-persistent-voters-only' and config['root']==root and
         all(config[k]==preparation[k] for k in ('node','binding','session')),'lifecycle prepared configuration')
    need(v.scope.generation(config)==v.scope.generation(preparation),'lifecycle prepared generation')
    v.host.validate_pin(config['host']);v.c.hex_value(config['session'],32,'lifecycle session')
    need(config['host']['bootId']==preparation['host']['bootId'] and config['host']['uid']==preparation['host']['uid'],
         'lifecycle prepared host')
    v.host.path(config['socket']);v.host.path(root)


def observation(value,config,sha):
    need(type(value) is dict and set(value)=={'state','started','identity','stopped','exited','serviceAlive','jvmAlive'} and
         value['state'] in ('PREPARED','STARTING','READY','EXITING','STOPPED','CRASHED','FAILED','UNCERTAIN') and
         type(value['serviceAlive']) is bool and type(value['jvmAlive']) is bool,'lifecycle observation fields')
    started=value['started'];identity=value['identity'];stop=value['stopped'];exited=value['exited']
    if started:
        need(type(started) is dict and set(started)=={'configSha256','service'} and started['configSha256']==sha,'lifecycle observed start')
        v.c.validate_process(started['service'],config['host'])
    if identity:
        need(started and type(identity) is dict and set(identity)=={'service','jvm','consumer','host','session'} and
             identity['service']==started['service'] and identity['host']==config['host'] and identity['session']==config['session'],
             'lifecycle observed identity')
        v.c.validate_process(identity['jvm'],config['host']);need(identity['jvm']!=identity['service'],'lifecycle JVM independence')
    need(not value['serviceAlive'] or started,'lifecycle live service without identity')
    need(not value['jvmAlive'] or identity,'lifecycle live JVM without identity')
    if stop:
        need(identity and type(stop) is dict and set(stop)=={'schema','configSha256','identity','lastSequence','journalSha256','exitCode','failure'} and
             stop['schema']==v.SCHEMA and stop['configSha256']==sha and stop['identity']==identity,'lifecycle observed stop')
    if exited:
        need(started and type(exited) is dict and set(exited)=={'configSha256','service','exitCode'} and exited['configSha256']==sha and
             exited['service']==started['service'] and type(exited['exitCode']) is int and exited['exitCode'] in (0,1),'lifecycle observed exit')
    if value['state']=='READY':need(identity and value['serviceAlive'] and value['jvmAlive'] and exited is None,'lifecycle ready process observation')
    if value['state']=='STOPPED':
        need(stop and stop['exitCode']==0 and stop['failure'] is None and exited and exited['exitCode']==0 and
             not value['serviceAlive'] and not value['jvmAlive'],'lifecycle stopped process observation')
    if value['state']=='CRASHED':
        need(config['binding'].get('remoteRestart')==v.scope.RESTART_EXECUTION and v.scope.generation(config)==1 and
             stop and stop['exitCode']==-9 and stop['failure'] is None and exited and exited['exitCode']==0 and
             not value['serviceAlive'] and not value['jvmAlive'],'lifecycle crashed process observation')
    if value['state']=='FAILED':need(exited and not value['serviceAlive'] and not value['jvmAlive'],'lifecycle failed process observation')
    return value


def manifest(value,config,sha):
    need(type(value) is dict and set(value)=={'schema','configSha256','node','bytes','sha256','members','terminal'} and
         value['schema']==guest.SCHEMA and value['configSha256']==sha and value['node']==config['node'],'lifecycle collection identity')
    need(type(value['bytes']) is int and 0<value['bytes']<=guest.MAX_ARCHIVE,'lifecycle archive size')
    v.c.hex_value(value['sha256'],64,'lifecycle archive hash')
    members=value['members'];total=v.h.bundle.validate_index(members)
    need(len(members)<=guest.MAX_FILES and total<=guest.MAX_ARCHIVE,'lifecycle inventory bound')
    node=config['node']
    need(all(name.split('/')[0]==node or name.split('/')[0].startswith(node+'-') for name in members),'lifecycle foreign collection path')
    need(not metadata(node) & set(members),'lifecycle circular collection metadata')
    observation(value['terminal'],config,sha);need(value['terminal']['state']=='STOPPED','lifecycle incomplete collection')
    return value


def metadata(node):
    return {v.scope.control_name(node,g)+'/'+name for g in (1,2) for name in ('lifecycle.json','ssh-streams.json')}


def validate(root,binding,config,sha):
    root=Path(root);node=config['node'];control=root/v.scope.control_name(node,v.scope.generation(config))
    need(binding.get('remoteVoterLifecycle')==guest.EXECUTION,'lifecycle retained scope')
    ssh.binding(binding['remoteVoterTransport'])
    value=v.c.read(control/'lifecycle.json',v.c.RESPONSE_BYTES)
    need(type(value) is dict and set(value)=={'schema','execution','configSha256','launchSubmissions','launchReplyLost','collection'} and
         value['schema']==guest.SCHEMA and value['execution']==guest.EXECUTION and value['configSha256']==sha and
         type(value['launchSubmissions']) is int and value['launchSubmissions']==1 and type(value['launchReplyLost']) is bool,
         'lifecycle retained launch/export')
    preparation=v.c.read(control/'preparation.json',v.c.REQUEST_BYTES)
    need(type(preparation) is dict and set(preparation)=={'node','binding','session','host'}|({'generation'} if 'generation' in config else set()),'lifecycle retained preparation')
    v.host.validate_pin(preparation['host']);configuration(config,preparation,config['root'])
    meta=manifest(value['collection'],config,sha)
    for key in ('started','identity','stopped','exited'):
        need(v.c.read(control/(key+'.json'))==meta['terminal'][key],'lifecycle retained terminal differs')
    index=v.h.bundle.inventory(root)
    observed={name:record for name,record in index.items() if
        (name.split('/')[0]==node or name.split('/')[0].startswith(node+'-')) and
        name not in metadata(node)}
    need(observed==meta['members'],'lifecycle collected bytes differ')
    return dict(files=len(observed),bytes=sum(r['bytes'] for r in observed.values()))
