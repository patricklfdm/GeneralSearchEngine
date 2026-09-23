"""Phase 5B: real torn authority/pressure and cancellation/close across recovery."""
import argparse
import json
import tarfile
import time
from . import public_qualification_harness as q, public_qualification_evidence as physical
from . import public_fault_harness as fault, public_protocol_harness as protocol
from . import public_promise_harness as matrix
from . import public_final_harness as final, hardening_harness as repeated, public_history
from . import storage_inspector as storage, combined_lifecycle_evidence as evidence
from .storage_harness import need, save

CASES = ('torn-accept-pressure', 'torn-proof-pressure', 'cancel-chosen-recovery', 'close-pinned-recovery')


class Group(repeated.RepeatedGroup):
    def __init__(self,root,cp):
        super().__init__(root,cp); self.quarantined={}
    def close(self):
        self.workers.update(self.quarantined); self.quarantined.clear()
        super().close()
    def start(self, node):
        generation=self.generations.get(node,0)+1
        need(generation<=2 and node not in self.workers,'combined lifecycle generation bound')
        began=time.monotonic_ns()
        worker=q.Worker(self.root,node,self.cp,self.history,generation,consumer='lifecycle')
        self.generations[node]=generation; self.workers[node]=worker
        self.starts.append(dict(node=node,generation=generation,pid=worker.proc.pid,startNanos=began,readyNanos=time.monotonic_ns()))
        return worker
    def rows(self,node,event):return [r for r in fault.rows(self.root,node) if r['event']==event]
    def call_id(self):return self.history[-1]['opId']
    def release(self):
        fault.partition(self.root); protocol.network(self.root,[]); fault.replace(self.root/'pressure-rules.txt','')
        (self.root/'pressure-release').touch()
        for node in protocol.NODES:(self.root/(node+'-release')).touch()


def torn(group, receipt):
    root=group.root; old=receipt['oldLeader']; active=group.workers[old]
    proof=next(r['record'] for r in reversed(group.rows(old,'FORCE')) if r['kind']=='PROOF')
    peer=next(v['voter'] for v in storage.f.inspect(storage.raw(proof),'PROOF')['receipts'] if v['voter']!=old)
    target=old if receipt['case']=='torn-accept-pressure' else peer
    need(target!='node-3','quarantined voter must leave the non-campaigning follower healthy')
    kind='ACCEPT' if target==old else 'PROOF'; receipt.update(target=target,kind=kind,seedProof=proof)
    docs=[dict(id=40+i,value=f'uncertain-{i}-'+'x'*512) for i in (0,1)]
    fault.replace(root/(target+'-partial-write.txt'),kind+'\n')
    pending=active.send('addAll',documents=docs); receipt['uncertainWrite']=group.call_id()
    receipt['partial']=fault.wait_for(lambda: next(iter(group.rows(target,'PARTIAL_WRITE_FAILURE')),None),'missing real torn append')
    outcome=pending.result(timeout=20)
    need(outcome and outcome['outcome']=='INDETERMINATE','torn write lost conservative outcome')
    receipt['denied']=[]
    for command,values in [('read',{}),('addAll',dict(documents=[dict(id=999,value='must-not-appear')]))]:
        result=group.workers[target].send(command,**values).result(timeout=20); receipt['denied'].append(group.call_id())
        need(result and result.get('reasonCode')=='STORAGE_FAILURE' and
             result['outcome']==('NOT_APPLICABLE' if command=='read' else 'NOT_SUBMITTED'),'quarantined public handle served work')
    # A failed runtime rejects public work but keeps its listener until close.
    # Keep that endpoint alive so real connect-before-write reservations can be
    # held; exclude it from healthy service and retain ownership for cleanup.
    group.quarantined[target]=group.workers.pop(target)
    receipt['quarantinedInventory']=storage.inventory(root/target)
    if kind=='PROOF':group.expected.extend(docs)
    leader,active=group.read(); receipt['survivingRead']=group.call_id()
    # The healthy leader probes every peer. Its two damaged-peer reservations
    # stay occupied while the only healthy follower restarts on retained disks.
    receipt['pressureOwner']=leader; receipt['pressureStartNanos']=time.monotonic_ns()
    fault.replace(root/'pressure-rules.txt',f'{leader} {target} BEFORE_REQUEST_WRITE *\n')
    fault.wait_for(lambda: len(group.rows(leader,'PRESSURE_HELD'))==2,'two real damaged-peer slots not held')
    full=max(r['order'] for r in group.rows(leader,'PRESSURE_HELD'))
    fault.wait_for(lambda: any(r['transition']=='OUTBOUND_REJECTED' and r['order']>full for r in group.rows(leader,'TRANSPORT')),
                   'no actual capacity rejection under quarantine pressure')
    receipt['restart']=group.stop('node-3',1); group.start('node-3')
    _,active=group.read(); receipt['duringRead']=group.call_id()
    receipt['duringWrite']=group.write(active,60); group.read(); receipt['duringAfterWriteRead']=group.call_id()
    receipt['releaseNanos']=time.monotonic_ns(); fault.replace(root/'pressure-rules.txt',''); (root/'pressure-release').touch()
    fault.wait_for(lambda: len(group.rows(leader,'PRESSURE_RELEASED'))==2,'pressure did not drain')
    victim=group.quarantined[target]; began=time.monotonic_ns(); victim.stop(); del group.quarantined[target]
    stopped=dict(node=target,pid=victim.proc.pid,generation=1,startNanos=began,endNanos=time.monotonic_ns(),exitCode=victim.proc.returncode)
    need(storage.inventory(root/target)==receipt['quarantinedInventory'],'pressure changed quarantined bytes')
    with tarfile.open(root/'quarantined.tar.gz','w:gz') as tar:tar.add(root/target,arcname=target)
    receipt['quarantinedArchiveSha256']=storage.sha((root/'quarantined.tar.gz').read_bytes())
    stopped['archivedNanos']=time.monotonic_ns(); group.stops.append(stopped); receipt['quarantinedStop']=stopped
    receipt['probes']=[]
    for attempt in (1,2):
        result=q.command(['java','-cp',group.cp,q.PACKAGE+'admission.PublicLifecycleConsumer',root,target[-1],'probe'],root,f'quarantine-probe-{attempt}')
        receipt['probes'].append(json.loads(result.stdout)); inventory=storage.inventory(root/target)
        save(root/f'quarantine-probe-{attempt}-inventory.json',inventory)
        need(inventory==receipt['quarantinedInventory'],'rejected reopen changed damaged authority')


