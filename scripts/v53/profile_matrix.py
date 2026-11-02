"""Replay seven indivisible ordinary membership histories from one source/build.

This gate does not execute JVMs or retry measurements. Producer success is only
provenance: every original is independently replayed before its negative cases.
Process/fault cohorts, complete observation coverage and Phase 3 remain separate.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

from . import remove_process_matrix as shared
from . import joining_profile_run as joining_run
from . import remove_profile_run as remove_run
from . import joining_profile_ballot_evidence as joining
from . import remove_ballot_evidence as removal

h=shared.h
need=h.need
PROFILES=('3-ADD','4-ADD','4-REMOVE','5-REMOVE','3-REPLACE','4-REPLACE','5-REPLACE')
SCHEMA='gse-v53-membership-profile-matrix-v1'
BUILDS=shared.BUILDS
read=shared.read
slug=str.lower


def reader_manifest():
    files=dict(shared.reader_manifest()['files'])
    name='docs/v5x/v5.3/acceptance-plan.json'
    files[name]=h.digest(h.snapshot.s.regular(h.ROOT/name,8*h.snapshot.MIB))
    return dict(files=files,sha256=h.digest(joining.ballot.f.canonical(files)))


def catalogue():
    plan=read(h.ROOT/'docs/v5x/v5.3/acceptance-plan.json')
    need(tuple(str(v['initial'])+'-'+v['kind'] for v in plan['profiles'])==PROFILES,'profile matrix frozen catalogue')
    need(set(PROFILES)==set(joining.PROFILES)|set(removal.PROFILES),'profile matrix reader catalogue')
    return PROFILES


def check_pins(source,build,toolchain,reader):
    need(all(shared.hash_field(v) for v in (source,build,toolchain,reader)),'profile matrix pinned hashes')
    manifest=reader_manifest()
    need(manifest['sha256']==reader,'profile matrix pinned reader');catalogue()
    return manifest


def command(profile):
    remove=profile in removal.PROFILES
    cls=remove_run.CLASS if remove else h.CLASS
    method=remove_run.METHOD if remove else joining_run.COMPLETE_METHOD
    args=['-o','-B','-ntp','-f','reactor/pom.xml','-pl','../'+h.MODULE,'-am',
          '-Dsurefire.failIfNoSpecifiedTests=false','-Dtest='+cls.rsplit('.',1)[-1]+'#'+method,
          '-Dv53.'+('remove' if remove else 'joining')+'.profile='+profile]
    if remove:args.append('-Dv53.remove.retirement.captures=true')
    return args+['test']


def successful_process(value):return type(value) is dict and type(value.get('exit')) is int and value['exit']==0


def member(path,profile,source,build,toolchain,reader):
    manifest=check_pins(source,build,toolchain,reader)
    need(profile in PROFILES,'profile matrix declared member');remove=profile in removal.PROFILES
    path=Path(path);need(path.is_dir() and not path.is_symlink(),'profile matrix producer directory')
    receipt=read(path/'receipt.json')
    need(type(receipt) is dict and receipt.get('schema')==(remove_run.SCHEMA if remove else 'gse-v53-joining-profile-completion-v1') and
         receipt.get('status')=='PARTIAL' and receipt.get('executionStatus')=='PASS' and receipt.get('profile')==profile and
         type(receipt.get('retries')) is int and receipt['retries']==0 and receipt.get('phase3Complete') is False,
         'profile matrix successful whole member: '+profile)
    if remove:
        need(all(receipt.get(k) is True for k in ('retirementCapturesRequested','transientRetirementBytesQualified',
                  'continuousOriginalQualified','automaticOperationCompletion')) and
             all(receipt.get(k) is False for k in ('publicRuntimeQualified','completeNetworkQualified','processDeathQualified')),
             'profile matrix captured ordinary REMOVE: '+profile)
    else:
        need(all(receipt.get(k) is True for k in ('completeExecutionRequested','semanticChainQualified','semanticFinalAndColdQualified')) and
             all(receipt.get(k) is False for k in ('finalAndColdReopenQualified','forceAndNetworkQualified')) and
             'sameViewRecoveryRequested' not in receipt,'profile matrix ordinary complete joining: '+profile)
    need(all(successful_process(receipt.get(k)) for k in ('execution','replayExecution',*(['prefixExecution'] if remove else []))),
         'profile matrix successful processes: '+profile)
    need(read(path/'execution.json')==receipt['execution'],'profile matrix execution receipt: '+profile)
    recorded,_=h.read_recorded_source(path)
    need(receipt.get('sourceSha256')==source==h.digest((path/'source.json').read_bytes()) and
         receipt.get('baseHead')==recorded['head'],'profile matrix exact producer source: '+profile)
    need(all(recorded['files'].get(k)==v for k,v in manifest['files'].items()),
         'profile matrix readers belong to producer source: '+profile)
    args=receipt.get('command');wanted=command(profile)
    need(type(args) is list and len(args)==len(wanted)+1 and type(args[0]) is str and Path(args[0]).name=='mvn' and args[1:]==wanted,
         'profile matrix exact whole command: '+profile)
    work=path/'workspace'
    for name in (*BUILDS,h.MODULE+'/target/surefire-reports'):
        relative=Path(name)
        need(all((work/p).is_dir() and not (work/p).is_symlink() for p in (relative,*relative.parents)),
             'profile matrix linked generated parent: '+profile)
    reports=work/h.MODULE/'target/surefire-reports'
    for report in reports.glob('TEST-*.xml'):
        suite=ET.fromstring(h.snapshot.s.regular(report,8*h.snapshot.MIB))
        need(not any(v.tag.startswith(('flaky','rerun')) for v in suite.iter()),'profile matrix unretried JUnit: '+profile)
    junit=remove_run.junit(reports) if remove else joining_run.junit(reports,joining_run.COMPLETE_METHOD)
    need(receipt.get('junit')==junit,'profile matrix exact JUnit receipt: '+profile)
    builds=read(path/'build.json')
    need(type(builds) is dict and set(builds)==set(BUILDS) and receipt.get('buildSha256')==build==h.digest((path/'build.json').read_bytes()),
         'profile matrix exact build manifest: '+profile)
    for name in BUILDS:need(h.inventory(work/name)==builds[name],'profile matrix original built bytes: '+profile)
    tools=read(path/'toolchain.json');observed=h.digest((path/'toolchain.json').read_bytes())
    need(successful_process(tools) and receipt.get('toolchainSha256')==observed and
         shared.process_toolchain.pin((path/'toolchain.json').read_bytes())==toolchain,'profile matrix toolchain receipt: '+profile)
    name=receipt.get('raw')
    need(type(name) is str and re.fullmatch('workspace/'+h.MODULE+r'/target/v53-native-dispatch/run-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',name),
         'profile matrix original history path: '+profile)
    raw=path/name
    need(all((path/p).is_dir() and not (path/p).is_symlink() for p in Path(name).parents),'profile matrix linked history parent: '+profile)
    captures=raw.with_name('retirement-captures-'+raw.name) if remove else None
    need({v.name for v in raw.parent.iterdir()}=={raw.name,*([captures.name] if remove else [])},
         'profile matrix exact original history directory: '+profile)
    inventory=h.inventory(raw);captured=None
    need(read(path/'inventory.json')==inventory,'profile matrix original history inventory: '+profile)
    semantic=read(path/'replay.json');original=semantic.get('original',{})
    negatives=(remove_run.reader.negative_cases(profile) if remove else joining_run.complete_reader.NEGATIVES)
    need(receipt.get('replaySha256')==h.digest((path/'replay.json').read_bytes()) and original.get('status')=='PASS' and
         original.get('profile')==profile and original.get('phase3Complete') is False and
         semantic.get('negatives')==[dict(case=k,status='REJECTED',reason=v) for k,v in negatives.items()] and
         type(receipt.get('negativeCases')) is int and receipt['negativeCases']==len(negatives),
         'profile matrix retained semantic replay: '+profile)
    if remove:
        need(original.get('automaticOperationCompletion') is True and original.get('publicReady') is False,
             'profile matrix original REMOVE semantics: '+profile)
        need(receipt.get('captures')==captures.relative_to(path).as_posix(),'profile matrix same-history capture path: '+profile)
        copies,captured=removal.prior.collect(raw,captures,profile)
        prefix=read(path/'retirement-prefixes.json')
        need(captured==read(path/'capture-inventory.json') and prefix.get('status')=='PARTIAL' and prefix.get('profile')==profile and
             prefix.get('transientRetirementBytesQualified') is True and all(prefix.get(k) is False for k in ('phase3Complete','processDeathQualified')) and
             type(prefix.get('capturedPrefixes')) is int and prefix['capturedPrefixes']==receipt.get('capturedPrefixes')==len(copies) and
             receipt.get('prefixReplaySha256')==h.digest((path/'retirement-prefixes.json').read_bytes()),
             'profile matrix retained retirement replay: '+profile)
    else:
        need(original.get('semanticFinalAndColdQualified') is True and original.get('finalAndColdReopenQualified') is False,
             'profile matrix retained complete replay: '+profile)
    return dict(raw=raw,captures=captures,inventory=inventory,captureInventory=captured,observedToolchainSha256=observed,
                plan=h.digest(h.snapshot.s.regular(raw/'original-plan.gsbp',h.snapshot.MIB)),
                receiptSha256=h.digest((path/'receipt.json').read_bytes()))


def check_result(result,profile):
    original=result.get('original',{});prior=original.get('precondition',{})
    need(original.get('status')=='PARTIAL' and original.get('profile')==profile and
         all(original.get(k) is False for k in ('phase3Complete','processDeathQualified','allMembershipProfilesQualified','currentSourceNativeCohortQualified')),
         'profile matrix composed original scope: '+profile)
    if profile in removal.PROFILES:
        need(original.get('ballotForceCompositionQualified') is True and prior.get('transientRetirementBytesQualified') is True and
             result.get('mutatedFullPrerequisiteReplayed') is False,'profile matrix captured ballot composition: '+profile)
        expected=[dict(case=k,status='REJECTED',reason=v,retirementReplay='PASS',physicalWireAndOtherObservationsUnchanged=True)
                  for k,v in removal.NEGATIVES.items()]
    else:
        need(original.get('ballotCompositionQualified') is True and all(prior.get(k) is True for k in
             ('peerLedgerCompositionQualified','futureLedgerCompositionQualified','learnerLedgerCompositionQualified')) and
             type(original.get('adoptionFences')) is list and result.get('mutatedPrerequisiteReplayed') is False,
             'profile matrix joining ballot composition: '+profile)
        expected=[]
        for name,reason in joining.NEGATIVES.items():
            absent=None
            if name=='adoption-fence-missing' and not original['adoptionFences']:absent='no original adoption transaction'
            if name=='adoption-promise-missing' and not any(v['promiseAppended'] for v in original['adoptionFences']):absent='no original adoption promise append'
            expected.append(dict(case=name,status='NOT_APPLICABLE',reason=absent) if absent else
                            dict(case=name,status='REJECTED',reason=reason,mutationScope='allocator-promise-and-adoption-boundaries'))
    need(result.get('negatives')==sorted(expected,key=lambda v:v['case']),'profile matrix exact negative results: '+profile)


def qualify_member(path,profile,source,build,toolchain,reader):
    original=member(path,profile,source,build,toolchain,reader)
    if profile in removal.PROFILES:result=removal.qualify(original['raw'],original['captures'],profile,workers=1)
    else:result=joining.qualify(original['raw'],profile,workers=1)
    check_result(result,profile)
    need(member(path,profile,source,build,toolchain,reader)==original,'profile matrix producer changed during replay: '+profile)
    return dict(profile=profile,status='PASS',sourceSha256=source,buildSha256=build,toolchainSha256=toolchain,readerSha256=reader,
                producerReceiptSha256=original['receiptSha256'],originalPlanSha256=original['plan'],
                qualification=result,phase3Complete=False)


def validate(paths,source,build,toolchain,reader,*,workers=1,progress=None):
    from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
    need(type(workers) is int and 1<=workers<=4,'profile matrix replay workers');check_pins(source,build,toolchain,reader)
    need(type(paths) is dict and set(paths)==set(PROFILES),'profile matrix complete declared set')
    need(len({Path(v).resolve() for v in paths.values()})==len(PROFILES),'profile matrix distinct producer directories')
    originals={p:member(paths[p],p,source,build,toolchain,reader) for p in PROFILES}
    need(len({v['plan'] for v in originals.values()})==len(PROFILES),'profile matrix distinct original histories')
    outcomes={}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks={pool.submit(qualify_member,paths[p],p,source,build,toolchain,reader):p for p in PROFILES};pending=set(tasks)
        while pending:
            done,pending=wait(pending,timeout=60,return_when=FIRST_COMPLETED)
            for task in done:
                profile=tasks[task]
                try:outcomes[profile]=task.result()
                except Exception as error:outcomes[profile]=dict(profile=profile,status='FAIL',failure=dict(type=type(error).__name__,message=str(error)))
                if progress:progress(dict(stage='member-terminal',completed=len(outcomes),total=len(PROFILES),**outcomes[profile]))
            if not done and progress:progress(dict(stage='independent-replay',completed=len(outcomes),total=len(PROFILES)))
    for profile in PROFILES:
        need(member(paths[profile],profile,source,build,toolchain,reader)==originals[profile],'profile matrix producer changed before completion: '+profile)
    check_pins(source,build,toolchain,reader)
    passed=all(outcomes[p]['status']=='PASS' for p in PROFILES)
    return dict(schema=SCHEMA,status='PASS' if passed else 'FAIL',scope='seven-ordinary-histories-through-implemented-ballot-retention-composition',
                sourceSha256=source,buildSha256=build,toolchainSha256=toolchain,readerSha256=reader,
                cases=[outcomes[p] for p in PROFILES],wholeHistories=len(PROFILES),
                negativeCases=sum(len(v.get('qualification',{}).get('negatives',[])) for v in outcomes.values()),
                declaredMembershipProfileMatrixQualified=passed,processDeathQualified=False,
                originalObservationCoverageComplete=False,phase3Complete=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True);sub.add_parser('plan')
    for name in ('member','aggregate'):
        cmd=sub.add_parser(name);cmd.add_argument('output')
        if name=='member':cmd.add_argument('--producer',required=True);cmd.add_argument('--profile',required=True,choices=PROFILES)
        else:cmd.add_argument('--inputs',required=True);cmd.add_argument('--workers',type=int,default=1)
        for pin in ('source','build','toolchain','reader'):cmd.add_argument('--'+pin+'-sha256',required=True)
    args=parser.parse_args()
    if args.command=='plan':
        print(json.dumps(dict(profiles=[dict(profile=p,id=slug(p)) for p in catalogue()],reader=reader_manifest(),phase3Complete=False),sort_keys=True));return
    output=Path(args.output);output.mkdir(parents=True,exist_ok=False);receipt=dict(schema=SCHEMA,status='RUNNING',phase3Complete=False)
    try:
        pins=[getattr(args,p+'_sha256') for p in ('source','build','toolchain','reader')]
        if args.command=='member':receipt=qualify_member(args.producer,args.profile,*pins)
        else:
            inputs=Path(args.inputs);need(inputs.is_dir() and not inputs.is_symlink(),'profile matrix input directory')
            need({v.name for v in inputs.iterdir()}=={slug(p) for p in PROFILES},'profile matrix exact input directory set')
            with (output/'progress.jsonl').open('x') as stream:
                def progress(row):
                    stream.write(json.dumps(row,sort_keys=True)+'\n');stream.flush()
                    print(json.dumps({k:v for k,v in row.items() if k!='qualification'},sort_keys=True),file=sys.stderr,flush=True)
                receipt=validate({p:inputs/slug(p) for p in PROFILES},*pins,workers=args.workers,progress=progress)
        need(receipt['status']=='PASS','profile matrix failed members')
    except BaseException as error:
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    print(json.dumps(dict(status='PASS',receipt=str(output/'receipt.json'),phase3Complete=False),sort_keys=True))


if __name__=='__main__':main()
