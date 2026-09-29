"""Owned V4.4 control fixtures; OS identities and source/JVM replies are synthetic."""
from copy import deepcopy
import io
from pathlib import Path
import tempfile
import unittest
from . import cloud_package as package, performance_model as m, remote_command as c
from . import guest_owned_workload as w, guest_owned_qualification as qualification
from . import guest_source_producer as producer, guest_bootstrap as boot
from . import test_guest_owned_workload as workload, test_guest_owned_configured as configured
from . import test_guest_owned_bootstrap as bootstrap, test_guest_source_producer as source
from . import test_guest_owned_services as services
from .test_guest_healthy_evidence import HealthyFixture

MODE=package.MODES[0]


class LocalLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.fixture=workload.OwnedWorkloadTest();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;f.services.mode=MODE
        self.probe=w.Probe(f.services,f.root/'local',clock=f.clock.seconds,sleep=f.clock.sleep)
        self.probe.clients=f.probe.clients[:1];self.probe.clients[0][2]['mode']=MODE
        self.probe.prepared=True;f.probe=self.probe;configured.synthetic_proc(self)
    def tape(self):self.probe.cell('healthy',self.fixture.clock.nanos()+300*10**9)
    def collect(self):
        self.probe.stop();return self.probe.collect_validate(self.fixture.root,self.fixture.clock.nanos()+600*10**9)
    def test_one_node_one_start_and_five_windows_without_election_or_activation(self):
        self.tape();self.assertEqual(self.probe.scope,w.LOCAL_SCOPE);self.assertEqual(self.probe.active[0],1)
        client=self.probe.clients[0][1]
        self.assertEqual([q['command'] for q in client.calls],['start-voter']+['window']*5+['collect'])
        self.assertEqual([q['payload']['window'] for q in client.calls if q['command']=='window'],
                         [s['window'] for s in w.schedule.windows('healthy','experiment')])
        with self.assertRaisesRegex(ValueError,'consumed'):self.tape()
    def test_lost_original_replies_query_same_ids_without_another_start_or_window(self):
        client=self.probe.clients[0][1];client.lost=True;self.tape()
        self.assertEqual(client.calls,client.queries)
        self.assertEqual(len({q['commandId'] for q in client.calls}),len(client.calls))
    def test_failed_window_ends_tape_and_stops_only_started_local_process(self):
        client=self.probe.clients[0][1];client.failure='window'
        with self.assertRaisesRegex(ValueError,'injected window'):self.tape()
        result=self.collect();self.assertEqual(result['status'],'FAIL');self.assertTrue(client.closed)
        self.assertEqual(result['mode'],MODE);self.assertEqual(result['scope'],w.LOCAL_SCOPE)
        self.assertEqual(sum(q['command']=='window' for q in client.calls),1)
        self.assertEqual(sum(q['command']=='stop-voter' for q in client.calls),1)
        self.assertTrue(list(self.probe.retention_files()))
    def test_uncertain_start_is_never_restarted_and_remains_in_cleanup(self):
        client=self.probe.clients[0][1];client.lost=True;query=client.query
        client.query=lambda q,end:client.store.envelope(q,'UNCERTAIN') if q['command']=='start-voter' else query(q,end)
        with self.assertRaisesRegex(ValueError,'never resubmit'):self.tape()
        result=self.collect();self.assertEqual(result['status'],'FAIL');self.assertTrue(client.closed)
        self.assertEqual(sum(q['command']=='start-voter' for q in client.calls),1)
        self.assertFalse(any(q['command']=='window' for q in client.calls))
        self.assertTrue(list((self.probe.raw/'commands/1').glob('*/failure.json')))
    def test_preparation_binds_single_admitted_member_and_exact_manifest(self):
        original=self.fixture.prepare_fixture();self.probe.prepare(self.fixture.req,self.fixture.clock.nanos()+600*10**9)
        self.assertEqual((self.probe.raw/'package-manifest.json').read_bytes(),original)
        self.assertEqual(len(c.read(self.probe.raw/'plan.json')['configs']),1)
    def test_other_or_duplicate_member_cannot_borrow_local_scope(self):
        self.fixture.prepare_fixture();self.probe.clients.append(self.probe.clients[0])
        with self.assertRaisesRegex(ValueError,'member set'):
            self.probe.prepare(self.fixture.req,self.fixture.clock.nanos()+600*10**9)
    def test_automatic_physical_or_backup_flags_rejected_before_output(self):
        for args in (dict(physical=True),dict(backup=True),dict(physical=True,backup=True)):
            with self.assertRaisesRegex(ValueError,'scope'):
                w.Probe(self.fixture.services,self.fixture.root/'invalid',**args)
        self.assertFalse((self.fixture.root/'invalid').exists())


