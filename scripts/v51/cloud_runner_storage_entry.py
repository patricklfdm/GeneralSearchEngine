"""Explicitly selected, exact-request Runner storage entry and independent review.

Only storage qualification is exposed. No engine workload, Compute or IAM writes.
The network constructor rechecks trusted context itself; no approval boolean,
caller-selected token, transport, clock or GitHub observation is accepted.
"""
import argparse
import html
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import urlsplit, parse_qsl
from . import cloud_runner_storage as s, cloud_runner_storage_plan as plan
from . import cloud_runner_precheck as precheck, cloud_runner_review as workflow
from . import cloud_cleanup_credentials as credentials, cloud_cleanup_entry as entry
from . import cloud_cleanup_observation as observation, cloud_permissions as permissions
from . import cloud_native_authority as n, cloud_authority as a, cloud_gcp as g, cloud_http as h
from . import cloud_preflight as p, cloud_ci as ci, performance_model as m
from .remote_command import read, write_once

SCHEMA='gse-v51-runner-storage-entry-v1'
STEP='Qualify exact approved Runner storage request (no allocation)'


def selection(env):
    selected=env.get('RUNNER_STORAGE_REQUEST','');confirmation=env.get('RUNNER_STORAGE_CONFIRMATION','')
    if selected==confirmation=='':return None
    a.digest(selected);a.digest(confirmation)
    m.need(env.get('RUNNER_PERMISSION_PRECHECK')=='true','storage requires explicit Runner precheck')
    return selected,confirmation


def check_inputs(cfg,env,binding,preflight,root,jobs,*,now):
    source=binding['source']
    prerequisites=precheck.prerequisites(cfg,env,binding,preflight,jobs,now=now)
    root=Path(root);bound=read(root/'identity/receipt.json')
    m.need(bound==dict(schema=precheck.SCHEMA,status='BOUND',binding=binding,prerequisites=prerequisites,**permissions.BOUNDARY)
           and read(root/'identity/binding.json')==binding,'storage original identity/prerequisites changed')
    permission=permissions.check_saved(cfg,binding,root/'permissions',now=now)
    receipt=read(root/'receipt.json');a.integer(receipt['checkedAt'],1,now)
    expected=dict(schema=precheck.SCHEMA,source=source,status='PRECHECK_PASS',execution='runner-permission-diagnostics',
                  binding=binding,prerequisites=prerequisites,permission=permission,checkedAt=receipt['checkedAt'],**permissions.BOUNDARY)
    m.need(receipt==expected,'storage requires successful same-run Runner precheck')
    return prerequisites


def admission(cfg,env,source,checkout,preflight,root,*,get=ci.github,wall=time.time):
    m.need(selection(env) is not None,'storage request and confirmation required')
    binding=precheck.identity(cfg,env,source,checkout)
    jobs=precheck.collect_jobs(binding,get)
    prerequisites=check_inputs(cfg,env,binding,preflight,root,jobs,now=int(wall()))
    entry.collect_run(binding,get)
    m.need(int(wall())<prerequisites['expiresAt'],'storage prerequisite expired')
    return binding,prerequisites


class _ManifestReader(h.Api):
    def __init__(self,cfg,sha,tokens):
        super().__init__(transport=h.Network(),tokens=tokens)
        self.url=g.Store(cfg,self,authority=n).url(plan.manifest_key(sha))
    def authorize(self,method,url,body):
        parsed=urlsplit(url);pairs=parse_qsl(parsed.query,strict_parsing=True) if parsed.query else [];query=dict(pairs)
        m.need(method=='GET' and body is None and parsed._replace(query='').geturl()==self.url and len(query)==len(pairs),
               'storage entry manifest GET only')
        m.need(not query or set(query)=={'alt','generation','ifGenerationMatch'} and query['alt']=='media' and
               query['generation']==query['ifGenerationMatch'] and g.numeric(query['generation']), 'storage manifest pinned GET')


