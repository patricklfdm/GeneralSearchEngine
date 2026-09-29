"""Bounded immutable bootstrap bytes; one consumed receiver, no source paths on wire.

Loaded only from an authenticated installed package. The caller enforces the
package's original boot-bound deadline on every connection and before receipts.
"""
import hashlib
import os
from pathlib import Path
import re
import tarfile
from . import guest_bootstrap as boot, cloud_guest as guest, remote_collection as parts
from . import performance_model as m, remote_command as c, guest_delivery_receiver as files

CHUNK_BYTES = 1 << 20
SOURCE_BYTES = 64 << 20
WIRE_BYTES = 65 << 20  # Existing gzip/tar headers plus the six bounded source files.
METADATA_BYTES = 64 << 10
SCHEMA = 'gse-v51-bootstrap-transfer-v1'


def validate(value):
    m.need(type(value) is dict and set(value)=={'schema','config','bootstrap','parts','chunks'} and value['schema']==SCHEMA,
           'source transfer fields')
    config=value['config'];guest.validate(config);seed=value['bootstrap'];manifest=value['parts']
    m.need(type(seed) is dict and set(seed)=={'schema','config','files','partsSha256'} and seed['schema']==boot.SCHEMA and
           seed['config']==config and seed['partsSha256']==m.sha(m.canonical(manifest)), 'source descriptor binding')
    members=seed['files'];m.need(type(members) is dict and set(members)==boot.expected_files(config),'source closed file set')
    for row in members.values():
        m.need(type(row) is dict and set(row)=={'bytes','sha256'} and type(row['bytes']) is int and
               0<=row['bytes']<=min(SOURCE_BYTES,parts.LIMITS['memberBytes']) and isinstance(row['sha256'],str) and
               re.fullmatch('[0-9a-f]{64}',row['sha256']), 'source file size/digest')
    m.need(sum(row['bytes'] for row in members.values())<=SOURCE_BYTES,'source expanded byte bound')
    parts.validate_manifest(manifest,m.sha(m.canonical(config)))
    m.need(manifest['compressedBytes']<=WIRE_BYTES,'source compressed byte bound')
    expected=[dict(part=row['name'],offset=offset,bytes=min(CHUNK_BYTES,row['bytes']-offset))
              for row in manifest['parts'] for offset in range(0,row['bytes'],CHUNK_BYTES)]
    chunks=value['chunks']
    m.need(type(chunks) is list and len(chunks)==len(expected)<=65,'source chunk count')
    for i,(chunk,row) in enumerate(zip(chunks,expected)):
        m.need(type(chunk) is dict and set(chunk)=={'index','part','offset','bytes','sha256'} and type(chunk['index']) is int and
               chunk['index']==i and type(chunk['offset']) is int and type(chunk['bytes']) is int and
               all(chunk[k]==v for k,v in row.items()) and isinstance(chunk['sha256'],str) and
               re.fullmatch('[0-9a-f]{64}',chunk['sha256']), 'source chunk identity/order')
    m.need(len(m.canonical(value))<=METADATA_BYTES,'source metadata bound')
    return value


def describe(folder, digest, config):
    folder=c.directory(folder);seed=boot.descriptor(folder,digest,config);manifest=c.read(folder/'parts/parts.json')
    m.need(manifest['compressedBytes']<=WIRE_BYTES,'source compressed byte bound')
    chunks=[]
    for row in manifest['parts']:
        path=folder/'parts'/row['name']
        m.need(path.is_file() and not path.is_symlink() and path.stat().st_size==row['bytes'],'source part type/size')
        whole=hashlib.sha256()
        with path.open('rb') as stream:
            offset=0
            while raw:=stream.read(CHUNK_BYTES):
                whole.update(raw);chunks.append(dict(index=len(chunks),part=row['name'],offset=offset,bytes=len(raw),sha256=m.sha(raw)))
                offset+=len(raw)
        m.need(whole.hexdigest()==row['sha256'],'source part digest')
    return validate(dict(schema=SCHEMA,config=config,bootstrap=seed,parts=manifest,chunks=chunks))


