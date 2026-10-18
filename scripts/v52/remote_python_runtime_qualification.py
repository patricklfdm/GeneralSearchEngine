"""Original complete declared histories with helpers delivered over pinned SSH."""
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
from . import remote_formal_qualification as formal,remote_restart_qualification as restart,remote_partition_qualification as partition
from .evidence import need


class Installed:
    def __init__(self,*args,targets,installations,descriptor,payload,java=None):
        self.installations=installations;self.descriptor=descriptor;self.payload=payload
        self.java=java
        super().__init__(*args,targets=targets)
    def python_context(self,node):
        value=self.installations[node]
        result=dict(root=value['root'],descriptorSha256=value['descriptorSha256'])
        if self.java is not None:
            from . import remote_java_evidence as j
            result['java']=j.selection(self.java['installations'][node])
        return result
    def delivery_client(self,node,own):
        return delivery.Delivery(self.targets[node],own.parent,node,self.meta,python_context=self.python_context(node))
    def prepare(self):
        super().prepare()
        self.binding['remotePython']=dict(schema=evidence.SCHEMA,
            descriptorSha256=receiver.digest(receiver.encoded(self.descriptor)),nodes=self.installations)
        h.runtime.save(self.collected/evidence.FILE,self.descriptor)
        (self.collected/evidence.PAYLOAD).write_bytes(self.payload)
        if self.java is not None:
            from . import remote_java_evidence as j
            descriptor=self.java['descriptor']
            self.binding['remoteJava']=dict(schema=j.SCHEMA,descriptorSha256=receiver.digest(receiver.encoded(descriptor)),
                                           nodes=self.java['installations'])
            j.receipts(descriptor,self.binding['remoteJava'],self.binding)
            j.r.verify_archive(self.java['archive'],descriptor)
            h.runtime.save(self.collected/j.FILE,descriptor)
            shutil.copyfile(self.java['archive'],self.collected/j.ARCHIVE)
            j.r.verify_archive(self.collected/j.ARCHIVE,descriptor)
        h.runtime.save(self.collected/'binding.json',self.binding)


class Receivers(Installed,previous.Receivers):pass
class FormalReceivers(Installed,formal.Receivers):pass
class RestartReceivers(Installed,restart.Receivers):pass
class PartitionReceivers(Installed,partition.Receivers):pass


def receiver_type(name):
    spec=h.specification(name)
    if spec['family']=='UNTIMED':return Receivers
    if spec['family'] in ('M01','M02','M03'):return FormalReceivers
    need(spec['family']=='M04' and name in h.recovery.CASES,'Python undeclared whole history')
    return RestartReceivers if name==h.recovery.CASES[0] else PartitionReceivers


def negatives(owner,*,locations=('evidence','relocated')):
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
    for location in locations:
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