class LocalCollectionTest(workload.OwnedCollectionTest):
    mode=MODE


class LocalRunnerTest(workload.RunnerWorkloadTest):
    def setUp(self):
        super().setUp();self.probe.scope=w.LOCAL_SCOPE;self.probe.mode=MODE
        self.probe.collect_validate.return_value.update(scope=w.LOCAL_SCOPE,mode=MODE)
    def test_receipt_from_another_mode_fails_and_still_cleans_all_resources(self):
        self.probe.collect_validate.return_value['mode']=package.MODES[1]
        result=self.run_case();self.assertEqual(result['status'],'FAIL');self.assertFalse(self.provider.objects)
        self.startup.stop.assert_called_once()


class LocalBootstrapTest(unittest.TestCase):
    def setUp(self):
        self.fixture=bootstrap.BootstrapTest();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;f.configs=f.configs[:1];f.configs[0]['mode']=MODE;f.endpoints=f.endpoints[:1]
    def test_one_source_import_seal_with_source_only_identity_and_lost_replies(self):
        f=self.fixture;f.fault='lost-replies';result=f.run_bootstrap()
        self.assertEqual(result['status'],'PASS');self.assertEqual(set(result['identity']),{'sourceSha256'})
        self.assertEqual([row['node'] for row in result['members']],['node-1'])
        for phase in ('install','seal'):
            self.assertEqual(f.endpoints[0].counts[phase],1);self.assertEqual(f.endpoints[0].counts['query-'+phase],2)
        self.assertEqual(len(list(f.bridge.retention_files())),7)
    def test_local_singleton_cannot_claim_replicated_bootstrap(self):
        self.fixture.configs[0]['mode']=package.MODES[1]
        with self.assertRaisesRegex(ValueError,'member set'):self.fixture.run_bootstrap()
        self.assertFalse(self.fixture.events)
    def test_local_node_two_is_rejected_before_source_preparation(self):
        self.fixture.configs[0]['binding']['node']='node-2'
        with self.assertRaisesRegex(ValueError,'member set'):self.fixture.run_bootstrap()
        self.assertFalse(self.fixture.events)


class LocalSourceTest(unittest.TestCase):
    def setUp(self):
        self.fixture=source.ProducerTest();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;f.configs[:]=f.configs[:1];cfg=f.configs[0];cfg['mode']=MODE
        cfg['root']=str(Path(f.fixture.fixture.parent)/MODE)
    def test_consumed_producer_download_install_and_seal_only_one_source(self):
        f=self.fixture;f.fault='lost-replies';exports=f.download()
        self.assertEqual(f.generated,1);self.assertEqual([row['node'] for row in exports],['node-1'])
        self.assertEqual(sum(action=='prepare' for action,_,_ in f.calls),1)
        self.assertTrue(all(node in (None,'node-1') for _,node,_ in f.calls))
        row=exports[0];cfg=f.configs[0];value=source.wire.describe(Path(row['folder']),row['descriptorSha256'],cfg)
        source.wire.begin(f.base,value,lambda:None)
        for chunk in value['chunks']:
            with (Path(row['folder'])/'parts'/chunk['part']).open('rb') as stream:
                stream.seek(chunk['offset']);source.wire.put(f.base,value,chunk['index'],io.BytesIO(stream.read(chunk['bytes'])),lambda:None)
        self.assertEqual(source.wire.finish(f.base,value,lambda:None)['state'],'SUCCEEDED')
        (producer.location(f.base)/'exports').rename(producer.location(f.base)/'hidden-exports')
        Path(row['folder']).rename(Path(row['folder']).with_name('hidden-cache'))
        request=dict(config=cfg,descriptorSha256=row['descriptorSha256'],sourceTransferSha256=m.sha(m.canonical(value)))
        self.assertEqual(f.fixture.call('install',request)['receipt']['result']['files'],6)
        sealed=f.fixture.call('seal',request)['receipt']['result']
        self.assertEqual(set(sealed['identity']),{'sourceSha256'})
        ready=c.read(Path(cfg['root'])/boot.LOCAL_READY);self.assertEqual(ready['files'],{})
        self.assertFalse(any((Path(cfg['root'])/('node-'+str(n))).exists() for n in (1,2,3)))
    def test_unrequested_member_export_cannot_be_downloaded(self):
        self.fixture.call('prepare')
        for node in ('node-2','node-3'):
            with self.assertRaisesRegex(ValueError,'selected member'):self.fixture.call('manifest',node=node)
    def test_local_producer_rejects_extra_missing_or_foreign_mode_members(self):
        request=self.fixture.request
        for configs in ([],request['configs']*3,[dict(request['configs'][0],mode=package.MODES[1])]):
            with self.assertRaisesRegex(ValueError,'member count'):producer.validate(dict(request,configs=configs))
        changed=deepcopy(request);changed['configs'][0]['binding']['node']='node-2'
        with self.assertRaisesRegex(ValueError,'member configurations'):producer.validate(changed)
        self.assertFalse(producer.location(self.fixture.base).exists())


