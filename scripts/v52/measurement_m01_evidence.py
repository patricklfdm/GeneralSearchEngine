"""Independent full M01 member replay; whole-set/machine admission is separate.

No short-history substitution, inferred success, business retry or hidden outcome
filter is accepted. A member PASS is not a complete Phase 6 measurement result.
"""
import copy
import json
import os
from pathlib import Path
from scripts.v51 import runtime_evidence as physical,public_qualification_harness as q
from scripts.v51.performance_model import strict_json
from . import measurement_model as model,measurement_m01 as m01,measurement_bundle as bundle
from . import measurement_trace as trace,measurement_window as window,measurement_load as load
from . import measurement_history as lifecycle,measurement_projection as projection,measurement_publication as publication
from . import measurement_reads as cuts,measurement_samples as samples,measurement_oracle as oracle
from . import measurement_authority_budget as budget,public_reads_evidence as reads
from . import measurement_stream
from . import measurement_options as options,measurement_identity as identities
from . import measurement_verified
from .evidence import need,digest,encoded


def metadata(root,name,maximum):
    return identities.metadata(root,name,maximum)


def identity(root,expected):
    def check_profile(binding,inventory):
        mode=binding['mode'];profile=binding.get('measurementProfile',{})
        need(binding.get('readParameters')==options.parameters() and options.FILE not in inventory and
             'faultParameters' not in binding and 'measurement-fault.json' not in inventory,'measurement M01 read parameters changed')
        need(profile==m01.profile(mode,profile.get('repetition')) and binding['programSha256']==model.PLAN_SHA and
             binding.get('publicationAuthority')=='forced-generation-v1' and 'smokeInitialization' not in binding and
             'driverExercise' not in binding,'measurement M01 full preparation profile')
    return identities.identity(root,expected,check_profile,label='measurement M01')


def initial_publication(history,scenario,offered,traces,mode):
    leader=scenario['leader'];initial=scenario['initialRead'];by_id={c['opId']:c for c in history}
    read_id=index=None
    for row in traces[leader]:
        if row['event'] in ('PUBLIC_READ_INVOKE','REPLICA_READ_INVOKED') and row.get('opId')==initial:read_id=row['readId']
        elif row['event'] in ('READ_CAPTURE_VALIDATED','REPLICA_READ_CAPTURE_VALIDATED') and row['readId']==read_id:
            need(index is None and row['sequence']==1,'measurement M01 changed initial cut');index=row['index']
    need(index is not None and type(scenario['baselineIndex']) is int and scenario['baselineIndex']>=index,
         'measurement M01 preparation below initial cut')
    baseline=scenario['baseline'];need(set(baseline)=={leader,scenario['readTarget']},'measurement M01 preparation target set')
    for node,status in baseline.items():
        call=by_id.get(status['opId'])
        need(status['state'] in ('FOLLOWER','LEADER_READY') and status['sequence']==1 and
             status['publishedIndex']>=scenario['baselineIndex'],'measurement M01 initial target publication')
        need(call is not None and call['node']==node and call['kind']=='status' and call['response']==status and
             by_id[initial]['endNanos']<call['startNanos']<call['endNanos']<=offered['startNanos'],
             'measurement M01 preparation ledger binding')
    return dict(index=index,preparedThrough=scenario['baselineIndex'],sequence=1)


