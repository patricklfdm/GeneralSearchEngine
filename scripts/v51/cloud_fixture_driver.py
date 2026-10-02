"""Exact-request single-disk preparation; no workload, cleanup, IAM change or retry."""
import argparse
from copy import deepcopy
import os
import re
from pathlib import Path
import subprocess
import time
from urllib.parse import quote, urlencode
import uuid
from . import cloud_authority as a, cloud_native_authority as n, cloud_gcp as g
from . import cloud_http as h, cloud_preflight as p, cloud_ci as ci
from . import cloud_cleanup as cleanup, cloud_cleanup_observation as observation
from . import cloud_cleanup_deployment as deployment, cloud_identity_audit as audit
from . import performance_model as m, remote_command as c, guest_setup

SCHEMA='gse-v51-single-disk-request-v1'
COST=1_000_000
BOUNDARY=dict(cleanupReady=False, paidAdmission=False, fullRemoteQualification=False,
              objectPermissionsQualified=False, engineWorkloadExecuted=False)


def price(value, now):
    """Operator-reviewed inputs, not a provider quote or automatic financial approval."""
    m.need(type(value) is dict and set(value)=={'observedAt','expiresAt','region','diskType',
        'diskMicrousdPerGiBHour','pricedThroughSeconds','otherCostsMicrousd','sources'}, 'fixture price fields')
    a.integer(value['observedAt'],1);a.integer(value['expiresAt'],value['observedAt']+1,value['observedAt']+86400)
    m.need(value['observedAt']<=now<value['expiresAt'] and
           (value['region'],value['diskType'])==('us-west4','pd-balanced'), 'fixture price age/region')
    rate=a.integer(value['diskMicrousdPerGiBHour'],1,COST)
    seconds=a.integer(value['pricedThroughSeconds'],6480,86400)
    extra=value['otherCostsMicrousd']
    m.need(type(extra) is dict and set(extra)=={'requests','retention30Days','actions','failureOverhang'}, 'fixture price coverage')
    for amount in extra.values():a.integer(amount,1,COST)
    sources=value['sources']
    m.need(type(sources) is list and 1<=len(sources)<=8 and all(type(v) is str and len(v)<=1024 and
           re.fullmatch(r'https://(?:cloud|docs\.cloud)\.google\.com/[^\s]+|https://docs\.github\.com/[^\s]+',v)
           for v in sources), 'fixture price sources')
    total=(100*rate*seconds+3599)//3600+sum(extra.values())
    m.need(total<=COST, 'fixture estimate exceeds reservation')
    return total


def objects(req):
    sha=n.validate_request(req);prefix=n.PREFIX+'attempts/'+sha+'/'
    return dict(manifest=prefix+'single-disk-fixture.json', existing=prefix+'canary-existing.json',
                created=prefix+'canary-created.json',
                outside='v5.1-cleanup-qualification-canaries/'+req['attempt']+'/outside.json')


def canary(req, kind):
    m.need(kind in ('existing','created','outside'),'fixture canary kind')
    return dict(schema='gse-v51-cleanup-canary-v1',requestSha256=n.validate_request(req),kind=kind)


