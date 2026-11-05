"""Isolated hosted REMOVE histories and downloaded original-first qualification.

Only the dedicated experiment push or explicit dispatch can run this workflow.
Preparation and member receipts never imply complete Phase 3 qualification.
"""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import threading
import time
import xml.etree.ElementTree as ET
from . import remove_process_matrix as m
from . import process_toolchain as tc

h=m.h;need=h.need
WORKFLOW='.github/workflows/v53-remove-process.yml'
BRANCH='refs/heads/experiment/v53-remove-process'
MAX_BYTES=1024*1024*1024
SCHEMA='gse-v53-remove-hosted-v1'


def context(*,workflow=WORKFLOW,branch=BRANCH):
    env=os.environ
    need(env.get('GITHUB_ACTIONS')=='true' and env.get('GITHUB_REPOSITORY')=='patricklfdm/GeneralSearchEngine','REMOVE hosted repository')
    source=env.get('GITHUB_SHA','');ref=env.get('GITHUB_REF','');event=env.get('GITHUB_EVENT_NAME','')
    need(re.fullmatch('[0-9a-f]{40}',source) and ref.startswith('refs/heads/') and
         (event=='workflow_dispatch' or event=='push' and ref==branch),'REMOVE hosted event/ref')
    need(env.get('V53_WORKFLOW_REF')=='patricklfdm/GeneralSearchEngine/'+workflow+'@'+ref and
         env.get('V53_WORKFLOW_SHA')==source,'REMOVE hosted workflow source')
    run=env.get('GITHUB_RUN_ID','');attempt=env.get('GITHUB_RUN_ATTEMPT','')
    need(all(re.fullmatch('[1-9][0-9]{0,19}',v) for v in (run,attempt)),'REMOVE hosted run/attempt')
    need(subprocess.check_output(['git','rev-parse','HEAD'],cwd=h.ROOT,text=True).strip()==source,'REMOVE hosted checkout')
    return dict(kind='github',repository=env['GITHUB_REPOSITORY'],source=source,ref=ref,event=event,run=run,attempt=attempt,workflow=workflow)


def artifact_name(ctx,kind,case=None):
    suffix='-'+m.slug(case) if case is not None else ''
    return 'v53-remove-'+kind+'-'+ctx['run']+'-'+ctx['attempt']+'-'+ctx['source']+suffix


def pack(root,output,ctx,kind,case=None,*,schema=SCHEMA):
    root=Path(root);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    before=h.inventory(root,maximum=MAX_BYTES);archive=output/'bundle.tar.gz'
    with tarfile.open(archive,'x:gz') as stream:stream.add(root,arcname='data')
    need(h.inventory(root,maximum=MAX_BYTES)==before,'REMOVE hosted inputs changed while packing')
    value=dict(schema=schema,context=ctx,kind=kind,case=case,inventory=before,archiveSha256=tc.file_hash(archive))
    h.save(output/'manifest.json',value);return value


def unpack(bundle,output,ctx,kind,case=None,*,schema=SCHEMA):
    bundle=Path(bundle);output=Path(output);manifest=m.read(bundle/'manifest.json');archive=bundle/'bundle.tar.gz'
    need(set(manifest)=={'schema','context','kind','case','inventory','archiveSha256'} and
         manifest['schema']==schema and manifest['context']==ctx and manifest['kind']==kind and manifest['case']==case,
         'REMOVE hosted exact artifact binding')
    need(archive.is_file() and not archive.is_symlink() and archive.stat().st_size<=MAX_BYTES and
         tc.file_hash(archive)==manifest['archiveSha256'],'REMOVE hosted archive digest')
    output.mkdir(parents=True,exist_ok=False);seen=set();total=0
    with tarfile.open(archive,'r:gz') as stream:
        for item in stream:
            path=Path(item.name);need(item.name not in seen and len(seen)<65536 and not path.is_absolute() and
                path.as_posix()==item.name and '..' not in path.parts and path.parts and path.parts[0]=='data' and
                item.type in (tarfile.DIRTYPE,tarfile.REGTYPE,tarfile.AREGTYPE) and not item.sparse,
                'REMOVE hosted archive member')
            seen.add(item.name);total+=item.size
            need(0<=item.size<=256*1024*1024 and total<=MAX_BYTES,'REMOVE hosted archive capacity')
            target=output/path
            if item.isdir():target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with target.open('xb') as dest:shutil.copyfileobj(stream.extractfile(item),dest,1024*1024)
                target.chmod(0o755 if item.mode & 0o111 else 0o644)
    need(h.inventory(output/'data',maximum=MAX_BYTES)==manifest['inventory'],'REMOVE hosted extracted inventory')
    return output/'data',manifest


