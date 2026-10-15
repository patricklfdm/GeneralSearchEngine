"""One fresh public history supplies the complete targeted physical-negative matrix."""
import argparse
import json
from pathlib import Path
import tempfile
from scripts.v51 import public_fault_harness as fault, public_trace, performance_bundle as bundle
from . import public_reads_harness as healthy, public_reads_evidence as evidence, token
from . import public_read_fault_harness as prior, public_read_negative_evidence as checker
from .evidence import need,digest

save=healthy.save


def run(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False);root=output/'raw';root.mkdir()
    workers={};history=[];processes=[];details=dict(scenario='negative-qualification')
    receipt=dict(status='FAIL',execution='public-read-targeted-negatives',paidCloud=False)
    try:
        (root/'promise-evidence').touch();(root/'lifecycle-evidence').touch()
        binding,cp=healthy.prepare(root,scenario='negative-qualification');receipt['binding']=binding
        leader,active,carried=prior.baseline(root,cp,workers,history)
        worker=workers['node-3'];node=worker.node
        ahead=dict(token.decode(evidence.physical.raw(carried['token'])),index=(1<<63)-1)
        expired=worker.send('read',policy='AT_LEAST_INDEX',minimum=checker.b64(token.encode(ahead)),waitTimeoutMillis=100).result(timeout=10)
        need(expired and expired.get('reasonCode')=='DEADLINE_EXCEEDED','targeted deadline did not expire: '+str(expired));details['deadlineOp']=expired['opId']
        fault.replace(root/(node+'-arm.txt'),'REPLICA_READ_BEFORE_DISPATCH\npause\n')
        cancelled=worker.send('read',policy='STALE_ALLOWED');details['cancelledOp']=history[-1]['opId']
        fault.wait_for(lambda:any(r['event']=='CUT_REACHED' and r['cut']=='REPLICA_READ_BEFORE_DISPATCH' for r in public_trace.live_rows(root,node)),
                       'targeted pre-capture pause unavailable')
        result=worker.call('cancel',target=details['cancelledOp']);need(result['cancelled'],'targeted original future not cancelled');details['cancelOp']=result['opId']
        need(cancelled.result(timeout=10)['outcome']=='CANCELLED','targeted cancelled response changed')
        (root/(node+'-release')).touch()
        worker.call('read',policy='AT_LEAST_INDEX',minimum=carried['token'],waitTimeoutMillis=5000)
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        errors=[]
        for node,worker in workers.items():
            (root/(node+'-release')).touch()
            try:worker.stop()
            except Exception as error:errors.append(str(error))
            processes.append(dict(node=node,pid=worker.proc.pid,generation=worker.generation,exitCode=worker.proc.returncode))
        save(root/'history.json',history);save(root/'processes.json',processes);save(root/'read-negatives.json',details)
        receipt['cleanupErrors']=errors;save(output/'receipt.json',receipt);need(not errors,'negative process cleanup: '+str(errors))
    try:
        queries=healthy.replay(root,evidence.traces_at(root),root/'control-replay');save(root/'oracle-results.json',queries)
        save(root/'bundle-members.json',bundle.members(root));receipt['validation']=evidence.validate(root,binding,queries)
        receipt['negatives']=checker.negatives(root,binding,queries)
        archive=output/'bundle.tar.gz';bundle.pack(root,archive);relocated=output/'relocated';bundle.unpack(archive,relocated)
        with tempfile.TemporaryDirectory(prefix='v52-negative-oracle-') as temp:
            portable=healthy.replay(relocated,evidence.traces_at(relocated),Path(temp)/'replay')
            need(portable==queries,'portable negative query control')
            need(evidence.validate(relocated,binding,portable)==receipt['validation'],'portable negative original validation')
            need(checker.negatives(relocated,binding,portable)==receipt['negatives'],'portable targeted negative results')
        receipt.update(status='PASS',bundleSha256=digest(archive.read_bytes()))
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:save(output/'receipt.json',receipt)
    print(json.dumps(dict(status='PASS',negatives=len(receipt['negatives']),families=16,paidCloud=False)),flush=True)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args();run(a.output)
