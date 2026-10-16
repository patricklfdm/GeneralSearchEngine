"""Pinned persistent per-voter SSH streams. Local launch and delivery only."""
import os
from pathlib import Path
import select
import shlex
import signal
import subprocess
import threading
import time
from . import remote_ssh as ssh,remote_voter as voter,remote_voter_relay as relay
from .evidence import need,digest


class Rejected(ValueError):
    retryable=False
    def __init__(self,code):
        need(code in relay.ERRORS,'SSH voter rejection code');self.code=code
        super().__init__('V5.2 SSH voter relay rejected: '+code)


class Reader:
    def __init__(self,stream):self.stream=stream;self.buffer=bytearray();self.first=True
    def readline(self,limit):
        need(type(limit) is int and 0<limit<=voter.FRAME+1,'SSH stream line bound')
        while True:
            at=self.buffer.find(b'\n');count=at+1 if at>=0 else 0
            if count or len(self.buffer)>=limit:
                count=min(count or limit,limit);raw=bytes(self.buffer[:count]);del self.buffer[:count]
                if self.first and raw.endswith(b'\n'):
                    self.first=False;value=voter.strict(raw)
                    if type(value) is dict and value.get('schema')==relay.ERROR_SCHEMA:
                        need(set(value)=={'schema','code'},'SSH voter error envelope');raise Rejected(value['code'])
                return raw
            deadline=self.stream.read_deadline
            remaining=None if deadline is None else deadline-time.monotonic()
            if remaining is not None and remaining<=0:raise TimeoutError('SSH stream handshake deadline')
            ready,_,_=select.select([self.stream.proc.stdout],[],[],remaining)
            if not ready:raise TimeoutError('SSH stream handshake deadline')
            try:chunk=os.read(self.stream.proc.stdout.fileno(),min(16384,limit-len(self.buffer)))
            except BlockingIOError:continue
            if not chunk:
                if self.buffer:raw=bytes(self.buffer);self.buffer.clear();return raw
                self.stream.check_exit();return b''
            self.buffer.extend(chunk)
    def close(self):pass  # The stream owns its descriptors through reader shutdown.


