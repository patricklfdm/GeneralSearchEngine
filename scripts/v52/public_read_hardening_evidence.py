"""Independent combined-fault schedules and exact public ownership accounting."""
import copy
from pathlib import Path
from scripts.v51 import performance_bundle as bundle, rejoin_evidence as rejoin
from . import public_reads_evidence as e,public_read_lifecycle_evidence as lifecycle,token
from .evidence import need,digest

PLAN=Path(__file__).resolve().parents[2]/'docs/v5x/v5.2/phase5-hardening-plan.json'
PLAN_SHA='29b3ff1b7e6cfbf8f499cad7cc0f3e13f8048d408252ebe17c0cd2a199074059'
CASES=('partition-captured-halt','partition-captured-kill','sustained-bounded-reads')


def plan():
    need(digest(PLAN.read_bytes())==PLAN_SHA,'hardening frozen plan changed');return e.read(PLAN)


def counters(row,owned,captured,available):
    expected=dict(readsOwned=owned,readsCaptured=captured,readsWaiting=owned-captured,readsSettling=0,
                  readsAlarms=owned-captured,admissionAvailable=available)
    need(all(type(row.get(k)) is int and row[k]==v for k,v in expected.items()),'hardening counters or reserved slot differ')


def repeated(rows,target):
    def one(event):
        found=[r for r in rows if r['event']==event and r.get('opId')==target['opId']]
        need(len(found)==1,'hardening callback report cardinality');return found[0]
    first=one('REPLICA_READ_REPORT_FIRST');second=one('REPLICA_READ_REPORT_SECOND')
    need(target.get('repeat') is True and target['policy']=='STALE_ALLOWED' and first['report']==second['report'],
         'hardening repeated callback changed')
    pauses=[r for r in rows if r['event']=='CUT_REACHED' and r['cut']=='REPLICA_READ_REPORT_FIRST' and
            r['mode']=='pause' and first['order']<r['order']<second['order']]
    releases=[r for r in rows if r['event']=='CUT_RELEASED' and r['cut']=='REPLICA_READ_REPORT_FIRST' and
              first['order']<r['order']<second['order']]
    need(len(pauses)==len(releases)==1 and pauses[0]['order']<releases[0]['order'],'hardening callback pause order')
    need(not any(r['event'] in ('PUBLISHED','LOCAL_PUBLISHED') and first['order']<r['order']<second['order'] for r in rows),
         'hardening publication changed during callback')
    return first,pauses[0],releases[0],second


