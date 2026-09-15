"""Owned-JVM public offline operations, real SIGKILL cuts and pinned V4.4 round trips."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import time
import xml.etree.ElementTree as ET
from . import offline_format as inspect
from .admission_format import check
from .recovery_harness import CONTROL_SHA

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'io.github.patricklfdm.generalsearch.'
WORKER = PACKAGE + 'replication.V50OfflineCrashWorker'
CONTROL = PACKAGE + 'admission.AdmissionV44Control'
CORE = ROOT / 'target/general-search-engine-5.0.0-SNAPSHOT.jar'
REPLICATION = ROOT / 'general-search-engine-replication/target/general-search-engine-replication-5.0.0-SNAPSHOT.jar'
CLASSPATH = None  # Set only after isolated consumer/fault-worker compilation.
BOOTSTRAP_CUTS = ['BOOTSTRAP_PLAN_FORCED', 'BOOTSTRAP_PREPARING_FORCED']
BOOTSTRAP_CUTS += [f'BOOTSTRAP_TARGET_{i}_CREATED' for i in range(3)]
for i in range(3):
    BOOTSTRAP_CUTS += [f'BOOTSTRAP_TARGET_{i}_{name}_FORCED' for name in inspect.f.ROOT_FILES]
    BOOTSTRAP_CUTS += [f'BOOTSTRAP_TARGET_{i}_VERIFIED', f'BOOTSTRAP_PREPARATION_{i}_FORCED']
BOOTSTRAP_CUTS += ['BOOTSTRAP_PREPARED_FORCED', 'BOOTSTRAP_COMMITTING_FORCED', 'BOOTSTRAP_RECEIPT_PENDING_FORCED',
                  'BOOTSTRAP_RECEIPT_RENAMED', 'BOOTSTRAP_RECEIPT_PARENT_FORCED', 'BOOTSTRAP_COMMITTED_FORCED']
BOOTSTRAP_CUTS += [f'BOOTSTRAP_SEAL_{i}_{stage}' for i in range(3) for stage in ('PENDING_FORCED', 'RENAMED', 'FORCED')]
REPLACEMENT_CUTS = ['REPLACEMENT_PLAN_FORCED', 'REPLACEMENT_PREPARING_FORCED', 'REPLACEMENT_TARGET_CREATED']
REPLACEMENT_CUTS += ['REPLACEMENT_' + name + '_FORCED' for name in sorted(inspect.f.ROOT_FILES + ('bootstrap-prepared.gsr', 'bootstrap-seal.gsr', 'rebuilding.gsr'))]
REPLACEMENT_CUTS += ['REPLACEMENT_TARGET_VERIFIED', 'REPLACEMENT_ROW_PENDING_FORCED', 'REPLACEMENT_PREPARED_FORCED']


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def hashes(root):
    return {name: hashlib.sha256(value).hexdigest() for name, value in inspect.files(root).items()}


def capture(root, label, oracle=inspect.bootstrap):
    output = root / 'evidence' / label
    output.mkdir(parents=True)
    subjects = [p for p in root.iterdir() if p.is_dir() and p.name in
                ('operation', 'node-1', 'node-2', 'node-3', 'replacement', 'replacement-operation', 'source')]
    before = {p.name: hashes(p) for p in subjects}
    with tarfile.open(output / 'before-reopen.tar.gz', 'w:gz') as archive:
        for subject in subjects:
            archive.add(subject, arcname=subject.name)
    save(output / 'sha256.json', before)
    try:
        result = oracle(root)
        save(output / 'independent.json', result)
        return result
    finally:
        check(before == {p.name: hashes(p) for p in subjects}, 'independent inspection changed source/target bytes')


class Case:
    def __init__(self, root):
        self.root, self.count = root, 0
        (root / 'evidence').mkdir(parents=True)

    def invoke(self, command, extra='', source=None, cut=None, accept=True):
        self.count += 1
        prefix = self.root / 'evidence' / f'{self.count:03d}-{command}'
        marker = prefix.with_suffix('.barrier')
        args = ['java', '-cp', CLASSPATH]
        if cut:
            args += ['-Dgse.offline.cut=' + cut, '-Dgse.offline.marker=' + str(marker)]
        args += [WORKER, str(self.root), command, str(source) if source else '-', str(extra)]
        with prefix.with_suffix('.stdout').open('w') as stdout, prefix.with_suffix('.stderr').open('w') as stderr:
            process = subprocess.Popen(args, cwd=ROOT, stdout=stdout, stderr=stderr)
            try:
                if cut:
                    deadline = time.monotonic() + 40
                    while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
                        time.sleep(0.01)
                    check(marker.exists(), 'owned process missed barrier: ' + cut + '\n' + prefix.with_suffix('.stderr').read_text())
                    recorded = marker.read_text().splitlines()
                    check(recorded == [str(process.pid), cut], 'barrier process identity mismatch')
                    process.kill(); process.wait(timeout=10)
                    check(process.returncode == -9, 'worker was not killed by SIGKILL')
                else:
                    process.wait(timeout=40)
                save(prefix.with_suffix('.process.json'), dict(pid=process.pid, command=command, args=args,
                                                              exitCode=process.returncode, barrier=cut))
                if cut:
                    return None
                if not accept:
                    check(process.returncode != 0, command + ' unexpectedly succeeded')
                    return prefix.with_suffix('.stderr').read_text()
                check(process.returncode == 0, command + ' failed: ' + prefix.with_suffix('.stderr').read_text())
                return json.loads(prefix.with_suffix('.stdout').read_text())
            finally:
                if process.poll() is None:
                    process.kill(); process.wait(timeout=10)
                save(prefix.with_suffix('.process.json'), dict(pid=process.pid, command=command, args=args,
                                                              exitCode=process.returncode, barrier=cut))

    def bootstrap(self, cut=None, source=None):
        plan = self.invoke('plan', source=source)['planDigest']
        check(self.invoke('plan', source=source)['planDigest'] == plan, 'nondeterministic typed plan')
        self.invoke('apply', plan, source, cut)
        return plan


def control(artifact, classes, case, command, minor, source=None):
    classpath = os.pathsep.join(map(str, (artifact, classes, REPLICATION, classes.parent / 'public-consumer-classes')))
    args = ['java', '-cp', classpath, CONTROL, command, str(case.root), str(minor)] + ([] if source is None else [str(source)])
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, timeout=40)
    prefix = case.root / 'evidence' / f'control-{command}-{minor}'
    prefix.with_suffix('.stdout').write_text(result.stdout); prefix.with_suffix('.stderr').write_text(result.stderr)
    check(result.returncode == 0, 'published V4.4 ' + command + ' failed: ' + result.stderr)
    check([line for line in result.stderr.splitlines() if line.startswith('controlSource=')] == ['controlSource=' + str(artifact)],
          'control did not load the pinned published V4.4 core')
    return json.loads(result.stdout)


def run(workspace, artifact, only=None):
    global CLASSPATH
    workspace, artifact = workspace.resolve(), artifact.resolve()
    check(not workspace.exists(), 'evidence directory must be absent')
    workspace.mkdir(parents=True)
    check(hashlib.sha256(artifact.read_bytes()).hexdigest() == CONTROL_SHA, 'published V4.4 checksum mismatch')
    receipt = dict(schema='gse-v50-offline-authority-evidence-v1', status='RUNNING', publicRuntime='not-exercised-by-offline-gate',
                   sourceSha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                   workingTreeDiffSha256=hashlib.sha256(subprocess.check_output(['git', 'diff', '--binary', 'HEAD'], cwd=ROOT)).hexdigest(),
                   coreJarSha256=hashlib.sha256(CORE.read_bytes()).hexdigest(), replicationJarSha256=hashlib.sha256(REPLICATION.read_bytes()).hexdigest(),
                   controlJarSha256=CONTROL_SHA, cases=[])
    def passed(name, details):
        receipt['cases'].append(dict(case=name, status='PASS', **details))
        print(json.dumps(receipt['cases'][-1], sort_keys=True), flush=True)
    try:
        source_files = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).split(b'\0')
        inventory = [[name.decode(), hashlib.sha256((ROOT / name.decode()).read_bytes()).hexdigest()]
                     for name in sorted(set(source_files) - {b''}) if (ROOT / name.decode()).is_file()]
        receipt['sourceInventorySha256'] = hashlib.sha256(json.dumps(inventory, separators=(',', ':')).encode()).hexdigest()
        receipt['java'] = []
        for module, tests, jar in (('', ('engine.V50ApplicationTransferTest',), CORE),
                ('general-search-engine-replication', ('admission.V50AdmissionDeclarationsTest', 'replication.V50OfflineAuthorityTest',
                 'replication.V50OfflineRejectionsTest', 'replication.V50OfflineFixtureAgreementTest'), REPLICATION)):
            base = ROOT / module
            check(all(p.stat().st_mtime_ns <= jar.stat().st_mtime_ns for p in (base / 'src/main').rglob('*') if p.is_file()),
                  'production JAR predates sources; run reactor clean package')
            for test in tests:
                report = base / ('target/surefire-reports/TEST-' + PACKAGE + test + '.xml')
                suite = ET.parse(report).getroot()
                check(int(suite.attrib['tests']) > 0 and all(int(suite.attrib.get(k, 0)) == 0 for k in ('failures', 'errors', 'skipped')),
                      'Java gate did not execute: ' + test)
                check(all(p.stat().st_mtime_ns <= report.stat().st_mtime_ns for p in (base / 'src').rglob('*') if p.is_file()),
                      'Java report predates sources: ' + test)
                receipt['java'].append(dict(test=test, tests=int(suite.attrib['tests']), reportSha256=hashlib.sha256(report.read_bytes()).hexdigest()))
        classes = workspace / 'control-classes'; classes.mkdir()
        sources = ROOT / 'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/admission'
        consumer = workspace / 'public-consumer-classes'; consumer.mkdir()
        candidate_compile = subprocess.run(['javac', '--release', '21', '-proc:none', '-cp', os.pathsep.join(map(str, (CORE, REPLICATION))),
                '-d', str(consumer), *[str(sources / (name + '.java')) for name in ('AdmissionJson', 'AdmissionSemanticModel', 'OfflineApplication', 'OfflinePublicConsumer')]],
                cwd=ROOT, text=True, capture_output=True, timeout=40)
        (workspace / 'consumer-compile.stderr').write_text(candidate_compile.stderr)
        check(candidate_compile.returncode == 0, 'public consumer failed to compile against production JARs: ' + candidate_compile.stderr)
        workers = workspace / 'fault-worker-classes'; workers.mkdir()
        worker_compile = subprocess.run(['javac', '--release', '21', '-proc:none', '-cp', os.pathsep.join(map(str, (CORE, REPLICATION, consumer))),
                '-d', str(workers), str(sources.parent / 'replication/V50OfflineCrashWorker.java')],
                cwd=ROOT, text=True, capture_output=True, timeout=40)
        (workspace / 'worker-compile.stderr').write_text(worker_compile.stderr)
        check(worker_compile.returncode == 0, 'fault worker failed to compile: ' + worker_compile.stderr)
        CLASSPATH = os.pathsep.join(map(str, (CORE, REPLICATION, consumer, workers)))
        compile_result = subprocess.run(['javac', '--release', '21', '-proc:none', '-cp', os.pathsep.join(map(str, (artifact, REPLICATION, consumer))),
                '-d', str(classes), *[str(sources / (name + '.java')) for name in ('AdmissionJson', 'AdmissionSemanticModel', 'PublicRuntimeWorkload', 'AdmissionV44Control')]],
                cwd=ROOT, text=True, capture_output=True, timeout=40)
        (workspace / 'control-compile.stderr').write_text(compile_result.stderr)
        check(compile_result.returncode == 0, 'control did not compile against published V4.4: ' + compile_result.stderr)
        if only in (None, 'bootstrap'):
            for index, cut in enumerate(BOOTSTRAP_CUTS):
                case = Case(workspace / f'bootstrap-{index:02d}')
                plan = case.bootstrap(cut)
                before = capture(case.root, 'killed')
                if before['phase'] < 4:
                    for node in ('node-1', 'node-2', 'node-3'):
                        if (case.root / node).exists():
                            case.invoke('inspect', node, accept=False)
                result = case.invoke('resume', plan)
                after = capture(case.root, 'resumed')
                check(after['phase'] == 4 and len(after['sealedNodes']) == 3, 'resume failed to deliver all seals')
                check(result == case.invoke('resume', plan), 'repeated resume changed the decision')
                passed(cut, dict(beforePhase=before['phase'], afterPhase=after['phase']))
        if only in (None, 'cleanup'):
            discovery = Case(workspace / 'cleanup-discovery'); discovery.bootstrap('BOOTSTRAP_PREPARED_FORCED')
            discovery_plan = discovery.invoke('cleanup-plan')
            cleanup_cuts = ['CLEANUP_PLAN_FORCED', 'CLEANUP_ABORTING_FORCED'] + [f'CLEANUP_DELETE_{i}_FORCED' for i in range(len(discovery_plan['deletePaths']))]
            for index, cut in enumerate(cleanup_cuts):
                case = Case(workspace / f'cleanup-{index:02d}'); case.bootstrap('BOOTSTRAP_PREPARED_FORCED')
                plan = case.invoke('cleanup-plan'); plan_file = case.root / 'evidence/cleanup-plan.json'; save(plan_file, plan)
                case.invoke('cleanup-apply', plan_file, cut=cut)
                if (case.root / 'operation').exists():
                    capture(case.root, 'killed', inspect.cleanup)
                    check(case.invoke('cleanup-plan') == plan, 'cleanup resume changed exact deletion authority')
                    case.invoke('cleanup-apply', plan_file)
                check(all(not (case.root / name).exists() for name in ('operation', 'node-1', 'node-2', 'node-3')), 'cleanup left owned outputs')
                passed(cut, dict(cleaned=True))
        if only in (None, 'replacement'):
            for index, cut in enumerate(REPLACEMENT_CUTS):
                case = Case(workspace / f'replacement-{index:02d}'); case.bootstrap()
                before = hashes(case.root / 'node-1')
                plan = case.invoke('replacement-plan'); plan_file = case.root / 'evidence/replacement-plan.json'; save(plan_file, plan)
                case.invoke('replacement-apply', plan_file, cut=cut)
                capture(case.root, 'killed', inspect.replacement)
                case.invoke('replacement-resume', plan_file)
                after = capture(case.root, 'resumed', inspect.replacement)
                check(after['phase'] == 2 and not after['voter'], 'replacement became a genesis voter')
                check(before == hashes(case.root / 'node-1'), 'replacement changed its source')
                passed(cut, dict(voter=False))
        if only in (None, 'semantic'):
            for minor in range(3):
                case = Case(workspace / f'v44-source-{minor}')
                expected = control(artifact, classes, case, 'create', minor)
                before = hashes(case.root / 'source')
                actual = case.invoke('semantic', source=case.root / 'source')
                check(actual['sequence'] == expected['sequence'] and actual['semantics'] == expected['semantics'], 'imported V4.4 semantics changed')
                capture(case.root, 'imported')
                check(before == hashes(case.root / 'source'), 'typed import changed published backup')
                for output_minor in range(3):
                    restored = Case(case.root / f'roundtrip-{output_minor}')
                    report = control(artifact, classes, restored, 'restore', output_minor, case.root / f'export-{output_minor}')
                    check(report == expected, 'published V4.4 rejected or changed exported application state')
                passed('published-v44-source-' + str(minor), dict(exportFormats=[0, 1, 2], semanticComparison='PASS'))
        receipt['status'] = 'PASS'
    except Exception as error:
        receipt['status'], receipt['failure'] = 'FAIL', str(error)
        raise
    finally:
        save(workspace / 'receipt.json', receipt)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path)
    parser.add_argument('--control-jar', type=Path, required=True)
    parser.add_argument('--only', choices=('bootstrap', 'cleanup', 'replacement', 'semantic'))
    args = parser.parse_args(); run(args.workspace, args.control_jar, args.only)
