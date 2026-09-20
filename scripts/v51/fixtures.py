"""Explicit fixture generation; validation never rewrites tracked expected bytes."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
from . import format_encoder as enc
from . import format_inspector as check

ROOT=enc.CATALOG.parent
UUID='11111111-1111-1111-1111-111111111111'
HASH='ab'*32
B64=lambda b:base64.b64encode(b).decode()


def fixture_receipt(domain,manifest,voter,epoch,proposer,incarnation,index,digest):
    import struct
    import uuid
    def text(s):raw=s.encode('utf-8');return struct.pack('>i',len(raw))+raw
    parts=[text('gse-replication/1.2/'+domain),bytes.fromhex(manifest),text(voter),
           struct.pack('>q',epoch),text(proposer),uuid.UUID(incarnation).bytes,
           struct.pack('>q',index),bytes.fromhex(digest)]
    return hashlib.sha256(b''.join(parts)).hexdigest()


def sample(schema,frames):
    if isinstance(schema,dict):
        if 'object' in schema:return {k:sample(v,frames) for k,v in schema['object'].items()}
        if 'optional' in schema:return None
        if 'array' in schema:return [sample(schema['array'],frames) for _ in range(schema['min'])]
        if 'enum' in schema:return schema['enum'][0]
        if 'integer' in schema:return schema['integer'][0]
    if schema.startswith('frame:'):return B64(frames[schema[6:]])
    return {'hash':HASH,'uuid':UUID,'node':'node-1','id':'fixture-v1','text':'/fixture/path',
            'relative':'file.gsr','positive':2,'counter':0,'u8':9,'blob':'','bool':False}[schema]


def generate():
    catalog=enc.catalog();frames={};values={}
    order=['GENESIS','MANIFEST','NODE','JOURNAL','PROMISE','ENTRY','ACCEPT','PROOF','READY','SNAPSHOT','IMAGE',
           'SELECTOR','GENERATION','FLOOR','REBUILDING','TRANSFER','STARTED','PLAN','PREPARED','RECEIPT','SEAL','DECISION','CLEANUP','BASIS','SELECTED']
    manifest_digest=None
    for name in order:
        value=sample(catalog['records'][name]['schema'],frames)
        if 'manifestDigest' in value:value['manifestDigest']=manifest_digest or HASH
        if name=='GENESIS':value['source']='EMPTY'
        if name=='MANIFEST':
            value['members']=[dict(node=f'node-{i}',host=f'node-{i}.invalid',port=19000+i) for i in (1,2,3)]
            value['genesisDigest']=frames['GENESIS'][16:48].hex()
        if name in ('PROMISE','ACCEPT','PROOF'):value.update(epoch=5,proposer='node-1',incarnation=UUID)
        if name=='ENTRY':
            value.update(originEpoch=2,originIncarnation=UUID,index=1,previousEpoch=1,previousIndex=0,
                         previousDigest=manifest_digest,payloadDigest=hashlib.sha256(b'').hexdigest())
        if name=='ACCEPT':value['entryDigest']=frames['ENTRY'][16:48].hex()
        if name=='PROOF':
            value.update(index=1,entryDigest=frames['ENTRY'][16:48].hex(),previousDigest=manifest_digest)
            # Independent fixture-side construction of the receipt preimage.
            def receipt(node):
                def text(s):b=s.encode();return len(b).to_bytes(4,'big')+b
                import uuid
                raw=text('gse-replication/1.2/ACCEPT_ACK')+bytes.fromhex(manifest_digest)+text(node)+(5).to_bytes(8,'big')+text('node-1')+uuid.UUID(UUID).bytes+(1).to_bytes(8,'big')+bytes.fromhex(value['entryDigest'])
                return hashlib.sha256(raw).hexdigest()
            value['receipts']=[dict(voter=n,digest=receipt(n)) for n in ('node-1','node-2')]
        if name=='SNAPSHOT':
            value['anchors']=[dict(originEpoch=2,originIncarnation=UUID,operation=9,entryDigest=frames['ENTRY'][16:48].hex(),payloadDigest=hashlib.sha256(b'').hexdigest())]
            value['terminalProof']=B64(frames['PROOF'])
        if name in ('TRANSFER','BASIS','SELECTED'):
            value['ballot']=dict(epoch=5,proposer='node-1',incarnation=UUID)
        if name=='FLOOR':
            for i,s in enumerate(value['sources']):s['node']=f'node-{i+1}'
        if name=='SELECTED':
            for i,b in enumerate(value['bases']):b['node']=f'node-{i+1}'
            value.update(prefixIndex=0,prefixDigest=manifest_digest,nextEntry=B64(frames['ENTRY']),sourceBallot=dict(epoch=2,proposer='node-1',incarnation=UUID))
        if name=='PLAN':
            for i,target in enumerate(value['targets'],1):
                target.update(node=f'node-{i}',authorityPath=f'/fixture/node-{i}',materializationPath=f'/fixture/app-{i}')
                target['policy']=dict(heartbeatIntervalMillis=5000,minElectionTimeoutMillis=15000,maxElectionTimeoutMillis=25000,operationTimeoutMillis=20000)
                target['bounds']=dict(maxFrameBytes=8388608,maxEntriesPerAppend=1000,maxInFlightPerPeer=256,maxPendingClientOperations=10000,maxRetryAttempts=12,requestTimeoutMillis=5000,retryBackoffMillis=250,snapshotChunkBytes=4194304,maxRetainedLogBytes=8589934592,maxSnapshotStagingBytes=17179869184)
        if name=='PREPARED':value['planDigest']=frames['PLAN'][16:48].hex()
        if name=='READY':value['genesisDigest']=frames['GENESIS'][16:48].hex()
        if name=='RECEIPT':
            preps=[]
            for i in (1,2,3):
                prep=dict(values['PREPARED'],node=f'node-{i}');preps.append(B64(enc.encode('PREPARED',prep)))
            value['preparations']=preps
        if name=='BASIS':
            value['imageDigest']=frames['IMAGE'][16:48].hex();value['imageBytes']=len(frames['IMAGE'])
        frames[name]=enc.encode(name,value);values[name]=value
        check.inspect(frames[name],name)
        if name=='MANIFEST':manifest_digest=frames[name][16:48].hex()
    manifest=dict(values['MANIFEST'],digest=manifest_digest)
    for name,raw in frames.items():check.contextual_frame(raw,name,manifest)
    envelope=dict(protocol='gse-replication/1.2',groupId=UUID,configurationId='fixture-v1',manifestDigest=manifest_digest,
                  sender='node-1',recipient='node-2',epoch=5,proposer='node-1',incarnationId=UUID,traceId=UUID,eventSequence=1)
    wires={}
    for name,spec in catalog['wire'].items():
        payload=sample(spec['schema'],frames)
        if 'promised' in payload:payload['promised']=dict(epoch=5,proposer='node-1',incarnation=UUID)
        if 'chunkDigest' in payload:payload['chunkDigest']=hashlib.sha256(base64.b64decode(payload['chunk'])).hexdigest()
        message_envelope=dict(envelope)
        if name in ('PROMISE','ACCEPT_ACK','COMMIT_PROOF_ACK','HEARTBEAT_ACK'):
            message_envelope.update(sender='node-2',recipient='node-1')
        if name=='PROMISE':
            basis=dict(values['BASIS'],node='node-2');payload['basis']=B64(enc.encode('BASIS',basis))
        if name=='ACCEPT_ACK':
            payload.update(index=1,entryDigest=frames['ENTRY'][16:48].hex())
            payload['receipt']=fixture_receipt('ACCEPT_ACK',manifest_digest,'node-2',5,'node-1',UUID,1,payload['entryDigest'])
        if name=='COMMIT_PROOF_ACK':
            payload.update(index=1,proofDigest=hashlib.sha256(frames['PROOF']).hexdigest())
            payload['receipt']=fixture_receipt('PROOF_ACK',manifest_digest,'node-2',5,'node-1',UUID,1,payload['proofDigest'])
        wires[name]=enc.wire(name,message_envelope,payload);check.wire(wires[name],manifest)
    return frames,wires,manifest


def write():
    frames,wires,manifest=generate()
    fixture={'schema':'gse-v51-format-fixtures-v1','manifest':manifest,
             'storage':{k:B64(v) for k,v in frames.items()},'wire':{k:B64(v) for k,v in wires.items()}}
    (ROOT/'format-fixtures.json').write_text(json.dumps(fixture,sort_keys=True,indent=2)+'\n')
    (ROOT/'fixtures.sha256').write_text(''.join(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()+'  '+n+'\n' for n in ('format-catalog.json','format-fixtures.json')))


def validate():
    lines=(ROOT/'fixtures.sha256').read_text().splitlines()
    check.need(len(lines)==2 and [line.split('  ')[-1] for line in lines]==['format-catalog.json','format-fixtures.json'],'checksum inventory')
    for line in lines:
        digest,name=line.split('  ');check.need(name in ('format-catalog.json','format-fixtures.json') and hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,'frozen fixture checksum')
    fixture=json.loads((ROOT/'format-fixtures.json').read_text());frames,wires,manifest=generate()
    check.need(fixture['manifest']==manifest,'manifest fixture')
    check.need(fixture['storage']=={k:B64(v) for k,v in frames.items()},'storage fixture drift')
    check.need(fixture['wire']=={k:B64(v) for k,v in wires.items()},'wire fixture drift')
    return dict(status='PASS',storageRecords=len(frames),wireMessages=len(wires),execution='independent-format-only')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['generate','validate']);a=p.parse_args()
    if a.command=='generate':write()
    else:print(json.dumps(validate()))
