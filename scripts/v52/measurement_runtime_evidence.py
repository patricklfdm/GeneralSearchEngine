"""Independent untimed consumer smoke checks; full M01–M04 admission is separate."""
import copy
import json
import os
from dataclasses import replace
from pathlib import Path
from scripts.v51 import runtime_evidence as physical, recovery_inspector as recovery
from scripts.v51 import performance_bundle as bundle,performance_artifacts
from scripts.v51 import public_qualification_harness as q
from . import measurement_model as model,measurement_trace as trace,measurement_oracle as oracle,token
from . import public_reads_evidence as reads
from . import measurement_load as load,measurement_samples as samples,measurement_bundle
from . import measurement_projection,measurement_stream,measurement_history,measurement_publication,measurement_reads
from .measurement_reads import publication_generation
from .evidence import need,digest,encoded

DRIVER_MARKERS=(dict(name='warmup-start',offsetNanos=0),dict(name='measured-start',offsetNanos=500_000_000),
                dict(name='measured-end',offsetNanos=3_000_000_000))



def stream(root,node):
    # This short smoke matrix must never materialize a full M01-sized trace during
    # its post-decode negative mutations. Measured replay has a separate admission.
    return trace.Trace(Path(root)/(node+'-trace.jsonl'),node=node,limits=replace(trace.Limits(),decoded_bytes=64<<20,rows=65536))


