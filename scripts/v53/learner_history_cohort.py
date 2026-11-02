"""Exact-source original-first qualification of two whole native learner histories.

This focused 3-ADD pair does not qualify all profiles, process death, autonomous
membership, the full network matrix, combined peak resources or Phase 3 closure.
"""
import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import json
from pathlib import Path
import re
import sys

from . import learner_history_run as run
from . import learner_retention_evidence as retention

h, need, shared, tc = run.h, run.h.need, run.shared, run.tc
read, reader_manifest, hash_field = shared.read, shared.reader_manifest, shared.hash_field
KINDS, BUILDS = run.CASES, run.BUILDS
SCHEMA = 'gse-v53-learner-history-cohort-v1'


def slug(case):
    run.selected(case)
    return case


def check_pins(source, build, toolchain, reader):
    need(all(hash_field(v) for v in (source,build,toolchain,reader)), 'learner cohort pinned hashes')
    manifest = reader_manifest(); need(manifest['sha256'] == reader, 'learner cohort pinned reader')
    return manifest


def member(path, case, source, build, toolchain, reader):
    manifest = check_pins(source,build,toolchain,reader); run.selected(case)
    path = Path(path); need(path.is_dir() and not path.is_symlink(), 'learner cohort producer directory')
    receipt = read(path/'receipt.json')
    need(type(receipt) is dict and receipt.get('schema') == run.SCHEMA and receipt.get('case') == case and
         receipt.get('status') == 'PARTIAL' and receipt.get('executionStatus') == 'PASS' and
         receipt.get('collectionComplete') is True and all(receipt.get(k) is False for k in ('nativeHistoryQualified','phase3Complete')) and
         type(receipt.get('retries')) is int and receipt['retries'] == 0, 'learner cohort successful unretried whole history')
    for name in ('execution','collectionExecution'):
        value = receipt.get(name)
        need(type(value) is dict and type(value.get('exit')) is int and value['exit'] == 0, 'learner cohort successful processes')
    need(h.snapshot.f.canonical(read(path/'execution.json')) == h.snapshot.f.canonical(receipt['execution']), 'learner cohort original execution record')
    recorded, _ = h.read_recorded_source(path)
    need(receipt.get('sourceSha256') == source == h.digest((path/'source.json').read_bytes()) and
         receipt.get('baseHead') == recorded['head'], 'learner cohort exact producer source')
    need(receipt.get('readerSha256') == reader and all(recorded['files'].get(k) == v for k,v in manifest['files'].items()),
         'learner cohort reader belongs to producer source')
    args = receipt.get('command'); wanted = run.command(case)
    need(type(args) is list and len(args) == len(wanted)+1 and type(args[0]) is str and Path(args[0]).name == 'mvn' and args[1:] == wanted,
         'learner cohort exact whole command')
    work = path/'workspace'
    for name in (*BUILDS,h.MODULE+'/target/surefire-reports'):
        relative = Path(name)
        need(all((work/p).is_dir() and not (work/p).is_symlink() for p in (relative,*relative.parents)), 'learner cohort linked generated parent')
    need(h.snapshot.f.canonical(receipt.get('junit')) == h.snapshot.f.canonical(run.junit(work/h.MODULE/'target/surefire-reports',case)),
         'learner cohort exact JUnit receipt')
    classes = read(path/'build.json')
    need(type(classes) is dict and set(classes) == set(BUILDS) and receipt.get('buildSha256') == build == h.digest((path/'build.json').read_bytes()),
         'learner cohort exact build manifest')
    for name in BUILDS: need(h.inventory(work/name) == classes[name], 'learner cohort original built bytes')
    tc.validate(read(path/'toolchain.json')); tools_hash = h.digest((path/'toolchain.json').read_bytes())
    need(receipt.get('toolchainSha256') == tools_hash and tc.pin((path/'toolchain.json').read_bytes()) == toolchain,
         'learner cohort portable toolchain')
    name = receipt.get('raw')
    need(type(name) is str and re.fullmatch('workspace/'+h.MODULE+r'/target/v53-native-dispatch/run-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',name),
         'learner cohort original history path')
    raw = path/name
    need(all((path/p).is_dir() and not (path/p).is_symlink() for p in Path(name).parents), 'learner cohort linked history parent')
    need({v.name for v in raw.parent.iterdir()} == {raw.name}, 'learner cohort exact original history directory')
    collection = read(path/'collection.json'); inventory = h.inventory(raw)
    need(receipt.get('collectionSha256') == h.digest((path/'collection.json').read_bytes()) and
         h.snapshot.f.canonical(collection) == h.snapshot.f.canonical(run.collect(raw,case)) and collection.get('inventory') == inventory,
         'learner cohort independently recollected original')
    plan = h.digest(h.snapshot.s.regular(raw/'original-plan.gsbp',h.snapshot.MIB))
    return dict(raw=raw, plan=plan, inventory=inventory, receiptSha256=h.digest((path/'receipt.json').read_bytes()))


