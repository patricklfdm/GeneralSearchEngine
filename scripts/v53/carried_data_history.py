"""Capture complete native carried DATA histories without replaying a client.

Old ACCEPT/PROOF/CERTIFICATE/APPLIED, new-ballot completion and the next fresh
BARRIER remain one original. Full physical replay precedes every exact negative.
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
from . import carried_slot_evidence as carried
from . import native_carried_network as recovery

dispatch=carried.d

need=h.need;read=shared.read;reader_manifest=shared.reader_manifest;BUILDS=shared.BUILDS
SCHEMA='gse-v53-carried-data-history-execution-v2'
COHORT='gse-v53-carried-data-history-cohort-v2'
PACKAGE='io.github.patricklfdm.generalsearch.replication.'
METHODS={
    'data-accept':('V53CarriedDataDriverTest','acceptedDataReplaysOnceBeforeFreshBarrier','v53-native-dispatch'),
    'data-proof':('V53CarriedDataDriverTest','provenDataReplaysOnceBeforeFreshBarrier','v53-native-dispatch'),
    'data-certificate':('V53CarriedDataDriverTest','certifiedDataReplaysOnceBeforeFreshBarrier','v53-native-dispatch'),
    'data-applied':('V53CarriedDataDriverTest','appliedDataReplaysOnceBeforeFreshBarrier','v53-native-dispatch'),
}
PROCESS_CASES={}
for label,cut,suffix in (
    ('cleanup','NATIVE_RETIREMENT_CERTIFICATE_RETAINED','DuringCarriedCertificateCleanup'),
    ('accept-rename','ACCEPT_RENAMED','AfterCarriedAcceptRename'),
    ('proof-rename','PROOF_RENAMED','AfterCarriedProofRename'),
    ('application-force','APPLY_ACK_DIRECTORY_FORCED','AfterCarriedApplicationForce')):
    for mode in ('halt','kill'):
        case='data-applied-'+label+'-'+mode
        PROCESS_CASES[case]=dict(mode=mode,cut=cut)
        METHODS[case]=('V53NativeCarriedProcessTest',mode+suffix,'v53-native-carried-process')
CASES=tuple(METHODS)


def selected(case):
    need(type(case) is str and case in METHODS,'carried DATA history exact case');return METHODS[case]


def command(case):
    cls,method,_=selected(case)
    return ['-o','-B','-ntp','-f','reactor/pom.xml','-pl','../'+h.MODULE,'-am',
            '-Dsurefire.failIfNoSpecifiedTests=false','-Dtest='+cls+'#'+method,
            *(['-Dv53.transport.diagnostics=true'] if case not in PROCESS_CASES else []),'test']


def junit(reports,case):
    cls,method,_=selected(case);cls=PACKAGE+cls;paths=sorted(Path(reports).glob('TEST-*.xml'))
    need(len(paths)==1,'carried DATA history exact JUnit report')
    suite=ET.fromstring(h.snapshot.s.regular(paths[0],8*h.snapshot.MIB));tests=suite.findall('testcase')
    need(suite.get('name')==cls and suite.get('tests')=='1' and len(tests)==1 and
         all(suite.get(k)=='0' for k in ('failures','errors','skipped')) and
         tests[0].get('classname')==cls and tests[0].get('name')==method and
         not any(v.tag in ('failure','error','skipped') or v.tag.startswith(('flaky','rerun')) for v in suite.iter()),
         'carried DATA history exact unretried passing test')
    return dict(className=cls,method=method,tests=1,failures=0,errors=0,skipped=0,retries=0)


def phase(case):
    selected(case);return 'APPLIED' if case in PROCESS_CASES else case.removeprefix('data-').upper()


def histories(case):selected(case);return [case]


def negative_cases(case):
    selected(case)
    if case in PROCESS_CASES:
        return [dict(suite='process-history',case=name,status='REJECTED',reason=reason)
                for name,reason in recovery.negative_cases(PROCESS_CASES[case]['cut']).items()]
    return [dict(suite='physical',case=name,status='REJECTED',reason=reason)
            for name,reason in carried.negative_cases(phase(case),confirmed_retention=True,kind='DATA').items()]


def collect(raw,case):
    selected(case);raw=Path(raw);before=h.inventory(raw)
    need((raw/'carried-phase.txt').read_text()==phase(case),'carried DATA exact carried phase')
    need((raw/'carried-kind.txt').read_bytes()==b'DATA','carried DATA payload declaration')
    if case in PROCESS_CASES:
        result=read(raw/'process/result.json');recovery.process.children(result)
        need({k:result[k] for k in ('mode','cut')}==PROCESS_CASES[case], 'carried DATA exact process cut/mode')
        need(not (raw/'carried-result.json').exists(),'carried DATA unexpected nonprocess claim')
    else:
        entry=(raw/'entry-1.gsr').read_bytes()
        need(read(raw/'carried-result.json')==dict(status='PASS',carried=h.digest(entry),slots=2,publicReady=False),
             'carried DATA producer scope')
        need(not (raw/'process').exists(),'carried DATA unexpected process claim')
    need(not (raw/'round-result.json').exists(),'carried DATA unexpected lifecycle claim')
    plans={case:h.digest(h.snapshot.s.regular(raw/'original-plan.gsbp',h.snapshot.MIB))}
    need(h.inventory(raw)==before,'carried DATA changed during collection')
    return dict(status='PARTIAL',case=case,collectionComplete=True,nativeHistoryQualified=False,phase3Complete=False,
                scope='original-native-carried-data-collection',plans=plans,inventory=before)


def replay(raw,case):
    selected(case);raw=Path(raw);before=h.inventory(raw)
    value=(recovery.qualify(raw) if case in PROCESS_CASES else carried.qualify(raw,confirmed_retention=True,kind='DATA'))
    need(h.inventory(raw)==before,'carried DATA original changed in reader')
    suite='process-history' if case in PROCESS_CASES else 'physical'
    return dict(original=value['original'],negatives=[dict(suite=suite,**v) for v in value['negatives']],originalPreserved=True)


def capture(output,maven,case,source_from=None):
    selected(case);output=Path(output).absolute()
    need(source_from is None or not output.resolve().is_relative_to(Path(source_from).resolve()),'carried DATA history source separation')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,case=case,status='RUNNING',executionStatus='NOT_RUN',collectionComplete=False,
                 nativeHistoryQualified=False,phase3Complete=False,retries=0)
    try:
        work=output/'workspace';source=h.source_copy(h.ROOT,work) if source_from is None else h.recorded_source(source_from,work)
        h.save(output/'source.json',source);reader=reader_manifest()
        need(all(source['files'].get(k)==v for k,v in reader['files'].items()),'carried DATA history reader belongs to source')
        h.save(output/'toolchain.json',tc.capture(maven,work))
        receipt.update(baseHead=source['head'],sourceSha256=h.digest((output/'source.json').read_bytes()),readerSha256=reader['sha256'],
            toolchainSha256=h.digest((output/'toolchain.json').read_bytes()),command=[maven,*command(case)])
        h.save(output/'receipt.json',receipt)
        execution=h.execute(receipt['command'],work,output/'maven.log',stage='carried-data-'+case)
        h.save(output/'execution.json',execution);receipt['execution']=execution;h.check_source(work,source)
        need(type(execution['exit']) is int and execution['exit']==0,'carried DATA history Maven failed; original retained')
        receipt['junit']=junit(work/h.MODULE/'target/surefire-reports',case);receipt['executionStatus']='PASS'
        h.save(output/'build.json',{name:h.inventory(work/name) for name in BUILDS})
        receipt['buildSha256']=h.digest((output/'build.json').read_bytes())
        roots=list((work/h.MODULE/'target'/selected(case)[2]).iterdir())
        need(len(roots)==1,'carried DATA history exact raw directory');raw=roots[0];receipt['raw']=raw.relative_to(output).as_posix()
        collected=h.execute([sys.executable,'-B','-m','scripts.v53.carried_data_history','collect',str(output/'collection.json'),
            '--case',case,'--raw',str(raw)],work,output/'collection.log',stage='carried-data-collection-'+case)
        h.save(output/'collection-execution.json',collected);receipt['collectionExecution']=collected
        need(type(collected['exit']) is int and collected['exit']==0,'carried DATA history collection failed; original retained')
        need(read(output/'collection.json')==collect(raw,case),'carried DATA history immutable source collection')
        h.check_source(work,source);receipt.update(status='PARTIAL',collectionComplete=True,
            collectionSha256=h.digest((output/'collection.json').read_bytes()))
    except BaseException as error:
        if receipt['executionStatus']=='NOT_RUN':receipt['executionStatus']='FAIL'
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


def check_pins(source,build,toolchain,reader):
    need(all(shared.hash_field(v) for v in (source,build,toolchain,reader)),'carried DATA cohort pinned hashes')
    manifest=reader_manifest();need(manifest['sha256']==reader,'carried DATA cohort pinned reader');return manifest


def member(path,case,source,build,toolchain,reader):
    selected(case);manifest=check_pins(source,build,toolchain,reader);path=Path(path)
    need(path.is_dir() and not path.is_symlink(),'carried DATA cohort producer directory');receipt=read(path/'receipt.json')
    need(type(receipt) is dict and receipt.get('schema')==SCHEMA and receipt.get('case')==case and receipt.get('status')=='PARTIAL'
         and receipt.get('executionStatus')=='PASS' and receipt.get('collectionComplete') is True
         and all(receipt.get(k) is False for k in ('nativeHistoryQualified','phase3Complete'))
         and type(receipt.get('retries')) is int and receipt['retries']==0,'carried DATA cohort successful unretried producer')
    for field,file in (('execution','execution.json'),('collectionExecution','collection-execution.json')):
        value=receipt.get(field)
        need(type(value) is dict and type(value.get('exit')) is int and value['exit']==0
             and h.snapshot.f.canonical(read(path/file))==h.snapshot.f.canonical(value),'carried DATA cohort successful process receipts')
    recorded,_=h.read_recorded_source(path);work=path/'workspace'
    need(receipt.get('sourceSha256')==source==h.digest((path/'source.json').read_bytes()) and receipt.get('baseHead')==recorded['head'],
         'carried DATA cohort exact producer source')
    need(receipt.get('readerSha256')==reader and all(recorded['files'].get(k)==v for k,v in manifest['files'].items()),
         'carried DATA cohort reader belongs to producer')
    args=receipt.get('command');wanted=command(case)
    need(type(args) is list and len(args)==len(wanted)+1 and type(args[0]) is str and Path(args[0]).name=='mvn'
         and args[1:]==wanted,'carried DATA cohort exact complete command')
    for name in (*BUILDS,h.MODULE+'/target/surefire-reports'):
        need(all((work/p).is_dir() and not (work/p).is_symlink() for p in (Path(name),*Path(name).parents)),
             'carried DATA cohort linked generated parent')
    need(h.snapshot.f.canonical(receipt.get('junit'))==h.snapshot.f.canonical(junit(work/h.MODULE/'target/surefire-reports',case)),
         'carried DATA cohort exact JUnit receipt')
    classes=read(path/'build.json')
    need(type(classes) is dict and set(classes)==set(BUILDS) and receipt.get('buildSha256')==build==h.digest((path/'build.json').read_bytes()),
         'carried DATA cohort exact build manifest')
    for name in BUILDS:need(h.inventory(work/name)==classes[name],'carried DATA cohort original compiled bytes')
    tc.validate(read(path/'toolchain.json'))
    need(receipt.get('toolchainSha256')==h.digest((path/'toolchain.json').read_bytes()) and tc.pin((path/'toolchain.json').read_bytes())==toolchain,
         'carried DATA cohort portable toolchain')
    name=receipt.get('raw');base='workspace/'+h.MODULE+'/target/'+selected(case)[2]
    need(type(name) is str and re.fullmatch(base+r'/run-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',name),
         'carried DATA cohort exact raw path')
    need(all((path/p).is_dir() and not (path/p).is_symlink() for p in Path(name).parents),'carried DATA cohort linked raw parent')
    raw=path/name;need({v.name for v in raw.parent.iterdir()}=={raw.name},'carried DATA cohort exactly one original run')
    collection=collect(raw,case)
    need(receipt.get('collectionSha256')==h.digest((path/'collection.json').read_bytes()) and
         h.snapshot.f.canonical(read(path/'collection.json'))==h.snapshot.f.canonical(collection),
         'carried DATA cohort independent original collection')
    return dict(raw=raw,plans=collection['plans'],inventory=collection['inventory'],receiptSha256=h.digest((path/'receipt.json').read_bytes()))


def check_process_result(original,case):
    """Enforce the owning reader's result shape; this does not replay raw bytes."""
    need(type(original) is dict, 'carried DATA process original result')
    process=original.get('process');network=original.get('network')
    need(type(process) is dict and type(network) is dict, 'carried DATA process original result')
    fixed=dict(status='PASS',scope='native-carried-whole-group-process-history',originalFirst=True,
        process=process,network=network,fullWireReplay=True,processHistoryQualified=True,
        phase3Complete=False,cohortAdmitted=False,powerLoss=False,publicRuntime=False)
    exact=lambda actual,expected: h.snapshot.f.canonical(actual)==h.snapshot.f.canonical(expected)
    need(exact(original,fixed),'carried DATA process original scope')
    messages=process.get('childMessages')
    need(type(messages) is list and len(messages)==2 and all(type(v) is int and 0<v<=32768 for v in messages),
         'carried DATA process child observations')
    physical=dict(status='PARTIAL',scope='native-carried-whole-group-physical',physicalReplay=True,
        cut=PROCESS_CASES[case]['cut'],campaigns=2,dataApplications=1,publishedSlots=2,
        fullWireReplay=False,processHistoryQualified=False,phase3Complete=False)
    expected=dict(status='PARTIAL',scope='native-carried-whole-group-physical-and-process',componentChecks='PASS',
        originalFirst=True,**PROCESS_CASES[case],freshGroupJvms=2,survivingOriginalOwners=0,childMessages=messages,
        clientCalls=0,physical=physical,processObservations=True,fullWireReplay=False,processHistoryQualified=False,
        cohortAdmitted=False,powerLoss=False,phase3Complete=False)
    need(exact(process,expected),'carried DATA complete original process result')
    need(set(network)=={'fullWireReplay','phases','exchanges','requests','silent','silentRequests','background'} and
         network['fullWireReplay'] is True,'carried DATA complete process network result')
    count=lambda v:type(v) is int and 0<=v<=32768
    need(all(count(network[k]) for k in ('exchanges','requests','silentRequests')) and
         0<network['exchanges']<=network['requests'],'carried DATA process network counts')
    phases=network['phases'];background=network['background'];silent=network['silent']
    need(type(phases) is list and len(phases)==5 and all(type(v) is dict for v in phases),
         'carried DATA complete five process phases')
    for i,row in enumerate(phases):
        keys={'exchanges','transfers','unusedIncompleteTransfers'}
        if i in (0,2):
            keys.add('voters')
            need(row.get('voters') in (['node-1','node-2'],['node-1','node-3']),'carried DATA process selected pair')
        elif i in (3,4):
            keys|={'index','recordingQuorums'}
            need(type(row.get('index')) is int and row['index']==i-2 and
                 type(row.get('recordingQuorums')) is int and row['recordingQuorums']==1,'carried DATA process publication quorum')
        need(set(row)==keys and all(count(row[k]) for k in ('exchanges','transfers','unusedIncompleteTransfers')) and
             row['unusedIncompleteTransfers']<=row['transfers']<=row['exchanges'] and
             (i==1 or row['exchanges']>0),'carried DATA process phase counts')
    need(type(background) is dict and set(background)=={'samples','exchanges','contactOnly','silentRequests'} and
         background['contactOnly'] is True and all(count(background[k]) for k in ('samples','exchanges','silentRequests')) and
         sum(v['exchanges'] for v in phases)+background['exchanges']==network['exchanges'],
         'carried DATA process heartbeat coverage')
    need(type(silent) is list and all(type(v) is dict and set(v)=={'index','kind','attempts'} and
         type(v['index']) is int and v['index'] in (1,2) and v['kind'] in ('FUTURE_RETENTION_INTENT','CHECKPOINT_ACK_LOOKUP') and
         type(v['attempts']) is int and 1<=v['attempts']<=3 for v in silent) and
         sum(v['attempts'] for v in silent)==network['silentRequests'], 'carried DATA process silent attempts')


