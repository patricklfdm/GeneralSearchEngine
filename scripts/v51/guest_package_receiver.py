"""Trusted, unprivileged, at-most-once package transfer. Never imports staged code."""
import base64
import hashlib
import os
from pathlib import Path
import re
import signal
import sys
import time
from . import cloud_package as package, guest_delivery_receiver as r

PART_BYTES = 1 << 20


def descriptor(value):
    r.need(type(value) is dict and set(value) == {'schema', 'binding', 'instanceId', 'diskId', 'guestAccessSha256',
           'archiveBytes', 'manifestSha256', 'buildManifestSha256', 'parts'}, 'package transfer fields')
    r.need(value['schema'] == 'gse-v51-package-transfer-v1', 'package transfer schema')
    # Reuse the established binding/identity validators, without changing their
    # helper-payload bound. This descriptor is metadata, not a helper payload.
    identity(value)
    r.need(type(value['archiveBytes']) is int and 0 < value['archiveBytes'] <= package.MAX_BYTES,
           'package transfer archive bound')
    for key in ('manifestSha256', 'buildManifestSha256'):
        r.need(isinstance(value[key], str) and re.fullmatch('[0-9a-f]{64}', value[key]), 'package transfer digest')
    parts = value['parts']; count = (value['archiveBytes']+PART_BYTES-1)//PART_BYTES
    r.need(type(parts) is list and len(parts) == count, 'package transfer part count')
    for i, part in enumerate(parts):
        r.need(type(part) is dict and set(part) == {'index', 'bytes', 'sha256'} and type(part['index']) is int and
               part['index'] == i and type(part['bytes']) is int and part['bytes'] == min(PART_BYTES, value['archiveBytes']-i*PART_BYTES) and
               isinstance(part['sha256'], str) and re.fullmatch('[0-9a-f]{64}', part['sha256']), 'package transfer part identity')
    return value


def identity(value):
    """Existing boot/deadline machinery authenticates the complete descriptor bytes."""
    raw = r.canonical(value)
    return r.descriptor(dict(schema='gse-v51-helper-delivery-v1', binding=value['binding'], instanceId=value['instanceId'],
        diskId=value['diskId'], guestAccessSha256=value['guestAccessSha256'], payloadSha256=r.sha(raw), payloadBytes=len(raw)))


def location(parent, value): return r.location(parent, identity(value), os.getuid())
def read(path): return r.decode(r.read(path, os.getuid()))
def exists(path): return path.exists() or path.is_symlink()


def envelope(value, state, completed=0, **fields):
    return dict(schema='gse-v51-package-transfer-receipt-v1', requestSha256=r.sha(r.canonical(value)), state=state,
                completedParts=completed, paidCloud=False, fullRemoteQualification=False, **fields)


def verify(root, value):
    r.owned(root/'package', os.getuid(), True)
    manifest = package.verify(root/'package', value['binding']['source'])
    r.need(r.sha(r.read(root/'package/manifest.json', os.getuid(), 4 << 20)) == value['manifestSha256'] and
           manifest['buildManifestSha256'] == value['buildManifestSha256'] and
           r.sha(r.canonical(package.read(root/'package/workload.json'))) == value['binding']['workloadSha256'],
           'installed package manifest/build/workload identity')
    return dict(package=str(root/'package'), manifestSha256=value['manifestSha256'], files=len(manifest['files']))


