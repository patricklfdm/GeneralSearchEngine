"""Fail-closed multi-generation schedules and crash-specific resource accounting."""
import base64
import copy
import unittest
from .hardening_evidence import processes, rounds
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


if __name__=='__main__': unittest.main()
