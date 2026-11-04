"""Capture two complete native carried transition histories without replaying a client.

Old INTENT/FINAL votes, new-ballot completion and the fresh stable
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
from . import carried_transition_evidence as physical
from . import carried_transition_network as network
from . import carried_transition_exports as exports
from . import carried_transition_retention as retention
from . import carried_transition_retirement as retirement
from . import carried_transition_prefixes as prefixes

need=h.need;read=shared.read;reader_manifest=shared.reader_manifest;BUILDS=shared.BUILDS
SCHEMA='gse-v53-carried-transition-history-execution-v1'
COHORT='gse-v53-carried-transition-history-cohort-v1'
PACKAGE='io.github.patricklfdm.generalsearch.replication.'
METHODS={
    'intent':('V53CarriedTransitionDriverTest','carriedIntentFinishesBeforeFreshStableBarrier','v53-native-dispatch'),
    'final':('V53CarriedTransitionDriverTest','carriedFinalFinishesBeforeFreshStableBarrier','v53-native-dispatch'),
}
CASES=tuple(METHODS)


def selected(case):
    need(type(case) is str and case in METHODS,'carried transition history exact case');return METHODS[case]


def command(case):
    cls,method,_=selected(case)
    return ['-o','-B','-ntp','-f','reactor/pom.xml','-pl','../'+h.MODULE,'-am',
            '-Dsurefire.failIfNoSpecifiedTests=false','-Dtest='+cls+'#'+method,'-Dv53.carried.retirement.captures=true','test']


def junit(reports,case):
    cls,method,_=selected(case);cls=PACKAGE+cls;paths=sorted(Path(reports).glob('TEST-*.xml'))
    need(len(paths)==1,'carried transition history exact JUnit report')
    suite=ET.fromstring(h.snapshot.s.regular(paths[0],8*h.snapshot.MIB));tests=suite.findall('testcase')
    need(suite.get('name')==cls and suite.get('tests')=='1' and len(tests)==1 and
         all(suite.get(k)=='0' for k in ('failures','errors','skipped')) and
         tests[0].get('classname')==cls and tests[0].get('name')==method and
         not any(v.tag in ('failure','error','skipped') or v.tag.startswith(('flaky','rerun')) for v in suite.iter()),
         'carried transition history exact unretried passing test')
    return dict(className=cls,method=method,tests=1,failures=0,errors=0,skipped=0,retries=0)


def phase(case):selected(case);return case.upper()


def histories(case):selected(case);return [case]


STAGES=('physical','network','exports','retention','retirement','prefixes')


def negative_cases(case):
    kind=phase(case);rows=[]
    for suite,values in (('physical',physical.negative_cases(kind)),('network',network.NEGATIVES),('exports',exports.NEGATIVES)):
        for name,reason in values.items():
            row=dict(suite=suite,case=name,status='REJECTED',reason=reason)
            if suite=='exports':row['networkPrecondition']='PASS'
            rows.append(row)
    for stage,values in sorted(retention.NEGATIVES.items()):
        rows.extend(dict(suite='retention',stage=stage,case=name,status='REJECTED',reason=reason,
                         originalFilesAndOtherObservationsUnchanged=True) for name,reason in sorted(values.items()))
    rows.extend(dict(suite='retirement',case=name,status='REJECTED',reason=reason,retentionReplay='PASS',
                     originalFilesAndOtherObservationsUnchanged=True) for name,reason in sorted(retirement.NEGATIVES.items()))
    rows.extend(dict(suite='prefixes',case=name,status='REJECTED',reason=reason) for name,reason in prefixes.NEGATIVES.items())
    return rows


def sidecar(raw):
    raw=Path(raw);return raw.with_name('retirement-captures-'+raw.name)


def collect(raw,case):
    kind=phase(case);raw=Path(raw);before=h.inventory(raw);index,count,_=physical.shape(kind)
    entry=h.snapshot.s.regular(raw/f'entry-{index}.gsr',h.snapshot.MIB)
    expected=dict(status='PASS',kind=kind,oldIndex=index,oldEntry=h.digest(entry),activations=count,
                  internalReady=True,publicReady=False,originalBudgetSeconds=600)
    need(h.snapshot.f.canonical(read(raw/'carried-transition-result.json'))==h.snapshot.f.canonical(expected),'carried transition producer scope')
    need(not (raw/'transition-round-result.json').exists(),'carried transition unexpected ordinary result')
    copies,captured=prefixes.collect(raw,sidecar(raw),kind)
    plans={case:h.digest(h.snapshot.s.regular(raw/'original-plan.gsbp',h.snapshot.MIB))}
    need(h.inventory(raw)==before,'carried transition changed during collection')
    return dict(status='PARTIAL',case=case,collectionComplete=True,nativeHistoryQualified=False,phase3Complete=False,
                scope='original-native-carried-transition-collection',plans=plans,inventory=before,
                captureInventory=captured,capturedPrefixes=len(copies))


def original_chain(original):
    chain={'prefixes':original};value=original
    for name in ('retirement','retention','exports','network'):
        need(type(value) is dict and type(value.get('precondition')) is dict,'carried transition complete original chain')
        value=value['precondition'];chain[name]=value
    need(type(value.get('physical')) is dict,'carried transition physical chain');chain['physical']=value['physical']
    return chain


def replay(raw,case):
    kind=phase(case);raw=Path(raw);before=collect(raw,case)
    # The complete unmodified composition must pass before ANY mutation runs.
    original=prefixes.validate(raw,sidecar(raw),kind);expected=original_chain(original);rows=[]
    for stage,reader in (('physical',physical),('network',network),('exports',exports),('retention',retention),('retirement',retirement),('prefixes',prefixes)):
        value=reader.qualify(raw,sidecar(raw),kind) if stage=='prefixes' else reader.qualify(raw,kind)
        need(h.snapshot.f.canonical(value['original'])==h.snapshot.f.canonical(expected[stage]),'carried transition original stage drift: '+stage)
        rows.extend(dict(suite=stage,**v) for v in value['negatives'])
        print(json.dumps(dict(stage='carried-transition-qualified',case=case,suite=stage,negatives=len(value['negatives']))),file=sys.stderr,flush=True)
    need(collect(raw,case)==before,'carried transition original or captures changed in reader')
    result=dict(original=original,negatives=rows,originalPreserved=True);check_result(result,case);return result


def capture(output,maven,case,source_from=None):
    selected(case);output=Path(output).absolute()
    need(source_from is None or not output.resolve().is_relative_to(Path(source_from).resolve()),'carried transition history source separation')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,case=case,status='RUNNING',executionStatus='NOT_RUN',collectionComplete=False,
                 nativeHistoryQualified=False,phase3Complete=False,retries=0)
    try:
        work=output/'workspace';source=h.source_copy(h.ROOT,work) if source_from is None else h.recorded_source(source_from,work)
        h.save(output/'source.json',source);reader=reader_manifest()
        need(all(source['files'].get(k)==v for k,v in reader['files'].items()),'carried transition history reader belongs to source')
        h.save(output/'toolchain.json',tc.capture(maven,work))
        receipt.update(baseHead=source['head'],sourceSha256=h.digest((output/'source.json').read_bytes()),readerSha256=reader['sha256'],
            toolchainSha256=h.digest((output/'toolchain.json').read_bytes()),command=[maven,*command(case)])
        h.save(output/'receipt.json',receipt)
        execution=h.execute(receipt['command'],work,output/'maven.log',stage='carried-transition-'+case)
        h.save(output/'execution.json',execution);receipt['execution']=execution;h.check_source(work,source)
        need(type(execution['exit']) is int and execution['exit']==0,'carried transition history Maven failed; original retained')
        receipt['junit']=junit(work/h.MODULE/'target/surefire-reports',case);receipt['executionStatus']='PASS'
        h.save(output/'build.json',{name:h.inventory(work/name) for name in BUILDS})
        receipt['buildSha256']=h.digest((output/'build.json').read_bytes())
        roots=list((work/h.MODULE/'target'/selected(case)[2]).glob('run-*'))
        need(len(roots)==1,'carried transition history exact raw directory');raw=roots[0];receipt['raw']=raw.relative_to(output).as_posix()
        need({v.name for v in raw.parent.iterdir()}=={raw.name,sidecar(raw).name},'carried transition history exact original and captures')
        receipt['captures']=sidecar(raw).relative_to(output).as_posix()
        collected=h.execute([sys.executable,'-B','-m','scripts.v53.carried_transition_history','collect',str(output/'collection.json'),
            '--case',case,'--raw',str(raw)],work,output/'collection.log',stage='carried-transition-collection-'+case)
        h.save(output/'collection-execution.json',collected);receipt['collectionExecution']=collected
        need(type(collected['exit']) is int and collected['exit']==0,'carried transition history collection failed; original retained')
        need(read(output/'collection.json')==collect(raw,case),'carried transition history immutable source collection')
        h.check_source(work,source);receipt.update(status='PARTIAL',collectionComplete=True,
            collectionSha256=h.digest((output/'collection.json').read_bytes()))
    except BaseException as error:
        if receipt['executionStatus']=='NOT_RUN':receipt['executionStatus']='FAIL'
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


def check_pins(source,build,toolchain,reader):
    need(all(shared.hash_field(v) for v in (source,build,toolchain,reader)),'carried transition cohort pinned hashes')
    manifest=reader_manifest();need(manifest['sha256']==reader,'carried transition cohort pinned reader');return manifest


def member(path,case,source,build,toolchain,reader):
    selected(case);manifest=check_pins(source,build,toolchain,reader);path=Path(path)
    need(path.is_dir() and not path.is_symlink(),'carried transition cohort producer directory');receipt=read(path/'receipt.json')
    need(type(receipt) is dict and receipt.get('schema')==SCHEMA and receipt.get('case')==case and receipt.get('status')=='PARTIAL'
         and receipt.get('executionStatus')=='PASS' and receipt.get('collectionComplete') is True
         and all(receipt.get(k) is False for k in ('nativeHistoryQualified','phase3Complete'))
         and type(receipt.get('retries')) is int and receipt['retries']==0,'carried transition cohort successful unretried producer')
    for field,file in (('execution','execution.json'),('collectionExecution','collection-execution.json')):
        value=receipt.get(field)
        need(type(value) is dict and type(value.get('exit')) is int and value['exit']==0
             and h.snapshot.f.canonical(read(path/file))==h.snapshot.f.canonical(value),'carried transition cohort successful process receipts')
    recorded,_=h.read_recorded_source(path);work=path/'workspace'
    need(receipt.get('sourceSha256')==source==h.digest((path/'source.json').read_bytes()) and receipt.get('baseHead')==recorded['head'],
         'carried transition cohort exact producer source')
    need(receipt.get('readerSha256')==reader and all(recorded['files'].get(k)==v for k,v in manifest['files'].items()),
         'carried transition cohort reader belongs to producer')
    args=receipt.get('command');wanted=command(case)
    need(type(args) is list and len(args)==len(wanted)+1 and type(args[0]) is str and Path(args[0]).name=='mvn'
         and args[1:]==wanted,'carried transition cohort exact complete command')
    for name in (*BUILDS,h.MODULE+'/target/surefire-reports'):
        need(all((work/p).is_dir() and not (work/p).is_symlink() for p in (Path(name),*Path(name).parents)),
             'carried transition cohort linked generated parent')
    need(h.snapshot.f.canonical(receipt.get('junit'))==h.snapshot.f.canonical(junit(work/h.MODULE/'target/surefire-reports',case)),
         'carried transition cohort exact JUnit receipt')
    classes=read(path/'build.json')
    need(type(classes) is dict and set(classes)==set(BUILDS) and receipt.get('buildSha256')==build==h.digest((path/'build.json').read_bytes()),
         'carried transition cohort exact build manifest')
    for name in BUILDS:need(h.inventory(work/name)==classes[name],'carried transition cohort original compiled bytes')
    tc.validate(read(path/'toolchain.json'))
    need(receipt.get('toolchainSha256')==h.digest((path/'toolchain.json').read_bytes()) and tc.pin((path/'toolchain.json').read_bytes())==toolchain,
         'carried transition cohort portable toolchain')
    name=receipt.get('raw');base='workspace/'+h.MODULE+'/target/'+selected(case)[2]
    need(type(name) is str and re.fullmatch(base+r'/run-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',name),
         'carried transition cohort exact raw path')
    need(all((path/p).is_dir() and not (path/p).is_symlink() for p in Path(name).parents),'carried transition cohort linked raw parent')
    raw=path/name;need({v.name for v in raw.parent.iterdir()}=={raw.name,sidecar(raw).name},'carried transition cohort exactly one original run and captures')
    need(receipt.get('captures')==sidecar(raw).relative_to(path).as_posix(),'carried transition cohort exact captures path')
    collection=collect(raw,case)
    need(receipt.get('collectionSha256')==h.digest((path/'collection.json').read_bytes()) and
         h.snapshot.f.canonical(read(path/'collection.json'))==h.snapshot.f.canonical(collection),
         'carried transition cohort independent original collection')
    return dict(raw=raw,plans=collection['plans'],inventory=collection['inventory'],captureInventory=collection['captureInventory'],receiptSha256=h.digest((path/'receipt.json').read_bytes()))


def check_result(value,case):
    kind=phase(case);index,count,_=physical.shape(kind)
    need(type(value) is dict and set(value)=={'original','negatives','originalPreserved'} and value['originalPreserved'] is True,
         'carried transition preserved original replay')
    chain=original_chain(value['original']);original=value['original']
    keys={'status','profile','kind','generations','sources','borrowedGenerations','generationMembers','callbacks','physicalImagePeak',
          'transactionChainSha256','peerPrecondition','completeObservedRetirementCallbacksQualified','transientRetirementBytesQualified',
          'capturedPrefixes','processDeathQualified','phase3Complete','publicReady','sourceCohortQualified','precondition'}
    need(set(original)==keys and original['profile']==kind and original['sourceCohortQualified'] is False,
         'carried transition complete prefix result')
    for name,row in chain.items():
        need(type(row) is dict and row.get('kind')==kind and row.get('status')==('PASS' if name=='physical' else 'PARTIAL') and
             all(row.get(k) is False for k in ('phase3Complete','publicReady','processDeathQualified')),'carried transition stage scope: '+name)
    for stage,fields in {'physical':('physicalQualified','publicationBoundaryQualified','internalReady','originalEntryPreserved'),
                         'network':('observedAttemptsQualified','durableActivationAndSlotACKsQualified'),
                         'exports':('observedExportAuthorityQualified','completeCopyFloorLifetimesQualified'),
                         'retention':('retentionRevisionCompositionQualified',),
                         'retirement':('completeObservedRetirementCallbacksQualified',),
                         'prefixes':('completeObservedRetirementCallbacksQualified','transientRetirementBytesQualified')}.items():
        need(all(chain[stage].get(k) is True for k in fields),'carried transition incomplete stage: '+stage)
    need(type(chain['physical'].get('activations')) is int and chain['physical']['activations']==count and
         h.snapshot.f.canonical(chain['physical'].get('publishedSlots'))==h.snapshot.f.canonical(list(range(index,8))) and
         shared.hash_field(chain['physical'].get('oldEntry')),'carried transition exact carried slots')
    for field in ('generations','sources','borrowedGenerations','generationMembers','callbacks','physicalImagePeak','capturedPrefixes'):
        need(type(original.get(field)) is int and original[field]>0,'carried transition prefix count')
    need(original['capturedPrefixes']==original['callbacks']<=prefixes.p.MAXIMUM_CAPTURES and original['physicalImagePeak']<=7 and
         shared.hash_field(original['transactionChainSha256']),'carried transition bounded prefix completion')
    need(all(h.snapshot.f.canonical(original[k])==h.snapshot.f.canonical(v) for k,v in chain['retirement'].items()
             if k not in ('precondition','transientRetirementBytesQualified')),'carried transition same retirement derivation')
    need(h.snapshot.f.canonical(value['negatives'])==h.snapshot.f.canonical(negative_cases(case)),'carried transition exact negative vector')


def qualify_member(path,case,*pins):
    before=member(path,case,*pins);result=replay(before['raw'],case);check_result(result,case)
    need(member(path,case,*pins)==before,'carried transition cohort changed during replay');check_pins(*pins)
    return dict(case=case,status='PASS',plans=before['plans'],producerReceiptSha256=before['receiptSha256'],qualification=result,
                **dict(zip(('sourceSha256','buildSha256','toolchainSha256','readerSha256'),pins)),phase3Complete=False)


def aggregate(paths,*pins,workers=1,progress=None):
    check_pins(*pins);need(type(workers) is int and 1<=workers<=4,'carried transition cohort replay workers')
    need(type(paths) is dict and set(paths)==set(CASES),'carried transition cohort complete two histories')
    need(len({Path(v).resolve() for v in paths.values()})==len(CASES),'carried transition cohort distinct producers')
    originals={k:member(paths[k],k,*pins) for k in CASES};plans=[v for k in CASES for v in originals[k]['plans'].values()]
    need(len(plans)==len(set(plans))==len(CASES),'carried transition cohort distinct complete original histories')
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
            if not done and progress:progress(dict(stage='carried-transition-replay',completed=len(outcomes),total=len(CASES)))
    for k in CASES:need(member(paths[k],k,*pins)==originals[k],'carried transition cohort original changed before aggregate')
    check_pins(*pins);passed=all(outcomes[k]['status']=='PASS' for k in CASES)
    return dict(schema=COHORT,status='PASS' if passed else 'FAIL',scope='complete-declared-native-carried-transition-phases',
        cases=[outcomes[k] for k in CASES],wholeOwnershipHistories=len(CASES),nativeCases=len(CASES),
        negativeCases=sum(len(v.get('qualification',{}).get('negatives',[])) for v in outcomes.values()),
        **dict(zip(('sourceSha256','buildSha256','toolchainSha256','readerSha256'),pins)),declaredCarriedTransitionHistoriesQualified=passed,processDeathQualified=False,
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
            with heartbeat('carried-transition-'+a.command,getattr(a,'case',None)),(output/'progress.jsonl').open('x') as stream:
                def progress(v):stream.write(json.dumps(v,sort_keys=True)+'\n');stream.flush();print(json.dumps(v),file=sys.stderr,flush=True)
                if a.command=='member':result=qualify_member(a.producer,a.case,*pins)
                else:
                    inputs=Path(a.inputs);need(inputs.is_dir() and not inputs.is_symlink() and {v.name for v in inputs.iterdir()}==set(CASES),
                        'carried transition cohort exact input directories')
                    result=aggregate({k:inputs/k for k in CASES},*pins,workers=a.workers,progress=progress)
            need(result['status']=='PASS','carried transition cohort failed originals')
        except BaseException as error:result.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
        finally:h.save(output/'receipt.json',result)
    print(json.dumps(dict(status=result['status'],phase3Complete=False,output=a.output),sort_keys=True))


if __name__=='__main__':main()