def location(base,config):
    guest.validate(config)
    return Path(base).parent/('source-transfer-'+config['mode'])
def read(path, maximum=METADATA_BYTES): return files.decode(files.read(path,os.getuid(),maximum))
def exists(path): return path.exists() or path.is_symlink()
def envelope(value,state,count=0,**extra):
    return dict(schema='gse-v51-bootstrap-transfer-receipt-v1',requestSha256=m.sha(m.canonical(value)),
                state=state,completedChunks=count,**extra)


def check_archive(folder,value):
    """Verify expanded bytes without writing or trusting archive member sizes."""
    expected=value['bootstrap']['files'];manifest=value['parts'];seen={}
    source=parts.PartsReader(folder/'parts',manifest['parts'])
    try:
        with tarfile.open(fileobj=source,mode='r|gz') as archive:
            for member in archive:
                m.need(member.isfile() and member.name not in seen and
                       (member.name==parts.INDEX and member.size<=METADATA_BYTES or
                        member.name in expected and member.size==expected[member.name]['bytes']), 'source expanded inventory/bound')
                sha=hashlib.sha256();remaining=member.size;index=b''
                with archive.extractfile(member) as stream:
                    while remaining:
                        data=stream.read(min(CHUNK_BYTES,remaining));m.need(data,'source truncated member')
                        remaining-=len(data);sha.update(data)
                        if member.name==parts.INDEX:index+=data
                if member.name==parts.INDEX:
                    m.need(sha.hexdigest()==manifest['memberIndexSha256'] and m.strict_json(index)==expected,'source index identity')
                else: m.need(sha.hexdigest()==expected[member.name]['sha256'],'source expanded member digest')
                seen[member.name]=True
    finally:source.close()
    m.need(set(seen)==set(expected)|{parts.INDEX},'source expanded file coverage')


def query(base,value,check):
    validate(value);check();root=location(base,value['config'])
    if not exists(root):return envelope(value,'NOT_FOUND')
    files.owned(root,os.getuid(),True)
    if not exists(root/'request.json'):return envelope(value,'UNCERTAIN')
    m.need(read(root/'request.json')==value,'source retained descriptor changed')
    for i,chunk in enumerate(value['chunks']):
        folder=root/('chunk-%04d'%i)
        if not exists(folder):return envelope(value,'RECEIVING',i)
        files.owned(folder,os.getuid(),True)
        if not exists(folder/'receipt.json'):return envelope(value,'UNCERTAIN',i)
        receipt=read(folder/'receipt.json')
        m.need(receipt['chunk']==chunk and receipt['state'] in ('SUCCEEDED','FAILED'),'source chunk receipt identity')
        if receipt['state']=='FAILED':return envelope(value,'FAILED',i,error=receipt['error'])
        raw=files.read(folder/'data.bin',os.getuid(),CHUNK_BYTES)
        m.need(len(raw)==chunk['bytes'] and m.sha(raw)==chunk['sha256'],'source retained chunk changed')
    count=len(value['chunks']);finish=root/'finish'
    if not exists(finish):return envelope(value,'READY',count)
    files.owned(finish,os.getuid(),True)
    if not exists(finish/'receipt.json'):return envelope(value,'UNCERTAIN',count)
    receipt=read(finish/'receipt.json')
    m.need(receipt['state'] in ('FAILED','SUCCEEDED') and all(receipt.get(k)==v for k,v in envelope(value,receipt['state'],count).items()),
           'source finish receipt identity')
    if receipt['state']=='SUCCEEDED':
        folder=root/'export'
        m.need(read(folder/'bootstrap.json')==value['bootstrap'] and read(folder/'parts/parts.json')==value['parts'],'source assembled metadata changed')
        m.need({p.name for p in (folder/'parts').iterdir()}=={'parts.json',*(p['name'] for p in value['parts']['parts'])},'source assembled part inventory')
        for row in value['parts']['parts']:
            raw=files.read(folder/'parts'/row['name'],os.getuid(),parts.LIMITS['partBytes'])
            m.need(len(raw)==row['bytes'] and m.sha(raw)==row['sha256'],'source assembled part changed')
        m.need(receipt.get('descriptorSha256')==m.sha(m.canonical(value['bootstrap'])),'source finished descriptor')
    check();return receipt


