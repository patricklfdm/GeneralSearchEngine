"""Native transfer-only receiver. Metadata and the mounted data volume gate every call."""
import base64
import os
import re
import signal
import stat
import sys
import time
from pathlib import Path
from . import guest_delivery_receiver as r, guest_package_receiver as p
from . import guest_native_volume as volume, guest_volume as v, guest_transport as transport


def validate(value):
    p.descriptor(value)
    r.need(value['schema'] == 'gse-v51-native-package-transfer-v1','native package domain')
    context = value['nativeVolume']
    r.need(type(context) is dict and set(context) == {'request','volume','startupSha256'},'native package volume context')
    request = volume.validate(context['request']); mount = context['volume']
    r.need(value['binding'] == request['binding'] and value['instanceId'] == request['provider']['instanceId'] and
           value['diskId'] == request['provider']['diskId'] and value['guestAccessSha256'] == r.sha(r.canonical(request['access'])),
           'native package request binding')
    r.need(type(mount) is dict and set(mount) == {'device','majorMinor','uuid','mount','uid','gid'} and
           mount['mount'] == v.MOUNT and v.device_name(mount['device']) and
           re.fullmatch('[0-9]+:[0-9]+',mount['majorMinor']) and
           re.fullmatch('[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}',mount['uuid']) and
           all(type(mount[k]) is int and 0 < mount[k] < 2**32-1 for k in ('uid','gid')) and
           re.fullmatch('[0-9a-f]{64}',context['startupSha256']),'native package mount identity')
    return value


def context(value, deadline):
    native = value['nativeVolume']; mount = native['volume']
    uid,gid = volume.account(native['request'],deadline,privileged=False)
    r.need((uid,gid) == (mount['uid'],mount['gid']),'native package account changed')
    parent = Path(v.MOUNT)
    for path in parent.parents:
        info = volume.root.directory(path)
        r.need(info['kind'] == 'directory' and info['uid'] == 0 and info['mode'] & 0o022 == 0,'native package ancestor')
    r.owned(parent,uid,True); info = parent.stat()
    r.need(info.st_gid == gid and stat.S_IMODE(info.st_mode) == 0o700 and
           f'{os.major(info.st_dev)}:{os.minor(info.st_dev)}' == mount['majorMinor'],
           'native package mounted device')
    mounts = r.decode(transport.process(v.FINDMNT,b'',deadline,maximum=65536))['filesystems']
    rows = [row for row in mounts if row['target'] == v.MOUNT or row['target'].startswith(v.MOUNT+'/') or
            row['maj:min'] == mount['majorMinor']]
    r.need(len(rows) == 1 and rows[0]['target'] == v.MOUNT and rows[0]['maj:min'] == mount['majorMinor'] and
           rows[0]['fstype'] == 'ext4' and {'rw','nodev','nosuid'} <= set(rows[0]['options'].split(',')) and
           'ro' not in rows[0]['options'].split(','),'native package mount options')
    devices = r.decode(transport.process(v.LSBLK,b'',deadline,maximum=65536))['blockdevices']
    rows = [row for row in devices if row['maj:min'] == mount['majorMinor']]
    r.need(len(rows) == 1 and rows[0]['name'] == mount['device'] and rows[0]['uuid'] == mount['uuid'] and
           rows[0]['fstype'] == 'ext4' and rows[0]['label'] == 'gse-'+value['binding']['attempt'][:12],
           'native package filesystem changed')


def perform(action, value, token, stream, index=None):
    validate(value)
    r.need(action in ('clock','begin','part','query','finish') and
           (type(index) is int if action == 'part' else index is None),'native package transfer-only action')
    if action == 'clock':
        context(value,time.monotonic()+5)
        return r.clock_sample(p.identity(value),token)
    budget = r.validate_budget(r.decode(base64.b64decode(token,validate=True)),p.identity(value))
    deadline = r.guest_deadline(budget,p.identity(value)); context(value,deadline)
    if action == 'begin': answer = p.begin(v.MOUNT,value,budget)
    elif action == 'part': answer = p.put(v.MOUNT,value,budget,index,stream)
    elif action == 'finish': answer = p.finish(v.MOUNT,value,budget)
    else: answer = p.query(v.MOUNT,value,budget)
    context(value,deadline); r.guest_deadline(budget,p.identity(value))
    return dict(schema='gse-v51-package-transport-v1',deadlineSha256=r.sha(r.canonical(budget)),receipt=answer)


def main():
    action, encoded, token, *tail = sys.argv[1:]
    r.need(len(encoded) <= 131072 and len(token) <= 4096 and len(tail) <= 1,'native package envelope bound')
    value = validate(r.decode(base64.b64decode(encoded,validate=True)))
    seconds = 5 if action == 'clock' else r.guest_deadline(r.decode(base64.b64decode(token,validate=True)),p.identity(value))-time.monotonic()
    def expired(*_): raise TimeoutError('native package original deadline')
    signal.signal(signal.SIGALRM,expired); signal.setitimer(signal.ITIMER_REAL,max(.001,seconds))
    try: print(r.canonical(perform(action,value,token,sys.stdin.buffer,int(tail[0]) if tail else None)).decode(),flush=True)
    finally: signal.setitimer(signal.ITIMER_REAL,0)
