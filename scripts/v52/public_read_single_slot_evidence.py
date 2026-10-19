"""R=0 rejects explicit views while unchanged public legacy operations remain usable."""
import copy
from . import public_reads_evidence as e,public_read_lifecycle_evidence as lifecycle,token
from .evidence import need
from scripts.v51 import format_inspector as records

CASES=('single-slot',)


def schedule(root,traces,history,processes):
    details=e.read(root/'read-single-slot.json');need(details['scenario']==CASES[0],'single-slot scenario')
    need((root/'read-capacity.txt').read_text().strip()=='1','single-slot fixture capacity')
    plan=records.inspect((root/'operation/plan.gsr').read_bytes(),'PLAN')
    need(len(plan['targets'])==3 and all(t['bounds']['maxPendingClientOperations']==1 for t in plan['targets']),'single-slot public bootstrap bound')
    manifest,genesis,entries=e.context(root,traces);node=details['node'];rows=traces[node];attempts={a['opId']:a for a in history}
    for process in processes:
        own=[r for r in traces[process['node']] if r['pid']==process['pid']]
        need(not any(r['event'] in lifecycle.ATOMIC or r['event'] in ('REPLICA_READ_CALLBACK','REPLICA_READ_CAPTURED') for r in own),
             'zero capacity allocated a read or invoked callback')
        lifecycle.ownership(own,limit=0)
    def call(op):
        attempt=attempts[op];invoke=[r for r in rows if r['event']=='CLIENT_INVOKE' and r.get('opId')==op]
        response=[r for r in rows if r['event'] in ('CLIENT_SUCCESS','CLIENT_FAILURE') and r.get('opId')==op]
        need(attempt['node']==node and len(invoke)==len(response)==1 and invoke[0]['order']<response[0]['order'] and
             attempt['startNanos']<attempt['endNanos'] and attempt['response']=={k:v for k,v in response[0].items() if k not in lifecycle.META},
             'single-slot public invocation/response binding')
        return attempt,invoke[0],response[0]
    def probe(op):
        attempt,invoke,result=call(op);counts=result['queues']
        need(attempt['kind']=='probe' and result['outcome']=='SUCCESS' and counts['admissionAvailable']==1 and
             all(counts['reads'+k]==0 for k in ('Owned','Waiting','Captured','Settling','Alarms','Marker','HighWater')),
             'single-slot read consumed reserved public capacity')
        return result
    baseline=probe(details['baselineProbe']);after=probe(details['rejectedProbe']);final=probe(details['finalProbe'])
    need(len(details['rejections'])==3 and len(set(details['rejections']))==3,'single-slot rejection set')
    for op in details['rejections']:
        attempt,invoke,result=call(op)
        need(baseline['order']<invoke['order']<result['order']<after['order'] and attempt['kind']=='read' and
             result['outcome']=='NOT_APPLICABLE' and result['reasonCode']=='CAPACITY_EXCEEDED','single-slot rejection ordering')
        if attempt['policy']=='AT_LEAST_INDEX':
            minimum=token.decode(e.physical.raw(attempt['minimum']))
            need(minimum==dict(version=1,groupId=manifest['groupId'],historyId=manifest['historyId'],manifestDigest=manifest['digest'],index=details['baselineIndex']) and
                 attempt['waitTimeoutMillis']==60000,'single-slot compatible token')
    legacy=details['legacyOps'];need(len(legacy)==3 and len(set(legacy))==3,'single-slot legacy query set')
    queries=e.read(root/'oracle-results.json')
    for op in legacy:
        attempt,invoke,result=call(op)
        need(attempt['kind']=='legacy-get' and result['outcome']=='SUCCESS' and invoke['key']==attempt['key']==result['key']==1,'legacy query binding')
        own=[r for r in rows if invoke['order']<r['order']<result['order']]
        def single(event):
            found=[r for r in own if r['event']==event];need(len(found)==1,'legacy capture event missing or duplicated');return found[0]
        validated=single('READ_CAPTURE_VALIDATED');captured=single('READ_CAPTURED');released=single('READ_RELEASED')
        need(validated['order']<captured['order']<released['order'] and
             all(validated[k]==captured[k]==released[k] for k in ('epoch','index','sequence')),'legacy capture lifetime')
        published=[r for r in own if r['event']=='PUBLISHED' and r['order']<validated['order'] and
                   len(e.recovery.snapshot(e.physical.raw(r['snapshot']),manifest)['anchors'])==captured['index']]
        need(len(published)==1,'legacy query lacks own publication');snapshot=e.recovery.snapshot(e.physical.raw(published[0]['snapshot']),manifest)
        terminal=snapshot['anchors'][-1]['entryDigest'];proof=e.physical.frame(snapshot['terminalProof'],'PROOF',manifest)
        need(entries[terminal]['operation']==9 and proof['epoch']==captured['epoch'] and any(r['event']=='FORCE' and r['kind']=='ACCEPT' and
             e.physical.frame(r['record'],'ACCEPT',manifest)['entryDigest']==terminal for r in own if r['order']<validated['order']),
             'legacy query lacks fresh proven barrier')
        promises=[e.physical.frame(r['record'],'PROMISE',manifest)['epoch'] for r in rows if r['event']=='FORCE' and r['kind']=='PROMISE' and r['order']<validated['order']]
        need(promises and promises[-1]==captured['epoch'],'legacy query after higher promise')
        value=e.prefix(snapshot,manifest,genesis,entries);wanted=next(d for d in value['documents'] if d['id']==1)
        need(result['document']==wanted and value['sequence']==captured['sequence'] and
             queries[e.digest(e.encoded(value))]['documents']==value['documents'],'legacy result differs from published query control')
    writer,write_invoke,write_result=call(details['writerOp']);last,read_invoke,read_result=call(legacy[-1])
    need(writer['kind']=='addAll' and writer['outcome']=='SUCCESS' and
         after['order']<write_invoke['order']<write_result['order']<read_invoke['order']<read_result['order']<final['order'],
         'single-slot legacy/write service did not remain available')
    need(all(a['outcome']=='SUCCESS' or a['opId'] in details['rejections'] for a in history),'undeclared single-slot failure')


