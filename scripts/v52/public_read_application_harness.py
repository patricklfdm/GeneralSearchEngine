"""Whole public histories for paused seven-query views overlapping application mutations."""
import argparse
import json
from pathlib import Path
import tempfile
from scripts.v51 import public_fault_harness as fault, public_trace, performance_bundle as bundle
from . import public_reads_harness as healthy, public_reads_evidence as evidence
from . import public_read_fault_harness as prior, public_read_application_evidence as checker
from .evidence import need,digest

save=healthy.save


def scenario(root,name):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=False)
    workers={};history=[];processes=[];details=dict(scenario=name);receipt=dict(status='FAIL',scenario=name,paidCloud=False)
    try:
        (root/'promise-evidence').touch()
        binding,cp=healthy.prepare(root,scenario=name);receipt['binding']=binding
        leader,active,carried=prior.baseline(root,cp,workers,history);details['carriedOp']=carried['opId']
        cut='REPLICA_READ_REPORT_FIRST';fault.replace(root/(leader+'-arm.txt'),cut+'\npause\n')
        options=dict(policy=checker.POLICIES[name],repeat=True)
        if name=='application-minimum':options.update(minimum=carried['token'],waitTimeoutMillis=5000)
        pending=active.send('read',**options);details['targetOp']=history[-1]['opId']
        fault.wait_for(lambda:any(r['event']=='CUT_REACHED' and r['cut']==cut for r in public_trace.live_rows(root,leader)),
                       'application callback did not pause')
        wave=[('update',dict(documents=[dict(id=1,value='updated java search')])),
              ('updateAll',dict(documents=[dict(id=3,value='bulk updated memory search'),dict(id=5,value='bulk updated java query')])),
              ('remove',dict(keys=[7])),('removeAll',dict(keys=[20,21])),
              ('createIndex',dict(index=dict(field='id',kind='equality',analyzer=''))),
              ('dropIndex',dict(field='id')),('add',dict(documents=[dict(id=90,value='added java search')]))]
        futures=[];details['mutations']=[]
        for kind,values in wave:
            futures.append(active.send(kind,**values));details['mutations'].append(history[-1]['opId'])
        fault.wait_for(lambda:all(any(r['event']=='CLIENT_INVOKE' and r.get('opId')==op for r in public_trace.live_rows(root,leader))
                                 for op in details['mutations']),'application wave not submitted during callback')
        need(not any(f.done() for f in futures),'mutation completed while callback owns application worker')
        (root/(leader+'-release')).touch()
        result=pending.result(timeout=20);need(result and result['outcome']=='SUCCESS','paused application read failed: '+str(result))
        for future in futures:
            result=future.result(timeout=20);need(result and result['outcome']=='SUCCESS','application wave failed: '+str(result))
        details['laterOp']=active.call('read',policy='LEADER_STRONG')['opId']
        details['minimumOp']=active.call('read',policy='AT_LEAST_INDEX',minimum=carried['token'],waitTimeoutMillis=5000)['opId']
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        errors=[]
        for node,worker in workers.items():
            (root/(node+'-release')).touch()
            try:worker.stop()
            except Exception as error:errors.append(str(error))
            processes.append(dict(node=node,pid=worker.proc.pid,generation=worker.generation,exitCode=worker.proc.returncode))
        save(root/'history.json',history);save(root/'processes.json',processes);save(root/'read-application.json',details)
        receipt['cleanupErrors']=errors;save(root.parent/(root.name+'-receipt.json'),receipt)
        need(not errors,'application read cleanup: '+str(errors))
    try:
        queries=healthy.replay(root,evidence.traces_at(root),root/'control-replay');save(root/'oracle-results.json',queries)
        save(root/'bundle-members.json',bundle.members(root));receipt['validation']=evidence.validate(root,binding,queries)
        receipt['negatives']=checker.negatives(root,binding,queries)
        archive=root.parent/(root.name+'.tar.gz');bundle.pack(root,archive)
        relocated=root.parent/(root.name+'-relocated');bundle.unpack(archive,relocated)
        with tempfile.TemporaryDirectory(prefix='v52-application-oracle-') as temp:
            portable=healthy.replay(relocated,evidence.traces_at(relocated),Path(temp)/'replay')
            need(portable==queries,'portable application query control')
            need(evidence.validate(relocated,binding,portable)==receipt['validation'],'portable application physical evidence')
            need(checker.negatives(relocated,binding,portable)==receipt['negatives'],'portable application rejection results')
        receipt.update(status='PASS',bundleSha256=digest(archive.read_bytes()))
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:save(root.parent/(root.name+'-receipt.json'),receipt)
    return receipt


def run(output,only=None):
    need(only is None or only in checker.CASES,'unknown application read case');root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='FAIL',scope='targeted' if only else 'public-read-application',paidCloud=False,cases=[]);common=None
    try:
        for name in checker.CASES:
            if only and only!=name:continue
            try:
                result=scenario(root/name,name)
                bound={k:result['binding'][k] for k in ('source','checkoutSha256','java','artifacts','classes','run','attempt','codec','seed')}
                if common is None:common=bound
                need(bound==common,'application source/build/attempt changed between cases')
                item=dict(case=name,status='PASS',validation=result['validation'],negativeCases=len(result['negatives']))
            except Exception as error:item=dict(case=name,status='FAIL',failure=str(error))
            receipt['cases'].append(item);print(json.dumps(item),flush=True)
        need(all(c['status']=='PASS' for c in receipt['cases']),'public application read cases failed')
        receipt.update(status='PASS',binding=common)
    finally:save(root/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--only',choices=checker.CASES);a=p.parse_args();run(a.output,a.only)
