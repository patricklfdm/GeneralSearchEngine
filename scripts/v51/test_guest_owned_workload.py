"""Owned workload lifecycle tests; synthetic replies are not engine evidence."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import os
import tempfile
import unittest
from . import cloud_authority as a, cloud_fake as fake, cloud_runner as runner, cloud_package as package
from . import guest_owned_workload as w, remote_command as c, remote_schedule as schedule, performance_model as m
from .test_guest_service import config
from .test_cloud_package import fixture as package_fixture
from .test_guest_healthy_evidence import HealthyFixture
from . import remote_collection as collection


class Client:
    def __init__(self, root, cfg, leader=False):
        self.config=cfg;self.base=root;self.leader=leader;self.calls=[];self.queries=[];self.closed=False;self.lost=False;self.failure=None
        self.store=c.CommandStore(root,cfg['binding'],create=True)
    def submit(self, value, deadline):
        self.calls.append(value)
        def handler(name,payload,checkpoint):
            if name==self.failure:raise ValueError('injected '+name)
            if name=='stop-voter':self.closed=True;return dict(stopped=True)
            if name=='collect':raise ValueError('collection fixture failure' if self.closed else 'guest collection requires stopped JVM')
            if name=='fault':return dict(status=dict(state='LEADER_READY' if self.leader else 'FOLLOWER'))
            if name=='window':return dict(calls=len(next(s for s in schedule.windows('healthy','experiment') if s['window']==payload['window'])['calls']))
            return {}
        answer=self.store.execute(value,handler)
        if self.lost:raise ConnectionError('lost original response')
        return answer
    def query(self,value,deadline):self.queries.append(value);return self.store.query(value)


class OwnedWorkloadTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.clock=fake.Clock();self.req,self.pre,self.app=fake.fixture()
        self.services=SimpleNamespace(offline=True,mode=package.MODES[2],bootstrap=object(),provider=SimpleNamespace(req=self.req))
        self.probe=w.Probe(self.services,self.root/'probe',clock=self.clock.seconds,sleep=self.clock.sleep)
        for n in (1,2,3):
            cfg=config(self.root/f'cell-{n}');cfg['binding']=c.binding(self.req['source'],self.req['bundleSha256'],self.req['attempt'],'node-'+str(n))
            client=Client(self.root/f'client-{n}',cfg,leader=n==2)
            self.probe.clients.append((n,client,cfg))
        self.probe.prepared=True
    def test_five_windows_observed_leader_and_passive_configuration(self):
        self.probe.cell('healthy',self.clock.nanos()+300*10**9)
        self.assertEqual(self.probe.active[0],2);self.assertEqual(self.probe.cells,['healthy'])
        expected=[s['window'] for s in schedule.windows('healthy','experiment')]
        for n,cl,_ in self.probe.clients:
            self.assertEqual([q['payload']['window'] for q in cl.calls if q['command']=='window'],expected if n==2 else [])
            self.assertEqual([q['payload']['window'] for q in cl.calls if q['payload'].get('action')=='configure'],[] if n==2 else expected)
        with self.assertRaisesRegex(ValueError,'consumed'):self.probe.cell('healthy',self.clock.nanos()+300*10**9)
    def test_lost_window_reply_queries_original_never_reexecutes(self):
        self.probe.clients[1][1].lost=True;self.probe.cell('healthy',self.clock.nanos()+300*10**9)
        cl=self.probe.clients[1][1]
        self.assertEqual(cl.calls,cl.queries);self.assertEqual(len({q['commandId'] for q in cl.calls}),len(cl.calls))
        self.assertEqual(len(list((self.probe.raw/'commands/2').glob('*/receipt.json'))),len(cl.calls))
    def test_failed_window_stops_tape_and_all_attempted_voters_even_if_collection_fails(self):
        self.probe.clients[1][1].failure='window'
        with self.assertRaisesRegex(ValueError,'injected window'):self.probe.cell('healthy',self.clock.nanos()+300*10**9)
        self.probe.stop();result=self.probe.collect_validate(self.root,self.clock.nanos()+600*10**9)
        self.assertEqual(result['status'],'FAIL');self.assertEqual(len(result['errors']),3)
        self.assertTrue(all(cl.closed for _,cl,_ in self.probe.clients))
        self.assertEqual(sum(q['command']=='window' for _,cl,_ in self.probe.clients for q in cl.calls),1)
        self.assertEqual(c.read(self.probe.raw/'cell.json')['status'],'FAIL')
        self.assertTrue(list(self.probe.retention_files()))
    def test_stop_failure_does_not_skip_remaining_voters_or_collection(self):
        self.probe.cell('healthy',self.clock.nanos()+300*10**9);self.probe.clients[0][1].failure='stop-voter'
        self.probe.stop();answer=self.probe.collect_validate(self.root,self.clock.nanos()+600*10**9)
        self.assertEqual(len(answer['errors']),4);self.assertTrue(self.probe.clients[2][1].closed)
        self.assertEqual(len(self.probe.stop_attempted),3)
    def test_deadline_loss_retains_unresolved_request_without_replay(self):
        cl=self.probe.clients[0][1];cl.lost=True
        cl.query=lambda value,deadline:cl.store.envelope(value,'UNCERTAIN')
        with self.assertRaisesRegex(ValueError,'never resubmit'):
            self.probe.execute(self.probe.clients[0],'start-voter',{},self.clock.seconds()+.1)
        self.assertEqual(len(cl.calls),1)
        self.assertEqual(len(list((self.probe.raw/'commands/1').glob('*/failure.json'))),1)
    def test_live_wrong_mode_or_missing_bootstrap_rejected(self):
        for key,value in [('offline',False),('mode',package.MODES[0]),('bootstrap',None)]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                w.Probe(SimpleNamespace(**dict(vars(self.services),**{key:value})),self.root/'reject')
    def prepare_fixture(self):
        package_fixture(self.root/'package');manifest=(self.root/'package/manifest.json').read_bytes()
        self.services.archive=self.root/'guest.tar.gz';self.services.root=self.root/'services';self.services.root.mkdir()
        self.services.clients=self.probe.clients;members=[]
        for node,cl,cfg in self.probe.clients:
            cfg['packageManifestSha256']=m.sha(manifest);members.append(dict(node=node,configSha256=m.sha(m.canonical(cfg))))
        c.write_once(self.services.root/'receipt.json',dict(status='PASS',requestSha256=a.validate_request(self.req),
            bootstrap=dict(status='PASS',publicBootstrapVerified=True),members=members))
        self.probe.prepared=False;return manifest
    def test_prepare_checks_admitted_identity_and_retains_exact_manifest_bytes(self):
        original=self.prepare_fixture();self.probe.prepare(self.req,self.clock.nanos()+600*10**9)
        self.assertEqual((self.probe.raw/'package-manifest.json').read_bytes(),original)
        with self.assertRaisesRegex(ValueError,'request/scope'):self.probe.prepare(self.req,self.clock.nanos()+600*10**9)
    def test_changed_client_configuration_after_admission_is_rejected(self):
        self.prepare_fixture();self.probe.clients[1][2]['ports'][0]+=1
        with self.assertRaisesRegex(ValueError,'client identity'):self.probe.prepare(self.req,self.clock.nanos()+600*10**9)
    def test_collection_failures_do_not_mask_missing_started_member(self):
        self.probe.clients[1][1].failure='start-voter'
        with self.assertRaisesRegex(ValueError,'injected start'):self.probe.cell('healthy',self.clock.nanos()+300*10**9)
        self.probe.stop();result=self.probe.collect_validate(self.root,self.clock.nanos()+600*10**9)
        self.assertEqual(result['status'],'FAIL');self.assertEqual([n for n,_,_ in self.probe.started],[1,2])
        self.assertTrue(self.probe.clients[1][1].closed);self.assertFalse(self.probe.clients[2][1].calls)


class OwnedCollectionTest(unittest.TestCase):
    """Exercise the actual owned collector and independent validator together."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.clock=fake.Clock();req,_,_=fake.fixture()
        services=SimpleNamespace(offline=True,mode=package.MODES[2],bootstrap=object(),provider=SimpleNamespace(req=req))
        self.probe=w.Probe(services,self.root/'probe',clock=self.clock.seconds,sleep=self.clock.sleep)
        self.fixtures={};self.fault=None;self.original_parts={}
        # Incompressible valid stderr gives a full 8 MiB part and a short tail.
        # Small warmup collections did not exercise the owned adapter's boundary.
        payload=os.urandom((8<<20)+1024)
        for node in (1,2,3):
            f=HealthyFixture(self.root/f'raw-{node}',active=node==1,node=f'node-{node}')
            f.files[f.node+'-stderr.log']=payload;f.render();(f.root/collection.INDEX).unlink()
            parts=self.root/f'parts-{node}'
            manifest=collection.pack(f.root,parts,m.sha(m.canonical(f.config['binding'])))
            self.assertEqual(manifest['parts'][0]['bytes'],8<<20);self.assertEqual(len(manifest['parts']),2)
            f.transcript[-1]['receipt']['result']=manifest
            self.fixtures[node]=f;self.original_parts[node]=parts
            client=SimpleNamespace(config=f.config,base=f.base,part=Mock(side_effect=self.download(node)))
            self.probe.clients.append((node,client,f.config))
            self.probe.transcripts[node]=list(f.transcript[:-2])
        self.probe.manifest=self.fixtures[1].manifest;self.probe.started=list(self.probe.clients)
        self.probe.active=self.probe.clients[0];self.probe.cells=['healthy'];self.probe.engineWorkloadExecuted=True
        self.probe.stop()
    def download(self,node):
        def read(name,maximum,deadline):
            raw=(self.original_parts[node]/name).read_bytes();self.assertEqual(len(raw),maximum)
            if node==1 and self.fault=='truncated':return raw[:-1]
            if node==1 and self.fault=='corrupt':return bytes([raw[0]^1])+raw[1:]
            return raw
        return read
    def collect(self):
        def received(member,name,payload,deadline):
            f=self.fixtures[member[0]];row=f.transcript[-2 if name=='stop-voter' else -1]
            self.assertEqual(row['request']['command'],name);self.assertEqual(row['request']['payload'],payload)
            self.probe.transcripts[member[0]].append(row);return row['receipt']
        with patch.object(self.probe,'succeeded',side_effect=received):
            return self.probe.collect_validate(self.root,self.clock.nanos()+600*10**9)
    def test_full_size_parts_and_tail_replay_all_members_without_retries(self):
        result=self.collect();self.assertEqual(result['status'],'PASS',result['errors'])
        self.assertEqual([r['calls'] for r in result['members']],[90,0,0])
        for node,client,_ in self.probe.clients:
            self.assertEqual(client.part.call_count,2)
            downloaded=self.probe.raw/f'node-{node}'/'parts'
            for original in self.original_parts[node].glob('*.bin'):
                self.assertEqual((downloaded/original.name).read_bytes(),original.read_bytes())
            self.assertFalse(list(downloaded.glob('*.partial')))
    def test_truncated_large_part_remains_failed_partial_and_other_members_are_checked(self):
        self.fault='truncated';result=self.collect()
        self.assertEqual(result['status'],'FAIL');self.assertEqual(len(result['members']),2)
        self.assertEqual(result['errors'],[dict(node=1,phase='collection-validation',message='part incomplete/hash mismatch')])
        folder=self.probe.raw/'node-1/parts';self.assertFalse((folder/'part-0000.bin').exists())
        self.assertEqual((folder/'part-0000.bin.partial').stat().st_size,(8<<20)-1)
        self.assertEqual(self.probe.clients[0][1].part.call_count,1)
    def test_corrupt_large_part_is_not_retried_or_published(self):
        self.fault='corrupt';result=self.collect()
        self.assertEqual(result['status'],'FAIL');self.assertEqual(len(result['members']),2)
        self.assertEqual(result['errors'][0]['message'],'part incomplete/hash mismatch')
        folder=self.probe.raw/'node-1/parts';self.assertFalse((folder/'part-0000.bin').exists())
        self.assertEqual((folder/'part-0000.bin.partial').stat().st_size,8<<20)
        self.assertEqual(self.probe.clients[0][1].part.call_count,1)


class RunnerWorkloadTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.clock=fake.Clock();self.store=fake.Store();self.provider=fake.Provider(self.store)
        self.probe=Mock(execution=a.EXECUTION,scope=w.SCOPE,services=object(),engineWorkloadExecuted=True)
        self.startup=Mock(execution=a.EXECUTION,services=self.probe.services)
        self.startup.prepare.return_value=dict(status='PASS')
        self.startup.retention_files.return_value=[];self.probe.retention_files.return_value=[('fixture.bin',b'fixture')]
        self.probe.collect_validate.return_value=dict(status='PASS',execution=a.EXECUTION,scope=w.SCOPE,paidCloud=False,
            engineWorkloadExecuted=True,fullRemoteQualification=False,physicalHistoryQualified=False,cells=['healthy'])
    def run_case(self,**kwargs):
        req,pre,app=fake.fixture(**kwargs)
        return runner.Runner(self.store,self.provider,self.probe,self.root/'run',clock=self.clock.nanos,
            wall=self.clock.wall,startup=self.startup,qualification=w.SCOPE).run(req,pre,app)
    def test_partial_scope_runs_only_healthy_and_preserves_cleanup_and_charge(self):
        result=self.run_case();self.assertEqual(result['status'],'PASS',result['errors'])
        self.assertEqual(self.probe.cell.call_count,1);self.assertEqual(self.probe.cell.call_args.args[0],'healthy')
        self.assertTrue(result['engineWorkloadExecuted']);self.assertFalse(result['fullRemoteQualification'])
        self.assertEqual(result['qualificationScope'],w.SCOPE);self.assertFalse(self.provider.objects)
        self.assertTrue(result['leaseReleased']);self.assertEqual(a.inspect_ledger(self.store.get(a.LEDGER)[1])[0],1_000_000)
    def test_failed_collected_evidence_retained_before_failed_completion(self):
        self.probe.collect_validate.return_value['status']='FAIL'
        result=self.run_case();self.assertEqual(result['status'],'FAIL');self.assertIn('evidenceSha256',result)
        self.assertFalse(self.provider.objects);self.startup.stop.assert_called_once()
        self.assertEqual(a.inspect_ledger(self.store.get(a.LEDGER)[1])[0],1_000_000)
    def test_collection_exception_still_stops_services_cleans_resources_and_holds_lease(self):
        self.probe.collect_validate.side_effect=ValueError('collection failed')
        result=self.run_case();self.assertEqual(result['status'],'FAIL');self.assertFalse(self.provider.objects)
        self.startup.stop.assert_called_once();self.assertFalse(result['leaseReleased'])
    def test_canonical_rejected_before_lease_or_allocation(self):
        with self.assertRaisesRegex(ValueError,'not a full preset'):self.run_case(member='canonical-1',order='canonical-first')
        self.assertFalse(self.store.events);self.assertFalse(self.provider.events)
    def test_owned_probe_cannot_be_used_as_full_preset_or_with_other_services(self):
        for qualification in (None,'unknown',w.SCOPE):
            self.startup.services=object()
            with self.assertRaisesRegex(ValueError,'scope/startup'):
                runner.Runner(self.store,self.provider,self.probe,self.root/'run',startup=self.startup,qualification=qualification)


if __name__=='__main__':unittest.main()
