"""Replay every supplemental resource original against one exact source/build.

This offline entry never runs Maven or trusts prior PASS receipts. Resource
components remain separate histories; their peaks are never added together.
Learner pressure belongs to the twelve-subset history cohort, not this set.
"""
import argparse
import importlib
import json
import re
from pathlib import Path
from . import phase3_seed_cohort as seeds
from . import phase3_history_cohort as histories

need=seeds.need;h=seeds.h
SCHEMA='gse-v53-phase3-resource-cohort-v1'
INDEX_SCHEMA='gse-v53-phase3-resource-set-v1'
COMMON_PINS=('sourceSha256','buildSha256','toolchainSha256')
# Fixed owning code and full profiles. An input cannot select a smoke profile,
# omit an inconvenient component, or import a different validator.
MEMBERS={
    'required-four':('required_four_resource_run','5-REPLACE-required-four','required-four-observed-ownership','observedResourcesQualified'),
    'maximum-image':('maximum_transition_run','maximum-application-remove','maximum-image-storage-transition','maximumImageTransitionQualified'),
    'capacity-completion':('capacity_completion_run','capacity-231','conditional-prefix-storage-continuation','capacityBoundaryQualified'),
    'source-queue':('source_queue_run','source-queue-64mib','source-queue-component-only','queuePressureQualified'),
    'queue-completion':('queue_completion_run','joint-queue-final-64mib','joint-queue-completion-component-only','nativeFinalCompleted'),
}


def adapters():
    return {name:importlib.import_module('.'+row[0],__package__) for name,row in MEMBERS.items()}


def inspect(index,inputs):
    """Validate all producers before spending time on any physical replay."""
    index,inputs=map(seeds.unlinked,(index,inputs));raw=seeds.read_bytes(index);value=seeds.plan.decode(raw)
    need(type(value) is dict and set(value)=={'schema','source','members'} and value['schema']==INDEX_SCHEMA,
         'resource cohort index envelope')
    need(type(value['source']) is str and re.fullmatch('[0-9a-f]{40}',value['source']), 'resource cohort source SHA')
    need(type(value['members']) is dict and set(value['members'])==set(MEMBERS),'resource cohort complete supplemental set')
    histories.exact_directory(inputs,MEMBERS);source=seeds.checkout_source(value['source']);modules=adapters()
    common=None;originals={}
    for name,adapter in modules.items():
        row=value['members'][name];profile=MEMBERS[name][1]
        need(type(row) is dict and set(row)=={'profile','pins'} and row['profile']==profile,'resource cohort exact full profile: '+name)
        reader=adapter.check_pins(row['pins']);pins={k:row['pins'][k] for k in COMMON_PINS}
        if common is None:common=pins
        need(pins==common,'resource cohort mixed source/build/tools: '+name)
        path=seeds.unlinked(inputs/name);member=adapter.member(path,profile,row['pins'])
        recorded,_=h.read_recorded_source(path)
        need(recorded==source and all(source['files'].get(k)==v for k,v in reader['files'].items()),
             'resource cohort original is not exact checkout: '+name)
        originals[name]=dict(producerReceiptSha256=member['producerReceiptSha256'],
            rawInventorySha256=h.digest(h.snapshot.f.canonical(member['inventory'])),
            junitInventory=h.inventory(path/'workspace'/h.MODULE/'target/surefire-reports'),pins=row['pins'])
    need(seeds.read_bytes(index)==raw and seeds.checkout_source(value['source'])==source,'resource cohort source/index changed')
    return dict(source=value['source'],indexSha256=h.digest(raw),commonPins=common,originals=originals)


def check_result(name,result,pins,original):
    adapter=adapters()[name];_,profile,scope,qualified=MEMBERS[name]
    expected=dict(schema=adapter.SCHEMA,status='PASS',scope=scope,profile=profile,
        originalFirst=True,originalPreserved=True,combinedResourcesQualified=False,phase3Complete=False,
        producerReceiptSha256=original['producerReceiptSha256'],rawInventorySha256=original['rawInventorySha256'],**pins)
    expected[qualified]=True
    need(type(result) is dict and all(type(result.get(k)) is type(v) and result[k]==v for k,v in expected.items()),
         'resource cohort owning result binding: '+name)
    if name=='capacity-completion':
        need(result.get('continuationQualified') is True and result.get('historicalPrefixQualified') is False,
             'resource cohort conditional prefix scope')
    if name=='queue-completion':need(result.get('queuePressureQualified') is True,'resource cohort actual joint pressure')
    adapter.check_result(result['qualification'],profile)


def run(index,inputs,output,*,expected_common=None):
    index,inputs,output=map(seeds.unlinked,(index,inputs,output))
    need(not index.is_relative_to(output) and not output.is_relative_to(inputs) and not inputs.is_relative_to(output),
         'resource cohort output overlaps inputs')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,status='FAIL',execution='offline-supplemental-original-replay',
        allSupplementalOriginalsReplayed=False,resourceWorkflowExecutionAttested=False,
        combinedPeakResourcesQualified=False,frozenScenarioCoverageQualified=False,
        historicalCapacityPrefixQualified=False,phase3Complete=False,members={})
    try:
        before=inspect(index,inputs);(output/'index.json').write_bytes(seeds.read_bytes(index))
        h.save(output/'originals.json',before)
        if expected_common is not None:
            need(type(expected_common) is dict and all(before['commonPins'][k]==expected_common.get(k) for k in COMMON_PINS),
                 'resource cohort differs from history seed source/build/tools')
        receipt.update(source=before['source'],indexSha256=before['indexSha256'],commonPins=before['commonPins'],
                       originalsSha256=seeds.shared.tc.file_hash(output/'originals.json'))
        for name,adapter in adapters().items():
            receipt['active']=name;h.save(output/'receipt.json',receipt)
            print(json.dumps(dict(stage='resource-original-replay',member=name,completed=len(receipt['members']))),flush=True)
            with seeds.shared.progress('phase3-resource-original-replay',name):
                result=histories.retained_call(output/name,lambda work:adapter.verify(work,inputs/name,
                    MEMBERS[name][1],before['originals'][name]['pins']))
            check_result(name,result,before['originals'][name]['pins'],before['originals'][name])
            receipt['members'][name]=dict(scope=result['scope'],receiptSha256=seeds.shared.tc.file_hash(output/name/'receipt.json'))
        need(inspect(index,inputs)==before,'resource cohort originals changed during replay')
        receipt.pop('active',None)
        receipt.update(status='PARTIAL',allSupplementalOriginalsReplayed=True,
            acceptanceAuthority='five separate supplemental originals replayed; no summed peaks, workflow attestation or Phase 3 closure')
    except BaseException as error:
        receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


def unchanged(index,inputs,output,result):
    need(inspect(index,inputs)==seeds.read(output/'originals.json') and
         seeds.shared.tc.file_hash(output/'originals.json')==result['originalsSha256'] and
         seeds.read(output/'receipt.json')==result,'resource cohort originals changed after replay')
    for name,row in result['members'].items():
        need(seeds.shared.tc.file_hash(output/name/'receipt.json')==row['receiptSha256'],
             'resource cohort owning receipt changed after replay')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('index','inputs','output'):parser.add_argument('--'+key,required=True)
    args=parser.parse_args()
    with seeds.shared.progress('phase3-resource-cohort','original-first'):
        result=run(args.index,args.inputs,args.output)
    print(json.dumps({k:result[k] for k in ('status','allSupplementalOriginalsReplayed','phase3Complete')},sort_keys=True))
