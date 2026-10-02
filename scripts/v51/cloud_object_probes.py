"""Manual-identity canary probes and independent after-state review; no readiness grant."""
import argparse
from copy import deepcopy
import html
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import quote, urlencode
from . import cloud_fixture_driver as f, cloud_native_authority as n, cloud_authority as a
from . import cloud_cleanup_entry as entry, cloud_cleanup_credentials as credentials
from . import cloud_cleanup_deployment as deployment, cloud_preflight as p, cloud_http as h
from . import cloud_gcp as g, cloud_ci as ci, performance_model as m, remote_command as c
from . import cloud_permissions as permissions

CASES=('create','read-created','read-existing','overwrite-denied','delete-denied',
       'outside-read-denied','outside-write-denied','outside-delete-denied')


def validate_manifest(value, cfg, sha, source):
    a.digest(sha);a.digest(source,40)
    m.need(type(value) is dict and set(value)=={'schema','request','guestAccess','fixtureSha256','fixtureRequest','baseline'} and
           value['schema']=='gse-v51-object-probe-manifest-v1','object probe manifest fields')
    req=value['request'];m.need(n.validate_request(req)==sha and req['source']==source and
           req['configurationSha256']==g.config(cfg['provider']),'object probe source/request/configuration')
    a.digest(value['fixtureSha256'])
    m.need(f.validate(value['fixtureRequest'],now=req['createdAt'])==value['fixtureSha256'] and
           value['fixtureRequest']['request']==req and value['fixtureRequest']['configuration']==cfg and
           value['fixtureRequest']['guestAccess']==value['guestAccess'],'object probe retained fixture binding')
    f.guest_setup.access(value['guestAccess'])
    m.need(value['guestAccess']['attempt']==req['attempt'] and
           m.sha(m.canonical(value['guestAccess']))==req['guestAccessSha256'],'object probe guest binding')
    m.need(set(value['baseline'])=={'existing','outside'},'object probe baseline inventory')
    for kind,row in value['baseline'].items():
        m.need(type(row) in (list,tuple) and len(row)==2 and row[1]==f.canary(req,kind),'object probe baseline bytes')
        a.integer(row[0],1)
    return value


def manifest_key(sha):
    a.digest(sha);return n.PREFIX+'attempts/'+sha+'/single-disk-fixture.json'


def operations(cfg, manifest):
    req=manifest['request'];keys=f.objects(req);base='https://storage.googleapis.com/storage/v1/b/'+cfg['provider']['bucket']+'/o/'
    upload='https://storage.googleapis.com/upload/storage/v1/b/'+cfg['provider']['bucket']+'/o'
    def get(key):return base+quote(keys[key],safe='')
    def put(kind):return upload+'?'+urlencode(dict(uploadType='media',name=keys[kind],ifGenerationMatch=0))
    def delete(kind):return get(kind)+'?'+urlencode(dict(ifGenerationMatch=0))
    return [('create','POST',put('created'),f.canary(req,'created'),200),
            ('read-created','GET',get('created'),None,200),
            ('read-existing','GET',get('existing'),None,200),
            ('overwrite-denied','POST',put('existing'),f.canary(req,'existing'),403),
            ('delete-denied','DELETE',delete('existing'),None,403),
            ('outside-read-denied','GET',get('outside'),None,403),
            ('outside-write-denied','POST',put('outside'),f.canary(req,'outside'),403),
            ('outside-delete-denied','DELETE',delete('outside'),None,403)]


