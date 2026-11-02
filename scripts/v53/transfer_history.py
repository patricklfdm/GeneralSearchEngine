"""Capture and admit the complete native TCP lifetime/process matrices.

The nine service lifetimes on each original owner and each two-process restart
history stay indivisible. Collection is not acceptance; the cohort replays every
original before its exact negative vector. No native retries or budget overrides.
"""
import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

from . import joining_history_run as h
from . import remove_process_matrix as shared
from . import process_toolchain as tc
from . import transfer_fault_evidence as faults
from . import transfer_process_evidence as process

need=h.need;read=shared.read;reader_manifest=shared.reader_manifest;BUILDS=shared.BUILDS
SCHEMA='gse-v53-transfer-history-execution-v1'
COHORT='gse-v53-transfer-history-cohort-v1'
PACKAGE='io.github.patricklfdm.generalsearch.replication.'
METHODS={
    'tcp-lifetimes':('V53TransferFaultsTest','publicBootstrapTcpFaultsAtAllStableSizes','v53-transfer-faults'),
    'process-recovery':('V53TransferProcessTest','originalSourceSurvivesEveryTransferReplyProcessCut','v53-transfer-process'),
}
CASES=tuple(METHODS)
READERS={'tcp-lifetimes':faults,'process-recovery':process}


def selected(case):
    need(type(case) is str and case in METHODS,'transfer history exact case');return METHODS[case]


def command(case):
    cls,method,_=selected(case)
    return ['-o','-B','-ntp','-f','reactor/pom.xml','-pl','../'+h.MODULE,'-am',
            '-Dsurefire.failIfNoSpecifiedTests=false','-Dtest='+cls+'#'+method,'test']


def junit(reports,case):
    cls,method,_=selected(case);cls=PACKAGE+cls;paths=sorted(Path(reports).glob('TEST-*.xml'))
    need(len(paths)==1,'transfer history exact JUnit report')
    suite=ET.fromstring(h.snapshot.s.regular(paths[0],8*h.snapshot.MIB));tests=suite.findall('testcase')
    need(suite.get('name')==cls and suite.get('tests')=='1' and len(tests)==1 and
         all(suite.get(k)=='0' for k in ('failures','errors','skipped')) and
         tests[0].get('classname')==cls and tests[0].get('name')==method and
         not any(v.tag in ('failure','error','skipped') or v.tag.startswith(('flaky','rerun')) for v in suite.iter()),
         'transfer history exact unretried passing test')
    return dict(className=cls,method=method,tests=1,failures=0,errors=0,skipped=0,retries=0)


def fixture(case):
    selected(case)
    if case=='tcp-lifetimes':
        return dict(schema='gse-v53-transfer-faults-v1',status='PASS',network=True,publicRuntime=False,phase3Complete=False,
            profiles=[dict(size=n,cases=[dict(case=k,size=n) for k in faults.CASES]) for n in (3,4,5)])
    return dict(schema='gse-v53-transfer-process-v1',status='PASS',cases=list(process.PROFILES),completeMatrix=True,phase3Complete=False)


def histories(case):
    selected(case)
    return [f'stable-{n}' for n in (3,4,5)] if case=='tcp-lifetimes' else [process.name(v) for v in process.PROFILES]


def collect(raw,case):
    selected(case);raw=Path(raw);before=h.inventory(raw)
    need({v.name for v in raw.iterdir()}=={'receipt.json',*histories(case)},'transfer history complete original directories')
    need(h.snapshot.f.canonical(read(raw/'receipt.json'))==h.snapshot.f.canonical(fixture(case)),
         'transfer history complete producer fixture')
    plans={}
    for name in histories(case):
        member=raw/name;source=member if case=='tcp-lifetimes' else member/'history'
        plans[name]=h.digest(h.snapshot.s.regular(source/'original-plan.gsbp',h.snapshot.MIB))
        if case=='tcp-lifetimes':
            need({v.name for v in (member/'cases').iterdir()}==set(faults.CASES),'transfer history continuous service cases')
            for k in faults.CASES:
                result=read(member/'cases'/k/'result.json')
                need(result.get('case')==k and result.get('status')=='PASS','transfer history failed service case')
        # Physical contents, force/exit receipts and transcripts are validated
        # independently later; this collection cannot claim their correctness.
    need(len(set(plans.values()))==len(plans),'transfer history distinct original bootstraps')
    need(h.inventory(raw)==before,'transfer history changed during collection')
    return dict(status='PARTIAL',case=case,collectionComplete=True,nativeHistoryQualified=False,phase3Complete=False,
                scope='original-transfer-matrix-collection',plans=plans,inventory=before)


