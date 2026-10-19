from copy import deepcopy
import fcntl
import os
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from . import remote_partition_guest as g,remote_partition as client,remote_partition_scope as scope
from . import remote_partition_qualification as q,remote_delivery_package as package
from . import remote_voter as v,remote_voter_lifecycle as lifecycle,remote_partition_evidence as evidence
from . import test_remote_delivery as delivery_fixture
from . import test_remote_voter_ssh as ssh_fixture


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.control=self.root/'node-1-control';self.control.mkdir(mode=0o700)
        self.config=dict(root=str(self.root),node='node-1',host=v.host.observe(self.control))
        self.cut=dict(operation='cut',target='node-3');self.heal=dict(operation='heal',target='node-3')
        self.cleanup=dict(operation='cleanup',target=None)
        self.ready=patch.object(g.lifecycle,'inspection',return_value={'state':'READY'});self.ready.start();self.addCleanup(self.ready.stop)
    def apply(self,command):return g.apply(self.control,self.config,command)
    def query(self,command):return g.query(self.control,self.config,command)


class TransitionTest(Fixture):
    def test_exact_bidirectional_cut_then_heal_with_one_original_result(self):
        cut=self.apply(self.cut)
        self.assertEqual(b'node-1 node-3\nnode-2 node-3\nnode-3 node-1\nnode-3 node-2\n',(self.root/g.FILE).read_bytes())
        client.observed(cut,self.config,self.cut)
        with patch.object(g,'publish',side_effect=AssertionError('replayed mutation')):
            self.assertEqual(cut,self.apply(self.cut))
        healed=self.apply(self.heal);self.assertEqual(b'',(self.root/g.FILE).read_bytes())
        self.assertEqual(cut['result']['afterSha256'],healed['result']['beforeSha256'])
        with patch.object(g,'publish',side_effect=AssertionError('reapplied stale cut')):
            self.assertEqual(cut['result'],self.apply(self.cut)['result'])
        self.assertEqual(b'',(self.root/g.FILE).read_bytes())

    def test_unknown_action_payload_target_and_arbitrary_path_reject(self):
        for command in ({'operation':'kill','target':'node-3'},dict(self.cut,path='/tmp/x'),
                        dict(self.cut,target='node-4'),dict(self.cut,target=None),dict(self.cleanup,target='node-1')):
            with self.assertRaises(ValueError):self.apply(command)
        self.assertFalse((self.root/g.FILE).exists())
        with self.assertRaises(ValueError):g.exchange('shell',self.control,{'argv':['sh']})

    def test_heal_without_cut_and_changed_target_reject(self):
        with self.assertRaisesRegex(ValueError,'original cut'):self.apply(self.heal)
        self.apply(self.cut)
        for command in (dict(self.cut,target='node-2'),dict(self.heal,target='node-2')):
            with self.assertRaisesRegex(ValueError,'consumed request changed'):self.apply(command)

    def test_partial_claim_is_consumed_and_not_reissued(self):
        store=self.control/'partition';store.mkdir(mode=0o700);(store/'cut-request.json.writing').write_text('partial')
        with patch.object(g,'publish') as publish:
            self.assertEqual('UNCERTAIN',self.apply(self.cut)['state']);publish.assert_not_called()

    def test_lost_execution_before_file_write_is_uncertain_and_cleanup_is_separate(self):
        with patch.object(g,'publish',side_effect=OSError('write failed')):
            with self.assertRaises(OSError):self.apply(self.cut)
        with patch.object(g,'publish') as publish:
            self.assertEqual('UNCERTAIN',self.apply(self.cut)['state']);publish.assert_not_called()
        self.apply(self.cleanup);self.assertEqual(b'',(self.root/g.FILE).read_bytes())
        self.assertEqual('UNCERTAIN',self.query(self.cut)['state'])
        with self.assertRaisesRegex(ValueError,'cleanup consumed'):self.apply(self.heal)

    def test_lost_execution_after_write_is_not_promoted_to_success(self):
        original=v.c.write_once
        def write(path,value,*args):
            if path.name=='cut-result.json':raise OSError('lost publication')
            return original(path,value,*args)
        with patch.object(v.c,'write_once',side_effect=write):
            with self.assertRaises(OSError):self.apply(self.cut)
        self.assertEqual(g.body(self.cut),(self.root/g.FILE).read_bytes())
        self.assertEqual('UNCERTAIN',self.apply(self.cut)['state'])
        self.apply(self.cleanup);self.assertEqual(b'',(self.root/g.FILE).read_bytes())

    def test_cleanup_can_heal_partial_temporary_file_but_not_repair_original_receipt(self):
        self.apply(self.cut);(self.root/'network-blocks.pending').write_text('partial')
        with self.assertRaises(FileExistsError):self.apply(self.heal)
        self.apply(self.cleanup)
        self.assertEqual('UNCERTAIN',self.query(self.heal)['state'])
        self.assertFalse((self.root/'network-blocks.pending').exists())
        self.assertEqual(b'',(self.root/g.FILE).read_bytes())

    def test_foreign_file_or_changed_live_cut_rejects(self):
        (self.root/g.FILE).write_text('foreign')
        with self.assertRaisesRegex(ValueError,'fresh control'):self.apply(self.cut)
        (self.root/g.FILE).unlink();self.apply(self.cut);(self.root/g.FILE).write_bytes(b'')
        with self.assertRaisesRegex(ValueError,'original cut'):self.apply(self.heal)

    def test_linked_control_file_is_never_followed(self):
        victim=self.root/'victim';victim.write_text('preserve');(self.root/g.FILE).symlink_to(victim)
        with self.assertRaises(OSError):self.apply(self.cut)
        (self.root/g.FILE).unlink();os.link(victim,self.root/g.FILE)
        with self.assertRaisesRegex(ValueError,'bound/type'):self.apply(self.cut)
        self.assertEqual('preserve',victim.read_text())

    def test_query_rejects_replaced_receipt_directory(self):
        elsewhere=self.root/'foreign';elsewhere.mkdir(mode=0o700)
        (self.control/'partition').symlink_to(elsewhere,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'directory symlink'):self.query(self.cut)

    def test_fifo_control_is_rejected_without_blocking(self):
        os.mkfifo(self.root/g.FILE)
        with self.assertRaisesRegex(ValueError,'bound/type'):self.query(self.cut)

    def test_overlapping_transition_fails_fast_without_new_claim(self):
        store=self.control/'partition';store.mkdir(mode=0o700)
        with (store/'lock').open('wb') as lock:
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):self.apply(self.cut)
        self.assertFalse((store/'cut-request.json').exists())

    def test_absent_original_service_prevents_fault_but_not_cleanup(self):
        with patch.object(g.lifecycle,'inspection',return_value={'state':'FAILED'}):
            with self.assertRaisesRegex(ValueError,'ready voter'):self.apply(self.cut)
            self.assertEqual('APPLIED',self.apply(self.cleanup)['state'])

    def test_seal_requires_stopped_healed_noncleanup_history(self):
        self.apply(self.cut);self.apply(self.heal)
        with self.assertRaisesRegex(ValueError,'stopped voters'):g.seal(self.control,self.config)
        with patch.object(g.lifecycle,'inspection',return_value={'state':'STOPPED'}):
            g.seal(self.control,self.config);g.seal(self.control,self.config)
            self.apply(self.cleanup)
            with self.assertRaisesRegex(ValueError,'cleanup/partial'):g.seal(self.control,self.config)

    def test_false_or_changed_guest_receipt_rejects(self):
        answer=self.apply(self.cut)
        for mutate in (lambda r:r.update(state='UNCERTAIN'),lambda r:r.update(currentSha256='0'*64),
                       lambda r:r['result'].update(afterSha256='0'*64),lambda r:r['result'].update(endNanos=0),
                       lambda r:r['result']['process'].update(bootId='foreign')):
            bad=deepcopy(answer);mutate(bad)
            with self.assertRaises(ValueError):client.observed(bad,self.config,self.cut)