class _Policy:
    def initialize(self, cfg, binding, sha):
        a.digest(sha);self.cfg,self.binding,self.sha=deepcopy(cfg),deepcopy(binding),sha
        self.manifest=None;self.used=set();self.expected=None
        self.read_keys={n.LEASE,n.LEDGER,manifest_key(sha)}
        self.base='https://storage.googleapis.com/storage/v1/b/'+cfg['provider']['bucket']+'/o/'
        self.deadline=self.clock()+180
    def authorize(self, method, url, body):
        if method=='GET':
            # Store reads must be exact-key metadata or generation-pinned media.
            from urllib.parse import urlsplit, parse_qsl
            parsed=urlsplit(url);base=parsed._replace(query='').geturl();pairs=parse_qsl(parsed.query,strict_parsing=True) if parsed.query else []
            query=dict(pairs)
            m.need(body is None and len(pairs)==len(query) and any(base==self.base+quote(key,safe='') for key in self.read_keys),'object probe read scope')
            m.need(not query or set(query)=={'alt','generation','ifGenerationMatch'} and query['alt']=='media' and
                   query['generation']==query['ifGenerationMatch'] and g.numeric(query['generation']),'object probe pinned read')
        else:
            m.need(self.manifest is not None and (method,url,body)==self.expected and url not in self.used,'object probe mutation scope/replay')
            # The expected request is derived from the fixed canary inventory.
            allowed=[(method_,url_,body_) for _,method_,url_,body_,_ in operations(self.cfg,self.manifest) if method_!='GET']
            m.need((method,url,body) in allowed,'object probe mutation drift')
            self.used.add(url);self.expected=None
    def bind(self, manifest):
        validate_manifest(manifest,self.cfg,self.sha,self.binding['source'])
        m.need(manifest['fixtureRequest']['execution']==('offline-single-disk-request' if self.offline else 'operator-single-disk-request'),
               'object probe fixture execution')
        m.need(self.manifest is None,'object probe rebind');self.manifest=deepcopy(manifest)
        self.read_keys.update(f.objects(manifest['request']).values())
    def call(self, method, url, body=None, **kwargs):
        kwargs['deadline']=min(kwargs['deadline'],self.deadline)
        return super().call(method,url,body,**kwargs)


class OfflineApi(_Policy,h.Api):
    def __init__(self,cfg,binding,sha,*,transport,tokens,clock):
        m.need(transport.offline is True,'object probe fixture transport')
        h.Api.__init__(self,transport=transport,tokens=tokens,clock=clock);self.initialize(cfg,binding,sha)


class NetworkApi(_Policy,h.Api):
    def __init__(self,cfg,binding,env,descriptor,sha):
        m.need(binding==entry.identity(cfg,env,trigger='manual',source=binding['source'],checkout=binding['source']), 'object probe workflow binding')
        h.Api.__init__(self,transport=h.Network(),tokens=credentials.NetworkCredentials(binding,env,descriptor))
        self.initialize(cfg,binding,sha)


def run(cfg, api, output, *, now):
    m.need(type(api) in (OfflineApi,NetworkApi) and cfg==api.cfg,'object probe client')
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema='gse-v51-object-probe-receipt-v1',binding=api.binding,requestSha256=api.sha,
                 status='FAIL',startedAt=now,execution='offline-object-probes' if api.offline else 'manual-identity-object-probes',
                 cases=[],**f.BOUNDARY)
    phase='retained-fixture'
    try:
        store=g.Store(cfg['provider'],api,authority=n);original=store.get(manifest_key(api.sha))
        m.need(original is not None,'object probe manifest missing');manifest=validate_manifest(original[1],cfg,api.sha,api.binding['source'])
        api.bind(manifest);store=f.Store(cfg['provider'],api,manifest['request'])
        lease=store.get(n.LEASE);ledger=store.get(n.LEDGER)
        m.need(lease is not None and ledger is not None,'object probe retained authority missing')
        n.validate_lease(lease[1]);_,attempts=n.inspect_ledger(ledger[1])
        rows=[r for r in lease[1]['resources'] if r['attempted']]
        m.need(lease[1]['request']==manifest['request'] and now<lease[1]['expiresAt'] and len(rows)==1 and
               rows[0]['id'] is not None and (rows[0]['spec']['kind'],rows[0]['spec']['node'],rows[0]['spec']['purpose'])==('disk',1,'data') and
               api.sha in attempts and attempts[api.sha]['status']=='PENDING','object probe needs active prepared disk')
        keys=f.objects(manifest['request']);existing=store.get(keys['existing'])
        m.need(m.canonical(existing)==m.canonical(manifest['baseline']['existing']) and store.get(keys['created']) is None,'object probe canary already used/changed')
        receipt.update(manifest=manifest,manifestGeneration=original[0],leaseGeneration=lease[0])
        c.write_once(root/'manifest.json',manifest)
        for name,method,url,body,expected in operations(cfg,manifest):
            phase=name;api.expected=(method,url,deepcopy(body));status=200
            try:
                if name in ('read-created','read-existing'):
                    kind=name.removeprefix('read-');value=store.get(keys[kind])
                    m.need(value is not None and value[1]==f.canary(manifest['request'],kind),'object probe positive read bytes')
                    if kind=='existing':m.need(m.canonical(value)==m.canonical(existing),'object probe existing generation')
                    else:receipt['created']=list(value)
                else:api.call(method,url,body,deadline=api.deadline,maximum=64<<10)
            except h.ApiError as error:status=error.status
            receipt['cases'].append(dict(case=name,httpStatus=status,expected=expected,status='PASS' if status==expected else 'FAIL'))
            m.need(status==expected,'object probe inconclusive/unexpected response')
        m.need(store.get(keys['existing'])==existing and store.get(n.LEASE)==lease and store.get(n.LEDGER)==ledger and
               store.get(keys['manifest'])==original,'object probe changed retained state')
        receipt['status']='PROBES_RECORDED'  # Outside bytes require the independent reader below.
    except (Exception,KeyboardInterrupt) as error:
        receipt['failure']=dict(phase=phase,type=type(error).__name__)
        if isinstance(error,h.ApiError):receipt['failure']['httpStatus']=error.status
    receipt['credentialExchangeCompleted']=getattr(api.tokens,'exchanges',0)>0
    c.write_once(root/'receipt.json',receipt);(root/'summary.md').write_text(summary(receipt));return receipt


