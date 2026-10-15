"""Exact M01 offered-window accounting, separate from physical qualification.

No timings are synthesized and no failure is removed from latency distributions.
The execution entry must additionally bind source/build/environment, physical
cuts, actual core answers, lifecycle and process-resource observations.
"""
from collections import Counter
from . import measurement_model as model,measurement_load as load
from .evidence import need

DURATION=180_000_000_000
WINDOWS=(('warmup',0,60_000_000_000,600,60),('measured',60_000_000_000,120_000_000_000,1200,120))


def distribution(values):
    need(all(type(v) is int and v>=0 for v in values),'measurement negative/noninteger latency')
    if not values:return dict(count=0,min=None,p50=None,p95=None,p99=None,max=None)
    values=sorted(values);n=len(values)
    return dict(count=n,min=values[0],p50=values[(n*50+99)//100-1],p95=values[(n*95+99)//100-1],
                p99=values[(n*99+99)//100-1],max=values[-1])


def validate(offered,history,mode,leader,read_target,initial_read,repetition):
    need(mode in model.MODES and type(repetition) is int and 1<=repetition<=3,'measurement window mode/repetition')
    nodes={'node-1','node-2','node-3'};need(leader in nodes,'measurement initial leader')
    expected=leader if mode.endswith('strong') else sorted(nodes-{leader})[-1]
    need(read_target==expected,'measurement changed frozen read target')
    calls={c['opId']:c for c in history};need(len(calls)==len(history),'measurement window duplicate operation')
    initial=calls.get(initial_read)
    need(initial is not None and initial['kind']=='read' and initial.get('setupToken') is True and
         initial['node']==leader and initial['outcome']=='SUCCESS' and initial['query']==model.query(0) and
         initial['endNanos']<=offered['startNanos'],'measurement window initial strong read')
    program=model.program();result=load.validate(offered,program,DURATION,history)
    identities={r['opId'] for r in offered['offers']}
    business={c['opId'] for c in history if c['kind'] in ('read','update')}
    need(business==identities|{initial_read} and initial_read not in identities,'measurement undeclared/missing offered business call')
    for offer,planned in zip(offered['offers'],program):
        call=calls[offer['opId']]
        need(call['node']==(leader if planned['kind']=='update' else read_target) and not call.get('setupToken'),
             'measurement offered target/setup substitution')
        if planned['kind']=='read':
            if mode=='candidate-minimum':need(call.get('minimum')==initial['response'].get('token') and call.get('minimum'),
                                             'measurement changed carried initial token')
            else:need('minimum' not in call,'measurement minimum on non-minimum mode')
        response=call['response']
        need(all(type(response[k]) is int for k in ('receivedNanos','apiStartNanos','apiEndNanos')) and
             response['receivedNanos']<=response['apiStartNanos']<=response['apiEndNanos'],'measurement window API timing')
    windows={}
    for name,offset,duration,read_count,write_count in WINDOWS:
        rows=[r for r in result['latencies'] if r['window']==name]
        need(Counter(r['kind'] for r in rows)=={'read':read_count,'update':write_count},'measurement frozen window counts')
        groups={}
        for kind in ('read','update'):
            selected=[r for r in rows if r['kind']==kind];completed=[calls[r['opId']] for r in selected]
            outcomes=Counter(c['outcome'] for c in completed);reasons=Counter(c['response']['reasonCode'] for c in completed if 'reasonCode' in c['response'])
            metrics={field:distribution([r[field] for r in selected]) for field in
                     ('offerDelayNanos','submitNanos','dueToResponseNanos','offerToResponseNanos')}
            metrics['apiNanos']=distribution([c['response']['apiEndNanos']-c['response']['apiStartNanos'] for c in completed])
            metrics['clientQueueNanos']=distribution([c['response']['apiStartNanos']-c['response']['receivedNanos'] for c in completed])
            # Coverage, not an availability/latency SLA. Never accept a vacuous
            # all-rejected history as a query/replication measurement.
            if kind=='read':
                successful=Counter(c['query']['kind'] for c in completed if c['outcome']=='SUCCESS')
                need(all(successful[k]>0 for k in model.KINDS),'measurement window lacks successful query coverage')
            else:need(outcomes['SUCCESS']>0,'measurement window lacks successful mutation')
            groups[kind]=dict(offered=len(selected),completed=len(selected),outcomes=dict(sorted(outcomes.items())),
                reasons=dict(sorted(reasons.items())),completedAfterWindow=sum(c['endNanos']>offered['startNanos']+offset+duration for c in completed),
                latencyNanos=metrics)
        windows[name]=dict(offsetNanos=offset,durationNanos=duration,operations=groups)
    return dict(status='PASS',execution='m01-window-ledger-only',qualifiedMeasurement=False,mode=mode,repetition=repetition,
                offered=result['offered'],completed=result['completed'],windows=windows,latencies=result['latencies'],
                latencySemantics='all outcomes; grouped by original offered window; late responses retained')
