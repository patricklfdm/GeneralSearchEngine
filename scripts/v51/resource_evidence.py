"""Independent resource-boundary inspection; no production decoder imports."""
import copy
import json
import struct
import tarfile
from pathlib import Path
from . import storage_inspector as s, public_qualification_evidence as physical, model
from .storage_harness import need


def image_offer(snapshot,manifest_digest):
    """Derive only the IMAGE envelope size/digest, using the independent catalog."""
    body=s.canonical(dict(manifestDigest=manifest_digest,snapshot=snapshot,acceptances=[]))
    header=struct.pack('>4sHHHHi',b'GSER',1,2,s.f.load()['records']['IMAGE']['id'],0,len(body))
    return 48+len(body),s.sha(header+body)


def snapshot_offer(request,reply,staging):
    need(request['type']=='SNAPSHOT_OFFER' and request['payload']['response'] is False,'wrong snapshot admission request')
    need(reply['type']=='REJECT' and reply['payload']['reason']=='CAPACITY_EXCEEDED','snapshot offer did not reject capacity')
    need(all(request[k]==reply[k] for k in ('groupId','configurationId','manifestDigest','epoch','proposer','incarnationId','traceId','eventSequence')) and
         request['sender']==reply['recipient'] and request['recipient']==reply['sender'],'snapshot rejection correlation')
    limit=min(s.f.MAX_IMAGE,staging//4)
    need(request['payload']['imageBytes']>limit,'snapshot image fits sealed transfer allowance')
    return dict(boundary='snapshot-offer',transferLimit=limit)


def public(root,traces,history,receipt):
    root=Path(root);encoded=(root/'node-3/manifest.gsr').read_bytes()
    manifest=dict(s.f.inspect(encoded,'MANIFEST'),digest=encoded[16:48].hex())
    seal=s.f.inspect((root/'node-3/bootstrap-seal.gsr').read_bytes(),'SEAL')
    plan=s.f.inspect(s.raw(s.f.inspect(s.raw(seal['receipt']),'RECEIPT')['plan']),'PLAN')
    need(s.raw(plan['manifest'])==encoded,'resource manifest binding')
    key='maxSnapshotStagingBytes' if receipt['case']=='snapshot-staging' else 'maxRetainedLogBytes'
    need(receipt['case'] in ('snapshot-staging','retained-bytes'),'unknown resource case')
    need([v['bounds'][key] for v in plan['targets']]==[64<<20,64<<20,128<<10],'resource bound not sealed')
    row=receipt['rejection'];need(row in traces['node-3'],'missing actual capacity observation')
    need(row['node']=='node-3' and row['manifestDigest']==manifest['digest'] and row['groupId']==manifest['groupId'],'capacity authority binding')
    if receipt['case']=='snapshot-staging':
        request=s.f.wire(s.raw(row['request']),manifest);reply=s.f.wire(s.raw(row['frame']),manifest)
        need(row['event']=='REPLY','missing snapshot rejection reply')
        detail=snapshot_offer(request,reply,plan['targets'][2]['bounds'][key])
        need(request['sender']==receipt['leader'] and request['recipient']=='node-3','snapshot rejection peer')
        candidates=[r for r in traces[receipt['leader']] if r['event']=='PUBLISHED'
                    and image_offer(r['snapshot'],manifest['digest'])==
                    (request['payload']['imageBytes'],request['payload']['imageDigest'])]
        need(candidates,'offered image has no exact published source')
        from .runtime_evidence import application
        docs=next(v for v in history if v['opId']==receipt['loadWrite'])['documents']
        for source in candidates:
            snapshot=s.f.inspect(s.raw(source['snapshot']),'SNAPSHOT');_,values=application(s.raw(snapshot['application']))
            need(all(values.get(v['id'])==v['value'] for v in docs),'oversized source lacks load write')
        need(any(r['event']=='RECEIVED' and r.get('request')==row['request'] and r.get('frame')==row['frame']
                 for r in traces[receipt['leader']]),'snapshot rejection not received by proposer')
        transfer=request['payload']['transferId']
        for own in traces.values():
            for event in own:
                if not isinstance(event.get('request'),str):continue
                sent=s.f.wire(s.raw(event['request']),manifest)
                if sent['sender']==request['sender'] and sent['recipient']=='node-3' and sent['payload'].get('transferId')==transfer:
                    need(sent['type'] not in ('SNAPSHOT_CHUNK','REJOIN_INSTALL'),'rejected offer transferred or installed')
        requested=request['payload']['imageBytes']
    else:
        need(row['event']=='RESOURCE_REJECTED' and row['budget']=='retained' and row['limit']==plan['targets'][2]['bounds'][key],'wrong resource rejection')
        reservation(row)
        need(row['requested']>row['limit'],'retained image must exceed total budget independent of cleanup')
        need(row['files'] and len({v['path'] for v in row['files']})==len(row['files']) and
             sum(v['size'] for v in row['files'])==row['retained'],'capacity inventory differs from accounting')
        detail=dict(boundary='recovery-write');requested=row['requested']
    need(any(v['event']=='STARTED' and v['pid']==row['pid'] and v['generation']==row['generation'] for v in traces['node-3']),'capacity observation process')
    calls={v['opId']:v for v in history}
    need(len(receipt['rejectedCalls'])==2,'missing exhausted voter calls')
    for opid,kind in zip(receipt['rejectedCalls'],('addAll','read')):
        op=calls[opid]
        need(op['node']=='node-3' and op['kind']==kind and op['outcome']==('NOT_SUBMITTED' if kind=='addAll' else 'NOT_APPLICABLE') and op['startNanos']>receipt['observedNanos'],'exhausted voter client outcome')
    for field,kind in (('postRejectionWrite','addAll'),('postRejectionRead','read'),('afterRestartRead','read'),('afterLeaderRestartRead','read')):
        op=calls[receipt[field]]
        need(op['kind']==kind and op['outcome']=='SUCCESS' and op['node']!='node-3' and op['startNanos']>receipt['observedNanos'],'missing later quorum service')
    need(calls[receipt['afterRestartRead']]['startNanos']>receipt['restartNanos'],'missing post-restart read')
    starts=[v for v in traces['node-3'] if v['event']=='STARTED']
    need(len(starts)==2 and {v['generation'] for v in starts}=={1,2} and len({v['pid'] for v in starts})==2,'missing retained public restart')
    leader_starts=[v for v in traces[receipt['leader']] if v['event']=='STARTED']
    need(len({v['pid'] for v in leader_starts})==2 and {v['generation'] for v in leader_starts}=={1,2},'missing public leader restart')
    before=receipt['retained'];archive=root/'before-reopen.tar.gz'
    need(s.sha(archive.read_bytes())==before['sha256'] and before['node']=='node-3','resource archive identity')
    with tarfile.open(archive) as tar:
        saved={m.name.removeprefix('node-3/'):dict(size=m.size,sha256=s.sha(tar.extractfile(m).read())) for m in tar.getmembers() if m.isfile()}
    need(saved==before['inventory'],'resource archive differs')
    current=s.inspect(root/'node-3')
    need(current['provenThrough']>=receipt['seedIndex'] and before['inspection']['provenThrough']>=receipt['seedIndex'],'resource pressure lost proven prefix')
    for inventory in (before['inventory'],s.inventory(root/'node-3')):
        retained=sum(v['size'] for v in inventory.values());staging=sum(v['size'] for k,v in inventory.items() if k.startswith(('basis/','transfer/')))
        need(retained<=plan['targets'][2]['bounds']['maxRetainedLogBytes'] and staging<=plan['targets'][2]['bounds']['maxSnapshotStagingBytes'],'retained resource budget exceeded')
    return dict(status='PASS',bound=key,limit=128<<10,requestedBytes=requested,detail=detail,retainedProvenIndex=current['provenThrough'])


def public_negatives(root,history,receipt):
    traces=physical.traces_at(root);variants=[]
    changed=copy.deepcopy(traces);changed['node-3'].remove(receipt['rejection']);variants.append(('missing-capacity-reply',changed,history,receipt))
    changed=copy.deepcopy(traces);changed['node-3']=[r for r in changed['node-3'] if r['generation']==1];variants.append(('missing-restart',changed,history,receipt))
    for field in ('postRejectionWrite','postRejectionRead','afterRestartRead','afterLeaderRestartRead'):
        h=copy.deepcopy(history);next(v for v in h if v['opId']==receipt[field])['outcome']='NOT_APPLICABLE';variants.append(('missing-'+field,traces,h,receipt))
    claim=copy.deepcopy(receipt);claim['retained']['sha256']='0'*64;variants.append(('changed-archive',traces,history,claim))
    claim=copy.deepcopy(receipt);changed=copy.deepcopy(traces)
    own=next(r for r in changed['node-3'] if r==receipt['rejection'])
    if receipt['case']=='retained-bytes':
        own['retained']+=1;claim['rejection']=own;variants.append(('forged-occupancy',changed,history,claim))
        claim=copy.deepcopy(receipt);changed=copy.deepcopy(traces)
        own=next(r for r in changed['node-3'] if r==receipt['rejection']);own['requested']=own['limit']
        claim['rejection']=own;variants.append(('cleanup-dependent-load',changed,history,claim))
    else:
        # Keep valid wire bytes, but splice in a response for a different exchange.
        other=next(r for r in changed['node-3'] if r['event']=='REPLY' and r['frame']!=own['frame'])
        own['frame']=other['frame'];claim['rejection']=own;variants.append(('borrowed-response',changed,history,claim))
        changed={n:[r for r in rows if r['event']!='PUBLISHED'] for n,rows in traces.items()}
        variants.append(('missing-published-image',changed,history,receipt))
    h=copy.deepcopy(history);next(v for v in h if v['opId']==receipt['rejectedCalls'][0])['outcome']='SUCCESS';variants.append(('exhausted-voter-success',traces,h,receipt))
    results=[]
    for name,t,h,r in variants:
        try:public(root,t,h,r)
        except ValueError as error:results.append(dict(case=name,status='REJECTED',reason=str(error)))
        else:raise ValueError('resource oracle admitted '+name)
    return results


def epoch_probes(probes):
    expected={(observed,rank) for observed in ((1<<63)-7,(1<<63)-4,(1<<63)-1) for rank in range(3)}
    need(len(probes)==9 and {(p['observed'],p['rank']) for p in probes}==expected,'missing epoch boundary probe')
    for p in probes:
        try:value=model.next_epoch(p['observed'],p['rank'])
        except model.Rejected:need(p.get('reason')=='CAPACITY_EXCEEDED' and 'next' not in p,'epoch overflow was not rejected')
        else:need(p.get('next')==value and 'reason' not in p,'wrong next ranked epoch')


def reservation(row):
    need(all(type(row[k]) is int and row[k]>=0 for k in ('limit','retained','replaced','requested')),'invalid reservation accounting')
    need(0<row['limit'] and 0<=row['replaced']<=row['retained'] and row['requested']>row['limit']-row['retained']+row['replaced'],'capacity observation does not exceed budget')


def capacity_math(case,limit,report,request,total):
    if case=='promise-count':
        need(limit==10_000 and report['promiseCount']==limit and request['epoch']>report['promisedEpoch'],'promise limit not reached')
    elif case=='retained-bytes':need(total==limit and request['bytes']>0,'retained budget not exactly full')
    elif case=='entry-count':need(limit==1_000_000 and request['index']==limit+1,'wrong entry boundary')
    elif case=='ancestry-count':need(limit==1_000_000 and request['count']==limit+1,'wrong ancestry boundary')
    elif case=='transfer-staging':
        need(limit==128<<10 and request['imageBytes']==limit and request['receivedBytes']==0 and total>0,'wrong transfer reservation boundary')
        need(request['imageBytes']>limit-total,'transfer reservation should fit')
    else:raise ValueError('unknown capacity case')


def internal(root):
    root=Path(root);result=json.loads((root/'result.json').read_text());case=result['case']
    need(result['execution']=='internal-resource-boundary' and result['publicRuntime'] is False,'internal evidence relabelled public')
    def inventory(name):return {v['path']:dict(size=v['size'],sha256=v['sha256']) for v in json.loads((root/name).read_text())}
    before=inventory('before.json');after=inventory('after.json')
    need(before==after==s.inventory(root/'node-1'),'rejected boundary changed authority')
    with tarfile.open(root/'before-reopen.tar.gz') as tar:
        saved={m.name.removeprefix('node-1/'):dict(size=m.size,sha256=s.sha(tar.extractfile(m).read())) for m in tar.getmembers() if m.isfile()}
    need(saved==before,'internal resource archive differs')
    report=s.inspect(root/'node-1');reopened=json.loads((root/'reopened.json').read_text())
    for key in ('promiseCount','promisedEpoch','acceptedThrough','provenThrough','applicationSequence','retainedBytes'):
        need(report[key]==reopened[key], 'reopened resource authority differs: '+key)
    request={}
    if case!='epoch-overflow':
        if case=='ancestry-count':request=json.loads((root/'ancestry-request.json').read_text())
        else:
            encoded=(root/'request.gsr').read_bytes()
            kind='PROMISE' if case in ('promise-count','retained-bytes') else 'ACCEPT' if case=='entry-count' else 'TRANSFER'
            request=s.f.inspect(encoded,kind)
            need(request['manifestDigest']==report['manifestDigest'],'resource request manifest')
            if case=='retained-bytes':request=dict(request,bytes=len(encoded))
            if case=='entry-count':request=s.f.inspect(s.raw(request['entry']),'ENTRY')
    total=sum(v['size'] for v in before.values());internal_claim(result,report,request,total)
    variants=[]
    if case=='epoch-overflow':
        changed=copy.deepcopy(result);changed['probes'][-1]={'observed':(1<<63)-1,'rank':2,'next':1};variants.append(('wrapped-epoch',changed))
        changed=copy.deepcopy(result);changed['probes'].pop();variants.append(('missing-rank-boundary',changed))
        changed=copy.deepcopy(result);changed['probes'][0]['next']+=1;variants.append(('wrong-ranked-epoch',changed))
    else:
        changed=copy.deepcopy(result);changed['rejection']['reason']='INTEGRITY_FAILURE';variants.append(('wrong-failure-classification',changed))
        changed=copy.deepcopy(result);changed['limit']+=1;variants.append(('wrong-resource-boundary',changed))
        changed=copy.deepcopy(result);changed['eventsAfter']['DELETE_AFTER_ROOT_TRUNCATE']=1;variants.append(('cleanup-to-make-space',changed))
    negatives=[]
    for name,changed in variants:
        try:internal_claim(changed,report,request,total)
        except ValueError as error:negatives.append(dict(case=name,status='REJECTED',reason=str(error)))
        else:raise ValueError('internal resource oracle admitted '+name)
    return dict(status='PASS',case=case,execution='internal-resource-boundary',publicRuntime=False,inspection=report,negatives=negatives)


def internal_claim(result,report,request,total):
    case=result['case']
    if case=='epoch-overflow':
        need(report['promisedEpoch']==(1<<63)-1,'maximum epoch was reset');epoch_probes(result['probes'])
    else:
        need(result['rejection']['reason']=='CAPACITY_EXCEEDED','resource failure misclassified')
        capacity_math(case,result['limit'],report,request,total)
        if case in ('promise-count','retained-bytes'):
            need(result['afterStatus']['promiseCount']==report['promiseCount'] and result['afterStatus']['promisedEpoch']==report['promisedEpoch'],'exact retry changed promise')
        delta={k:result['eventsAfter'].get(k,0)-result['eventsBefore'].get(k,0) for k in set(result['eventsAfter'])|set(result['eventsBefore'])}
        delta={k:v for k,v in delta.items() if v}
        need(delta==({'PROMISE_AFTER_FORCE':1,'PROMISE_BEFORE_ACK':1} if case in ('promise-count','retained-bytes') else {}),'rejection wrote/deleted authority')