class ControllerTest(Fixture):
    def controller(self):
        obj=object.__new__(client.Controller);obj.worker=SimpleNamespace(node='node-1',config=self.config)
        obj.endpoint=Mock();obj.calls=[];obj.losses=[];obj.records=[];return obj

    def test_lost_cut_or_heal_reply_only_queries_original_once(self):
        cut=self.apply(self.cut);heal=self.apply(self.heal)
        for request,answer in ((self.cut,cut),(self.heal,heal)):
            obj=self.controller();obj.exchange=Mock(return_value=answer)
            self.assertEqual(answer,obj.transition(request,discard=True)['answer'])
            self.assertEqual(['apply','query'],[c.args[0] for c in obj.exchange.call_args_list])
            self.assertEqual([request['operation']],obj.losses)

    def test_permanent_rejection_never_retries_or_queries(self):
        for code in g.ERRORS:
            obj=self.controller();obj.exchange=Mock(side_effect=lifecycle.Rejected(code))
            with self.assertRaises(lifecycle.Rejected):obj.transition(self.cut)
            obj.exchange.assert_called_once_with('apply',self.cut)

    def test_uncertain_query_stops_instead_of_waiting_until_phase_budget(self):
        obj=self.controller();obj.exchange=Mock(side_effect=[TimeoutError(),dict(state='UNCERTAIN',request=self.cut,result=None,currentSha256=None)])
        with self.assertRaisesRegex(ValueError,'incomplete'):obj.transition(self.cut)
        self.assertEqual(2,obj.exchange.call_count);self.assertEqual([],obj.records)

    def test_receiver_waits_for_all_acks_and_never_controls_guest_paths_locally(self):
        obj=object.__new__(q.Receivers);obj.controls={node:Mock() for node in v.h.topology.NODES};obj.collected=self.root
        obj.cut_target=None;obj.partition_record=dict(transitions=[],cleanup=[])
        barrier=threading.Barrier(3)
        def concurrent(*args,**kwargs):barrier.wait(timeout=2);return {}
        for endpoint in obj.controls.values():endpoint.transition.side_effect=concurrent
        with patch.object(q.h.recovery,'partition') as publish:
            obj.partition('node-3');publish.assert_called_once_with(self.root,'node-3')
        self.assertEqual(3,len(obj.partition_record['transitions'][0]['nodes']))
        with patch.object(q.h.recovery,'partition') as publish:
            obj.partition();publish.assert_called_once_with(self.root,None)

    def test_partial_cut_failure_does_not_advance_and_cleanup_is_independent(self):
        obj=object.__new__(q.Receivers);obj.controls={node:Mock() for node in v.h.topology.NODES};obj.collected=self.root
        obj.cut_target=None;obj.partition_record=dict(transitions=[],cleanup=[]);obj.workers={n:Mock() for n in v.h.topology.NODES}
        for endpoint in obj.controls.values():endpoint.transition.return_value={}
        obj.controls['node-2'].transition.side_effect=ValueError('permanent')
        with patch.object(q.h.recovery,'partition') as publish:
            with self.assertRaisesRegex(ValueError,'permanent'):obj.partition('node-3')
            publish.assert_not_called()
        self.assertIsNone(obj.partition_record['transitions'][0]['endNanos'])
        self.assertEqual(2,len(obj.partition_record['transitions'][0]['nodes']))
        errors=[]
        def retain(node,action):
            try:action()
            except ValueError:errors.append(node)
        obj.cleanup_partition(retain)
        self.assertEqual(['node-2'],errors);self.assertEqual(3,len(obj.partition_record['cleanup']))
        self.assertEqual(b'',(self.root/g.FILE).read_bytes())


