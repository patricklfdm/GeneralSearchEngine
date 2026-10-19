"""Pinned Java image stream. Submit installation once; recover only its result."""
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import shlex
import stat
import time
from . import remote_java_receiver as r,remote_ssh as ssh,remote_python_ssh as python
from .remote_voter_lifecycle import original_launch


def trusted():
    # No installed package is imported before verification. Only these two fixed
    # source modules are sent; the capsule/command cannot select arbitrary code.
    sources={m.__name__.rsplit('.',1)[1]:Path(m.__file__).read_text() for m in (r.p,r)}
    return ("import sys,types\np=types.ModuleType('trusted_v52');p.__path__=[];sys.modules['trusted_v52']=p\n"
        "sources="+repr(sources)+"\nfor name in ('remote_python_receiver','remote_java_receiver'):\n"
        " q=types.ModuleType('trusted_v52.'+name);q.__package__='trusted_v52';sys.modules[q.__name__]=q\n"
        " exec(compile(sources[name],'<trusted-v52-'+name+'>','exec'),q.__dict__)\n"
        "sys.modules['trusted_v52.remote_java_receiver'].main()\n")


def transfer(channel,value,archive,deadline):
    try:
        header=r.p.encoded(r.descriptor(value))+b'\n'
        for offset in range(0,len(header),r.PIECE):channel.sendall(header[offset:offset+r.PIECE],deadline=deadline)
        if archive is not None:
            path=Path(archive);r.p.need(not path.is_symlink(),'Java upload linked archive')
            with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as stream:
                info=os.fstat(stream.fileno());r.p.need(stat.S_ISREG(info.st_mode) and info.st_size==value['bytes'],'Java upload archive size/type')
                sha=hashlib.sha256();remaining=value['bytes']
                while remaining:
                    r.p.need(time.monotonic()<deadline,'Java original upload deadline')
                    raw=stream.read(min(remaining,r.PIECE));r.p.need(raw,'Java upload truncated');remaining-=len(raw);sha.update(raw)
                    channel.sendall(raw,deadline=deadline)
                r.p.need(not stream.read(1) and sha.hexdigest()==value['sha256'],'Java original upload changed')
        channel.proc.stdin.close();raw=channel.reader.readline(8193)
        r.p.need(0<len(raw)<=8192 and raw.endswith(b'\n') and channel.reader.readline(2)==b'','Java install response bound')
        channel.check_exit();r.p.need(time.monotonic()<deadline,'Java late response');return r.p.decode(raw)
    finally:channel.finish()


class Installer(ssh.Endpoint):
    def __init__(self,target,value):
        super().__init__(target,Path(__file__).resolve().parents[2])
        self.value=deepcopy(r.descriptor(value));self.pin=r.p.digest(r.p.encoded(self.value))
        self.calls=[];self.end=None;self.reply_lost=False

    def exchange(self,action,parent,archive=None):
        r.p.need(action in ('install','verify') and not self.closed,'Java SSH action/closed')
        r.p.need(ssh.ssh_args(self.target)==self.args and all(Path(self.target[k]).read_bytes()==v for k,v in self.pins.items()),
                 'Java SSH target changed')
        deadline=self.end if self.end is not None else time.monotonic()+60
        r.p.need(time.monotonic()<deadline,'Java original installation deadline');self.calls.append(action)
        remote=['/usr/bin/python3','-I','-S','-c',trusted(),action,str(parent),self.pin]
        try:
            if self.master is None:
                self.master=ssh.master.Master(self.args,self.private.name,float('inf'),None,connect_deadline=deadline);self.connections+=1
            self.master.check(deadline)
            args=[v if not v.startswith('ProxyCommand=') else 'ProxyCommand=false' for v in self.master.args]
            result=transfer(python.Stream([*args,shlex.join(remote)],self.master,deadline),self.value,archive,deadline)
        except BaseException:self.disconnect();raise
        r.p.need(type(result) is dict and set(result)=={'schema','descriptorSha256','root','host','filesSha256','java'} and
            result['schema']==r.RECEIPT and result['descriptorSha256']==self.pin and result['root']==str(Path(parent)/('java-'+self.value['sha256'])) and
            result['filesSha256']==r.p.digest(r.p.encoded(self.value['files'])) and result['java']==self.value['source']['java'],
            'Java SSH installation receipt');ssh.host.validate_pin(result['host']);return result

    def install(self,parent,archive,*,discard_reply=False):
        r.p.need(not self.calls and self.end is None,'Java installation already consumed');self.end=time.monotonic()+300
        def submit():
            result=self.exchange('install',parent,archive)
            if discard_reply:self.disconnect();raise ConnectionError('qualification discarded original Java installation reply')
            return result
        def lost():self.reply_lost=True
        return original_launch(submit,lambda:self.exchange('verify',parent),lost=lost)
