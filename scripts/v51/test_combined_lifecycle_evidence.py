"""Combined faults need actual overlapping service, pressure and drained owners."""
import copy
import unittest
from .combined_lifecycle_evidence import overlap, pressure, samples


class CombinedOverlapTest(unittest.TestCase):
    def setUp(self):self.calls={'write':dict(node='node-1',outcome='SUCCESS',startNanos=20,endNanos=30)}
    def test_service_fits_entire_fault_window(self):overlap(self.calls,['write'],10,40,owner='node-1')
    def test_early_late_failed_or_foreign_service_rejected(self):
        for change in (dict(startNanos=10),dict(endNanos=40),dict(outcome='INDETERMINATE'),dict(node='node-2')):
            with self.subTest(change=change):
                calls=copy.deepcopy(self.calls);calls['write'].update(change)
                with self.assertRaises(ValueError):overlap(calls,['write'],10,40,owner='node-1')
    def test_missing_or_duplicate_operations_fail(self):
        for ids in ([],['write','write']):
            with self.assertRaises(ValueError):overlap(self.calls,ids,10,40)


class CombinedPressureTest(unittest.TestCase):
    def setUp(self):
        self.rows=[]
        for identity in (1,2):
            self.rows.extend([dict(event='TRANSPORT',transition='OUTBOUND_ADMITTED',pid=7,order=identity*2,request=str(identity)),
                dict(event='PRESSURE_HELD',barrier='BEFORE_REQUEST_WRITE',pid=7,order=identity*2+1,request=str(identity),hold=identity),
                dict(event='PRESSURE_RELEASED',pid=7,order=10+identity,hold=identity)])
        self.accounting=dict(rejected=[dict(row=dict(transition='OUTBOUND_REJECTED',pid=7,order=8),count=2,peer='node-2')])
    def check(self):return pressure(self.rows,self.accounting,'node-2',lambda _:dict(sender='node-3',recipient='node-2'))
    def test_actual_two_slot_pressure_with_matching_rejection(self):self.assertEqual(2,len(self.check()[0]))
    def test_missing_hold_release_or_admission_rejected(self):
        for event in ('PRESSURE_HELD','PRESSURE_RELEASED','TRANSPORT'):
            with self.subTest(event=event):
                original=self.rows;self.rows=[r for r in original if r['event']!=event]
                with self.assertRaises(ValueError):self.check()
                self.rows=original
    def test_rejection_must_have_both_target_peer_slots(self):
        for change in (dict(count=1),dict(peer='node-1')):
            with self.subTest(change=change):
                saved=copy.deepcopy(self.accounting);self.accounting['rejected'][0].update(change)
                with self.assertRaises(ValueError):self.check()
                self.accounting=saved
    def test_rejection_must_occur_while_held_in_same_process(self):
        for change in (dict(order=4),dict(order=12),dict(pid=99),dict(transition='INBOUND_REJECTED')):
            with self.subTest(change=change):
                saved=copy.deepcopy(self.accounting);self.accounting['rejected'][0]['row'].update(change)
                with self.assertRaises(ValueError):self.check()
                self.accounting=saved
    def test_pressure_cannot_borrow_a_process_or_reorder_release(self):
        for change in (dict(pid=99),dict(order=1)):
            with self.subTest(change=change):
                saved=copy.deepcopy(self.rows);next(r for r in self.rows if r['event']=='PRESSURE_RELEASED').update(change)
                with self.assertRaises(ValueError):self.check()
                self.rows=saved


class CombinedSampleTest(unittest.TestCase):
    def setUp(self):
        keys=['admissionAvailable','orderedQueue','deadlinesQueue','inputsQueue','inputsRemaining','completionsQueue',
              'completionsRemaining','networkQueue','networkActive','appQueue','appActive','clientsQueue','clientsActive']
        self.sample={k:0 for k in keys};self.sample['admissionAvailable']=4
        self.traces={'node-1':[dict(event='LIFECYCLE_SAMPLE',opId='sample',pid=7,generation=2,sample=self.sample)]}
        self.values={'node-1':dict(node='node-1',pid=7,generation=2,observedNanos=30,status=dict(opId='sample',pending=0,sample=self.sample))}
    def check(self):samples(self.traces,self.values,{'node-1'},20)
    def test_healthy_only_samples_still_require_real_bound_rows(self):self.check()
    def test_missing_process_member_or_early_sample_fails(self):
        for change in (dict(pid=8),dict(generation=1),dict(observedNanos=20)):
            with self.subTest(change=change):
                saved=copy.deepcopy(self.values);self.values['node-1'].update(change)
                with self.assertRaises(ValueError):self.check()
                self.values=saved
        with self.assertRaises(ValueError):samples(self.traces,{}, {'node-1'},20)
    def test_actual_timer_or_permit_leak_is_rejected(self):
        for key,value in (('deadlinesQueue',1),('admissionAvailable',3),('networkActive',5)):
            with self.subTest(key=key):
                old=self.sample[key];self.sample[key]=value
                with self.assertRaises(ValueError):self.check()
                self.sample[key]=old
    def test_fabricated_diagnostic_fails(self):
        self.values['node-1']['status']['sample']=dict(self.sample,appActive=1)
        with self.assertRaises(ValueError):self.check()


if __name__=='__main__':unittest.main()
