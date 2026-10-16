"""Real loopback lifecycle and byte collection, local immutable seed staging."""
import argparse
import json
from pathlib import Path
import tempfile
import threading
import time
import uuid
from scripts.v51.guest_ssh_qualification import Server
from . import remote_voter as v,remote_voter_lifecycle as lifecycle,remote_voter_guest as guest
from . import remote_voter_qualification as local,remote_voter_ssh_qualification as previous
from . import remote_voter_lifecycle_evidence as evidence,remote_history as h
from .evidence import need


class LostResultClient(local.LostResultClient,lifecycle.Client):pass


class Receivers(previous.Receivers):
    def __init__(self,*args,targets):
        self.clients=[];self.exports={};super().__init__(*args,targets=targets)
    def prepare(self):
        super().prepare()
        for root in self.roots.values():root.chmod(0o700)
        self.binding['remoteVoterLifecycle']=guest.EXECUTION;h.runtime.save(self.collected/'binding.json',self.binding)
    def start_service(self,root,node,cp,mode,history,generation):
        need(generation==1,'lifecycle restart not qualified')
        client=LostResultClient(root,node,self.binding,history,target=self.targets[node],discard_launch=node=='node-1')
        self.clients.append(client);return client
    def collect_receiver(self,node,own):
        need(node in self.workers,'lifecycle no successful owner to collect')
        self.exports[node]=self.workers[node].collect(self.collected,self.root/'downloads'/node)
    def finish(self,failure):
        try:super().finish(failure)
        finally:
            errors=[]
            for client in self.clients:
                try:client.close_transport()
                except BaseException as error:errors.append(str(error))
            if errors:raise ValueError('lifecycle transport cleanup failed: '+repr(errors))


def run(output):
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False);expected=h.source();began=time.monotonic()
    receipt=dict(status='FAIL',execution=guest.EXECUTION,sourceBinding=expected,localArtifactAndSeedStaging=True,
                 remoteServiceLifecycle=True,sshEvidenceDownload=True,qualifiedMeasurement=False,fullRemoteQualification=False,paidCloud=False)
    done=threading.Event();stage='private-sshd';owners=[]
    def progress(value):
        nonlocal stage
        stage=value;print(json.dumps(dict(stage=stage,elapsedSeconds=round(time.monotonic()-began,1))),flush=True)
    def beat():
        while not done.wait(60):print(json.dumps(dict(stage=stage,status='RUNNING',elapsedSeconds=round(time.monotonic()-began,1))),flush=True)
    thread=threading.Thread(target=beat,daemon=True);thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix='v52-lifecycle-keys-',dir=h.ROOT/'target') as private,Server(private,root) as server:
            targets={}
            for node in h.topology.NODES:
                alias='gse-v52-'+uuid.uuid4().hex;known=Path(private)/(node+'-known')
                known.write_text(alias+' '+server.host['publicKey']+'\n');known.chmod(0o600)
                targets[node]=dict(host='127.0.0.1',port=server.port,user=server.user,key=str(Path(private)/'client/identity'),knownHosts=str(known),alias=alias)
            receipt['tools']=server.versions
            def factory(*args):
                own=Receivers(*args,targets=targets);owners.append(own);return own
            result=h.run(root/'history','candidate-minimum-untimed-smoke',expected,progress=progress,receiver_factory=factory)
            own=owners[0];workers=list(own.workers.values())
            need(sum(w.launch_lost for w in workers)==1 and all(w.launch_submissions==1 for w in workers),'lifecycle original launch counts')
            need(sum(w.injected and w.recovered for w in workers)==1,'lifecycle original result reconnect')
            need(all(w.final['state']=='STOPPED' and w.released and w.endpoint.closed and w.lifecycle.closed and
                     not v.c.process_alive(w.owner_identity['service']) and not v.c.process_alive(w.owner_identity['jvm']) and
                     not Path(w.config['socket']).parent.exists() and all(ch.proc.poll() is not None for ch in w.channels) for w in workers),
                 'lifecycle cleanup incomplete')
            mutation_results=negatives(own)
            need(h.source()==expected,'lifecycle qualification source changed')
            receipt.update(status='PASS',originalReads=result['originalReads'],originalUpdates=result['originalUpdates'],
                negativesPerLocation=len(result['result']['negatives']),lifecycleNegatives=mutation_results,
                archiveSha256=result['archiveSha256'],lostLaunchReplyRecovered=True,lostUpdateResponseRecovered=True,
                stoppedServices=3,stoppedJvms=3,downloads={node:dict(files=len(meta['members']),bytes=meta['bytes'],sha256=meta['sha256']) for node,meta in own.exports.items()})
        need(server.process.poll() is not None,'lifecycle sshd cleanup')
        return receipt
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        done.set();thread.join(2);receipt['elapsedSeconds']=round(time.monotonic()-began,3);h.runtime.save(root/'receipt.json',receipt)


def negatives(owner):
    """Mutate retained metadata in isolated copies; never touch original history."""
    import shutil
    mutations={
        'missing-lifecycle':lambda p:(p/'lifecycle.json').unlink(),
        'repeated-launch':lambda p:change(p/'lifecycle.json',lambda r:r.update(launchSubmissions=2)),
        'live-service':lambda p:change(p/'lifecycle.json',lambda r:r['collection']['terminal'].update(serviceAlive=True)),
        'changed-exit-owner':lambda p:change(p/'exited.json',lambda r:r['service'].update(pid=r['service']['pid']+1)),
        'changed-collected-bytes':lambda p:(p/'agent.log').write_bytes(b'changed'),
        'missing-export-file':lambda p:(p/'preparation.json').unlink(),
        'missing-lifecycle-binding':None,
    }
    results=[]
    for location in ('evidence','relocated'):
        original=owner.root/location
        for name,mutate in mutations.items():
            target=owner.root/'lifecycle-negatives'/location/name;shutil.copytree(original,target)
            control=target/'node-1-control';config=v.c.read(control/'config.json',v.c.REQUEST_BYTES)
            bound=dict(owner.binding)
            if mutate:mutate(control)
            else:bound.pop('remoteVoterLifecycle')
            h.runtime.save(target/h.bundle.INDEX,h.bundle.members(target))
            try:evidence.validate(target,bound,config,v.digest(v.encoded(config)))
            except (ValueError,FileNotFoundError) as error:results.append(dict(location=location,case=name,status='REJECTED',reason=str(error)))
            else:raise ValueError('lifecycle negative accepted: '+name)
            # Keep small rejection metadata; remove only our disposable copies.
            shutil.rmtree(target)
    h.runtime.save(owner.root/'lifecycle-negatives/results.json',results);return results


def change(path,mutate):
    value=v.c.read(path,v.c.RESPONSE_BYTES);mutate(value);h.runtime.save(path,value)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args();print(json.dumps(run(a.output)),flush=True)