def lifecycle(group, receipt):
    root=group.root; old=receipt['oldLeader']; active=group.workers[old]; cancel=receipt['case'].startswith('cancel-')
    cut='WIRE_AFTER_RESPONSE_READ_ACCEPT' if cancel else 'READ_CAPTURED'
    fault.replace(root/(old+'-arm.txt'),cut+'\npause\n')
    if cancel:
        docs=[dict(id=40+i,value=f'cancelled-{i}-'+'x'*512) for i in (0,1)]
        pending=active.send('addAll',documents=docs)
    else:
        receipt['oldDocuments']=list(group.expected); pending=active.send('read')
    receipt['heldOperation']=group.call_id()
    receipt['pause']=fault.wait_for(lambda: next(iter(group.rows(old,'CUT_REACHED')),None),'lifecycle recovery pause absent')
    if cancel:
        fault.wait_for(lambda: any(r['opId']==receipt['heldOperation'] for r in group.rows(old,'CLIENT_ENQUEUED')),'future not exposed')
        result=active.call('cancel',target=receipt['heldOperation']); receipt['cancel']=group.call_id()
        need(result['cancelled'] is True and pending.result(timeout=5)['outcome']=='CANCELLED','future did not cancel')
        group.expected.extend(docs)
    fault.partition(root,old); receipt['partitionNanos']=time.monotonic_ns()
    survivors={n:w for n,w in group.workers.items() if n!=old}
    new,service=group.read(survivors); receipt['majorityRead']=group.call_id(); receipt['newLeader']=new
    receipt['majorityWrite']=group.write(service,60); group.read(survivors); receipt['majorityAfterWriteRead']=group.call_id()
    receipt['healNanos']=time.monotonic_ns(); fault.partition(root)
    if cancel:
        old_epoch=next(r for r in reversed(group.rows(old,'FORCE')) if r['kind']=='PROMISE' and r['order']<receipt['pause']['order'])
        epoch=storage.f.inspect(storage.raw(old_epoch['record']),'PROMISE')['epoch']
        receipt['higherPromise']=fault.wait_for(lambda: next((r for r in group.rows(old,'FORCE') if r['kind']=='PROMISE' and
             storage.f.inspect(storage.raw(r['record']),'PROMISE')['epoch']>epoch),None),'held cancelled leader was not fenced')
    else:
        receipt['installed']=fault.wait_for(lambda: next((r for r in group.rows(old,'REJOIN_INSTALLED')
            if len(storage.f.inspect(storage.raw(r['snapshot']),'SNAPSHOT')['anchors'])>receipt['seedIndex']),None),'new snapshot did not overlap pinned read')
        closing=active.send('closeHandle'); receipt['closing']=group.call_id()
        receipt['whileClosingWrite']=group.write(service,70); group.read(survivors); receipt['whileClosingRead']=group.call_id()
        result=closing.result(timeout=20)
        need(result and result.get('reasonCode')=='DEADLINE_EXCEEDED' and result['outcome']=='NOT_APPLICABLE','close bypassed pinned recovery view')
        result=active.send('duplicateStart').result(timeout=20); receipt['duplicate']=group.call_id()
        need(result and result.get('reasonCode')=='STORAGE_FAILURE' and result['outcome']=='NOT_APPLICABLE','close released retained ownership')
        result=active.send('addAll',documents=[dict(id=999,value='must-not-appear')]).result(timeout=10); receipt['closedRejection']=group.call_id()
        need(result and result.get('reasonCode')=='CLOSED' and result['outcome']=='NOT_SUBMITTED','closing handle admitted work')
        need(not pending.done(),'pinned view ended before release')
    receipt['releaseNanos']=time.monotonic_ns(); (root/(old+'-release')).touch()
    if not cancel:
        need(pending.result(timeout=10)['documents']==receipt['oldDocuments'],'recovery changed old captured view')
        active.call('closeHandle'); receipt['closed']=group.call_id()
        active.call('closeHandle'); receipt['closedAgain']=group.call_id()
    else:
        fault.wait_for(lambda: group.rows(old,'CUT_RELEASED'),'stale acknowledgement did not release')
    receipt['restart']=group.stop(old,1); group.start(old)


