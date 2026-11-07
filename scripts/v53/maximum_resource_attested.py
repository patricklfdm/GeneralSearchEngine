"""Live exact-attempt byte binding around both owning maximum component readers.

Two separate whole histories remain two components: never sum their peaks or
promote this prerequisite to combined-resource, final-source or Phase 3 closure.
"""
import argparse
import json
import math
import sys
from pathlib import Path
from . import maximum_resource_artifacts as artifacts
from . import maximum_native_capacity as hosted_capacity
from .maximum_transition_inventory import inventory

workflows=artifacts.workflows;seeds=artifacts.seeds;h=artifacts.h;need=artifacts.need;tc=artifacts.tc
SCHEMA='gse-v53-maximum-resource-attested-v1'
COMMON_PINS=(*seeds.COMMON_PINS,'readerSha256')
MINIMUM_FREE_BYTES=448*1024**3
OBSERVATION_BYTES=1024**3
SCOPES={'maximum-native':'maximum-native-required-four-observed-ownership',
        'maximum-queue':'maximum-image-joint-queue-component-only'}


def capacity(path):
    observed=hosted_capacity.check(path,'verify-download')
    need(observed['capacity']['freeBytes']>=MINIMUM_FREE_BYTES,
         'maximum attested insufficient disk for both retained originals')
    return dict(schema='gse-v53-maximum-attested-capacity-v1',status='PASS',minimumFreeBytes=MINIMUM_FREE_BYTES,
                observed=observed,runtimeBudgetsChanged=False,phase3Complete=False)


def binding_result(value,output,source,index_hash):
    need(type(value) is dict and value.get('schema')==artifacts.SCHEMA and value.get('status')=='PARTIAL' and
         value.get('source')==source and value.get('indexSha256')==index_hash and
         all(value.get(k) is True for k in ('workflowExecutionAttested','artifactBytesBound')) and
         all(value.get(k) is False for k in ('originalHistoriesReplayed','priorFailuresResolved','combinedResourcesQualified','phase3Complete')) and
         type(value.get('selectedJobs')) is int and value['selectedJobs']==6,
         'maximum attested external binding prerequisite')
    need(seeds.read(output/'receipt.json')==value,'maximum attested retained binding receipt')
    for field,name in (('bindingsSha256','bindings.json'),('localInputsSha256','local-inputs.json'),
                       ('observationInventoriesSha256','observation-inventories.json')):
        need(value.get(field)==tc.file_hash(output/name),'maximum attested binding digest')
    return seeds.read(output/'bindings.json')


def inspect_seeds(value,bundles,output,bound):
    source=seeds.checkout_source(value['source']);common=None;prepared={};modules=workflows.adapters()
    for name,adapter in modules.items():
        ctx=value['cohorts'][name];root,manifest=adapter.unpack(bundles/name/'seed',output/name,ctx,'seed')
        need(manifest['archiveSha256']==bound[name]['seed']['archiveSha256'],'maximum attested externally bound seed')
        seed=adapter.seed_inputs(root,ctx);preparation,_=seeds.preparation(root,seed)
        original,_=h.read_recorded_source(root/'producer')
        need(original==source,'maximum attested seed is not exact checkout')
        selected={k:seed[k] for k in COMMON_PINS}
        need(all(seeds.shared.m.hash_field(v) for v in selected.values()),'maximum attested seed pins')
        if common is None:common=selected
        need(selected==common,'maximum attested mixed source/build/tools/reader/dependencies')
        prepared[name]=dict(pins=adapter.pins(seed),preparation=preparation,seed=seed,
                           inventory=inventory(root,maximum=adapter.limit('seed')))
    return common,prepared,source


