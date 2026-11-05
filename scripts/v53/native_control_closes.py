"""Bind native cleanup intervals to original multi-session source associations.

Cleanup completion is distinct from listener drain; this reader makes no
whole-runtime shutdown or OS-lock/custody claim.
"""
from . import control_close_evidence as close
from . import native_source_resources as source

need=close.need


def bind(traces,closes,associations,*,export_ownership=False):
    account=close.replay(traces,closes,export_ownership=export_ownership)
    leases,legacy,_=source.scan(traces);need(not legacy,'native close legacy source bindings')
    by_session={};by_trace={}
    for response,(session,trace) in associations.items():
        need(response in leases and session in leases and trace in leases and response[0]==session[0]==trace[0] and
             leases[response]['role']=='source-response' and leases[session]['role']=='source-session' and
             leases[trace]['role'] in close.SERVICES.values(),'native close original association')
        by_session.setdefault(session,set()).add(response);by_trace.setdefault(session,set()).add(trace)
    expected={k for k,v in leases.items() if v['role']=='source-session'}
    need(set(by_session)==expected and expected,'native close complete original sessions')
    responses=0;services=0;joining=0
    for session,keys in by_session.items():
        node,owner=session;observed=account['owners'][node];pair=observed['pairs'][owner]
        cursor=pair['begin']['resourceSequence']
        wanted=sorted(key[1] for key in keys if leases[key]['start']<=cursor<leases[key]['end'])
        need(pair['begin']['children']==wanted,'native close complete original response inventory')
        need(by_trace[session]=={(node,observed['sessionParents'][owner])},'native close exact original trace')
        responses+=len(wanted)
    for observed in account['owners'].values():
        for name in observed['pairs']:
            if close.role(name) in close.SERVICES:services+=1
            if close.role(name)=='joining-checkpoint-service':joining+=1
    export_result=None
    if export_ownership:
        from . import session_export_evidence
        export_result=session_export_evidence.inspect(traces,closes)
    return dict(status=export_result['status'] if export_result else 'PASS',scope='native-source-cleanup-performing-invocations',cleanupIntervals=account['cleanupIntervals'],
                childReferences=account['childReferences'],services=services,sessions=len(expected),responsesAtClose=responses,
                joiningCheckpointServices=joining,nativeServiceCleanupIntervalsQualified=True,listenerDrainQualified=False,
                exportOwnership=export_result,wholeRuntimeResourcesQualified=False,phase3Complete=False)


def replay(events,wires,traces,boundaries,identities,root,closes,*,export_ownership=False):
    associations={}
    original=source.replay(events,wires,traces,boundaries,identities,root,bindings=associations)
    return dict(bind(traces,closes,associations,export_ownership=export_ownership),precondition=original)
