"""Closed drill commands, once-only crashes and complete offline admission."""
from concurrent.futures import Future
from copy import deepcopy
import base64
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from . import guest_fault_service as service, guest_fault_recovery as recovery, guest_fault_jvm as jvm
from . import guest_owned_drill as drill, guest_owned_experiment as experiment, cloud_guest, cloud_fake
from . import remote_command as c, guest_fault_evidence as evidence
from .test_guest_service import config
from . import test_guest_owned_workload as common
from . import guest_recovery_evidence as replay, format_encoder as encoder, fixtures


class DrillScopeTest(unittest.TestCase):
    def test_all_twelve_are_offline_and_native_keeps_three_faults(self):
        expected=('leader-loss','isolated-old-leader','asymmetric-requests','asymmetric-responses','slow-follower',
                  'interrupted-transfer','entry-chosen','proof-quorum','group-restart','maintenance','no-quorum','minority-capacity')
        self.assertEqual(expected,drill.CASES)
        for case in expected:
            cfg=dict(config(Path('/tmp/drill')),faultCell=case);cloud_guest.validate(cfg)
            cfg['execution']=cloud_guest.NATIVE_EXECUTION
            if case in service.CASES:cloud_guest.validate(cfg)
            else:
                with self.assertRaisesRegex(ValueError,'fault cell'):cloud_guest.validate(cfg)
        self.assertEqual(('healthy','leader-loss','maintenance','no-quorum'),experiment.CELLS)

    def test_every_offline_cell_uses_its_frozen_plan_budget(self):
        from . import native_experiment_timing as timing, cloud_workload_contract as plan
        for cell in plan.load()['cells']:
            self.assertEqual(cell['seconds'],timing.cell({},cell['name']))
        for case in recovery.CASES:
            with self.assertRaises(KeyError):timing.cell(dict(schema=timing.REQUEST_SCHEMA,timingProfile=timing.PROFILE),case)

    def test_partition_routes_to_each_guest_with_a_distinct_target_node(self):
        with tempfile.TemporaryDirectory() as temp:
            cell=drill.Cell(SimpleNamespace(clients=[(n,None,{}) for n in (1,2,3)],provider=SimpleNamespace(req={})),Path(temp)/'cell','interrupted-transfer')
            cell.end=time.monotonic()+30;cell.succeeded=Mock(return_value={'result':{}})
            cell.partition('node-2','isolate')
            self.assertEqual(3,cell.succeeded.call_count)
            for call in cell.succeeded.call_args_list:
                self.assertEqual({'action':'isolate','node':'node-2'},call.args[2])
            self.assertEqual({1,2,3},{v.args[0][0] for v in cell.succeeded.call_args_list})

    def test_partial_or_reordered_cases_cannot_close_drill(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);req,_,_=cloud_fake.fixture();c.write_once(root/'plan.json',dict(scope=drill.SCOPE,request=req))
            for index,cases in enumerate((drill.CASES[:-1],tuple(reversed(drill.CASES)),recovery.CASES)):
                with self.assertRaisesRegex(ValueError,'aggregate scope'):
                    evidence.validate(root,root/str(index),cases=cases,scope=drill.SCOPE)

    def test_closed_command_line_scope_does_not_admit_mixed_presets(self):
        from .guest_owned_qualification import run
        for name in ('network','experiment','maintenance','faults','workload','bootstrap'):
            with self.assertRaisesRegex(ValueError,'own scope'):
                run('/unused','/unused','a'*40,failure_drill=True,**{name:True})


