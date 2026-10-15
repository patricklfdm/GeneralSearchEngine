"""Bounded, complete consumer ledger and explicit-read ownership replay.

This layer proves correlation/lifetime, not physical publication or query truth.
The caller must also run the independent physical and published-core validators.
One declared M04 SIGKILL is admitted only with completed calls and released views.
"""
from collections import Counter
from . import measurement_model as model,measurement_trace as trace,measurement_generations as generations,token
from scripts.v51.runtime_evidence import raw
from .evidence import need

MAX_CALLS_PER_PROCESS=4096
TRANSITIONS={'REPLICA_READ_ADMITTED','REPLICA_READ_CAPTURE_VALIDATED',
             'REPLICA_READ_SETTLING','REPLICA_READ_OWNERSHIP_RELEASED'}
READ_COUNTS=('readsOwned','readsWaiting','readsCaptured','readsSettling','readsAlarms','readsMarker','readsHighWater')
TRANSIENT={'NOT_LEADER','NOT_READY','QUORUM_UNAVAILABLE','STALE_EPOCH','CAPACITY_EXCEEDED','DEADLINE_EXCEEDED'}
REQUEST_FIELDS={'read':{'query','setupToken','minimum'},'update':{'document'},'status':set(),'probe':set(),
                'sample-start':set(),'sample-mark':{'marker'},'sample-stop':set()}
CONTROLLER_FIELDS={'node','pid','generation','startNanos','endNanos','outcome','response','disconnectNanos'}


def integer(value,label,minimum=0):
    need(type(value) is int and value>=minimum,'measurement ledger '+label);return value


def policy(call,mode):
    return ('LEADER_STRONG' if call.get('setupToken') or mode.endswith('strong') else
            'STALE_ALLOWED' if mode=='candidate-stale' else 'AT_LEAST_INDEX')


class Ownership:
    """Only replay transitions whose observation is under the protocol monitor.

    CAPTURED/RELEASED hook counts are sampled outside that monitor: another request
    can change counts before its row is written. They cannot prove a global cut.
    """
    def __init__(self,pending_limit):
        integer(pending_limit,'pending bound',1)
        self.limit=min(64,pending_limit-1);self.owned={};self.admitted=set();self.high_water=0

    def observe(self,row,invocations,released):
        event=row['event']
        if event not in TRANSITIONS:return
        identity=integer(row['readId'],'ownership read identity',1);need(identity in invocations,'measurement ownership lacks invocation')
        invocation=invocations[identity]
        need(row['policy']==invocation['policy'] and row['deadlineNanos']==invocation['deadlineNanos'],
             'measurement ownership changed request')
        for key in ('preparing','cancelled','completionReturned'):need(type(row[key]) is bool,'measurement ownership flag type')
        integer(row['cancelling'],'cancellation count')
        need(not row['cancelled'] and row['cancelling']==0,'measurement undeclared cancellation')
        if event=='REPLICA_READ_ADMITTED':
            need(identity not in self.admitted and row['phase']=='QUEUED','measurement duplicate/invalid admission')
            self.admitted.add(identity);self.owned[identity]='QUEUED';self.high_water=max(self.high_water,len(self.owned))
        elif event=='REPLICA_READ_CAPTURE_VALIDATED':
            need(self.owned.get(identity)=='QUEUED' and row['phase']=='CAPTURED' and not row['preparing'],
                 'measurement capture without queued ownership')
            self.owned[identity]='CAPTURED'
        elif event=='REPLICA_READ_SETTLING':
            previous=self.owned.get(identity)
            need(previous in ('QUEUED','CAPTURED') and row['phase']=='SETTLING' and
                 (previous!='CAPTURED' or identity in released),'measurement settling before view release')
            self.owned[identity]='SETTLING'
        else:
            need(self.owned.get(identity)=='SETTLING' and row['phase']=='SETTLING' and
                 row['completionReturned'] and not row['preparing'],'measurement premature ownership release')
            del self.owned[identity]
        if event!='REPLICA_READ_OWNERSHIP_RELEASED':need(not row['completionReturned'],'measurement completion before settlement')
        counts=Counter(self.owned.values())
        expected=dict(owned=len(self.owned),waiting=counts['QUEUED'],captured=counts['CAPTURED'],
                      settling=counts['SETTLING'],alarms=counts['QUEUED'],highWater=self.high_water)
        need(all(type(row[k]) is int and row[k]==value for k,value in expected.items()) and
             0<=integer(row['marker'],'dispatch marker')<=1 and self.high_water<=self.limit and counts['CAPTURED']<=1,
             'measurement ownership accounting differs from transitions')


