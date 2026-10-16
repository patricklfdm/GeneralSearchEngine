"""Pinned SSH control barriers; an uncertain fault only queries its own receipt."""
import time
from pathlib import Path
from types import SimpleNamespace
from . import remote_partition_guest as guest,remote_voter_lifecycle as lifecycle
from . import remote_voter_ssh as stream
from .evidence import need,digest


class Endpoint(stream.Endpoint):
    protocol=SimpleNamespace(LAUNCH=guest.STREAM_LAUNCH)
    def __init__(self,*args):
        super().__init__(*args);self.channel=None;self.control=None;self.sha=None;self.streams=[];self.owners=[]
    def answer(self):
        value=guest.v.receive(self.channel.reader)
        if value is None:raise ConnectionError('partition original control channel ended')
        if value.get('schema')==guest.ERROR_SCHEMA:
            need(set(value)=={'schema','code'},'partition error envelope');raise lifecycle.Rejected(value['code'])
        return value
    def exchange(self,action,root,value,deadline):
        need(action in guest.ACTIONS and type(value) is dict and set(value)=={'configSha256','request'} and
             not self.closed and 0<deadline-time.monotonic()<=300,'partition channel request')
        need(self.control is None or (root==self.control and value['configSha256']==self.sha),'partition channel identity changed')
        need(stream.ssh.ssh_args(self.target)==self.args and all(Path(self.target[k]).read_bytes()==b for k,b in self.pins.items()),
             'partition channel target/credentials changed')
        try:
            if self.channel is None:
                need(len(self.streams)<4,'partition original control channels exhausted')
                self.control=root;self.sha=value['configSha256'];self.channel=self.open(root,self.sha,deadline);self.streams.append(self.channel)
                ready=self.answer()
                need(set(ready)=={'ready','configSha256','host','process'} and ready['ready'] is True and ready['configSha256']==self.sha,
                     'partition prepared channel identity')
                self.host=ready['host'];guest.v.host.validate_pin(self.host)
                guest.v.c.validate_process(ready['process'],self.host);self.owners.append(ready['process'])
            self.channel.settimeout(deadline-time.monotonic())
            guest.v.send(self.channel,dict(action=action,value=value));answer=self.answer()
            need(answer['configSha256']==self.sha and answer['host']==self.host,'partition channel response identity')
            return answer
        except BaseException:self.disconnect();raise
    def disconnect(self):
        try:
            if self.channel:self.channel.finish();self.channel=None
        finally:super().disconnect()


def observed(value,config,command):
    need(type(value) is dict and set(value)=={'state','request','result','currentSha256'} and value['request']==command and
         value['state']=='APPLIED','partition original transition incomplete')
    guest.outcome(value['result'],config,command)
    need(value['currentSha256']==digest(guest.body(command)),'partition control no longer matches original transition')
    return value


class Controller:
    def __init__(self,worker,target):
        self.worker=worker;self.endpoint=Endpoint(target,guest.v.h.ROOT);self.calls=[];self.losses=[];self.records=[]
    def warm(self):
        answer=self.exchange('query',dict(operation='cleanup',target=None))
        need(answer==dict(state='NOT_ISSUED',request=dict(operation='cleanup',target=None),result=None,currentSha256=None),
             'partition fresh control required')
    def exchange(self,action,command):
        self.calls.append(dict(action=action,request=command))
        answer=self.endpoint.exchange(action,self.worker.control,dict(configSha256=self.worker.sha,request=command),time.monotonic()+30)
        need(type(answer) is dict and set(answer)=={'configSha256','host','answer'} and answer['configSha256']==self.worker.sha and
             answer['host']==self.worker.config['host'],'partition response binding')
        return answer['answer']
    def transition(self,command,*,discard=False):
        guest.request(command);start=time.monotonic_ns()
        def submit():
            answer=self.exchange('apply',command)
            if discard:
                self.endpoint.disconnect();raise ConnectionError('qualification discarded original partition reply')
            return answer
        def lost():self.losses.append(command['operation'])
        answer=lifecycle.original_launch(submit,lambda:self.exchange('query',command),lost=lost)
        observed(answer,self.worker.config,command)
        result=dict(node=self.worker.node,request=command,startNanos=start,endNanos=time.monotonic_ns(),
                    replyLost=command['operation'] in self.losses,answer=answer)
        self.records.append(result);return result
    def close(self):self.endpoint.close()
