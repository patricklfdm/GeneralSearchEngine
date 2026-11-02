"""Capture and admit all seven existing native carried/stable round histories.

Prior vote completion and fresh barrier remain in one original. Collection is
not acceptance. Physical and lifecycle readers replay originals before exact
negative vectors; no native retries, conditional bootstrap or budget overrides.
"""
import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import json
from pathlib import Path
import re
import shutil
import tempfile
import sys
import xml.etree.ElementTree as ET

from . import joining_history_run as h
from . import remove_process_matrix as shared
from . import process_toolchain as tc
from . import carried_slot_evidence as carried
from . import round_driver_evidence as rounds

dispatch=carried.d

need=h.need;read=shared.read;reader_manifest=shared.reader_manifest;BUILDS=shared.BUILDS
SCHEMA='gse-v53-round-history-execution-v1'
COHORT='gse-v53-round-history-cohort-v1'
PACKAGE='io.github.patricklfdm.generalsearch.replication.'
METHODS={
    'slot-accept':('V53CarriedSlotDriverTest','inheritedAcceptReacceptsBeforeFloorAndFreshBarrier','v53-native-dispatch'),
    'slot-proof':('V53CarriedSlotDriverTest','inheritedProofReacceptsBeforeFloorAndFreshBarrier','v53-native-dispatch'),
    'slot-certificate':('V53CarriedSlotDriverTest','inheritedCertificateReacceptsBeforeFloorAndFreshBarrier','v53-native-dispatch'),
    'slot-applied':('V53CarriedSlotDriverTest','inheritedAppliedCertificateReacceptsBeforeFloorAndFreshBarrier','v53-native-dispatch'),
    'round-stable':('V53RoundDriverTest','activationFreshBarrierAndSequentialDataHaveOneGuardedOwner','v53-native-dispatch'),
    'round-discovered':('V53RoundDriverTest','discoveredStartScansBeforeFreshActivationAndBarrier','v53-native-dispatch'),
    'round-carried':('V53RoundDriverTest','retainedAppliedEntryCompletesBeforeFreshReadyBarrier','v53-native-dispatch'),
}
CASES=tuple(METHODS)


def selected(case):
    need(type(case) is str and case in METHODS,'round history exact case');return METHODS[case]


def command(case):
    cls,method,_=selected(case)
    return ['-o','-B','-ntp','-f','reactor/pom.xml','-pl','../'+h.MODULE,'-am',
            '-Dsurefire.failIfNoSpecifiedTests=false','-Dtest='+cls+'#'+method,'test']


def junit(reports,case):
    cls,method,_=selected(case);cls=PACKAGE+cls;paths=sorted(Path(reports).glob('TEST-*.xml'))
    need(len(paths)==1,'round history exact JUnit report')
    suite=ET.fromstring(h.snapshot.s.regular(paths[0],8*h.snapshot.MIB));tests=suite.findall('testcase')
    need(suite.get('name')==cls and suite.get('tests')=='1' and len(tests)==1 and
         all(suite.get(k)=='0' for k in ('failures','errors','skipped')) and
         tests[0].get('classname')==cls and tests[0].get('name')==method and
         not any(v.tag in ('failure','error','skipped') or v.tag.startswith(('flaky','rerun')) for v in suite.iter()),
         'round history exact unretried passing test')
    return dict(className=cls,method=method,tests=1,failures=0,errors=0,skipped=0,retries=0)


def phase(case):
    selected(case);return case.removeprefix('slot-').upper() if case.startswith('slot-') else 'APPLIED' if case=='round-carried' else None


def histories(case):selected(case);return [case]


def negative_cases(case):
    selected(case);old=phase(case)
    physical=dict(carried.NEGATIVES,**dispatch.OBSERVATION_NEGATIVES,**carried.retirement.NEGATIVES) if old else dict(dispatch.NEGATIVES,**dispatch.OBSERVATION_NEGATIVES)
    if case=='round-discovered':physical=dict(dispatch.NEGATIVES,**dispatch.DISCOVERY_NEGATIVES,**dispatch.OBSERVATION_NEGATIVES)
    if not old:physical.update(dispatch.PRECOMMAND_NEGATIVES)
    rows=[dict(suite='physical',case=k,status='REJECTED',reason=v.format(phase=(old or '').lower())) for k,v in physical.items()]
    if case.startswith('round-'):
        lifecycle=dict(rounds.NEGATIVES,**dispatch.OBSERVATION_NEGATIVES)
        if old:lifecycle.update(carried.retirement.NEGATIVES)
        rows += [dict(suite='lifecycle',case=k,status='REJECTED',reason=v) for k,v in lifecycle.items()]
    return rows


