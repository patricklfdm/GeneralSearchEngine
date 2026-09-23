"""Phase 6A model review boundary: isolated control parity and synthetic projections.

Invoked by the existing foundation gate; does not expose the full performance
receipt schema or add a premature performance/paid workflow.
"""
import argparse
import copy
import json
import os
import shutil
from pathlib import Path
import subprocess
import time
import zipfile
from . import controls, performance_plan as plan, performance_model as model
from . import performance_fixtures as fixtures, performance_projection as projection, performance_semantics as semantics
from .storage_inspector import inventory

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'io.github.patricklfdm.generalsearch.admission.'


def save(path, value):
    path.write_bytes(model.canonical(value) + b'\n')


def command(args, root, label, deadline):
    args = list(map(str, args))
    receipt = dict(args=args, startNanos=time.monotonic_ns(), exitCode=None)
    output, errors = root / (label + '.stdout'), root / (label + '.stderr')
    try:
        remaining = deadline - time.monotonic()
        model.need(remaining > 0, 'rich foundation command budget')
        # Files retain compiler/runtime diagnostics even on timeout; no unbounded
        # PIPE buffer and subprocess ownership always ends before validation.
        with output.open('xb') as out, errors.open('xb') as err:
            with subprocess.Popen(args, cwd=ROOT, stdout=out, stderr=err) as process:
                receipt['pid'] = process.pid
                try:
                    receipt['exitCode'] = process.wait(timeout=min(60, remaining))
                except BaseException:
                    process.kill()
                    receipt['exitCode'] = process.wait(timeout=10)
                    raise
        model.need(receipt['exitCode'] == 0, label + ' failed; see ' + str(errors))
        model.need(output.stat().st_size <= 4 << 20 and errors.stat().st_size <= 4 << 20, 'rich command output bound')
    finally:
        receipt['endNanos'] = time.monotonic_ns()
        save(root / (label + '-process.json'), receipt)
    return receipt


def negatives(rows, admitted_plan):
    """Reseal per-answer hashes where relevant; semantic validation must still fail."""
    results = []
    for name in ('missing-call', 'reordered-call', 'hidden-failure', 'seed-drift', 'partial-bulk', 'stale-read', 'query-order', 'sequence-drift'):
        changed = copy.deepcopy(rows)
        if name == 'missing-call':
            changed.pop(0)
        elif name == 'reordered-call':
            changed[10], changed[11] = changed[11], changed[10]
        elif name == 'hidden-failure':
            changed[10]['outcome'] = 'NOT_SUBMITTED'
        elif name == 'seed-drift':
            changed[10]['state']['documents'][0][2] = 'forged'
        elif name == 'partial-bulk':
            next(v for v in changed if v['operation'] == 'ADD_ALL')['state']['documents'].pop()
        elif name == 'stale-read':
            next(v for v in changed if v['operation'] == 'GET')['answer'] = 'stale'
        elif name == 'query-order':
            next(v for v in changed if v['operation'] == 'QUERY')['answer'].reverse()
        else:
            changed[8]['afterSequence'] += 1
        for row in changed:
            row['answerSha256'] = model.sha(model.canonical(row['answer']))
        try:
            semantics.validate_calls(changed, admitted_plan)
        except ValueError as error:
            results.append(dict(case=name, status='REJECTED', reason=str(error), mutatedTapeSha256=model.sha(model.canonical(changed))))
        else:
            raise ValueError('rich semantic negative accepted: ' + name)
    return results


def backup_negatives(root, admitted_plan):
    """Change raw source data and recompute CRC, payload SHA and content identity."""
    source = root / 'control/source'
    meta = semantics.metadata(source / 'gse-backup-metadata')
    original = {p.name: p.read_bytes() for p in source.iterdir()}
    checkpoint = original['gse-backup-checkpoint']
    results = []
    for name, before, after in [('changed-source-document', b'Java 1\n', b'Java 9\n'),
                               ('changed-source-index', b'category', b'categ0ry')]:
        target = root / 'negative-backups' / name
        shutil.copytree(source, target)
        model.need(checkpoint[:-4].count(before) == 1, 'negative mutation target')
        changed = semantics.backup.checked(checkpoint[:-4].replace(before, after))
        payloads = {'gse-backup-checkpoint': changed, 'gse-backup-metadata': original['gse-backup-metadata']}
        old_payloads = {k: original[k] for k in payloads}
        def content(values):
            return bytes.fromhex(model.sha(semantics.backup._backup_preimage(values, meta['profile'], meta['history'], 4,
                                            'performance-store', 'semantic-schema', 'semantic-codec', 1)))
        body = original['gse-backup-manifest'][:-4]
        replacements = [(bytes.fromhex(model.sha(checkpoint)), bytes.fromhex(model.sha(changed))),
                        (content(old_payloads), content(payloads))]
        for old, new in replacements:
            model.need(body.count(old) == 1, 'negative manifest target')
            body = body.replace(old, new)
        (target / 'gse-backup-checkpoint').write_bytes(changed)
        (target / 'gse-backup-manifest').write_bytes(semantics.backup.checked(body))
        try:
            semantics.source_backup(target, model.initial(admitted_plan))
        except ValueError as error:
            results.append(dict(case=name, status='REJECTED', reason=str(error), resealed=True, members=inventory(target)))
        else:
            raise ValueError('rich backup negative accepted: ' + name)
    return results


