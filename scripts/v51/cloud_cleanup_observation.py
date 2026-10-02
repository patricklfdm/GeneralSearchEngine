"""Read-only native cleanup state observations and independent transition review.

No allocation, cleanup invocation, dispatch, identity change or admission result.
Retained JSON is review evidence, not authenticated artifact provenance or IAM proof.
"""
import argparse
from pathlib import Path
import subprocess
import time
from . import cloud_authority as a, cloud_native_authority as n, cloud_gcp as g
from . import cloud_cleanup as cleanup, cloud_cleanup_entry as entry, cloud_ci as ci
from . import cloud_preflight as preflight, cloud_http, performance_model as m
from .remote_command import read, write_once

SCHEMA = 'gse-v51-cleanup-observation-v1'
BOUNDARY = dict(activationAllowed=False, effectiveIamQualified=False, cleanupReady=False,
                paidAdmission=False, paidCloud=False, fullRemoteQualification=False,
                artifactProvenanceVerified=False)


class Reads:
    """A fixed total deadline and GET-only boundary, including offline test inputs."""
    def __init__(self, api):
        self.api = api; self.clock = api.clock; self.offline = api.offline
        self.deadline = self.clock()+180
    def call(self, method, url, body=None, *, deadline, **kwargs):
        m.need(method=='GET' and body is None, 'cleanup observation is read-only')
        return self.api.call(method, url, deadline=min(deadline, self.deadline), **kwargs)


def item(value):
    if value is None: return None
    m.need(type(value) in (list, tuple) and len(value)==2, 'observation object')
    a.integer(value[0], 1)
    return value[1]


def envelope(cfg, value):
    m.need(value['schema']==SCHEMA and value['status']=='OBSERVED' and
           value['execution'] in ('read-only-native-cleanup-observation','offline-cleanup-observation') and
           value['configurationSha256']==preflight.configuration(cfg), 'observation scope/status')
    a.digest(value['source'], 40); a.digest(value['collectorSha256']); a.integer(value['startedAt'], 1); a.integer(value['completedAt'], 1)
    m.need(value['startedAt']<=value['completedAt']<=value['startedAt']+180, 'observation time bound')
    m.need(all(value[k] is False for k in BOUNDARY), 'observation claimed admission')
    lease = item(value['lease']); ledger = item(value['ledger'])
    if lease is not None:
        n.validate_lease(lease)
        m.need(lease['request']['configurationSha256']==g.config(cfg['provider']), 'observation lease configuration')
    n.inspect_ledger(ledger if ledger is not None else n.empty_ledger())
    return lease


def capture(cfg, source, *, before=None, api=None, wall=time.time):
    a.digest(source, 40); digest=preflight.configuration(cfg)
    if before is not None:
        envelope(cfg,before)
        m.need(before['referenceSha256'] is None and before['source']==source, 'original before observation required')
    api=Reads(api if api is not None else cloud_http.Api());store=g.Store(cfg['provider'],api,authority=n)
    value=dict(schema=SCHEMA,execution='offline-cleanup-observation' if api.offline else 'read-only-native-cleanup-observation',
               source=source,collectorSha256=m.sha(Path(__file__).read_bytes()),configurationSha256=digest,startedAt=int(wall()),status='BLOCKED',
               referenceSha256=m.sha(m.canonical(before)) if before is not None else None,
               resources=[],context=None,completion=None,**BOUNDARY)
    phase='control'
    try:
        value['lease']=store.get(n.LEASE);value['ledger']=store.get(n.LEDGER)
        lease=item(value['lease']);ledger=item(value['ledger'])
        if lease is not None:n.validate_lease(lease)
        n.inspect_ledger(ledger if ledger is not None else n.empty_ledger())
        authority=item(before['lease']) if before is not None else lease
        if before is not None:
            m.need(lease is None or authority is not None and lease['request']==authority['request'], 'observed another lease')
        if authority is not None:
            req=authority['request'];sha=n.validate_request(req)
            m.need(g.config(cfg['provider'])==req['configurationSha256'],'observed request configuration')
            phase='retained-context'
            value['context']=store.get(cleanup.context_key(req,authority=n))
            value['completion']=store.get(n.PREFIX+'attempts/'+sha+'/completion.json')
            rows=[r for r in authority['resources'] if r['attempted']]
            if rows:
                context=cleanup.validate_context(item(value['context']),req,authority=n)
                provider=cleanup.provider_from_context(context,req,api,authority=n)
                phase='resource-observation'
                for row in rows:
                    spec=row['spec'];operation=provider.operation(spec)
                    identity=operation['id'] if operation['state']=='DONE' else row['id']
                    if identity is not None:g.numeric(identity)
                    value['resources'].append(dict(spec=spec,operation=operation,byName=provider.describe(spec),
                        queriedId=identity,byId=provider.describe(spec,identity=identity) if identity is not None else None))
            phase='stable-attempt-context'
            m.need(value['context']==store.get(cleanup.context_key(req,authority=n)) and
                   value['completion']==store.get(n.PREFIX+'attempts/'+sha+'/completion.json'),'attempt objects changed during observation')
        phase='stable-control'
        m.need(value['lease']==store.get(n.LEASE) and value['ledger']==store.get(n.LEDGER),
               'control changed during observation')
        m.need(api.clock()<=api.deadline,'observation deadline')
        value['status']='OBSERVED'
    except (Exception,KeyboardInterrupt) as error:
        value['failure']=dict(phase=phase,type=type(error).__name__)  # No provider/credential text.
    value['completedAt']=int(wall())
    if value['completedAt']>value['startedAt']+180:
        value.update(status='BLOCKED',failure=dict(phase='deadline',type='TimeoutError'))
    return value