class NetworkApi(s._Policy):
    def __init__(self,cfg,env,source,checkout,preflight,root):
        workflow.workflow()
        binding,prerequisites=admission(cfg,env,source,checkout,preflight,root)
        sha,confirmation=selection(env)
        tokens=credentials.NetworkCredentials(binding,env,entry.credential_file(env))
        reader=_ManifestReader(cfg['provider'],sha,tokens)
        retained=g.Store(cfg['provider'],reader,authority=n).get(plan.manifest_key(sha))
        m.need(retained is not None and m.sha(m.canonical(retained[1]))==confirmation,'storage exact retained request confirmation')
        now=int(time.time());value=plan.validate_manifest(retained[1],cfg,sha,now=now)
        m.need(value['requests']['run']['source']==source,'storage request source mismatch')
        provider=read(Path(preflight)/'provider.json')['observations']
        m.need(provider['lease'] is None and provider['ledger']==retained[1]['baseline'][n.LEDGER],
               'storage preparation does not match same-run observer control')
        entry.collect_run(binding)
        now=int(time.time());plan.validate(value,now=now)
        m.need(now<prerequisites['expiresAt'],'storage entry expired during manifest read')
        h.Api.__init__(self,transport=h.Network(),tokens=tokens)
        self.initialize(cfg['provider'],value['requests']['run'],retained[1]['baseline'],maximum_cost=plan.COST,native=True)
        wall=time.time()
        self.deadline=self.clock()+min(300,prerequisites['expiresAt']-wall,value['expiresAt']-wall,self.lease['expiresAt']-wall)
        self.binding=binding;self.prerequisites=prerequisites;self.manifest=retained[1];self.manifest_generation=retained[0]
        self.plan_sha=sha;self.confirmation=confirmation


def summary(value):
    def safe(v):return html.escape(str(v)).replace('|','&#124;').replace('\n',' ')
    binding=value.get('binding',{});manifest=value.get('manifest',{});proposal=manifest.get('plan',{})
    rows=[('Status',value['status']),('Source',value['source']),('Plan SHA-256',value.get('planSha256','unavailable')),
          ('Confirmation SHA-256',value.get('confirmation','unavailable')),
          *[(k,binding.get(k,'unavailable')) for k in ('runId','runAttempt','serviceAccount')],
          ('Previous reserve (USD)',proposal['previousCostMicrousd']/1_000_000 if proposal else 'unavailable'),
          ('Preparation reserve (USD)',1),('Runner reserve (USD)',1),('Cumulative ceiling (USD)',a.MAXIMUM_BUDGET_MICROUSD/1_000_000),
          ('Request expires (UTC epoch)',proposal.get('expiresAt','unavailable')),
          ('Lease released',value.get('result',{}).get('leaseReleased','not established')),
          ('Credential exchange',value.get('credentialExchangeCompleted',False)),('Failure',value.get('failure','none'))]
    cases=value.get('result',{}).get('cases',[])
    return '# V5.1 Runner storage qualification\n\n| Parameter | Value |\n| --- | --- |\n'+\
        ''.join('| '+safe(k)+' | '+safe(v)+' |\n' for k,v in rows)+\
        '\n| Probe | Result |\n| --- | --- |\n'+''.join('| '+safe(v['case'])+' | '+safe(v['status'])+' |\n' for v in cases)+\
        '\nStorage-only attempt: no engine workload. Independent object/control readback and artifact provenance remain required. Schedule is optional.\n'