def validate(root,expected,answers=None,*,traces=None,history=None,offered=None,scenario=None):
    root=Path(root).resolve();binding,processes=identity(root,expected);mode=binding['mode'];p=binding['measurementProfile']
    history=metadata(root,'history.json',32<<20) if history is None else history
    offered=metadata(root,'offered.json',32<<20) if offered is None else offered
    scenario=metadata(root,'scenario.json',1<<20) if scenario is None else scenario
    need(scenario['family']=='M01' and scenario['stage']=='observed' and scenario['mode']==mode and scenario['repetition']==p['repetition'],
         'measurement M01 scenario identity/completion')
    execution=metadata(root,'execution.json',1<<20)
    need(execution==dict(status='STOPPED',qualifiedMeasurement=False,paidCloud=False,failure=None,closeErrors=[]),
         'measurement M01 incomplete process execution')
    windows=window.validate(offered,history,mode,scenario['leader'],scenario['readTarget'],scenario['initialRead'],p['repetition'])
    traces=traces if traces is not None else {process['node']:trace.Trace(root/(process['node']+'-trace.jsonl'),node=process['node']) for process in processes}
    raw=(root/'node-1/manifest.gsr').read_bytes();manifest=dict(physical.f.inspect(raw,'MANIFEST'),digest=raw[16:48].hex())
    # Aggregate limits precede every general authority collector/reconstructor.
    authority_budget=budget.validate(traces,manifest)
    base=physical.validate(root,traces,evidence_location=bundle.EvidenceLocation(root,binding['origin']),require_restart=False)
    manifest,genesis,entries=reads.context(root,traces)
    calls={c['opId']:c for c in history if c['kind'] in ('read','update')}
    updates=[c for c in calls.values() if c['kind']=='update'];state=projection.Projection(manifest,genesis,entries,updates)
    authority=publication.validate(traces,manifest,state,mode,selector_limit=budget.MAX_SELECTORS,
                                   transfer_limit=publication.MAX_MEASURED_TRANSFERS)
    ledger=lifecycle.validate(traces,processes,history,mode)
    observed=cuts.validate(traces,processes,calls,manifest,entries,state,mode,answers)
    initial=initial_publication(history,scenario,offered,traces,mode)
    markers=load.validate_markers(offered,m01.MARKERS,history,traces);resources={}
    for node,rows in traces.items():
        observations=[]
        for row in rows:
            if row['event']=='CLIENT_SAMPLE':
                need(len(observations)<1024,'measurement M01 resource observation count');observations.append(row)
        controls=[c for c in history if c['node']==node and c['kind'].startswith('sample-')]
        resources[node]=samples.windows(observations,mode,controls,offered,markers,node)
    need(windows['completed']==1980 and ledger['outcomes']['read'].get('SUCCESS',0)==observed['successfulReads'] and
         ledger['outcomes']['update'].get('SUCCESS',0)==observed['successfulUpdates'],'measurement M01 outcome reconciliation')
    return dict(status='PASS',execution='m01-member-physical-replay',qualifiedMeasurement=False,paidCloud=False,
                mode=mode,repetition=p['repetition'],base=base,authorityBudget=authority_budget,publicationAuthority=authority,
                initial=initial,windows=windows,ledger=ledger,phaseMarkers=markers,resources=resources,
                oracleInput=state.query_input(observed['cuts']),readTimings=observed['timings'],
                successfulReads=observed['successfulReads'],successfulUpdates=observed['successfulUpdates'],
                chosenUpdateOrdinals=state.ordinals)


def negative_cases(mode,initial,leader):
    """Closed post-decode mutations; none can qualify an invalid original."""
    def event(name,extra=lambda row:True):return lambda row:row['event']==name and extra(row)
    def replace(**values):return lambda row:dict(row,**values)
    def controls(change):return lambda history,offered,scenario:change(history,offered,scenario)
    def initial_answer(history,offered,scenario):
        next(c for c in history if c['opId']==initial)['response']['answer']={'forged':True}
    def hidden(history,offered,scenario):
        extra=copy.deepcopy(next(c for c in history if c['kind']=='update'));extra['opId']='undeclared-retry';history.append(extra)
    def target(history,offered,scenario):
        call=next(c for c in history if c['kind']=='read' and not c.get('setupToken'));call['node']=next(n for n in ('node-1','node-2','node-3') if n!=call['node'])
    def leak(row):row['queues']['admissionAvailable']=63;return row
    cases=[
        ('missing-offer',None,None,controls(lambda h,o,s:o['offers'].pop()),'load offered count'),
        ('shortened-window',None,None,controls(lambda h,o,s:o.__setitem__('durationNanos',120_000_000_000)),'load incomplete dispatch'),
        ('shifted-due-time',None,None,controls(lambda h,o,s:o['offers'][0].__setitem__('dueNanos',o['offers'][0]['dueNanos']+1)),'load changed offered request'),
        ('hidden-business-retry',None,None,hidden,'measurement undeclared/missing offered business call'),
        ('changed-read-target',None,None,target,'measurement offered target/setup substitution'),
        ('changed-controller-answer',None,None,initial_answer,'measurement ledger response binding'),
        ('forged-query-answer',event('CLIENT_SUCCESS',lambda r:r.get('opId')==initial),replace(answer={'forged':True}),initial_answer,
         'measurement query differs from actual published core'),
        ('missing-command-receipt',event('CLIENT_RECEIVED',lambda r:r.get('opId')==initial),replace(event='REMOVED_RECEIPT'),None,
         'measurement duplicate/unreceived invocation'),
        ('leaked-admission-permit',event('CLIENT_IDLE'),leak,None,'measurement idle admission leak'),
        ('missing-leader-proof-force',event('FORCE',lambda r:r['node']==leader and r['kind']=='PROOF'),replace(event='REMOVED_FORCE'),None,
         'publication before local proof/remote ACK'),
        ('missing-resource-sample',event('CLIENT_SAMPLE'),replace(sampleOrdinal=99),None,'sample missing/duplicate ordinal'),
        ('fabricated-allocation',event('CLIENT_SAMPLE'),replace(allocatedBytes=dict(status='UNSUPPORTED',value=0)),None,
         'sample fabricated unavailable metric: allocatedBytes'),
        ('changed-resource-boundary',event('CLIENT_SAMPLE',lambda r:r.get('marker')=='measured-start'),replace(marker='warmup-start'),None,
         'sample incomplete/out-of-order window markers'),
        # A healthy run need not install a snapshot. Every successful setup read
        # does require a captured view; mutate that mandatory authority instead.
        ('missing-read-capture',event('READ_CAPTURE_VALIDATED' if mode.endswith('legacy-strong') else 'REPLICA_READ_CAPTURE_VALIDATED'),
         replace(event='REMOVED_CAPTURE'),None,'measurement missing/duplicate entered view')]
    if not mode.endswith('legacy-strong'):
        def settling(row):row['settling']+=1;return row
        cases.extend([
            ('changed-capture-sequence',event('REPLICA_READ_CAPTURE_VALIDATED'),replace(sequence=999),None,
             'measurement capture differs from local publication'),
            ('changed-strong-epoch',event('REPLICA_READ_CAPTURE_VALIDATED',lambda r:r['policy']=='LEADER_STRONG'),replace(barrierEpoch=999),None,
             'measurement strong barrier not fresh'),
            ('changed-settling-count',event('REPLICA_READ_SETTLING'),settling,None,'measurement ownership accounting differs from transitions'),
            ('premature-permit-release',event('REPLICA_READ_OWNERSHIP_RELEASED'),replace(completionReturned=False),None,'measurement premature ownership release')])
    if mode=='candidate-minimum':
        def minimum(history,offered,scenario):next(c for c in history if c['kind']=='read' and not c.get('setupToken'))['minimum']='AA=='
        cases.append(('changed-carried-token',None,None,minimum,'measurement changed carried initial token'))
    return cases


