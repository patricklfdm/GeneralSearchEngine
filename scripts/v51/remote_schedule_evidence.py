"""Independent dispatch-accounting checks, not an engine semantic oracle."""
from collections import defaultdict
from . import cloud_workload_contract as contract, performance_model as m


def validate(spec, events, result):
    plan = contract.load()
    m.need(spec['schema'] == 'gse-v51-guest-window-v1' and spec['workloadSha256'] == contract.PLAN_SHA256, 'schedule workload identity')
    expected = [dict(r, ordinal=i, payload=r['payload'].hex()) for i,r in enumerate(
        contract.program(plan,spec['cell'],spec['preset']),1) if r['window']==spec['window']]
    m.need(expected and spec['calls'] == expected, 'changed frozen arrival tape')
    name = spec['window']
    if spec['cell'] == 'healthy':
        warmup = plan['healthy']['warmupCalls'] if spec['preset']=='canonical' else plan['presets']['experiment']['healthyWarmupCalls']
        seconds = plan['healthy']['windowSeconds'] if spec['preset']=='canonical' else plan['presets']['experiment']['healthyWindowSeconds']
        duration = warmup if name=='warmup' else seconds
        lanes = 1
    else:
        duration = plan['readHeavy' if spec['cell']=='read-heavy' else 'sustained']['seconds']
        lanes = 4
    m.need((spec['lanes'],spec['durationNanos'],spec['latenessNanos'],spec['burstSpreadNanos'],spec['drainNanos']) ==
           (lanes,duration*10**9,250_000_000,0 if lanes==1 else 10_000_000,10*10**9), 'changed schedule bounds')
    calls = {r['ordinal']:r for r in expected}
    histories = defaultdict(list)
    for event in events:
        m.need(event['ordinal'] in calls, 'unplanned arrival observation')
        histories[event['ordinal']].append(event)
    m.need(set(histories)==set(calls) and len(result['calls'])==len(calls), 'missing arrival observations')
    latest = {r['ordinal']:r for r in result['calls']}
    m.need(len(latest)==len(calls) and set(latest)==set(calls), 'duplicate/extra final arrivals')
    successful = True
    intervals = defaultdict(list)
    bursts = defaultdict(list)
    for ordinal, call in calls.items():
        trace = histories[ordinal]
        states = [r['state'] for r in trace]
        m.need(states in (['NOT_DISPATCHED'], ['RESERVED','NOT_DISPATCHED'], ['RESERVED','UNFINISHED'],
                         ['RESERVED','DISPATCHED','COMPLETED'], ['RESERVED','DISPATCHED','UNFINISHED'],
                         ['RESERVED','DISPATCHED','UNFINISHED','LATE_RESULT']), 'invalid dispatch transition')
        first, last = trace[0], trace[-1]
        m.need(last==latest[ordinal], 'final scheduler row differs from raw events')
        due = result['startedNanos']+call['dueMillis']*10**6
        for event in trace:
            if 'invokedNanos' in event:
                m.need(event['invokedNanos'] == last.get('invokedNanos'), 'invocation clock changed between observations')
        for event in trace:
            m.need(event['lane']==call['lane'] and event['dueNanos']==due and
                   event['offeredNanos']==first['offeredNanos'], 'arrival identity/clock changed')
        if last['state']!='COMPLETED':
            successful=False
            continue
        invoked, ended = last['invokedNanos'], last['endedNanos']
        m.need(due <= first['offeredNanos'] <= invoked <= ended <= result['endedNanos'], 'dispatch/result clock order')
        m.need(invoked-due<=250_000_000, 'late API invocation')
        successful &= isinstance(last['result'],dict) and last['result'].get('outcome')=='SUCCESS'
        intervals[call['lane']].append((invoked,ended))
        bursts[due].append(invoked)
    for values in intervals.values():
        ordered=sorted(values)
        m.need(all(a[1]<=b[0] for a,b in zip(ordered,ordered[1:])), 'overlapping calls in one lane')
    if lanes==4:
        successful &= all(len(v)==4 and max(v)-min(v)<=10_000_000 for v in bursts.values())
    m.need(result['scheduledEndNanos']==result['startedNanos']+duration*10**9, 'window duration changed')
    successful &= result['scheduledEndNanos']<=result['endedNanos']<=result['scheduledEndNanos']+10*10**9
    m.need(result['status']==('PASS' if successful else 'FAIL'), 'scheduler verdict differs from raw observations')
    return dict(status=result['status'],execution='dispatch-accounting-only',calls=len(calls),engineSemanticsQualified=False)
