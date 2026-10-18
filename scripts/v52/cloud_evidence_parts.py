"""Closed immutable JSON chunks for original native member evidence.

This is storage framing, never workload or admission proof. Every chunk is bound
to the complete original manifest and request; no partial manifest grants PASS.
"""
import base64
import hashlib
import math
from pathlib import Path
from . import cloud_authority as a,measurement_bundle as bundle
from .evidence import need,encoded,digest

SCHEMA='gse-v52-cloud-evidence-parts-v1'
CHUNK='gse-v52-cloud-evidence-chunk-v1'
PIECE=4<<20
MAX_FILES=256
MAX_TOTAL=54<<30  # Thirteen original bounded 4 GiB archives plus provenance.
MAX_PARTS=math.ceil(MAX_TOTAL/PIECE)+MAX_FILES


def validate(value,request):
    a.fields(value,'schema requestSha256 files parts totalBytes','evidence manifest')
    need(value['schema']==SCHEMA and value['requestSha256']==a.validate_request(request,domain=a.domain(request)),
         'V5.2 evidence manifest request')
    files=value['files'];parts=value['parts']
    need(type(files) is list and 0<len(files)<=MAX_FILES and type(parts) is list and 0<len(parts)<=MAX_PARTS,
         'V5.2 evidence file/part count')
    names=[];cursor=0;total=0
    for row in files:
        a.fields(row,'name bytes sha256 firstPart parts','evidence file');bundle.name(row['name']);names.append(row['name'])
        size=a.integer(row['bytes'],1,bundle.LIMITS['compressed']);a.hex_value(row['sha256'])
        need(type(row['firstPart']) is int and row['firstPart']==cursor and type(row['parts']) is int and
             row['parts']==math.ceil(size/PIECE),'V5.2 evidence file part coverage')
        remaining=size
        for index in range(cursor,cursor+row['parts']):
            need(index<len(parts),'V5.2 evidence missing part')
            part=parts[index];a.fields(part,'ordinal bytes sha256','evidence part');a.hex_value(part['sha256'])
            need(type(part['ordinal']) is int and part['ordinal']==index and type(part['bytes']) is int and
                 part['bytes']==min(PIECE,remaining),'V5.2 evidence original part order/size')
            remaining-=part['bytes']
        cursor+=row['parts'];total+=size
    need(names==sorted(set(names)) and cursor==len(parts),'V5.2 evidence duplicate/reordered/unreferenced file')
    need(not any(p.as_posix() in names for name in names for p in Path(name).parents),'V5.2 evidence file/directory collision')
    need(type(value['totalBytes']) is int and value['totalBytes']==total<=MAX_TOTAL and len(encoded(value))<=4<<20,
         'V5.2 evidence total/manifest bound')
    return value


def file(path):
    path=Path(path)
    need(not any(p.is_symlink() for p in (path,*path.parents)) and path.is_file() and path.stat().st_nlink==1 and
         0<path.stat().st_size<=bundle.LIMITS['compressed'],'V5.2 evidence original regular file')
    return path


def scan(paths,request):
    need(type(paths) is dict and 0<len(paths)<=MAX_FILES,'V5.2 evidence input inventory')
    files=[];parts=[];total=0
    for name,path in sorted(paths.items()):
        bundle.name(name);path=file(path);count=0;sha=hashlib.sha256();first=len(parts)
        with path.open('rb') as stream:
            while raw:=stream.read(PIECE):
                count+=len(raw);total+=len(raw);need(count<=bundle.LIMITS['compressed'] and total<=MAX_TOTAL and
                    len(parts)<MAX_PARTS,'V5.2 evidence expanded bound')
                sha.update(raw);parts.append(dict(ordinal=len(parts),bytes=len(raw),sha256=digest(raw)))
        need(count==path.stat().st_size,'V5.2 evidence original file changed')
        files.append(dict(name=name,bytes=count,sha256=sha.hexdigest(),firstPart=first,parts=len(parts)-first))
    return validate(dict(schema=SCHEMA,requestSha256=a.validate_request(request,domain=a.domain(request)),
        files=files,parts=parts,totalBytes=total),request)


def chunk(manifest,ordinal,raw):
    part=manifest['parts'][ordinal]
    need(len(raw)==part['bytes'] and digest(raw)==part['sha256'],'V5.2 evidence original chunk changed')
    return dict(schema=CHUNK,requestSha256=manifest['requestSha256'],manifestSha256=digest(encoded(manifest)),
        ordinal=ordinal,data=base64.b64encode(raw).decode('ascii'))


def decode(value,manifest,ordinal):
    a.fields(value,'schema requestSha256 manifestSha256 ordinal data','evidence chunk')
    a.integer(ordinal,0,len(manifest['parts'])-1);part=manifest['parts'][ordinal]
    need(value['schema']==CHUNK and value['requestSha256']==manifest['requestSha256'] and
         value['manifestSha256']==digest(encoded(manifest)) and type(value['ordinal']) is int and value['ordinal']==ordinal and
         type(value['data']) is str and len(value['data'])==4*math.ceil(part['bytes']/3),'V5.2 evidence chunk binding/bound')
    try:raw=base64.b64decode(value['data'],validate=True)
    except (ValueError,TypeError):raise ValueError('V5.2 evidence chunk encoding') from None
    need(base64.b64encode(raw).decode('ascii')==value['data'] and len(raw)==part['bytes'] and digest(raw)==part['sha256'],
         'V5.2 evidence chunk bytes changed')
    return raw


def chunks(paths,manifest):
    need(set(paths)=={r['name'] for r in manifest['files']},'V5.2 evidence original file inventory changed')
    for row in manifest['files']:
        path=file(paths[row['name']]);sha=hashlib.sha256()
        with path.open('rb') as stream:
            for ordinal in range(row['firstPart'],row['firstPart']+row['parts']):
                raw=stream.read(PIECE);sha.update(raw);yield ordinal,chunk(manifest,ordinal,raw)
            need(not stream.read(1) and sha.hexdigest()==row['sha256'],'V5.2 evidence original file changed')


def restore(manifest,request,read,output):
    """Use one selected manifest; unknown/missing chunks cannot fill another run."""
    validate(manifest,request);output=Path(output)
    need(not any(p.is_symlink() for p in (output,*output.parents)),'V5.2 evidence restore symlink')
    output.mkdir(parents=True,exist_ok=False)
    for row in manifest['files']:
        path=output/row['name'];path.parent.mkdir(parents=True,exist_ok=True);sha=hashlib.sha256()
        with path.open('xb') as stream:
            for ordinal in range(row['firstPart'],row['firstPart']+row['parts']):
                raw=decode(read(ordinal),manifest,ordinal);stream.write(raw);sha.update(raw)
        need(path.stat().st_size==row['bytes'] and sha.hexdigest()==row['sha256'],'V5.2 restored original file hash')
    return output
