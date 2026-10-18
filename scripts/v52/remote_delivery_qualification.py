"""Real pinned uploads/bootstrap, persistent voters and portable physical replay."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import threading
import time
import uuid
from scripts.v51.guest_ssh_qualification import Server
from . import remote_history as h,remote_voter as v,remote_voter_lifecycle_qualification as previous
from . import remote_delivery as delivery,remote_delivery_package as package,remote_delivery_evidence as evidence
from .evidence import need,digest,encoded


class Receivers(previous.Receivers):
    def __init__(self,*args,targets):
        self.deliveries=[];self.bootstraps={};self.capsule=None;super().__init__(*args,targets=targets)
    def prepare(self):
        (self.root/'receivers').mkdir(mode=0o700)
        super().prepare()
        self.binding['remoteDelivery']=dict(schema='gse-v52-delivered-receivers-v1',execution=package.execution(self.meta),package=self.meta,
            nodes={node:dict(descriptorSha256=value['descriptorSha256'],receiptSha256=digest(encoded(value))) for node,value in self.bootstraps.items()})
        evidence.selection(self.binding);h.runtime.save(self.collected/'binding.json',self.binding)
    def prepare_receiver(self,node,own,plan,original):
        if self.capsule is None:
            self.capsule,self.meta=package.create(self.producer,self.root/'delivery-source',self.binding)
            shutil.copyfile(self.capsule,self.collected/package.CAPSULE)
        endpoint=self.delivery_client(node,own);self.deliveries.append(endpoint)
        try:value=endpoint.run(self.capsule,discard_part=self.qualify_transport and node=='node-1',discard_install=self.qualify_transport and node=='node-2')
        finally:endpoint.close()
        self.bootstraps[node]=value;self.classpath[node]=self.paths(own,original);return value['answer']
    def delivery_client(self,node,own):
        return delivery.Delivery(self.targets[node],own.parent,node,self.meta)
    def verify_worker(self,worker,own):
        # Files live on the guest. Its fixed entry verifies the delivered bytes;
        # the controller checks loaded paths against the retained package inputs.
        for component in ('core','replication'):
            path=Path(worker.identity[component+'Source'])
            need(path.parent==own/'artifacts' and path.name in self.binding['artifacts'] and
                 h.bundle.sha_file(self.collected/'artifacts'/path.name)==self.binding['artifacts'][path.name],'delivery loaded artifact binding')
        need(worker.identity['readParameters']==self.binding['readParameters'],'delivery public read parameters')
    def finish(self,failure):
        try:super().finish(failure)
        finally:
            for endpoint in self.deliveries:endpoint.close()


def negatives(owner,*,locations=('evidence','relocated')):
    changes={
        'missing-receipt':lambda p:(p/'node-1-delivery.json').unlink(),
        'changed-package-byte':lambda p:change_byte(p/package.CAPSULE),
        'wrong-source':lambda p:change(p/'node-1-delivery.json',lambda r:r['descriptor']['package']['source'].update(source='0'*40)),
        'wrong-receiver-host':lambda p:change(p/'node-1-control/preparation.json',lambda r:r['host'].update(parentInode=1)),
        'wrong-bootstrap-node':lambda p:change(p/'node-1-delivery.json',lambda r:r['answer'].update(node='node-3')),
        'wrong-genesis':lambda p:change_byte(p/'node-1/genesis.gsr'),
        'missing-delivery-binding':None,
    }
    results=[]
    for location in locations:
        evidence.validate(owner.root/location,owner.binding)
        for name,mutate in changes.items():
            root=owner.root/'delivery-negatives'/location/name;shutil.copytree(owner.root/location,root)
            bound=dict(owner.binding)
            if mutate:mutate(root)
            else:bound.pop('remoteDelivery')
            h.runtime.save(root/h.bundle.INDEX,h.bundle.members(root))
            try:evidence.validate(root,bound)
            except (ValueError,FileNotFoundError) as error:results.append(dict(location=location,case=name,status='REJECTED',reason=str(error)))
            else:raise ValueError('delivery negative accepted: '+name)
            shutil.rmtree(root)
    h.runtime.save(owner.root/'delivery-negatives/results.json',results);return results


def change(path,mutate):
    value=v.c.read(path,v.c.REQUEST_BYTES);mutate(value);h.runtime.save(path,value)


def change_byte(path):
    raw=path.read_bytes();path.write_bytes(bytes([raw[0]^1])+raw[1:])


def run(output):
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False);source=h.source();began=time.monotonic()
    receipt=dict(status='FAIL',execution=package.EXECUTION,sourceBinding=source,sharedPythonCheckout=True,
                 localArtifactAndSeedStaging=False,sshDelivery=True,remoteBootstrap=True,qualifiedMeasurement=False,
                 fullRemoteQualification=False,paidCloud=False)
    done=threading.Event();stage='private-sshd';owners=[]
    def progress(value):
        nonlocal stage
        stage=value;print(json.dumps(dict(stage=stage,elapsedSeconds=round(time.monotonic()-began,1))),flush=True)
    def beat():
        while not done.wait(60):print(json.dumps(dict(stage=stage,status='RUNNING',elapsedSeconds=round(time.monotonic()-began,1))),flush=True)
    thread=threading.Thread(target=beat,daemon=True);thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix='v52-delivery-keys-',dir=h.ROOT/'target') as private,Server(private,root) as server:
            targets={}
            for node in h.topology.NODES:
                alias='gse-v52-'+uuid.uuid4().hex;known=Path(private)/(node+'-known')
                known.write_text(alias+' '+server.host['publicKey']+'\n');known.chmod(0o600)
                targets[node]=dict(host='127.0.0.1',port=server.port,user=server.user,key=str(Path(private)/'client/identity'),knownHosts=str(known),alias=alias)
            receipt['tools']=server.versions
            def factory(*args):
                owner=Receivers(*args,targets=targets);owners.append(owner);return owner
            result=h.run(root/'history','candidate-minimum-untimed-smoke',source,progress=progress,receiver_factory=factory)
            own=owners[0];workers=list(own.workers.values())
            need(len(own.deliveries)==3 and all(d.endpoint.closed and
                 sum(call['action']=='install' for call in d.calls)==1 and sum(call['action']=='part' for call in d.calls)==len(own.meta['parts'])
                 for d in own.deliveries),'delivery repeated upload/bootstrap')
            need([d.losses for d in own.deliveries]==[['part'],['install'],[]],'delivery lost reply coverage')
            need(sum(w.launch_lost for w in workers)==1 and sum(w.injected and w.recovered for w in workers)==1,'delivery original voter reply recovery')
            need(all(w.final['state']=='STOPPED' and w.released and w.endpoint.closed and w.lifecycle.closed and
                 not v.c.process_alive(w.owner_identity['service']) and not v.c.process_alive(w.owner_identity['jvm']) and
                 not Path(w.config['socket']).parent.exists() and all(ch.proc.poll() is not None for ch in w.channels) for w in workers),
                 'delivery voter cleanup incomplete')
            need(all(not v.c.process_alive(r['process']) for r in own.bootstraps.values()),'delivery bootstrap still running')
            lifecycle_negatives=previous.negatives(own);delivery_negatives=negatives(own)
            need(h.source()==source,'delivery qualification source changed')
            receipt.update(status='PASS',originalReads=result['originalReads'],originalUpdates=result['originalUpdates'],
                negativesPerLocation=len(result['result']['negatives']),lifecycleNegatives=lifecycle_negatives,deliveryNegatives=delivery_negatives,
                archiveSha256=result['archiveSha256'],packageSha256=own.meta['sha256'],packageBytes=own.meta['bytes'],
                packageFiles=len(own.meta['members']),partsPerNode=len(own.meta['parts']),stoppedServices=3,stoppedJvms=3,
                lostReplies=['upload-part','bootstrap-launch','voter-launch','original-update'],
                bootstrapSubmissions={d.node:sum(c['action']=='install' for c in d.calls) for d in own.deliveries})
        need(server.process.poll() is not None,'delivery sshd cleanup');return receipt
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        done.set();thread.join(2);receipt['elapsedSeconds']=round(time.monotonic()-began,3);h.runtime.save(root/'receipt.json',receipt)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');args=parser.parse_args();print(json.dumps(run(args.output)),flush=True)
