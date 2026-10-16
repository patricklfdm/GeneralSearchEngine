"""Original whole smoke history with every helper delivered over pinned SSH."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import threading
import time
import uuid
from scripts.v51.guest_ssh_qualification import Server
from . import remote_history as h, remote_voter as v, remote_delivery as delivery
from . import remote_delivery_qualification as previous, remote_voter_lifecycle_qualification as lifecycle
from . import remote_python_package as package, remote_python_receiver as receiver, remote_python_ssh as ssh
from . import remote_python_runtime_evidence as evidence
from .evidence import need


class Receivers(previous.Receivers):
    def __init__(self,*args,targets,installations,descriptor,payload):
        self.installations=installations;self.descriptor=descriptor;self.payload=payload
        super().__init__(*args,targets=targets)
    def context(self,node):
        value=self.installations[node]
        return dict(root=value['root'],descriptorSha256=value['descriptorSha256'])
    def delivery_client(self,node,own):
        return delivery.Delivery(self.targets[node],own.parent,node,self.meta,python_context=self.context(node))
    def prepare(self):
        super().prepare()
        self.binding['remotePython']=dict(schema=evidence.SCHEMA,
            descriptorSha256=receiver.digest(receiver.encoded(self.descriptor)),nodes=self.installations)
        h.runtime.save(self.collected/evidence.FILE,self.descriptor)
        (self.collected/evidence.PAYLOAD).write_bytes(self.payload)
        h.runtime.save(self.collected/'binding.json',self.binding)
    def start_service(self,root,node,cp,mode,history,generation):
        need(generation==1,'Python receiver undeclared generation')
        client=lifecycle.LostResultClient(root,node,self.binding,history,target=self.targets[node],
            discard_launch=node=='node-1',python_context=self.context(node))
        self.clients.append(client);return client


def negatives(owner):
    cases={
        'changed-python-payload':(lambda p:previous.change_byte(p/evidence.PAYLOAD),'Python capsule payload changed'),
        'missing-python-payload':(lambda p:(p/evidence.PAYLOAD).unlink(),'Python retained payload length/type'),
        'missing-voter-runtime':(lambda p:(p/'node-1-control/python-runtime.json').unlink(),None),
        'missing-bootstrap-runtime':(lambda p:(p/'node-2-python-bootstrap.json').unlink(),None),
        'changed-capsule-source':(lambda p:previous.change(p/evidence.FILE,lambda r:r['source'].update(source='0'*40)), 'Python retained source changed'),
        'wrong-voter-process':(lambda p:previous.change(p/'node-1-control/python-runtime.json',lambda r:r['process'].update(pid=1)), 'Python retained runtime identity'),
        'fallback-to-checkout':(lambda p:previous.change(p/'node-1-control/python-runtime.json',lambda r:r['selection'].update(root=str(h.ROOT))), 'Python retained runtime identity'),
        'site-enabled':(lambda p:previous.change(p/'node-1-control/python-runtime.json',lambda r:r.update(noSite=False)), 'Python retained runtime identity'),
        'wrong-bootstrap-entry':(lambda p:previous.change(p/'node-1-python-bootstrap.json',lambda r:r['process'].update(entry='gse-v52-voter')), 'Python retained runtime identity'),
    }
    results=[]
    for location in ('evidence','relocated'):
        evidence.validate(owner.root/location,owner.binding)
        for name,(mutate,reason) in cases.items():
            root=owner.root/'python-negatives'/location/name;shutil.copytree(owner.root/location,root)
            mutate(root);h.runtime.save(root/h.bundle.INDEX,h.bundle.members(root))
            try:evidence.validate(root,owner.binding)
            except (ValueError,FileNotFoundError) as error:
                need(reason is None and isinstance(error,FileNotFoundError) or str(error)==reason,'Python unrelated negative: '+name+': '+str(error))
                results.append(dict(location=location,case=name,status='REJECTED',reason=str(error)))
            else:raise ValueError('Python negative accepted: '+name)
            shutil.rmtree(root)
    h.runtime.save(owner.root/'python-negatives/results.json',results);return results


def run(output):
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    source=h.source();began=time.monotonic();done=threading.Event();stage='python-package';owners=[]
    receipt=dict(status='FAIL',execution='loopback-ssh-installed-python-only',sourceBinding=source,
        sharedPythonCheckout=False,independentHosts=False,qualifiedMeasurement=False,fullRemoteQualification=False,paidCloud=False)
    def progress(value):
        nonlocal stage
        stage=value;print(json.dumps(dict(stage=stage,elapsedSeconds=round(time.monotonic()-began,1))),flush=True)
    def beat():
        while not done.wait(60):print(json.dumps(dict(stage=stage,status='RUNNING',elapsedSeconds=round(time.monotonic()-began,1))),flush=True)
    thread=threading.Thread(target=beat,daemon=True);thread.start()
    try:
        built=package.create(h.ROOT,root/'python-package')
        descriptor=receiver.decode((root/'python-package/descriptor.json').read_bytes())
        raw=(root/'python-package/payload.json').read_bytes()
        need(built['source']==source,'Python controller source changed')
        (root/'private-python').mkdir(mode=0o700)
        with tempfile.TemporaryDirectory(prefix='v52-python-keys-',dir=h.ROOT/'target') as private,Server(private,root) as server:
            targets={};installations={};installers=[]
            for node in h.topology.NODES:
                alias='gse-v52-'+uuid.uuid4().hex;known=Path(private)/(node+'-known')
                known.write_text(alias+' '+server.host['publicKey']+'\n');known.chmod(0o600)
                target=dict(host='127.0.0.1',port=server.port,user=server.user,key=str(Path(private)/'client/identity'),knownHosts=str(known),alias=alias)
                targets[node]=target;parent=root/'private-python'/node;parent.mkdir(mode=0o700)
                endpoint=ssh.Installer(target,descriptor);installers.append(endpoint)
                progress('python-install-'+node)
                try:installations[node]=endpoint.install(parent,raw,discard_reply=node=='node-1')
                finally:endpoint.close()
            def factory(*args):
                owner=Receivers(*args,targets=targets,installations=installations,descriptor=descriptor,payload=raw);owners.append(owner);return owner
            result=h.run(root/'history','candidate-minimum-untimed-smoke',source,progress=progress,receiver_factory=factory)
            own=owners[0];workers=own.clients
            need([i.calls for i in installers]==[['install','verify'],['install'],['install']] and all(i.closed for i in installers),
                 'Python installation resubmitted/transport leaked')
            need(len(workers)==3 and sum(w.launch_lost for w in workers)==1 and all(w.launch_submissions==1 for w in workers) and
                 sum(w.injected and w.recovered for w in workers)==1,'Python original voter recovery')
            need(all(w.final['state']=='STOPPED' and w.released and w.endpoint.closed and w.lifecycle.closed and
                 not v.c.process_alive(w.owner_identity['service']) and not v.c.process_alive(w.owner_identity['jvm']) and
                 not Path(w.config['socket']).parent.exists() and all(ch.proc.poll() is not None for ch in w.channels) for w in workers),
                 'Python owned-process cleanup')
            need(all(d.endpoint.closed and sum(c['action']=='install' for c in d.calls)==1 for d in own.deliveries) and
                 all(not v.c.process_alive(r['process']) for r in own.bootstraps.values()),'Python bootstrap cleanup')
            for node,value in installations.items():
                receiver.installed(Path(value['root']),descriptor)
                need(not (Path(value['root'])/'files/.git').exists(),'Python receiver contains Git checkout')
            receipt.update(status='PASS',originalReads=result['originalReads'],originalUpdates=result['originalUpdates'],
                negativesPerLocation=len(result['result']['negatives']),pythonNegatives=negatives(own),
                deliveryNegatives=previous.negatives(own),lifecycleNegatives=lifecycle.negatives(own),
                package=built,installations=installations,archiveSha256=result['archiveSha256'],
                stoppedServices=3,stoppedJvms=3,lostInstallReplyRecovered=True)
            need(h.source()==source,'Python source changed during qualification')
        need(server.process.poll() is not None,'Python sshd cleanup');return receipt
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        done.set();thread.join(2);receipt['elapsedSeconds']=round(time.monotonic()-began,3);h.runtime.save(root/'receipt.json',receipt)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');args=parser.parse_args();print(json.dumps(run(args.output)),flush=True)
