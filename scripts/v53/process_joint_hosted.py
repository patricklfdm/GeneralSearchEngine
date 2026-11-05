"""Thirty-two whole native joint-floor process histories, isolated execution and downloaded replay.

Exact source/run/attempt binds every artifact. No JVM history is split, retried
or reconstructed from a successful fragment. The scope is not Phase 3 closure.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from . import process_joint_cohort as m
from . import remove_process_hosted as shared

h=m.h;need=m.need;tc=shared.tc
WORKFLOW='.github/workflows/v53-joint-floor-process.yml'
BRANCH='refs/heads/experiment/v53-joint-floor-process'
SCHEMA='gse-v53-joint-floor-process-hosted-v1'
MAX_BYTES=shared.MAX_BYTES
pins=shared.pins
# Each original death/recovery and FINAL/BARRIER continuation is indivisible.
HISTORIES=tuple(m.CASES)


def context():return shared.context(workflow=WORKFLOW,branch=BRANCH)


def artifact_name(ctx,kind,case=None):
    return 'v53-joint-floor-process-'+kind+'-'+ctx['run']+'-'+ctx['attempt']+'-'+ctx['source']+('-'+m.shared.slug(case) if case else '')


def plan():
    return dict(include=[dict(case=case,id=m.shared.slug(case)) for case in m.CASES])


def pack(root,output,ctx,kind,case=None):return shared.pack(root,output,ctx,kind,case,schema=SCHEMA)


def unpack(bundle,output,ctx,kind,case=None):
    bundle=Path(bundle)
    need(bundle.is_dir() and not bundle.is_symlink() and {p.name for p in bundle.iterdir()}=={'manifest.json','bundle.tar.gz'},
         'joint process hosted artifact directory')
    return shared.unpack(bundle,output,ctx,kind,case,schema=SCHEMA)


def seed_inputs(data,ctx):
    value=m.shared.read(data/'seed.json')
    need(value.get('schema')==SCHEMA and value.get('context')==ctx and value.get('status')=='PARTIAL' and
         value.get('phase3Complete') is False and value.get('cases')==list(m.CASES),'joint process hosted seed scope')
    m.check_pins(*pins(value));source,_=h.read_recorded_source(data/'producer')
    need(source['head']==ctx['source'] and h.digest((data/'producer/source.json').read_bytes())==value['sourceSha256'],
         'joint process hosted seed source')
    build=m.shared.read(data/'producer/build.json')
    need(type(build) is dict and set(build)==set(m.shared.BUILDS) and h.digest((data/'producer/build.json').read_bytes())==value['buildSha256'],
         'joint process hosted seed build')
    for name in m.shared.BUILDS:need(h.inventory(data/'producer/workspace'/name)==build[name],'joint process hosted seed classes')
    tc.validate(m.read(data/'producer/toolchain.json'))
    need(tc.pin((data/'producer/toolchain.json').read_bytes())==value['toolchainSha256'] and m.reader_manifest()==value.get('reader'),
         'joint process hosted seed tools/reader')
    need(all(source['files'].get(k)==v for k,v in value['reader']['files'].items()),'joint process hosted reader differs from recorded source')
    need(shared.dependencies(data/'repository')==value['repositorySha256'],'joint process hosted seed dependencies')
    return value


def prepare(output,maven,ctx):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);data=output/'data';data.mkdir()
    receipt=dict(schema=SCHEMA,context=ctx,status='FAIL',phase3Complete=False)
    try:
        prepared=shared.prepare_source(data,maven,ctx);reader=m.reader_manifest()
        receipt.update(status='PARTIAL',cases=list(m.CASES),readerSha256=reader['sha256'],reader=reader,**prepared)
        h.save(data/'seed.json',receipt);seed_inputs(data,ctx);pack(data,output/'artifact',ctx,'seed')
    except BaseException as error:receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


def execute(seed_bundle,output,maven,case,ctx):
    need(case in m.CASES,'joint process hosted declared execution')
    output=Path(output);output.mkdir(parents=True,exist_ok=False);data=output/'data';data.mkdir()
    receipt=dict(schema=SCHEMA,context=ctx,case=case,status='FAIL',phase3Complete=False)
    try:
        seed_root,manifest=unpack(seed_bundle,output/'seed',ctx,'seed');seed=seed_inputs(seed_root,ctx)
        repository=output/'repository';shutil.copytree(seed_root/'repository',repository)
        with shared.repository_env(repository):
            need(tc.pin(h.snapshot.f.canonical(tc.capture(maven,h.ROOT)))==seed['toolchainSha256'],
                 'joint process hosted worker toolchain')
            m.capture(data/'producer',maven,case,source_from=seed_root/'producer')
        need(shared.dependencies(repository)==seed['repositorySha256'],'joint process hosted runtime dependency drift')
        original=m.member(data/'producer',case,*pins(seed));seed_inputs(seed_root,ctx)
        receipt.update(status='PARTIAL',seedArchiveSha256=manifest['archiveSha256'],
            producerReceiptSha256=original['receiptSha256'],originalPlans=original['plans'],
            **{name+'Sha256':value for name,value in zip(('source','build','toolchain','reader'),pins(seed))})
    except BaseException as error:receipt.update(failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:
        h.save(data/'hosted-member.json',receipt);h.save(output/'receipt.json',receipt)
        # Keep a failed original as well; it is never a successful cohort member.
        failing=sys.exc_info()[0] is not None
        try:pack(data,output/'artifact',ctx,'raw',case)
        except BaseException as error:
            receipt.update(status='FAIL',artifactFailure=dict(type=type(error).__name__,message=str(error)))
            h.save(data/'hosted-member.json',receipt);h.save(output/'receipt.json',receipt)
            if not failing:raise
    return receipt


def verify(seed_bundle,raw_bundle,output,case,ctx):
    need(case in m.CASES,'joint process hosted declared verification');output=Path(output);output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,context=ctx,case=case,status='FAIL',phase3Complete=False)
    try:
        seed_root,seed_manifest=unpack(seed_bundle,output/'seed',ctx,'seed');seed=seed_inputs(seed_root,ctx)
        raw,raw_manifest=unpack(raw_bundle,output/'original',ctx,'raw',case);claimed=m.shared.read(raw/'hosted-member.json')
        need(claimed.get('schema')==SCHEMA and claimed.get('context')==ctx and claimed.get('case')==case and
             claimed.get('status')=='PARTIAL' and claimed.get('phase3Complete') is False and
             [claimed.get(name+'Sha256') for name in ('source','build','toolchain','reader')]==pins(seed) and
             claimed.get('seedArchiveSha256')==seed_manifest['archiveSha256'],'joint process hosted original member binding')
        member=m.qualify_member(raw/'producer',case,*pins(seed))
        need(member['producerReceiptSha256']==claimed.get('producerReceiptSha256') and
             member['plans']==claimed.get('originalPlans'),'joint process hosted original receipt binding')
        seed_inputs(seed_root,ctx)
        need(h.inventory(raw,maximum=MAX_BYTES)==raw_manifest['inventory'],'joint process hosted downloaded original changed')
        receipt.update(status='PARTIAL',seedArchiveSha256=seed_manifest['archiveSha256'],rawArchiveSha256=raw_manifest['archiveSha256'],
                       originalFirstDownloadedReplay=True,member=member)
    except BaseException as error:receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


def aggregate(seed_bundle,inputs,output,ctx,execute_result,verify_result, *, offline_replay=False):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);receipt=dict(schema=SCHEMA,context=ctx,status='FAIL',phase3Complete=False)
    try:
        shared.aggregate_precondition(execute_result, verify_result, offline_replay, 'joint process hosted failed/missing workflow stage')
        seed_root,manifest=unpack(seed_bundle,output/'seed',ctx,'seed');seed=seed_inputs(seed_root,ctx);inputs=Path(inputs)
        need(inputs.is_dir() and not inputs.is_symlink() and {p.name for p in inputs.iterdir()}==
             {artifact_name(ctx,'verified',p) for p in m.CASES},'joint process hosted complete verified inventory')
        cases=[];histories=set();archives=set();receipts=set()
        for case in m.CASES:
            directory=inputs/artifact_name(ctx,'verified',case)
            need(directory.is_dir() and not directory.is_symlink() and {p.name for p in directory.iterdir()}=={'receipt.json'},
                 'joint process hosted verifier artifact shape')
            value=m.shared.read(directory/'receipt.json');member=value.get('member',{})
            need(value.get('schema')==SCHEMA and value.get('context')==ctx and value.get('case')==case and value.get('status')=='PARTIAL' and
                 value.get('phase3Complete') is False and value.get('originalFirstDownloadedReplay') is True and
                 value.get('seedArchiveSha256')==manifest['archiveSha256'],'joint process hosted verifier context')
            need(member.get('case')==case and member.get('status')=='PASS' and member.get('phase3Complete') is False and
                 [member.get(name+'Sha256') for name in ('source','build','toolchain','reader')]==pins(seed),'joint process hosted verifier pins')
            m.check_result(member['qualification'],case)
            plans=member.get('plans')
            need(type(plans) is dict and set(plans)=={case} and
                 all(m.shared.hash_field(v) for v in plans.values()) and
                 len(set(plans.values()))==len(plans),'joint process hosted complete original plans')
            need(m.shared.hash_field(member.get('producerReceiptSha256')) and
                 m.shared.hash_field(value.get('rawArchiveSha256')),'joint process hosted original digest')
            need(not histories.intersection(plans.values()) and value['rawArchiveSha256'] not in archives and
                 member['producerReceiptSha256'] not in receipts,'joint process hosted duplicated history')
            histories.update(plans.values());archives.add(value['rawArchiveSha256']);receipts.add(member['producerReceiptSha256']);cases.append(value)
        need(len(histories)==len(m.CASES),'joint process hosted complete ownership histories')
        seed_inputs(seed_root,ctx)
        negatives=[v for case in cases for v in case['member']['qualification']['negatives']]
        need(len(negatives)==sum(len(m.negative_cases(case)) for case in m.CASES),
             'joint process hosted complete cut-specific negative count')
        receipt.update(status='PASS',cases=cases,wholeOwnershipHistories=len(histories),nativeCases=len(m.CASES),negativeCases=len(negatives),
            rejected=sum(v['status']=='REJECTED' for v in negatives),seedArchiveSha256=manifest['archiveSha256'],
            **{name+'Sha256':value for name,value in zip(('source','build','toolchain','reader'),pins(seed))},
            declaredJointFloorProcessHistoriesQualified=True,processDeathQualified=False,allMembershipProfilesQualified=False,combinedPeakResourcesQualified=False,
            autonomousCompetitionQualified=False,completePhysicalQualified=False,powerLossQualified=False,
            acceptanceAuthority='all exact-attempt workflow stages plus 32 whole-history downloaded original-first verifier receipts')
        shared.complete_aggregate(receipt, offline_replay)
    except BaseException as error:receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


def summary(path,ctx,command,case,result):
    rows=[('Source',ctx['source']),('Run / attempt',ctx['run']+' / '+ctx['attempt']),('Copy / cut / mode',case or 'all 32 histories'),
          ('Status',result['status']),('Scope','Original joint-floor death, scratch recovery and FINAL/BARRIER'),('Phase 3 complete',False)]
    rows.extend([('Declared histories',len(m.CASES)),('Expected negative results',
                 len(m.negative_cases(case)) if case else sum(len(m.negative_cases(k)) for k in m.CASES))])
    for name in ('wholeOwnershipHistories','nativeCases','negativeCases','rejected'):
        if name in result:rows.append((name,result[name]))
    for name in ('sourceSha256','buildSha256','toolchainSha256','readerSha256'):
        if name in result:rows.append((name,result[name]))
    with Path(path).open('a') as stream:
        stream.write('### V5.3 joint-floor process histories '+command+'\n\n| Parameter | Value |\n| --- | --- |\n'+
                     ''.join('| '+k+' | `'+str(v)+'` |\n' for k,v in rows)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('plan','prepare','execute','verify','aggregate'))
    parser.add_argument('--output');parser.add_argument('--seed');parser.add_argument('--inputs');parser.add_argument('--case',choices=m.CASES)
    args=parser.parse_args();ctx=context()
    if args.command=='plan':
        print(json.dumps(plan(),separators=(',',':')));return
    need(args.output,'joint process hosted output required');result=dict(status='FAIL')
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
