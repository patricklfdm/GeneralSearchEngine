"""Trusted root receiver for one admitted guest's one-shot data-volume setup.

Controller source arrives over pinned SSH; no staged Python is imported. The
request carries numeric provider identities, not a caller-selected command/path.
This receiver does not allocate resources or authorize a paid Runner invocation.
"""
import base64
import os
from pathlib import Path
import pwd
import re
import signal
import sys
import time
from . import guest_delivery_receiver as r, guest_root_policy as policy, guest_root_receiver as root
from . import guest_volume as v, guest_transport as transport

PARENT = '/var/lib/gse-v51-native-volume'
SCHEMA = 'gse-v51-native-volume-request-v1'


def validate(value):
    r.need(type(value) is dict and set(value) == {'schema','binding','provider','bootDiskId','access','requestSha256'} and
           value['schema'] == SCHEMA, 'native volume request fields/scope')
    p = value['provider']; access = policy.access(value['access']); binding = value['binding']
    r.need(type(p) is dict and set(p) == {'instanceId','diskId','node','sizeGiB','attempt'} and
           type(p['node']) is int and p['node'] in (1,2,3) and type(p['sizeGiB']) is int and p['sizeGiB'] == 100 and
           p['attempt'] == access['attempt'] == binding['attempt'] and binding['node'] == 'node-'+str(p['node']),
           'native volume provider binding')
    identity(value)
    r.need(isinstance(value['bootDiskId'],str) and re.fullmatch('[1-9][0-9]{0,19}',value['bootDiskId']) and
           value['bootDiskId'] != p['diskId'] and isinstance(value['requestSha256'],str) and
           re.fullmatch('[0-9a-f]{64}',value['requestSha256']), 'native volume boot/request identity')
    return value


def identity(value):
    raw = r.canonical(value); p = value['provider']
    return r.descriptor(dict(schema='gse-v51-helper-delivery-v1',binding=value['binding'],instanceId=p['instanceId'],
        diskId=p['diskId'],guestAccessSha256=r.sha(r.canonical(value['access'])),payloadSha256=r.sha(raw),payloadBytes=len(raw)))


def validate_budget(budget, value):
    return r.validate_budget(budget, identity(validate(value)), profile=r.NATIVE_PREPARATION_PROFILE)


def guest_deadline(budget, value):
    return r.guest_deadline(budget, identity(validate(value)), profile=r.NATIVE_PREPARATION_PROFILE)


def account(value, deadline, *, privileged):
    user = value['access']['user']; entry = pwd.getpwnam(user)
    r.need(entry.pw_uid > 0 and entry.pw_gid > 0, 'native guest account')
    ids = (os.getuid(),os.geteuid(),os.getgid(),os.getegid())
    r.need(ids == ((0,0,0,0) if privileged else (entry.pw_uid,entry.pw_uid,entry.pw_gid,entry.pw_gid)),
           'native guest effective identity')
    if privileged:
        r.need((os.environ.get('SUDO_USER'),os.environ.get('SUDO_UID'),os.environ.get('SUDO_GID')) ==
               (user,str(entry.pw_uid),str(entry.pw_gid)), 'native guest invoking account')
    a = value['access']
    r.need(root.metadata(deadline) == dict(instanceId=value['provider']['instanceId'],sshKeys=a['user']+':'+a['publicKey'],
           blockProjectSshKeys='TRUE',enableOslogin='FALSE'), 'native guest metadata identity')
    return entry.pw_uid, entry.pw_gid


def context(value, deadline):
    account(value,deadline,privileged=True)
    parent = Path(PARENT)
    for path in parent.parents:
        info = root.directory(path)
        r.need(info['kind'] == 'directory' and info['uid'] == 0 and info['mode'] & 0o022 == 0,
               'native volume ancestor')
    if parent.exists() or parent.is_symlink():
        r.need(root.directory(parent) == dict(kind='directory',uid=0,mode=0o700), 'native volume parent')


