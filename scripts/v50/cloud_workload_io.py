"""Bounded streaming evidence: ordered chunks, strict JSON and read-only inventories."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import zipfile
from .admission_format import check

MIB = 1 << 20
JSON_LIMIT, BINARY_LIMIT, BUNDLE_LIMIT = 16*MIB, 32*MIB, 4096*MIB
LINE_LIMIT, FILE_LIMIT = MIB, 2000


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(MIB), b''): h.update(part)
    return h.hexdigest()


def parse_json(raw):
    check(len(raw) <= JSON_LIMIT, 'JSON member bound')
    def pairs(items):
        result = dict(items); check(len(result) == len(items), 'duplicate JSON key'); return result
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: check(False, 'nonfinite JSON'))
    def bound(v, depth=0):
        check(depth <= 24, 'JSON nesting bound')
        if isinstance(v, dict):
            for child in v.values(): bound(child, depth+1)
        elif isinstance(v, list):
            for child in v: bound(child, depth+1)
        elif type(v) is int: check(-(1 << 63) <= v < 1 << 63, 'JSON integer bound')
    bound(value)
    return value


def read(path):
    check(Path(path).stat().st_size <= JSON_LIMIT, 'JSON member bound')
    return parse_json(Path(path).read_bytes())


def relative(name):
    check(isinstance(name, str) and name and '\\' not in name and '\x00' not in name, 'evidence path')
    p = PurePosixPath(name)
    check(not p.is_absolute() and '..' not in p.parts and '.' not in name.split('/') and str(p) == name, 'evidence path traversal')
    return p


def inventory(root, exclude=(), logical=False):
    root = Path(root); check(not root.is_symlink(), 'symlink root'); result = {}; total = 0
    for path in sorted(root.rglob('*')):
        mode = path.lstat().st_mode
        check(stat.S_ISREG(mode) or stat.S_ISDIR(mode), 'nonregular evidence member')
        if stat.S_ISDIR(mode): continue
        name = path.relative_to(root).as_posix(); relative(name)
        if name in exclude: continue
        size = path.stat().st_size; total += size
        check(size <= (JSON_LIMIT if path.suffix in ('.json', '.jsonl') else BUNDLE_LIMIT if logical else BINARY_LIMIT), 'member size bound')
        check(total <= BUNDLE_LIMIT and len(result) < FILE_LIMIT, 'bundle bound')
        result[name] = dict(bytes=size, sha256=sha_file(path))
    return result


def rows(directory):
    directory = Path(directory)
    files = sorted(directory.glob('part-*.jsonl'))
    check(files and [p.name for p in files] == [f'part-{i:04d}.jsonl' for i in range(len(files))], 'missing/duplicate stream part')
    count = total = 0
    for path in files:
        check(not path.is_symlink() and path.stat().st_size <= 8*MIB, 'stream part bound')
        with path.open('rb') as stream:
            while line := stream.readline(LINE_LIMIT + 1):
                total += len(line); count += 1
                check(len(line) <= LINE_LIMIT and line.endswith(b'\n') and total <= 512*MIB and count <= 600000, 'stream bound/truncated row')
                yield parse_json(line)


def pack(source, target):
    """Snapshot selected evidence into bounded binary parts; no compression amplification."""
    source, target = Path(source), Path(target)
    check(not target.exists(), 'fresh bundle required'); target.mkdir()
    items = {}; total = 0; parts = 0
    for path in sorted(source.rglob('*')):
        mode = path.lstat().st_mode
        check(stat.S_ISREG(mode) or stat.S_ISDIR(mode), 'nonregular pack source')
        if not path.is_file(): continue
        name = path.relative_to(source).as_posix(); relative(name)
        size = path.stat().st_size; total += size
        check(total <= BUNDLE_LIMIT and len(items) < FILE_LIMIT, 'uncompressed bundle bound')
        h = hashlib.sha256(); chunks = []
        with path.open('rb') as stream:
            while chunk := stream.read(BINARY_LIMIT):
                check(parts < FILE_LIMIT - 1, 'part count bound')
                label = f'chunk-{parts:04d}.bin'; parts += 1
                (target / label).write_bytes(chunk); h.update(chunk)
                chunks.append(dict(path=label, bytes=len(chunk), sha256=hashlib.sha256(chunk).hexdigest()))
        items[name] = dict(bytes=size, sha256=h.hexdigest(), parts=chunks)
    manifest = dict(schema='gse-v50-workload-parts-v1', bytes=total, files=items)
    from .offline_harness import save
    save(target / 'parts.json', manifest)
    check((target / 'parts.json').stat().st_size <= JSON_LIMIT, 'parts manifest bound')
    return manifest


def unpack(bundle, target):
    """Validate all lengths/paths before allocation; exclusive writes into a fresh owned directory."""
    bundle, target = Path(bundle), Path(target)
    check(not target.exists(), 'fresh inspection directory required')
    inv = inventory(bundle); manifest = read(bundle / 'parts.json')
    check(set(manifest) == {'schema', 'bytes', 'files'} and manifest['schema'] == 'gse-v50-workload-parts-v1', 'parts schema')
    files = manifest['files']; check(0 < len(files) <= FILE_LIMIT, 'logical file count')
    seen = set(); total = 0
    for name, item in files.items():
        relative(name); check(set(item) == {'bytes', 'sha256', 'parts'} and type(item['bytes']) is int and item['bytes'] >= 0, 'file descriptor')
        total += item['bytes']; check(total <= BUNDLE_LIMIT, 'uncompressed bound')
        size = 0
        for index, part in enumerate(item['parts']):
            check(set(part) == {'path', 'bytes', 'sha256'} and re.fullmatch(r'chunk-[0-9]{4}\.bin', part['path']), 'chunk descriptor')
            check(part['path'] not in seen and part['path'] in inv, 'duplicate/missing chunk')
            check(type(part['bytes']) is int and 0 < part['bytes'] <= BINARY_LIMIT, 'chunk size')
            check(index == len(item['parts']) - 1 or part['bytes'] == BINARY_LIMIT, 'nonterminal short chunk')
            check(inv[part['path']] == {k: part[k] for k in ('bytes', 'sha256')}, 'chunk checksum')
            size += part['bytes']; seen.add(part['path'])
        check(size == item['bytes'], 'incomplete reassembly')
    check(total == manifest['bytes'] and set(inv) == seen | {'parts.json'}, 'unlisted chunks/total')
    target.mkdir()
    for name, item in files.items():
        path = target / name; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as out:
            for part in item['parts']:
                with (bundle / part['path']).open('rb') as stream: shutil.copyfileobj(stream, out, MIB)
        check(path.stat().st_size == item['bytes'] and sha_file(path) == item['sha256'], 'ordered reassembly checksum')
    return manifest


def validate_source_archive(path, inputs):
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        check(len(infos) <= 4000 and len({v.filename for v in infos}) == len(infos), 'archive member count/duplicates')
        check(sum(v.file_size for v in infos) <= 128*MIB and set(inputs) == {v.filename for v in infos}, 'archive expansion/inventory')
        for info in infos:
            relative(info.filename)
            check(not info.is_dir() and not stat.S_ISLNK(info.external_attr >> 16), 'archive member type')
            h = hashlib.sha256(); size = 0
            with archive.open(info) as stream:
                for chunk in iter(lambda: stream.read(MIB), b''):
                    size += len(chunk); check(size <= info.file_size, 'archive expansion'); h.update(chunk)
            check(size == info.file_size and h.hexdigest() == inputs[info.filename], 'source archive checksum')
