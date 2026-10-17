"""Attempt-bound public SSH access and local key checks; no remote execution."""
import base64
import os
from pathlib import Path
import re
from .evidence import need, encoded, digest
from . import remote_command as command, remote_host as host

SCHEMA = 'gse-v52-guest-access-v1'


def ed25519(value):
    need(type(value) is str and len(value)==80 and re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/]+={0,2}', value), 'V5.2 Ed25519 public key')
    raw = base64.b64decode(value.split()[1], validate=True)
    need(len(raw)==51 and raw[:19]==b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20', 'V5.2 Ed25519 encoding')
    need(base64.b64encode(raw).decode()==value.split()[1], 'V5.2 canonical public key')
    return value


def validate(value, attempt=None):
    need(type(value) is dict and set(value)=={'schema','attempt','user','publicKey'} and value['schema']==SCHEMA,
         'V5.2 access fields')
    need(type(value['attempt']) is str and re.fullmatch('[0-9a-f]{32}',value['attempt']) and
         value['user']=='gse-'+value['attempt'][:24] and (attempt is None or value['attempt']==attempt), 'V5.2 access attempt/user')
    ed25519(value['publicKey']); return value


def descriptor(attempt, public_key):
    need(type(attempt) is str and re.fullmatch('[0-9a-f]{32}',attempt), 'V5.2 access attempt')
    return validate(dict(schema=SCHEMA,attempt=attempt,user='gse-'+attempt[:24],publicKey=public_key))


def metadata(value):
    validate(value)
    return [dict(key=k,value=v) for k,v in (('block-project-ssh-keys','TRUE'),('enable-oslogin','FALSE'),
        ('enable-guest-attributes','TRUE'),('ssh-keys',value['user']+':'+value['publicKey']))]


def generate(directory, attempt):
    # Reuse only the local key generation/permissions invariant. It has no
    # provider request or namespace; never expose private key bytes in evidence.
    from scripts.v51.guest_setup import generate as original
    result=original(directory,attempt)
    value=descriptor(result['attempt'],result['publicKey'])
    command.write_once(Path(directory)/'v52-access.json',value)
    return value


def check_private_key(path, value):
    from scripts.v51.guest_setup import check_private_key as original
    validate(value); original(path,{k:value[k] for k in ('attempt','user','publicKey')})


class HostKeyPending(ValueError): pass


def host_key(response):
    need(type(response) is dict and len(encoded(response))<=65536 and response.get('queryPath')=='hostkeys/', 'V5.2 host-key query scope')
    query=response.get('queryValue',{});need(type(query) is dict,'V5.2 host-key result')
    items=query.get('items',[]);need(type(items) is list and len(items)<=10,'V5.2 host-key entries')
    need(all(type(row) is dict and set(row)=={'namespace','key','value'} and row['namespace']=='hostkeys' and
             type(row['key']) is str and 0<len(row['key'])<=128 and type(row['value']) is str and 0<len(row['value'])<=16384
             for row in items),'V5.2 host-key entry scope/shape')
    selected=[row for row in items if row.get('namespace')=='hostkeys' and row.get('key')=='ssh-ed25519']
    if not selected:raise HostKeyPending('V5.2 host key not yet published')
    need(len(selected)==1 and type(selected[0].get('value')) is str,'V5.2 ambiguous host key')
    return ed25519('ssh-ed25519 '+selected[0]['value'])


def alias(request_sha, node, instance_id):
    from . import cloud_authority as authority
    authority.hex_value(request_sha);authority.numeric(instance_id)
    need(node in ('node-1','node-2','node-3'),'V5.2 host pin node')
    return 'gse-v52-'+digest(encoded([request_sha,node,instance_id]))[:32]


def pin(path, name, public_key):
    need(type(name) is str and re.fullmatch('gse-v52-[0-9a-f]{32}',name),'V5.2 host alias')
    ed25519(public_key);path=host.path(str(path));command.directory(path.parent)
    info=path.parent.stat();need(info.st_uid==os.getuid() and info.st_mode & 0o077==0,'V5.2 private host-pin directory')
    with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600),'wb') as stream:
        stream.write((name+' '+public_key+'\n').encode());stream.flush();os.fsync(stream.fileno())
    command.sync_directory(path.parent)
    return dict(alias=name,sha256=digest(path.read_bytes()))
