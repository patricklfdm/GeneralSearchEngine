"""Fail-closed multi-generation schedules and crash-specific resource accounting."""
import base64
import copy
import unittest
from .hardening_evidence import processes, rounds, partition_drop
from .public_pressure_evidence import reservations


class RepeatedProcessTest(unittest.TestCase):
    def setUp(self):
        self.traces={}; self.starts=[]; self.stops=[]
        for ordinal in (1,2,3):
            node=f'node-{ordinal}'; self.traces[node]=[]
            for generation in (1,2,3,4):
                pid=ordinal*10+generation; begin=generation*100
                self.starts.append(dict(node=node,pid=pid,generation=generation,startNanos=begin,readyNanos=begin+1))
                self.traces[node].extend(dict(node=node,pid=pid,generation=generation,order=i,event=event)
                                         for i,event in enumerate(('STARTED','CLOSED'),1))
                if generation<4:
                    self.stops.append(dict(node=node,pid=pid,generation=generation,startNanos=begin+2,
                                           endNanos=begin+3,archivedNanos=begin+4,exitCode=0))
    def check(self): return processes(self.traces,self.starts,self.stops)

    def test_four_contiguous_generations_are_bound_to_real_starts(self):
        self.assertEqual(12,len(self.check()))

    def test_missing_duplicate_or_unknown_process_is_rejected(self):
        for change in ('missing','duplicate','unknown'):
            with self.subTest(change=change):
                starts=copy.deepcopy(self.starts)
                if change=='missing': starts.pop()
                elif change=='duplicate': starts.append(dict(starts[0]))
                else: starts[-1]['pid']=999
                with self.assertRaises(ValueError): processes(self.traces,starts,self.stops)

    def test_wrong_trace_generation_or_local_order_is_rejected(self):
        for field,value in (('generation',3),('order',7),('node','node-2')):
            with self.subTest(field=field):
                traces=copy.deepcopy(self.traces); traces['node-1'][-1][field]=value
                with self.assertRaises(ValueError): processes(traces,self.starts,self.stops)

    def test_restart_requires_terminated_archived_previous_owner(self):
        for change in (dict(endNanos=202),dict(archivedNanos=202),dict(node='node-2'),dict(exitCode=1)):
            with self.subTest(change=change):
                stops=copy.deepcopy(self.stops); stops[0].update(change)
                with self.assertRaises(ValueError): processes(self.traces,self.starts,stops)
        with self.assertRaises(ValueError): processes(self.traces,self.starts,self.stops[1:])

    def test_sigkill_is_distinct_from_graceful_close(self):
        self.stops[0]['exitCode']=-9
        with self.assertRaisesRegex(ValueError,'SIGKILL'): self.check()
        self.traces['node-1'].pop(1)
        self.assertEqual(12,len(self.check()))
        self.stops[0]['exitCode']=0
        with self.assertRaisesRegex(ValueError,'did not close'): self.check()

    def test_final_process_must_close(self):
        self.traces['node-2'].pop()
        with self.assertRaisesRegex(ValueError,'did not close'): self.check()


class CrashAccountingTest(unittest.TestCase):
    def row(self,pid,identity=1,action='ADMITTED'):
        return dict(event='TRANSPORT',transition='OUTBOUND_'+action,pid=pid,reservation=identity,
                    bytes=64,request=base64.b64encode(b'2'*64).decode())
    def check(self,rows,dead=()):
        return reservations(rows,lambda _:dict(recipient='node-2'),64,terminated_pids=dead)

    def test_only_verified_dead_process_can_abandon_bounded_reservations(self):
        old=self.row(11); new=self.row(12)
        with self.assertRaisesRegex(ValueError,'leaked'): self.check([old])
        result=self.check([old,new,self.row(12,action='RELEASED')],dead={11})
        self.assertEqual({11:1},result['abandonedAtProcessExit'])
        self.assertEqual(dict(inbound=0,outbound=1,bytes=64),result['peaks'])

    def test_dead_owner_does_not_excuse_live_owner_leak(self):
        with self.assertRaisesRegex(ValueError,'leaked'): self.check([self.row(11),self.row(12)],dead={11})

    def test_new_owner_cannot_release_dead_owners_reservation(self):
        with self.assertRaisesRegex(ValueError,'release without'):
            self.check([self.row(11),self.row(12,action='RELEASED')],dead={11})

    def test_crash_does_not_excuse_exceeded_capacity(self):
        with self.assertRaisesRegex(ValueError,'admission bound'):
            self.check([self.row(11,i) for i in (1,2,3)],dead={11})


class FixedRoundsTest(unittest.TestCase):
    def receipt(self):
        return dict(case='whole-group-restart',rounds=[dict(number=n,beginNanos=n*10,endNanos=n*10+5) for n in (1,2,3)])
    def test_three_disjoint_rounds(self): self.assertEqual(3,len(rounds(self.receipt())))
    def test_missing_reordered_or_overlapping_rounds(self):
        for change in ('missing','reordered','overlap'):
            with self.subTest(change=change):
                value=self.receipt()
                if change=='missing': value['rounds'].pop()
                elif change=='reordered': value['rounds'].reverse()
                else: value['rounds'][-1]['beginNanos']=24
                with self.assertRaises(ValueError): rounds(value)


