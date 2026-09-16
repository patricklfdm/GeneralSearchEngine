"""Offline guest bundle: three exact JARs, independently compiled probes and Java runtime."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
from .cloud_common import ROOT, canonical, inventory, plan, read, require, save, sha
from .offline_harness import CORE, REPLICATION
from .performance_harness import source_inputs


def build(target, control, *, workload_qualification=False):
    p = plan(); target = Path(target).resolve(); control = Path(control).resolve()
    require(not target.exists(), 'fresh bundle workspace required'); target.mkdir(parents=True)
    content = target / 'bundle'; content.mkdir()
    workload_path = ROOT / p['workloadPlan']
    if workload_qualification:
        from .cloud_workload_plan import PLAN as workload_path, read_plan
        read_plan(workload_path)
    workload = read(workload_path)
    require(sha(control.read_bytes()) == workload['publishedControl']['sha256'], 'published V4.4 checksum')
    jars = {}
    for name, source in [('core', CORE), ('replication', REPLICATION), ('control', control)]:
        dest = content / (name + '.jar'); shutil.copyfile(source, dest); jars[name] = sha(dest.read_bytes())
    shutil.copyfile(workload_path, content / 'workload.json')
    if not workload_qualification:
        shutil.copyfile(Path(__file__).with_name('cloud_guest.py'), content / 'guest.py')
    java = Path(shutil.which('java')).resolve().parent
    version = subprocess.check_output([java / 'java', '--version'], text=True)
    require(p['runtimeJava'] in version, 'Java runtime pin')
    subprocess.run([java / 'jlink', '--add-modules', 'java.base,java.management,jdk.management,jdk.unsupported',
                    '--strip-debug', '--no-header-files', '--no-man-pages', '--output', content / 'jre'], check=True, timeout=120)
    # jlink emits license links. Freeze their bytes so guest extraction accepts
    # only ordinary files and does not depend on a host filesystem link target.
    for path in (content / 'jre').rglob('*'):
        if path.is_symlink():
            require(path.resolve().is_relative_to(content / 'jre') and path.is_file(), 'unexpected jlink link')
            raw = path.read_bytes(); path.unlink(); path.write_bytes(raw)
    sources = ROOT / 'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch'
    common = [sources / 'admission' / (n + '.java') for n in ('AdmissionJson', 'AdmissionSemanticModel', 'PerformanceTelemetry', 'PerformanceWorkload')]
    if workload_qualification:
        common += [sources / 'admission' / (n + '.java') for n in ('CloudWorkloadTelemetry', 'CloudWorkload')]
    def compile(dest, cp, files):
        dest.mkdir(exist_ok=True)
        subprocess.run(['javac', '--release', '21', '-cp', cp, '-d', str(dest), *map(str, files)], check=True, timeout=60)
    candidate = content / 'classes-candidate'; oracle = content / 'classes-control'
    cp = os.pathsep.join(str(content / (n + '.jar')) for n in ('core', 'replication'))
    family = 'CloudWorkload' if workload_qualification else 'Performance'
    compile(candidate, cp, [*common, sources / f'admission/V50{family}Consumer.java'])
    compile(candidate, cp + os.pathsep + str(candidate), [sources / f'replication/V50{family}Worker.java'])
    compile(oracle, str(content / 'control.jar'), [*common, sources / f'admission/V50{family}Control.java'])
    inputs = source_inputs()
    # Include the runner plan as an exact input (the local 6A helper predates it).
    inputs['docs/v5x/v5.0/phase6-runner-plan.json'] = sha((ROOT / 'docs/v5x/v5.0/phase6-runner-plan.json').read_bytes())
    if workload_qualification: inputs[str(workload_path.relative_to(ROOT))] = sha(workload_path.read_bytes())
    for name in inputs:
        dest = content / 'source-inputs' / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(ROOT / name, dest)
    manifest = dict(schema='gse-v50-cloud-bundle-v1', source=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                    dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)), jars=jars, inputs=inputs,
                    java=version, planSha256=sha(canonical(p)), files=inventory(content))
    if workload_qualification:
        manifest.update(schema='gse-v50-cloud-workload-bundle-v1', execution='offline-workload-bundle-only',
                        workloadPlanSha256=sha(workload_path.read_bytes()))
    save(content / 'bundle.json', manifest)
    archive = target / 'bundle.tar.gz'
    with tarfile.open(archive, 'w:gz', dereference=True) as out:
        for path in sorted(content.rglob('*')):
            if path.is_file(): out.add(path, arcname=str(path.relative_to(content)), recursive=False)
    require(archive.stat().st_size <= p['maximumBundleBytes'], 'bundle size')
    save(target / 'bundle-receipt.json', dict(sha256=sha(archive.read_bytes()), manifest=manifest))
    return archive


def extract(archive, target, maximum=128 << 20):
    """Reject paths, links, duplicates and expansion bombs before writing any member."""
    target = Path(target); require(not target.exists(), 'fresh extraction target')
    with tarfile.open(archive, 'r:gz') as stream:
        members = stream.getmembers(); names = [m.name for m in members]
        require(len(names) <= 2000 and len(set(names)) == len(names) and sum(m.size for m in members) <= maximum, 'archive bounds')
        for member in members:
            require(member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts, 'unsafe archive member')
        target.mkdir(parents=True)
        stream.extractall(target, members=members, filter='data')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path); parser.add_argument('--control-jar', type=Path, required=True)
    parser.add_argument('--workload-qualification', action='store_true')
    args = parser.parse_args(); print(build(args.output, args.control_jar, workload_qualification=args.workload_qualification))
