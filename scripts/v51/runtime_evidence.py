"""Independent wire/force/application oracle for three concurrent internal runtimes."""
import base64
import json
import struct
from pathlib import Path
from . import format_inspector as f, storage_inspector as storage, recovery_inspector as recovery


def raw(value):return base64.b64decode(value,validate=True)
def frame(value,kind,manifest):return f.contextual_frame(raw(value),kind,manifest)


def application(data):
    offset=0
    def take(size):
        nonlocal offset
        f.need(0<=size<=len(data)-offset,'application size');value=data[offset:offset+size];offset+=size;return value
    def integer():return struct.unpack('>i',take(4))[0]
    def blob():return take(integer())
    f.need(take(2)==b'\x00\x01','application version')
    indexes=[json.loads(blob()) for _ in range(integer())]
    documents={}
    for _ in range(integer()):
        key=struct.unpack('>i',blob())[0];doc=blob();f.need(len(doc)>=4 and struct.unpack('>i',doc[:4])[0]==key and key not in documents,'application key')
        documents[key]=doc[4:].decode('utf-8')
    f.need(offset==len(data),'application trailing data');return indexes,documents


def command(data):
    values=documents_command(data);f.need(len(values)==1,'single command count');return values[0]


def documents_command(data):
    f.need(len(data)>=6 and data[:2]==b'\x00\x01','command header')
    count=struct.unpack('>i',data[2:6])[0];f.need(0<count<=100,'command count');offset=6;values=[]
    for _ in range(count):
        f.need(len(data)-offset>=12,'command item header')
        key_bytes,key,size=struct.unpack('>iii',data[offset:offset+12]);offset+=12
        f.need(key_bytes==4 and 4<=size<=len(data)-offset,'command item size')
        doc=data[offset:offset+size];offset+=size
        f.need(struct.unpack('>i',doc[:4])[0]==key and key not in dict(values),'command document identity')
        values.append((key,doc[4:].decode('utf-8')))
    f.need(offset==len(data),'command trailing data');return values