def request(call):
    kind=call['kind'];need(kind in REQUEST_FIELDS,'measurement undeclared command')
    value={k:v for k,v in call.items() if k not in CONTROLLER_FIELDS}
    need(set(value)<={'opId','kind'}|REQUEST_FIELDS[kind],'measurement undeclared request fields')
    if kind=='read':
        need('query' in value and ('setupToken' not in value or value['setupToken'] is True),'measurement read request shape')
    if kind=='update':need('document' in value,'measurement update request shape')
    return value


def failure(call,response,invocation,captured,callbacks,mode,*,allow_progress_not_reached=False):
    """Admit observed transient classifications, without inferring their cause."""
    need(not any(k in response for k in ('answer','token','sequence','policy')),'measurement failed call carried result')
    reason=response.get('reasonCode');outcome=response['outcome'];kind=call['kind']
    need(isinstance(response.get('reason'),str) and response['reason'],'measurement failure detail missing')
    if kind=='read':
        need(not captured and not callbacks,'measurement rejected read exposed view')
        if reason=='PROGRESS_NOT_REACHED':
            need(allow_progress_not_reached and mode=='candidate-minimum' and outcome=='REJECTED' and invocation is not None and
                 invocation['policy']=='AT_LEAST_INDEX' and invocation['waitTimeoutMillis']==0,
                 'measurement undeclared zero-wait progress rejection')
            return reason
        client_rejected=reason=='RejectedExecutionException' and outcome=='VALIDATION_FAILURE'
        if not client_rejected:
            need(reason in TRANSIENT and outcome=='NOT_APPLICABLE','measurement undeclared read failure')
            if reason=='DEADLINE_EXCEEDED' and invocation is not None and not mode.endswith('legacy-strong'):
                need(response['apiEndNanos']>=invocation['deadlineNanos'],'measurement deadline rejection before deadline')
        return 'CLIENT_REJECTED' if client_rejected else reason
    need(kind=='update' and reason in TRANSIENT and outcome in ('NOT_SUBMITTED','INDETERMINATE'),
         'measurement undeclared mutation/control failure')
    return reason


