"""Independent original-first replay of quorum-bound remote publication.

Derive original votes, application ends, future proofs and published generation.
Wire callbacks/results are claims checked against those bytes and force order.
This qualifies explicit stable histories, not autonomous membership operations.
"""
import argparse
import base64
import copy
import json
import shutil
import tempfile
from pathlib import Path
from . import future_quorum_evidence as q
from . import source_exchange_evidence as transfer

p,c,f,e,need=q.p,q.c,q.f,q.e,q.need


def published(files,end,acks,node):
    prefix,members,packet=c.current(files);cap=packet['capsule']
    certificate=f.decode(end['certificate.gsr'],'records','CERTIFICATE')
    proof=dict(certificate);del proof['proofs'];accept=dict(proof);del accept['accepts']
    selected=f.decode(members['selected.gsr'],'records','SELECTED')
    entry=f.encode('records','ENTRY',dict(root=cap['root'],authority=selected['view'],index=1,
        previous=cap['cut']['entry'],origin=selected['ballot'],kind='BARRIER',payload=e.digest(b'')))
    values=[files['root.gsr'],files['genesis.gsr'],entry,f.encode('records','ACCEPT',accept),f.encode('records','PROOF',proof),
            end['certificate.gsr'],b'',end['catalog.gsr'],end['statement.gsr'],*acks]
    objects={e.digest(raw):raw for raw in values};catalog=f.decode(end['catalog.gsr'],'records','CATALOG')
    upper=dict(cut=catalog['cut'],catalog=e.digest(end['catalog.gsr']),application=catalog['application'])
    item=dict(kind='RANGE',statement=e.digest(end['statement.gsr']),endorsements=[e.digest(raw) for raw in acks],certificate=None,descriptor=None)
    source=e.packet_bytes(dict(cap,**upper,items=[item]),objects,{catalog['application']:len(end['application.image'])})
    coverage=dict(schema='gse-v53-selected-coverage/1.3',selection=e.digest(members['selected.gsr']),parent=c.anchor(cap),certificate=e.digest(end['certificate.gsr']))
    copied={k:members[k] for k in ('promise.gsr','basis.gsr','selected.gsr','selected-sources.gsr')}
    copied.update({'source.gscp':source,c.COVERAGE:f.canonical(coverage),catalog['application']+'.image':end['application.image']})
    selector,generation=c.generation(copied,e.p.decode(source)['capsule'],node,'b' if prefix=='generations/a/' else 'a',None)
    changed=dict(files,**generation,**{'selector.gsr':selector,'pending.accept':c.EMPTY})
    return {k:v for k,v in changed.items() if k!='applied-end' and not k.startswith('applied-end/')}


