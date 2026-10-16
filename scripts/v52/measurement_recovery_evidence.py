"""Complete, portable M04 member replay; formal cohort admission remains separate."""
import copy
import json
import os
from pathlib import Path
from scripts.v51 import runtime_evidence as physical,public_qualification_harness as q
from . import measurement_recovery as controller,measurement_recovery_ledger as ledger,measurement_recovery_retained as retained
from . import measurement_identity as identities,measurement_generations as generations,measurement_bundle as bundle
from . import measurement_trace as trace,measurement_model as model,measurement_options as options,measurement_stream
from . import measurement_authority_budget as budget,measurement_history as lifecycle,measurement_projection as projection
from . import measurement_publication as publication,measurement_reads as cuts,measurement_samples as samples
from . import measurement_oracle as oracle,public_reads_evidence as reads
from . import measurement_verified
from .evidence import need,digest,encoded


def metadata(root,name,maximum):return identities.metadata(root,name,maximum,label='measurement recovery')


def identity(root,expected,scenario):
    plan=controller.profile(expected.get('measurementProfile',{}).get('case'))
    restarted=scenario['leader'] if plan['case']==controller.CASES[0] else None
    def check(binding,inventory):
        need(binding['mode']=='candidate-minimum' and binding['measurementProfile']==plan and binding['programSha256']==model.PLAN_SHA and
             binding.get('publicationAuthority')=='forced-generation-v1' and binding['readParameters']==options.parameters() and
             not {'driverExercise','smokeInitialization','readConfigurationOnly'}&set(binding) and options.FILE not in inventory,
             'recovery preparation profile')
        need(binding['faultParameters']==plan['faultParameters']==metadata(root,controller.FILE,1024),'recovery fault parameter binding')
        if restarted is None:
            need(not (root/'pre-reopen').exists() and (root/'network-blocks.txt').read_bytes()==b'', 'recovery undeclared crash or unhealed partition')
        else:need(not (root/'network-blocks.txt').exists() and {p.name for p in (root/'pre-reopen').iterdir()}=={restarted},'recovery retained directory set')
    binding,processes=identities.identity(root,expected,check,label='measurement recovery',restarted=restarted)
    if restarted is not None:
        dead=next(p for p in processes if p['exitCode']==-9)
        need(all(dead[k]==scenario['crash'][k] for k in ('node','pid','generation','exitCode')),'recovery crash process binding')
    return binding,processes,restarted


def resources(traces,processes,history,scenario):
    result={};fault=scenario.get('killIssuedNanos',scenario.get('partitionNanos'));last=scenario.get('restartedReadObservedNanos',scenario.get('minimumObservedNanos'))
    for process in processes:
        node=process['node'];gen=process['generation'];key=node+'-g'+str(gen);abrupt=process['exitCode']==-9
        values=[]
        for row in generations.rows(traces,process,processes):
            if row['event']=='CLIENT_SAMPLE':
                need(len(values)<1024,'recovery sample count bound');values.append(row)
        result[key]=samples.validate(values,'candidate-minimum',abrupt=abrupt)
        controls=[c for c in history if c['node']==node and c['generation']==gen and c['kind'].startswith('sample-')]
        need([c['kind'] for c in controls]==(['sample-start'] if abrupt else ['sample-start','sample-stop']) and
             all(c['outcome']=='SUCCESS' for c in controls),'recovery sampled process coverage')
        expected=values[:1] if abrupt else (values[0],values[-1])
        need([c['response']['sample'] for c in controls]==[{k:v for k,v in row.items() if k not in trace.META} for row in expected],
             'recovery sample response binding')
        need(controls[0]['endNanos']<fault if gen==1 else controls[0]['startNanos']>scenario['restartStartedNanos'],
             'recovery sampling missed fault/reopen')
        if gen==2:
            first=next(c for c in history if c['opId']==scenario['recovered']['status']['opId'])
            need(controls[0]['endNanos']<first['startNanos'],'recovery restart sample began after recovery')
        if not abrupt:need(controls[-1]['startNanos']>last,'recovery sample stopped before final read')
    return result


