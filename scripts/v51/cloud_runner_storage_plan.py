"""Review and once-only operator canary preparation for Runner storage probes.

Preparation and probing reserve separate costs. Neither can pass an engine member.
No Compute operation, IAM change, dispatch or workload is available here.
"""
import argparse
from copy import deepcopy
from pathlib import Path
import re
import subprocess
import time
import uuid
from urllib.parse import quote, urlencode, urlsplit, parse_qsl
from . import cloud_runner_storage as s, cloud_native_authority as n, cloud_authority as a
from . import cloud_http as h, cloud_gcp as g, cloud_preflight as p, cloud_ci as ci
from . import cloud_cleanup_observation as observation, cloud_fixture_driver as driver
from . import cloud_runner_review as review, cloud_identity_audit as audit
from . import performance_model as m
from .remote_command import read, write_once

SCHEMA = 'gse-v51-runner-storage-plan-v1'
MANIFEST = 'gse-v51-runner-storage-prepared-v1'
COST = 1_000_000
FLAGS = dict(paidAdmission=False, objectPermissionsQualified=False, fullRemoteQualification=False, engineWorkloadExecuted=False)


def prices(value, now):
    m.need(type(value) is dict and set(value) == {'observedAt','expiresAt','pricedThroughSeconds','retentionDays','stages','sources'},
           'storage price fields')
    a.integer(value['observedAt'], 1); a.integer(value['expiresAt'], value['observedAt']+1, value['observedAt']+86400)
    m.need(value['observedAt'] <= now < value['expiresAt'], 'storage prices expired/future')
    a.integer(value['pricedThroughSeconds'], 6480, 86400); a.integer(value['retentionDays'], 30, 365)
    m.need(type(value['stages']) is dict and set(value['stages']) == {'prepare','run'}, 'storage price stages')
    for row in value['stages'].values():
        m.need(type(row) is dict and set(row) == {'requests','retention','actions','failureOverhang'}, 'storage price coverage')
        for cost in row.values(): a.integer(cost, 1, COST)
        m.need(sum(row.values()) <= COST, 'storage estimate exceeds stage reservation')
    sources = value['sources']
    m.need(type(sources) is list and 1 <= len(sources) <= 8 and all(type(v) is str and len(v) <= 1024 and
           re.fullmatch(r'https://(?:cloud|docs\.cloud)\.google\.com/[^\s]+|https://docs\.github\.com/[^\s]+',v) for v in sources),
           'storage price sources')


def make(cfg, source, operator, pricing, before, *, now, identities, offline=False):
    p.configuration(cfg); a.digest(source,40); a.integer(now,1)
    m.need(type(offline) is bool and type(operator) is str and re.fullmatch(r'[A-Za-z0-9_.+%-]+@[A-Za-z0-9.-]+',operator)
           and not operator.startswith(('gse-v51-','gse-v50-')), 'storage preparer must be operator')
    observation.envelope(cfg,before)
    m.need(before['execution'] == ('offline-cleanup-observation' if offline else 'read-only-native-cleanup-observation') and
           before['source'] == source and before['referenceSha256'] is None and before['lease'] is None and
           now-300 <= before['startedAt'] <= before['completedAt'] <= now, 'storage preparation control observation')
    old = observation.item(before['ledger']) or n.empty_ledger(); total, attempts = n.inspect_ledger(old)
    m.need(not any(v['status']=='PENDING' for v in attempts.values()) and total+2*COST <= a.MAXIMUM_BUDGET_MICROUSD,
           'storage pending attempt or budget ceiling')
    m.need(type(identities) is dict and set(identities)=={'prepareAttempt','prepareSequence','runAttempt','runSequence'}
           and len(set(identities.values()))==4, 'storage distinct stage identities')
    for value in identities.values(): a.digest(value,32)
    prices(pricing,now)
    specification = dict(purpose='storage-only',configurationSha256=p.configuration(cfg),
                         pricesSha256=m.sha(m.canonical(pricing)),maximumCostPerStageMicrousd=COST,
                         stages=['prepare','run'],resourcesAttempted=0)
    requests = {stage:n.request(source,m.sha(m.canonical(dict(specification,stage=stage))),g.config(cfg['provider']),
                identities[stage+'Sequence'],identities[stage+'Attempt'],'experiment',now=now,
                guest_access_sha256=m.sha(m.canonical(dict(purpose='storage-only; no SSH',stage=stage)))) for stage in ('prepare','run')}
    result = dict(schema=SCHEMA,execution='offline-runner-storage-plan' if offline else 'operator-runner-storage-plan',
                configuration=deepcopy(cfg),operator=operator,prices=deepcopy(pricing),before=deepcopy(before),
                identities=deepcopy(identities),requests=requests,previousCostMicrousd=total,
                maximumCostPerStageMicrousd=COST,maximumCombinedCostMicrousd=2*COST,
                expiresAt=min(now+900,pricing['expiresAt']),**FLAGS)
    return m.strict_json(m.canonical(result))


