"""Closed V5.2 request-scoped HTTP policy, exercised through real control calls.

Concrete entries are offline and factory-owned native cleanup. This policy cannot
supply deployment, CI, provisioning or paid-workload admission proof.
"""
from copy import deepcopy
import math
import re
import threading
import urllib.parse as url
import uuid
from scripts.v51 import cloud_http as h
from . import cloud_authority as a, cloud_provider as p, cloud_read_retry
from .evidence import need, encoded, digest, strict


class Policy:
    def __init__(self, configuration, request, *, role, previous_cost, cost, wall):
        need(role in ('runner','cleanup'), 'V5.2 wire role')
        self.plan=p.Plan(configuration,request);self.req=self.plan.request;self.cfg=self.plan.config
        self.domain=a.domain(request);self.sha=a.validate_request(request,domain=self.domain,historical=role=='cleanup')
        self.role,self.wall=role,wall;self.previous_cost,self.cost=previous_cost,cost
        if role=='runner':a.integer(previous_cost);a.integer(cost,1)
        else:need(previous_cost is None and cost is None,'V5.2 cleanup cannot reserve')
        self.prefix=a.PREFIX+'attempts/'+self.sha+'/'
        self.objects=p.STORAGE+'storage/v1/b/'+self.cfg['bucket']+'/o/'
        self.upload=p.STORAGE+'upload/storage/v1/b/'+self.cfg['bucket']+'/o'
        self.store=None;self.metadata={};self.ids={};self.polls={};self.pages={}
        self.evidence_manifest=None;self.retained=None
        self.completed={};self.resolved={};self.absent=set();self.marker_tickets=set();self.sent=set()
        self.submitter=uuid.uuid4().hex;self.dispatched=set()
        self.cleanup={};self.empty_operations=set();self.list_seen={};self.page_seen={};self.seen_operations=set();self.targets={}
        self.operation_keys={self.prefix+'operations/'+s['operationId']:s for s in self.plan.specs.values()}

    def object(self,key):
        if key in (a.LEASE,a.LEDGER):return key,None
        if key==self.prefix+'provider-context.json':return 'context',None
        if key==self.prefix+'completion.json':return 'completion',None
        if key==self.prefix+'evidence/manifest.json':return 'evidence-manifest',None
        part=re.fullmatch(re.escape(self.prefix)+r'evidence/chunk-([0-9]{5})\.json',key)
        if part:
            from . import cloud_evidence_parts as evidence
            index=int(part[1]);need(index<evidence.MAX_PARTS,'V5.2 evidence part key bound')
            return 'evidence-part',index
        if re.fullmatch(re.escape(self.prefix)+r'cleanup-[1-9][0-9]{0,19}\.json',key):return 'cleanup',None
        cleanup=re.fullmatch(re.escape(self.prefix)+r'cleanups/([0-9a-f]{64})\.json',key)
        if cleanup:return 'cleanup',cleanup[1]
        for base,spec in self.operation_keys.items():
            for suffix,kind in (('.json','operation'),('-submitted.json','submitted'),('-unsubmitted.json','unsubmitted')):
                if key==base+suffix:return kind,spec
        raise ValueError('V5.2 wire object outside original request')

    def route(self,method,endpoint,body):
        need(method in ('GET','POST','DELETE') and type(endpoint) is str and len(endpoint)<=8192,'V5.2 wire method/URL')
        parsed=url.urlsplit(endpoint)
        need(parsed.scheme=='https' and parsed.netloc in ('compute.googleapis.com','storage.googleapis.com') and
             not parsed.fragment and parsed.netloc==parsed.hostname,'V5.2 wire endpoint')
        pairs=url.parse_qsl(parsed.query,keep_blank_values=True,strict_parsing=True) if parsed.query else []
        q=dict(pairs);need(len(pairs)==len(q),'V5.2 wire duplicate query')
        base=parsed._replace(query='').geturl()
        need(method=='POST' or body is None,'V5.2 wire read/delete body')
        if parsed.netloc=='storage.googleapis.com':
            if method=='POST':
                need(base==self.upload and set(q)=={'uploadType','name','ifGenerationMatch'} and q['uploadType']=='media',
                     'V5.2 wire upload endpoint')
                key=q['name'];kind,spec=self.object(key)
                expected=q['ifGenerationMatch']
                need(re.fullmatch('0|[1-9][0-9]{0,19}',expected),'V5.2 wire upload generation')
                need(type(body) is dict and len(encoded(body))<=p.MAX_OBJECT,'V5.2 wire control body')
                return dict(kind=kind,spec=spec,key=key,expected=int(expected),operation='put')
            need(base.startswith(self.objects),'V5.2 wire bucket')
            key=url.unquote(base[len(self.objects):]);kind,spec=self.object(key)
            need(base==self.objects+url.quote(key,safe=''),'V5.2 wire object encoding')
            if method=='DELETE':
                need(key==a.LEASE and set(q)=={'ifGenerationMatch'},'V5.2 wire object deletion')
                return dict(kind=kind,spec=spec,key=key,expected=int(a.numeric(q['ifGenerationMatch'])),operation='release')
            if not q:return dict(kind=kind,spec=spec,key=key,operation='metadata')
            need(set(q)=={'alt','generation','ifGenerationMatch'} and q['alt']=='media' and
                 q['generation']==q['ifGenerationMatch'],'V5.2 wire pinned media')
            generation=int(a.numeric(q['generation']));meta=self.metadata.get(key)
            p.read_need(meta is not None and meta['generation']==q['generation'],'V52_CONTROL_READ_GENERATION')
            return dict(kind=kind,spec=spec,key=key,expected=generation,operation='media')
        image=p.COMPUTE+self.cfg['imageProject']+'/global/images/'+self.cfg['imageName']
        if base==image:
            need(method=='GET' and not q,'V5.2 wire image scope');return dict(operation='image')
        for spec in self.plan.specs.values():
            resource=self.plan.endpoint(spec);scope=self.plan.scope(spec);name=spec['name']
            if base==scope+'/operations' and method=='GET':
                if q.get('filter')!='clientOperationId = "'+self.plan.operation_id(spec)+'"':continue
                need(set(q) in ({'filter','maxResults'},{'filter','maxResults','pageToken'}) and q['maxResults']=='100',
                     'V5.2 wire operation query')
                if 'pageToken' in q:need(q['pageToken']==self.pages.get(name),'V5.2 wire unobserved page token')
                return dict(operation='list',spec=spec,page=q.get('pageToken'))
            if base==resource+'/getGuestAttributes':
                need(spec['kind']=='instance' and method=='GET' and q=={'queryPath':'hostkeys/'} and self.role=='runner',
                     'V5.2 wire guest-attribute scope')
                return dict(operation='host-key',spec=spec)
            if base==resource and method=='GET':
                need(not q,'V5.2 wire named resource query');return dict(operation='resource',spec=spec,identity=None)
            if method=='POST' and base==resource.rsplit('/',1)[0] and type(body) is dict and body.get('name')==name:
                need(self.role=='runner' and q=={'requestId':self.plan.operation_id(spec)} and body==self.plan.body(spec),
                     'V5.2 wire original insert/body')
                return dict(operation='insert',spec=spec)
            for identity in self.ids.get(name,set()):
                if base!=self.plan.endpoint(spec,identity):continue
                if method=='GET':
                    need(not q,'V5.2 wire numeric resource query');return dict(operation='resource',spec=spec,identity=identity)
                need(method=='DELETE' and q=={'requestId':self.plan.operation_id(spec,'delete',identity)},'V5.2 wire exact-ID delete')
                return dict(operation='delete',spec=spec,identity=identity)
        if base in self.polls:
            need(method=='GET' and not q,'V5.2 wire operation poll')
            return dict(operation='poll',name=base.rsplit('/',1)[1],**self.polls[base])
        raise ValueError('V5.2 wire call outside original resources/operations')

    def current(self, *, active=False, charged=False):
        need(self.store is not None,'V5.2 wire store not connected')
        observed=self.store.get(a.LEASE)
        need(observed is not None,'V5.2 wire original lease missing')
        generation,lease=observed;a.validate_lease(lease)
        need(lease['request']==self.req,'V5.2 wire original owner changed')
        if active:need(lease['phase']=='ACTIVE' and lease['renewedAt']<=self.wall()<lease['expiresAt'],'V5.2 wire owner inactive/expired')
        if charged:
            ledger=self.store.get(a.LEDGER)
            row=a.inspect_ledger(ledger[1],domain=self.domain)['attempts'].get(self.sha) if ledger else None
            need(row is not None and row['request']==self.req and row['status']=='PENDING','V5.2 wire original charge missing')
        return generation,lease

    def row(self,lease,spec):return next(r for r in lease['resources'] if r['spec']==spec)
    def context(self):return dict(schema='gse-v52-provider-context-v1',requestSha256=self.sha,request=self.req,configuration=self.cfg)
    def original(self,kind,spec):
        if kind=='submitted':return dict(schema='gse-v52-provider-submission-v2',spec=spec,submitter=self.submitter)
        return dict(schema='gse-v52-provider-not-submitted-v1',spec=spec)

    def marker(self,kind,value,spec):
        if kind=='submitted' and type(value) is dict and value.get('schema')=='gse-v52-provider-submission-v2':
            a.fields(value,'schema spec submitter','submission marker');a.hex_value(value['submitter'],32)
            need(value['spec']==spec,'V5.2 wire marker intent changed');return
        schema='gse-v52-provider-submission-v1' if kind=='submitted' else 'gse-v52-provider-not-submitted-v1'
        need(value==dict(schema=schema,spec=spec),'V5.2 wire retained marker changed')

    def can_prove_unsubmitted(self,spec,value):
        # Only this original process knows it never called the provider transport.
        # A new process cannot acquire this fact by copying the public marker.
        return (spec['name'] in self.marker_tickets and spec['name'] not in self.dispatched and
                value==self.original('submitted',spec))

    def validate_lease_write(self,body,expected):
        a.validate_lease(body);need(body['request']==self.req,'V5.2 wire lease request changed')
        now=int(self.wall());old=self.store.get(a.LEASE)
        if old is None:
            need(self.role=='runner' and expected==0 and body==a.lease(self.req,body['startedAt']) and
                 body['startedAt']<=now<body['expiresAt'],'V5.2 wire initial lease')
            ledger=self.store.get(a.LEDGER);ledger=ledger[1] if ledger else a.empty_ledger(domain=self.domain)
            a.reserve(ledger,self.req,previous_cost=self.previous_cost,cost=self.cost)
            context=self.store.get(self.prefix+'provider-context.json')
            need(context is not None and context[1]==self.context(),'V5.2 initial lease requires retained context')
            return
        generation,previous=old;a.validate_lease(previous)
        need(generation==expected and previous['request']==self.req,'V5.2 wire lease generation/owner changed')
        same=deepcopy(previous);same['phase']='CLEANING'
        if body==same:
            need(self.role=='runner' or previous['phase']=='CLEANING' or now>=previous['expiresAt']+previous['graceSeconds'],
                 'V5.2 wire cleanup before expiry/grace')
            return
        if previous['phase']=='ACQUIRING':
            need(self.role=='runner','V5.2 wire cleanup activation')
            self.current(charged=True);same=deepcopy(previous);same['phase']='ACTIVE'
            need(body==same,'V5.2 wire initial activation');return
        if previous['phase']=='ACTIVE':
            need(self.role=='runner','V5.2 wire cleanup cannot renew/provision');self.current(active=True,charged=True)
            if body['renewedAt']!=previous['renewedAt']:
                need(body['renewedAt']<=now and body==a.renew(previous,body['renewedAt']),'V5.2 wire invalid renewal');return
        need(previous['phase']==body['phase'] and all(body[k]==v for k,v in previous.items() if k!='resources'),
             'V5.2 wire lease transition')
        changes=0
        for index,(oldrow,newrow) in enumerate(zip(previous['resources'],body['resources'])):
            if oldrow==newrow:continue
            changes+=1;spec=oldrow['spec'];name=spec['name']
            if previous['phase']=='ACTIVE' and not oldrow['attempted']:
                need(newrow==dict(oldrow,attempted=True) and name not in self.sent and
                     all(r['id'] is not None for r in previous['resources'][:index]),'V5.2 wire retained intent changed')
            else:
                need(oldrow['attempted'] and name in self.resolved and oldrow['id'] in (None,self.resolved[name]) and
                     newrow==dict(oldrow,id=self.resolved[name]),'V5.2 wire unproven resource ID')
        need(changes<=1,'V5.2 wire multiple lease transitions')

    def cleanup_value(self,value):
        a.fields(value,'status checks errors leftovers','cleanup receipt')
        _,lease=self.current();need(lease['phase']=='CLEANING','V5.2 wire cleanup phase')
        rows=sorted((r for r in lease['resources'] if r['attempted']),key=lambda r:{'instance':0,'disk':1,'firewall':2}[r['spec']['kind']])
        need(type(value['checks']) is list and len(value['checks'])==len(rows) and type(value['errors']) is list,
             'V5.2 wire cleanup inventory')
        for check,row in zip(value['checks'],rows):
            need(type(check) is dict and set(check) in ({'name','expectedId','absent','observed'},{'name','expectedId','absent'}) and
                 check['name']==row['spec']['name'] and check['expectedId']==row['id'] and type(check['absent']) is bool,
                 'V5.2 wire cleanup check')
            if check['absent']:
                name=check['name'];need(name in self.absent and name in self.resolved and self.resolved[name]==row['id'] and
                                       check.get('observed') is None,'V5.2 wire unobserved absence')
            if check.get('observed') is not None:
                a.fields(check['observed'],'spec id','cleanup observation')
                need(check['observed']['spec']==row['spec'],'V5.2 wire foreign cleanup observation')
                a.numeric(check['observed']['id'])
        for error in value['errors']:
            a.fields(error,'phase type','redacted cleanup error')
            need(error['phase'] in {prefix+r['spec']['name'] for prefix in ('delete:','absence:') for r in rows} and
                 type(error['type']) is str and re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,99}',error['type']), 'V5.2 wire cleanup error')
        need(value['leftovers']==[r['name'] for r in value['checks'] if not r['absent']] and
             value['status']==('PASS' if not value['errors'] and not value['leftovers'] else 'FAIL'),'V5.2 wire cleanup result')

    def before(self,route,body):
        operation=route['operation']
        if operation=='list':
            name=route['spec']['name']
            if route['page'] is None:
                self.empty_operations.discard(name);self.list_seen[name]=0;self.page_seen[name]=set();self.pages.pop(name,None)
            return
        if operation in ('metadata','media','image','resource','poll'):return
        if operation=='host-key':
            _,lease=self.current(active=True,charged=True);row=self.row(lease,route['spec'])
            need(row['id'] is not None,'V5.2 wire host key before allocation');return
        if operation=='put':
            kind,spec,key,expected=(route[k] for k in ('kind','spec','key','expected'))
            if kind==a.LEASE:self.validate_lease_write(body,expected);return
            if kind==a.LEDGER:
                old=self.store.get(a.LEDGER);generation,ledger=old if old else (0,a.empty_ledger(domain=self.domain))
                need(expected==generation,'V5.2 wire ledger generation changed');_,lease=self.current()
                if lease['phase']=='ACQUIRING':
                    need(self.role=='runner' and body==a.reserve(ledger,self.req,previous_cost=self.previous_cost,cost=self.cost),
                         'V5.2 wire exact reservation')
                else:
                    retained=self.store.get(self.prefix+'completion.json')
                    need(lease['phase']=='CLEANING' and retained is not None and body==a.finish(ledger,self.req,retained[1]),
                         'V5.2 wire terminal ledger')
                return
            need(expected==0,'V5.2 wire immutable overwrite')
            if kind=='context':
                need(self.role=='runner' and body==self.context(),'V5.2 wire context changed')
                current=self.store.get(a.LEASE)
                if current is None:
                    old=self.store.get(a.LEDGER);ledger=old[1] if old else a.empty_ledger(domain=self.domain)
                    a.reserve(ledger,self.req,previous_cost=self.previous_cost,cost=self.cost)
                else:self.current(active=True,charged=True)
                return
            _,lease=self.current()
            if kind=='submitted':
                need(self.role=='runner' and body==self.original(kind,spec),'V5.2 wire submission marker')
                _,lease=self.current(active=True,charged=True);row=self.row(lease,spec)
                need(row['attempted'] and row['id'] is None and spec['name'] not in self.marker_tickets,'V5.2 wire duplicate submission marker')
                retained=self.store.get(self.prefix+'provider-context.json')
                need(retained is not None and retained[1]==self.context(),'V5.2 wire missing original context')
                need(self.store.get(key) is None,'V5.2 wire original submission marker exists')
                self.marker_tickets.add(spec['name'])
            elif kind=='operation':
                need(lease['phase'] in ('ACTIVE','CLEANING') and self.row(lease,spec)['attempted'] and
                     body==self.completed.get(spec['name']),'V5.2 wire operation receipt not observed')
            elif kind=='unsubmitted':
                marker=key.replace('-unsubmitted.json','-submitted.json')
                submission=self.store.get(marker)
                need(lease['phase']=='CLEANING' and self.row(lease,spec)['attempted'] and
                     body==self.original(kind,spec) and spec['name'] in self.empty_operations and
                     (submission is None or self.can_prove_unsubmitted(spec,submission[1])),
                     'V5.2 wire unsubmitted proof not observed')
                retained=self.store.get(self.prefix+'provider-context.json')
                need(retained is not None and retained[1]==self.context(),'V5.2 wire missing original context')
            elif kind in ('evidence-manifest','evidence-part'):
                from . import cloud_evidence_parts as evidence
                need(self.role=='runner','V5.2 cleanup cannot publish member evidence')
                self.current(active=True,charged=True)
                if kind=='evidence-manifest':evidence.validate(body,self.req)
                else:
                    need(self.evidence_manifest is not None,'V5.2 evidence original manifest missing')
                    evidence.decode(body,self.evidence_manifest,spec)
            elif kind=='cleanup':
                need(spec is None or spec==digest(encoded(body)),'V5.2 wire cleanup content address')
                self.cleanup_value(body)
            elif kind=='completion':
                a.validate_completion(body,self.req)
                need(lease['phase']=='CLEANING' and body['cleanupSha256'] in self.cleanup,
                     'V5.2 wire completion without retained cleanup')
                if body['status']=='FAIL':need(body['evidenceSha256'] is None,'V5.2 failed completion evidence claim')
                else:
                    from . import cloud_retention as evidence
                    need(self.role=='runner' and type(self.retained) is evidence.Retained and
                         self.cleanup[body['cleanupSha256']]['status']=='PASS' and
                         body==self.retained.completion(self.store.api,self.req,body['cleanupSha256']),
                         'V5.2 wire PASS requires original qualified retention and cleanup')
                    need(self.store.get(self.prefix+'evidence/manifest.json')==
                         (self.retained.generations['manifest'],self.retained.manifest),
                         'V5.2 wire original retained manifest changed')
            return
        _,lease=self.current(active=operation=='insert',charged=operation=='insert')
        if operation=='release':
            need(lease['phase']=='CLEANING' and self.store.get(a.LEASE)[0]==route['expected'],'V5.2 wire release fence')
            retained=self.store.get(self.prefix+'completion.json');ledger=self.store.get(a.LEDGER)
            need(retained is not None,'V5.2 wire release completion missing')
            if ledger:
                row=a.inspect_ledger(ledger[1],domain=self.domain)['attempts'].get(self.sha)
                need(row is None or row['status']!='PENDING','V5.2 wire release pending ledger')
            # Cached absence is not a release capability. Observe the final names
            # again under the same bounded exchange, without deleting by name.
            for row in lease['resources']:
                if not row['attempted']:continue
                try:self.store.api.call('GET',self.plan.endpoint(row['spec']),deadline=self.store.api.deadline)
                except h.ApiError as error:
                    if error.status!=404:raise
            need(all(r['spec']['name'] in self.absent and self.resolved.get(r['spec']['name'],'UNKNOWN')==r['id']
                     for r in lease['resources'] if r['attempted']),'V5.2 wire release without resolved absence')
            return
        spec=route['spec'];name=spec['name'];row=self.row(lease,spec)
        if operation=='insert':
            need(self.role=='runner' and row['attempted'] and row['id'] is None and name in self.marker_tickets and
                 name not in self.sent,'V5.2 wire insert without original submission')
            marker=self.store.get(self.prefix+'operations/'+spec['operationId']+'-submitted.json')
            need(marker is not None and marker[1]==self.original('submitted',spec),'V5.2 wire submission not retained')
            if spec['kind']=='disk' and spec['purpose']=='boot':
                image=self.store.api.call('GET',self.plan.body(spec)['sourceImage'],deadline=self.store.api.deadline)
                need(image.get('id')==self.cfg['imageId'] and image.get('name')==self.cfg['imageName'] and
                     image.get('status')=='READY' and image.get('deprecated',{}).get('state') in (None,'DEPRECATED'),
                     'V5.2 wire pinned image changed')
            _,latest=self.current(active=True,charged=True)
            need(self.row(latest,spec)==row,'V5.2 wire insertion intent changed during checks')
            # Consume before transport, including uncertain responses. A new API
            # instance cannot recreate a ticket from an old retained marker.
            self.sent.add(name);self.absent.discard(name);self.empty_operations.discard(name);return
        need(operation=='delete' and lease['phase']=='CLEANING' and row['attempted'] and row['id']==route['identity'] and
             self.resolved.get(name)==row['id'],'V5.2 wire delete original identity/phase')
        try:self.store.api.call('GET',self.plan.endpoint(spec,route['identity']),deadline=self.store.api.deadline)
        except h.ApiError as error:
            if error.status!=404:raise
        _,latest=self.current()
        need(latest['phase']=='CLEANING' and self.row(latest,spec)==row,'V5.2 wire deletion owner changed during checks')
        self.absent.discard(name)

    def observe_operation(self,spec,value,action='insert',identity=None):
        result=self.plan.decode(spec,value,action,identity)
        endpoint=self.plan.scope(spec)+'/operations/'+value['name']
        binding=dict(spec=spec,action=action,identity=identity)
        need(endpoint not in self.polls or self.polls[endpoint]==binding,'V5.2 wire operation name rebound')
        self.polls[endpoint]=deepcopy(binding)
        if action=='insert':
            name=spec['name'];self.seen_operations.add(name);self.empty_operations.discard(name)
            target=value.get('targetId')
            if target is not None:
                need(name not in self.targets or self.targets[name]==target,'V5.2 wire original operation target changed')
                self.targets[name]=target
            if result['state']=='DONE':
                need(name not in self.targets or self.targets[name]==result['id'],'V5.2 wire original operation target lost')
        if result['state']=='DONE' and action=='insert':
            name=spec['name'];known=self.resolved.get(name,'UNKNOWN')
            need(known in ('UNKNOWN',result['id']),'V5.2 wire original operation ID changed')
            self.resolved[name]=result['id']
            if result['id'] is not None:self.ids.setdefault(name,set()).add(result['id'])
            op={k:value[k] for k in ('name','clientOperationId','operationType','targetLink','status','targetId') if k in value}
            if value.get('error'):op['error']=True
            self.completed[name]=dict(schema='gse-v52-provider-operation-v1',spec=spec,operation=op)

    def observe(self,route,status,raw):
        operation=route['operation'];key=route.get('key');spec=route.get('spec')
        if status==404:
            if operation=='metadata':self.metadata.pop(key,None)
            if operation=='resource' and route['identity'] is None:self.absent.add(spec['name'])
            return
        if not 200<=status<300:return
        if operation in ('release','host-key','image'):return
        value=strict(raw) if raw else {}
        if operation in ('metadata','put'):
            need(type(value) is dict and value.get('bucket')==self.cfg['bucket'] and value.get('name')==key,
                 'V5.2 wire object response identity')
            a.numeric(value.get('generation'));size=value.get('size')
            need(type(size) is str and re.fullmatch('0|[1-9][0-9]{0,7}',size) and int(size)<=p.MAX_OBJECT and
                 value.get('contentType')=='application/json','V5.2 wire object metadata bounds/type')
            self.metadata[key]=deepcopy(value);return
        if operation=='media':
            p.read_need(len(raw)==int(self.metadata[key]['size']),'V52_CONTROL_READ_TRUNCATED')
            kind=route['kind']
            if kind==a.LEASE:
                a.validate_lease(value)
                if value['request']==self.req:
                    for row in value['resources']:
                        if row['id'] is not None:self.ids.setdefault(row['spec']['name'],set()).add(row['id'])
            elif kind==a.LEDGER:a.inspect_ledger(value,domain=self.domain)
            elif kind=='context':need(value==self.context(),'V5.2 wire retained context changed')
            elif kind=='operation':
                a.fields(value,'schema spec operation','operation receipt')
                need(value['schema']=='gse-v52-provider-operation-v1' and value['spec']==spec,'V5.2 wire retained operation changed')
                need(self.plan.decode(spec,value['operation'])['state']=='DONE','V5.2 wire retained incomplete operation')
                self.observe_operation(spec,value['operation'])
            elif kind in ('submitted','unsubmitted'):
                self.marker(kind,value,spec)
                if kind=='unsubmitted':self.resolved[spec['name']]=None
            elif kind=='cleanup':
                # Strict shape here; fresh absence is required again before any
                # new PASS retention or release, never inferred from this receipt.
                a.fields(value,'status checks errors leftovers','retained cleanup')
                need(spec is None or spec==digest(encoded(value)),'V5.2 wire cleanup content address')
                self.cleanup[digest(encoded(value))]=deepcopy(value)
            elif kind=='evidence-manifest':
                from . import cloud_evidence_parts as evidence
                evidence.validate(value,self.req);self.evidence_manifest=deepcopy(value)
            elif kind=='evidence-part':
                from . import cloud_evidence_parts as evidence
                need(self.evidence_manifest is not None,'V5.2 evidence original manifest missing')
                evidence.decode(value,self.evidence_manifest,spec)
            elif kind=='completion':a.validate_completion(value,self.req)
            return
        if operation=='resource':
            observed=self.plan.inspect(spec,value)
            need(route['identity'] is None or observed['id']==route['identity'],'V5.2 wire numeric resource changed')
            self.absent.discard(spec['name']);return
        if operation=='list':
            need(type(value) is dict and type(value.get('items',[])) is list and len(value.get('items',[]))<=1,'V5.2 wire operation list')
            name=spec['name'];self.list_seen[name]+=len(value.get('items',[]))
            need(self.list_seen[name]<=1,'V5.2 wire multiple original operations')
            for op in value.get('items',[]):self.observe_operation(spec,op)
            token=value.get('nextPageToken')
            if token:
                need(type(token) is str and 0<len(token)<=2048 and token not in self.page_seen[name] and
                     len(self.page_seen[name])<31,'V5.2 wire operation page token')
                self.pages[name]=token;self.page_seen[name].add(token)
            else:
                self.pages.pop(name,None)
                if self.list_seen[name]==0 and name not in self.seen_operations:self.empty_operations.add(name)
            return
        if operation=='poll':
            need(type(value) is dict and value.get('name')==route['name'],'V5.2 wire polled operation name changed')
            self.observe_operation(spec,value,route['action'],route['identity']);return
        if operation in ('insert','delete'):self.observe_operation(spec,value,operation,route.get('identity'))