def validate(root,expected,answers=None,*,traces=None,history=None,package=bundle):
    root=Path(root).resolve();binding=reads.read(root/'binding.json');need(binding==expected,'measurement source/build/attempt binding')
    need(package in (bundle,measurement_bundle),'measurement package profile')
    if package is measurement_bundle:package.inventory(root)
    else:need(reads.read(root/'bundle-members.json')==package.members(root),'measurement smoke inventory')
    need(all(digest((root/'artifacts'/name).read_bytes())==sha for name,sha in binding['artifacts'].items()),'measurement artifact hashes')
    need(all(digest((root/name).read_bytes())==sha for name,sha in binding['classes'].items()),'measurement consumer hashes')
    history=reads.read(root/'history.json') if history is None else history;processes=reads.read(root/'processes.json');scenario=reads.read(root/'scenario.json')
    need(len(processes)==3 and len({v['pid'] for v in processes})==3 and {v['node'] for v in processes}=={'node-1','node-2','node-3'} and
         all(v['generation']==1 and v['exitCode']==0 for v in processes),'measurement three stopped public JVMs')
    need(binding['mode'] in model.MODES and scenario['mode']==binding['mode'] and binding['programSha256']==model.PLAN_SHA,'measurement smoke mode/program')
    traces=traces if traces is not None else {p['node']:stream(root,p['node']) for p in processes}
    for reader in traces.values():
        if isinstance(reader,trace.Trace):reader.verify()
    cores=[name for name in binding['artifacts'] if name.startswith('general-search-engine-') and not name.startswith('general-search-engine-replication-') and name!='general-search-engine-4.4.0.jar']
    need(len(cores)==1,'measurement runtime core identity');version=cores[0][len('general-search-engine-'):-4]
    need(version=='5.1.0' if binding['mode'].startswith('published') else version in ('5.2.0-SNAPSHOT','5.2.0'),'measurement mode artifact version')
    for process in processes:
        identity=process['identity'];need(all(identity[k]==process[k] for k in ('node','pid')) and identity['mode']==binding['mode'],'measurement startup identity')
        for component,name in (('core',cores[0]),('replication','general-search-engine-replication-'+version+'.jar')):
            need(name in binding['artifacts'] and identity[component+'Source']==str(Path(binding['origin'])/'artifacts'/name),'measurement loaded artifact source')
    location=(performance_artifacts if package is bundle else package).EvidenceLocation(root,binding['origin'])
    base=physical.validate(root,traces,evidence_location=location,require_restart=False)
    manifest,genesis,entries=reads.context(root,traces)
    calls={r['opId']:r for r in history if r['kind'] in ('read','update')}
    need(len(calls)==14 and len([r for r in calls.values() if r['kind']=='read'])==11 and
         all(r['outcome']=='SUCCESS' and r['startNanos']<r['endNanos'] for r in calls.values()),'measurement smoke complete public ledger')
    updates=[r for r in calls.values() if r['kind']=='update'];program=[r['document'] for r in model.program() if r['kind']=='update'][:3]
    need([r['document'] for r in updates]==program==scenario['updates'] and all(r['node']==scenario['leader'] for r in updates),'measurement smoke update program')
    requested=[r for r in calls.values() if r['kind']=='read' and not r.get('setupToken')]
    need(len(requested)==10 and [r['query'] for r in requested]==[model.query(i) for i in range(10)] and
         all(r['node']==scenario['readTarget'] for r in requested),'measurement smoke read program/target')
    need(scenario['readTarget']==(scenario['leader'] if binding['mode'].endswith('strong') else sorted({'node-1','node-2','node-3'}-{scenario['leader']})[-1]),'measurement frozen targeting')
    if 'smokeInitialization' in binding:
        need(binding['smokeInitialization']=='read-write-targets-confirmed-updates-v1','measurement unknown smoke initialization')
        baseline=scenario['baseline'];write_indices=[v['index'] for v in entries.values() if v['operation']==2]
        need(set(baseline)=={scenario['leader'],scenario['readTarget']} and len(write_indices)==3 and max(write_indices)<=scenario['baselineIndex']<=base['chosen'],'measurement prepared cut')
        for node,status in baseline.items():
            need(status['state'] in ('FOLLOWER','LEADER_READY') and status['publishedIndex']>=scenario['baselineIndex'] and status['sequence']==4,'measurement prepared publication')
            call=next((c for c in history if c['opId']==status['opId']),None)
            observed=next((r for r in traces[node] if r['event']=='CLIENT_SUCCESS' and r.get('opId')==status['opId']),None)
            need(call is not None and observed is not None and call['node']==node and call['kind']=='status' and
                 call['response']==status=={k:v for k,v in observed.items() if k not in trace.META} and
                 updates[-1]['endNanos']<call['startNanos']<call['endNanos']<requested[0]['startNanos'],'measurement prepared observation binding')
    initial=[r for r in calls.values() if r.get('setupToken')]
    need(len(initial)==1 and initial[0]['opId']==scenario['initialRead'] and initial[0]['node']==scenario['leader'] and
         initial[0]['endNanos']<updates[0]['startNanos'],'measurement initial read ordering')
    if binding['mode']=='candidate-minimum':need(all(r['minimum']==initial[0]['response']['token'] for r in requested),'measurement initial minimum changed')
    projection=measurement_projection.Projection(manifest,genesis,entries,updates)
    authority=None
    if 'publicationAuthority' in binding:
        need(binding['publicationAuthority']=='forced-generation-v1','measurement unknown publication authority profile')
        authority=measurement_publication.validate(traces,manifest,projection,binding['mode'])
    observed=measurement_reads.validate(traces,processes,calls,manifest,entries,projection,binding['mode'],answers)
    cuts=observed['cuts'];timings=observed['timings']
    ledger=measurement_history.validate(traces,processes,history,binding['mode'])
    driver=None
    if binding.get('driverExercise',False):
        offered=reads.read(root/'offered.json')
        requests=[dict(kind='read',ordinal=i,offsetNanos=i*100_000_000,window='driver-smoke',query=model.query(i)) for i in range(10)]
        dispatched=load.validate(offered,requests,3_000_000_000,history)
        need(dispatched['outcomes']=={'SUCCESS':10} and {v['opId'] for v in offered['offers']}=={v['opId'] for v in requested},'measurement driver smoke operation set')
        resources={};resource_windows={};markers=None
        if 'driverMarkerSchedule' in binding:
            need(binding['driverMarkerSchedule']==list(DRIVER_MARKERS),'measurement driver phase schedule changed')
            markers=load.validate_markers(offered,DRIVER_MARKERS,history,traces)
        for node,reader in traces.items():
            observed=[r for r in reader if r['event']=='CLIENT_SAMPLE'];resources[node]=samples.validate(observed,binding['mode'])
            need(resources[node]['periodicSamples']>=2,'measurement driver smoke missing periodic samples')
            controls=[c for c in history if c['node']==node and c['kind'].startswith('sample-')]
            if markers is not None:resource_windows[node]=samples.windows(observed,binding['mode'],controls,offered,markers,node)
            else:
                need([c['kind'] for c in controls]==['sample-start','sample-stop'] and all(c['outcome']=='SUCCESS' for c in controls),'measurement sampler control ledger')
                need(controls[0]['endNanos']<=offered['startNanos'] and controls[-1]['startNanos']>=offered['drainEndNanos'],'measurement sampler does not cover dispatch')
                for call,sample in zip(controls,(observed[0],observed[-1])):
                    need(call['response']['sample']=={k:v for k,v in sample.items() if k not in trace.META},'measurement sampler response differs from observation')
        driver=dict(load=dispatched,resources=resources)
        if markers is not None:driver.update(phaseMarkers=markers,resourceWindows=resource_windows)
    result=dict(status='PASS',execution='untimed-measurement-consumer-physical-smoke',qualifiedMeasurement=False,base=base,reads=11,updates=3,
                oracleInput=oracle.prepare(cuts,program),timings=timings,driver=driver,ledger=ledger)
    if authority is not None:result['publicationAuthority']=authority
    return result


