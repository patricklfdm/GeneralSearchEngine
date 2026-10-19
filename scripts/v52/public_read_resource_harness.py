"""Public queue saturation and reserved writer progress at three configured bounds."""
import argparse
import json
from pathlib import Path
import tempfile
from scripts.v51 import public_fault_harness as fault, public_trace, performance_bundle as bundle
from . import public_reads_harness as healthy, public_reads_evidence as evidence
from . import public_read_fault_harness as prior, public_read_resource_evidence as checker
from .evidence import need,digest

save=healthy.save


def scenario(root,name):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=False)
    workers={};history=[];processes=[];details=dict(scenario=name);receipt=dict(status='FAIL',scenario=name,paidCloud=False)
    try:
        (root/'promise-evidence').touch();(root/'lifecycle-evidence').touch();(root/'reclamation-evidence').touch()
        (root/'read-capacity.txt').write_text(str(checker.CAPACITIES[name])+'\n')
        binding,cp=healthy.prepare(root,scenario=name);receipt['binding']=binding
        leader,active,carried=prior.baseline(root,cp,workers,history)
        # A published cut can still overlap installation of a replacement source.
        # Finish initialization before testing healthy reserved-writer capacity.
        carried_index=evidence.token.decode(evidence.physical.raw(carried['token']))['index']
        details['baselineFloors']={}
        for node in workers:
            details['baselineFloors'][node]=fault.wait_for(lambda:next((r for r in reversed(public_trace.live_rows(root,node))
                    if r['event']=='RECOVERY_FLOOR' and r['index']==carried_index),None),'resource baseline floor unavailable',80)
        pending_limit=checker.CAPACITIES[name];limit=min(64,pending_limit-1)
        details.update(node=leader,carriedOp=carried['opId'])
        def counts(owned):
            def sample():
                row=active.call('probe');v=row['queues']
                return row if v['readsOwned']==v['readsWaiting']==v['readsAlarms']==owned and v['readsCaptured']==v['readsSettling']==0 and v['admissionAvailable']==pending_limit-owned else None
            return fault.wait_for(sample,'resource ownership did not settle',10)
        details['baselineProbe']=counts(0)['opId']
        import base64
        lower=evidence.token.decode(evidence.physical.raw(carried['token']));lower['index']+=1
        minimum=base64.b64encode(evidence.token.encode(lower)).decode()
        pending=[];details['waitingOps']=[]
        for _ in range(limit):
            pending.append(active.send('read',policy='AT_LEAST_INDEX',minimum=minimum,waitTimeoutMillis=60000))
            details['waitingOps'].append(history[-1]['opId'])
        details['fullProbe']=counts(limit)['opId'];need(not any(f.done() for f in pending),'behind waiter unexpectedly completed')
        excess=active.send('read',policy='AT_LEAST_INDEX',minimum=minimum,waitTimeoutMillis=60000).result(timeout=10)
        need(excess and excess.get('reasonCode')=='CAPACITY_EXCEEDED','excess public read was not rejected: '+str(excess))
        details['excessOp']=excess['opId'];details['rejectedProbe']=counts(limit)['opId']
        details['added']=[dict(id=80,value='reserved writer java'),dict(id=81,value='reserved writer search')]
        details['writerOp']=active.call('addAll',documents=details['added'])['opId']
        for future in pending:
            result=future.result(timeout=35);need(result and result['outcome']=='SUCCESS','waiting public read failed: '+str(result))
        details['finalProbe']=counts(0)['opId']
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        errors=[]
        for node,worker in workers.items():
            (root/(node+'-release')).touch()
            try:worker.stop()
            except Exception as error:errors.append(str(error))
            processes.append(dict(node=node,pid=worker.proc.pid,generation=worker.generation,exitCode=worker.proc.returncode))
        save(root/'history.json',history);save(root/'processes.json',processes);save(root/'read-resources.json',details)
        receipt['cleanupErrors']=errors;save(root.parent/(root.name+'-receipt.json'),receipt)
        need(not errors,'resource read cleanup: '+str(errors))
    try:
        queries=healthy.replay(root,evidence.traces_at(root),root/'control-replay');save(root/'oracle-results.json',queries)
        save(root/'bundle-members.json',bundle.members(root));receipt['validation']=evidence.validate(root,binding,queries)
        receipt['negatives']=checker.negatives(root,binding,queries)
        archive=root.parent/(root.name+'.tar.gz');bundle.pack(root,archive)
        relocated=root.parent/(root.name+'-relocated');bundle.unpack(archive,relocated)
        with tempfile.TemporaryDirectory(prefix='v52-resource-oracle-') as temp:
            portable=healthy.replay(relocated,evidence.traces_at(relocated),Path(temp)/'replay')
            need(portable==queries,'portable resource query control')
            need(evidence.validate(relocated,binding,portable)==receipt['validation'],'portable resource physical evidence')
            need(checker.negatives(relocated,binding,portable)==receipt['negatives'],'portable resource rejection results')
        receipt.update(status='PASS',bundleSha256=digest(archive.read_bytes()))
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:save(root.parent/(root.name+'-receipt.json'),receipt)
    return receipt


def run(output,only=None):
    need(only is None or only in checker.CASES,'unknown resource read case');root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='FAIL',scope='targeted' if only else 'public-read-resource',paidCloud=False,cases=[]);common=None
    try:
        for name in checker.CASES:
            if only and only!=name:continue
            try:
                result=scenario(root/name,name)
                bound={k:result['binding'][k] for k in ('source','checkoutSha256','java','artifacts','classes','run','attempt','codec','seed')}
                if common is None:common=bound
                need(bound==common,'resource source/build/attempt changed between cases')
                item=dict(case=name,status='PASS',validation=result['validation'],negativeCases=len(result['negatives']))
            except Exception as error:item=dict(case=name,status='FAIL',failure=str(error))
            receipt['cases'].append(item);print(json.dumps(item),flush=True)
        need(all(c['status']=='PASS' for c in receipt['cases']),'public resource read cases failed')
        receipt.update(status='PASS',binding=common)
    finally:save(root/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--only',choices=checker.CASES);a=p.parse_args();run(a.output,a.only)
