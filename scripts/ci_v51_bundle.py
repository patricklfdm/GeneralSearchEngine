"""Exact-checkout V5.1 verification outputs; never a release or Maven cache input."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import xml.etree.ElementTree as ET

SCHEMA = 'gse-ci-v51-build-v1'
MODULE = 'general-search-engine-replication'
REPORTS = MODULE + '/target/surefire-reports'
CLASSES = MODULE + '/target/test-classes'
MAX_BYTES = 256 * 1024 * 1024
REQUIRED_SUITES = {
    'V51AutomaticRecordsTest', 'V51AutomaticStoreTest', 'V51AutomaticProtocolTest',
    'V51AutomaticRuntimeTest', 'V51AutomaticWireTest', 'V51AutomaticRejoinTest',
    'V51RecoveryExchangeTest', 'V51RecoveryWitnessTest', 'V51BootstrapTest',
    'V51PublicRuntimeTest', 'V51VersionBoundaryTest', 'V51AutomaticTransportTest',
    'V51ApplicationRebuildTest',
}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(value))


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def binding(root, source):
    need(re.fullmatch('[0-9a-f]{40}', source), 'invalid source SHA')
    need(git(root, 'rev-parse', 'HEAD').decode().strip() == source, 'checkout SHA mismatch')
    names = git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').split(b'\0')
    inventory = []
    for name in sorted(set(names) - {b''}):
        path = root / os.fsdecode(name)
        need(path.is_file() and not path.is_symlink(), 'missing or linked source: ' + str(path))
        inventory.append([os.fsdecode(name), bool(path.stat().st_mode & 0o111), digest(path.read_bytes())])
    java = subprocess.run(['java', '-XshowSettings:properties', '-version'], check=True,
                          capture_output=True, text=True).stderr
    properties = dict(re.findall(r'^\s*(java\.(?:runtime.version|vendor)) = (.+)$', java, re.MULTILINE))
    need(set(properties) == {'java.runtime.version', 'java.vendor'}, 'missing Java identity')
    return dict(source=source, checkoutSha256=digest(encoded(inventory)), java=properties)


def layout(root):
    version = ET.parse(root / 'pom.xml').getroot().findtext('{*}version')
    need(version and re.fullmatch(r'5\.1\.[0-9]+(?:-SNAPSHOT)?', version), 'not a V5.1 build')
    return [f'target/general-search-engine-{version}.jar',
            f'{MODULE}/target/general-search-engine-replication-{version}.jar', CLASSES, REPORTS]


def allowed(name, roots):
    path = PurePosixPath(name)
    return (str(path) == name and not path.is_absolute() and '..' not in path.parts and
            (name in roots[:2] or any(name.startswith(p + '/') for p in roots[2:])))


def prerequisites(files, roots):
    need(all(name in files for name in roots[:2]), 'missing core or replication JAR')
    for worker in ('V51StorageWorker', 'V51ProtocolWorker', 'V51RuntimeWorker'):
        need(any(p.startswith(CLASSES + '/') and p.endswith('/' + worker + '.class') for p in files),
             'missing test worker: ' + worker)
    suites = set()
    for name, data in files.items():
        if name.startswith(REPORTS + '/TEST-') and name.endswith('.xml'):
            suite = ET.fromstring(data)
            need(suite.tag == 'testsuite' and int(suite.attrib['tests']) > 0 and
                 all(int(suite.attrib.get(k, 0)) == 0 for k in ('failures', 'errors')),
                 'failed or empty Java suite: ' + name)
            short = suite.attrib['name'].rsplit('.', 1)[-1]
            if short in REQUIRED_SUITES:
                need(int(suite.attrib.get('skipped', 0)) == 0, 'skipped prerequisite: ' + short)
            suites.add(short)
    need(REQUIRED_SUITES <= suites, 'missing executed Java prerequisites: ' + str(sorted(REQUIRED_SUITES - suites)))


def prepare(root, source, state):
    prepared = dict(schema=SCHEMA, binding=binding(root, source), startedNs=0)
    save(state, prepared)
    # Use the filesystem clock/resolution for comparison with later output mtimes.
    prepared['startedNs'] = state.stat().st_mtime_ns
    save(state, prepared)


def create(root, source, state, output):
    prepared = json.loads(state.read_text())
    identity = binding(root, source)
    need(prepared['schema'] == SCHEMA and prepared['binding'] == identity, 'source/toolchain changed during build')
    roots = layout(root)
    files = {}
    for name in roots:
        path = root / name
        need(path.exists() and not path.is_symlink(), 'missing or linked output: ' + name)
        for item in sorted(path.rglob('*')) if path.is_dir() else [path]:
            need(not item.is_symlink(), 'linked build output')
            if item.is_file():
                relative = item.relative_to(root).as_posix()
                if relative.endswith('.jar') or (relative.startswith(REPORTS + '/TEST-') and relative.endswith('.xml')):
                    need(item.stat().st_mtime_ns >= prepared['startedNs'], 'stale build output: ' + relative)
                files[relative] = item.read_bytes()
    need(len(files) <= 20000 and sum(map(len, files.values())) <= MAX_BYTES, 'oversized build bundle')
    prerequisites(files, roots)
    output.mkdir(parents=True, exist_ok=True)
    archive = output / 'build.tar.gz'
    with archive.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode='w', format=tarfile.USTAR_FORMAT) as tar:
            for name, data in sorted(files.items()):
                info = tarfile.TarInfo(name); info.size = len(data); info.mode = 0o644
                tar.addfile(info, io.BytesIO(data))
    manifest = dict(schema=SCHEMA, binding=identity, roots=roots, archiveSha256=digest(archive.read_bytes()),
                    files=[dict(path=n, size=len(d), sha256=digest(d)) for n, d in sorted(files.items())])
    save(output / 'manifest.json', manifest)
    return dict(status='PASS', files=len(files), archiveBytes=archive.stat().st_size,
                unpackedBytes=sum(map(len, files.values())), archiveSha256=manifest['archiveSha256'])


def restore(root, source, bundle):
    manifest = json.loads((bundle / 'manifest.json').read_text())
    need(manifest['schema'] == SCHEMA and manifest['binding'] == binding(root, source), 'source/toolchain mismatch')
    roots = layout(root)
    need(manifest['roots'] == roots, 'bundle layout mismatch')
    entries = manifest['files']
    need(0 < len(entries) <= 20000, 'invalid file count')
    expected = {v['path']: v for v in entries}
    need(len(expected) == len(entries) and all(allowed(n, roots) for n in expected), 'invalid/duplicate bundle path')
    need(all(type(v['size']) is int and 0 <= v['size'] <= MAX_BYTES for v in entries) and
         sum(v['size'] for v in entries) <= MAX_BYTES, 'invalid bundle size')
    archive = bundle / 'build.tar.gz'
    need(archive.stat().st_size <= MAX_BYTES and digest(archive.read_bytes()) == manifest['archiveSha256'],
         'archive hash/size mismatch')
    files = {}
    with tarfile.open(archive, mode='r:gz') as tar:
        for member in tar:
            need(member.isfile() and member.name in expected and member.name not in files,
                 'unexpected/linked/duplicate archive member')
            record = expected[member.name]
            need(member.size == record['size'], 'member size mismatch')
            data = tar.extractfile(member).read()
            need(digest(data) == record['sha256'], 'member hash mismatch: ' + member.name)
            files[member.name] = data
    need(set(files) == set(expected), 'missing archive member')
    prerequisites(files, roots)
    for name in roots:
        path = root / name
        need(not path.exists() and not path.is_symlink(), 'refusing existing build output: ' + name)
        need(not any(p.is_symlink() for p in path.parents if p != root.parent), 'linked destination parent')
    # Consumers check out after the producer. Verified identical source/bytes make
    # rebasing local freshness timestamps safe; XML/JAR contents remain untouched.
    sources = git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').split(b'\0')
    stamp = max([time.time_ns(), *( (root / os.fsdecode(n)).stat().st_mtime_ns for n in sources if n)]) + 1
    with tempfile.TemporaryDirectory(prefix='gse-v51-build-') as temp:
        staging = Path(temp)
        for name, data in files.items():
            path = staging / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data); path.chmod(0o644); os.utime(path, ns=(stamp, stamp))
        for name in roots:
            target = root / name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(staging / name), target)
    return dict(status='PASS', binding=manifest['binding'], manifestSha256=digest((bundle / 'manifest.json').read_bytes()),
                archiveSha256=manifest['archiveSha256'], files=len(files), restoredMtimeNs=stamp,
                archiveBytes=archive.stat().st_size, unpackedBytes=sum(map(len, files.values())))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('prepare', 'create', 'restore'))
    p.add_argument('--source', required=True)
    p.add_argument('--workspace', type=Path, default=Path.cwd())
    p.add_argument('--state', type=Path)
    p.add_argument('--bundle', type=Path)
    p.add_argument('--receipt', type=Path, required=True)
    a = p.parse_args(); start = time.monotonic(); receipt = dict(status='FAIL', action=a.action)
    try:
        root = a.workspace.resolve()
        if a.action == 'prepare':
            need(a.state is not None, '--state required'); prepare(root, a.source, a.state)
            receipt['status'] = 'PASS'
        elif a.action == 'create':
            need(a.state is not None and a.bundle is not None, '--state and --bundle required')
            receipt.update(create(root, a.source, a.state, a.bundle))
        else:
            need(a.bundle is not None, '--bundle required')
            receipt.update(restore(root, a.source, a.bundle))
    except (ValueError, OSError, KeyError, TypeError, ET.ParseError, tarfile.TarError, subprocess.SubprocessError) as error:
        receipt['error'] = str(error)
    finally:
        receipt['elapsedSeconds'] = round(time.monotonic() - start, 3)
        save(a.receipt, receipt); print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt['status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
