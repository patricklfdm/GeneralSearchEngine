"""Three persistent SSH voter streams with one lost original update response."""
import argparse
import json
from pathlib import Path
import tempfile
import threading
import time
import uuid
from scripts.v51.guest_ssh_qualification import Server
from . import remote_voter as v,remote_voter_ssh as ssh,remote_voter_qualification as local
from . import remote_voter_ssh_evidence as evidence,remote_history as h
from .evidence import need


class LostResultClient(local.LostResultClient,ssh.Client):pass


class Receivers(local.Receivers):
    def __init__(self,*args,targets):self.targets=targets;super().__init__(*args)
    def prepare(self):
        super().prepare()
        self.binding['remoteVoterTransport']=dict(schema=evidence.SCHEMA,execution=v.scope.domains.execution(self.binding,evidence.EXECUTION),
            nodes={node:ssh.public_target(target) for node,target in self.targets.items()})
        evidence.binding(self.binding['remoteVoterTransport']);h.runtime.save(self.collected/'binding.json',self.binding)
    def start_service(self,root,node,cp,mode,history,generation):
        need(generation==1,'SSH voter restart not qualified')
        return LostResultClient(root,node,self.binding,history,target=self.targets[node])


def run(output):
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False);original=h.source()
    receipt=dict(status='FAIL',execution=evidence.EXECUTION,sourceBinding=original,
        qualifiedMeasurement=False,fullRemoteQualification=False,paidCloud=False,localLaunchAndDelivery=True)
    began=time.monotonic();done=threading.Event();stage='private-sshd';owners=[]
    def progress(value):
        nonlocal stage
        stage=value;print(json.dumps(dict(stage=stage,elapsedSeconds=round(time.monotonic()-began,1))),flush=True)
    def heartbeat():
        while not done.wait(60):print(json.dumps(dict(stage=stage,status='RUNNING',elapsedSeconds=round(time.monotonic()-began,1))),flush=True)
    beat=threading.Thread(target=heartbeat,daemon=True);beat.start()
    try:
        with tempfile.TemporaryDirectory(prefix='v52-voter-keys-',dir=h.ROOT/'target') as private,Server(private,root) as server:
            targets={}
            for node in h.topology.NODES:
                alias='gse-v52-'+uuid.uuid4().hex;known=Path(private)/(node+'-known')
                known.write_text(alias+' '+server.host['publicKey']+'\n');known.chmod(0o600)
                targets[node]=dict(host='127.0.0.1',port=server.port,user=server.user,key=str(Path(private)/'client/identity'),
                                  knownHosts=str(known),alias=alias)
            receipt['tools']=server.versions
            def factory(*args):
                own=Receivers(*args,targets=targets);owners.append(own);return own
            result=h.run(root/'history','candidate-minimum-untimed-smoke',original,progress=progress,receiver_factory=factory)
            owner=owners[0];workers=owner.workers
            need(sum(w.injected and w.recovered for w in workers.values())==1,'SSH voter lost-response cut')
            need(sorted(w.connections for w in workers.values())==[1,1,2] and
                 sorted(w.endpoint.connections for w in workers.values())==[1,1,2],'SSH voter persistent channel/master count')
            need(all(w.agent.returncode==0 and not v.c.process_alive(w.owner_identity['service']) and
                     not v.c.process_alive(w.owner_identity['jvm']) and w.endpoint.closed and
                     all(ch.proc.poll() is not None for ch in w.channels) for w in workers.values()),'SSH voter cleanup incomplete')
            need(h.source()==original,'SSH voter qualification source changed')
            receipt.update(status='PASS',originalReads=result['originalReads'],originalUpdates=result['originalUpdates'],
                negativesPerLocation=len(result['result']['negatives']),archiveSha256=result['archiveSha256'],
                streams={node:w.recorded for node,w in workers.items()},lostUpdateResponseRecovered=True,
                stoppedServices=3,stoppedJvms=3,physicalAndRelocatedReplay=True)
        need(server.process.poll() is not None,'SSH qualification daemon did not stop')
        return receipt
    except BaseException as error:receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:
        done.set();beat.join(2);receipt['elapsedSeconds']=round(time.monotonic()-began,3)
        h.runtime.save(root/'receipt.json',receipt)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args();print(json.dumps(run(a.output)),flush=True)