class BoundedStartupTest(unittest.TestCase):
    def cell(self, initial='node-2', remaining=600):
        from .test_native_presets import request
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.now=0
        def sleep(seconds):self.now+=seconds
        cell=drill.Cell(SimpleNamespace(clients=[(n,None,{}) for n in (1,2,3)],
            provider=SimpleNamespace(req=request('failure-drill'))),Path(temp.name)/'cell',
            'minority-capacity',clock=lambda:self.now,sleep=sleep)
        cell.end=remaining;cell.command=Mock();cell.start=Mock();cell.leader=Mock(return_value=initial)
        return cell

    def states(self, leader, epoch=5, bounded='FOLLOWER', bounded_epoch=5):
        return {node:dict(state=bounded if node=='node-3' else ('LEADER_READY' if node==leader else 'FOLLOWER'),
                         epoch=bounded_epoch if node=='node-3' else epoch) for node in ('node-1','node-2','node-3')}

    def test_startup_reselects_either_healthy_leader_after_heal_without_mutation_replay(self):
        # Native run 37981974124 had node-2 ready at epoch 3 before healing,
        # then node-1 ready at epoch 5 while both other voters were followers.
        for initial,active in (('node-2','node-1'),('node-1','node-2'),('node-2','node-2')):
            with self.subTest(initial=initial,active=active):
                cell=self.cell(initial);states=self.states(active)
                cell.status=Mock(side_effect=lambda node,deadline=None:states[node])
                self.assertEqual(active,cell.start_group())
                self.assertEqual([],cell.history)
                self.assertEqual(3,cell.start.call_count)
                self.assertEqual(['prepare-direction']*3+['heal-direction']*3,
                                 [v.args[1] for v in cell.command.call_args_list])
                cell.leader.assert_called_once()

    def test_no_leader_wrong_epoch_or_bounded_leader_never_satisfies_fencing(self):
        ambiguous=self.states('node-1');ambiguous['node-2']['state']='LEADER_READY'
        for states in (self.states(None),self.states('node-1',bounded_epoch=4),
                       self.states(None,bounded='LEADER_READY'),self.states('node-1',bounded='CANDIDATE'),ambiguous):
            with self.subTest(states=states):
                cell=self.cell(remaining=.2);cell.status=Mock(side_effect=lambda node,deadline=None:states[node])
                with self.assertRaisesRegex(ValueError,'owned bounded voter initial fencing'):cell.start_group()
                self.assertEqual([],cell.history)

    def test_final_observation_arriving_at_or_after_deadline_cannot_pass(self):
        for arrival in (180,181):
            cell=self.cell()
            def status(node,deadline=None):
                if node=='node-3':self.now=arrival
                return self.states('node-1')[node]
            cell.status=Mock(side_effect=status)
            with self.assertRaisesRegex(ValueError,'owned bounded voter initial fencing'):cell.start_group()
            self.assertEqual(3,cell.status.call_count)

    def test_fencing_wait_has_one_deadline_and_accepts_only_before_it(self):
        for remaining,late in ((600,False),(600,True),(.15,True)):
            cell=self.cell(remaining=remaining);deadline=min(180,remaining);seen=[]
            def status(node,limit=None):
                seen.append(limit)
                if late:self.now=deadline+1
                else:self.now+=1
                return self.states('node-1' if late else None)[node]
            cell.status=Mock(side_effect=status)
            with self.assertRaisesRegex(ValueError,'owned bounded voter initial fencing'):cell.start_group()
            self.assertTrue(seen);self.assertEqual({deadline},set(seen))
            self.assertLessEqual(len(seen),180)

    def test_transient_election_can_converge_but_status_failure_is_not_swallowed(self):
        cell=self.cell()
        cell.status=Mock(side_effect=lambda node,deadline=None:self.states('node-1' if self.now else None)[node])
        self.assertEqual('node-1',cell.start_group())
        cell=self.cell();cell.status=Mock(side_effect=ConnectionError('lost status'))
        with self.assertRaisesRegex(ConnectionError,'lost status'):cell.start_group()
        self.assertEqual(1,cell.status.call_count)


class DrillRunnerTest(common.RunnerWorkloadTest):
    def setUp(self):
        super().setUp();self.probe.mode=drill.MODE;self.probe.scope=drill.SCOPE
        self.probe.collect_validate.return_value.update(mode=drill.MODE,scope=drill.SCOPE,cells=list(drill.CASES))
    def test_partial_scope_runs_only_healthy_and_preserves_cleanup_and_charge(self):
        result=self.run_case();self.assertEqual('PASS',result['status'],result['errors'])
        self.assertEqual(list(drill.CASES),[v.args[0] for v in self.probe.cell.call_args_list])
        self.assertTrue(result['leaseReleased']);self.assertFalse(result['fullRemoteQualification'])
    def test_missing_one_cell_rejects_complete_drill(self):
        self.probe.collect_validate.return_value['cells']=list(drill.CASES[:-1])
        self.assertEqual('FAIL',self.run_case()['status'])


class RecoveryHandlerTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.jvm=Mock(closed=False,identity=dict(pid=41,node='node-1',generation=1))
    def handler(self,case):
        return service.Handler(SimpleNamespace(config=dict(config(self.root),faultCell=case),cell=self.root,root=self.root,
            node='node-1',jvm=self.jvm))
    def command(self,h,**payload):return h.handle('fault',payload,lambda:None)

    def test_exact_large_documents_do_not_enable_arbitrary_sizes_or_tags(self):
        for case,size in (('interrupted-transfer',4096),('minority-capacity',20000)):
            self.assertTrue(recovery.bulk_allowed(case,recovery.documents(40,size)))
            for docs in (recovery.documents(40,size+1),recovery.documents(40,size-1),recovery.documents(80,size),[{}]):
                self.assertFalse(recovery.bulk_allowed(case,docs))
            self.assertFalse(recovery.bulk_allowed('leader-loss',recovery.documents(40,size)))
        self.assertFalse(recovery.bulk_allowed('interrupted-transfer',recovery.documents(60,4096)))
        self.assertTrue(recovery.bulk_allowed('minority-capacity',recovery.documents(60,20000)))

    def test_arm_is_one_fixed_cut_and_cannot_rearm(self):
        h=self.handler('entry-chosen');h.generation=1
        with self.assertRaises(ValueError):self.command(h,action='arm-cut',cut='PROOF_ACK_RECEIVED')
        result=self.command(h,action='arm-cut');self.assertEqual(recovery.CUTS[h.case],result['cut'])
        self.assertEqual('ACCEPT_ACK_RECEIVED\nkill\n',(self.root/'node-1-arm.txt').read_text())
        with self.assertRaisesRegex(ValueError,'consumed'):self.command(h,action='arm-cut')

    def test_target_claim_precedes_pipe_submission_and_survives_lost_reply(self):
        h=self.handler('proof-quorum');h.generation=1;self.command(h,action='arm-cut')
        self.jvm.submit.side_effect=ConnectionError('lost original pipe write')
        with self.assertRaises(ConnectionError):self.command(h,action='start-target',intentId='call-05')
        self.assertEqual({'action':'start-target','intentId':'call-05'},c.read(self.root/'target-claim.json'))
        with self.assertRaises(FileExistsError):self.command(h,action='start-target',intentId='call-05')
        self.jvm.submit.assert_called_once_with('addAll',intentId='call-05',documents=recovery.documents(40,512))

    def test_target_is_pending_and_never_calls_finish(self):
        h=self.handler('entry-chosen');h.generation=1;self.command(h,action='arm-cut')
        request=dict(kind='addAll',intentId='call-05',opId='node-1-g1-6',documents=recovery.documents(40,512));future=Future()
        self.jvm.submit.return_value=({'request':request},future)
        self.assertEqual(dict(identity=self.jvm.identity,request=request),self.command(h,action='start-target',intentId='call-05'))
        self.assertFalse(future.done());self.jvm.finish.assert_not_called()
        with self.assertRaisesRegex(ValueError,'consumed'):self.command(h,action='start-target',intentId='call-06')

    def test_cut_must_belong_to_current_process_before_sigkill(self):
        h=self.handler('interrupted-transfer');h.generation=1;self.command(h,action='arm-cut')
        cut=dict(event='CUT_REACHED',cut=recovery.CUTS[h.case],mode='kill',pid=40)
        with patch.object(recovery.public_trace,'live_rows',return_value=[cut]):
            with self.assertRaisesRegex(ValueError,'before original cut'):h.handle('stop-voter',dict(forced=True),lambda:None)
            self.jvm.stop.assert_not_called()
            cut['pid']=41;h.recovery.before_kill()

    def test_prepare_direction_consumed_and_watchdog_remains_invalid(self):
        h=self.handler('minority-capacity');h.s.jvm=None
        with patch.object(recovery.threading,'Timer') as timer:
            result=self.command(h,action='prepare-direction')
            self.assertEqual(60,timer.call_args.args[0]);self.assertEqual(4,len(result['rules']))
            with self.assertRaises(ValueError):self.command(h,action='prepare-direction')
            timer.call_args.args[1]();self.assertTrue(c.read(self.root/'prepare-isolation.json')['watchdog'])
            h.s.jvm=self.jvm
            self.assertTrue(self.command(h,action='heal-direction')['watchdog'])

    def test_capacity_isolation_needs_completed_initial_direction_and_fixed_target(self):
        h=self.handler('minority-capacity')
        with self.assertRaises(ValueError):self.command(h,action='isolate',node='node-3')
        h.recovery.direction_healed=True
        with self.assertRaises(ValueError):self.command(h,action='isolate',node='node-1')
        with patch.object(recovery.threading,'Timer') as timer:
            result=self.command(h,action='isolate',node='node-3');self.assertEqual(60,timer.call_args.args[0])
            self.assertTrue(all('node-3' in row.split()[:2] for row in result['rules']))
            self.assertFalse(self.command(h,action='heal')['watchdog'])
            with self.assertRaises(ValueError):self.command(h,action='isolate',node='node-3')

    def test_recovery_actions_reject_unadmitted_native_execution_and_arbitrary_inputs(self):
        h=self.handler('group-restart');h.s.config['execution']=cloud_guest.NATIVE_EXECUTION
        with self.assertRaisesRegex(ValueError,'native fault request missing'):self.command(h,action='observe-recovery')
        h.s.config['execution']=cloud_guest.EXECUTION
        for values in (dict(action='observe-recovery',path='/tmp'),dict(action='arm-cut'),dict(action='start-target',intentId='call-01'),
                       dict(action='isolate',node='node-1',seconds=70)):
            with self.assertRaises(ValueError):self.command(h,**values)

    def test_failed_retained_stop_is_consumed_before_a_second_attempt(self):
        cell=drill.Cell(SimpleNamespace(clients=[(1,None,{})],provider=SimpleNamespace(req={})),self.root/'cell','group-restart')
        cell.end=time.monotonic()+30;cell.succeeded=Mock(side_effect=ConnectionError('lost close'))
        with self.assertRaises(ConnectionError):cell.retained_stop('node-1')
        with self.assertRaisesRegex(ValueError,'consumed'):cell.retained_stop('node-1')
        cell.succeeded.assert_called_once()


class TransferPathTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.cell=drill.Cell(SimpleNamespace(clients=[(n,None,{}) for n in (1,2,3)],provider=SimpleNamespace(req={})),
                             self.root/'cell','interrupted-transfer',clock=lambda:1,sleep=lambda _:None)
        self.cell.end=10;self.cell.record['recipientCampaign']=None
        self.manifest=dict(groupId=fixtures.UUID,configurationId='transfer-test',digest='ab'*32,
                           members=[dict(node='node-'+str(n)) for n in (1,2,3)])
        envelope=dict(groupId=fixtures.UUID,configurationId='transfer-test',manifestDigest='ab'*32,
            protocol='gse-replication/1.2',epoch=2,incarnationId=fixtures.UUID,proposer='node-1',
            sender='node-1',recipient='node-3',eventSequence=7,traceId=fixtures.UUID)
        request=encoder.wire('HEARTBEAT',envelope,dict(activated=True,provenIndex=6,progressBytes=0,sequence=9,stage=7))
        response=encoder.wire('HEARTBEAT_ACK',dict(envelope,sender='node-3',recipient='node-1'),dict(provenIndex=5,sequence=9))
        self.heartbeat=dict(event='REPLY',node='node-3',pid=41,order=20,localNanos=12,
            request=base64.b64encode(request).decode(),frame=base64.b64encode(response).decode())
        self.cut=dict(event='CUT_REACHED',pid=41,localNanos=16)
        self.isolation=dict(appliedNanos=10,healedNanos=15)
        self.record=dict(case='interrupted-transfer',recipientHeartbeat=self.heartbeat,cut=self.cut,targetNode='node-3',seedLeader='node-1',
                         sourceFloor=dict(index=6),recipientCampaign=None)

    def test_transfer_partition_preserves_heartbeats_but_blocks_all_data_paths(self):
        for case in ('interrupted-transfer','minority-capacity'):
            with self.subTest(case=case):
                root=self.root/case;root.mkdir()
                h=service.Handler(SimpleNamespace(config=dict(config(root),faultCell=case),
                    cell=root,node='node-3',jvm=Mock(closed=False)))
                h.recovery.direction_healed=True
                with patch.object(recovery.threading,'Timer'):
                    value=h.handle('fault',dict(action='isolate',node='node-3'),lambda:None)
                def blocked(sender,recipient,kind):
                    return any(row in value['rules'] for row in (f'{sender} {recipient} BEFORE_REQUEST_WRITE *',
                                                                 f'{sender} {recipient} BEFORE_REQUEST_WRITE {kind}'))
                for peer in ('node-1','node-2'):
                    for sender,recipient in ((peer,'node-3'),('node-3',peer)):
                        self.assertFalse(blocked(sender,recipient,'HEARTBEAT'))
                        for kind in ('ACCEPT','COMMIT_PROOF','SNAPSHOT_OFFER','SNAPSHOT_CHUNK','REJOIN_INSTALL','SOURCE_OFFER','SOURCE_CHUNK','PREPARE','SELECTED_OFFER','BASIS_CHUNK'):
                            self.assertTrue(blocked(sender,recipient,kind),kind)
                self.assertFalse(blocked('node-1','node-2','ACCEPT'))
                self.assertEqual(value['rules'],(root/'network-rules.txt').read_text().splitlines())

    def test_cut_wait_fails_immediately_if_recipient_campaigns_even_with_a_cut(self):
        for cut in (None,dict(cut=recovery.CUTS['interrupted-transfer'])):
            self.cell.observe=Mock(return_value=dict(campaign=dict(event='CAMPAIGN_BEGIN',order=22),heartbeat=self.heartbeat,cut=cut))
            with self.assertRaisesRegex(ValueError,'recipient started a campaign'):
                self.cell.cut('node-3',5)
            self.cell.observe.assert_called_once()
            self.assertEqual(22,self.cell.record['recipientLastObservation']['campaign']['order'])

    def test_heal_releases_recipient_before_any_sender_can_deliver_the_chunk(self):
        for case in ('interrupted-transfer','minority-capacity'):
            self.cell.case=case;calls=[]
            self.cell.command=lambda node,action:calls.append((node,action)) or {}
            result=self.cell.partition('node-3','heal')
            self.assertEqual(('node-3','heal'),calls[0])
            self.assertEqual({'node-1','node-2','node-3'},set(result))
            self.assertEqual(3,len(calls))

    def test_capacity_recipient_campaign_fails_before_waiting_for_a_capacity_reply(self):
        self.cell.case='minority-capacity'
        self.cell.observe=Mock(return_value=dict(campaign=dict(event='CAMPAIGN_BEGIN'),heartbeat=None,cut=None,
                                                 rejection=dict(event='RESOURCE_REJECTED'),capacityReply=None))
        with self.assertRaisesRegex(ValueError,'recipient started a campaign'):
            self.cell.recipient_observation('node-3')
        self.cell.observe.assert_called_once()

    def test_transfer_wait_requires_current_activated_source_heartbeat(self):
        stale=dict(self.heartbeat,localNanos=9)
        self.cell.observe=Mock(side_effect=[dict(campaign=None,heartbeat=v,cut=None) for v in (stale,self.heartbeat)])
        self.cell.recipient_heartbeat('node-3','node-1',6,10,5)
        self.assertEqual(2,self.cell.observe.call_count)
        self.assertEqual(self.heartbeat,self.cell.record['recipientHeartbeat'])

    def test_independent_transfer_path_rejects_absent_early_and_foreign_heartbeats(self):
        replay.recipient_path(self.record,[self.heartbeat],self.isolation,self.manifest)
        for field,value in (('localNanos',9),('localNanos',15),('pid',99),('event','RECEIVED')):
            record=deepcopy(self.record);record['recipientHeartbeat'][field]=value
            with self.assertRaisesRegex(ValueError,'heartbeat outside'):
                replay.recipient_path(record,[record['recipientHeartbeat']],self.isolation,self.manifest)
        with self.assertRaisesRegex(ValueError,'heartbeat outside'):
            replay.recipient_path(self.record,[],self.isolation,self.manifest)
        record=dict(self.record,seedLeader='node-2')
        with self.assertRaisesRegex(ValueError,'bind live source'):
            replay.recipient_path(record,[self.heartbeat],self.isolation,self.manifest)

    def test_independent_path_rejects_campaign_during_hold_or_after_heal(self):
        for when in (11,15,16):
            campaign=dict(event='CAMPAIGN_BEGIN',pid=41,localNanos=when)
            with self.assertRaisesRegex(ValueError,'recipient campaigned'):
                replay.recipient_path(self.record,[self.heartbeat,campaign],self.isolation,self.manifest)
        previous=dict(event='CAMPAIGN_BEGIN',pid=41,localNanos=8)
        replay.recipient_path(dict(self.record,recipientCampaign=previous),[previous,self.heartbeat],self.isolation,self.manifest)

    def test_capacity_path_requires_live_heartbeat_until_original_resource_rejection(self):
        record=dict(self.record,case='minority-capacity',rejection=dict(self.cut,event='RESOURCE_REJECTED'))
        replay.recipient_path(record,[self.heartbeat],self.isolation,self.manifest)
        for rows in ([],[self.heartbeat,dict(event='CAMPAIGN_BEGIN',pid=41,localNanos=15)]):
            with self.assertRaises(ValueError):replay.recipient_path(record,rows,self.isolation,self.manifest)

    def test_missing_capacity_reply_negative_preserves_heartbeat_and_other_refusals(self):
        self.assertFalse(evidence.capacity_reply(self.heartbeat))
        envelope=recovery.m.strict_json(base64.b64decode(self.heartbeat['frame'])[48:])
        for reason in ('NOT_READY','CAPACITY_EXCEEDED'):
            frame=encoder.wire('REJECT',envelope,dict(reason=reason,promised=dict(epoch=2,proposer='node-1',incarnation=fixtures.UUID)))
            row=dict(self.heartbeat,frame=base64.b64encode(frame).decode())
            self.assertEqual(reason=='CAPACITY_EXCEEDED',evidence.capacity_reply(row))


class DisconnectedJvmTest(unittest.TestCase):
    def test_sigkill_retains_unresolved_original_invocation(self):
        with tempfile.TemporaryDirectory() as temp:
            v=object.__new__(jvm.Jvm);v.root=Path(temp);v.node='node-1';v.prefix='node-1-g1';v.generation=1
            v.identity=dict(pid=1,node=v.node,generation=1);v.closed=False;v.deadline=time.monotonic()+10
            v.rows=[dict(request=dict(kind='addAll',opId='op-1'),startNanos=1,outcome='PENDING')]
            v.proc=Mock(returncode=-9);v.proc.poll.return_value=-9;v.reader=Mock();v.reader.is_alive.return_value=False;v.streams_close=Mock()
            with patch.object(jvm.public_trace,'finish'):v.stop(True)
            row=c.read(v.root/(v.prefix+'-exchanges.json'))[0]
            self.assertEqual('PENDING',row['outcome']);self.assertGreater(row['disconnectNanos'],row['startNanos'])
            self.assertNotIn('response',row);self.assertNotIn('failure',row)
            v.proc.stdin.write.assert_not_called()


if __name__=='__main__':unittest.main()