def capture(output,maven,case,source_from=None):
    selected(case);output=Path(output).absolute()
    need(source_from is None or not output.resolve().is_relative_to(Path(source_from).resolve()),'transfer history source separation')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,case=case,status='RUNNING',executionStatus='NOT_RUN',collectionComplete=False,
                 nativeHistoryQualified=False,phase3Complete=False,retries=0)
    try:
        work=output/'workspace';source=h.source_copy(h.ROOT,work) if source_from is None else h.recorded_source(source_from,work)
        h.save(output/'source.json',source);reader=reader_manifest()
        need(all(source['files'].get(k)==v for k,v in reader['files'].items()),'transfer history reader belongs to source')
        h.save(output/'toolchain.json',tc.capture(maven,work))
        receipt.update(baseHead=source['head'],sourceSha256=h.digest((output/'source.json').read_bytes()),readerSha256=reader['sha256'],
            toolchainSha256=h.digest((output/'toolchain.json').read_bytes()),command=[maven,*command(case)])
        h.save(output/'receipt.json',receipt)
        execution=h.execute(receipt['command'],work,output/'maven.log',stage='transfer-'+case)
        h.save(output/'execution.json',execution);receipt['execution']=execution;h.check_source(work,source)
        need(type(execution['exit']) is int and execution['exit']==0,'transfer history Maven failed; original retained')
        receipt['junit']=junit(work/h.MODULE/'target/surefire-reports',case);receipt['executionStatus']='PASS'
        h.save(output/'build.json',{name:h.inventory(work/name) for name in BUILDS})
        receipt['buildSha256']=h.digest((output/'build.json').read_bytes())
        roots=list((work/h.MODULE/'target'/selected(case)[2]).iterdir())
        need(len(roots)==1,'transfer history exact raw directory');raw=roots[0];receipt['raw']=raw.relative_to(output).as_posix()
        collected=h.execute([sys.executable,'-B','-m','scripts.v53.transfer_history','collect',str(output/'collection.json'),
            '--case',case,'--raw',str(raw)],work,output/'collection.log',stage='transfer-collection-'+case)
        h.save(output/'collection-execution.json',collected);receipt['collectionExecution']=collected
        need(type(collected['exit']) is int and collected['exit']==0,'transfer history collection failed; original retained')
        need(read(output/'collection.json')==collect(raw,case),'transfer history immutable source collection')
        h.check_source(work,source);receipt.update(status='PARTIAL',collectionComplete=True,
            collectionSha256=h.digest((output/'collection.json').read_bytes()))
    except BaseException as error:
        if receipt['executionStatus']=='NOT_RUN':receipt['executionStatus']='FAIL'
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


def check_pins(source,build,toolchain,reader):
    need(all(shared.hash_field(v) for v in (source,build,toolchain,reader)),'transfer cohort pinned hashes')
    manifest=reader_manifest();need(manifest['sha256']==reader,'transfer cohort pinned reader');return manifest


def member(path,case,source,build,toolchain,reader):
    selected(case);manifest=check_pins(source,build,toolchain,reader);path=Path(path)
    need(path.is_dir() and not path.is_symlink(),'transfer cohort producer directory');receipt=read(path/'receipt.json')
    need(type(receipt) is dict and receipt.get('schema')==SCHEMA and receipt.get('case')==case and receipt.get('status')=='PARTIAL'
         and receipt.get('executionStatus')=='PASS' and receipt.get('collectionComplete') is True
         and all(receipt.get(k) is False for k in ('nativeHistoryQualified','phase3Complete'))
         and type(receipt.get('retries')) is int and receipt['retries']==0,'transfer cohort successful unretried producer')
    for field,file in (('execution','execution.json'),('collectionExecution','collection-execution.json')):
        value=receipt.get(field)
        need(type(value) is dict and type(value.get('exit')) is int and value['exit']==0
             and h.snapshot.f.canonical(read(path/file))==h.snapshot.f.canonical(value),'transfer cohort successful process receipts')
    recorded,_=h.read_recorded_source(path);work=path/'workspace'
    need(receipt.get('sourceSha256')==source==h.digest((path/'source.json').read_bytes()) and receipt.get('baseHead')==recorded['head'],
         'transfer cohort exact producer source')
    need(receipt.get('readerSha256')==reader and all(recorded['files'].get(k)==v for k,v in manifest['files'].items()),
         'transfer cohort reader belongs to producer')
    args=receipt.get('command');wanted=command(case)
    need(type(args) is list and len(args)==len(wanted)+1 and type(args[0]) is str and Path(args[0]).name=='mvn'
         and args[1:]==wanted,'transfer cohort exact complete command')
    for name in (*BUILDS,h.MODULE+'/target/surefire-reports'):
        need(all((work/p).is_dir() and not (work/p).is_symlink() for p in (Path(name),*Path(name).parents)),
             'transfer cohort linked generated parent')
    need(h.snapshot.f.canonical(receipt.get('junit'))==h.snapshot.f.canonical(junit(work/h.MODULE/'target/surefire-reports',case)),
         'transfer cohort exact JUnit receipt')
    classes=read(path/'build.json')
    need(type(classes) is dict and set(classes)==set(BUILDS) and receipt.get('buildSha256')==build==h.digest((path/'build.json').read_bytes()),
         'transfer cohort exact build manifest')
    for name in BUILDS:need(h.inventory(work/name)==classes[name],'transfer cohort original compiled bytes')
    tc.validate(read(path/'toolchain.json'))
    need(receipt.get('toolchainSha256')==h.digest((path/'toolchain.json').read_bytes()) and tc.pin((path/'toolchain.json').read_bytes())==toolchain,
         'transfer cohort portable toolchain')
    name=receipt.get('raw');base='workspace/'+h.MODULE+'/target/'+selected(case)[2]
    need(type(name) is str and re.fullmatch(base+r'/run-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',name),
         'transfer cohort exact raw path')
    need(all((path/p).is_dir() and not (path/p).is_symlink() for p in Path(name).parents),'transfer cohort linked raw parent')
    raw=path/name;need({v.name for v in raw.parent.iterdir()}=={raw.name},'transfer cohort exactly one original run')
    collection=collect(raw,case)
    need(receipt.get('collectionSha256')==h.digest((path/'collection.json').read_bytes()) and
         h.snapshot.f.canonical(read(path/'collection.json'))==h.snapshot.f.canonical(collection),
         'transfer cohort independent original collection')
    return dict(raw=raw,plans=collection['plans'],inventory=collection['inventory'],receiptSha256=h.digest((path/'receipt.json').read_bytes()))