def validate(root):
    root=Path(root);size=len(list((root/'before-endpoint').iterdir()));need(size in (3,4,5),'remote publication stable size')
    before,ends=q.prelude(root,size);names=sorted(before);target=names[-1]
    identities={node:q.future.identity(files) for node,files in before.items()}
    cap,selected,logical=q.payload(before,ends);intent=e.digest(f.canonical(logical))
    timeline=q.read(root/'timeline.json');events=q.read(root/'endpoint-events.json')
    need([row['node'] for row in events]==names,'remote publication original owners')
    by_node={row['node']:row['events'] for row in events};recorded=set()
    for node,steps in by_node.items():
        q.n.native_order(steps,1)
        count=steps.count('FUTURE_RETENTION_BEFORE_WRITE')
        if count:
            recorded.add(node)
            q.s.ordered(steps,['FUTURE_RETENTION_FORCED','FUTURE_RETENTION_PARENT_FORCED','FUTURE_RETENTION_ACK_BEFORE_RETURN'],'remote future '+node)
        need(steps.count('PUBLICATION_SELECTOR_FORCED')==(1 if node==target else 0),'remote publication exact selector count')
    need('node-1' in recorded,'remote publication local recording')
    retained={node:q.pending(before[node],ends[node],identities[target]) for node in recorded}
    rows=q.read(root/'publication-wire.json');future_replies={};publications=[];traces={};all_traces=set();future_trace=set()
    for row in rows:
        need(set(row)=={'request','response','withheld'} and type(row['withheld']) is bool,'remote publication wire shape')
        kind,sent=transfer.wire(row['request']);reply_kind,reply=transfer.wire(row['response'])
        sender,recipient=sent['sender']['node'],sent['recipient']['node']
        need(sender in names and recipient in names and sent['sender']==identities[sender] and sent['recipient']==identities[recipient],
             'remote publication permanent owners')
        need({k:v for k,v in reply.items() if k!='payload'}==dict({k:v for k,v in sent.items() if k!='payload'},sender=sent['recipient'],recipient=sent['sender']) and
             sent['root']==cap['root'] and sent['view']==selected['view'] and sent['ballot']==selected['ballot'],'remote publication wire correlation')
        if kind=='FUTURE_RETENTION_INTENT':
            need(reply_kind=='FUTURE_RETENTION_ACK' and sender=='node-1' and recipient in recorded and sent['payload']==logical and
                 sent['sequence']==int(recipient[5:]),'remote publication exact recording request')
            q.acknowledgement(base64.b64decode(row['response'],validate=True),sent,intent,retained[recipient])
            need(not row['withheld'],'remote publication recording response');future_replies[e.digest(base64.b64decode(row['response']))]=recipient
            future_trace.add(sent['trace'])
        elif kind=='PUBLISH':
            need(reply_kind=='PUBLISH_ACK' and sender=='node-1' and recipient==target and sent['payload']==dict(certificate=logical['certificate'])
                 and sent['sequence']==size+1,'remote publication exact request');publications.append((row,sent,reply))
        else:
            need(kind in ('CHUNK','TRANSFER_COMMIT') and sender==target and recipient!=target and not row['withheld'],'remote publication transfer directions')
            traces.setdefault((recipient,sent['trace']),[]).append((kind,sent,reply_kind,reply))
    need(publications,'remote publication identical retry/duplicate')
    need(len(future_trace)==1 and {sent['trace'] for _,sent,_ in publications}==future_trace,'remote publication original trace')
    need(2<=len(publications)<=4 and len({row['request'] for row,_,_ in publications})==1 and
         sum(row['withheld'] for row,_,_ in publications)==(1 if size==3 else 0),'remote publication identical retry/duplicate')
    observed={target:ends[target]['ack.gsr']}
    for (node,trace),frames in traces.items():
        need(node not in observed and trace not in all_traces and trace not in future_trace,'remote publication distinct checkpoint source');all_traces.add(trace)
        raw=ends[node]['ack.gsr'];digest=e.digest(raw);offset=0;tid=None
        for index,(kind,sent,reply_kind,reply) in enumerate(frames):
            need(sent['sequence']==index+1,'remote publication transfer sequence');a,b=sent['payload'],reply['payload']
            if index==0:
                tid=a['id'];need((kind,reply_kind)==('CHUNK','SOURCE_OFFER') and a==dict(id=tid,action='REQUEST',offset=0,digest=digest,bytes='') and
                    b==dict(id=tid,digest=digest,bytes=len(raw),kind='RECORD'),'remote publication original checkpoint offer')
            elif index==len(frames)-1:
                need((kind,reply_kind)==('TRANSFER_COMMIT','TRANSFER_COMMIT') and a==b==dict(id=tid,digest=digest) and offset==len(raw),
                     'remote publication checkpoint commit')
            else:
                part=base64.b64decode(b['bytes'],validate=True)
                need((kind,reply_kind)==('CHUNK','CHUNK') and 0<len(part)<=4*e.MIB and
                     a==dict(id=tid,action='REQUEST',offset=offset,digest=digest,bytes='') and
                     b==dict(id=tid,action='DATA',offset=offset,digest=e.digest(part),bytes=base64.b64encode(part).decode()) and
                     part==raw[offset:offset+len(part)],'remote publication original checkpoint bytes');offset+=len(part)
        need(len(frames)>=3,'remote publication complete checkpoint transfer');observed[node]=raw
    need(len(observed)==size//2+1 and set(observed)==set(names[:size//2]+[target]),'remote publication actual checkpoint majority')
    expected_receipts=[dict(event='PUBLICATION_CHECKPOINT_RECEIVED',receiver=target,statement=ends[target]['statement.gsr'].hex(),ack=observed[node].hex())
                       for node in sorted(observed) if node!=target]
    need(q.read(root/'publication-receipts.json')==expected_receipts,'remote publication exact actual receipts')
    quorum_events=[(i,row) for i,row in enumerate(timeline) if row['event']=='FUTURE_QUORUM_COMPLETE']
    need(len(quorum_events)==1,'remote publication one original quorum');quorum_index,quorum_row=quorum_events[0];voters=quorum_row['voters']
    need(voters==sorted(set(voters)) and 'node-1' in voters and len(voters)==size//2+1 and set(voters)<=recorded,'remote publication recorded governing majority')
    prior=timeline[:quorum_index];received={future_replies[row['digest']] for row in prior if row['event']=='NETWORK_RECEIVED'
                                       and row.get('kind')=='FUTURE_RETENTION_ACK' and row['digest'] in future_replies}
    need(set(voters)-{'node-1'}<=received,'remote publication quorum delivery before dispatch')
    for node in voters:
        q.s.ordered([row['event'] for row in prior if row['node']==node],
                    ['FUTURE_RETENTION_FORCED','FUTURE_RETENTION_PARENT_FORCED'],'remote quorum force '+node)
    publication_index=next(i for i,row in enumerate(timeline) if row['event']=='PUBLICATION_SELECTOR_FORCED')
    send_events=[(i,row) for i,row in enumerate(timeline) if row['event']=='PUBLICATION_SEND_BOUNDARY']
    request_events=[(i,row) for i,row in enumerate(timeline) if row['event']=='PUBLICATION_REQUEST_RECEIVED']
    request_digest=e.digest(base64.b64decode(publications[0][0]['request']))
    need(2<=len(send_events)<=4 and len(request_events)<=len(send_events) and len(request_events)>=len(publications) and
         all(i>quorum_index and row['node']=='node-1' and row['digest']==request_digest for i,row in send_events) and
         all(i>send_events[0][0] and row['node']==target and row['digest']==request_digest for i,row in request_events) and
         request_events[0][0]<publication_index,'remote publication recorded before actual send')
    actual_receipts=[row for row in timeline[:publication_index] if row['event']=='PUBLICATION_CHECKPOINT_RECEIVED']
    need(actual_receipts==[dict(node=target,event='PUBLICATION_CHECKPOINT_RECEIVED',digest=e.digest(observed[node])) for node in sorted(observed) if node!=target],
         'remote publication checkpoint delivery before selector')
    for node in observed:
        q.s.ordered([row['event'] for row in timeline[:publication_index] if row['node']==node],['APPLY_ACK_DIRECTORY_FORCED'],'remote applied force '+node)
    final={node:dict(files,**({q.future.FILE:retained[node]} if node in recorded else {})) for node,files in before.items()}
    final[target]=published(final[target],ends[target],[observed[node] for node in sorted(observed)],target)
    if target in recorded:
        ledger=q.s.r.decode(before[target][q.s.FILE]);plan=copy.deepcopy(ledger['plan'])
        peer=next(v for v in plan['peers'] if v['identity']==identities[target]);peer['possible'].append(logical['upper'])
        final[target][q.s.FILE]=q.s.r.frame(dict(ledger,revision=ledger['revision']+1,previous=e.digest(before[target][q.s.FILE]),plan=plan))
        final[target][q.future.FILE]=q.future.frame(dict(q.future.initial(before[target]),revision=2,previous=e.digest(retained[target])),{})
        q.s.ordered(by_node[target],['PUBLICATION_SELECTOR_FORCED','RETENTION_PARENT_FORCED','FUTURE_RETENTION_PROMOTED',
                    'FUTURE_RETENTION_CLEARED','PUBLICATION_BEFORE_RETURN','PUBLICATION_ACK_BEFORE_RETURN'],'remote publication force before ACK')
    else:q.s.ordered(by_node[target],['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_ACK_BEFORE_RETURN'],'remote publication force before ACK')
    p.match(root,'after-endpoint',final)
    _,members,_=c.current(final[target]);selector=f.decode(final[target]['selector.gsr'],'records','SELECTOR')
    generation=final[target]['generations/'+selector['generation']+'/generation.gsr']
    expected=dict(certificate=logical['certificate'],selection=logical['selection'],published=logical['upper'],generation=e.digest(generation))
    need(all(reply['payload']==expected for _,_,reply in publications),'remote publication exact durable ACK')
    ack=e.digest(base64.b64decode(publications[0][0]['response']))
    delivered=[(i,row) for i,row in enumerate(timeline) if row['event']=='NETWORK_RECEIVED' and row.get('kind')=='PUBLISH_ACK']
    need(len(delivered)==2 and all(i>publication_index and row['node']=='node-1' and row['digest']==ack and
         any(prior['node']==target and prior['event']=='PUBLICATION_ACK_BEFORE_RETURN' for prior in timeline[publication_index:i])
         for i,row in delivered),'remote publication actual acknowledgement delivery')
    need(q.read(root/'publication-result.json')==dict(status='PASS',size=size,target=target,quorum=voters,ack=ack,lostAck=size==3),'remote publication result')
    return dict(status='PASS',nativeOwners=size,checkpointOwners=len(observed),published=target,publicationAttempts=len(send_events)-1,
                duplicate=1,recordedVoters=voters,autonomous=False,phase3Complete=False)


def qualify(root):
    root=Path(root);original=validate(root);negatives=[]
    variants=[('certificate','admitted exact certified: node-1'),('checkpoint','remote publication original checkpoint bytes'),
              ('quorum','remote publication quorum delivery before dispatch'),('received','remote publication checkpoint delivery before selector'),
              ('target','remote publication exact request'),('published','admitted exact after-endpoint: '+original['published']),
              ('ack','remote publication exact durable ACK'),('retry','remote publication identical retry/duplicate'),
              ('force','selected retention force order: remote publication force before ACK'),
              ('dispatch-order','remote publication recorded before actual send'),('ack-delivery','remote publication actual acknowledgement delivery')]
    for name,reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-remote-publication-negative-') as temp:
            dest=Path(temp)/'raw';shutil.copytree(root,dest)
            if name in ('certificate','published'):
                path=dest/('certified/node-1/pending.accept' if name=='certificate' else 'after-endpoint/'+original['published']+'/selector.gsr')
                raw=path.read_bytes();path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name in ('quorum','received','dispatch-order','ack-delivery'):
                path=dest/'timeline.json';rows=q.read(path)
                if name=='dispatch-order':
                    item=next(row for row in rows if row['event']=='PUBLICATION_SEND_BOUNDARY');rows.remove(item);rows.insert(0,item)
                else:
                    rows=[row for row in rows if not (row['event']=='PUBLICATION_CHECKPOINT_RECEIVED' if name=='received' else
                          row.get('kind')==('PUBLISH_ACK' if name=='ack-delivery' else 'FUTURE_RETENTION_ACK'))]
                path.write_text(json.dumps(rows))
            elif name=='force':
                path=dest/'endpoint-events.json';rows=q.read(path);row=next(v for v in rows if v['node']==original['published']);row['events'].remove('PUBLICATION_BEFORE_RETURN');path.write_text(json.dumps(rows))
            else:
                path=dest/'publication-wire.json';rows=q.read(path)
                if name=='retry':
                    rows=[row for row in rows if transfer.wire(row['response'])[0]!='PUBLISH_ACK']
                else:
                    row=next(v for v in rows if transfer.wire(v['response'])[0]==('CHUNK' if name=='checkpoint' else 'PUBLISH_ACK'))
                    field='request' if name=='target' else 'response';kind,value=transfer.wire(row[field])
                    if name=='checkpoint':
                        part=b'wrong';value['payload']['bytes']=base64.b64encode(part).decode();value['payload']['digest']=e.digest(part)
                    elif name=='target':value['payload']['certificate']='f'*64
                    else:value['payload']['generation']='f'*64
                    row[field]=base64.b64encode(f.encode('wire',kind,value)).decode()
                path.write_text(json.dumps(rows))
            try:validate(dest)
            except ValueError as error:need(str(error)==reason,'remote publication wrong negative: '+name+': '+str(error))
            else:raise ValueError('remote publication mutation accepted: '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root),sort_keys=True))
