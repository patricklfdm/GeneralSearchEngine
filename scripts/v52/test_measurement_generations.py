import copy
import unittest
from . import measurement_generations as g,measurement_history as h
from .test_measurement_history import fixture


def reopened():
    traces,processes,history=fixture()
    processes[0]['exitCode']=-9
    old=traces['node-1'];old[:]=[r for r in old if r['event'] not in ('CLIENT_IDLE','CLOSED')]
    queues=dict(admissionAvailable=64,readsOwned=0,readsWaiting=0,readsCaptured=0,readsSettling=0,readsAlarms=0,readsMarker=0,readsHighWater=0)
    p=dict(node='node-1',generation=2,pid=4,exitCode=0);processes.append(p)
    traces['node-1'] += [dict(node='node-1',generation=2,pid=4,order=i,localNanos=i*100,event=event,groupId='group',manifestDigest='digest',**fields)
                         for i,event,fields in ((1,'CLIENT_IDLE',dict(queues=queues)),(2,'CLOSED',{}))]
    return traces,processes,history


class MeasurementGenerationsTest(unittest.TestCase):
    def test_only_declared_owned_sigkill_and_one_reopen_are_allowed(self):
        data=reopened();r=h.validate(*data,'candidate-explicit-strong',restarted='node-1')
        self.assertEqual({'SUCCESS':1},r['outcomes']['read']);self.assertEqual(4,len(r['resources']))
        with self.assertRaisesRegex(ValueError,'clean processes'):h.validate(*data,'candidate-explicit-strong')
        for change in (lambda p:p[0].__setitem__('exitCode',0),lambda p:p[-1].__setitem__('generation',3),
                       lambda p:p[-1].__setitem__('pid',1),lambda p:p.append(dict(p[-1])),lambda p:p.pop()):
            bad=copy.deepcopy(data);change(bad[1])
            with self.assertRaises(ValueError):h.validate(*bad,'candidate-explicit-strong',restarted='node-1')

    def test_crash_cannot_hide_pending_call_owned_view_or_fake_clean_close(self):
        for issue in ('pending','owned','closed'):
            data=reopened()
            if issue=='pending':data[2][0]['outcome']='PENDING'
            if issue=='owned':next(r for r in data[0]['node-1'] if r['event']=='REPLICA_READ_OWNERSHIP_RELEASED')['event']='REMOVED'
            if issue=='closed':data[0]['node-1'].insert(-2,dict(data[0]['node-1'][-3],event='CLOSED',order=100,localNanos=100000))
            with self.subTest(issue=issue),self.assertRaises(ValueError):h.validate(*data,'candidate-explicit-strong',restarted='node-1')

    def test_foreign_or_interleaved_generation_cannot_disappear_in_filter(self):
        for issue in ('foreign','interleaved','missing'):
            data=reopened();rows=data[0]['node-1']
            if issue=='foreign':rows[0]['pid']=999
            if issue=='interleaved':rows.insert(0,rows.pop(-1))
            if issue=='missing':rows[:]=[r for r in rows if r['generation']==1]
            with self.subTest(issue=issue),self.assertRaisesRegex(ValueError,'undeclared trace|interleaved|missing process trace'):
                h.validate(*data,'candidate-explicit-strong',restarted='node-1')


if __name__=='__main__':unittest.main()
