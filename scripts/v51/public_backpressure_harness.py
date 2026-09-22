"""Public queued deadlines, query reentrancy and bounded completion callbacks."""
import argparse
import concurrent.futures
import json
import time
from . import public_qualification_harness as q, public_qualification_evidence as physical
from . import public_fault_harness as fault, public_protocol_harness as protocol
from . import public_promise_harness as matrix, public_recovery_harness as recovery
from . import public_history, backpressure_evidence as evidence
from .storage_harness import need, save

CASES = ('queued-deadline', 'query-reentrancy', 'completion-chain', 'completion-capacity')


class Worker(q.Worker):
    def chain(self, first, second):
        # Register all planned calls before dispatch. Trace order independently binds
        # the actual nested invocations to the original completion callback.
        with self.lock:
            commands=[]; futures=[]
            for kind,values in (('addAll',dict(documents=first)),('addAll',dict(documents=second)),('read',{})):
                self.serial+=1; identity=f'{self.node}-g{self.generation}-{self.serial}'
                command=dict(opId=identity,kind=kind,**values);commands.append(command)
                record=dict(command,node=self.node,pid=self.proc.pid,generation=self.generation,
                            startNanos=time.monotonic_ns(),endNanos=None,outcome='PENDING')
                self.history.append(record);future=concurrent.futures.Future();futures.append(future);self.pending[identity]=future,record
            self.proc.stdin.write(json.dumps(dict(kind='completionChain',calls=commands))+'\n');self.proc.stdin.flush()
            return commands,futures


