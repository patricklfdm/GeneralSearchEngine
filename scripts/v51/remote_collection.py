"""Complete binary evidence parts, independently checked before extraction.

An interrupted part can be downloaded again by immutable digest. This permission
applies only to evidence bytes, never to workload commands or mutations.
"""
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import stat
import tarfile
from . import cloud_workload_contract as contract, performance_model as m
from .remote_command import directory, read, write_once, sync_directory

LIMITS = contract.load()['evidence']
INDEX = 'evidence-members.json'


def safe_name(name):
    m.need(isinstance(name, str) and name and '\\' not in name and '\x00' not in name, 'unsafe evidence name')
    path = PurePosixPath(name)
    m.need(not path.is_absolute() and path.as_posix() == name and all(p not in ('', '.', '..') for p in path.parts), 'unsafe evidence path')
    return path


def inventory(root):
    root = directory(root)
    result, total, traces = {}, 0, 0
    for path in sorted(root.rglob('*')):
        m.need(not path.is_symlink(), 'evidence symlink')
        if path.is_dir():
            continue
        m.need(stat.S_ISREG(path.stat().st_mode), 'evidence regular file required')
        name = path.relative_to(root).as_posix()
        safe_name(name)
        m.need(name != INDEX, 'reserved evidence inventory name')
        size = path.stat().st_size
        total += size
        if name.endswith(('.jsonl', '.log')):
            traces += size
        m.need(size <= LIMITS['memberBytes'] and total <= LIMITS['expandedBytes'] and
               traces <= LIMITS['traceBytes'] and len(result) < LIMITS['files']-1, 'evidence file/byte budget')
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b''):
                digest.update(chunk)
        result[name] = dict(bytes=size, sha256=digest.hexdigest())
    return result


class PartWriter:
    def __init__(self, root):
        self.root, self.parts, self.current, self.total = root, [], None, 0

    def flush(self):
        if self.current:
            self.current.flush()

    def finish_part(self):
        if self.current is None:
            return
        self.current.flush()
        os.fsync(self.current.fileno())
        self.current.close()
        temporary = self.root / (self.name + '.partial')
        os.rename(temporary, self.root / self.name)
        sync_directory(self.root)
        self.parts.append(dict(name=self.name, bytes=self.size, sha256=self.digest.hexdigest()))
        self.current = None

    def write(self, data):
        original = len(data)
        m.need(self.total + original <= LIMITS['compressedBytes'], 'compressed evidence budget')
        while data:
            if self.current is None:
                m.need(len(self.parts) < LIMITS['parts'], 'evidence part count')
                self.name = f'part-{len(self.parts):04d}.bin'
                self.current = (self.root / (self.name + '.partial')).open('xb')
                self.size, self.digest = 0, hashlib.sha256()
            chunk = data[:LIMITS['partBytes']-self.size]
            self.current.write(chunk)
            self.digest.update(chunk)
            self.size += len(chunk)
            self.total += len(chunk)
            data = data[len(chunk):]
            if self.size == LIMITS['partBytes']:
                self.finish_part()
        return original

    def abort(self):
        if self.current:
            self.current.close()
            self.current = None


def pack(root, target, binding_sha256):
    root, target = directory(root), Path(target).absolute()
    m.need(root not in target.parents and root != target, 'parts must be outside evidence')
    directory(target.parent)
    target.mkdir(mode=0o700)
    members = inventory(root)
    index = m.canonical(members) + b'\n'
    m.need(len(index) <= LIMITS['responseBytes'] and sum(v['bytes'] for v in members.values())+len(index) <= LIMITS['expandedBytes'], 'evidence index budget')
    writer = PartWriter(target)
    try:
        with tarfile.open(fileobj=writer, mode='w|gz', format=tarfile.USTAR_FORMAT) as archive:
            for name, entry in members.items():
                info = tarfile.TarInfo(name)
                info.size, info.mode = entry['bytes'], 0o600
                with (root / name).open('rb') as stream:
                    archive.addfile(info, stream)
            info = tarfile.TarInfo(INDEX)
            info.size, info.mode = len(index), 0o600
            archive.addfile(info, io.BytesIO(index))
        writer.finish_part()
        m.need(inventory(root) == members, 'evidence changed during collection')
        manifest = dict(schema='gse-v51-binary-evidence-v1', bindingSha256=binding_sha256,
                        workloadSha256=contract.PLAN_SHA256, memberIndexSha256=m.sha(index),
                        parts=writer.parts, compressedBytes=writer.total)
        validate_manifest(manifest, binding_sha256)
        write_once(target / 'parts.json', manifest)
        return manifest
    finally:
        writer.abort()


