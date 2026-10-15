"""Independent higher-promise and installed-but-unpublished read authority checks."""
import copy
from pathlib import Path
from . import public_reads_evidence as e, public_read_lifecycle_evidence as lifecycle, token
from .evidence import need
from scripts.v51 import performance_bundle as bundle

CASES=('promise-before','promise-after','promise-after-halt','promise-after-kill','install-paused','install-halt','install-kill')


def crossing(rows,epoch,start,end):
    promises=[r for r in rows if r['event']=='FORCE' and r['kind']=='PROMISE' and
              e.physical.f.inspect(e.physical.raw(r['record']),'PROMISE')['epoch']>epoch and start<r['order']<end]
    need(promises,'missing crossing higher promise');return promises


def schedule(root,name,traces,history,processes,*,details=None):
    need(name in CASES,'unknown public read protocol schedule')
    details=e.read(root/'read-protocol.json') if details is None else details
    need(details['scenario']==name,'read protocol scenario binding');by_id={a['opId']:a for a in history}
    def call(key):
        need(details[key] in by_id,'missing scheduled read protocol call');return by_id[details[key]]
    def response(key):
        value=call(key);need(value['outcome']=='SUCCESS','read protocol recovery did not succeed');return value['response']
    target=call('targetOp');node=details['node'];own=[r for r in traces[node] if r['pid']==target['pid']]
    abrupt=name.endswith(('-halt','-kill'))
    need(target['node']==node,'read protocol target node')
    for process in processes:lifecycle.ownership([r for r in traces[process['node']] if r['pid']==process['pid']],process['exitCode']!=0)
    pauses=[r for r in own if r['event']=='CUT_REACHED' and r['cut']==details['pause'] and r['mode']=='pause']
    need(len(pauses)==1,'missing read protocol pause');pause=pauses[0]
    release=[r for r in own if r['event']=='CUT_RELEASED' and r['cut']==details['pause']]
    def events(event,op):return [r for r in own if r['event']==event and r.get('opId')==op['opId']]
    invocations=events('CLIENT_INVOKE',target);need(len(invocations)==1,'missing protocol read invocation')
    invoke=invocations[0]
    runtime=next((r for r in own if r['event']=='REPLICA_READ_INVOKED' and r['order']>invoke['order']),None)
    need(runtime is not None,'missing protocol runtime invocation')
    captures=[r for r in own if r['event']=='REPLICA_READ_CAPTURE_VALIDATED' and r['readId']==runtime['readId']]
    if name.startswith('promise-'):
        need(target['policy']=='LEADER_STRONG' and runtime['policy']=='LEADER_STRONG','fenced read silently changed policy')
        need(len(release)==1 and pause['order']<release[0]['order'],'missing promise pause release')
        crossing(own,details['oldEpoch'],pause['order'],release[0]['order'])
        need(any(r['event']=='NETWORK_DROP' for rows in traces.values() for r in rows),'missing fencing partition')
        later=response('laterOp');need(call('laterOp')['node']==details['successor']!=node,'missing successor strong read')
        if name=='promise-before':
            failures=events('CLIENT_FAILURE',target)
            need(target.get('reasonCode')=='STALE_EPOCH' and target['outcome']=='NOT_APPLICABLE' and len(failures)==1,
                 'uncaptured strong read was not fenced')
            need(not captures and not events('REPLICA_READ_CALLBACK',target),'fenced request obtained a view')
            crossing(own,details['oldEpoch'],pause['order'],failures[0]['order'])
            settlements=[r for r in own if r['event']=='REPLICA_READ_SETTLING' and r['readId']==runtime['readId']]
            need(len(settlements)==1 and settlements[0]['barrierEpoch']==details['oldEpoch'] and settlements[0]['barrierIndex']>0,
                 'before-capture fence lacks completed fresh barrier')
        else:
            need(len(captures)==1 and captures[0]['barrierEpoch']==details['oldEpoch'] and captures[0]['order']<pause['order'],
                 'crossing promise lacks earlier valid capture')
            need(len(events('REPLICA_READ_CALLBACK',target))==1,'captured overlapping callback count')
            if not abrupt:
                need(target['outcome']=='SUCCESS' and target['response']['documents']==details['carried']['documents'] and
                     target['response']['token']==captures[0]['token'],'higher promise changed captured result')
    else:
        need(details['pause']=='BEFORE_LOCAL_PUBLISH','wrong install pause')
        pending=next((r for r in reversed(own[:own.index(pause)]) if r['event']=='BEFORE_LOCAL_PUBLISH'),None)
        need(pending is not None,'missing pending application reconstruction')
        manifest=e.context(root,traces)[0]
        selected=e.physical.frame(details['selectedBeforeIsolation'],'SELECTED',manifest)
        need(node not in {b['node'] for b in selected['bases']} and any(r['event']=='PROMISE_QUORUM' and
             r['selected']==details['selectedBeforeIsolation'] for r in traces[details['originalLeader']]),'install isolation removed selected quorum')
        need(any(r['event']=='NETWORK_DROP' for rows in traces.values() for r in rows),'install isolation not observed')
        snapshot=e.recovery.snapshot(e.physical.raw(pending['snapshot']),manifest)
        installs=[r for r in own if r['event']=='REJOIN_INSTALLED' and r['order']<pause['order'] and
                  e.publication_identity(e.recovery.snapshot(e.physical.raw(r['snapshot']),manifest))==e.publication_identity(snapshot)]
        need(installs and len(snapshot['anchors'])>=token.decode(e.physical.raw(response('laterOp')['token']))['index'],
             'missing verified snapshot installation')
        denied=call('deniedOp');need(denied['outcome']=='NOT_APPLICABLE' and denied['reasonCode']=='NOT_READY' and
                                    denied['policy']=='STALE_ALLOWED','install local-read state gate')
        need(target['policy']=='AT_LEAST_INDEX' and target['minimum']==details['carried']['token'],'install minimum options')
        for value in (denied,target):
            need(not events('REPLICA_READ_CALLBACK',value),'install invoked unreadable callback')
            invocation=events('CLIENT_INVOKE',value);need(len(invocation)==1 and pause['order']<invocation[0]['order'],'read not during paused install')
            observed=next((r for r in own if r['event']=='REPLICA_READ_INVOKED' and r['order']>invocation[0]['order']),None)
            need(observed is not None and not any(r['event']=='REPLICA_READ_ADMITTED' and r['readId']==observed['readId'] for r in own),
                 'unreadable install allocated read ownership')
        need(not captures,'install minimum acquired a view')
        if not abrupt:
            need(target['outcome']=='NOT_APPLICABLE' and target['reasonCode']=='NOT_READY','install minimum state gate')
            need(len(release)==1 and all(events('CLIENT_FAILURE',v)[0]['order']<release[0]['order'] for v in (denied,target)),
                 'install rejection escaped publication hold')
        else:need(not release,'interrupted install was released before process death')
        until=release[0]['order'] if release else own[-1]['order']
        need(not any(r['event']=='LOCAL_PUBLISHED' and pause['order']<r['order']<until for r in own),'paused install was already published')
    recovered=response('recoveredOp');carried=details['carried']
    need(carried['opId'] in by_id and by_id[carried['opId']]['response']==carried,'unobserved protocol carried token')
    need(call('recoveredOp')['minimum']==carried['token'] and call('recoveredOp')['node']==node and
         token.decode(e.physical.raw(recovered['token']))['index']>=token.decode(e.physical.raw(carried['token']))['index'],
         'read protocol carried lower bound')
    if name.startswith('promise-'):need(recovered['documents']==response('laterOp')['documents'],'healed publication lost successor write')
    else:need(recovered['documents']==response('laterOp')['documents'],'installed application differs from source')
    if abrupt:
        cuts=[r for r in own if r['event']=='CUT_REACHED' and r['cut']==details['cut'] and r['mode']==details['mode']]
        need(len(cuts)==1 and cuts[0]==own[-1] and details['pid']==target['pid'],'missing read protocol abrupt boundary')
        need(target['outcome']=='PENDING' and target['endNanos'] is None and target.get('disconnectNanos') is not None and
             not events('CLIENT_SUCCESS',target) and not events('CLIENT_FAILURE',target),'lost protocol response reclassified')
        before=root/'pre-reopen'/node
        need(details['preReopen']==bundle.members(before) and details['preReopen'],'read protocol pre-reopen inventory')
        stored=e.physical.storage._inspect(before,8<<30,8<<20,Path(e.read(root/'binding.json')['origin'])/node)
        restore=[r for r in traces[node] if r['generation']==2 and r['event']=='APPLICATION_RESTORED']
        need(len(restore)==1 and call('recoveredOp')['generation']==2,'missing protocol retained restart')
        snapshot=e.recovery.snapshot(e.physical.raw(restore[0]['snapshot']),e.context(root,traces)[0])
        need(len(snapshot['anchors'])==stored['provenThrough'] and all(a['entryDigest']==stored['acceptedDigests'][i]
             for i,a in enumerate(snapshot['anchors'])),'protocol retained prefix changed')
    allowed={target['opId']}|({details['deniedOp']} if name.startswith('install-') else set())
    need(all(v['outcome']=='SUCCESS' or v['opId'] in allowed for v in history),'undeclared failed protocol call')


def negatives(root,binding,queries):
    e.validate(root,binding,queries);results=e.negatives(root,binding,queries)
    original=e.traces_at(root);history=e.read(root/'history.json');processes=e.read(root/'processes.json');details=e.read(root/'read-protocol.json')
    node=details['node'];name=binding['scenario'];own=original[node]
    changed=copy.deepcopy(original)
    if name.startswith('promise-'):
        changed[node]=[r for r in changed[node] if not(r['event']=='FORCE' and r['kind']=='PROMISE' and
                       e.physical.f.inspect(e.physical.raw(r['record']),'PROMISE')['epoch']>details['oldEpoch'])]
        reason='missing crossing higher promise';variant='missing-crossing-promise'
    else:
        changed[node]=[r for r in changed[node] if r['event']!='REJOIN_INSTALLED'];reason='missing verified snapshot installation';variant='missing-installation'
    try:schedule(root,name,changed,history,processes,details=details)
    except ValueError as error:
        need(reason in str(error),'unrelated protocol negative: '+str(error));results.append(dict(case=variant,status='REJECTED',reason=str(error)))
    else:raise ValueError('invalid read protocol evidence accepted: '+variant)
    return results