def validate(root,traces=None,*,rejected_tails=None,retired_voters=None,evidence_location=None):
    root=Path(root);encoded=(root/'node-1/manifest.gsr').read_bytes();manifest=dict(f.inspect(encoded,'MANIFEST'),digest=encoded[16:48].hex())
    genesis=f.inspect((root/'node-1/genesis.gsr').read_bytes(),'GENESIS');indexes,initial=application(raw(genesis['application']))
    nodes={row['node'] for row in manifest['members']};rejected_tails=rejected_tails or {}
    f.need(len(rejected_tails)<=1 and set(rejected_tails)<=nodes,'only one explicitly witnessed torn voter may be excluded')
    quarantined={node:storage.torn_append(root/node,witness) for node,witness in rejected_tails.items()}
    retired_voters=retired_voters or {}
    f.need(len(retired_voters)<=2 and set(retired_voters)<=nodes and not set(retired_voters)&set(rejected_tails), 'invalid retired voters')
    f.need(evidence_location is None or (not retired_voters and not rejected_tails), 'relocated fault inventory unsupported')
    inspect=evidence_location.inspect if evidence_location is not None else storage.inspect
    reports={node:(storage.inspect_archive(root/'lost'/node,root/node,retired_voters[node])
                   if node in retired_voters else inspect(root/node)) for node in nodes-set(rejected_tails)}
    traces=traces if traces is not None else {node:[json.loads(line) for line in (root/(node+'-trace.jsonl')).read_text().splitlines()] for node in nodes}
    f.need(set(traces)==nodes and all(traces.values()),'incomplete voter traces')
    f.need(all(witness in traces[node] and witness['event']=='PARTIAL_WRITE_FAILURE' for node,witness in rejected_tails.items()),'unobserved quarantined append')
    entries={};accepted={};chosen={};reply_frames=set();pids=set();basis_bytes={};parts={};selections={}
    for node,rows in traces.items():
        for row in rows:
            pids.add(row['pid'])
            if row['event']=='REPLY':reply_frames.add(storage.sha(raw(row['frame'])))
            if row['event'] in ('REPLY','RECEIVED'):
                message=f.wire(raw(row['frame']),manifest);payload=message['payload']
                for encoded in ([payload['basis']] if message['type']=='PROMISE' else payload['bases'] if message['type']=='SELECTED_OFFER' else []):
                    basis=frame(encoded,'BASIS',manifest);key=basis['node'],basis['basisId']
                    f.need(key not in basis_bytes or basis_bytes[key]==raw(encoded),'changed frozen basis');basis_bytes[key]=raw(encoded)
                if message['type']=='BASIS_CHUNK' and payload['action']=='DATA':
                    key=message['sender'],payload['basisId'];ranges=parts.setdefault(key,{})
                    f.need(payload['offset'] not in ranges or ranges[payload['offset']]==raw(payload['chunk']),'changed basis retry');ranges[payload['offset']]=raw(payload['chunk'])
                if message['type']=='SELECTED_OFFER' and payload['response']:
                    selected=frame(payload['selected'],'SELECTED',manifest);selections[(selected['ballot']['epoch'],selected['ballot']['incarnation'])]=selected
            if row['event']=='FORCE' and row['kind']=='ACCEPT':
                vote=frame(row['record'],'ACCEPT',manifest);entry=frame(vote['entry'],'ENTRY',manifest);digest=raw(vote['entry'])[16:48].hex();entries[digest]=entry
                voters=accepted.setdefault((vote['epoch'],vote['incarnation'],entry['index'],digest),set());voters.add(node)
                if len(voters)>=2:
                    f.need(entry['index'] not in chosen or chosen[entry['index']]==digest,'conflicting chosen value');chosen[entry['index']]=digest
    f.need(len(pids)>=4,'three runtime JVMs and retained-disk restart required')
    for selected in selections.values():
        bases=[]
        for binding in selected['bases']:
            key=binding['node'],binding['basisId'];f.need(key in basis_bytes and key in parts,'selection lacks transferred basis')
            chunks=parts[key];image=b''
            for offset,chunk in sorted(chunks.items()):f.need(offset==len(image),'basis transfer hole');image+=chunk
            f.need(basis_bytes[key][16:48].hex()==binding['basisDigest'],'selected descriptor digest')
            bases.append(recovery.basis(basis_bytes[key],image,manifest))
        recovery.select(selected,bases,manifest)
    publications=successes=chunks=0
    for node,rows in traces.items():
        forced=set();votes=set();received=set();published={};previous={};received_votes=set()
        for row in rows:
            pid=row['pid'];f.need(row['order']>previous.get(pid,0),'process trace order');previous[pid]=row['order']
            event=row['event']
            if event=='FORCE':
                value=frame(row['record'],row['kind'],manifest);forced.add((row['kind'],storage.sha(raw(row['record']))))
                if row['kind']=='ACCEPT':
                    entry=frame(value['entry'],'ENTRY',manifest);votes.add((value['epoch'],value['incarnation'],entry['index'],value['entryDigest']))
                if row['kind']=='PROOF':
                    f.need(chosen.get(value['index'])==value['entryDigest'],'proof value lacks entry quorum')
                    if value['proposer']==node:f.need(any((r['voter'],value['epoch'],value['incarnation'],value['index'],value['entryDigest']) in received_votes for r in value['receipts'] if r['voter']!=node),'leader proof before remote acceptance')
            elif event in ('REPLY','RECEIVED'):
                value=f.wire(raw(row['frame']),manifest);payload=value['payload'];kind=value['type']
                if event=='RECEIVED':
                    request=f.wire(raw(row['request']),manifest)
                    f.need(all(request[k]==value[k] for k in ('traceId','eventSequence','epoch','incarnationId','proposer')) and request['sender']==value['recipient'] and request['recipient']==value['sender'],'wire reply correlation')
                    f.need(storage.sha(raw(row['frame'])) in reply_frames,'unobserved responder')
                    if kind=='COMMIT_PROOF_ACK':received.add(payload['proofDigest'])
                    if kind=='ACCEPT_ACK':received_votes.add((value['sender'],value['epoch'],value['incarnationId'],payload['index'],payload['entryDigest']))
                elif kind in ('ACCEPT_ACK','COMMIT_PROOF_ACK'):
                    record_kind='ACCEPT' if kind=='ACCEPT_ACK' else 'PROOF'
                    f.need(any(k==record_kind for k,_ in forced),'receipt before any force')
                    if kind=='COMMIT_PROOF_ACK':f.need(('PROOF',payload['proofDigest']) in forced,'proof receipt before exact force')
                    else:f.need((value['epoch'],value['incarnationId'],payload['index'],payload['entryDigest']) in votes,'accept receipt before exact force')
                if kind=='BASIS_CHUNK' and payload['action']=='DATA':chunks+=1
            elif event=='PUBLISHED':
                snapshot=frame(row['snapshot'],'SNAPSHOT',manifest);proof=frame(snapshot['terminalProof'],'PROOF',manifest);digest=storage.sha(raw(snapshot['terminalProof']))
                f.need(('PROOF',digest) in forced and digest in received,'publication before local proof/remote ACK')
                f.need((proof['epoch'],proof['incarnation']) in selections,'publication without verified selected quorum')
                projection=dict(initial);sequence=genesis['baseSequence']
                for index,anchor in enumerate(snapshot['anchors'],1):
                    f.need(chosen.get(index)==anchor['entryDigest'],'unobserved publication ancestor');entry=entries[anchor['entryDigest']]
                    if entry['operation'] in (1,2,4,5):
                        items=documents_command(raw(entry['payload']))
                        f.need(entry['operation'] in (4,5) or len(items)==1,'single mutation count')
                        for key,value in items:
                            f.need((key in projection)==(entry['operation'] in (2,5)),'application mutation precondition');projection[key]=value
                        sequence+=1
                    else:f.need(entry['operation']==9,'unsupported runtime fixture operation')
                actual_indexes,actual=application(raw(snapshot['application']))
                f.need(list(actual.items())==list(projection.items()) and actual_indexes==indexes and snapshot['applicationSequence']==sequence,'V4 canonical application projection')
                published[len(snapshot['anchors'])]=projection;publications+=1
            elif event=='SUCCESS':
                f.need(row['index'] in published and published[row['index']].get(row['id'])==row['value'],'success before exact publication');successes+=1
            elif event=='CLIENT_SUCCESS' and row['kind']=='addAll':
                # Concurrent callers cannot identify their own cut from a later status cache.
                # Unique tagged documents must already occur together in one proven publication.
                f.need(any(all(state.get(d['id'])==d['value'] for d in row['documents']) for state in published.values()),'bulk success before publication');successes+=1
        for index,digest in chosen.items():
            if node in reports and reports[node]['provenThrough']>=index:f.need(reports[node]['acceptedDigests'][index-1]==digest,'retained chosen history changed')
    f.need(successes>=3 and publications>=5 and chunks>=6,'incomplete runtime execution')
    return dict(status='PASS',execution='internal-runtime-real-tcp',publicRuntime=False,processes=len(pids),chosen=len(chosen),publications=publications,successes=successes,chunkFrames=chunks,quarantined=quarantined)


