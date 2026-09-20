"""Fixture encoder from the reviewed declarative catalog; no product-format imports."""
import base64
import hashlib
import json
import struct
import uuid
from pathlib import Path

CATALOG=Path(__file__).resolve().parents[2]/'general-search-engine-replication/src/test/resources/replication/v51/format-catalog.json'


def catalog():return json.loads(CATALOG.read_text())
def runtime_catalog():
    value=catalog();extension=json.loads((CATALOG.parent/'runtime-wire-extension.json').read_text())
    value['wire'].update(extension['wire']);value['envelope']['object']['type']['enum']+=list(extension['wire'])
    return value
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')
def frame(kind,body,magic=b'GSER',minor=2):
    header=struct.pack('>4sHHHHi',magic,1,minor,kind,0,len(body))
    return header+hashlib.sha256(header+body).digest()+body

def scalar(schema,value):
    if isinstance(schema,dict):
        if 'optional' in schema:return b'\0' if value is None else b'\1'+scalar(schema['optional'],value)
        if 'array' in schema:return struct.pack('>i',len(value))+b''.join(scalar(schema['array'],v) for v in value)
        if 'object' in schema:return b''.join(scalar(t,value[n]) for n,t in schema['object'].items())
        raise ValueError('unsupported binary schema')
    if schema=='hash':return bytes.fromhex(value)
    if schema=='uuid':return uuid.UUID(value).bytes
    if schema in ('positive','counter'):return struct.pack('>q',value)
    if schema=='u8':return struct.pack('>B',value)
    raw=base64.b64decode(value,validate=True) if schema=='blob' or schema.startswith('frame:') else value.encode('utf-8')
    return struct.pack('>i',len(raw))+raw

def encode(name,value):
    spec=catalog()['records'][name]
    body=canonical(value) if spec['encoding']=='canonical-json' else b''.join(scalar(t,value[n]) for n,t in spec['fields'])
    return frame(spec['id'],body)

def wire(name,envelope,payload):
    value=dict(envelope,type=name,payload=payload)
    return frame(runtime_catalog()['wire'][name]['id'],canonical(value),b'GSRP')
