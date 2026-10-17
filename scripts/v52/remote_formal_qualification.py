"""Complete frozen M01–M03 histories over delivered persistent SSH services."""
import argparse
import json
from pathlib import Path
import tempfile
import threading
import time
import uuid
from scripts.v51.guest_ssh_qualification import Server
from . import remote_history as h,remote_delivery_qualification as previous,remote_voter as v
from . import remote_voter_lifecycle as lifecycle,remote_voter_scope as scope,remote_voter_export as export
from .evidence import need

DEFAULTS=('m02-above-1000','m03-p4','m03-p65','candidate-explicit-strong-r1','published-v51-legacy-strong-r1')


class Receivers(previous.Receivers):
    def admit_spec(self):
        need(self.spec['family'] in ('M01','M02','M03') and scope.profile(self.spec['profile'])==self.spec['profile'],
             'formal receiver exact declared history')
    def prepare(self):
        super().prepare();self.binding['remoteFormal']=scope.domains.execution(self.binding,scope.FORMAL_EXECUTION);h.runtime.save(self.collected/'binding.json',self.binding)
    def start_service(self,root,node,cp,mode,history,generation):
        need(generation==1,'formal undeclared generation')
        # Launch-loss qualification happens before original observation starts.
        # No stream-loss injection, blocking submit retry or new offered clock is
        # inserted into the unchanged formal workload controller.
        worker=lifecycle.Client(root,node,self.binding,history,target=self.targets[node],discard_launch=node=='node-1',python_context=self.python_context(node))
        self.clients.append(worker);return worker
    def collect_receiver(self,node,own):
        need(node in self.workers and node not in self.exports,'formal collection ownership')
        def admit(meta):export.aggregate([*self.exports.values(),meta])
        self.exports[node]=self.workers[node].collect(self.collected,self.root/'downloads'/node,admit=admit)


def history_names(names):
    names=list(names);plan=h.suite.load()
    need(names and len(names)==len(set(names)) and all(n in plan['histories'] and
         plan['histories'][n]['family'] in ('M01','M02','M03') for n in names),'formal exact history selection')
    return names


def counts(spec):
    plan=spec['profile']
    if spec['family']=='M01':return 1801,180
    return plan['readCount']+(2 if spec['family']=='M03' else 1),plan['setupUpdates']+int(plan['releaseUpdate'])


def run(output,names=DEFAULTS):
    names=history_names(names);root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    source=h.source();began=time.monotonic();done=threading.Event();current=None;stage='private-sshd'
    receipt=dict(status='FAIL',execution=scope.FORMAL_EXECUTION,sourceBinding=source,histories=[],selected=names,
                 sharedPythonCheckout=True,qualifiedMeasurement=False,fullRemoteQualification=False,paidCloud=False)
    def progress(value):
        nonlocal stage
        stage=value;print(json.dumps(dict(history=current,stage=stage,elapsedSeconds=round(time.monotonic()-began,1))),flush=True)
    def beat():
        while not done.wait(60):print(json.dumps(dict(history=current,stage=stage,status='RUNNING',
                                                     elapsedSeconds=round(time.monotonic()-began,1))),flush=True)
    thread=threading.Thread(target=beat,daemon=True);thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix='v52-formal-keys-',dir=h.ROOT/'target') as private,Server(private,root) as server:
            targets={}
            for node in h.topology.NODES:
                alias='gse-v52-'+uuid.uuid4().hex;known=Path(private)/(node+'-known')
                known.write_text(alias+' '+server.host['publicKey']+'\n');known.chmod(0o600)
                targets[node]=dict(host='127.0.0.1',port=server.port,user=server.user,key=str(Path(private)/'client/identity'),knownHosts=str(known),alias=alias)
            receipt['tools']=server.versions
            for current in names:
                owners=[];start=time.monotonic()
                record=dict(history=current,status='FAIL');receipt['histories'].append(record)
                def factory(*args):
                    owner=Receivers(*args,targets=targets);owners.append(owner);return owner
                try:
                    result=h.run(root/current,current,source,progress=progress,receiver_factory=factory)
                    own=owners[0];workers=own.clients;spec=own.spec
                    need(len(workers)==3 and sum(w.launch_lost for w in workers)==1 and all(w.launch_submissions==1 for w in workers),
                         'formal original launch count')
                    need((result['originalReads'],result['originalUpdates'])==counts(spec),'formal original business counts')
                    need(all(w.final['state']=='STOPPED' and w.released and w.endpoint.closed and w.lifecycle.closed and
                         not v.c.process_alive(w.owner_identity['service']) and not v.c.process_alive(w.owner_identity['jvm']) and
                         not Path(w.config['socket']).parent.exists() and all(ch.proc.poll() is not None for ch in w.channels) for w in workers),
                         'formal original owner cleanup')
                    need(all(d.endpoint.closed and sum(c['action']=='install' for c in d.calls)==1 and
                         sum(c['action']=='part' for c in d.calls)==len(own.meta['parts']) for d in own.deliveries) and
                         all(not v.c.process_alive(r['process']) for r in own.bootstraps.values()),'formal delivery count/cleanup')
                    record.update(status='PASS',family=spec['family'],mode=spec['mode'],originalReads=result['originalReads'],
                        originalUpdates=result['originalUpdates'],negativesPerLocation=len(result['result']['negatives']),
                        archiveSha256=result['archiveSha256'],exports={n:dict(bytes=m['bytes'],sha256=m['sha256'],inventory=m['inventory'])
                            for n,m in own.exports.items()},exportBudget=export.aggregate(list(own.exports.values())),
                        stoppedServices=3,stoppedJvms=3)
                except BaseException as error:record['failure']=dict(type=type(error).__name__,message=str(error));raise
                finally:
                    record['elapsedSeconds']=round(time.monotonic()-start,3);h.runtime.save(root/'receipt.json',receipt)
                need(h.source()==source,'formal source changed')
        need(server.process.poll() is not None,'formal sshd cleanup');receipt['status']='PASS';return receipt
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        done.set();thread.join(2);receipt['elapsedSeconds']=round(time.monotonic()-began,3);h.runtime.save(root/'receipt.json',receipt)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');parser.add_argument('--history',action='append')
    args=parser.parse_args();print(json.dumps(run(args.output,args.history or DEFAULTS)),flush=True)
