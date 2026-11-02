"""Exact-source 52-member REMOVE process qualification and bounded aggregation.

Whole histories are indivisible. Original sources, classes, JUnit, collection and
all composed readers are rechecked; a member receipt never substitutes for replay.
"""
import argparse
import json
from pathlib import Path
import re
import sys

from . import joining_history_run as h
from . import remove_process_ballot as gate
from . import remove_process_run as run

KINDS=run.CASES
BUILDS=('target/classes',h.MODULE+'/target/classes',h.MODULE+'/target/test-classes')
need=h.need


def read(path):
    def unique(rows):
        need(len(rows)==len(dict(rows)),'REMOVE process matrix duplicate metadata key');return dict(rows)
    return json.loads(h.snapshot.s.regular(path,8*h.snapshot.MIB),object_pairs_hook=unique)


def hash_field(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def member(path,kind,source_sha256,build_sha256,toolchain_sha256):
    run.selected(kind)
    path=Path(path);need(path.is_dir() and not path.is_symlink(),'REMOVE process matrix producer directory');receipt=read(path/'receipt.json')
    need(type(receipt) is dict and receipt.get('schema')=='gse-v53-remove-process-execution-v1' and receipt.get('status')=='PARTIAL' and
         receipt.get('executionStatus')=='PASS' and receipt.get('case')==kind and
         receipt.get('collectionComplete') is True and receipt.get('physicalHistoryQualified') is False and receipt.get('processDeathQualified') is False and
         receipt.get('phase3Complete') is False and type(receipt.get('retries')) is int and receipt['retries']==0,
         'REMOVE process matrix successful whole member: '+kind)
    need(all(type(receipt.get(k)) is dict and type(receipt[k].get('exit')) is int and receipt[k]['exit']==0 for k in ('execution',)),
         'REMOVE process matrix successful processes: '+kind)
    need(read(path/'execution.json')==receipt['execution'],'REMOVE process matrix execution receipt: '+kind)
    source,_=h.read_recorded_source(path)
    need(receipt.get('sourceSha256')==source_sha256==h.digest((path/'source.json').read_bytes()) and
         receipt.get('baseHead')==source['head'],'REMOVE process matrix exact producer source: '+kind)
    command=receipt.get('command');wanted=['-o','-B','-ntp','-f','reactor/pom.xml','-pl','../'+h.MODULE,'-am',
        '-Dsurefire.failIfNoSpecifiedTests=false','-Dtest='+run.CLASS.rsplit('.',1)[-1]+'#'+run.METHOD,'-Dv53.remove.retirement.process='+kind,'test']
    need(type(command) is list and len(command)==len(wanted)+1 and type(command[0]) is str and
         Path(command[0]).name=='mvn' and command[1:]==wanted,'REMOVE process matrix exact whole command: '+kind)
    work=path/'workspace'
    for name in (*BUILDS,h.MODULE+'/target/surefire-reports'):
        relative=Path(name)
        need(all((work/p).is_dir() and not (work/p).is_symlink() for p in (relative,*relative.parents)),
             'REMOVE process matrix linked generated parent: '+kind)
    reports=work/h.MODULE/'target/surefire-reports'
    for report in reports.glob('TEST-*.xml'):h.snapshot.s.regular(report,8*h.snapshot.MIB)
    junit=run.junit(reports)
    need(receipt.get('junit')==junit,'REMOVE process matrix exact JUnit receipt: '+kind)
    build=read(path/'build.json')
    need(type(build) is dict and set(build)==set(BUILDS) and receipt.get('buildSha256')==build_sha256==h.digest((path/'build.json').read_bytes()),
         'REMOVE process matrix exact build manifest: '+kind)
    for name in BUILDS:need(h.inventory(work/name)==build[name],'REMOVE process matrix original built bytes: '+kind)
    toolchain=read(path/'toolchain.json');toolchain_hash=h.digest((path/'toolchain.json').read_bytes())
    need(type(toolchain) is dict and type(toolchain.get('exit')) is int and toolchain['exit']==0 and
         receipt.get('toolchainSha256')==toolchain_hash==toolchain_sha256,'REMOVE process matrix toolchain receipt: '+kind)
    name=receipt.get('raw')
    need(type(name) is str and re.fullmatch('workspace/'+h.MODULE+r'/target/v53-remove-retirement-process/run-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',name),
         'REMOVE process matrix original history path: '+kind)
    raw=path/name
    need(all((path/parent).is_dir() and not (path/parent).is_symlink() for parent in Path(name).parents),
         'REMOVE process matrix linked history parent: '+kind)
    need({v.name for v in raw.parent.iterdir()}=={raw.name},'REMOVE process matrix exact original history directory: '+kind)
    collection=read(path/'collection.json');inventory=h.inventory(raw)
    need(type(collection) is dict and receipt.get('collectionSha256')==h.digest((path/'collection.json').read_bytes()) and
         collection.get('status')=='PARTIAL' and collection.get('collectionComplete') is True and
         all(collection.get(k) is False for k in ('physicalHistoryQualified','processDeathQualified','phase3Complete')) and
         collection.get('inventory')==inventory,'REMOVE process matrix original collection: '+kind)
    # Original plan includes original execution paths. Its physical validity is
    # checked downstream; distinct copies of one history cannot fill the matrix.
    need(collection==run.collect(raw,kind),'REMOVE process matrix independently recollected member: '+kind)
    need(gate.p.profile_at(raw)==run.selected(kind),'REMOVE process matrix current capture schema: '+kind)
    plan_hash=h.digest(h.snapshot.s.regular(raw/'history/original-plan.gsbp',h.snapshot.MIB))
    return dict(raw=raw,toolchain=toolchain_hash,plan=plan_hash,inventory=inventory,
                receiptSha256=h.digest((path/'receipt.json').read_bytes()))



def reader_manifest():
    names=sorted((h.ROOT/'scripts/v53').glob('*.py'))+[h.ROOT/'scripts/v43/derived_format_v12.py',h.ROOT/'docs/v5x/v5.3/format-catalog.json']
    files={str(p.relative_to(h.ROOT)):h.digest(h.snapshot.s.regular(p,8*h.snapshot.MIB)) for p in names}
    return dict(files=files,sha256=h.digest(gate.f.canonical(files)))


def slug(case):return case.lower().replace(',','__')


def check_pins(source,build,toolchain,reader):
    need(all(hash_field(v) for v in (source,build,toolchain,reader)),'REMOVE process matrix pinned hashes')
    need(reader_manifest()['sha256']==reader,'REMOVE process matrix pinned reader')


def check_result(result,case):
    original=result.get('original',{})
    need(original.get('status')=='PARTIAL' and original.get('ballotForceCompositionQualified') is True and
         original.get('phase3Complete') is False and
         original.get('precondition',{}).get('retirementRetentionCompositionQualified') is True,
         'REMOVE process matrix composed original result: '+case)
    expected=sorted((dict(case=name,status='REJECTED',reason=reason,retirementReplay='PASS',
                         physicalWireAndOtherObservationsUnchanged=True) for name,reason in gate.NEGATIVES.items()),key=lambda v:v['case'])
    need(result.get('negatives')==expected and result.get('mutatedFullPrerequisiteReplayed') is False,
         'REMOVE process matrix exact negative results: '+case)


def qualify_member(path,case,source,build,toolchain,reader):
    check_pins(source,build,toolchain,reader)
    original=member(path,case,source,build,toolchain)
    result=gate.qualify(original['raw'],workers=1);check_result(result,case)
    need(member(path,case,source,build,toolchain)==original,'REMOVE process matrix producer changed during replay: '+case)
    check_pins(source,build,toolchain,reader)
    return dict(case=case,status='PASS',producerReceiptSha256=original['receiptSha256'],originalPlanSha256=original['plan'],
                qualification=result,sourceSha256=source,buildSha256=build,toolchainSha256=toolchain,readerSha256=reader,
                phase3Complete=False)


def validate(paths,source,build,toolchain,reader,*,workers=1,progress=None):
    from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
    need(type(workers) is int and 1<=workers<=4,'REMOVE process matrix replay workers')
    check_pins(source,build,toolchain,reader)
    need(type(paths) is dict and set(paths)==set(KINDS),'REMOVE process matrix complete declared set')
    need(len({Path(v).resolve() for v in paths.values()})==len(KINDS),'REMOVE process matrix distinct producer directories')
    originals={case:member(paths[case],case,source,build,toolchain) for case in KINDS}
    need(len({v['plan'] for v in originals.values()})==len(KINDS),'REMOVE process matrix distinct original histories')
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
        need(member(paths[case],case,source,build,toolchain)==originals[case],
             'REMOVE process matrix producer changed before completion: '+case)
    check_pins(source,build,toolchain,reader)
    passed=all(outcomes[case]['status']=='PASS' for case in KINDS)
    return dict(schema='gse-v53-remove-process-matrix-v1',status='PASS' if passed else 'FAIL',
                scope='52-original-REMOVE-process-histories-through-ballot-retirement-composition',
                sourceSha256=source,buildSha256=build,toolchainSha256=toolchain,readerSha256=reader,
                cases=[outcomes[case] for case in KINDS],wholeHistories=len(KINDS),
                negativeCases=sum(len(v.get('qualification',{}).get('negatives',[])) for v in outcomes.values()),
                declaredRemoveProcessMatrixQualified=passed,allMembershipProfilesQualified=False,
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
    receipt=dict(status='RUNNING',phase3Complete=False)
    try:
        pins=[getattr(args,p+'_sha256') for p in ('source','build','toolchain','reader')]
        if args.command=='member':receipt=qualify_member(args.producer,args.case,*pins)
        else:
            inputs=Path(args.inputs);need(inputs.is_dir() and not inputs.is_symlink(),'REMOVE process matrix input directory')
            need({v.name for v in inputs.iterdir()}=={slug(case) for case in KINDS},'REMOVE process matrix exact input directory set')
            with (output/'progress.jsonl').open('x') as stream:
                def progress(row):
                    stream.write(json.dumps(row,sort_keys=True)+'\n');stream.flush()
                    print(json.dumps({k:v for k,v in row.items() if k!='qualification'},sort_keys=True),file=sys.stderr,flush=True)
                receipt=validate({case:inputs/slug(case) for case in KINDS},*pins,workers=args.workers,progress=progress)
        need(receipt['status']=='PASS','REMOVE process matrix failed members')
    except BaseException as error:
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    print(json.dumps(dict(status='PASS',receipt=str(output/'receipt.json'),phase3Complete=False),sort_keys=True))


if __name__=='__main__':main()
