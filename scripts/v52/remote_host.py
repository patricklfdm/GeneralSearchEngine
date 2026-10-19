"""Observed local guest identity for SSH qualification, never provider admission."""
from copy import deepcopy
import os
from pathlib import Path
from . import remote_command as c
from .evidence import need, digest, encoded

SCHEMA='gse-v52-ssh-guest-v1'
EXECUTION='loopback-ssh-history-only'
ROOT=Path(__file__).resolve().parents[2]
PIN_FIELDS={'bootId','uid','parentDevice','parentInode'}


def path(value):
    need(type(value) is str and 0<len(value)<=4096 and '\x00' not in value,'SSH guest path')
    p=Path(value)
    need(p.is_absolute() and str(p)==value and '..' not in p.parts,'SSH guest canonical path')
    return p


def observe(parent):
    parent=c.directory(path(str(parent)));info=parent.stat()
    need(info.st_uid==os.getuid() and info.st_mode & 0o077==0,'SSH guest private parent')
    return dict(bootId=c.boot_id(),uid=os.getuid(),parentDevice=info.st_dev,parentInode=info.st_ino)


def validate_pin(value):
    need(type(value) is dict and set(value)==PIN_FIELDS,'SSH guest host fields')
    import uuid
    need(type(value['bootId']) is str and len(value['bootId'])==36,'SSH guest boot identity')
    try:boot=uuid.UUID(value['bootId'])
    except ValueError:raise ValueError('SSH guest boot identity') from None
    need(str(boot)==value['bootId'] and boot.int!=0,'SSH guest boot identity')
    need(all(type(value[k]) is int and 0<=value[k]<1<<64 for k in PIN_FIELDS-{'bootId'}) and value['parentInode']>0,
         'SSH guest resource identity')
    return value


def config(owner,root,host):
    value=dict(schema=SCHEMA,execution=EXECUTION,owner=deepcopy(owner),root=str(root),checkout=str(ROOT),host=deepcopy(host))
    validate(value);return value


def validate(value):
    need(type(value) is dict and set(value)=={'schema','execution','owner','root','checkout','host'},'SSH guest configuration fields')
    need(value['schema']==SCHEMA and value['execution']==EXECUTION,'SSH guest qualification scope')
    c.validate_binding(value['owner']);validate_pin(value['host'])
    need(value['owner']['node']=='node-1' and value['owner']['bootId']==value['host']['bootId'],'SSH guest coordinator/boot binding')
    path(value['checkout']);root=path(value['root'])
    need(root.parent!=root and len(encoded(value))+1<=c.REQUEST_BYTES,'SSH guest configuration bound')
    return root


def check(value):
    root=validate(value)
    need(observe(root.parent)==value['host'],'SSH guest host changed')
    need(Path(value['checkout'])==ROOT,'SSH guest checkout changed')
    from .remote_owned_history import source
    observed=source();bound=value['owner']['selection']['binding']
    need(all(observed[k]==bound[k] for k in ('source','checkoutSha256')),'SSH guest source changed')
    return root


def sha(value):return digest(encoded(value))
