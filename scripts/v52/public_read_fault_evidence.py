"""Declared fault edges checked separately from the common physical/public read oracle."""
import copy
from . import public_reads_evidence as e, token
from .evidence import need
from scripts.v51 import performance_bundle as bundle


def schedule(root,name,traces,history,processes,*,fault=None):
    fault=e.read(root/'fault.json') if fault is None else fault;need(fault['scenario']==name,'read fault scenario binding')
    by_id={a['opId']:a for a in history};node=fault['node'];own=traces[node]
    def call(key):
        need(fault[key] in by_id,'missing scheduled public operation');return by_id[fault[key]]
    def response(key):
        value=call(key);need(value['outcome']=='SUCCESS','scheduled read did not succeed');return value['response']
    def no_callback(key):
        identity=call(key)['opId'];need(not any(r['event']=='REPLICA_READ_CALLBACK' and r['opId']==identity for r in own),'rejected read invoked callback')
    def rejected(key,reason):
        value=call(key);need(value.get('reasonCode')==reason and value['outcome']!='SUCCESS','scheduled rejection category')
        events=[r for r in own if r['event']=='CLIENT_FAILURE' and r['opId']==value['opId']]
        need(len(events)==1 and events[0].get('reasonCode')==reason,'missing worker rejection');no_callback(key)
    if name.startswith(('capture-','release-')):
        lost=call('lostOp');need(lost['outcome']=='PENDING' and lost['endNanos'] is None and lost.get('disconnectNanos') is not None,
                                'lost read response counted as completion')
        need(lost['node']==node and lost['pid']==fault['pid'] and lost['generation']==1,'crashed request process identity')
        first=[r for r in own if r['pid']==fault['pid']]
        cuts=[r for r in first if r['event']=='CUT_REACHED' and r['cut']==fault['cut'] and r['mode']==fault['mode']]
        need(len(cuts)==1 and first[-1]==cuts[0],'abrupt read cut not final observed event')
        invoked=next((r for r in first if r['event']=='CLIENT_INVOKE' and r['opId']==lost['opId']),None)
        need(invoked and invoked['order']<cuts[0]['order'],'crash before request invocation')
        read=[r for r in first if r['event']=='REPLICA_READ_INVOKED' and r['order']>invoked['order']]
        need(len(read)==1,'crash request lacks unique runtime read')
        captures=[r for r in first if r['event']=='REPLICA_READ_CAPTURE_VALIDATED' and r['readId']==read[0]['readId']]
        need(len(captures)==1,'crash lacks validated capture')
        need(not any(r['event'] in ('CLIENT_SUCCESS','CLIENT_FAILURE') and r['opId']==lost['opId'] for r in first),'crashed read response appeared')
        callbacks=[r for r in first if r['event']=='REPLICA_READ_CALLBACK' and r['opId']==lost['opId']]
        need(len(callbacks)==(0 if name.startswith('capture-') else 1),'wrong callback/crash ordering')
        need(fault['preReopen']==bundle.members(root/'pre-reopen'/node) and fault['preReopen'],'missing/changed pre-reopen authority files')
        from pathlib import Path
        before=e.physical.storage._inspect(root/'pre-reopen'/node,8<<30,8<<20,Path(e.read(root/'binding.json')['origin'])/node)
        restored=[r for r in own if r['generation']==2 and r['event']=='APPLICATION_RESTORED']
        need(len(restored)==1,'retained restart lacks restored publication')
        manifest=e.context(root,traces)[0];snapshot=e.recovery.snapshot(e.physical.raw(restored[0]['snapshot']),manifest)
        need(len(snapshot['anchors'])==before['provenThrough'] and all(a['entryDigest']==before['acceptedDigests'][i]
             for i,a in enumerate(snapshot['anchors'])),'restored publication differs from pre-reopen durable prefix')
        carried=fault['carried'];need(carried['opId'] in by_id and by_id[carried['opId']]['response']==carried,'unobserved carried token')
        minimum=token.decode(e.physical.raw(carried['token']))
        successor=response('successorOp');restarted=response('restartedOp')
        need(fault['successor']!=node and call('successorOp')['node']==fault['successor'],'no new leader carried-token read')
        need(call('restartedOp')['node']==node and call('restartedOp')['generation']==2 and
             call('restartedOp')['pid']!=fault['pid'],'no retained restart read')
        for key,value in (('successorOp',successor),('restartedOp',restarted)):
            need(call(key)['minimum']==carried['token'] and value['policy']=='AT_LEAST_INDEX' and
                 token.decode(e.physical.raw(value['token']))['index']>=minimum['index'],'carried bound lost on restart')
        need(successor['documents']==restarted['documents'],'restarted view differs from new majority')
        need(all(a['outcome']=='SUCCESS' or a['opId']==lost['opId'] for a in history),'undeclared unsuccessful crash call')
    elif name=='isolated-follower':
        selected=e.physical.frame(fault['selectedBeforeIsolation'],'SELECTED',e.context(root,traces)[0])
        need(node not in {b['node'] for b in selected['bases']} and
             any(r['event']=='PROMISE_QUORUM' and r['selected']==fault['selectedBeforeIsolation'] for r in traces[fault['originalLeader']]),
             'isolation did not preserve the observed selected quorum')
        before=response('beforeOp');stale=response('staleOp');later=response('laterOp');caught=response('caughtOp')
        need(before['documents']==stale['documents'] and before['token']==stale['token'],'isolated stale cut changed')
        need(token.decode(e.physical.raw(stale['token']))['index']<token.decode(e.physical.raw(later['token']))['index'],'isolated cut was not behind')
        need(caught['documents']==later['documents'] and call('caughtOp')['minimum']==later['token'],'healed carried read differs')
        need(any(r['event']=='NETWORK_DROP' for rows in traces.values() for r in rows),'partition not observed on real transport')
        rejected('deniedOp','PROGRESS_NOT_REACHED')
        need(call('deniedOp')['minimum']==later['token'] and call('deniedOp')['waitTimeoutMillis']==0,'isolation lower bound changed')
        need(all(a['outcome']=='SUCCESS' or a['opId']==fault['deniedOp'] for a in history),'undeclared unsuccessful isolation call')
    elif name=='unpublished-proof':
        cuts=[r for r in own if r['event']=='CUT_REACHED' and r['cut']=='BEFORE_LOCAL_PUBLISH']
        releases=[r for r in own if r['event']=='CUT_RELEASED' and r['cut']=='BEFORE_LOCAL_PUBLISH']
        need(len(cuts)==len(releases)==1 and cuts[0]['order']<releases[0]['order'],'missing publication hold/release')
        before=next(r for r in reversed(own[:own.index(cuts[0])]) if r['event']=='BEFORE_LOCAL_PUBLISH')
        manifest=e.context(root,traces)[0];snapshot=e.recovery.snapshot(e.physical.raw(before['snapshot']),manifest)
        need(len(snapshot['anchors'])==fault['pendingIndex'],'pending publication index changed')
        proof=e.digest(e.physical.raw(snapshot['terminalProof']))
        need(any(r['event']=='FORCE' and r['kind']=='PROOF' and e.digest(e.physical.raw(r['record']))==proof and r['order']<cuts[0]['order'] for r in own) or
             any(r['event']=='REJOIN_INSTALLED' and r['order']<cuts[0]['order'] and
                 e.digest(e.physical.raw(e.recovery.snapshot(e.physical.raw(r['snapshot']),manifest)['terminalProof']))==proof for r in own),
             'held publication lacks forced proof or verified install')
        need(fault['rejection'] in ('DEADLINE_EXCEEDED','NOT_READY'),'unknown held read outcome')
        rejected('deniedOp',fault['rejection'])
        if fault['rejection']=='NOT_READY':
            rejected('heldOp','NOT_READY')
            need(any(r['event']=='REJOIN_INSTALLED' and r['order']<cuts[0]['order'] and
                     len(e.recovery.snapshot(e.physical.raw(r['snapshot']),manifest)['anchors'])==fault['pendingIndex'] for r in own),
                 'NOT_READY lacks the observed pending snapshot install')
        need(not any(r['event']=='REPLICA_READ_CAPTURE_VALIDATED' and cuts[0]['order']<r['order']<releases[0]['order'] for r in own),'capture while application publication held')
        held=response('resumedOp');caught=response('caughtOp')
        need(held['documents']==caught['documents'] and token.decode(e.physical.raw(caught['token']))['index']>=fault['pendingIndex'],'released prefix read differs')
        need(all(a['outcome']=='SUCCESS' or a['opId'] in (fault['deniedOp'],fault['heldOp']) for a in history),'undeclared unsuccessful publication call')
    else:raise ValueError('unknown public read fault schedule')


