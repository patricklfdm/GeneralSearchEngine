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
from . import measurement_projection,measurement_stream,measurement_history,measurement_publication
from .evidence import need,digest,encoded


def publication_generation(row,mode):
    if 'applicationGeneration' not in row:
        need(mode=='published-v51-legacy-strong','candidate publication missing application generation');return None
    value=row['applicationGeneration'];need(type(value) is int and value>0,'measurement publication generation type');return value


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
    cuts=[];successes={};timings={}
    for process in processes:
        node=process['node'];invoked={};captures={};entered={};released={};callbacks={};client_invocations={};force_order={};promised=0;barriers=set();latest=None;idle=False;reservations={}
        for row in traces[node]:
            event=row['event'];need(row['pid']==process['pid'] and row['generation']==1,'measurement observation process')
            need(row['groupId']==manifest['groupId'] and row['manifestDigest']==manifest['digest'],'measurement observation authority')
            if event=='FORCE':
                record=physical.frame(row['record'],row['kind'],manifest)
                need(row['forceStartNanos']<row['forceEndNanos']<=row['localNanos'],'measurement force timing')
                if row['kind']=='PROMISE':promised=record['epoch']
                if row['kind']=='ACCEPT':force_order[record['entryDigest']]=row['order']
            elif event in ('APPLICATION_RESTORED','PUBLISHED','LOCAL_PUBLISHED'):
                snapshot=recovery.snapshot(physical.raw(row['snapshot']),manifest);value=projection.publication(snapshot)
                latest=dict(value,generation=publication_generation(row,binding['mode']),order=row['order'])
            elif event=='CLIENT_INVOKE' and row['opId'] in calls:
                call=calls[row['opId']];need(row['opId'] not in client_invocations and all(row[k]==call[k] for k in ('kind','query','document') if k in call),'measurement client invocation binding')
                client_invocations[row['opId']]=row
            elif event in ('PUBLIC_READ_INVOKE','REPLICA_READ_INVOKED'):
                need(event==('PUBLIC_READ_INVOKE' if binding['mode'].endswith('legacy-strong') else 'REPLICA_READ_INVOKED'),'measurement wrong public read capability')
                need(type(row['readId']) is int and row['readId']>0,'measurement read identity type')
                identity=row['readId'];need(identity not in invoked and row['opId'] in client_invocations,'measurement read invocation correlation')
                invoked[identity]=row
            elif event in ('READ_CAPTURE_VALIDATED','REPLICA_READ_CAPTURE_VALIDATED'):
                need(event==('READ_CAPTURE_VALIDATED' if binding['mode'].endswith('legacy-strong') else 'REPLICA_READ_CAPTURE_VALIDATED'),'measurement wrong capture capability')
                need(all(type(row[k]) is int and row[k]>=0 for k in ('readId','index','sequence')),'measurement captured counter type')
                identity=row['readId'];need(identity in invoked and identity not in captures and latest is not None,'measurement read capture identity')
                invocation=invoked[identity];call=calls[invocation['opId']]
                need(latest['index']==row['index'] and latest['sequence']==row['sequence'] and latest['order']<row['order'],'measurement capture differs from local publication')
                need(invocation['order']<row['order'],'measurement capture before invocation')
                policy='LEADER_STRONG' if event=='READ_CAPTURE_VALIDATED' else row['policy']
                expected_policy='LEADER_STRONG' if call.get('setupToken') or binding['mode'].endswith('strong') else 'STALE_ALLOWED' if binding['mode']=='candidate-stale' else 'AT_LEAST_INDEX'
                need(policy==expected_policy,'measurement silent read policy fallback')
                if event=='REPLICA_READ_CAPTURE_VALIDATED':
                    identity_token=token.decode(physical.raw(row['token']))
                    need(identity_token==dict(version=1,groupId=manifest['groupId'],historyId=manifest['historyId'],manifestDigest=manifest['digest'],index=row['index']), 'measurement captured token identity')
                    need(row['applicationGeneration']==latest['generation'] and row['captureNanos']<row['deadlineNanos']==invocation['deadlineNanos'],'measurement capture deadline/generation')
                    need(1<=row['owned']<=63 and row['waiting']+row['captured']+row['settling']==row['owned'] and row['captured']==1,'measurement capture ownership')
                    if policy=='AT_LEAST_INDEX':
                        lower=token.decode(physical.raw(call['minimum']));need(invocation['minimum']==call['minimum'] and invocation['waitTimeoutMillis']==5000 and
                            all(lower[k]==identity_token[k] for k in ('groupId','historyId','manifestDigest')) and lower['index']<=row['index'],'measurement minimum not satisfied')
                if policy=='LEADER_STRONG':
                    last=latest['last'];epoch=row['epoch'] if event=='READ_CAPTURE_VALIDATED' else row['barrierEpoch']
                    need(last in entries and entries[last]['operation']==9 and invocation['order']<force_order.get(last,0)<row['order'] and
                         epoch==promised==latest['epoch'] and last not in barriers,'measurement strong barrier not fresh')
                    if event=='REPLICA_READ_CAPTURE_VALIDATED':need(row['barrierIndex']==row['index'],'measurement strong barrier cut')
                    barriers.add(last)
                captures[identity]=row
            elif event in ('READ_CAPTURED','REPLICA_READ_CAPTURED'):
                need(event==('READ_CAPTURED' if binding['mode'].endswith('legacy-strong') else 'REPLICA_READ_CAPTURED'),'measurement wrong entered capability')
                identity=row['readId'];need(identity in captures and identity not in entered,'measurement entered view identity')
                original=captures[identity]
                need(all(encoded(row[k])==encoded(original[k]) for k in ('index','sequence','token','policy','applicationGeneration') if k in original) and
                     row['order']>original['order'],'measurement changed entered cut')
                entered[identity]=row
            elif event in ('READ_RELEASED','REPLICA_READ_RELEASED'):
                identity=row['readId'];need(identity in entered and identity not in released,'measurement view release identity')
                original=captures[identity];need(all(row[k]==original[k] for k in ('index','sequence')) and row['order']>original['order'],'measurement changed released cut')
                released[identity]=row
            elif event in ('CLIENT_CALLBACK_BEGIN','CLIENT_CALLBACK_END'):
                callbacks.setdefault(row['opId'],[]).append(row)
            elif event=='CLIENT_SUCCESS' and row['opId'] in calls:
                identity=row['opId'];call=calls[identity];need(identity in client_invocations and identity not in successes,'measurement duplicate/uninvoked response')
                actual={k:v for k,v in row.items() if k not in trace.META}
                need(actual==call['response'] and call['pid']==row['pid'] and call['node']==node,'measurement controller/worker response differs')
                need(row['receivedNanos']<=row['apiStartNanos']<=client_invocations[identity]['localNanos']<=row['apiEndNanos']<=row['localNanos'],'measurement clock-local API timing')
                if call['kind']=='read':
                    sources=[i for i,r in invoked.items() if r['opId']==identity];need(len(sources)==1 and sources[0] in released,'measurement read reply before release')
                    read_id=sources[0];capture=captures[read_id];release=released[read_id];need(release['order']<row['order'],'measurement reply before release')
                    if 'token' in capture:
                        need(all(row[k]==capture[k] for k in ('token','sequence','policy')),'measurement read result changed capture')
                        cb=callbacks.get(identity,[]);need([r['event'] for r in cb]==['CLIENT_CALLBACK_BEGIN','CLIENT_CALLBACK_END'] and
                           entered[read_id]['order']<cb[0]['order']<cb[1]['order']<release['order'] and all(r['sequence']==capture['sequence'] for r in cb),'measurement callback interval')
                    cut=dict(sequence=capture['sequence'],query=call['query']);cuts.append(cut)
                    if answers is not None:need(row['answer']==answers[oracle.key(**cut)],'measurement query differs from actual published core')
                    timings[identity]=dict(apiNanos=row['apiEndNanos']-row['apiStartNanos'],clientQueueNanos=row['apiStartNanos']-row['receivedNanos'],
                                          validationToCaptureNanos=entered[read_id]['localNanos']-capture['localNanos'],
                                          captureToReleaseNanos=release['localNanos']-entered[read_id]['localNanos'])
                if call['kind']=='update':
                    need(latest is not None,'measurement update lacks publication');projection.update_response(call,latest['index'])
                successes[identity]=row
            elif event=='CLIENT_IDLE':
                queues=row['queues'];need(queues['admissionAvailable']==64 and all(queues.get(k,0)==0 for k in ('readsOwned','readsWaiting','readsCaptured','readsSettling','readsAlarms')),'measurement final ownership leak');idle=True
            elif event=='TRANSPORT':
                identity=row['reservation'];transition=row['transition'];need(type(row['bytes']) is int and row['bytes']>=0,'measurement transport bytes')
                if transition.endswith('_ADMITTED'):
                    need(identity>0 and identity not in reservations,'measurement duplicate transport admit');reservations[identity]=row['bytes']
                elif transition.endswith('_RELEASED'):
                    need(identity in reservations and reservations.pop(identity)==row['bytes'],'measurement unmatched transport release')
        need(idle,'measurement missing final resource observation');need(not reservations,'measurement unreleased transport ownership')
    need(set(successes)==set(calls),'measurement incomplete success observations')
    ledger=measurement_history.validate(traces,processes,history,binding['mode'])
    driver=None
    if binding.get('driverExercise',False):
        offered=reads.read(root/'offered.json')
        requests=[dict(kind='read',ordinal=i,offsetNanos=i*100_000_000,window='driver-smoke',query=model.query(i)) for i in range(10)]
        dispatched=load.validate(offered,requests,3_000_000_000,history)
        need(dispatched['outcomes']=={'SUCCESS':10} and {v['opId'] for v in offered['offers']}=={v['opId'] for v in requested},'measurement driver smoke operation set')
        resources={}
        for node,reader in traces.items():
            observed=[r for r in reader if r['event']=='CLIENT_SAMPLE'];resources[node]=samples.validate(observed,binding['mode'])
            need(resources[node]['periodicSamples']>=2,'measurement driver smoke missing periodic samples')
            controls=[c for c in history if c['node']==node and c['kind'].startswith('sample-')]
            need([c['kind'] for c in controls]==['sample-start','sample-stop'] and all(c['outcome']=='SUCCESS' for c in controls),'measurement sampler control ledger')
            need(controls[0]['endNanos']<=offered['startNanos'] and controls[-1]['startNanos']>=offered['drainEndNanos'],'measurement sampler does not cover dispatch')
            for call,sample in zip(controls,(observed[0],observed[-1])):
                need(call['response']['sample']=={k:v for k,v in sample.items() if k not in trace.META},'measurement sampler response differs from observation')
        driver=dict(load=dispatched,resources=resources)
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