def check_result(value,case):
    selected(case)
    need(type(value) is dict and set(value)=={'original','negatives','originalPreserved'} and value['originalPreserved'] is True,
         'carried DATA preserved original replay')
    original=value['original']
    if case in PROCESS_CASES:
        check_process_result(original,case)
        need(value['negatives']==negative_cases(case),'carried DATA exact negative vector')
        return
    keys={'status','phase','slots','voters','selected','transfers','automaticElection','publicReady','phase3Complete',
          'retentionSemantics','carriedKind','applicationSequence','lastDataIndex'}
    need(type(original) is dict and set(original)==keys and original['status']=='PASS' and original['phase']==phase(case) and
         original['retentionSemantics']=='original-copy-confirmation' and original['carriedKind']=='DATA' and
         all(original[k] is False for k in ('automaticElection','publicReady','phase3Complete')) and
         all(type(original[k]) is int for k in ('slots','voters','selected','transfers','applicationSequence','lastDataIndex')) and
         original['slots']==original['selected']==2 and original['voters']==3 and original['transfers']>0 and
         original['applicationSequence']==original['lastDataIndex']==1,'carried DATA complete physical result')
    need(value['negatives']==negative_cases(case),'carried DATA exact negative vector')


def qualify_member(path,case,*pins):
    before=member(path,case,*pins);result=replay(before['raw'],case);check_result(result,case)
    need(member(path,case,*pins)==before,'carried DATA cohort changed during replay');check_pins(*pins)
    return dict(case=case,status='PASS',plans=before['plans'],producerReceiptSha256=before['receiptSha256'],qualification=result,
                **dict(zip(('sourceSha256','buildSha256','toolchainSha256','readerSha256'),pins)),phase3Complete=False)