def negative_cases(case):
    run.selected(case)
    if case == 'alternating-slots': return dict(run.cycles.NEGATIVES)
    need(not (set(run.cancellation.NEGATIVES)&set(retention.NEGATIVES)), 'learner cohort negative catalogue collision')
    return dict(run.cancellation.NEGATIVES, **retention.NEGATIVES)


def check_result(value, case):
    run.selected(case); need(type(value) is dict and set(value) == {'original','negatives'}, 'learner cohort replay envelope')
    original = value['original']
    need(type(original) is dict and original.get('status') == 'PASS' and
         all(original.get(k) is True for k in ('physicalQualification','forceOrderQualified')) and
         all(original.get(k) is False for k in ('processDeathQualified','phase3Complete')), 'learner cohort complete original result')
    if case == 'alternating-slots':
        need(set(original) == {'status','scope','revisions','snapshots','exchanges','physicalQualification','learnerAcquisitionQualified',
                              'selectedHeadQualified','forceOrderQualified','fullNetworkQualification','processDeathQualified','phase3Complete'} and
             original.get('scope') == 'native-six-revision-learner-history' and original.get('fullNetworkQualification') is False and
             all(original.get(k) is True for k in ('learnerAcquisitionQualified','selectedHeadQualified')) and
             type(original.get('revisions')) is int and original['revisions'] == 6 and
             type(original.get('snapshots')) is int and original['snapshots'] == 25 and
             type(original.get('exchanges')) is int and original['exchanges'] > 0, 'learner cohort complete six revisions')
    else:
        need(set(original) == {'status','scope','acquisition','progress','physicalQualification','forceOrderQualified',
                              'coldReopenQualified','processDeathQualified','autonomous','phase3Complete','learnerRetention'} and
             original.get('scope') == 'native-learner-cancellation' and original.get('coldReopenQualified') is True and
             original.get('autonomous') is False and type(original.get('learnerRetention')) is dict and
             original['learnerRetention'], 'learner cohort retained cancellation')
        retained = original['learnerRetention']
        need(set(retained) == {'quorums','forcedUpdates','sourceExposures','wireACKs','failedAttempts'} and
             all(type(v) is int for v in retained.values()) and
             (retained['quorums'],retained['forcedUpdates'],retained['sourceExposures']) == (2,4,2) and
             2 <= retained['wireACKs'] <= 6 and 0 <= retained['failedAttempts'] <= 6, 'learner cohort original retention rounds')
        for field in ('acquisition','progress'):
            trace = original[field]
            need(type(trace) is dict and set(trace) == {'exchanges','originalFiles','peer'} and trace['peer'] == 'node-1' and
                 all(type(trace[k]) is int and trace[k] > 0 for k in ('exchanges','originalFiles')), 'learner cohort retained source transcripts')
    need(value['negatives'] == [dict(case=k,status='REJECTED',reason=v) for k,v in negative_cases(case).items()],
         'learner cohort exact negative vector')


def qualify_member(path, case, source, build, toolchain, reader):
    before = member(path,case,source,build,toolchain,reader)
    # Both drivers validate the unmodified original before the first mutation.
    result = (run.cycles.qualify(before['raw']) if case == 'alternating-slots'
              else run.cancellation.qualify(before['raw'],retained_learners=True))
    check_result(result,case)
    need(member(path,case,source,build,toolchain,reader) == before, 'learner cohort producer changed during replay')
    check_pins(source,build,toolchain,reader)
    return dict(case=case, status='PASS', producerReceiptSha256=before['receiptSha256'], originalPlanSha256=before['plan'],
                qualification=result, sourceSha256=source, buildSha256=build, toolchainSha256=toolchain, readerSha256=reader, phase3Complete=False)