def check_result(value,case):
    selected(case)
    need(type(value) is dict and set(value)=={'original','negatives','originalPreserved'} and value['originalPreserved'] is True,
         'transfer cohort preserved original replay')
    original=value['original']
    need(type(original) is dict and original.get('status')=='PASS' and original.get('phase3Complete') is False
         and original.get('allMembershipProfilesQualified') is False,'transfer cohort scoped original result')
    if case=='tcp-lifetimes':
        need(set(original)=={'status','scope','profiles','cases','faultInjectionClock','resourceCounts','processDeathQualified','allMembershipProfilesQualified','phase3Complete'}
             and original['scope']=='original-public-bootstrap-TCP-transfer-faults' and type(original['cases']) is int and original['cases']==27
             and original['processDeathQualified'] is False and original['faultInjectionClock']=='explicit-offset; not measured elapsed time'
             and original['resourceCounts']=='source-bound observations','transfer cohort complete lifetime matrix')
        need(type(original['profiles']) is list and len(original['profiles'])==3,'transfer cohort lifetime profile count')
        for row,size in zip(original['profiles'],(3,4,5)):
            need(set(row)=={'size','cases'} and type(row['size']) is int and row['size']==size and
                 type(row['cases']) is list and len(row['cases'])==len(faults.CASES) and
                 [v.get('case') for v in row['cases']]==list(faults.CASES),'transfer cohort ordered lifetime cases')
    else:
        need(set(original)=={'status','scope','cases','processes','interruptedReplies','transferProcessQualified','allMembershipProfilesQualified',
                            'completePhysicalQualified','forceAndNetworkQualified','phase3Complete','powerLossQualified'}
             and original['scope']=='original-donor-TCP-halt-SIGKILL-reopen' and type(original['processes']) is int and original['processes']==36
             and type(original['interruptedReplies']) is int and original['interruptedReplies']==18 and original['transferProcessQualified'] is True
             and all(original[k] is False for k in ('completePhysicalQualified','forceAndNetworkQualified','powerLossQualified')),
             'transfer cohort complete process matrix')
        need(type(original['cases']) is list and len(original['cases'])==18 and
             [v.get('profile') for v in original['cases']]==list(process.PROFILES) and
             all(v.get('status')=='PASS' and v.get('originalSourcePreserved') is True for v in original['cases']),
             'transfer cohort ordered process cases')
    need(value['negatives']==[dict(case=k,status='REJECTED',reason=v) for k,v in READERS[case].NEGATIVES],
         'transfer cohort exact negative vector')


def qualify_member(path,case,*pins):
    before=member(path,case,*pins);result=READERS[case].qualify(before['raw']);check_result(result,case)
    need(member(path,case,*pins)==before,'transfer cohort changed during replay');check_pins(*pins)
    return dict(case=case,status='PASS',plans=before['plans'],producerReceiptSha256=before['receiptSha256'],qualification=result,
                **dict(zip(('sourceSha256','buildSha256','toolchainSha256','readerSha256'),pins)),phase3Complete=False)


