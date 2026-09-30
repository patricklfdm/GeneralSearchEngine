from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from urllib.parse import urlencode, quote
from . import cloud_authority as a, cloud_native_authority as n, cloud_native_cleanup as native
from . import cloud_cleanup as c, cloud_cleanup_qualification as q, cloud_gcp as g, cloud_runner as r, cloud_fake, performance_model as m
from .cloud_http import Api


class NativeCleanupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.req, self.lease, self.http = q.interrupted(authority=n)
        self.now = self.lease['expiresAt']+self.lease['graceSeconds']

    def bound(self):
        _, http, api, _ = q.restore(q.snapshot(self.http))
        policy = native.CleanupApi(http.configuration, api)
        store = g.Store(http.configuration, policy, authority=n)
        generation, lease = store.get(n.LEASE); policy.bind(lease, generation, now=self.now)
        store.get(n.LEDGER); value = store.get(c.context_key(self.req, authority=n))[1]
        provider = g.Compute(http.configuration, self.req, policy, guest_access=value['guestAccess'], authority=n)
        return policy, http, store, provider

    def rejected(self, policy, http, requests):
        count = len(http.requests)
        for method, url, body in requests:
            with self.subTest(method=method, url=url), self.assertRaises((ValueError, KeyError, TypeError)):
                policy.call(method, url, body, deadline=policy.clock()+30)
            self.assertEqual(len(http.requests), count, 'rejected request reached HTTP transport')

    def test_domains_reject_each_others_request_lease_and_ledger(self):
        fake_req, fake_lease, http = q.interrupted()
        native_ledger = m.strict_json(self.http.objects[n.LEDGER][1]); fake_ledger = m.strict_json(http.objects[a.LEDGER][1])
        for auth, req, lease, ledger in ((a, self.req, self.lease, native_ledger), (n, fake_req, fake_lease, fake_ledger)):
            for fn, value in ((auth.validate_request, req), (auth.validate_lease, lease), (auth.inspect_ledger, ledger)):
                with self.subTest(fn=fn), self.assertRaises(ValueError): fn(value)
        # Relabelling just the top-level ledger/lease cannot migrate embedded authority.
        changed = deepcopy(fake_ledger); changed.update(schema=n.empty_ledger()['schema'], execution=n.EXECUTION)
        with self.assertRaises(ValueError): n.inspect_ledger(changed)
        changed = deepcopy(fake_lease); changed.update(schema=self.lease['schema'], execution=n.EXECUTION)
        with self.assertRaises(ValueError): n.validate_lease(changed)

    def test_native_request_requires_ssh_binding_and_is_not_paid_admission(self):
        for key, value in (('paidCloud', False), ('paidCloud', 1), ('execution', a.EXECUTION), ('guestAccessSha256', 'bad')):
            with self.subTest(key=key), self.assertRaises(ValueError): n.validate_request(dict(self.req, **{key:value}))
        absent = deepcopy(self.req); del absent['guestAccessSha256']
        with self.assertRaises(ValueError): n.validate_request(absent)
        _, pre, approval = cloud_fake.fixture()
        with self.assertRaises(ValueError): a.admit(self.req, pre, approval, self.req['createdAt'])
        policy, _, store, provider = self.bound()
        with self.assertRaisesRegex(ValueError, 'unqualified'): r.adapters(store, provider)
        self.assertEqual(store.execution, n.ADAPTER_EXECUTION)

    def test_live_activation_guard_precedes_credentials_and_http(self):
        transport = Mock(offline=False); tokens = Mock(); api = Api(transport=transport, tokens=tokens)
        with self.assertRaisesRegex(ValueError, 'activation unavailable'):
            native.reconcile(self.http.configuration, api, self.root/'live', trigger='manual', now=self.now)
        tokens.assert_not_called(); transport.send.assert_not_called(); self.assertFalse((self.root/'live').exists())
        self.assertEqual(g.Store(self.http.configuration, api, authority=n).execution, 'unqualified-v51-gcp-provider')

    def test_native_cleanup_rejects_fake_retained_bytes_without_mutation(self):
        _, _, http = q.interrupted(); state = q.snapshot(http)
        _, restored, api, _ = q.restore(state)
        with self.assertRaises(ValueError): native.reconcile(http.configuration, api, self.root/'fake', trigger='manual', now=self.now)
        self.assertEqual(q.snapshot(restored), state)
        self.assertTrue(all(row['method'] == 'GET' for row in restored.requests))

    def test_binding_requires_observed_generation_exact_lease_and_expiry(self):
        _, http, api, _ = q.restore(q.snapshot(self.http)); policy = native.CleanupApi(http.configuration, api)
        store = g.Store(http.configuration, policy, authority=n)
        with self.assertRaises(ValueError): policy.bind(self.lease, 123, now=self.now)
        generation, lease = store.get(n.LEASE)
        for value, gen, now in ((lease,generation+1,self.now),(lease,generation,self.now-1),
                               (dict(lease,expiresAt=lease['expiresAt']-1),generation,self.now)):
            with self.assertRaises(ValueError): policy.bind(value, gen, now=now)
        policy.bind(lease,generation,now=self.now)
        with self.assertRaises(ValueError): policy.bind(lease,generation,now=self.now)

    def test_unbound_policy_allows_only_pinned_control_reads(self):
        _, http, api, _ = q.restore(q.snapshot(self.http)); policy = native.CleanupApi(http.configuration, api)
        ledger = policy.objects+quote(n.LEDGER,safe='')
        self.rejected(policy,http,[('DELETE',ledger,None),('POST',policy.upload+'?'+urlencode(dict(uploadType='media',name=n.LEASE,ifGenerationMatch=0)),self.lease),
            ('GET',policy.objects+quote(n.PREFIX+'attempts/x/completion.json',safe=''),None),
            ('GET','https://compute.googleapis.com/compute/v1/projects/offline-project/zones/us-west4-a/instances',None),
            ('GET',ledger+'?alt=media',None),('GET',ledger+'?alt=media&generation=1&ifGenerationMatch=2',None),
            ('GET',ledger+'?generation=1&generation=2',None),('GET',ledger+'#fragment',None),
            ('GET',ledger.replace('https://','http://'),None),('GET',ledger.replace('storage.googleapis.com','storage.googleapis.com.evil'),None),
            ('GET',ledger+'?alt=media&generation=1&ifGenerationMatch=1&extra=1',None)])

    def test_policy_forbids_allocations_name_deletes_and_unresolved_ids(self):
        policy,http,store,provider = self.bound(); spec = self.lease['resources'][0]['spec']; identity=self.lease['resources'][0]['id']
        base=provider.url(spec)
        self.rejected(policy,http,[('POST',base.rsplit('/',1)[0]+'?requestId='+provider.operation_id(spec),provider.body(spec)),
            ('DELETE',base+'?requestId='+provider.operation_id(spec,'delete',identity),None),
            ('DELETE',provider.url(spec,identity)+'?requestId='+provider.operation_id(spec,'delete',identity),None),
            ('GET',provider.url(spec,identity),None),('GET',provider.scope(spec)+'/operations',None),
            ('GET',provider.scope(spec)+'/operations/unobserved',None),('GET',base.replace('offline-project','foreign-project'),None),
            ('POST',base+'/setMetadata',{}),('GET',base+'/getGuestAttributes',None)])
        provider.operation(spec)
        self.rejected(policy,http,[('DELETE',provider.url(spec,identity)+'?requestId=wrong',None),
            ('DELETE',provider.url(spec,'999999')+'?requestId='+provider.operation_id(spec,'delete','999999'),None),
            ('DELETE',provider.url(spec,identity)+'?requestId='+provider.operation_id(spec,'delete',identity)+'&requestId=wrong',None)])
        provider.delete(spec,identity)
        self.assertFalse(any(v['method']=='POST' and '/compute/' in v['path'] for v in http.requests))

    def test_storage_policy_forbids_history_reset_evidence_deletion_and_foreign_paths(self):
        policy,http,store,_=self.bound()
        def post(key,body,expected=0):return 'POST',policy.upload+'?'+urlencode(dict(uploadType='media',name=key,ifGenerationMatch=expected)),body
        expected=store.get(n.LEDGER)[0]
        self.rejected(policy,http,[post(n.LEDGER,n.empty_ledger(),expected),post(n.LEASE,self.lease,0),
            post(policy.attempt+'cleanup-context.json',{},0),post(n.PREFIX+'attempts/'+'0'*64+'/completion.json',{},0),
            post(policy.attempt+'parts/payload',b'bytes',0),post(n.PREFIX+'../foreign',{},0),
            ('DELETE',policy.objects+quote(n.LEDGER,safe='')+'?ifGenerationMatch='+str(expected),None),
            ('DELETE',policy.objects+quote(policy.attempt+'completion.json',safe='')+'?ifGenerationMatch=1',None),
            ('GET',policy.objects.replace('offline-evidence','other-bucket')+quote(n.LEASE,safe=''),None)])

    def test_lease_updates_cannot_add_intents_or_rewrite_ids(self):
        policy,http,store,provider=self.bound()
        for row in self.lease['resources']:provider.operation(row['spec'])
        changes=[lambda v:v['resources'][0].update(id='999999'),lambda v:v['resources'][0].update(id=None),
                 lambda v:v['resources'][0].update(attempted=False),lambda v:v.update(expiresAt=v['expiresAt']+1)]
        for change in changes:
            value=deepcopy(self.lease);change(value)
            with self.assertRaises(ValueError):store.put(n.LEASE,value,policy.lease_generation)
        self.assertFalse(any(v['method']=='POST' for v in http.requests))

    def test_completion_requires_native_request_binding_and_create_only(self):
        policy,http,store,_=self.bound()
        value=dict(schema=n.COMPLETION_SCHEMA,execution=n.EXECUTION,paidCloud=True,requestSha256=n.validate_request(self.req),status='FAIL',
                   engineWorkloadExecuted=False,fullRemoteQualification=False,reason='expired interrupted owner')
        key=policy.attempt+'completion.json'
        for field,bad in (('schema',a.COMPLETION_SCHEMA),('execution',a.EXECUTION),('paidCloud',False),('requestSha256','0'*64),('status','PASS'),('engineWorkloadExecuted',True)):
            with self.assertRaises(ValueError):store.put(key,dict(value,**{field:bad}),0)
        gen=store.put(key,value,0)
        with self.assertRaisesRegex(ValueError,'overwrite'):store.put(key,value,gen)
        ledger_gen,ledger=store.get(n.LEDGER)
        # Exact one-event terminal append is the only writable ledger operation.
        store.put(n.LEDGER,n.finish(ledger,self.req,value),ledger_gen)
        with self.assertRaises(ValueError):store.put(n.LEDGER,n.empty_ledger(),store.get(n.LEDGER)[0])

    def test_lease_release_requires_completion_and_every_absence(self):
        policy,http,store,provider=self.bound()
        with self.assertRaises(ValueError):store.delete(n.LEASE,policy.lease_generation)
        completion=dict(schema=n.COMPLETION_SCHEMA,execution=n.EXECUTION,paidCloud=True,requestSha256=n.validate_request(self.req),status='FAIL',
                   engineWorkloadExecuted=False,fullRemoteQualification=False,reason='expired interrupted owner')
        store.put(policy.attempt+'completion.json',completion,0)
        gen,ledger=store.get(n.LEDGER);store.put(n.LEDGER,n.finish(ledger,self.req,completion),gen)
        with self.assertRaises(ValueError):store.delete(n.LEASE,policy.lease_generation)
        for row in self.lease['resources']:
            provider.operation(row['spec']);provider.delete(row['spec'],row['id']);provider.describe(row['spec'])
        store.delete(n.LEASE,policy.lease_generation);self.assertIsNone(store.get(n.LEASE))

    def test_pending_delete_poll_is_bound_to_exact_returned_operation(self):
        policy,http,store,provider=self.bound();row=self.lease['resources'][0];spec=row['spec'];identity=row['id'];provider.operation(spec)
        original=http.compute;polled=[]
        def pending(method,path,query,body):
            status,raw=original(method,path,query,body)
            if method=='DELETE' and status==200:
                op=m.strict_json(raw);op['status']='RUNNING';return http.reply(op)
            if method=='GET' and '/operations/' in path:polled.append(path)
            return status,raw
        http.compute=pending;provider.sleep=lambda seconds:None;provider.delete(spec,identity)
        self.assertEqual(len(polled),1)
        self.rejected(policy,http,[('GET',provider.scope(spec)+'/operations/foreign-operation',None)])

    def test_manual_and_schedule_share_cleanup_requests_and_failed_charge(self):
        outcomes=[]
        for trigger in ('manual','schedule'):
            _,http,api,_=q.restore(q.snapshot(self.http))
            result=native.reconcile(http.configuration,api,self.root/trigger,trigger=trigger,now=self.now)
            self.assertEqual(result['status'],'PASS');self.assertEqual(result['execution'],n.ADAPTER_EXECUTION)
            self.assertFalse(http.resources);self.assertNotIn(n.LEASE,http.objects)
            total,attempts=n.inspect_ledger(m.strict_json(http.objects[n.LEDGER][1]));self.assertEqual(total,1_000_000)
            self.assertEqual(attempts[n.validate_request(self.req)]['status'],'FAIL')
            outcomes.append([v for v in http.requests if '/compute/' in v['path']])
        self.assertEqual(outcomes[0],outcomes[1])

    def test_native_facade_domain_cannot_be_overridden(self):
        fake_req,_,_=q.interrupted()
        with self.assertRaises(TypeError):n.validate_request(fake_req,domain='fake')

    def test_completed_original_attempt_and_charge_are_preserved(self):
        _,http,api,_=q.restore(q.snapshot(self.http));store=g.Store(http.configuration,api,authority=n)
        completion=dict(schema=n.COMPLETION_SCHEMA,execution=n.EXECUTION,paidCloud=True,
                        requestSha256=n.validate_request(self.req),status='PASS',engineWorkloadExecuted=True)
        r.finalize(store,self.lease,completion,authority=n)
        before=deepcopy(http.objects[n.LEDGER])
        result=native.reconcile(http.configuration,api,self.root/'completed',trigger='schedule',now=self.now)
        self.assertEqual(result['status'],'PASS');self.assertEqual(http.objects[n.LEDGER],before)
        self.assertEqual(store.get(n.PREFIX+'attempts/'+n.validate_request(self.req)+'/completion.json')[1],completion)

    def test_lost_delete_reply_keeps_lease_then_reconciles_without_repeating_delete(self):
        _,http,api,_=q.restore(q.snapshot(self.http));original=http.compute;lost=[]
        def lose(method,path,query,body):
            result=original(method,path,query,body)
            if method=='DELETE' and not lost:
                lost.append(path);raise ConnectionError('lost delete reply')
            return result
        http.compute=lose
        first=native.reconcile(http.configuration,api,self.root/'lost',trigger='manual',now=self.now)
        self.assertEqual(first['status'],'FAIL');self.assertIn(n.LEASE,http.objects);self.assertFalse(http.resources)
        state=q.snapshot(http);_,fresh,fresh_api,_=q.restore(state)
        second=native.reconcile(fresh.configuration,fresh_api,self.root/'later',trigger='schedule',now=self.now+1)
        self.assertEqual(second['status'],'PASS');self.assertNotIn(n.LEASE,fresh.objects)
        self.assertFalse(any(v['method']=='DELETE' and '/compute/' in v['path'] for v in fresh.requests))
        self.assertEqual(n.inspect_ledger(m.strict_json(fresh.objects[n.LEDGER][1]))[0],1_000_000)

    def test_lease_cas_conflict_blocks_resource_deletion(self):
        _,http,api,_=q.restore(q.snapshot(self.http));changed=[]
        def race(method,path,query,body):
            if method=='POST' and query.get('name')==n.LEASE and not changed:
                changed.append(True);q.rewrite(http,n.LEASE,lambda value:None)
        http.hook=race
        result=native.reconcile(http.configuration,api,self.root/'cas',trigger='manual',now=self.now)
        self.assertEqual(result['status'],'FAIL');self.assertIn(n.LEASE,http.objects)
        self.assertEqual(len(http.resources),13)
        self.assertFalse(any(v['method']=='DELETE' for v in http.requests))

    def test_metadata_only_refresh_cannot_authorize_stale_ledger_or_lease_bytes(self):
        policy,http,store,_=self.bound()
        completion=dict(schema=n.COMPLETION_SCHEMA,execution=n.EXECUTION,paidCloud=True,
                        requestSha256=n.validate_request(self.req),status='FAIL',engineWorkloadExecuted=False,
                        fullRemoteQualification=False,reason='expired interrupted owner')
        store.put(policy.attempt+'completion.json',completion,0)
        ledger=deepcopy(policy.ledger)
        q.rewrite(http,n.LEDGER,lambda value:None)
        metadata=policy.call('GET',store.url(n.LEDGER),deadline=policy.clock()+30)
        count=len(http.requests)
        with self.assertRaisesRegex(ValueError,'prerequisites'):
            store.put(n.LEDGER,n.finish(ledger,self.req,completion),int(metadata['generation']))
        self.assertEqual(len(http.requests),count)
        q.rewrite(http,n.LEASE,lambda value:None)
        with self.assertRaisesRegex(ValueError,'generation changed'):store.get(n.LEASE)

    def test_native_ledger_preserves_budget_order_and_failed_canonical_block(self):
        request=dict(self.req,order='canonical-first',member='canonical-1')
        ledger=n.reserve(n.empty_ledger(),request,dict(previousCostMicrousd=0,maximumCostMicrousd=100_000_000))
        completion=dict(requestSha256=n.validate_request(request),status='FAIL')
        ledger=n.finish(ledger,request,completion)
        self.assertEqual(n.inspect_ledger(ledger)[0],100_000_000)
        next_req=dict(request,attempt='f'*32)
        for approval in (dict(previousCostMicrousd=0,maximumCostMicrousd=1),dict(previousCostMicrousd=100_000_000,maximumCostMicrousd=1)):
            with self.assertRaises(ValueError):n.reserve(ledger,next_req,approval)


if __name__=='__main__':unittest.main()