def schedule(root,name,traces,history,processes,*,details=None):
    frozen=plan();need(name in CASES,'unknown hardening schedule')
    need(digest((root/'hardening-plan.json').read_bytes())==PLAN_SHA==e.read(root/'binding.json').get('hardeningPlanSha256'),
         'hardening retained plan binding')
    details=e.read(root/'read-hardening.json') if details is None else details
    need(details['scenario']==name,'hardening scenario binding');case=next(c for c in frozen['cases'] if c['name']==name)
    pending=case['pendingLimit'];limit=min(64,pending-1);by_id={v['opId']:v for v in history};node=details['node']
    bootstrap=e.physical.f.inspect((root/'operation/plan.gsr').read_bytes(),'PLAN')
    need(len(bootstrap['targets'])==3 and all(t['bounds']['maxPendingClientOperations']==pending for t in bootstrap['targets']),
         'hardening public pending bound')
    need((root/'operation-timeout.txt').read_text().strip()==str(frozen['operationTimeoutMillis']),'hardening operation bound')
    for process in processes:lifecycle.ownership([r for r in traces[process['node']] if r['pid']==process['pid']],process['exitCode']!=0,limit=limit)
    def call(op):need(op in by_id,'hardening call missing');return by_id[op]
    def event(kind,op):
        attempt=call(op);found=[r for r in traces[attempt['node']] if r['pid']==attempt['pid'] and r['event']==kind and r.get('opId')==op]
        need(len(found)==1,'hardening event missing or duplicated: '+kind);return found[0]
    def response(op):
        attempt=call(op);need(attempt['outcome']=='SUCCESS','hardening expected successful call');return attempt['response']
    for attempt in history:
        if attempt['kind'] in ('read',*e.MUTATION_FIELDS):continue
        need(attempt['outcome']=='SUCCESS','hardening auxiliary call failed')
        observed=event('CLIENT_SUCCESS',attempt['opId']);invoked=event('CLIENT_INVOKE',attempt['opId'])
        need(attempt['response']=={k:v for k,v in observed.items() if k not in lifecycle.META} and
             attempt['kind']==invoked['kind'] and attempt.get('target')==invoked.get('target') and
             invoked['order']<observed['order'] and attempt['startNanos']<attempt['endNanos'],'hardening auxiliary binding')
    def probe(op,owned,captured,available):
        need(call(op)['kind']=='probe' and call(op)['node']==node,'hardening probe target')
        counters(response(op)['queues'],owned,captured,available);return event('CLIENT_SUCCESS',op)
    def cancelled(target,action,*,captured=False):
        attempt=call(target);control=call(action)
        need(attempt['outcome']=='CANCELLED' and attempt['reasonCode']=='CancellationException' and
             control['kind']=='cancel' and control['target']==target and response(action)['cancelled'] is True and
             attempt['endNanos']<=control['endNanos'],'hardening original Future cancellation')
        callbacks=[r for r in traces[attempt['node']] if r['pid']==attempt['pid'] and r['event']=='REPLICA_READ_CALLBACK' and r.get('opId')==target]
        need(len(callbacks)==int(captured),'hardening cancelled callback count')
        return event('CLIENT_SUCCESS',action)
    manifest=e.context(root,traces)[0]
    def floor_set(values,index,before):
        need(set(values)==set(traces),'hardening floor voter set')
        for voter,floor in values.items():
            need(floor in traces[voter] and floor['event']=='RECOVERY_FLOOR' and floor['index']==index,'hardening floor witness')
            local=rejoin.packet(floor['local'],manifest);remote=rejoin.packet(floor['remote'],manifest)
            need(local['seal']['node']==voter and remote['seal']['node']!=voter and
                 len(local['snapshot']['anchors'])==len(remote['snapshot']['anchors'])==index,'hardening floor source binding')
            if voter==node:need(floor['order']<before,'hardening floor after round start')
    carried=response(details['carriedOp']);allowed=set()
    if name.startswith('partition-'):
        target=call(details['targetOp']);own=[r for r in traces[node] if r['pid']==target['pid']]
        need(target['node']==node and event('CLIENT_INVOKE',target['opId']).get('repeat') is True,'hardening repeated invocation')
        first,pause,release,second=repeated(own,target)
        baseline=probe(details['baselineProbe'],0,0,16);floor_set(details['baselineFloors'],token.decode(e.physical.raw(carried['token']))['index'],baseline['order'])
        full=probe(details['fullProbe'],2,1,14);cancel=cancelled(details['queuedOp'],details['cancelOp']);held=probe(details['heldProbe'],1,1,15)
        need(baseline['order']<first['order']<pause['order']<full['order']<cancel['order']<held['order']<release['order']<second['order'],
             'hardening partition ownership order')
        queued=call(details['queuedOp']);need(queued['node']==node and queued['policy']=='AT_LEAST_INDEX' and queued['waitTimeoutMillis']==60000 and
                                           token.decode(e.physical.raw(queued['minimum']))==dict(token.decode(e.physical.raw(carried['token'])),index=(1<<63)-1),
                                           'hardening queued minimum options')
        need(first['report']==carried['report'],'hardening held cut differs from carried result')
        from .public_read_protocol_evidence import crossing
        promises=crossing(own,details['oldEpoch'],held['order'],release['order'])
        need(any(e.physical.f.inspect(e.physical.raw(r['record']),'PROMISE')['proposer']==details['successor'] for r in promises),
             'hardening promise successor')
        need(any(r['event']=='NETWORK_DROP' for rows in traces.values() for r in rows),'hardening partition missing')
        later=response(details['laterOp']);writer=call(details['writerOp']);later_call=call(details['laterOp'])
        need(writer['node']==later_call['node']==details['successor']!=node and writer['outcome']=='SUCCESS' and
             writer['kind']=='addAll' and writer['documents']==[dict(id=80,value='combined successor search'),dict(id=81,value='combined successor java')] and
             later_call['policy']=='LEADER_STRONG' and
             call(details['cancelOp'])['endNanos']<writer['startNanos']<writer['endNanos']<later_call['startNanos']<later_call['endNanos'],
             'hardening surviving majority order')
        floor=details['laterFloor'];need(floor in traces[details['successor']] and floor['event']=='RECOVERY_FLOOR' and
             floor['index']==token.decode(e.physical.raw(later['token']))['index'],'hardening successor floor')
        local=rejoin.packet(floor['local'],manifest);remote=rejoin.packet(floor['remote'],manifest)
        need(local['seal']['node']==details['successor'] and remote['seal']['node']!=details['successor'] and
             len(local['snapshot']['anchors'])==len(remote['snapshot']['anchors'])==floor['index'],'hardening successor floor sources')
        cuts=[r for r in own if r['event']=='CUT_REACHED' and r['cut']=='REPLICA_READ_RELEASED' and r['mode']==details['mode']]
        need(len(cuts)==1 and own[-1]==cuts[0] and second['order']<cuts[0]['order'] and details['pid']==target['pid'],'hardening crash boundary')
        need(target['outcome']=='PENDING' and target['endNanos'] is None and target.get('disconnectNanos') is not None and
             not any(r['event'] in ('CLIENT_SUCCESS','CLIENT_FAILURE') and r.get('opId')==target['opId'] for r in own),'hardening lost response changed')
        before=root/'pre-reopen'/node;need(details['preReopen']==bundle.members(before) and details['preReopen'],'hardening pre-reopen inventory')
        stored=e.physical.storage._inspect(before,8<<30,8<<20,Path(e.read(root/'binding.json')['origin'])/node)
        restore=[r for r in traces[node] if r['generation']==2 and r['event']=='APPLICATION_RESTORED'];need(len(restore)==1,'hardening retained restore')
        snapshot=e.recovery.snapshot(e.physical.raw(restore[0]['snapshot']),manifest)
        need(len(snapshot['anchors'])==stored['provenThrough'] and all(a['entryDigest']==stored['acceptedDigests'][i] for i,a in enumerate(snapshot['anchors'])),
             'hardening retained prefix changed')
        recovered=call(details['recoveredOp']);result=response(details['recoveredOp'])
        need(recovered['node']==node and recovered['generation']==2 and recovered['minimum']==carried['token'] and
             result['documents']==later['documents'] and result['sequence']==later['sequence'] and
             token.decode(e.physical.raw(result['token']))['index']>=token.decode(e.physical.raw(later['token']))['index'],
             'hardening recovered application differs')
        final=probe(details['finalProbe'],0,0,16)
        need(final['pid']==recovered['pid'] and final['generation']==2 and
             event('CLIENT_SUCCESS',recovered['opId'])['order']<final['order'],'hardening final restart probe')
        allowed.update((target['opId'],queued['opId']))
        need(not details['rounds'],'partition case contains pressure rounds')
    else:
        need(len(details['rounds'])==case['cycles'],'hardening cycle count');previous=details['carriedOp'];seen=set()
        own=traces[node]
        for cycle,record in enumerate(details['rounds']):
            need(record['cycle']==cycle and record['carriedOp']==previous,'hardening continuous round chain')
            target=call(record['targetOp']);need(target['node']==node and target['generation']==1 and target['opId'] not in seen,'hardening round target reused');seen.add(target['opId'])
            need(event('CLIENT_INVOKE',target['opId']).get('repeat') is True,'hardening repeated invocation')
            first,pause,release,second=repeated(own,target)
            baseline=probe(record['baselineProbe'],0,0,4);floor_set(record['floors'],token.decode(e.physical.raw(response(previous)['token']))['index'],baseline['order'])
            full=probe(record['fullProbe'],3,1,1);writer_probe=probe(record['writerProbe'],3,1,0)
            queued_cancel=cancelled(record['queuedOp'],record['cancelQueuedOp']);queued_probe=probe(record['queuedProbe'],2,1,1)
            expired=call(record['expiryOp']);expiry_probe=probe(record['expiryProbe'],2,1,1)
            waiting_cancel=cancelled(record['waitingOp'],record['cancelWaitingOp']);waiting_probe=probe(record['waitingProbe'],1,1,2)
            captured_cancel=cancelled(target['opId'],record['cancelCapturedOp'],captured=True);captured_probe=probe(record['capturedProbe'],1,1,2)
            final=probe(record['finalProbe'],0,0,4)
            excess=call(record['excessOp']);writer=call(record['writerOp']);later=call(record['laterOp'])
            order=[baseline['order'],first['order'],pause['order'],full['order'],event('CLIENT_INVOKE',excess['opId'])['order'],
                   event('CLIENT_FAILURE',excess['opId'])['order'],event('CLIENT_INVOKE',writer['opId'])['order'],writer_probe['order'],
                   queued_cancel['order'],queued_probe['order'],event('CLIENT_INVOKE',expired['opId'])['order'],event('CLIENT_FAILURE',expired['opId'])['order'],
                   expiry_probe['order'],waiting_cancel['order'],waiting_probe['order'],captured_cancel['order'],captured_probe['order'],release['order'],second['order'],
                   event('CLIENT_SUCCESS',writer['opId'])['order'],event('CLIENT_INVOKE',later['opId'])['order'],event('CLIENT_SUCCESS',later['opId'])['order'],final['order']]
            need(all(a<b for a,b in zip(order,order[1:])),'hardening sustained ownership/write order')
            need(excess['policy']=='STALE_ALLOWED' and excess['outcome']=='NOT_APPLICABLE' and excess['reasonCode']=='CAPACITY_EXCEEDED','hardening excess outcome')
            need(expired['outcome']=='NOT_APPLICABLE' and expired['reasonCode']=='DEADLINE_EXCEEDED' and expired['waitTimeoutMillis']==case['expiryWaitMillis'],
                 'hardening expiry outcome')
            for op,wait in ((record['waitingOp'],case['behindWaitMillis']),(record['expiryOp'],case['expiryWaitMillis'])):
                attempt=call(op);minimum=token.decode(e.physical.raw(attempt['minimum']));wanted=dict(token.decode(e.physical.raw(response(previous)['token'])),index=(1<<63)-1)
                need(attempt['node']==node and attempt['policy']=='AT_LEAST_INDEX' and attempt['waitTimeoutMillis']==wait and minimum==wanted,'hardening waiting options')
            need(call(record['queuedOp'])['policy']=='STALE_ALLOWED','hardening queued policy')
            first_id=case['firstDocumentId']+case['documentsPerCycle']*cycle
            added=[dict(id=i,value=f'hardening java search {i}') for i in range(first_id,first_id+case['documentsPerCycle'])]
            need(writer['node']==node and writer['kind']=='addAll' and writer['documents']==record['added']==added and writer['outcome']=='SUCCESS','hardening reserved writer')
            before=response(previous);result=response(later['opId'])
            need(later['node']==node and later['policy']=='STALE_ALLOWED' and result['documents']==before['documents']+added and
                 result['sequence']==before['sequence']+1 and token.decode(e.physical.raw(result['token']))['index']>token.decode(e.physical.raw(before['token']))['index'],
                 'hardening round publication differs')
            previous=later['opId'];allowed.update((target['opId'],record['waitingOp'],record['queuedOp'],record['excessOp'],record['expiryOp']))
        floor_set(details['baselineFloors'],token.decode(e.physical.raw(carried['token']))['index'],event('CLIENT_INVOKE',details['rounds'][0]['targetOp'])['order'])
        floor_set(details['finalFloors'],token.decode(e.physical.raw(response(previous)['token']))['index'],own[-1]['order']+1)
    need(all(v['outcome']=='SUCCESS' or v['opId'] in allowed for v in history),'undeclared hardening failed call')


