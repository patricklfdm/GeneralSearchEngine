"""Construct a relocatable, exact-build guest package. Does not execute cloud work."""
import argparse
import gzip
import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
from scripts import ci_v51_bundle as build
from . import cloud_package as package, cloud_workload_contract as workload, controls
from . import performance_harness as base, performance_model as m, performance_plan as local

ROOT = base.ROOT
GUEST_INPUTS = ('scripts/v51/__init__.py',
    *('scripts/v51/'+module+'.py' for module in ('cloud_guest', 'guest_jvm', 'cloud_package',
       'remote_command', 'remote_collection', 'remote_schedule', 'remote_schedule_evidence',
       'cloud_workload_contract', 'performance_model', 'performance_plan')),
    'docs/v5x/v5.1/phase6-plan.json', 'docs/v5x/v5.1/phase6-cloud-workload-plan.json')


def create(output, manifest, source, control_directory):
    output, manifest = Path(output).resolve(), Path(manifest).resolve()
    output.mkdir(parents=True, exist_ok=False)
    identity = build.binding(ROOT, source); verified = package.read(manifest)
    m.need(verified['schema'] == build.SCHEMA and verified['binding'] == identity, 'guest source/toolchain/build mismatch')
    env = workload.load()['environment']
    m.need(identity['java'] == {'java.vendor': env['javaVendor'], 'java.runtime.version': env['javaRuntime']}, 'guest pinned Java')
    # Candidate hashes and successful prerequisite reports belong to this build.
    files = {r['path']: r for r in verified['files']}
    report_bytes = {}
    for name in [*verified['roots'][:2], *[n for n in files if n.startswith(build.REPORTS+'/TEST-') and n.endswith('.xml')]]:
        path = ROOT/name; m.need(path.is_file() and not path.is_symlink(), 'guest missing build output')
        raw = path.read_bytes(); m.need(len(raw) == files[name]['size'] and m.sha(raw) == files[name]['sha256'], 'guest changed build output')
        report_bytes[name] = raw
    # Required worker classes are verified alongside the reports, without executing them.
    for worker in ('V51StorageWorker', 'V51ProtocolWorker', 'V51RuntimeWorker'):
        name = next(n for n in files if n.startswith(build.CLASSES+'/') and n.endswith('/'+worker+'.class'))
        raw = (ROOT/name).read_bytes(); m.need(m.sha(raw) == files[name]['sha256'], 'guest changed build worker'); report_bytes[name] = raw
    build.prerequisites(report_bytes, verified['roots'])
    controls.resolve(control_directory)
    root = output/'package'; root.mkdir()
    logs = output/'build'; logs.mkdir()
    run = base.Run(root, local.load())
    adapters = base.compile_adapters(run, Path(control_directory))
    # Keep process diagnostics outside the immutable payload.
    for path in root.glob('compile-*'): shutil.move(str(path), logs/path.name)
    check_source = ROOT/'scripts/v51/java/V51BundleCheck.java'
    for mode, adapter in adapters.items():
        classes = root/('classes-'+mode)
        run.process(['javac', '--release', '21', '-proc:none', '-d', classes, check_source], 'check-'+mode, logs)
    java_home = Path(shutil.which('java')).resolve().parents[1]
    run.process([java_home/'bin/jlink', '--add-modules', 'java.base,java.management,jdk.management,jdk.unsupported',
                 '--strip-debug', '--no-header-files', '--no-man-pages', '--output', root/'runtime'], 'jlink', logs)
    for path in sorted((root/'runtime').rglob('*')):
        if path.is_symlink():
            resolved = path.resolve(); m.need(resolved.is_relative_to(root/'runtime') and resolved.is_file(), 'external jlink link')
            data = resolved.read_bytes(); path.unlink(); path.write_bytes(data)
    shutil.copyfile(manifest, root/'ci-build-manifest.json')
    shutil.copyfile(workload.PLAN, root/'workload.json')
    shutil.copyfile(ROOT/'docs/v5x/v5.1/published-controls.json', root/'published-controls.json')
    shutil.copyfile(ROOT/'scripts/v51/cloud_package.py', root/'guest.py')
    # Guest dependencies are an explicit closed set, including the two frozen plans.
    for name in GUEST_INPUTS:
        target = root/'source-inputs'/name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, target)
    modes = {mode: dict(jars=[str(Path(r['path']).relative_to(root)) for r in adapter['artifacts']],
                       classes='classes-'+mode, main=package.MAINS[mode]) for mode, adapter in adapters.items()}
    value = dict(schema=package.SCHEMA, source=source, buildBinding=identity, buildManifestSha256=m.sha(manifest.read_bytes()),
                 dirty=bool(build.git(ROOT, 'status', '--porcelain')), paidCloud=False, fullRemoteQualification=False,
                 workloadSha256=m.sha((root/'workload.json').read_bytes()), modes=modes,
                 adapterSources={mode: adapter['sources'] for mode, adapter in adapters.items()},
                 bundleCheckSha256=m.sha(check_source.read_bytes()), jvmArguments=workload.load()['environment']['jvmArguments'],
                 files=package.inventory(root))
    base.save(root/'manifest.json', value); package.verify(root, source)
    archive = output/'guest.tar.gz'
    with archive.open('xb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode='w', format=tarfile.USTAR_FORMAT) as tar:
            for path in sorted(p for p in root.rglob('*') if p.is_file()):
                data = path.read_bytes(); info = tarfile.TarInfo(path.relative_to(root).as_posix())
                info.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644; info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
    digest = m.sha(archive.read_bytes())
    checks = []
    with tempfile.TemporaryDirectory(prefix='v51-relocated-guest-') as temp:
        relocated = Path(temp)/'guest'; package.unpack(archive, relocated, digest, source)
        # Execute the packaged standalone verifier as well as the caller-side verifier.
        run.process(['python3', '-I', relocated/'guest.py', 'verify'], 'standalone-verify', logs)
        for mode in package.MODES:
            raw = run.process(package.command(relocated, mode, check=True), 'launch-'+mode, logs)
            result = m.strict_json(raw); m.need(result == dict(mode=mode, status='PASS'), 'guest code-source check'); checks.append(result)
    m.need(build.binding(ROOT, source) == identity, 'source changed during guest build')
    receipt = dict(schema='gse-v51-guest-build-v1', status='PASS', source=source, dirty=value['dirty'],
        buildManifestSha256=value['buildManifestSha256'], archiveSha256=digest, archiveBytes=archive.stat().st_size,
        payloadFiles=len(value['files']), payloadBytes=sum(r['size'] for r in value['files']), checks=checks,
        paidCloud=False, fullRemoteQualification=False, engineWorkloadExecuted=False)
    base.save(output/'receipt.json', receipt)
    print(m.canonical(receipt).decode()); return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('output', type=Path); p.add_argument('--source', required=True)
    p.add_argument('--build-manifest', type=Path, required=True); p.add_argument('--controls', type=Path, default=ROOT/'target/v51-published-controls')
    a = p.parse_args()
    try:
        create(a.output, a.build_manifest, a.source, a.controls)
    except Exception as error:
        if a.output.is_dir() and not (a.output/'failure.json').exists():
            base.save(a.output/'failure.json', dict(status='FAIL', type=type(error).__name__, message=str(error)[:2000],
                paidCloud=False, fullRemoteQualification=False))
        raise
