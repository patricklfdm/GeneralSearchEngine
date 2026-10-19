"""Read-only build verification and deterministic V5.2 cloud input packaging.

This checks bytes and a clean checkout, not GitHub provenance or paid admission.
No packaged program is executed and no existing build output is restored/removed.
"""
import argparse
from copy import deepcopy
import gzip
import io
from pathlib import Path
import tarfile
from scripts import ci_v51_bundle as build
from . import cloud_authority as a, cloud_suite as suite, measurement_bundle as bundle
from .evidence import need, encoded, digest, strict

SCHEMA = 'gse-v52-cloud-inputs-v1'
PROOF = 'gse-v52-cloud-input-inspection-v1'
ARCHIVE = 'inputs.tar.gz'
INDEX = 'inputs.json'
MAX_BYTES = build.MAX_BYTES
MAX_JSON = 8 << 20
VERSION = '5.2.0-SNAPSHOT'
CONTROL_NAMES = {'general-search-engine-4.4.0.jar', 'general-search-engine-5.1.0.jar',
                 'general-search-engine-replication-5.1.0.jar'}
FLAGS = dict(paidAdmission=False, fullRemoteQualification=False)


def regular(path, maximum):
    path = Path(path)
    need(not any(p.is_symlink() for p in (path, *path.parents)) and path.is_file(), 'V5.2 input file type')
    need(0 <= path.stat().st_size <= maximum, 'V5.2 input file bound')
    with path.open('rb') as stream: raw = stream.read(maximum + 1)
    need(len(raw) <= maximum, 'V5.2 input file changed size')
    return raw


def identity(value):
    a.fields(value, 'source checkoutSha256 java', 'input source')
    a.hex_value(value['source'], 40); a.hex_value(value['checkoutSha256'])
    a.fields(value['java'], 'java.runtime.version java.vendor', 'input Java')
    need(all(type(v) is str and 0 < len(v) <= 256 for v in value['java'].values()), 'V5.2 input Java identity')


def checkout(root, source):
    root = Path(root)
    need(not any(p.is_symlink() for p in (root, *root.parents)) and root.is_dir(), 'V5.2 input checkout type')
    need(Path(build.git(root, 'rev-parse', '--show-toplevel').decode().strip()) == root.resolve(), 'V5.2 input checkout root')
    need(not build.git(root, 'status', '--porcelain=v1', '--untracked-files=all').strip(), 'V5.2 input dirty checkout')
    actual = build.binding(root, source); identity(actual)
    need(build.layout(root)[0] == f'target/general-search-engine-{VERSION}.jar', 'V5.2 input candidate version')
    return actual


def controls(root):
    suite.load()
    raw = regular(Path(root)/'docs/v5x/v5.2/published-controls.json', MAX_JSON)
    need(digest(raw) == suite.load()['controlsManifestSha256'], 'V5.2 input published control manifest')
    value = strict(raw); a.fields(value, 'schema artifacts', 'published controls')
    need(value['schema'] == 'gse-v52-published-controls-v1' and type(value['artifacts']) is list and
         len(value['artifacts']) == 3, 'V5.2 input published control inventory')
    pins = {}
    for row in value['artifacts']:
        a.fields(row, 'artifact version sha256', 'published control'); a.hex_value(row['sha256'])
        name = row['artifact']+'-'+row['version']+'.jar'
        need(name in CONTROL_NAMES and name not in pins, 'V5.2 input published control name')
        pins[name] = row['sha256']
    return raw, pins


