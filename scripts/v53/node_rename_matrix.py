"""Exact-source four-member node rename qualification and bounded aggregation.

Whole histories are indivisible. Original sources, classes, JUnit, collection and
all composed readers are rechecked; a member receipt never substitutes for replay.
"""
import argparse
import json
from pathlib import Path
import re
import sys

from . import joining_history_run as h
from . import node_current_evidence as gate
from . import remove_process_matrix as shared
from . import node_rename_run as run
from . import process_toolchain

KINDS=run.CASES
BUILDS=('target/classes',h.MODULE+'/target/classes',h.MODULE+'/target/test-classes')
need=h.need
SCHEMA='gse-v53-node-rename-matrix-v1'


read=shared.read
hash_field=shared.hash_field


def member(path,kind,source_sha256,build_sha256,toolchain_sha256,reader_sha256):
    manifest=check_pins(source_sha256,build_sha256,toolchain_sha256,reader_sha256)
    run.selected(kind)
    path=Path(path);need(path.is_dir() and not path.is_symlink(),'node rename matrix producer directory');receipt=read(path/'receipt.json')
    need(type(receipt) is dict and receipt.get('schema')==run.SCHEMA and receipt.get('status')=='PARTIAL' and
         receipt.get('executionStatus')=='PASS' and receipt.get('case')==kind and
         receipt.get('collectionComplete') is True and receipt.get('physicalHistoryQualified') is False and receipt.get('processDeathQualified') is False and
         receipt.get('phase3Complete') is False and type(receipt.get('retries')) is int and receipt['retries']==0,
         'node rename matrix successful whole member: '+kind)
    need(all(type(receipt.get(k)) is dict and type(receipt[k].get('exit')) is int and receipt[k]['exit']==0 for k in ('execution',)),
         'node rename matrix successful processes: '+kind)
    need(read(path/'execution.json')==receipt['execution'],'node rename matrix execution receipt: '+kind)
    source,_=h.read_recorded_source(path)
    need(receipt.get('sourceSha256')==source_sha256==h.digest((path/'source.json').read_bytes()) and
         receipt.get('baseHead')==source['head'],'node rename matrix exact producer source: '+kind)
    need(all(source['files'].get(k)==v for k,v in manifest['files'].items()),'node rename matrix reader belongs to producer source')
    command=receipt.get('command');wanted=run.command(kind)
    need(type(command) is list and len(command)==len(wanted)+1 and type(command[0]) is str and
         Path(command[0]).name=='mvn' and command[1:]==wanted,'node rename matrix exact whole command: '+kind)
    work=path/'workspace'
    for name in (*BUILDS,h.MODULE+'/target/surefire-reports'):
        relative=Path(name)
        need(all((work/p).is_dir() and not (work/p).is_symlink() for p in (relative,*relative.parents)),
             'node rename matrix linked generated parent: '+kind)
    reports=work/h.MODULE/'target/surefire-reports'
    for report in reports.glob('TEST-*.xml'):h.snapshot.s.regular(report,8*h.snapshot.MIB)
    junit=run.junit(reports,kind)
    need(receipt.get('junit')==junit,'node rename matrix exact JUnit receipt: '+kind)
    build=read(path/'build.json')
    need(type(build) is dict and set(build)==set(BUILDS) and receipt.get('buildSha256')==build_sha256==h.digest((path/'build.json').read_bytes()),
         'node rename matrix exact build manifest: '+kind)
    for name in BUILDS:need(h.inventory(work/name)==build[name],'node rename matrix original built bytes: '+kind)
    toolchain=read(path/'toolchain.json');process_toolchain.validate(toolchain)
    toolchain_hash=h.digest((path/'toolchain.json').read_bytes())
    need(type(toolchain) is dict and type(toolchain.get('exit')) is int and toolchain['exit']==0 and
         receipt.get('toolchainSha256')==toolchain_hash and
         process_toolchain.pin((path/'toolchain.json').read_bytes())==toolchain_sha256,'node rename matrix toolchain receipt: '+kind)
    name=receipt.get('raw')
    need(type(name) is str and re.fullmatch('workspace/'+h.MODULE+r'/target/v53-node-process/run-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',name),
         'node rename matrix original history path: '+kind)
    raw=path/name
    need(all((path/parent).is_dir() and not (path/parent).is_symlink() for parent in Path(name).parents),
         'node rename matrix linked history parent: '+kind)
    need({v.name for v in raw.parent.iterdir()}=={raw.name},'node rename matrix exact original history directory: '+kind)
    collection=read(path/'collection.json');inventory=h.inventory(raw)
    need(type(collection) is dict and receipt.get('collectionSha256')==h.digest((path/'collection.json').read_bytes()) and
         collection.get('status')=='PARTIAL' and collection.get('collectionComplete') is True and
         all(collection.get(k) is False for k in ('physicalHistoryQualified','processDeathQualified','phase3Complete')) and
         collection.get('inventory')==inventory,'node rename matrix original collection: '+kind)
    # Original plan includes original execution paths. Its physical validity is
    # checked downstream; distinct copies of one history cannot fill the matrix.
    need(collection==run.collect(raw,kind),'node rename matrix independently recollected member: '+kind)
    plan_hash=h.digest(h.snapshot.s.regular(raw/'history/original-plan.gsbp',h.snapshot.MIB))
    return dict(raw=raw,toolchain=toolchain_sha256,observedToolchain=toolchain_hash,plan=plan_hash,inventory=inventory,
                receiptSha256=h.digest((path/'receipt.json').read_bytes()))



