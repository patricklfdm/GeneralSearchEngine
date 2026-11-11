"""Exact-source joining initialization process cohort and independent replay.

All 360 whole histories are required. Metadata collection is not qualification;
the original physical/authority chain and every applicable negative run again.
No JVM execution, history retries or paid cloud operations occur in this module.
"""
import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import json
from pathlib import Path
import re
import sys

from . import joining_process_authority as gate
from . import joining_process_run as run
from . import remove_process_matrix as shared
from . import process_toolchain

h, need, physical = run.h, run.h.need, gate.physical
KINDS, BUILDS = run.CASES, run.BUILDS
SCHEMA = 'gse-v53-joining-process-matrix-v1'
read, hash_field, reader_manifest = shared.read, shared.hash_field, shared.reader_manifest


def slug(case):
    run.selected(case)
    return case.lower().replace(',', '__')


def check_pins(source, build, toolchain, reader):
    need(all(hash_field(v) for v in (source, build, toolchain, reader)), 'joining process matrix pinned hashes')
    manifest = reader_manifest()
    need(manifest['sha256'] == reader, 'joining process matrix pinned reader')
    return manifest


def member(path, case, source, build, toolchain, reader):
    """Recollect retained bytes; a successful producer label is insufficient."""
    run.selected(case); manifest = check_pins(source, build, toolchain, reader)
    path = Path(path)
    need(path.is_dir() and not path.is_symlink(), 'joining process matrix producer directory')
    receipt = read(path/'receipt.json')
    need(type(receipt) is dict and receipt.get('schema') == run.SCHEMA and receipt.get('status') == 'PARTIAL' and
         receipt.get('executionStatus') == 'PASS' and receipt.get('case') == case and receipt.get('collectionComplete') is True and
         all(receipt.get(k) is False for k in ('physicalHistoryQualified', 'processDeathQualified', 'phase3Complete')) and
         type(receipt.get('retries')) is int and receipt['retries'] == 0, 'joining process matrix successful unretried member')
    execution = receipt.get('execution')
    need(type(execution) is dict and type(execution.get('exit')) is int and execution['exit'] == 0 and
         gate.f.canonical(read(path/'execution.json')) == gate.f.canonical(execution), 'joining process matrix original execution')
    recorded, _ = h.read_recorded_source(path)
    need(receipt.get('sourceSha256') == source == h.digest((path/'source.json').read_bytes()) and
         receipt.get('baseHead') == recorded['head'], 'joining process matrix exact producer source')
    need(all(recorded['files'].get(k) == v for k, v in manifest['files'].items()), 'joining process matrix reader belongs to producer source')
    command = receipt.get('command'); wanted = run.command(case)
    need(type(command) is list and len(command) == len(wanted)+1 and type(command[0]) is str and
         Path(command[0]).name == 'mvn' and command[1:] == wanted, 'joining process matrix exact whole command')
    work = path/'workspace'
    for name in (*BUILDS, h.MODULE+'/target/surefire-reports'):
        relative = Path(name)
        need(all((work/p).is_dir() and not (work/p).is_symlink() for p in (relative, *relative.parents)),
             'joining process matrix linked generated parent')
    reports = work/h.MODULE/'target/surefire-reports'
    for report in reports.glob('TEST-*.xml'): h.snapshot.s.regular(report, 8*h.snapshot.MIB)
    need(gate.f.canonical(receipt.get('junit')) == gate.f.canonical(run.junit(reports, case)), 'joining process matrix exact JUnit receipt')
    classes = read(path/'build.json')
    need(type(classes) is dict and set(classes) == set(BUILDS) and
         receipt.get('buildSha256') == build == h.digest((path/'build.json').read_bytes()), 'joining process matrix exact build manifest')
    for name in BUILDS: need(h.inventory(work/name) == classes[name], 'joining process matrix original built bytes')
    tools = read(path/'toolchain.json'); process_toolchain.validate(tools)
    observed_tools = h.digest((path/'toolchain.json').read_bytes())
    need(receipt.get('toolchainSha256') == observed_tools and
         process_toolchain.pin((path/'toolchain.json').read_bytes()) == toolchain, 'joining process matrix exact toolchain')
    name = receipt.get('raw')
    need(type(name) is str and re.fullmatch('workspace/'+h.MODULE+r'/target/v53-native-dispatch/run-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', name),
         'joining process matrix original history path')
    need(all((path/parent).is_dir() and not (path/parent).is_symlink() for parent in Path(name).parents),
         'joining process matrix linked history parent')
    raw = path/name
    need({p.name for p in raw.parent.iterdir()} == {raw.name}, 'joining process matrix exact original directory')
    collection = read(path/'collection.json'); inventory = h.inventory(raw)
    need(type(collection) is dict and receipt.get('collectionSha256') == h.digest((path/'collection.json').read_bytes()) and
         collection.get('inventory') == inventory, 'joining process matrix original collection')
    need(gate.f.canonical(collection) == gate.f.canonical(run.collect(raw, case)), 'joining process matrix independently recollected member')
    plan = h.digest(h.snapshot.s.regular(raw/'original-plan.gsbp', h.snapshot.MIB))
    return dict(raw=raw, inventory=inventory, plan=plan, toolchain=toolchain, observedToolchain=observed_tools,
                receiptSha256=h.digest((path/'receipt.json').read_bytes()))