def negatives(root,expected,answers,*,traces=None):
    validate(root,expected,answers,traces=traces)
    root=Path(root);history=metadata(root,'history.json',32<<20);offered=metadata(root,'offered.json',32<<20);scenario=metadata(root,'scenario.json',1<<20)
    original=traces if traces is not None else {f'node-{i}':trace.Trace(root/f'node-{i}-trace.jsonl',node=f'node-{i}') for i in (1,2,3)};result=[]
    for name,predicate,change,mutate,reason in negative_cases(expected['mode'],scenario['initialRead'],scenario['leader']):
        traces=measurement_stream.changed(original,predicate,change) if predicate else original
        calls=copy.deepcopy(history);dispatch=copy.deepcopy(offered);case=copy.deepcopy(scenario)
        if mutate:mutate(calls,dispatch,case)
        try:validate(root,expected,answers,traces=traces,history=calls,offered=dispatch,scenario=case)
        except ValueError as error:
            need(str(error)==reason,'measurement M01 unrelated negative rejection: '+name+': '+str(error))
            result.append(dict(case=name,status='REJECTED',reason=reason))
        else:raise ValueError('measurement M01 negative accepted: '+name)
    return result


def replay(root,expected,output):
    """Replay one full member and its negatives; whole-set admission is separate."""
    root=Path(root).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    with measurement_verified.traces(root,output) as traces:
        preliminary=validate(root,expected,traces=traces);value=preliminary['oracleInput'];(output/'input.json').write_bytes(encoded(value)+b'\n')
        jar=root/'artifacts/general-search-engine-4.4.0.jar';cp=os.pathsep.join(map(str,(jar,root/'control-classes')))
        run=q.command(['java','-cp',cp,q.PACKAGE+'admission.V52MeasurementOracle',output/'oracle',output/'input.json'],output,'oracle')
        need(run.stderr.strip()=='coreSource='+str(jar),'measurement M01 loaded wrong query control')
        need(json.loads(run.stdout)==dict(status='PASS',measured=False,requests=len(value['requests']),updatesApplied=len(value['updates']),
                                         finalSequence=1+len(value['updates'])),'measurement M01 query replay incomplete')
        answers=oracle.validate_output(value,output/'oracle/answers.jsonl');checked=validate(root,expected,answers,traces=traces)
        checked['negatives']=negatives(root,expected,answers,traces=traces)
    (output/'validation.json').write_bytes(encoded(checked)+b'\n');return checked
