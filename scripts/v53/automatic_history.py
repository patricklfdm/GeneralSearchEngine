"""Source-bound automatic competition, restart and reply-revocation admission.

Each whole native execution remains indivisible. Producer collection stays
PARTIAL; all original reader layers precede exact applicable negative vectors.
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
from . import automatic_history_replay as gate
from . import automatic_restart_lifecycle as restart
from . import transfer_reply_lifetime as replies

need=h.need;read=shared.read;reader_manifest=shared.reader_manifest;BUILDS=shared.BUILDS
SCHEMA='gse-v53-automatic-history-execution-v1'
COHORT='gse-v53-automatic-history-cohort-v1'
PACKAGE='io.github.patricklfdm.generalsearch.replication.'
METHODS={
    'competition':('V53CompetingNodeQualification','threeAutomaticOwnersConvergeAndPublishOneOriginalData','v53-competing-node'),
    'higher-ballot-restart':('V53AutomaticRestartTest','higherBallotAutomaticallyDrainsAndReactivatesBeforeNewData','v53-native-dispatch'),
    'reply-revocation':('V53TransferReplyLifetimeTest','materializedRepliesCannotOutliveOriginalScope','v53-transfer-reply-lifetime'),
}
CASES=tuple(METHODS)


def selected(case):
    need(type(case) is str and case in METHODS,'automatic history exact case');return METHODS[case]


def command(case):
    cls,method,_=selected(case)
    return ['-o','-B','-ntp','-f','reactor/pom.xml','-pl','../'+h.MODULE,'-am',
            '-Dsurefire.failIfNoSpecifiedTests=false','-Dtest='+cls+'#'+method,*(['-Dv53.restart.lifecycle.captures=true'] if case=='higher-ballot-restart' else []),'test']


def junit(reports,case):
    cls,method,_=selected(case);cls=PACKAGE+cls;paths=sorted(Path(reports).glob('TEST-*.xml'))
    need(len(paths)==1,'automatic history exact JUnit report')
    suite=ET.fromstring(h.snapshot.s.regular(paths[0],8*h.snapshot.MIB));tests=suite.findall('testcase')
    need(suite.get('name')==cls and suite.get('tests')=='1' and len(tests)==1 and
         all(suite.get(k)=='0' for k in ('failures','errors','skipped')) and
         tests[0].get('classname')==cls and tests[0].get('name')==method and
         not any(v.tag in ('failure','error','skipped') or v.tag.startswith(('flaky','rerun')) for v in suite.iter()),
         'automatic history exact unretried passing test')
    return dict(className=cls,method=method,tests=1,failures=0,errors=0,skipped=0,retries=0)


def histories(case):
    selected(case)
    return [f'{n}-{b}-{f}' for n,b,f in replies.CASES] if case=='reply-revocation' else [case]


def sidecar(raw,case):
    selected(case);raw=Path(raw)
    return raw.with_name('restart-lifecycle-'+raw.name) if case=='higher-ballot-restart' else None


def raw_members(raw,case):
    captured=sidecar(raw,case)
    return {raw.name}|({captured.name} if captured else set())


def collect(raw,case):
    selected(case);raw=Path(raw);before=h.inventory(raw);plans={};captures=None
    if case=='reply-revocation':
        names=histories(case)
        need({v.name for v in raw.iterdir()}==set(names)|{'receipt.json'},'automatic complete reply matrix')
        expected=dict(schema=replies.SCHEMA,status='PASS',cases=[dict(case=name,size=n,boundary=b,fault=f)
            for name,(n,b,f) in zip(names,replies.CASES)],publicRuntime=False,phase3Complete=False)
        need(h.snapshot.f.canonical(read(raw/'receipt.json'))==h.snapshot.f.canonical(expected),'automatic complete reply producer')
        for name,(n,b,f) in zip(names,replies.CASES):
            need(read(raw/name/'result.json')==dict(size=n,boundary=b,fault=f,status='PASS'),'automatic reply case failed')
            plans[name]=h.digest(h.snapshot.s.regular(raw/name/'source/original-plan.gsbp',h.snapshot.MIB))
    else:
        plans[case]=h.digest(h.snapshot.s.regular(raw/'original-plan.gsbp',h.snapshot.MIB))
        if case=='competition':
            expected=dict(status='PARTIAL',producerPassed=True,nodes=3,automaticOwners=3,defaultBounds=True,physicalReplay=False,phase3Complete=False)
            name='result.json'
            need(h.snapshot.s.regular(raw/'failure.txt',h.snapshot.MIB)==h.snapshot.s.regular(raw/'close-failure.txt',h.snapshot.MIB)==b'',
                 'automatic competition producer failure')
        else:
            expected=dict(status='PARTIAL',producerPassed=True,rounds=2,barriers=2,dataCalls=1,originalBudgetNanos=restart.BUDGET,physicalReplay=False,phase3Complete=False)
            name='restart-result.json';captures=h.inventory(sidecar(raw,case))
            need(set(captures['files'])=={restart.CAPTURE,restart.OBSERVATIONS} and not captures['directories'],'automatic restart exact captures')
            attachment=read(sidecar(raw,case)/restart.CAPTURE)
            need(attachment.get('schema')==restart.SCHEMA and attachment.get('producerPassed') is True and attachment.get('ownerDrained') is True
                 and attachment.get('captureFailure')==attachment.get('observationFailure')==''
                 and attachment.get('eventsSha256')==before['files'].get('events.json')
                 and attachment.get('planSha256')==plans[case],'automatic restart complete producer attachment')
        need(h.snapshot.f.canonical(read(raw/name))==h.snapshot.f.canonical(expected),'automatic exact producer result')
    need(len(set(plans.values()))==len(plans),'automatic distinct original plans')
    need(h.inventory(raw)==before and (captures is None or h.inventory(sidecar(raw,case))==captures),'automatic changed during collection')
    return dict(status='PARTIAL',case=case,collectionComplete=True,nativeHistoryQualified=False,phase3Complete=False,
                scope='automatic-native-original-collection',plans=plans,inventory=before,captureInventory=captures)


def replay(raw,case):return gate.replay(raw,case,sidecar(raw,case))
def check_result(value,case):selected(case);gate.check_result(value,case)


def capture(output,maven,case,source_from=None):
    selected(case);output=Path(output).absolute()
    need(source_from is None or not output.resolve().is_relative_to(Path(source_from).resolve()),'automatic history source separation')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,case=case,status='RUNNING',executionStatus='NOT_RUN',collectionComplete=False,
                 nativeHistoryQualified=False,phase3Complete=False,retries=0)
    try:
        work=output/'workspace';source=h.source_copy(h.ROOT,work) if source_from is None else h.recorded_source(source_from,work)
        h.save(output/'source.json',source);reader=reader_manifest()
        need(all(source['files'].get(k)==v for k,v in reader['files'].items()),'automatic history reader belongs to source')
        h.save(output/'toolchain.json',tc.capture(maven,work))
        receipt.update(baseHead=source['head'],sourceSha256=h.digest((output/'source.json').read_bytes()),readerSha256=reader['sha256'],
            toolchainSha256=h.digest((output/'toolchain.json').read_bytes()),command=[maven,*command(case)])
        h.save(output/'receipt.json',receipt)
        execution=h.execute(receipt['command'],work,output/'maven.log',stage='automatic-'+case)
        h.save(output/'execution.json',execution);receipt['execution']=execution;h.check_source(work,source)
        need(type(execution['exit']) is int and execution['exit']==0,'automatic history Maven failed; original retained')
        receipt['junit']=junit(work/h.MODULE/'target/surefire-reports',case);receipt['executionStatus']='PASS'
        h.save(output/'build.json',{name:h.inventory(work/name) for name in BUILDS})
        receipt['buildSha256']=h.digest((output/'build.json').read_bytes())
        roots=list((work/h.MODULE/'target'/selected(case)[2]).glob('run-*'))
        need(len(roots)==1,'automatic history exact raw directory');raw=roots[0];receipt['raw']=raw.relative_to(output).as_posix()
        need({v.name for v in raw.parent.iterdir()}==raw_members(raw,case),'automatic history exact original and captures')
        receipt['captures']=sidecar(raw,case).relative_to(output).as_posix() if sidecar(raw,case) else None
        collected=h.execute([sys.executable,'-B','-m','scripts.v53.automatic_history','collect',str(output/'collection.json'),
            '--case',case,'--raw',str(raw)],work,output/'collection.log',stage='automatic-collection-'+case)
        h.save(output/'collection-execution.json',collected);receipt['collectionExecution']=collected
        need(type(collected['exit']) is int and collected['exit']==0,'automatic history collection failed; original retained')
        need(read(output/'collection.json')==collect(raw,case),'automatic history immutable source collection')
        h.check_source(work,source);receipt.update(status='PARTIAL',collectionComplete=True,
            collectionSha256=h.digest((output/'collection.json').read_bytes()))
    except BaseException as error:
        if receipt['executionStatus']=='NOT_RUN':receipt['executionStatus']='FAIL'
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


def check_pins(source,build,toolchain,reader):
    need(all(shared.hash_field(v) for v in (source,build,toolchain,reader)),'automatic cohort pinned hashes')
    manifest=reader_manifest();need(manifest['sha256']==reader,'automatic cohort pinned reader');return manifest


def member(path,case,source,build,toolchain,reader):
    selected(case);manifest=check_pins(source,build,toolchain,reader);path=Path(path)
    need(path.is_dir() and not path.is_symlink(),'automatic cohort producer directory');receipt=read(path/'receipt.json')
    need(type(receipt) is dict and receipt.get('schema')==SCHEMA and receipt.get('case')==case and receipt.get('status')=='PARTIAL'
         and receipt.get('executionStatus')=='PASS' and receipt.get('collectionComplete') is True
         and all(receipt.get(k) is False for k in ('nativeHistoryQualified','phase3Complete'))
         and type(receipt.get('retries')) is int and receipt['retries']==0,'automatic cohort successful unretried producer')
    for field,file in (('execution','execution.json'),('collectionExecution','collection-execution.json')):
        value=receipt.get(field)
        need(type(value) is dict and type(value.get('exit')) is int and value['exit']==0
             and h.snapshot.f.canonical(read(path/file))==h.snapshot.f.canonical(value),'automatic cohort successful process receipts')
    recorded,_=h.read_recorded_source(path);work=path/'workspace'
    need(receipt.get('sourceSha256')==source==h.digest((path/'source.json').read_bytes()) and receipt.get('baseHead')==recorded['head'],
         'automatic cohort exact producer source')
    need(receipt.get('readerSha256')==reader and all(recorded['files'].get(k)==v for k,v in manifest['files'].items()),
         'automatic cohort reader belongs to producer')
    args=receipt.get('command');wanted=command(case)
    need(type(args) is list and len(args)==len(wanted)+1 and type(args[0]) is str and Path(args[0]).name=='mvn'
         and args[1:]==wanted,'automatic cohort exact complete command')
    for name in (*BUILDS,h.MODULE+'/target/surefire-reports'):
        need(all((work/p).is_dir() and not (work/p).is_symlink() for p in (Path(name),*Path(name).parents)),
             'automatic cohort linked generated parent')
    need(h.snapshot.f.canonical(receipt.get('junit'))==h.snapshot.f.canonical(junit(work/h.MODULE/'target/surefire-reports',case)),
         'automatic cohort exact JUnit receipt')
    classes=read(path/'build.json')
    need(type(classes) is dict and set(classes)==set(BUILDS) and receipt.get('buildSha256')==build==h.digest((path/'build.json').read_bytes()),
         'automatic cohort exact build manifest')
    for name in BUILDS:need(h.inventory(work/name)==classes[name],'automatic cohort original compiled bytes')
    tc.validate(read(path/'toolchain.json'))
    need(receipt.get('toolchainSha256')==h.digest((path/'toolchain.json').read_bytes()) and tc.pin((path/'toolchain.json').read_bytes())==toolchain,
         'automatic cohort portable toolchain')
    name=receipt.get('raw');base='workspace/'+h.MODULE+'/target/'+selected(case)[2]
    need(type(name) is str and re.fullmatch(base+r'/run-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',name),
         'automatic cohort exact raw path')
    need(all((path/p).is_dir() and not (path/p).is_symlink() for p in Path(name).parents),'automatic cohort linked raw parent')
    raw=path/name;need({v.name for v in raw.parent.iterdir()}==raw_members(raw,case),'automatic cohort exactly one original run and captures')
    need(receipt.get('captures')==(sidecar(raw,case).relative_to(path).as_posix() if sidecar(raw,case) else None),'automatic cohort exact captures path')
    collection=collect(raw,case)
    need(receipt.get('collectionSha256')==h.digest((path/'collection.json').read_bytes()) and
         h.snapshot.f.canonical(read(path/'collection.json'))==h.snapshot.f.canonical(collection),
         'automatic cohort independent original collection')
    return dict(raw=raw,plans=collection['plans'],inventory=collection['inventory'],captureInventory=collection['captureInventory'],receiptSha256=h.digest((path/'receipt.json').read_bytes()))


def qualify_member(path,case,*pins):
    before=member(path,case,*pins);result=replay(before['raw'],case);check_result(result,case)
    need(member(path,case,*pins)==before,'automatic cohort changed during replay');check_pins(*pins)
    return dict(case=case,status='PASS',plans=before['plans'],producerReceiptSha256=before['receiptSha256'],qualification=result,
                **dict(zip(('sourceSha256','buildSha256','toolchainSha256','readerSha256'),pins)),phase3Complete=False)


def aggregate(paths,*pins,workers=1,progress=None):
    check_pins(*pins);need(type(workers) is int and 1<=workers<=3,'automatic cohort replay workers')
    need(type(paths) is dict and set(paths)==set(CASES),'automatic cohort complete three histories')
    need(len({Path(v).resolve() for v in paths.values()})==len(CASES),'automatic cohort distinct producers')
    originals={k:member(paths[k],k,*pins) for k in CASES};plans=[v for k in CASES for v in originals[k]['plans'].values()]
    need(len(plans)==len(set(plans))==50,'automatic cohort distinct complete original histories')
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
                if progress:progress(dict(stage='member-terminal',completed=len(outcomes),total=len(CASES),case=case,status=value['status']))
            if not done and progress:progress(dict(stage='automatic-replay',completed=len(outcomes),total=len(CASES)))
    for k in CASES:need(member(paths[k],k,*pins)==originals[k],'automatic cohort original changed before aggregate')
    check_pins(*pins);passed=all(outcomes[k]['status']=='PASS' for k in CASES)
    return dict(schema=COHORT,status='PASS' if passed else 'FAIL',scope='declared-native-automatic-and-reply-lifetimes',
        cases=[outcomes[k] for k in CASES],wholeOwnershipHistories=50,executionGroups=3,
        negativeCases=sum(len(v.get('qualification',{}).get('negatives',[])) for v in outcomes.values()),
        **dict(zip(('sourceSha256','buildSha256','toolchainSha256','readerSha256'),pins)),declaredMatricesQualified=passed,
        allMembershipProfilesQualified=False,combinedPeakResourcesQualified=False,fullLifecycleQualified=False,
        completeExportLifetimesQualified=False,phase3Complete=False)


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
        print(json.dumps(dict(cases=[dict(case=k,command=command(k),histories=histories(k),negativeSuites=gate.suites(k)) for k in CASES],
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
            with heartbeat('automatic-'+a.command,getattr(a,'case',None)),(output/'progress.jsonl').open('x') as stream:
                def progress(v):stream.write(json.dumps(v,sort_keys=True)+'\n');stream.flush();print(json.dumps(v),file=sys.stderr,flush=True)
                if a.command=='member':result=qualify_member(a.producer,a.case,*pins)
                else:
                    inputs=Path(a.inputs);need(inputs.is_dir() and not inputs.is_symlink() and {v.name for v in inputs.iterdir()}==set(CASES),
                        'automatic cohort exact input directories')
                    result=aggregate({k:inputs/k for k in CASES},*pins,workers=a.workers,progress=progress)
            need(result['status']=='PASS','automatic cohort failed originals')
        except BaseException as error:result.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
        finally:h.save(output/'receipt.json',result)
    print(json.dumps(dict(status=result['status'],phase3Complete=False,output=a.output),sort_keys=True))


if __name__=='__main__':main()