def validate(root,expected,answers=None,*,traces=None,history=None,scenario=None):
    root=Path(root).resolve();scenario=metadata(root,'scenario.json',1<<20) if scenario is None else scenario
    binding,processes,restarted=identity(root,expected,scenario);plan=binding['measurementProfile']
    history=metadata(root,'history.json',32<<20) if history is None else history
    need(metadata(root,'execution.json',1<<20)==dict(status='STOPPED',qualifiedMeasurement=False,paidCloud=False,failure=None,closeErrors=[]),
         'recovery incomplete process execution')
    schedule=ledger.schedule(history,scenario,plan)
    traces=traces if traces is not None else {f'node-{i}':trace.Trace(root/f'node-{i}-trace.jsonl',node=f'node-{i}') for i in (1,2,3)}
    raw=(root/'node-1/manifest.gsr').read_bytes();manifest=dict(physical.f.inspect(raw,'MANIFEST'),digest=raw[16:48].hex())
    bounds=budget.validate(traces,manifest)
    base=physical.validate(root,traces,evidence_location=identities.evidence_location(root,binding),require_restart=restarted is not None)
    manifest,genesis,entries=reads.context(root,traces);calls={c['opId']:c for c in history if c['kind'] in ('read','update')}
    state=projection.Projection(manifest,genesis,entries,[c for c in calls.values() if c['kind']=='update'])
    restorations={};retained_report=None
    if restarted is not None:restorations,retained_report=retained.validate(root,binding,dict(scenario,initialIndex=schedule['initialIndex']),traces,manifest,genesis,state)
    authority=publication.validate(traces,manifest,state,'candidate-minimum',selector_limit=budget.MAX_SELECTORS,
                                   transfer_limit=publication.MAX_MEASURED_TRANSFERS,restorations=restorations)
    life=lifecycle.validate(traces,processes,history,'candidate-minimum',restarted=restarted)
    successful=cuts.validate(traces,processes,calls,manifest,entries,state,'candidate-minimum',answers,restarted=restarted,restorations=restorations)
    fault=ledger.gates(history,scenario,plan,traces,processes,manifest)
    need(state.ordinals==[0,1,2,3] and life['outcomes']['read']==life['outcomes']['update']=={'SUCCESS':4} and
         successful['successfulReads']==successful['successfulUpdates']==4,'recovery complete outcome reconciliation')
    timings=[dict(opId=c['opId'],kind=c['kind'],outcome=c['outcome'],controllerOfferToResponseNanos=c['endNanos']-c['startNanos'],
                  apiNanos=c['response']['apiEndNanos']-c['response']['apiStartNanos'],
                  clientQueueNanos=c['response']['apiStartNanos']-c['response']['receivedNanos']) for c in calls.values()]
    return dict(status='PASS',execution='recovery-member-physical-replay',qualifiedMeasurement=False,paidCloud=False,case=plan['case'],
                base=base,authorityBudget=bounds,publicationAuthority=authority,ledger=life,gates=fault,retained=retained_report,
                oracleInput=state.query_input(successful['cuts']),readTimings=successful['timings'],allOfferedTimings=timings,
                crashTransport=successful.get('crashTransport',{}),resources=resources(traces,processes,history,scenario),chosenUpdateOrdinals=state.ordinals)