def execute_network(cfg,env,source,checkout,preflight,root,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    result=dict(schema=SCHEMA,status='FAIL',source=source,startedAt=int(time.time()),execution='runner-identity-storage-entry',
                credentialExchangeCompleted=False,paidCloud=False,**plan.FLAGS)
    api=None;phase='admission'
    try:
        api=NetworkApi(cfg,env,source,checkout,preflight,root)
        result.update(binding=api.binding,prerequisites=api.prerequisites,manifest=api.manifest,
                      manifestGeneration=api.manifest_generation,planSha256=api.plan_sha,confirmation=api.confirmation)
        write_once(output/'manifest.json',api.manifest)
        phase='storage'
        result['result']=s.run(api)
        phase='final-run-observation'
        entry.collect_run(api.binding)
        m.need(api.clock()<=api.deadline,'storage result after original deadline')
        result['status']='PROBES_RECORDED'
    except (Exception,KeyboardInterrupt) as error:
        result['failure']=dict(phase=phase,type=type(error).__name__,**credentials.diagnostic(error))
        if isinstance(error,h.ApiError):result['failure']['httpStatus']=error.status
        if api is not None and api.requests:result['failure']['operation']=api.requests[-1]['action']
    finally:
        if api is not None:
            result['credentialExchangeCompleted']=api.tokens.exchanges>0
            result['paidCloud']=any(v['method']!='GET' for v in api.requests)
            write_once(output/'http.json',api.requests)
        result['completedAt']=int(time.time());write_once(output/'receipt.json',result)
        (output/'summary.md').write_text(summary(result))
    return result


def capture(cfg,manifest,*,api=None,wall=time.time):
    value=manifest['plan'];sha=manifest['planSha256']
    # Historical validation checks original preparation time, never refreshes admission.
    plan.validate_manifest(manifest,cfg,sha,now=manifest['preparedAt'],offline=value['execution']=='offline-runner-storage-plan')
    reader=observation.Reads(api if api is not None else h.Api());store=plan.Store(cfg['provider'],reader,value)
    started=int(wall());objects={key:store.get(key) for key in sorted(store.keys)}
    m.need(objects=={key:store.get(key) for key in sorted(store.keys)},'storage independent observation changed')
    m.need(reader.clock()<=reader.deadline,'storage independent observation deadline')
    return dict(schema='gse-v51-runner-storage-observation-v1',execution='offline-storage-observation' if reader.offline else 'read-only-storage-observation',
                planSha256=sha,startedAt=started,completedAt=int(wall()),objects=objects)


def check_state(cfg,manifest,after,*,native):
    value=plan.validate_manifest(manifest,cfg,manifest['planSha256'],now=manifest['preparedAt'],offline=not native)
    m.need(after['schema']=='gse-v51-runner-storage-observation-v1' and after['planSha256']==manifest['planSha256'] and
           after['execution']==('read-only-storage-observation' if native else 'offline-storage-observation'),'storage observation domain/binding')
    a.integer(after['startedAt'],manifest['preparedAt']);a.integer(after['completedAt'],after['startedAt'],after['startedAt']+180)
    req=value['requests']['run'];keys=s.inventory(req);objects=after['objects']
    # Exact inventory also records unused preparation/Runner paths as absent.
    wanted=plan.Store(cfg['provider'],h.Api(),value).keys
    m.need(set(objects)==wanted and objects[n.LEASE] is None,'storage after inventory/lease')
    for name in ('existing','outside'):
        m.need(m.canonical(objects[keys[name]])==m.canonical(manifest['baseline'][keys[name]]),'storage protected canary changed')
    expected={keys['created']:s.canary(req,'created'),keys['report']:s.report(req,native=native),
              keys['completion']:s.completion(req),plan.manifest_key(manifest['planSha256']):manifest,
              s.inventory(value['requests']['prepare'])['completion']:plan.prepared_completion(value['requests']['prepare'])}
    reserved=n.reserve(plan.ledgers(value)[1],req,dict(previousCostMicrousd=value['previousCostMicrousd']+plan.COST,maximumCostMicrousd=plan.COST))
    expected[n.LEDGER]=n.finish(reserved,req,s.completion(req))
    for key,body in expected.items():
        row=objects[key];m.need(observation.item(row)==body,'storage retained bytes/terminal ledger changed')
    for key in wanted-{n.LEASE,*expected,keys['existing'],keys['outside']}:
        m.need(objects[key] is None,'unexpected storage attempt evidence')
    return dict(status='OBJECT_SCOPE_MATCH',planSha256=manifest['planSha256'],retainedCostMicrousd=n.inspect_ledger(expected[n.LEDGER])[0],**plan.FLAGS)


def review(cfg,receipt,after,run,root):
    manifest=receipt['manifest'];value=manifest['plan'];binding=receipt['binding'];source=value['requests']['run']['source']
    m.need(receipt['schema']==SCHEMA and receipt['status']=='PROBES_RECORDED' and receipt['execution']=='runner-identity-storage-entry'
           and receipt['source']==source and receipt['credentialExchangeCompleted'] is True and receipt['paidCloud'] is True
           and all(receipt[k] is False for k in plan.FLAGS),'storage receipt authority/outcome')
    chosen=permissions.selected(cfg,'runner');a.integer(binding['runId'],1);a.integer(binding['runAttempt'],1)
    env=dict(GITHUB_ACTIONS='true',GITHUB_REPOSITORY=ci.REPOSITORY,GITHUB_REPOSITORY_ID=str(ci.REPOSITORY_ID),
        GITHUB_REPOSITORY_OWNER_ID=str(ci.OWNER_ID),GITHUB_REF='refs/heads/master',GITHUB_EVENT_NAME='workflow_dispatch',
        GITHUB_WORKFLOW_REF=chosen['claims']['workflow_ref'],GITHUB_WORKFLOW_SHA=source,GITHUB_SHA=source,GITHUB_JOB='run',
        PERMISSION_ENVIRONMENT=chosen['environment'],RUNNER_PERMISSION_PRECHECK='true',
        GITHUB_RUN_ID=str(binding['runId']),GITHUB_RUN_ATTEMPT=str(binding['runAttempt']))
    m.need(binding==precheck.identity(cfg,env,source,source),'storage receipt Runner identity')
    for k in ('before','attempt','after'):observation.completed_run(binding,run[k])
    jobs=run['jobs'];m.need(jobs['total_count']==2 and len(jobs['jobs'])==2,'storage job inventory')
    precheck.observer_job(binding,jobs,now=after['startedAt'])
    matches=[job for job in jobs['jobs'] if job['name']==workflow.RUNNER_JOB_NAME]
    m.need(len(matches)==1,'storage Runner job missing/duplicate');job=matches[0]
    m.need(job['run_id']==binding['runId'] and job['run_attempt']==binding['runAttempt'] and job['head_sha']==source
           and job['status']=='completed' and job['conclusion']=='success','storage Runner job incomplete')
    for name in (STEP,'Report runner permission diagnostics','Retain runner precheck evidence including failures'):
        steps=[v for v in job['steps'] if v['name']==name]
        m.need(len(steps)==1 and steps[0]['status']=='completed' and steps[0]['conclusion']=='success','storage step missing/skipped')
    a.integer(receipt['startedAt'],value['requests']['run']['createdAt'])
    a.integer(receipt['completedAt'],receipt['startedAt'],after['startedAt'])
    prerequisites=check_inputs(cfg,env,binding,Path(root)/'preflight',root,jobs,now=receipt['startedAt'])
    m.need(receipt['prerequisites']==prerequisites,'storage original prerequisites changed')
    m.need(read(Path(root)/'preflight/provider.json')['observations']['ledger']==manifest['baseline'][n.LEDGER],
           'storage observer ledger differs from prepared state')
    m.need(receipt['completedAt']<min(value['expiresAt'],receipt['prerequisites']['expiresAt']) and
           ci.timestamp(job['started_at'])<=receipt['startedAt']<=receipt['completedAt']<=ci.timestamp(job['completed_at']), 'storage run time')
    m.need(receipt['confirmation']==m.sha(m.canonical(manifest)) and receipt['planSha256']==manifest['planSha256'], 'storage confirmation drift')
    m.need(receipt['result']==dict(s.report(value['requests']['run'],native=True),leaseReleased=True,maximumCostMicrousd=plan.COST), 'storage cases/result changed')
    result=check_state(cfg,manifest,after,native=True)
    m.need(after['objects'][plan.manifest_key(receipt['planSha256'])][0]==receipt['manifestGeneration'],'storage manifest generation changed')
    return dict(result,workflowIdentityClaimRecorded=True,artifactProvenanceVerified=False,providerAuditVerified=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    guard=sub.add_parser('guard');guard.add_argument('--source',required=True)
    run=sub.add_parser('run');run.add_argument('--source',required=True);run.add_argument('--preflight',type=Path,required=True)
    run.add_argument('--precheck',type=Path,required=True);run.add_argument('--output',type=Path,required=True)
    observe=sub.add_parser('observe');observe.add_argument('--manifest',type=Path,required=True);observe.add_argument('--output',type=Path,required=True)
    check=sub.add_parser('review');check.add_argument('--receipt',type=Path,required=True);check.add_argument('--after',type=Path,required=True)
    check.add_argument('--precheck',type=Path,required=True);check.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();cfg=read(p.CONFIG)
    if args.command in ('guard','run'):
        checkout=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ci.ROOT,text=True).strip()
        precheck.identity(cfg,os.environ,args.source,checkout);selection(os.environ);workflow.workflow()
        if args.command=='guard':return
        result=execute_network(cfg,os.environ,args.source,checkout,args.preflight,args.precheck,args.output)
    else:
        if args.command=='observe':
            manifest=read(args.manifest);plan.driver.operator_account(manifest['plan']['operator'])
            result=capture(cfg,manifest)
        else:
            receipt=read(args.receipt);observed=observation.collect_run(receipt['binding'])
            result=review(cfg,receipt,read(args.after),observed,args.precheck)
        args.output.mkdir(parents=True,exist_ok=False)
        write_once(args.output/('observation.json' if args.command=='observe' else 'receipt.json'),result)
        if args.command=='review':write_once(args.output/'github.json',observed)
    print(m.canonical({k:v for k,v in result.items() if k in ('status','failure','planSha256')}).decode())
    if result.get('status')=='FAIL':raise SystemExit(2)


if __name__=='__main__':main()
