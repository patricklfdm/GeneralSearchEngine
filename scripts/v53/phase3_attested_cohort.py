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

histories=workflows.histories;seeds=workflows.seeds;need=seeds.need;h=seeds.h
SCHEMA='gse-v53-phase3-attested-cohort-v3'


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


def run(index,seed_inputs,inputs,output,get=workflows.github,*,resource_index,resource_inputs,resource_execution_index,resource_bundles):
    index,seed_inputs,inputs,output,resource_index,resource_inputs,resource_execution_index,resource_bundles=map(seeds.unlinked,
        (index,seed_inputs,inputs,output,resource_index,resource_inputs,resource_execution_index,resource_bundles))
    need(all(not p.is_relative_to(output) for p in (index,resource_index,resource_execution_index)) and
         all(not output.is_relative_to(p) and not p.is_relative_to(output)
         for p in (seed_inputs,inputs,resource_inputs,resource_bundles)),'attested cohort output overlaps inputs')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,status='FAIL',execution='observed-workflow-and-original-replay',
        workflowExecutionAttested=False,allDeclaredHistoriesReplayed=False,runtimeQualified=False,
        allSupplementalOriginalsReplayed=False,resourceWorkflowExecutionAttested=False,resourceArtifactsBound=False,
        combinedPeakResourcesQualified=False,frozenScenarioCoverageQualified=False,phase3Complete=False)
    try:
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
        original=histories.run(index,seed_inputs,inputs,output/'histories',expected_common=bound['commonPins'])
        need(original.get('status')=='PARTIAL' and original.get('allDeclaredHistoriesReplayed') is True and
             original.get('workflowExecutionAttested') is False and original.get('source')==first['source'] and
             original.get('indexSha256')==first['indexSha256'] and all(original.get(k) is False for k in
                 ('phase3Complete','runtimeQualified','combinedPeakResourcesQualified','frozenScenarioCoverageQualified')),
             'attested cohort exact original replay')
        common=seeds.read(output/'histories/seeds/receipt.json')['commonPins']
        resource_result=resources.run(resource_index,resource_inputs,output/'resources',expected_common=common)
        need(resource_result.get('status')=='PARTIAL' and resource_result.get('allSupplementalOriginalsReplayed') is True and
             resource_result.get('source')==first['source'] and
             all(resource_result.get(k) is False for k in ('phase3Complete','combinedPeakResourcesQualified',
                 'resourceWorkflowExecutionAttested','historicalCapacityPrefixQualified')) and
             resources.inspect(resource_index,resource_inputs)==resource_before,
             'attested cohort exact supplemental replay')
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
        need(seeds.read_bytes(index)==raw,'attested cohort index changed')
        receipt.update(status='PARTIAL',source=first['source'],indexSha256=first['indexSha256'],
            workflowExecutionAttested=True,allDeclaredHistoriesReplayed=True,historiesReplayed=original['historiesReplayed'],
            groupsReplayed=original['groupsReplayed'],rawArchives=original['rawArchives'],selectedJobs=first['selectedJobs'],
            priorAttempts=first['priorAttempts'],priorAttemptsRequireReview=first['priorAttemptsRequireReview'] or resource_first['priorAttemptsRequireReview'],
            failedOriginalsReplayed=False,candidateWitnesses=original['candidateWitnesses'],
            allSupplementalOriginalsReplayed=True,resourceIndexSha256=resource_result['indexSha256'],
            resourceWorkflowExecutionAttested=True,resourceArtifactsBound=True,
            supplementalJobs=resource_first['selectedJobs'],supplementalPriorAttempts=resource_first['priorAttempts'],
            receipts={name:seeds.shared.tc.file_hash(output/name/'receipt.json') for name in ('workflow-before','histories','resources','workflow-after',
                'resource-workflow-before','resource-bindings','resource-workflow-after')},
            acceptanceAuthority='twelve workflow subsets and five supplemental originals bound and replayed around exact-attempt observations; combined resource/coverage closure and failed-attempt review remain separate')
    except BaseException as error:
        receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('index','seeds','inputs','resource-index','resources','resource-workflows','resource-artifacts','output'):parser.add_argument('--'+key,required=True)
    args=parser.parse_args()
    with seeds.shared.progress('phase3-attested-cohort','original-first'):
        result=run(args.index,args.seeds,args.inputs,args.output,resource_index=args.resource_index,resource_inputs=args.resources,
                   resource_execution_index=args.resource_workflows,resource_bundles=args.resource_artifacts)
    print(json.dumps({k:result[k] for k in ('status','historiesReplayed','selectedJobs','phase3Complete')},sort_keys=True))