def dependencies(repository):
    inventory=h.inventory(repository,maximum=MAX_BYTES)
    files={k:v for k,v in inventory['files'].items() if k.endswith(('.jar','.pom'))}
    need(files and any('surefire' in k for k in files),'REMOVE hosted offline dependencies')
    return h.digest(m.gate.f.canonical(files))


@contextmanager
def repository_env(path):
    path=Path(path).absolute();need(not re.search(r'\s',str(path)),'REMOVE hosted Maven repository path')
    before=os.environ.get('MAVEN_OPTS');os.environ['MAVEN_OPTS']='-Dmaven.repo.local='+str(path)
    try:yield
    finally:
        if before is None:os.environ.pop('MAVEN_OPTS',None)
        else:os.environ['MAVEN_OPTS']=before


def seed_inputs(data,ctx):
    value=m.read(data/'seed.json');need(value['schema']==SCHEMA and value['context']==ctx and value['status']=='PARTIAL' and
        value['phase3Complete'] is False and value['cases']==list(m.KINDS),'REMOVE hosted seed scope')
    source,_=h.read_recorded_source(data/'producer');need(source['head']==ctx['source'] and
        h.digest((data/'producer/source.json').read_bytes())==value['sourceSha256'],'REMOVE hosted seed source')
    build=m.read(data/'producer/build.json');need(set(build)==set(m.BUILDS) and
        h.digest((data/'producer/build.json').read_bytes())==value['buildSha256'],'REMOVE hosted seed build')
    for name in m.BUILDS:need(h.inventory(data/'producer/workspace'/name)==build[name],'REMOVE hosted seed classes')
    need(tc.pin((data/'producer/toolchain.json').read_bytes())==value['toolchainSha256'] and
        m.reader_manifest()==value['reader'] and value['reader']['sha256']==value['readerSha256'],'REMOVE hosted seed reader/tools')
    need(all(source['files'].get(name)==digest for name,digest in value['reader']['files'].items()),
         'REMOVE hosted reader differs from recorded source')
    need(dependencies(data/'repository')==value['repositorySha256'],'REMOVE hosted seed dependencies')
    return value


def prepare_source(data,maven,ctx):
    """Freeze source, reference classes and offline tools once for a cohort.

    No membership history is executed here. Each collector independently builds
    its original workspace and must reproduce these exact reference class bytes.
    """
    data=Path(data);producer=data/'producer';producer.mkdir();repository=data/'repository';repository.mkdir()
    if ctx['kind']=='github':
        need(not subprocess.check_output(['git','status','--porcelain','--untracked-files=normal'],cwd=h.ROOT),'REMOVE hosted dirty source')
    source=h.source_copy(h.ROOT,producer/'workspace');need(source['head']==ctx['source'],'REMOVE hosted prepared source')
    h.save(producer/'source.json',source)
    with repository_env(repository):
        tools=tc.capture(maven,producer/'workspace');h.save(producer/'toolchain.json',tools)
        command=[maven,'-B','-ntp','-f','reactor/pom.xml','-pl','../'+h.MODULE,'-am',
                 '-Dsurefire.failIfNoSpecifiedTests=false','-Dtest=V53BallotAllocatorTest','test']
        execution=h.execute(command,producer/'workspace',producer/'maven.log',stage='REMOVE-hosted-prepare')
    need(execution['exit']==0,'REMOVE hosted preparation failed');h.check_source(producer/'workspace',source)
    reports=list((producer/'workspace'/h.MODULE/'target/surefire-reports').glob('TEST-*.xml'))
    need(len(reports)==1,'REMOVE hosted preparation exact report');suite=ET.parse(reports[0]).getroot()
    need(suite.get('name','').endswith('.V53BallotAllocatorTest') and int(suite.get('tests','0'))>0 and
        all(suite.get(k)=='0' for k in ('failures','errors','skipped')) and not any(
            row.tag in {'failure','error','skipped','flakyFailure','flakyError','rerunFailure','rerunError'} for row in suite.iter()),
        'REMOVE hosted preparation unretried test')
    h.save(producer/'build.json',{name:h.inventory(producer/'workspace'/name) for name in m.BUILDS})
    return dict(sourceSha256=h.digest((producer/'source.json').read_bytes()),
                buildSha256=h.digest((producer/'build.json').read_bytes()),
                toolchainSha256=tc.pin((producer/'toolchain.json').read_bytes()),
                repositorySha256=dependencies(repository),preparationExecution=execution)


