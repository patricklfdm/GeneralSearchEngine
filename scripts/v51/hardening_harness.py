"""Phase 5A: repeat combined faults on the same public group and retained disks."""
import argparse
import json
import time
from pathlib import Path
import xml.etree.ElementTree as ET
from . import public_qualification_harness as q, public_qualification_evidence as physical
from . import public_fault_harness as fault, public_protocol_harness as protocol
from . import public_promise_harness as matrix, public_recovery_harness as recovery
from . import public_final_harness as final, public_history
from .storage_harness import ROOT, need, save

CASES = ('partition-accept-kill', 'partition-proof-kill', 'whole-group-restart')
ROUNDS = 3
CUTS = {'partition-accept-kill':'WIRE_AFTER_RESPONSE_READ_ACCEPT',
        'partition-proof-kill':'WIRE_AFTER_RESPONSE_READ_COMMIT_PROOF'}


class RepeatedGroup(final.Group):
    def __init__(self, root, cp):
        super().__init__(root, cp); self.generations = {}; self.stops = []
    def start(self, node):
        generation=self.generations.get(node,0)+1
        need(generation<=4 and node not in self.workers, 'restart generation bound')
        began=time.monotonic_ns()
        worker=q.Worker(self.root,node,self.cp,self.history,generation,consumer='backpressure')
        self.generations[node]=generation; self.workers[node]=worker
        self.starts.append(dict(node=node,generation=generation,pid=worker.proc.pid,
                                startNanos=began,readyNanos=time.monotonic_ns()))
        return worker
    def stop(self, node, round_number, *, kill=False):
        worker=self.workers.pop(node); began=time.monotonic_ns(); worker.stop(kill=kill)
        entry=dict(node=node,pid=worker.proc.pid,generation=worker.generation,round=round_number,
                   startNanos=began,endNanos=time.monotonic_ns(),exitCode=worker.proc.returncode)
        need(entry['exitCode']==(-9 if kill else 0), 'wrong termination result')
        retained=recovery.archive(self.root,node)
        path=f'archives/round-{round_number}-{node}.tar.gz'
        (self.root/'before-reopen.tar.gz').rename(self.root/path)
        entry.update(archive=path,retained=retained,archivedNanos=time.monotonic_ns())
        self.stops.append(entry); return entry
    def drained(self, floor):
        result={}
        for node,worker in self.workers.items():
            value=fault.wait_for(lambda: (s if (s:=worker.call('status'))['pending']==0 and
                s['provenIndex']>=floor and s['sample']['admissionAvailable']==4 and s['sample']['orderedQueue']==s['sample']['deadlinesQueue']==0 else None),
                'post-recovery proven prefix/admission/timers not drained')
            result[node]=dict(node=node,pid=worker.proc.pid,generation=worker.generation,
                             observedNanos=time.monotonic_ns(),status=value)
        return result
    def save(self):
        super().save(); save(self.root/'worker-stops.json',self.stops)


class RecoveryGroup(RepeatedGroup):
    """Phase 5A client schedule; shared lifecycle groups keep their original driver."""
    def dispatch(self, worker, kind, **values):
        need(len(self.history)<48, 'hardening history dispatch bound')
        return worker.send(kind,**values)
    def read(self, workers=None, *, uncertain=()):
        # A strong read decides only this cut. It cannot lease the next write's epoch.
        workers=self.workers if workers is None else workers
        for _ in range(4):
            node,active=fault.leader(workers)
            result=self.dispatch(active,'read').result(timeout=35)
            need(result is not None and result.get('kind')=='read', 'hardening read disconnected/mismatched')
            if result['outcome']=='SUCCESS':
                observed=result['documents']
                need(observed==self.expected or uncertain and observed==self.expected+list(uncertain),
                     'hardening recovery projection changed')
                self.expected=list(observed)
                return node,active
            need(result['outcome']=='NOT_APPLICABLE' and result.get('reasonCode') in protocol.READ_REJECTIONS,
                 'unexpected hardening read failure: '+str(result))
        raise ValueError('hardening read exhausted four attempts: '+str(result))
    def write(self, worker, tag):
        docs=[dict(id=tag+i,value=f'tag-{tag+i}-'+'x'*512) for i in (0,1)]
        result=self.dispatch(worker,'addAll',documents=docs).result(timeout=35)
        need(result is not None and result['outcome']=='SUCCESS', 'public call failed: '+str(result))
        self.expected.extend(docs);return self.history[-1]['opId']


