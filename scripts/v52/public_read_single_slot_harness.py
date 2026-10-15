"""P=1 rejects all explicit policies without consuming the old public API slot."""
import argparse
import json
from pathlib import Path
import tempfile
from scripts.v51 import public_fault_harness as fault, public_trace, performance_bundle as bundle,public_qualification_harness as q
from . import public_reads_harness as healthy, public_reads_evidence as evidence
from . import public_read_fault_harness as prior, public_read_single_slot_evidence as checker
from .evidence import need,digest

save=healthy.save


def scenario(root,name):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=False)
    workers={};history=[];processes=[];details=dict(scenario=name);receipt=dict(status='FAIL',scenario=name,paidCloud=False)
    try:
        (root/'promise-evidence').touch();(root/'reclamation-evidence').touch();(root/'lifecycle-evidence').touch()
        (root/'read-capacity.txt').write_text('1\n')
        binding,cp=healthy.prepare(root,scenario=name);receipt['binding']=binding
        for node in ('node-1','node-2','node-3'):workers[node]=q.Worker(root,node,cp,history,consumer='replica-read')
        leader,active=fault.leader(workers);details['node']=leader
        def available():
            def probe():
                row=active.call('probe');counts=row['queues']
                return row if counts['admissionAvailable']==1 and all(counts['reads'+k]==0 for k in ('Owned','Waiting','Captured','Settling','Alarms','Marker','HighWater')) else None
            return fault.wait_for(probe,'single-slot legacy permit did not return',10)
        for key in (20,30,40):
            available();active.call('addAll',documents=[dict(id=i,value=f'java search query {i}') for i in (key,key+1)])
        details['legacyOps']=[]
        for _ in range(2):
            available();details['legacyOps'].append(active.call('legacy-get',key=1)['opId'])
        index=active.call('status')['publishedIndex'];details['baselineIndex']=index
        for node in workers:
            fault.wait_for(lambda:next((r for r in reversed(public_trace.live_rows(root,node)) if r['event']=='RECOVERY_FLOOR' and r['index']==index),None),
                           'single-slot baseline floor unavailable',80)
        details['baselineProbe']=available()['opId'];details['rejections']=[]
        manifest=evidence.context(root,{n:public_trace.live_rows(root,n) for n in workers})[0]
        import base64
        minimum=base64.b64encode(evidence.token.encode(dict(version=1,groupId=manifest['groupId'],historyId=manifest['historyId'],manifestDigest=manifest['digest'],index=index))).decode()
        for policy in ('LEADER_STRONG','STALE_ALLOWED','AT_LEAST_INDEX'):
            options=dict(policy=policy)
            if policy=='AT_LEAST_INDEX':options.update(minimum=minimum,waitTimeoutMillis=60000)
            result=active.send('read',**options).result(timeout=10)
            need(result and result.get('reasonCode')=='CAPACITY_EXCEEDED','single-slot explicit read accepted or wrong reason: '+str(result))
            details['rejections'].append(result['opId'])
        details['rejectedProbe']=available()['opId']
        details['writerOp']=active.call('addAll',documents=[dict(id=80,value='old API java'),dict(id=81,value='old API search')])['opId']
        available();details['legacyOps'].append(active.call('legacy-get',key=1)['opId'])
        details['finalProbe']=available()['opId']
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        errors=[];fault.partition(root)
        for node,worker in workers.items():
            (root/(node+'-release')).touch()
            try:worker.stop()
            except Exception as error:errors.append(str(error))
            processes.append(dict(node=node,pid=worker.proc.pid,generation=worker.generation,exitCode=worker.proc.returncode))
        save(root/'history.json',history);save(root/'processes.json',processes);save(root/'read-single-slot.json',details)
        receipt['cleanupErrors']=errors;save(root.parent/(root.name+'-receipt.json'),receipt)
        need(not errors,'single_slot read cleanup: '+str(errors))
    try:
        queries=healthy.replay(root,evidence.traces_at(root),root/'control-replay');save(root/'oracle-results.json',queries)
        save(root/'bundle-members.json',bundle.members(root));receipt['validation']=evidence.validate(root,binding,queries)
        receipt['negatives']=checker.negatives(root,binding,queries)
        archive=root.parent/(root.name+'.tar.gz');bundle.pack(root,archive)
        relocated=root.parent/(root.name+'-relocated');bundle.unpack(archive,relocated)
        with tempfile.TemporaryDirectory(prefix='v52-single_slot-oracle-') as temp:
            portable=healthy.replay(relocated,evidence.traces_at(relocated),Path(temp)/'replay')
            need(portable==queries,'portable single_slot query control')
            need(evidence.validate(relocated,binding,portable)==receipt['validation'],'portable single_slot physical evidence')
            need(checker.negatives(relocated,binding,portable)==receipt['negatives'],'portable single_slot rejection results')
        receipt.update(status='PASS',bundleSha256=digest(archive.read_bytes()))
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:save(root.parent/(root.name+'-receipt.json'),receipt)
    return receipt


def run(output,only=None):
    need(only is None or only in checker.CASES,'unknown single_slot read case');root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='FAIL',scope='targeted' if only else 'public-read-single-slot',paidCloud=False,cases=[]);common=None
    try:
        for name in checker.CASES:
            if only and only!=name:continue
            try:
                result=scenario(root/name,name)
                bound={k:result['binding'][k] for k in ('source','checkoutSha256','java','artifacts','classes','run','attempt','codec','seed')}
                if common is None:common=bound
                need(bound==common,'single_slot source/build/attempt changed between cases')
                item=dict(case=name,status='PASS',validation=result['validation'],negativeCases=len(result['negatives']))
            except Exception as error:item=dict(case=name,status='FAIL',failure=str(error))
            receipt['cases'].append(item);print(json.dumps(item),flush=True)
        need(all(c['status']=='PASS' for c in receipt['cases']),'public single_slot read cases failed')
        receipt.update(status='PASS',binding=common)
    finally:save(root/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--only',choices=checker.CASES);a=p.parse_args();run(a.output,a.only)