def make(cfg, source, operator, public_key, prices, before, *, now, attempt, sequence, offline=False):
    p.configuration(cfg);a.digest(source,40);a.digest(attempt,32);a.digest(sequence,32);a.integer(now,1)
    m.need(type(offline) is bool and type(operator) is str and re.fullmatch(r'[A-Za-z0-9_.+%-]+@[A-Za-z0-9.-]+',operator), 'fixture operator')
    m.need(not operator.startswith(('gse-v51-','gse-v50-')), 'fixture preparer must be a separately approved operator')
    observation.envelope(cfg,before)
    expected_execution='offline-cleanup-observation' if offline else 'read-only-native-cleanup-observation'
    m.need(before['execution']==expected_execution and before['source']==source and before['lease'] is None and
           before['referenceSha256'] is None and now-300<=before['startedAt']<=before['completedAt']<=now,
           'fixture needs fresh independent empty lease observation')
    old=observation.item(before['ledger']);total,attempts=n.inspect_ledger(old if old is not None else n.empty_ledger())
    m.need(not any(v['status']=='PENDING' for v in attempts.values()) and total+COST<=a.MAXIMUM_BUDGET_MICROUSD,
           'fixture pending attempt/budget')
    estimate=price(prices,now)
    manifest=dict(schema='gse-v51-single-disk-manifest-v1',source=source,configurationSha256=p.configuration(cfg),
                  kind='cleanup-qualification',disk=dict(node=1,purpose='data',sizeGiB=100),
                  leaseSeconds=5400,graceSeconds=1080,maximumCostMicrousd=COST,pricesSha256=m.sha(m.canonical(prices)))
    guest=dict(attempt=attempt,user='gse-'+attempt[:24],publicKey=public_key);guest_setup.access(guest)
    req=n.request(source,m.sha(m.canonical(manifest)),g.config(cfg['provider']),sequence,attempt,'experiment',
                  now=now,guest_access_sha256=m.sha(m.canonical(guest)))
    return dict(schema=SCHEMA,execution='offline-single-disk-request' if offline else 'operator-single-disk-request',
                configuration=deepcopy(cfg),request=req,guestAccess=guest,operator=operator,
                qualificationManifest=manifest,prices=deepcopy(prices),estimatedCostMicrousd=estimate,
                before=deepcopy(before),previousCostMicrousd=total,maximumCostMicrousd=COST,
                expiresAt=min(now+900,prices['expiresAt']),**BOUNDARY)


def validate(value, *, now):
    req=value['request'];cfg=value['configuration']
    expected=make(cfg,req['source'],value['operator'],value['guestAccess']['publicKey'],value['prices'],value['before'],
                  now=req['createdAt'],attempt=req['attempt'],sequence=req['sequence'],
                  offline=value['execution']=='offline-single-disk-request')
    m.need(value==expected,'fixture request drift')
    m.need(req['createdAt']<=now<value['expiresAt'],'fixture request expired/future')
    price(value['prices'],now)
    return m.sha(m.canonical(value))


class Store(g.Store):
    """Exact fixture keys, including one dedicated object outside control scope."""
    def __init__(self, cfg, api, req):
        super().__init__(cfg,api,authority=n)
        self.keys={n.LEASE,n.LEDGER,cleanup.context_key(req,authority=n),*objects(req).values()}
    def url(self, key):
        m.need(key in self.keys,'fixture object scope')
        return self.base+quote(key,safe='')


