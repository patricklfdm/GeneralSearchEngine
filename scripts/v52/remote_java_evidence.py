"""Portable Java bytes, host installations and actual JVM process correlation."""
from pathlib import Path
from . import remote_java_receiver as r,remote_command as c,remote_host_domains as domains
from .remote_host import validate_pin

SCHEMA='gse-v52-java-receivers-v1'
FILE='java-image.json'
ARCHIVE='java-runtime.tar.gz'


def selection(receipt):return dict(root=receipt['root'],descriptorSha256=receipt['descriptorSha256'])


def receipts(value,scope,binding):
    r.descriptor(value)
    r.p.need(type(scope) is dict and set(scope)=={'schema','descriptorSha256','nodes'} and scope['schema']==SCHEMA and
             type(scope['nodes']) is dict and set(scope['nodes'])=={'node-1','node-2','node-3'},'Java retained receiver binding')
    r.p.need(scope['descriptorSha256']==r.p.digest(r.p.encoded(value)) and
             all(binding.get(k)==v for k,v in value['source'].items()),'Java retained original source changed')
    roots=set();parents=set()
    for node,own in scope['nodes'].items():
        r.p.need(type(own) is dict and set(own)=={'schema','descriptorSha256','root','host','filesSha256','java'} and
                 own['schema']==r.RECEIPT and own['descriptorSha256']==scope['descriptorSha256'] and
                 own['filesSha256']==r.p.digest(r.p.encoded(value['files'])) and own['java']==value['source']['java'],
                 'Java retained installation')
        validate_pin(own['host']);r.selection(selection(own));path=Path(own['root'])
        domains.observed(binding,node,own['host']) if domains.validate(binding) is not None else None
        host=own['host'];key=(host['bootId'],host['uid'],str(path))
        r.p.need(path.name=='java-'+value['sha256'] and key not in roots,'Java retained installation root');roots.add(key)
        parent=tuple(host[k] for k in ('bootId','uid','parentDevice','parentInode'))
        r.p.need(parent not in parents,'Java shared receiver directory');parents.add(parent)
    return scope['nodes']


def process(value,identity,receipt,descriptor):
    c.validate_process(identity,receipt['host'])
    r.p.need(value==dict(schema='gse-v52-java-process-v1',process=identity,selection=selection(receipt),
        executable=str(Path(receipt['root'])/'files/bin/java'),executableSha256=descriptor['files']['bin/java']['sha256']),
        'Java retained process executable changed')


def validate(root,binding):
    root=Path(root);value=r.descriptor(c.read(root/FILE,r.MAX_MANIFEST))
    nodes=receipts(value,binding.get('remoteJava'),binding)
    r.verify_archive(root/ARCHIVE,value)
    for node,receipt in nodes.items():
        python=binding.get('remotePython',{}).get('nodes',{}).get(node)
        r.p.need(type(python) is dict and all(receipt['host'][k]==python['host'][k] for k in ('bootId','uid')),
                 'Java installed Python host changed')
    # The Python evidence driver checks every allowed generation and requires the
    # exact optional Java runtime field, then calls process() for each real JVM.
    return value,nodes