def negatives(root,expected,answers,*,package=bundle):
    validate(root,expected,answers,package=package)
    root=Path(root);original={f'node-{i}':stream(root,f'node-{i}') for i in (1,2,3)}
    history=reads.read(root/'history.json');mode=expected['mode']
    def find(event,extra=lambda row:True):return lambda row:row['event']==event and extra(row)
    def edit(**values):
        def apply(row):row.update(values);return row
        return apply
    def field(key,value):
        def apply(row):row[key]=value(row) if callable(value) else value;return row
        return apply
    def nested(field,key,value):
        def apply(row):row[field][key]=value;return row
        return apply
    def remove(field,key):
        def apply(row):row[field].pop(key);return row
        return apply
    initial=next(c for c in history if c['kind']=='read');mode=expected['mode']
    capture='READ_CAPTURE_VALIDATED' if mode.endswith('legacy-strong') else 'REPLICA_READ_CAPTURE_VALIDATED'
    entered='READ_CAPTURED' if mode.endswith('legacy-strong') else 'REPLICA_READ_CAPTURED'
    invocation='PUBLIC_READ_INVOKE' if mode.endswith('legacy-strong') else 'REPLICA_READ_INVOKED'
    other='REPLICA_READ_INVOKED' if invocation=='PUBLIC_READ_INVOKE' else 'PUBLIC_READ_INVOKE'
    def response(calls):next(c for c in calls if c['opId']==initial['opId'])['response']['answer']={'forged':True}
    cases=[('changed-controller-answer',None,None,response,'measurement controller/worker response differs'),
           ('forged-core-answer',find('CLIENT_SUCCESS',lambda row:row.get('opId')==initial['opId']),edit(answer={'forged':True}),response,'measurement query differs from actual published core'),
           ('wrong-captured-sequence',find(capture),edit(sequence=999),None,'measurement capture differs from local publication'),
           ('leaked-permit',find('CLIENT_IDLE'),nested('queues','admissionAvailable',63),None,'measurement final ownership leak'),
           ('wrong-public-capability',find(invocation),edit(event=other),None,'measurement wrong public read capability'),
           ('missing-entered-view',find(entered),edit(event='REMOVED_CAPTURE'),None,'measurement view release identity')]
    cases.extend([
        ('missing-received-command',find('CLIENT_RECEIVED',lambda row:row.get('opId')==initial['opId']),edit(event='REMOVED_RECEIVED'),None,
         'measurement duplicate/unreceived invocation'),
        ('duplicate-controller-operation',None,None,lambda calls:calls.append(copy.deepcopy(next(c for c in calls if c['opId']==initial['opId']))),
         'measurement duplicate/invalid operation identity')])
    if not mode.endswith('legacy-strong'):
        strong=find(capture,lambda row:row['policy']=='LEADER_STRONG')
        cases.extend([
            ('wrong-policy',strong,edit(policy='STALE_ALLOWED'),None,'measurement silent read policy fallback'),
            ('wrong-strong-epoch',strong,edit(barrierEpoch=999),None,'measurement strong barrier not fresh'),
            ('expired-capture',find(capture),field('captureNanos',lambda row:row['deadlineNanos']),None,'measurement capture deadline/generation'),
            ('wrong-release-cut',find('REPLICA_READ_RELEASED'),edit(sequence=999),None,'measurement changed released cut')])
        cases.extend([
            ('missing-read-admission',find('REPLICA_READ_ADMITTED'),edit(event='REMOVED_ADMISSION'),None,'measurement capture without queued ownership'),
            ('wrong-settling-count',find('REPLICA_READ_SETTLING'),field('settling',lambda row:row['settling']+1),None,'measurement ownership accounting differs from transitions'),
            ('release-before-completion-return',find('REPLICA_READ_OWNERSHIP_RELEASED'),edit(completionReturned=False),None,'measurement premature ownership release')])
    if mode!='published-v51-legacy-strong':
        cases.append(('missing-final-read-counter',find('CLIENT_IDLE'),remove('queues','readsOwned'),None,'measurement idle read counters missing'))
    if mode=='candidate-minimum':
        def minimum(calls):next(c for c in calls if c['kind']=='read' and not c.get('setupToken'))['minimum']='AA=='
        cases.append(('different-minimum',None,None,minimum,'measurement initial minimum changed'))
    if 'smokeInitialization' in expected:
        baseline=reads.read(root/'scenario.json')['baseline'];baseline_node=next(iter(baseline));identity=baseline[baseline_node]['opId']
        cases.append(('missing-prepared-publication',find('CLIENT_SUCCESS',lambda row:row['node']==baseline_node and row.get('opId')==identity),
                      edit(event='REMOVED_PREPARED_STATUS'),None,'measurement prepared observation binding'))
    if expected.get('driverExercise',False):
        cases.extend([
            ('missing-resource-sample',find('CLIENT_SAMPLE'),edit(sampleOrdinal=99),None,'sample missing/duplicate ordinal'),
            ('fabricated-unsupported-allocation',find('CLIENT_SAMPLE'),edit(allocatedBytes=dict(status='UNSUPPORTED',value=0)),None,
             'sample fabricated unavailable metric: allocatedBytes')])
        if mode!='published-v51-legacy-strong':
            cases.append(('missing-read-resource-counter',find('CLIENT_SAMPLE'),remove('queues','readsOwned'),None,'sample missing candidate read counters'))
    if 'publicationAuthority' in expected:
        selector=find('STORAGE_CUT',lambda row:row['cut']=='SELECTOR_BEFORE_ACK')
        cases.append(('missing-generation-packet',selector,lambda row:{k:v for k,v in row.items() if k!='readGeneration'},None,
                      'measurement selector lacks generation bytes'))
        installs=[(node,r) for node,rows in original.items() for r in rows if r['event']=='REJOIN_INSTALLED']
        if installs:
            installed_node,installed_row=installs[0]
            nonempty=find('STORAGE_CUT',lambda row:row['node']==installed_node and row['cut']=='SELECTOR_BEFORE_ACK' and
                          any(v['name']=='snapshot.gsr' and v['bytes']==installed_row['snapshot'] for v in row['readGeneration']))
            cases.append(('missing-forced-rejoin-generation',nonempty,edit(event='REMOVED_SELECTOR'),None,'measurement rejoin lacks forced generation'))
    if 'driverMarkerSchedule' in expected:
        cases.append(('changed-phase-marker',find('CLIENT_SAMPLE',lambda row:row.get('marker')=='measured-start'),
                      edit(marker='warmup-start'),None,'sample incomplete/out-of-order window markers'))
    result=[]
    for name,predicate,change,mutate_history,reason in cases:
        rows=measurement_stream.changed(original,predicate,change) if predicate else original;calls=copy.deepcopy(history)
        if mutate_history:mutate_history(calls)
        try:validate(root,expected,answers,traces=rows,history=calls,package=package)
        except ValueError as error:need(str(error)==reason,'measurement unrelated negative rejection: '+name+': '+str(error));result.append(dict(case=name,status='REJECTED',reason=reason))
        else:raise ValueError('measurement negative accepted: '+name)
    return result


def replay(root,expected,output,*,package=bundle):
    root=Path(root).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    preliminary=validate(root,expected,package=package);value=preliminary['oracleInput'];(output/'input.json').write_bytes(encoded(value)+b'\n')
    jar=root/'artifacts/general-search-engine-4.4.0.jar';cp=os.pathsep.join(map(str,(jar,root/'control-classes')))
    result=q.command(['java','-cp',cp,q.PACKAGE+'admission.V52MeasurementOracle',output/'oracle',output/'input.json'],output,'oracle')
    need(result.stderr.strip()=='coreSource='+str(jar),'measurement replay loaded wrong query control')
    need(json.loads(result.stdout)==dict(status='PASS',measured=False,requests=len(value['requests']),updatesApplied=3,finalSequence=4),'measurement query replay incomplete')
    answers=oracle.validate_output(value,output/'oracle/answers.jsonl');checked=validate(root,expected,answers,package=package)
    checked['negatives']=negatives(root,expected,answers,package=package)
    (output/'validation.json').write_bytes(encoded(checked)+b'\n');return checked
