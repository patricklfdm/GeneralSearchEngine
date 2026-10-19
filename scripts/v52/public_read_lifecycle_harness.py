"""Original public futures, cooperative callback lifetime and actual process deaths."""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
from scripts.v51 import public_qualification_harness as q, public_fault_harness as fault, public_trace
from scripts.v51 import performance_bundle as bundle
from . import public_reads_harness as healthy, public_reads_evidence as evidence, token
from . import public_read_fault_harness as prior, public_read_lifecycle_evidence as checker
from .evidence import need, digest

save=healthy.save


def scenario(root,name):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=False)
    workers={};history=[];processes=[];details=dict(scenario=name)
    receipt=dict(status='FAIL',scenario=name,paidCloud=False)
    def stopped(w):processes.append(dict(node=w.node,pid=w.proc.pid,generation=w.generation,exitCode=w.proc.returncode))
    try:
        (root/'promise-evidence').touch();(root/'lifecycle-evidence').touch()
        binding,cp=healthy.prepare(root,scenario=name);receipt['binding']=binding
        leader,active,carried=prior.baseline(root,cp,workers,history)
        node='node-3';worker=workers[node];details.update(node=node,carried=carried)
        def probe():return worker.call('probe')
        def counts(owned,captured=0,settling=0):
            def sample():
                row=probe();values=row['queues']
                return row if all(values['reads'+k]==v for k,v in [('Owned',owned),('Captured',captured),('Settling',settling)]) else None
            return fault.wait_for(sample,'read resource counts did not settle',10)
        def arm(cut,mode='pause'):
            (root/(node+'-release')).unlink(missing_ok=True);fault.replace(root/(node+'-arm.txt'),cut+'\n'+mode+'\n')
        def reached(cut):
            return fault.wait_for(lambda:next((r for r in reversed(public_trace.live_rows(root,node))
                                  if r['event']=='CUT_REACHED' and r['cut']==cut),None),'read lifecycle cut unavailable: '+cut)
        def release():(root/(node+'-release')).touch()
        def read(**values):
            future=worker.send('read',**values);return future,history[-1]['opId']
        details['baselineProbe']=counts(0)['opId']
        kind=name.removeprefix('lifecycle-');crash=kind.endswith(('-halt','-kill'))
        base=kind.rsplit('-',1)[0] if crash else kind
        pause=None;held=None
        if base=='cancel-queued':
            pause='REPLICA_READ_CALLBACK';arm(pause);held,held_id=read(policy='STALE_ALLOWED');reached(pause);details['heldOp']=held_id
        elif base in ('cancel-captured','close-captured'):
            pause='REPLICA_READ_CALLBACK';arm(pause)
        elif base=='cancel-before-capture':pause='REPLICA_READ_BEFORE_DISPATCH';arm(pause)
        elif base=='cancel-completion':pause='REPLICA_READ_COMPLETION_RETURN';arm(pause)
        options=dict(policy='STALE_ALLOWED')
        if base.endswith('waiting'):
            lower=dict(token.decode(evidence.physical.raw(carried['token'])),index=(1<<63)-1)
            options=dict(policy='AT_LEAST_INDEX',minimum=base64.b64encode(token.encode(lower)).decode(),waitTimeoutMillis=60000)
        target,target_id=read(**options);details['targetOp']=target_id
        if pause and base!='cancel-queued':reached(pause)
        before=counts(2 if held else 1,1 if base in ('cancel-queued','cancel-captured','close-captured') else 0,
                      1 if base=='cancel-completion' else 0)
        details['beforeProbe']=before['opId']
        if base.startswith('cancel-'):
            response=worker.call('cancel',target=target_id);details['actionOp']=response['opId']
            need(response['cancelled']==(base!='cancel-completion'),'wrong original future cancellation result')
            original=target.result(timeout=10)
            need(original and original['outcome']==('SUCCESS' if base=='cancel-completion' else 'CANCELLED'),'wrong cancelled read outcome')
            retained=base in ('cancel-captured','cancel-completion')
            after=counts(1 if retained or held else 0,1 if base=='cancel-captured' or held else 0,1 if base=='cancel-completion' else 0)
            details['duringProbe']=after['opId']
        else:
            closing=worker.send('begin-close');details['actionOp']=history[-1]['opId'];closed=closing.result(timeout=15)
            need(closed and closed.get('reasonCode')=='DEADLINE_EXCEEDED' if base=='close-captured' else closed and closed['outcome']=='SUCCESS',
                 'wrong cooperative close result: '+str(closed))
            if base=='close-waiting':
                need(target.result(timeout=10).get('reasonCode')=='CLOSED','close revived waiting read')
            details['duringProbe']=counts(1 if base=='close-captured' else 0,1 if base=='close-captured' else 0)['opId']
        if crash:
            mode=kind.rsplit('-',1)[1];cut='REPLICA_READ_RELEASED'
            # Arm the subsequent release, leaving the existing callback pause held.
            fault.replace(root/(node+'-arm.txt'),cut+'\n'+mode+'\n');release();reached(cut)
            if mode=='kill':worker.proc.kill()
            need(worker.proc.wait(timeout=10)==(-9 if mode=='kill' else 71),'wrong lifecycle abrupt exit')
            worker.stop(kill=True);stopped(worker);del workers[node]
            details.update(pid=worker.proc.pid,mode=mode,cut=cut)
            if base=='close-captured':need(target.result(timeout=5) is None,'interrupted close callback returned')
            before=root/'pre-reopen'/node;shutil.copytree(root/node,before);details['preReopen']=bundle.members(before)
            worker=q.Worker(root,node,cp,history,generation=2,consumer='replica-read');workers[node]=worker
            prior.published(worker,token.decode(evidence.physical.raw(carried['token']))['index'])
            details['restartedOp']=worker.call('read',policy='AT_LEAST_INDEX',minimum=carried['token'],waitTimeoutMillis=5000)['opId']
            details['finalProbe']=counts(0)['opId']
        else:
            if pause:release()
            if held:need(held.result(timeout=15)['outcome']=='SUCCESS','held predecessor failed')
            if base=='close-captured':
                need(target.result(timeout=15)['outcome']=='SUCCESS','live callback failed after incomplete close')
                details['secondCloseOp']=worker.call('begin-close')['opId']
            details['finalProbe']=counts(0)['opId']
            if not base.startswith('close-'):
                details['afterOp']=worker.call('read',policy='STALE_ALLOWED')['opId'];counts(0)
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        errors=[]
        for node,worker in workers.items():
            (root/(node+'-release')).touch()
            try:worker.stop()
            except Exception as error:errors.append(str(error))
            stopped(worker)
        save(root/'history.json',history);save(root/'processes.json',processes);save(root/'lifecycle.json',details)
        receipt['cleanupErrors']=errors;save(root.parent/(root.name+'-receipt.json'),receipt)
        need(not errors,'lifecycle process cleanup: '+str(errors))
    try:
        queries=healthy.replay(root,evidence.traces_at(root),root/'control-replay');save(root/'oracle-results.json',queries)
        save(root/'bundle-members.json',bundle.members(root));receipt['validation']=evidence.validate(root,binding,queries)
        receipt['negatives']=checker.negatives(root,binding,queries)
        archive=root.parent/(root.name+'.tar.gz');bundle.pack(root,archive)
        relocated=root.parent/(root.name+'-relocated');bundle.unpack(archive,relocated)
        with tempfile.TemporaryDirectory(prefix='v52-lifecycle-oracle-') as temp:
            portable=healthy.replay(relocated,evidence.traces_at(relocated),Path(temp)/'replay')
            need(portable==queries,'portable lifecycle query control')
            need(evidence.validate(relocated,binding,portable)==receipt['validation'],'portable lifecycle physical evidence')
            need(checker.negatives(relocated,binding,portable)==receipt['negatives'],'portable lifecycle rejection results')
        receipt.update(status='PASS',bundleSha256=digest(archive.read_bytes()))
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:save(root.parent/(root.name+'-receipt.json'),receipt)
    return receipt


def run(output,only=None):
    need(only is None or only in checker.CASES,'unknown lifecycle case');root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='FAIL',scope='targeted' if only else 'public-read-cancel-close',paidCloud=False,cases=[]);common=None
    try:
        for name in checker.CASES:
            if only and name!=only:continue
            try:
                result=scenario(root/name,name)
                bound={k:result['binding'][k] for k in ('source','checkoutSha256','java','artifacts','classes','run','attempt','codec','seed')}
                if common is None:common=bound
                need(bound==common,'lifecycle source/build/attempt changed between cases')
                item=dict(case=name,status='PASS',validation=result['validation'],negativeCases=len(result['negatives']))
            except Exception as error:item=dict(case=name,status='FAIL',failure=str(error))
            receipt['cases'].append(item);print(json.dumps(item),flush=True)
        need(all(c['status']=='PASS' for c in receipt['cases']),'public read lifecycle cases failed')
        receipt.update(status='PASS',binding=common)
    finally:save(root/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--only',choices=checker.CASES);a=p.parse_args();run(a.output,a.only)
