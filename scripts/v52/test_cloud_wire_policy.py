from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from scripts.v51 import cloud_http as h
from . import cloud_authority as a, cloud_control as c, cloud_provider as p, cloud_wire_policy as w
from .cloud_provider_offline import Server
from .test_cloud_provider import configuration
from .test_cloud_authority import fixture
from .evidence import encoded,strict,digest


def request():
    value=fixture();value['configurationSha256']=p.config(configuration());return value


class RouteTest(unittest.TestCase):
    def setUp(self):
        self.req=request();self.cfg=configuration();self.scope=w.Policy(self.cfg,self.req,role='runner',previous_cost=0,cost=1,wall=lambda:1000)
        self.plan=self.scope.plan;self.spec=next(iter(self.plan.specs.values()));self.key=p.context_key(self.req)
        self.addCleanup(patch.stopall);patch.object(h.Network,'send',side_effect=AssertionError('network forbidden')).start()

    def route(self,method,endpoint,body=None):return self.scope.route(method,endpoint,body)

    def test_cleanup_digest_path_is_exact_and_readback_rejects_different_bytes(self):
        value=dict(status='PASS',checks=[],errors=[],leftovers=[]);sha=digest(encoded(value))
        key=c.cleanup_key(self.req,sha);endpoint=self.scope.objects+p.url.quote(key,safe='')
        route=self.route('GET',endpoint);self.assertEqual(('cleanup',sha),(route['kind'],route['spec']))
        raw=encoded(value);self.scope.metadata[key]=dict(size=str(len(raw)),generation='42')
        media=self.route('GET',p.query(endpoint,alt='media',generation='42',ifGenerationMatch='42'))
        self.scope.observe(media,200,raw)
        changed=encoded(dict(value,status='FAIL'));self.scope.metadata[key]['size']=str(len(changed))
        with self.assertRaisesRegex(ValueError,'content address'):self.scope.observe(media,200,changed)
        with self.assertRaisesRegex(ValueError,'outside original request'):self.route('GET',endpoint.replace(sha,'not-a-digest'))

    def test_pure_plan_preserves_every_original_body_and_operation_without_admission(self):
        server=Server(self.cfg);provider=p.Provider(p.Store(self.cfg,p.OfflineApi(server)),self.req)
        for spec in self.plan.specs.values():
            self.assertEqual(provider.body(spec),self.plan.body(spec));self.assertEqual(provider.operation_id(spec),self.plan.operation_id(spec))
        native=deepcopy(self.req);native.update(execution=a.DOMAINS['native'],paidCloud=True)
        p.Plan(self.cfg,native)
        with self.assertRaisesRegex(ValueError,'domain'):w.ScopedOfflineApi(server,native,wall=lambda:1000)
        self.assertEqual([],server.events)

    def test_each_insert_requires_exact_original_body_and_request_id(self):
        for spec in self.plan.specs.values():
            endpoint=p.query(self.plan.endpoint(spec).rsplit('/',1)[0],requestId=self.plan.operation_id(spec));body=self.plan.body(spec)
            self.assertEqual('insert',self.route('POST',endpoint,body)['operation'])
            for changed in (dict(body,extra=True),dict(body,description='foreign'),dict(body,name='foreign')):
                with self.assertRaises(ValueError):self.route('POST',endpoint,changed)
            with self.assertRaises(ValueError):self.route('POST',endpoint+'&requestId=duplicate',body)
            with self.assertRaises(ValueError):self.route('POST',endpoint.replace(self.plan.operation_id(spec),'00000000-0000-0000-0000-000000000000'),body)

    def test_unknown_paths_query_aliases_and_cross_namespace_calls_reject(self):
        object_url=self.scope.objects+__import__('urllib.parse',fromlist=['quote']).quote(self.key,safe='')
        for endpoint in (object_url.replace('v5.2','v5.1'),object_url.replace('offline-evidence','foreign'),
            object_url.replace('%2F','/'),object_url+'#fragment',object_url+'?alt=media',
            'http://storage.googleapis.com/storage/v1/b/offline-evidence/o/a',
            'https://storage.googleapis.com:443/storage/v1/b/offline-evidence/o/a',
            self.plan.base+'/zones/us-east1-a/instances/x',self.plan.base+'/global/firewalls'):
            with self.subTest(endpoint=endpoint),self.assertRaises(ValueError):self.route('GET',endpoint)
        with self.assertRaises(ValueError):self.route('GET',object_url,{})
        with self.assertRaises(ValueError):self.route('PATCH',object_url,{})

    def test_numeric_reads_and_deletes_need_observed_original_id_and_exact_operation(self):
        endpoint=self.plan.endpoint(self.spec,'123')
        with self.assertRaises(ValueError):self.route('GET',endpoint)
        self.scope.ids[self.spec['name']]={'123'}
        self.assertEqual('resource',self.route('GET',endpoint)['operation'])
        deleted=p.query(endpoint,requestId=self.plan.operation_id(self.spec,'delete','123'))
        self.assertEqual('delete',self.route('DELETE',deleted)['operation'])
        with self.assertRaises(ValueError):self.route('DELETE',p.query(self.plan.endpoint(self.spec),requestId=self.plan.operation_id(self.spec,'delete','123')))
        with self.assertRaises(ValueError):self.route('DELETE',p.query(endpoint,requestId=self.plan.operation_id(self.spec)))

    def test_media_requires_exact_previously_observed_generation(self):
        endpoint=self.scope.objects+__import__('urllib.parse',fromlist=['quote']).quote(a.LEASE,safe='')
        media=p.query(endpoint,alt='media',generation=100,ifGenerationMatch=100)
        with self.assertRaisesRegex(ValueError,'unobserved'):self.route('GET',media)
        self.scope.metadata[a.LEASE]=dict(generation='100')
        self.assertEqual('media',self.route('GET',media)['operation'])
        for changed in (media.replace('ifGenerationMatch=100','ifGenerationMatch=101'),media+'&generation=100'):
            with self.assertRaises(ValueError):self.route('GET',changed)

    def test_cleanup_cannot_insert_read_host_keys_or_reserve(self):
        scope=w.Policy(self.cfg,self.req,role='cleanup',previous_cost=None,cost=None,wall=lambda:1090)
        spec=self.spec;endpoint=p.query(self.plan.endpoint(spec).rsplit('/',1)[0],requestId=self.plan.operation_id(spec))
        with self.assertRaises(ValueError):scope.route('POST',endpoint,self.plan.body(spec))
        vm=next(s for s in self.plan.specs.values() if s['kind']=='instance')
        with self.assertRaises(ValueError):scope.route('GET',p.query(self.plan.endpoint(vm)+'/getGuestAttributes',queryPath='hostkeys/'),None)
        with self.assertRaisesRegex(ValueError,'cannot reserve'):w.Policy(self.cfg,self.req,role='cleanup',previous_cost=0,cost=1,wall=lambda:1090)

    def test_operation_poll_and_pages_must_come_from_original_response(self):
        spec=self.spec;endpoint=self.plan.scope(spec)+'/operations/foreign'
        with self.assertRaises(ValueError):self.route('GET',endpoint)
        listing=p.query(self.plan.scope(spec)+'/operations',filter='clientOperationId = "'+self.plan.operation_id(spec)+'"',maxResults=100)
        with self.assertRaises(ValueError):self.route('GET',listing+'&pageToken=unobserved')
        r=self.route('GET',listing);self.scope.before(r,None)
        self.scope.observe(r,200,encoded(dict(nextPageToken='opaque')))
        r=self.route('GET',listing+'&pageToken=opaque')
        with self.assertRaisesRegex(ValueError,'page token'):self.scope.observe(r,200,encoded(dict(nextPageToken='opaque')))

    def test_pending_first_page_followed_by_empty_page_is_not_absent_operation(self):
        spec=self.spec;listing=p.query(self.plan.scope(spec)+'/operations',filter='clientOperationId = "'+self.plan.operation_id(spec)+'"',maxResults=100)
        op=dict(name='pending',clientOperationId=self.plan.operation_id(spec),operationType='insert',targetLink=self.plan.endpoint(spec),status='PENDING')
        r=self.route('GET',listing);self.scope.before(r,None);self.scope.observe(r,200,encoded(dict(items=[op],nextPageToken='next')))
        r=self.route('GET',listing+'&pageToken=next');self.scope.before(r,None);self.scope.observe(r,200,b'{}')
        self.assertNotIn(spec['name'],self.scope.empty_operations)
        self.assertEqual('poll',self.route('GET',self.plan.scope(spec)+'/operations/pending')['operation'])
        r=self.route('GET',listing);self.scope.before(r,None);self.scope.observe(r,200,b'{}')
        self.assertNotIn(spec['name'],self.scope.empty_operations)

    def test_original_operation_cannot_change_target_type_or_id(self):
        spec=self.spec;op=dict(name='op',clientOperationId=self.plan.operation_id(spec),operationType='insert',targetLink=self.plan.endpoint(spec),status='DONE',targetId='123')
        self.scope.observe_operation(spec,op)
        for change in (dict(targetId='124'),dict(targetLink=self.plan.endpoint(spec)+'other'),dict(operationType='delete'),dict(clientOperationId='foreign')):
            with self.assertRaises(ValueError):self.scope.observe_operation(spec,dict(op,**change))

    def test_polled_name_and_pending_target_cannot_change(self):
        spec=self.spec;op=dict(name='original',clientOperationId=self.plan.operation_id(spec),operationType='insert',
                              targetLink=self.plan.endpoint(spec),status='PENDING',targetId='123')
        self.scope.observe_operation(spec,op)
        route=self.route('GET',self.plan.scope(spec)+'/operations/original')
        with self.assertRaisesRegex(ValueError,'polled operation name'):
            self.scope.observe(route,200,encoded(dict(op,name='replacement')))
        with self.assertRaisesRegex(ValueError,'target changed'):
            self.scope.observe(route,200,encoded(dict(op,status='DONE',targetId='124')))

    def test_exact_id_absence_does_not_establish_name_absence(self):
        route=dict(operation='resource',spec=self.spec,identity='123');self.scope.observe(route,404,b'')
        self.assertNotIn(self.spec['name'],self.scope.absent)
        route['identity']=None;self.scope.observe(route,404,b'');self.assertIn(self.spec['name'],self.scope.absent)

    def test_object_metadata_rejects_wrong_media_type_size_and_identity(self):
        route=dict(operation='metadata',key=a.LEASE)
        value=dict(bucket=self.cfg['bucket'],name=a.LEASE,generation='100',size='10',contentType='application/json')
        for change in (dict(size=str(p.MAX_OBJECT+1)),dict(size='01'),dict(contentType='text/plain'),dict(bucket='foreign')):
            with self.assertRaises(ValueError):self.scope.observe(route,200,encoded(dict(value,**change)))

    def test_legacy_marker_is_readable_but_cannot_grant_a_scoped_submission(self):
        legacy=dict(schema='gse-v52-provider-submission-v1',spec=self.spec)
        self.scope.marker('submitted',legacy,self.spec)
        self.scope.marker_tickets.add(self.spec['name'])
        self.assertNotEqual(legacy,self.scope.original('submitted',self.spec))
        self.assertFalse(self.scope.can_prove_unsubmitted(self.spec,legacy))
        with self.assertRaises(ValueError):self.scope.marker('submitted',dict(legacy,submitter='foreign'),self.spec)


class LifecycleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.req=request();server=Server(configuration());api=w.ScopedOfflineApi(server,cls.req,wall=lambda:1000)
        store=p.Store(configuration(),api);provider=p.Provider(store,cls.req,wall=lambda:1000,sleep=server.sleep)
        owner=c.OfflineOwner(store,provider,cls.req,wall=lambda:1000)
        with patch.object(h.Network,'send',side_effect=AssertionError('network forbidden')):
            result=owner.prepare(previous_cost=0,cost=1)
        if result['status']!='RESOURCES_PREPARED_NOT_QUALIFIED':raise AssertionError(result)
        cls.snapshot=deepcopy((server.objects,server.resources,server.operations,server.serial))

    def setUp(self):
        self.now=1000;self.server=Server(configuration())
        self.server.objects,self.server.resources,self.server.operations,self.server.serial=deepcopy(self.snapshot)
        self.connect();self.spec=a.resources(self.req)[0]
        self.addCleanup(patch.stopall);patch.object(h.Network,'send',side_effect=AssertionError('network forbidden')).start()

    def connect(self,role='runner'):
        self.api=w.ScopedOfflineApi(self.server,self.req,role=role,previous_cost=None if role=='cleanup' else 0,
                                   cost=None if role=='cleanup' else 1,wall=lambda:self.now)
        self.store=p.Store(configuration(),self.api)
        self.provider=p.Provider(self.store,self.req,wall=lambda:self.now,sleep=self.server.sleep)

    def replace(self,key,value):
        gen,_,kind=self.server.objects[key];self.server.objects[key]=(gen,encoded(value),kind)

    def mutations(self):return [e for e in self.server.events if e['method']!='GET']

    def call(self,method,endpoint,body=None):return self.api.call(method,endpoint,body,deadline=self.api.clock()+30)

    def test_complete_created_allocation_is_reconstructed_and_cleaned_at_expiry(self):
        self.connect('cleanup');self.server.operations.clear()
        self.assertEqual('WAITING',c.reconcile(self.store,self.provider,trigger='workflow_dispatch',now=1089)['status'])
        self.assertEqual([],self.mutations())
        self.now=1090;result=c.reconcile(self.store,self.provider,trigger='workflow_dispatch',now=1090)
        self.assertEqual('PASS',result['status']);self.assertTrue(result['leaseReleased']);self.assertFalse(result['paidCloud'])
        self.assertEqual({},self.server.resources);self.assertIsNone(self.store.get(a.LEASE))
        deletes=[e for e in self.mutations() if e['method']=='DELETE' and 'compute.googleapis.com' in e['url']]
        self.assertEqual(13,len(deletes));self.assertTrue(all(e['url'].split('?')[0].rsplit('/',1)[1].isdigit() for e in deletes))
        self.assertEqual('FAIL',a.inspect_ledger(self.store.get(a.LEDGER)[1],domain='offline')['attempts'][a.validate_request(self.req,domain='offline')]['status'])

    def test_live_owner_renewal_retains_original_claim_and_stale_writes_reject(self):
        generation,lease=self.store.get(a.LEASE);claim=a.resource_claim(lease);self.now=1050
        renewed=a.renew(lease,1050);new=c.put(self.store,a.LEASE,renewed,generation)
        self.assertGreater(new,generation);self.assertEqual(claim,a.resource_claim(self.store.get(a.LEASE)[1]))
        before=len(self.mutations())
        with self.assertRaisesRegex(ValueError,'generation'):self.store.put(a.LEASE,renewed,generation)
        self.assertEqual(before,len(self.mutations()))

    def test_cleanup_cannot_claim_early_activate_or_renew_even_through_raw_api(self):
        self.connect('cleanup');generation,lease=self.store.get(a.LEASE)
        for value in (dict(lease,phase='CLEANING'),a.renew(lease,1001)):
            with self.assertRaises(ValueError):self.store.put(a.LEASE,value,generation)
        self.assertEqual([],self.mutations())

    def test_lease_request_intent_and_identity_cannot_be_replaced(self):
        generation,lease=self.store.get(a.LEASE)
        for change in (lambda v:v['resources'][0].update(id='999'),lambda v:v['resources'][0].update(attempted=False,id=None),
                       lambda v:v.update(renewedAt=1001,expiresAt=1061),lambda v:v['request']['selection'].update(attempt='d'*32)):
            value=deepcopy(lease);change(value)
            with self.assertRaises(ValueError):self.store.put(a.LEASE,value,generation)
        self.assertEqual([],self.mutations())

    def test_ledger_cannot_rewrite_reservation_cost_or_fabricate_completion(self):
        generation,ledger=self.store.get(a.LEDGER);bad=deepcopy(ledger);bad['entries'][0]['reservedCostMicrousd']=99
        with self.assertRaises(ValueError):self.store.put(a.LEDGER,bad,generation)
        completion=dict(schema='gse-v52-owned-completion-v1',execution=self.req['execution'],requestSha256=self.api.policy.sha,
                        status='PASS',evidenceSha256='a'*64,cleanupSha256='b'*64)
        with self.assertRaises(ValueError):self.store.put(self.api.policy.prefix+'completion.json',completion,0)
        self.assertEqual([],self.mutations())

    def test_immutable_context_and_unobserved_operation_receipts_reject(self):
        with self.assertRaises(ValueError):self.store.put(p.context_key(self.req),p.context(configuration(),self.req),1)
        op=dict(schema='gse-v52-provider-operation-v1',spec=self.spec,operation={})
        with self.assertRaisesRegex(ValueError,'not observed'):self.store.put(self.provider.receipt_key(self.spec),op,0)
        with self.assertRaises(ValueError):self.store.delete(p.context_key(self.req),1)
        self.assertEqual([],self.mutations())

    def test_reconstructed_api_cannot_reuse_prior_submission_marker(self):
        _,lease=self.store.get(a.LEASE);lease['resources'][0]['id']=None;self.replace(a.LEASE,lease)
        endpoint=p.query(self.provider.endpoint(self.spec).rsplit('/',1)[0],requestId=self.provider.operation_id(self.spec))
        with self.assertRaisesRegex(ValueError,'original submission'):self.call('POST',endpoint,self.provider.body(self.spec))
        self.assertEqual([],self.mutations())

    def test_expiry_during_token_refresh_prevents_mutation(self):
        generation,lease=self.store.get(a.LEASE);self.api.token=None
        def refresh(timeout):self.now=1060;return 'offline-not-a-credential'
        self.api.tokens=refresh
        with self.assertRaisesRegex(ValueError,'expired'):self.store.put(a.LEASE,dict(lease),generation)
        self.assertEqual([],self.mutations())

    def test_owner_fencing_during_token_refresh_prevents_numeric_delete(self):
        generation,lease=self.store.get(a.LEASE);lease['phase']='CLEANING';self.replace(a.LEASE,lease)
        self.provider.operation(self.spec);identity=lease['resources'][0]['id'];self.api.token=None
        def refresh(timeout):self.server.objects.pop(a.LEASE);return 'offline-not-a-credential'
        self.api.tokens=refresh
        endpoint=p.query(self.provider.endpoint(self.spec,identity),requestId=self.provider.operation_id(self.spec,'delete',identity))
        with self.assertRaisesRegex(ValueError,'lease missing'):self.call('DELETE',endpoint)
        self.assertEqual([],self.mutations())

    def test_metadata_drift_during_refresh_is_checked_before_numeric_delete(self):
        _,lease=self.store.get(a.LEASE);lease['phase']='CLEANING';self.replace(a.LEASE,lease)
        self.provider.operation(self.spec);identity=lease['resources'][0]['id'];self.api.token=None
        value=next(v for v in self.server.resources.values() if v['name']==self.spec['name'])
        def refresh(timeout):value['description']='foreign';return 'offline-not-a-credential'
        self.api.tokens=refresh
        endpoint=p.query(self.provider.endpoint(self.spec,identity),requestId=self.provider.operation_id(self.spec,'delete',identity))
        with self.assertRaisesRegex(ValueError,'ownership'):self.call('DELETE',endpoint)
        self.assertEqual([],self.mutations())

    def test_image_drift_during_refresh_is_checked_before_boot_disk_insert(self):
        _,lease=self.store.get(a.LEASE)
        row=next(r for r in lease['resources'] if r['spec']['kind']=='disk' and r['spec']['purpose']=='boot')
        row['id']=None;self.replace(a.LEASE,lease);spec=row['spec']
        # Model the original process after retaining its one submission marker.
        self.api.policy.marker_tickets.add(spec['name']);self.api.token=None
        key=self.provider.receipt_key(spec).replace('.json','-submitted.json')
        self.replace(key,self.api.policy.original('submitted',spec))
        def refresh(timeout):self.server.image['id']='999';return 'offline-not-a-credential'
        self.api.tokens=refresh
        endpoint=p.query(self.provider.endpoint(spec).rsplit('/',1)[0],requestId=self.provider.operation_id(spec))
        with self.assertRaisesRegex(ValueError,'pinned image changed'):self.call('POST',endpoint,self.provider.body(spec))
        self.assertEqual([],self.mutations())

    def test_release_requires_terminal_evidence_and_fresh_resource_absence(self):
        generation,lease=self.store.get(a.LEASE);lease['phase']='CLEANING';self.replace(a.LEASE,lease)
        with self.assertRaisesRegex(ValueError,'completion missing'):self.store.delete(a.LEASE,generation)
        self.assertEqual([],self.mutations())

    def test_cached_absence_cannot_release_a_lease_when_original_names_exist(self):
        generation,lease=self.store.get(a.LEASE);lease['phase']='CLEANING';self.replace(a.LEASE,lease)
        completion=dict(schema='gse-v52-owned-completion-v1',execution=self.req['execution'],requestSha256=self.api.policy.sha,
                        status='FAIL',evidenceSha256=None,cleanupSha256='b'*64)
        self.server.serial+=1
        self.server.objects[self.api.policy.prefix+'completion.json']=(self.server.serial,encoded(completion),'application/json')
        _,ledger=self.store.get(a.LEDGER);self.replace(a.LEDGER,a.finish(ledger,self.req,completion))
        for row in lease['resources']:
            self.api.policy.absent.add(row['spec']['name']);self.api.policy.resolved[row['spec']['name']]=row['id']
        with self.assertRaisesRegex(ValueError,'resolved absence'):self.store.delete(a.LEASE,generation)
        self.assertEqual([],self.mutations());self.assertIsNotNone(self.store.get(a.LEASE))
        self.assertEqual(13,len(self.server.resources))

    def test_direct_generic_http_call_cannot_bypass_mutation_checks(self):
        _,lease=self.store.get(a.LEASE);identity=lease['resources'][0]['id'];self.provider.operation(self.spec)
        endpoint=p.query(self.provider.endpoint(self.spec,identity),requestId=self.provider.operation_id(self.spec,'delete',identity))
        with self.assertRaisesRegex(ValueError,'identity/phase'):
            h.Api.call(self.api,'DELETE',endpoint,deadline=self.api.clock()+30)
        self.assertEqual([],self.mutations())

    def test_cleanup_receipt_cannot_fabricate_absence_or_retain_arbitrary_errors(self):
        generation,lease=self.store.get(a.LEASE);lease['phase']='CLEANING';self.replace(a.LEASE,lease)
        rows=sorted(lease['resources'],key=lambda r:{'instance':0,'disk':1,'firewall':2}[r['spec']['kind']])
        value=dict(status='PASS',checks=[dict(name=r['spec']['name'],expectedId=r['id'],absent=True,observed=None) for r in rows],errors=[],leftovers=[])
        with self.assertRaisesRegex(ValueError,'unobserved absence'):self.store.put(self.api.policy.prefix+f'cleanup-{generation}.json',value,0)
        self.assertEqual([],self.mutations())

    def test_nested_fresh_checks_share_original_exchange_deadline(self):
        generation,lease=self.store.get(a.LEASE);lease['phase']='CLEANING'
        def delay(stage,event):
            if stage=='after' and event['method']=='GET':self.server.seconds+=16
        self.server.fault=delay
        with self.assertRaisesRegex(TimeoutError,'late response|deadline'):self.store.put(a.LEASE,lease,generation)
        self.assertEqual([],self.mutations())

    def test_late_explicit_denial_is_not_converted_to_retryable_timeout(self):
        def denied(*args):
            self.server.seconds+=31
            return 403,b''
        with patch.object(w._Gate,'exchange',side_effect=denied):
            with self.assertRaises(h.ApiError) as error:self.store.get(a.LEASE)
        self.assertEqual(403,error.exception.status)
        self.assertEqual([],self.mutations())

    def test_expired_scoped_call_is_typed_without_any_exchange(self):
        count=len(self.server.events)
        with self.assertRaises(TimeoutError):self.api.call('GET',self.store.endpoint(a.LEASE),deadline=self.api.clock())
        self.assertEqual(count,len(self.server.events))

    def test_adapter_replacement_and_cross_request_store_binding_reject(self):
        class Lookalike:offline=True
        self.api.transport.server=Lookalike()
        with self.assertRaisesRegex(ValueError,'adapter changed'):self.store.get(a.LEASE)
        self.assertEqual([],self.mutations())
        self.connect();other=fixture(attempt='d'*32);other['configurationSha256']=p.config(configuration())
        with self.assertRaisesRegex(ValueError,'provider changed'):p.Provider(self.store,other)
        with self.assertRaisesRegex(ValueError,'store changed'):p.Store(configuration(),self.api)


class PartialLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.req=request();self.server=Server(configuration());self.now=1000
        self.api=w.ScopedOfflineApi(self.server,self.req,wall=lambda:self.now)
        self.store=p.Store(configuration(),self.api)
        self.provider=p.Provider(self.store,self.req,wall=lambda:self.now,sleep=self.server.sleep)
        self.owner=c.OfflineOwner(self.store,self.provider,self.req,wall=lambda:self.now)
        self.addCleanup(patch.stopall);patch.object(h.Network,'send',side_effect=AssertionError('network forbidden')).start()
        self.owner.acquire(previous_cost=0,cost=1)
        changed=deepcopy(self.owner.lease);changed['resources'][0]['attempted']=True;self.owner.persist(changed)
        self.spec=changed['resources'][0]['spec']

    def compute(self,method):return [e for e in self.server.events if e['method']==method and 'compute.googleapis.com' in e['url']]

    def test_lost_insert_reply_is_resolved_without_resubmission_then_cleaned(self):
        fired=[]
        def fault(stage,event):
            if not fired and stage=='after' and event['method']=='POST' and 'compute.googleapis.com' in event['url']:
                fired.append(True);raise ConnectionError('lost insert reply')
        self.server.fault=fault
        with self.assertRaises(ConnectionError):self.provider.create(self.spec,1300)
        self.server.fault=lambda *args:None
        endpoint=p.query(self.provider.endpoint(self.spec).rsplit('/',1)[0],requestId=self.provider.operation_id(self.spec))
        with self.assertRaisesRegex(ValueError,'original submission'):
            self.api.call('POST',endpoint,self.provider.body(self.spec),deadline=self.api.clock()+30)
        result=self.owner.close()
        self.assertEqual('PASS',result['status']);self.assertEqual({},self.server.resources)
        self.assertEqual(1,len(self.compute('POST')));self.assertEqual(1,len(self.compute('DELETE')))

    def test_lost_marker_reply_can_only_observe_original_write_then_insert_once(self):
        fired=[]
        def fault(stage,event):
            if not fired and stage=='after' and event['method']=='POST' and '-submitted.json' in event['url']:
                fired.append(True);raise ConnectionError('lost marker reply')
        self.server.fault=fault;result=self.provider.create(self.spec,1300)
        self.assertTrue(fired);self.assertIsNotNone(result['id']);self.assertEqual(1,len(self.compute('POST')))
        marker=[e for e in self.server.events if e['method']=='POST' and '-submitted.json' in e['url']]
        self.assertEqual(1,len(marker));self.server.fault=lambda *args:None
        self.assertEqual('PASS',self.owner.close()['status'])

    def test_fenced_unsubmitted_intent_retains_proof_and_can_release(self):
        result=self.owner.close();self.assertEqual('PASS',result['status']);self.assertFalse(self.compute('POST'))
        key=self.provider.receipt_key(self.spec).replace('.json','-unsubmitted.json')
        self.assertEqual('gse-v52-provider-not-submitted-v1',self.store.get(key)[1]['schema'])
        self.assertIsNone(self.store.get(a.LEASE))

    def test_wrong_reservation_amount_is_rejected_without_resource_work(self):
        generation,ledger=self.store.get(a.LEDGER);changed=deepcopy(ledger);changed['entries'][0]['reservedCostMicrousd']=2
        with self.assertRaises(ValueError):self.store.put(a.LEDGER,changed,generation)
        self.assertFalse(self.compute('POST'));self.assertEqual('PASS',self.owner.close()['status'])

    def test_next_intent_waits_for_original_resource_id(self):
        changed=deepcopy(self.owner.lease);changed['resources'][1]['attempted']=True
        with self.assertRaisesRegex(ValueError,'retained intent changed'):self.owner.persist(changed)
        self.assertFalse(self.compute('POST'))

    def test_unknown_submission_stays_unresolved_and_retained_for_reconciliation(self):
        key=self.provider.receipt_key(self.spec).replace('.json','-submitted.json')
        c.put(self.store,key,self.api.policy.original('submitted',self.spec),0)
        # Reconstructed process cannot tell whether an old marker preceded a POST.
        api=w.ScopedOfflineApi(self.server,self.req,role='cleanup',previous_cost=None,cost=None,wall=lambda:1090)
        store=p.Store(configuration(),api);provider=p.Provider(store,self.req,wall=lambda:1090,sleep=self.server.sleep)
        result=c.reconcile(store,provider,trigger='workflow_dispatch',now=1090)
        self.assertEqual('FAIL',result['status']);self.assertFalse(result['leaseReleased']);self.assertIsNotNone(store.get(a.LEASE))
        self.assertTrue(result['cleanup']['errors']);self.assertTrue(all(set(e)=={'phase','type'} for e in result['cleanup']['errors']))
        self.assertFalse(self.compute('POST'));self.assertFalse(self.compute('DELETE'))

    def try_insert(self,api,provider):
        endpoint=p.query(provider.endpoint(self.spec).rsplit('/',1)[0],requestId=provider.operation_id(self.spec))
        return api.call('POST',endpoint,provider.body(self.spec),deadline=api.clock()+30)

    def test_rejected_old_marker_cannot_grant_new_process_a_submission(self):
        key=self.provider.receipt_key(self.spec).replace('.json','-submitted.json')
        original=self.api.policy.original('submitted',self.spec);self.store.put(key,original,0)
        api=w.ScopedOfflineApi(self.server,self.req,wall=lambda:self.now)
        store=p.Store(configuration(),api);provider=p.Provider(store,self.req,wall=lambda:self.now,sleep=self.server.sleep)
        self.assertNotEqual(original['submitter'],api.policy.submitter)
        with self.assertRaises((h.ApiError,ValueError)):store.put(key,original,0)
        with self.assertRaises(ValueError):self.try_insert(api,provider)
        self.assertFalse(self.compute('POST'))

    def test_competing_marker_cas_winner_cannot_grant_loser_submission(self):
        key=self.provider.receipt_key(self.spec).replace('.json','-submitted.json')
        other=w.ScopedOfflineApi(self.server,self.req,wall=lambda:self.now)
        competing=other.policy.original('submitted',self.spec);fired=[]
        def race(stage,event):
            if not fired and stage=='before' and event['method']=='POST' and '-submitted.json' in event['url']:
                fired.append(True);self.server.serial+=1
                self.server.objects[key]=(self.server.serial,encoded(competing),'application/json')
        self.server.fault=race
        with self.assertRaises(h.ApiError):self.store.put(key,self.api.policy.original('submitted',self.spec),0)
        self.server.fault=lambda *args:None
        with self.assertRaises(ValueError):self.try_insert(self.api,self.provider)
        self.assertFalse(self.compute('POST'))

    def test_original_never_dispatched_marker_can_be_cancelled_only_after_fencing(self):
        key=self.provider.receipt_key(self.spec).replace('.json','-submitted.json')
        value=self.api.policy.original('submitted',self.spec);c.put(self.store,key,value,0)
        self.assertFalse(self.api.can_prove_unsubmitted(self.spec,value))
        result=self.owner.close();self.assertEqual('PASS',result['status']);self.assertFalse(self.compute('POST'))
        proof=self.store.get(self.provider.receipt_key(self.spec).replace('.json','-unsubmitted.json'))
        self.assertEqual('gse-v52-provider-not-submitted-v1',proof[1]['schema']);self.assertIsNone(self.store.get(a.LEASE))

    def test_uncertain_transport_call_cannot_be_cancelled_as_unsubmitted(self):
        def fault(stage,event):
            if stage=='before' and event['method']=='POST' and 'compute.googleapis.com' in event['url']:
                raise ConnectionError('unknown transport outcome')
        self.server.fault=fault
        with self.assertRaises(ConnectionError):self.provider.create(self.spec,1300)
        self.server.fault=lambda *args:None
        result=self.owner.close();self.assertEqual('FAIL',result['status']);self.assertFalse(result['leaseReleased'])
        self.assertIn(self.spec['name'],self.api.policy.dispatched);self.assertIsNotNone(self.store.get(a.LEASE))


if __name__=='__main__':unittest.main()
