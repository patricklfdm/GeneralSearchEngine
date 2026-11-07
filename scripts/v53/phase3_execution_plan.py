"""Offline execution handoff from the actual Phase 3 workflow contracts.

No dispatch, Git write, build, API request or original replay. A plan is not
execution evidence and cannot fill any cohort slot or close a requirement.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import shlex
import subprocess
from . import phase3_workflow_cohort as workflows
from . import phase3_resource_workflows as resources
from . import maximum_resource_workflows as maximum
from . import maximum_native_capacity as native_capacity
from . import maximum_resource_attested as attested

seeds=workflows.seeds;plan=seeds.plan;need=seeds.need
SCHEMA='gse-v53-phase3-execution-plan-v1'


def entries(source):
    catalogs=plan.catalogues();modules=seeds.adapters();rows=[]
    for family,adapters in (('histories',modules),('resources',resources.adapters()),('maximum',maximum.adapters())):
        for name,adapter in adapters.items():
            raw=plan.regular(plan.ROOT,adapter.WORKFLOW);text=raw.decode()
            need(source['files'].get(adapter.WORKFLOW)==plan.digest(raw),'execution plan workflow/source drift')
            events=text.split('\non:\n')[1].split('\npermissions:',1)[0]
            dispatch=re.findall(r'^  workflow_dispatch:\n(.*?)(?=^  [a-z_]+:|\Z)',events,re.M|re.S)
            need(len(dispatch)==1 and not dispatch[0].strip(),'execution plan unsupported dispatch inputs')
            push=re.findall(r'^  push:\n(.*?)(?=^  [a-z_]+:|\Z)',events,re.M|re.S)
            branch=adapter.BRANCH.removeprefix('refs/heads/')
            need(not push or len(push)==1 and push[0].strip()=='branches: ['+branch+']',
                 'execution plan push trigger differs from owning branch')
            if family=='histories':contract=workflows.contract(name,adapter,catalogs[name],text)
            else:contract=(resources if family=='resources' else maximum).contract(name,adapter,text)
            chunks=re.split(r'^  ([\w-]+):\n',text.split('\njobs:\n')[1],flags=re.M)
            blocks=dict(zip(chunks[1::2],chunks[2::2]));roles={}
            for role,body in blocks.items():
                runner=re.findall(r'^    runs-on: (.+)$',body,re.M)
                need(len(runner)==1,'execution plan exact runner')
                parallel=re.findall(r'^      max-parallel: ([1-9][0-9]*)$',body,re.M)
                need(len(parallel)<=1,'execution plan parallel setting')
                dependency=re.findall(r'^    needs: (.+)$',body,re.M)
                need(len(dependency)<=1,'execution plan dependency setting')
                roles[role]=dict(runsOn=runner[0],jobs=sum(j['role']==role for j in contract['jobs'].values()),
                                 matrixMaximumParallel=int(parallel[0]) if parallel else None,
                                 needs=[v.strip() for v in dependency[0].strip('[]').split(',')] if dependency else [])
            large=any('gse-v53-large-evidence' in role['runsOn'] for role in roles.values())
            row=dict(id=family+'/'+name,family=family,name=name,workflow=adapter.WORKFLOW,
                     workflowSha256=contract['workflowSha256'],groups=contract['groups'],
                     selectedJobs=len(contract['jobs']),roles=roles,jobContracts=contract['jobs'],
                     requiresLargeHost=large,pushTriggerRef=adapter.BRANCH if push else None,
                     manualDispatchRequiresDefaultBranchWorkflow=True)
            if large:row['concurrency']=workflows.large_runner_concurrency(text)
            if family=='histories':row['wholeHistories']=catalogs[name]['members']
            rows.append(row)
    need(len({r['workflow'] for r in rows})==len(rows),'execution plan duplicate workflow')
    return rows


def inspect(source,ref):
    need(type(source) is str and re.fullmatch('[0-9a-f]{40}',source),'execution plan source')
    need(type(ref) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_./-]*',ref) and
         '..' not in ref and '//' not in ref and
         all(p and not p.startswith('.') and not p.endswith(('.', '.lock')) for p in ref.split('/')),
         'execution plan branch')
    before=seeds.checkout_source(source)
    local=subprocess.check_output(['git','rev-parse','--verify','refs/heads/'+ref],cwd=plan.ROOT,text=True).strip()
    need(local==source,'execution plan branch is not selected source')
    inventory,_,_=plan.inspect();rows=entries(before)
    for row in rows:
        row['dispatchCommand']=['gh','workflow','run',Path(row['workflow']).name,'--repo',workflows.REPOSITORY,'--ref',ref]
        row['createOnlyPushCommand']=(['git','push','--porcelain','--force-with-lease='+row['pushTriggerRef']+':',
            'git@github.com:'+workflows.REPOSITORY+'.git',source+':'+row['pushTriggerRef']]
            if row['pushTriggerRef'] else None)
    need(seeds.checkout_source(source)==before,'execution plan source changed during inspection')
    count=Counter()
    for row in rows:count[row['family']]+=row['selectedJobs']
    capacity=native_capacity.native
    return dict(schema=SCHEMA,status='PLANNED',execution='offline-source-inspection-only',source=source,ref=ref,
        sourceFilesSha256=plan.digest(plan.encoded(before['files'])),
        qualificationInputsSha256=inventory['inspectedInputsSha256'],
        workflowCount=len(rows),selectedJobs=sum(count.values()),selectedJobsByFamily=dict(count),
        pushEntryWorkflows=sum(r['pushTriggerRef'] is not None for r in rows),
        manualOnlyWorkflows=sum(r['pushTriggerRef'] is None for r in rows),
        wholeHistoryGroups=sum(r['groups'] for r in rows if r['family']=='histories'),
        wholeHistories=inventory['plannedHostedHistories'],workflows=rows,
        machineRequirements=dict(nativeLinuxRequired=True,wslAccepted=False,
            minimumAvailableMemoryBytes=capacity.MINIMUM_AVAILABLE_MEMORY,
            largeDirectFreeBytes=dict(capacity.FREE_BY_STAGE),
            maximumHostedFreeBytes=dict(native_capacity.FREE_BY_STAGE),
            finalReplayFreeBytesAfterInputs=attested.MINIMUM_FREE_BYTES,
            capacitiesArePerStage=True,retainedInputsAndFailedRunsAreAdditional=True),
        prerequisites=['Explicit operator authorization and a pushed frozen ref are required before dispatch.',
            'Manual dispatch requires the workflow definition on the default branch as well as the frozen target ref; neither was queried by this offline plan.',
            'If manual registration is absent, only workflows with their existing push trigger can start via the create-only experimental branch command.',
            'Create-only pushes reject changing an existing remote branch; a ref already at the selected source is an up-to-date no-op, not a new run. Require the porcelain new-branch result and inspect Actions before recording a start. Do not force-update, delete or reset a ref to manufacture a fresh attempt.',
            'Provision the dedicated native Linux runner before dispatching the three large workflows.',
            'All large workflows share one group with queue=max and cancel-in-progress=false; maximum 100 pending, no order guarantee.',
            'Never change the selected ref until every selected run is complete; retain every failed/cancelled attempt.'],
        acceptanceOrder=['Reconcile complete matching seeds and exact source/build/tools/dependencies.',
            'Select explicit run/attempt IDs and retain original artifact ZIPs and all prior attempts.',
            'Run phase3_attested_cohort v4 with all twelve subsets, five supplemental originals and both maximum originals.',
            'Review prior failures and actual coverage/combined-resource evidence before the separate closure audit.'],
        openGaps=[g['id'] for g in inventory['gaps']],runtimeQualified=False,phase3Complete=False,
        workflowsDispatched=0,finalSourceNativeHistoriesExecuted=0)


def render(value):
    lines=['# Phase 3 execution handoff','',f"Source: `{value['source']}`; ref: `{value['ref']}`.",'',
        '**PLANNED only. No workflow or experiment was started.**','',
        f"{value['workflowCount']} workflows / {value['selectedJobs']} selected jobs. "
        f"The twelve history subsets contain {value['wholeHistories']} whole histories in {value['wholeHistoryGroups']} groups.",'',
        'The five supplemental and two maximum originals remain additional requirements; do not sum separate resource peaks.','',
        '| Set | Workflow | Jobs | Large native host | Existing push entry |','| --- | --- | ---: | --- | --- |']
    for row in value['workflows']:
        lines.append(f"| {row['id']} | `{Path(row['workflow']).name}` | {row['selectedJobs']} | {'yes' if row['requiresLargeHost'] else 'no'} | {'yes' if row['pushTriggerRef'] else 'no'} |")
    lines+=['',f"{value['pushEntryWorkflows']} workflows have an existing exact experimental push entry; "
        f"{value['manualOnlyWorkflows']} are manual-only. Pushing the development branch does not register all manual workflows on the default branch."]
    lines+=['','## Before execution','']+['- '+v for v in value['prerequisites']]
    machine=value['machineRequirements'];gib=1024**3
    lines+=['',f"Native Linux: at least {machine['minimumAvailableMemoryBytes']//gib} GiB available memory. "
        'Disk values below are free space at that stage, not total disk sizes. Retained inputs and failed runs remain on disk.','',
        '| Stage | Free GiB |','| --- | ---: |']
    for prefix,key in [('Direct large','largeDirectFreeBytes'),('Maximum hosted','maximumHostedFreeBytes')]:
        for stage,size in machine[key].items():lines.append(f'| {prefix} {stage} | {size//gib} |')
    lines += [f"| Complete final replay, after inputs | {machine['finalReplayFreeBytesAfterInputs']//gib} |",'',
        '## Manual dispatch — only after authorization and default-branch registration','',
        'These commands are printed, never executed by the planner. Verify the default-branch workflow and frozen remote ref first.','']
    for row in value['workflows']:
        lines+=['### '+row['id'],'','```bash',shlex.join(row['dispatchCommand']),'```','']
    lines+=['## Existing push entry — alternate startup before manual registration','',
        'Only these existing trigger branches may start from a push. Every command publishes the same exact source. '
        'The empty expected lease permits creation and prevents changing an existing branch. '
        'A porcelain new-branch result (*) publishes a new trigger; up-to-date (=) starts nothing, even with exit zero. '
        'Confirm the actual Actions run after creation. Execute only after explicit authorization. '
        'Do not also manually dispatch the same member. Manual-only entries remain pending.','']
    for row in value['workflows']:
        if row['createOnlyPushCommand']:
            lines+=['### '+row['id'],'','```bash',shlex.join(row['createOnlyPushCommand']),'```','']
    lines+=['## Acceptance order','']+[str(i)+'. '+v for i,v in enumerate(value['acceptanceOrder'],1)]
    lines+=['','Open gaps: '+', '.join(value['openGaps'])+'.','']
    return '\n'.join(lines)


def run(source,ref,output):
    output=seeds.unlinked(output)
    need(not output.is_relative_to(plan.ROOT) or output.is_relative_to(plan.ROOT/'target'),
         'execution plan output must not dirty source')
    need(not output.exists(),'execution plan output already exists')
    value=inspect(source,ref)
    output.mkdir(parents=True,exist_ok=False)
    (output/'plan.json').write_text(json.dumps(value,indent=2)+'\n')
    (output/'EXECUTION.md').write_text(render(value))
    return value


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('source','ref','output'):p.add_argument('--'+key,required=True)
    a=p.parse_args();value=run(a.source,a.ref,a.output)
    print(json.dumps({k:value[k] for k in ('status','source','workflowCount','selectedJobs','phase3Complete')}))