def run(output,name='candidate-minimum-untimed-smoke',*,java_runtime=False,transport_losses=True):
    factory_type=receiver_type(name);spec=h.specification(name)
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    source=h.source();began=time.monotonic();done=threading.Event();stage='python-package';owners=[]
    receipt=dict(status='FAIL',execution='loopback-ssh-installed-python-only',sourceBinding=source,history=name,family=spec['family'],
        transportLossInjection=transport_losses,sharedPythonCheckout=False,independentHosts=False,qualifiedMeasurement=False,fullRemoteQualification=False,paidCloud=False)
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
        java=None;java_installers=[]
        if java_runtime:
            from . import remote_java_package as jp,remote_java_ssh as js,remote_java_qualification as jq
            progress('java-package')
            java=dict(descriptor=jp.create(h.ROOT,source,root/'java-package'),archive=str(root/'java-package/runtime.tar.gz'),installations={})
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
                try:installations[node]=endpoint.install(parent,raw,discard_reply=transport_losses and node=='node-1')
                finally:endpoint.close()
                if java is not None:
                    progress('java-install-'+node)
                    endpoint=js.Installer(target,java['descriptor']);java_installers.append(endpoint)
                    try:java['installations'][node]=endpoint.install(parent,java['archive'],discard_reply=transport_losses and node=='node-1')
                    finally:endpoint.close()
            if java is not None:
                from .remote_java_evidence import selection
                context=dict(root=installations['node-1']['root'],descriptorSha256=installations['node-1']['descriptorSha256'],
                             java=selection(java['installations']['node-1']))
                jq.probes(context,root/'private-python/node-1',root)
            def factory(*args):
                owner=factory_type(*args,targets=targets,installations=installations,descriptor=descriptor,payload=raw,java=java);owner.qualify_transport=transport_losses;owner.allow_control_download=transport_losses
                owners.append(owner);return owner
            result=h.run(root/'history',name,source,progress=progress,receiver_factory=factory)
            own=owners[0];workers=own.clients
            need([i.calls for i in installers]==([['install','verify'],['install'],['install']] if transport_losses else [['install']]*3) and all(i.closed for i in installers),
                 'Python installation resubmitted/transport leaked')
            is_restart=factory_type is RestartReceivers;count=4 if is_restart else 3
            need(len(workers)==count and sum(w.launch_lost for w in workers)==int(transport_losses) and all(w.launch_submissions==1 for w in workers),
                 'Python original voter recovery')
            need(sum(bool(getattr(w,'injected',False) and getattr(w,'recovered',False)) for w in workers)==int(transport_losses and (spec['family']=='UNTIMED' or factory_type is PartitionReceivers)),
                 'Python original result recovery')
            expected=(11,3) if spec['family']=='UNTIMED' else (4,4) if spec['family']=='M04' else formal.counts(spec)
            need((result['originalReads'],result['originalUpdates'])==expected,'Python unchanged whole-history counts')
            need(all(w.final['state']==('CRASHED' if is_restart and w is own.crashed else 'STOPPED') and w.released and w.endpoint.closed and w.lifecycle.closed and
                 not v.c.process_alive(w.owner_identity['service']) and not v.c.process_alive(w.owner_identity['jvm']) and
                 not Path(w.config['socket']).parent.exists() and all(ch.proc.poll() is not None for ch in w.channels) for w in workers),
                 'Python owned-process cleanup')
            need(all(d.endpoint.closed and sum(c['action']=='install' for c in d.calls)==1 and
                 sum(c['action']=='part' for c in d.calls)==len(own.meta['parts']) for d in own.deliveries) and
                 all(not v.c.process_alive(r['process']) for r in own.bootstraps.values()),'Python bootstrap cleanup')
            for node,value in installations.items():
                receiver.installed(Path(value['root']),descriptor)
                need(not (Path(value['root'])/'files/.git').exists(),'Python receiver contains Git checkout')
            locations=('evidence','relocated' if spec['family']=='UNTIMED' else 'portable/relocated')
            if java is not None:
                need([i.calls for i in java_installers]==([['install','verify'],['install'],['install']] if transport_losses else [['install']]*3) and all(i.closed for i in java_installers),
                     'Java installation resubmitted/transport leaked')
                receipt.update(javaInstallations=java['installations'],javaDescriptorSha256=receiver.digest(receiver.encoded(java['descriptor'])),
                               javaNegatives=jq.negatives(own,locations=locations),ambientJavaUsed=False)
            if is_restart:
                need(own.crashed.crash_submissions==1 and (not transport_losses or own.crashed.terminal_lost and own.crashed.terminal_query is not None),'Python retained restart original terminal')
                receipt['faultNegatives']=restart.negatives(own)
            elif factory_type is PartitionReceivers:
                controllers=list(own.controls.values())
                need(len(controllers)==3 and [c.losses for c in controllers]==([['cut'],['heal'],[]] if transport_losses else [[],[],[]]) and
                     all([r['request']['operation'] for r in c.calls if r['action']=='apply']==['cut','heal'] for c in controllers) and
                     not own.partition_record['cleanup'],'Python original partition transitions')
                need(all(c.endpoint.closed and all(ch.proc.poll() is not None for ch in c.endpoint.streams) and
                     all(not v.c.process_alive(p) for p in c.endpoint.owners) for c in controllers),'Python partition control cleanup')
                receipt['faultNegatives']=partition.negatives(own)
                receipt['selectedBasisNegatives']=partition.basis_negatives(own)
            receipt.update(originalReads=result['originalReads'],originalUpdates=result['originalUpdates'],
                negativesPerLocation=len(result['result']['negatives']),pythonNegatives=negatives(own,locations=locations),
                deliveryNegatives=previous.negatives(own,locations=locations),
                lifecycleNegatives=lifecycle.negatives(own,locations=locations) if spec['family']=='UNTIMED' or factory_type is PartitionReceivers else [],
                package=built,installations=installations,archiveSha256=result['archiveSha256'],
                stoppedServices=count,stoppedJvms=count,lostInstallReplyRecovered=transport_losses)
            need(h.source()==source,'Python source changed during qualification')
        need(server.process.poll() is not None,'Python sshd cleanup');receipt['status']='PASS';return receipt
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        done.set();thread.join(2);receipt['elapsedSeconds']=round(time.monotonic()-began,3);h.runtime.save(root/'receipt.json',receipt)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');parser.add_argument('--history',default='candidate-minimum-untimed-smoke');args=parser.parse_args();print(json.dumps(run(args.output,args.history)),flush=True)