class Stream:
    def __init__(self,args,master,deadline):
        self.proc=None;self.master=master;self.read_deadline=deadline;self.diagnostics=bytearray()
        self.diagnostic_error=False;self.closed=False;self.reader=Reader(self)
        self.proc=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        for stream in (self.proc.stdin,self.proc.stdout):os.set_blocking(stream.fileno(),False)
        self.drain=threading.Thread(target=self.stderr,daemon=True);self.drain.start()
    def stderr(self):
        while True:
            chunk=self.proc.stderr.read(4096)
            if not chunk:return
            if len(self.diagnostics)+len(chunk)>65536:
                self.diagnostic_error=True;self.shutdown();return
            self.diagnostics.extend(chunk)
    def check_exit(self):
        code=self.proc.wait(timeout=5);self.drain.join(5)
        need(not self.diagnostic_error,'SSH stream diagnostic bound')
        if code:
            # Prefer the pinned master's terminal authentication diagnosis.
            try:self.master.check(time.monotonic()+1)
            except ssh.transport.ProcessError:raise
            raise ssh.transport.exit_error(code,bytes(self.diagnostics),ssh=True)
    def makefile(self,mode):need(mode=='rb','SSH stream read mode');return self.reader
    def settimeout(self,seconds):
        need(seconds is None or type(seconds) in (int,float) and 0<seconds<=300,'SSH stream timeout')
        self.read_deadline=None if seconds is None else time.monotonic()+seconds
    def sendall(self,data,*,deadline=None):
        need(not self.closed and type(data) is bytes and len(data)<=voter.FRAME,'SSH stream send bound/closed')
        deadline=min(time.monotonic()+10,deadline) if deadline is not None else time.monotonic()+10;cursor=0
        while cursor<len(data):
            left=deadline-time.monotonic()
            if left<=0:raise TimeoutError('SSH stream original send deadline')
            _,ready,_=select.select([],[self.proc.stdin],[],left)
            if not ready:raise TimeoutError('SSH stream original send deadline')
            try:cursor+=os.write(self.proc.stdin.fileno(),data[cursor:cursor+16384])
            except BlockingIOError:continue
            except BrokenPipeError:self.check_exit();raise
    def shutdown(self,*unused):
        if self.proc is not None and self.proc.poll() is None:
            try:os.killpg(self.proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
    def close(self):
        if self.closed:return
        self.closed=True;self.shutdown();self.proc.wait(timeout=5);self.drain.join(5)
        # Client.disconnect joins the stdout reader after close. Keep its fd open
        # until then; finish() owns descriptor disposal.
    def finish(self):
        self.close()
        for stream in (self.proc.stdin,self.proc.stdout,self.proc.stderr):stream.close()


class Endpoint(ssh.Endpoint):
    protocol=relay
    python_entry='relay'
    def __init__(self,target,checkout,*,python_context=None):
        super().__init__(target,checkout);self.python_context=python_context
    def launch(self,args):
        if self.python_context is None:return ['python3','-I','-c',self.protocol.LAUNCH,str(self.checkout),*map(str,args)]
        from . import remote_python_context as context
        return context.command(self.python_context,self.python_entry,args)
    def open(self,control,sha,deadline):
        need(not self.closed and 0<deadline-time.monotonic()<=300,'SSH voter endpoint deadline/closed')
        need(ssh.ssh_args(self.target)==self.args,'SSH V5.2 target changed')
        need(all(Path(self.target[k]).read_bytes()==v for k,v in self.pins.items()),'SSH V5.2 credential changed')
        voter.c.hex_value(sha,64,'relay configuration digest');voter.host.path(str(control))
        try:
            if self.master is None:
                self.master=ssh.master.Master(self.args,self.private.name,float('inf'),None,connect_deadline=deadline);self.connections+=1
            self.master.check(deadline)
            # A lost multiplexing socket must fail this channel, never open an
            # unnoticed replacement connection or resubmit its bytes.
            args=[v if not v.startswith('ProxyCommand=') else 'ProxyCommand=false' for v in self.master.args]
            remote=self.launch([str(control),sha])
            return Stream([*args,shlex.join(remote)],self.master,deadline)
        except BaseException:self.disconnect();raise


def public_target(target):
    ssh.ssh_args(target)
    return {**{k:target[k] for k in ('host','port','user','alias')},
            'hostPinSha256':digest(Path(target['knownHosts']).read_bytes())}


class Client(voter.Client):
    def __init__(self,root,node,binding,history,*,target):
        need(binding.get('remoteVoterTransport',{}).get('nodes',{}).get(node)==public_target(target),'SSH voter target binding')
        self.endpoint=Endpoint(target,voter.h.ROOT);self.channels=[];self.active_stream=None;self.recorded=[]
        try:super().__init__(root,node,binding,history)
        except BaseException:self.endpoint.close();raise
    def open_channel(self):
        need(len(self.channels)<4,'SSH voter channel attempts exhausted; original result uncertain')
        stream=self.endpoint.open(self.control,self.sha,time.monotonic()+30)
        self.active_stream=stream;self.channels.append(stream)
        self.recorded.append(dict(configSha256=self.sha,after=self.cursor,through=None,terminal=False))
        return stream
    def receive_event(self,row):
        super().receive_event(row)
        self.recorded[-1].update(through=self.cursor,terminal=row['kind']=='STOPPED')
    def disconnect(self):
        stream=self.active_stream
        try:super().disconnect()
        finally:
            if stream:
                stream.finish();self.active_stream=None
                self.recorded[-1]['through']=self.cursor
            self.endpoint.disconnect()
    def stop(self):
        try:super().stop()
        finally:
            voter.c.write_once(self.control/'ssh-streams.json',dict(schema='gse-v52-voter-ssh-streams-v1',
                target=public_target(self.endpoint.target),configSha256=self.sha,channels=self.recorded))
    def abort(self):
        try:super().abort()
        finally:self.endpoint.close()