def completed_run(binding, value):
    # Reuse exact repository/entry checks without treating completion as a live entry.
    m.need(value['status']=='completed' and value['conclusion']=='success','cleanup run not successful')
    entry.validate_run(binding,dict(value,status='in_progress',conclusion=None))


def collect_run(binding, get=ci.github):
    a.integer(binding['runId'],1);a.integer(binding['runAttempt'],1)
    path='actions/runs/'+str(binding['runId']); before=get(path)
    attempt=get(path+'/attempts/'+str(binding['runAttempt']))
    jobs=get(path+'/attempts/'+str(binding['runAttempt'])+'/jobs?per_page=100')
    after=get(path)
    return dict(before=before,attempt=attempt,after=after,jobs=jobs)


def check_run(binding, observed):
    for key in ('before','attempt','after'):completed_run(binding,observed[key])
    jobs=observed['jobs']
    m.need(jobs['total_count']==1 and len(jobs['jobs'])==1,'cleanup job inventory')
    job=jobs['jobs'][0]
    m.need(job['run_id']==binding['runId'] and job['run_attempt']==binding['runAttempt'] and
           job['head_sha']==binding['source'] and job['name']=='cleanup' and
           job['status']=='completed' and job['conclusion']=='success','cleanup job identity/result')
    for name in ('Bind cleanup entry and exact run attempt','Authenticate exact cleanup identity',
                 'Check actual cleanup permissions without cloud mutations',
                 'Reconcile retained expired lease','Retain cleanup diagnostics'):
        steps=[s for s in job['steps'] if s['name']==name]
        m.need(len(steps)==1 and steps[0]['status']=='completed' and steps[0]['conclusion']=='success',
               'cleanup step missing/skipped/failed')
    return ci.timestamp(job['started_at']),ci.timestamp(job['completed_at'])


def resource_rows(lease, value):
    expected=[r['spec'] for r in lease['resources'] if r['attempted']]
    rows=value['resources'];m.need(type(rows) is list and [r['spec'] for r in rows]==expected,'resource observation inventory')
    for row in rows:
        op=row['operation'];m.need(op['spec']==row['spec'] and op['state'] in ('DONE','PENDING','UNKNOWN'),'operation observation')
        if op['id'] is not None:g.numeric(op['id'])
        m.need(op['state']=='DONE' or op['id'] is None,'unresolved operation ID')
        for key in ('byName','byId'):
            observed=row[key]
            if observed is not None:
                m.need(observed['spec']==row['spec'],'observed resource spec');g.numeric(observed['id'])
        if row['queriedId'] is not None:g.numeric(row['queriedId'])
        m.need(row['byId'] is None or row['byId']['id']==row['queriedId'],'numeric resource observation')
        if op['state']=='DONE':
            m.need(row['queriedId']==op['id'] and all(row[k] is None or row[k]['id']==op['id'] for k in ('byName','byId')),
                   'resource differs from original operation')
    return rows


