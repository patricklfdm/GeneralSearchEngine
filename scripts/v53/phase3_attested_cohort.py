"""Observe GitHub stages around complete original-first Phase 3 replay.

No downloaded PASS receipt can replace an owning reader. No producer, workflow
dispatch, retry or cloud operation is invoked. This still cannot close missing
coverage/resource obligations or resolve prior failed histories.
"""
import argparse
import json
from pathlib import Path
from . import phase3_workflow_cohort as workflows
from . import phase3_resource_cohort as resources
from . import phase3_resource_workflows as resource_workflows
from . import phase3_resource_artifacts as resource_artifacts
from . import maximum_resource_attested as maximum

histories=workflows.histories;seeds=workflows.seeds;need=seeds.need;h=seeds.h
SCHEMA='gse-v53-phase3-attested-cohort-v4'


def unchanged_originals(index,seed_inputs,inputs,output,result):
    value=seeds.read(index);modules=seeds.adapters();catalogs=seeds.plan.catalogues()
    inventory=histories.raw_inventory(inputs,value,modules,catalogs)
    need(h.digest(seeds.plan.encoded(inventory))==result['rawInventorySha256'],'attested cohort originals changed after replay')
    seed_path=output/'seeds/receipt.json'
    need(seeds.shared.tc.file_hash(seed_path)==result['seedReceiptSha256'],'attested cohort seed receipt changed')
    seed_result=seeds.read(seed_path);histories.exact_directory(seed_inputs,modules)
    for name,member in seed_result['seeds'].items():
        need(seeds.bundle_identity(seed_inputs/name)=={k:member[k] for k in ('manifestSha256','archiveSha256')},
             'attested cohort seed changed after replay')
    need(seeds.read(output/'receipt.json')==result,'attested cohort history receipt changed')


