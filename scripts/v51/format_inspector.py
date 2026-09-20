"""Read-only independent byte/schema inspector. Does not import the fixture encoder."""
import base64
import hashlib
import json
import re
import struct
import uuid
from pathlib import Path

CATALOG=Path(__file__).resolve().parents[2]/'general-search-engine-replication/src/test/resources/replication/v51/format-catalog.json'
MAX_IMAGE=67108864
ZERO='00000000-0000-0000-0000-000000000000'


def need(test,message):
    if not test:raise ValueError(message)

def load():return json.loads(CATALOG.read_bytes())

def json_body(raw):
    def pairs(values):
        result={}
        for k,v in values:
            need(k not in result,'duplicate JSON key');result[k]=v
        return result
    value=json.loads(raw,object_pairs_hook=pairs)
    need(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')==raw,'canonical JSON')
    return value


def check_schema(t,v,depth=0):
    need(depth<=16,'schema depth')
    if isinstance(t,dict):
        if 'optional' in t:
            if v is not None:check_schema(t['optional'],v,depth+1)
        elif 'object' in t:
            need(type(v) is dict and set(v)==set(t['object']),'exact object fields')
            for k,schema in t['object'].items():check_schema(schema,v[k],depth+1)
        elif 'array' in t:
            need(type(v) is list and t['min']<=len(v)<=t['max'],'array bound')
            for item in v:check_schema(t['array'],item,depth+1)
        elif 'enum' in t:need(any(type(v) is type(x) and v==x for x in t['enum']),'enum value')
        elif 'integer' in t:need(type(v) is int and t['integer'][0]<=v<=t['integer'][1],'integer range')
        else:raise ValueError('unknown schema')
        return
    if t in ('positive','counter','u8'):
        need(type(v) is int and (1 if t=='positive' else 0)<=v<=(255 if t=='u8' else (1<<63)-1),'scalar integer');return
    if t=='bool':need(type(v) is bool,'boolean');return
    need(type(v) is str,'string scalar')
    if t=='hash':need(re.fullmatch('[0-9a-f]{64}',v),'hash')
    elif t=='uuid':need(str(uuid.UUID(v))==v,'canonical UUID')
    elif t in ('id','node'):need(re.fullmatch('[a-z0-9][a-z0-9._-]{0,'+('63' if t=='node' else '127')+'}',v),'identity')
    elif t in ('text','relative'):
        need(0<len(v.encode('utf-8'))<=4096 and '\0' not in v,'text bound')
        if t=='relative':need(not v.startswith('/') and all(s not in ('','.','..') for s in v.split('/')) and '\\' not in v,'relative path')
    elif t=='blob' or t.startswith('frame:'):
        raw=base64.b64decode(v,validate=True)
        need(len(raw)<=MAX_IMAGE and base64.b64encode(raw).decode()==v,'canonical base64/bound')
        if t.startswith('frame:'):inspect(raw,t[6:],depth=depth+1)
    else:raise ValueError('unknown scalar '+t)


class Reader:
    def __init__(self,raw):self.raw=raw;self.offset=0
    def take(self,n):
        need(0<=n<=len(self.raw)-self.offset,'truncated binary field')
        r=self.raw[self.offset:self.offset+n];self.offset+=n;return r
    def read(self,t):
        if isinstance(t,dict):
            if 'optional' in t:
                tag=self.take(1);need(tag in (b'\0',b'\1'),'optional discriminator')
                return None if tag==b'\0' else self.read(t['optional'])
            if 'array' in t:
                count=int.from_bytes(self.take(4),'big',signed=True);need(t['min']<=count<=t['max'],'binary count')
                return [self.read(t['array']) for _ in range(count)]
            if 'object' in t:return {k:self.read(s) for k,s in t['object'].items()}
            raise ValueError('unknown binary schema')
        if t=='hash':return self.take(32).hex()
        if t=='uuid':return str(uuid.UUID(bytes=self.take(16)))
        if t in ('positive','counter'):return int.from_bytes(self.take(8),'big',signed=True)
        if t=='u8':return self.take(1)[0]
        n=int.from_bytes(self.take(4),'big',signed=True);need(0<=n<=MAX_IMAGE,'binary byte bound');raw=self.take(n)
        return base64.b64encode(raw).decode() if t=='blob' or t.startswith('frame:') else raw.decode('utf-8','strict')


def inspect(raw,name,depth=0):
    need(depth<=16,'nested frame depth');spec=load()['records'][name]
    need(48<len(raw)<=spec['maximum'],'frame capacity')
    magic,major,minor,kind,flags,size=struct.unpack('>4sHHHHi',raw[:16])
    need((magic,major,minor,kind,flags)==(b'GSER',1,2,spec['id'],0),'storage version/kind/flags')
    need(size==len(raw)-48 and hashlib.sha256(raw[:16]+raw[48:]).digest()==raw[16:48],'frame length/digest')
    if spec['encoding']=='canonical-json':value=json_body(raw[48:])
    else:
        reader=Reader(raw[48:]);value={k:reader.read(t) for k,t in spec['fields']}
        need(reader.offset==len(reader.raw),'trailing fields')
    check_schema(spec['schema'],value,depth);semantics(name,value)
    return value


def ballot(epoch,proposer,incarnation):
    need((epoch==1 and proposer is None and incarnation==ZERO) or (epoch>1 and proposer is not None and incarnation!=ZERO),'ballot/genesis')

def receipt(domain,manifest,voter,epoch,proposer,incarnation,index,digest):
    def text(s):
        b=s.encode();return len(b).to_bytes(4,'big')+b
    raw=text('gse-replication/1.2/'+domain)+bytes.fromhex(manifest)+text(voter)+epoch.to_bytes(8,'big')+text(proposer)+uuid.UUID(incarnation).bytes+index.to_bytes(8,'big')+bytes.fromhex(digest)
    return hashlib.sha256(raw).hexdigest()

def semantics(name,v):
    if name in ('PROMISE','ACCEPT','PROOF'):ballot(v['epoch'],v['proposer'],v['incarnation'])
    if name=='MANIFEST':
        need(len({m['node'] for m in v['members']})==3 and len({(m['host'],m['port']) for m in v['members']})==3,'distinct voters/endpoints')
    if name=='ENTRY':
        need(v['originEpoch']>=2 and v['originIncarnation']!=ZERO and 1<=v['operation']<=10,'entry origin/op')
        need(v['previousIndex']==v['index']-1 and v['previousEpoch']<=v['originEpoch'],'entry predecessor')
        payload=base64.b64decode(v['payload']);need(hashlib.sha256(payload).hexdigest()==v['payloadDigest'],'payload digest')
        need(v['operation']<=8 or not payload,'control payload')
    if name=='ACCEPT':
        raw=base64.b64decode(v['entry']);e=inspect(raw,'ENTRY')
        need(v['manifestDigest']==e['manifestDigest'] and v['entryDigest']==raw[16:48].hex() and v['epoch']>=e['originEpoch'],'acceptance identity/origin')
    if name=='PROOF':
        voters=[r['voter'] for r in v['receipts']];need(voters==sorted(set(voters)),'distinct ordered receipt quorum')
        for r in v['receipts']:
            need(r['digest']==receipt('ACCEPT_ACK',v['manifestDigest'],r['voter'],v['epoch'],v['proposer'],v['incarnation'],v['index'],v['entryDigest']),'receipt domain')
    if name=='SNAPSHOT':
        need(v['applicationSequence']==v['baseSequence']+sum(a['operation']<=8 for a in v['anchors']),'application sequence')
        need(bool(v['anchors'])==(v['terminalProof'] is not None),'terminal proof presence')
        if v['terminalProof']:
            proof=inspect(base64.b64decode(v['terminalProof']),'PROOF');last=v['anchors'][-1]
            need(proof['manifestDigest']==v['manifestDigest'] and proof['index']==len(v['anchors']) and proof['entryDigest']==last['entryDigest'] and proof['epoch']>=last['originEpoch'],'snapshot terminal')
    if name=='SELECTED':
        need(len({x['node'] for x in v['bases']})==2,'selected basis quorum')
        need((v['nextEntry'] is None)==(v['sourceBallot'] is None),'selected optional pair')
    if name=='FLOOR':need(len({x['node'] for x in v['sources']})==2,'floor requires two recovery sources')
    if name=='TRANSFER':need(v['receivedBytes']<=v['imageBytes'],'transfer progress')
    if name=='PLAN':
        mraw=base64.b64decode(v['manifest']);m=inspect(mraw,'MANIFEST')
        graw=base64.b64decode(v['genesis']);g=inspect(graw,'GENESIS')
        need(m['genesisDigest']==graw[16:48].hex() and m['groupId']==g['groupId']
             and m['historyId']==g['historyId'] and m['baseSequence']==g['baseSequence'],'plan genesis binding')
        need([t['node'] for t in v['targets']]==[n['node'] for n in m['members']],'plan target order')
        paths=[t[p] for t in v['targets'] for p in ('authorityPath','materializationPath')]+[v['operationPath']]
        need(len(set(paths))==len(paths),'plan path collision')
        need((v['sourcePath'] is None)==(g['source']=='EMPTY'),'plan source')
        need(v['maxSourceBytes']<=1<<40 and v['maxOperationBytes']<=1<<40,'plan byte bounds')
        for target in v['targets']:
            b=target['bounds'];p=target['policy'];r=b['requestTimeoutMillis']
            ceilings=dict(maxFrameBytes=67108864,maxEntriesPerAppend=10000,maxInFlightPerPeer=4096,
                maxPendingClientOperations=100000,maxRetryAttempts=100,requestTimeoutMillis=300000,
                retryBackoffMillis=60000,snapshotChunkBytes=67108864,maxRetainedLogBytes=1<<40,maxSnapshotStagingBytes=1<<40)
            need(all(b[k]<=maximum for k,maximum in ceilings.items()),'plan replication bound')
            need(b['maxFrameBytes']>=131072 and b['maxInFlightPerPeer']>=2 and b['snapshotChunkBytes']>=4096,'automatic control capacity')
            need(r<=p['heartbeatIntervalMillis']<=300000 and p['minElectionTimeoutMillis']>=3*p['heartbeatIntervalMillis']
                 and p['minElectionTimeoutMillis']+p['heartbeatIntervalMillis']<=p['maxElectionTimeoutMillis']<=1500000
                 and 2*r<=p['operationTimeoutMillis']<=1200000,'plan leadership policy')
    if name=='RECEIPT':
        raw=base64.b64decode(v['plan']);plan=inspect(raw,'PLAN');mraw=base64.b64decode(plan['manifest'])
        preparations=[inspect(base64.b64decode(p),'PREPARED') for p in v['preparations']]
        need([p['node'] for p in preparations]==[t['node'] for t in plan['targets']],'receipt voter order')
        need(all(p['planDigest']==raw[16:48].hex() and p['manifestDigest']==mraw[16:48].hex() for p in preparations),'receipt plan binding')
    if name=='SEAL':
        receipt_value=inspect(base64.b64decode(v['receipt']),'RECEIPT')
        nodes=[inspect(base64.b64decode(p),'PREPARED')['node'] for p in receipt_value['preparations']]
        need(v['node'] in nodes,'seal voter')
    if name=='CLEANUP':
        paths=[f['path'] for f in v['files']];need(len(set(paths))==len(paths) and len(set(v['deletePaths']))==len(v['deletePaths']) and set(v['deletePaths'])<=set(paths),'cleanup inventory')


def contextual_frame(raw,name,manifest):
    """Bind structurally valid frames to a separately admitted manifest, including nested frames."""
    value=inspect(raw,name)
    nodes=[m['node'] for m in manifest['members']]
    if 'manifestDigest' in value:need(value['manifestDigest']==manifest['digest'],'nested manifest identity')
    if name in ('MANIFEST','GENESIS'):need(value['groupId']==manifest['groupId'],'group identity')
    if name=='MANIFEST':need(raw[16:48].hex()==manifest['digest'],'manifest bytes')
    if 'node' in value:need(value['node'] in nodes,'storage voter')
    def bound_ballot(epoch,proposer,incarnation):
        ballot(epoch,proposer,incarnation)
        if epoch>1:need(proposer==nodes[(epoch-2)%3],'storage ranked proposer')
    if name in ('PROMISE','ACCEPT','PROOF'):bound_ballot(value['epoch'],value['proposer'],value['incarnation'])
    if 'ballot' in value:
        b=value['ballot'];bound_ballot(b['epoch'],b['proposer'],b['incarnation'])
    if name=='PROOF':need(all(r['voter'] in nodes for r in value['receipts']),'proof voter membership')
    if name=='SELECTED':
        need(all(b['node'] in nodes for b in value['bases']) and value['ballot']['proposer'] in {b['node'] for b in value['bases']},'selected quorum identity')
    walk_context(load()['records'][name]['schema'],value,manifest)
    return value


def walk_context(schema,value,manifest):
    if isinstance(schema,dict):
        if 'optional' in schema and value is not None:walk_context(schema['optional'],value,manifest)
        elif 'object' in schema:
            for k,s in schema['object'].items():walk_context(s,value[k],manifest)
        elif 'array' in schema:
            for item in value:walk_context(schema['array'],item,manifest)
    elif schema.startswith('frame:'):contextual_frame(base64.b64decode(value),schema[6:],manifest)


def wire(raw,manifest):
    need(48<len(raw)<=MAX_IMAGE,'wire capacity')
    magic,major,minor,kind,flags,size=struct.unpack('>4sHHHHi',raw[:16]);catalog=load()
    spec=next((v for v in catalog['wire'].values() if v['id']==kind),None)
    need((magic,major,minor,flags)==(b'GSRP',1,2,0) and spec is not None,'wire version/kind')
    need(size==len(raw)-48 and hashlib.sha256(raw[:16]+raw[48:]).digest()==raw[16:48],'wire length/digest')
    value=json_body(raw[48:]);envelope=dict(value);payload=envelope.pop('payload',None)
    check_schema(catalog['envelope'],envelope);check_schema(spec['schema'],payload)
    walk_context(spec['schema'],payload,manifest)
    need(catalog['wire'][value['type']]['id']==kind,'wire type')
    need((value['groupId'],value['configurationId'],value['manifestDigest'])==(manifest['groupId'],manifest['configurationId'],manifest['digest']),'wire group/manifest')
    nodes=[m['node'] for m in manifest['members']]
    need(value['sender'] in nodes and value['recipient'] in nodes and value['sender']!=value['recipient'],'wire peers')
    ballot(value['epoch'],value['proposer'],value['incarnationId'])
    if value['epoch']>1:need(value['proposer']==nodes[(value['epoch']-2)%3],'wire ranked proposer')
    elif value['type'] not in ('HANDSHAKE','AUTHORITY_STATUS_PROBE','AUTHORITY_STATUS','REJECT'):raise ValueError('genesis authority message')
    requests={'PREPARE','ACCEPT','COMMIT_PROOF','HEARTBEAT','COMMIT_ADVANCE'}
    replies={'PROMISE','ACCEPT_ACK','COMMIT_PROOF_ACK','HEARTBEAT_ACK'}
    if value['type'] in requests:need(value['sender']==value['proposer'],'request proposer')
    if value['type'] in replies:need(value['recipient']==value['proposer'],'response proposer')
    if 'response' in payload:
        need(value['recipient' if payload['response'] else 'sender']==value['proposer'],'snapshot request/response proposer')
    if value['type'] in ('ACCEPT','COMMIT_PROOF'):
        field='acceptance' if value['type']=='ACCEPT' else 'proof'
        record=inspect(base64.b64decode(payload[field]),'ACCEPT' if field=='acceptance' else 'PROOF')
        need((record['epoch'],record['proposer'],record['incarnation'])==(value['epoch'],value['proposer'],value['incarnationId']),'nested ballot')
    if value['type']=='PROMISE':
        basis=inspect(base64.b64decode(payload['basis']),'BASIS');b=basis['ballot']
        need(basis['node']==value['sender'] and (b['epoch'],b['proposer'],b['incarnation'])==(value['epoch'],value['proposer'],value['incarnationId']),'promise basis sender/ballot')
    if value['type'] in ('ACCEPT_ACK','COMMIT_PROOF_ACK'):
        proof=value['type']=='COMMIT_PROOF_ACK';digest=payload['proofDigest' if proof else 'entryDigest']
        need(payload['receipt']==receipt('PROOF_ACK' if proof else 'ACCEPT_ACK',value['manifestDigest'],value['sender'],value['epoch'],value['proposer'],value['incarnationId'],payload['index'],digest),'wire receipt domain')
    if 'chunk' in payload:
        chunk=base64.b64decode(payload['chunk'])
        need(payload['chunkBytes']<=payload['maxChunkBytes'],'chunk bound')
        if payload['action']=='DATA':
            need(len(chunk)==payload['chunkBytes']>0 and hashlib.sha256(chunk).hexdigest()==payload['chunkDigest'],'chunk data/digest')
        elif payload['action']=='REQUEST':
            need(not chunk and payload['chunkBytes']==0 and payload['chunkDigest']==hashlib.sha256(b'').hexdigest(),'chunk request')
        else:need(not chunk and payload['chunkBytes']>0,'chunk acknowledgement')
    return value