def begin(base,value,check):
    answer=query(base,value,check)
    if answer['state']!='NOT_FOUND':return answer
    root=location(base,value['config'])
    try:root.mkdir(mode=0o700)
    except FileExistsError:return query(base,value,check)
    files.sync(root.parent);files.publish(root/'request.json',value);return query(base,value,check)


def put(base,value,index,stream,check):
    m.need(type(index) is int and 0<=index<len(value['chunks']),'source chunk index')
    answer=query(base,value,check)
    if answer['state']!='RECEIVING' or answer['completedChunks']!=index:return answer
    root=location(base,value['config']);folder=root/('chunk-%04d'%index);chunk=value['chunks'][index]
    try:folder.mkdir(mode=0o700)
    except FileExistsError:return query(base,value,check)
    files.sync(root)
    try:
        raw=stream.read(chunk['bytes']+1);files.write(folder/'data.bin',raw)
        m.need(len(raw)==chunk['bytes'] and m.sha(raw)==chunk['sha256'],'source chunk digest/size')
        check();receipt=dict(chunk=chunk,state='SUCCEEDED')
    except Exception as error:receipt=dict(chunk=chunk,state='FAILED',error=dict(type=type(error).__name__,message=str(error)[:1000]))
    files.publish(folder/'receipt.json',receipt);return query(base,value,check)


def finish(base,value,check):
    answer=query(base,value,check)
    if answer['state']!='READY':return answer
    root=location(base,value['config'])
    try:(root/'finish').mkdir(mode=0o700)
    except FileExistsError:return query(base,value,check)
    files.sync(root)
    try:
        folder=root/'export';folder.mkdir(mode=0o700);(folder/'parts').mkdir(mode=0o700)
        for row in value['parts']['parts']:
            check();sha=hashlib.sha256()
            with os.fdopen(os.open(folder/'parts'/row['name'],os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as out:
                for chunk in (v for v in value['chunks'] if v['part']==row['name']):
                    check();raw=files.read(root/('chunk-%04d'%chunk['index'])/'data.bin',os.getuid(),CHUNK_BYTES)
                    m.need(len(raw)==chunk['bytes'] and m.sha(raw)==chunk['sha256'],'source assembly chunk changed')
                    out.write(raw);sha.update(raw)
                out.flush();os.fsync(out.fileno())
            m.need(sha.hexdigest()==row['sha256'],'source assembled digest')
        files.sync(folder/'parts');files.publish(folder/'parts/parts.json',value['parts']);files.publish(folder/'bootstrap.json',value['bootstrap'])
        check_archive(folder,value);check()
        receipt=envelope(value,'SUCCEEDED',len(value['chunks']),descriptorSha256=m.sha(m.canonical(value['bootstrap'])))
    except Exception as error:receipt=envelope(value,'FAILED',len(value['chunks']),error=dict(type=type(error).__name__,message=str(error)[:1000]))
    files.publish(root/'finish/receipt.json',receipt);return query(base,value,check)


def received(base,config,digest,check):
    root=location(base,config);value=read(root/'request.json')
    m.need(value['config']==config and m.sha(m.canonical(value['bootstrap']))==digest,'source installed request identity')
    m.need(query(base,value,check)['state']=='SUCCEEDED','source transfer not complete')
    return root/'export'
