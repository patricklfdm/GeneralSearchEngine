"""Retained installed-source bindings, independent of original filesystem paths."""
from pathlib import Path
from . import remote_python_receiver as r, remote_command as c
from .remote_host import validate_pin

SCHEMA='gse-v52-python-receivers-v1'
FILE='python-capsule.json'
PAYLOAD='python-capsule-payload.json'


def runtime(value,receipt,source,process,entry):
    r.need(type(value) is dict and set(value)=={'schema','selection','source','installation','process','isolated','noSite'} and
           value['schema']=='gse-v52-python-runtime-v1' and value['selection']==dict(root=receipt['root'],descriptorSha256=receipt['descriptorSha256']) and
           value['source']==source and value['installation']==receipt and value['process']==dict(pid=process['pid'],entry='gse-v52-'+entry) and
           value['isolated'] is True and value['noSite'] is True,'Python retained runtime identity')


def validate(root,binding):
    root=Path(root);scope=binding.get('remotePython')
    r.need(type(scope) is dict and set(scope)=={'schema','descriptorSha256','nodes'} and scope['schema']==SCHEMA and
           set(scope['nodes'])=={'node-1','node-2','node-3'},'Python retained receiver binding')
    value=r.descriptor(c.read(root/FILE,r.MAX_MANIFEST))
    r.need(r.digest(r.encoded(value))==scope['descriptorSha256'] and
           all(binding[k]==v for k,v in value['source'].items()),'Python retained source changed')
    payload=root/PAYLOAD
    r.need(payload.is_file() and not payload.is_symlink() and payload.stat().st_size==value['bytes'],'Python retained payload length/type')
    r.payload(payload.read_bytes(),value)
    roots=set();parents=set()
    for node,receipt in scope['nodes'].items():
        r.need(type(receipt) is dict and set(receipt)=={'schema','descriptorSha256','root','host','filesSha256'} and
               receipt['schema']==r.RECEIPT and receipt['descriptorSha256']==scope['descriptorSha256'] and
               receipt['filesSha256']==r.digest(r.encoded(value['files'])),'Python retained installation')
        path=Path(receipt['root'])
        r.need(path.is_absolute() and '..' not in path.parts and path.name=='python-'+value['sha256'] and
               str(path) not in roots,'Python retained installation root');roots.add(str(path))
        validate_pin(receipt['host'])
        parent=tuple(receipt['host'][k] for k in ('bootId','uid','parentDevice','parentInode'))
        r.need(parent not in parents,'Python shared receiver directory');parents.add(parent)
        delivery=c.read(root/(node+'-delivery.json'),c.REQUEST_BYTES)
        host=delivery['receiverHost']
        r.need(all(receipt['host'][k]==host[k] for k in ('bootId','uid')),'Python receiver host changed')
        runtime(c.read(root/(node+'-python-bootstrap.json')),receipt,value['source'],delivery['process'],'delivery')
        controls=sorted(root.glob(node+'-control*'))
        allowed={node+'-control'}|({node+'-control-g2'} if 'remoteRestart' in binding else set())
        r.need(node+'-control' in {p.name for p in controls} and all(p.is_dir() and p.name in allowed for p in controls),
               'Python retained control generations')
        for control in controls:
            identity=c.read(control/'identity.json')
            runtime(c.read(control/'python-runtime.json'),receipt,value['source'],identity['service'],'voter')
    return dict(status='PASS',execution='retained-python-source-bindings-only',nodes=3,
                descriptorSha256=scope['descriptorSha256'],fullRemoteQualification=False,paidCloud=False)
