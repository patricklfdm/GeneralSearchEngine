"""Final-source joining reply-loss cohort through the current ballot composition.

Historical peer-only qualification remains available in joining_fault_matrix.
This entry requires the actual current reader in the producer source and replays
all three whole histories, original-first, without executing or retrying JVMs.
"""
import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from . import joining_fault_matrix as legacy
from . import profile_matrix as profile

h=legacy.h;need=h.need;gate=legacy.gate
KINDS=legacy.KINDS
SCHEMA='gse-v53-joining-fault-cohort-v1'
reader_manifest=profile.reader_manifest
slug=str.lower


def check_pins(source,build,toolchain,reader):
    need(all(legacy.hash_field(v) for v in (source,build,toolchain,reader)),'joining cohort pinned hashes')
    manifest=reader_manifest();need(manifest['sha256']==reader,'joining cohort pinned reader');return manifest


def member(path,kind,source,build,toolchain,reader):
    need(kind in KINDS,'joining cohort declared reply');manifest=check_pins(source,build,toolchain,reader)
    path=Path(path);need(path.is_dir() and not path.is_symlink(),'joining cohort producer directory')
    result=legacy.member(path,kind,source,build);receipt=legacy.read(path/'receipt.json');recorded,_=h.read_recorded_source(path)
    need(all(recorded['files'].get(k)==v for k,v in manifest['files'].items()),'joining cohort readers belong to producer source')
    need(legacy.read(path/'execution.json')==receipt['execution'],'joining cohort original execution receipt')
    reports=path/'workspace'/h.MODULE/'target/surefire-reports'
    for report in reports.glob('TEST-*.xml'):
        suite=ET.fromstring(h.snapshot.s.regular(report,8*h.snapshot.MIB))
        need(not any(v.tag.startswith(('flaky','rerun')) for v in suite.iter()),'joining cohort unretried JUnit')
    need(profile.shared.process_toolchain.pin((path/'toolchain.json').read_bytes())==toolchain,'joining cohort exact toolchain')
    need(legacy.read(path/'collection.json')==h.collection(result['raw']),'joining cohort independently recollected original')
    return dict(result,observedToolchain=result['toolchain'],toolchain=toolchain)


def check_result(result,kind):
    original=result.get('original',{})
    need(original.get('status')=='PASS' and original.get('sourceFault')==kind and original.get('joiningSourceFaultQualified') is True and
         original.get('fullImplementedCompositionQualified') is True and
         all(type(original.get(k)) is int and original[k]==1 for k in ('lostReplies','recoveredLostReplies')) and
         original.get('phase3Complete') is False and original.get('processDeathQualified') is False and result.get('originalPreserved') is True,
         'joining cohort complete original fault composition')
    need(result.get('negatives')==[dict(case=k,status='REJECTED',reason=v) for k,v in gate.NEGATIVES.items()],
         'joining cohort exact fault negatives')
    ballot=result.get('ballotQualification',{});profile.check_result(ballot,'3-ADD')
    need(ballot['original']==original.get('ballotPrecondition'),'joining cohort same original ballot result')


def qualify_member(path,kind,source,build,toolchain,reader):
    before=member(path,kind,source,build,toolchain,reader)
    result=gate.qualify(before['raw'],full_chain=True);check_result(result,kind)
    need(member(path,kind,source,build,toolchain,reader)==before,'joining cohort producer changed during replay')
    return dict(case=kind,status='PASS',qualification=result,producerReceiptSha256=before['receiptSha256'],originalPlanSha256=before['plan'],
                sourceSha256=source,buildSha256=build,toolchainSha256=toolchain,readerSha256=reader,phase3Complete=False)


