"""Phase 0 independent framing fixture, not a production codec."""
import base64
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import struct
import uuid

from .membership_model import need

ROOT=Path(__file__).resolve().parents[2]
CATALOG=ROOT/'docs/v5x/v5.3/format-catalog.json'


def catalog():return json.loads(CATALOG.read_text())


def canonical(value):return json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(',',':'),allow_nan=False).encode('ascii')


def parse_budget(body):
    depth=0;nodes=0
    for match in re.finditer(rb'"(?:\\.|[^"\\])*"|[{}\[\],:]|[^\s{}\[\],:"]+',body):
        token=match.group()
        if token in (b'{',b'['):depth+=1
        if token in (b'}',b']'):depth-=1
        if token not in (b'}',b']',b',',b':'):nodes+=1
        need(0<=depth<=16 and nodes<=65536,'parser depth/node budget')
    need(depth==0,'unbalanced JSON')


def check_type(value,spec,types):
    if isinstance(spec,str) and spec in types:return check_type(value,types[spec],types)
    if isinstance(spec,dict):
        if 'object' in spec:
            need(type(value) is dict and set(value)==set(spec['object']),'exact fields')
            for k,s in spec['object'].items():check_type(value[k],s,types)
        elif 'array' in spec:
            need(type(value) is list and spec['min']<=len(value)<=spec['max'],'array bound')
            for row in value:check_type(row,spec['array'],types)
        elif 'nullable' in spec:
            if value is not None:check_type(value,spec['nullable'],types)
        elif 'enum' in spec:need(type(value) is str and value in spec['enum'],'enum')
        else:raise ValueError('unknown schema')
        return
    if spec in ('counter','positive','port'):
        minimum=0 if spec=='counter' else 1;maximum=65535 if spec=='port' else 2**63-1
        need(type(value) is int and minimum<=value<=maximum,'integer range');return
    if spec=='bool':need(type(value) is bool,'boolean');return
    need(type(value) is str and value.isascii(),'ASCII string')
    if spec=='hash':need(re.fullmatch('[0-9a-f]{64}',value) is not None,'hash')
    elif spec=='uuid':
        try:valid=str(uuid.UUID(value))==value and uuid.UUID(value).int!=0
        except ValueError:valid=False
        need(valid,'uuid')
    elif spec in ('node','id'):need(re.fullmatch('[a-z0-9][a-z0-9._-]{0,'+str(63 if spec=='node' else 127)+'}',value) is not None,'identifier')
    elif spec=='host':
        need(1<=len(value)<=253,'host bound')
        if ':' in value or re.fullmatch('[0-9.]+',value):
            try:valid=str(ipaddress.ip_address(value))==value
            except ValueError:valid=False
        else:valid=all(re.fullmatch('[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',label) is not None for label in value.split('.'))
        need(valid,'canonical host')
    elif spec=='relative':need(0<len(value)<=256 and not value.startswith('/') and all(re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]*',p) and p not in ('.','..') for p in value.split('/')),'relative path')
    elif spec=='blob':
        need(len(value)<=((4194304+2)//3)*4,'blob bound')
        try:raw=base64.b64decode(value,validate=True)
        except Exception as e:raise ValueError('base64') from e
        need(base64.b64encode(raw).decode()==value and len(raw)<=4194304,'canonical base64')
    else:raise ValueError('unknown scalar '+spec)


def encode(family,name,value):
    c=catalog();need(family in ('records','wire'),'family');spec=c[family][name]
    check_type(value,spec['schema'],c['types']);body=canonical(value)
    need(0<len(body)<=spec['maximum']-48,'record capacity')
    prefix=struct.pack('>4sHHHHI',b'GSER' if family=='records' else b'GSRP',1,3,spec['id'],0,len(body))
    return prefix+hashlib.sha256(prefix+body).digest()+body


def decode(data,family,name,root=None):
    c=catalog();need(family in ('records','wire') and name in c[family],'family/kind');spec=c[family][name]
    need(type(data) is bytes and 48<len(data)<=spec['maximum'],'frame size')
    magic,major,minor,kind,flags,length=struct.unpack('>4sHHHHI',data[:16])
    need(magic==(b'GSER' if family=='records' else b'GSRP') and (major,minor)==(1,3),'protocol mismatch')
    need(kind==spec['id'] and flags==0 and length==len(data)-48,'kind/flags/length')
    need(hashlib.sha256(data[:16]+data[48:]).digest()==data[16:48],'checksum')
    parse_budget(data[48:])
    def object_pairs(rows):
        need(len(rows)==len({k for k,v in rows}),'duplicate key');return dict(rows)
    try:value=json.loads(data[48:].decode('ascii'),object_pairs_hook=object_pairs)
    except (UnicodeError,json.JSONDecodeError) as e:raise ValueError('invalid body') from e
    need(canonical(value)==data[48:],'noncanonical body');check_type(value,spec['schema'],c['types'])
    if root is not None:need(value.get('root')==root,'foreign root')
    return value


def sample(spec,types,serial=1):
    if isinstance(spec,str) and spec in types:return sample(types[spec],types,serial)
    if isinstance(spec,dict):
        if 'object' in spec:return {k:sample(s,types,serial) for k,s in spec['object'].items()}
        if 'array' in spec:return [sample(spec['array'],types,i+1) for i in range(spec['min'])]
        if 'nullable' in spec:return None
        if 'enum' in spec:return spec['enum'][0]
    return {'hash':f'{serial:064x}','uuid':str(uuid.UUID(int=serial)),'counter':0,'positive':1,'port':9000+serial,
            'node':f'node-{serial}','id':f'fixture-{serial}','host':f'node-{serial}.example','relative':f'part-{serial}.bin',
            'bool':False,'blob':''}[spec]


def independent_bytes(family,kind,value):
    """Fixture construction deliberately avoids struct and the encoder."""
    body=canonical(value);prefix=(b'GSER' if family=='records' else b'GSRP')
    prefix+=(1).to_bytes(2,'big')+(3).to_bytes(2,'big')+kind.to_bytes(2,'big')+bytes(2)+len(body).to_bytes(4,'big')
    digest=hashlib.new('sha256');digest.update(prefix);digest.update(body)
    return prefix+digest.digest()+body


def generate():
    c=catalog();fixtures=[];commands=[]
    for family in ('records','wire'):
        for name,spec in sorted(c[family].items()):
            value=sample(spec['schema'],c['types']);data=independent_bytes(family,spec['id'],value)
            fixtures.append(dict(family=family,name=name,value=value,hex=data.hex(),sha256=hashlib.sha256(data).hexdigest()))
    for name,spec in sorted(c['commands'].items()):
        if name=='DATA':continue  # The unchanged application codec owns those fixtures.
        value=None if name=='BARRIER' else sample({'object':spec},c['types'])
        raw=b'' if name=='BARRIER' else canonical(value)
        commands.append(dict(name=name,value=value,hex=raw.hex(),sha256=hashlib.sha256(raw).hexdigest()))
    prefix=b'GSRT'+bytes([1,0,0,0])+uuid.UUID(int=1).bytes+uuid.UUID(int=2).bytes+bytes.fromhex('03'*32)+(17).to_bytes(8,'big')
    token=prefix+hashlib.sha256(b'gse-replica-read-token/1\0'+prefix).digest()
    return dict(schema='gse-v53-byte-fixtures-v1',scope='syntax-only; identity/certificate semantics require separate protocol oracles',
                catalogSha256=hashlib.sha256(CATALOG.read_bytes()).hexdigest(),fixtures=fixtures,commandPayloads=commands,
                unchangedReadTokenV1=dict(hex=token.hex(),sha256=hashlib.sha256(token).hexdigest()))
