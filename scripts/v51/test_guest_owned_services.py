import io
from copy import deepcopy
from pathlib import Path
import tarfile
import tempfile
import time
import unittest
from . import cloud_authority as a, cloud_fake, cloud_gcp, cloud_runner, cloud_package as package
from . import guest_startup, guest_startup_fake as fake, guest_owned_services as owned
from . import guest_package_delivery as delivery, guest_package_receiver as receiver, guest_delivery_receiver as helper
from . import performance_model as m, remote_command as c
from .test_cloud_package import fixture, save


class OwnedServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root=Path(self.temp.name)
        self.req,self.pre,self.approval,self.clock,self.http,self.store,old,self.transport=fake.fixture(self.root/'key')
        self.clock.now=time.monotonic_ns(); self.clock.wall=lambda:10001
        base=self.root/'package'; manifest=fixture(base)
        (base/'workload.json').write_bytes(m.canonical(a.workload.load()))
        manifest['workloadSha256']=m.sha((base/'workload.json').read_bytes()); manifest['files']=package.inventory(base); save(base/'manifest.json',manifest)
        self.archive=self.root/'guest.tar.gz'
        with tarfile.open(self.archive,'w:gz',format=tarfile.USTAR_FORMAT) as tar:
            for item in sorted(base.rglob('*')):
                if item.is_file():
                    raw=item.read_bytes(); info=tarfile.TarInfo(str(item.relative_to(base))); info.size=len(raw)
                    info.mode=0o755 if item.stat().st_mode & 0o111 else 0o644; tar.addfile(info,io.BytesIO(raw))
        self.req['bundleSha256']=m.sha(self.archive.read_bytes()); sha=a.validate_request(self.req)
        self.pre['requestSha256']=sha; self.approval.update(requestSha256=sha,preflightSha256=m.sha(m.canonical(self.pre)))
        self.provider=cloud_gcp.Compute(old.config,self.req,old.api,guest_access=old.guest_access,sleep=self.clock.sleep)
        self.mounts={n:str(self.root/f'mount-{n}') for n in (1,2,3)}
        for path in self.mounts.values(): Path(path).mkdir(mode=0o700)
        self.events=[]; self.endpoints=[]; self.clients=[]; self.fault=None
        self.services=owned.Services(self.provider,self.archive,self.endpoint,qualification_mounts=self.mounts,
            clock=self.clock.seconds,sleep=self.clock.sleep)
        self.startup=guest_startup.Prepare(self.provider,self.transport,self.root/'key/identity',self.root/'startup',services=self.services)
        self.probe=cloud_fake.Probe(self.root/'probe',self.clock)
        original=self.probe.prepare
        def prepared(req,deadline): self.events.append('probe'); return original(req,deadline)
        self.probe.prepare=prepared

    def endpoint(self,target,parent,value):
        test=self; node=int(value['binding']['node'][-1])
        class Endpoint(delivery.Endpoint):
            offline=True
            def exchange(ep,action,data,deadline,index=None):
                test.events.append((node,action)); ep.calls.append(dict(action=action,index=index))
                if ep.budget is None:
                    sample=helper.clock_sample(receiver.identity(value),'d'*32)
                    ep.budget=dict(schema='gse-v51-helper-deadline-v1',sample=sample,expiresNanos=sample['sampledNanos']+600*10**9)
                if action=='begin': answer=receiver.begin(parent,value,ep.budget)
                elif action=='part': answer=receiver.put(parent,value,ep.budget,index,io.BytesIO(data))
                elif action=='finish': answer=receiver.finish(parent,value,ep.budget)
                else: answer=receiver.query(parent,value,ep.budget)
                if test.fault=='lost-transfer' and action in ('part','finish'): raise ConnectionError('lost transfer response')
                return answer
            def client(ep,config):
                client=Client(config); test.clients.append(client); return client
        class Client:
            def __init__(self,config): self.config=config; self.starts=0; self.stops=0; self.closed=False
            def start(self,deadline):
                test.events.append((node,'start')); self.starts+=1
                if test.fault=='second-start' and node==2: raise ValueError('second start failure')
                if test.fault=='lost-start': raise ConnectionError('lost start response')
                return dict(state='LAUNCHED',pid=100+node,configSha256=m.sha(m.canonical(self.config)))
            def ready(self,deadline):
                sha=m.sha(m.canonical(self.config))
                if test.fault=='wrong-ready' and not self.closed: sha='e'*64
                if test.fault=='ready-deadline' and not self.closed: test.clock.sleep(601)
                return dict(ready=dict(pid=100+node,configSha256=sha),closed=dict(status='PASS',jvmStopped=True) if self.closed else None)
            def shutdown(self,deadline):
                test.events.append((node,'shutdown')); self.stops+=1
                if test.fault=='stop-failure': raise ValueError('shutdown failed')
                self.closed=True
                if test.fault=='lost-stop': raise ConnectionError('lost shutdown response')
        endpoint=Endpoint(target,parent,value); self.endpoints.append(endpoint); return endpoint

    def run_owned(self):
        return cloud_runner.Runner(self.store,self.provider,self.probe,self.root/'run',clock=self.clock.nanos,
            wall=self.clock.wall,startup=self.startup).run(self.req,self.pre,self.approval)
    def assert_clean(self,result):
        self.assertEqual(result['cleanup']['status'],'PASS'); self.assertFalse(self.http.resources)
        ledger=self.store.get(a.LEDGER)[1]; total,_=a.inspect_ledger(ledger); self.assertEqual(total,self.approval['maximumCostMicrousd'])
        self.assertTrue(self.probe.stopped)
    def test_complete_controller_orders_mount_delivery_start_probe_stop_and_retains(self):
        result=self.run_owned(); self.assertEqual(result['status'],'PASS',result['errors']); self.assert_clean(result)
        starts=[self.events.index((n,'start')) for n in (1,2,3)]
        self.assertLess(max(self.events.index((n,'finish')) for n in (1,2,3)),min(starts))
        self.assertGreater(self.events.index('probe'),max(starts)); self.assertTrue(all(c.closed for c in self.clients))
        self.assertTrue(result['leaseReleased']); self.assertEqual(len(self.services.clients),3)
        retained={k.rsplit('/startup/',1)[-1] for k in self.http.objects if '/startup/' in k}
        self.assertIn('services/stop.json',retained); self.assertEqual(len([v for v in retained if '-check-' in v]),18)
        self.assertTrue(all(b.formats==1 for b in self.transport.blocks))
        self.assertFalse(result['engineWorkloadExecuted'])
    def test_lost_transfer_responses_query_without_replaying_writes(self):
        self.fault='lost-transfer'; result=self.run_owned(); self.assertEqual(result['status'],'PASS',result['errors'])
        for endpoint in self.endpoints:
            self.assertEqual(sum(r['action']=='part' for r in endpoint.calls),len(endpoint.value['parts']))
            self.assertEqual(sum(r['action']=='finish' for r in endpoint.calls),1)
            self.assertEqual(sum(r['action']=='query' for r in endpoint.calls),len(endpoint.value['parts'])+1)
    def test_lost_start_queries_identity_without_second_start(self):
        self.fault='lost-start'; result=self.run_owned(); self.assertEqual(result['status'],'PASS',result['errors'])
        self.assertEqual([c.starts for c in self.clients],[1,1,1])
    def test_lost_shutdown_is_observed_without_second_write(self):
        self.fault='lost-stop'; result=self.run_owned(); self.assertEqual(result['status'],'PASS',result['errors'])
        self.services.stop(self.clock.seconds()+30); self.assertEqual([c.stops for c in self.clients],[1,1,1])
    def test_partial_start_failure_stops_started_and_uncertain_members(self):
        self.fault='second-start'; result=self.run_owned(); self.assertEqual(result['status'],'FAIL'); self.assert_clean(result)
        self.assertNotIn('probe',self.events); self.assertEqual(len(self.clients),2)
        self.assertTrue(all(c.closed and c.stops==1 for c in self.clients))
        self.assertIn('services/receipt.json',{k.rsplit('/startup/',1)[-1] for k in self.http.objects})
    def test_wrong_readiness_binding_blocks_probe_and_still_stops(self):
        self.fault='wrong-ready'; result=self.run_owned(); self.assertEqual(result['status'],'FAIL'); self.assert_clean(result)
        self.assertNotIn('probe',self.events); self.assertTrue(self.clients[0].closed)
    def test_original_preparation_deadline_is_not_extended_by_readiness(self):
        self.fault='ready-deadline'; result=self.run_owned(); self.assertEqual(result['status'],'FAIL'); self.assert_clean(result)
        self.assertNotIn('probe',self.events); self.assertEqual(result['budget']['status'],'FAIL')
    def test_collection_failure_still_closes_and_retains_services(self):
        self.probe.fault='collection-failure'; result=self.run_owned(); self.assertEqual(result['status'],'FAIL'); self.assert_clean(result)
        self.assertTrue(all(c.closed for c in self.clients)); self.assertFalse(result['leaseReleased'])
        self.assertTrue(any(k.endswith('/startup/services/stop.json') for k in self.http.objects))
    def test_service_stop_failure_does_not_prevent_provider_cleanup(self):
        self.fault='stop-failure'; result=self.run_owned(); self.assertEqual(result['status'],'FAIL'); self.assert_clean(result)
        self.assertTrue(any(e['phase']=='guest-stop' for e in result['errors']))
        with self.assertRaisesRegex(ValueError,'earlier stop'): self.services.stop(self.clock.seconds()+30)
        self.assertEqual([c.stops for c in self.clients],[1,1,1])
    def test_retention_failure_preserves_lease_charge_and_stops(self):
        original=self.store.put
        def put(key,value,expected):
            if key.endswith('/services/stop.json'): raise ConnectionError('stop retention failed')
            return original(key,value,expected)
        self.store.put=put; result=self.run_owned(); self.assertEqual(result['status'],'FAIL'); self.assert_clean(result)
        self.assertFalse(result['leaseReleased']); self.assertTrue(all(c.closed for c in self.clients))
    def test_expired_validation_entry_still_attempts_stop_during_cleanup(self):
        original=self.probe.stop
        def stop(): original(); self.clock.sleep(2000)
        self.probe.stop=stop; result=self.run_owned(); self.assertEqual(result['status'],'FAIL'); self.assert_clean(result)
        self.assertTrue(all(c.closed for c in self.clients)); self.assertFalse(result['leaseReleased'])
    def test_mount_removed_after_delivery_blocks_every_service(self):
        original=self.transport.readiness
        def observe(facts,*args):
            if (3,'finish') in self.events: self.transport.blocks[1].attached=False
            return original(facts,*args)
        self.transport.readiness=observe; result=self.run_owned(); self.assertEqual(result['status'],'FAIL'); self.assert_clean(result)
        self.assertFalse(self.clients); self.assertNotIn('probe',self.events)
    def test_mount_changed_after_start_blocks_probe_and_closes_partial_set(self):
        original=self.transport.readiness
        def observe(facts,*args):
            if self.clients: self.transport.blocks[0].mode=0o755
            return original(facts,*args)
        self.transport.readiness=observe; result=self.run_owned(); self.assertEqual(result['status'],'FAIL'); self.assert_clean(result)
        self.assertEqual(len(self.clients),1); self.assertTrue(self.clients[0].closed); self.assertNotIn('probe',self.events)
    def test_provider_drift_after_delivery_blocks_launch(self):
        original=self.provider.guest_facts
        def facts(*args,**kwargs):
            answer=original(*args,**kwargs)
            if (3,'finish') in self.events: answer['privateIp']='10.0.0.99'
            return answer
        self.provider.guest_facts=facts; result=self.run_owned(); self.assertEqual(result['status'],'FAIL'); self.assert_clean(result)
        self.assertFalse(self.clients); self.assertIn('service provider drift',str(result['errors']))
    def test_host_key_drift_after_delivery_blocks_launch(self):
        original=self.provider.guest_host_key
        def host(*args,**kwargs):
            answer=original(*args,**kwargs)
            if (3,'finish') in self.events: answer['publicKey']='changed'
            return answer
        self.provider.guest_host_key=host; result=self.run_owned(); self.assertEqual(result['status'],'FAIL'); self.assert_clean(result)
        self.assertFalse(self.clients); self.assertIn('host pin drift',str(result['errors']))
    def test_native_package_endpoint_is_rejected_before_transfer(self):
        self.services.factory=delivery.Endpoint; result=self.run_owned(); self.assertEqual(result['status'],'FAIL'); self.assert_clean(result)
        self.assertFalse(self.clients); self.assertIn('binding/scope',str(result['errors']))
    def test_unknown_retention_file_and_symlink_are_rejected(self):
        self.assertEqual(self.run_owned()['status'],'PASS')
        path=self.services.root/'unexpected.json'; path.write_text('{}')
        with self.assertRaisesRegex(ValueError,'inventory'): list(self.startup.retention_files())
        path.unlink(); path=self.services.root/'plan.json'; path.unlink(); path.symlink_to(self.root/'package/manifest.json')
        with self.assertRaisesRegex(ValueError,'inventory'): list(self.startup.retention_files())


if __name__=='__main__': unittest.main()
