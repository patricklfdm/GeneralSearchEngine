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
    native = value.get('schema') == 'gse-v51-native-package-transfer-v1' if type(value) is dict else False
    fields = {'schema', 'binding', 'instanceId', 'diskId', 'guestAccessSha256',
              'archiveBytes', 'manifestSha256', 'buildManifestSha256', 'parts'}
    r.need(type(value) is dict and set(value) == fields | ({'nativeVolume'} if native else set()), 'package transfer fields')
    r.need(native or value['schema'] == 'gse-v51-package-transfer-v1', 'package transfer schema')
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
    if value['schema'] == 'gse-v51-native-package-transfer-v1':
        return dict(schema='gse-v51-native-package-transfer-receipt-v1',requestSha256=r.sha(r.canonical(value)),
                    state=state,completedParts=completed,execution='native-guest-package',fullRemoteQualification=False,**fields)
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


def bootstrap(parent, value, budget, tail):
    """Use the original package deadline before importing verified bootstrap code."""
    base = installed(parent,value)
    r.need(read(base.parent/'deadline.json') == budget, 'bootstrap original package deadline changed')
    r.need(len(tail) == 2 and tail[0] in ('install','seal','query-install','query-seal'), 'bootstrap action')
    action, encoded = tail
    r.need(len(encoded) <= 65536, 'bootstrap request bound')
    request = r.decode(base64.b64decode(encoded,validate=True))
    transferred = set(request) == {'config','sourceTransferSha256','descriptorSha256'}
    r.need(transferred or set(request) == {'config','folder','descriptorSha256'}, 'bootstrap request fields')
    config = request['config']
    r.need(config['binding'] == value['binding'] and config['packageManifestSha256'] == value['manifestSha256'] and
           config['root'] == str(Path(parent)/config['mode']), 'bootstrap installed configuration binding')
    sys.dont_write_bytecode = True; sys.path.insert(0,str(base/'source-inputs'))
    from scripts.v51 import guest_bootstrap as boot, cloud_guest as guest
    guest.validate(config); deadline = r.guest_deadline(budget,identity(value))
    digest = request['descriptorSha256']
    if transferred:
        from scripts.v51 import guest_source_transfer as source
        folder = source.received(base,config,digest,lambda:r.guest_deadline(budget,identity(value)))
        r.need(r.sha(r.canonical(source.read(folder.parent/'request.json'))) == request['sourceTransferSha256'],
               'bootstrap transferred source identity')
    else: folder = Path(request['folder'])
    if action.startswith('query-'): answer = boot.observe(config,action[6:],digest)
    elif action == 'install':
        # The exclusive cell mkdir consumes even a crash before bootstrap's claim.
        root = Path(config['root']); r.owned(root.parent,os.getuid(),True)
        root.mkdir(mode=0o700); r.sync(root.parent)
        answer = dict(state='SUCCEEDED',result=boot.install(folder,digest,config))
    else:
        r.need(boot.observe(config,'install',digest)['state'] == 'SUCCEEDED', 'bootstrap seed not ready')
        answer = dict(state='SUCCEEDED',result=boot.seal(base,config,deadline=deadline))
    r.guest_deadline(budget,identity(value))
    return dict(schema='gse-v51-package-bootstrap-v1',action=action,requestSha256=r.sha(r.canonical(request)),
        deadlineSha256=r.sha(r.canonical(budget)),receipt=answer)


