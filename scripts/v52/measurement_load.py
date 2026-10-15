"""Clocked offered-load dispatch. Completion never paces the next offer."""
import concurrent.futures
import time
from .evidence import need


def dispatch(calls,duration_nanos,submit,*,clock=time.monotonic_ns,sleep=time.sleep):
    """Submit once at each original due time, retain delays and transport failures.

    submit returns (operation identity, original future). It must not await an API
    response. A dispatch/transport failure stops further offers; pending original
    futures remain observable and the undispatched suffix is explicitly retained.
    """
    need(type(duration_nanos) is int and duration_nanos>0,'load duration')
    offsets=[r['offsetNanos'] for r in calls]
    need(0<len(calls)<=4096 and all(type(v) is int and 0<=v<duration_nanos for v in offsets) and
         all(a<b for a,b in zip(offsets,offsets[1:])),'load due-time order')
    start=clock();rows=[];pending=[];failure=None
    def until(due):
        while True:
            remaining=due-clock()
            if remaining<=0:return
            sleep(remaining/1_000_000_000)
    for ordinal,call in enumerate(calls):
        row=dict(ordinal=ordinal,request=call,dueNanos=start+call['offsetNanos'],status='NOT_DISPATCHED')
        rows.append(row)
        if failure is not None:continue
        until(row['dueNanos']);row['offerNanos']=clock()
        try:
            identity,future=submit(call)
            need(isinstance(identity,str) and identity and isinstance(future,concurrent.futures.Future),'load submit contract')
            row.update(opId=identity,submittedNanos=clock(),status='DISPATCHED');pending.append((row,future))
        except BaseException as error:
            row.update(status='DISPATCH_FAILED',submittedNanos=clock(),failure=dict(type=type(error).__name__,message=str(error)))
            failure=row['failure']
    if failure is None:until(start+duration_nanos)
    return dict(startNanos=start,durationNanos=duration_nanos,dispatchEndNanos=clock(),failure=failure,offers=rows),pending


def drain(receipt,pending,timeout_seconds,*,clock=time.monotonic_ns):
    """One common observation bound, not a fresh timeout or retry per request."""
    need(type(timeout_seconds) in (int,float) and timeout_seconds>0,'load drain bound')
    start=clock();done,unfinished=concurrent.futures.wait([f for _,f in pending],timeout=timeout_seconds)
    for row,future in pending:
        if future not in done:row['completionStatus']='UNOBSERVED';continue
        if future.cancelled():row['completionStatus']='FUTURE_CANCELLED';continue
        try:
            result=future.result()
            row.update(completionStatus='DISCONNECTED' if result is None else 'OBSERVED',response=result)
        except BaseException as error:row.update(completionStatus='OBSERVER_FAILED',completionFailure=dict(type=type(error).__name__,message=str(error)))
    receipt.update(drainStartNanos=start,drainEndNanos=clock(),unobserved=len(unfinished))
    # No cancelling/retrying an uncertain business operation on observer timeout.
    return receipt


def validate(receipt,calls,duration_nanos,history):
    need(receipt['durationNanos']==duration_nanos and receipt['failure'] is None,'load incomplete dispatch')
    start=receipt['startNanos'];rows=receipt['offers'];need(len(rows)==len(calls),'load offered count')
    need(receipt['dispatchEndNanos']>=start+duration_nanos and receipt['drainStartNanos']>=receipt['dispatchEndNanos'] and
         receipt['drainEndNanos']>=receipt['drainStartNanos'] and receipt['unobserved']==0,'load shortened/incomplete observation')
    calls_by_id={v['opId']:v for v in history};need(len(calls_by_id)==len(history),'load duplicate operation identity')
    ids=set();outcomes={};latencies=[]
    for ordinal,(row,request) in enumerate(zip(rows,calls)):
        need(row['ordinal']==ordinal and row['request']==request and row['dueNanos']==start+request['offsetNanos'],'load changed offered request')
        need(row['status']=='DISPATCHED' and row['completionStatus']=='OBSERVED' and row['opId'] not in ids,'load missing/retried offer');ids.add(row['opId'])
        need(start<=row['dueNanos']<=row['offerNanos']<=row['submittedNanos']<=receipt['dispatchEndNanos'],'load dispatch clock')
        call=calls_by_id[row['opId']]
        need(all(call.get(k)==request[k] for k in ('kind','query','document') if k in request),'load request differs from public ledger')
        need(row['offerNanos']<=call['startNanos']<=row['submittedNanos'] and type(call['endNanos']) is int and
             call['startNanos']<=call['endNanos']<=receipt['drainEndNanos'] and call['response']==row['response'],'load response differs from public ledger')
        outcome=call['outcome'];need(outcome==row['response']['outcome'] and outcome!='PENDING','load incomplete outcome')
        outcomes[outcome]=outcomes.get(outcome,0)+1
        latencies.append(dict(opId=row['opId'],kind=request['kind'],window=request.get('window'),outcome=outcome,
                              offerDelayNanos=row['offerNanos']-row['dueNanos'],submitNanos=row['submittedNanos']-row['offerNanos'],
                              dueToResponseNanos=call['endNanos']-row['dueNanos'],offerToResponseNanos=call['endNanos']-row['offerNanos']))
    return dict(offered=len(rows),completed=len(rows),outcomes=outcomes,latencies=latencies)
