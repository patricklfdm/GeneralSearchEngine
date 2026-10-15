"""Chosen-publication/query-cut checks shared by short and measured histories.

Run the independent physical authority and complete consumer-ledger validators
as well. This helper validates successful reads and updates; failed attempts stay
in the supplied ledger and never become query cuts or successful samples.
"""
from scripts.v51 import runtime_evidence as physical,recovery_inspector as recovery
from . import measurement_trace as trace,measurement_oracle as oracle,token
from .evidence import need,encoded


def publication_generation(row,mode):
    if 'applicationGeneration' not in row:
        need(mode=='published-v51-legacy-strong','candidate publication missing application generation');return None
    value=row['applicationGeneration'];need(type(value) is int and value>0,'measurement publication generation type');return value



def validate(traces,processes,calls,manifest,entries,projection,mode,answers=None,*,pending_limit=64):
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
                latest=dict(value,generation=publication_generation(row,mode),order=row['order'])
            elif event=='CLIENT_INVOKE' and row['opId'] in calls:
                call=calls[row['opId']];need(row['opId'] not in client_invocations and all(row[k]==call[k] for k in ('kind','query','document') if k in call),'measurement client invocation binding')
                client_invocations[row['opId']]=row
            elif event in ('PUBLIC_READ_INVOKE','REPLICA_READ_INVOKED'):
                need(event==('PUBLIC_READ_INVOKE' if mode.endswith('legacy-strong') else 'REPLICA_READ_INVOKED'),'measurement wrong public read capability')
                need(type(row['readId']) is int and row['readId']>0,'measurement read identity type')
                identity=row['readId'];need(identity not in invoked and row['opId'] in client_invocations,'measurement read invocation correlation')
                invoked[identity]=row
            elif event in ('READ_CAPTURE_VALIDATED','REPLICA_READ_CAPTURE_VALIDATED'):
                need(event==('READ_CAPTURE_VALIDATED' if mode.endswith('legacy-strong') else 'REPLICA_READ_CAPTURE_VALIDATED'),'measurement wrong capture capability')
                need(all(type(row[k]) is int and row[k]>=0 for k in ('readId','index','sequence')),'measurement captured counter type')
                identity=row['readId'];need(identity in invoked and identity not in captures and latest is not None,'measurement read capture identity')
                invocation=invoked[identity];call=calls[invocation['opId']]
                need(latest['index']==row['index'] and latest['sequence']==row['sequence'] and latest['order']<row['order'],'measurement capture differs from local publication')
                need(invocation['order']<row['order'],'measurement capture before invocation')
                policy='LEADER_STRONG' if event=='READ_CAPTURE_VALIDATED' else row['policy']
                expected_policy='LEADER_STRONG' if call.get('setupToken') or mode.endswith('strong') else 'STALE_ALLOWED' if mode=='candidate-stale' else 'AT_LEAST_INDEX'
                need(policy==expected_policy,'measurement silent read policy fallback')
                if event=='REPLICA_READ_CAPTURE_VALIDATED':
                    identity_token=token.decode(physical.raw(row['token']))
                    need(identity_token==dict(version=1,groupId=manifest['groupId'],historyId=manifest['historyId'],manifestDigest=manifest['digest'],index=row['index']), 'measurement captured token identity')
                    need(row['applicationGeneration']==latest['generation'] and row['captureNanos']<row['deadlineNanos']==invocation['deadlineNanos'],'measurement capture deadline/generation')
                    need(1<=row['owned']<=min(64,pending_limit-1) and row['waiting']+row['captured']+row['settling']==row['owned'] and row['captured']==1,'measurement capture ownership')
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
                need(event==('READ_CAPTURED' if mode.endswith('legacy-strong') else 'REPLICA_READ_CAPTURED'),'measurement wrong entered capability')
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
    need(set(successes)=={key for key,call in calls.items() if call['outcome']=='SUCCESS'},'measurement incomplete success observations')
    return dict(cuts=cuts,timings=timings,successfulReads=sum(calls[k]['kind']=='read' for k in successes),successfulUpdates=sum(calls[k]['kind']=='update' for k in successes))