def negative_cases(plan,scenario):
    def event(name,extra=lambda r:True):return lambda r:r['event']==name and extra(r)
    def replace(**values):return lambda r:dict(r,**values)
    def hidden(h,s):
        call=copy.deepcopy(next(c for c in h if c['kind']=='update'));call['opId']='hidden-update';h.append(call)
    def forged_answer(h,s):next(c for c in h if c['opId']==s['initialRead'])['response']['answer']={'forged':True}
    cases=[
        ('hidden-business',None,None,hidden,'recovery undeclared business call'),
        ('changed-carried-token',None,None,lambda h,s:s.__setitem__('carriedToken','AA=='),'recovery initial strong token'),
        ('forged-query-answer',event('CLIENT_SUCCESS',lambda r:r.get('opId')==scenario['initialRead']),replace(answer={'forged':True}),forged_answer,
         'measurement query differs from actual published core'),
        ('missing-fault-configuration',event('FAULT_CONFIGURATION'),replace(event='REMOVED_CONFIG'),None,'recovery fault configuration observation'),
        ('missing-proof-force',event('FORCE',lambda r:r['kind']=='PROOF' and r['node']==scenario['leader']),replace(event='REMOVED_FORCE'),None,'publication before local proof/remote ACK'),
        ('missing-generation-bytes',event('STORAGE_CUT',lambda r:r['cut']=='SELECTOR_BEFORE_ACK'),lambda r:{k:v for k,v in r.items() if k!='readGeneration'},None,'measurement selector lacks generation bytes'),
        ('premature-permit-release',event('REPLICA_READ_OWNERSHIP_RELEASED'),replace(completionReturned=False),None,'measurement premature ownership release'),
        ('changed-wait',event('REPLICA_READ_INVOKED',lambda r:r['policy']=='AT_LEAST_INDEX'),replace(waitTimeoutMillis=999),None,'measurement invoked policy/options changed'),
        ('foreign-process-row',event('CLIENT_SAMPLE'),lambda r:dict(r,pid=r['pid']+1000000),None,'measurement undeclared trace process'),
        ('missing-sample',event('CLIENT_SAMPLE'),replace(sampleOrdinal=99),None,'sample missing/duplicate ordinal'),
        ('invented-allocation',event('CLIENT_SAMPLE'),replace(allocatedBytes=dict(status='UNSUPPORTED',value=0)),None,'sample fabricated unavailable metric: allocatedBytes')]
    if plan['case']==controller.CASES[0]:
        cases.extend([
            ('changed-crash-pid',None,None,lambda h,s:s['crash'].__setitem__('pid',s['crash']['pid']+1),'recovery crash process binding'),
            ('changed-retained-inventory',None,None,lambda h,s:s['crash']['preReopen'].pop(next(iter(s['crash']['preReopen']))),'recovery pre-reopen inventory/bound'),
            ('missing-restored-generation',event('APPLICATION_RESTORED',lambda r:r['generation']==2),replace(event='REMOVED_RESTORATION'),None,'recovery missing/duplicate retained restoration'),
            ('early-restart',None,None,lambda h,s:s.__setitem__('restartIssuedNanos',s['exitObservedNanos']),'recovery crash/restart milestone order'),
            ('fabricated-abrupt-stop',event('CLIENT_SAMPLE',lambda r:r['node']==scenario['leader'] and r['generation']==1),replace(sampleKind='STOP'),None,'sample start/stop coverage')])
    else:
        probe=scenario['installed']['probe']['opId']
        def hint(h,s):
            next(c for c in h if c['opId']==probe)['response']['queues']['snapshotInstalledIndexObserved']+=1
            s['installed']['probe']['queues']['snapshotInstalledIndexObserved']+=1
        def row_hint(r):r['queues']['snapshotInstalledIndexObserved']+=1;return r
        cases.extend([
            ('early-heal',None,None,lambda h,s:s.__setitem__('healIssuedNanos',s['partitionNanos']),'recovery partition/held publication order'),
            ('changed-target',None,None,lambda h,s:s.__setitem__('target',s['leader']),'recovery snapshot target identity'),
            ('fabricated-install-hint',event('CLIENT_SUCCESS',lambda r:r.get('opId')==probe),row_hint,hint,'recovery missing/reordered physical snapshot install')])
    return cases