class _Gate:
    offline=True
    def __init__(self,api,server):self.api,self.server=api,server
    def send(self,method,endpoint,headers,body,timeout,maximum):
        with self.api.lock:return self._send(method,endpoint,headers,body,timeout,maximum)

    def _send(self,method,endpoint,headers,body,timeout,maximum):
        api=self.api;api.validate_adapter();deadline=min(api.deadline,api.clock()+timeout)
        value=strict(body) if body is not None else None
        route=api.policy.route(method,endpoint,value)
        if route['operation'] in ('metadata','put'):maximum=min(maximum,64<<10)
        elif route['operation']=='media':maximum=min(maximum,p.MAX_OBJECT)
        previous=api.deadline;api.deadline=deadline
        try:
            api.policy.before(route,value)
            left=deadline-api.clock()
            if left<=0:raise TimeoutError('V5.2 wire original exchange deadline')
            if route['operation']=='insert':api.policy.dispatched.add(route['spec']['name'])
            result=self.exchange(method,endpoint,headers,body,left,maximum)
            status,raw=result;need(type(raw) is bytes and len(raw)<=maximum,'V5.2 wire response bound')
            if api.clock()>deadline:
                # A received denial must not become a retryable timeout merely
                # because it arrived late. Never observe a late response as proof.
                if type(status) is int and 400<=status<=599:raise h.ApiError(status,method)
                raise TimeoutError('V5.2 wire late response')
            api.policy.observe(route,status,raw);return result
        finally:api.deadline=previous

    def exchange(self,method,endpoint,headers,body,timeout,maximum):
        return self.server.send(method,endpoint,headers,body,timeout,maximum)


