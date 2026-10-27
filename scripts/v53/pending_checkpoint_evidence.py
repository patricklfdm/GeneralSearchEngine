"""Original native checkpoint receipt transfer followed by real local publication.

No claimed ACK list supplies authority: derive application/checkpoint records,
replay the wire contents and force/delivery ordering, then derive published files.
This is an explicitly driven storage/transport history, not autonomous dispatch.
"""
import argparse
import base64
import json
import shutil
import tempfile
import uuid
from pathlib import Path
from . import future_quorum_evidence as q
from . import source_exchange_evidence as transfer

p,c,f,e,need=q.p,q.c,q.f,q.e,q.need


def publication(before, ends):
    files=before['node-1'];prefix,members,packet=c.current(files);cap=packet['capsule'];end=ends['node-1']
    certificate=f.decode(end['certificate.gsr'],'records','CERTIFICATE')
    proof=dict(certificate);del proof['proofs'];accept=dict(proof);del accept['accepts']
    selected=f.decode(members['selected.gsr'],'records','SELECTED')
    entry=f.encode('records','ENTRY',dict(root=cap['root'],authority=selected['view'],index=1,
        previous=cap['cut']['entry'],origin=selected['ballot'],kind='BARRIER',payload=e.digest(b'')))
    acks=[ends[node]['ack.gsr'] for node in sorted(ends)]
    values=[files['root.gsr'],files['genesis.gsr'],entry,f.encode('records','ACCEPT',accept),f.encode('records','PROOF',proof),
            end['certificate.gsr'],b'',end['catalog.gsr'],end['statement.gsr'],*acks]
    objects={e.digest(raw):raw for raw in values};catalog=f.decode(end['catalog.gsr'],'records','CATALOG')
    upper=dict(cut=catalog['cut'],catalog=e.digest(end['catalog.gsr']),application=catalog['application'])
    item=dict(kind='RANGE',statement=e.digest(end['statement.gsr']),endorsements=[e.digest(raw) for raw in acks],certificate=None,descriptor=None)
    source=e.packet_bytes(dict(cap,**upper,items=[item]),objects,{catalog['application']:len(end['application.image'])})
    coverage=dict(schema='gse-v53-selected-coverage/1.3',selection=e.digest(members['selected.gsr']),parent=c.anchor(cap),certificate=e.digest(end['certificate.gsr']))
    copied={k:members[k] for k in ('promise.gsr','basis.gsr','selected.gsr','selected-sources.gsr')}
    copied.update({'source.gscp':source,c.COVERAGE:f.canonical(coverage),catalog['application']+'.image':end['application.image']})
    selector,generation=c.generation(copied,e.p.decode(source)['capsule'],'node-1','b' if prefix=='generations/a/' else 'a',None)
    changed=dict(files,**generation,**{'selector.gsr':selector,'pending.accept':c.EMPTY})
    changed={k:v for k,v in changed.items() if k!='applied-end' and not k.startswith('applied-end/')}
    return dict(before,**{'node-1':changed})


