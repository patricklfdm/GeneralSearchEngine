"""Pinned SSH control barriers; an uncertain fault only queries its own receipt."""
import time
from . import remote_partition_guest as guest,remote_voter_lifecycle as lifecycle
from .evidence import need,digest


class Endpoint(lifecycle.Endpoint):protocol=guest


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
