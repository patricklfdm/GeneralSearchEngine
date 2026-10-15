"""Public explicit-read fencing and snapshot-install boundaries on actual TCP voters."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import time
from scripts.v51 import public_qualification_harness as q, public_fault_harness as fault, public_trace
from scripts.v51 import performance_bundle as bundle
from . import public_reads_harness as healthy, public_reads_evidence as evidence, token
from . import public_read_fault_harness as prior, public_read_protocol_evidence as checker
from .evidence import need, digest

save=healthy.save


def scenario(root,name):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=False)
    workers={};history=[];processes=[];details=dict(scenario=name);receipt=dict(status='FAIL',scenario=name,paidCloud=False)
    def stopped(worker):processes.append(dict(node=worker.node,pid=worker.proc.pid,generation=worker.generation,exitCode=worker.proc.returncode))
    def rows(node):return public_trace.live_rows(root,node)
    def arm(node,cut,mode='pause'):fault.replace(root/(node+'-arm.txt'),cut+'\n'+mode+'\n')
    def reached(node,cut):return fault.wait_for(lambda:next((r for r in reversed(rows(node)) if r['event']=='CUT_REACHED' and r['cut']==cut),None),'protocol read cut unavailable: '+cut,80)
    def release(node):(root/(node+'-release')).touch()
    def published(worker,index):
        # This fixture freezes a 60-second operation/transfer lease. A rejected
        # install may occupy its original transfer until expiry; 40 seconds is
        # therefore not a valid recovery observation budget. Polling is bounded
        # independently of the public read's unchanged 5-second minimum wait.
        started=time.monotonic();until=started+80
        while time.monotonic()<until:
            state=worker.call('status');need(state['state']!='FAILED','failed protocol-read follower')
            if state['state'] in ('FOLLOWER','LEADER_READY','UNAVAILABLE') and state['publishedIndex']>=index:
                details['recoveryWaitSeconds']=time.monotonic()-started;return
            time.sleep(.2)
        raise ValueError('read protocol recovery did not publish within lease plus margin: '+json.dumps(state))
    def crash(node,cut,mode):
        worker=workers[node];reached(node,cut)
        if mode=='kill':worker.proc.kill()
        need(worker.proc.wait(timeout=10)==(-9 if mode=='kill' else 71),'wrong protocol read exit')
        worker.stop(kill=True);stopped(worker);del workers[node]
        before=root/'pre-reopen'/node;shutil.copytree(root/node,before)
        details.update(node=node,pid=worker.proc.pid,cut=cut,mode=mode,preReopen=bundle.members(before))
    try:
        (root/'promise-evidence').touch()
        # Explicitly frozen fault-fixture deadline, as in the existing V5.1 fencing
        # schedule. The pause tests promise ordering rather than a deadline race.
        (root/'operation-timeout.txt').write_text('60000\n')
        binding,cp=healthy.prepare(root,scenario=name);receipt['binding']=binding
        abrupt=name.endswith(('-halt','-kill'));mode=name.rsplit('-',1)[1] if abrupt else None
        if name.startswith('promise-'):
            old,active,carried=prior.baseline(root,cp,workers,history);details.update(node=old,carried=carried)
            epoch=active.call('status')['epoch'];before=name=='promise-before'
            cut='REPLICA_READ_BEFORE_DISPATCH' if before else 'REPLICA_READ_CAPTURED'
            arm(old,cut);pending=active.send('read',policy='LEADER_STRONG');details['targetOp']=history[-1]['opId'];reached(old,cut)
            fault.partition(root,old)
            successor,service=fault.leader({n:w for n,w in workers.items() if n!=old})
            service.call('addAll',documents=[dict(id=80,value='successor search'),dict(id=81,value='successor java')])
            later=service.call('read',policy='LEADER_STRONG');details.update(successor=successor,laterOp=later['opId'],oldEpoch=epoch,pause=cut)
            fault.partition(root)
            fault.wait_for(lambda:any(r['event']=='FORCE' and r['kind']=='PROMISE' and
                           (p:=evidence.physical.f.inspect(evidence.physical.raw(r['record']),'PROMISE'))['epoch']>epoch and p['proposer']==successor
                           for r in rows(old)),'paused reader did not force successor promise')
            # Keep later state reconstruction behind the held callback/dispatch,
            # then let the already captured call finish against its original view.
            fault.partition(root,old)
            if abrupt:arm(old,'REPLICA_READ_RELEASED',mode)
            release(old)
            if abrupt:
                crash(old,'REPLICA_READ_RELEASED',mode);need(pending.result(timeout=5) is None,'interrupted captured read responded')
            else:
                result=pending.result(timeout=15)
                need(result and (result.get('reasonCode')=='STALE_EPOCH' if before else result['outcome']=='SUCCESS'),'wrong public fencing outcome: '+str(result))
            fault.partition(root)
            if abrupt:workers[old]=q.Worker(root,old,cp,history,generation=2,consumer='replica-read')
            published(workers[old],token.decode(evidence.physical.raw(later['token']))['index'])
            details['recoveredOp']=workers[old].call('read',policy='AT_LEAST_INDEX',minimum=carried['token'],waitTimeoutMillis=5000)['opId']
        else:
            leader,active,carried=prior.baseline(root,cp,workers,history)
            selected=next(r['selected'] for r in reversed(rows(leader)) if r['event']=='PROMISE_QUORUM')
            decision=evidence.physical.frame(selected,'SELECTED',evidence.context(root,{n:rows(n) for n in workers})[0])
            node=next(n for n in workers if n not in {b['node'] for b in decision['bases']});worker=workers[node]
            fault.partition(root,node)
            active.call('addAll',documents=[dict(id=80,value='installed search'),dict(id=81,value='installed java')])
            later=active.call('read',policy='LEADER_STRONG');index=token.decode(evidence.physical.raw(later['token']))['index']
            details.update(selectedBeforeIsolation=selected,originalLeader=leader,laterOp=later['opId'])
            fault.wait_for(lambda:any(r['event']=='RECOVERY_FLOOR' and r['index']>=index for r in rows(leader)),'snapshot source floor unavailable',80)
            arm(node,'BEFORE_LOCAL_PUBLISH');fault.partition(root);reached(node,'BEFORE_LOCAL_PUBLISH')
            need(any(r['event']=='REJOIN_INSTALLED' and len(evidence.recovery.snapshot(evidence.physical.raw(r['snapshot']),
                 evidence.context(root,{n:rows(n) for n in workers})[0])['anchors'])>=index for r in rows(node)),
                 'held publication is not the new verified snapshot install')
            denied=worker.send('read',policy='STALE_ALLOWED').result(timeout=10)
            need(denied and denied.get('reasonCode')=='NOT_READY','install served an unready local read')
            details.update(node=node,carried=carried,deniedOp=denied['opId'],pause='BEFORE_LOCAL_PUBLISH')
            if abrupt:arm(node,'REPLICA_READ_COMPLETION_ENTER',mode)
            pending=worker.send('read',policy='AT_LEAST_INDEX',minimum=carried['token'],waitTimeoutMillis=5000);details['targetOp']=history[-1]['opId']
            if abrupt:
                crash(node,'REPLICA_READ_COMPLETION_ENTER',mode);need(pending.result(timeout=5) is None,'interrupted install rejection responded')
                workers[node]=worker=q.Worker(root,node,cp,history,generation=2,consumer='replica-read')
            else:
                denied=pending.result(timeout=10);need(denied and denied.get('reasonCode')=='NOT_READY','install served a minimum read');release(node)
            published(worker,index)
            details['recoveredOp']=worker.call('read',policy='AT_LEAST_INDEX',minimum=carried['token'],waitTimeoutMillis=5000)['opId']
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        errors=[];fault.partition(root)
        for node,worker in workers.items():
            release(node)
            try:worker.stop()
            except Exception as error:errors.append(str(error))
            stopped(worker)
        save(root/'history.json',history);save(root/'processes.json',processes);save(root/'read-protocol.json',details)
        receipt['cleanupErrors']=errors;save(root.parent/(root.name+'-receipt.json'),receipt)
        need(not errors,'read protocol cleanup: '+str(errors))
    try:
        queries=healthy.replay(root,evidence.traces_at(root),root/'control-replay');save(root/'oracle-results.json',queries)
        save(root/'bundle-members.json',bundle.members(root));receipt['validation']=evidence.validate(root,binding,queries)
        receipt['negatives']=checker.negatives(root,binding,queries)
        archive=root.parent/(root.name+'.tar.gz');bundle.pack(root,archive)
        relocated=root.parent/(root.name+'-relocated');bundle.unpack(archive,relocated)
        with tempfile.TemporaryDirectory(prefix='v52-protocol-oracle-') as temp:
            portable=healthy.replay(relocated,evidence.traces_at(relocated),Path(temp)/'replay')
            need(portable==queries,'portable read protocol query control')
            need(evidence.validate(relocated,binding,portable)==receipt['validation'],'portable read protocol physical evidence')
            need(checker.negatives(relocated,binding,portable)==receipt['negatives'],'portable read protocol rejection results')
        receipt.update(status='PASS',bundleSha256=digest(archive.read_bytes()))
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:save(root.parent/(root.name+'-receipt.json'),receipt)
    return receipt


def run(output,only=None):
    need(only is None or only in checker.CASES,'unknown read protocol case');root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='FAIL',scope='targeted' if only else 'public-read-promise-install',paidCloud=False,cases=[]);common=None
    try:
        for name in checker.CASES:
            if only and name!=only:continue
            try:
                result=scenario(root/name,name)
                bound={k:result['binding'][k] for k in ('source','checkoutSha256','java','artifacts','classes','run','attempt','codec','seed')}
                if common is None:common=bound
                need(bound==common,'read protocol source/build/attempt changed between cases')
                item=dict(case=name,status='PASS',validation=result['validation'],negativeCases=len(result['negatives']))
            except Exception as error:item=dict(case=name,status='FAIL',failure=str(error))
            receipt['cases'].append(item);print(json.dumps(item),flush=True)
        need(all(c['status']=='PASS' for c in receipt['cases']),'public read protocol cases failed')
        receipt.update(status='PASS',binding=common)
    finally:save(root/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--only',choices=checker.CASES);a=p.parse_args();run(a.output,a.only)