def check_replay(name,adapter,result,path,ctx,pins,bound):
    expected=dict(schema=adapter.SCHEMA,status='PASS',context=ctx,profile=adapter.PROFILE,scope=SCOPES[name],
        wholeHistories=1,originalFirstDownloadedReplay=True,combinedResourcesQualified=False,
        wholeReaderMemoryQualified=False,phase3Complete=False,
        seedArchiveSha256=bound['seed']['archiveSha256'],rawArchiveSha256=bound['raw']['archiveSha256'],**pins)
    expected.update(observedResourcesQualified=True) if name=='maximum-native' else expected.update(
        queuePressureQualified=True,nativeFinalCompleted=True,maximumImageQueueQualified=True)
    need(type(result) is dict and all(type(result.get(k)) is type(v) and result[k]==v for k,v in expected.items()),
         'maximum attested owning replay scope/binding')
    need(seeds.read(path/'receipt.json')==result,'maximum attested retained replay receipt')
    # Recheck the actual child measurement and complete owner-specific result,
    # including exact negatives; a returned parent PASS label is insufficient.
    measurement=path/'measurement';execution=seeds.read(measurement/'execution.json')
    command=[sys.executable,'-B','-m',adapter.reader.__name__,str(measurement/'reader'),
             '--producer',str(path/'original/data/producer'),'--pins',str(measurement/'pins.json')]
    need(type(execution) is dict and set(execution)=={'command','exit','elapsedSeconds'} and
         execution['command']==command and type(execution['exit']) is int and execution['exit']==0 and
         type(execution['elapsedSeconds']) in (int,float) and math.isfinite(execution['elapsedSeconds']) and execution['elapsedSeconds']>=0 and
         seeds.read(measurement/'pins.json')==pins and (measurement/'reader.log').is_file(),
         'maximum attested exact fresh reader execution')
    qualified,memory=adapter.reader.result(measurement/'reader',pins)
    need(qualified==result.get('qualification') and memory==result.get('readerMemory'),
         'maximum attested owning child result/measurement')
    member=adapter.m.member(path/'original/data/producer',adapter.PROFILE,pins)
    need(qualified['producerReceiptSha256']==member['producerReceiptSha256'] and
         qualified['rawInventorySha256']==h.digest(h.snapshot.f.canonical(member['inventory'])),
         'maximum attested original producer/result binding')
    return dict(scope=result['scope'],receiptSha256=tc.file_hash(path/'receipt.json'),
                producerReceiptSha256=member['producerReceiptSha256'],rawInventorySha256=qualified['rawInventorySha256'],
                readerMemory=memory,inventory=inventory(path,maximum=adapter.BUNDLE_BYTES+adapter.limit('seed')+OBSERVATION_BYTES))


