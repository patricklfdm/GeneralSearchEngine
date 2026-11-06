"""Observe GitHub stages around complete original-first Phase 3 replay.

No downloaded PASS receipt can replace an owning reader. No producer, workflow
dispatch, retry or cloud operation is invoked. This still cannot close missing
coverage/resource obligations or resolve prior failed histories.
"""
import argparse
import json
from pathlib import Path
from . import phase3_workflow_cohort as workflows

histories=workflows.histories;seeds=workflows.seeds;need=seeds.need;h=seeds.h
SCHEMA='gse-v53-phase3-attested-cohort-v1'


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


def run(index,seed_inputs,inputs,output,get=workflows.github):
    index,seed_inputs,inputs,output=map(seeds.unlinked,(index,seed_inputs,inputs,output))
    need(not index.is_relative_to(output) and all(not output.is_relative_to(p) and not p.is_relative_to(output)
         for p in (seed_inputs,inputs)),'attested cohort output overlaps inputs')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,status='FAIL',execution='observed-workflow-and-original-replay',
        workflowExecutionAttested=False,allDeclaredHistoriesReplayed=False,runtimeQualified=False,
        combinedPeakResourcesQualified=False,frozenScenarioCoverageQualified=False,phase3Complete=False)
    try:
        raw=seeds.read_bytes(index);(output/'index.json').write_bytes(raw)
        first=workflows.collect(index,output/'workflow-before',get)
        need(first.get('status')=='PARTIAL' and first.get('workflowExecutionAttested') is True,
             'attested cohort workflow prerequisite')
        original=histories.run(index,seed_inputs,inputs,output/'histories')
        need(original.get('status')=='PARTIAL' and original.get('allDeclaredHistoriesReplayed') is True and
             original.get('workflowExecutionAttested') is False and original.get('source')==first['source'] and
             original.get('indexSha256')==first['indexSha256'] and all(original.get(k) is False for k in
                 ('phase3Complete','runtimeQualified','combinedPeakResourcesQualified','frozenScenarioCoverageQualified')),
             'attested cohort exact original replay')
        # Do not trust retained observation receipts after a long replay. Query
        # all attempts again and preserve both observations without overwriting.
        last=workflows.collect(index,output/'workflow-after',get)
        need(all(first[k]==last[k] for k in ('source','indexSha256','contractsSha256','observationsSha256',
            'selectedJobs','priorAttempts','cohorts')),'attested cohort workflow observations changed during replay')
        unchanged_originals(index,seed_inputs,inputs,output/'histories',original)
        need(seeds.read_bytes(index)==raw,'attested cohort index changed')
        receipt.update(status='PARTIAL',source=first['source'],indexSha256=first['indexSha256'],
            workflowExecutionAttested=True,allDeclaredHistoriesReplayed=True,historiesReplayed=original['historiesReplayed'],
            groupsReplayed=original['groupsReplayed'],rawArchives=original['rawArchives'],selectedJobs=first['selectedJobs'],
            priorAttempts=first['priorAttempts'],priorAttemptsRequireReview=first['priorAttemptsRequireReview'],
            failedOriginalsReplayed=False,candidateWitnesses=original['candidateWitnesses'],
            receipts={name:seeds.shared.tc.file_hash(output/name/'receipt.json') for name in ('workflow-before','histories','workflow-after')},
            acceptanceAuthority='all declared originals replayed with observed workflow stages; resource/coverage closure and failed-attempt review remain separate')
    except BaseException as error:
        receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('index','seeds','inputs','output'):parser.add_argument('--'+key,required=True)
    args=parser.parse_args()
    with seeds.shared.progress('phase3-attested-cohort','original-first'):
        result=run(args.index,args.seeds,args.inputs,args.output)
    print(json.dumps({k:result[k] for k in ('status','historiesReplayed','selectedJobs','phase3Complete')},sort_keys=True))
