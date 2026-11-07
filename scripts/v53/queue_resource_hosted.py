"""Two independent whole queue histories from one immutable hosted seed.

Manual opt-in only. No history splitting, measurement retries or cloud authority.
Downloaded original replay is mandatory; workflow observation remains separate.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from . import source_queue_run as source
from . import queue_completion_run as completion
from . import remove_process_hosted as shared
from .maximum_transition_inventory import inventory

h=source.h;need=source.need;tc=shared.tc;read=source.read
WORKFLOW='.github/workflows/v53-queue-resources.yml'
BRANCH='refs/heads/experiment/v53-queue-resources'
SCHEMA='gse-v53-queue-resources-hosted-v1'
MEMBERS={'source-queue':source,'queue-completion':completion}
HISTORIES=tuple(MEMBERS)


def context():
    value=shared.context(workflow=WORKFLOW,branch=BRANCH)
    need(value['event']=='workflow_dispatch','queue resources manual dispatch only');return value


def selected(case):
    need(type(case) is str and case in MEMBERS,'queue resources complete declared history');return MEMBERS[case]


def pins(seed):return {k:seed[k] for k in source.PINS}


def artifact_name(ctx,kind,case=None):
    need(kind in ('seed','raw','verified','aggregate'),'queue resources artifact kind')
    need((kind in ('seed','aggregate') and case is None) or (kind in ('raw','verified') and case in MEMBERS),
         'queue resources artifact history')
    return 'v53-queue-resources-'+kind+'-'+ctx['run']+'-'+ctx['attempt']+'-'+ctx['source']+('-'+case if case else '')


def limit(kind,case):
    if kind=='seed':need(case is None,'queue resources seed history');return shared.MAX_BYTES
    need(kind=='raw','queue resources archive kind');return selected(case).RAW_BYTES+1024**3


def pack(root,output,ctx,kind,case=None):
    need(not Path(output).resolve().is_relative_to(Path(root).resolve()),'queue resources archive separation')
    return shared.pack(root,output,ctx,kind,case,schema=SCHEMA,maximum=limit(kind,case),inventory_fn=inventory)


def unpack(bundle,output,ctx,kind,case=None):
    bundle=Path(bundle)
    need(bundle.is_dir() and not bundle.is_symlink() and {p.name for p in bundle.iterdir()}=={'manifest.json','bundle.tar.gz'},
         'queue resources artifact shape')
    return shared.unpack(bundle,output,ctx,kind,case,schema=SCHEMA,maximum=limit(kind,case),inventory_fn=inventory)


def seed_inputs(data,ctx):
    value=read(data/'seed.json')
    need(value.get('schema')==SCHEMA and value.get('context')==ctx and value.get('cases')==list(HISTORIES) and
         value.get('status')=='PARTIAL' and value.get('phase3Complete') is False,'queue resources seed scope')
    for module in MEMBERS.values():
        need(module.check_pins(pins(value))==value.get('reader'),'queue resources common source reader')
    original,_=h.read_recorded_source(data/'producer')
    need(original['head']==ctx['source'] and h.digest((data/'producer/source.json').read_bytes())==value['sourceSha256'] and
         all(original['files'].get(k)==v for k,v in value['reader']['files'].items()),'queue resources seed source')
    build=read(data/'producer/build.json')
    need(type(build) is dict and set(build)==set(source.BUILDS) and
         h.digest((data/'producer/build.json').read_bytes())==value['buildSha256'],'queue resources seed build')
    for name in source.BUILDS:need(h.inventory(data/'producer/workspace'/name)==build[name],'queue resources seed classes')
    tc.validate(read(data/'producer/toolchain.json'))
    need(tc.pin((data/'producer/toolchain.json').read_bytes())==value['toolchainSha256'],'queue resources seed tools')
    need(shared.dependencies(data/'repository')==value['repositorySha256'],'queue resources seed dependencies')
    return value


def prepare(output,maven,ctx):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);data=output/'data';data.mkdir()
    receipt=dict(schema=SCHEMA,context=ctx,status='FAIL',phase3Complete=False)
    try:
        prepared=shared.prepare_source(data,maven,ctx);reader=source.reader_manifest()
        receipt.update(status='PARTIAL',cases=list(HISTORIES),reader=reader,readerSha256=reader['sha256'],**prepared)
        h.save(data/'seed.json',receipt);seed_inputs(data,ctx);pack(data,output/'artifact',ctx,'seed')
    except BaseException as error:receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


def execute(seed_bundle,output,maven,case,ctx):
    module=selected(case);output=Path(output);output.mkdir(parents=True,exist_ok=False);data=output/'data';data.mkdir()
    receipt=dict(schema=SCHEMA,context=ctx,case=case,status='FAIL',phase3Complete=False)
    try:
        seed_root,manifest=unpack(seed_bundle,output/'seed',ctx,'seed');seed=seed_inputs(seed_root,ctx)
        repository=output/'repository';shutil.copytree(seed_root/'repository',repository)
        with shared.repository_env(repository):
            need(tc.pin(h.snapshot.f.canonical(tc.capture(maven,h.ROOT)))==seed['toolchainSha256'],'queue resources worker tools')
            module.capture(data/'producer',maven,module.PROFILE,source_from=seed_root/'producer')
        need(shared.dependencies(repository)==seed['repositorySha256'],'queue resources execution dependency drift')
        original=module.member(data/'producer',module.PROFILE,pins(seed));seed_inputs(seed_root,ctx)
        receipt.update(status='PARTIAL',seedArchiveSha256=manifest['archiveSha256'],
                       producerReceiptSha256=original['producerReceiptSha256'],**pins(seed))
    except BaseException as error:receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:
        h.save(data/'hosted-member.json',receipt);h.save(output/'receipt.json',receipt)
        failing=sys.exc_info()[0] is not None
        try:pack(data,output/'artifact',ctx,'raw',case)
        except BaseException as error:
            receipt.update(status='FAIL',artifactFailure=dict(type=type(error).__name__,message=str(error)))
            h.save(data/'hosted-member.json',receipt);h.save(output/'receipt.json',receipt)
            if not failing:raise
    return receipt


def verify(seed_bundle,raw_bundle,output,case,ctx):
    module=selected(case);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,context=ctx,case=case,status='FAIL',phase3Complete=False)
    try:
        seed_root,seed_manifest=unpack(seed_bundle,output/'seed',ctx,'seed');seed=seed_inputs(seed_root,ctx)
        raw,manifest=unpack(raw_bundle,output/'original',ctx,'raw',case);claimed=read(raw/'hosted-member.json')
        need(claimed.get('schema')==SCHEMA and claimed.get('context')==ctx and claimed.get('case')==case and
             claimed.get('status')=='PARTIAL' and claimed.get('phase3Complete') is False and
             all(claimed.get(k)==v for k,v in pins(seed).items()) and
             claimed.get('seedArchiveSha256')==seed_manifest['archiveSha256'],'queue resources original member binding')
        result=module.qualify(raw/'producer',module.PROFILE,pins(seed))
        need(result['producerReceiptSha256']==claimed.get('producerReceiptSha256'),'queue resources producer receipt binding')
        seed_inputs(seed_root,ctx)
        need(inventory(raw,maximum=limit('raw',case))==manifest['inventory'],'queue resources downloaded original changed')
        receipt.update(status='PARTIAL',originalFirstDownloadedReplay=True,member=result,
                       seedArchiveSha256=seed_manifest['archiveSha256'],rawArchiveSha256=manifest['archiveSha256'])
    except BaseException as error:receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


def aggregate(seed_bundle,inputs,output,ctx,execute_result,verify_result):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,context=ctx,status='FAIL',phase3Complete=False,
        workflowExecutionAttested=False,combinedPeakResourcesQualified=False)
    try:
        need(execute_result=='success' and verify_result=='success','queue resources failed or missing workflow stage')
        seed_root,manifest=unpack(seed_bundle,output/'seed',ctx,'seed');seed=seed_inputs(seed_root,ctx);inputs=Path(inputs)
        need(inputs.is_dir() and not inputs.is_symlink() and {p.name for p in inputs.iterdir()}==
             {artifact_name(ctx,'verified',case) for case in HISTORIES},'queue resources complete verified set')
        cases={};archives=set();producers=set();verifier_bytes={}
        for case,module in MEMBERS.items():
            path=inputs/artifact_name(ctx,'verified',case)
            need(path.is_dir() and not path.is_symlink() and {p.name for p in path.iterdir()}=={'receipt.json'},
                 'queue resources verifier artifact shape')
            value=read(path/'receipt.json');member=value.get('member',{})
            need(value.get('schema')==SCHEMA and value.get('context')==ctx and value.get('case')==case and
                 value.get('status')=='PARTIAL' and value.get('phase3Complete') is False and
                 value.get('originalFirstDownloadedReplay') is True and value.get('seedArchiveSha256')==manifest['archiveSha256'],
                 'queue resources verifier context')
            expected=dict(schema=module.SCHEMA,status='PASS',profile=module.PROFILE,**pins(seed),
                scope='source-queue-component-only' if case=='source-queue' else 'joint-queue-completion-component-only',
                originalFirst=True,originalPreserved=True,queuePressureQualified=True,combinedResourcesQualified=False,phase3Complete=False)
            if case=='queue-completion':expected['nativeFinalCompleted']=True
            need(type(member) is dict and all(type(member.get(k)) is type(v) and member[k]==v for k,v in expected.items()),
                 'queue resources exact owning result')
            module.check_result(member['qualification'],module.PROFILE)
            archive=value.get('rawArchiveSha256');producer=member.get('producerReceiptSha256')
            need(all(source.shared.hash_field(v) for v in (archive,producer,member.get('rawInventorySha256'))),
                 'queue resources original digest')
            need(archive not in archives and producer not in producers,'queue resources duplicated original')
            archives.add(archive);producers.add(producer);cases[case]=value
            verifier_bytes[case]=tc.file_hash(path/'receipt.json')
        seed_inputs(seed_root,ctx)
        need({p.name for p in inputs.iterdir()}=={artifact_name(ctx,'verified',c) for c in HISTORIES},
             'queue resources verifier set changed')
        for case,value in cases.items():
            path=inputs/artifact_name(ctx,'verified',case)/'receipt.json'
            need(read(path)==value and tc.file_hash(path)==verifier_bytes[case],'queue resources verifier changed during aggregate')
        receipt.update(status='PARTIAL',cases=cases,wholeHistories=len(cases),
            negativeCases=sum(len(v['member']['qualification']['negatives']) for v in cases.values()),
            workflowStagesReportedSuccessful=True,declaredQueueOriginalsReplayed=True,
            seedArchiveSha256=manifest['archiveSha256'],**pins(seed),
            acceptanceAuthority='two exact-attempt downloaded verifier receipts; final-source independent replay and observed workflow admission remain required')
    except BaseException as error:receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


def summary(path,ctx,stage,case,result):
    rows=[('Status',result['status']),('Source',ctx['source']),('Run / attempt',ctx['run']+' / '+ctx['attempt']),
          ('History',case or 'two complete originals'),('Phase 3 complete',False)]
    for key in (*source.PINS,'wholeHistories','negativeCases','workflowExecutionAttested'):
        if key in result:rows.append((key,result[key]))
    if 'failure' in result:rows.append(('Failure',result['failure']['message'].replace('|','/').replace('\n',' ')))
    with Path(path).open('a') as stream:
        stream.write('### V5.3 queue resources '+stage+'\n\n| Parameter | Value |\n| --- | --- |\n'+
                     ''.join('| '+k+' | `'+str(v)+'` |\n' for k,v in rows)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('plan','prepare','execute','verify','aggregate'))
    parser.add_argument('--output');parser.add_argument('--seed');parser.add_argument('--inputs');parser.add_argument('--case',choices=HISTORIES)
    args=parser.parse_args();ctx=context()
    if args.command=='plan':print(json.dumps(dict(include=[dict(case=c,id=c) for c in HISTORIES]),separators=(',',':')));return
    need(args.output,'queue resources output required');result=dict(status='FAIL')
    try:
        with shared.progress(args.command,args.case):
            if args.command=='prepare':result=prepare(args.output,tc.locate(h.ROOT/'mvnw',h.ROOT),ctx)
            elif args.command=='execute':result=execute(args.seed,args.output,tc.locate(h.ROOT/'mvnw',h.ROOT),args.case,ctx)
            elif args.command=='verify':result=verify(args.seed,args.inputs,args.output,args.case,ctx)
            else:result=aggregate(args.seed,args.inputs,args.output,ctx,os.environ.get('EXECUTE_RESULT'),os.environ.get('VERIFY_RESULT'))
        print(json.dumps(dict(status=result['status'],phase3Complete=False,receipt=str(Path(args.output)/'receipt.json')),sort_keys=True))
    finally:
        if os.environ.get('GITHUB_STEP_SUMMARY'):summary(os.environ['GITHUB_STEP_SUMMARY'],ctx,args.command,args.case,result)


if __name__=='__main__':main()
