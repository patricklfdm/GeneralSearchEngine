from copy import deepcopy
import unittest
from unittest.mock import patch
import urllib.parse as url
from scripts.v51.cloud_http import Api, ApiError, Network
from . import cloud_authority as a, cloud_control as control, cloud_provider as p
from .cloud_provider_offline import Server
from .test_cloud_authority import fixture
from .evidence import encoded, strict


def configuration():
    return dict(schema='gse-v52-provider-config-v1',project='offline-project',bucket='offline-evidence',
        network='private-network',subnetwork='private-subnet',region='us-west4',zone='us-west4-a',
        imageProject='offline-images',imageName='pinned-image',imageId='123456',machineType='e2-standard-4',diskType='pd-ssd',port=19752)


class ProviderTest(unittest.TestCase):
    def setUp(self):
        self.cfg=configuration();self.req=fixture();self.req['configurationSha256']=p.config(self.cfg)
        self.server=Server(self.cfg);self.api=p.OfflineApi(self.server);self.store=p.Store(self.cfg,self.api)
        self.provider=p.Provider(self.store,self.req,wall=lambda:1000,sleep=self.server.sleep)
        self.owner=control.OfflineOwner(self.store,self.provider,self.req,wall=lambda:1000)
        self.spec=a.resources(self.req)[0]

    def prepare(self):return self.owner.prepare(previous_cost=0,cost=1)
    def compute_mutations(self,method='POST'):
        return [e for e in self.server.events if e['method']==method and 'compute.googleapis.com' in e['url']]
    def operation_url(self,spec=None):return self.provider.scope(spec or self.spec)+'/operations?'
    def reply(self,value):return 200,encoded(value)

    def test_complete_http_owner_and_independent_cleanup(self):
        with patch.object(Network,'send',side_effect=AssertionError('network forbidden')):
            result=self.prepare();self.assertEqual('RESOURCES_PREPARED_NOT_QUALIFIED',result['status'])
            self.assertFalse(result['paidCloud']);self.assertFalse(result['fullRemoteQualification'])
            self.assertEqual(13,len(self.server.resources));self.assertEqual(13,len(self.compute_mutations()))
            # Reconstruct using only the retained configuration/request. Provider
            # operations may expire after DONE; immutable receipts retain them.
            self.server.operations.clear();other=p.reconstruct(self.store,self.req)
            for trigger in ('schedule','workflow_dispatch'):
                self.assertEqual('WAITING',control.reconcile(self.store,other,trigger=trigger,now=1089)['status'])
            out=control.reconcile(self.store,other,trigger='workflow_dispatch',now=1090)
        self.assertEqual('PASS',out['status']);self.assertTrue(out['leaseReleased'])
        self.assertEqual({},self.server.resources);self.assertIsNone(self.store.get(a.LEASE))
        deletes=self.compute_mutations('DELETE');self.assertEqual(13,len(deletes))
        self.assertEqual(['instances']*3+['disks']*6+['firewalls']*4,[url.urlsplit(e['url']).path.split('/')[-2] for e in deletes])
        self.assertTrue(all(url.urlsplit(e['url']).path.split('/')[-1].isdigit() for e in deletes))
        ledger=a.inspect_ledger(self.store.get(a.LEDGER)[1],domain='offline')
        self.assertEqual('FAIL',next(iter(ledger['attempts'].values()))['status'])

    def test_only_concrete_offline_api_is_admitted(self):
        class Lookalike: offline=True
        for transport in (Lookalike(),Network()):
            with self.assertRaisesRegex(ValueError,'not admitted'):p.OfflineApi(transport)
        with self.assertRaisesRegex(ValueError,'not admitted'):p.Store(self.cfg,Api(transport=self.server))
        native=deepcopy(self.req);native.update(execution=a.DOMAINS['native'],paidCloud=True)
        with self.assertRaises(ValueError):p.Provider(self.store,native)
        class Derived(p.Provider):pass
        with self.assertRaisesRegex(ValueError,'not admitted'):control.OfflineOwner(self.store,Derived(self.store,self.req),self.req)
        self.api.transport=Lookalike()
        with self.assertRaisesRegex(ValueError,'not admitted'):self.store.get(a.LEASE)
        self.assertEqual([],self.server.events)

    def test_config_closed_names_region_and_digest(self):
        for key,value in (('schema','gse-v51-provider-config-v1'),('project','a/b'),('region','us-east1'),('port',True),('imageId','123/4')):
            cfg=deepcopy(self.cfg);cfg[key]=value
            with self.assertRaises(ValueError):p.config(cfg)
        wrong=deepcopy(self.req);wrong['configurationSha256']='0'*64
        with self.assertRaisesRegex(ValueError,'digest changed'):p.Provider(self.store,wrong)
        cfg=deepcopy(self.cfg);cfg['credential']='secret'
        with self.assertRaises(ValueError):p.config(cfg)
        self.assertEqual([],self.server.events)

    def test_context_retained_before_first_insert_and_cannot_be_rebound(self):
        def fault(stage,event):
            if stage=='before' and event['method']=='POST' and 'compute.googleapis.com' in event['url']:
                found=self.store.get(p.context_key(self.req));self.assertEqual(p.context(self.cfg,self.req),found[1])
                lease=self.store.get(a.LEASE)[1];name=strict(event['body'])['name']
                self.assertTrue(next(r for r in lease['resources'] if r['spec']['name']==name)['attempted'])
        self.server.fault=fault;self.prepare();self.server.fault=lambda *args:None
        key=p.context_key(self.req);version,value=self.store.get(key);value['configuration']['zone']='us-east1-a'
        self.store.put(key,value,version)
        with self.assertRaises(ValueError):p.reconstruct(self.store,self.req)

    def test_missing_context_and_context_write_failure_prevent_inserts(self):
        with self.assertRaisesRegex(ValueError,'missing provider context'):p.reconstruct(self.store,self.req)
        def fault(stage,event):
            if stage=='before' and 'upload/storage' in event['url'] and 'provider-context.json' in event['url']:return 403,b''
        self.server.fault=fault
        with self.assertRaises(ApiError):self.prepare()
        self.assertEqual([],self.compute_mutations())
        # Context now precedes the initial lease CAS. A denied context write
        # leaves no owner or charge to reconcile, rather than an empty cleanup.
        self.assertIsNone(self.owner.cleanup_result);self.assertTrue(self.owner.closed)
        self.assertEqual('ApiError',self.owner.preparation_failure['type'])
        self.assertIsNone(self.store.get(a.LEASE));self.assertIsNone(self.store.get(a.LEDGER))
        self.assertEqual({},self.server.objects);self.assertEqual({},self.server.resources)

    def test_v51_or_escaped_object_paths_are_rejected_before_http(self):
        for key in ('v5.1-automatic/control/active.json',a.PREFIX+'../foreign',a.PREFIX+'x%2fy',a.PREFIX+'x?alt=media',a.PREFIX+'x//y'):
            with self.assertRaises(ValueError):self.store.get(key)
        self.assertEqual([],self.server.events)

    def test_conditional_store_write_read_and_delete(self):
        generation=control.put(self.store,a.LEASE,dict(original=True),0)
        self.assertEqual((generation,dict(original=True)),self.store.get(a.LEASE))
        with self.assertRaises(ApiError):self.store.put(a.LEASE,dict(replacement=True),0)
        with self.assertRaises(ApiError):self.store.delete(a.LEASE,generation+1)
        self.store.delete(a.LEASE,generation);self.assertIsNone(self.store.get(a.LEASE))
        reads=[url.parse_qs(url.urlsplit(e['url']).query) for e in self.server.events if 'alt=media' in e['url']]
        self.assertTrue(reads);self.assertTrue(all(v['generation']==v['ifGenerationMatch'] for v in reads))

    def test_metadata_media_race_does_not_read_new_generation(self):
        generation=self.store.put(a.LEASE,dict(original=True),0);changed=False
        def fault(stage,event):
            nonlocal changed
            if stage=='before' and 'alt=media' in event['url'] and not changed:
                changed=True;self.store.put(a.LEASE,dict(new=True),generation)
        self.server.fault=fault
        with self.assertRaises(ApiError) as error:self.store.get(a.LEASE)
        self.assertEqual(412,error.exception.status)

    def test_invalid_metadata_duplicate_json_and_truncation_reject(self):
        version=self.store.put(a.LEASE,dict(ok=True),0)
        base=self.server.metadata(a.LEASE,self.server.objects[a.LEASE])
        for field,value in (('name','foreign'),('bucket','foreign'),('generation','0'),('size','99999999'),('contentType','text/plain')):
            row=dict(base);row[field]=value
            self.server.fault=lambda stage,e,row=row:self.reply(row) if stage=='before' and e['url']==self.store.endpoint(a.LEASE) else None
            with self.assertRaises(ValueError):self.store.get(a.LEASE)
        self.server.fault=lambda *args:None
        for raw in (b'{"x":1,"x":2}',b'[]',b'{"x":NaN}'):
            self.server.objects[a.LEASE]=(version,raw,'application/json')
            with self.assertRaises(ValueError):self.store.get(a.LEASE)
        self.server.objects[a.LEASE]=(version,b'{"x":1}','application/json')
        self.server.fault=lambda stage,e:(200,b'{}') if stage=='before' and 'alt=media' in e['url'] else None
        with self.assertRaisesRegex(ValueError,'truncated'):self.store.get(a.LEASE)

    def test_lost_gcs_write_and_delete_replies_are_not_repeated(self):
        seen=set()
        def fault(stage,event):
            if stage=='after' and 'storage.googleapis.com' in event['url'] and event['method'] in ('POST','DELETE'):
                tag=(event['method'],event['url'],event['body'])
                if tag not in seen:seen.add(tag);raise ConnectionError('lost response')
        self.server.fault=fault;self.prepare();self.assertEqual('PASS',self.owner.close()['status'])
        events=[(e['method'],e['url'],e['body']) for e in self.server.events if e['method'] in ('POST','DELETE')]
        self.assertEqual(len(events),len(set(events)))

    def test_get_credential_refresh_is_bounded_mutation_is_never_replayed(self):
        counts={'GET':0,'POST':0}
        def fault(stage,event):
            if stage=='before':counts[event['method']]+=1;return 401,b''
        self.server.fault=fault
        with self.assertRaises(ApiError):self.store.get(a.LEASE)
        with self.assertRaises(ApiError):self.store.put(a.LEASE,dict(a=1),0)
        self.assertEqual(dict(GET=2,POST=1),counts)

    def test_lost_insert_reply_resolves_original_operation_then_cleans(self):
        lost=False
        def fault(stage,event):
            nonlocal lost
            if stage=='after' and event['method']=='POST' and 'compute.googleapis.com' in event['url'] and not lost:
                lost=True;raise ConnectionError('lost original insert')
        self.server.fault=fault
        with self.assertRaises(ConnectionError):self.prepare()
        self.assertEqual(1,len(self.compute_mutations()));self.assertEqual(1,len(self.compute_mutations('DELETE')))
        self.assertEqual('PASS',self.owner.cleanup_result['status']);self.assertEqual({},self.server.resources)

    def test_unknown_insert_outcome_keeps_original_lease(self):
        self.server.fault=lambda stage,e: (_ for _ in ()).throw(TimeoutError('before insert')) if stage=='before' and e['method']=='POST' and 'compute.googleapis.com' in e['url'] else None
        with self.assertRaises(TimeoutError):self.prepare()
        self.assertEqual('FAIL',self.owner.cleanup_result['status']);self.assertIsNotNone(self.store.get(a.LEASE))
        self.assertEqual(1,len(self.compute_mutations()));self.assertEqual([],self.compute_mutations('DELETE'))

    def test_operation_pagination_empty_page_then_original(self):
        op=self.server.operation(url.urlsplit(self.provider.scope(self.spec)).path,'firewalls',self.spec['name'],'123',self.provider.operation_id(self.spec),'insert')
        queries=[]
        def fault(stage,event):
            if stage=='before' and event['url'].startswith(self.operation_url()):
                queries.append(event['url']);page=url.parse_qs(url.urlsplit(event['url']).query).get('pageToken')
                return self.reply(dict(items=[op]) if page else dict(items=[],nextPageToken='next/+='))
        self.server.fault=fault;self.assertEqual('123',self.provider.operation(self.spec)['id'])
        self.assertEqual(2,len(queries));self.assertEqual(['next/+='],url.parse_qs(url.urlsplit(queries[-1]).query)['pageToken'])

    def test_operation_pagination_duplicate_and_cycle_reject(self):
        op=self.server.operation(url.urlsplit(self.provider.scope(self.spec)).path,'firewalls',self.spec['name'],'123',self.provider.operation_id(self.spec),'insert')
        for items in ([op],[]):
            self.server.fault=lambda stage,e:self.reply(dict(items=items,nextPageToken='loop')) if stage=='before' and e['url'].startswith(self.operation_url()) else None
            with self.assertRaisesRegex(ValueError,'ambiguous|page token'):self.provider.operation(self.spec)

    def test_operation_binding_cannot_change_request_target_id_or_poll_name(self):
        op=self.server.operation(url.urlsplit(self.provider.scope(self.spec)).path,'firewalls',self.spec['name'],'123',self.provider.operation_id(self.spec),'insert')
        for key,value in (('clientOperationId','foreign'),('operationType','delete'),('targetLink','https://evil/'),('name','../x'),('status','UNKNOWN'),('targetId',True)):
            changed=deepcopy(op);changed[key]=value
            with self.assertRaises(ValueError):self.provider.decode(self.spec,changed)
        pending=dict(op,status='RUNNING');changed=dict(op,name='other')
        self.server.fault=lambda stage,e:self.reply(changed) if stage=='before' and '/operations/' in e['url'] else None
        with self.assertRaisesRegex(ValueError,'name changed'):self.provider.wait(self.spec,pending,self.api.clock()+1)

    def test_pending_operation_poll_has_finite_original_deadline(self):
        op=self.server.operation(url.urlsplit(self.provider.scope(self.spec)).path,'firewalls',self.spec['name'],'123',self.provider.operation_id(self.spec),'insert');op['status']='RUNNING'
        with self.assertRaisesRegex(ValueError,'deadline'):self.provider.wait(self.spec,op,self.api.clock()+1)
        polls=[e for e in self.server.events if '/operations/' in e['url']]
        self.assertLessEqual(len(polls),4);self.assertEqual([],self.compute_mutations())

    def test_reused_name_and_changed_id_are_not_deleted(self):
        self.prepare();key=next(k for k in self.server.resources if k[1]=='instances');self.server.resources[key]['id']='9999999'
        out=self.owner.close();self.assertEqual('FAIL',out['status']);self.assertIn(key,self.server.resources)
        self.assertTrue(all('/9999999?' not in e['url'] for e in self.compute_mutations('DELETE')))
        self.assertIsNotNone(self.store.get(a.LEASE))

    def test_numeric_delete_does_not_delete_replacement_after_observation(self):
        self.prepare();original=next(v for (scope,kind,name),v in self.server.resources.items() if kind=='instances')
        key=next(k for k,v in self.server.resources.items() if v is original);old=original['id']
        def fault(stage,event):
            if stage=='before' and event['method']=='DELETE' and '/instances/'+old+'?' in event['url']:
                self.server.resources[key]=dict(original,id='987654321')
        self.server.fault=fault;out=self.owner.close()
        self.assertEqual('FAIL',out['status']);self.assertEqual('987654321',self.server.resources[key]['id'])
        self.assertTrue(all('/987654321?' not in e['url'] for e in self.compute_mutations('DELETE')))

    def test_foreign_spec_and_unowned_create_reject_before_compute_mutation(self):
        spec=deepcopy(self.spec);spec['name']='foreign'
        with self.assertRaises(ValueError):self.provider.describe(spec)
        with self.assertRaisesRegex(ValueError,'missing original ownership'):self.provider.create(self.spec,1300)
        self.assertEqual([],self.compute_mutations())
        with self.assertRaisesRegex(ValueError,'requires cleanup'):self.provider.delete(self.spec,'123')

    def test_body_does_not_impose_hard_lifetime_or_external_access(self):
        for spec in a.resources(self.req):
            body=self.provider.body(spec)
            if spec['kind']=='instance':
                self.assertNotIn('maxRunDuration',body['scheduling']);self.assertNotIn('instanceTerminationAction',body['scheduling'])
                self.assertEqual([],body['serviceAccounts']);self.assertEqual([],body['networkInterfaces'][0]['accessConfigs'])
                self.assertTrue(all(not d['autoDelete'] for d in body['disks']))
            if spec['kind']=='firewall' and spec['purpose']=='iap':self.assertEqual(['35.235.240.0/20'],body['sourceRanges'])

    def test_resource_security_and_layout_drift_reject(self):
        self.prepare()
        instance=next(v for k,v in self.server.resources.items() if k[1]=='instances')
        spec=self.provider.specs[instance['name']]
        changes=(lambda v:v.update(description='foreign'),lambda v:v.update(serviceAccounts=[dict(email='x')]),
            lambda v:v['networkInterfaces'][0].update(accessConfigs=[dict(natIP='1.1.1.1')]),
            lambda v:v['disks'][0].update(autoDelete=True),lambda v:v['disks'][0].update(source='https://evil/disk'),
            lambda v:v['scheduling'].update(maxRunDuration=dict(seconds='60')),
            lambda v:v['metadata']['items'].append(dict(key='startup-script',value='foreign')))
        for mutate in changes:
            changed=deepcopy(instance);mutate(changed)
            with self.assertRaises(ValueError):self.provider.inspect(spec,changed)
        disk=next(v for k,v in self.server.resources.items() if k[1]=='disks' and 'sourceImageId' in v)
        changed=dict(disk,sourceImageId='999');
        with self.assertRaisesRegex(ValueError,'image ID'):self.provider.inspect(self.provider.specs[disk['name']],changed)
        firewall=next(v for k,v in self.server.resources.items() if k[1]=='firewalls')
        with self.assertRaises(ValueError):self.provider.inspect(self.provider.specs[firewall['name']],dict(firewall,priority=100))

    def test_pinned_deprecated_image_allowed_but_obsolete_or_replaced_reject(self):
        self.server.image['deprecated']=dict(state='DEPRECATED');self.prepare();self.owner.close()
        for change in (dict(id='999'),dict(deprecated=dict(state='OBSOLETE')),dict(status='PENDING')):
            self.setUp();self.server.image.update(change)
            with self.assertRaisesRegex(ValueError,'image'):self.prepare()
            # Four firewall inserts precede boot-image validation; no disk/VM
            # mutation can be issued after the image check rejects.
            self.assertEqual(4,len(self.compute_mutations()));self.assertEqual('PASS',self.owner.cleanup_result['status'])

    def test_lost_delete_reply_does_not_resubmit_or_release_early(self):
        self.prepare();lost=False
        def fault(stage,event):
            nonlocal lost
            if stage=='after' and event['method']=='DELETE' and 'compute.googleapis.com' in event['url'] and not lost:
                lost=True;raise ConnectionError('lost delete')
        self.server.fault=fault;out=self.owner.close();self.assertEqual('FAIL',out['status'])
        self.assertIsNotNone(self.store.get(a.LEASE));before=len(self.compute_mutations('DELETE'))
        self.server.fault=lambda *args:None
        out=control.reconcile(self.store,p.reconstruct(self.store,self.req),trigger='workflow_dispatch',now=1090)
        self.assertEqual('PASS',out['status']);self.assertEqual(before,len(self.compute_mutations('DELETE')))

    def test_retained_operation_from_other_attempt_cannot_authorize_cleanup(self):
        self.prepare();key=self.provider.receipt_key(self.spec);generation,value=self.store.get(key)
        value['operation']['clientOperationId']='foreign';self.store.put(key,value,generation)
        out=self.owner.close();self.assertEqual('FAIL',out['status'])
        self.assertTrue(any(k[2]==self.spec['name'] for k in self.server.resources))

    def reconstructed_create(self, spec):
        provider=p.reconstruct(self.store,self.req);provider.wall=lambda:1000;provider.sleep=self.server.sleep
        return provider.create(spec,1300)

    def original_intent(self, spec):
        self.owner.acquire(previous_cost=0,cost=1)
        lease=deepcopy(self.owner.lease)
        for row in lease['resources']:
            row['attempted']=True
            if row['spec']==spec:break
        self.owner.persist(lease)

    def test_original_insert_cannot_be_reissued_after_lost_reply(self):
        self.original_intent(self.spec)
        def fault(stage,event):
            if stage=='after' and event['method']=='POST' and 'compute.googleapis.com' in event['url']:
                raise ConnectionError('lost original response')
        self.server.fault=fault
        with self.assertRaises(ConnectionError):self.provider.create(self.spec,1300)
        self.server.fault=lambda *args:None
        with self.assertRaisesRegex(ValueError,'already submitted'):
            self.reconstructed_create(self.spec)
        self.assertEqual(1,len(self.compute_mutations()))

    def test_expiry_during_image_observation_prevents_insert(self):
        spec=next(s for s in a.resources(self.req) if s['kind']=='disk')
        self.original_intent(spec);now=[1000];self.provider.wall=lambda:now[0]
        def fault(stage,event):
            if stage=='after' and '/global/images/' in event['url']:now[0]=1061
        self.server.fault=fault
        with self.assertRaisesRegex(ValueError,'not owned/charged'):self.provider.create(spec,1300)
        self.assertEqual([],self.compute_mutations())

    def test_cleanup_mode_alone_cannot_delete_active_lease(self):
        self.original_intent(self.spec);answer=self.provider.create(self.spec,1300)
        lease=deepcopy(self.owner.lease);lease['resources'][0]['id']=answer['id'];self.owner.persist(lease)
        self.provider.begin_cleanup()
        with self.assertRaisesRegex(ValueError,'cleanup ownership'):self.provider.delete(self.spec,answer['id'])
        self.assertEqual([],self.compute_mutations('DELETE'))

    def test_failed_submission_retention_never_issues_insert(self):
        def fault(stage,event):
            if stage=='before' and event['method']=='POST' and '-submitted.json' in event['url']:
                return 403,b'sensitive provider detail'
        self.server.fault=fault
        with self.assertRaises(ApiError) as error:self.prepare()
        self.assertNotIn('sensitive',str(error.exception))
        self.assertEqual([],self.compute_mutations());self.assertEqual('PASS',self.owner.cleanup_result['status'])
        self.assertIsNone(self.store.get(a.LEASE))

    def test_operation_receipt_failure_preserves_resource_until_retention_recovers(self):
        def fault(stage,event):
            if stage=='before' and event['method']=='POST' and '%2Foperations%2F' in event['url'] and '-submitted' not in event['url']:
                return 403,b''
        self.server.fault=fault
        with self.assertRaises(ApiError):self.prepare()
        self.assertEqual(1,len(self.server.resources));self.assertEqual('FAIL',self.owner.cleanup_result['status'])
        self.server.fault=lambda *args:None
        result=control.reconcile(self.store,p.reconstruct(self.store,self.req),trigger='workflow_dispatch',now=1090)
        self.assertEqual('PASS',result['status']);self.assertEqual({},self.server.resources)
        self.assertEqual(1,len(self.compute_mutations()))

    def test_lost_lease_delete_reply_never_removes_new_owner(self):
        self.prepare();other=fixture(attempt='d'*32);other['configurationSha256']=self.req['configurationSha256']
        replacement=a.lease(other,1000);replaced=False
        def fault(stage,event):
            nonlocal replaced
            if stage=='after' and event['method']=='DELETE' and self.store.endpoint(a.LEASE)+'?' in event['url'] and not replaced:
                replaced=True;control.put(self.store,a.LEASE,replacement,0);raise ConnectionError('lost old release')
        self.server.fault=fault;result=self.owner.close()
        self.assertEqual('PASS',result['status']);self.assertEqual(replacement,self.store.get(a.LEASE)[1])
        releases=[e for e in self.server.events if e['method']=='DELETE' and self.store.endpoint(a.LEASE)+'?' in e['url']]
        self.assertEqual(1,len(releases))

    def test_unending_operation_pages_stop_at_bound(self):
        pages=[]
        def fault(stage,event):
            if stage=='before' and event['url'].startswith(self.operation_url()):
                pages.append(event['url']);return self.reply(dict(items=[],nextPageToken='page-'+str(len(pages))))
        self.server.fault=fault
        with self.assertRaisesRegex(ValueError,'page bound'):self.provider.operation(self.spec)
        self.assertEqual(32,len(pages));self.assertEqual([],self.compute_mutations())

    def test_provider_configuration_mutation_is_rejected(self):
        self.provider.config['project']='foreign-project'
        with self.assertRaisesRegex(ValueError,'configuration changed'):self.provider.describe(self.spec)
        self.assertEqual([],self.server.events)

    def test_cleaning_proves_unsubmitted_intent_but_active_owner_cannot(self):
        self.original_intent(self.spec)
        self.assertEqual('UNKNOWN',self.provider.operation(self.spec)['state'])
        self.provider.begin_cleanup()
        self.assertEqual('UNKNOWN',self.provider.operation(self.spec)['state'])
        lease=deepcopy(self.owner.lease);lease['phase']='CLEANING';self.owner.persist(lease)
        result=self.provider.operation(self.spec)
        self.assertEqual(dict(spec=self.spec,state='DONE',id=None),result)
        # A delayed writer can still persist its pre-POST marker, but must fail
        # the subsequent active-lease check. Retain the earlier fenced proof.
        key=self.provider.receipt_key(self.spec).replace('.json','-submitted.json')
        control.put(self.store,key,dict(schema='gse-v52-provider-submission-v1',spec=self.spec),0)
        self.assertEqual(result,p.reconstruct(self.store,self.req).operation(self.spec))
        self.assertEqual([],self.compute_mutations())

    def test_owner_and_provider_requests_must_match_before_reservation(self):
        other=fixture(attempt='d'*32);other['configurationSha256']=self.req['configurationSha256']
        with self.assertRaisesRegex(ValueError,'provider request changed'):
            control.OfflineOwner(self.store,self.provider,other,wall=lambda:1000)
        self.assertEqual([],self.server.events)


if __name__=='__main__':unittest.main()
