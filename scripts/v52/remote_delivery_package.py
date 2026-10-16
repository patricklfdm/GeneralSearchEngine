"""Closed JAR/helper/seed capsule for untimed and frozen M04 loopback receivers."""
from copy import deepcopy
import hashlib
from pathlib import Path
import shutil
import tarfile
from . import remote_history as h,remote_command as c,remote_host as host
from . import remote_voter_scope as scope
from .evidence import need,encoded,digest,strict

SCHEMA='gse-v52-receiver-package-v1'
EXECUTION='loopback-ssh-receiver-delivery-only'
CAPSULE='delivery-package.tar.gz'
PART=32<<10
MAX_BYTES=32<<20
MAX_FILES=512
SOURCE_KEYS=('source','checkoutSha256','java')
SEED={'control/seed/gse-backup-manifest','control/seed/gse-backup-checkpoint','control/seed/gse-backup-metadata'}


def validate(meta):
    need(type(meta) is dict and set(meta)=={'schema','source','mode','topology','artifacts','classes','members','bytes','sha256','parts'} |
         ({'recovery'} if 'recovery' in meta else set()),'delivery package fields')
    if 'recovery' in meta:
        scope.profile(meta['recovery']);need(meta['mode']=='candidate-minimum','delivery recovery mode')
    need(meta['schema']==SCHEMA and meta['mode'] in h.runtime.model.MODES,'delivery package scope')
    source=meta['source'];need(type(source) is dict and set(source)==set(SOURCE_KEYS),'delivery source fields')
    c.hex_value(source['source'],40,'delivery source');c.hex_value(source['checkoutSha256'],64,'delivery checkout')
    need(type(source['java']) is dict and set(source['java'])=={'java.runtime.version','java.vendor'} and
         all(type(v) is str and 0<len(v)<=256 for v in source['java'].values()),'delivery Java binding')
    need(h.topology.validate(meta['topology'])['placement']=='local-no-gcp','delivery remote host scope')
    need(type(meta['bytes']) is int and 0<meta['bytes']<=MAX_BYTES,'delivery archive bound');c.hex_value(meta['sha256'],64,'delivery archive hash')
    members=meta['members'];total=h.bundle.validate_index(members)
    need(0<len(members)<=MAX_FILES and total<=MAX_BYTES and len(encoded(meta))+1<=c.REQUEST_BYTES,'delivery manifest bound')
    for kind in ('artifacts','classes'):
        rows=meta[kind];need(type(rows) is dict and rows,'delivery missing '+kind)
        for name,sha in rows.items():
            h.bundle.name(name);c.hex_value(sha,64,'delivery file hash')
            if kind=='artifacts':need('/' not in name and name.endswith('.jar'),'delivery artifact path');name='artifacts/'+name
            else:need(name.startswith(('consumer/','observer/')) and name.endswith('.class'),'delivery helper path')
            need(name in members and members[name]['sha256']==sha,'delivery input hash binding')
    expected={'artifacts/'+n for n in meta['artifacts']}|set(meta['classes'])|SEED|{h.topology.FILE}
    if 'recovery' in meta:expected.add(h.recovery.FILE)
    need(set(members)==expected,'delivery closed file inventory')
    parts=meta['parts'];need(type(parts) is list and len(parts)==(meta['bytes']+PART-1)//PART,'delivery part count')
    for i,row in enumerate(parts):
        need(type(row) is dict and set(row)=={'bytes','sha256'} and type(row['bytes']) is int and
             row['bytes']==min(PART,meta['bytes']-i*PART),'delivery part length');c.hex_value(row['sha256'],64,'delivery part hash')
    return meta


def create(producer,target,binding):
    target=Path(target);target.mkdir();stage=target/'files';stage.mkdir()
    recovery=scope.history(binding)
    for name in ('artifacts','consumer','observer'):shutil.copytree(Path(producer)/name,stage/name)
    shutil.copytree(Path(producer)/'control/seed',stage/'control/seed')
    if recovery:
        need(c.read(Path(producer)/h.recovery.FILE)==recovery['faultParameters'],'delivery recovery parameters')
        shutil.copyfile(Path(producer)/h.recovery.FILE,stage/h.recovery.FILE)
    h.runtime.save(stage/h.topology.FILE,binding['remoteTopology']);archive=target/CAPSULE
    members=h.bundle.pack(stage,archive);parts=[]
    with archive.open('rb') as stream:
        while raw:=stream.read(PART):parts.append(dict(bytes=len(raw),sha256=digest(raw)))
    meta=dict(schema=SCHEMA,source={k:deepcopy(binding[k]) for k in SOURCE_KEYS},mode=binding['mode'],
        topology=deepcopy(binding['remoteTopology']),artifacts=deepcopy(binding['artifacts']),
        classes={k:v for k,v in binding['classes'].items() if not k.startswith('control-classes/')},members=members,
        bytes=archive.stat().st_size,sha256=h.bundle.sha_file(archive),parts=parts)
    if recovery:meta['recovery']=recovery
    validate(meta);verify_archive(archive,meta);return archive,meta


def verify_archive(archive,meta):
    """Stream bounded regular USTAR members before any destination is created."""
    validate(meta);archive=Path(archive)
    need(archive.is_file() and not archive.is_symlink() and archive.stat().st_size==meta['bytes'] and
         h.bundle.sha_file(archive)==meta['sha256'],'delivery archive bytes changed')
    seen=set();files=set();directories=0
    with tarfile.open(archive,'r|gz',tarinfo=h.bundle.ClosedTarInfo,encoding='ascii',errors='strict') as source:
        first=source.next()
        need(first is not None and first.name==h.bundle.INDEX and first.isfile() and 0<first.size<=c.REQUEST_BYTES,'delivery first inventory')
        with source.extractfile(first) as incoming:raw=incoming.read(c.REQUEST_BYTES+1)
        need(len(raw)==first.size and strict(raw)==meta['members'],'delivery archive inventory mismatch')
        seen.add(h.bundle.INDEX)
        for item in source:
            # Streaming TarFile iteration yields first again after next().
            if item is first:continue
            name=h.bundle.name(item.name);need(name not in seen and not item.pax_headers and item.sparse is None,'delivery duplicate/extended member');seen.add(name)
            if item.isdir():
                directories+=1;need(item.size==0 and directories<=128 and any(n.startswith(name+'/') for n in meta['members']),
                    'delivery directory bound/path');continue
            need(item.isfile() and name in meta['members'] and item.size==meta['members'][name]['bytes'],'delivery unlisted/changed member')
            sha=hashlib.sha256()
            with source.extractfile(item) as incoming:
                while raw:=incoming.read(64<<10):sha.update(raw)
            need(sha.hexdigest()==meta['members'][name]['sha256'],'delivery member hash');files.add(name)
    need(files==set(meta['members']),'delivery missing archive member')
    return meta


def installed(root,meta):
    root=Path(root)
    for name,row in meta['members'].items():
        path=root/name;c.directory(path.parent)
        need(path.is_file() and not path.is_symlink() and path.stat().st_size==row['bytes'] and
             h.bundle.sha_file(path)==row['sha256'],'delivery installed input changed')
    need(h.topology.read(root)==meta['topology'],'delivery installed topology changed')
    if 'recovery' in meta:
        need(c.read(root/h.recovery.FILE)==meta['recovery']['faultParameters'],'delivery installed recovery parameters')


def descriptor(value):
    need(type(value) is dict and set(value)=={'schema','execution','parent','host','node','session','package'},'delivery descriptor fields')
    need(value['schema']=='gse-v52-receiver-delivery-v1' and value['execution']==EXECUTION and value['node'] in h.topology.NODES,'delivery descriptor scope')
    host.path(value['parent']);host.validate_pin(value['host']);c.hex_value(value['session'],32,'delivery session');validate(value['package'])
    need(len(encoded(value))+1<=c.REQUEST_BYTES,'delivery descriptor bound');return value


def check(value,*,source=True):
    descriptor(value);parent=host.path(value['parent'])
    need(host.observe(parent)==value['host'],'delivery host changed')
    if source:need(h.source()==value['package']['source'],'delivery source changed')
    return parent


def bootstrap_answer(answer,value):
    descriptor(value);meta=value['package'];root=Path(value['parent'])/value['node']
    need(type(answer) is dict and set(answer)=={'status','node','originalRoot','topology','manifestSha256','genesisSha256','coreSource','replicationSource'} and
         answer['status']=='PREPARED_NOT_STARTED' and answer['node']==value['node'] and answer['originalRoot']==str(root) and
         answer['topology']==meta['topology'],'delivery bootstrap identity')
    for name in ('manifestSha256','genesisSha256'):c.hex_value(answer[name],64,'delivery authority digest')
    for component,stem in (('core','general-search-engine-'),('replication','general-search-engine-replication-')):
        path=Path(answer[component+'Source'])
        need(path.parent==root/'artifacts' and path.name in meta['artifacts'] and path.name.startswith(stem) and
             (component!='core' or not path.name.startswith('general-search-engine-replication-')) and
             not path.name.endswith('-4.4.0.jar'),'delivery bootstrap loaded artifact')
    return answer
