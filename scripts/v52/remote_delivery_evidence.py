"""Bind delivered inputs and prepared authority to actual collected evidence."""
from pathlib import Path
from . import remote_delivery_package as p
from .evidence import need,digest,encoded


def receipt(value,expected=None):
    need(type(value) is dict and set(value)=={'schema','execution','descriptor','descriptorSha256','process','receiverHost','answer'} and
         value['schema']=='gse-v52-receiver-bootstrap-v1' and value['execution']==p.EXECUTION,'delivery receipt fields')
    desc=p.descriptor(value['descriptor']);need(expected is None or desc==expected,'delivery receipt descriptor changed')
    need(value['descriptorSha256']==digest(encoded(desc)),'delivery receipt hash')
    p.c.validate_process(value['process'],desc['host']);p.host.validate_pin(value['receiverHost'])
    need(all(value['receiverHost'][k]==desc['host'][k] for k in ('bootId','uid')),'delivery receiver host changed')
    p.bootstrap_answer(value['answer'],desc);return value


def selection(binding):
    value=binding.get('remoteDelivery')
    need(type(value) is dict and set(value)=={'schema','execution','package','nodes'} and value['schema']=='gse-v52-delivered-receivers-v1' and
         value['execution']==p.EXECUTION and set(value['nodes'])==set(p.h.topology.NODES),'delivery retained selection')
    meta=p.validate(value['package'])
    need(meta.get('recovery')==p.scope.history(binding),'delivery history scope changed')
    need(meta['source']=={k:binding[k] for k in p.SOURCE_KEYS} and meta['mode']==binding['mode'] and
         meta['topology']==binding['remoteTopology'] and meta['artifacts']==binding['artifacts'] and
         meta['classes']=={k:v for k,v in binding['classes'].items() if not k.startswith('control-classes/')},'delivery final source/input binding')
    for node,row in value['nodes'].items():
        need(type(row) is dict and set(row)=={'descriptorSha256','receiptSha256'},'delivery node selection fields')
        for sha in row.values():p.c.hex_value(sha,64,'delivery selected digest')
    return value


def node_receipt(root,binding,node):
    chosen=selection(binding);value=receipt(p.c.read(Path(root)/(node+'-delivery.json'),p.c.REQUEST_BYTES));desc=value['descriptor']
    need(chosen['nodes'][node]==dict(descriptorSha256=value['descriptorSha256'],receiptSha256=digest(encoded(value))) and
         desc['node']==node and desc['package']==chosen['package'],'delivery selected receipt changed')
    need({k:value['answer'][k] for k in ('originalRoot','manifestSha256','genesisSha256')}==binding['remoteReceivers'][node],
         'delivery bootstrap authority binding');return value


def live(root,binding,node):
    root=Path(root);value=node_receipt(root,binding,node)
    need(str(root)==value['answer']['originalRoot'] and p.host.observe(root)==value['receiverHost'],'delivery live receiver replaced')
    p.installed(root,value['descriptor']['package']);return value


def validate(root,binding):
    root=Path(root);chosen=selection(binding);p.h.bundle.inventory(root)
    p.verify_archive(root/p.CAPSULE,chosen['package'])
    for name,sha in chosen['package']['artifacts'].items():need(p.h.bundle.sha_file(root/'artifacts'/name)==sha,'delivery collected artifact changed')
    for name,sha in chosen['package']['classes'].items():need(p.h.bundle.sha_file(root/name)==sha,'delivery collected helper changed')
    for node in p.h.topology.NODES:
        value=node_receipt(root,binding,node)
        config=p.c.read(root/(node+'-control/config.json'),p.c.REQUEST_BYTES)
        need(config['root']==value['answer']['originalRoot'] and all(config['host'][k]==value['receiverHost'][k] for k in ('uid','bootId')),
             'delivery service placement changed')
        preparation=p.c.read(root/(node+'-control/preparation.json'),p.c.REQUEST_BYTES)
        need(preparation['host']==value['receiverHost'],'delivery service receiver directory changed')
        need(p.h.bundle.sha_file(root/node/'genesis.gsr')==value['answer']['genesisSha256'],'delivery retained genesis changed')
    return dict(status='PASS',nodes=3,packageSha256=chosen['package']['sha256'])
