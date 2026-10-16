"""Pinned loopback SSH control qualification. No live provider entry is enabled."""
from copy import deepcopy
import os
import math
from pathlib import Path
import re
import tempfile
import time
from scripts.v51 import guest_transport as transport,guest_ssh_master as master
from scripts.v51.performance_model import strict_json
from . import remote_command as c,remote_slots as slots,remote_host as host,remote_ssh_guest as guest
from .evidence import need,encoded


class Rejected(ValueError):
    retryable=False
    def __init__(self,code):
        need(code in guest.ERRORS,'SSH unknown rejection code');self.code=code
        super().__init__('V5.2 SSH guest rejected: '+code)


def ssh_args(target):
    need(type(target) is dict and set(target)=={'host','port','user','key','knownHosts','alias'},'SSH V5.2 target fields')
    # This stage has neither independent cloud facts nor three-host clock domains.
    need(target['host']=='127.0.0.1' and type(target['port']) is int and 1024<=target['port']<=65535,
         'SSH V5.2 live host execution not admitted')
    need(type(target['user']) is str and re.fullmatch('[a-z_][a-z0-9_-]{0,63}',target['user']),'SSH V5.2 user')
    need(type(target['alias']) is str and re.fullmatch('gse-v52-[0-9a-f]{32}',target['alias']),'SSH V5.2 host alias')
    for name in ('key','knownHosts'):
        p=host.path(target[name]);c.directory(p.parent)
        need(p.is_file() and not p.is_symlink() and p.stat().st_uid==os.getuid() and p.stat().st_mode & 0o077==0,
             'SSH V5.2 owned credential file')
    known=Path(target['knownHosts']);need(0<known.stat().st_size<=1024,'SSH V5.2 host pin bound')
    need(re.fullmatch(re.escape(target['alias'])+r' ssh-ed25519 [A-Za-z0-9+/]+={0,2}\n',known.read_text()),'SSH V5.2 exact host pin')
    return ['ssh','-F','/dev/null','-T','-i',target['key'],'-p',str(target['port']),
            '-o','BatchMode=yes','-o','IdentitiesOnly=yes','-o','IdentityAgent=none','-o','HostKeyAlgorithms=ssh-ed25519',
            '-o','UpdateHostKeys=no','-o','ForwardAgent=no','-o','ClearAllForwardings=yes',
            '-o','ControlMaster=no','-o','ControlPath=none','-o','StrictHostKeyChecking=yes',
            '-o','UserKnownHostsFile='+target['knownHosts'],'-o','GlobalKnownHostsFile=/dev/null',
            '-o','HostKeyAlias='+target['alias'],'-o','ConnectTimeout=10','-o','ServerAliveInterval=15',
            '-o','ServerAliveCountMax=2','-o','ProxyCommand=none',target['user']+'@'+target['host'],'']


class Endpoint:
    """One original submit. Reconnects open query channels; never replay a channel."""
    offline=True
    def __init__(self,target,checkout):
        self.target=deepcopy(target);self.args=ssh_args(target);self.checkout=host.path(str(checkout))
        self.private=tempfile.TemporaryDirectory(prefix='v52-ssh-');self.master=None;self.connections=0
        self.pins={name:Path(target[name]).read_bytes() for name in ('key','knownHosts')}
        self.config=None;self.closed=False

    def disconnect(self):
        if self.master is not None:self.master.close();self.master=None

    def close(self):
        self.disconnect();self.private.cleanup();self.pins.clear();self.closed=True

    def exchange(self,action,root,value,deadline):
        need(not self.closed and action in ('probe','prepare','submit','query','cancel','inspect'),'SSH V5.2 action/session')
        need(type(deadline) in (int,float) and math.isfinite(deadline) and 0<deadline-time.monotonic()<=300,'SSH V5.2 expired/unbounded exchange')
        need(ssh_args(self.target)==self.args,'SSH V5.2 target changed')
        need(all(Path(self.target[k]).read_bytes()==v for k,v in self.pins.items()),'SSH V5.2 credential changed')
        remote=['python3','-I','-c',guest.LAUNCH,str(self.checkout),action,str(host.path(str(root)))]
        data=b'' if value is None else encoded(value)
        try:
            if self.master is None:
                self.master=master.Master(self.args,self.private.name,float('inf'),None,connect_deadline=deadline);self.connections+=1
            raw=self.master.exchange(remote,data,deadline,maximum=c.RESPONSE_BYTES,request_maximum=c.REQUEST_BYTES)
        except BaseException:
            self.disconnect();raise
        answer=strict_json(raw)
        if type(answer) is dict and answer.get('schema')=='gse-v52-ssh-error-v1':
            need(set(answer)=={'schema','code'},'SSH V5.2 error envelope');raise Rejected(answer['code'])
        return answer

    def probe(self,parent,deadline):
        value=self.exchange('probe',parent,None,deadline)
        need(type(value) is dict and set(value)=={'schema','host'} and value['schema']=='gse-v52-ssh-probe-v1','SSH V5.2 probe identity')
        return host.validate_pin(value['host'])

    def bind(self,config):
        host.validate(config);need(config['checkout']==str(self.checkout),'SSH V5.2 checkout binding')
        need(self.config is None or self.config==config,'SSH V5.2 endpoint already bound');self.config=deepcopy(config)

    def checked(self,value):
        need(self.config is not None and type(value) is dict and set(value)=={'schema','configSha256','host','answer'} and
             value['schema']=='gse-v52-ssh-reply-v1' and value['configSha256']==host.sha(self.config) and value['host']==self.config['host'],
             'SSH V5.2 response host/configuration')
        return value['answer']

    def prepare(self,deadline):
        need(self.config is not None,'SSH V5.2 unbound endpoint')
        result=self.checked(self.exchange('prepare',self.config['root'],self.config,deadline))
        need(result==dict(state='PREPARED_NOT_EXECUTED'),'SSH V5.2 preparation outcome');return result

    def control(self,action,value,deadline):
        need(self.config is not None,'SSH V5.2 unbound endpoint')
        if action=='inspect':need(value is None,'SSH V5.2 inspect request')
        else:slots.validate(value,self.config['owner']);need(value['command']=='execute-history','SSH V5.2 history command only')
        answer=self.checked(self.exchange(action,self.config['root'],dict(configSha256=host.sha(self.config),request=value),deadline))
        return guest.validate_inspection(answer,self.config) if action=='inspect' else c.validate_receipt(answer,value,self.config['owner'])

    def submit(self,value,deadline):return self.control('submit',value,deadline)
    def query(self,value,deadline):return self.control('query',value,deadline)
    def cancel(self,value,deadline):return self.control('cancel',value,deadline)
    def inspect(self,deadline):return self.control('inspect',None,deadline)