class LocalServiceTest(unittest.TestCase):
    def test_node_one_service_preserves_three_resource_cleanup_and_accounting(self):
        configured.synthetic_proc(self)
        f=services.OwnedServiceTest();f.setUp();self.addCleanup(f.doCleanups)
        f.services.mode=MODE;f.fault='lost-stop'
        result=f.run_owned();self.assertEqual(result['status'],'PASS',result['errors']);f.assert_clean(result)
        self.assertEqual([n for n,_,_ in f.services.clients],[1]);self.assertEqual(len(f.endpoints),1)
        self.assertEqual([cl.starts for cl in f.clients],[1]);self.assertEqual([cl.stops for cl in f.clients],[1])
        self.assertTrue(all(block.formats==1 for block in f.transport.blocks))
        self.assertEqual(len(f.transport.blocks),3);self.assertTrue(result['leaseReleased'])
        plan=c.read(f.services.root/'plan.json');self.assertEqual(len(plan['configs']),1)
        self.assertEqual(len(plan['startupSha256']),3)


class LocalEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def test_no_status_activation_or_replication_jar_needed_for_frozen_tape(self):
        f=HealthyFixture(self.root/'raw',mode=MODE);f.render();result=f.validate()
        self.assertEqual(result['calls'],90);self.assertFalse(result['physicalHistoryQualified'])
        self.assertFalse(any(q['request']['command']=='fault' for q in f.transcript))
        self.assertEqual(len(m.strict_json(f.manifest)['modes'][MODE]['jars']),1)
    def test_other_host_cannot_claim_experiment_local_issuer(self):
        f=HealthyFixture(self.root/'raw',mode=MODE,node='node-2');f.render()
        with self.assertRaisesRegex(ValueError,'local issuer role'):f.validate()
    def test_resealed_local_wrong_answer_is_rejected(self):
        f=HealthyFixture(self.root/'raw',mode=MODE);response=f.results[-2]
        response['call'].update(answer=[],answerSha256=m.sha(m.canonical([])))
        for _,events,result in f.extra:
            for row in [*events,*result['calls']]:
                if 'result' in row and row['result']['opId']==response['opId']:row['result']['resultSha256']=m.sha(m.canonical(response))
        f.render()
        with self.assertRaisesRegex(ValueError,'logical answer'):f.validate()


class QualificationScopeTest(unittest.TestCase):
    def test_invalid_local_scope_fails_before_setup(self):
        for options in (dict(mode=MODE),dict(mode=MODE,workload=True),dict(mode=MODE,workload=True,physical=True),
                        dict(mode=MODE,workload=True,backup=True),dict(mode='unknown')):
            with self.assertRaises(ValueError):qualification.run('not-created','not-a-bundle','a'*40,**options)
        self.assertFalse(Path('not-created').exists())


if __name__=='__main__':unittest.main()
