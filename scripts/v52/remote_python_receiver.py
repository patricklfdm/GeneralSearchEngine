"""Standalone bounded Python capsule installer. No payload imports occur here.

Invoke this trusted source with Python -I -S. An authenticated controller supplies
an exact descriptor digest; an installed manifest alone is never an authority.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

SCHEMA = 'gse-v52-python-capsule-v1'
RECEIPT = 'gse-v52-python-install-v1'
ENTRIES = ('scripts.v52.remote_delivery_guest', 'scripts.v52.remote_partition_guest',
           'scripts.v52.remote_restart_guest', 'scripts.v52.remote_voter_guest',
           'scripts.v52.remote_voter_relay')
DATA = frozenset((
    'pom.xml',
    'docs/v5x/v5.1/phase6-plan.json',
    'docs/v5x/v5.1/phase6-cloud-workload-plan.json',
    'docs/v5x/v5.1/published-controls.json',
    'docs/v5x/v5.2/phase5-hardening-plan.json',
    'docs/v5x/v5.2/phase6-program.json',
    'docs/v5x/v5.2/phase6-cloud-suite.json',
    'docs/v5x/v5.2/phase6-local-machine.json',
    'docs/v5x/v5.2/published-controls.json',
    'general-search-engine-replication/src/test/resources/replication/v51/format-catalog.json',
    'general-search-engine-replication/src/test/resources/replication/v51/bootstrap-catalog.json',
    'general-search-engine-replication/src/test/resources/replication/v51/runtime-wire-extension.json',
    'general-search-engine-replication/src/test/resources/replication/v51/rejoin-wire-extension.json',
))
MAX_FILES = 512
MAX_FILE = 512 << 10
MAX_EXPANDED = 4 << 20
MAX_PAYLOAD = 6 << 20
MAX_MANIFEST = 128 << 10
MAX_REQUEST = MAX_PAYLOAD + MAX_MANIFEST + 4096


def need(value, message):
    if not value:
        raise ValueError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(raw):
    def pairs(items):
        value = dict(items)
        need(len(value) == len(items), 'duplicate Python capsule field')
        return value
    def constant(_):
        raise ValueError('nonfinite Python capsule field')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def hex_value(value, length):
    need(type(value) is str and re.fullmatch('[0-9a-f]{%d}' % length, value), 'Python capsule digest')


def name(value):
    need(type(value) is str and len(value) <= 256, 'Python capsule path')
    if value in DATA:
        return value
    need(re.fullmatch(r'scripts/(?:[a-z][a-z0-9_]*/)*[a-z_][a-z0-9_]*\.py', value) and
         not any(part.startswith('test_') or part in ('__pycache__', 'tests') for part in value.split('/')),
         'Python capsule undeclared path')
    return value


def descriptor(value):
    need(type(value) is dict and set(value) == {'schema', 'source', 'entries', 'files', 'bytes', 'sha256'} and
         value['schema'] == SCHEMA and value['entries'] == list(ENTRIES), 'Python capsule descriptor')
    source = value['source']
    need(type(source) is dict and set(source) == {'source', 'checkoutSha256', 'java'}, 'Python capsule source fields')
    hex_value(source['source'], 40); hex_value(source['checkoutSha256'], 64)
    need(type(source['java']) is dict and set(source['java']) == {'java.runtime.version', 'java.vendor'} and
         all(type(v) is str and 0 < len(v) <= 256 for v in source['java'].values()), 'Python capsule Java binding')
    files = value['files']
    need(type(files) is dict and 0 < len(files) <= MAX_FILES and DATA <= files.keys(), 'Python capsule inventory')
    need(all(entry.replace('.', '/') + '.py' in files for entry in ENTRIES), 'Python capsule missing entry')
    total = 0
    for path, row in files.items():
        name(path)
        need(type(row) is dict and set(row) == {'bytes', 'sha256'} and type(row['bytes']) is int and
             0 <= row['bytes'] <= MAX_FILE, 'Python capsule member bound')
        hex_value(row['sha256'], 64); total += row['bytes']
    need(total <= MAX_EXPANDED and len(encoded(value)) <= MAX_MANIFEST, 'Python capsule expansion/manifest bound')
    need(type(value['bytes']) is int and 0 < value['bytes'] <= MAX_PAYLOAD, 'Python capsule payload bound')
    hex_value(value['sha256'], 64)
    return value


def payload(raw, value):
    descriptor(value)
    need(type(raw) is bytes and len(raw) == value['bytes'] and digest(raw) == value['sha256'], 'Python capsule payload changed')
    body = decode(raw)
    need(type(body) is dict and set(body) == {'schema', 'files'} and body['schema'] == SCHEMA and
         type(body['files']) is dict and set(body['files']) == set(value['files']), 'Python capsule payload inventory')
    result = {}
    for path, content in body['files'].items():
        row = value['files'][path]
        need(type(content) is str and len(content) == 4 * ((row['bytes'] + 2) // 3), 'Python capsule encoded bound')
        data = base64.b64decode(content, validate=True)
        need(len(data) == row['bytes'] and digest(data) == row['sha256'], 'Python capsule member changed')
        result[path] = data
    return result


def owned(path, directory=False):
    info = path.lstat()
    need((stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)) and
         info.st_uid == os.getuid() and info.st_mode & 0o077 == 0 and (directory or info.st_nlink == 1),
         'Python capsule owned path')
    return info


def location(parent, value):
    parent = Path(parent)
    need(parent.is_absolute() and '..' not in parent.parts and str(parent) == str(parent.absolute()), 'Python capsule absolute parent')
    for p in (parent, *parent.parents):
        info = p.lstat()
        need(stat.S_ISDIR(info.st_mode) and info.st_uid in (0, os.getuid()) and
             (not info.st_mode & 0o022 or info.st_uid == 0 and info.st_mode & stat.S_ISVTX), 'Python capsule linked/writable ancestor')
    owned(parent, True)
    return parent / ('python-' + value['sha256'])


def sync(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    sync(path.parent)


def read(path, maximum):
    owned(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid() and
             info.st_mode & 0o077 == 0 and info.st_size <= maximum, 'Python capsule read bound/type')
        raw = stream.read(maximum + 1)
    need(len(raw) <= maximum, 'Python capsule read bound')
    return raw


def host(parent):
    info = owned(parent, True)
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    need(re.fullmatch(r'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}', boot), 'Python capsule boot identity')
    return dict(bootId=boot, uid=os.getuid(), parentDevice=info.st_dev, parentInode=info.st_ino)


def installed(root, value):
    descriptor(value); root = Path(root)
    need(root == location(root.parent, value), 'Python capsule destination identity')
    owned(root, True)
    need(decode(read(root/'descriptor.json', MAX_MANIFEST)) == value, 'Python capsule installed descriptor changed')
    own = root/'files'; owned(own, True)
    expected_dirs = {str(p) for n in value['files'] for p in Path(n).parents if str(p) != '.'}
    files = set(); dirs = set()
    for path in own.rglob('*'):
        relative = path.relative_to(own).as_posix()
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            need(relative in expected_dirs, 'Python capsule extra directory'); owned(path, True); dirs.add(relative)
        else:
            need(relative in value['files'], 'Python capsule extra file')
            row = value['files'][relative]; raw = read(path, row['bytes'])
            need(len(raw) == row['bytes'] and digest(raw) == row['sha256'], 'Python capsule installed bytes changed')
            files.add(relative)
    need(files == set(value['files']) and dirs == expected_dirs, 'Python capsule incomplete installation')
    need({p.name for p in root.iterdir()} == {'descriptor.json', 'files', 'receipt.json'}, 'Python capsule incomplete/extra root')
    receipt = decode(read(root/'receipt.json', MAX_MANIFEST))
    need(receipt == dict(schema=RECEIPT, descriptorSha256=digest(encoded(value)), root=str(root),
                         host=host(root.parent), filesSha256=digest(encoded(value['files']))), 'Python capsule installation receipt changed')
    return receipt


def install(parent, value, raw):
    files = payload(raw, value)  # Check every input before consuming a destination.
    root = location(parent, value)
    root.mkdir(mode=0o700); sync(root.parent)  # Partial installs remain consumed.
    write(root/'descriptor.json', encoded(value))
    own = root/'files'; own.mkdir(mode=0o700); sync(root)
    for name_, data in sorted(files.items()):
        path = own/name_
        for p in reversed(path.parent.relative_to(own).parents):
            if str(p) != '.':
                (own/p).mkdir(mode=0o700, exist_ok=True)
        path.parent.mkdir(mode=0o700, exist_ok=True)
        write(path, data)
    # Force directory entries before publishing the only completed receipt.
    for path in sorted((p for p in own.rglob('*') if p.is_dir()), key=lambda p:len(p.parts), reverse=True):
        sync(path)
    sync(own)
    receipt = dict(schema=RECEIPT, descriptorSha256=digest(encoded(value)), root=str(root),
                   host=host(root.parent), filesSha256=digest(encoded(value['files'])))
    write(root/'receipt.json', encoded(receipt))
    return installed(root, value)


def main():
    # Never import or execute an entry from the wire. Installation/verification
    # is independent of subsequent workload launch admission.
    need(len(sys.argv) == 4 and sys.argv[1] in ('install', 'verify'), 'Python capsule action')
    hex_value(sys.argv[3], 64)
    raw = sys.stdin.buffer.read(MAX_REQUEST + 1)
    need(len(raw) <= MAX_REQUEST, 'Python capsule request bound')
    request = decode(raw)
    need(type(request) is dict and set(request) == {'descriptor', 'payload'} and
         digest(encoded(request['descriptor'])) == sys.argv[3], 'Python capsule trusted descriptor changed')
    value = descriptor(request['descriptor'])
    if sys.argv[1] == 'install':
        need(type(request['payload']) is str and len(request['payload']) <= MAX_PAYLOAD, 'Python capsule wire payload')
        result = install(sys.argv[2], value, request['payload'].encode('ascii'))
    else:
        need(request['payload'] is None, 'Python capsule verify payload')
        result = installed(location(sys.argv[2], value), value)
    sys.stdout.buffer.write(encoded(result) + b'\n')


if __name__ == '__main__':
    main()
