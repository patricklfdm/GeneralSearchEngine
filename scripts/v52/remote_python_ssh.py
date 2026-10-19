"""One pinned SSH installation. A lost install reply can only verify its result."""
from pathlib import Path
import time
import shlex
from .remote_voter_ssh import Stream
from . import remote_ssh as ssh, remote_python_receiver as receiver


class Installer(ssh.Endpoint):
    def __init__(self,target,descriptor):
        super().__init__(target,Path(__file__).resolve().parents[2])
        receiver.descriptor(descriptor)
        self.descriptor=descriptor;self.sha=receiver.digest(receiver.encoded(descriptor))
        self.calls=[];self.reply_lost=False

    def exchange(self,action,parent,payload):
        receiver.need(action in ('install','verify') and not self.closed,'Python SSH action/closed')
        receiver.need(ssh.ssh_args(self.target)==self.args and
                      all(Path(self.target[k]).read_bytes()==v for k,v in self.pins.items()),'Python SSH target changed')
        deadline=time.monotonic()+30
        self.calls.append(action)
        remote=['python3','-I','-S','-c',Path(receiver.__file__).read_text(),action,str(parent),self.sha]
        request=receiver.encoded(dict(descriptor=self.descriptor,payload=payload))
        try:
            if self.master is None:
                self.master=ssh.master.Master(self.args,self.private.name,float('inf'),None,connect_deadline=deadline)
                self.connections+=1
            self.master.check(deadline)
            args=[v if not v.startswith('ProxyCommand=') else 'ProxyCommand=false' for v in self.master.args]
            raw=transfer(Stream([*args,shlex.join(remote)],self.master,deadline),request,deadline)
        except BaseException:self.disconnect();raise
        value=receiver.decode(raw)
        receiver.need(type(value) is dict and set(value)=={'schema','descriptorSha256','root','host','filesSha256'} and
                      value['schema']==receiver.RECEIPT and value['descriptorSha256']==self.sha and
                      value['root']==str(Path(parent)/('python-'+self.descriptor['sha256'])) and
                      value['filesSha256']==receiver.digest(receiver.encoded(self.descriptor['files'])),
                      'Python SSH installation receipt')
        ssh.host.validate_pin(value['host'])
        return value

    def install(self,parent,raw,*,discard_reply=False):
        receiver.payload(raw,self.descriptor)
        receiver.need(not self.calls,'Python SSH installation already consumed')
        def submit():
            value=self.exchange('install',parent,raw.decode('ascii'))
            if discard_reply:
                self.disconnect();raise ConnectionError('qualification discarded Python installation reply')
            return value
        from .remote_voter_lifecycle import original_launch
        def lost():self.reply_lost=True
        return original_launch(submit,lambda:self.exchange('verify',parent,None),lost=lost)


def transfer(channel,request,deadline):
    # Preserve V5.1's 1 MiB envelope limit. This separate bounded capsule stream
    # writes 64 KiB pieces once and then accepts one small terminal receipt.
    try:
        receiver.need(type(request) is bytes and len(request)<=receiver.MAX_REQUEST,'Python SSH request bound')
        for offset in range(0,len(request),64<<10):
            receiver.need(time.monotonic()<deadline,'Python SSH transfer deadline')
            channel.sendall(request[offset:offset+(64<<10)],deadline=deadline)
        channel.proc.stdin.close()
        raw=channel.reader.readline(8193)
        receiver.need(0<len(raw)<=8192 and raw.endswith(b'\n'),'Python SSH response bound')
        receiver.need(channel.reader.readline(2)==b'','Python SSH trailing response')
        channel.check_exit();return raw
    finally:channel.finish()
