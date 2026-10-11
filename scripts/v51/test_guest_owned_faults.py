"""Owned fault scope, consumed operations, deadlines and independent rejection checks."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import sys
import time
import unittest
from unittest.mock import Mock, patch
from . import cloud_guest, cloud_fake, cloud_runner, guest_owned_faults as faults
from . import guest_fault_service as service, guest_fault_evidence as evidence, remote_command as c
from .test_guest_service import config
from . import test_guest_owned_workload as common


class FaultDiagnosticTest(unittest.TestCase):
    def test_original_trace_bound_reaches_controller_and_safe_runner_code(self):
        from .guest_fault_jvm import Jvm
        from . import cloud_runner_diagnostics as diagnostics
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            script='''import json,os,sys,pathlib
pathlib.Path(sys.argv[1],"node-1-trace.jsonl").write_text(json.dumps(dict(node="node-1",pid=os.getpid(),generation=1,order=1))+"\\n")
print(json.dumps(dict(status="STARTED",pid=os.getpid())),flush=True)
sys.stdin.readline()
print("private-secret\\nCaused by: java.io.IOException: remote fault trace per-node bound",file=sys.stderr,flush=True)
sys.exit(1)
'''
            jvm=Jvm([sys.executable,'-c',script,temp],root,'node-1',1,time.monotonic()+15)
            try:
                with self.assertRaisesRegex(ValueError,'^remote fault trace per-node bound$'):jvm.command('status')
                with self.assertRaisesRegex(ValueError,'^remote fault trace per-node bound$'):jvm.submit('read')
            finally:
                with self.assertRaises(ValueError):jvm.stop()
            self.assertEqual(1,len(jvm.rows))
            cell=faults.Cell(SimpleNamespace(clients=[],provider=SimpleNamespace(req={})),root/'cell','leader-loss')
            cell.execute=Mock(return_value=dict(state='FAILED',error=jvm.rows[0]['failure']))
            with self.assertRaises(ValueError) as caught:cell.succeeded(None,'fault',{},0)
            result=diagnostics.runtime_failure('execution',caught.exception)
            self.assertEqual('RUNTIME_TRACE_CAPACITY',result['code']);self.assertNotIn('private-secret',str(result))
            self.assertEqual(1,cell.execute.call_count)

    def test_only_exact_bounded_stderr_line_classifies_eof(self):
        from .guest_fault_jvm import Jvm, Pipes
        with tempfile.TemporaryDirectory() as temp:
            jvm=Jvm.__new__(Jvm);jvm.root=Path(temp);jvm.prefix='node-1-g1'
            exact='Caused by: java.io.IOException: remote fault trace per-node bound'
            for text in ('remote fault trace per-node bound',
                         'private-secret: Caused by: java.io.IOException: remote fault trace per-node bound',
                         'Caused by: java.io.IOException: remote fault trace per-node bound extra',
                         'private-secret '+exact+'\n'+'x'*(8192-len(exact)-2),
                         exact+'\n'+'x'*8192,
                         'unrelated failure'):
                (jvm.root/(jvm.prefix+'-stderr.log')).write_text(text+'\n')
                with patch.object(Pipes,'line',side_effect=ValueError('guest JVM EOF')):
                    with self.assertRaisesRegex(ValueError,'^guest JVM EOF$'):jvm.line(1)
            (jvm.root/(jvm.prefix+'-stderr.log')).write_text('x'*10000+'\n'+exact+'\n')
            with patch.object(Pipes,'line',side_effect=ValueError('guest JVM EOF')):
                with self.assertRaisesRegex(ValueError,'^remote fault trace per-node bound$'):jvm.line(1)
            with patch.object(Pipes,'line',side_effect=TimeoutError('original deadline')):
                with self.assertRaisesRegex(TimeoutError,'original deadline'):jvm.line(1)

    def test_unrecognized_remote_failure_is_not_promoted_to_a_safe_code(self):
        from . import cloud_runner_diagnostics as diagnostics
        with tempfile.TemporaryDirectory() as temp:
            cell=faults.Cell(SimpleNamespace(clients=[],provider=SimpleNamespace(req={})),Path(temp)/'cell','leader-loss')
            cell.execute=Mock(return_value=dict(state='FAILED',error=dict(type='ValueError',message='private-secret remote fault trace per-node bound')))
            with self.assertRaises(ValueError) as caught:cell.succeeded(None,'fault',{},0)
            result=diagnostics.runtime_failure('execution',caught.exception)
            self.assertEqual('UNCLASSIFIED',result['code']);self.assertNotIn('private-secret',str(result))


class ScopeTest(unittest.TestCase):
    def test_fault_service_accepts_only_declared_automatic_cells(self):
        good=config(Path('/tmp/fault-qualification'))
        for case in service.CASES:cloud_guest.validate(dict(good,faultCell=case))
        for change in ({'faultCell':'undeclared-fault'},{'faultCell':'leader-loss','mode':'published-v5.0-configured'},
                       {'faultCell':'leader-loss','duration':30}):
            with self.assertRaises(ValueError):cloud_guest.validate(dict(good,**change))
    def test_closed_runner_scope_and_exact_two_cells(self):
        req,_,_=cloud_fake.fixture();clock=cloud_fake.Clock();store=cloud_fake.Store();provider=cloud_fake.Provider(req,clock)
        probe=SimpleNamespace(execution=cloud_fake.a.EXECUTION,scope=faults.SCOPE,mode=faults.MODE,services=object())
        startup=SimpleNamespace(execution=probe.execution,services=probe.services)
        runner=cloud_runner.Runner(store,provider,probe,'/tmp/unused-fault-runner',qualification=faults.SCOPE,startup=startup)
        self.assertEqual(runner.qualification_cells,['leader-loss','no-quorum'])
        with self.assertRaises(ValueError):cloud_runner.Runner(store,provider,probe,'/tmp/unused-fault-runner',startup=startup)
    def test_native_and_fault_options_cannot_be_combined_with_healthy_scope(self):
        from .guest_owned_qualification import run
        for options in (dict(fault_local=True),dict(faults=True,three_mode=True),dict(faults=True,workload=True),dict(faults=True,bootstrap=True)):
            with self.assertRaises(ValueError):run('/unused','/unused','a'*40,**options)


class HandlerTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        cfg=dict(config(self.root),faultCell='leader-loss')
        self.jvm=Mock(closed=False,proc=SimpleNamespace(returncode=None))
        self.s=SimpleNamespace(config=cfg,cell=self.root,root=self.root,base=Path('/package'),node='node-1',jvm=self.jvm)
        self.handler=service.Handler(self.s);self.handler.generation=1
    def call(self,name,payload):return self.handler.handle(name,payload,lambda:None)
    def test_restart_before_confirmed_sigkill_rejected(self):
        with self.assertRaises(ValueError):self.call('fault',dict(action='restart'))
    def test_fresh_call_id_claim_survives_uncertain_original(self):
        payload=dict(action='call',kind='read',intentId='call-01');self.jvm.command.side_effect=TimeoutError('uncertain')
        with self.assertRaises(TimeoutError):self.call('fault',payload)
        self.assertTrue((self.root/'calls/call-01.json').exists())
        with self.assertRaises(FileExistsError):self.call('fault',payload)
        self.assertEqual(self.jvm.command.call_count,1)
    def test_no_arbitrary_argv_path_rule_duration_or_operation(self):
        for payload in (dict(action='isolate',seconds=30),dict(action='heal',rules=[]),dict(action='status',path='/tmp'),
                        dict(action='call',kind='checkpoint',intentId='call-01'),dict(action='call',kind='read',intentId='call-25')):
            with self.assertRaises(ValueError):self.call('fault',payload)
        self.jvm.command.assert_not_called()
    def test_isolation_has_independent_watchdog_and_cannot_be_rearmed(self):
        self.handler.case='no-quorum'
        with patch.object(service.threading,'Timer') as timer:
            result=self.call('fault',dict(action='isolate'))
            self.assertEqual(result['rules'],service.RULES);self.assertEqual(timer.call_args.args[0],17)
            with self.assertRaises(ValueError):self.call('fault',dict(action='isolate'))
            timer.call_args.args[1]()
            receipt=c.read(self.root/'isolation.json');self.assertTrue(receipt['watchdog'])
            self.assertEqual(self.call('fault',dict(action='heal')),receipt)
            self.assertEqual((self.root/'network-rules.txt').read_text(),'\n')
    def test_retained_restart_rejects_changed_original_storage(self):
        self.jvm.closed=True;self.jvm.proc.returncode=-9
        for root in (self.root/'node-1',self.root/'crash/node-1'):root.mkdir(parents=True);(root/'file').write_bytes(b'old')
        (self.root/'node-1/file').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'authority changed'):self.call('fault',dict(action='restart'))
    def test_no_quorum_never_accepts_kill(self):
        self.handler.case='no-quorum'
        with self.assertRaisesRegex(ValueError,'kill scope'):self.call('stop-voter',dict(forced=True))
        self.jvm.stop.assert_not_called()
    def test_collection_of_live_voter_rejected(self):
        with self.assertRaisesRegex(ValueError,'stopped collection'):self.call('collect',dict(physical=True))

    def test_stopped_collection_packs_complete_segments_without_changing_original(self):
        from . import public_trace, remote_collection as parts, performance_model as m
        self.jvm.closed=True
        self.s.root=self.root/'agents/node-1';self.s.root.mkdir(parents=True)
        (self.s.root/'store').mkdir();self.s.current=dict(commandId='collect-once')
        rows=[m.canonical(dict(node='node-1',pid=41,generation=1,order=i+1,localNanos=i+1,payload='x'*200))+b'\n' for i in range(5)]
        original=b''.join(rows);path=self.root/'node-1-trace.jsonl';path.write_bytes(original)
        with patch.object(service.authority,'capture'),patch.object(public_trace,'FAULT_SEGMENT_BYTES',500):
            result=self.call('collect',dict(physical=True))
        parts.unpack(self.s.root/'parts',self.root/'retained',m.sha(m.canonical(self.s.config['binding'])))
        self.assertEqual(5,len(public_trace.fault_rows(self.root/'retained','node-1')))
        self.assertEqual(original,path.read_bytes())
        self.assertGreater(len(list((self.root/'retained').glob('*-trace*.jsonl'))),1)
        self.assertEqual(result,c.read(self.s.root/'parts/parts.json'))


class ControllerTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.clock=cloud_fake.Clock();members=[(n,Mock(),{}) for n in (1,2,3)]
        self.cell=faults.Cell(SimpleNamespace(clients=members,provider=SimpleNamespace(req={})),self.root/'cell','leader-loss',clock=self.clock.seconds,sleep=self.clock.sleep)
        self.cell.end=self.clock.seconds()+120
    def test_uncertain_stop_is_not_replayed(self):
        self.cell.succeeded=Mock(side_effect=ConnectionError('lost'))
        with self.assertRaises(ConnectionError):self.cell.stop_node('node-1',True)
        self.cell.stop_node('node-1',True);self.cell.succeeded.assert_called_once()
    def test_four_fresh_progress_pairs_cannot_replay_uncertain_mutation(self):
        self.cell.leader=Mock(return_value='node-2');calls=[]
        def call(node,kind,**values):
            calls.append((kind,values));return dict(outcome='INDETERMINATE' if kind=='addAll' else 'NOT_APPLICABLE')
        self.cell.call=call
        with self.assertRaisesRegex(ValueError,'attempts exhausted'):self.cell.progress(self.cell.end)
        self.assertEqual([v['documents'][0]['id'] for k,v in calls if k=='addAll'],[100,110,120,130])
        self.assertEqual(len(calls),8)
    def test_final_slow_call_does_not_extend_progress_deadline(self):
        self.cell.leader=Mock(return_value='node-1')
        def call(*args,**kwargs):self.clock.sleep(31);return dict(outcome='SUCCESS')
        self.cell.call=call
        with self.assertRaisesRegex(ValueError,'progress deadline'):self.cell.progress(self.clock.seconds()+60)
    def test_case_and_aggregate_order_consumed(self):
        self.cell.attempted=True
        with self.assertRaisesRegex(ValueError,'consumed'):self.cell.run(self.clock.nanos()+120*10**9)
        req,_,_=cloud_fake.fixture();services=SimpleNamespace(offline=True,mode=faults.MODE,provider=SimpleNamespace(req=req))
        probe=faults.Probe(services,self.root/'probe')
        with self.assertRaisesRegex(ValueError,'order'):probe.cell('no-quorum',0)
    def test_partial_parallel_failure_still_observes_other_results(self):
        seen=[]
        def attempt(v):
            seen.append(v[0])
            if v[0]==1:raise ValueError('first')
        with self.assertRaisesRegex(ValueError,'first'):self.cell.parallel(attempt)
        self.assertEqual(sorted(seen),[1,2,3])


class FaultRunnerTest(common.RunnerWorkloadTest):
    def test_partial_scope_runs_only_healthy_and_preserves_cleanup_and_charge(self):
        result=self.run_case();self.assertEqual(result['status'],'PASS',result['errors'])
        self.assertEqual([v.args[0] for v in self.probe.cell.call_args_list],list(faults.CASES))
        self.assertTrue(result['leaseReleased']);self.assertFalse(result['fullRemoteQualification'])
        self.assertFalse(self.provider.objects)
    def setUp(self):
        super().setUp();self.probe.mode=faults.MODE;self.probe.scope=faults.SCOPE
        self.probe.collect_validate.return_value.update(mode=faults.MODE,scope=faults.SCOPE,cells=list(faults.CASES))


class EvidenceTest(unittest.TestCase):
    def test_package_plan_uses_file_hash_and_rejects_canonical_or_wrong_source(self):
        req={'source':'a'*40};raw=evidence.m.sha(evidence.contract.PLAN.read_bytes())
        self.assertNotEqual(raw,evidence.contract.PLAN_SHA256)
        manifest=dict(source=req['source'],workloadSha256=raw)
        evidence.package_binding(manifest,req)
        for changed in (dict(manifest,workloadSha256=evidence.contract.PLAN_SHA256),dict(manifest,source='b'*40)):
            with self.assertRaisesRegex(ValueError,'source/plan'):evidence.package_binding(changed,req)
    def sample(self):
        queues={k:0 for k in ('orderedQueue','deadlinesQueue','inputsQueue','completionsQueue','networkQueue','appQueue',
                'clientsQueue','queuedBytes','authorityDiskBytes','transferDiskBytes','maintenancePending','pinsBytes','stagingBytes')}
        queues.update(admissionAvailable=4,inboundAvailable=8,outboundAvailable=[dict(node=n,available=2) for n in evidence.faults.NODES])
        return dict(event='PERFORMANCE_SAMPLE',boundary='start',localNanos=2,samplingStartNanos=1,queues=queues,
                    heapUsedBytes=1,heapMaxBytes=512<<20,VmRSSBytes=1,threads=1,retainedBytes=0,gcCount=0,gcMillis=0,cpuNanos=0,processIo={'read_bytes':0})
    def test_transport_samples_include_self_and_reject_missing_duplicate_or_leaked_permits(self):
        start=self.sample();closed=deepcopy(start);closed['boundary']='closed'
        evidence.resource_samples([start,closed],False)
        for peers in (start['queues']['outboundAvailable'][:2], [dict(node='node-1',available=2)]*3,
                      [dict(node=n,available=1) for n in evidence.faults.NODES]):
            changed=deepcopy(closed);changed['queues']['outboundAvailable']=peers
            with self.assertRaises(ValueError):evidence.resource_samples([start,changed],False)
    def test_missing_clean_sampling_boundary_is_only_allowed_for_killed_process(self):
        evidence.resource_samples([self.sample()],True)
        with self.assertRaisesRegex(ValueError,'sampling boundaries'):evidence.resource_samples([self.sample()],False)
    def test_activation_bound_deduplicates_votes_but_not_distinct_noops(self):
        from . import format_encoder as enc, storage_fixture as fixture
        import base64,json
        samples=json.loads((enc.CATALOG.parent/'format-fixtures.json').read_text())['storage']
        manifest=base64.b64decode(samples['MANIFEST']);base=fixture.records(manifest)
        vote=evidence.f.inspect(base['ACCEPT'],'ACCEPT');entry=evidence.f.inspect(evidence.faults.a.raw(vote['entry']),'ENTRY')
        trace=[]
        for i in range(66):
            value=enc.encode('ENTRY',dict(entry,index=i+1,previousIndex=i,operation=9,payload='',payloadDigest=evidence.m.sha(b'')))
            accepted=enc.encode('ACCEPT',dict(vote,entry=fixture.b64(value),entryDigest=value[16:48].hex()))
            trace.append(dict(event='FORCE',kind='ACCEPT',record=fixture.b64(accepted)))
        history=[dict(kind='read')]
        evidence.logical_bounds(history,{'node-1':trace[:65],'node-2':trace[:65]},65)
        with self.assertRaisesRegex(ValueError,'barrier ceiling'):evidence.logical_bounds(history,{'node-1':trace},66)
        with self.assertRaisesRegex(ValueError,'slot bound'):evidence.logical_bounds(history,{},513)
        with self.assertRaisesRegex(ValueError,'barrier ceiling'):evidence.logical_bounds([dict(kind='backup')]*9,{},1)
    def test_remote_pid_collisions_do_not_hide_processes_or_manufacture_restart(self):
        from . import storage_fixture as fixture, runtime_evidence as runtime
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture.create(root)
            traces={n:[dict(pid=42,event='DIAGNOSTIC',order=1)] for n in evidence.faults.NODES}
            # These deliberately incomplete traces must get past the process count,
            # while the independent execution-completeness check still rejects them.
            with patch.object(runtime,'application',return_value=([],{})):
                with self.assertRaisesRegex(ValueError,'incomplete runtime execution'):runtime.validate(root,traces,require_restart=False)
                with self.assertRaisesRegex(ValueError,'retained-disk restart required'):runtime.validate(root,traces)
                traces['node-1'].append(dict(pid=43,event='DIAGNOSTIC',order=1))
                with self.assertRaisesRegex(ValueError,'incomplete runtime execution'):runtime.validate(root,traces)


if __name__=='__main__':unittest.main()
