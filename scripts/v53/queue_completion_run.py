"""Immutable native joint queue pressure through FINAL/BARRIER admission.

One complete original and ten exact negatives (twelve for explicit segmentation). A small-image rehearsal, isolated
SOURCE pressure, or downloaded PASS receipt cannot fill this resource slot.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from . import queue_completion_evidence as gate
from . import joining_history_run as h
from . import remove_process_matrix as shared
from . import process_toolchain as tc
from .maximum_transition_inventory import inventory

need=h.need;read=shared.read;reader_manifest=shared.reader_manifest;BUILDS=shared.BUILDS
SCHEMA='gse-v53-queue-completion-execution-v1'
SEGMENTED_SCHEMA='gse-v53-segmented-queue-completion-execution-v1'
PACKAGE='io.github.patricklfdm.generalsearch.replication.'
# Complete raw inventory cap; the physical reader also checks its individual files.
RAW_BYTES=8*1024*1024*1024
PINS=('sourceSha256','buildSha256','toolchainSha256','readerSha256')
PROFILE='joint-queue-final-64mib'
SEGMENTED_PROFILE=PROFILE+'-segmented'
CLASS='V53QueueCompletionQualification'
METHOD='admittedRemoveFinishesAfterRealJointQueuePressure'
SEGMENTED_METHOD='segmentedQueuePressureCompletesSameNativeHistory'


def selected(profile):
    need(type(profile) is str and profile in (PROFILE,SEGMENTED_PROFILE),'queue-completion run explicit profile')
    return CLASS,METHOD if profile==PROFILE else SEGMENTED_METHOD,'v53-queue-completion'


def schema(profile):
    selected(profile);return SCHEMA if profile==PROFILE else SEGMENTED_SCHEMA


def options(profile):
    selected(profile);return {} if profile==PROFILE else dict(wire_layout=gate.history.wire_archive.SEGMENTED)


def command(profile):
    cls,method,_=selected(profile)
    return ['-o','-B','-ntp','-f','reactor/pom.xml','-pl','../'+h.MODULE,'-am',
            '-Dsurefire.failIfNoSpecifiedTests=false','-Dtest='+cls+'#'+method,'test']


def junit(reports,profile):
    cls,method,_=selected(profile);cls=PACKAGE+cls;paths=sorted(Path(reports).glob('TEST-*.xml'))
    need(len(paths)==1,'queue-completion run exact JUnit report')
    suite=ET.fromstring(h.snapshot.s.regular(paths[0],8*h.snapshot.MIB));tests=suite.findall('testcase')
    need(suite.get('name')==cls and suite.get('tests')=='1' and len(tests)==1 and
         all(suite.get(k)=='0' for k in ('failures','errors','skipped')) and
         tests[0].get('classname')==cls and tests[0].get('name')==method and
         not any(v.tag in ('failure','error','skipped') or v.tag.startswith(('flaky','rerun')) for v in suite.iter()),
         'queue-completion run exact unretried passing test')
    return dict(className=cls,method=method,tests=1,failures=0,errors=0,skipped=0,retries=0)


def locate(work,profile):
    _,_,directory=selected(profile);root=Path(work)/h.MODULE/'target'/directory
    need(root.is_dir() and not root.is_symlink(),'queue-completion run original directory')
    names=[p.name for p in root.iterdir()]
    need(len(names)==1 and re.fullmatch(r'run-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',names[0]),
         'queue-completion run single exact original')
    result=root/names[0];need(result.is_dir() and not result.is_symlink(),'queue-completion run linked original');return result


def collect(raw,profile):
    selected(profile);raw=Path(raw);before=inventory(raw,maximum=RAW_BYTES)
    # Collection proves completeness of the retained inventory, not runtime acceptance.
    for name in ('events.json','calls.json','failures.json','continuous-result.json',
                 'queue-completion.json','queue-resources.json','original-plan.gsbp','original-application.image'):
        need(name in before['files'],'queue-completion run missing observations: '+name)
    if profile==PROFILE:
        need('wire.json' in before['files'],'queue-completion run missing observations: wire.json')
        need(not any(p.startswith(gate.history.wire_archive.DIRECTORY+'/') for p in before['files']),
             'queue-completion run unexpected segmented evidence')
    else:
        # Prove complete transport collection without granting physical admission.
        gate.history.wire_history(raw,backup=True,maximum_bytes=RAW_BYTES,wire_bytes=256*gate.t.MIB,**options(profile))
    for name in ('initial','before-network','installed-1','installed-2','installed-3',
                 'published-5','published-6','published-7','after-close'):
        need(any(p.startswith(name+'/') for p in before['files']),'queue-completion run missing original directory: '+name)
    need(inventory(raw,maximum=RAW_BYTES)==before,'queue-completion run changed during collection')
    return dict(schema=schema(profile),status='PARTIAL',profile=profile,collectionComplete=True,
                queuePressureQualified=False,combinedResourcesQualified=False,phase3Complete=False,inventory=before)


def collect_to(output,raw,profile):
    output=Path(output)
    need(not output.resolve().is_relative_to(Path(raw).resolve()),'queue-completion collector original separation')
    need(not output.exists() and not output.is_symlink(),'queue-completion collector output already exists')
    value=collect(raw,profile)
    # Exclusive creation also closes the gap between the initial check and save.
    with output.open('x') as stream:stream.write(json.dumps(value,sort_keys=True,indent=2)+'\n')
    return value


def capture(output,maven,profile,source_from=None):
    selected(profile);output=Path(output).absolute()
    need(source_from is None or not output.resolve().is_relative_to(Path(source_from).resolve()),'queue-completion run source separation')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=schema(profile),profile=profile,status='RUNNING',executionStatus='NOT_RUN',collectionComplete=False,
                 queuePressureQualified=False,combinedResourcesQualified=False,phase3Complete=False,retries=0)
    try:
        work=output/'workspace';source=h.source_copy(h.ROOT,work) if source_from is None else h.recorded_source(source_from,work)
        h.save(output/'source.json',source);reader=reader_manifest()
        need(all(source['files'].get(k)==v for k,v in reader['files'].items()),'queue-completion run reader belongs to source')
        h.save(output/'reader.json',reader);h.save(output/'toolchain.json',tc.capture(maven,work))
        receipt.update(baseHead=source['head'],sourceSha256=h.digest((output/'source.json').read_bytes()),readerSha256=reader['sha256'],
                       toolchainSha256=h.digest((output/'toolchain.json').read_bytes()),command=[maven,*command(profile)])
        h.save(output/'receipt.json',receipt)
        execution=h.execute(receipt['command'],work,output/'maven.log',stage='queue-completion-resources-'+profile)
        h.save(output/'execution.json',execution);receipt['execution']=execution;h.check_source(work,source)
        need(type(execution['exit']) is int and execution['exit']==0,'queue-completion run Maven failed; original retained')
        receipt['junit']=junit(work/h.MODULE/'target/surefire-reports',profile);receipt['executionStatus']='PASS'
        h.save(output/'build.json',{name:h.inventory(work/name) for name in BUILDS});receipt['buildSha256']=h.digest((output/'build.json').read_bytes())
        raw=locate(work,profile);receipt['raw']=raw.relative_to(output).as_posix()
        execution=h.execute([sys.executable,'-B','-m','scripts.v53.queue_completion_run','collect',str(output/'collection.json'),
                             '--profile',profile,'--raw',str(raw)],work,output/'collection.log',stage='queue-completion-resources-collection')
        h.save(output/'collection-execution.json',execution);receipt['collectionExecution']=execution
        need(type(execution['exit']) is int and execution['exit']==0,'queue-completion run collection failed; original retained')
        need(read(output/'collection.json')==collect(raw,profile),'queue-completion run immutable source collection')
        h.check_source(work,source);receipt.update(status='PARTIAL',collectionComplete=True,collectionSha256=h.digest((output/'collection.json').read_bytes()))
        pins={k:receipt[k] for k in PINS};pins['toolchainSha256']=tc.pin((output/'toolchain.json').read_bytes());h.save(output/'pins.json',pins)
    except BaseException as error:
        if receipt['executionStatus']=='NOT_RUN':receipt['executionStatus']='FAIL'
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


def check_pins(pins):
    need(type(pins) is dict and set(pins)==set(PINS) and all(shared.hash_field(v) for v in pins.values()),'queue-completion admission explicit pins')
    manifest=reader_manifest();need(manifest['sha256']==pins['readerSha256'],'queue-completion admission pinned reader');return manifest


def member(path,profile,pins):
    selected(profile);manifest=check_pins(pins);path=Path(path)
    need(path.is_dir() and not path.is_symlink(),'queue-completion admission producer directory');receipt=read(path/'receipt.json')
    need(type(receipt) is dict and receipt.get('schema')==schema(profile) and receipt.get('profile')==profile and receipt.get('status')=='PARTIAL' and
         receipt.get('executionStatus')=='PASS' and receipt.get('collectionComplete') is True and
         all(receipt.get(k) is False for k in ('queuePressureQualified','combinedResourcesQualified','phase3Complete')) and
         type(receipt.get('retries')) is int and receipt['retries']==0,'queue-completion admission successful unretried producer')
    for field,file in (('execution','execution.json'),('collectionExecution','collection-execution.json')):
        value=receipt.get(field)
        need(type(value) is dict and type(value.get('exit')) is int and value['exit']==0 and
             h.snapshot.f.canonical(read(path/file))==h.snapshot.f.canonical(value),'queue-completion admission successful process receipts')
    source,_=h.read_recorded_source(path);work=path/'workspace'
    need(receipt.get('sourceSha256')==pins['sourceSha256']==h.digest((path/'source.json').read_bytes()) and receipt.get('baseHead')==source['head'],
         'queue-completion admission exact source')
    need(receipt.get('readerSha256')==pins['readerSha256'] and read(path/'reader.json')==manifest and
         all(source['files'].get(k)==v for k,v in manifest['files'].items()),'queue-completion admission reader belongs to producer')
    args=receipt.get('command');wanted=command(profile)
    need(type(args) is list and len(args)==len(wanted)+1 and type(args[0]) is str and Path(args[0]).name=='mvn' and args[1:]==wanted,
         'queue-completion admission exact complete command')
    for name in (*BUILDS,h.MODULE+'/target/surefire-reports',h.MODULE+'/target/'+selected(profile)[2]):
        need(all((work/p).is_dir() and not (work/p).is_symlink() for p in (Path(name),*Path(name).parents)),
             'queue-completion admission linked generated parent')
    need(h.snapshot.f.canonical(receipt.get('junit'))==h.snapshot.f.canonical(junit(work/h.MODULE/'target/surefire-reports',profile)),
         'queue-completion admission exact JUnit receipt')
    classes=read(path/'build.json')
    need(type(classes) is dict and set(classes)==set(BUILDS) and receipt.get('buildSha256')==pins['buildSha256']==h.digest((path/'build.json').read_bytes()),
         'queue-completion admission exact build manifest')
    for name in BUILDS:need(h.inventory(work/name)==classes[name],'queue-completion admission original compiled bytes')
    tc.validate(read(path/'toolchain.json'))
    need(receipt.get('toolchainSha256')==h.digest((path/'toolchain.json').read_bytes()) and tc.pin((path/'toolchain.json').read_bytes())==pins['toolchainSha256'],
         'queue-completion admission portable toolchain')
    raw=locate(work,profile);need(receipt.get('raw')==raw.relative_to(path).as_posix(),'queue-completion admission exact raw path')
    collected=collect(raw,profile)
    need(receipt.get('collectionSha256')==h.digest((path/'collection.json').read_bytes()) and read(path/'collection.json')==collected,
         'queue-completion admission original collection')
    return dict(raw=raw,inventory=collected['inventory'],producerReceiptSha256=h.digest((path/'receipt.json').read_bytes()))


def check_result(value,profile):
    selected(profile)
    need(type(value) is dict and set(value)=={'original','negatives'},'queue-completion admission result shape')
    original=value['original']
    expected=dict(status='PASS',scope='joint-queue-completion-component-only',sessions=4,capacityRefusals=1,
                  nativeFinalCompleted=True,queuePressureQualified=True,phase3Complete=False,combinedMaximumQualified=False)
    if profile==SEGMENTED_PROFILE:expected.update(wireLayout=gate.history.wire_archive.SEGMENTED,bootstrapSource=gate.history.wire_archive.source.BACKUP)
    need(type(original) is dict and set(original)==set(expected)|{'maximumQueuedBytes'} and
         all(type(original.get(k)) is type(v) and original[k]==v for k,v in expected.items()) and
         type(original.get('maximumQueuedBytes')) is int and
         11*((gate.queue.CHUNK+2)//3)*4<original['maximumQueuedBytes']<=gate.queue.LIMIT,
         'queue-completion admission original pressure and native completion')
    expected=[dict(case=name,status='REJECTED',reason=reason) for name,reason in gate.negative_cases(**options(profile)).items()]
    need(value['negatives']==expected,'queue-completion admission exact negatives')


def qualify(path,profile,pins):
    before=member(path,profile,pins);result=gate.qualify(gate.load(before['raw'],**options(profile)),**options(profile));check_result(result,profile)
    need(member(path,profile,pins)==before,'queue-completion admission changed during replay');check_pins(pins)
    return dict(schema=schema(profile),status='PASS',scope='joint-queue-completion-component-only',profile=profile,**pins,
                producerReceiptSha256=before['producerReceiptSha256'],rawInventorySha256=h.digest(h.snapshot.f.canonical(before['inventory'])),
                originalFirst=True,originalPreserved=True,queuePressureQualified=True,nativeFinalCompleted=True,combinedResourcesQualified=False,phase3Complete=False,qualification=result)


def verify(output,producer,profile,pins):
    output=Path(output);need(not output.resolve().is_relative_to(Path(producer).resolve()),'queue-completion verifier original separation')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=schema(profile),status='FAIL',profile=profile,phase3Complete=False)
    try:receipt=qualify(producer,profile,pins)
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    for action in ('capture','collect','verify'):
        p=sub.add_parser(action);p.add_argument('output');p.add_argument('--profile',choices=(PROFILE,SEGMENTED_PROFILE),required=True)
        if action=='capture':p.add_argument('--maven',default='mvn');p.add_argument('--source-from')
        elif action=='collect':p.add_argument('--raw',required=True)
        else:p.add_argument('--producer',required=True);p.add_argument('--pins',required=True)
    a=parser.parse_args()
    if a.action=='capture':value=capture(a.output,a.maven,a.profile,a.source_from)
    elif a.action=='verify':value=verify(a.output,a.producer,a.profile,read(Path(a.pins)))
    else:value=collect_to(a.output,a.raw,a.profile)
    print(json.dumps({k:value[k] for k in ('status','profile','phase3Complete')},sort_keys=True))
