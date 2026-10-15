"""Validate JVM-local sampled resources without treating them as exact peaks."""
from .evidence import need
from . import measurement_trace as trace

INTERVAL=1_000_000_000
COUNTERS=('processCpuNanos','allocatedBytes')
READ_COUNTS=('readsOwned','readsWaiting','readsCaptured','readsSettling','readsAlarms','readsMarker','readsHighWater')


def integer(value,label,minimum=0):
    need(type(value) is int and value>=minimum,'sample '+label);return value


def metric(value,label):
    need(type(value) is dict and value.get('status') in ('AVAILABLE','UNAVAILABLE','UNSUPPORTED','DISABLED','UNDEFINED'),'sample metric status: '+label)
    if value['status']=='AVAILABLE':
        need(set(value)=={'status','value'},'sample metric fields: '+label);return integer(value['value'],'metric value: '+label)
    need(set(value)=={'status'},'sample fabricated unavailable metric: '+label);return None


def validate(rows,mode,*,pending_limit=64):
    need(2<=len(rows)<=1024 and rows[0]['sampleKind']=='START' and rows[-1]['sampleKind']=='STOP','sample start/stop coverage')
    origin=rows[0]['dueNanos'];periodic=1;previous=None;last_counters={};first_counters={};availability={};marks=[]
    peaks={k:0 for k in ('heapUsedBytes','nonHeapUsedBytes','liveThreads','retainedBytes','consumerActive','consumerQueued')}
    durations=[];delays=[]
    for ordinal,row in enumerate(rows):
        need(row['sampleOrdinal']==ordinal and type(row['sampleOrdinal']) is int,'sample missing/duplicate ordinal')
        kind=row['sampleKind'];need(kind in ('START','PERIODIC','MARK','STOP'),'sample kind')
        if kind=='START':need(ordinal==0,'sample duplicate start')
        if kind=='STOP':need(ordinal==len(rows)-1,'sample early stop')
        start=integer(row['sampleStartNanos'],'start clock');end=integer(row['sampleEndNanos'],'end clock');due=integer(row['dueNanos'],'due clock')
        need(due<=start<=end<=row['localNanos'] and (previous is None or previous['localNanos']<=start),'sample local clock order')
        if previous:need(all(row[k]==previous[k] for k in ('pid','generation','node')),'sample process identity')
        if kind=='PERIODIC':need(due==origin+periodic*INTERVAL,'sample changed periodic due time');periodic+=1
        if kind=='MARK':
            need(row['marker'] in ('warmup-start','measured-start','measured-end'),'sample marker');marks.append(row['marker'])
        else:need(row['marker']=='','sample unexpected marker')
        durations.append(end-start);delays.append(start-due)
        for key in peaks:peaks[key]=max(peaks[key],integer(row[key],key))
        need(row['consumerActive']<=8 and row['consumerQueued']<=64,'sample consumer queue bound')
        committed=integer(row['heapCommittedBytes'],'heap committed');maximum=metric(row['heapMaxBytes'],'heapMaxBytes')
        need(row['heapUsedBytes']<=committed and (maximum is None or committed<=maximum),'sample heap bounds')
        need(integer(row['peakLiveThreads'],'thread peak')>=row['liveThreads'],'sample live thread peak')
        for key in COUNTERS:
            value=metric(row[key],key);availability.setdefault(key,set()).add(row[key]['status'])
            if value is not None:
                need(key not in last_counters or value>=last_counters[key],'sample cumulative counter regressed: '+key)
                first_counters.setdefault(key,value);last_counters[key]=value
        gc=row['gc'];need(isinstance(gc,list) and len(gc)<=16 and len({v['name'] for v in gc})==len(gc),'sample collector identities')
        for item in gc:
            need(isinstance(item['name'],str) and item['name'],'sample collector name');metric(item['count'],'gc count');metric(item['millis'],'gc millis')
        queues=row['queues'];need(type(queues) is dict and 'admissionAvailable' in queues,'sample missing admission')
        for key,value in queues.items():integer(value,'queue '+key)
        need(queues['admissionAvailable']<=pending_limit,'sample admission bound')
        if mode!='published-v51-legacy-strong':
            need(all(key in queues for key in READ_COUNTS),'sample missing candidate read counters')
            limit=min(64,pending_limit-1)
            need(queues['readsOwned']==sum(queues[k] for k in ('readsWaiting','readsCaptured','readsSettling')) and
                 queues['readsOwned']<=queues['readsHighWater']<=limit and queues['readsAlarms']<=queues['readsOwned'] and
                 queues['readsMarker']<=1,'sample explicit read ownership')
        previous=row
    need(not marks or marks==['warmup-start','measured-start','measured-end'],'sample incomplete/out-of-order window markers')
    # A delayed or skipped final timer firing is reported, never synthesized. The
    # start/stop interval is JVM-local and does not imply an exact controller cut.
    elapsed=rows[-1]['sampleEndNanos']-rows[0]['sampleStartNanos']
    deltas={key:dict(status='AVAILABLE',value=last_counters[key]-first_counters[key]) if availability[key]=={'AVAILABLE'} else
            dict(status='INCOMPLETE',observedStatuses=sorted(availability[key])) for key in COUNTERS}
    return dict(samples=len(rows),periodicSamples=periodic-1,elapsedNanos=elapsed,sampledHighWater=peaks,
                cumulativeDeltas=deltas,sampleDurationNanos=durations,sampleDelayNanos=delays,
                semantics='process-wide-including-observer; sampled-high-water-is-not-exact-peak')