reader_manifest=shared.reader_manifest


def slug(case):return case.lower().replace(',','__')


def check_pins(source,build,toolchain,reader):
    need(all(hash_field(v) for v in (source,build,toolchain,reader)),'node rename matrix pinned hashes')
    manifest=reader_manifest();need(manifest['sha256']==reader,'node rename matrix pinned reader');return manifest


def check_result(result,case):
    expected=run.selected(case);original=result.get('original',{})
    need(original.get('status')=='PASS' and original.get('scope')=='current-node-rename-recovery' and
         all(original.get(k)==v for k,v in expected.items()) and
         all(original.get(k) is True for k in ('originalFirst','physicalReplay','processRestart','carriedOriginalEntry')) and
         all(original.get(k) is False for k in ('interruptedClientSuccess','powerLoss','publicRuntime','phase3Complete')) and
         all(type(original.get(k)) is int and original[k]==v for k,v in dict(campaigns=3,publishedSlots=5,freshLeaderJvms=2).items()),
         'node rename matrix complete original result: '+case)
    from . import node_late_prepare as late
    cases=gate.p.negative_cases(expected['cut'])|gate.EXTRA_NEGATIVES
    if original['network'].get('lateUnusedPrepares'):cases.update(late.NEGATIVES)
    need(result.get('negatives')==[dict(case=k,status='REJECTED',reason=v) for k,v in cases.items()],
         'node rename matrix exact negative results: '+case)


def qualify_member(path,case,source,build,toolchain,reader):
    check_pins(source,build,toolchain,reader)
    original=member(path,case,source,build,toolchain,reader)
    result=gate.qualify(original['raw']);check_result(result,case)
    need(member(path,case,source,build,toolchain,reader)==original,'node rename matrix producer changed during replay: '+case)
    check_pins(source,build,toolchain,reader)
    return dict(case=case,status='PASS',producerReceiptSha256=original['receiptSha256'],originalPlanSha256=original['plan'],
                qualification=result,sourceSha256=source,buildSha256=build,toolchainSha256=toolchain,readerSha256=reader,
                phase3Complete=False)


