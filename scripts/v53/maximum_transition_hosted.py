"""Opt-in maximum-transition original and independent downloaded resource replay.

One original remains indivisible. Execution and replay require the dedicated
large native-Linux runner; the ordinary and V5.2 cloud runners are not selected. Seed and evidence bind the exact source,
workflow, run and attempt. Success qualifies maximum image bytes with this storage transition, not the full runtime resource envelope.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from . import maximum_transition_run as m
from . import remove_process_hosted as shared

h=m.h;need=m.need;tc=shared.tc
WORKFLOW='.github/workflows/v53-maximum-transition.yml'
BRANCH='refs/heads/experiment/v53-maximum-transition'
SCHEMA='gse-v53-maximum-transition-hosted-v1'
PROFILE=m.PROFILE
# Retained raw plus immutable source/build files, independent of runtime budgets.
BUNDLE_BYTES=m.RAW_BYTES+1024**3


def context():
    value=shared.context(workflow=WORKFLOW,branch=BRANCH)
    need(value['event']=='workflow_dispatch','maximum-transition hosted manual dispatch only')
    return value


def pins(seed):return {k:seed[k] for k in m.PINS}


def limit(kind):
    need(kind in ('seed','raw'),'maximum-transition hosted artifact kind')
    return shared.MAX_BYTES if kind=='seed' else BUNDLE_BYTES


def pack(root,output,ctx,kind):
    need(not Path(output).resolve().is_relative_to(Path(root).resolve()),'maximum-transition hosted archive separation')
    return shared.pack(root,output,ctx,kind,PROFILE,schema=SCHEMA,maximum=limit(kind),inventory_fn=m.inventory)


def unpack(bundle,output,ctx,kind):
    bundle=Path(bundle)
    need(bundle.is_dir() and not bundle.is_symlink() and {p.name for p in bundle.iterdir()}=={'manifest.json','bundle.tar.gz'},
         'maximum-transition hosted artifact shape')
    return shared.unpack(bundle,output,ctx,kind,PROFILE,schema=SCHEMA,maximum=limit(kind),inventory_fn=m.inventory)


def seed_inputs(data,ctx):
    value=m.read(data/'seed.json')
    need(value.get('schema')==SCHEMA and value.get('context')==ctx and value.get('profile')==PROFILE and
         value.get('status')=='PARTIAL' and value.get('phase3Complete') is False,'maximum-transition hosted seed scope')
    reader=m.check_pins(pins(value));source,_=h.read_recorded_source(data/'producer')
    need(source['head']==ctx['source'] and h.digest((data/'producer/source.json').read_bytes())==value['sourceSha256'],
         'maximum-transition hosted seed source')
    need(value.get('reader')==reader and all(source['files'].get(k)==v for k,v in reader['files'].items()),
         'maximum-transition hosted source reader')
    build=m.read(data/'producer/build.json')
    need(type(build) is dict and set(build)==set(m.BUILDS) and h.digest((data/'producer/build.json').read_bytes())==value['buildSha256'],
         'maximum-transition hosted seed build')
    for name in m.BUILDS:
        need(h.inventory(data/'producer/workspace'/name)==build[name],'maximum-transition hosted seed classes')
    tc.validate(m.read(data/'producer/toolchain.json'))
    need(tc.pin((data/'producer/toolchain.json').read_bytes())==value['toolchainSha256'],'maximum-transition hosted seed tools')
    need(shared.dependencies(data/'repository')==value['repositorySha256'],'maximum-transition hosted seed dependencies')
    return value


def prepare(output,maven,ctx):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);data=output/'data';data.mkdir()
    receipt=dict(schema=SCHEMA,context=ctx,profile=PROFILE,status='FAIL',phase3Complete=False)
    try:
        prepared=shared.prepare_source(data,maven,ctx);reader=m.reader_manifest()
        receipt.update(status='PARTIAL',reader=reader,readerSha256=reader['sha256'],**prepared)
        h.save(data/'seed.json',receipt);seed_inputs(data,ctx);pack(data,output/'artifact',ctx,'seed')
    except BaseException as error:receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


def execute(seed_bundle,output,maven,ctx):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);data=output/'data';data.mkdir()
    receipt=dict(schema=SCHEMA,context=ctx,profile=PROFILE,status='FAIL',phase3Complete=False)
    try:
        seed_root,manifest=unpack(seed_bundle,output/'seed',ctx,'seed');seed=seed_inputs(seed_root,ctx)
        repository=output/'repository';shutil.copytree(seed_root/'repository',repository)
        with shared.repository_env(repository):
            need(tc.pin(h.snapshot.f.canonical(tc.capture(maven,h.ROOT)))==seed['toolchainSha256'],'maximum-transition hosted worker tools')
            m.capture(data/'producer',maven,PROFILE,source_from=seed_root/'producer')
        need(shared.dependencies(repository)==seed['repositorySha256'],'maximum-transition hosted execution dependencies changed')
        original=m.member(data/'producer',PROFILE,pins(seed));seed_inputs(seed_root,ctx)
        receipt.update(status='PARTIAL',seedArchiveSha256=manifest['archiveSha256'],
                       producerReceiptSha256=original['producerReceiptSha256'],**pins(seed))
    except BaseException as error:receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:
        h.save(data/'hosted-member.json',receipt);h.save(output/'receipt.json',receipt)
        failing=sys.exc_info()[0] is not None
        try:pack(data,output/'artifact',ctx,'raw')
        except BaseException as error:
            receipt.update(status='FAIL',artifactFailure=dict(type=type(error).__name__,message=str(error)))
            h.save(data/'hosted-member.json',receipt);h.save(output/'receipt.json',receipt)
            if not failing:raise
    return receipt


def verify(seed_bundle,raw_bundle,output,ctx,execute_result):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,context=ctx,profile=PROFILE,status='FAIL',phase3Complete=False)
    try:
        from .maximum_transition_capacity import check as capacity
        h.save(output/'capacity.json',capacity(output,'verify'))
        need(execute_result=='success','maximum-transition hosted successful execution job required')
        seed_root,seed_manifest=unpack(seed_bundle,output/'seed',ctx,'seed');seed=seed_inputs(seed_root,ctx)
        raw,raw_manifest=unpack(raw_bundle,output/'original',ctx,'raw');claimed=m.read(raw/'hosted-member.json')
        need(claimed.get('schema')==SCHEMA and claimed.get('context')==ctx and claimed.get('profile')==PROFILE and
             claimed.get('status')=='PARTIAL' and claimed.get('phase3Complete') is False and
             all(claimed.get(k)==v for k,v in pins(seed).items()) and claimed.get('seedArchiveSha256')==seed_manifest['archiveSha256'],
             'maximum-transition hosted original member binding')
        result=m.qualify(raw/'producer',PROFILE,pins(seed))
        need(result['producerReceiptSha256']==claimed.get('producerReceiptSha256'),'maximum-transition hosted producer receipt binding')
        seed_inputs(seed_root,ctx)
        need(m.inventory(raw,maximum=BUNDLE_BYTES)==raw_manifest['inventory'],'maximum-transition hosted downloaded original changed')
        receipt.update(status='PASS',scope='maximum-image-storage-transition',wholeHistories=1,
                       originalFirstDownloadedReplay=True,workflowExecutionAttested=True,
                       seedArchiveSha256=seed_manifest['archiveSha256'],rawArchiveSha256=raw_manifest['archiveSha256'],
                       maximumImageTransitionQualified=True,combinedResourcesQualified=False,
                       **pins(seed),qualification=result)
    except BaseException as error:receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


def summary(path,ctx,stage,result):
    rows=[('Status',result['status']),('Source',ctx['source']),('Run / attempt',ctx['run']+' / '+ctx['attempt']),
          ('Profile',PROFILE),('Scope','One maximum-image storage transition; 16 exact negatives'),('Phase 3 complete',False)]
    for key in (*m.PINS,'wholeHistories','maximumImageTransitionQualified','combinedResourcesQualified'):
        if key in result:rows.append((key,result[key]))
    if 'failure' in result:rows.append(('Failure',result['failure']['message'].replace('|','/').replace('\n',' ')))
    with Path(path).open('a') as stream:
        stream.write('### V5.3 maximum-transition resources '+stage+'\n\n| Parameter | Value |\n| --- | --- |\n'+
                     ''.join('| '+k+' | `'+str(v)+'` |\n' for k,v in rows)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('prepare','execute','verify'))
    parser.add_argument('--output',required=True);parser.add_argument('--seed');parser.add_argument('--inputs')
    a=parser.parse_args();ctx=context();result=dict(status='FAIL')
    try:
        with shared.progress(a.command,PROFILE):
            if a.command=='prepare':result=prepare(a.output,tc.locate(h.ROOT/'mvnw',h.ROOT),ctx)
            elif a.command=='execute':result=execute(a.seed,a.output,tc.locate(h.ROOT/'mvnw',h.ROOT),ctx)
            else:result=verify(a.seed,a.inputs,a.output,ctx,os.environ.get('EXECUTE_RESULT'))
        print(json.dumps(dict(status=result['status'],phase3Complete=False,receipt=str(Path(a.output)/'receipt.json')),sort_keys=True))
    finally:
        if os.environ.get('GITHUB_STEP_SUMMARY'):summary(os.environ['GITHUB_STEP_SUMMARY'],ctx,a.command,result)


if __name__=='__main__':main()