def negatives(root,binding,queries):
    e.validate(root,binding,queries);original=e.traces_at(root);history=e.read(root/'history.json');details=e.read(root/'read-single-slot.json');cases=[]
    for name,event,reason in (
            ('missing-legacy-capture','READ_CAPTURE_VALIDATED','legacy capture event missing or duplicated'),
            ('missing-legacy-release','READ_RELEASED','legacy capture event missing or duplicated')):
        traces={n:[r for r in rs if r['event']!=event] for n,rs in original.items()}
        try:e.validate(root,binding,queries,traces=traces)
        except ValueError as error:
            need(str(error)==reason,'unexpected single-slot negative: '+str(error));cases.append(dict(case=name,status='REJECTED',reason=reason))
        else:raise ValueError('invalid legacy read accepted')
    for name,op,field,value,reason in (
            ('legacy-wrong-document',details['legacyOps'][-1],'document',{},'legacy result differs from published query control'),
            ('lost-reserved-slot',details['finalProbe'],'queues',{},'single-slot read consumed reserved public capacity')):
        traces=copy.deepcopy(original);changed=copy.deepcopy(history);row=next(r for r in traces[details['node']] if r['event']=='CLIENT_SUCCESS' and r.get('opId')==op)
        if field=='queues':value=dict(row['queues'],admissionAvailable=0)
        row[field]=value;next(a for a in changed if a['opId']==op)['response'][field]=value
        try:e.validate(root,binding,queries,traces=traces,history=changed)
        except ValueError as error:
            need(str(error)==reason,'unexpected single-slot negative: '+str(error));cases.append(dict(case=name,status='REJECTED',reason=reason))
        else:raise ValueError('forged legacy result accepted')
    op=details['rejections'][0];traces=copy.deepcopy(original);changed=copy.deepcopy(history)
    row=next(r for r in traces[details['node']] if r['event']=='CLIENT_FAILURE' and r.get('opId')==op)
    row['event']='CLIENT_SUCCESS';row['outcome']='SUCCESS'
    attempt=next(a for a in changed if a['opId']==op);attempt['outcome']=attempt['response']['outcome']='SUCCESS'
    try:e.validate(root,binding,queries,traces=traces,history=changed)
    except ValueError as error:
        need(str(error)=='success before view release','unexpected single-slot success negative: '+str(error))
        cases.append(dict(case='zero-capacity-forged-success',status='REJECTED',reason=str(error)))
    else:raise ValueError('zero-capacity success accepted')
    return cases
