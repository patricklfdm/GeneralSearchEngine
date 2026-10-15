"""Fresh, owned public read histories with real isolation, publication pauses and process death."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import time
from scripts.v51 import public_qualification_harness as q, public_fault_harness as faults, public_trace
from scripts.v51 import performance_bundle as bundle
from . import public_reads_harness as healthy, public_reads_evidence as evidence, public_read_fault_evidence, token
from .evidence import need, digest, encoded

CASES=('capture-halt','capture-kill','release-halt','release-kill','isolated-follower','unpublished-proof')
save=healthy.save


def published(worker,index):
    def ready():
        status=worker.call('status')
        need(status['state']!='FAILED','failed public follower')
        return status['state'] in ('FOLLOWER','LEADER_READY','UNAVAILABLE') and status['publishedIndex']>=index
    faults.wait_for(ready,'public follower publication unavailable',40)


def baseline(root,cp,workers,history):
    workers['node-1']=q.Worker(root,'node-1',cp,history,consumer='replica-read')
    workers['node-1'].call('read',policy='STALE_ALLOWED')
    for node in ('node-2','node-3'):workers[node]=q.Worker(root,node,cp,history,consumer='replica-read')
    leader,active=faults.leader(workers)
    for key in (20,30,40):active.call('addAll',documents=[dict(id=i,value=f'java search query {i}') for i in (key,key+1)])
    carried=active.call('read',policy='LEADER_STRONG');index=token.decode(evidence.physical.raw(carried['token']))['index']
    for node,worker in workers.items():
        if node==leader:continue
        published(worker,index);worker.call('read',policy='STALE_ALLOWED')
        worker.call('read',policy='AT_LEAST_INDEX',minimum=carried['token'],waitTimeoutMillis=5000)
    return leader,active,carried


def scenario(root,name):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='FAIL',scenario=name,paidCloud=False);workers={};history=[];processes=[];fault=dict(scenario=name)
    def stopped(worker):processes.append(dict(node=worker.node,pid=worker.proc.pid,generation=worker.generation,exitCode=worker.proc.returncode))
    try:
        # Prevent the deliberately isolated third follower's own campaign from masking a local-read schedule.
        (root/'promise-evidence').touch()
        binding,cp=healthy.prepare(root,scenario=name);receipt['binding']=binding
        leader,active,carried=baseline(root,cp,workers,history);fault.update(carried=carried,originalLeader=leader)
        if name.startswith(('capture-','release-')):
            cut='REPLICA_READ_CAPTURED' if name.startswith('capture-') else 'REPLICA_READ_RELEASED';mode=name.split('-')[1]
            faults.replace(root/(leader+'-arm.txt'),cut+'\n'+mode+'\n')
            held=active.send('read',policy='LEADER_STRONG');lost=history[-1]['opId']
            faults.wait_for(lambda:any(r['event']=='CUT_REACHED' and r['cut']==cut for r in public_trace.live_rows(root,leader)), 'read crash cut unavailable')
            if mode=='kill':active.proc.kill()
            need(active.proc.wait(timeout=10)==(-9 if mode=='kill' else 71),'wrong abrupt exit')
            active.stop(kill=True);stopped(active);del workers[leader]
            need(held.result(timeout=5) is None,'lost response unexpectedly delivered')
            before=root/'pre-reopen'/leader;shutil.copytree(root/leader,before)
            fault.update(node=leader,pid=active.proc.pid,cut=cut,mode=mode,lostOp=lost,preReopen=bundle.members(before))
            successor,service=faults.leader(workers)
            service.call('addAll',documents=[dict(id=80,value='new majority search'),dict(id=81,value='new majority java')])
            observed=service.call('read',policy='AT_LEAST_INDEX',minimum=carried['token'],waitTimeoutMillis=5000)
            fresh=service.call('read',policy='LEADER_STRONG')
            workers[leader]=q.Worker(root,leader,cp,history,generation=2,consumer='replica-read')
            published(workers[leader],token.decode(evidence.physical.raw(fresh['token']))['index'])
            restarted=workers[leader].call('read',policy='AT_LEAST_INDEX',minimum=carried['token'],waitTimeoutMillis=5000)
            fault.update(successor=successor,successorOp=observed['opId'],restartedOp=restarted['opId'])
        elif name=='isolated-follower':
            # Keep the actual selected quorum intact. Isolating its peer would test
            # failover/indeterminate mutation instead of a healthy-majority stale read.
            selected=next(r['selected'] for r in reversed(public_trace.live_rows(root,leader)) if r['event']=='PROMISE_QUORUM')
            decision=evidence.physical.frame(selected,'SELECTED',evidence.context(root,{n:public_trace.live_rows(root,n) for n in workers})[0])
            node=next(n for n in workers if n not in {b['node'] for b in decision['bases']})
            fault['selectedBeforeIsolation']=selected
            worker=workers[node];before=worker.call('read',policy='STALE_ALLOWED')
            faults.partition(root,node)
            active.call('addAll',documents=[dict(id=80,value='majority later search'),dict(id=81,value='majority later java')])
            later=active.call('read',policy='LEADER_STRONG')
            stale=worker.call('read',policy='STALE_ALLOWED')
            denied=worker.send('read',policy='AT_LEAST_INDEX',minimum=later['token'],waitTimeoutMillis=0).result(timeout=10)
            need(denied and denied.get('reasonCode')=='PROGRESS_NOT_REACHED','isolated future bound did not reject')
            fault.update(node=node,beforeOp=before['opId'],laterOp=later['opId'],staleOp=stale['opId'],deniedOp=denied['opId'])
            faults.partition(root);published(worker,token.decode(evidence.physical.raw(later['token']))['index'])
            caught=worker.call('read',policy='AT_LEAST_INDEX',minimum=later['token'],waitTimeoutMillis=5000);fault['caughtOp']=caught['opId']
        else:
            node=next(n for n in workers if n not in (leader,'node-3'));worker=workers[node];cut='BEFORE_LOCAL_PUBLISH'
            faults.replace(root/(node+'-arm.txt'),cut+'\npause\n')
            active.call('addAll',documents=[dict(id=80,value='publication held search'),dict(id=81,value='publication held java')])
            faults.wait_for(lambda:any(r['event']=='CUT_REACHED' and r['cut']==cut for r in public_trace.live_rows(root,node)), 'local publication pause unavailable')
            pending=next(r for r in reversed(public_trace.live_rows(root,node)) if r['event']==cut)
            manifest=evidence.context(root,{n:public_trace.live_rows(root,n) for n in workers})[0]
            snapshot=evidence.recovery.snapshot(evidence.physical.raw(pending['snapshot']),manifest)
            lower=dict(token.decode(evidence.physical.raw(carried['token'])),index=len(snapshot['anchors']))
            import base64
            minimum=base64.b64encode(token.encode(lower)).decode()
            waiting=worker.send('read',policy='AT_LEAST_INDEX',minimum=minimum,waitTimeoutMillis=100)
            wait_id=history[-1]['opId'];held=worker.send('read',policy='STALE_ALLOWED');held_id=history[-1]['opId']
            denied=waiting.result(timeout=10)
            need(denied and denied.get('reasonCode') in ('DEADLINE_EXCEEDED','NOT_READY'),'unpublished prefix became readable: '+str(denied))
            if denied['reasonCode']=='DEADLINE_EXCEEDED':need(not held.done(),'stale read passed held application worker')
            else:need(held.result(timeout=10).get('reasonCode')=='NOT_READY','install state allowed stale capture')
            (root/(node+'-release')).touch()
            if denied['reasonCode']=='DEADLINE_EXCEEDED':
                resumed=held.result(timeout=15);need(resumed and resumed['outcome']=='SUCCESS','released publication read failed')
            published(worker,lower['index'])
            if denied['reasonCode']=='NOT_READY':resumed=worker.call('read',policy='STALE_ALLOWED')
            caught=worker.call('read',policy='AT_LEAST_INDEX',minimum=minimum,waitTimeoutMillis=5000)
            fault.update(node=node,cut=cut,pendingIndex=lower['index'],deniedOp=wait_id,heldOp=held_id,resumedOp=resumed['opId'],caughtOp=caught['opId'],rejection=denied['reasonCode'])
    except BaseException as error:
        receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        errors=[]
        for node,worker in workers.items():
            (root/(node+'-release')).touch()
            try:worker.stop()
            except Exception as error:errors.append(str(error))
            stopped(worker)
        save(root/'history.json',history);save(root/'processes.json',processes);save(root/'fault.json',fault)
        receipt['cleanupErrors']=errors;save(root.parent/(root.name+'-receipt.json'),receipt)
        need(not errors,'read fault cleanup: '+str(errors))
    try:
        traces=evidence.traces_at(root);queries=healthy.replay(root,traces,root/'control-replay');save(root/'oracle-results.json',queries)
        save(root/'bundle-members.json',bundle.members(root));receipt['validation']=evidence.validate(root,binding,queries)
        receipt['negatives']=public_read_fault_evidence.negatives(root,binding,queries)
        archive=root.parent/(root.name+'.tar.gz');bundle.pack(root,archive)
        relocated=root.parent/(root.name+'-relocated');bundle.unpack(archive,relocated)
        with tempfile.TemporaryDirectory(prefix='v52-fault-oracle-') as temp:
            portable=healthy.replay(relocated,evidence.traces_at(relocated),Path(temp)/'replay')
            need(portable==queries,'relocated fault query replay')
            need(evidence.validate(relocated,binding,portable)==receipt['validation'],'relocated fault physical validation')
            need(public_read_fault_evidence.negatives(relocated,binding,portable)==receipt['negatives'],'relocated fault negatives')
        receipt.update(status='PASS',bundleSha256=digest(archive.read_bytes()),queryCuts=len(queries))
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:save(root.parent/(root.name+'-receipt.json'),receipt)
    return receipt


def run(output,only=None):
    need(only is None or only in CASES,'unknown read fault case');root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='FAIL',scope='targeted' if only else 'six-case-public-read-faults',paidCloud=False,cases=[]);common=None
    try:
        for name in CASES:
            if only and name!=only:continue
            try:
                result=scenario(root/name,name)
                bound={k:result['binding'][k] for k in ('source','checkoutSha256','java','artifacts','classes','run','attempt','codec','seed')}
                if common is None:common=bound
                need(bound==common,'read fault matrix source/build/attempt changed between cases')
                item=dict(case=name,status='PASS',validation=result['validation'],negativeCases=len(result['negatives']))
            except Exception as error:item=dict(case=name,status='FAIL',failure=str(error))
            receipt['cases'].append(item);print(json.dumps(item),flush=True)
        need(all(c['status']=='PASS' for c in receipt['cases']),'public read fault cases failed')
        receipt.update(status='PASS',binding=common)
    finally:save(root/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--only',choices=CASES);a=p.parse_args();run(a.output,a.only)