def expected_negatives(catalogue):
    return [dict(case=name, status='REJECTED', reason=reason) for name, reason in catalogue.items()]


def check_result(result, case):
    """Exact scope and all three negative vectors, including evidenced absence."""
    run.selected(case)
    authority = result.get('authority', {}); original = authority.get('original', {})
    need(authority.get('status') == 'PASS' and authority.get('completeNegativeCatalogue') is True and
         authority.get('originalPreserved') is True and original.get('status') == 'PARTIAL' and original.get('case') == case and
         original.get('scope') == 'original-joining-process-export-control-and-maintenance' and
         all(original.get(k) is True for k in ('exportControlAuthorityVerified', 'maintenanceAuthorityVerified',
                                             'continuousLedgersQualified', 'ballotCompositionVerified')) and
         all(v.get(k) is False for v in (authority, original) for k in ('processDeathQualified', 'phase3Complete')),
         'joining process matrix complete original authority')
    sessions = original.get('exports', {}).get('boundSessions')
    need(type(original.get('joiningLearnerWrites')) is int and original['joiningLearnerWrites'] >= 0 and
         type(sessions) is dict and all(type(k) is str and type(v) is int and v >= 0 for k, v in sessions.items()),
         'joining process matrix original absence observations')
    absent = gate.negative_plan(original)
    expected = [dict(case=k, status='NOT_APPLICABLE' if k in absent else 'REJECTED', reason=absent.get(k, v))
                for k, v in gate.NEGATIVES.items()]
    need(authority.get('negatives') == expected, 'joining process matrix exact authority negatives')
    composed = result.get('physical', {}); prior = original.get('precondition', {})
    need(composed.get('originalPreserved') is True and gate.f.canonical(composed.get('original')) == gate.f.canonical(prior) and prior.get('case') == case and
         all(prior.get(k) is True for k in ('originalPhysicalHistoryVerified', 'observedTransportVerified', 'durableACKsVerified')) and
         prior.get('phase3Complete') is False and prior.get('processDeathQualified') is False,
         'joining process matrix same original physical replay')
    need(composed.get('negatives') == expected_negatives(physical.negative_reasons(prior.get('transportFormat','legacy'))),
         'joining process matrix exact physical negatives')
    need(result.get('transactionNegatives') == expected_negatives(physical.transaction.NEGATIVES),
         'joining process matrix exact transaction negatives')


def qualify_member(path, case, source, build, toolchain, reader, *, progress=None):
    before = member(path, case, source, build, toolchain, reader)
    # Full original-first validation is part of each driver. Do not turn an
    # unrelated original failure into successful negative qualification.
    authority = gate.qualify(before['raw'], case, workers=1, progress=progress)
    need(authority['status'] == 'PASS', 'joining process matrix authority qualification failed')
    composed = physical.qualify(before['raw'], case, progress=progress)
    transaction = physical.transaction.negatives(before['raw'], case)
    result = dict(authority=authority, physical=composed, transactionNegatives=transaction)
    check_result(result, case)
    need(member(path, case, source, build, toolchain, reader) == before, 'joining process matrix producer changed during replay')
    check_pins(source, build, toolchain, reader)
    return dict(schema=SCHEMA, case=case, status='PASS', qualification=result, producerReceiptSha256=before['receiptSha256'],
                originalPlanSha256=before['plan'], sourceSha256=source, buildSha256=build,
                toolchainSha256=toolchain, readerSha256=reader, declaredJoiningProcessMatrixQualified=False, phase3Complete=False)


