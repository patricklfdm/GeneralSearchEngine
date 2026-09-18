"""One bounded, uncompressed transfer of the existing evidence parts per guest."""
import hashlib
from pathlib import Path
import re
import stat
import zipfile
from .cloud_common import require
from .cloud_workload_io import BINARY_LIMIT, BUNDLE_LIMIT, FILE_LIMIT, JSON_LIMIT, MIB, inventory, parse_json, sha_file

ARCHIVE_LIMIT = BUNDLE_LIMIT + JSON_LIMIT + FILE_LIMIT * 512


def archive_parts(parts, target):
    parts, target = Path(parts), Path(target)
    files = inventory(parts)
    require('parts.json' in files and all(name == 'parts.json' or re.fullmatch(r'chunk-[0-9]{4}\.bin', name)
                                        for name in files), 'collection archive members')
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_STORED) as archive:
        for name in files: archive.write(parts / name, name)
    size = target.stat().st_size
    require(0 < size <= ARCHIVE_LIMIT, 'collection archive size')
    return dict(path=str(target), bytes=size, sha256=sha_file(target))


def extract_parts(archive, target, manifest, manifest_sha):
    """Check the declared flat inventory before streaming exclusively owned files."""
    archive, target = Path(archive), Path(target)
    require(not target.exists() and not target.is_symlink(), 'fresh collection parts directory')
    require(not archive.is_symlink() and 0 < archive.stat().st_size <= ARCHIVE_LIMIT, 'collection archive size')
    expected = {'parts.json': dict(bytes=None, sha256=manifest_sha)}
    total = 0
    require(0 < len(manifest['files']) <= FILE_LIMIT, 'collection file count')
    for item in manifest['files'].values():
        for part in item['parts']:
            name = part['path']
            require(re.fullmatch(r'chunk-[0-9]{4}\.bin', name) and name not in expected and
                    type(part['bytes']) is int and 0 < part['bytes'] <= BINARY_LIMIT, 'collection part identity/bound')
            total += part['bytes']; expected[name] = part
            require(total <= BUNDLE_LIMIT and len(expected) <= FILE_LIMIT, 'collection aggregate bound')
    require(total == manifest['bytes'], 'collection aggregate size')
    with zipfile.ZipFile(archive) as stream:
        members = stream.infolist(); names = [m.filename for m in members]
        require(len(names) == len(set(names)) == len(expected) and set(names) == set(expected), 'collection archive inventory')
        for member in members:
            mode = member.external_attr >> 16
            require(not member.is_dir() and stat.S_IFMT(mode) in (0, stat.S_IFREG) and
                    not member.flag_bits & 1 and member.compress_type == zipfile.ZIP_STORED and
                    member.compress_size == member.file_size, 'collection archive member type')
            size = expected[member.filename]['bytes']
            require(0 < member.file_size <= JSON_LIMIT if size is None else member.file_size == size,
                    'collection archive member size')
        target.mkdir(parents=True)
        for member in members:
            digest = hashlib.sha256(); size = 0; path = target / member.filename
            with stream.open(member) as source, path.open('xb') as dest:
                while chunk := source.read(MIB):
                    size += len(chunk); require(size <= member.file_size, 'collection archive expansion')
                    digest.update(chunk); dest.write(chunk)
            require(size == member.file_size and digest.hexdigest() == expected[member.filename]['sha256'],
                    'collection archive member checksum')
        require(parse_json((target / 'parts.json').read_bytes()) == manifest, 'collection manifest transfer')