def validate(value, *, now):
    req = value['requests']['prepare']
    expected = make(value['configuration'],req['source'],value['operator'],value['prices'],value['before'],
                    now=req['createdAt'],identities=value['identities'],offline=value['execution']=='offline-runner-storage-plan')
    m.need(value==expected and len(m.canonical(value)) <= 1<<20 and
           req['createdAt'] <= now < value['expiresAt'], 'storage plan drift/expiry/size')
    prices(value['prices'],now)
    return m.sha(m.canonical(value))


def manifest_key(sha):
    a.digest(sha); return n.PREFIX+'runner-storage-requests/'+sha+'.json'


def prepared_completion(req):
    return dict(s.completion(req),reason='storage-only canary preparation; no engine workload')


def ledgers(value):
    old = observation.item(value['before']['ledger']) or n.empty_ledger()
    req = value['requests']['prepare']
    reserved = n.reserve(old,req,dict(previousCostMicrousd=value['previousCostMicrousd'],maximumCostMicrousd=COST))
    return reserved,n.finish(reserved,req,prepared_completion(req))


def validate_manifest(value, cfg, sha, *, now, offline=False):
    m.need(type(value) is dict and set(value)=={'schema','plan','planSha256','preparedAt','baseline'} and
           value['schema']==MANIFEST and value['planSha256']==sha, 'storage manifest shape')
    plan=value['plan']; m.need(validate(plan,now=now)==sha and plan['configuration']==cfg and
        plan['execution']==('offline-runner-storage-plan' if offline else 'operator-runner-storage-plan'), 'storage manifest binding/domain')
    a.integer(value['preparedAt'],plan['requests']['prepare']['createdAt'],now)
    keys=s.inventory(plan['requests']['run']);baseline=value['baseline']
    m.need(type(baseline) is dict and set(baseline)=={n.LEDGER,keys['existing'],keys['outside']},'storage prepared inventory')
    for row in baseline.values():
        m.need(type(row) in (list,tuple) and len(row)==2,'storage prepared row');a.integer(row[0],1)
    m.need(baseline[n.LEDGER][1]==ledgers(plan)[1], 'storage preparation ledger not terminal')
    for name in ('existing','outside'):
        m.need(baseline[keys[name]][1]==s.canary(plan['requests']['run'],name),'storage prepared canary bytes')
    return plan


class Store(g.Store):
    def __init__(self, cfg, api, value):
        super().__init__(cfg,api,authority=n)
        self.keys={n.LEASE,n.LEDGER,manifest_key(m.sha(m.canonical(value))),
                   *s.inventory(value['requests']['prepare']).values(),*s.inventory(value['requests']['run']).values()}
    def url(self,key):
        m.need(key in self.keys,'storage preparation read scope')
        return self.base+quote(key,safe='')