def prepare(output,maven,ctx):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);data=output/'data';data.mkdir()
    receipt=dict(schema=SCHEMA,context=ctx,status='FAIL',phase3Complete=False)
    try:
        prepared=prepare_source(data,maven,ctx);reader=m.reader_manifest()
        receipt.update(status='PARTIAL',cases=list(m.KINDS),readerSha256=reader['sha256'],reader=reader,**prepared)
        h.save(data/'seed.json',receipt);seed_inputs(data,ctx);pack(data,output/'artifact',ctx,'seed')
    except BaseException as error:receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


def pins(seed):return [seed[name+'Sha256'] for name in ('source','build','toolchain','reader')]


def execute(bundle,output,maven,case,ctx):
    m.run.selected(case);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    data=output/'data';data.mkdir();receipt=dict(schema=SCHEMA,context=ctx,case=case,status='FAIL',phase3Complete=False)
    try:
        seed_root,manifest=unpack(bundle,output/'seed',ctx,'seed');seed=seed_inputs(seed_root,ctx)
        working=output/'repository';shutil.copytree(seed_root/'repository',working)
        with repository_env(working):
            need(tc.pin(m.gate.f.canonical(tc.capture(maven,h.ROOT)))==seed['toolchainSha256'],'REMOVE hosted worker toolchain')
            m.run.run(data/'producer',maven,case,source_from=seed_root/'producer',portable_toolchain=True)
        need(dependencies(working)==seed['repositorySha256'],'REMOVE hosted runtime dependency drift')
        original=m.member(data/'producer',case,*pins(seed)[:3]);seed_inputs(seed_root,ctx)
        receipt.update(status='PARTIAL',seedArchiveSha256=manifest['archiveSha256'],
            producerReceiptSha256=original['receiptSha256'],originalPlanSha256=original['plan'],
            **{name+'Sha256':value for name,value in zip(('source','build','toolchain','reader'),pins(seed))})
    except BaseException as error:receipt.update(failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:
        h.save(data/'hosted-member.json',receipt);h.save(output/'receipt.json',receipt)
        pack(data,output/'artifact',ctx,'raw',case)
    return receipt


def verify(seed_bundle,raw_bundle,output,case,ctx):
    m.run.selected(case);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,context=ctx,case=case,status='FAIL',phase3Complete=False)
    try:
        seed_root,seed_manifest=unpack(seed_bundle,output/'seed',ctx,'seed');seed=seed_inputs(seed_root,ctx)
        raw,raw_manifest=unpack(raw_bundle,output/'original',ctx,'raw',case);claimed=m.read(raw/'hosted-member.json')
        need(claimed.get('schema')==SCHEMA and claimed.get('context')==ctx and claimed.get('case')==case and
             claimed.get('status')=='PARTIAL' and claimed.get('phase3Complete') is False and
             [claimed.get(name+'Sha256') for name in ('source','build','toolchain','reader')]==pins(seed) and
             claimed.get('seedArchiveSha256')==seed_manifest['archiveSha256'],'REMOVE hosted original member binding')
        result=m.qualify_member(raw/'producer',case,*pins(seed))
        need(result['producerReceiptSha256']==claimed.get('producerReceiptSha256') and
             result['originalPlanSha256']==claimed.get('originalPlanSha256'),'REMOVE hosted original receipt binding')
        seed_inputs(seed_root,ctx);need(h.inventory(raw,maximum=MAX_BYTES)==raw_manifest['inventory'],'REMOVE hosted downloaded original changed')
        receipt.update(status='PARTIAL',seedArchiveSha256=seed_manifest['archiveSha256'],rawArchiveSha256=raw_manifest['archiveSha256'],
                       originalFirstDownloadedReplay=True,member=result)
    except BaseException as error:receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


def aggregate_precondition(execute_result, verify_result, offline_replay, reason):
    need(type(offline_replay) is bool, 'hosted aggregate explicit offline policy')
    if offline_replay:
        need(execute_result is None and verify_result is None, 'offline aggregate must not claim workflow results')
    else:need(execute_result==verify_result=='success', reason)


def complete_aggregate(receipt, offline_replay):
    if offline_replay:
        need(receipt['status']=='PASS' and receipt['phase3Complete'] is False, 'offline aggregate complete evidence required')
        receipt.update(status='PARTIAL', offlineEvidenceOnly=True, workflowExecutionAttested=False,
                       acceptanceAuthority='offline original-first replay; GitHub workflow stages are not attested')


