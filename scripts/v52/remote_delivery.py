"""One source capsule, pinned upload receipts and one detached bootstrap per node."""
import base64
from copy import deepcopy
from pathlib import Path
import time
import uuid
from . import remote_delivery_package as p,remote_delivery_guest as guest,remote_delivery_evidence as evidence
from . import remote_voter_lifecycle as lifecycle
from .evidence import need,encoded,digest


class Endpoint(lifecycle.Endpoint):
    protocol=guest
    python_entry='delivery'


def observed(value,descriptor):
    need(type(value) is dict and set(value)=={'descriptorSha256','state','completedParts','started','terminal','alive'} and
         value['descriptorSha256']==digest(encoded(descriptor)) and type(value['completedParts']) is int and
         0<=value['completedParts']<=len(descriptor['package']['parts']) and type(value['alive']) is bool and
         value['state'] in ('UPLOADING','READY','STARTING','RUNNING','EXITING','SUCCEEDED','FAILED','UNCERTAIN'),'delivery observation fields')
    started=value['started'];terminal=value['terminal']
    if started:
        need(type(started) is dict and set(started)=={'descriptorSha256','process'} and started['descriptorSha256']==value['descriptorSha256'],
             'delivery observed worker identity');p.c.validate_process(started['process'],descriptor['host'])
    need(started or not value['alive'],'delivery live worker missing identity')
    if terminal:
        need(started and type(terminal) is dict and terminal['descriptorSha256']==value['descriptorSha256'] and
             terminal['process']==started['process'] and terminal['state'] in ('SUCCEEDED','FAILED'),'delivery observed terminal identity')
        expected={'descriptorSha256','process','state'}|({'receipt'} if terminal['state']=='SUCCEEDED' else {'error'})
        need(set(terminal)==expected,'delivery terminal fields')
        if terminal['state']=='SUCCEEDED':
            evidence.receipt(terminal['receipt'],descriptor);need(terminal['receipt']['process']==started['process'],'delivery bootstrap worker changed')
        else:need(terminal['error']=='INSTALL_FAILED','delivery terminal error code')
    if value['state'] in ('READY','STARTING','RUNNING','EXITING','SUCCEEDED','FAILED'):
        need(value['completedParts']==len(descriptor['package']['parts']),'delivery incomplete upload')
    if value['state'] in ('SUCCEEDED','FAILED'):
        need(terminal and terminal['state']==value['state'] and not value['alive'],'delivery worker not terminal')
    return value


class Delivery:
    def __init__(self,target,parent,node,meta,*,python_context=None):
        self.endpoint=Endpoint(target,p.h.ROOT,python_context=python_context);self.parent=Path(parent);self.value=None;self.calls=[];self.losses=[]
        self.node=node;self.meta=deepcopy(meta);self.discarded=set()
    def close(self):self.endpoint.close()
    def exchange(self,action,payload=None):
        self.calls.append(dict(action=action,index=payload.get('index') if type(payload) is dict else None))
        if action=='begin':root,value=self.parent,self.value
        else:root,value=guest.store_for(self.value),dict(descriptorSha256=digest(encoded(self.value)),request=payload)
        answer=self.endpoint.exchange(action,root,value,time.monotonic()+30)
        need(type(answer) is dict and set(answer)=={'descriptorSha256','host','answer'} and
             answer['descriptorSha256']==digest(encoded(self.value)) and answer['host']==self.value['host'],'delivery reply binding')
        return observed(answer['answer'],self.value)
    def once(self,action,payload=None,*,discard=False):
        def submit():
            answer=self.exchange(action,payload)
            if discard:
                self.endpoint.disconnect();self.discarded.add(action);raise ConnectionError('qualification discarded delivery reply')
            return answer
        return lifecycle.original_launch(submit,lambda:self.exchange('query'),lost=lambda:self.losses.append(action))
    def run(self,archive,*,discard_part=False,discard_install=False):
        pin=self.endpoint.exchange('probe',self.parent,None,time.monotonic()+30)
        need(type(pin) is dict and set(pin)=={'host'},'delivery parent probe');p.host.validate_pin(pin['host'])
        self.value=dict(schema='gse-v52-receiver-delivery-v1',execution=p.EXECUTION,parent=str(self.parent),host=pin['host'],
                        node=self.node,session=uuid.uuid4().hex,package=self.meta);p.descriptor(self.value)
        p.verify_archive(archive,self.meta)
        first=self.once('begin');need(first['state']=='UPLOADING' and first['completedParts']==0,'delivery fresh destination required')
        with Path(archive).open('rb') as stream:
            for index,row in enumerate(self.meta['parts']):
                raw=stream.read(row['bytes']);need(len(raw)==row['bytes'] and digest(raw)==row['sha256'],'delivery controller source changed')
                answer=self.once('part',dict(index=index,data=base64.b64encode(raw).decode('ascii')),discard=discard_part and index==0)
                need(answer['state'] in ('UPLOADING','READY') and answer['completedParts']==index+1,'delivery chunk not retained')
            need(stream.read(1)==b'','delivery source trailing bytes')
        answer=self.once('install',discard=discard_install);until=time.monotonic()+150
        while answer['state'] in ('STARTING','RUNNING','EXITING'):
            need(time.monotonic()<until,'delivery original bootstrap observation exhausted; do not replay')
            time.sleep(.1);answer=self.exchange('query')
        need(answer['state']=='SUCCEEDED','delivery bootstrap failed/uncertain: '+answer['state'])
        return evidence.receipt(answer['terminal']['receipt'],self.value)
