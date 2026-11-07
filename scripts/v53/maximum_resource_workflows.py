"""Observe both maximum component workflows; no original or closure credit.

The frozen five-member supplemental cohort is deliberately unchanged. Failed
and cancelled prior attempts remain in the shared read-only API observations.
"""
import argparse
import importlib
import json
import re
from . import phase3_workflow_cohort as observed

seeds=observed.seeds;need=observed.need;h=observed.h;plan=observed.plan
SCHEMA='gse-v53-maximum-resource-workflows-v1'
INDEX_SCHEMA='gse-v53-maximum-resource-workflow-set-v1'
WORKFLOWS={
    'maximum-native':('maximum_native_hosted','v53-maximum-native-resources'),
    'maximum-queue':('maximum_queue_hosted','v53-maximum-queue'),
}


def adapters():return {name:importlib.import_module('.'+row[0],__package__) for name,row in WORKFLOWS.items()}


def artifact_name(name,ctx,kind):
    need(name in WORKFLOWS and kind in ('seed','raw'),'maximum workflows artifact selector')
    return WORKFLOWS[name][1]+'-'+kind+'-'+ctx['run']+'-'+ctx['attempt']+'-'+ctx['source']


def validate_index(value,modules):
    need(type(value) is dict and set(value)=={'schema','source','cohorts'} and value['schema']==INDEX_SCHEMA,
         'maximum workflows index envelope')
    source=value['source'];need(type(source) is str and re.fullmatch('[0-9a-f]{40}',source),'maximum workflows source SHA')
    need(type(value['cohorts']) is dict and set(value['cohorts'])==set(WORKFLOWS),'maximum workflows exact component set')
    runs=set()
    for name,adapter in modules.items():
        ctx=value['cohorts'][name];seeds.context(ctx,adapter,source)
        need(ctx['event']=='workflow_dispatch','maximum workflows manual-only context')
        need(ctx['run'] not in runs,'maximum workflows duplicate run');runs.add(ctx['run'])
    return source


def contract(name,adapter,text):
    need(name in WORKFLOWS and text.count('\njobs:\n')==1 and text.count('\non:\n')==1 and
         not re.search(r'continue-on-error:|workflow_call:|^\s*uses:.*@(?:main|master)\s*$',text,re.M),
         'maximum workflows unsupported workflow')
    for action in re.findall(r'uses: (\S+)',text):
        need(action=='./.github/actions/v53-process-setup' or re.fullmatch(r'[\w-]+/[\w-]+@[0-9a-f]{40}',action),
             'maximum workflows pinned actions')
    event=text.split('\non:\n')[1].split('\npermissions:',1)[0]
    need(re.findall(r'^  ([a-z_]+):',event,re.M)==['workflow_dispatch'] and
         re.findall(r'^  ([a-z-]+): (.+)$',text.split('\npermissions:\n')[1].split('\n\n',1)[0],re.M)==[('contents','read')],
         'maximum workflows manual read-only authority')
    chunks=re.split(r'^  ([\w-]+):\n',text.split('\njobs:\n')[1],flags=re.M)
    need(chunks[1::2]==['prepare','execute','verify'],'maximum workflows exact job graph')
    blocks=dict(zip(chunks[1::2],chunks[2::2]));jobs={};module=WORKFLOWS[name][0]
    for role,body in blocks.items():
        names=re.findall(r'^    name: (.+)$',body,re.M)
        need(len(names)==1 and '${{' not in names[0] and '    strategy:' not in body,'maximum workflows indivisible named job')
        job=names[0];dependency={'prepare':[],'execute':['prepare'],'verify':['[prepare, execute]']}[role]
        need(re.findall(r'^    needs: (.+)$',body,re.M)==dependency,'maximum workflows dependency graph')
        runner='ubuntu-24.04' if role=='prepare' else '[self-hosted, Linux, X64, gse-v53-large-evidence]'
        need(re.findall(r'^    runs-on: (.+)$',body,re.M)==[runner] and 'ref: ${{ github.sha }}' in body and
             'persist-credentials: false' in body,'maximum workflows source/runner')
        steps=re.findall(r'^      - name: ([^\n]+)\n(.*?)(?=^      - name:|\Z)',body,re.M|re.S)
        need(steps and len({n for n,_ in steps})==len(steps) and all('${{' not in n for n,_ in steps),
             'maximum workflows explicit unique steps')
        need(sum('python -B -m scripts.v53.'+module+' '+role in b for _,b in steps)==1,'maximum workflows owning command')
        if role!='prepare':
            stage='execute' if role=='execute' else 'verify-download'
            capacity=[i for i,(_,b) in enumerate(steps) if 'maximum_native_capacity "$GITHUB_WORKSPACE" --stage '+stage in b]
            downloads=[i for i,(_,b) in enumerate(steps) if 'uses: actions/download-artifact@' in b]
            need('clean: false' in body and len(capacity)==1 and downloads and capacity[0]<min(downloads),
                 'maximum workflows pre-download native capacity')
        if role=='verify':need('EXECUTE_RESULT: ${{ needs.execute.result }}' in body,'maximum workflows execution result binding')
        for _,step in steps:
            if 'uses: actions/upload-artifact@' in step:
                need('retention-days: 90' in step and 'compression-level: 0' in step,'maximum workflows evidence retention')
            if re.search(r'uses: actions/(?:up|down)load-artifact@',step):
                names_=re.findall(r'^          name: (.+)$',step,re.M)
                need(len(names_)==1 and names_[0].startswith(WORKFLOWS[name][1]+'-') and
                     names_[0].endswith('${{ github.run_id }}-${{ github.run_attempt }}-${{ github.sha }}'),
                     'maximum workflows exact artifact attempt')
        required=[n for n,b in steps if re.search(r'^        run:|uses: actions/(?:up|down)load-artifact@',b,re.M)]
        need(job not in jobs,'maximum workflows duplicate job name');jobs[job]=dict(role=role,group=name,steps=required)
    return dict(workflow=adapter.WORKFLOW,workflowSha256=h.digest(text.encode()),groups=1,jobs=jobs)


def inspect_index(index):
    raw=seeds.read_bytes(index);value=plan.decode(raw);modules=adapters();source_sha=validate_index(value,modules)
    source=seeds.checkout_source(source_sha);contracts={}
    for name,adapter in modules.items():
        data=plan.regular(plan.ROOT,adapter.WORKFLOW)
        need(source['files'].get(adapter.WORKFLOW)==h.digest(data),'maximum workflows workflow/source binding')
        contracts[name]=contract(name,adapter,data.decode())
    return raw,value,source,contracts,WORKFLOWS


def collect(index,output,get=observed.github):
    return observed.collect_declared(index,output,get,inspect_index,SCHEMA)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('index','output'):p.add_argument('--'+k,required=True)
    a=p.parse_args()
    with seeds.shared.progress('maximum-resource-workflows','all-attempts'):value=collect(a.index,a.output)
    print(json.dumps({k:value[k] for k in ('status','selectedJobs','priorAttempts','phase3Complete')},sort_keys=True))