def scenario(root,cp,case):
    root.mkdir(); (root/'archives').mkdir(); group=Group(root,cp); receipt=dict(status='FAIL',case=case,publicRuntime=True)
    for marker in ('promise-evidence','selection-evidence','pressure-evidence','lifecycle-evidence'):(root/marker).touch()
    (root/'bounds-profile.txt').write_text('backpressure\n'); (root/'chunk-bytes.txt').write_text('4096\n')
    try:
        final.bootstrap(root,cp)
        protocol.network(root,[f'{n} node-3 BEFORE_REQUEST_WRITE PREPARE' for n in ('node-1','node-2')])
        for node in protocol.NODES:group.start(node)
        old,active=fault.leader(group.workers); receipt['oldLeader']=old; protocol.network(root,[])
        for tag in (10,20,30):group.write(active,tag)
        _,active=group.read(); receipt['seedIndex']=active.call('status')['appliedIndex']
        receipt['baseline']=group.drained(receipt['seedIndex'])
        if case.startswith('torn-'):torn(group,receipt)
        else:lifecycle(group,receipt)
        _,active=group.read(); receipt['recoveredRead']=group.call_id(); receipt['resumedWrite']=group.write(active,80)
        _,active=group.read(); receipt['finalRead']=group.call_id(); receipt['expected']=list(group.expected)
        receipt['drained']=group.drained(active.call('status')['appliedIndex'])
    except BaseException as error:receipt['failure']=str(error);raise
    finally:
        group.release()
        try:group.close()
        finally:group.save();save(root/'receipt.json',receipt)
    try:
        traces=physical.traces_at(root); history=group.application()
        identities=evidence.processes(traces,group.starts,group.stops)
        tails={receipt['target']:receipt['partial']} if case.startswith('torn-') else None
        receipt['history']=public_history.check(history,max_operations=32)
        receipt['physical']=physical.physical(root,history,traces,rejected_tails=tails,process_generations=identities)
        receipt['combined']=evidence.validate(root,traces,group.history,receipt,group.starts,group.stops)
        receipt['negatives']=physical.negatives(root,history,rejected_tails=tails,process_generations=identities,max_operations=32)+evidence.negatives(root,traces,group.history,receipt,group.starts,group.stops)
        receipt['status']='PASS'
    except BaseException as error:receipt['failure']=str(error);raise
    finally:save(root/'receipt.json',receipt)
    return receipt


def run(output,only=None):
    return matrix.run_matrix(output,only,cases=CASES,scenario_runner=scenario,execution='public-combined-lifecycle',consumer_sources=('PublicLifecycleConsumer.java',))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--only');a=p.parse_args();run(a.output,a.only)
