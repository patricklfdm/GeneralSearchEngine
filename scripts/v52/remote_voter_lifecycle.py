"""Controller for fixed SSH service lifecycle and stopped evidence export.

Receiver artifact/seed staging remains local. No local service PID ownership is
inferred from an SSH process; only the authenticated guest observes its processes.
"""
import base64
import math
from pathlib import Path
import shutil
import tarfile
import time
from . import remote_voter as v,remote_voter_ssh as stream,remote_voter_guest as guest
from . import remote_voter_lifecycle_evidence as evidence
from .evidence import need,encoded,digest,strict


class Rejected(ValueError):
    retryable=False
    def __init__(self,code):
        need(code in guest.ERRORS,'lifecycle unknown error code');self.code=code
        super().__init__('V5.2 voter lifecycle rejected: '+code)


class Endpoint(stream.Endpoint):
    protocol=guest
    def exchange(self,action,root,value,deadline):
        need(action in self.protocol.ACTIONS and not self.closed,'lifecycle action/session')
        need(type(deadline) in (int,float) and math.isfinite(deadline) and 0<deadline-time.monotonic()<=300,'lifecycle exchange deadline')
        need(stream.ssh.ssh_args(self.target)==self.args and all(Path(self.target[k]).read_bytes()==b for k,b in self.pins.items()),
             'lifecycle SSH target/credentials changed')
        remote=['python3','-I','-c',self.protocol.LAUNCH,str(self.checkout),action,str(v.host.path(str(root)))]
        try:
            if self.master is None:
                self.master=stream.ssh.master.Master(self.args,self.private.name,float('inf'),None,connect_deadline=deadline);self.connections+=1
            raw=self.master.exchange(remote,b'' if value is None else encoded(value),deadline,
                                     maximum=v.c.RESPONSE_BYTES,request_maximum=v.c.REQUEST_BYTES)
        except BaseException:self.disconnect();raise
        result=strict(raw)
        if type(result) is dict and result.get('schema')==self.protocol.ERROR_SCHEMA:
            need(set(result)=={'schema','code'},'lifecycle error envelope');raise Rejected(result['code'])
        return result


def original_launch(start,query,*,lost=lambda:None):
    """Only uncertain transport loss may observe the original consumed launch."""
    try:return start()
    except stream.ssh.transport.ProcessError as error:
        if not error.retryable:raise
        lost();return query()
    except (TimeoutError,ConnectionError):lost();return query()