def aggregate(seed_bundle,inputs,output,ctx,execute_result,verify_result, *, offline_replay=False):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);receipt=dict(schema=SCHEMA,context=ctx,status='FAIL',phase3Complete=False)
    try:
        aggregate_precondition(execute_result, verify_result, offline_replay, 'REMOVE hosted failed/missing workflow stage')
        seed_root,manifest=unpack(seed_bundle,output/'seed',ctx,'seed');seed=seed_inputs(seed_root,ctx);inputs=Path(inputs)
        wanted={artifact_name(ctx,'verified',case) for case in m.KINDS}
        need(inputs.is_dir() and not inputs.is_symlink() and {p.name for p in inputs.iterdir()}==wanted,'REMOVE hosted complete verified inventory')
        cases=[];histories=set();archives=set()
        for case in m.KINDS:
            directory=inputs/artifact_name(ctx,'verified',case)
            need(directory.is_dir() and not directory.is_symlink() and {p.name for p in directory.iterdir()}=={'receipt.json'},'REMOVE hosted verifier artifact shape')
            value=m.read(directory/'receipt.json');member=value.get('member',{})
            need(value.get('schema')==SCHEMA and value.get('context')==ctx and value.get('case')==case and value.get('status')=='PARTIAL' and
                value.get('phase3Complete') is False and value.get('originalFirstDownloadedReplay') is True and
                value.get('seedArchiveSha256')==manifest['archiveSha256'],'REMOVE hosted verifier context')
            need(member.get('case')==case and member.get('status')=='PASS' and member.get('phase3Complete') is False and
                [member.get(name+'Sha256') for name in ('source','build','toolchain','reader')]==pins(seed),
                'REMOVE hosted verifier pins')
            m.check_result(member['qualification'],case)
            for field in ('originalPlanSha256','producerReceiptSha256'):need(m.hash_field(member.get(field)),'REMOVE hosted original digest')
            need(m.hash_field(value.get('rawArchiveSha256')),'REMOVE hosted raw artifact digest')
            need(member['originalPlanSha256'] not in histories and value['rawArchiveSha256'] not in archives,'REMOVE hosted duplicated history')
            histories.add(member['originalPlanSha256']);archives.add(value['rawArchiveSha256']);cases.append(value)
        seed_inputs(seed_root,ctx)
        receipt.update(status='PASS',cases=cases,wholeHistories=52,negativeCases=52*len(m.gate.NEGATIVES),
            seedArchiveSha256=manifest['archiveSha256'],
            **{name+'Sha256':value for name,value in zip(('source','build','toolchain','reader'),pins(seed))},
            declaredRemoveProcessMatrixQualified=True,allMembershipProfilesQualified=False,originalObservationCoverageComplete=False,
            acceptanceAuthority='all exact-attempt workflow stages plus 52 independent downloaded original-first verifier receipts')
        complete_aggregate(receipt, offline_replay)
    except BaseException as error:receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


@contextmanager
def progress(stage,case,interval=60):
    start=time.monotonic();stop=threading.Event()
    def pulse():
        while not stop.wait(interval):
            print(json.dumps(dict(stage=stage,case=case,elapsedSeconds=round(time.monotonic()-start,1))),flush=True)
    worker=threading.Thread(target=pulse,daemon=True);worker.start()
    try:yield
    finally:stop.set();worker.join()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('plan','prepare','execute','verify','aggregate'))
    parser.add_argument('--output');parser.add_argument('--seed');parser.add_argument('--inputs');parser.add_argument('--case',choices=m.KINDS)
    args=parser.parse_args();ctx=context()
    if args.command=='plan':
        print(json.dumps(dict(include=[dict(case=case,id=m.slug(case)) for case in m.KINDS]),separators=(',',':')));return
    need(args.output,'REMOVE hosted output required')
    result=dict(status='FAIL')
    try:
        with progress(args.command,args.case):
            if args.command=='prepare':result=prepare(args.output,tc.locate(h.ROOT/'mvnw',h.ROOT),ctx)
            elif args.command=='execute':result=execute(args.seed,args.output,tc.locate(h.ROOT/'mvnw',h.ROOT),args.case,ctx)
            elif args.command=='verify':result=verify(args.seed,args.inputs,args.output,args.case,ctx)
            else:result=aggregate(args.seed,args.inputs,args.output,ctx,os.environ.get('EXECUTE_RESULT'),os.environ.get('VERIFY_RESULT'))
        print(json.dumps(dict(status=result['status'],phase3Complete=False,receipt=str(Path(args.output)/'receipt.json')),sort_keys=True))
    finally:
        summary=os.environ.get('GITHUB_STEP_SUMMARY')
        if summary:
            with Path(summary).open('a') as stream:
                stream.write('### V5.3 REMOVE process '+args.command+'\n\n'+
                    '| Parameter | Value |\n| --- | --- |\n'+
                    ''.join('| '+key+' | `'+str(value)+'` |\n' for key,value in [('Source',ctx['source']),('Run / attempt',ctx['run']+' / '+ctx['attempt']),
                      ('Case',args.case or 'all 52'),('Status',result['status']),('Phase 3 complete',False)])+'\n')


if __name__=='__main__':main()
