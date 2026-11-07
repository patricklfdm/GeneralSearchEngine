"""Immutable SOURCE queue component execution and independent admission.

One original, exact JUnit/build/tools/reader pins and eight exact negatives.
A component PASS does not qualify combined pressure or complete Phase 3.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from . import source_queue_evidence as gate
from . import joining_history_run as h
from . import remove_process_matrix as shared
from . import process_toolchain as tc

need=h.need;read=shared.read;reader_manifest=shared.reader_manifest;BUILDS=shared.BUILDS
SCHEMA='gse-v53-source-queue-execution-v1'
PACKAGE='io.github.patricklfdm.generalsearch.replication.'
# Complete raw inventory cap; the physical reader also checks its individual files.
RAW_BYTES=256*1024*1024
PINS=('sourceSha256','buildSha256','toolchainSha256','readerSha256')
PROFILE='source-queue-64mib'
CLASS='V53SourceQueueQualification'
METHOD='cachedOriginalChunksRefuseSendThenReleaseAndRetry'


def selected(profile):
    need(type(profile) is str and profile==PROFILE,'source-queue run explicit profile')
    return CLASS,METHOD,'v53-source-queue'


def command(profile):
    selected(profile)
    return ['-o','-B','-ntp','-f','reactor/pom.xml','-pl','../'+h.MODULE,'-am',
            '-Dsurefire.failIfNoSpecifiedTests=false','-Dtest='+CLASS+'#'+METHOD,'test']


def junit(reports,profile):
    cls,method,_=selected(profile);cls=PACKAGE+cls;paths=sorted(Path(reports).glob('TEST-*.xml'))
    need(len(paths)==1,'source-queue run exact JUnit report')
    suite=ET.fromstring(h.snapshot.s.regular(paths[0],8*h.snapshot.MIB));tests=suite.findall('testcase')
    need(suite.get('name')==cls and suite.get('tests')=='1' and len(tests)==1 and
         all(suite.get(k)=='0' for k in ('failures','errors','skipped')) and
         tests[0].get('classname')==cls and tests[0].get('name')==method and
         not any(v.tag in ('failure','error','skipped') or v.tag.startswith(('flaky','rerun')) for v in suite.iter()),
         'source-queue run exact unretried passing test')
    return dict(className=cls,method=method,tests=1,failures=0,errors=0,skipped=0,retries=0)


def locate(work,profile):
    _,_,directory=selected(profile);root=Path(work)/h.MODULE/'target'/directory
    need(root.is_dir() and not root.is_symlink(),'source-queue run original directory')
    names=[p.name for p in root.iterdir()]
    need(len(names)==1 and re.fullmatch(r'run-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',names[0]),
         'source-queue run single exact original')
    result=root/names[0];need(result.is_dir() and not result.is_symlink(),'source-queue run linked original');return result


def collect(raw,profile):
    selected(profile);raw=Path(raw);before=h.inventory(raw,maximum=RAW_BYTES)
    # Collection proves completeness of the retained inventory, not runtime acceptance.
    for name in ('events.json','resources.json','receipt.json','original-plan.gsbp',
                 'original-application.image','contents.json'):
        need(name in before['files'],'source-queue run missing observations: '+name)
    for name in ('initial','captured','after','exported','frames'):
        need(any(p.startswith(name+'/') for p in before['files']),'source-queue run missing original directory: '+name)
    need(h.inventory(raw,maximum=RAW_BYTES)==before,'source-queue run changed during collection')
    return dict(schema=SCHEMA,status='PARTIAL',profile=profile,collectionComplete=True,
                queuePressureQualified=False,combinedResourcesQualified=False,phase3Complete=False,inventory=before)


def collect_to(output,raw,profile):
    output=Path(output)
    need(not output.resolve().is_relative_to(Path(raw).resolve()),'source-queue collector original separation')
    need(not output.exists() and not output.is_symlink(),'source-queue collector output already exists')
    value=collect(raw,profile)
    # Exclusive creation also closes the gap between the initial check and save.
    with output.open('x') as stream:stream.write(json.dumps(value,sort_keys=True,indent=2)+'\n')
    return value


def capture(output,maven,profile,source_from=None):
    selected(profile);output=Path(output).absolute()
    need(source_from is None or not output.resolve().is_relative_to(Path(source_from).resolve()),'source-queue run source separation')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,profile=profile,status='RUNNING',executionStatus='NOT_RUN',collectionComplete=False,
                 queuePressureQualified=False,combinedResourcesQualified=False,phase3Complete=False,retries=0)
    try:
        work=output/'workspace';source=h.source_copy(h.ROOT,work) if source_from is None else h.recorded_source(source_from,work)
        h.save(output/'source.json',source);reader=reader_manifest()
        need(all(source['files'].get(k)==v for k,v in reader['files'].items()),'source-queue run reader belongs to source')
        h.save(output/'reader.json',reader);h.save(output/'toolchain.json',tc.capture(maven,work))
        receipt.update(baseHead=source['head'],sourceSha256=h.digest((output/'source.json').read_bytes()),readerSha256=reader['sha256'],
                       toolchainSha256=h.digest((output/'toolchain.json').read_bytes()),command=[maven,*command(profile)])
        h.save(output/'receipt.json',receipt)
        execution=h.execute(receipt['command'],work,output/'maven.log',stage='source-queue-resources-'+profile)
        h.save(output/'execution.json',execution);receipt['execution']=execution;h.check_source(work,source)
        need(type(execution['exit']) is int and execution['exit']==0,'source-queue run Maven failed; original retained')
        receipt['junit']=junit(work/h.MODULE/'target/surefire-reports',profile);receipt['executionStatus']='PASS'
        h.save(output/'build.json',{name:h.inventory(work/name) for name in BUILDS});receipt['buildSha256']=h.digest((output/'build.json').read_bytes())
        raw=locate(work,profile);receipt['raw']=raw.relative_to(output).as_posix()
        execution=h.execute([sys.executable,'-B','-m','scripts.v53.source_queue_run','collect',str(output/'collection.json'),
                             '--profile',profile,'--raw',str(raw)],work,output/'collection.log',stage='source-queue-resources-collection')
        h.save(output/'collection-execution.json',execution);receipt['collectionExecution']=execution
        need(type(execution['exit']) is int and execution['exit']==0,'source-queue run collection failed; original retained')
        need(read(output/'collection.json')==collect(raw,profile),'source-queue run immutable source collection')
        h.check_source(work,source);receipt.update(status='PARTIAL',collectionComplete=True,collectionSha256=h.digest((output/'collection.json').read_bytes()))
        pins={k:receipt[k] for k in PINS};pins['toolchainSha256']=tc.pin((output/'toolchain.json').read_bytes());h.save(output/'pins.json',pins)
    except BaseException as error:
        if receipt['executionStatus']=='NOT_RUN':receipt['executionStatus']='FAIL'
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


def check_pins(pins):
    need(type(pins) is dict and set(pins)==set(PINS) and all(shared.hash_field(v) for v in pins.values()),'source-queue admission explicit pins')
    manifest=reader_manifest();need(manifest['sha256']==pins['readerSha256'],'source-queue admission pinned reader');return manifest


def member(path,profile,pins):
    selected(profile);manifest=check_pins(pins);path=Path(path)
    need(path.is_dir() and not path.is_symlink(),'source-queue admission producer directory');receipt=read(path/'receipt.json')
    need(type(receipt) is dict and receipt.get('schema')==SCHEMA and receipt.get('profile')==profile and receipt.get('status')=='PARTIAL' and
         receipt.get('executionStatus')=='PASS' and receipt.get('collectionComplete') is True and
         all(receipt.get(k) is False for k in ('queuePressureQualified','combinedResourcesQualified','phase3Complete')) and
         type(receipt.get('retries')) is int and receipt['retries']==0,'source-queue admission successful unretried producer')
    for field,file in (('execution','execution.json'),('collectionExecution','collection-execution.json')):
        value=receipt.get(field)
        need(type(value) is dict and type(value.get('exit')) is int and value['exit']==0 and
             h.snapshot.f.canonical(read(path/file))==h.snapshot.f.canonical(value),'source-queue admission successful process receipts')
    source,_=h.read_recorded_source(path);work=path/'workspace'
    need(receipt.get('sourceSha256')==pins['sourceSha256']==h.digest((path/'source.json').read_bytes()) and receipt.get('baseHead')==source['head'],
         'source-queue admission exact source')
    need(receipt.get('readerSha256')==pins['readerSha256'] and read(path/'reader.json')==manifest and
         all(source['files'].get(k)==v for k,v in manifest['files'].items()),'source-queue admission reader belongs to producer')
    args=receipt.get('command');wanted=command(profile)
    need(type(args) is list and len(args)==len(wanted)+1 and type(args[0]) is str and Path(args[0]).name=='mvn' and args[1:]==wanted,
         'source-queue admission exact complete command')
    for name in (*BUILDS,h.MODULE+'/target/surefire-reports',h.MODULE+'/target/'+selected(profile)[2]):
        need(all((work/p).is_dir() and not (work/p).is_symlink() for p in (Path(name),*Path(name).parents)),
             'source-queue admission linked generated parent')
    need(h.snapshot.f.canonical(receipt.get('junit'))==h.snapshot.f.canonical(junit(work/h.MODULE/'target/surefire-reports',profile)),
         'source-queue admission exact JUnit receipt')
    classes=read(path/'build.json')
    need(type(classes) is dict and set(classes)==set(BUILDS) and receipt.get('buildSha256')==pins['buildSha256']==h.digest((path/'build.json').read_bytes()),
         'source-queue admission exact build manifest')
    for name in BUILDS:need(h.inventory(work/name)==classes[name],'source-queue admission original compiled bytes')
    tc.validate(read(path/'toolchain.json'))
    need(receipt.get('toolchainSha256')==h.digest((path/'toolchain.json').read_bytes()) and tc.pin((path/'toolchain.json').read_bytes())==pins['toolchainSha256'],
         'source-queue admission portable toolchain')
    raw=locate(work,profile);need(receipt.get('raw')==raw.relative_to(path).as_posix(),'source-queue admission exact raw path')
    collected=collect(raw,profile)
    need(receipt.get('collectionSha256')==h.digest((path/'collection.json').read_bytes()) and read(path/'collection.json')==collected,
         'source-queue admission original collection')
    return dict(raw=raw,inventory=collected['inventory'],producerReceiptSha256=h.digest((path/'receipt.json').read_bytes()))


def check_result(value,profile):
    selected(profile)
    need(type(value) is dict and set(value)=={'original','negatives'},'source-queue admission result shape')
    original=value['original']
    expected=dict(status='PASS',sessions=6,attempts=49,capacityRefusals=1,recoveredIdenticalRetries=1,
                  queueLimit=gate.LIMIT,phase3Complete=False,combinedResources=False)
    need(type(original) is dict and set(original)==set(expected)|{'maximumQueuedBytes'} and
         all(type(original.get(k)) is type(v) and original[k]==v for k,v in expected.items()) and
         type(original.get('maximumQueuedBytes')) is int and 11*((gate.CHUNK+2)//3)*4<original['maximumQueuedBytes']<=gate.LIMIT,
         'source-queue admission original byte pressure')
    expected=[dict(case=name,status='REJECTED',reason=reason) for name,reason in gate.NEGATIVES.items()]
    need(value['negatives']==expected,'source-queue admission exact negatives')


def qualify(path,profile,pins):
    before=member(path,profile,pins);result=gate.qualify(gate.load(before['raw']));check_result(result,profile)
    need(member(path,profile,pins)==before,'source-queue admission changed during replay');check_pins(pins)
    return dict(schema=SCHEMA,status='PASS',scope='source-queue-component-only',profile=profile,**pins,
                producerReceiptSha256=before['producerReceiptSha256'],rawInventorySha256=h.digest(h.snapshot.f.canonical(before['inventory'])),
                originalFirst=True,originalPreserved=True,queuePressureQualified=True,combinedResourcesQualified=False,phase3Complete=False,qualification=result)


def verify(output,producer,profile,pins):
    output=Path(output);need(not output.resolve().is_relative_to(Path(producer).resolve()),'source-queue verifier original separation')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,status='FAIL',profile=profile,phase3Complete=False)
    try:receipt=qualify(producer,profile,pins)
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    for action in ('capture','collect','verify'):
        p=sub.add_parser(action);p.add_argument('output');p.add_argument('--profile',choices=(PROFILE,),required=True)
        if action=='capture':p.add_argument('--maven',default='mvn');p.add_argument('--source-from')
        elif action=='collect':p.add_argument('--raw',required=True)
        else:p.add_argument('--producer',required=True);p.add_argument('--pins',required=True)
    a=parser.parse_args()
    if a.action=='capture':value=capture(a.output,a.maven,a.profile,a.source_from)
    elif a.action=='verify':value=verify(a.output,a.producer,a.profile,read(Path(a.pins)))
    else:value=collect_to(a.output,a.raw,a.profile)
    print(json.dumps({k:value[k] for k in ('status','profile','phase3Complete')},sort_keys=True))