def windows(rows,mode,controls,offered,markers,node):
    """Resource observations at actual asynchronous boundaries, never fake clocks."""
    complete=validate(rows,mode)
    need([c['kind'] for c in controls]==['sample-start','sample-mark','sample-mark','sample-mark','sample-stop'] and
         all(c['outcome']=='SUCCESS' for c in controls),'sample window control ledger')
    need(controls[0]['endNanos']<=offered['startNanos'] and controls[-1]['startNanos']>=offered['drainEndNanos'],
         'sample window controls do not cover dispatch')
    marks=[r for r in rows if r['sampleKind']=='MARK']
    need([r['marker'] for r in marks]==[m['name'] for m in markers]==['warmup-start','measured-start','measured-end'],
         'sample complete window boundaries')
    for call,sample in zip(controls,[rows[0],*marks,rows[-1]]):
        need(call['node']==node and call['response']['sample']=={k:v for k,v in sample.items() if k not in trace.META},
             'sample boundary response differs from observation')
    need(all(c['opId']==m['operations'][node] and c['marker']==m['name'] for c,m in zip(controls[1:-1],markers)),
         'sample boundary differs from original dispatch')
    result={}
    for ordinal,name in enumerate(('warmup','measured')):
        first,last=marks[ordinal:ordinal+2];selected=[r for r in rows if first['sampleOrdinal']<=r['sampleOrdinal']<=last['sampleOrdinal']]
        deltas={}
        for key in COUNTERS:
            availability={r[key]['status'] for r in selected}
            deltas[key]=(dict(status='AVAILABLE',value=last[key]['value']-first[key]['value']) if availability=={'AVAILABLE'} else
                         dict(status='INCOMPLETE',observedStatuses=sorted(availability)))
        peaks={key:max(r[key] for r in selected) for key in ('heapUsedBytes','nonHeapUsedBytes','liveThreads','retainedBytes','consumerActive','consumerQueued')}
        result[name]=dict(samples=len(selected),periodicSamples=sum(r['sampleKind']=='PERIODIC' for r in selected),
            nominalControllerDurationNanos=markers[ordinal+1]['dueNanos']-markers[ordinal]['dueNanos'],
            observedBoundarySpacingNanos=last['sampleStartNanos']-first['sampleStartNanos'],
            boundaryClockIntervals=dict(start=[first['sampleStartNanos'],first['sampleEndNanos']],end=[last['sampleStartNanos'],last['sampleEndNanos']]),
            cumulativeDeltas=deltas,sampledHighWater=peaks)
    return dict(status='PASS',wholeSession=complete,windows=result,
                semantics='actual process-local marker observations; controller dispatch lag retained; includes observer overhead; sampled peaks only')
