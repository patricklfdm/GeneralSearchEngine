"""Fixed read-only guest probe, sent as source over the already pinned SSH route.

No repository import, shell, caller-selected URL/path or remote mutation. Provider
authority and the original lease are checked by the controller on both sides.
"""
import ipaddress
import json
import os
from pathlib import Path
import pwd
import re
import sys
import urllib.request
import uuid

SCHEMA='gse-v52-native-guest-identity-v1'
FIELDS={'schema','instanceId','privateAddress','bootId','uid','gid','user'}


def need(value):
    if not value:raise ValueError('V5.2 guest identity rejected')


def validate(value):
    need(type(value) is dict and set(value)==FIELDS and value['schema']==SCHEMA)
    need(type(value['instanceId']) is str and re.fullmatch('[1-9][0-9]{0,19}',value['instanceId']))
    need(type(value['user']) is str and re.fullmatch('gse-[0-9a-f]{24}',value['user']))
    need(all(type(value[k]) is int and 0<value[k]<1<<32 for k in ('uid','gid')))
    need(type(value['bootId']) is str and str(uuid.UUID(value['bootId']))==value['bootId'] and uuid.UUID(value['bootId']).int!=0)
    address=ipaddress.IPv4Address(value['privateAddress'])
    need(str(address)==value['privateAddress'] and any(address in ipaddress.IPv4Network(n) for n in
        ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')))
    return value


def metadata():
    # Disable environment proxies and redirects for this fixed metadata origin.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):raise ValueError('V5.2 guest metadata redirect')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    paths={'instanceId':'id','privateAddress':'network-interfaces/0/ip','sshKeys':'attributes/ssh-keys',
        'blockProjectSshKeys':'attributes/block-project-ssh-keys','enableOslogin':'attributes/enable-oslogin'}
    values={}
    for key,path in paths.items():
        request=urllib.request.Request('http://169.254.169.254/computeMetadata/v1/instance/'+path,
                                      headers={'Metadata-Flavor':'Google'})
        with opener.open(request,timeout=3) as response:
            need(response.status==200 and response.headers.get('Metadata-Flavor')=='Google')
            raw=response.read(8193);need(0<len(raw)<=8192);values[key]=raw.decode('ascii')
    return values


def observe(value):
    need(type(value) is dict and set(value)=={'instanceId','privateAddress','user','publicKey'})
    need(type(value['user']) is str and re.fullmatch('gse-[0-9a-f]{24}',value['user']))
    need(type(value['publicKey']) is str and re.fullmatch('ssh-ed25519 [A-Za-z0-9+/]+={0,2}',value['publicKey']))
    user=pwd.getpwnam(value['user'])
    need((os.getuid(),os.geteuid(),os.getgid(),os.getegid())==(user.pw_uid,user.pw_uid,user.pw_gid,user.pw_gid))
    actual=metadata()
    need(actual==dict(instanceId=value['instanceId'],privateAddress=value['privateAddress'],
        sshKeys=value['user']+':'+value['publicKey'],blockProjectSshKeys='TRUE',enableOslogin='FALSE'))
    return validate(dict(schema=SCHEMA,instanceId=actual['instanceId'],privateAddress=actual['privateAddress'],
        bootId=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),uid=user.pw_uid,gid=user.pw_gid,user=user.pw_name))


def main():
    try:
        raw=sys.stdin.buffer.read(8193);need(0<len(raw)<=8192)
        def pairs(rows):
            value={}
            for k,v in rows:need(k not in value);value[k]=v
            return value
        result=observe(json.loads(raw,object_pairs_hook=pairs))
    except Exception:
        print('V52_GUEST_IDENTITY_REJECTED',file=sys.stderr);return 2
    print(json.dumps(result,sort_keys=True,separators=(',',':')),flush=True);return 0


if __name__=='__main__':raise SystemExit(main())