def run(output, control_directory=ROOT / 'target/v51-controls', candidate_core=ROOT / 'target/general-search-engine-5.1.0-SNAPSHOT.jar'):
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema='gse-v51-performance-foundation-v1', execution='rich-model-and-control-only',
                   performanceMeasured=False, automaticRuntimeExecuted=False, paidCloud=False, status='FAIL')
    deadline = time.monotonic() + 300
    try:
        admitted = plan.load()
        save(root / 'plan.json', admitted)
        receipt['plan'] = plan.validate(admitted)
        receipt['source'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, timeout=10).strip()
        paths = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT, timeout=10).decode().split('\0')
        sources = {p: model.sha((ROOT / p).read_bytes()) for p in sorted(set(paths)) if p and (ROOT / p).is_file()}
        save(root / 'source-inventory.json', sources)
        receipt['sourceInventorySha256'] = model.sha(model.canonical(sources))
        resolved = controls.resolve(control_directory)
        model.need([{k: item[k] for k in ('artifact', 'version', 'sha256')} for item in resolved['artifacts']] ==
                   admitted['publishedControls']['artifacts'], 'rich controls differ from admitted pins')
        control_directory = Path(control_directory).resolve()
        core44 = control_directory / 'general-search-engine-4.4.0.jar'
        jars = {'published-v44': core44, 'published-v50': control_directory / 'general-search-engine-5.0.0.jar',
                'candidate': Path(candidate_core).resolve()}
        receipt['controls'] = resolved
        module_sources = ROOT / 'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/admission'
        java = ROOT / 'scripts/v51/java'
        sources = [module_sources / 'AdmissionJson.java', module_sources / 'AdmissionSemanticModel.java',
                   java / 'V51RichWorkload.java', java / 'V51RichControl.java']
        receipt['compiledCores'] = {}
        for name, jar in jars.items():
            model.need(jar.is_file() and not jar.is_symlink(), 'rich compile JAR')
            with zipfile.ZipFile(jar) as archive:
                model.need(not any('/V51Rich' in n for n in archive.namelist()), 'rich fixture in production JAR')
                if name == 'candidate':
                    model.need(b'Implementation-Version: 5.1.0-SNAPSHOT' in archive.read('META-INF/MANIFEST.MF'), 'rich candidate core version')
            classes = root / ('classes-' + name)
            classes.mkdir()
            command(['javac', '--release', '21', '-proc:none', '-cp', jar, '-d', classes, *sources], root, 'compile-' + name, deadline)
            model.need(all(p.relative_to(classes).as_posix().startswith('io/github/patricklfdm/generalsearch/admission/') for p in classes.rglob('*.class')),
                       'rich control class shadowing')
            receipt['compiledCores'][name] = dict(path=str(jar), sha256=model.sha(jar.read_bytes()), execution='compile-only')
        control_root = root / 'control'
        control_root.mkdir()
        cp = os.pathsep.join(map(str, (core44, root / 'classes-published-v44')))
        proc = command(['java', *admitted['jvmArguments'], '-cp', cp, PACKAGE + 'V51RichControl', control_root, root / 'plan.json'], root, 'control', deadline)
        receipt['control'] = semantics.validate(control_root, admitted, core44, proc)
        rows = [model.strict_json(line) for line in (control_root / 'calls.jsonl').read_bytes().splitlines()]
        receipt['negatives'] = negatives(rows, admitted) + backup_negatives(root, admitted)
        fixture = fixtures.generate(admitted)
        projected = projection.project(fixture['manifest'], fixture['genesis'], fixture['votes'])
        for snapshot in fixture['snapshots']:
            projection.snapshot(projected, snapshot)
        receipt['syntheticProjection'] = fixtures.encoding_report(admitted, fixture)
        save(root / 'synthetic-projection.json', {k: fixtures.b64(v) if isinstance(v, bytes) else
             {n: [fixtures.b64(r) for r in rows] for n, rows in v.items()} if isinstance(v, dict) else
             [fixtures.b64(r) for r in v] for k, v in fixture.items()})
        receipt['status'] = 'PASS'
    except BaseException as error:
        receipt['failure'] = dict(type=type(error).__name__, message=str(error))
        raise
    finally:
        receipt['elapsedSeconds'] = round(300 - (deadline - time.monotonic()), 3)
        save(root / 'receipt.json', receipt)
        save(root / 'members.json', inventory(root))
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('--controls', type=Path, default=ROOT / 'target/v51-controls')
    args = parser.parse_args()
    result = run(args.output, args.controls)
    print(json.dumps({k: result[k] for k in ('status', 'execution', 'performanceMeasured', 'automaticRuntimeExecuted')}))
