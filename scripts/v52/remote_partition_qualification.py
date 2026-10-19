"""Complete unchanged M04 follower snapshot history over pinned SSH ownership."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import threading
import time
import uuid
from scripts.v51.guest_ssh_qualification import Server
from . import remote_delivery_qualification as previous,remote_history as h,remote_voter as v
from . import remote_partition as control,remote_partition_scope as scope,remote_partition_evidence as evidence
from . import measurement_recovery_evidence as recovery_evidence,measurement_trace as trace
from .evidence import need


class Receivers(previous.Receivers):
    def __init__(self,*args,targets):
        self.controls={};self.cut_target=None
        self.partition_record=dict(schema='gse-v52-partition-controller-v1',case=scope.CASE,transitions=[],cleanup=[])
        super().__init__(*args,targets=targets)
    def admit_spec(self):
        need(self.name==scope.CASE and self.spec['family']=='M04' and self.spec['profile']==scope.recovery.profile(scope.CASE),
             'partition receiver exact declared history')
    def prepare(self):
        super().prepare();self.binding['remotePartition']=v.scope.domains.execution(self.binding,scope.EXECUTION)
        h.runtime.save(self.collected/'binding.json',self.binding)
    def start_service(self,root,node,cp,mode,history,generation):
        worker=super().start_service(root,node,cp,mode,history,generation)
        endpoint=control.Controller(worker,self.targets[node],python_context=self.python_context(node));self.controls[node]=endpoint
        try:endpoint.warm()
        except BaseException:
            try:worker.abort()
            finally:worker.close_transport();endpoint.close()
            raise
        return worker
    def partition(self,node=None):
        rows=self.partition_record['transitions'];op='cut' if node else 'heal'
        need((op=='cut' and not rows and node in h.topology.NODES) or
             (op=='heal' and len(rows)==1 and len(rows[0]['nodes'])==3),'partition controller transition order')
        if op=='cut':self.cut_target=node
        command=dict(operation=op,target=self.cut_target)
        row=dict(request=command,startNanos=time.monotonic_ns(),endNanos=None,nodes=[]);rows.append(row)
        try:
            need(set(self.controls)==set(h.topology.NODES),'partition controls not prepared')
            answers={};errors={}
            # Each independent receiver gets one command concurrently. Wait for
            # every original response (including failures) before cleanup. The
            # finite exchange bounds still apply; never replay the fault.
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures={pool.submit(self.controls[node].transition,command,
                    discard=self.qualify_transport and (op,node) in {('cut','node-1'),('heal','node-2')}):node for node in h.topology.NODES}
                for future in as_completed(futures):
                    node=futures[future]
                    try:answers[node]=future.result()
                    except Exception as error:errors[node]=dict(type=type(error).__name__,message=str(error))
            row['nodes']=[answers[node] for node in h.topology.NODES if node in answers]
            if errors:
                row['failures']=errors;raise ValueError('partition receiver transition failed: '+json.dumps(errors))
            h.recovery.partition(self.collected,self.cut_target if op=='cut' else None)
            row['endNanos']=time.monotonic_ns()
        finally:h.runtime.save(self.collected/evidence.FILE,self.partition_record)
    def cleanup_partition(self,retain):
        # Successful original heal needs no third transition. For an incomplete
        # history heal each launched owner over SSH, retaining cleanup separately.
        rows=self.partition_record['transitions']
        complete=len(rows)==2 and rows[-1]['request']['operation']=='heal' and rows[-1]['endNanos'] is not None
        if rows and not complete:
            for node,worker in self.workers.items():
                def heal(node=node,worker=worker):
                    if node not in self.controls:self.controls[node]=control.Controller(worker,self.targets[node],python_context=self.python_context(node))
                    record=dict(node=node,status='FAIL');self.partition_record['cleanup'].append(record)
                    try:record.update(status='HEALED',answer=self.controls[node].transition(dict(operation='cleanup',target=None)))
                    finally:h.runtime.save(self.collected/evidence.FILE,self.partition_record)
                retain(node,heal)
        retain('collected-network-controls',lambda:h.recovery.partition(self.collected))
    def finish(self,failure):
        try:super().finish(failure)
        finally:
            for endpoint in self.controls.values():endpoint.close()


def negatives(owner):
    def change(path,mutate):
        value=v.c.read(path,v.c.REQUEST_BYTES);mutate(value);h.runtime.save(path,value)
    def change_row(root,mutate):change(root/evidence.FILE,mutate)
    cases={
        'missing-cut-receipt':(lambda p:(p/'node-1-control/partition/cut-result.json').unlink(),None),
        'changed-cut-target':(lambda p:change(p/'node-1-control/partition/cut-request.json',lambda r:r['request'].update(target='foreign')), 'partition original receipt changed'),
        'missing-receiver-ack':(lambda p:change_row(p,lambda r:r['transitions'][0]['nodes'].pop()),'partition controller barrier fields'),
        'premature-business-barrier':(lambda p:change(p/'scenario.json',lambda r:r.update(partitionNanos=1)),'partition whole-history barrier order'),
        'changed-result-hash':(lambda p:change_row(p,lambda r:r['transitions'][0]['nodes'][0]['answer']['result'].update(afterSha256='0'*64)), 'partition resulting cut changed'),
        'unhealed-final-state':(lambda p:change(p/'node-1-control/partition/final.json',lambda r:r.update(currentSha256='0'*64)),'partition collected state not healed'),
        'cleanup-as-success':(lambda p:(p/'node-1-control/partition/cleanup-request.json').write_text('{}'),'partition unknown/partial/cleanup records'),
        'duplicate-transition':(lambda p:change_row(p,lambda r:r['transitions'].append(deepcopy(r['transitions'][-1]))),'partition complete cut/heal'),
        'missing-partition-binding':(None,'partition retained scope'),
    }
    results=[]
    for location in ('evidence','portable/relocated'):
        evidence.validate(owner.root/location,owner.binding)
        for name,(mutate,reason) in cases.items():
            target=owner.root/'partition-negatives'/location/name;shutil.copytree(owner.root/location,target);bound=dict(owner.binding)
            if mutate:mutate(target)
            else:bound.pop('remotePartition')
            h.runtime.save(target/h.bundle.INDEX,h.bundle.members(target))
            try:evidence.validate(target,bound)
            except (ValueError,FileNotFoundError) as error:
                need(reason is None and isinstance(error,FileNotFoundError) or str(error)==reason,'partition unrelated negative: '+name+': '+str(error))
                results.append(dict(location=location,case=name,status='REJECTED',reason=str(error)))
            else:raise ValueError('partition negative accepted: '+name)
            shutil.rmtree(target)
    h.runtime.save(owner.root/'partition-negatives/results.json',results);return results


def basis_negatives(owner):
    results=[]
    for location in ('evidence','portable/relocated'):
        root=owner.root/location
        traces={node:trace.Trace(root/(node+'-trace.jsonl'),node=node) for node in h.topology.NODES}
        recovery_evidence.validate(root,owner.binding,traces=traces)
        physical=recovery_evidence.physical;raw=(root/'node-1/manifest.gsr').read_bytes()
        manifest=dict(physical.f.inspect(raw,'MANIFEST'),digest=raw[16:48].hex())
        def basis(row):
            return row['event'] in ('REPLY','RECEIVED') and physical.f.wire(physical.raw(row['frame']),manifest)['type']=='BASIS_CHUNK'
        class RemovedBasis:
            def __init__(self,rows):self.rows=rows
            def __iter__(self):
                for row in self.rows:yield dict(row,event='REMOVED_BASIS_TRANSFER') if basis(row) else row
        changed={node:RemovedBasis(rows) for node,rows in traces.items()}
        try:recovery_evidence.validate(root,owner.binding,traces=changed)
        except ValueError as error:
            need(str(error)=='selection lacks transferred basis','partition unrelated basis rejection: '+str(error))
            results.append(dict(location=location,case='missing-selected-basis-transfer',status='REJECTED',reason=str(error)))
        else:raise ValueError('partition selected basis negative accepted')
    h.runtime.save(owner.root/'partition-negatives/basis-results.json',results);return results


def run(output):
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False);source=h.source();began=time.monotonic()
    receipt=dict(status='FAIL',execution=scope.EXECUTION,sourceBinding=source,sharedPythonCheckout=True,
                 sshDelivery=True,remoteBootstrap=True,remoteFaultLifecycle=True,qualifiedMeasurement=False,
                 fullRemoteQualification=False,paidCloud=False)
    done=threading.Event();stage='private-sshd';owners=[]
    def progress(value):
        nonlocal stage
        stage=value;print(json.dumps(dict(stage=stage,elapsedSeconds=round(time.monotonic()-began,1))),flush=True)
    def beat():
        while not done.wait(60):print(json.dumps(dict(stage=stage,status='RUNNING',elapsedSeconds=round(time.monotonic()-began,1))),flush=True)
    thread=threading.Thread(target=beat,daemon=True);thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix='v52-partition-keys-',dir=h.ROOT/'target') as private,Server(private,root) as server:
            targets={}
            for node in h.topology.NODES:
                alias='gse-v52-'+uuid.uuid4().hex;known=Path(private)/(node+'-known')
                known.write_text(alias+' '+server.host['publicKey']+'\n');known.chmod(0o600)
                targets[node]=dict(host='127.0.0.1',port=server.port,user=server.user,key=str(Path(private)/'client/identity'),knownHosts=str(known),alias=alias)
            receipt['tools']=server.versions
            def factory(*args):
                owner=Receivers(*args,targets=targets);owners.append(owner);return owner
            result=h.run(root/'history',scope.CASE,source,progress=progress,receiver_factory=factory)
            own=owners[0];workers=list(own.workers.values());controllers=list(own.controls.values())
            need(result['originalReads']==result['originalUpdates']==4,'partition unchanged M04 business counts')
            need(len(controllers)==3 and [c.losses for c in controllers]==[['cut'],['heal'],[]] and
                 all([r['request']['operation'] for r in c.calls if r['action']=='apply']==['cut','heal'] for c in controllers),
                 'partition original transitions/lost reply coverage')
            need(not own.partition_record['cleanup'],'partition unplanned cleanup')
            need(all(d.endpoint.closed and sum(c['action']=='install' for c in d.calls)==1 and
                 sum(c['action']=='part' for c in d.calls)==len(own.meta['parts']) for d in own.deliveries),'partition original delivery')
            need(sum(w.launch_lost for w in workers)==1 and sum(w.injected and w.recovered for w in workers)==1 and
                 all(w.launch_submissions==1 for w in workers),'partition original voter operations')
            need(all(w.final['state']=='STOPPED' and w.released and w.endpoint.closed and w.lifecycle.closed and
                 not v.c.process_alive(w.owner_identity['service']) and not v.c.process_alive(w.owner_identity['jvm']) and
                 not Path(w.config['socket']).parent.exists() and all(ch.proc.poll() is not None for ch in w.channels) for w in workers) and
                 all(c.endpoint.closed and all(ch.proc.poll() is not None for ch in c.endpoint.streams) and
                     all(not v.c.process_alive(p) for p in c.endpoint.owners) for c in controllers) and
                 all(not v.c.process_alive(r['process']) for r in own.bootstraps.values()),
                 'partition owned-process cleanup incomplete')
            locations=('evidence','portable/relocated')
            receipt['lifecycleNegatives']=previous.previous.negatives(own,locations=locations)
            receipt['deliveryNegatives']=previous.negatives(own,locations=locations)
            receipt['partitionNegatives']=negatives(own)
            receipt['selectedBasisNegatives']=basis_negatives(own)
            need(h.source()==source,'partition qualification source changed')
            receipt.update(status='PASS',originalReads=4,originalUpdates=4,negativesPerLocation=len(result['result']['negatives']),
                archiveSha256=result['archiveSha256'],packageSha256=own.meta['sha256'],packageFiles=len(own.meta['members']),
                stoppedServices=3,stoppedJvms=3,receiverTransitions=6,lostCutReplyRecovered=True,lostHealReplyRecovered=True)
        need(server.process.poll() is not None,'partition sshd cleanup');return receipt
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        done.set();thread.join(2);receipt['elapsedSeconds']=round(time.monotonic()-began,3);h.runtime.save(root/'receipt.json',receipt)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');args=parser.parse_args();print(json.dumps(run(args.output)),flush=True)
