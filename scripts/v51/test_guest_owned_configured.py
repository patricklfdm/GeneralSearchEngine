"""Owned configured control tests; all OS/JVM observations here are synthetic."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_package as package, performance_model as m, remote_command as c
from . import guest_owned_workload as w, guest_owned_qualification as qualification, cloud_runner as runner
from . import test_guest_owned_workload as fixtures
from .test_guest_healthy_evidence import HealthyFixture

MODE=package.MODES[1]


def synthetic_proc(test):
    read=Path.read_text
    def metadata(path,*args,**kwargs):
        if str(path)=='/proc/sys/kernel/random/boot_id':return '11111111-1111-4111-8111-111111111111'
        if str(path)=='/proc/self/stat':return '1 (synthetic) '+' '.join(['0']*20)
        return read(path,*args,**kwargs)
    mocked=patch.object(Path,'read_text',metadata);mocked.start();test.addCleanup(mocked.stop)


class ConfiguredLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.OwnedWorkloadTest();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;f.services.mode=MODE
        self.probe=w.Probe(f.services,f.root/'configured',clock=f.clock.seconds,sleep=f.clock.sleep)
        self.probe.clients=f.probe.clients;self.probe.prepared=True
        for _,client,cfg in self.probe.clients:cfg['mode']=MODE
        f.probe=self.probe;synthetic_proc(self);self.order=[]
        for node,client,_ in self.probe.clients:
            submit=client.submit
            def observed(value,end,node=node,submit=submit):
                self.order.append((node,value,end));return submit(value,end)
            client.submit=observed
    def tape(self):self.probe.cell('healthy',self.fixture.clock.nanos()+300*10**9)
    def collect(self):
        self.probe.stop();return self.probe.collect_validate(self.fixture.root,self.fixture.clock.nanos()+600*10**9)
    def activations(self):return [(n,q) for n,q,_ in self.order if q['command']=='fault' and q['payload']==dict(action='activate')]
    def test_all_starts_precede_single_node_one_activation_and_five_windows(self):
        self.tape();self.assertEqual(self.probe.scope,w.CONFIGURED_SCOPE);self.assertEqual(self.probe.active[0],1)
        self.assertEqual([n for n,_ in self.activations()],[1])
        activation=next(i for i,(_,q,_) in enumerate(self.order) if q['payload']==dict(action='activate'))
        self.assertEqual([n for n,q,_ in self.order[:activation] if q['command']=='start-voter'],[1,2,3])
        self.assertFalse(any(q['payload']==dict(action='status') for _,q,_ in self.order))
        for node,client,_ in self.probe.clients:
            windows=[q['payload']['window'] for q in client.calls if q['command']=='window']
            passive=[q['payload']['window'] for q in client.calls if q['payload'].get('action')=='configure']
            expected=[s['window'] for s in w.schedule.windows('healthy','experiment')]
            self.assertEqual(windows,expected if node==1 else []);self.assertEqual(passive,[] if node==1 else expected)
        with self.assertRaisesRegex(ValueError,'consumed'):self.tape()
    def test_lost_activation_and_window_replies_only_query_original_ids(self):
        client=self.probe.clients[0][1];client.lost=True;self.tape()
        self.assertEqual(client.calls,client.queries);self.assertEqual(len(self.activations()),1)
        self.assertEqual(len({q['commandId'] for q in client.calls}),len(client.calls))
        self.assertEqual(len([q for q in client.calls if q['command']=='window']),5)
    def test_failed_activation_never_starts_tape_and_still_stops_every_voter(self):
        self.probe.clients[0][1].failure='fault'
        with self.assertRaisesRegex(ValueError,'injected fault'):self.tape()
        result=self.collect();self.assertEqual(result['status'],'FAIL');self.assertEqual(result['mode'],MODE)
        self.assertEqual(result['scope'],w.CONFIGURED_SCOPE);self.assertFalse(result['physicalHistoryQualified'])
        self.assertEqual(len(self.activations()),1);self.assertFalse(any(q['command']=='window' for _,q,_ in self.order))
        self.assertTrue(all(cl.closed for _,cl,_ in self.probe.clients))
        self.assertEqual(c.read(self.probe.raw/'cell.json')['status'],'FAIL')
        self.assertTrue(list(self.probe.retention_files()))
    def test_uncertain_activation_exhausts_original_deadline_without_reactivation(self):
        client=self.probe.clients[0][1];client.lost=True;query=client.query
        def uncertain(value,end):
            if value['payload']==dict(action='activate'):return client.store.envelope(value,'UNCERTAIN')
            return query(value,end)
        client.query=uncertain
        with self.assertRaisesRegex(ValueError,'never resubmit'):self.tape()
        self.assertEqual(len(self.activations()),1)
        original_end=next(end for _,q,end in self.order if q['payload']==dict(action='activate'))
        self.assertAlmostEqual(self.fixture.clock.seconds(),original_end,places=6)
        self.assertTrue(list((self.probe.raw/'commands/1').glob('*/failure.json')))
        self.collect();self.assertTrue(all(cl.closed for _,cl,_ in self.probe.clients))
        self.assertFalse(any(q['command']=='window' for _,q,_ in self.order))
    def test_preparation_binds_configured_manifest_and_all_members(self):
        original=self.fixture.prepare_fixture();self.probe.prepare(self.fixture.req,self.fixture.clock.nanos()+600*10**9)
        self.assertEqual((self.probe.raw/'package-manifest.json').read_bytes(),original)
        plan=c.read(self.probe.raw/'plan.json');self.assertEqual(plan['mode'],MODE);self.assertEqual(plan['scope'],w.CONFIGURED_SCOPE)
    def test_changed_mode_cannot_borrow_an_admitted_service_receipt(self):
        self.fixture.prepare_fixture();self.probe.clients[1][2]['mode']=package.MODES[2]
        with self.assertRaisesRegex(ValueError,'client identity'):
            self.probe.prepare(self.fixture.req,self.fixture.clock.nanos()+600*10**9)
    def test_configured_physical_scope_allows_optional_backup(self):
        for i,args in enumerate((dict(physical=True),dict(physical=True,backup=True))):
            probe=w.Probe(self.fixture.services,self.fixture.root/str(i),**args)
            self.assertEqual(probe.scope,w.CONFIGURED_SCOPE);self.assertTrue(probe.require_physical)
        with self.assertRaisesRegex(ValueError,'scope'):
            w.Probe(self.fixture.services,self.fixture.root/'invalid',backup=True)
        self.assertFalse((self.fixture.root/'invalid').exists())


class AutomaticLifecycleCompatibilityTest(fixtures.OwnedWorkloadTest):
    def setUp(self):super().setUp();synthetic_proc(self)


class ConfiguredCollectionTest(fixtures.OwnedCollectionTest):
    mode=MODE


class ConfiguredRunnerTest(fixtures.RunnerWorkloadTest):
    def setUp(self):
        super().setUp();self.probe.scope=w.CONFIGURED_SCOPE;self.probe.mode=MODE
        self.probe.collect_validate.return_value.update(scope=w.CONFIGURED_SCOPE,mode=MODE)
    def test_mode_scope_mismatch_rejected_before_allocation(self):
        self.probe.scope=w.SCOPE
        with self.assertRaisesRegex(ValueError,'scope/startup'):self.run_case()
        self.assertFalse(self.store.events);self.assertFalse(self.provider.events)
    def test_wrong_mode_evidence_still_cleans_resources_and_retains_failure(self):
        self.probe.collect_validate.return_value['mode']=package.MODES[2]
        result=self.run_case();self.assertEqual(result['status'],'FAIL')
        self.assertFalse(self.provider.objects);self.startup.stop.assert_called_once()
        self.assertTrue(any('scope' in row['message'] for row in result['errors']))
    def test_configured_probe_cannot_be_admitted_as_full_preset(self):
        with self.assertRaisesRegex(ValueError,'scope/startup'):
            runner.Runner(self.store,self.provider,self.probe,self.root/'unscoped',startup=self.startup)
        self.assertFalse(self.store.events)


class ConfiguredEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def fixture(self,**args):return HealthyFixture(self.root/'raw',mode=MODE,**args)
    def replace_activation(self,f,action):
        row=f.transcript[1];row['request']['payload']=dict(action=action)
        row['receipt']['requestSha256']=m.sha(m.canonical(row['request']))
        f.exchanges[0]['request']['command']=action;f.exchanges[0]['response']['command']=action
    def test_status_or_missing_activation_cannot_establish_configured_readiness(self):
        f=self.fixture();self.replace_activation(f,'status');f.render()
        with self.assertRaisesRegex(ValueError,'activation role/coverage/order'):f.validate()
    def test_activation_cannot_carry_unrequested_jvm_fields(self):
        f=self.fixture();f.exchanges[0]['request']['peer']='node-2';f.render()
        with self.assertRaisesRegex(ValueError,'control JVM request'):f.validate()
    def test_duplicate_original_activation_receipt_rejected(self):
        f=self.fixture();row=deepcopy(f.transcript[1]);command=f'{len(f.transcript)+1:032x}'
        row['request']['commandId']=command;row['receipt'].update(commandId=command,requestSha256=m.sha(m.canonical(row['request'])),
            startedNanos=1_070_000_001,endedNanos=1_080_000_000)
        f.transcript.insert(2,row);f.render()
        with self.assertRaisesRegex(ValueError,'activation role/coverage/order'):f.validate()
    def test_activation_after_first_window_rejected_even_with_resealed_receipts(self):
        f=self.fixture();row=f.transcript.pop(1);row['receipt'].update(startedNanos=12_100_000_100,endedNanos=12_100_000_200)
        f.transcript.insert(2,row);f.render()
        with self.assertRaisesRegex(ValueError,'activation role/coverage/order'):f.validate()
    def test_other_voter_cannot_issue_configured_tape(self):
        f=self.fixture(node='node-2');f.render()
        with self.assertRaisesRegex(ValueError,'activation role/coverage/order'):f.validate()
    def test_passive_voter_cannot_claim_activation(self):
        f=self.fixture(active=False);self.replace_activation(f,'activate');f.render()
        with self.assertRaisesRegex(ValueError,'activation role/coverage/order'):f.validate()


class QualificationScopeTest(unittest.TestCase):
    def test_invalid_modes_and_scope_combinations_fail_before_any_setup(self):
        for options in (dict(mode=MODE),dict(mode=package.MODES[0],workload=True),dict(mode='unknown'),
                        dict(mode=MODE,workload=True,physical=True),dict(mode=MODE,workload=True,backup=True)):
            with self.assertRaises(ValueError):qualification.run('not-created','not-a-bundle','a'*40,**options)
        self.assertFalse(Path('not-created').exists())


if __name__=='__main__':unittest.main()