def build_files(directory, expected, roots):
    """Authenticate the shared bundle without extraction or trusting its receipt."""
    identity(expected); directory = Path(directory)
    raw = regular(directory/'manifest.json', MAX_JSON); value = strict(raw)
    a.fields(value, 'schema binding roots archiveSha256 files', 'shared build')
    need(value['schema'] == build.SCHEMA and encoded(value['binding']) == encoded(expected) and
         value['roots'] == roots, 'V5.2 original build binding/layout')
    a.hex_value(value['archiveSha256']); entries = value['files']
    need(type(entries) is list and 0 < len(entries) <= 20000, 'V5.2 build file count')
    inventory = {}; total = 0
    for row in entries:
        a.fields(row, 'path size sha256', 'build member'); bundle.name(row['path'])
        need(build.allowed(row['path'], roots) and row['path'] not in inventory, 'V5.2 build file path/duplicate')
        total += a.integer(row['size'], 0, MAX_BYTES); a.hex_value(row['sha256'])
        need(total <= MAX_BYTES, 'V5.2 expanded build ceiling'); inventory[row['path']] = row
    for name in inventory:
        need(not any(p.as_posix() in inventory for p in Path(name).parents), 'V5.2 build file/directory collision')
    archive = regular(directory/'build.tar.gz', MAX_BYTES)
    need(digest(archive) == value['archiveSha256'], 'V5.2 original build archive hash')
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r|gz', tarinfo=bundle.ClosedTarInfo) as source:
        for item in source:
            need(item.isfile() and not item.pax_headers and item.sparse is None and item.name in inventory and
                 item.name not in files, 'V5.2 unexpected build archive member')
            row = inventory[item.name]
            need(item.size == row['size'], 'V5.2 build member size')
            with source.extractfile(item) as incoming: data = incoming.read(item.size + 1)
            need(len(data) == item.size and digest(data) == row['sha256'], 'V5.2 build member hash')
            files[item.name] = data
    need(set(files) == set(inventory), 'V5.2 missing build archive member')
    build.prerequisites(files, roots)
    return raw, {Path(name).name: files[name] for name in roots[:2]}


def manifest(binding, build_raw, controls_raw, files):
    identity(binding)
    return dict(schema=SCHEMA, source=deepcopy(binding), buildManifestSha256=digest(build_raw),
                controlsManifestSha256=digest(controls_raw),
                files={name: dict(bytes=len(raw), sha256=digest(raw)) for name, raw in sorted(files.items())})


def payload(binding, build_raw, controls_raw, candidate, published):
    need(set(published) == CONTROL_NAMES, 'V5.2 package controls')
    files = {'artifacts/'+name: raw for name, raw in {**candidate, **published}.items()}
    files.update({'source.json': encoded(binding), 'build-manifest.json': build_raw, 'published-controls.json': controls_raw})
    need(len(files) == 8 and all(len(v) <= (64 << 20) for v in files.values()) and
         sum(map(len, files.values())) <= MAX_BYTES, 'V5.2 package input ceiling')
    return files


def pack(path, meta, files):
    """Stable archive bytes across paths/times; no build, helper or workload run."""
    with Path(path).open('xb') as target, gzip.GzipFile(filename='', fileobj=target, mode='wb', mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode='w|', format=tarfile.USTAR_FORMAT) as output:
            for name, raw in [(INDEX, encoded(meta)), *sorted(files.items())]:
                bundle.name(name); item = tarfile.TarInfo(name); item.mode = 0o644; item.size = len(raw)
                output.addfile(item, io.BytesIO(raw))


def verify_archive(path, binding, build_raw, controls_raw, candidate, pins, *, include_files=False):
    raw = regular(path, MAX_BYTES); files = {}; meta = None
    sizes = {}; expected = {'artifacts/'+name for name in (*candidate, *pins)} | {
        'source.json', 'build-manifest.json', 'published-controls.json'}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r|gz', tarinfo=bundle.ClosedTarInfo) as source:
        for item in source:
            need(item.isfile() and not item.pax_headers and item.sparse is None, 'V5.2 package regular files only')
            if meta is None:
                need(item.name == INDEX and 0 < item.size <= MAX_JSON, 'V5.2 package first inventory')
                with source.extractfile(item) as incoming: meta = strict(incoming.read(item.size + 1))
                a.fields(meta, 'schema source buildManifestSha256 controlsManifestSha256 files', 'package')
                need(type(meta['files']) is dict and set(meta['files']) == expected, 'V5.2 package closed inventory')
                for name, row in meta['files'].items():
                    a.fields(row, 'bytes sha256', 'package member'); a.hex_value(row['sha256'])
                    sizes[name] = a.integer(row['bytes'], 0, (64 << 20) if name.startswith('artifacts/') else MAX_JSON)
                need(sum(sizes.values()) <= MAX_BYTES, 'V5.2 package expanded ceiling')
                continue
            need(item.name in expected and item.name not in files and item.size == sizes[item.name],
                 'V5.2 package unexpected/duplicate/changed member')
            with source.extractfile(item) as incoming: data = incoming.read(item.size + 1)
            need(len(data) == item.size and digest(data) == meta['files'][item.name]['sha256'], 'V5.2 package member hash')
            files[item.name] = data
    need(meta is not None and set(files) == expected, 'V5.2 package missing member')
    for name, sha in pins.items(): need(digest(files['artifacts/'+name]) == sha, 'V5.2 published input hash')
    wanted = payload(binding, build_raw, controls_raw, candidate, {name: files['artifacts/'+name] for name in pins})
    need(files == wanted and encoded(meta) == encoded(manifest(binding, build_raw, controls_raw, wanted)),
         'V5.2 package source/build/input drift')
    proof = dict(schema=PROOF, status='INPUTS_VERIFIED_NOT_ADMITTED', source=deepcopy(binding),
        buildManifestSha256=digest(build_raw), controlsManifestSha256=digest(controls_raw),
        packageSha256=digest(raw), packageBytes=len(raw), inputManifestSha256=digest(encoded(meta)), **FLAGS)
    return (proof, wanted) if include_files else proof


