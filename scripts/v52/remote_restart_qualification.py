"""Frozen M04 retained restart, with delivery and every JVM owner over SSH."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import threading
import time
import uuid
from scripts.v51.guest_ssh_qualification import Server
from . import remote_delivery_qualification as previous,remote_history as h,remote_voter as v
from . import remote_restart as client,remote_restart_evidence as evidence,remote_voter_scope as scope
from .evidence import need,digest,encoded


class Receivers(previous.Receivers):
    def __init__(self,*args,targets):
        self.crashed=None;self.restart_record=dict(schema='gse-v52-restart-controller-v1',case=scope.RESTART_CASE,
                                                  node=None,crash=None,restart=None)
        super().__init__(*args,targets=targets)
    def admit_spec(self):
        need(self.name==scope.RESTART_CASE and self.spec['family']=='M04' and self.spec['profile']==scope.partition.recovery.profile(scope.RESTART_CASE),
             'restart receiver exact declared history')
    def prepare(self):
        super().prepare();self.binding['remoteRestart']=scope.RESTART_EXECUTION;h.runtime.save(self.collected/'binding.json',self.binding)
    def start_service(self,root,node,cp,mode,history,generation):
        before=time.monotonic_ns()
        worker=client.Client(root,node,self.binding,history,target=self.targets[node],generation=generation,
                             discard_launch=generation==2)
        self.clients.append(worker)
        if generation==2:
            self.restart_record['restart']=dict(configSha256=worker.sha,generation=2,startNanos=before,endNanos=time.monotonic_ns())
            h.runtime.save(self.collected/evidence.FILE,self.restart_record)
        return worker
    def crash(self,node):
        need(self.name==scope.RESTART_CASE and self.crashed is None and node in self.workers and self.generations[node]==1,
             'restart undeclared/repeated crash')
        worker=self.workers[node];before=time.monotonic_ns();answer=worker.crash()
        self.crashed=worker;self.record(worker);self.workers.pop(node)
        self.restart_record.update(node=node,crash=dict(configSha256=worker.sha,submissionCount=worker.crash_submissions,
            terminalReplyLost=worker.terminal_lost,startNanos=before,endNanos=time.monotonic_ns(),answerSha256=digest(encoded(answer))))
        h.runtime.save(self.collected/evidence.FILE,self.restart_record)
        return dict(node=node,pid=worker.proc.pid,generation=1,exitCode=-9,preReopen=answer['crash']['preReopen'])
    def collect_receiver(self,node,own):
        super().collect_receiver(node,own)
        if self.crashed is not None and self.crashed.node==node:
            self.crashed.record_stream(self.collected)
            target=self.collected/'pre-reopen'/node
            shutil.copytree(self.collected/(node+'-pre-reopen'),target)


def negatives(owner):
    node=owner.crashed.node;old=node+'-control';new=node+'-control-g2'
    def change(root,name,mutate):previous.change(root/name,mutate)
    cases={
        'missing-crash-receipt':(lambda p:(p/old/'crash.json').unlink(),None),
        'wrong-crash-owner':(lambda p:change(p,old+'/crash.json',lambda r:r['identity']['jvm'].update(pid=1)),'restart original crash identity'),
        'missing-original-claim':(lambda p:(p/old/'crash-request.json').unlink(),None),
        'changed-retained-bytes':(lambda p:previous.change_byte(next((p/(node+'-pre-reopen')).rglob('manifest.gsr'))),'restart retained bytes changed'),
        'changed-copy':(lambda p:previous.change_byte(p/'pre-reopen'/node/'manifest.gsr'),'restart scenario retained bytes'),
        'repeated-kill':(lambda p:change(p,evidence.FILE,lambda r:r['crash'].update(submissionCount=2)),'restart original crash count'),
        'changed-terminal':(lambda p:change(p,evidence.FILE,lambda r:r['crash'].update(answerSha256='0'*64)),'restart original terminal digest'),
        'early-restart':(lambda p:change(p,evidence.FILE,lambda r:r['restart'].update(startNanos=1)),'restart whole-history milestone order'),
        'reused-session':(lambda p:change(p,new+'/config.json',lambda r:r.update(session=v.c.read(p/old/'config.json',v.c.REQUEST_BYTES)['session'])),'restart retained generations'),
        'failed-service':(lambda p:change(p,old+'/exited.json',lambda r:r.update(exitCode=1)),'restart incomplete original exit'),
        'undeclared-scope':(None,'restart retained scope'),
    }
    results=[]
    for location in ('evidence','portable/relocated'):
        evidence.validate(owner.root/location,owner.binding)
        for name,(mutate,reason) in cases.items():
            target=owner.root/'restart-negatives'/location/name;shutil.copytree(owner.root/location,target);bound=dict(owner.binding)
            if mutate:mutate(target)
            else:bound.pop('remoteRestart')
            h.runtime.save(target/h.bundle.INDEX,h.bundle.members(target))
            try:evidence.validate(target,bound)
            except (ValueError,FileNotFoundError) as error:
                need(reason is None and isinstance(error,FileNotFoundError) or str(error)==reason,'restart unrelated negative: '+name+': '+str(error))
                results.append(dict(location=location,case=name,status='REJECTED',reason=str(error)))
            else:raise ValueError('restart negative accepted: '+name)
            shutil.rmtree(target)
    h.runtime.save(owner.root/'restart-negatives/results.json',results);return results


def run(output):
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False);source=h.source();began=time.monotonic()
    receipt=dict(status='FAIL',execution=scope.RESTART_EXECUTION,sourceBinding=source,sharedPythonCheckout=True,
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
        with tempfile.TemporaryDirectory(prefix='v52-restart-keys-',dir=h.ROOT/'target') as private,Server(private,root) as server:
            targets={}
            for node in h.topology.NODES:
                alias='gse-v52-'+uuid.uuid4().hex;known=Path(private)/(node+'-known')
                known.write_text(alias+' '+server.host['publicKey']+'\n');known.chmod(0o600)
                targets[node]=dict(host='127.0.0.1',port=server.port,user=server.user,key=str(Path(private)/'client/identity'),knownHosts=str(known),alias=alias)
            receipt['tools']=server.versions
            def factory(*args):
                owner=Receivers(*args,targets=targets);owners.append(owner);return owner
            result=h.run(root/'history',scope.RESTART_CASE,source,progress=progress,receiver_factory=factory)
            own=owners[0];workers=own.clients
            need(result['originalReads']==result['originalUpdates']==4,'restart unchanged M04 business counts')
            need(len(workers)==4 and sum(w.launch_lost for w in workers)==1 and all(w.launch_submissions==1 for w in workers),
                 'restart original voter launches')
            need(own.crashed.crash_submissions==1 and own.crashed.terminal_lost and own.crashed.terminal_query is not None,
                 'restart lost terminal query coverage')
            need(all(w.final['state']==('CRASHED' if w is own.crashed else 'STOPPED') and w.released and w.endpoint.closed and w.lifecycle.closed and
                 not v.c.process_alive(w.owner_identity['service']) and not v.c.process_alive(w.owner_identity['jvm']) and
                 not Path(w.config['socket']).parent.exists() and all(ch.proc.poll() is not None for ch in w.channels) for w in workers),
                 'restart owned-process cleanup incomplete')
            need(all(d.endpoint.closed and sum(c['action']=='install' for c in d.calls)==1 and
                 sum(c['action']=='part' for c in d.calls)==len(own.meta['parts']) for d in own.deliveries) and
                 all(not v.c.process_alive(r['process']) for r in own.bootstraps.values()),'restart original delivery/cleanup')
            receipt['restartNegatives']=negatives(own)
            receipt['deliveryNegatives']=previous.negatives(own,locations=('evidence','portable/relocated'))
            need(h.source()==source,'restart qualification source changed')
            receipt.update(status='PASS',originalReads=4,originalUpdates=4,negativesPerLocation=len(result['result']['negatives']),
                archiveSha256=result['archiveSha256'],packageSha256=own.meta['sha256'],packageFiles=len(own.meta['members']),
                stoppedServices=4,stoppedJvms=4,lostCrashTerminalRecovered=True,lostRestartReplyRecovered=True)
        need(server.process.poll() is not None,'restart sshd cleanup');return receipt
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        done.set();thread.join(2);receipt['elapsedSeconds']=round(time.monotonic()-began,3);h.runtime.save(root/'receipt.json',receipt)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');args=parser.parse_args();print(json.dumps(run(args.output)),flush=True)