def capture(cfg, manifest, *, api=None, wall=time.time):
    req=manifest['request'];sha=n.validate_request(req);validate_manifest(manifest,cfg,sha,req['source'])
    api=f.observation.Reads(api if api is not None else h.Api());store=f.Store(cfg['provider'],api,req);started=int(wall())
    # GET-only generic API, independent of the manual identity and probe process.
    values={kind:store.get(key) for kind,key in f.objects(req).items()}
    m.need(values=={kind:store.get(key) for kind,key in f.objects(req).items()},'object probe after-state changed')
    m.need(api.clock()<=api.deadline,'object probe observation deadline')
    return dict(schema='gse-v51-object-probe-observation-v1',requestSha256=sha,startedAt=started,completedAt=int(wall()),
                execution='offline-object-observation' if api.offline else 'read-only-object-observation',objects=values)


def review(cfg, receipt, after):
    manifest=receipt['manifest'];req=manifest['request'];sha=n.validate_request(req)
    validate_manifest(manifest,cfg,sha,receipt['binding']['source'])
    binding=receipt['binding'];selected=entry.identities.proposal(cfg)['identities']['manual']
    a.integer(binding['runId'],1,10**20-1);a.integer(binding['runAttempt'],1,10**20-1)
    env=dict(GITHUB_ACTIONS='true',GITHUB_REPOSITORY=ci.REPOSITORY,GITHUB_REPOSITORY_ID=str(ci.REPOSITORY_ID),
             GITHUB_REPOSITORY_OWNER_ID=str(ci.OWNER_ID),GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_REF='refs/heads/master',
             GITHUB_WORKFLOW_REF=selected['claims']['workflow_ref'],GITHUB_WORKFLOW_SHA=req['source'],GITHUB_SHA=req['source'],
             GITHUB_JOB='cleanup',CLEANUP_ENVIRONMENT=selected['environment'],
             GITHUB_RUN_ID=str(binding['runId']),GITHUB_RUN_ATTEMPT=str(binding['runAttempt']))
    m.need(binding==entry.identity(cfg,env,trigger='manual',source=req['source'],checkout=req['source']),
           'object probe recorded identity drift')
    for value in (receipt['startedAt'],after['startedAt'],after['completedAt'],receipt['manifestGeneration']):a.integer(value,1)
    m.need(receipt['schema']=='gse-v51-object-probe-receipt-v1' and all(receipt[k] is False for k in f.BOUNDARY) and
           receipt['execution'] in ('offline-object-probes','manual-identity-object-probes') and
           receipt['status']=='PROBES_RECORDED' and receipt['requestSha256']==sha and
           after['schema']=='gse-v51-object-probe-observation-v1' and after['requestSha256']==sha and
           req['createdAt']<=receipt['startedAt']<=after['startedAt']<=after['completedAt'],'object probe review binding/time')
    m.need(after['completedAt']-after['startedAt']<=180,'object probe observation time')
    expected=[dict(case=name,httpStatus=status,expected=status,status='PASS') for name,_,_,_,status in operations(cfg,manifest)]
    m.need(receipt['cases']==expected,'object probe case inventory/outcomes')
    created=receipt['created'];m.need(type(created) in (list,tuple) and len(created)==2 and
                                   created[1]==f.canary(req,'created'),'object probe created bytes')
    a.integer(created[0],1)
    wanted=dict(manifest=[receipt['manifestGeneration'],manifest],created=receipt['created'],**manifest['baseline'])
    m.need(m.canonical(after['objects'])==m.canonical(wanted),'object probe independent bytes/generations changed')
    live=receipt['execution']=='manual-identity-object-probes'
    m.need(manifest['fixtureRequest']['execution']==('operator-single-disk-request' if live else 'offline-single-disk-request'),
           'object probe review fixture execution')
    m.need(after['execution']==('read-only-object-observation' if live else 'offline-object-observation'),'object probe observation execution')
    m.need(not live or receipt['credentialExchangeCompleted'] is True,'object probe actual credential exchange absent')
    return dict(status='OBJECT_SCOPE_MATCH',execution='object-probe-state-review',requestSha256=sha,
                workflowIdentityClaimRecorded=live,artifactProvenanceVerified=False,providerAuditVerified=False,**f.BOUNDARY)


