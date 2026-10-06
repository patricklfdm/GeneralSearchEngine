"""Explicit prepare/confirmed-run CLI for the fixed native owned experiment.

Defaults and diagnostics do not allocate. The public network functions fix all
authority, credential, artifact and workload implementations; no backend override.
"""
import argparse
from contextlib import contextmanager
import html
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
import uuid
from . import cloud_runner_admission as admission, cloud_runner_prepared as prepared
from . import cloud_runner_owned as owned, cloud_runner_precheck as precheck
from . import cloud_runner_storage_entry as storage, cloud_runner_review as workflow
from . import cloud_preflight as p, cloud_ci as ci, cloud_authority as a
from . import guest_setup, performance_model as m, remote_command as c

SCHEMA='gse-v51-runner-experiment-entry-v1'
STEP='Run exact approved native V5.1 experiment'
SECRET='V51_EXPERIMENT_SSH_KEY'
FAILURES={
    'experiment SSH secret missing/oversized':'SSH_SECRET_MISSING_OR_INVALID',
    'experiment SSH secret is not an unencrypted Ed25519 private key':'SSH_SECRET_INVALID',
    'experiment prepared SSH key changed':'SSH_KEY_CHANGED',
    'experiment private directory inside evidence':'SSH_DIRECTORY_INSIDE_EVIDENCE',
    'Runner plan drift/expiry':'PLAN_CHANGED_OR_EXPIRED',
    'Runner price freshness/selection':'PRICE_CHANGED_OR_EXPIRED',
    'Runner estimate exceeds approved reservation':'RESERVATION_TOO_SMALL',
    'prepared producer not successful':'PREPARATION_NOT_SUCCESSFUL',
    'prepared artifact missing/duplicate':'PREPARED_ARTIFACT_MISSING_OR_DUPLICATE',
    'prepared exact plan/source confirmation':'PLAN_CONFIRMATION_MISMATCH',
    'prepared original ZIP size/digest':'PREPARED_ARCHIVE_MISMATCH',
    'prepared receipt/approval changed':'PREPARED_RECEIPT_MISMATCH',
    'prepared artifact/producer changed during download':'PREPARATION_CHANGED',
    'preparation CI/precheck changed':'PREPARATION_PREREQUISITES_CHANGED',
    'experiment precheck expired during CI reads':'PRECHECK_EXPIRED',
    'exact-source CI not green':'EXACT_SOURCE_CI_NOT_GREEN',
    'master moved or source is not master':'MASTER_CHANGED',
    'Runner current control state changed':'RETAINED_CONTROL_CHANGED',
}


def failure(phase,error):
    # Only exact source-controlled messages become public codes. Never copy
    # provider output, secret parser diagnostics or credential-bearing URLs.
    return dict(phase=phase,type=type(error).__name__,code=FAILURES.get(str(error),'UNCLASSIFIED'))


def selection(env):
    mode=env.get('RUNNER_EXPERIMENT','off')
    quote=env.get('RUNNER_EXPERIMENT_QUOTE','');run=env.get('RUNNER_PREPARED_RUN','')
    confirmation=env.get('RUNNER_EXPERIMENT_CONFIRMATION','')
    m.need(mode in ('off','prepare','run'),'experiment selection')
    if mode=='off':
        m.need(quote==run==confirmation=='','experiment inputs without selection');return mode
    m.need(env.get('RUNNER_PERMISSION_PRECHECK')=='true' and not env.get('RUNNER_STORAGE_REQUEST') and
           not env.get('RUNNER_STORAGE_CONFIRMATION'),'experiment requires precheck and exclusive selection')
    m.need(env.get('GITHUB_RUN_ATTEMPT')=='1','experiment requires a new dispatch; no job rerun')
    if mode=='prepare':
        m.need(run==confirmation=='' and 0<len(quote.encode())<=16384,'prepare input scope')
        value=m.strict_json(quote.encode())
        m.need(type(value) is dict and set(value)=={'prices','maximumCostMicrousd','sequence'},'prepare quote fields')
        a.digest(value['sequence'],32);a.integer(value['maximumCostMicrousd'],1,a.MAXIMUM_BUDGET_MICROUSD)
    else:
        m.need(quote=='' and re.fullmatch(r'[1-9][0-9]{0,19}',run) and run!=env.get('GITHUB_RUN_ID'),
               'run requires another completed preparation')
        a.digest(confirmation)
    return mode


