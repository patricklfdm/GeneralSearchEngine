"""Carried minimum token after two-source retirement and real follower snapshot catch-up."""
import argparse
import json
from pathlib import Path
import tempfile
from scripts.v51 import public_fault_harness as fault, public_trace, performance_bundle as bundle
from . import public_reads_harness as healthy, public_reads_evidence as evidence
from . import public_read_fault_harness as prior, public_read_compaction_evidence as checker
from .evidence import need,digest

save=healthy.save


def scenario(root,name):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=False)
    workers={};history=[];processes=[];details=dict(scenario=name);receipt=dict(status='FAIL',scenario=name,paidCloud=False)
    def floor(node,index):
        return fault.wait_for(lambda:next((r for r in reversed(public_trace.live_rows(root,node)) if r['event']=='RECOVERY_FLOOR' and r['index']>=index),None),
                              'read token recovery floor unavailable',80)
    try:
        (root/'promise-evidence').touch();(root/'reclamation-evidence').touch()
        binding,cp=healthy.prepare(root,scenario=name);receipt['binding']=binding
        leader,active,carried=prior.baseline(root,cp,workers,history)
        lower=evidence.token.decode(evidence.physical.raw(carried['token']))['index']
        details.update(carriedOp=carried['opId'],leader=leader,baselineFloor=floor(leader,lower))
        selected=next(r['selected'] for r in reversed(public_trace.live_rows(root,leader)) if r['event']=='PROMISE_QUORUM')
        manifest=evidence.context(root,{n:public_trace.live_rows(root,n) for n in workers})[0]
        pair=evidence.physical.frame(selected,'SELECTED',manifest)
        follower=next(n for n in workers if n not in {v['node'] for v in pair['bases']})
        details.update(follower=follower,selectedBeforeIsolation=selected)
        fault.partition(root,follower)
        added=[dict(id=80,value='after compaction java'),dict(id=81,value='after compaction search')]
        active.call('addAll',documents=added);details['documents']=carried['documents']+added
        floor(leader,lower+1)
        details['leaderRead']=active.call('read',policy='AT_LEAST_INDEX',minimum=carried['token'],waitTimeoutMillis=5000)['opId']
        fault.partition(root);floor(follower,lower+1)
        prior.published(workers[follower],lower+1)
        details['followerRead']=workers[follower].call('read',policy='AT_LEAST_INDEX',minimum=carried['token'],waitTimeoutMillis=5000)['opId']
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        errors=[];fault.partition(root)
        for node,worker in workers.items():
            (root/(node+'-release')).touch()
            try:worker.stop()
            except Exception as error:errors.append(str(error))
            processes.append(dict(node=node,pid=worker.proc.pid,generation=worker.generation,exitCode=worker.proc.returncode))
        save(root/'history.json',history);save(root/'processes.json',processes);save(root/'read-compaction.json',details)
        receipt['cleanupErrors']=errors;save(root.parent/(root.name+'-receipt.json'),receipt)
        need(not errors,'compaction read cleanup: '+str(errors))
    try:
        queries=healthy.replay(root,evidence.traces_at(root),root/'control-replay');save(root/'oracle-results.json',queries)
        save(root/'bundle-members.json',bundle.members(root));receipt['validation']=evidence.validate(root,binding,queries)
        receipt['negatives']=checker.negatives(root,binding,queries)
        archive=root.parent/(root.name+'.tar.gz');bundle.pack(root,archive)
        relocated=root.parent/(root.name+'-relocated');bundle.unpack(archive,relocated)
        with tempfile.TemporaryDirectory(prefix='v52-compaction-oracle-') as temp:
            portable=healthy.replay(relocated,evidence.traces_at(relocated),Path(temp)/'replay')
            need(portable==queries,'portable compaction query control')
            need(evidence.validate(relocated,binding,portable)==receipt['validation'],'portable compaction physical evidence')
            need(checker.negatives(relocated,binding,portable)==receipt['negatives'],'portable compaction rejection results')
        receipt.update(status='PASS',bundleSha256=digest(archive.read_bytes()))
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:save(root.parent/(root.name+'-receipt.json'),receipt)
    return receipt


def run(output,only=None):
    need(only is None or only in checker.CASES,'unknown compaction read case');root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='FAIL',scope='targeted' if only else 'public-read-compaction',paidCloud=False,cases=[]);common=None
    try:
        for name in checker.CASES:
            if only and only!=name:continue
            try:
                result=scenario(root/name,name)
                bound={k:result['binding'][k] for k in ('source','checkoutSha256','java','artifacts','classes','run','attempt','codec','seed')}
                if common is None:common=bound
                need(bound==common,'compaction source/build/attempt changed between cases')
                item=dict(case=name,status='PASS',validation=result['validation'],negativeCases=len(result['negatives']))
            except Exception as error:item=dict(case=name,status='FAIL',failure=str(error))
            receipt['cases'].append(item);print(json.dumps(item),flush=True)
        need(all(c['status']=='PASS' for c in receipt['cases']),'public compaction read cases failed')
        receipt.update(status='PASS',binding=common)
    finally:save(root/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--only',choices=checker.CASES);a=p.parse_args();run(a.output,a.only)