def scenario(root,cp,case):
    root.mkdir();workers={};history=[];expected=[];receipt=dict(status='FAIL',case=case,publicRuntime=True)
    (root/'bounds-profile.txt').write_text('backpressure\n');(root/'chunk-bytes.txt').write_text('4096\n')
    (root/'promise-evidence').touch()
    def start(node,generation=1):
        workers[node]=Worker(root,node,cp,history,generation,consumer='backpressure');return workers[node]
    def docs(tag):return [dict(id=tag+i,value=f'tag-{tag+i}-'+'x'*512) for i in (0,1)]
    def write(active,tag,**values):
        active.call('addAll',documents=docs(tag),**values);expected.extend(docs(tag));return history[-1]['opId']
    def rows(event):return [r for r in fault.rows(root,leader) if r['event']==event]
    def pending_zero():return workers[leader].call('status')['pending']==0
    def release():
        (root/'query-release').touch();(root/'completion-release').touch()
        for node in protocol.NODES:(root/(node+'-release')).touch()
    try:
        q.command(['java','-cp',cp,q.PACKAGE+'admission.PublicRuntimeConsumer',root,'setup'],root,'public-bootstrap')
        for node in protocol.NODES:start(node)
        leader,active=fault.leader(workers);receipt['leader']=leader
        for tag in (10,20,30):write(active,tag)
        protocol.read_after_recovery(workers,expected);fault.wait_for(pending_zero,'seed admission did not drain')
        if case=='queued-deadline':
            held=active.send('read',hold=True);receipt['heldRead']=history[-1]['opId']
            fault.wait_for(lambda: rows('QUERY_HELD'),'query did not enter callback')
            queued=[];receipt['queued']=[]
            for tag in (40,50,60):
                queued.append(active.send('addAll',documents=docs(tag),poison=True));receipt['queued'].append(history[-1]['opId'])
            fault.wait_for(lambda: active.call('status')['pending']==4,'public admission not full')
            refused=active.send('addAll',documents=docs(70),poison=True).result(timeout=5);receipt['overflow']=history[-1]['opId']
            need(refused and refused.get('reasonCode')=='CAPACITY_EXCEEDED' and refused['outcome']=='NOT_SUBMITTED','queued overflow classification')
            for future in queued:
                result=future.result(timeout=20)
                need(result and result.get('reasonCode')=='DEADLINE_EXCEEDED' and result['outcome']=='NOT_SUBMITTED','queued deadline classification')
            need(not held.done(),'active cooperative query was forcibly timed out')
            (root/'query-release').touch();need(held.result(timeout=10)['documents']==expected,'held query changed')
        elif case=='query-reentrancy':
            result=active.call('read',reenter=True);receipt['callbackRead']=history[-1]['opId'];need(result['documents']==expected,'reentrant outer read changed')
        elif case=='completion-chain':
            # Pause the outer publication until its completion handler is attached.
            fault.replace(root/(leader+'-arm.txt'),'BEFORE_PUBLISH\npause\n')
            commands,futures=active.chain(docs(40),docs(50));receipt['chain']=[v['opId'] for v in commands]
            fault.wait_for(lambda: rows('CUT_REACHED') and any(r.get('opId')==receipt['chain'][0] for r in rows('CLIENT_ENQUEUED')),'completion handler not attached')
            (root/(leader+'-release')).touch()
            for future in futures:need(future.result(timeout=35)['outcome']=='SUCCESS','nested public completion call failed')
            expected.extend(docs(40)+docs(50));need(history[-1]['documents']==expected,'completion chain read changed')
            fault.wait_for(lambda: rows('COMPLETION_CHAIN_EXIT'),'nested completion did not return')
        else:
            receipt['heldCompletions']=[]
            for tag in (40,50,60,70):
                release_file=root/(leader+'-release');release_file.unlink(missing_ok=True)
                cuts=len(rows('CUT_REACHED'))
                fault.replace(root/(leader+'-arm.txt'),'BEFORE_PUBLISH\npause\n')
                future=active.send('addAll',documents=docs(tag),completion='hold');opid=history[-1]['opId']
                fault.wait_for(lambda: len(rows('CUT_REACHED'))>cuts and any(r.get('opId')==opid for r in rows('CLIENT_ENQUEUED')),'completion handler not attached')
                release_file.touch();need(future.result(timeout=20)['outcome']=='SUCCESS','held completion write failed')
                expected.extend(docs(tag));receipt['heldCompletions'].append(opid)
                fault.wait_for(lambda: len(rows('COMPLETION_HELD'))==len(receipt['heldCompletions']),'completion callback not held')
            need(active.call('status')['pending']==4,'completion permits released before callback return')
            receipt['rejected']=[]
            for kind,values in (('addAll',dict(documents=docs(80))),('read',{})):
                result=active.send(kind,**values).result(timeout=5);receipt['rejected'].append(history[-1]['opId'])
                need(result and result.get('reasonCode')=='CAPACITY_EXCEEDED' and result['outcome']==('NOT_SUBMITTED' if kind=='addAll' else 'NOT_APPLICABLE'),'completion pressure outcome')
            (root/'completion-release').touch()
        fault.wait_for(pending_zero,'public admission leaked after callbacks')
        receipt['resumedWrite']=write(active,90);protocol.read_after_recovery(workers,expected);receipt['resumedRead']=history[-1]['opId']
        active.stop();del workers[leader];receipt['retained']=recovery.archive(root,leader)
        start(leader,2);receipt['restartNanos']=time.monotonic_ns();protocol.read_after_recovery(workers,expected);receipt['afterRestartRead']=history[-1]['opId'];receipt['expected']=expected
    except BaseException as error:receipt['failure']=str(error);raise
    finally:
        release();errors=[]
        for worker in workers.values():
            try:worker.stop()
            except Exception as error:errors.append(str(error))
        if errors:receipt['cleanupErrors']=errors
        save(root/'history.json',history);save(root/'receipt.json',receipt)
        need(not errors,'backpressure cleanup: '+str(errors))
    try:
        traces=physical.traces_at(root)
        receipt['history']=public_history.check(history);receipt['physical']=physical.physical(root,history,traces)
        receipt['scenario']=evidence.public(root,traces,history,receipt)
        receipt['negatives']=physical.negatives(root,history)+evidence.public_negatives(root,traces,history,receipt)
        receipt['status']='PASS'
    except BaseException as error:receipt['failure']=str(error);raise
    finally:save(root/'receipt.json',receipt)
    return receipt


def run(output,only=None):
    return matrix.run_matrix(output,only,cases=CASES,scenario_runner=scenario,execution='public-runtime-backpressure',
                             consumer_sources=('PublicBackpressureConsumer.java',))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--only');a=p.parse_args();run(a.output,a.only)