def review(cfg, source, before, after, binding, receipt, observed_run):
    """Review a successful run bracketed by two stable state samples; never admit."""
    result=dict(schema='gse-v51-cleanup-state-review-v1',status='BLOCKED',source=source,**BOUNDARY)
    try:
        left=envelope(cfg,before);right=envelope(cfg,after)
        m.need(before['source']==after['source']==source and before['referenceSha256'] is None and
               after['referenceSha256']==m.sha(m.canonical(before)),'observation chain/source')
        m.need(before['execution']==after['execution'] and before['collectorSha256']==after['collectorSha256'],
               'observation execution/collector changed')
        trigger=binding['trigger'];a.integer(binding['runId'],1);a.integer(binding['runAttempt'],1)
        selected=entry.identities.proposal(cfg)['identities'][trigger]
        env=dict(GITHUB_ACTIONS='true',GITHUB_REPOSITORY=ci.REPOSITORY,GITHUB_REPOSITORY_ID=str(ci.REPOSITORY_ID),
                 GITHUB_REPOSITORY_OWNER_ID=str(ci.OWNER_ID),GITHUB_EVENT_NAME=selected['claims']['event_name'],
                 GITHUB_REF='refs/heads/master',GITHUB_WORKFLOW_REF=selected['claims']['workflow_ref'],GITHUB_WORKFLOW_SHA=source,
                 GITHUB_SHA=source,GITHUB_JOB='cleanup',CLEANUP_ENVIRONMENT=selected['environment'],
                 GITHUB_RUN_ID=str(binding['runId']),GITHUB_RUN_ATTEMPT=str(binding['runAttempt']))
        m.need(binding==entry.identity(cfg,env,trigger=trigger,source=source,checkout=source),'cleanup binding changed')
        start,end=check_run(binding,observed_run)
        a.integer(receipt['checkedAt'],1)
        m.need(before['completedAt']<=start<=receipt['checkedAt']<=end<=after['startedAt'], 'run not bracketed by observations')
        m.need(all(receipt[k]==v for k,v in binding.items()) and receipt['execution']=='gcp-native-cleanup-entry' and
               receipt['credentialExchangeCompleted'] is True and receipt['effectiveIamQualified'] is False,'cleanup receipt binding/exchange')
        inner=receipt['reconciliation']
        m.need(inner['trigger']==trigger and inner['execution']==n.CLEANUP_EXECUTION and receipt['status']==inner['status'], 'reconciliation identity')
        m.need('failure' not in receipt and 'failure' not in inner,'cleanup failure retained')
        old=item(before['ledger']);new=item(after['ledger'])
        old=old if old is not None else n.empty_ledger();new=new if new is not None else n.empty_ledger()
        old_cost,old_attempts=n.inspect_ledger(old);new_cost,new_attempts=n.inspect_ledger(new)
        m.need(old_cost==new_cost,'cleanup charge changed')
        if left is not None:
            sha=n.validate_request(left['request'])
            m.need(sha in old_attempts and old_attempts[sha]['request']==left['request'],'lease reservation differs')
        if left is None:
            m.need(right is None and before['ledger']==after['ledger'] and before['resources']==after['resources']==[] and
                   not any(v['status']=='PENDING' for v in new_attempts.values()),'empty cleanup changed/unresolved state')
            m.need(receipt['status']=='PASS' and inner.get('activeLease') is False,'no-lease receipt')
            case='NO_LEASE'
        elif receipt['status']=='WAITING':
            m.need(receipt['checkedAt']<left['expiresAt']+left['graceSeconds'] and inner.get('activeLease') is True,'waiting expiry boundary')
            m.need(all(before[k]==after[k] for k in ('lease','ledger','context','completion','resources')),'waiting changed state')
            resource_rows(left,before);resource_rows(left,after);case='ACTIVE_OR_GRACE'
        else:
            m.need(receipt['status']=='PASS' and receipt['checkedAt']>=left['expiresAt']+left['graceSeconds'] and
                   inner.get('leaseReleased') is True and right is None,'expired cleanup boundary/release')
            sha=n.validate_request(left['request']);m.need(sha in old_attempts,'missing original reservation')
            m.need(before['context']==after['context'],'retained context changed')
            if item(before['completion']) is not None:m.need(before['completion']==after['completion'],'completion replaced')
            completion=item(after['completion'])
            m.need(completion['schema']==n.COMPLETION_SCHEMA and completion['execution']==n.EXECUTION and
                   completion['paidCloud'] is True and completion['requestSha256']==sha,'terminal completion identity')
            if item(before['completion']) is None:m.need(completion['status']=='FAIL','cleanup invented successful workload')
            expected=n.finish(old,left['request'],completion) if old_attempts[sha]['status']=='PENDING' else old
            m.need(new==expected and new_attempts[sha]['status']==completion['status'],'terminal ledger append differs')
            m.need(any(v.get('completionSha256')==m.sha(m.canonical(completion)) and v['requestSha256']==sha for v in new['entries']), 'completion ledger hash')
            previous=resource_rows(left,before);current=resource_rows(left,after)
            for retained,pre,post in zip([r for r in left['resources'] if r['attempted']],previous,current):
                if pre['operation']['state']=='DONE':m.need(pre['operation']==post['operation'],'original operation changed')
                op=post['operation'];m.need(op['state']=='DONE' and post['queriedId']==op['id'] and
                    (retained['id'] is None or retained['id']==op['id']) and post['byName'] is None and post['byId'] is None,'unresolved original operation or resource remains')
            outcome=inner['cleanup'];m.need(outcome['status']=='PASS' and outcome['errors']==outcome['leftovers']==[],'cleanup outcome')
            expected_checks=[dict(name=r['spec']['name'],expectedId=r['operation']['id'],absent=True,observed=None) for r in current]
            m.need(sorted(outcome['checks'],key=lambda r:r['name'])==sorted(expected_checks,key=lambda r:r['name']),'absence receipt differs from independent state')
            result['previouslyPresentResources']=sum(r['byName'] is not None for r in previous)
            result['attemptedResources']=len(current);case='EXPIRED_ABSENCE_CONFIRMED'
        result.update(status='STATE_MATCH',case=case,runId=binding['runId'],runAttempt=binding['runAttempt'],
                      execution=before['execution'],retainedCostMicrousd=new_cost,
                      limitations=['Local evidence provenance and effective IAM are not established by this comparison.',
                                   'Before/after state does not identify who issued a delete; provider audit evidence remains required.'])
    except (ValueError,KeyError,TypeError,IndexError,AttributeError) as error:
        result['failure']=dict(type=type(error).__name__,reason=str(error)[:180])
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    capture_parser=sub.add_parser('capture');capture_parser.add_argument('--before',type=Path)
    capture_parser.add_argument('--output',type=Path,required=True)
    review_parser=sub.add_parser('review');review_parser.add_argument('--before',type=Path,required=True)
    review_parser.add_argument('--after',type=Path,required=True);review_parser.add_argument('--entry',type=Path,required=True)
    review_parser.add_argument('--output',type=Path,required=True)
    args=p.parse_args();cfg=read(preflight.CONFIG)
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ci.ROOT,text=True).strip()
    args.output.mkdir(parents=True,exist_ok=False)
    if args.command=='capture':
        result=capture(cfg,source,before=read(args.before) if args.before else None)
        write_once(args.output/'observation.json',result)
    else:
        binding=read(args.entry/'binding.json');receipt=read(args.entry/'receipt.json')
        observed=collect_run(binding);write_once(args.output/'github.json',observed)
        result=review(cfg,source,read(args.before),read(args.after),binding,receipt,observed)
        write_once(args.output/'review.json',result)
    print(m.canonical({k:result[k] for k in ('status','source','execution','case','failure','cleanupReady') if k in result}).decode())
    return 2 if result['status']=='BLOCKED' else 0


if __name__=='__main__':raise SystemExit(main())
