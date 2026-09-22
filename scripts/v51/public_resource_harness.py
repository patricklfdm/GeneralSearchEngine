"""Public minority resource exhaustion; no authority initialization or repair."""
import argparse
import time
from . import public_qualification_harness as q, public_qualification_evidence as physical
from . import public_fault_harness as fault, public_protocol_harness as protocol
from . import public_promise_harness as matrix, public_recovery_harness as recovery
from . import public_history, storage_inspector as storage
from .storage_harness import need,save

CASES=('snapshot-staging','retained-bytes')


def scenario(root,cp,case):
    root.mkdir();workers={};history=[];expected=[];receipt=dict(case=case,status='FAIL',publicRuntime=True)
    (root/'promise-evidence').touch();(root/'resource-evidence').touch();(root/'chunk-bytes.txt').write_text('4096\n')
    (root/'bounds-profile.txt').write_text('resource-'+('staging' if case=='snapshot-staging' else 'retained')+'\n')
    def start(node,generation=1):workers[node]=q.Worker(root,node,cp,history,generation);return workers[node]
    def write(active,tag,size):
        docs=[dict(id=tag+i,value=f'tag-{tag+i}-'+'x'*size) for i in (0,1)]
        active.call('addAll',documents=docs);expected.extend(docs);return history[-1]['opId']
    def capacity_reply():
        for row in fault.rows(root,'node-3'):
            if row['event']=='RESOURCE_REJECTED':return row
    try:
        q.command(['java','-cp',cp,q.PACKAGE+'admission.PublicRuntimeConsumer',root,'setup'],root,'public-bootstrap')
        protocol.network(root,[f'{n} node-3 BEFORE_REQUEST_WRITE PREPARE' for n in ('node-1','node-2')])
        for node in protocol.NODES:start(node)
        leader,active=fault.leader(workers);receipt['leader']=leader;need(leader!='node-3','bounded voter led')
        protocol.network(root,[])
        for tag in (10,20,30):write(active,tag,64)
        protocol.read_after_recovery(workers,expected)
        index=active.call('status')['provenIndex']
        fault.wait_for(lambda: workers['node-3'].call('status')['provenIndex']>=index,'bounded voter never caught up before load')
        receipt['seedIndex']=index;receipt['seedInventory']=storage.inventory(root/'node-3')
        receipt['loadWrite']=write(active,40,6000)
        receipt['rejection']=fault.wait_for(capacity_reply,'no real capacity rejection from bounded voter')
        receipt['observedNanos']=time.monotonic_ns()
        receipt['rejectedCalls']=[]
        for kind,args in [('addAll',dict(documents=[dict(id=90,value='must-not-appear')])),('read',{})]:
            denied=workers['node-3'].send(kind,**args).result(timeout=35)
            need(denied is not None and denied['outcome']==('NOT_SUBMITTED' if kind=='addAll' else 'NOT_APPLICABLE'),'exhausted voter served a client')
            receipt['rejectedCalls'].append(history[-1]['opId'])
        receipt['postRejectionWrite']=write(active,50,64)
        protocol.read_after_recovery({n:w for n,w in workers.items() if n!='node-3'},expected);receipt['postRejectionRead']=history[-1]['opId']
        workers.pop('node-3').stop();receipt['retained']=recovery.archive(root,'node-3')
        receipt['restartNanos']=time.monotonic_ns();start('node-3',2)
        # The sealed budget is unchanged. Restart may fail closed again; healthy
        # quorum service must not require deleting authority or enlarging limits.
        protocol.read_after_recovery({n:w for n,w in workers.items() if n!='node-3'},expected);receipt['afterRestartRead']=history[-1]['opId']
        workers.pop(leader).stop();start(leader,2)
        protocol.read_after_recovery({n:w for n,w in workers.items() if n!='node-3'},expected);receipt['afterLeaderRestartRead']=history[-1]['opId']
        receipt['expected']=expected
    except BaseException as error:receipt['failure']=str(error);raise
    finally:
        errors=[]
        for worker in workers.values():
            try:worker.stop()
            except Exception as error:errors.append(str(error))
        save(root/'history.json',history);save(root/'receipt.json',receipt)
        need(not errors,'resource cleanup: '+str(errors))
    try:
        from . import resource_evidence
        receipt['history']=public_history.check(history);receipt['physical']=physical.physical(root,history)
        receipt['resources']=resource_evidence.public(root,physical.traces_at(root),history,receipt)
        receipt['negatives']=physical.negatives(root,history)+resource_evidence.public_negatives(root,history,receipt)
        receipt['status']='PASS'
    except BaseException as error:receipt['failure']=str(error);raise
    finally:save(root/'receipt.json',receipt)
    return receipt


def run(output,only=None):return matrix.run_matrix(output,only,cases=CASES,scenario_runner=scenario,execution='public-resource-exhaustion')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--only');a=p.parse_args();run(a.output,a.only)