def validate(root):
    root=Path(root);before,ends=q.prelude(root,3);names=sorted(before)
    identities={node:q.future.identity(files) for node,files in before.items()}
    cap,selected,_=q.payload(before,ends);result=q.read(root/'checkpoint-result.json')
    need(result==dict(status='PASS',published='node-1',statement=e.digest(ends['node-1']['statement.gsr']),
                     acknowledgements=[e.digest(ends[node]['ack.gsr']) for node in names]),'pending checkpoint original result')
    rows=q.read(root/'checkpoint-wire.json');position=0;traces=set();received={}
    for node in names[1:]:
        raw=ends[node]['ack.gsr'];digest=e.digest(raw);sequence=0;trace=None
        def exchange(wanted,answer):
            nonlocal position,sequence,trace
            need(position<len(rows),'pending checkpoint incomplete wire');row=rows[position];position+=1;sequence+=1
            need(set(row)=={'request','response'},'pending checkpoint wire row')
            kind,sent=transfer.wire(row['request']);reply_kind,reply=transfer.wire(row['response'])
            need((kind,reply_kind)==(wanted,answer),'pending checkpoint wire kinds')
            if trace is None:
                trace=sent['trace'];need(str(uuid.UUID(trace))==trace and trace not in traces,'pending checkpoint distinct trace');traces.add(trace)
            fields=dict(root=cap['root'],view=selected['view'],ballot=selected['ballot'],trace=trace,sequence=sequence)
            need({k:v for k,v in sent.items() if k!='payload'}==dict(fields,sender=identities['node-1'],recipient=identities[node]) and
                 {k:v for k,v in reply.items() if k!='payload'}==dict(fields,sender=identities[node],recipient=identities['node-1']),
                 'pending checkpoint exact wire correlation')
            return sent['payload'],reply['payload']
        sent,offer=exchange('CHUNK','SOURCE_OFFER');tid=sent['id'];need(str(uuid.UUID(tid))==tid,'pending checkpoint transfer id')
        need(sent==dict(id=tid,action='REQUEST',offset=0,digest=digest,bytes='') and
             offer==dict(id=tid,digest=digest,bytes=len(raw),kind='RECORD'),'pending checkpoint exact offer')
        offset=0
        while offset<len(raw):
            sent,reply=exchange('CHUNK','CHUNK');part=base64.b64decode(reply['bytes'],validate=True)
            need(0<len(part)<=4*e.MIB and sent==dict(id=tid,action='REQUEST',offset=offset,digest=digest,bytes='') and
                 reply==dict(id=tid,action='DATA',offset=offset,digest=e.digest(part),bytes=base64.b64encode(part).decode()) and
                 part==raw[offset:offset+len(part)],'pending checkpoint exact data')
            offset+=len(part)
        sent,reply=exchange('TRANSFER_COMMIT','TRANSFER_COMMIT')
        need(sent==reply==dict(id=tid,digest=digest),'pending checkpoint exact transfer commit');received[node]=digest
    need(position==len(rows),'pending checkpoint extra wire')
    timeline=q.read(root/'timeline.json');boundaries=[i for i,row in enumerate(timeline) if row['event']=='PUBLICATION_SELECTOR_FORCED']
    need(len(boundaries)==1,'pending checkpoint exact publication');prior=timeline[:boundaries[0]]
    need([row for row in prior if row['event']=='PENDING_CHECKPOINT_ACK_RECEIVED']==[
        dict(node=node,event='PENDING_CHECKPOINT_ACK_RECEIVED',digest=received[node]) for node in names[1:]],'pending checkpoint received before publication')
    q.s.ordered([row['event'] for row in timeline if row['node']=='node-1'],
                ['APPLY_ACK_DIRECTORY_FORCED','PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN'],
                'pending checkpoint local publication')
    for node in names[1:]:
        own=[row['event'] for row in prior if row['node']==node]
        q.s.ordered(own,['APPLY_ACK_DIRECTORY_FORCED','PENDING_CHECKPOINT_ACK_RECEIVED'],'pending checkpoint forced original '+node)
    events=q.read(root/'endpoint-events.json');need([row['node'] for row in events]==names,'pending checkpoint original owners')
    for row in events:
        q.n.native_order(row['events'],1)
        need(row['events'].count('PUBLICATION_SELECTOR_FORCED')==(1 if row['node']=='node-1' else 0),'pending checkpoint publication owner')
    final=publication(before,ends);p.match(root,'after-checkpoint-publication',final);p.match(root,'after-endpoint',final)
    return dict(status='PASS',originalNativeOwners=3,checkpointTransfers=2,exchanges=len(rows),publishedIndex=1,
                remotePublishedIndex=0,automaticDispatch=False,phase3Complete=False)


def qualify(root):
    root=Path(root);original=validate(root);negatives=[]
    variants=[('certificate','admitted exact certified: node-1'),('source-ack','admitted exact before-endpoint: node-2'),
              ('published','admitted exact after-checkpoint-publication: node-1'),('data','pending checkpoint exact data'),
              ('correlation','pending checkpoint exact wire correlation'),('missing-commit','pending checkpoint incomplete wire'),
              ('received','pending checkpoint received before publication'),
              ('force','selected retention force order: pending checkpoint forced original node-2'),
              ('local-force','selected retention force order: pending checkpoint local publication'),('result','pending checkpoint original result')]
    for name,reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-pending-checkpoint-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(root,target)
            if name in ('certificate','source-ack','published'):
                path=target/{'certificate':'certified/node-1/pending.accept','source-ack':'before-endpoint/node-2/applied-end/ack.gsr',
                             'published':'after-checkpoint-publication/node-1/selector.gsr'}[name]
                raw=path.read_bytes();path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name in ('data','correlation','missing-commit'):
                path=target/'checkpoint-wire.json';rows=q.read(path)
                if name=='missing-commit':rows.pop()
                else:
                    index=1 if name=='data' else 0;kind,value=transfer.wire(rows[index]['response'])
                    if name=='data':
                        part=b'changed';value['payload']['bytes']=base64.b64encode(part).decode();value['payload']['digest']=e.digest(part)
                    else:value['sequence']+=1
                    rows[index]['response']=base64.b64encode(f.encode('wire',kind,value)).decode()
                path.write_text(json.dumps(rows))
            elif name in ('received','force','local-force'):
                path=target/'timeline.json';rows=q.read(path);event='PENDING_CHECKPOINT_ACK_RECEIVED' if name=='received' else 'APPLY_ACK_DIRECTORY_FORCED'
                victim=next(row for row in rows if row['event']==event and row['node']==('node-1' if name=='local-force' else 'node-2'));rows.remove(victim)
                if name=='received':rows.append(victim)
                path.write_text(json.dumps(rows))
            else:
                path=target/'checkpoint-result.json';value=q.read(path);value['published']='node-2';path.write_text(json.dumps(value))
            try:validate(target)
            except ValueError as error:need(str(error)==reason,'pending checkpoint wrong negative: '+name+': '+str(error))
            else:raise ValueError('pending checkpoint mutation accepted: '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root),sort_keys=True))