def validate(paths, source, build, toolchain, reader, *, workers=1, progress=None):
    need(type(workers) is int and 1 <= workers <= 4, 'joining process matrix replay workers')
    check_pins(source, build, toolchain, reader)
    need(type(paths) is dict and set(paths) == set(KINDS), 'joining process matrix complete declared set')
    need(len({Path(v).resolve() for v in paths.values()}) == len(KINDS), 'joining process matrix distinct producers')
    originals = {case: member(paths[case], case, source, build, toolchain, reader) for case in KINDS}
    need(len({v['plan'] for v in originals.values()}) == len(KINDS), 'joining process matrix distinct original histories')
    outcomes = {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks = {pool.submit(qualify_member, paths[case], case, source, build, toolchain, reader): case for case in KINDS}
        pending = set(tasks)
        while pending:
            done, pending = wait(pending, timeout=60, return_when=FIRST_COMPLETED)
            for task in done:
                case = tasks[task]
                try: result = task.result()
                except Exception as error: result = dict(case=case, status='FAIL', failure=dict(type=type(error).__name__, message=str(error)))
                outcomes[case] = result
                if progress: progress(dict(stage='member-terminal', completed=len(outcomes), total=len(KINDS), **result))
            if not done and progress: progress(dict(stage='independent-replay', completed=len(outcomes), total=len(KINDS)))
    for case in KINDS:
        need(member(paths[case], case, source, build, toolchain, reader) == originals[case],
             'joining process matrix producer changed before completion')
    check_pins(source, build, toolchain, reader)
    passed = all(v['status'] == 'PASS' for v in outcomes.values())
    return dict(schema=SCHEMA, status='PASS' if passed else 'FAIL', scope='360-original-joining-initialization-process-histories',
                cases=[outcomes[k] for k in KINDS], wholeHistories=len(KINDS),
                sourceSha256=source, buildSha256=build, toolchainSha256=toolchain, readerSha256=reader,
                declaredJoiningProcessMatrixQualified=passed, allMembershipProfilesQualified=False,
                originalObservationCoverageComplete=False, phase3Complete=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('plan')
    for name in ('member', 'aggregate'):
        cmd = sub.add_parser(name); cmd.add_argument('output')
        if name == 'member':
            cmd.add_argument('--producer', required=True); cmd.add_argument('--case', required=True, choices=KINDS)
        else:
            cmd.add_argument('--inputs', required=True); cmd.add_argument('--workers', type=int, default=1)
        for pin in ('source', 'build', 'toolchain', 'reader'): cmd.add_argument('--'+pin+'-sha256', required=True)
    args = parser.parse_args()
    if args.command == 'plan':
        print(json.dumps(dict(cases=[dict(case=v, id=slug(v)) for v in KINDS], reader=reader_manifest(),
                              negativesPerHistory=len(gate.NEGATIVES)+len(physical.NEGATIVES)+len(physical.transaction.NEGATIVES),
                              phase3Complete=False), sort_keys=True)); return
    output = Path(args.output); output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema=SCHEMA, status='RUNNING', phase3Complete=False)
    h.save(output/'receipt.json', receipt)
    try:
        from .remove_process_hosted import progress as heartbeat
        pins = [getattr(args, p+'_sha256') for p in ('source', 'build', 'toolchain', 'reader')]
        with heartbeat('joining-process-'+args.command, getattr(args, 'case', None)), (output/'progress.jsonl').open('x') as stream:
            def progress(row):
                stream.write(json.dumps(row, sort_keys=True)+'\n'); stream.flush()
                print(json.dumps({k:v for k,v in row.items() if k != 'qualification'}, sort_keys=True), file=sys.stderr, flush=True)
            if args.command == 'member': receipt = qualify_member(args.producer, args.case, *pins, progress=progress)
            else:
                inputs = Path(args.inputs)
                need(inputs.is_dir() and not inputs.is_symlink() and {p.name for p in inputs.iterdir()} == {slug(v) for v in KINDS},
                     'joining process matrix exact input directories')
                receipt = validate({v: inputs/slug(v) for v in KINDS}, *pins, workers=args.workers, progress=progress)
        need(receipt['status'] == 'PASS', 'joining process matrix failed members')
    except BaseException as error:
        receipt.update(status='FAIL', failure=dict(type=type(error).__name__, message=str(error))); raise
    finally: h.save(output/'receipt.json', receipt)
    print(json.dumps(dict(status='PASS', receipt=str(output/'receipt.json'), phase3Complete=False), sort_keys=True))


if __name__ == '__main__': main()
