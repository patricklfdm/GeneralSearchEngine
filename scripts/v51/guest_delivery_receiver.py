"""Standalone authenticated helper receiver; no payload imports during installation.

The controller sends THIS trusted source through the authenticated SSH command.
Native privileged/cloud admission remains outside this receiver.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

MAX_BYTES = 512 << 10
MAX_DEADLINE_NANOS = 600 * 10**9
MODULES = ('cloud_guest', 'guest_jvm', 'guest_bootstrap', 'cloud_package',
           'remote_command', 'remote_collection', 'remote_schedule', 'remote_schedule_evidence',
           'cloud_workload_contract', 'performance_model', 'performance_plan',
           'guest_volume', 'guest_setup', 'guest_transport', 'guest_delivery_receiver')
INPUTS = ('scripts/v51/__init__.py', *('scripts/v51/'+n+'.py' for n in MODULES),
          'docs/v5x/v5.1/phase6-plan.json', 'docs/v5x/v5.1/phase6-cloud-workload-plan.json')
NAMES = frozenset(('helper.py', 'scripts/__init__.py', *INPUTS))


def need(value, message):
    if not value: raise ValueError(message)


def canonical(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
def sha(raw): return hashlib.sha256(raw).hexdigest()


def decode(raw):
    def pairs(items):
        value = dict(items); need(len(value) == len(items), 'duplicate delivery JSON key'); return value
    def constant(value): raise ValueError('nonfinite delivery JSON')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def descriptor(value):
    need(type(value) is dict and set(value) == {'schema', 'binding', 'instanceId', 'diskId', 'guestAccessSha256',
         'payloadSha256', 'payloadBytes'}, 'delivery descriptor fields')
    need(value['schema'] == 'gse-v51-helper-delivery-v1', 'delivery descriptor schema')
    binding = value['binding']
    need(type(binding) is dict and set(binding) == {'schema', 'source', 'bundleSha256', 'attempt', 'node', 'workloadSha256'} and
         binding['schema'] == 'gse-v51-guest-binding-v1' and binding['node'] in ('node-1', 'node-2', 'node-3'), 'delivery binding')
    for name, size in (('source', 40), ('bundleSha256', 64), ('attempt', 32), ('workloadSha256', 64)):
        need(isinstance(binding[name], str) and re.fullmatch('[0-9a-f]{%d}' % size, binding[name]), 'delivery binding '+name)
    for name in ('instanceId', 'diskId'):
        need(isinstance(value[name], str) and re.fullmatch('[1-9][0-9]{0,19}', value[name]), 'delivery numeric identity')
    for name in ('guestAccessSha256', 'payloadSha256'):
        need(isinstance(value[name], str) and re.fullmatch('[0-9a-f]{64}', value[name]), 'delivery digest')
    need(type(value['payloadBytes']) is int and 0 < value['payloadBytes'] <= MAX_BYTES, 'delivery payload bound')
    return value


def boot_identity():
    # A new Linux boot must never reuse a mapping from the previous monotonic epoch.
    value = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    need(re.fullmatch(r'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}', value), 'delivery boot identity')
    return value


def clock_sample(value, nonce):
    need(isinstance(nonce, str) and re.fullmatch('[0-9a-f]{32}', nonce), 'delivery clock nonce')
    return dict(schema='gse-v51-helper-clock-v1', requestSha256=sha(canonical(descriptor(value))),
                nonce=nonce, bootId=boot_identity(), sampledNanos=time.monotonic_ns())


def validate_sample(sample, value, nonce):
    need(type(sample) is dict and set(sample) == {'schema', 'requestSha256', 'nonce', 'bootId', 'sampledNanos'} and
         sample['schema'] == 'gse-v51-helper-clock-v1' and sample['requestSha256'] == sha(canonical(descriptor(value))) and
         isinstance(nonce, str) and re.fullmatch('[0-9a-f]{32}', nonce) and sample['nonce'] == nonce,
         'delivery clock identity')
    need(isinstance(sample['bootId'], str) and
         re.fullmatch(r'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}', sample['bootId']) and
         type(sample['sampledNanos']) is int and 0 <= sample['sampledNanos'] < 2**63, 'delivery clock sample')
    return sample


def validate_budget(budget, value):
    need(type(budget) is dict and set(budget) == {'schema', 'sample', 'expiresNanos'} and
         budget['schema'] == 'gse-v51-helper-deadline-v1' and type(budget['sample']) is dict,
         'delivery deadline fields')
    sample = validate_sample(budget['sample'], value, budget['sample'].get('nonce'))
    need(type(budget['expiresNanos']) is int and
         0 < budget['expiresNanos'] - sample['sampledNanos'] <= MAX_DEADLINE_NANOS,
         'delivery deadline duration')
    return budget


def guest_deadline(budget, value):
    validate_budget(budget, value)
    need(budget['sample']['bootId'] == boot_identity(), 'delivery guest rebooted')
    need(budget['sample']['sampledNanos'] <= time.monotonic_ns() < budget['expiresNanos'],
         'delivery guest deadline expired or clock moved backwards')
    return budget['expiresNanos'] / 10**9


def owned(path, uid, directory=False):
    info = path.lstat()
    need((stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)) and
         info.st_uid == uid and info.st_mode & 0o022 == 0 and (directory or info.st_nlink == 1), 'delivery owned path')
    return info


def location(parent, value, uid):
    parent = Path(parent)
    need(parent.is_absolute() and '..' not in parent.parts and type(uid) is int and uid == os.getuid(), 'delivery destination/uid')
    for item in (parent, *parent.parents):
        info = item.lstat()
        need(stat.S_ISDIR(info.st_mode), 'delivery linked parent')
        # A sticky /tmp ancestor is permitted; the actual installation parent is private.
        need(info.st_uid in (0, uid) and (info.st_mode & 0o022 == 0 or
             info.st_uid == 0 and info.st_mode & stat.S_ISVTX), 'delivery writable parent')
    info = owned(parent, uid, True)
    need(stat.S_IMODE(info.st_mode) == 0o700, 'delivery private parent')
    return parent/(value['binding']['attempt']+'-'+value['binding']['node'])


def sync(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)


def write(path, raw):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    sync(path.parent)


def publish(path, value):
    temp = path.with_name(path.name+'.writing'); write(temp, canonical(value))
    os.link(temp, path, follow_symlinks=False); sync(path.parent); temp.unlink(); sync(path.parent)


def read(path, uid, maximum=MAX_BYTES):
    # Atomic publication can briefly leave the receipt and its .writing link.
    # Only that exact private companion is allowed, never an arbitrary hardlink.
    info = path.lstat()
    temporary = path.with_name(path.name+'.writing')
    publishing = info.st_nlink == 2 and temporary.exists() and not temporary.is_symlink() and os.path.samestat(info, temporary.lstat())
    if publishing:
        need(stat.S_ISREG(info.st_mode) and info.st_uid == uid and info.st_mode & 0o022 == 0, 'delivery publishing receipt')
    else: owned(path, uid)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and info.st_uid == uid and info.st_mode & 0o022 == 0 and
             (info.st_nlink == 1 or publishing and info.st_nlink == 2), 'delivery read type')
        raw = stream.read(maximum+1)
    need(len(raw) <= maximum, 'delivery read bound'); return raw


def payload(raw, value):
    need(len(raw) == value['payloadBytes'] and sha(raw) == value['payloadSha256'], 'delivery payload digest/size')
    document = decode(raw)
    need(set(document) == {'schema', 'source', 'files'} and document['schema'] == 'gse-v51-helper-payload-v1' and
         document['source'] == value['binding']['source'] and type(document['files']) is dict and
         set(document['files']) == NAMES, 'delivery payload source/inventory')
    files = {name:base64.b64decode(data, validate=True) for name, data in document['files'].items()}
    need(sum(map(len, files.values())) <= MAX_BYTES, 'delivery decoded bound')
    need(sha(canonical(decode(files['docs/v5x/v5.1/phase6-cloud-workload-plan.json']))) ==
         value['binding']['workloadSha256'], 'delivery workload binding')
    return files


def verify(root, value, uid):
    owned(root, uid, True)
    need(decode(read(root/'request.json', uid)) == value, 'delivery request identity')
    files = payload(read(root/'payload.json', uid), value)
    directory = root/'files'; owned(directory, uid, True)
    expected_dirs = {str(parent) for name in files for parent in Path(name).parents if str(parent) != '.'}
    seen = set(); directories = set()
    for path in directory.rglob('*'):
        name = path.relative_to(directory).as_posix()
        if path.is_dir() and not path.is_symlink():
            need(name in expected_dirs, 'delivery unexpected directory'); owned(path, uid, True); directories.add(name)
        else:
            need(name in files and read(path, uid) == files[name], 'delivery installed bytes changed'); seen.add(name)
    need(seen == set(files) and directories == expected_dirs, 'delivery installed inventory')
    return dict(files=len(files), decodedBytes=sum(map(len, files.values())))


def envelope(value, state, **fields):
    return dict(schema='gse-v51-helper-receipt-v1', requestSha256=sha(canonical(value)), state=state,
                paidCloud=False, realBlockDeviceWritten=False, fullRemoteQualification=False, **fields)


def query(parent, value, uid, *, budget=None):
    descriptor(value); root = location(parent, value, uid)
    if budget is not None: guest_deadline(budget, value)
    if not root.exists() and not root.is_symlink(): return envelope(value, 'NOT_FOUND')
    owned(root, uid, True)
    if budget is not None:
        if not (root/'deadline.json').exists() and not (root/'deadline.json').is_symlink():
            return envelope(value, 'UNCERTAIN')
        need(decode(read(root/'deadline.json', uid)) == budget, 'delivery deadline changed')
    if not (root/'request.json').exists() and not (root/'request.json').is_symlink(): return envelope(value, 'UNCERTAIN')
    need(decode(read(root/'request.json', uid)) == value, 'delivery request identity')
    if not (root/'receipt.json').exists() and not (root/'receipt.json').is_symlink(): return envelope(value, 'UNCERTAIN')
    answer = decode(read(root/'receipt.json', uid))
    need(answer.get('state') in ('SUCCEEDED', 'FAILED') and all(answer.get(k) == v for k, v in envelope(value, answer['state']).items()), 'delivery receipt identity')
    if answer['state'] == 'SUCCEEDED': need(answer['inventory'] == verify(root, value, uid), 'delivery receipt inventory')
    return answer


def install(parent, value, uid, stream, deadline, *, budget=None):
    descriptor(value); root = location(parent, value, uid)
    if budget is not None: need(guest_deadline(budget, value) == deadline, 'delivery deadline mismatch')
    need(time.monotonic() < deadline, 'delivery original deadline')
    if root.exists() or root.is_symlink(): return query(parent, value, uid, budget=budget)
    root.mkdir(mode=0o700); sync(root.parent)  # Consumed before reading bytes.
    if budget is not None: publish(root/'deadline.json', budget)
    publish(root/'request.json', value)
    try:
        raw = stream.read(value['payloadBytes']+1)
        files = payload(raw, value); need(time.monotonic() < deadline, 'delivery original deadline')
        write(root/'payload.json', raw)
        (root/'files').mkdir(mode=0o700); sync(root)
        for name, data in sorted(files.items()):
            need(time.monotonic() < deadline, 'delivery original deadline')
            # mkdir(parents=True) applies mode only to the last directory. Build
            # each closed component explicitly so umask=0002 cannot create 0775
            # intermediates that our ownership check correctly rejects.
            parent = root/'files'
            for component in Path(name).parts[:-1]:
                parent = parent/component
                try: parent.mkdir(mode=0o700)
                except FileExistsError: owned(parent, uid, True)
            path = root/'files'/name
            write(path, data)
        for path in sorted((root/'files').rglob('*'), reverse=True):
            if path.is_dir(): sync(path)
        sync(root/'files'); sync(root)
        answer = envelope(value, 'SUCCEEDED', inventory=verify(root, value, uid))
        need(time.monotonic() < deadline, 'delivery original deadline')
    except (Exception, KeyboardInterrupt) as error:
        answer = envelope(value, 'FAILED', error=dict(type=type(error).__name__, message=str(error)[:1000]))
    publish(root/'receipt.json', answer); return answer


def main():
    # Trusted source is sent via python -I -c; no installed module imports here.
    action, parent, encoded, uid, token = sys.argv[1:]
    value = descriptor(decode(base64.b64decode(encoded, validate=True))); uid = int(uid)
    if action == 'clock':
        location(parent, value, uid)  # Read-only, before any consumed installation.
        print(canonical(clock_sample(value, token)).decode(), flush=True); return
    budget = validate_budget(decode(base64.b64decode(token, validate=True)), value)
    deadline = guest_deadline(budget, value)
    if action == 'install': answer = install(parent, value, uid, sys.stdin.buffer, deadline, budget=budget)
    elif action in ('query', 'check'):
        answer = query(parent, value, uid, budget=budget)
        if action == 'check':
            need(answer['state'] == 'SUCCEEDED', 'delivery helper unavailable')
            root = location(parent, value, uid)
            result = subprocess.run([sys.executable, '-I', str(root/'files/helper.py')], stdin=subprocess.DEVNULL,
                                    capture_output=True, timeout=max(.001, deadline-time.monotonic()), check=True)
            need(len(result.stdout) <= 4096 and len(result.stderr) <= 4096 and
                 decode(result.stdout) == dict(status='PASS', nativeWritesEnabled=False), 'delivery helper check')
            need(query(parent, value, uid, budget=budget) == answer, 'delivery helper changed after check')
    else: raise ValueError('delivery action')
    guest_deadline(budget, value)
    print(canonical(dict(schema='gse-v51-helper-transport-v1', deadlineSha256=sha(canonical(budget)), receipt=answer)).decode(), flush=True)


if __name__ == '__main__': main()