class _PreparationPolicy:
    """Closed write order, bodies and generations, shared by real/offline entries."""
    def initialize(self, value, now):
        validate(value,now=now);self.value=deepcopy(value)
        self.cfg=deepcopy(value['configuration']['provider']);self.req=deepcopy(value['request'])
        self.expected=None;self.requests=[];self.stage=0;self.failed=False
        self.store=Store(self.cfg,self,self.req);self.deadline=self.clock()+300
        self.lease=n.lease(self.req,now);self.generation=0;self.baseline={};self.created_id=None
        prior=value['before']['ledger'];self.prior_generation=prior[0] if prior is not None else 0
        self.reserved=n.reserve(prior[1] if prior is not None else n.empty_ledger(),self.req,value)
        self.disk=next(r['spec'] for r in self.lease['resources'] if r['spec']['kind']=='disk' and r['spec']['node']==1 and r['spec']['purpose']=='data')
    def authorize(self, method, url, body):
        if method=='GET':
            from urllib.parse import urlsplit,parse_qsl
            parsed=urlsplit(url);base=parsed._replace(query='').geturl();pairs=parse_qsl(parsed.query,strict_parsing=True) if parsed.query else []
            query=dict(pairs);m.need(body is None and len(query)==len(pairs),'fixture read query')
            if parsed.netloc=='storage.googleapis.com':
                m.need(any(base==self.store.url(k) for k in self.store.keys),'fixture object read scope')
                m.need(not query or set(query)=={'alt','generation','ifGenerationMatch'} and query['alt']=='media' and
                       query['generation']==query['ifGenerationMatch'] and g.numeric(query['generation']),'fixture pinned read')
            else:
                provider=self.provider()
                allowed=[provider.url(self.disk)]
                if self.created_id is not None:allowed.append(provider.url(self.disk,self.created_id))
                resource=base in allowed and not query
                original=base==provider.scope(self.disk)+'/operations' and query=={'filter':'clientOperationId = "'+provider.operation_id(self.disk)+'"'}
                poll=base.startswith(provider.scope(self.disk)+'/operations/') and not query and re.fullmatch('[a-zA-Z0-9_-]{1,200}',base.rsplit('/',1)[-1])
                m.need(resource or original or poll,'fixture compute read scope')
        else:
            m.need(not self.failed and method=='POST' and self.expected==(method,url,body),'fixture unexpected mutation')
            self.expected=None
    def call(self, method, url, body=None, **kwargs):
        kwargs['deadline']=min(kwargs['deadline'],self.deadline)
        self.requests.append(dict(method=method,url=url,bodySha256=m.sha(m.canonical(body)) if body is not None else None))
        result=super().call(method,url,body,**kwargs)
        # The create response identifies the numeric GET used by Compute.create.
        if self.stage==6 and method in ('POST','GET') and isinstance(result,dict) and result.get('operationType')=='insert':
            decoded=self.provider().decode_operation(self.disk,result)
            if decoded['state']=='DONE':self.created_id=decoded['id']
        return result
    def provider(self, sleep=time.sleep):
        return g.Compute(self.cfg,self.req,self,guest_access=self.value['guestAccess'],sleep=sleep,authority=n)
    def write_step(self):
        keys=objects(self.req)
        if self.stage==0:return n.LEASE,self.lease,0
        if self.stage==1:return n.LEDGER,self.reserved,self.prior_generation
        if self.stage==2:return cleanup.context_key(self.req,authority=n),cleanup.context(self.cfg,self.req,self.value['guestAccess'],authority=n),0
        if self.stage in (3,4):
            kind='existing' if self.stage==3 else 'outside';return keys[kind],canary(self.req,kind),0
        if self.stage in (5,7):
            lease=deepcopy(self.lease);row=next(r for r in lease['resources'] if r['spec']==self.disk);row['attempted']=True
            if self.stage==7:row['id']=g.numeric(self.created_id)
            return n.LEASE,lease,self.generation
        if self.stage==8:
            return keys['manifest'],dict(schema='gse-v51-object-probe-manifest-v1',request=self.req,guestAccess=self.value['guestAccess'],
                fixtureSha256=m.sha(m.canonical(self.value)),fixtureRequest=self.value,baseline=self.baseline),0
        raise ValueError('fixture write order')
    def upload(self, key, body, generation):
        m.need(not self.failed and (key,body,generation)==self.write_step(),'fixture write order/body/generation')
        url='https://storage.googleapis.com/upload/storage/v1/b/'+self.cfg['bucket']+'/o?'+urlencode(
            dict(uploadType='media',name=key,ifGenerationMatch=generation))
        self.expected=('POST',url,deepcopy(body))
        try:result=self.store.put(key,body,generation)
        except BaseException:
            self.failed=True;raise
        if key==n.LEASE:self.lease=deepcopy(body);self.generation=result
        if self.stage in (3,4):self.baseline['existing' if self.stage==3 else 'outside']=[result,deepcopy(body)]
        self.stage+=1;return result
    def insert(self, provider, spec):
        m.need(not self.failed and self.stage==6 and spec==self.disk and provider.api is self and
               provider.req==self.req and provider.config==self.cfg,'fixture disk scope/order')
        m.need(self.store.get(n.LEASE)==(self.generation,self.lease) and self.store.get(n.LEDGER)[1]==self.reserved,
               'fixture durable intent/reservation changed')
        url=provider.url(spec).rsplit('/',1)[0]+'?'+urlencode(dict(requestId=provider.operation_id(spec)))
        self.expected=('POST',url,provider.body(spec))
        try:result=provider.create(spec,int(self.deadline*10**9))
        except BaseException:
            self.failed=True;raise
        m.need(result['id']==self.created_id,'fixture created ID mismatch')
        self.stage=7;return result


class PreparationApi(_PreparationPolicy,h.Api):
    def __init__(self, value, now, *, transport, tokens, clock):
        m.need(transport.offline is True and value['execution']=='offline-single-disk-request','fixture offline constructor')
        h.Api.__init__(self,transport=transport,tokens=tokens,clock=clock);self.initialize(value,now)