class _Linux(v.Linux):
    """Only the fixed volume algorithm may use this backend after root admission."""
    def __init__(self, value): self.value = value
    def run(self, argv, deadline):
        if argv[0] not in ('mkdir','mkfs.ext4','mount','chown','chmod'):
            return super().run(argv,deadline)
        context(self.value,deadline)
        uid,gid = self.user(self.value['access']['user'])
        allowed = (argv == ['mkdir','-m','0755',v.MOUNT] or argv == ['chmod','0700',v.MOUNT] or
                   argv == ['chown',str(uid)+':'+str(gid),v.MOUNT] or
                   len(argv) == 4 and argv[:3] == ['mkfs.ext4','-L','gse-'+self.value['provider']['attempt'][:12]] and v.device_name(argv[3]) or
                   len(argv) == 7 and argv[:5] == ['mount','-t','ext4','-o','nodev,nosuid'] and
                   v.device_name(argv[5]) and argv[6] == v.MOUNT)
        r.need(allowed, 'native volume write scope')
        return transport.process(argv,b'',deadline,maximum=65536,
                                 env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C','LC_ALL':'C'})


def _perform(action, value, token, backend):
    validate(value); desc = identity(value)
    r.need(action in ('clock','prepare','query','check'), 'native volume action')
    if action == 'clock':
        context(value,time.monotonic()+5)
        return r.clock_sample(desc,token)
    budget = validate_budget(r.decode(base64.b64decode(token,validate=True)),value)
    deadline = guest_deadline(budget,value); context(value,deadline)
    parent = Path(PARENT); answer = dict(state='NOT_FOUND')
    if action == 'prepare':
        try:
            parent.mkdir(mode=0o700); r.sync(parent.parent)
        except FileExistsError: pass
        context(value,deadline)
    if parent.exists():
        folder = r.location(parent,desc,0)
        if action == 'prepare' and not folder.exists():
            try: folder.mkdir(mode=0o700)
            except FileExistsError: pass
            else:
                r.sync(parent)
                r.publish(folder/'request.json',value); r.publish(folder/'deadline.json',budget)
                # The exclusive outer claim precedes all volume observations and
                # writes. A crash cannot turn this directory into a fresh attempt.
                try:
                    v._prepare(folder/'volume',value['provider'],value['access']['user'],backend,deadline,
                               recheck=lambda:context(value,deadline),native=True)
                except Exception:
                    # A durable FAIL receipt is queried below. Torn receipts stay
                    # UNCERTAIN; neither case re-enters the formatting algorithm.
                    pass
        if folder.exists() or folder.is_symlink():
            r.owned(folder,0,True); answer = dict(state='UNCERTAIN')
            if (folder/'deadline.json').exists():
                r.need(r.decode(r.read(folder/'deadline.json',0)) == budget and
                       r.decode(r.read(folder/'request.json',0)) == value, 'native volume consumed identity/deadline')
                receipt = folder/'volume/receipt.json'
                if receipt.exists():
                    startup = r.decode(r.read(receipt,0))
                    r.need(startup['schema'] == 'gse-v51-native-volume-startup-v1' and startup['provider'] == value['provider'] and
                           startup['status'] in ('PASS','FAIL') and 'paidCloud' not in startup, 'native volume receipt')
                    answer = dict(state='SUCCEEDED' if startup['status'] == 'PASS' else 'FAILED',startup=startup)
                    if action == 'check' and answer['state'] == 'SUCCEEDED':
                        answer['readiness'] = v._readiness(folder/'volume',value['provider'],value['access']['user'],
                                                         backend,deadline,native=True)
    context(value,deadline); guest_deadline(budget,value)
    return dict(schema='gse-v51-native-volume-transport-v1',requestSha256=r.sha(r.canonical(value)),
                deadlineSha256=r.sha(r.canonical(budget)),**answer)


def main():
    action, encoded, token = sys.argv[1:]
    r.need(len(encoded) <= 16384 and len(token) <= 4096,'native volume request bound')
    value = validate(r.decode(base64.b64decode(encoded,validate=True)))
    seconds = 5 if action == 'clock' else guest_deadline(r.decode(base64.b64decode(token,validate=True)),value)-time.monotonic()
    def expired(*_): raise TimeoutError('native volume original deadline')
    signal.signal(signal.SIGALRM,expired); signal.setitimer(signal.ITIMER_REAL,max(.001,seconds))
    try: print(r.canonical(_perform(action,value,token,_Linux(value))).decode(),flush=True)
    finally: signal.setitimer(signal.ITIMER_REAL,0)
