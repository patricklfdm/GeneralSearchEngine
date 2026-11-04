"""Bind actual automatic restart observations to unchanged physical/network history.

The sidecar samples original event ordinals and clocks; it never inserts protocol
markers or reconstructs lifecycle state from final diagnostics. One deliberate
higher-ballot heartbeat qualifies one restart, not arbitrary fault schedules.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile

from . import automatic_restart_network as network
from . import automatic_restart_current as current
from . import automatic_lifecycle as lifecycle
from . import joining_history_run as h

need=network.need;f=network.f;SCHEMA='gse-v53-restart-lifecycle-capture-v1'
CAPTURE='capture.json';OBSERVATIONS=lifecycle.FILE;BUDGET=300_000_000_000
FIELDS={'schema','firstEvent','prefixSha256','attachedNanos','events','opened','requests','captureFailure',
        'observationFailure','producerPassed','ownerDrained','resourceLeases','eventsSha256','planSha256'}


def attachment(events,value,rows,events_hash,plan_hash):
    need(type(value) is dict and set(value)==FIELDS and value['schema']==SCHEMA,'restart lifecycle capture shape')
    need(value['producerPassed'] is True and value['ownerDrained'] is True and
         value['captureFailure']==value['observationFailure']=='' and
         type(value['resourceLeases']) is list and len(value['resourceLeases'])==3 and
         all(type(v) is int and v==0 for v in value['resourceLeases']),'restart lifecycle complete producer drain')
    need(value['eventsSha256']==events_hash and value['planSha256']==plan_hash,'restart lifecycle original binding')
    first=value['firstEvent'];attached=value['attachedNanos'];clocks=value['events']
    need(type(first) is int and 0<=first<len(events) and type(attached) is int and attached>=0 and
         value['prefixSha256']==h.digest(f.canonical(events[:first])),'restart lifecycle original trace prefix')
    need(type(clocks) is list and len(clocks)==len(events)-first<=65536,'restart lifecycle complete event clocks')
    previous=attached;times={first-1:attached}
    for index,row in enumerate(clocks,first):
        need(type(row) is dict and set(row)=={'index','nanoTime','sha256'} and type(row['index']) is int and
             row['index']==index and row['sha256']==h.digest(f.canonical(events[index])) and
             type(row['nanoTime']) is int and row['nanoTime']>=previous,'restart lifecycle exact observed event clock')
        times[index]=previous=row['nanoTime']
    def anchor(row):
        after=row.get('afterEvent');at=row.get('nanoTime')
        need(type(after) is int and first-1<=after<len(events) and type(at) is int and at>=times[after] and
             (after+1==len(events) or at<=times[after+1]),'restart lifecycle original event anchor')
        return after,at
    opened=value['opened']
    need(type(opened) is dict and set(opened)=={'node','afterEvent','nanoTime','budgetNanos'} and opened['node']=='node-1'
         and type(opened['budgetNanos']) is int and opened['budgetNanos']==BUDGET,'restart lifecycle actual owner construction')
    open_after,open_time=anchor(opened)
    need(type(rows) is list and 0<len(rows)<=256,'restart lifecycle bounded observations')
    prior_after,prior_time=open_after,open_time
    for ordinal,row in enumerate(rows,1):
        need(type(row) is dict and set(row)==lifecycle.FIELDS and row['node']=='node-1' and row['event'] in lifecycle.EVENTS and
             row['state'] in lifecycle.STATES and type(row['detail']) is str and len(row['detail'])<=256,
             'restart lifecycle observation shape')
        need(type(row['ordinal']) is int and row['ordinal']==ordinal,'restart lifecycle complete observation ordinal')
        after,at=anchor(row)
        need(after>=prior_after and at>=prior_time,'restart lifecycle observation order')
        need(type(row['rounds']) is int and 0<=row['rounds']<=3 and type(row['pending']) is int and 0<=row['pending']<=64 and
             type(row['originalStarted']) is int and open_time<=row['originalStarted']<=at,'restart lifecycle bounded counters')
        prior_after,prior_time=after,at
    state=lifecycle.owner(events,rows,opened_after=open_after)
    need(state['started'] and state['rounds']==2 and state['losses']==['HIGHER_BALLOT'] and state['drained'] and
         len(state['readyCallbacks'])==2,'restart lifecycle exact recovered owner')
    need(not any(v['event']=='FAILED' for v in rows),'restart lifecycle retained terminal failure')
    begun=rows[0]['originalStarted']
    need(all(v['nanoTime']-begun<BUDGET for v in rows if v['event'] not in ('CLOSE','SESSION_CLOSED','TERMINATED','DRAINED')),
         'restart lifecycle original operation deadline')
    need(all(0<=times[i]-begun<BUDGET for i,v in enumerate(events) if v['event'] in
             ('ROUND_INSTALLED','ROUND_SLOT_BEGIN','ROUND_SLOT_COMPLETE','ROUND_BEFORE_READY')),
         'restart lifecycle original operation deadline')
    requests=value['requests']
    need(type(requests) is list and len(requests)==1 and type(requests[0]) is dict and
         set(requests[0])=={'node','afterEvent','nanoTime','request'} and requests[0]['node']=='node-1',
         'restart lifecycle one actual incoming fence')
    received=requests[0];anchor(received)
    ready=[v for v in rows if v['event']=='READY'];loss=next(v for v in rows if v['event']=='LOSS')
    need(ready[0]['nanoTime']<received['nanoTime']<=loss['nanoTime'] and ready[0]['afterEvent']<=received['afterEvent']<=loss['afterEvent']
         and loss['state']=='READY' and loss['rounds']==1 and loss['pending']==0,'restart lifecycle received fence before ready loss')
    # State-machine validation already demands close -> open -> next round. Bind
    # these observations to the next actual native campaign and its fresh READY.
    begins=[v for v in rows if v['event']=='ROUND_BEGIN'];installed=[i for i,v in enumerate(events) if v['event']=='ROUND_INSTALLED']
    need(len(begins)==len(installed)==2 and all(v['afterEvent']<at for v,at in zip(begins,installed)) and
         state['readyCallbacks'][0]<begins[1]['afterEvent']<installed[1]<state['readyCallbacks'][1],
         'restart lifecycle new session before native reactivation')
    return dict(state=state,observations=len(rows),eventClocks=len(clocks),originalStarted=begun,
                lossAfterEvent=loss['afterEvent'],receivedAfterEvent=received['afterEvent'])


def validate(root,sidecar):
    root=Path(root);sidecar=Path(sidecar);before=h.inventory(root);captured=h.inventory(sidecar)
    need(set(captured['files'])=={CAPTURE,OBSERVATIONS} and not captured['directories'],'restart lifecycle exact attachment inventory')
    # An unrelated corrupt original must fail before lifecycle mutations are tried.
    original=current.validate(root)
    events=h.read_json(root,'events.json',32*1024*1024)
    value=h.read_json(sidecar,CAPTURE,16*1024*1024);rows=h.read_json(sidecar,OBSERVATIONS,1024*1024)
    result=attachment(events,value,rows,before['files']['events.json'],before['files']['original-plan.gsbp'])
    try:incoming=base64.b64decode(value['requests'][0]['request'],validate=True)
    except (ValueError,TypeError) as error:raise ValueError('restart lifecycle original received fence') from error
    need(incoming==h.snapshot.s.regular(root/'fence-request.gsw',h.snapshot.MIB),'restart lifecycle original received fence')
    # network.validate derives the peer allocator, exact higher ballot/request,
    # original correlated ACK and its delivery between the two physical campaigns.
    need(h.inventory(root)==before and h.inventory(sidecar)==captured,'restart lifecycle changed original')
    return dict(status='PARTIAL',scope='one-native-higher-ballot-observed-restart',precondition=original,**result,
                actualStateTransitionsQualified=True,originalDeadlinePreserved=True,lossCauseQualified=True,
                physicalNetworkQualified=True,fullLifecycleQualified=False,processRestart=False,
                finalSourceCohortQualified=False,phase3Complete=False)


NEGATIVES={
 'missing-clock':'restart lifecycle complete event clocks',
 'clock-bytes':'restart lifecycle exact observed event clock',
 'clock-index':'restart lifecycle exact observed event clock',
 'clock-order':'restart lifecycle exact observed event clock',
 'prefix-binding':'restart lifecycle original trace prefix',
 'plan-binding':'restart lifecycle original binding',
 'capture-failed':'restart lifecycle complete producer drain',
 'observer-failed':'restart lifecycle complete producer drain',
 'resource-retained':'restart lifecycle complete producer drain',
 'owner-not-drained':'restart lifecycle complete producer drain',
 'boolean-budget':'restart lifecycle actual owner construction',
 'missing-observation':'restart lifecycle complete observation ordinal',
 'renewed-start':'automatic lifecycle renewed original deadline',
 'session-open-before-close':'automatic lifecycle fresh session before old drain',
 'stale-ready':'automatic lifecycle original ready callback',
 'changed-loss':'restart lifecycle exact recovered owner',
 'missing-fence':'restart lifecycle one actual incoming fence',
 'changed-fence':'restart lifecycle original received fence',
 'loss-before-receive':'restart lifecycle received fence before ready loss',
 'undrained-pending':'automatic lifecycle worker termination order',
 'late-operation':'restart lifecycle original operation deadline',
 'late-data-completion':'restart lifecycle original operation deadline',
}


def mutate(sidecar,name,*,events=None):
    need(name in NEGATIVES,'restart lifecycle declared negative')
    value=h.read_json(sidecar,CAPTURE,16*1024*1024);rows=h.read_json(sidecar,OBSERVATIONS,1024*1024)
    find=lambda event:next(v for v in rows if v['event']==event)
    if name=='missing-clock':value['events'].pop()
    elif name=='clock-bytes':value['events'][0]['sha256']='0'*64
    elif name=='clock-index':value['events'][0]['index']=True
    elif name=='clock-order':value['events'][0]['nanoTime']=value['attachedNanos']-1
    elif name=='prefix-binding':value['prefixSha256']='0'*64
    elif name=='plan-binding':value['planSha256']='0'*64
    elif name=='capture-failed':value['captureFailure']='failed capture'
    elif name=='observer-failed':value['observationFailure']='failed observation'
    elif name=='resource-retained':value['resourceLeases'][0]=1
    elif name=='owner-not-drained':value['ownerDrained']=False
    elif name=='boolean-budget':value['opened']['budgetNanos']=True
    elif name=='missing-observation':rows.pop(1)
    elif name=='renewed-start':find('SESSION_OPENED')['originalStarted']+=1
    elif name=='session-open-before-close':find('SESSION_OPENED')['event'],find('SESSION_CLOSED')['event']='SESSION_CLOSED','SESSION_OPENED'
    elif name=='stale-ready':[v for v in rows if v['event']=='READY'][1]['detail']=find('READY')['detail']
    elif name=='changed-loss':find('LOSS')['detail']='CONTACT_UNAVAILABLE'
    elif name=='missing-fence':value['requests']=[]
    elif name=='changed-fence':value['requests'][0]['request']=base64.b64encode(b'changed original').decode()
    elif name=='loss-before-receive':
        loss=find('LOSS');value['requests'][0].update(afterEvent=loss['afterEvent'],nanoTime=loss['nanoTime']+1)
    elif name=='undrained-pending':find('TERMINATED')['pending']=1
    elif name=='late-operation':
        # Preserve relative actual-clock anchors and the immutable original start;
        # only move the entire later timeline to just beyond that same deadline.
        loss=find('LOSS');at=loss['afterEvent'];nanos=loss['nanoTime'];shift=BUDGET
        for row in value['events']:
            if row['index']>at:row['nanoTime']+=shift
        for row in rows:
            if row['nanoTime']>=nanos:row['nanoTime']+=shift
    elif name=='late-data-completion':
        # Last completion is after the second READY; lifecycle close alone must
        # not exempt a real operation from its original deadline.
        need(type(events) is list,'restart lifecycle original events for completion mutation')
        at=max(i for i,v in enumerate(events) if v['event']=='ROUND_SLOT_COMPLETE')
        nanos=next(v['nanoTime'] for v in value['events'] if v['index']==at)
        for row in value['events']:
            if row['index']>=at:row['nanoTime']+=BUDGET
        for row in rows:
            if row['nanoTime']>=nanos:row['nanoTime']+=BUDGET
    (sidecar/CAPTURE).write_bytes(f.canonical(value));(sidecar/OBSERVATIONS).write_bytes(f.canonical(rows))


def qualify(root,sidecar):
    root=Path(root);sidecar=Path(sidecar);original=validate(root,sidecar);before=h.inventory(root);captured=h.inventory(sidecar);negatives=[]
    events=h.read_json(root,'events.json',32*1024*1024)
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-restart-lifecycle-negative-') as temp:
            copy=Path(temp)/'sidecar';shutil.copytree(sidecar,copy);mutate(copy,name,events=events)
            try:validate(root,copy)
            except ValueError as error:need(str(error)==reason,'unrelated restart lifecycle negative '+name+': '+str(error))
            else:raise ValueError('restart lifecycle accepted mutation: '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason,physicalOriginalUnchanged=True))
        print(json.dumps(dict(case=name,completed=len(negatives),total=len(NEGATIVES))),flush=True)
    need(h.inventory(root)==before and h.inventory(sidecar)==captured,'restart lifecycle negative changed original')
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('sidecar');parser.add_argument('--qualify',action='store_true')
    args=parser.parse_args();print(json.dumps((qualify if args.qualify else validate)(args.root,args.sidecar),sort_keys=True))
