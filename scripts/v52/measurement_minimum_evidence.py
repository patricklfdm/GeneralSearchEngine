"""Full M02/M03 member replay; a member is not complete Phase 6 acceptance."""
import copy
import json
import os
from pathlib import Path
from scripts.v51 import runtime_evidence as physical,public_qualification_harness as q
from . import measurement_minimum as controller,measurement_minimum_ledger as gates,measurement_identity as identities
from . import measurement_bundle as bundle,measurement_trace as trace,measurement_stream,measurement_options as options
from . import measurement_model as model,measurement_authority_budget as budget,measurement_history as lifecycle
from . import measurement_projection as projection,measurement_publication as publication,measurement_reads as cuts
from . import measurement_samples as samples,measurement_oracle as oracle,public_reads_evidence as reads
from . import measurement_window as window
from .evidence import need,digest,encoded


def metadata(root,name,maximum):return identities.metadata(root,name,maximum,label='measurement minimum')


def identity(root,expected):
    def check(binding,inventory):
        plan=controller.profile(binding.get('measurementProfile',{}).get('case'))
        need(binding['mode']==controller.MODE and binding['measurementProfile']==plan and
             binding['programSha256']==model.PLAN_SHA and binding.get('publicationAuthority')=='forced-generation-v1' and
             not {'driverExercise','smokeInitialization','readConfigurationOnly','faultParameters'}&set(binding) and
             'measurement-fault.json' not in inventory,'measurement minimum preparation profile')
        need(options.validate(binding['readParameters'])==plan['parameters'] and options.FILE in inventory and
             metadata(root,options.FILE,4096)==plan['parameters'],'measurement minimum parameter binding')
    return identities.identity(root,expected,check,label='measurement minimum')


def validate(root,expected,answers=None,*,traces=None,history=None,scenario=None,observed=None):
    root=Path(root).resolve();binding,processes=identity(root,expected);plan=binding['measurementProfile'];parameters=plan['parameters']
    history=metadata(root,'history.json',32<<20) if history is None else history
    scenario=metadata(root,'scenario.json',1<<20) if scenario is None else scenario
    observed=metadata(root,'observed.json',4<<20) if observed is None else observed
    need(metadata(root,'execution.json',1<<20)==dict(status='STOPPED',qualifiedMeasurement=False,paidCloud=False,failure=None,closeErrors=[]),
         'measurement minimum incomplete process execution')
    gates.schedule(history,scenario,observed,plan)
    traces=traces if traces is not None else {p['node']:trace.Trace(root/(p['node']+'-trace.jsonl'),node=p['node']) for p in processes}
    raw=(root/'node-1/manifest.gsr').read_bytes();manifest=dict(physical.f.inspect(raw,'MANIFEST'),digest=raw[16:48].hex())
    authority_budget=budget.validate(traces,manifest)
    base=physical.validate(root,traces,evidence_location=bundle.EvidenceLocation(root,binding['origin']),require_restart=False)
    manifest,genesis,entries=reads.context(root,traces);calls={c['opId']:c for c in history if c['kind'] in ('read','update')}
    state=projection.Projection(manifest,genesis,entries,[c for c in calls.values() if c['kind']=='update'])
    authority=publication.validate(traces,manifest,state,controller.MODE,selector_limit=budget.MAX_SELECTORS)
    ledger=lifecycle.validate(traces,processes,history,controller.MODE,pending_limit=parameters['pendingLimit'],
        minimum_wait_millis=parameters['waitTimeoutMillis'],allow_progress_not_reached=plan['family']=='M02' and parameters['waitTimeoutMillis']==0)
    successful=cuts.validate(traces,processes,calls,manifest,entries,state,controller.MODE,answers,
        pending_limit=parameters['pendingLimit'],minimum_wait_millis=parameters['waitTimeoutMillis'])
    gate_result=gates.validate(history,scenario,observed,traces,manifest,plan)
    if plan['releaseUpdate']:
        chosen=state.update_entries[scenario['releaseUpdate']]
        need(chosen['index']==gate_result['baselineIndex']+1 and chosen['sequence']==5,'measurement minimum unrelated release progress')
    resources={}
    for node,rows in traces.items():
        values=[]
        for row in rows:
            if row['event']=='CLIENT_SAMPLE':
                need(len(values)<1024,'measurement minimum resource observation count');values.append(row)
        resources[node]=samples.validate(values,controller.MODE,pending_limit=parameters['pendingLimit'])
        controls=[c for c in history if c['node']==node and c['kind'].startswith('sample-')]
        need([c['response']['sample'] for c in controls]==[{k:v for k,v in r.items() if k not in trace.META} for r in (values[0],values[-1])],
             'measurement minimum sample response binding')
    timings=[]
    for row in observed['operations']:
        call=calls[row['opId']];response=call['response']
        timings.append(dict(opId=call['opId'],kind=row['kind'],outcome=call['outcome'],reasonCode=response.get('reasonCode'),
            controllerOfferToResponseNanos=call['endNanos']-row['offerNanos'],apiNanos=response['apiEndNanos']-response['apiStartNanos'],
            clientQueueNanos=response['apiStartNanos']-response['receivedNanos']))
    distributions={}
    for kind in sorted({r['kind'] for r in timings}):
        distributions[kind]={}
        for outcome in sorted({r['outcome'] for r in timings if r['kind']==kind}):
            selected=[r for r in timings if r['kind']==kind and r['outcome']==outcome]
            distributions[kind][outcome]={key:window.distribution([r[key] for r in selected]) for key in
                                         ('controllerOfferToResponseNanos','apiNanos','clientQueueNanos')}
    need(ledger['outcomes']['read'].get('SUCCESS',0)==successful['successfulReads'] and
         ledger['outcomes']['update'].get('SUCCESS',0)==successful['successfulUpdates'],'measurement minimum outcome reconciliation')
    return dict(status='PASS',execution='minimum-member-physical-replay',qualifiedMeasurement=False,paidCloud=False,case=plan['case'],
                base=base,authorityBudget=authority_budget,publicationAuthority=authority,ledger=ledger,gates=gate_result,
                oracleInput=state.query_input(successful['cuts']),readTimings=successful['timings'],allOfferedTimings=timings,
                outcomeLatencies=distributions,resources=resources,chosenUpdateOrdinals=state.ordinals)