def collect(raw,case):
    selected(case);raw=Path(raw);before=h.inventory(raw);old=phase(case)
    if old:
        need(h.snapshot.s.regular(raw/'carried-phase.txt',32).decode()==old,'round history exact carried phase')
        expected=dict(status='PASS',carried=h.digest(h.snapshot.s.regular(raw/'entry-1.gsr',8192)),slots=2,publicReady=False)
        need(h.snapshot.f.canonical(read(raw/'carried-result.json'))==h.snapshot.f.canonical(expected),'round history carried producer scope')
    else:
        need(h.snapshot.f.canonical(read(raw/'result.json'))==h.snapshot.f.canonical(dict(status='PASS',slots=2,network=True,autonomous=False)),
             'round history stable producer scope')
    if case.startswith('round-'):
        expected=dict(status='PASS',mode='carried-applied' if old else 'stable',internalReady=True,publicReady=False)
        need(h.snapshot.f.canonical(read(raw/'round-result.json'))==h.snapshot.f.canonical(expected),'round history lifecycle producer scope')
    else:need(not (raw/'round-result.json').exists(),'round history unexpected lifecycle claim')
    plans={case:h.digest(h.snapshot.s.regular(raw/'original-plan.gsbp',h.snapshot.MIB))}
    need(h.inventory(raw)==before,'round history changed during collection')
    return dict(status='PARTIAL',case=case,collectionComplete=True,nativeHistoryQualified=False,phase3Complete=False,
                scope='original-native-round-collection',plans=plans,inventory=before)


def replay(raw,case):
    selected(case);raw=Path(raw);before=h.inventory(raw);old=phase(case);options=dict(confirmed_retention=True)
    if case=='round-discovered':options['discovery']=True
    reader=carried if old else dispatch
    if case.startswith('round-'):
        lifecycle=rounds.qualify(raw,**options)
        # Match the existing round reader's exact projection, omitting only its
        # result extension. Never modify the original to make it admissible.
        with tempfile.TemporaryDirectory(prefix='v53-round-physical-') as temp:
            path=Path(temp)/'raw';shutil.copytree(raw,path);(path/'round-result.json').unlink()
            physical=reader.qualify(path,**options,**({'precommand_maintenance':True} if not old else {}))
        need(lifecycle['original']['original']==physical['original'],'round cohort identical physical derivation')
        original=lifecycle['original']
        negatives=[dict(suite='physical',**v) for v in physical['negatives']]+[dict(suite='lifecycle',**v) for v in lifecycle['negatives']]
    else:
        physical=reader.qualify(raw,**options);original=physical['original']
        negatives=[dict(suite='physical',**v) for v in physical['negatives']]
    need(h.inventory(raw)==before,'round cohort original changed in reader')
    return dict(original=original,negatives=negatives,originalPreserved=True)


def capture(output,maven,case,source_from=None):
    selected(case);output=Path(output).absolute()
    need(source_from is None or not output.resolve().is_relative_to(Path(source_from).resolve()),'round history source separation')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,case=case,status='RUNNING',executionStatus='NOT_RUN',collectionComplete=False,
                 nativeHistoryQualified=False,phase3Complete=False,retries=0)
    try:
        work=output/'workspace';source=h.source_copy(h.ROOT,work) if source_from is None else h.recorded_source(source_from,work)
        h.save(output/'source.json',source);reader=reader_manifest()
        need(all(source['files'].get(k)==v for k,v in reader['files'].items()),'round history reader belongs to source')
        h.save(output/'toolchain.json',tc.capture(maven,work))
        receipt.update(baseHead=source['head'],sourceSha256=h.digest((output/'source.json').read_bytes()),readerSha256=reader['sha256'],
            toolchainSha256=h.digest((output/'toolchain.json').read_bytes()),command=[maven,*command(case)])
        h.save(output/'receipt.json',receipt)
        execution=h.execute(receipt['command'],work,output/'maven.log',stage='round-'+case)
        h.save(output/'execution.json',execution);receipt['execution']=execution;h.check_source(work,source)
        need(type(execution['exit']) is int and execution['exit']==0,'round history Maven failed; original retained')
        receipt['junit']=junit(work/h.MODULE/'target/surefire-reports',case);receipt['executionStatus']='PASS'
        h.save(output/'build.json',{name:h.inventory(work/name) for name in BUILDS})
        receipt['buildSha256']=h.digest((output/'build.json').read_bytes())
        roots=list((work/h.MODULE/'target'/selected(case)[2]).iterdir())
        need(len(roots)==1,'round history exact raw directory');raw=roots[0];receipt['raw']=raw.relative_to(output).as_posix()
        collected=h.execute([sys.executable,'-B','-m','scripts.v53.round_history','collect',str(output/'collection.json'),
            '--case',case,'--raw',str(raw)],work,output/'collection.log',stage='round-collection-'+case)
        h.save(output/'collection-execution.json',collected);receipt['collectionExecution']=collected
        need(type(collected['exit']) is int and collected['exit']==0,'round history collection failed; original retained')
        need(read(output/'collection.json')==collect(raw,case),'round history immutable source collection')
        h.check_source(work,source);receipt.update(status='PARTIAL',collectionComplete=True,
            collectionSha256=h.digest((output/'collection.json').read_bytes()))
    except BaseException as error:
        if receipt['executionStatus']=='NOT_RUN':receipt['executionStatus']='FAIL'
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