def query(parent, value, budget):
    descriptor(value); r.guest_deadline(budget, identity(value)); root = location(parent, value)
    if not exists(root): return envelope(value, 'NOT_FOUND')
    r.owned(root, os.getuid(), True)
    if not exists(root/'deadline.json'): return envelope(value, 'UNCERTAIN')
    r.need(read(root/'deadline.json') == budget, 'package original deadline changed')
    if not exists(root/'request.json'): return envelope(value, 'UNCERTAIN')
    r.need(read(root/'request.json') == value, 'package original descriptor changed')
    for i, part in enumerate(value['parts']):
        folder = root/('part-%04d' % i)
        if not exists(folder): return envelope(value, 'RECEIVING', i)
        r.owned(folder, os.getuid(), True)
        if not exists(folder/'receipt.json'): return envelope(value, 'UNCERTAIN', i)
        receipt = read(folder/'receipt.json')
        r.need(receipt['part'] == part and receipt['state'] in ('SUCCEEDED', 'FAILED'), 'package part receipt')
        if receipt['state'] == 'FAILED': return envelope(value, 'FAILED', i, error=receipt['error'])
        raw = r.read(folder/'data.bin', os.getuid(), PART_BYTES)
        r.need(len(raw) == part['bytes'] and r.sha(raw) == part['sha256'], 'retained package part changed')
    count = len(value['parts'])
    if not exists(root/'install'): return envelope(value, 'READY', count)
    r.owned(root/'install', os.getuid(), True)
    if not exists(root/'install/receipt.json'): return envelope(value, 'UNCERTAIN', count)
    receipt = read(root/'install/receipt.json')
    r.need(receipt['state'] in ('SUCCEEDED', 'FAILED') and all(receipt.get(k) == v for k,v in envelope(value, receipt['state'], count).items()),
           'package install receipt')
    if receipt['state'] == 'SUCCEEDED': r.need(receipt['installed'] == verify(root, value), 'installed package changed')
    return receipt


def begin(parent, value, budget):
    answer = query(parent, value, budget)
    if answer['state'] != 'NOT_FOUND': return answer
    root = location(parent, value)
    try: root.mkdir(mode=0o700)
    except FileExistsError: return query(parent, value, budget)
    r.sync(root.parent); r.publish(root/'deadline.json', budget); r.publish(root/'request.json', value)
    return query(parent, value, budget)


def put(parent, value, budget, index, stream):
    r.need(type(index) is int and 0 <= index < len(value['parts']), 'package part index')
    answer = query(parent, value, budget)
    if answer['state'] != 'RECEIVING' or answer['completedParts'] != index: return answer
    root = location(parent, value); folder = root/('part-%04d' % index); part = value['parts'][index]
    try: folder.mkdir(mode=0o700)
    except FileExistsError: return query(parent, value, budget)
    r.sync(root)  # Claim before consuming input; partial part is never resumed.
    try:
        raw = stream.read(part['bytes']+1)
        r.write(folder/'data.bin', raw)  # Retain malformed/partial input for diagnosis.
        r.need(len(raw) == part['bytes'] and r.sha(raw) == part['sha256'], 'package part digest/size')
        r.guest_deadline(budget, identity(value)); receipt = dict(part=part, state='SUCCEEDED')
    except Exception as error:
        receipt = dict(part=part, state='FAILED', error=dict(type=type(error).__name__, message=str(error)[:1000]))
    r.publish(folder/'receipt.json', receipt)
    return query(parent, value, budget)


def finish(parent, value, budget):
    answer = query(parent, value, budget)
    if answer['state'] != 'READY': return answer
    root = location(parent, value)
    try: (root/'install').mkdir(mode=0o700)
    except FileExistsError: return query(parent, value, budget)
    r.sync(root)
    try:
        digest = hashlib.sha256()
        with os.fdopen(os.open(root/'archive.tar.gz', os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW, 0o600), 'wb') as out:
            for part in value['parts']:
                r.guest_deadline(budget, identity(value))
                raw = r.read(root/('part-%04d' % part['index'])/'data.bin', os.getuid(), PART_BYTES)
                r.need(len(raw) == part['bytes'] and r.sha(raw) == part['sha256'], 'package part changed before assembly')
                out.write(raw); digest.update(raw)
            out.flush(); os.fsync(out.fileno())
        r.sync(root)
        r.need(digest.hexdigest() == value['binding']['bundleSha256'], 'package complete archive digest')
        package.unpack(root/'archive.tar.gz', root/'package', digest.hexdigest(), value['binding']['source'])
        for path in sorted((root/'package').rglob('*'), reverse=True):
            if path.is_dir(): path.chmod(0o700); r.sync(path)
            else:
                fd = os.open(path, os.O_RDONLY|os.O_NOFOLLOW)
                try: os.fsync(fd)
                finally: os.close(fd)
        (root/'package').chmod(0o700); r.sync(root/'package'); r.sync(root)
        installed = verify(root, value); r.guest_deadline(budget, identity(value))
        receipt = envelope(value, 'SUCCEEDED', len(value['parts']), installed=installed)
    except Exception as error:
        receipt = envelope(value, 'FAILED', len(value['parts']), error=dict(type=type(error).__name__, message=str(error)[:1000]))
    r.publish(root/'install/receipt.json', receipt); return query(parent, value, budget)


