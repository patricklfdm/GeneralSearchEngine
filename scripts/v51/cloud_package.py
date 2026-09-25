"""Standalone guest package verification. No repository imports or cloud access."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile

SCHEMA = 'gse-v51-guest-package-v1'
MAX_BYTES = 256 << 20
MODES = ('published-v4.4-local', 'published-v5.0-configured', 'candidate-v5.1-automatic')
PACKAGE = 'io.github.patricklfdm.generalsearch.'
MAINS = dict(zip(MODES, ('admission.V51CloudLocal', 'replication.V51CloudConfigured', 'replication.V51CloudAutomatic')))


def need(value, message):
    if not value: raise ValueError(message)


def sha(data): return hashlib.sha256(data).hexdigest()


def read(path):
    def pairs(items):
        result = {}
        for k, v in items:
            need(k not in result, 'duplicate package JSON key'); result[k] = v
        return result
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 4 << 20, 'package metadata size/type')
    return json.loads(path.read_bytes(), object_pairs_hook=pairs)


def safe(name):
    p = PurePosixPath(name)
    need(isinstance(name, str) and str(p) == name and not p.is_absolute() and '..' not in p.parts and
         name not in ('', '.') and '\\' not in name, 'package path')
    return name


def inventory(root):
    rows = []; total = 0
    for path in sorted(root.rglob('*')):
        need(not path.is_symlink(), 'linked package member')
        if path.is_dir(): continue
        need(path.is_file(), 'nonregular package member')
        name = safe(path.relative_to(root).as_posix())
        if name == 'manifest.json': continue
        size = path.stat().st_size; total += size
        need(len(rows) < 10000 and total <= MAX_BYTES, 'package inventory bound')
        rows.append(dict(path=name, size=size, sha256=sha(path.read_bytes()), executable=bool(path.stat().st_mode & 0o111)))
    need(len(rows) <= 10000 and sum(r['size'] for r in rows) <= MAX_BYTES, 'package inventory bound')
    return rows


def verify(root, expected_source=None):
    root = Path(root); need(root.is_dir() and not root.is_symlink(), 'package directory')
    manifest = read(root/'manifest.json')
    need(manifest['schema'] == SCHEMA and re.fullmatch('[0-9a-f]{40}', manifest['source']), 'package schema/source')
    if expected_source is not None: need(manifest['source'] == expected_source, 'package source mismatch')
    need(manifest['paidCloud'] is False and manifest['fullRemoteQualification'] is False, 'package qualification scope')
    need(manifest['files'] == inventory(root), 'package inventory changed')
    files = {r['path']: r for r in manifest['files']}
    binding = read(root/'ci-build-manifest.json')
    need(sha((root/'ci-build-manifest.json').read_bytes()) == manifest['buildManifestSha256'] and
         binding['binding'] == manifest['buildBinding'] and binding['binding']['source'] == manifest['source'], 'package build binding')
    candidate = {r['path']: r['sha256'] for r in binding['files']}
    modes = manifest['modes']; need(set(modes) == set(MODES), 'package modes')
    wanted = []
    pins = read(root/'published-controls.json')['artifacts']
    for mode in MODES:
        value = modes[mode]; jars = value['jars']; directory = 'classes-'+mode
        need(value['classes'] == directory and value['main'] == MAINS[mode] and
             len(jars) == (1 if mode == MODES[0] else 2), 'package classpath isolation')
        need(any(n.startswith(directory+'/') for n in files), 'missing guest classes')
        for name in jars:
            safe(name); need(name.startswith('artifacts/') and name.count('/') == 1 and name.endswith('.jar'), 'package JAR path')
            wanted.append(name)
            if mode == MODES[2]:
                key = ('general-search-engine-replication/target/' if Path(name).name.startswith('general-search-engine-replication-') else 'target/')+Path(name).name
                need(files[name]['sha256'] == candidate[key], 'package candidate build mismatch')
            else:
                version = '4.4.0' if mode == MODES[0] else '5.0.0'
                pin = next((p for p in pins if Path(name).name == p['artifact']+'-'+p['version']+'.jar' and p['version'] == version), None)
                need(pin is not None and files[name]['sha256'] == pin['sha256'], 'package published control mismatch')
    need(len(set(wanted)) == 5 and sorted(wanted) == sorted(n for n in files if n.endswith('.jar') and not n.startswith('runtime/')), 'package five distinct JARs')
    need(files['runtime/bin/java']['executable'] is True and 'guest.py' in files, 'package launcher/runtime')
    need(sha((root/'workload.json').read_bytes()) == manifest['workloadSha256'], 'package workload digest')
    return manifest


def unpack(archive, target, expected_sha, expected_source):
    archive, target = Path(archive), Path(target)
    need(re.fullmatch('[0-9a-f]{64}', expected_sha) and archive.is_file() and not archive.is_symlink() and
         archive.stat().st_size <= MAX_BYTES, 'package archive input')
    # Authenticate the entire blob before even parsing its members or executing its verifier.
    need(sha(archive.read_bytes()) == expected_sha, 'package archive digest')
    target.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive, 'r:gz') as tar:
        seen = set(); total = 0
        for info in tar:
            name = safe(info.name); total += info.size
            need(info.isfile() and name not in seen and info.size >= 0 and info.mode in (0o644, 0o755) and
                 len(seen) < 10000 and total <= MAX_BYTES, 'package archive member/type/bound')
            seen.add(name); path = target/name
            path.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(info) as src, path.open('xb') as dst:
                remaining = info.size
                while remaining:
                    data = src.read(min(1 << 20, remaining)); need(data, 'truncated package member')
                    dst.write(data); remaining -= len(data)
            path.chmod(info.mode)
    return verify(target, expected_source)


def command(root, mode, check=False, args=()):
    root = Path(root).resolve(); manifest = verify(root); need(mode in MODES, 'guest mode')
    value = manifest['modes'][mode]; cp = os.pathsep.join(str(root/p) for p in [*value['jars'], value['classes']])
    main = 'admission.V51BundleCheck' if check else value['main']
    extra = [mode, *[str(root/p) for p in value['jars']]] if check else list(args)
    return [str(root/'runtime/bin/java'), *manifest['jvmArguments'], '-cp', cp, PACKAGE+main, *extra]


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('action', choices=('verify', 'check', 'launch')); p.add_argument('--mode', choices=MODES)
    p.add_argument('args', nargs='*'); a = p.parse_args(); root = Path(__file__).resolve().parent
    if a.action == 'verify':
        value = verify(root); print(json.dumps(dict(status='PASS', source=value['source'], files=len(value['files']))))
    else:
        need(a.mode is not None, 'guest mode required')
        if a.action == 'check': subprocess.run(command(root, a.mode, True), check=True, timeout=30)
        else: os.execv(str(root/'runtime/bin/java'), command(root, a.mode, args=a.args))