def validate(paths, source, build, toolchain, reader, *, workers=1, progress=None):
    need(type(workers) is int and 1 <= workers <= 2, 'learner cohort replay workers')
    check_pins(source,build,toolchain,reader)
    need(type(paths) is dict and set(paths) == set(KINDS), 'learner cohort complete pair')
    need(len({Path(v).resolve() for v in paths.values()}) == len(KINDS), 'learner cohort distinct producer directories')
    originals = {case:member(paths[case],case,source,build,toolchain,reader) for case in KINDS}
    need(len({v['plan'] for v in originals.values()}) == len(KINDS), 'learner cohort distinct original histories')
    outcomes = {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks = {pool.submit(qualify_member,paths[case],case,source,build,toolchain,reader):case for case in KINDS}
        pending = set(tasks)
        while pending:
            done,pending = wait(pending,timeout=60,return_when=FIRST_COMPLETED)
            for task in done:
                case = tasks[task]
                try: value = task.result()
                except Exception as error: value = dict(case=case,status='FAIL',failure=dict(type=type(error).__name__,message=str(error)))
                outcomes[case] = value
                if progress: progress(dict(stage='member-terminal',completed=len(outcomes),total=len(KINDS),**value))
            if not done and progress: progress(dict(stage='learner-replay',completed=len(outcomes),total=len(KINDS)))
    for case in KINDS:
        need(member(paths[case],case,source,build,toolchain,reader) == originals[case], 'learner cohort original changed before completion')
    check_pins(source,build,toolchain,reader)
    passed = all(outcomes[k]['status'] == 'PASS' for k in KINDS)
    return dict(schema=SCHEMA,status='PASS' if passed else 'FAIL',scope='two-whole-native-3-add-learner-histories',
                sourceSha256=source,buildSha256=build,toolchainSha256=toolchain,readerSha256=reader,
                cases=[outcomes[k] for k in KINDS],wholeHistories=2,
                negativeCases=sum(len(v.get('qualification',{}).get('negatives',[])) for v in outcomes.values()),
                declaredLearnerHistoryPairQualified=passed,allMembershipProfilesQualified=False,processDeathQualified=False,
                fullNetworkQualification=False,combinedPeakResourcesQualified=False,phase3Complete=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command',required=True)
    sub.add_parser('plan')
    for mode in ('member','aggregate'):
        cmd = sub.add_parser(mode); cmd.add_argument('output')
        if mode == 'member': cmd.add_argument('--producer',required=True); cmd.add_argument('--case',required=True,choices=KINDS)
        else: cmd.add_argument('--inputs',required=True); cmd.add_argument('--workers',type=int,default=1)
        for pin in ('source','build','toolchain','reader'): cmd.add_argument('--'+pin+'-sha256',required=True)
    args = parser.parse_args()
    if args.command == 'plan':
        print(json.dumps(dict(cases=[dict(case=k,negativeCases=len(negative_cases(k)),command=run.command(k)) for k in KINDS],
                              reader=reader_manifest(),phase3Complete=False),sort_keys=True)); return
    output = Path(args.output); output.mkdir(parents=True,exist_ok=False)
    receipt = dict(schema=SCHEMA,status='RUNNING',phase3Complete=False)
    try:
        pins = [getattr(args,k+'_sha256') for k in ('source','build','toolchain','reader')]
        from .remove_process_hosted import progress as heartbeat
        with heartbeat('learner-'+args.command,getattr(args,'case',None)), (output/'progress.jsonl').open('x') as stream:
            def progress(value):
                stream.write(json.dumps(value,sort_keys=True)+'\n'); stream.flush()
                print(json.dumps({k:v for k,v in value.items() if k != 'qualification'},sort_keys=True),file=sys.stderr,flush=True)
            if args.command == 'member': receipt = qualify_member(args.producer,args.case,*pins)
            else:
                inputs = Path(args.inputs)
                need(inputs.is_dir() and not inputs.is_symlink() and {p.name for p in inputs.iterdir()} == set(KINDS),
                     'learner cohort exact input directories')
                receipt = validate({case:inputs/case for case in KINDS},*pins,workers=args.workers,progress=progress)
        need(receipt['status'] == 'PASS','learner cohort failed originals')
    except BaseException as error:
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error))); raise
    finally: h.save(output/'receipt.json',receipt)
    print(json.dumps(dict(status=receipt['status'],receipt=str(output/'receipt.json'),phase3Complete=False),sort_keys=True))


if __name__ == '__main__': main()
