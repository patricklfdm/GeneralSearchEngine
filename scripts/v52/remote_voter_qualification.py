"""Three real local voter services, one original smoke, independent portable replay."""
import argparse
import json
from pathlib import Path
import threading
import time
from . import remote_voter as v, remote_voter_evidence as evidence, remote_history as h
from .evidence import need


class LostResultClient(v.Client):
    """Drop exactly one already-executed update reply, then query the stream."""
    def __init__(self,*args,**kwargs):
        self.injected=False;self.recovered=False
        super().__init__(*args,**kwargs)

    def receive_event(self,row):
        if row['kind']=='RESULT' and row['response']['kind']=='update' and not self.injected:
            self.injected=True
            raise ConnectionError('qualification discarded original update response')
        super().receive_event(row)

    def submit(self,kind,**values):
        first=kind=='update' and not self.injected
        original=super().submit(kind,**values)
        if first:
            self.reader.join(35)
            need(self.injected and not self.reader.is_alive(),'voter lost-result cut not reached')
            self.disconnect();self.connect();self.recovered=True
        return original


class Receivers(h.Receivers):
    def __init__(self,*args):
        super().__init__(*args,worker_factory=self.start_service)
        self.admit_spec()

    def admit_spec(self):need(self.spec['family']=='UNTIMED','voter qualification whole smoke only')

    def start_service(self,root,node,cp,mode,history,generation):
        need(generation==1,'voter service restart not qualified')
        return LostResultClient(root,node,self.binding,history)

    def prepare(self):
        super().prepare()
        self.binding['remoteVoterControl']='local-persistent-voters-v1'
        h.runtime.save(self.collected/'binding.json',self.binding)
        h.runtime.save(self.collected/'controller-domain.json',dict(clock='python-monotonic-ns',
                       process=v.process(v.os.getpid()),session=v.os.urandom(16).hex()))


def run(output):
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False);expected=h.source()
    receipt=dict(status='FAIL',execution='local-persistent-voters-only',sourceBinding=expected,
                 qualifiedMeasurement=False,fullRemoteQualification=False,paidCloud=False)
    started=time.monotonic();done=threading.Event();stage='preparation';owners=[]
    def progress(value):
        nonlocal stage
        stage=value;print(json.dumps(dict(stage=stage,elapsedSeconds=round(time.monotonic()-started,1))),flush=True)
    def heartbeat():
        while not done.wait(60):print(json.dumps(dict(stage=stage,elapsedSeconds=round(time.monotonic()-started,1),status='RUNNING')),flush=True)
    thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
    def factory(*args):
        owner=Receivers(*args);owners.append(owner);return owner
    try:
        result=h.run(root/'history','candidate-minimum-untimed-smoke',expected,progress=progress,receiver_factory=factory)
        owner=owners[0];calls=owner.history
        need(sum(w.injected and w.recovered for w in owner.workers.values())==1,'voter missing/extra dropped update response')
        need(sum(c['kind']=='update' for c in calls)==3,'voter repeated public update')
        original=evidence.validate(owner.collected,owner.binding)
        relocated=evidence.validate(owner.root/'relocated',owner.binding)
        need(original==relocated,'voter relocated message edges changed')
        need(all(w.agent.returncode==0 and not v.c.process_alive(w.owner_identity['service']) and
                 not v.c.process_alive(w.owner_identity['jvm']) for w in owner.workers.values()),'voter live process after cleanup')
        need(h.source()==expected,'voter qualification final source drift')
        receipt.update(status='PASS',originalReads=result['originalReads'],originalUpdates=result['originalUpdates'],
            negativesPerLocation=len(result['result']['negatives']),messageEvidence=original,
            connections={node:w.connections for node,w in owner.workers.items()},lostUpdateResponseRecovered=True,
            independentServices=3,stoppedJvms=3,archiveSha256=result['archiveSha256'])
        return receipt
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        done.set();thread.join(2);receipt['elapsedSeconds']=round(time.monotonic()-started,3)
        h.runtime.save(root/'receipt.json',receipt)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args();print(json.dumps(run(a.output)),flush=True)
