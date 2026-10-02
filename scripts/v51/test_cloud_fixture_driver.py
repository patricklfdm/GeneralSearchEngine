from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from urllib.parse import urlsplit,parse_qs,urlencode
from . import cloud_fixture_driver as f, cloud_object_probes as probes
from . import cloud_http as h, cloud_native_authority as n
from . import cloud_cleanup_entry as entry, cloud_cleanup_qualification as q
from . import cloud_native_cleanup as cleanup, cloud_runner, performance_model as m


from .cloud_fixture_driver_qualification import fixture, ManualTransport

class FixtureDriverTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.value,self.clock,self.http,self.reader,self.api,self.invocation=fixture()
    def prepare(self,name='prepared'):
        return f.execute(self.value,self.api,self.root/name,now=self.clock.wall(),sleep=self.clock.sleep)
    def probe(self,result,denial=403,name='probes'):
        cfg=self.value['configuration'];v=self.invocation
        binding=entry.identity(cfg,v['env'],trigger='manual',source=v['source'],checkout=v['checkout'])
        api=probes.OfflineApi(cfg,binding,n.validate_request(self.value['request']),
            transport=ManualTransport(self.http,self.value['request'],denial),tokens=lambda _: 'offline-token',clock=self.clock.seconds)
        return probes.run(cfg,api,self.root/name,now=self.clock.wall()),api

    def test_once_only_single_disk_then_existing_expired_reconciler(self):
        result=self.prepare();self.assertEqual('PREPARED',result['status'],result)
        self.assertEqual((1,1),(self.http.inserts,len(self.http.resources)))
        self.assertEqual(100,sum(int(v['sizeGb']) for v in self.http.resources.values()))
        lease=self.api.store.get(n.LEASE)[1];self.assertEqual(1,sum(r['attempted'] for r in lease['resources']))
        before=q.snapshot(self.http)
        waiting=cleanup.reconcile(self.api.cfg,self.reader,self.root/'active',trigger='manual',now=self.clock.wall())
        self.assertEqual('WAITING',waiting['status']);self.assertEqual(before,q.snapshot(self.http))
        self.clock.sleep(5400)
        waiting=cleanup.reconcile(self.api.cfg,self.reader,self.root/'grace',trigger='manual',now=self.clock.wall())
        self.assertEqual('WAITING',waiting['status']);self.assertEqual(before,q.snapshot(self.http))
        self.clock.sleep(1080)
        gone=cleanup.reconcile(self.api.cfg,self.reader,self.root/'expired',trigger='manual',now=self.clock.wall())
        self.assertEqual('PASS',gone['status']);self.assertEqual({},self.http.resources)
        total,attempts=n.inspect_ledger(f.Store(self.api.cfg,self.reader,self.value['request']).get(n.LEDGER)[1])
        self.assertEqual(f.COST,total);self.assertEqual('FAIL',attempts[n.validate_request(self.value['request'])]['status'])

    def test_request_tampering_expiry_and_price_coverage_fail_before_writes(self):
        for change in (lambda v:v.update(maximumCostMicrousd=2_000_000),lambda v:v.update(operator='gse-v51-runner@example.com'),
                       lambda v:v['request'].update(source='d'*40),lambda v:v.update(paidAdmission=True),
                       lambda v:v['prices'].update(region='us-central1'),lambda v:v['prices'].update(pricedThroughSeconds=60),
                       lambda v:v['prices']['otherCostsMicrousd'].pop('failureOverhang'),
                       lambda v:v['prices'].update(diskMicrousdPerGiBHour=100000),
                       lambda v:v['qualificationManifest'].update(graceSeconds=1)):
            value=deepcopy(self.value);change(value)
            with self.subTest(value=value),self.assertRaises(ValueError):f.validate(value,now=self.clock.wall())
        with self.assertRaises(ValueError):f.validate(self.value,now=self.value['expiresAt'])
        self.assertEqual(0,self.http.inserts)

    def test_write_order_and_generic_policy_cannot_expand_resource_scope(self):
        with self.assertRaises(ValueError):self.api.upload(n.LEDGER,self.api.reserved,0)
        with self.assertRaises(ValueError):self.api.insert(self.api.provider(),self.api.disk)
        for method,url,body in [('DELETE',self.api.store.url(n.LEASE),None),
                ('POST','https://compute.googleapis.com/compute/v1/projects/offline-project/zones/us-west4-a/disks',{}),
                ('GET','https://storage.googleapis.com/storage/v1/b/foreign/o/x',None)]:
            for call in (self.api.call,lambda *args,**kw:h.Api.call(self.api,*args,**kw)):
                with self.assertRaises(ValueError):call(method,url,body,deadline=self.clock.seconds()+30)
        self.assertFalse(self.http.resources)

    def test_lost_insert_reply_retains_original_authority_without_retry(self):
        send=self.http.send
        def lose(method,url,*args):
            response=send(method,url,*args)
            if method=='POST' and url.startswith('https://compute.googleapis.com'):raise ConnectionError('secret-token-not-retained')
            return response
        self.http.send=lose
        result=self.prepare();self.assertEqual('FAIL',result['status']);self.assertEqual('disk',result['failure']['phase'])
        self.assertEqual(1,self.http.inserts);self.assertEqual(1,len(self.http.resources))
        self.assertNotIn('secret-token',(self.root/'prepared/receipt.json').read_text())
        with self.assertRaises(ValueError):self.api.insert(self.api.provider(),self.api.disk)
        self.http.send=send;self.clock.sleep(6480)
        gone=cleanup.reconcile(self.api.cfg,self.reader,self.root/'expired',trigger='manual',now=self.clock.wall())
        self.assertEqual('PASS',gone['status']);self.assertEqual(1,self.http.inserts);self.assertFalse(self.http.resources)

    def test_lost_reservation_and_lease_conflict_never_create_disk(self):
        for kind in ('reservation','lease'):
            with self.subTest(kind=kind):
                value,clock,http,reader,api,_=fixture();send=http.send
                def fail(method,url,*args):
                    if method=='POST' and 'storage.googleapis.com' in url:
                        key=parse_qs(urlsplit(url).query)['name'][0]
                        if key==n.LEASE and kind=='lease':return 412,b''
                        if key==n.LEDGER and kind=='reservation':
                            send(method,url,*args);raise ConnectionError('lost reservation')
                    return send(method,url,*args)
                http.send=fail;result=f.execute(value,api,self.root/kind,now=clock.wall(),sleep=clock.sleep)
                self.assertEqual('FAIL',result['status']);self.assertEqual(0,http.inserts)
                self.assertFalse(any(r['method']=='DELETE' for r in http.requests))
                if kind=='reservation':
                    self.assertIn(n.LEASE,http.objects);self.assertIn(n.LEDGER,http.objects)
                    http.send=send;clock.sleep(6480)
                    ended=cleanup.reconcile(api.cfg,reader,self.root/'incomplete-context',trigger='manual',now=clock.wall())
                    self.assertEqual('PASS',ended['status']);self.assertFalse(http.resources);self.assertEqual(0,http.inserts)
                    total,attempts=n.inspect_ledger(f.Store(api.cfg,reader,value['request']).get(n.LEDGER)[1])
                    self.assertEqual(f.COST,total);self.assertEqual('FAIL',attempts[n.validate_request(value['request'])]['status'])

    def test_existing_or_changed_state_cannot_be_overwritten(self):
        self.http.objects[n.LEASE]=(99,m.canonical(self.api.lease),'application/json')
        before=q.snapshot(self.http);result=self.prepare()
        self.assertEqual('FAIL',result['status']);self.assertEqual(before,q.snapshot(self.http))

    def test_completed_preparation_cannot_repeat_with_another_output_directory(self):
        first=self.prepare();self.assertEqual('PREPARED',first['status'])
        original=q.snapshot(self.http)
        api=f.PreparationApi(self.value,self.clock.wall(),transport=self.http,tokens=lambda _: 'offline-token',clock=self.clock.seconds)
        second=f.execute(self.value,api,self.root/'repeat',now=self.clock.wall(),sleep=self.clock.sleep)
        self.assertEqual('FAIL',second['status']);self.assertEqual(original,q.snapshot(self.http));self.assertEqual(1,self.http.inserts)

    def test_lost_canary_reply_does_not_allocate_or_replay_a_write(self):
        send=self.http.send;key=f.objects(self.value['request'])['outside']
        def lose(method,url,*args):
            result=send(method,url,*args)
            if method=='POST' and parse_qs(urlsplit(url).query).get('name')==[key]:raise ConnectionError('lost canary response')
            return result
        self.http.send=lose;result=self.prepare()
        self.assertEqual('FAIL',result['status']);self.assertEqual('canary-outside',result['failure']['phase'])
        self.assertEqual(0,self.http.inserts);self.assertIn(key,self.http.objects)
        with self.assertRaises(ValueError):self.api.upload(key,f.canary(self.value['request'],'outside'),0)

    def test_network_confirmation_and_source_ci_gates_precede_credentials(self):
        value=deepcopy(self.value);value['execution']='operator-single-disk-request'
        value['before']['execution']='read-only-native-cleanup-observation'
        with patch.object(f.time,'time',self.clock.wall),patch.object(f.c,'read',return_value=value['configuration']),\
             patch.object(f,'checkout',return_value=value['request']['source']),patch.object(f,'operator_account'),\
             patch.object(f.ci,'collect',side_effect=ValueError('source not protected')) as collect,\
             patch.object(h.Network,'send',side_effect=AssertionError('network credentials before gate')) as send:
            with self.assertRaises(ValueError):f.NetworkPreparationApi(value,confirmation='0'*64)
            collect.assert_not_called()
            with self.assertRaisesRegex(ValueError,'source not protected'):
                f.NetworkPreparationApi(value,confirmation=f.validate(value,now=self.clock.wall()))
            collect.assert_called_once();send.assert_not_called()

    def test_operator_account_rejects_ambient_credential_overrides(self):
        with patch.object(f.p,'principal',return_value=self.value['operator']),\
             patch.dict(f.os.environ,{},clear=True),patch.object(f.subprocess,'run') as command:
            command.return_value=Mock(returncode=0,stdout=b'(unset)\n')
            f.operator_account(self.value['operator']);self.assertEqual(3,command.call_count)
            with patch.dict(f.os.environ,{'CLOUDSDK_AUTH_ACCESS_TOKEN':'not-a-real-token'}),self.assertRaises(ValueError):
                f.operator_account(self.value['operator'])
            self.assertEqual(3,command.call_count)
            for index in range(3):
                command.side_effect=[Mock(returncode=0,stdout=b'(unset)\n')]*index+[Mock(returncode=0,stdout=b'override')]
                with self.subTest(index=index),self.assertRaises(ValueError):f.operator_account(self.value['operator'])
            command.side_effect=None;command.return_value=Mock(returncode=1,stdout=b'')
            with self.assertRaises(ValueError):f.operator_account(self.value['operator'])

    def test_network_constructor_rejects_offline_wrong_confirmation_and_overrides(self):
        with patch.object(f.h.Network,'send',side_effect=AssertionError('network')):
            with self.assertRaises(ValueError):f.NetworkPreparationApi(self.value,confirmation='0'*64)
            for key in ('tokens','transport','clock','now','force'):
                with self.subTest(key=key),self.assertRaises(TypeError):f.NetworkPreparationApi(self.value,confirmation='0'*64,**{key:True})
        network=object.__new__(f.NetworkPreparationApi);network.transport=Mock(offline=False)
        store=f.Store(self.api.cfg,network,self.value['request'])
        for domain in (f.a,n):
            with self.assertRaises(ValueError):cloud_runner.adapters(store,Mock(execution=store.execution),authority=domain)

    def test_manual_probes_need_independent_unchanged_canaries(self):
        prepared=self.prepare();self.assertEqual('PREPARED',prepared['status'],prepared)
        result,api=self.probe(prepared);self.assertEqual('PROBES_RECORDED',result['status'],result)
        after=probes.capture(self.value['configuration'],result['manifest'],api=self.reader,wall=self.clock.wall)
        verified=probes.review(self.value['configuration'],result,after)
        self.assertEqual('OBJECT_SCOPE_MATCH',verified['status']);self.assertFalse(verified['objectPermissionsQualified'])
        for change in (lambda v:v['objects']['outside'][1].update(changed=True),
                       lambda v:v['objects']['outside'].__setitem__(0,v['objects']['outside'][0]+1),
                       lambda v:v['objects'].pop('outside'),lambda v:v.update(requestSha256='0'*64)):
            damaged=deepcopy(after)
            # Local Store returns tuples; JSON round-trip mirrors downloaded evidence.
            damaged=m.strict_json(m.canonical(damaged));change(damaged)
            with self.assertRaises(ValueError):probes.review(self.value['configuration'],result,damaged)
        repeated,_=self.probe(prepared,name='repeated');self.assertEqual('FAIL',repeated['status'])
        for change in (lambda v:v.update(execution='unrecognized'),lambda v:v.update(cleanupReady=True),
                       lambda v:v['binding'].update(serviceAccount='foreign@example.com'),
                       lambda v:v['cases'].pop()):
            damaged=deepcopy(result);change(damaged)
            with self.assertRaises(ValueError):probes.review(self.value['configuration'],damaged,after)
        damaged=deepcopy(result);changed_after=deepcopy(after)
        damaged['created'][1]['kind']='existing';changed_after['objects']['created'][1]['kind']='existing'
        with self.assertRaises(ValueError):probes.review(self.value['configuration'],damaged,changed_after)

    def test_precondition_auth_missing_or_unavailable_is_not_permission_denial(self):
        for status in (200,204,400,401,404,409,412,429,500,503):
            with self.subTest(status=status):
                value,clock,http,reader,api,invocation=fixture();root=self.root/str(status)
                prepared=f.execute(value,api,root/'prepared',now=clock.wall(),sleep=clock.sleep)
                self.assertEqual('PREPARED',prepared['status'])
                binding=entry.identity(value['configuration'],invocation['env'],trigger='manual',source=invocation['source'],checkout=invocation['checkout'])
                probe=probes.OfflineApi(value['configuration'],binding,n.validate_request(value['request']),
                    transport=ManualTransport(http,value['request'],status),tokens=lambda _: 'offline-token',clock=clock.seconds)
                result=probes.run(value['configuration'],probe,root/'probes',now=clock.wall())
                self.assertEqual('FAIL',result['status']);self.assertEqual('overwrite-denied',result['failure']['phase'])
                self.assertEqual(None if status in (200,204) else status,result['cases'][-1]['httpStatus'])
                if status in (200,204):self.assertEqual('UNEXPECTED_SUCCESS',result['cases'][-1]['outcome'])
                self.assertEqual(1,len(http.resources))

    def test_probe_policy_cannot_touch_control_objects_or_unbound_paths(self):
        prepared=self.prepare();result,api=self.probe(prepared)
        for method,url,body in [('DELETE',api.base+'arbitrary',None),('POST','https://storage.googleapis.com/upload/storage/v1/b/offline-evidence/o',{}),
                               ('GET','https://compute.googleapis.com/compute/v1/projects/offline-project',None)]:
            with self.assertRaises(ValueError):api.call(method,url,body,deadline=self.clock.seconds()+30)
        for key in ('tokens','transport','clock','force'):
            with self.subTest(key=key),self.assertRaises(TypeError):probes.NetworkApi({},None,{},None,'a'*64,**{key:True})

    def test_optional_probe_workflow_preserves_reconciliation(self):
        text=probes.workflow(self.value['configuration'])
        self.assertIn('object_probe_request:',text)
        self.assertIn('"$OBJECT_PROBE_REQUEST"',text)
        self.assertNotIn('--force',text)
        self.assertEqual(1,text.count('Reconcile retained expired lease'))
        self.assertIn('concurrency:\n  group: v51-native-cleanup\n  cancel-in-progress: false',text)
        self.assertIn('environment: v51-cloud-manual-cleanup',text)


class ObjectProbeGenerationTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def prepared(self,name,*,preconditions_first=True,allow=()):
        value,clock,http,reader,api,invocation=fixture();cfg=value['configuration']
        prepared=f.execute(value,api,self.root/name/'prepared',now=clock.wall(),sleep=clock.sleep)
        self.assertEqual('PREPARED',prepared['status'])
        keys=f.objects(value['request'])
        transport=ManualTransport(http,value['request'],preconditions_first=preconditions_first,
                                  allow=[(method,keys[kind]) for method,kind in allow])
        binding=entry.identity(cfg,invocation['env'],trigger='manual',source=invocation['source'],checkout=invocation['checkout'])
        probe=probes.OfflineApi(cfg,binding,n.validate_request(value['request']),transport=transport,
                               tokens=lambda _: 'offline-token',clock=clock.seconds)
        return value,clock,http,reader,prepared,probe

    def test_permission_denials_with_either_provider_check_order(self):
        for first in (True,False):
            with self.subTest(preconditions_first=first):
                value,clock,http,reader,prepared,probe=self.prepared(str(first),preconditions_first=first)
                result=probes.run(value['configuration'],probe,self.root/str(first)/'probe',now=clock.wall())
                self.assertEqual('PROBES_RECORDED',result['status'],result)
                self.assertEqual(list(probes.CASES),[r['case'] for r in result['cases']])
                after=probes.capture(value['configuration'],prepared['probeManifest'],api=reader,wall=clock.wall)
                self.assertEqual('OBJECT_SCOPE_MATCH',probes.review(value['configuration'],result,after)['status'])

    def test_each_unexpected_permission_stops_after_one_request_and_only_touches_canaries(self):
        cases=(('overwrite-denied','POST','existing'),('delete-denied','DELETE','existing'),
               ('outside-read-denied','GET','outside'),('outside-write-denied','POST','outside'),
               ('outside-delete-denied','DELETE','outside'))
        for name,method,kind in cases:
            with self.subTest(case=name):
                value,clock,http,reader,prepared,probe=self.prepared(name,allow=[(method,kind)])
                keys=f.objects(value['request']);original=deepcopy(http.objects);resources=deepcopy(http.resources)
                result=probes.run(value['configuration'],probe,self.root/name/'probe',now=clock.wall())
                self.assertEqual('FAIL',result['status']);self.assertEqual(name,result['failure']['phase'])
                self.assertEqual('UNEXPECTED_SUCCESS',result['cases'][-1]['outcome'])
                self.assertIsNone(result['cases'][-1]['httpStatus'])
                self.assertEqual(probes.CASES.index(name)+1,len(result['cases']))
                self.assertEqual(1,sum(r['method']==method and r['key']==keys[kind] for r in probe.transport.requests))
                self.assertEqual(resources,http.resources);self.assertEqual(1,http.inserts)
                for key,old in original.items():
                    if key==keys[kind] and method!='GET':
                        if method=='DELETE':self.assertNotIn(key,http.objects)
                        else:
                            self.assertNotEqual(old[0],http.objects[key][0]);self.assertEqual(old[1:],http.objects[key][1:])
                    else:self.assertEqual(old,http.objects[key])
                self.assertEqual(set(original)|{keys['created']},set(http.objects)|({keys[kind]} if method=='DELETE' else set()))
                after=probes.capture(value['configuration'],prepared['probeManifest'],api=reader,wall=clock.wall)
                with self.assertRaises(ValueError):probes.review(value['configuration'],result,after)

    def test_generation_drift_fails_without_refreshing_or_mutating_new_version(self):
        for kind,phase in (('existing','overwrite-denied'),('outside','outside-write-denied')):
            with self.subTest(kind=kind):
                value,clock,http,reader,prepared,probe=self.prepared(kind)
                key=f.objects(value['request'])[kind];send=probe.transport.send
                def drift(method,url,*args):
                    if method=='POST' and parse_qs(urlsplit(url).query).get('name')==[key]:
                        gen,body,content=http.objects[key];http.objects[key]=(gen+100,body,content)
                    return send(method,url,*args)
                probe.transport.send=drift
                result=probes.run(value['configuration'],probe,self.root/kind/'probe',now=clock.wall())
                self.assertEqual('FAIL',result['status']);self.assertEqual(phase,result['failure']['phase'])
                self.assertEqual(412,result['cases'][-1]['httpStatus'])
                attempts=[r for r in probe.transport.requests if r['method']=='POST' and r['key']==key]
                self.assertEqual(1,len(attempts))
                self.assertEqual([str(prepared['probeManifest']['baseline'][kind][0])],attempts[0]['query']['ifGenerationMatch'])
                self.assertEqual(prepared['probeManifest']['baseline'][kind][0]+100,http.objects[key][0])

    def test_independent_review_rejects_outside_drift_even_if_provider_checks_permissions_first(self):
        value,clock,http,reader,prepared,probe=self.prepared('outside-drift',preconditions_first=False)
        key=f.objects(value['request'])['outside'];gen,body,content=http.objects[key]
        http.objects[key]=(gen+1,body,content)
        result=probes.run(value['configuration'],probe,self.root/'probe',now=clock.wall())
        self.assertEqual('PROBES_RECORDED',result['status'])
        after=probes.capture(value['configuration'],prepared['probeManifest'],api=reader,wall=clock.wall)
        with self.assertRaisesRegex(ValueError,'independent bytes/generations changed'):
            probes.review(value['configuration'],result,after)

    def test_lost_mutation_response_retains_failure_and_cannot_be_replayed(self):
        for method in ('POST','DELETE'):
            with self.subTest(method=method):
                value,clock,http,reader,prepared,probe=self.prepared(method,allow=[(method,'existing')])
                key=f.objects(value['request'])['existing'];send=probe.transport.send
                def lose(actual,url,*args):
                    result=send(actual,url,*args)
                    if actual==method and probe.transport.requests[-1]['key']==key:raise ConnectionError('lost mutation response')
                    return result
                probe.transport.send=lose
                result=probes.run(value['configuration'],probe,self.root/method/'probe',now=clock.wall())
                self.assertEqual('FAIL',result['status']);self.assertEqual('ConnectionError',result['failure']['type'])
                self.assertEqual('overwrite-denied' if method=='POST' else 'delete-denied',result['failure']['phase'])
                self.assertEqual(1,sum(r['method']==method and r['key']==key for r in probe.transport.requests))
                prior=deepcopy(http.objects)
                fresh=probes.OfflineApi(value['configuration'],probe.binding,probe.sha,transport=probe.transport,
                                       tokens=lambda _: 'offline-token',clock=clock.seconds)
                repeat=probes.run(value['configuration'],fresh,self.root/method/'repeat',now=clock.wall())
                self.assertEqual('FAIL',repeat['status']);self.assertEqual([],repeat['cases'])
                self.assertEqual(prior,http.objects);self.assertEqual(1,http.inserts)

    def test_policy_rejects_unapproved_versions_bodies_and_authority_keys(self):
        value,clock,http,reader,prepared,probe=self.prepared('policy')
        probe.bind(prepared['probeManifest']);before=deepcopy(http.objects)
        method,url,body=probes.operations(value['configuration'],prepared['probeManifest'])[3][1:4]
        base=url.split('?',1)[0];query={k:v[0] for k,v in parse_qs(urlsplit(url).query).items()}
        mutations=[]
        for generation in (None,'0',str(int(query['ifGenerationMatch'])+1)):
            changed=dict(query)
            if generation is None:changed.pop('ifGenerationMatch')
            else:changed['ifGenerationMatch']=generation
            mutations.append((method,base+'?'+urlencode(changed),body))
        mutations.append((method,url,dict(body,changed=True)))
        for key in (n.LEASE,n.LEDGER,f.objects(value['request'])['manifest']):
            mutations.append((method,base+'?'+urlencode(dict(query,name=key)),body))
        for request in mutations:
            with self.subTest(request=request):
                probe.expected=deepcopy(request)
                with self.assertRaises(ValueError):probe.call(*request,deadline=clock.seconds()+30)
        self.assertEqual(before,http.objects);self.assertEqual([],probe.transport.requests)

    def test_old_approval_cannot_be_reinterpreted_as_generation_bound_authorization(self):
        value,clock,http,reader,prepared,probe=self.prepared('legacy')
        legacy=deepcopy(value);legacy['schema']='gse-v51-single-disk-request-v1'
        legacy['qualificationManifest']['schema']='gse-v51-single-disk-manifest-v1'
        legacy['qualificationManifest'].pop('objectProbePolicy')
        legacy['request']['bundleSha256']=m.sha(m.canonical(legacy['qualificationManifest']))
        with self.assertRaisesRegex(ValueError,'fixture request drift'):f.validate(legacy,now=clock.wall())
        for field in ('schema','policy','nested-request'):
            manifest=deepcopy(prepared['probeManifest'])
            if field=='schema':manifest['schema']='gse-v51-object-probe-manifest-v1'
            elif field=='policy':manifest['fixtureRequest']['qualificationManifest']['objectProbePolicy']='generation-zero'
            else:manifest['fixtureRequest']=legacy;manifest['fixtureSha256']=m.sha(m.canonical(legacy))
            key=f.objects(value['request'])['manifest'];gen,_,content=http.objects[key]
            http.objects[key]=(gen,m.canonical(manifest),content);original=deepcopy(http.objects)
            with self.subTest(field=field):
                result=probes.run(value['configuration'],probe,self.root/field,now=clock.wall())
                self.assertEqual('FAIL',result['status']);self.assertEqual([],result['cases'])
                self.assertEqual(original,http.objects)
        self.assertFalse(any(r['method']!='GET' for r in probe.transport.requests))


if __name__=='__main__':unittest.main()