class _Preparation(h.Api):
    def initialize(self, value, now):
        self.sha=validate(value,now=now);self.value=deepcopy(value)
        self.cfg=value['configuration']['provider'];self.req=value['requests']['prepare']
        self.store=Store(self.cfg,self,value);self.stage=0;self.expected=None;self.failed=False;self.requests=[]
        self.deadline=self.clock()+min(300,value['expiresAt']-now)
        self.lease=n.lease(self.req,now);self.generation=None;self.baseline={}
        self.reserved,self.terminal=ledgers(value)
        self.manifest=None;self.prepared_at=None
    def authorize(self, method, url, body):
        if method=='GET':
            purl=urlsplit(url);pairs=parse_qsl(purl.query,strict_parsing=True) if purl.query else [];q=dict(pairs)
            m.need(body is None and len(q)==len(pairs) and purl._replace(query='').geturl() in
                   {self.store.url(k) for k in self.store.keys},'preparation closed GET')
            m.need(not q or set(q)=={'alt','generation','ifGenerationMatch'} and q['alt']=='media' and
                   q['generation']==q['ifGenerationMatch'] and g.numeric(q['generation']), 'preparation pinned GET')
        else:
            m.need(not self.failed and self.expected==(method,url,body),'preparation original mutation scope')
            self.expected=None
    def call(self, method, url, body=None, **kwargs):
        kwargs['deadline']=min(kwargs['deadline'],self.deadline)
        m.need(len(self.requests)<128,'preparation request bound')
        record=dict(method=method,url=url,bodySha256=m.sha(m.canonical(body)) if body is not None else None,outcome='UNRESOLVED')
        self.requests.append(record)
        try:result=super().call(method,url,body,**kwargs)
        except h.ApiError as error:
            record.update(outcome='HTTP_ERROR',httpStatus=error.status);raise
        record['outcome']='SUCCESS';return result
    def step(self, *, now):
        value=self.value;keys=s.inventory(value['requests']['run']);prior=value['before']['ledger']
        writes=[(n.LEASE,self.lease,0),(n.LEDGER,self.reserved,prior[0] if prior else 0),
                (keys['existing'],s.canary(value['requests']['run'],'existing'),0),
                (keys['outside'],s.canary(value['requests']['run'],'outside'),0),
                (s.inventory(self.req)['completion'],prepared_completion(self.req),0)]
        if self.stage<5:key,body,generation=writes[self.stage]
        elif self.stage==5:
            m.need(self.store.get(n.LEDGER)==(self.reservation_generation,self.reserved),'preparation reservation changed')
            key,body,generation=n.LEDGER,self.terminal,self.reservation_generation
        elif self.stage==6:
            m.need(self.store.get(n.LEDGER)==(self.terminal_generation,self.terminal),'preparation terminal ledger changed')
            key,body,generation=n.LEASE,None,self.generation
        elif self.stage==7:
            m.need(self.store.get(n.LEASE) is None,'preparation lease still held')
            self.baseline[n.LEDGER]=list(self.store.get(n.LEDGER))
            m.need(self.baseline[n.LEDGER]==[self.terminal_generation,self.terminal],'preparation final ledger changed')
            self.manifest=dict(schema=MANIFEST,plan=value,planSha256=self.sha,preparedAt=now,baseline=deepcopy(self.baseline))
            validate_manifest(self.manifest,value['configuration'],self.sha,now=now,offline=self.offline)
            key,body,generation=manifest_key(self.sha),self.manifest,0
        else:raise ValueError('preparation already submitted')
        method='DELETE' if self.stage==6 else 'POST'
        url=self.store.url(key)+'?ifGenerationMatch='+str(generation) if method=='DELETE' else self.upload+'?'+urlencode(
            dict(uploadType='media',name=key,ifGenerationMatch=generation))
        self.expected=(method,url,body)
        try:
            if method=='DELETE':self.store.delete(key,generation)
            else:
                gen=self.store.put(key,body,generation)
                if key==n.LEASE:self.generation=gen
                if key==n.LEDGER:
                    if self.stage==1:self.reservation_generation=gen
                    else:self.terminal_generation=gen
                if key in (keys['existing'],keys['outside']):self.baseline[key]=[gen,deepcopy(body)]
        except BaseException:self.failed=True;raise
        self.stage+=1


class OfflinePreparation(_Preparation):
    def __init__(self,value,*,transport,clock,now):
        m.need(transport.offline and value['execution']=='offline-runner-storage-plan','offline preparation required')
        h.Api.__init__(self,transport=transport,tokens=lambda _: 'offline-token',clock=clock)
        self.initialize(value,now)
        self.upload='https://storage.googleapis.com/upload/storage/v1/b/'+self.cfg['bucket']+'/o'