def negatives(root,binding,queries):
    traces=e.traces_at(root);history=e.read(root/'history.json');processes=e.read(root/'processes.json');fault=e.read(root/'fault.json')
    e.validate(root,binding,queries) # an invalid original cannot count as a rejection
    result=e.negatives(root,binding,queries);name=binding['scenario']
    for mutation in ('missing-cut-witness','forged-outcome'):
        changed=copy.deepcopy(traces);calls=copy.deepcopy(history);details=copy.deepcopy(fault)
        if mutation=='missing-cut-witness':
            event='CUT_REACHED' if name.startswith(('capture-','release-')) else 'NETWORK_DROP' if name=='isolated-follower' else 'CUT_RELEASED'
            changed={node:[r for r in rows if r['event']!=event] for node,rows in changed.items()}
            expected='abrupt read cut' if event=='CUT_REACHED' else 'partition not observed' if event=='NETWORK_DROP' else 'publication hold/release'
        elif name.startswith(('capture-','release-')):
            next(a for a in calls if a['opId']==fault['lostOp'])['outcome']='SUCCESS';expected='lost read response'
        elif name=='isolated-follower':
            next(a for a in calls if a['opId']==fault['staleOp'])['response']['documents']=[];expected='isolated stale cut changed'
        else:
            details['rejection']='PROGRESS_NOT_REACHED';expected='unknown held read outcome'
        try:schedule(root,name,changed,calls,processes,fault=details)
        except ValueError as error:
            need(expected in str(error),'unrelated fault negative failure: '+str(error))
            result.append(dict(case=mutation,status='REJECTED',reason=str(error)))
        else:raise ValueError('invalid read fault evidence accepted: '+mutation)
    return result