def aggregate(paths,*pins,workers=1,progress=None):
    check_pins(*pins);need(type(workers) is int and 1<=workers<=4,'carried DATA cohort replay workers')
    need(type(paths) is dict and set(paths)==set(CASES),'carried DATA cohort complete declared histories')
    need(len({Path(v).resolve() for v in paths.values()})==len(CASES),'carried DATA cohort distinct producers')
    originals={k:member(paths[k],k,*pins) for k in CASES};plans=[v for k in CASES for v in originals[k]['plans'].values()]
    need(len(plans)==len(set(plans))==len(CASES),'carried DATA cohort distinct complete original histories')
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
            if not done and progress:progress(dict(stage='carried-data-replay',completed=len(outcomes),total=len(CASES)))
    for k in CASES:need(member(paths[k],k,*pins)==originals[k],'carried DATA cohort original changed before aggregate')
    check_pins(*pins);passed=all(outcomes[k]['status']=='PASS' for k in CASES)
    return dict(schema=COHORT,status='PASS' if passed else 'FAIL',scope='complete-declared-native-carried-data-phases',
        cases=[outcomes[k] for k in CASES],wholeOwnershipHistories=len(CASES),nativeCases=len(CASES),processCases=len(PROCESS_CASES),
        negativeCases=sum(len(v.get('qualification',{}).get('negatives',[])) for v in outcomes.values()),
        **dict(zip(('sourceSha256','buildSha256','toolchainSha256','readerSha256'),pins)),declaredCarriedDataHistoriesQualified=passed,
        declaredWholeGroupCarriedRecoveryQualified=passed,processDeathQualified=False,
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
        print(json.dumps(dict(cases=[dict(case=k,command=command(k),histories=histories(k),negatives=len(negative_cases(k))) for k in CASES],
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
            with heartbeat('carried-data-'+a.command,getattr(a,'case',None)),(output/'progress.jsonl').open('x') as stream:
                def progress(v):stream.write(json.dumps(v,sort_keys=True)+'\n');stream.flush();print(json.dumps(v),file=sys.stderr,flush=True)
                if a.command=='member':result=qualify_member(a.producer,a.case,*pins)
                else:
                    inputs=Path(a.inputs);need(inputs.is_dir() and not inputs.is_symlink() and {v.name for v in inputs.iterdir()}==set(CASES),
                        'carried DATA cohort exact input directories')
                    result=aggregate({k:inputs/k for k in CASES},*pins,workers=a.workers,progress=progress)
            need(result['status']=='PASS','carried DATA cohort failed originals')
        except BaseException as error:result.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
        finally:h.save(output/'receipt.json',result)
    print(json.dumps(dict(status=result['status'],phase3Complete=False,output=a.output),sort_keys=True))


if __name__=='__main__':main()