class ScopeTest(delivery_fixture.Fixture):
    def recovery(self):
        bound={k:v for k,v in self.binding.items() if k!='driverExercise'};plan=scope.recovery.profile(scope.CASE)
        bound.update(measurementProfile=plan,faultParameters=plan['faultParameters'],readParameters=scope.options.parameters(),programSha256=scope.model.PLAN_SHA)
        package.h.runtime.save(self.producer/scope.recovery.FILE,plan['faultParameters']);return bound
    def test_exact_frozen_partition_history_and_parameter_capsule_accepted(self):
        bound=self.recovery();archive,meta=package.create(self.producer,self.root/'formal',bound)
        self.assertEqual(bound['measurementProfile'],meta['recovery']);self.assertIn(scope.recovery.FILE,meta['members'])
        destination=package.h.bundle.unpack(archive,self.parent/'node-1');package.installed(destination,meta)
        (destination/scope.recovery.FILE).write_text('{}')
        with self.assertRaisesRegex(ValueError,'installed input changed'):package.installed(destination,meta)
    def test_other_formal_histories_and_changed_frozen_limits_stay_rejected(self):
        for mutate in (lambda b:b['measurementProfile'].update(case=scope.recovery.CASES[0]),
                       lambda b:b['measurementProfile'].update(recoverySeconds=81),lambda b:b.update(driverExercise=True),
                       lambda b:b.update(programSha256='0'*64),lambda b:b['faultParameters'].update(case='foreign')):
            bad=deepcopy(self.recovery());mutate(bad)
            with self.assertRaises(ValueError):scope.history(bad)
        bad=deepcopy(self.binding);bad['remotePartition']=scope.EXECUTION
        with self.assertRaisesRegex(ValueError,'whole untimed'):scope.history(bad)
    def test_changed_or_omitted_package_scope_cannot_remove_required_parameter(self):
        archive,meta=package.create(self.producer,self.root/'formal',self.recovery())
        bad=deepcopy(meta);bad.pop('recovery')
        with self.assertRaisesRegex(ValueError,'closed file'):package.validate(bad)
        bad=deepcopy(meta);bad['members'].pop(scope.recovery.FILE)
        with self.assertRaisesRegex(ValueError,'closed file'):package.validate(bad)