def resume(group, row, tag):
    # Each attempt is a NEW mutation. Preserve failed outcomes and resolve a
    # potentially chosen bulk via the next fresh read plus independent evidence.
    row['recoveryBeginNanos']=time.monotonic_ns()
    attempts=row['recoveryWrites']=[];uncertain=[]
    for attempt in range(3):
        _,service=group.read(uncertain=uncertain);read_id=group.history[-1]['opId']
        docs=[dict(id=tag+2*attempt+i,value=f'tag-{tag+2*attempt+i}-'+'x'*512) for i in (0,1)]
        pending=group.dispatch(service,'addAll',documents=docs)
        write_id=group.history[-1]['opId'];attempts.append(dict(read=read_id,write=write_id))
        result=pending.result(timeout=35)
        need(result is not None and result.get('kind')=='addAll' and result.get('opId')==write_id,
             'hardening recovery write disconnected/mismatched')
        if result['outcome']=='SUCCESS':
            group.expected.extend(docs);row.update(recoveredRead=read_id,resumedWrite=write_id);return
        need(result['outcome']=='NOT_SUBMITTED' and result.get('reasonCode') in q.RECOVERY_REASONS or
             result['outcome']=='INDETERMINATE' and result.get('reasonCode') in q.UNCERTAIN_RECOVERY_REASONS,
             'unexpected hardening recovery write failure: '+str(result))
        uncertain=docs if result['outcome']=='INDETERMINATE' else []
    raise ValueError('hardening recovery exhausted three fresh writes: '+str(result))