class PartitionWitnessTest(unittest.TestCase):
    def setUp(self):
        from .fixtures import generate
        from . import format_encoder, format_inspector
        _,wires,self.manifest=generate()
        self.encoder=format_encoder
        self.inspector=format_inspector
        self.prepare=format_inspector.wire(wires['PREPARE'],self.manifest)
        self.traces={n:[] for n in ('node-1','node-2','node-3')}
        self.starts=[dict(node='node-1',pid=11,generation=1,readyNanos=1),
                     dict(node='node-1',pid=12,generation=2,readyNanos=60),
                     dict(node='node-2',pid=21,generation=1,readyNanos=1),
                     dict(node='node-3',pid=31,generation=1,readyNanos=1)]
        self.stop=dict(node='node-2',pid=21,generation=1,startNanos=200)
        self.stops=[dict(node='node-1',pid=11,generation=1,startNanos=50),self.stop]
        self.row=dict(number=2,oldLeader='node-2',oldPid=21,oldGeneration=1,
                      pause=dict(localNanos=90),partitionNanos=100,stops=[self.stop])

    def add(self, sender='node-1', recipient='node-2', **values):
        envelope=dict(self.prepare,sender=sender,recipient=recipient,proposer=sender,epoch=1+int(sender[-1]))
        data=self.encoder.wire('PREPARE',envelope,envelope['payload'])
        start=next(s for s in reversed(self.starts) if s['node']==sender)
        record=dict(event='NETWORK_DROP',node=sender,pid=start['pid'],generation=start['generation'],
                    order=10,localNanos=150,barrier='BEFORE_REQUEST_WRITE',request=base64.b64encode(data).decode())
        record.update(values);self.traces[sender].append(record);return record

    def check(self):
        wire=lambda data:self.inspector.wire(base64.b64decode(data),self.manifest)
        return partition_drop(self.traces,self.row,self.starts,self.stops,wire)

    def test_paused_old_leader_needs_no_outgoing_packet(self):
        self.add()
        result=self.check()
        self.assertEqual(('node-1','node-2',12,2,2),
                         tuple(result[k] for k in ('sender','recipient','pid','generation','round')))
        self.assertFalse(self.traces['node-2'])

    def test_outgoing_partition_witness_is_still_valid(self):
        self.add('node-2','node-3')
        self.assertEqual('node-2',self.check()['sender'])

    def test_response_discard_by_partition_also_counts(self):
        self.add(barrier='AFTER_RESPONSE_READ')
        self.assertEqual('AFTER_RESPONSE_READ',self.check()['barrier'])

    def test_missing_or_unrelated_peer_drop_is_not_isolation(self):
        with self.assertRaisesRegex(ValueError,'missing in-round'):self.check()
        self.add('node-1','node-3')
        with self.assertRaisesRegex(ValueError,'missing in-round'):self.check()

    def test_other_round_or_post_kill_drop_is_rejected(self):
        record=self.add()
        for stamp in (50,99,100,200,201,250):
            with self.subTest(stamp=stamp):
                record['localNanos']=stamp
                with self.assertRaisesRegex(ValueError,'missing in-round'):self.check()

    def test_retired_or_wrong_process_cannot_supply_witness(self):
        record=self.add();original=dict(record)
        for change in (dict(pid=11,generation=1),dict(pid=12,generation=1),dict(pid=999),dict(node='node-3')):
            with self.subTest(change=change):
                record.clear();record.update(original);record.update(change)
                with self.assertRaisesRegex(ValueError,'missing in-round'):self.check()

    def test_future_or_terminated_sender_cannot_supply_witness(self):
        self.add();self.starts[1]['readyNanos']=110
        with self.assertRaisesRegex(ValueError,'missing in-round'):self.check()
        self.starts[1]['readyNanos']=60
        self.stops.append(dict(node='node-1',pid=12,generation=2,startNanos=140))
        with self.assertRaisesRegex(ValueError,'missing in-round'):self.check()

    def test_old_owner_must_match_the_live_generation(self):
        self.add();self.row['oldGeneration']=2
        with self.assertRaisesRegex(ValueError,'partition owner not live'):self.check()

    def test_sender_trace_must_match_wire_direction(self):
        record=self.add();self.traces['node-1'].clear()
        self.traces['node-2'].append(dict(record,node='node-2',pid=21,generation=1))
        with self.assertRaisesRegex(ValueError,'missing in-round'):self.check()

    def test_response_writer_or_separate_network_rule_is_not_partition(self):
        record=self.add();record['barrier']='BEFORE_RESPONSE_WRITE'
        with self.assertRaisesRegex(ValueError,'missing in-round'):self.check()
        record['barrier']='BEFORE_REQUEST_WRITE';record['rule']='node-1 node-2 BEFORE_REQUEST_WRITE *'
        with self.assertRaisesRegex(ValueError,'missing in-round'):self.check()

    def test_foreign_or_corrupt_wire_is_not_partition_evidence(self):
        record=self.add();original=record['request']
        self.manifest=dict(self.manifest,digest='ff'*32)
        with self.assertRaisesRegex(ValueError,'wire group/manifest'):self.check()
        data=bytearray(base64.b64decode(original));data[-1]^=1
        record['request']=base64.b64encode(data).decode()
        with self.assertRaises(ValueError):self.check()

    def test_partition_must_follow_pause_and_precede_kill(self):
        self.add()
        for begin in (90,200):
            self.row['partitionNanos']=begin
            with self.assertRaisesRegex(ValueError,'witness interval'):self.check()


if __name__=='__main__': unittest.main()
