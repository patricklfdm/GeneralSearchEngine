"""Read-only exact-attempt observation of the four supplemental workflows.

Five whole histories expand to fifteen selected jobs. This observes execution;
only original artifact binding and independent replay can qualify the evidence.
"""
import argparse
import importlib
import json
import re
from . import phase3_workflow_cohort as observed

seeds=observed.seeds;need=observed.need;h=observed.h;plan=observed.plan
SCHEMA='gse-v53-phase3-resource-workflows-v1'
INDEX_SCHEMA='gse-v53-phase3-resource-workflow-set-v1'
WORKFLOWS={
    'required-four':('required_four_resource_hosted','v53-required-four-resources',('required-four',)),
    'maximum-image':('maximum_transition_hosted','v53-maximum-transition',('maximum-image',)),
    'capacity-completion':('capacity_completion_hosted','v53-capacity-completion',('capacity-completion',)),
    'queue-resources':('queue_resource_hosted','v53-queue-resources',('source-queue','queue-completion')),
}


def adapters():return {name:importlib.import_module('.'+row[0],__package__) for name,row in WORKFLOWS.items()}


def artifact_name(name,ctx,kind,member=None):
    need(name in WORKFLOWS and kind in ('seed','raw'),'resource workflows artifact selector')
    members=WORKFLOWS[name][2]
    need((kind=='seed' and member is None) or (kind=='raw' and member in members),'resource workflows artifact member')
    suffix='-'+member if name=='queue-resources' and member is not None else ''
    return WORKFLOWS[name][1]+'-'+kind+'-'+ctx['run']+'-'+ctx['attempt']+'-'+ctx['source']+suffix


def validate_index(value,modules):
    need(type(value) is dict and set(value)=={'schema','source','cohorts'} and value['schema']==INDEX_SCHEMA,
         'resource workflows index envelope')
    source=value['source'];need(type(source) is str and re.fullmatch('[0-9a-f]{40}',source),'resource workflows source SHA')
    need(type(value['cohorts']) is dict and set(value['cohorts'])==set(WORKFLOWS),'resource workflows complete set')
    runs=set()
    for name,adapter in modules.items():
        ctx=value['cohorts'][name];seeds.context(ctx,adapter,source)
        need(name not in ('maximum-image','queue-resources') or ctx['event']=='workflow_dispatch',
             'resource workflows manual-only context')
        need(ctx['run'] not in runs,'resource workflows duplicate run');runs.add(ctx['run'])
    return source


def contract(name,adapter,text):
    if name=='maximum-image':observed.large_runner_concurrency(text)
    need(text.count('\njobs:\n')==1 and not re.search(r'continue-on-error:|workflow_call:|^\s*uses:.*@(?:main|master)\s*$',text,re.M),
         'resource workflows unsupported workflow')
    chunks=re.split(r'^  ([\w-]+):\n',text.split('\njobs:\n')[1],flags=re.M)
    roles=['prepare','execute','verify']+(['aggregate'] if name=='queue-resources' else [])
    need(chunks[1::2]==roles,'resource workflows exact job graph')
    blocks=dict(zip(chunks[1::2],chunks[2::2]));jobs={};module,_,members=WORKFLOWS[name]
    if name=='queue-resources':
        need(tuple(adapter.HISTORIES)==members and 'python -B -m scripts.v53.'+module+' plan' in blocks['prepare'] and
             'matrix: ${{ steps.plan.outputs.matrix }}' in blocks['prepare'],'resource workflows owning queue planner')
    for role,body in blocks.items():
        names=re.findall(r'^    name: (.+)$',body,re.M)
        need(len(names)==1,'resource workflows explicit job name');template=names[0]
        dependency={'prepare':[],'execute':['prepare'],'verify':['[prepare, execute]'],
                    'aggregate':['[prepare, execute, verify]']}[role]
        need(re.findall(r'^    needs: (.+)$',body,re.M)==dependency,'resource workflows dependency graph')
        runner='[self-hosted, Linux, X64, gse-v53-large-evidence]' if name=='maximum-image' and role!='prepare' else 'ubuntu-24.04'
        need(re.findall(r'^    runs-on: (.+)$',body,re.M)==[runner] and 'ref: ${{ github.sha }}' in body and
             'persist-credentials: false' in body,'resource workflows source/runner')
        if name=='maximum-image' and role!='prepare':
            need('clean: false' in body and (role!='verify' or 'maximum_transition_capacity "$GITHUB_WORKSPACE"' in body),
                 'resource workflows native large-runner capacity check')
        if name=='queue-resources' and role in ('execute','verify'):
            need(template.count('${{ matrix.id }}')==1 and 'matrix: ${{ fromJSON(needs.prepare.outputs.matrix) }}' in body and
                 'fail-fast: false' in body and 'max-parallel: 2' in body,'resource workflows complete queue matrix')
            instances=[(template.replace('${{ matrix.id }}',member),member) for member in members]
        else:
            need('${{' not in template and '    strategy:' not in body,'resource workflows unexpected matrix')
            instances=[(template,members[0] if role in ('execute','verify') else None)]
        steps=re.findall(r'^      - name: ([^\n]+)\n(.*?)(?=^      - name:|\Z)',body,re.M|re.S)
        need(steps and len({n for n,_ in steps})==len(steps) and all('${{' not in n for n,_ in steps),
             'resource workflows explicit unique steps')
        need(any('python -B -m scripts.v53.'+module+' '+role in b for _,b in steps),'resource workflows owning command')
        required=[n for n,b in steps if re.search(r'^        run:',b,re.M) or 'uses: actions/upload-artifact@' in b]
        for job,member in instances:
            need(job not in jobs and '${{' not in job,'resource workflows unresolved/duplicate job')
            jobs[job]=dict(role=role,group=member,steps=required)
    return dict(workflow=adapter.WORKFLOW,workflowSha256=h.digest(text.encode()),groups=len(members),jobs=jobs)


def inspect_index(index):
    raw=seeds.read_bytes(index);value=plan.decode(raw);modules=adapters();source_sha=validate_index(value,modules)
    source=seeds.checkout_source(source_sha);contracts={}
    for name,adapter in modules.items():
        data=plan.regular(plan.ROOT,adapter.WORKFLOW)
        need(source['files'].get(adapter.WORKFLOW)==h.digest(data),'resource workflows workflow/source binding')
        contracts[name]=contract(name,adapter,data.decode())
    return raw,value,source,contracts,WORKFLOWS


def collect(index,output,get=observed.github):
    return observed.collect_declared(index,output,get,inspect_index,SCHEMA)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('index','output'):parser.add_argument('--'+key,required=True)
    args=parser.parse_args()
    with seeds.shared.progress('phase3-resource-workflows','all-attempts'):result=collect(args.index,args.output)
    print(json.dumps({k:result[k] for k in ('status','subsets','selectedJobs','priorAttempts','phase3Complete')},sort_keys=True))