def check_pins(source,build,toolchain,reader):
    need(all(shared.hash_field(v) for v in (source,build,toolchain,reader)),'round cohort pinned hashes')
    manifest=reader_manifest();need(manifest['sha256']==reader,'round cohort pinned reader');return manifest


def member(path,case,source,build,toolchain,reader):
    selected(case);manifest=check_pins(source,build,toolchain,reader);path=Path(path)
    need(path.is_dir() and not path.is_symlink(),'round cohort producer directory');receipt=read(path/'receipt.json')
    need(type(receipt) is dict and receipt.get('schema')==SCHEMA and receipt.get('case')==case and receipt.get('status')=='PARTIAL'
         and receipt.get('executionStatus')=='PASS' and receipt.get('collectionComplete') is True
         and all(receipt.get(k) is False for k in ('nativeHistoryQualified','phase3Complete'))
         and type(receipt.get('retries')) is int and receipt['retries']==0,'round cohort successful unretried producer')
    for field,file in (('execution','execution.json'),('collectionExecution','collection-execution.json')):
        value=receipt.get(field)
        need(type(value) is dict and type(value.get('exit')) is int and value['exit']==0
             and h.snapshot.f.canonical(read(path/file))==h.snapshot.f.canonical(value),'round cohort successful process receipts')
    recorded,_=h.read_recorded_source(path);work=path/'workspace'
    need(receipt.get('sourceSha256')==source==h.digest((path/'source.json').read_bytes()) and receipt.get('baseHead')==recorded['head'],
         'round cohort exact producer source')
    need(receipt.get('readerSha256')==reader and all(recorded['files'].get(k)==v for k,v in manifest['files'].items()),
         'round cohort reader belongs to producer')
    args=receipt.get('command');wanted=command(case)
    need(type(args) is list and len(args)==len(wanted)+1 and type(args[0]) is str and Path(args[0]).name=='mvn'
         and args[1:]==wanted,'round cohort exact complete command')
    for name in (*BUILDS,h.MODULE+'/target/surefire-reports'):
        need(all((work/p).is_dir() and not (work/p).is_symlink() for p in (Path(name),*Path(name).parents)),
             'round cohort linked generated parent')
    need(h.snapshot.f.canonical(receipt.get('junit'))==h.snapshot.f.canonical(junit(work/h.MODULE/'target/surefire-reports',case)),
         'round cohort exact JUnit receipt')
    classes=read(path/'build.json')
    need(type(classes) is dict and set(classes)==set(BUILDS) and receipt.get('buildSha256')==build==h.digest((path/'build.json').read_bytes()),
         'round cohort exact build manifest')
    for name in BUILDS:need(h.inventory(work/name)==classes[name],'round cohort original compiled bytes')
    tc.validate(read(path/'toolchain.json'))
    need(receipt.get('toolchainSha256')==h.digest((path/'toolchain.json').read_bytes()) and tc.pin((path/'toolchain.json').read_bytes())==toolchain,
         'round cohort portable toolchain')
    name=receipt.get('raw');base='workspace/'+h.MODULE+'/target/'+selected(case)[2]
    need(type(name) is str and re.fullmatch(base+r'/run-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',name),
         'round cohort exact raw path')
    need(all((path/p).is_dir() and not (path/p).is_symlink() for p in Path(name).parents),'round cohort linked raw parent')
    raw=path/name;need({v.name for v in raw.parent.iterdir()}=={raw.name},'round cohort exactly one original run')
    collection=collect(raw,case)
    need(receipt.get('collectionSha256')==h.digest((path/'collection.json').read_bytes()) and
         h.snapshot.f.canonical(read(path/'collection.json'))==h.snapshot.f.canonical(collection),
         'round cohort independent original collection')
    return dict(raw=raw,plans=collection['plans'],inventory=collection['inventory'],receiptSha256=h.digest((path/'receipt.json').read_bytes()))