class PreparedChannelTest(unittest.TestCase):
    setUp=ssh_fixture.EndpointTest.setUp
    def test_fixed_partition_entry_and_reuse_do_not_spawn_per_transition(self):
        endpoint=client.Endpoint(self.target,v.h.ROOT);self.addCleanup(endpoint.close)
        channel=Mock();sha='a'*64;host=v.host.observe(self.root)
        ready=dict(ready=True,configSha256=sha,host=host,process=v.process(os.getpid()));reply=dict(configSha256=sha,host=host,answer={})
        with patch.object(endpoint,'open',return_value=channel) as opened,patch.object(endpoint,'answer',side_effect=[ready,reply,reply]):
            value=dict(configSha256=sha,request=dict(operation='cleanup',target=None))
            endpoint.exchange('query',self.root,value,time.monotonic()+30)
            endpoint.exchange('query',self.root,value,time.monotonic()+30)
            opened.assert_called_once();self.assertEqual(2,channel.sendall.call_count)
        self.assertEqual(g.STREAM_LAUNCH,endpoint.protocol.LAUNCH)
        endpoint.close();channel.finish.assert_called_once()

    def test_changed_credential_on_existing_channel_rejects_before_send(self):
        endpoint=client.Endpoint(self.target,v.h.ROOT);self.addCleanup(endpoint.close)
        channel=Mock();endpoint.channel=channel;endpoint.control=self.root;endpoint.sha='a'*64
        (self.root/'key').write_text('changed')
        with self.assertRaisesRegex(ValueError,'credentials changed'):
            endpoint.exchange('apply',self.root,dict(configSha256='a'*64,request={}),time.monotonic()+30)
        channel.sendall.assert_not_called()

    def test_uncertain_stream_is_closed_without_internal_resubmit(self):
        endpoint=client.Endpoint(self.target,v.h.ROOT);self.addCleanup(endpoint.close)
        channel=Mock();endpoint.channel=channel;endpoint.control=self.root;endpoint.sha='a'*64
        with patch.object(endpoint,'answer',side_effect=ConnectionError('lost')):
            with self.assertRaises(ConnectionError):endpoint.exchange('apply',self.root,dict(configSha256='a'*64,request={}),time.monotonic()+30)
        channel.sendall.assert_called_once();channel.finish.assert_called_once();self.assertIsNone(endpoint.channel)

    def test_channel_exhaustion_fails_before_opening_or_sending(self):
        endpoint=client.Endpoint(self.target,v.h.ROOT);self.addCleanup(endpoint.close);endpoint.streams=[None]*4
        with patch.object(endpoint,'open') as opened:
            with self.assertRaisesRegex(ValueError,'channels exhausted'):
                endpoint.exchange('query',self.root,dict(configSha256='a'*64,request={}),time.monotonic()+30)
            opened.assert_not_called()

    def test_prepared_guest_rechecks_exact_config_and_owner_before_fault(self):
        config=dict(host={},binding={});sha=v.digest(v.encoded(config));value=dict(configSha256=sha,request={})
        with patch.object(v.c,'read',return_value={}),patch.object(g,'apply') as apply:
            with self.assertRaisesRegex(ValueError,'owner changed'):g.prepared_exchange('apply',self.root,value,config)
            apply.assert_not_called()
        with patch.object(v.c,'read',return_value=config),patch.object(v.host,'observe',return_value={'changed':True}),patch.object(g,'apply') as apply:
            with self.assertRaisesRegex(ValueError,'owner changed'):g.prepared_exchange('apply',self.root,value,config)
            apply.assert_not_called()

    def test_prepared_guest_checks_scope_without_reloading_source_per_command(self):
        bound=dict(remotePartition=scope.EXECUTION);plan=scope.recovery.profile(scope.CASE)
        bound.update(measurementProfile=plan,faultParameters=plan['faultParameters'],mode='candidate-minimum',
                     readParameters=scope.options.parameters(),programSha256=scope.model.PLAN_SHA)
        config=dict(host={},binding=bound);value=dict(configSha256=v.digest(v.encoded(config)),request={})
        with patch.object(v.c,'read',return_value=config),patch.object(v.host,'observe',return_value={}),\
             patch.object(g,'query',return_value='original') as query,patch.object(g.lifecycle,'load') as load:
            self.assertEqual('original',g.prepared_exchange('query',self.root,value,config)['answer'])
            query.assert_called_once();load.assert_not_called()
            with self.assertRaisesRegex(ValueError,'envelope'):g.prepared_exchange('apply',self.root,dict(value,pid=1),config)


if __name__=='__main__':unittest.main()
