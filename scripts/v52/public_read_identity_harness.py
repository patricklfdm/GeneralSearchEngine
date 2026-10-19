"""Public token identity, malformed bytes and maximum lower-bound/wait admission."""
import argparse
import json
from pathlib import Path
import tempfile
from scripts.v51 import public_fault_harness as fault, public_trace, performance_bundle as bundle
from . import public_reads_harness as healthy, public_reads_evidence as evidence
from . import public_read_fault_harness as prior, public_read_identity_evidence as checker
from .evidence import need,digest

save=healthy.save


def scenario(root,name):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=False)
    workers={};history=[];processes=[];details=dict(scenario=name);receipt=dict(status='FAIL',scenario=name,paidCloud=False)
    try:
        (root/'promise-evidence').touch();(root/'lifecycle-evidence').touch()
        binding,cp=healthy.prepare(root,scenario=name);receipt['binding']=binding
        leader,active,carried=prior.baseline(root,cp,workers,history)
        node=next(n for n in workers if n!=leader);worker=workers[node];details.update(node=node,carriedOp=carried['opId'])
        def counts(owned):
            def sample():
                row=worker.call('probe');v=row['queues']
                return row if v['readsOwned']==v['readsWaiting']==v['readsAlarms']==owned and v['readsCaptured']==v['readsSettling']==0 and v['admissionAvailable']==16-owned else None
            return fault.wait_for(sample,'identity ownership did not settle',10)
        details['baselineProbe']=counts(0)['opId'];details['rejections']={}
        variants=checker.variants(carried['token'])
        for label,values in variants.items():
            result=worker.send('read',policy='AT_LEAST_INDEX',minimum=values['minimum'],waitTimeoutMillis=0).result(timeout=10)
            need(result and result.get('reasonCode')==values['reason'],'wrong token rejection: '+str(result))
            details['rejections'][label]=result['opId']
        details['rejectedProbe']=counts(0)['opId']
        pending=worker.send('read',policy='AT_LEAST_INDEX',minimum=variants['maximum-index']['minimum'],waitTimeoutMillis=60000)
        details['waitingOp']=history[-1]['opId'];details['waitingProbe']=counts(1)['opId']
        need(not pending.done(),'maximum lower bound unexpectedly completed')
        details['cancelOp']=worker.call('cancel',target=details['waitingOp'])['opId']
        result=pending.result(timeout=10);need(result and result['outcome']=='CANCELLED','maximum waiter cancellation')
        details['finalProbe']=counts(0)['opId']
        details['afterOp']=worker.call('read',policy='AT_LEAST_INDEX',minimum=carried['token'],waitTimeoutMillis=60000)['opId']
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        errors=[]
        for node,worker in workers.items():
            (root/(node+'-release')).touch()
            try:worker.stop()
            except Exception as error:errors.append(str(error))
            processes.append(dict(node=node,pid=worker.proc.pid,generation=worker.generation,exitCode=worker.proc.returncode))
        save(root/'history.json',history);save(root/'processes.json',processes);save(root/'read-identity.json',details)
        receipt['cleanupErrors']=errors;save(root.parent/(root.name+'-receipt.json'),receipt)
        need(not errors,'identity read cleanup: '+str(errors))
    try:
        queries=healthy.replay(root,evidence.traces_at(root),root/'control-replay');save(root/'oracle-results.json',queries)
        save(root/'bundle-members.json',bundle.members(root));receipt['validation']=evidence.validate(root,binding,queries)
        receipt['negatives']=checker.negatives(root,binding,queries)
        archive=root.parent/(root.name+'.tar.gz');bundle.pack(root,archive)
        relocated=root.parent/(root.name+'-relocated');bundle.unpack(archive,relocated)
        with tempfile.TemporaryDirectory(prefix='v52-identity-oracle-') as temp:
            portable=healthy.replay(relocated,evidence.traces_at(relocated),Path(temp)/'replay')
            need(portable==queries,'portable identity query control')
            need(evidence.validate(relocated,binding,portable)==receipt['validation'],'portable identity physical evidence')
            need(checker.negatives(relocated,binding,portable)==receipt['negatives'],'portable identity rejection results')
        receipt.update(status='PASS',bundleSha256=digest(archive.read_bytes()))
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:save(root.parent/(root.name+'-receipt.json'),receipt)
    return receipt


def run(output,only=None):
    need(only is None or only in checker.CASES,'unknown identity read case');root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='FAIL',scope='targeted' if only else 'public-read-identity',paidCloud=False,cases=[]);common=None
    try:
        for name in checker.CASES:
            if only and only!=name:continue
            try:
                result=scenario(root/name,name)
                bound={k:result['binding'][k] for k in ('source','checkoutSha256','java','artifacts','classes','run','attempt','codec','seed')}
                if common is None:common=bound
                need(bound==common,'identity source/build/attempt changed between cases')
                item=dict(case=name,status='PASS',validation=result['validation'],negativeCases=len(result['negatives']))
            except Exception as error:item=dict(case=name,status='FAIL',failure=str(error))
            receipt['cases'].append(item);print(json.dumps(item),flush=True)
        need(all(c['status']=='PASS' for c in receipt['cases']),'public identity read cases failed')
        receipt.update(status='PASS',binding=common)
    finally:save(root/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--only',choices=checker.CASES);a=p.parse_args();run(a.output,a.only)