def run(index,seed_inputs,inputs,output,get=workflows.github,*,resource_index,resource_inputs,resource_execution_index,resource_bundles,
        maximum_index,maximum_zips,maximum_bundles):
    index,seed_inputs,inputs,output,resource_index,resource_inputs,resource_execution_index,resource_bundles,maximum_index,maximum_zips,maximum_bundles=map(seeds.unlinked,
        (index,seed_inputs,inputs,output,resource_index,resource_inputs,resource_execution_index,resource_bundles,maximum_index,maximum_zips,maximum_bundles))
    need(all(not p.is_relative_to(output) for p in (index,resource_index,resource_execution_index,maximum_index)) and
         all(not output.is_relative_to(p) and not p.is_relative_to(output)
         for p in (seed_inputs,inputs,resource_inputs,resource_bundles,maximum_zips,maximum_bundles)),'attested cohort output overlaps inputs')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,status='FAIL',execution='observed-workflow-and-original-replay',
        workflowExecutionAttested=False,allDeclaredHistoriesReplayed=False,runtimeQualified=False,
        allSupplementalOriginalsReplayed=False,resourceWorkflowExecutionAttested=False,resourceArtifactsBound=False,
        maximumComponentOriginalsReplayed=False,maximumWorkflowExecutionAttested=False,maximumArtifactsBound=False,
        combinedPeakResourcesQualified=False,frozenScenarioCoverageQualified=False,phase3Complete=False)
    try:
        h.save(output/'capacity.json',maximum.capacity(output))
        raw=seeds.read_bytes(index);(output/'index.json').write_bytes(raw)
        first=workflows.collect(index,output/'workflow-before',get)
        need(first.get('status')=='PARTIAL' and first.get('workflowExecutionAttested') is True,
             'attested cohort workflow prerequisite')
        resource_before=resources.inspect(resource_index,resource_inputs)
        need(resource_before['source']==first['source'],'attested cohort resource source')
        resource_first=resource_workflows.collect(resource_execution_index,output/'resource-workflow-before',get)
        need(resource_first.get('status')=='PARTIAL' and resource_first.get('workflowExecutionAttested') is True and
             resource_first.get('source')==first['source'],'attested cohort supplemental workflow prerequisite')
        bound=resource_artifacts.bind(resource_execution_index,resource_index,resource_inputs,resource_bundles,output/'resource-bindings')
        need(bound.get('status')=='PARTIAL' and bound.get('resourceArtifactsBound') is True and bound.get('phase3Complete') is False and
             bound.get('source')==first['source'] and bound.get('executionIndexSha256')==resource_first['indexSha256'] and
             bound.get('resourceIndexSha256')==resource_before['indexSha256'],'attested cohort supplemental artifact binding')
        maximum_raw=seeds.read_bytes(maximum_index);maximum_value=seeds.plan.decode(maximum_raw)
        maximum.workflows.validate_index(maximum_value,maximum.workflows.adapters())
        need(maximum_value['source']==first['source'],'attested cohort maximum source')
        replayed={}
        def replay_prerequisites(maximum_common):
            # The maximum seeds have already passed their own readers. The
            # history entry reconciles all twelve seeds before its first replay.
            common={k:maximum_common[k] for k in seeds.COMMON_PINS}
            original=histories.run(index,seed_inputs,inputs,output/'histories',expected_common=common)
            need(original.get('status')=='PARTIAL' and original.get('allDeclaredHistoriesReplayed') is True and
                 original.get('workflowExecutionAttested') is False and original.get('source')==first['source'] and
                 original.get('indexSha256')==first['indexSha256'] and all(original.get(k) is False for k in
                     ('phase3Complete','runtimeQualified','combinedPeakResourcesQualified','frozenScenarioCoverageQualified')) and
                 seeds.read(output/'histories/seeds/receipt.json')['commonPins']==common,
                 'attested cohort exact original replay')
            resource_result=resources.run(resource_index,resource_inputs,output/'resources',expected_common=common)
            need(resource_result.get('status')=='PARTIAL' and resource_result.get('allSupplementalOriginalsReplayed') is True and
                 resource_result.get('source')==first['source'] and
                 all(resource_result.get(k) is False for k in ('phase3Complete','combinedPeakResourcesQualified',
                     'resourceWorkflowExecutionAttested','historicalCapacityPrefixQualified')) and
                 resources.inspect(resource_index,resource_inputs)==resource_before,
                 'attested cohort exact supplemental replay')
            replayed.update(original=original,resources=resource_result)
        # Maximum external observations enclose every physical reader. Replay
        # the smaller components first: successful scratch pruning leaves the
        # reserved disk available before retaining two large maximum originals.
        maximum_result=maximum.run(maximum_index,maximum_zips,maximum_bundles,output/'maximum',get,
            expected_common=bound['commonPins'],replay_prerequisites=replay_prerequisites)
        expected=dict(schema=maximum.SCHEMA,status='PARTIAL',source=first['source'],indexSha256=h.digest(maximum_raw),
            workflowExecutionAttested=True,artifactBytesBound=True,maximumComponentOriginalsReplayed=True,wholeHistories=2,
            combinedResourcesQualified=False,wholeReaderMemoryQualified=False,finalSourceCohortQualified=False,
            priorFailuresResolved=False,phase3Complete=False)
        need(type(maximum_result) is dict and all(type(maximum_result.get(k)) is type(v) and maximum_result[k]==v for k,v in expected.items()) and
             all(maximum_result['commonPins'][k]==bound['commonPins'][k] for k in seeds.COMMON_PINS) and
             seeds.read(output/'maximum/receipt.json')==maximum_result and set(replayed)=={'original','resources'},
             'attested cohort exact maximum replay')
        original,resource_result=replayed['original'],replayed['resources']
        # Do not trust retained observation receipts after a long replay. Query
        # all attempts again and preserve both observations without overwriting.
        last=workflows.collect(index,output/'workflow-after',get)
        need(all(first[k]==last[k] for k in ('source','indexSha256','contractsSha256','observationsSha256',
            'selectedJobs','priorAttempts','cohorts')),'attested cohort workflow observations changed during replay')
        resource_last=resource_workflows.collect(resource_execution_index,output/'resource-workflow-after',get)
        need(all(resource_first[k]==resource_last[k] for k in ('source','indexSha256','contractsSha256','observationsSha256',
            'selectedJobs','priorAttempts','cohorts')),'attested cohort supplemental workflow observations changed during replay')
        unchanged_originals(index,seed_inputs,inputs,output/'histories',original)
        resources.unchanged(resource_index,resource_inputs,output/'resources',resource_result)
        resource_artifacts.unchanged(resource_execution_index,resource_index,resource_inputs,resource_bundles,output/'resource-bindings',bound)
        need(seeds.read_bytes(index)==raw and seeds.read_bytes(maximum_index)==maximum_raw,'attested cohort index changed')
        need(seeds.read(output/'maximum/receipt.json')==maximum_result,'attested cohort maximum receipt changed')
        receipt.update(status='PARTIAL',source=first['source'],indexSha256=first['indexSha256'],
            capacitySha256=seeds.shared.tc.file_hash(output/'capacity.json'),
            workflowExecutionAttested=True,allDeclaredHistoriesReplayed=True,historiesReplayed=original['historiesReplayed'],
            groupsReplayed=original['groupsReplayed'],rawArchives=original['rawArchives'],selectedJobs=first['selectedJobs'],
            priorAttempts=first['priorAttempts'],priorAttemptsRequireReview=first['priorAttemptsRequireReview'] or resource_first['priorAttemptsRequireReview'] or maximum_result['priorAttemptsRequireReview'],
            failedOriginalsReplayed=False,candidateWitnesses=original['candidateWitnesses'],
            allSupplementalOriginalsReplayed=True,resourceIndexSha256=resource_result['indexSha256'],
            resourceWorkflowExecutionAttested=True,resourceArtifactsBound=True,
            supplementalJobs=resource_first['selectedJobs'],supplementalPriorAttempts=resource_first['priorAttempts'],
            maximumComponentOriginalsReplayed=True,maximumWorkflowExecutionAttested=True,maximumArtifactsBound=True,
            maximumHistories=maximum_result['wholeHistories'],maximumJobs=6,maximumPriorAttempts=maximum_result['priorAttempts'],
            maximumIndexSha256=maximum_result['indexSha256'],
            receipts={name:seeds.shared.tc.file_hash(output/name/'receipt.json') for name in ('workflow-before','histories','resources','workflow-after',
                'resource-workflow-before','resource-bindings','resource-workflow-after','maximum')},
            acceptanceAuthority='twelve workflow subsets, five supplemental and two maximum originals bound and replayed around exact-attempt observations; combined resource/coverage closure and failed-attempt review remain separate')
    except BaseException as error:
        receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('index','seeds','inputs','resource-index','resources','resource-workflows','resource-artifacts',
                'maximum-workflows','maximum-zips','maximum-bundles','output'):parser.add_argument('--'+key,required=True)
    args=parser.parse_args()
    with seeds.shared.progress('phase3-attested-cohort','original-first'):
        result=run(args.index,args.seeds,args.inputs,args.output,resource_index=args.resource_index,resource_inputs=args.resources,
                   resource_execution_index=args.resource_workflows,resource_bundles=args.resource_artifacts,
                   maximum_index=args.maximum_workflows,maximum_zips=args.maximum_zips,maximum_bundles=args.maximum_bundles)
    print(json.dumps({k:result[k] for k in ('status','historiesReplayed','selectedJobs','phase3Complete')},sort_keys=True))
