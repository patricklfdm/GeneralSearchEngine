"""Publicly configured read caps, reserved writer capacity and exact release evidence."""
import copy
from . import public_reads_evidence as e,public_read_lifecycle_evidence as lifecycle,token
from .evidence import need
from scripts.v51 import format_inspector as records,rejoin_evidence as rejoin

CAPACITIES={'resource-p4':4,'resource-p65':65,'resource-default':10000}
CASES=tuple(CAPACITIES)


def schedule(root,traces,history,processes):
    details=e.read(root/'read-resources.json');name=details['scenario'];pending=CAPACITIES[name];limit=min(64,pending-1)
    need((root/'read-capacity.txt').read_text().strip()==str(pending),'resource fixture capacity changed')
    plan=records.inspect((root/'operation/plan.gsr').read_bytes(),'PLAN')
    expected=dict(maxFrameBytes=1<<20,maxEntriesPerAppend=100,maxInFlightPerPeer=8,maxPendingClientOperations=pending,
                  maxRetryAttempts=2,requestTimeoutMillis=1200,retryBackoffMillis=25,snapshotChunkBytes=65536,
                  maxRetainedLogBytes=64<<20,maxSnapshotStagingBytes=64<<20)
    need(len(plan['targets'])==3 and all(t['bounds']==expected for t in plan['targets']),'public bootstrap capacity binding')
    for process in processes:lifecycle.ownership([r for r in traces[process['node']] if r['pid']==process['pid']],limit=limit)
    by_id={a['opId']:a for a in history};node=details['node'];rows=traces[node]
    def event(kind,op):
        found=[r for r in rows if r['event']==kind and r.get('opId')==op]
        need(len(found)==1,'resource event missing or duplicated');return found[0]
    def probe(key,owned):
        attempt=by_id[details[key]];observed=event('CLIENT_SUCCESS',attempt['opId']);invoked=event('CLIENT_INVOKE',attempt['opId'])
        need(attempt['node']==node and attempt['kind']=='probe' and attempt['outcome']=='SUCCESS' and
             attempt['response']=={k:v for k,v in observed.items() if k not in lifecycle.META} and
             invoked['order']<observed['order'] and attempt['startNanos']<attempt['endNanos'],'resource probe binding')
        counts=observed['queues']
        need(counts['readsOwned']==counts['readsWaiting']==counts['readsAlarms']==owned and
             counts['readsCaptured']==counts['readsSettling']==0 and counts['admissionAvailable']==pending-owned and
             counts['readsHighWater']==(1 if key=='baselineProbe' else limit),'resource counters or reserved permit differ')
        return observed
    baseline=probe('baselineProbe',0);full=probe('fullProbe',limit);rejected=probe('rejectedProbe',limit);final=probe('finalProbe',0)
    carried=by_id[details['carriedOp']]['response'];lower=token.decode(e.physical.raw(carried['token']))
    need(set(details['baselineFloors'])==set(traces),'resource baseline voter set')
    manifest=e.context(root,traces)[0]
    for voter,floor in details['baselineFloors'].items():
        need(floor in traces[voter] and floor['event']=='RECOVERY_FLOOR' and floor['index']==lower['index'],
             'resource baseline recovery not complete')
        local=rejoin.packet(floor['local'],manifest);remote=rejoin.packet(floor['remote'],manifest)
        need(local['seal']['node']==voter and remote['seal']['node']!=voter and
             len(local['snapshot']['anchors'])==len(remote['snapshot']['anchors'])==lower['index'],
             'resource baseline source index')
        if voter==node:need(floor['order']<baseline['order'],'resource baseline probe before recovery floor')
    waiters=[by_id[op] for op in details['waitingOps']];need(len(waiters)==limit and len({a['opId'] for a in waiters})==limit,'resource waiter cardinality')
    writer=by_id[details['writerOp']];excess=by_id[details['excessOp']]
    write_event=event('CLIENT_INVOKE',writer['opId']);write_response=event('CLIENT_SUCCESS',writer['opId'])
    excess_event=event('CLIENT_INVOKE',excess['opId']);excess_response=event('CLIENT_FAILURE',excess['opId'])
    need(baseline['order']<full['order']<excess_event['order']<excess_response['order']<rejected['order']<write_event['order']<write_response['order']<final['order'],
         'resource saturation/write ordering')
    need(writer['node']==node and writer['kind']=='addAll' and writer['outcome']=='SUCCESS' and writer['documents']==details['added'],
         'reserved capacity failed to publish satisfying write')
    wanted=dict(lower,index=lower['index']+1)
    for attempt in waiters+[excess]:
        need(attempt['node']==node and attempt['kind']=='read' and attempt['policy']=='AT_LEAST_INDEX' and
             token.decode(e.physical.raw(attempt['minimum']))==wanted and attempt['waitTimeoutMillis']==60000,'resource waiting options')
    need(excess['outcome']=='NOT_APPLICABLE' and excess['reasonCode']=='CAPACITY_EXCEEDED' and
         not any(r['event'] in lifecycle.ATOMIC for r in rows if excess_event['order']<r['order']<excess_response['order']),
         'excess read admitted or changed rejection')
    for attempt in waiters:
        invoked=event('CLIENT_INVOKE',attempt['opId']);callback=event('REPLICA_READ_CALLBACK',attempt['opId']);response=event('CLIENT_SUCCESS',attempt['opId'])
        need(baseline['order']<invoked['order']<full['order'] and write_event['order']<callback['order']<response['order']<final['order'],
             'waiter completed before satisfying public write')
        result=attempt['response']
        need(attempt['outcome']=='SUCCESS' and token.decode(e.physical.raw(result['token']))==wanted and
             result['sequence']==carried['sequence']+1 and result['documents']==carried['documents']+details['added'],
             'resource read lost its actual publication cut')
    need(all(a['outcome']=='SUCCESS' or a['opId']==excess['opId'] for a in history),'undeclared resource failure')
    return dict(status='PASS',pending=pending,readLimit=limit,waiting=len(waiters),excessRejected=1)


def negatives(root,binding,queries):
    cases=e.negatives(root,binding,queries);original=e.traces_at(root);history=e.read(root/'history.json');details=e.read(root/'read-resources.json')
    traces=copy.deepcopy(original);changed=copy.deepcopy(history);op=details['fullProbe']
    row=next(r for r in traces[details['node']] if r['event']=='CLIENT_SUCCESS' and r.get('opId')==op)
    row['queues']['admissionAvailable']=0
    next(a for a in changed if a['opId']==op)['response']['queues']['admissionAvailable']=0
    try:e.validate(root,binding,queries,traces=traces,history=changed)
    except ValueError as error:
        need(str(error)=='resource counters or reserved permit differ','unexpected reserve negative: '+str(error))
        cases.append(dict(case='missing-reserved-writer-permit',status='REJECTED',reason=str(error)))
    else:raise ValueError('missing reserved permit accepted')
    traces=copy.deepcopy(original);rows=traces[details['node']]
    last=next(r for r in reversed(rows) if r['event']=='REPLICA_READ_OWNERSHIP_RELEASED');rows.remove(last)
    try:e.validate(root,binding,queries,traces=traces)
    except ValueError as error:
        need(str(error)=='normal process leaked read ownership','unexpected release negative: '+str(error))
        cases.append(dict(case='missing-final-ownership-release',status='REJECTED',reason=str(error)))
    else:raise ValueError('unreleased final read accepted')
    return cases