def validate_proof(value):
    a.fields(value, 'schema status source buildManifestSha256 controlsManifestSha256 packageSha256 packageBytes '
             'inputManifestSha256 paidAdmission fullRemoteQualification', 'input proof')
    need(value['schema'] == PROOF and value['status'] == 'INPUTS_VERIFIED_NOT_ADMITTED' and
         all(value[k] is False for k in FLAGS), 'V5.2 input proof scope')
    identity(value['source']); a.integer(value['packageBytes'], 1, MAX_BYTES)
    for key in ('buildManifestSha256', 'controlsManifestSha256', 'packageSha256', 'inputManifestSha256'): a.hex_value(value[key])
    need(value['controlsManifestSha256'] == suite.load()['controlsManifestSha256'], 'V5.2 input proof controls')
    return value


def verified_files(root, source, build_directory, package):
    """Return original bytes only after the same complete inspection as inspect."""
    root = Path(root); bound = checkout(root, source)
    build_raw, candidate = build_files(build_directory, bound, build.layout(root))
    controls_raw, pins = controls(root)
    result, files = verify_archive(package, bound, build_raw, controls_raw, candidate, pins, include_files=True)
    need(checkout(root, source) == bound, 'V5.2 checkout changed during input inspection')
    return validate_proof(result), files


def inspect(root, source, build_directory, package):
    return verified_files(root, source, build_directory, package)[0]


def create(root, source, build_directory, controls_directory, output):
    root = Path(root); output = Path(output); bound = checkout(root, source)
    build_raw, candidate = build_files(build_directory, bound, build.layout(root))
    controls_raw, pins = controls(root); published = {}
    for name, sha in pins.items():
        raw = regular(Path(controls_directory)/name, 64 << 20)
        need(digest(raw) == sha, 'V5.2 published input hash'); published[name] = raw
    files = payload(bound, build_raw, controls_raw, candidate, published)
    meta = manifest(bound, build_raw, controls_raw, files)
    need(not any(p.is_symlink() for p in (output, *output.parents)), 'V5.2 package output symlink')
    output.mkdir(parents=True, exist_ok=False)
    pack(output/ARCHIVE, meta, files)
    result = inspect(root, source, build_directory, output/ARCHIVE)
    need(result['source'] == bound, 'V5.2 checkout changed during packaging')
    (output/INDEX).write_bytes(encoded(meta)+b'\n'); (output/'receipt.json').write_bytes(encoded(result)+b'\n')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('action', choices=('create', 'inspect'))
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2]); p.add_argument('--source', required=True)
    p.add_argument('--build', type=Path, required=True); p.add_argument('--controls', type=Path)
    p.add_argument('--output', type=Path); p.add_argument('--package', type=Path); args = p.parse_args()
    if args.action == 'create':
        if args.controls is None or args.output is None: p.error('create requires --controls and --output')
        result = create(args.root, args.source, args.build, args.controls, args.output)
    else:
        if args.package is None: p.error('inspect requires --package')
        result = inspect(args.root, args.source, args.build, args.package)
    print(encoded(result).decode())