def guard(cfg, env, source, checkout):
    binding=precheck.identity(cfg,env,source,checkout)
    storage.selection(env);mode=selection(env);workflow.workflow()
    return binding,mode


@contextmanager
def private_key(secret, parent):
    """Environment secret only in an ephemeral directory outside uploaded evidence."""
    m.need(type(secret) is str and 0<len(secret.encode())<=4096,'experiment SSH secret missing/oversized')
    parent=c.directory(parent)
    with tempfile.TemporaryDirectory(prefix='v51-experiment-key-',dir=parent) as temp:
        key=Path(temp)/'identity'
        fd=os.open(key,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as stream:stream.write(secret)
        result=subprocess.run(['ssh-keygen','-y','-P','','-f',str(key)],stdin=subprocess.DEVNULL,
                              capture_output=True,timeout=10)
        m.need(result.returncode==0,'experiment SSH secret is not an unencrypted Ed25519 private key')
        public=guest_setup.ed25519(result.stdout.decode().strip())
        yield key,public


def current(cfg, env, source, checkout, preflight, precheck_root):
    binding,mode=guard(cfg,env,source,checkout)
    m.need(mode!='off','experiment not selected')
    jobs=precheck.collect_jobs(binding)
    proof=storage.check_inputs(cfg,env,binding,preflight,precheck_root,jobs,now=int(time.time()))
    github=ci.collect(source);ci.check(github,source,int(time.time()),(ci.ROOT/ci.WORKFLOW).read_text())
    m.need(github['configurationSha256']==p.configuration(cfg),'experiment protected configuration changed')
    m.need(int(time.time())<proof['expiresAt'],'experiment precheck expired during CI reads')
    return binding,proof,github


def secret_parent(env, root):
    parent=c.directory(Path(env['RUNNER_TEMP']).resolve())
    m.need(not parent.is_relative_to(Path(root).resolve()),'experiment private directory inside evidence')
    return parent


def prepare_network(cfg,env,source,checkout,preflight,precheck_root,output,secret):
    binding,mode=guard(cfg,env,source,checkout);m.need(mode=='prepare','prepare selection required')
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    result=dict(schema=SCHEMA,status='BLOCKED',mode=mode,source=source,binding=binding,
                paidCloud=False,engineWorkloadExecuted=False,fullRemoteQualification=False)
    phase='precheck'
    try:
        binding,before,github=current(cfg,env,source,checkout,preflight,precheck_root)
        phase='artifacts';public=root/'prepared';public.mkdir(mode=0o700)
        admission.artifacts.collect(public/'originals',github)
        proof=admission.artifacts.verify(public/'originals',github,admission.build.binding(ci.ROOT,source))
        phase='key-and-plan'
        with private_key(secret,secret_parent(env,root)) as (key,pub):
            attempt=uuid.uuid4().hex;guest=guest_setup.access(dict(attempt=attempt,user='gse-'+attempt[:24],publicKey=pub))
            guest_setup.check_private_key(key,guest)
            quote=m.strict_json(env['RUNNER_EXPERIMENT_QUOTE'].encode())
            provider=c.read(Path(preflight)/'provider.json')['observations']
            m.need(provider['lease'] is None,'preparation observer lease active')
            value=admission.plan(cfg,proof,guest,quote['prices'],provider['ledger'],sequence=quote['sequence'],
                                 now=int(time.time()),maximum_cost=quote['maximumCostMicrousd'])
        phase='freshness'
        binding,after,current_ci=current(cfg,env,source,checkout,preflight,precheck_root)
        m.need(after==before and current_ci==github,'preparation CI/precheck changed')
        for row in c.read(public/'originals/artifacts.json').values():
            m.need(ci.github(f"actions/artifacts/{row['id']}")==row,'preparation original artifact changed')
        result.update(status='PREPARED',preparation=prepared.save(public,value,binding,now=int(time.time())))
    except (Exception,KeyboardInterrupt) as error:
        result['failure']=failure(phase,error)
    result['checkedAt']=int(time.time());c.write_once(root/'receipt.json',result)
    return result


def run_network(cfg,env,source,checkout,preflight,precheck_root,output,secret):
    binding,mode=guard(cfg,env,source,checkout);m.need(mode=='run','run selection required')
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    result=dict(schema=SCHEMA,status='BLOCKED',mode=mode,source=source,binding=binding,
                paidCloud=False,engineWorkloadExecuted=False,fullRemoteQualification=False)
    phase='precheck'
    try:
        current(cfg,env,source,checkout,preflight,precheck_root)
        phase='prepared-handoff'
        public,value,approved=prepared.collect(root/'handoff',source,int(env['RUNNER_PREPARED_RUN']),
            env['RUNNER_EXPERIMENT_CONFIRMATION'],now=int(time.time()))
        result['planSha256']=approved['planSha256'];result['preparedRun']=int(env['RUNNER_PREPARED_RUN'])
        c.write_once(root/'approval.json',approved)
        phase='key'
        with private_key(secret,secret_parent(env,root)) as (key,pub):
            guest=value['resourcePlan']['guestAccess'];m.need(pub==guest['publicKey'],'experiment prepared SSH key changed')
            guest_setup.check_private_key(key,guest)
            # Native admission rechecks current source/CI/archives/approval and
            # live lease/ledger immediately before once-only resource creation.
            phase='native-experiment'
            answer=owned.run_native(cfg,env,source,checkout,preflight,precheck_root,value,approved,
                                    public/'originals',key,root/'execution')
            result.update(result=answer,status=answer['status'],paidCloud=answer['paidCloud'],
                          engineWorkloadExecuted=answer['engineWorkloadExecuted'])
    except (Exception,KeyboardInterrupt) as error:
        result['failure']=failure(phase,error)
        if phase=='native-experiment':result.update(status='FAIL',paidCloud=None)
    result['checkedAt']=int(time.time());c.write_once(root/'receipt.json',result)
    return result


def summary(root):
    root=Path(root);receipt=c.read(root/'receipt.json') if (root/'receipt.json').is_file() else {}
    # An outer hard timeout can leave the native receipt without the wrapper.
    execution=root/'execution/receipt.json';run=receipt.get('result',c.read(execution) if execution.is_file() else {})
    plan_path=root/('prepared/plan.json' if receipt.get('mode')=='prepare' else 'handoff/prepared/plan.json')
    plan=c.read(plan_path) if plan_path.is_file() else {};stage=plan.get('resourcePlan',{});req=stage.get('request',{})
    provider=plan.get('configuration',{}).get('provider',{});reserve=stage.get('reservation',{})
    recovery=run.get('preparation',{}).get('ownerRecovery',{})
    cleanup=run.get('cleanup') or recovery.get('cleanup') or {}
    def usd(key):return reserve[key]/1_000_000 if key in reserve else 'unavailable'
    rows=[('Status',receipt.get('status',run.get('status','NOT_STARTED_OR_INTERRUPTED'))),
        ('Mode',receipt.get('mode','unavailable')),('Source',receipt.get('source',req.get('source','unavailable'))),
        ('Prepared run',receipt.get('preparedRun',receipt.get('binding',{}).get('runId','unavailable'))),
        ('Plan SHA-256',receipt.get('planSha256',receipt.get('preparation',{}).get('planSha256','unavailable'))),
        ('Sequence',req.get('sequence','unavailable')),('Attempt',req.get('attempt','unavailable')),
        ('Region / zone',str(provider.get('region','?'))+' / '+str(provider.get('zone','?'))),
        ('Topology','3 voters; n2-standard-8; 450 GiB disks'),('Healthy modes','V4.4 local / V5.0 configured / V5.1 automatic'),
        ('Healthy calls',270),('Independent physical/history validation',run.get('evidence',{}).get('physicalHistoryQualified',False)),
        ('Independent backup/restore validation',run.get('evidence',{}).get('backupRestoreQualified',False)),
        ('Request expires (UTC epoch)',plan.get('expiresAt','unavailable')),('Preparation / lease / grace (s)','600 / 5400 / 1080'),
        ('Estimated cost (USD)',plan['estimatedCostMicrousd']/1_000_000 if plan else 'unavailable'),
        ('Reservation (USD)',usd('maximumCostMicrousd')),('Previous charges (USD)',usd('previousCostMicrousd')),
        ('Cumulative ceiling (USD)',a.MAXIMUM_BUDGET_MICROUSD/1_000_000),
        ('Paid execution',receipt.get('paidCloud','not established')),('Engine workload',run.get('engineWorkloadExecuted',False)),
        ('Evidence retention',recovery.get('retention',run.get('retention','not established'))),('Cleanup',cleanup.get('status','not established')),
        ('Lease released',recovery.get('leaseReleased',run.get('leaseReleased',False))),('Full Phase 6 qualification',False),
        ('Failure',receipt.get('failure','none'))]
    def safe(v):return html.escape(str(v)).replace('|','&#124;').replace('\n',' ').replace('\r',' ')
    text='# V5.1 native experiment\n\n| Parameter | Value |\n| --- | --- |\n'
    text+=''.join('| '+safe(k)+' | '+safe(v)+' |\n' for k,v in rows)
    text+='\n## Cells\n\n| Cell | Result |\n| --- | --- |\n'
    for cell in owned.experiment.CELLS:
        passed=cell in run.get('evidence',{}).get('cells',[])
        text+='| '+cell+' | '+('EXECUTED (see independent validation)' if passed else 'NOT_ESTABLISHED')+' |\n'
    budget=run.get('budget',{});spent=budget.get('spentNanos',{})
    if spent:
        text+='\n## Time accounting\n\n| Stage | Seconds |\n| --- | --- |\n'
        text+=''.join('| '+safe(k)+' | '+str(round(v/1e9,3))+' |\n' for k,v in spent.items())
    if run.get('errors'):
        text+='\n## Failures\n\n'+''.join('- '+safe(v.get('phase','unknown'))+': '+safe(v.get('type','failure'))+'\n' for v in run['errors'])
    text+='\nPreparation allocates nothing. Execution requires the exact plan digest and matching environment SSH secret. '
    text+='Failed charges remain recorded. Use a new preparation after failure/expiry; job reruns cannot resume an experiment. '
    text+='A recent manual cleanup is sufficient; schedule is optional.\n'
    return text


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('guard','prepare','run','summary'))
    parser.add_argument('--source');parser.add_argument('--preflight',type=Path);parser.add_argument('--precheck',type=Path)
    parser.add_argument('--output',type=Path);parser.add_argument('--github-step-summary',type=Path)
    args=parser.parse_args()
    # Remove the raw private key before starting any gh/gcloud/java subprocess.
    secret=os.environ.pop(SECRET,'')
    if args.action=='summary':
        m.need(args.output is not None,'summary output required');text=summary(args.output)
        args.output.mkdir(parents=True,exist_ok=True);(args.output/'summary.md').write_text(text)
        if args.github_step_summary:
            with args.github_step_summary.open('a') as stream:stream.write(text)
        return
    cfg=c.read(p.CONFIG);checkout=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ci.ROOT,text=True).strip()
    _,mode=guard(cfg,os.environ,args.source,checkout)
    if args.action=='guard':return
    m.need(args.action==mode and all(v is not None for v in (args.preflight,args.precheck,args.output)),'entry action/paths')
    def interrupted(*_):
        signal.signal(signal.SIGTERM,signal.SIG_IGN);raise KeyboardInterrupt('workflow termination')
    signal.signal(signal.SIGTERM,interrupted)
    fn=prepare_network if mode=='prepare' else run_network
    result=fn(cfg,os.environ,args.source,checkout,args.preflight,args.precheck,args.output,secret)
    print(m.canonical({k:result[k] for k in ('status','mode','paidCloud','fullRemoteQualification')}).decode())
    if result['status'] not in ('PREPARED','PASS'):raise SystemExit(2)


if __name__=='__main__':main()