class Client(stream.Client):
    def __init__(self,root,node,binding,history,*,target,discard_launch=False,generation=1):
        need(binding.get('remoteVoterLifecycle')==guest.EXECUTION and
             binding['remoteVoterTransport']['nodes'][node]==stream.public_target(target),'lifecycle target binding')
        self.initialize(root,node,history,generation)
        self.endpoint=stream.Endpoint(target,v.h.ROOT);self.lifecycle=Endpoint(target,v.h.ROOT)
        self.channels=[];self.active_stream=None;self.recorded=[];self.config=None;self.sha=None
        self.final=None;self.launch_lost=False;self.discard_launch=discard_launch;self.launch_submissions=0;self.released=False
        try:
            probe=self.lifecycle.exchange('probe',self.root,None,time.monotonic()+30)
            need(type(probe) is dict and set(probe)=={'host'},'lifecycle probe response')
            value=dict(node=node,binding=binding,session=v.os.urandom(16).hex(),host=v.host.validate_pin(probe['host']))
            if 'remoteRestart' in binding:value['generation']=generation
            else:need(generation==1,'lifecycle undeclared generation')
            prepared=self.lifecycle.exchange('prepare',self.root,value,time.monotonic()+30)
            need(type(prepared) is dict and set(prepared)=={'config'},'lifecycle prepare response')
            self.config=prepared['config'];evidence.configuration(self.config,value,str(self.root))
            self.sha=digest(encoded(self.config))
            def submit():
                self.launch_submissions+=1;answer=self.control_call('start')
                if discard_launch:
                    self.lifecycle.disconnect();raise ConnectionError('qualification discarded original launch reply')
                return answer
            observed=original_launch(submit,lambda:self.control_call('query'),lost=self.lost_launch)
            self.await_state(observed,{'READY'},40)
            self.connect()
        except BaseException:
            try:self.abort()
            finally:self.lifecycle.close()
            raise

    def lost_launch(self):self.launch_lost=True

    def control_call(self,action,request=None):
        result=self.lifecycle.exchange(action,self.control,dict(configSha256=self.sha,request=request),time.monotonic()+30)
        need(type(result) is dict and set(result)=={'configSha256','host','answer'} and
             result['configSha256']==self.sha and result['host']==self.config['host'],'lifecycle response binding')
        return result['answer']

    def await_state(self,observed,states,seconds):
        deadline=time.monotonic()+seconds
        while True:
            evidence.observation(observed,self.config,self.sha)
            if observed['state'] in states:return observed
            need(observed['state'] not in ('FAILED','UNCERTAIN','PREPARED','STOPPED','CRASHED'),'lifecycle original service failed: '+observed['state'])
            need(time.monotonic()<deadline,'lifecycle service transition timeout; launch remains consumed')
            time.sleep(.1);observed=self.control_call('query')

    def observe_identity(self):
        seen=self.control_call('query');evidence.observation(seen,self.config,self.sha)
        need(seen['state']=='READY','lifecycle voter unavailable');return seen['identity']

    def wait_stopped(self):
        self.final=self.await_state(self.control_call('query'),{'STOPPED'},15)
        need(self.final['identity']==self.owner_identity,'lifecycle stopped process changed')

    def stop(self):
        # Stream metadata is controller evidence, written into the downloaded
        # collection, never by reaching into a guest directory from this client.
        v.Client.stop(self)

    def abort(self):
        try:
            self.disconnect()
            if self.config is not None and self.sha is not None and self.final is None:
                seen=self.control_call('abort');evidence.observation(seen,self.config,self.sha)
                self.final=self.await_state(seen,{'STOPPED','FAILED','CRASHED'},15)
        finally:self.endpoint.close()

    def collect(self,destination,staging):
        need(self.final is not None and self.final['state']=='STOPPED','lifecycle controller collection before stop')
        meta=self.control_call('collect');evidence.manifest(meta,self.config,self.sha)
        staging=Path(staging);staging.mkdir(parents=True,exist_ok=False);archive=staging/'receiver.tar.gz'
        with archive.open('xb') as output:
            for offset in range(0,meta['bytes'],guest.CHUNK):
                answer=self.control_call('chunk',dict(sha256=meta['sha256'],offset=offset))
                output.write(decode_chunk(answer,meta,offset))
        need(archive.stat().st_size==meta['bytes'] and v.h.bundle.sha_file(archive)==meta['sha256'],'lifecycle downloaded archive hash')
        unpacked=unpack_export(archive,staging/'unpacked',meta)
        need(v.h.bundle.inventory(unpacked)==meta['members'],'lifecycle downloaded inventory')
        for path in unpacked.iterdir():
            if path.name==v.h.bundle.INDEX:continue
            target=Path(destination)/path.name;need(not target.exists() and not target.is_symlink(),'lifecycle destination occupied')
            if path.is_dir():shutil.copytree(path,target)
            else:shutil.copyfile(path,target)
        control=Path(destination)/v.scope.control_name(self.node,self.generation)
        self.record_stream(destination)
        v.c.write_once(control/'lifecycle.json',dict(schema=guest.SCHEMA,execution=guest.EXECUTION,configSha256=self.sha,
            launchSubmissions=self.launch_submissions,launchReplyLost=self.launch_lost,collection=meta),v.c.RESPONSE_BYTES)
        need(self.control_call('release')==dict(released=True),'lifecycle socket cleanup');self.released=True
        return meta

    def stream_record(self):
        return dict(schema='gse-v52-voter-ssh-streams-v1',target=stream.public_target(self.endpoint.target),
                    configSha256=self.sha,channels=self.recorded)

    def record_stream(self,destination):
        v.c.write_once(Path(destination)/v.scope.control_name(self.node,self.generation)/'ssh-streams.json',self.stream_record())

    def close_transport(self):
        try:
            if self.final and self.final['state'] in ('STOPPED','FAILED','CRASHED') and not self.released:
                need(self.control_call('release')==dict(released=True),'lifecycle socket cleanup');self.released=True
        finally:
            try:self.endpoint.close()
            finally:self.lifecycle.close()


def decode_chunk(value,meta,offset):
    need(type(value) is dict and set(value)=={'sha256','offset','data'} and value['sha256']==meta['sha256'] and
         type(value['offset']) is int and value['offset']==offset and type(value['data']) is str and
         len(value['data'])<=4*((guest.CHUNK+2)//3),'lifecycle chunk response')
    data=base64.b64decode(value['data'],validate=True)
    need(len(data)==min(guest.CHUNK,meta['bytes']-offset),'lifecycle chunk length');return data


def unpack_export(archive,target,meta):
    # Verify the declared expansion against the already bounded remote manifest
    # BEFORE the generic extractor allocates/writes any member bodies.
    with tarfile.open(archive,'r|gz',tarinfo=v.h.bundle.ClosedTarInfo,encoding='ascii',errors='strict') as source:
        first=source.next()
        need(first is not None and first.name==v.h.bundle.INDEX and first.isfile() and
             0<first.size<=v.c.RESPONSE_BYTES,'lifecycle archive first inventory')
        with source.extractfile(first) as stream:raw=stream.read(v.c.RESPONSE_BYTES+1)
        need(len(raw)==first.size and strict(raw)==meta['members'],'lifecycle archive declared inventory')
    return v.h.bundle.unpack(archive,target)