def validate_manifest(value, binding_sha256):
    m.need(set(value) == {'schema', 'bindingSha256', 'workloadSha256', 'memberIndexSha256', 'parts', 'compressedBytes'}, 'parts fields')
    m.need(value['schema'] == 'gse-v51-binary-evidence-v1' and value['bindingSha256'] == binding_sha256 and
           value['workloadSha256'] == contract.PLAN_SHA256, 'parts binding')
    import re
    for digest in (binding_sha256, value['memberIndexSha256']):
        m.need(isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest), 'collection digest')
    parts = value['parts']
    m.need(isinstance(parts, list) and 0 < len(parts) <= LIMITS['parts'], 'parts count')
    for i, part in enumerate(parts):
        m.need(set(part) == {'name', 'bytes', 'sha256'} and part['name'] == f'part-{i:04d}.bin', 'parts order/name')
        m.need(type(part['bytes']) is int and 0 < part['bytes'] <= LIMITS['partBytes'] and
               (i == len(parts)-1 or part['bytes'] == LIMITS['partBytes']), 'part size')
        m.need(isinstance(part['sha256'], str) and re.fullmatch('[0-9a-f]{64}', part['sha256']), 'part hash')
    m.need(type(value['compressedBytes']) is int and sum(p['bytes'] for p in parts) == value['compressedBytes'] <= LIMITS['compressedBytes'], 'compressed total')
    m.need(len(m.canonical(value)) <= LIMITS['responseBytes'], 'parts metadata limit')


def receive_part(target, part, chunks):
    """chunks yields bounded binary blocks, not JSON/base64 responses."""
    target = directory(target)
    m.need(part['name'].startswith('part-') and safe_name(part['name']).name == part['name'], 'part path')
    final = target / part['name']
    m.need(not final.exists() and not final.is_symlink(), 'part already retained; verify it before reuse')
    temporary = target / (part['name'] + '.partial')
    # A previous interrupted fetch may exist. Keep it; a fresh download directory
    # is required. Never overwrite a partially retained attempt's bytes.
    digest, size = hashlib.sha256(), 0
    with temporary.open('xb') as stream:
        for chunk in chunks:
            m.need(isinstance(chunk, bytes) and 0 < len(chunk) <= 1 << 20, 'binary block limit')
            size += len(chunk)
            m.need(size <= part['bytes'] <= LIMITS['partBytes'], 'part overflow')
            stream.write(chunk)
            digest.update(chunk)
        stream.flush()
        os.fsync(stream.fileno())
    m.need(size == part['bytes'] and digest.hexdigest() == part['sha256'], 'part incomplete/hash mismatch')
    os.rename(temporary, final)
    sync_directory(target)


class PartsReader:
    def __init__(self, root, parts):
        self.root, self.parts, self.ordinal, self.current = root, parts, 0, None

    def read(self, size):
        m.need(0 < size <= 1 << 20, 'archive input read size')
        result = b''
        while len(result) < size and self.ordinal < len(self.parts):
            if self.current is None:
                self.current = (self.root / self.parts[self.ordinal]['name']).open('rb')
            chunk = self.current.read(size-len(result))
            if chunk:
                result += chunk
            else:
                self.current.close()
                self.current = None
                self.ordinal += 1
        return result

    def close(self):
        if self.current:
            self.current.close()


def unpack(parts_root, target, binding_sha256):
    parts_root = directory(parts_root)
    manifest = read(parts_root / 'parts.json')
    validate_manifest(manifest, binding_sha256)
    m.need({p.name for p in parts_root.iterdir()} == {'parts.json', *(p['name'] for p in manifest['parts'])}, 'missing/extra evidence part')
    for part in manifest['parts']:
        path = parts_root / part['name']
        m.need(not path.is_symlink() and path.is_file() and path.stat().st_size == part['bytes'], 'part size/type')
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b''):
                digest.update(chunk)
        m.need(digest.hexdigest() == part['sha256'], 'part hash')
    target = Path(target).absolute()
    directory(target.parent)
    target.mkdir(mode=0o700)
    total, traces, actual = 0, 0, {}
    source = PartsReader(parts_root, manifest['parts'])
    try:
        with tarfile.open(fileobj=source, mode='r|gz') as archive:
            for item in archive:
                safe_name(item.name)
                m.need(item.isfile() and item.name not in actual and len(actual) < LIMITS['files'], 'duplicate/non-file/too many archive members')
                total += item.size
                if item.name.endswith(('.jsonl', '.log')):
                    traces += item.size
                m.need(0 <= item.size <= LIMITS['memberBytes'] and total <= LIMITS['expandedBytes'] and traces <= LIMITS['traceBytes'], 'expanded evidence budget')
                destination = target / item.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                with archive.extractfile(item) as stream, destination.open('xb') as output:
                    remaining = item.size
                    while remaining:
                        chunk = stream.read(min(1 << 20, remaining))
                        m.need(chunk, 'truncated archive')
                        output.write(chunk)
                        digest.update(chunk)
                        remaining -= len(chunk)
                actual[item.name] = dict(bytes=item.size, sha256=digest.hexdigest())
    finally:
        source.close()
    m.need(INDEX in actual and actual[INDEX]['bytes'] <= LIMITS['responseBytes'] and
           actual.pop(INDEX)['sha256'] == manifest['memberIndexSha256'], 'evidence member index')
    m.need(read(target / INDEX) == actual, 'evidence inventory differs')
    return dict(status='PASS', files=len(actual), expandedBytes=total, compressedBytes=manifest['compressedBytes'])