def check_result(value,case):
    selected(case);old=phase(case)
    need(type(value) is dict and set(value)=={'original','negatives','originalPreserved'} and value['originalPreserved'] is True,
         'round cohort preserved original replay')
    original=value['original']
    if case.startswith('round-'):
        need(type(original) is dict and set(original)=={'status','mode','slots','original','internalReady','publicReady','phase3Complete'} and
             original['status']=='PASS' and original['mode']==('carried-applied' if old else 'stable') and type(original['slots']) is int and original['slots']==2 and
             original['internalReady'] is True and original['publicReady'] is False and original['phase3Complete'] is False,'round cohort scoped lifecycle result')
        original=original['original']
    keys={'status','slots','selected','transfers','retentionSemantics','phase3Complete'}|({'phase','voters','automaticElection','publicReady'} if old else {'autonomous'})
    if case=='round-discovered':keys.add('discoveryPeers')
    need(type(original) is dict and set(original)==keys and original['status']=='PASS' and original['phase3Complete'] is False and
         original['retentionSemantics']=='original-copy-confirmation' and
         all(type(original[k]) is int for k in ('slots','selected','transfers')) and original['slots']==original['selected']==2 and original['transfers']>0,
         'round cohort complete physical result')
    if old:
        need(original['phase']==old and type(original['voters']) is int and original['voters']==3 and
             original['automaticElection'] is False and original['publicReady'] is False,'round cohort carried original scope')
    else:need(original['autonomous'] is False,'round cohort autonomous claim')
    if case=='round-discovered':need(type(original['discoveryPeers']) is int and original['discoveryPeers']==2,'round cohort complete discovery')
    need(value['negatives']==negative_cases(case),'round cohort exact negative vector')


def qualify_member(path,case,*pins):
    before=member(path,case,*pins);result=replay(before['raw'],case);check_result(result,case)
    need(member(path,case,*pins)==before,'round cohort changed during replay');check_pins(*pins)
    return dict(case=case,status='PASS',plans=before['plans'],producerReceiptSha256=before['receiptSha256'],qualification=result,
                **dict(zip(('sourceSha256','buildSha256','toolchainSha256','readerSha256'),pins)),phase3Complete=False)


def aggregate(paths,*pins,workers=1,progress=None):
    check_pins(*pins);need(type(workers) is int and 1<=workers<=4,'round cohort replay workers')
    need(type(paths) is dict and set(paths)==set(CASES),'round cohort complete seven histories')
    need(len({Path(v).resolve() for v in paths.values()})==len(CASES),'round cohort distinct producers')
    originals={k:member(paths[k],k,*pins) for k in CASES};plans=[v for k in CASES for v in originals[k]['plans'].values()]
    need(len(plans)==len(set(plans))==7,'round cohort distinct complete original histories')
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
            if not done and progress:progress(dict(stage='round-replay',completed=len(outcomes),total=len(CASES)))
    for k in CASES:need(member(paths[k],k,*pins)==originals[k],'round cohort original changed before aggregate')
    check_pins(*pins);passed=all(outcomes[k]['status']=='PASS' for k in CASES)
    return dict(schema=COHORT,status='PASS' if passed else 'FAIL',scope='complete-declared-native-carried-and-stable-rounds',
        cases=[outcomes[k] for k in CASES],wholeOwnershipHistories=7,nativeCases=7,
        negativeCases=sum(len(v.get('qualification',{}).get('negatives',[])) for v in outcomes.values()),
        **dict(zip(('sourceSha256','buildSha256','toolchainSha256','readerSha256'),pins)),declaredNativeRoundHistoriesQualified=passed,processDeathQualified=False,
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
            with heartbeat('round-'+a.command,getattr(a,'case',None)),(output/'progress.jsonl').open('x') as stream:
                def progress(v):stream.write(json.dumps(v,sort_keys=True)+'\n');stream.flush();print(json.dumps(v),file=sys.stderr,flush=True)
                if a.command=='member':result=qualify_member(a.producer,a.case,*pins)
                else:
                    inputs=Path(a.inputs);need(inputs.is_dir() and not inputs.is_symlink() and {v.name for v in inputs.iterdir()}==set(CASES),
                        'round cohort exact input directories')
                    result=aggregate({k:inputs/k for k in CASES},*pins,workers=a.workers,progress=progress)
            need(result['status']=='PASS','round cohort failed originals')
        except BaseException as error:result.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
        finally:h.save(output/'receipt.json',result)
    print(json.dumps(dict(status=result['status'],phase3Complete=False,output=a.output),sort_keys=True))


if __name__=='__main__':main()