def negative_cases(plan,scenario):
    def event(name,extra=lambda r:True):return lambda r:r['event']==name and extra(r)
    def replace(**values):return lambda r:dict(r,**values)
    def change_counter(history,scenario,observed):
        next(c for c in history if c['opId']==scenario['admittedProbe'])['response']['queues']['readAdmissionsObserved']+=1
    def counter(row):row['queues']['readAdmissionsObserved']+=1;return row
    floor_id=scenario['floorProbes'][scenario['readTarget']]['opId']
    def change_floor(history,scenario,observed):
        next(c for c in history if c['opId']==floor_id)['response']['queues']['recoveryFloorObserved']+=1
        scenario['floorProbes'][scenario['readTarget']]['queues']['recoveryFloorObserved']+=1
    def floor_counter(row):row['queues']['recoveryFloorObserved']+=1;return row
    def hidden(history,scenario,observed):
        value=copy.deepcopy(next(c for c in history if c['kind']=='update'));value['opId']='hidden-update';history.append(value)
    def copied_response(history,scenario,observed):observed['operations'][0]['response']['outcome']='FORGED'
    def initial_answer(history,scenario,observed):
        next(c for c in history if c['opId']==scenario['initialRead'])['response']['answer']={'forged':True}
    cases=[
        ('missing-offer',None,None,lambda h,s,o:o['operations'].pop(),'minimum incomplete offered ledger'),
        ('hidden-business-call',None,None,hidden,'minimum undeclared business call'),
        ('changed-response',None,None,copied_response,'minimum offered response/clock binding'),
        ('forged-query-answer',event('CLIENT_SUCCESS',lambda r:r.get('opId')==scenario['initialRead']),replace(answer={'forged':True}),initial_answer,
         'measurement query differs from actual published core'),
        ('changed-bound',None,None,lambda h,s,o:s.__setitem__('minimum','AA=='),'INVALID_TOKEN'),
        ('early-gate',None,None,lambda h,s,o:s.__setitem__('gateNanos',0),'minimum gate controller order'),
        ('fabricated-admission-counter',event('CLIENT_SUCCESS',lambda r:r.get('opId')==scenario['admittedProbe']),counter,change_counter,
         'minimum fabricated admission counter'),
        ('fabricated-floor-counter',event('CLIENT_SUCCESS',lambda r:r.get('opId')==floor_id),floor_counter,change_floor,
         'minimum fabricated recovery floor counter'),
        ('missing-proof-force',event('FORCE',lambda r:r['kind']=='PROOF' and r['node']==scenario['leader']),replace(event='REMOVED_FORCE'),None,
         'publication before local proof/remote ACK'),
        ('missing-generation-bytes',event('STORAGE_CUT',lambda r:r['cut']=='SELECTOR_BEFORE_ACK'),
         lambda r:{k:v for k,v in r.items() if k!='readGeneration'},None,'measurement selector lacks generation bytes'),
        ('missing-sample',event('CLIENT_SAMPLE'),replace(sampleOrdinal=99),None,'sample missing/duplicate ordinal'),
        ('invented-allocation',event('CLIENT_SAMPLE'),replace(allocatedBytes=dict(status='UNSUPPORTED',value=0)),None,
         'sample fabricated unavailable metric: allocatedBytes'),
        ('premature-permit-release',event('REPLICA_READ_OWNERSHIP_RELEASED'),replace(completionReturned=False),None,
         'measurement premature ownership release'),
        ('changed-wait',event('REPLICA_READ_INVOKED',lambda r:r['policy']=='AT_LEAST_INDEX'),replace(waitTimeoutMillis=999),None,
         'measurement invoked policy/options changed')]
    if plan['releaseUpdate']:
        cases.append(('early-progress-release',None,None,lambda h,s,o:s.__setitem__('releaseOfferNanos',0),
                      'minimum progress release preceded gate/delay'))
    if plan['family']=='M03':
        def reservation(history,scenario,observed):
            next(c for c in history if c['opId']==scenario['admittedProbe'])['response']['queues']['admissionAvailable']=0
        def reserved(row):row['queues']['admissionAvailable']=0;return row
        cases.append(('missing-reserved-slot',event('CLIENT_SUCCESS',lambda r:r.get('opId')==scenario['admittedProbe']),reserved,reservation,
                      'minimum saturation queue gate'))
    return cases