def run(index,zips,bundles,output,get=artifacts.github,*,expected_common=None,replay_prerequisites=None):
    """Optionally enclose the other cohort readers in this observation interval.

    The callback is an in-process composition hook, never an input-selected
    reader or a receipt granting acceptance. All maximum seed checks precede
    it; its exception stops this run before either maximum reader. Its return
    value is ignored and cannot qualify either maximum component.
    """
    index,zips,bundles,output=map(seeds.unlinked,(index,zips,bundles,output))
    need(not index.is_relative_to(output) and all(not p.is_relative_to(output) and not output.is_relative_to(p) for p in (zips,bundles)),
         'maximum attested output overlaps inputs')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,status='FAIL',workflowExecutionAttested=False,artifactBytesBound=False,
        maximumComponentOriginalsReplayed=False,combinedResourcesQualified=False,wholeReaderMemoryQualified=False,
        finalSourceCohortQualified=False,priorFailuresResolved=False,phase3Complete=False,members={})
    try:
        raw=seeds.read_bytes(index);value=seeds.plan.decode(raw);modules=workflows.adapters();workflows.validate_index(value,modules)
        (output/'index.json').write_bytes(raw);h.save(output/'capacity.json',capacity(output))
        first=artifacts.bind(index,zips,bundles,output/'binding-before',get)
        bound=binding_result(first,output/'binding-before',value['source'],h.digest(raw))
        external_before=inventory(output/'binding-before',maximum=4*1024**3)
        common,prepared,source=inspect_seeds(value,bundles,output/'seeds',bound)
        h.save(output/'prepared.json',dict(commonPins=common,members=prepared))
        if expected_common is not None:
            need(type(expected_common) is dict and set(expected_common)==set(seeds.COMMON_PINS) and
                 all(common[k]==expected_common[k] for k in seeds.COMMON_PINS),
                 'maximum attested differs from cohort source/build/tools/dependencies')
        if replay_prerequisites is not None:
            receipt['active']='cohort-prerequisites';h.save(output/'receipt.json',receipt)
            replay_prerequisites(dict(common))
        completed={};results={}
        for name,adapter in modules.items():
            receipt['active']=name;h.save(output/'receipt.json',receipt)
            print(json.dumps(dict(stage='maximum-owning-physical-replay',component=name,completed=len(completed))),flush=True)
            with seeds.shared.progress('maximum-attested-owning-reader',name):
                result=adapter.verify(bundles/name/'seed',bundles/name/'raw',output/'replay'/name,value['cohorts'][name],'success')
                completed[name]=check_replay(name,adapter,result,output/'replay'/name,value['cohorts'][name],prepared[name]['pins'],bound[name])
            results[name]=result
            receipt['members'][name]={k:v for k,v in completed[name].items() if k!='inventory'}
            h.save(output/'receipt.json',receipt)
        # Repeat live job/attempt/artifact observation and byte binding after
        # the full physical replay. No cached green observation is authoritative.
        last=artifacts.bind(index,zips,bundles,output/'binding-after',get)
        last_bound=binding_result(last,output/'binding-after',value['source'],h.digest(raw))
        need(bound==last_bound and all(first[k]==last[k] for k in ('source','indexSha256','selectedJobs','priorAttempts',
             'priorAttemptsRequireReview','bindingsSha256','localInputsSha256')),'maximum attested external bindings changed across replay')
        # Byte equality alone cannot detect changed API step outcomes or times.
        for role in ('workflow-before','workflow-after'):
            before=seeds.read(output/'binding-before'/role/'receipt.json');after=seeds.read(output/'binding-after'/role/'receipt.json')
            need(all(before[k]==after[k] for k in ('source','indexSha256','contractsSha256','observationsSha256',
                'selectedJobs','priorAttempts','cohorts')),'maximum attested workflow observations changed across replay')
        for role in ('artifacts-before','artifacts-after'):
            need(seeds.read(output/'binding-before'/role/'selected.json')==seeds.read(output/'binding-after'/role/'selected.json'),
                 'maximum attested artifact metadata changed across replay')
        for name,adapter in modules.items():
            seed_root=output/'seeds'/name/'data';seed=prepared[name]
            need(adapter.seed_inputs(seed_root,value['cohorts'][name])==seed['seed'] and
                 inventory(seed_root,maximum=adapter.limit('seed'))==seed['inventory'],'maximum attested preparation changed across replay')
            need(check_replay(name,adapter,results[name],output/'replay'/name,value['cohorts'][name],seed['pins'],bound[name])==completed[name],
                 'maximum attested owning original/receipt changed after replay')
        need(inventory(output/'binding-before',maximum=4*1024**3)==external_before,
             'maximum attested retained first observation changed')
        need(seeds.read(output/'prepared.json')==dict(commonPins=common,members=prepared) and
             seeds.read_bytes(index)==raw and seeds.checkout_source(value['source'])==source,
             'maximum attested source/index/preparation changed')
        h.save(output/'replay-inventories.json',{name:row['inventory'] for name,row in completed.items()})
        receipt.pop('active',None)
        receipt.update(status='PARTIAL',source=value['source'],indexSha256=h.digest(raw),commonPins=common,
            workflowExecutionAttested=True,artifactBytesBound=True,maximumComponentOriginalsReplayed=True,wholeHistories=2,
            priorAttempts=first['priorAttempts'],priorAttemptsRequireReview=first['priorAttemptsRequireReview'],
            beforeBindingSha256=tc.file_hash(output/'binding-before/receipt.json'),afterBindingSha256=tc.file_hash(output/'binding-after/receipt.json'),
            preparedSha256=tc.file_hash(output/'prepared.json'),replayInventoriesSha256=tc.file_hash(output/'replay-inventories.json'),
            acceptanceAuthority='two separate maximum component originals, externally bound and independently replayed; no summed peaks or Phase 3 closure')
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('index','zips','bundles','output'):p.add_argument('--'+k,required=True)
    a=p.parse_args()
    with seeds.shared.progress('maximum-resource-attested','whole-originals'):
        result=run(a.index,a.zips,a.bundles,a.output)
    print(json.dumps({k:result[k] for k in ('status','maximumComponentOriginalsReplayed','phase3Complete')},sort_keys=True))
