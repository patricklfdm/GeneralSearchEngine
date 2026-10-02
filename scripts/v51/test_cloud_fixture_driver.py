from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from urllib.parse import urlsplit,parse_qs
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
        for status in (200,400,401,404,409,412,429,500,503):
            with self.subTest(status=status):
                value,clock,http,reader,api,invocation=fixture();root=self.root/str(status)
                prepared=f.execute(value,api,root/'prepared',now=clock.wall(),sleep=clock.sleep)
                self.assertEqual('PREPARED',prepared['status'])
                binding=entry.identity(value['configuration'],invocation['env'],trigger='manual',source=invocation['source'],checkout=invocation['checkout'])
                probe=probes.OfflineApi(value['configuration'],binding,n.validate_request(value['request']),
                    transport=ManualTransport(http,value['request'],status),tokens=lambda _: 'offline-token',clock=clock.seconds)
                result=probes.run(value['configuration'],probe,root/'probes',now=clock.wall())
                self.assertEqual('FAIL',result['status']);self.assertEqual('overwrite-denied',result['failure']['phase'])
                self.assertEqual(status,result['cases'][-1]['httpStatus'])
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


if __name__=='__main__':unittest.main()