def negatives(root,binding,queries):
    e.validate(root,binding,queries);results=e.negatives(root,binding,queries)
    original=e.traces_at(root);history=e.read(root/'history.json');processes=e.read(root/'processes.json');details=e.read(root/'read-hardening.json')
    for event in ('REPLICA_READ_REPORT_FIRST','REPLICA_READ_REPORT_SECOND'):
        changed=copy.deepcopy(original);row=next(r for rows in changed.values() for r in rows if r['event']==event);row['report']={}
        try:e.validate(root,binding,queries,traces=changed)
        except ValueError as error:
            need(str(error)=='callback report differs from independent captured cut','unrelated hardening query negative: '+str(error))
            results.append(dict(case='changed-'+event.lower(),status='REJECTED',reason=str(error)))
        else:raise ValueError('invalid hardening callback accepted')
    mutations=[('missing-floor','hardening floor voter set'),('missing-cancel','hardening call missing')]
    if binding['scenario']=='sustained-bounded-reads':
        mutations.extend((('missing-round','hardening cycle count'),('reused-round','hardening round target reused')))
    else:
        mutations.extend((('missing-restart-files','hardening pre-reopen inventory'),('borrowed-final-probe','hardening final restart probe')))
    for name,reason in mutations:
        changed=copy.deepcopy(details)
        if name=='missing-floor':changed['baselineFloors'].pop(next(iter(changed['baselineFloors'])))
        elif name=='missing-cancel':
            if changed['rounds']:changed['rounds'][0]['cancelQueuedOp']='missing'
            else:changed['cancelOp']='missing'
        elif name=='missing-round':changed['rounds'].pop()
        elif name=='reused-round':changed['rounds'][1]['targetOp']=changed['rounds'][0]['targetOp']
        elif name=='borrowed-final-probe':changed['finalProbe']=changed['baselineProbe']
        else:changed['preReopen']=[]
        try:schedule(root,binding['scenario'],original,history,processes,details=changed)
        except ValueError as error:
            need(str(error)==reason,'unrelated hardening schedule negative: '+str(error));results.append(dict(case=name,status='REJECTED',reason=str(error)))
        else:raise ValueError('invalid hardening schedule accepted: '+name)
    return results