class NetworkPreparationApi(_PreparationPolicy,h.Api):
    def __init__(self, value, *, confirmation):
        self.preparation_evidence=network_checks(value,confirmation)
        def tokens(timeout):
            operator_account(value['operator'])
            result=subprocess.run(['gcloud','auth','print-access-token','--account='+value['operator']],capture_output=True,timeout=timeout)
            m.need(result.returncode==0 and result.stdout.strip(),'fixture operator credential unavailable')
            return result.stdout.decode().strip()
        h.Api.__init__(self,transport=h.Network(),tokens=tokens)
        self.initialize(value,int(time.time()))


def execute(value, api, output, *, now, sleep=time.sleep):
    """Shared once-only sequence; caller must have checked live entry authorization."""
    validate(value,now=now)
    m.need(type(api) in (PreparationApi,NetworkPreparationApi) and api.req==value['request'] and api.cfg==value['configuration']['provider'] and
           api.offline==(value['execution']=='offline-single-disk-request'),'fixture execution binding')
    root=Path(output);root.mkdir(parents=True,exist_ok=False);c.write_once(root/'request.json',value)
    receipt=dict(schema='gse-v51-single-disk-preparation-v1',status='FAIL',requestSha256=n.validate_request(api.req),
                 fixtureSha256=m.sha(m.canonical(value)),execution='offline-single-disk-preparation' if api.offline else 'gcp-single-disk-preparation',
                 startedAt=now,paidCloud=not api.offline,**BOUNDARY)
    phase='original-state'
    try:
        store=api.store;req=value['request'];keys=objects(req)
        prior=store.get(n.LEDGER)
        m.need(store.get(n.LEASE) is None and m.canonical(prior)==m.canonical(value['before']['ledger']), 'fixture state changed')
        old=prior[1] if prior is not None else n.empty_ledger()
        reserved=n.reserve(old,req,value)
        provider=g.Compute(api.cfg,req,api,guest_access=value['guestAccess'],sleep=sleep,authority=n)
        lease=deepcopy(api.lease);row=next(r for r in lease['resources'] if r['spec']['kind']=='disk' and r['spec']['node']==1 and r['spec']['purpose']=='data')
        m.need(provider.describe(row['spec']) is None and provider.operation(row['spec'])['state']=='UNKNOWN','fixture operation/resource already exists')
        for key in (*keys.values(),cleanup.context_key(req,authority=n)):
            m.need(store.get(key) is None,'fixture object already exists')
        phase='lease';generation=api.upload(n.LEASE,lease,0)
        phase='reservation';api.upload(n.LEDGER,reserved,prior[0] if prior is not None else 0)
        phase='context';api.upload(cleanup.context_key(req,authority=n),cleanup.context(api.cfg,req,value['guestAccess'],authority=n),0)
        baseline={}
        for kind in ('existing','outside'):
            phase='canary-'+kind;body=canary(req,kind);gen=api.upload(keys[kind],body,0)
            baseline[kind]=[gen,body]
        phase='intent';row['attempted']=True;generation=api.upload(n.LEASE,lease,generation)
        # Original operation is submitted once. Any uncertain response leaves the
        # attempted row and reservation intact for the existing expired reconciler.
        phase='disk';row['id']=api.insert(provider,row['spec'])['id']
        phase='retained-id';generation=api.upload(n.LEASE,lease,generation)
        phase='probe-manifest'
        manifest=dict(schema='gse-v51-object-probe-manifest-v1',request=req,guestAccess=value['guestAccess'],
                      fixtureSha256=receipt['fixtureSha256'],fixtureRequest=value,baseline=baseline)
        api.upload(keys['manifest'],manifest,0)
        receipt.update(status='PREPARED',leaseGeneration=generation,disk=deepcopy(row),probeManifest=manifest,
                       expiresAt=lease['expiresAt'],cleanupEligibleAt=lease['expiresAt']+lease['graceSeconds'],
                       reservedCostMicrousd=COST,previousCostMicrousd=value['previousCostMicrousd'])
    except (Exception,KeyboardInterrupt) as error:
        receipt['failure']=dict(phase=phase,type=type(error).__name__)
        if isinstance(error,h.ApiError):receipt['failure']['httpStatus']=error.status
    finally:
        c.write_once(root/'http.json',api.requests);c.write_once(root/'receipt.json',receipt)
    return receipt