def validate(paths,source,build,toolchain,reader,*,workers=1,progress=None):
    from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
    need(type(workers) is int and 1<=workers<=3,'joining cohort replay workers');check_pins(source,build,toolchain,reader)
    need(type(paths) is dict and set(paths)==set(KINDS),'joining cohort complete reply set')
    need(len({Path(v).resolve() for v in paths.values()})==3,'joining cohort distinct producers')
    originals={k:member(paths[k],k,source,build,toolchain,reader) for k in KINDS}
    need(len({v['plan'] for v in originals.values()})==3,'joining cohort distinct original histories')
    outcomes={}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks={pool.submit(qualify_member,paths[k],k,source,build,toolchain,reader):k for k in KINDS};pending=set(tasks)
        while pending:
            done,pending=wait(pending,timeout=60,return_when=FIRST_COMPLETED)
            for task in done:
                kind=tasks[task]
                try:outcomes[kind]=task.result()
                except Exception as error:outcomes[kind]=dict(case=kind,status='FAIL',failure=dict(type=type(error).__name__,message=str(error)))
                if progress:progress(dict(stage='member-terminal',completed=len(outcomes),total=3,**outcomes[kind]))
            if not done and progress:progress(dict(stage='independent-replay',completed=len(outcomes),total=3))
    for kind in KINDS:need(member(paths[kind],kind,source,build,toolchain,reader)==originals[kind],'joining cohort producer changed before completion')
    check_pins(source,build,toolchain,reader);passed=all(v['status']=='PASS' for v in outcomes.values())
    fault_negatives=[n for v in outcomes.values() for n in v.get('qualification',{}).get('negatives',[])]
    ballot_negatives=[n for v in outcomes.values() for n in v.get('qualification',{}).get('ballotQualification',{}).get('negatives',[])]
    return dict(schema=SCHEMA,status='PASS' if passed else 'FAIL',scope='three-original-3-ADD-reply-loss-histories-through-current-ballot-composition',
                sourceSha256=source,buildSha256=build,toolchainSha256=toolchain,readerSha256=reader,cases=[outcomes[k] for k in KINDS],
                wholeHistories=3,faultNegativeCases=len(fault_negatives),ballotNegativeCases=len(ballot_negatives),
                notApplicable=sum(v['status']=='NOT_APPLICABLE' for v in ballot_negatives),joiningSourceFaultCompositionQualified=passed,
                allMembershipProfilesQualified=False,processDeathQualified=False,originalObservationCoverageComplete=False,phase3Complete=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True);sub.add_parser('plan')
    for name in ('member','aggregate'):
        cmd=sub.add_parser(name);cmd.add_argument('output')
        if name=='member':cmd.add_argument('--producer',required=True);cmd.add_argument('--case',required=True,choices=KINDS)
        else:cmd.add_argument('--inputs',required=True);cmd.add_argument('--workers',type=int,default=1)
        for pin in ('source','build','toolchain','reader'):cmd.add_argument('--'+pin+'-sha256',required=True)
    args=parser.parse_args()
    if args.command=='plan':
        print(json.dumps(dict(cases=[dict(case=k,id=slug(k)) for k in KINDS],reader=reader_manifest(),phase3Complete=False),sort_keys=True));return
    output=Path(args.output);output.mkdir(parents=True,exist_ok=False);receipt=dict(schema=SCHEMA,status='RUNNING',phase3Complete=False)
    try:
        pins=[getattr(args,p+'_sha256') for p in ('source','build','toolchain','reader')]
        if args.command=='member':receipt=qualify_member(args.producer,args.case,*pins)
        else:
            inputs=Path(args.inputs);need(inputs.is_dir() and not inputs.is_symlink() and {v.name for v in inputs.iterdir()}=={slug(k) for k in KINDS},
                                         'joining cohort exact input directories')
            with (output/'progress.jsonl').open('x') as stream:
                def progress(row):
                    stream.write(json.dumps(row,sort_keys=True)+'\n');stream.flush()
                    print(json.dumps({k:v for k,v in row.items() if k!='qualification'},sort_keys=True),file=sys.stderr,flush=True)
                receipt=validate({k:inputs/slug(k) for k in KINDS},*pins,workers=args.workers,progress=progress)
        need(receipt['status']=='PASS','joining cohort failed member')
    except BaseException as error:receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    print(json.dumps(dict(status='PASS',receipt=str(output/'receipt.json'),phase3Complete=False),sort_keys=True))


if __name__=='__main__':main()