def protected(value):
    cfg=read(p.CONFIG);source=value['requests']['prepare']['source']
    m.need(cfg==value['configuration'] and driver.checkout()==source,'preparation protected source/configuration')
    driver.operator_account(value['operator'])
    github=ci.collect(source);ci.check(github,source,int(time.time()),(ci.ROOT/ci.WORKFLOW).read_text())
    m.need(github['configurationSha256']==p.configuration(cfg),'protected configuration differs')
    review.workflow()
    identities=audit.collect(cfg,'staged')
    m.need(review.evaluate(cfg,'enabled',identities,now=int(time.time()))['status']=='CONFIGURATION_MATCH','Runner configuration changed')
    before=observation.capture(cfg,source)
    observation.envelope(cfg,before)
    m.need(before['lease'] is None and m.canonical(before['ledger'])==m.canonical(value['before']['ledger']), 'preparation control changed')
    return dict(github=github,identities=identities,before=before)


class NetworkPreparation(_Preparation):
    def __init__(self,value,confirmation):
        m.need(value['execution']=='operator-runner-storage-plan' and validate(value,now=int(time.time()))==confirmation,
               'exact preparation confirmation required')
        self.evidence=protected(value)
        def token(timeout):
            driver.operator_account(value['operator'])
            result=subprocess.run(['gcloud','auth','print-access-token','--account='+value['operator']],capture_output=True,timeout=timeout)
            m.need(result.returncode==0 and result.stdout.strip(),'operator token unavailable')
            return result.stdout.decode().strip()
        h.Api.__init__(self,transport=h.Network(),tokens=token)
        self.initialize(value,int(time.time()))
        self.upload='https://storage.googleapis.com/upload/storage/v1/b/'+self.cfg['bucket']+'/o'


def prepare(api, output, *, wall=time.time):
    m.need(type(api) in (OfflinePreparation,NetworkPreparation),'preparation policy required')
    root=Path(output);root.mkdir(parents=True,exist_ok=False);write_once(root/'plan.json',api.value)
    result=dict(schema=MANIFEST,status='FAIL',execution='offline-storage-preparation' if api.offline else 'operator-storage-preparation',
                planSha256=api.sha,paidCloud=not api.offline,**FLAGS)
    try:
        validate(api.value,now=int(wall()));store=api.store
        m.need(store.get(n.LEASE) is None and m.canonical(store.get(n.LEDGER))==m.canonical(api.value['before']['ledger']), 'preparation state changed')
        for key in store.keys-{n.LEASE,n.LEDGER}:m.need(store.get(key) is None,'preparation attempt already exists')
        for _ in range(8):api.step(now=int(wall()))
        result.update(status='PREPARED',manifest=api.manifest,confirmation=m.sha(m.canonical(api.manifest)),
                      expiresAt=api.value['expiresAt'],previousCostMicrousd=api.value['previousCostMicrousd'],
                      preparationReservedMicrousd=COST,runnerReservationMicrousd=COST)
    except (Exception,KeyboardInterrupt) as error:
        result['failure']=dict(stage=api.stage,type=type(error).__name__)
        if isinstance(error,h.ApiError):result['failure']['httpStatus']=error.status
    finally:
        write_once(root/'receipt.json',result);write_once(root/'http.json',api.requests)
        if hasattr(api,'evidence'):write_once(root/'entry-evidence.json',api.evidence)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    plan=sub.add_parser('plan');plan.add_argument('--source',required=True);plan.add_argument('--operator',required=True)
    plan.add_argument('--prices',type=Path,required=True);plan.add_argument('--before',type=Path,required=True)
    plan.add_argument('--output',type=Path,required=True)
    run=sub.add_parser('prepare');run.add_argument('--plan',type=Path,required=True);run.add_argument('--confirm',required=True)
    run.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='plan':
        value=make(read(p.CONFIG),args.source,args.operator,read(args.prices),read(args.before),now=int(time.time()),
                   identities={k:uuid.uuid4().hex for k in ('prepareAttempt','prepareSequence','runAttempt','runSequence')})
        args.output.mkdir(parents=True,exist_ok=False);write_once(args.output/'plan.json',value)
        result=dict(status='REVIEW_ONLY',planSha256=validate(value,now=int(time.time())),**FLAGS)
        write_once(args.output/'review.json',result)
    else:result=prepare(NetworkPreparation(read(args.plan),args.confirm),args.output)
    print(m.canonical({k:v for k,v in result.items() if k in ('status','planSha256','confirmation','failure')}).decode())
    if result['status']=='FAIL':raise SystemExit(2)


if __name__=='__main__':main()