def installed(parent, value):
    """Completed installation is usable after its transfer deadline; no new writes."""
    root = location(parent, value); r.owned(root, os.getuid(), True)
    r.need(read(root/'request.json') == value, 'service package descriptor changed')
    budget = r.validate_budget(read(root/'deadline.json'), identity(value))
    r.need(budget['sample']['bootId'] == r.boot_identity(), 'service package boot changed')
    r.owned(root/'install', os.getuid(), True)
    receipt = read(root/'install/receipt.json')
    r.need(all(receipt.get(k) == v for k,v in envelope(value, 'SUCCEEDED', len(value['parts'])).items()) and
           receipt.get('installed') == verify(root, value), 'service requires completed package installation')
    return root/'package'


def service(parent, value, token, tail):
    base = installed(parent, value)  # Before importing any delivered Python.
    config = r.decode(base64.b64decode(token, validate=True))
    r.need(config['binding'] == value['binding'] and config['packageManifestSha256'] == value['manifestSha256'],
           'service transfer/configuration binding')
    r.need(tail and tail[0] in ('start','query','submit','cancel','shutdown','ready','part') and
           (tail[0] == 'part' and len(tail) == 3 and tail[1] == '--part' or tail[0] != 'part' and len(tail) == 1),
           'delivered service action')
    sys.dont_write_bytecode = True; sys.path.insert(0, str(base/'source-inputs'))
    from scripts.v51 import cloud_guest as guest
    target = guest.validate(config)
    if tail[0] == 'start':
        raw = sys.stdin.buffer.read((64 << 10)+1)
        r.need(len(raw) <= 64 << 10 and r.decode(raw) == config, 'service start input changed')
        print(r.canonical(guest.start(base, config)).decode(), flush=True)
    else:
        r.need(read(target/'config.json') == config, 'service retained configuration changed')
        guest.main(base, [tail[0], str(target/'config.json'), *tail[1:]])


def main():
    action, parent, encoded, token, *tail = sys.argv[1:]
    r.need(len(encoded) <= 131072 and len(token) <= 4096, 'package transfer envelope bound')
    value = descriptor(r.decode(base64.b64decode(encoded, validate=True)))
    if action == 'service':
        service(parent, value, token, tail); return
    if action == 'clock':
        r.need(not tail, 'package clock arguments'); location(parent, value)
        print(r.canonical(r.clock_sample(identity(value), token)).decode(), flush=True); return
    budget = r.validate_budget(r.decode(base64.b64decode(token, validate=True)), identity(value))
    deadline = r.guest_deadline(budget, identity(value))
    def expired(*_): raise TimeoutError('package original deadline')
    signal.signal(signal.SIGALRM, expired); signal.setitimer(signal.ITIMER_REAL, max(.001, deadline-time.monotonic()))
    try:
        r.need(action == 'part' and len(tail) == 1 or action in ('begin','query','finish') and not tail, 'package transfer action')
        if action == 'begin': answer = begin(parent, value, budget)
        elif action == 'part': answer = put(parent, value, budget, int(tail[0]), sys.stdin.buffer)
        elif action == 'finish': answer = finish(parent, value, budget)
        else: answer = query(parent, value, budget)
        r.guest_deadline(budget, identity(value))
        print(r.canonical(dict(schema='gse-v51-package-transport-v1', deadlineSha256=r.sha(r.canonical(budget)), receipt=answer)).decode(), flush=True)
    finally: signal.setitimer(signal.ITIMER_REAL, 0)