def summary(receipt):
    def safe(value):return html.escape(str(value)).replace('|','&#124;').replace('\n',' ')
    rows=[('Status',receipt['status']),('Request',receipt['requestSha256']),('Execution',receipt['execution'])]
    rows.extend((key,receipt['binding'].get(key,'')) for key in ('source','runId','runAttempt','serviceAccount'))
    return '# V5.1 object permission probes\n\n| Parameter | Value |\n| --- | --- |\n'+''.join('| '+safe(k)+' | '+safe(v)+' |\n' for k,v in rows)+\
        '\n| Case | HTTP status | Result |\n| --- | --- | --- |\n'+''.join('| '+safe(r['case'])+' | '+str(r['httpStatus'])+' | '+r['status']+' |\n' for r in receipt['cases'])+\
        '\nIndependent canary generation/byte review and GitHub/provider provenance remain required. This does not establish cleanup readiness.\n'


def workflow(cfg):
    return deployment.render(cfg,'manual')


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    run_parser=sub.add_parser('run');run_parser.add_argument('--request',required=True);run_parser.add_argument('--source',required=True)
    run_parser.add_argument('--output',type=Path,required=True)
    observe=sub.add_parser('observe');observe.add_argument('--manifest',type=Path,required=True);observe.add_argument('--output',type=Path,required=True)
    check=sub.add_parser('review');check.add_argument('--receipt',type=Path,required=True);check.add_argument('--after',type=Path,required=True);check.add_argument('--output',type=Path,required=True)
    proposed=sub.add_parser('workflow-review');proposed.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();cfg=c.read(p.CONFIG)
    if args.command=='run':
        checkout=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ci.ROOT,text=True).strip()
        binding=entry.identity(cfg,os.environ,trigger='manual',source=args.source,checkout=checkout)
        m.need(args.request==os.environ.get('OBJECT_PROBE_REQUEST') and
               (ci.ROOT/binding['workflow']).read_text()==workflow(cfg),'object probe dispatch/workflow bytes')
        observation=entry.collect_run(binding)
        permission_binding=permissions.identity(cfg,os.environ,role='manual',source=args.source,checkout=checkout)
        permissions.check_saved(cfg,permission_binding,args.output.parent/'permissions',now=int(time.time()))
        api=NetworkApi(cfg,binding,os.environ,entry.credential_file(os.environ),args.request)
        result=run(cfg,api,args.output,now=int(time.time()));c.write_once(args.output/'run.json',observation)
    elif args.command=='workflow-review':
        m.need('.github' not in args.output.resolve().parts,'object probe review workflow destination')
        args.output.mkdir(parents=True,exist_ok=False);raw=workflow(cfg).encode()
        (args.output/'v51-manual-cleanup.yml').write_bytes(raw)
        result=dict(status='REVIEW_ONLY',workflowSha256=m.sha(raw),deployed=False,**f.BOUNDARY)
        c.write_once(args.output/'review.json',result)
    else:
        result=capture(cfg,c.read(args.manifest)) if args.command=='observe' else review(cfg,c.read(args.receipt),c.read(args.after))
        args.output.mkdir(parents=True,exist_ok=False);c.write_once(args.output/'receipt.json',result)
    print(m.canonical(dict(status=result.get('status','OBSERVED'),output=str(args.output),
        **{k:result[k] for k in ('execution','requestSha256','workflowSha256','failure') if k in result})).decode())
    if result.get('status')=='FAIL':raise SystemExit(2)


if __name__=='__main__':main()
