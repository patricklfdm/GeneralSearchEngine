"""Three indivisible public histories combine faults and retained read ownership."""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
from scripts.v51 import public_qualification_harness as q, public_fault_harness as fault, public_trace
from scripts.v51 import performance_bundle as bundle
from . import public_reads_harness as healthy, public_reads_evidence as e, token
from . import public_read_fault_harness as prior, public_read_hardening_evidence as checker
from .evidence import need,digest

save=healthy.save


def scenario(root,name):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=False)
    plan=checker.plan();case=next(c for c in plan['cases'] if c['name']==name)
    workers={};history=[];processes=[];details=dict(scenario=name,rounds=[])
    receipt=dict(status='FAIL',scenario=name,paidCloud=False)
    def rows(node):return public_trace.live_rows(root,node)
    def stopped(w):processes.append(dict(node=w.node,pid=w.proc.pid,generation=w.generation,exitCode=w.proc.returncode))
    def release(node):(root/(node+'-release')).touch()
    def arm(node,cut,mode='pause',clear=True):
        if clear:(root/(node+'-release')).unlink(missing_ok=True)
        fault.replace(root/(node+'-arm.txt'),cut+'\n'+mode+'\n')
    def reached(node,cut,after=0):
        return fault.wait_for(lambda:next((r for r in reversed(rows(node)) if r['event']=='CUT_REACHED' and r['cut']==cut and r['order']>after),None),
                              'hardening cut unavailable: '+cut,plan['recoveryObservationSeconds'])
    def probe(worker,owned,captured,available):
        def sample():
            row=worker.call('probe');v=row['queues']
            return row if all(v[k]==n for k,n in dict(readsOwned=owned,readsCaptured=captured,readsWaiting=owned-captured,
                readsSettling=0,readsAlarms=owned-captured,admissionAvailable=available).items()) else None
        return fault.wait_for(sample,'hardening ownership did not settle',plan['probeObservationSeconds'])['opId']
    def floors(index):
        result={}
        for node in workers:
            result[node]=fault.wait_for(lambda:next((r for r in reversed(rows(node)) if r['event']=='RECOVERY_FLOOR' and r['index']==index),None),
                'hardening recovery floor unavailable',plan['recoveryObservationSeconds'])
        return result
    def send(worker,kind,**values):
        future=worker.send(kind,**values);return future,history[-1]['opId']
    def cancel(worker,future,op):
        result=worker.call('cancel',target=op);need(result['cancelled'],'original hardening Future not cancelled')
        response=future.result(timeout=10);need(response and response['outcome']=='CANCELLED','cancelled hardening outcome changed')
        return result['opId']
    def minimum(carried):
        return base64.b64encode(token.encode(dict(token.decode(e.physical.raw(carried['token'])),index=(1<<63)-1))).decode()
    try:
        for marker in ('promise-evidence','lifecycle-evidence','reclamation-evidence'):(root/marker).touch()
        (root/'operation-timeout.txt').write_text(str(plan['operationTimeoutMillis'])+'\n')
        if case['pendingLimit']!=16:(root/'read-capacity.txt').write_text(str(case['pendingLimit'])+'\n')
        shutil.copyfile(checker.PLAN,root/'hardening-plan.json')
        binding,cp=healthy.prepare(root,scenario=name);binding['hardeningPlanSha256']=checker.PLAN_SHA;save(root/'binding.json',binding);receipt['binding']=binding
        old,active,carried=prior.baseline(root,cp,workers,history);details.update(node=old,carriedOp=carried['opId'])
        details['baselineFloors']=floors(token.decode(e.physical.raw(carried['token']))['index'])
        if name.startswith('partition-'):
            details['baselineProbe']=probe(active,0,0,16);epoch=active.call('status')['epoch'];details['oldEpoch']=epoch
            arm(old,'REPLICA_READ_REPORT_FIRST');held,details['targetOp']=send(active,'read',policy='STALE_ALLOWED',repeat=True)
            reached(old,'REPLICA_READ_REPORT_FIRST')
            queued,details['queuedOp']=send(active,'read',policy='AT_LEAST_INDEX',minimum=minimum(carried),waitTimeoutMillis=60000)
            details['fullProbe']=probe(active,2,1,14);details['cancelOp']=cancel(active,queued,details['queuedOp'])
            details['heldProbe']=probe(active,1,1,15)
            fault.partition(root,old);successor,service=fault.leader({n:w for n,w in workers.items() if n!=old})
            details['writerOp']=service.call('addAll',documents=[dict(id=80,value='combined successor search'),dict(id=81,value='combined successor java')])['opId']
            later=service.call('read',policy='LEADER_STRONG');details.update(successor=successor,laterOp=later['opId'])
            index=token.decode(e.physical.raw(later['token']))['index']
            details['laterFloor']=fault.wait_for(lambda:next((r for r in reversed(rows(successor)) if r['event']=='RECOVERY_FLOOR' and r['index']==index),None),
                'combined successor floor unavailable',plan['recoveryObservationSeconds'])
            fault.partition(root)
            fault.wait_for(lambda:any(r['event']=='FORCE' and r['kind']=='PROMISE' and
                (p:=e.physical.f.inspect(e.physical.raw(r['record']),'PROMISE'))['epoch']>epoch and p['proposer']==successor for r in rows(old)),
                'held callback lacks successor promise',plan['recoveryObservationSeconds'])
            fault.partition(root,old);mode=name.rsplit('-',1)[1]
            arm(old,'REPLICA_READ_RELEASED',mode,clear=False);release(old);reached(old,'REPLICA_READ_RELEASED')
            if mode=='kill':active.proc.kill()
            need(active.proc.wait(timeout=10)==case['exitCode'],'hardening crash exit')
            active.stop(kill=True);stopped(active);del workers[old]
            need(held.result(timeout=5) is None,'crashed callback unexpectedly responded')
            before=root/'pre-reopen'/old;shutil.copytree(root/old,before);details.update(preReopen=bundle.members(before),pid=active.proc.pid,mode=mode)
            fault.partition(root);workers[old]=q.Worker(root,old,cp,history,generation=2,consumer='replica-read')
            def recovered():
                state=workers[old].call('status');need(state['state']!='FAILED','hardening restored voter failed')
                return state['state'] in ('FOLLOWER','LEADER_READY','UNAVAILABLE') and state['publishedIndex']>=index
            fault.wait_for(recovered,'hardening restart publication unavailable',plan['recoveryObservationSeconds'])
            details['recoveredOp']=workers[old].call('read',policy='AT_LEAST_INDEX',minimum=carried['token'],waitTimeoutMillis=5000)['opId']
            details['finalProbe']=probe(workers[old],0,0,16)
        else:
            previous=carried
            for cycle in range(case['cycles']):
                record=dict(cycle=cycle,carriedOp=previous['opId'],floors=floors(token.decode(e.physical.raw(previous['token']))['index']))
                details['rounds'].append(record);record['baselineProbe']=probe(active,0,0,4)
                last=rows(old)[-1]['order'];arm(old,'REPLICA_READ_REPORT_FIRST')
                held,record['targetOp']=send(active,'read',policy='STALE_ALLOWED',repeat=True);reached(old,'REPLICA_READ_REPORT_FIRST',last)
                waiting,record['waitingOp']=send(active,'read',policy='AT_LEAST_INDEX',minimum=minimum(previous),waitTimeoutMillis=case['behindWaitMillis'])
                queued,record['queuedOp']=send(active,'read',policy='STALE_ALLOWED');record['fullProbe']=probe(active,3,1,1)
                excess,record['excessOp']=send(active,'read',policy='STALE_ALLOWED');result=excess.result(timeout=10)
                need(result and result.get('reasonCode')=='CAPACITY_EXCEEDED','hardening excess read not rejected: '+str(result))
                first=case['firstDocumentId']+case['documentsPerCycle']*cycle
                record['added']=[dict(id=i,value=f'hardening java search {i}') for i in range(first,first+case['documentsPerCycle'])]
                writer,record['writerOp']=send(active,'addAll',documents=record['added']);record['writerProbe']=probe(active,3,1,0)
                record['cancelQueuedOp']=cancel(active,queued,record['queuedOp']);record['queuedProbe']=probe(active,2,1,1)
                expiry,record['expiryOp']=send(active,'read',policy='AT_LEAST_INDEX',minimum=minimum(previous),waitTimeoutMillis=case['expiryWaitMillis'])
                expired=expiry.result(timeout=10);need(expired and expired.get('reasonCode')=='DEADLINE_EXCEEDED','hardening deadline changed: '+str(expired))
                record['expiryProbe']=probe(active,2,1,1)
                record['cancelWaitingOp']=cancel(active,waiting,record['waitingOp']);record['waitingProbe']=probe(active,1,1,2)
                record['cancelCapturedOp']=cancel(active,held,record['targetOp']);record['capturedProbe']=probe(active,1,1,2)
                need(not writer.done(),'write bypassed held application view');release(old)
                result=writer.result(timeout=35);need(result and result['outcome']=='SUCCESS','hardening original writer failed: '+str(result))
                previous=active.call('read',policy='STALE_ALLOWED');record['laterOp']=previous['opId'];record['finalProbe']=probe(active,0,0,4)
            details['finalFloors']=floors(token.decode(e.physical.raw(previous['token']))['index'])
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        errors=[];fault.partition(root)
        for node,worker in workers.items():
            release(node)
            try:worker.stop()
            except Exception as error:errors.append(str(error))
            stopped(worker)
        save(root/'history.json',history);save(root/'processes.json',processes);save(root/'read-hardening.json',details)
        receipt['cleanupErrors']=errors;save(root.parent/(root.name+'-receipt.json'),receipt);need(not errors,'hardening cleanup: '+str(errors))
    try:
        queries=healthy.replay(root,e.traces_at(root),root/'control-replay');save(root/'oracle-results.json',queries)
        save(root/'bundle-members.json',bundle.members(root));receipt['validation']=e.validate(root,binding,queries);receipt['negatives']=checker.negatives(root,binding,queries)
        archive=root.parent/(root.name+'.tar.gz');bundle.pack(root,archive);relocated=root.parent/(root.name+'-relocated');bundle.unpack(archive,relocated)
        with tempfile.TemporaryDirectory(prefix='v52-hardening-oracle-') as temp:
            portable=healthy.replay(relocated,e.traces_at(relocated),Path(temp)/'replay')
            need(portable==queries,'portable hardening query control')
            need(e.validate(relocated,binding,portable)==receipt['validation'],'portable hardening physical validation')
            need(checker.negatives(relocated,binding,portable)==receipt['negatives'],'portable hardening negative results')
        receipt.update(status='PASS',bundleSha256=digest(archive.read_bytes()))
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:save(root.parent/(root.name+'-receipt.json'),receipt)
    return receipt


def run(output,only=None):
    need(only is None or only in checker.CASES,'unknown hardening case');root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='FAIL',scope='targeted' if only else 'public-read-combined-hardening',paidCloud=False,cases=[]);common=None
    try:
        for name in checker.CASES:
            if only and only!=name:continue
            try:
                result=scenario(root/name,name)
                bound={k:result['binding'][k] for k in ('source','checkoutSha256','java','artifacts','classes','run','attempt','codec','seed','hardeningPlanSha256')}
                if common is None:common=bound
                need(bound==common,'hardening source/build/attempt changed between cases')
                item=dict(case=name,status='PASS',validation=result['validation'],negativeCases=len(result['negatives']))
            except Exception as error:item=dict(case=name,status='FAIL',failure=str(error))
            receipt['cases'].append(item);print(json.dumps(item),flush=True)
        need(all(c['status']=='PASS' for c in receipt['cases']),'public read hardening cases failed');receipt.update(status='PASS',binding=common)
    finally:save(root/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--only',choices=checker.CASES);a=p.parse_args();run(a.output,a.only)
