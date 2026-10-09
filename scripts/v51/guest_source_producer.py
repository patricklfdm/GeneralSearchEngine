"""One consumed, package-bound source producer; read-only manifests and chunks.

The verified package wrapper owns host/boot/deadline admission. Never receives a
producer path from the controller or starts a persistent service/workload voter.
"""
from copy import deepcopy
import os
from pathlib import Path
from . import performance_model as m, remote_command as c, cloud_guest as guest, cloud_package as package
from . import guest_bootstrap as boot, guest_source_transfer as wire, guest_delivery_receiver as files

SCHEMA='gse-v51-source-producer-v1'


def validate(request):
    m.need(type(request) is dict and set(request)=={'schema','configs'} and request['schema']==SCHEMA,'producer request fields')
    configs=request['configs']
    m.need(type(configs) is list and configs,'producer member count')
    nodes=package.service_nodes(configs[0])
    m.need(len(configs)==len(nodes),'producer member count')
    for i,cfg in enumerate(configs):
        guest.validate(cfg);normalized=deepcopy(cfg);normalized['binding']['node']=configs[0]['binding']['node']
        m.need(cfg['binding']['node']=='node-'+str(nodes[i]) and normalized==configs[0],
               'producer exact member configurations')
    m.need(len(m.canonical(request))<=wire.METADATA_BYTES,'producer request bound')
    return configs


def location(base):return Path(base).parent/'source-producer'
def exists(path):return path.exists() or path.is_symlink()
def read(path,maximum=262144):return files.decode(files.read(path,os.getuid(),maximum))
def envelope(request,state,**extra):
    return dict(schema='gse-v51-source-producer-receipt-v1',requestSha256=m.sha(m.canonical(request)),state=state,**extra)


def retained(base,request,node):
    m.need(node in [cfg['binding']['node'] for cfg in request['configs']],'producer selected member')
    cfg=next(cfg for cfg in request['configs'] if cfg['binding']['node']==node);root=location(base)
    value=read(root/(node+'-descriptor.json'),wire.METADATA_BYTES);wire.validate(value)
    m.need(value['config']==cfg,'producer retained export configuration')
    folder=root/'exports'/node;digest=m.sha(m.canonical(value['bootstrap']))
    m.need(wire.describe(folder,digest,cfg)==value,'producer immutable export changed')
    return value,folder


def query(base,request,check):
    validate(request);check();root=location(base)
    if not exists(root):return envelope(request,'NOT_FOUND')
    files.owned(root,os.getuid(),True)
    if not exists(root/'request.json'):return envelope(request,'UNCERTAIN')
    m.need(read(root/'request.json')==request,'producer original request changed')
    if not exists(root/'receipt.json'):return envelope(request,'UNCERTAIN')
    receipt=read(root/'receipt.json');state=receipt.get('state')
    m.need(state in ('SUCCEEDED','FAILED') and all(receipt.get(k)==v for k,v in envelope(request,state).items()),'producer terminal identity')
    if state=='SUCCEEDED':
        summaries=[];inventories=[]
        for cfg in request['configs']:
            check();node=cfg['binding']['node'];value,_=retained(base,request,node)
            summaries.append(dict(node=node,descriptorSha256=m.sha(m.canonical(value['bootstrap'])),transferSha256=m.sha(m.canonical(value))))
            inventories.append(value['bootstrap']['files'])
        m.need(receipt.get('exports')==summaries and all(v==inventories[0] for v in inventories),'producer shared source/export identity')
    check();return receipt


def produce(base,request,deadline,check):
    config=validate(request)[0];root=location(base);files.owned(root,os.getuid(),True)
    m.need(read(root/'request.json')==request,'producer original request changed')
    # Authenticate the original service configuration, never a relaxed root.
    # The derived directory is seed-only and cannot acquire daemon authority.
    if config['execution']==guest.NATIVE_EXECUTION:
        from .guest_native_session import preparation_deadline
        m.need(deadline==preparation_deadline(base,config),'producer original preparation deadline')
    package.verify(base,config['binding']['source'])
    m.need(m.sha((base/'manifest.json').read_bytes())==config['packageManifestSha256'],'guest package manifest changed')
    check();cell=root/'cell';cell.mkdir(mode=0o700)
    local=deepcopy(config);local['root']=str(cell)
    guest.seed_source(base,config,cell,lambda label,args:guest.run_setup(root,label,args,deadline))
    check()
    exports=root/'exports';exports.mkdir(mode=0o700);rows=[]
    for cfg in request['configs']:
        check();node=cfg['binding']['node'];folder=exports/node
        row=boot.export(cell,folder,cfg,producer_config=local)
        value=wire.describe(folder,row['descriptorSha256'],cfg);wire.check_archive(folder,value);check()
        for path in sorted(folder.rglob('*'),key=lambda p:len(p.parts),reverse=True):
            if path.is_dir():path.chmod(0o700);files.sync(path)
            else:
                path.chmod(0o600)
                with path.open('rb') as stream:os.fsync(stream.fileno())
        files.sync(folder);files.sync(exports)
        # Export is finished before these descriptors or the terminal receipt exist.
        files.publish(root/(node+'-descriptor.json'),value)
        rows.append(dict(row,transferSha256=m.sha(m.canonical(value))))
    return rows


def prepare(base,request,deadline,check):
    old=query(base,request,check)
    if old['state']!='NOT_FOUND':return old
    root=location(base)
    try:root.mkdir(mode=0o700)
    except FileExistsError:return query(base,request,check)
    files.sync(root.parent);files.publish(root/'request.json',request)
    try:
        exports=produce(base,request,deadline,check);check()
        receipt=envelope(request,'SUCCEEDED',exports=exports)
    except (Exception,KeyboardInterrupt) as error:
        receipt=envelope(request,'FAILED',error=dict(type=type(error).__name__,message=str(error)[:2000]))
    files.publish(root/'receipt.json',receipt);return query(base,request,check)


def observe(base,request,node,check):
    m.need(query(base,request,check)['state']=='SUCCEEDED','producer export not complete')
    value,_=retained(base,request,node);check();return value


def chunk(base,request,node,index,check):
    value=observe(base,request,node,check)
    m.need(type(index) is int and 0<=index<len(value['chunks']),'producer chunk index')
    row=value['chunks'][index];path=location(base)/'exports'/node/'parts'/row['part']
    part=files.read(path,os.getuid(),wire.parts.LIMITS['partBytes'])
    raw=part[row['offset']:row['offset']+row['bytes']]
    m.need(len(raw)==row['bytes'] and m.sha(raw)==row['sha256'],'producer chunk changed');check();return raw