def negatives(root):
    import copy
    root=Path(root);original={f'node-{i}':[json.loads(line) for line in (root/f'node-{i}-trace.jsonl').read_text().splitlines()] for i in range(1,4)}
    def remove_proof(v):
        for node in v:v[node]=[r for r in v[node] if r['event']!='FORCE' or r['kind']!='PROOF']
    def remove_ack(v):
        for node in v:v[node]=[r for r in v[node] if r['event']!='RECEIVED' or json.loads(raw(r['frame'])[48:])['type']!='COMMIT_PROOF_ACK']
    def changed_success(v):
        next(r for rows in v.values() for r in rows if r['event']=='SUCCESS')['value']='forged'
    def remove_chunks(v):
        for node in v:v[node]=[r for r in v[node] if r['event'] not in ('REPLY','RECEIVED') or json.loads(raw(r['frame'])[48:])['type']!='BASIS_CHUNK']
    cases=[]
    for name,change in [('missing-proof-force',remove_proof),('missing-proof-ack',remove_ack),('changed-client-value',changed_success),('missing-basis-transfer',remove_chunks),('missing-voter',lambda v:v.pop('node-2'))]:
        mutated=copy.deepcopy(original);change(mutated)
        try:validate(root,mutated)
        except ValueError as error:cases.append(dict(case=name,status='REJECTED',reason=str(error)))
        else:raise ValueError('negative accepted: '+name)
    return cases