def checkout():
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ci.ROOT,text=True).strip()
    subprocess.check_output(['git','ls-files','--error-unmatch','scripts/v51/cloud_fixture_driver.py',
                             'scripts/v51/cloud_object_probes.py'],cwd=ci.ROOT,text=True)
    m.need(not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ci.ROOT,text=True).strip(), 'fixture requires clean tracked checkout')
    return source


def operator_account(expected):
    # --account alone does not override gcloud's ambient impersonation/token
    # settings. Reject those before relying on the reviewed operator identity.
    m.need(p.principal()==expected and not os.environ.get('CLOUDSDK_AUTH_ACCESS_TOKEN'),
           'fixture operator changed or token override')
    for name in ('impersonate_service_account','credential_file_override','access_token_file'):
        result=subprocess.run(['gcloud','config','get-value','auth/'+name],capture_output=True,timeout=10)
        m.need(result.returncode==0 and result.stdout.strip() in (b'',b'(unset)'),
               'fixture operator credential override')


def network_checks(value, confirmation):
    # All gates precede the first write. Review is not an approval boolean.
    now=int(time.time());digest=validate(value,now=now);cfg=c.read(p.CONFIG)
    m.need(value['execution']=='operator-single-disk-request' and value['configuration']==cfg and
           confirmation==digest and checkout()==value['request']['source'], 'fixture exact approval/source/configuration')
    operator_account(value['operator'])
    source=value['request']['source'];github=ci.collect(source)
    ci.check(github,source,int(time.time()),(ci.ROOT/ci.WORKFLOW).read_text())
    m.need(github['configurationSha256']==p.configuration(cfg),'fixture protected configuration')
    m.need((ci.ROOT/a.CLEANUP_WORKFLOWS['workflow_dispatch']).read_text()==deployment.render(cfg,'manual'),
           'fixture manual workflow bytes')
    state=audit.collect(cfg,'staged')
    m.need(deployment.evaluate(cfg,'manual',state,now=int(time.time()))['status']=='CONFIGURATION_MATCH','fixture manual configuration drift')
    # Inspect exact approved state again, using read-only network adapters.
    current=observation.capture(cfg,source)
    observation.envelope(cfg,current)
    m.need(current['lease'] is None and m.canonical(current['ledger'])==m.canonical(value['before']['ledger']),'fixture live control changed')
    now=int(time.time());validate(value,now=now)
    return dict(github=github,manualConfiguration=state,before=current)


def network_prepare(value, output, *, confirmation):
    api=NetworkPreparationApi(value,confirmation=confirmation)
    result=execute(value,api,output,now=int(time.time()))
    c.write_once(Path(output)/'entry-evidence.json',api.preparation_evidence)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    review=sub.add_parser('review');review.add_argument('--operator',required=True);review.add_argument('--public-key',type=Path,required=True)
    review.add_argument('--prices',type=Path,required=True);review.add_argument('--output',type=Path,required=True)
    run=sub.add_parser('prepare');run.add_argument('--request',type=Path,required=True);run.add_argument('--confirm',required=True)
    run.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='review':
        source=checkout();cfg=c.read(p.CONFIG);operator_account(args.operator)
        before=observation.capture(cfg,source)
        m.need(args.public_key.is_file() and not args.public_key.is_symlink() and args.public_key.stat().st_size<=4096,'public key file')
        value=make(cfg,source,args.operator,args.public_key.read_text().strip(),c.read(args.prices),before,
                   now=int(time.time()),attempt=uuid.uuid4().hex,sequence=uuid.uuid4().hex)
        args.output.mkdir(parents=True,exist_ok=False);c.write_once(args.output/'request.json',value)
        result=dict(status='REVIEW_ONLY',fixtureSha256=validate(value,now=int(time.time())),requestSha256=n.validate_request(value['request']),
                    maximumCostMicrousd=COST,expiresAt=value['expiresAt'],applied=False,**BOUNDARY)
        c.write_once(args.output/'review.json',result)
    else:result=network_prepare(c.read(args.request),args.output,confirmation=args.confirm)
    print(m.canonical({k:result[k] for k in ('status','execution','fixtureSha256','requestSha256','maximumCostMicrousd',
        'reservedCostMicrousd','previousCostMicrousd','expiresAt','cleanupEligibleAt','failure','paidCloud') if k in result}).decode())
    if result['status'] not in ('REVIEW_ONLY','PREPARED'):raise SystemExit(2)


if __name__=='__main__':main()