def validate(paths,source,build,toolchain,reader,*,workers=1,progress=None):
    from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
    need(type(workers) is int and 1<=workers<=4,'node rename matrix replay workers')
    check_pins(source,build,toolchain,reader)
    need(type(paths) is dict and set(paths)==set(KINDS),'node rename matrix complete declared set')
    need(len({Path(v).resolve() for v in paths.values()})==len(KINDS),'node rename matrix distinct producer directories')
    originals={case:member(paths[case],case,source,build,toolchain,reader) for case in KINDS}
    need(len({v['plan'] for v in originals.values()})==len(KINDS),'node rename matrix distinct original histories')
    outcomes={}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks={pool.submit(qualify_member,paths[case],case,source,build,toolchain,reader):case for case in KINDS}
        pending=set(tasks)
        while pending:
            done,pending=wait(pending,timeout=60,return_when=FIRST_COMPLETED)
            for task in done:
                case=tasks[task]
                try:result=task.result()
                except Exception as error:result=dict(case=case,status='FAIL',failure=dict(type=type(error).__name__,message=str(error)))
                outcomes[case]=result
                if progress:progress(dict(stage='member-terminal',completed=len(outcomes),total=len(KINDS),**result))
            if not done and progress:progress(dict(stage='independent-replay',completed=len(outcomes),total=len(KINDS)))
    # A later member must not alter a producer already checked by another worker.
    for case in KINDS:
        need(member(paths[case],case,source,build,toolchain,reader)==originals[case],
             'node rename matrix producer changed before completion: '+case)
    check_pins(source,build,toolchain,reader)
    passed=all(outcomes[case]['status']=='PASS' for case in KINDS)
    return dict(schema=SCHEMA,status='PASS' if passed else 'FAIL',
                scope='four-original-node-rename-histories-through-current-physical-network-replay',
                sourceSha256=source,buildSha256=build,toolchainSha256=toolchain,readerSha256=reader,
                cases=[outcomes[case] for case in KINDS],wholeHistories=len(KINDS),
                negativeCases=sum(len(v.get('qualification',{}).get('negatives',[])) for v in outcomes.values()),
                declaredNodeRenameMatrixQualified=passed,allMembershipProfilesQualified=False,
                originalObservationCoverageComplete=False,phase3Complete=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('plan')
    for name in ('member','aggregate'):
        cmd=sub.add_parser(name);cmd.add_argument('output')
        if name=='member':cmd.add_argument('--producer',required=True);cmd.add_argument('--case',required=True,choices=KINDS)
        else:cmd.add_argument('--inputs',required=True);cmd.add_argument('--workers',type=int,default=1)
        for pin in ('source','build','toolchain','reader'):cmd.add_argument('--'+pin+'-sha256',required=True)
    args=parser.parse_args()
    if args.command=='plan':
        print(json.dumps(dict(cases=[dict(case=v,id=slug(v)) for v in KINDS],reader=reader_manifest(),phase3Complete=False),sort_keys=True));return
    output=Path(args.output);output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,status='RUNNING',phase3Complete=False)
    try:
        pins=[getattr(args,p+'_sha256') for p in ('source','build','toolchain','reader')]
        if args.command=='member':receipt=qualify_member(args.producer,args.case,*pins)
        else:
            inputs=Path(args.inputs);need(inputs.is_dir() and not inputs.is_symlink(),'node rename matrix input directory')
            need({v.name for v in inputs.iterdir()}=={slug(case) for case in KINDS},'node rename matrix exact input directory set')
            with (output/'progress.jsonl').open('x') as stream:
                def progress(row):
                    stream.write(json.dumps(row,sort_keys=True)+'\n');stream.flush()
                    print(json.dumps({k:v for k,v in row.items() if k!='qualification'},sort_keys=True),file=sys.stderr,flush=True)
                receipt=validate({case:inputs/slug(case) for case in KINDS},*pins,workers=args.workers,progress=progress)
        need(receipt['status']=='PASS','node rename matrix failed members')
    except BaseException as error:
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    print(json.dumps(dict(status='PASS',receipt=str(output/'receipt.json'),phase3Complete=False),sort_keys=True))


if __name__=='__main__':main()