def aggregate(paths,*pins,workers=1,progress=None):
    check_pins(*pins);need(type(workers) is int and 1<=workers<=2,'transfer cohort replay workers')
    need(type(paths) is dict and set(paths)==set(CASES),'transfer cohort complete matrix pair')
    need(len({Path(v).resolve() for v in paths.values()})==len(CASES),'transfer cohort distinct producers')
    originals={k:member(paths[k],k,*pins) for k in CASES};plans=[v for k in CASES for v in originals[k]['plans'].values()]
    need(len(plans)==len(set(plans))==21,'transfer cohort distinct complete original histories')
    outcomes={}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks={pool.submit(qualify_member,paths[k],k,*pins):k for k in CASES};pending=set(tasks)
        while pending:
            done,pending=wait(pending,timeout=60,return_when=FIRST_COMPLETED)
            for task in done:
                case=tasks[task]
                try:value=task.result()
                except Exception as error:value=dict(case=case,status='FAIL',failure=dict(type=type(error).__name__,message=str(error)))
                outcomes[case]=value
                if progress:progress(dict(stage='member-terminal',completed=len(outcomes),total=2,case=case,status=value['status']))
            if not done and progress:progress(dict(stage='transfer-replay',completed=len(outcomes),total=2))
    for k in CASES:need(member(paths[k],k,*pins)==originals[k],'transfer cohort original changed before aggregate')
    check_pins(*pins);passed=all(outcomes[k]['status']=='PASS' for k in CASES)
    return dict(schema=COHORT,status='PASS' if passed else 'FAIL',scope='complete-bootstrap-TCP-lifetime-and-process-matrices',
        cases=[outcomes[k] for k in CASES],wholeOwnershipHistories=21,nativeCases=45,
        negativeCases=sum(len(v.get('qualification',{}).get('negatives',[])) for v in outcomes.values()),
        **dict(zip(('sourceSha256','buildSha256','toolchainSha256','readerSha256'),pins)),declaredTransferMatricesQualified=passed,
        allMembershipProfilesQualified=False,combinedPeakResourcesQualified=False,autonomousCompetitionQualified=False,
        completePhysicalQualified=False,powerLossQualified=False,phase3Complete=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True);sub.add_parser('plan')
    for mode in ('capture','collect','member','aggregate'):
        p=sub.add_parser(mode);p.add_argument('output')
        if mode!='aggregate':p.add_argument('--case',required=True,choices=CASES)
        if mode=='capture':p.add_argument('--maven',default='mvn');p.add_argument('--source-from')
        elif mode=='collect':p.add_argument('--raw',required=True)
        else:
            if mode=='member':p.add_argument('--producer',required=True)
            else:p.add_argument('--inputs',required=True);p.add_argument('--workers',type=int,default=1)
            for pin in ('source','build','toolchain','reader'):p.add_argument('--'+pin+'-sha256',required=True)
    a=parser.parse_args()
    if a.command=='plan':
        print(json.dumps(dict(cases=[dict(case=k,command=command(k),histories=histories(k),negatives=len(READERS[k].NEGATIVES)) for k in CASES],
                              reader=reader_manifest(),phase3Complete=False),sort_keys=True));return
    if a.command=='capture':result=capture(a.output,a.maven,a.case,a.source_from)
    elif a.command=='collect':
        result=collect(a.raw,a.case)
        with Path(a.output).open('x') as stream:json.dump(result,stream,sort_keys=True,indent=2);stream.write('\n')
    else:
        output=Path(a.output);output.mkdir(parents=True,exist_ok=False);result=dict(schema=COHORT,status='FAIL',phase3Complete=False)
        try:
            pins=[getattr(a,k+'_sha256') for k in ('source','build','toolchain','reader')]
            from .remove_process_hosted import progress as heartbeat
            with heartbeat('transfer-'+a.command,getattr(a,'case',None)),(output/'progress.jsonl').open('x') as stream:
                def progress(v):stream.write(json.dumps(v,sort_keys=True)+'\n');stream.flush();print(json.dumps(v),file=sys.stderr,flush=True)
                if a.command=='member':result=qualify_member(a.producer,a.case,*pins)
                else:
                    inputs=Path(a.inputs);need(inputs.is_dir() and not inputs.is_symlink() and {v.name for v in inputs.iterdir()}==set(CASES),
                        'transfer cohort exact input directories')
                    result=aggregate({k:inputs/k for k in CASES},*pins,workers=a.workers,progress=progress)
            need(result['status']=='PASS','transfer cohort failed originals')
        except BaseException as error:result.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
        finally:h.save(output/'receipt.json',result)
    print(json.dumps(dict(status=result['status'],phase3Complete=False,output=a.output),sort_keys=True))


if __name__=='__main__':main()