def scenario(root, cp, case):
    root.mkdir(); (root/'archives').mkdir(); group=RecoveryGroup(root,cp)
    receipt=dict(status='FAIL',case=case,publicRuntime=True,rounds=[])
    for marker in ('promise-evidence','selection-evidence','pressure-evidence','lifecycle-evidence'): (root/marker).touch()
    (root/'bounds-profile.txt').write_text('backpressure\n'); (root/'chunk-bytes.txt').write_text('4096\n')
    try:
        final.bootstrap(root,cp)
        for node in protocol.NODES: group.start(node)
        _,active=fault.leader(group.workers)
        for tag in (10,20,30): group.write(active,tag)
        _,active=group.read(); receipt['baseline']=group.drained(active.call('status')['appliedIndex'])
        for number in range(1,ROUNDS+1):
            row=dict(number=number,beginNanos=time.monotonic_ns()); receipt['rounds'].append(row)
            old,active=group.read(); row.update(oldLeader=old,oldPid=active.proc.pid,oldGeneration=active.generation)
            row['beforeRead']=group.history[-1]['opId']
            if case in CUTS:
                need(old!='node-3','non-campaigning voter led')
                (root/(old+'-release')).unlink(missing_ok=True)
                prior=max((r['order'] for r in fault.rows(root,old) if r['pid']==active.proc.pid),default=0)
                fault.replace(root/(old+'-arm.txt'),CUTS[case]+'\npause\n')
                tag=number*100; docs=[dict(id=tag+i,value=f'chosen-{tag+i}-'+'x'*512) for i in (0,1)]
                pending=group.dispatch(active,'addAll',documents=docs); row['uncertainWrite']=group.history[-1]['opId']
                row['pause']=fault.wait_for(lambda: next((r for r in fault.rows(root,old) if r['pid']==active.proc.pid
                    and r['order']>prior and r['event']=='CUT_REACHED'),None),'combined acknowledgement pause absent')
                need(row['pause']['cut']==CUTS[case], 'wrong acknowledgement cut')
                fault.partition(root,old); row['partitionNanos']=time.monotonic_ns(); group.expected.extend(docs)
                new,service=group.read({n:w for n,w in group.workers.items() if n!=old})
                row['majorityRead']=group.history[-1]['opId']; row['newLeader']=new
                row['majorityWrite']=group.write(service,tag+10)
                group.read({n:w for n,w in group.workers.items() if n!=old}); row['majorityAfterWriteRead']=group.history[-1]['opId']
                row['stops']=[group.stop(old,number,kill=True)]
                outcome=pending.result(timeout=5)
                need(outcome is None or outcome['outcome']=='INDETERMINATE','held write falsely completed: '+str(outcome))
                fault.partition(root); row['healNanos']=time.monotonic_ns(); group.start(old)
            else:
                row['stops']=[]
                for node in protocol.NODES:
                    if node!=old: row['stops'].append(group.stop(node,number))
                row['minorityNanos']=time.monotonic_ns(); row['denied']=[]
                for kind,values in [('read',{}),('addAll',dict(documents=[dict(id=900+number,value='must-not-appear')]))]:
                    outcome=group.dispatch(active,kind,**values).result(timeout=35)
                    need(outcome and outcome['outcome']==('NOT_APPLICABLE' if kind=='read' else 'NOT_SUBMITTED'),
                         'minority outcome: '+str(outcome))
                    row['denied'].append(group.history[-1]['opId'])
                row['stops'].append(group.stop(old,number)); row['allStoppedNanos']=time.monotonic_ns()
                order=protocol.NODES[number-1:]+protocol.NODES[:number-1]
                for node in order: group.start(node)
            resume(group,row,number*100+40)
            _,service=group.read(); row['finalRead']=group.history[-1]['opId']; row['expected']=list(group.expected)
            row['drained']=group.drained(service.call('status')['appliedIndex']); row['endNanos']=time.monotonic_ns()
        receipt['expected']=group.expected
    except BaseException as error: receipt['failure']=str(error); raise
    finally:
        fault.partition(root)
        for node in protocol.NODES: (root/(node+'-release')).touch()
        try: group.close()
        finally: group.save(); save(root/'receipt.json',receipt)
    try:
        from . import hardening_evidence as evidence
        traces=physical.traces_at(root); history=group.application()
        generations=evidence.processes(traces,group.starts,group.stops)
        receipt['history']=public_history.check(history,max_operations=48)
        receipt['physical']=physical.physical(root,history,traces,process_generations=generations)
        receipt['hardening']=evidence.validate(root,traces,history,receipt,group.starts,group.stops)
        receipt['negatives']=physical.negatives(root,history,process_generations=generations,max_operations=48)+evidence.negatives(root,traces,history,receipt,group.starts,group.stops)
        receipt['status']='PASS'
    except BaseException as error: receipt['failure']=str(error); raise
    finally: save(root/'receipt.json',receipt)
    return receipt


def run(output, only=None):
    module=ROOT/'general-search-engine-replication'; name='V51ApplicationRebuildTest'
    report=module/f'target/surefire-reports/TEST-io.github.patricklfdm.generalsearch.replication.{name}.xml'
    source=module/f'src/test/java/io/github/patricklfdm/generalsearch/replication/{name}.java'
    suite=ET.parse(report).getroot()
    need(int(suite.attrib['tests'])>=5 and all(int(suite.attrib.get(k,0))==0 for k in ('failures','errors','skipped')),
         'hardening Java prerequisite failed')
    need(report.stat().st_mtime_ns>=source.stat().st_mtime_ns, 'stale rebuild regression prerequisite')
    receipt=matrix.run_matrix(output,only,cases=CASES,scenario_runner=scenario,execution='public-combined-hardening',
                              consumer_sources=('PublicBackpressureConsumer.java',))
    receipt['javaTests']={name:dict(tests=int(suite.attrib['tests']),sha256=final.storage.sha(report.read_bytes()))}
    save(Path(output)/'receipt.json',receipt); return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--only');a=p.parse_args();run(a.output,a.only)