class _ScopedApi(cloud_read_retry.Api):
    """Shared request binding; concrete adapters must validate their own authority."""
    def bind_store(self,store):
        need(type(store) is p.Store and store.config==self.policy.cfg and
             (self.policy.store is None or self.policy.store is store),'V5.2 scoped store changed')
        self.policy.store=store

    def bind_provider(self,provider):
        need(type(provider) is p.Provider and provider.store is self.policy.store and provider.request==self.policy.req,
             'V5.2 scoped provider changed')

    def submission_value(self,spec):
        self.validate_adapter();self.policy.plan.spec(spec)
        return deepcopy(self.policy.original('submitted',spec))

    def can_prove_unsubmitted(self,spec,value):
        with self.lock:
            self.validate_adapter();self.policy.plan.spec(spec)
            _,lease=self.policy.current()
            return lease['phase']=='CLEANING' and self.policy.can_prove_unsubmitted(spec,value)

    def authorize(self,method,endpoint,body):
        self.validate_adapter();self.policy.route(method,endpoint,body)

    def call(self,method,endpoint,body=None,*,deadline,**kwargs):
        need(type(deadline) in (int,float) and math.isfinite(deadline),'V5.2 scoped original deadline')
        with self.lock:
            previous=self.deadline;self.deadline=min(previous,deadline)
            try:
                if self.clock()>=self.deadline:raise TimeoutError('V5.2 scoped original deadline')
                return super().call(method,endpoint,body,deadline=self.deadline,**kwargs)
            finally:self.deadline=previous


class ScopedOfflineApi(_ScopedApi):
    """Concrete offline qualification of the same policy needed by native entry."""
    def __init__(self,server,request,*,role='runner',previous_cost=0,cost=1,wall):
        from .cloud_provider_offline import Server
        need(type(server) is Server,'V5.2 scoped HTTP server not admitted')
        a.validate_request(request,domain='offline')
        self.policy=Policy(server.config,request,role=role,previous_cost=previous_cost,cost=cost,wall=wall)
        self.lock=threading.RLock();self.deadline=math.inf
        super().__init__(transport=_Gate(self,server),tokens=lambda timeout:'offline-not-a-credential',clock=server.clock)

    def validate_adapter(self):
        from .cloud_provider_offline import Server
        need(type(self.transport) is _Gate and self.transport.api is self and type(self.transport.server) is Server and
             self.clock==self.transport.server.clock and self.policy.cfg==self.transport.server.config and
             self.policy.domain=='offline','V5.2 scoped HTTP adapter changed')
