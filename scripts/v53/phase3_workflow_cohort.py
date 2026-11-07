"""Read-only exact-attempt observations for all declared Phase 3 workflows.

Successful workflow stages are a prerequisite, not original-history replay or
Phase 3 acceptance. Retain every prior attempt; never select an older green one.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from . import phase3_history_cohort as histories

seeds=histories.seeds;plan=seeds.plan;need=seeds.need;h=seeds.h
SCHEMA='gse-v53-phase3-workflow-cohort-v1'
REPOSITORY='patricklfdm/GeneralSearchEngine'
REPOSITORY_ID=1341513206
OWNER_ID=147357093
MAX_ATTEMPTS=100
MAX_JOBS=1024
MAX_RESPONSE=16*1024*1024
RUN_KEYS=('id','run_attempt','head_sha','head_branch','event','path','workflow_id','status','conclusion','updated_at')


def integer(value,low,high,label):
    need(type(value) is int and low<=value<=high,label);return value


def stamp(value):
    need(type(value) is str,'workflow cohort timestamp')
    try:value=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:raise ValueError('workflow cohort timestamp') from None
    need(value.tzinfo is not None,'workflow cohort timestamp zone');return value.timestamp()


def contract(name,adapter,catalog,text):
    """Closed parser for the existing four-job, explicit-name workflow layout.

    Matrix IDs come from the same owning artifact naming functions, and their
    complete group membership comes from the source catalogue, never API counts.
    """
    need(text.count('\njobs:\n')==1 and not re.search(r'continue-on-error:|workflow_call:|^\s*uses:.*@(?:main|master)\s*$',text,re.M),
         'workflow cohort unsupported workflow')
    chunks=re.split(r'^  ([\w-]+):\n',text.split('\njobs:\n')[1],flags=re.M)
    need(chunks[1::2]==['prepare','execute','verify','aggregate'],'workflow cohort exact job graph')
    blocks=dict(zip(chunks[1::2],chunks[2::2]));result={};group_names=histories.groups(name,adapter,catalog)
    ctx=dict(run='1',attempt='1',source='a'*40)
    prefix=adapter.artifact_name(ctx,'raw')+'-'
    ids={key:adapter.artifact_name(ctx,'raw',key).removeprefix(prefix) for key in group_names}
    need(len(set(ids.values()))==len(ids) and all(re.fullmatch('[A-Za-z0-9_-]+',v) for v in ids.values()),
         'workflow cohort exact matrix IDs')
    module=plan.COHORTS[name][2]
    need('python -B -m scripts.v53.'+module+' plan' in blocks['prepare'] and
         'matrix: ${{ steps.plan.outputs.matrix }}' in blocks['prepare'],'workflow cohort owning planner')
    for role,body in blocks.items():
        names=re.findall(r'^    name: (.+)$',body,re.M)
        need(len(names)==1,'workflow cohort explicit job name');template=names[0]
        expected_needs={'prepare':None,'execute':'prepare','verify':'[prepare, execute]',
                        'aggregate':'[prepare, execute, verify]'}[role]
        need(re.findall(r'^    needs: (.+)$',body,re.M)==([] if expected_needs is None else [expected_needs]),
             'workflow cohort dependency graph')
        need('ref: ${{ github.sha }}' in body and 'persist-credentials: false' in body and
             'runs-on: ubuntu-24.04' in body,'workflow cohort original checkout/runner')
        if role in ('execute','verify'):
            need(template.count('${{ matrix.id }}')==1 and
                 'matrix: ${{ fromJSON(needs.prepare.outputs.matrix) }}' in body and
                 'fail-fast: false' in body,'workflow cohort fixed complete matrix')
            instances=[(template.replace('${{ matrix.id }}',slug),key) for key,slug in ids.items()]
        else:
            need('${{' not in template and '    strategy:' not in body,'workflow cohort unexpected matrix');instances=[(template,None)]
        steps=re.findall(r'^      - name: ([^\n]+)\n(.*?)(?=^      - name:|\Z)',body,re.M|re.S)
        need(steps and len({n for n,_ in steps})==len(steps) and all('${{' not in n for n,_ in steps),
             'workflow cohort explicit unique step names')
        # Shell steps include the actual planner/producer/reader. Keep artifact
        # uploads too; composite setup children and platform post steps may vary.
        required=[n for n,b in steps if re.search(r'^        run:',b,re.M) or 'uses: actions/upload-artifact@' in b]
        need(any('python -B -m scripts.v53.'+module+' '+role in b for _,b in steps),
             'workflow cohort owning command')
        for job,key in instances:
            need(job not in result and '${{' not in job,'workflow cohort duplicate/unresolved job name')
            result[job]=dict(role=role,group=key,steps=required)
    return dict(workflow=adapter.WORKFLOW,workflowSha256=h.digest(text.encode()),groups=len(ids),jobs=result)


def contracts(modules,catalogs,source):
    result={}
    for name,adapter in modules.items():
        raw=plan.regular(plan.ROOT,adapter.WORKFLOW)
        need(source['files'].get(adapter.WORKFLOW)==h.digest(raw),'workflow cohort workflow/source bytes')
        result[name]=contract(name,adapter,catalogs[name],raw.decode())
    return result


def run_identity(value,ctx,attempt):
    need(type(value) is dict and all(k in value for k in (*RUN_KEYS,'repository','head_repository')),
         'workflow cohort run fields')
    for repo in (value['repository'],value['head_repository']):
        need(type(repo) is dict and repo.get('id')==REPOSITORY_ID and repo.get('full_name')==REPOSITORY and
             type(repo.get('owner')) is dict and repo['owner'].get('id')==OWNER_ID,'workflow cohort repository identity')
    need(integer(value['id'],1,10**20-1,'workflow cohort run ID')==int(ctx['run']) and
         integer(value['run_attempt'],1,MAX_ATTEMPTS,'workflow cohort attempt bound')==attempt and
         value['head_sha']==ctx['source'] and value['head_branch']==ctx['ref'].removeprefix('refs/heads/') and
         value['event']==ctx['event'] and value['path']==ctx['workflow'],'workflow cohort exact context')
    integer(value['workflow_id'],1,10**20-1,'workflow cohort workflow ID')


def check_jobs(jobs,ctx,expected,now):
    need(type(jobs) is list and len(jobs)==len(expected) and
         Counter(j.get('name') for j in jobs)==Counter(expected.keys()),'workflow cohort complete selected matrix')
    ids=set()
    for job in jobs:
        identifier=integer(job.get('id'),1,10**20-1,'workflow cohort job ID')
        need(identifier not in ids,'workflow cohort duplicate job ID');ids.add(identifier)
        need(type(job.get('run_id')) is int and job['run_id']==int(ctx['run']) and
             type(job.get('run_attempt')) is int and job['run_attempt']==int(ctx['attempt']) and
             job.get('head_sha')==ctx['source'] and job.get('head_branch')==ctx['ref'].removeprefix('refs/heads/') and
             job.get('status')=='completed' and job.get('conclusion')=='success','workflow cohort failed/skipped/mixed job')
        start,end=stamp(job.get('started_at')),stamp(job.get('completed_at'))
        need(0<start<=end<=now,'workflow cohort job interval')
        spec=expected[job['name']]
        steps=job.get('steps');need(type(steps) is list and steps,'workflow cohort missing steps')
        numbers=[v.get('number') for v in steps]
        need(all(type(n) is int and n>0 for n in numbers) and numbers==sorted(set(numbers)),
             'workflow cohort step positions')
        previous=0
        for name in spec['steps']:
            found=[s for s in steps if s.get('name')==name]
            need(len(found)==1 and found[0].get('status')=='completed' and found[0].get('conclusion')=='success',
                 'workflow cohort critical step not successful: '+name)
            need(start<=stamp(found[0].get('started_at'))<=stamp(found[0].get('completed_at'))<=end,
                 'workflow cohort critical step interval')
            need(found[0]['number']>previous,'workflow cohort critical step order');previous=found[0]['number']
    # The reviewed needs graph binds job dependencies. Cross-runner wall-clock
    # differences are retained telemetry, not a new protocol timing gate.
    return len(jobs)


def github(path):
    need(re.fullmatch(r'actions/runs/[1-9][0-9]{0,19}(?:/attempts/[1-9][0-9]{0,2}(?:/jobs\?per_page=100&page=[1-9][0-9]*)?)?',path),
         'workflow cohort read-only API path')
    result=subprocess.run(['gh','api','--hostname','github.com','--method','GET',
        '-H','Accept: application/vnd.github+json','-H','X-GitHub-Api-Version: 2026-03-10',
        'repos/'+REPOSITORY+'/'+path],capture_output=True,timeout=30)
    need(result.returncode==0 and 0<len(result.stdout)<=MAX_RESPONSE,'workflow cohort GitHub read failed/oversized')
    return result.stdout


def selected_signature(value):return {k:value[k] for k in RUN_KEYS}


def observed_attempt(run,jobs):
    # Ignore transport JSON formatting and unrelated repository/actor metadata;
    # retain the full raw responses separately. Execution identities, times,
    # outcomes and every step remain bound across the enclosing long replay.
    fields=('id','run_id','run_attempt','head_sha','head_branch','name','status','conclusion','started_at','completed_at')
    step_fields=('number','name','status','conclusion','started_at','completed_at')
    return dict(run=selected_signature(run),jobs=[dict(**{k:j.get(k) for k in fields},
        steps=[{k:s.get(k) for k in step_fields} for s in j.get('steps',[])]) for j in sorted(jobs,key=lambda v:v['id'])])


def inspect_index(index):
    raw=seeds.read_bytes(index);value=plan.decode(raw);modules=seeds.adapters();source_sha=seeds.validate_index(value,modules)
    source=seeds.checkout_source(source_sha);catalogs=plan.catalogues();expected=contracts(modules,catalogs,source)
    return raw,value,source,expected,catalogs


def collect(index,output,get=github):
    return collect_declared(index,output,get,inspect_index,SCHEMA)


def collect_declared(index,output,get,inspect,schema):
    """Shared read-only collector; inspectors are fixed owning code, not input imports."""
    index,output=seeds.unlinked(index),seeds.unlinked(output)
    need(not index.is_relative_to(output),'workflow cohort output overlaps index')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=schema,status='FAIL',execution='read-only-github-observation',workflowExecutionAttested=False,
                 originalHistoriesReplayed=False,phase3Complete=False,runtimeQualified=False,cohorts={})
    inventory={};total_bytes=0
    def fetch(path,file):
        nonlocal total_bytes
        raw=get(path);need(type(raw) is bytes and 0<len(raw)<=MAX_RESPONSE,'workflow cohort bounded API bytes')
        total_bytes+=len(raw);need(total_bytes<=512*1024*1024,'workflow cohort observation byte bound')
        target=output/file;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(raw)
        inventory[file]=dict(endpoint=path,sha256=h.digest(raw),bytes=len(raw))
        h.save(output/'api-inventory.json',inventory)
        return plan.decode(raw)
    try:
        inspected=inspect(index);raw,value,source,expected,_=inspected;source_sha=value['source']
        (output/'index.json').write_bytes(raw);h.save(output/'contracts.json',expected)
        latest={};observations={};prior_count=0;all_job_ids=set();workflow_ids=set()
        for name,ctx in value['cohorts'].items():
            base='actions/runs/'+ctx['run'];folder='api/'+name
            before=fetch(base,folder+'/before.json');attempt=int(ctx['attempt']);run_identity(before,ctx,attempt)
            need(before['workflow_id'] not in workflow_ids,'workflow cohort duplicate workflow ID');workflow_ids.add(before['workflow_id'])
            attempts=[];selected_jobs=None;seen_ids=set();observations[name]=[]
            # All attempts are retained before qualifying the chosen one, even
            # when that chosen attempt failed. Missing history is never ignored.
            for number in range(1,attempt+1):
                path=base+'/attempts/'+str(number);run=fetch(path,folder+f'/attempt-{number}/run.json');run_identity(run,ctx,number)
                need(run['workflow_id']==before['workflow_id'],'workflow cohort changed workflow identity')
                jobs=[];count=None
                for page in range(1,(MAX_JOBS+99)//100+1):
                    data=fetch(path+f'/jobs?per_page=100&page={page}',folder+f'/attempt-{number}/jobs-{page}.json')
                    need(type(data) is dict and type(data.get('jobs')) is list,'workflow cohort job page')
                    total=integer(data.get('total_count'),0,MAX_JOBS,'workflow cohort job count bound')
                    need(count is None or count==total,'workflow cohort changed page total');count=total
                    need(len(data['jobs'])==min(100,count-len(jobs)),'workflow cohort truncated/oversized page')
                    jobs.extend(data['jobs'])
                    if len(jobs)==count:break
                need(len(jobs)==count,'workflow cohort incomplete pagination')
                current_ids=set()
                for job in jobs:
                    identifier=integer(job.get('id'),1,10**20-1,'workflow cohort job ID')
                    need(identifier not in current_ids and identifier not in seen_ids and identifier not in all_job_ids and
                         type(job.get('run_id')) is int and job['run_id']==int(ctx['run']) and
                         type(job.get('run_attempt')) is int and job['run_attempt']==number and job.get('head_sha')==source_sha,
                         'workflow cohort duplicate/mixed attempt job')
                    current_ids.add(identifier)
                seen_ids.update(current_ids);all_job_ids.update(current_ids)
                observations[name].append(observed_attempt(run,jobs));h.save(output/'observations.json',observations)
                attempts.append(dict(attempt=number,status=run['status'],conclusion=run['conclusion'],jobs=len(jobs),
                    jobConclusions=dict(Counter(j.get('conclusion') or 'unfinished' for j in jobs))))
                if number==attempt:
                    need(selected_signature(run)==selected_signature(before),'workflow cohort selected attempt changed');selected_jobs=jobs
                else:
                    need(run['status']=='completed','workflow cohort prior attempt not terminal');prior_count+=1
            after=fetch(base,folder+'/after.json');run_identity(after,ctx,attempt)
            need(selected_signature(before)==selected_signature(after),'workflow cohort run changed during observation')
            # Keep failed and cancelled API observations, then reject acceptance.
            receipt['cohorts'][name]=dict(context=ctx,attempts=attempts,selectedJobs=len(selected_jobs))
            h.save(output/'receipt.json',receipt)
            need(before['status']=='completed' and before['conclusion']=='success','workflow cohort selected attempt not successful')
            check_jobs(selected_jobs,ctx,expected[name]['jobs'],datetime.now(timezone.utc).timestamp())
            latest[name]=before
            print(json.dumps(dict(cohort=name,attempt=attempt,jobs=len(selected_jobs),status='OBSERVED')),flush=True)
        # A new rerun may start while another cohort is being read.
        for name,ctx in value['cohorts'].items():
            current=fetch('actions/runs/'+ctx['run'],'api/'+name+'/final.json');run_identity(current,ctx,int(ctx['attempt']))
            need(selected_signature(current)==selected_signature(latest[name]),'workflow cohort later rerun/state change')
        need(inspect(index)==inspected,'workflow cohort input/source changed')
        receipt.update(status='PARTIAL',source=source_sha,indexSha256=h.digest(raw),contractsSha256=h.digest(plan.encoded(expected)),
            apiInventorySha256=h.digest(plan.encoded(inventory)),workflowExecutionAttested=True,subsets=len(expected),
            observationsSha256=h.digest(plan.encoded(observations)),
            selectedJobs=sum(len(v['jobs']) for v in expected.values()),priorAttempts=prior_count,
            priorAttemptsRequireReview=prior_count>0,failedOriginalsReplayed=False,
            acceptanceAuthority='selected workflow execution only; original replay, coverage and resources remain separate')
    except BaseException as error:
        receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--index',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    with seeds.shared.progress('phase3-workflow-observation','all-declared-attempts'):result=collect(args.index,args.output)
    print(json.dumps({k:result[k] for k in ('status','subsets','selectedJobs','priorAttempts','phase3Complete')},sort_keys=True))