def source_transfer(parent, value, budget, tail, stream):
    base=installed(parent,value)
    r.need(read(base.parent/'deadline.json')==budget,'source original package deadline changed')
    r.need(len(tail) in (2,3) and tail[0] in ('begin','chunk','finish','query') and
           (len(tail)==3)==(tail[0]=='chunk') and len(tail[1])<=90000,'source transfer arguments')
    action=tail[0];request=r.decode(base64.b64decode(tail[1],validate=True));config=request['config']
    r.need(config['binding']==value['binding'] and config['packageManifestSha256']==value['manifestSha256'] and
           config['root']==str(Path(parent)/config['mode']),'source installed configuration binding')
    sys.dont_write_bytecode=True;sys.path.insert(0,str(base/'source-inputs'))
    from scripts.v51 import guest_source_transfer as source
    check=lambda:r.guest_deadline(budget,identity(value))
    check();source.validate(request)
    if action=='chunk': answer=source.put(base,request,int(tail[2]),stream,check)
    else: answer=getattr(source,action)(base,request,check)
    check()
    return dict(schema='gse-v51-package-source-v1',action=action,requestSha256=r.sha(r.canonical(request)),
        deadlineSha256=r.sha(r.canonical(budget)),receipt=answer)


def producer(parent,value,budget,tail):
    base=installed(parent,value)
    r.need(read(base.parent/'deadline.json')==budget,'producer original package deadline changed')
    r.need(len(tail) in (2,3,4) and tail[0] in ('prepare','query','manifest','chunk') and len(tail[1])<=90000,
           'producer arguments')
    action=tail[0]
    r.need(len(tail)==(4 if action=='chunk' else 3 if action=='manifest' else 2),'producer action arguments')
    request=r.decode(base64.b64decode(tail[1],validate=True));config=request['configs'][0]
    r.need(value['binding']['node']=='node-1' and config['binding']==value['binding'] and
           config['packageManifestSha256']==value['manifestSha256'] and config['root']==str(Path(parent)/config['mode']),
           'producer installed configuration binding')
    sys.dont_write_bytecode=True;sys.path.insert(0,str(base/'source-inputs'))
    from scripts.v51 import guest_source_producer as source
    source.validate(request);check=lambda:r.guest_deadline(budget,identity(value));deadline=check()
    if action=='prepare':answer=source.prepare(base,request,deadline,check)
    elif action=='query':answer=source.query(base,request,check)
    elif action=='manifest':answer=source.observe(base,request,tail[2],check)
    else:answer=source.chunk(base,request,tail[2],int(tail[3]),check)
    check()
    if action=='chunk':return answer
    return dict(schema='gse-v51-package-producer-v1',action=action,requestSha256=r.sha(r.canonical(request)),
        deadlineSha256=r.sha(r.canonical(budget)),receipt=answer)


def main():
    action, parent, encoded, token, *tail = sys.argv[1:]
    r.need(len(encoded) <= 131072 and len(token) <= 4096, 'package transfer envelope bound')
    value = descriptor(r.decode(base64.b64decode(encoded, validate=True)))
    r.need(value['schema'] == 'gse-v51-package-transfer-v1', 'native package requires admitted receiver')
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
        if action=='producer':
            answer=producer(parent,value,budget,tail)
            sys.stdout.buffer.write(answer if isinstance(answer,bytes) else r.canonical(answer)+b'\n');sys.stdout.buffer.flush();return
        if action == 'source':
            print(r.canonical(source_transfer(parent,value,budget,tail,sys.stdin.buffer)).decode(),flush=True); return
        if action == 'bootstrap':
            print(r.canonical(bootstrap(parent,value,budget,tail)).decode(),flush=True); return
        r.need(action == 'part' and len(tail) == 1 or action in ('begin','query','finish') and not tail, 'package transfer action')
        if action == 'begin': answer = begin(parent, value, budget)
        elif action == 'part': answer = put(parent, value, budget, int(tail[0]), sys.stdin.buffer)
        elif action == 'finish': answer = finish(parent, value, budget)
        else: answer = query(parent, value, budget)
        r.guest_deadline(budget, identity(value))
        print(r.canonical(dict(schema='gse-v51-package-transport-v1', deadlineSha256=r.sha(r.canonical(budget)), receipt=answer)).decode(), flush=True)
    finally: signal.setitimer(signal.ITIMER_REAL, 0)