def negatives(root,expected,answers,*,traces=None):
    validate(root,expected,answers,traces=traces)
    root=Path(root);history=metadata(root,'history.json',32<<20);scenario=metadata(root,'scenario.json',1<<20)
    original=traces if traces is not None else {f'node-{i}':trace.Trace(root/f'node-{i}-trace.jsonl',node=f'node-{i}') for i in (1,2,3)};result=[]
    for name,predicate,change,mutate,reason in negative_cases(expected['measurementProfile'],scenario):
        traces=measurement_stream.changed(original,predicate,change) if predicate else original;h=copy.deepcopy(history);s=copy.deepcopy(scenario)
        if mutate:mutate(h,s)
        try:validate(root,expected,answers,traces=traces,history=h,scenario=s)
        except ValueError as error:
            need(str(error)==reason,'recovery unrelated negative rejection: '+name+': '+str(error));result.append(dict(case=name,status='REJECTED',reason=reason))
        else:raise ValueError('recovery negative accepted: '+name)
    return result


def replay(root,expected,output):
    root=Path(root).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    with measurement_verified.traces(root,output) as traces:
        preliminary=validate(root,expected,traces=traces);value=preliminary['oracleInput'];(output/'input.json').write_bytes(encoded(value)+b'\n')
        jar=root/'artifacts/general-search-engine-4.4.0.jar';cp=os.pathsep.join(map(str,(jar,root/'control-classes')))
        run=q.command(['java','-cp',cp,q.PACKAGE+'admission.V52MeasurementOracle',output/'oracle',output/'input.json'],output,'oracle')
        need(run.stderr.strip()=='coreSource='+str(jar),'measurement recovery loaded wrong query control')
        need(json.loads(run.stdout)==dict(status='PASS',measured=False,requests=len(value['requests']),updatesApplied=len(value['updates']),
                                         finalSequence=1+len(value['updates'])),'measurement recovery query replay incomplete')
        answers=oracle.validate_output(value,output/'oracle/answers.jsonl');checked=validate(root,expected,answers,traces=traces)
        checked['negatives']=negatives(root,expected,answers,traces=traces)
    (output/'validation.json').write_bytes(encoded(checked)+b'\n');return checked


def portable_member(source,expected,output):
    source=Path(source).resolve();output=Path(output).resolve()
    need(source!=output and source not in output.parents and output not in source.parents,'measurement recovery replay location overlap')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='FAIL',execution='recovery-portable-member',qualifiedMeasurement=False,paidCloud=False)
    try:
        if (source/bundle.INDEX).exists():
            previous=bundle.inventory(source)
            need((source/bundle.INDEX).read_bytes()==encoded(previous)+b'\n','measurement recovery noncanonical existing inventory')
        archive=output/'history.tar.gz';index=bundle.pack(source,archive)
        original=replay(source,expected,output/'original-validation');relocated=bundle.unpack(archive,output/'relocated')
        portable=replay(relocated,expected,output/'relocated-validation')
        need(original==portable,'measurement recovery relocated result/negative drift')
        scenario=metadata(source,'scenario.json',1<<20)
        required=[dict(case=v[0],status='REJECTED',reason=v[4]) for v in negative_cases(expected['measurementProfile'],scenario)]
        need(original['negatives']==required,'measurement recovery incomplete negative qualification')
        need(bundle.inventory(source)==index==bundle.inventory(relocated),'measurement recovery source changed during replay')
        raw=(source/'node-1/manifest.gsr').read_bytes();manifest=physical.f.inspect(raw,'MANIFEST')
        receipt.update(status='PASS',binding=expected,domain={k:manifest[k] for k in ('groupId','historyId')},manifestSha256=digest(raw),
                       inventorySha256=digest(encoded(index)),archiveSha256=bundle.sha_file(archive),archiveBytes=archive.stat().st_size,result=original)
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:(output/'receipt.json').write_bytes(encoded(receipt)+b'\n')
    return receipt