def negatives(root,expected,answers):
    validate(root,expected,answers)
    root=Path(root);history=metadata(root,'history.json',32<<20);scenario=metadata(root,'scenario.json',1<<20);observed=metadata(root,'observed.json',4<<20)
    original={f'node-{i}':trace.Trace(root/f'node-{i}-trace.jsonl',node=f'node-{i}') for i in (1,2,3)};result=[]
    for name,predicate,change,mutate,reason in negative_cases(expected['measurementProfile'],scenario):
        traces=measurement_stream.changed(original,predicate,change) if predicate else original
        h=copy.deepcopy(history);s=copy.deepcopy(scenario);o=copy.deepcopy(observed)
        if mutate:mutate(h,s,o)
        try:validate(root,expected,answers,traces=traces,history=h,scenario=s,observed=o)
        except ValueError as error:
            need(str(error)==reason,'measurement minimum unrelated negative rejection: '+name+': '+str(error))
            result.append(dict(case=name,status='REJECTED',reason=reason))
        else:raise ValueError('measurement minimum negative accepted: '+name)
    return result


def replay(root,expected,output):
    root=Path(root).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    preliminary=validate(root,expected);value=preliminary['oracleInput'];(output/'input.json').write_bytes(encoded(value)+b'\n')
    jar=root/'artifacts/general-search-engine-4.4.0.jar';cp=os.pathsep.join(map(str,(jar,root/'control-classes')))
    run=q.command(['java','-cp',cp,q.PACKAGE+'admission.V52MeasurementOracle',output/'oracle',output/'input.json'],output,'oracle')
    need(run.stderr.strip()=='coreSource='+str(jar),'measurement minimum loaded wrong query control')
    need(json.loads(run.stdout)==dict(status='PASS',measured=False,requests=len(value['requests']),updatesApplied=len(value['updates']),
                                     finalSequence=1+len(value['updates'])),'measurement minimum query replay incomplete')
    answers=oracle.validate_output(value,output/'oracle/answers.jsonl');checked=validate(root,expected,answers)
    checked['negatives']=negatives(root,expected,answers);(output/'validation.json').write_bytes(encoded(checked)+b'\n');return checked


def portable_member(source,expected,output):
    source=Path(source).resolve();output=Path(output).resolve()
    need(source!=output and source not in output.parents and output not in source.parents,'measurement minimum replay location overlap')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='FAIL',execution='minimum-portable-member',qualifiedMeasurement=False,paidCloud=False)
    try:
        if (source/bundle.INDEX).exists():
            previous=bundle.inventory(source)
            need((source/bundle.INDEX).read_bytes()==encoded(previous)+b'\n','measurement minimum noncanonical existing inventory')
        archive=output/'history.tar.gz';index=bundle.pack(source,archive)
        original=replay(source,expected,output/'original-validation');relocated=bundle.unpack(archive,output/'relocated')
        portable=replay(relocated,expected,output/'relocated-validation')
        need(original==portable,'measurement minimum relocated result/negative drift')
        scenario=metadata(source,'scenario.json',1<<20)
        required=[dict(case=v[0],status='REJECTED',reason=v[4]) for v in negative_cases(expected['measurementProfile'],scenario)]
        need(original['negatives']==required,'measurement minimum incomplete negative qualification')
        need(bundle.inventory(source)==index==bundle.inventory(relocated),'measurement minimum source changed during replay')
        raw=(source/'node-1/manifest.gsr').read_bytes();manifest=physical.f.inspect(raw,'MANIFEST')
        receipt.update(status='PASS',binding=expected,domain={k:manifest[k] for k in ('groupId','historyId')},manifestSha256=digest(raw),
                       inventorySha256=digest(encoded(index)),archiveSha256=bundle.sha_file(archive),archiveBytes=archive.stat().st_size,result=original)
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:(output/'receipt.json').write_bytes(encoded(receipt)+b'\n')
    return receipt