def validate(traces,processes,history,mode,*,pending_limit=64,minimum_wait_millis=5000,allow_progress_not_reached=False,restarted=None):
    need(mode in model.MODES,'measurement ledger mode')
    need(type(minimum_wait_millis) is int and minimum_wait_millis in (0,1000,5000,60000) and
         type(allow_progress_not_reached) is bool and (not allow_progress_not_reached or minimum_wait_millis==0),
         'measurement ledger wait profile')
    generations.validate(processes,restarted)
    need(type(history) is list and len(history)<=len(processes)*MAX_CALLS_PER_PROCESS,'measurement controller ledger bound')
    need(set(traces)=={p['node'] for p in processes},'measurement ledger trace voter set')
    calls={c['opId']:c for c in history}
    need(len(calls)==len(history) and all(isinstance(k,str) and 0<len(k)<=128 for k in calls),'measurement duplicate/invalid operation identity')
    by_process={(p['node'],p['pid'],p['generation']):{} for p in processes}
    for call in calls.values():
        key=call['node'],call['pid'],call['generation'];need(key in by_process,'measurement foreign consumer')
        need(call['outcome']!='PENDING' and 'response' in call and
             integer(call['startNanos'],'controller start')<integer(call['endNanos'],'controller end'),
             'measurement incomplete controller call')
        request(call);by_process[key][call['opId']]=call
    outcomes={kind:Counter() for kind in ('read','update','control')};reasons={kind:Counter() for kind in outcomes};resources={}
    legacy=mode.endswith('legacy-strong')
    for process in processes:
        node=process['node'];own=by_process[node,process['pid'],process['generation']];need(len(own)<=MAX_CALLS_PER_PROCESS,'measurement per-consumer ledger bound')
        need(all(c['pid']==process['pid'] and c['generation']==process['generation'] for c in own.values()),'measurement controller process binding')
        received={};invoked={};responses={};reads={};read_by_call={};captured={};entered={};released={};callbacks={}
        ownership=Ownership(pending_limit);idle=False;closed=False;last_order=0;last_clock=0
        for row in generations.rows(traces,process,processes):
            need(row['node']==node and row['pid']==process['pid'] and row['generation']==process['generation'],'measurement ledger observation process')
            need(integer(row['order'],'observation order',1)>last_order and integer(row['localNanos'],'local clock')>=last_clock,
                 'measurement ledger observation order');last_order=row['order'];last_clock=row['localNanos']
            event=row['event'];identity=row.get('opId')
            if event in ('CLIENT_RECEIVED','CLIENT_INVOKE','CLIENT_SUCCESS','CLIENT_FAILURE','CLIENT_CALLBACK_BEGIN','CLIENT_CALLBACK_END'):
                need(not idle and identity in own,'measurement unrecorded/late consumer operation')
                call=own[identity]
                if event in ('CLIENT_RECEIVED','CLIENT_INVOKE'):
                    need({k:v for k,v in row.items() if k not in trace.META}==request(call),'measurement request differs from controller')
                    if event=='CLIENT_RECEIVED':need(identity not in received,'measurement duplicate received command');received[identity]=row
                    else:
                        need(identity in received and identity not in invoked,'measurement duplicate/unreceived invocation');invoked[identity]=row
                elif event.startswith('CLIENT_CALLBACK_'):
                    need(call['kind']=='read' and identity in read_by_call and read_by_call[identity] in entered and
                         read_by_call[identity] not in released,'measurement callback outside captured view')
                    sequence=callbacks.setdefault(identity,[]);sequence.append(event)
                    need(sequence in (['CLIENT_CALLBACK_BEGIN'],['CLIENT_CALLBACK_BEGIN','CLIENT_CALLBACK_END']), 'measurement callback sequence')
                else:
                    need(identity in received and identity not in responses,'measurement duplicate/unreceived response')
                    response=call['response'];need({k:v for k,v in row.items() if k not in trace.META}==response and
                        row['kind']==call['kind'] and row['outcome']==call['outcome'] and
                        (event=='CLIENT_SUCCESS')==(call['outcome']=='SUCCESS'),'measurement ledger response binding')
                    for key in ('receivedNanos','apiStartNanos','apiEndNanos'):integer(row[key],key)
                    need(row['receivedNanos']<=received[identity]['localNanos']<=row['apiEndNanos']<=row['localNanos'] and
                         row['receivedNanos']<=row['apiStartNanos']<=row['apiEndNanos'],'measurement ledger response timing')
                    client_rejected=row.get('reasonCode')=='RejectedExecutionException' and call['kind']=='read' and row['outcome']=='VALIDATION_FAILURE'
                    if client_rejected:need(identity not in invoked and identity not in read_by_call,'measurement client rejection after API invocation')
                    else:need(identity in invoked and received[identity]['order']<invoked[identity]['order']<row['order'] and
                              received[identity]['localNanos']<=row['apiStartNanos']<=invoked[identity]['localNanos']<=row['apiEndNanos'],
                              'measurement missing/mistimed API invocation')
                    read_id=read_by_call.get(identity)
                    if read_id is not None:
                        need(reads[read_id]['localNanos']<=row['apiEndNanos'],'measurement response clock before runtime invocation')
                        if read_id in released:need(released[read_id]['localNanos']<=row['apiEndNanos'],'measurement response clock before view release')
                        if read_id in ownership.admitted:
                            need(ownership.owned.get(read_id) in (None,'SETTLING'),'measurement response before owned settlement')
                    if call['outcome']=='SUCCESS':
                        need('reasonCode' not in row and 'reason' not in row,'measurement success carried failure')
                        if call['kind']=='read':
                            need(read_id in released and 'answer' in row,'measurement successful read lacks released view')
                            if not legacy:need(callbacks.get(identity)==['CLIENT_CALLBACK_BEGIN','CLIENT_CALLBACK_END'],'measurement successful read lacks callback')
                    else:
                        reason=failure(call,row,reads.get(read_id),read_id in captured,callbacks.get(identity),mode,
                                       allow_progress_not_reached=allow_progress_not_reached)
                        reasons[call['kind'] if call['kind'] in ('read','update') else 'control'][reason]+=1
                    outcomes[call['kind'] if call['kind'] in ('read','update') else 'control'][call['outcome']]+=1
                    responses[identity]=row
            elif event in ('PUBLIC_READ_INVOKE','REPLICA_READ_INVOKED'):
                need(not idle and event==('PUBLIC_READ_INVOKE' if legacy else 'REPLICA_READ_INVOKED'),'measurement ledger wrong read capability')
                read_id=integer(row['readId'],'read identity',1)
                need(identity in invoked and own[identity]['kind']=='read' and identity not in read_by_call and read_id not in reads,
                     'measurement duplicate/uninvoked runtime read')
                need(identity not in responses,'measurement runtime invocation after response')
                if not legacy:
                    expected=policy(own[identity],mode);minimum=own[identity].get('minimum','') if expected=='AT_LEAST_INDEX' else ''
                    need(row['policy']==expected and row['minimum']==minimum and type(row['waitTimeoutMillis']) is int and
                         row['waitTimeoutMillis']==(minimum_wait_millis if expected=='AT_LEAST_INDEX' else 0),'measurement invoked policy/options changed')
                    integer(row['deadlineNanos'],'read deadline')
                    if minimum:token.decode(raw(minimum))
                reads[read_id]=row;read_by_call[identity]=read_id
            elif event in ('READ_CAPTURE_VALIDATED','REPLICA_READ_CAPTURE_VALIDATED','READ_CAPTURED','REPLICA_READ_CAPTURED','READ_RELEASED','REPLICA_READ_RELEASED'):
                need(not idle and event.startswith('READ_' if legacy else 'REPLICA_READ_'),'measurement ledger wrong capture capability')
                read_id=integer(row['readId'],'capture read identity',1);need(read_id in reads and reads[read_id]['opId'] not in responses,'measurement capture after response/uninvoked')
                if event.endswith('_CAPTURE_VALIDATED'):
                    need(read_id not in captured,'measurement duplicate capture');captured[read_id]=row
                elif event.endswith('_CAPTURED'):
                    need(read_id in captured and read_id not in entered,'measurement missing/duplicate entered view');entered[read_id]=row
                else:
                    need(read_id in entered and read_id not in released,'measurement missing/duplicate released view')
                    if not legacy:need(callbacks.get(reads[read_id]['opId'])==['CLIENT_CALLBACK_BEGIN','CLIENT_CALLBACK_END'],'measurement released view lacks callback')
                    released[read_id]=row
            elif event=='CLIENT_IDLE':
                need(not idle and set(responses)==set(own) and not ownership.owned,'measurement incomplete idle ledger');idle=True
                queues=row['queues'];need(type(queues.get('admissionAvailable')) is int and queues['admissionAvailable']==pending_limit,'measurement idle admission leak')
                if mode!='published-v51-legacy-strong':
                    need(all(type(queues.get(k)) is int for k in READ_COUNTS),'measurement idle read counters missing')
                    need(all(queues[k]==0 for k in READ_COUNTS[:-1]) and queues['readsHighWater']==ownership.high_water,'measurement idle read counters differ')
            elif event=='CLOSED':need(idle and not closed,'measurement missing/duplicate orderly close');closed=True
            if event in TRANSITIONS:
                need(not idle,'measurement ownership transition after idle')
                read_id=integer(row['readId'],'ownership read identity',1)
                if event!='REPLICA_READ_OWNERSHIP_RELEASED':
                    need(read_id in reads and reads[read_id]['opId'] not in responses,'measurement ownership transition after response')
            ownership.observe(row,reads,released)
        need((not idle and not closed if process['exitCode']==-9 else idle and closed) and
             set(received)==set(responses)==set(own) and not ownership.owned,'measurement incomplete stopped ledger')
        key=node if restarted is None else node+'-g'+str(process['generation'])
        resources[key]=dict(admitted=len(ownership.admitted),highWater=ownership.high_water,ownedAtClose=0)
        if process['exitCode']==-9:resources[key].update(termination='SIGKILL',ownedAtExit=resources[key].pop('ownedAtClose'))
    return dict(status='PASS',execution='complete-consumer-ledger-only',qualifiedMeasurement=False,
                outcomes={k:dict(sorted(v.items())) for k,v in outcomes.items()},
                reasons={k:dict(sorted(v.items())) for k,v in reasons.items()},resources=resources)
