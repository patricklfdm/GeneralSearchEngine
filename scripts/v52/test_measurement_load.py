import concurrent.futures
import copy
import unittest
from . import measurement_load as load,measurement_model as model
from .measurement_runtime import await_publication
from unittest.mock import Mock


class Clock:
    def __init__(self):self.now=10_000_000_000
    def __call__(self):return self.now
    def sleep(self,seconds):self.now+=max(1,round(seconds*1_000_000_000))


class MeasurementLoadTest(unittest.TestCase):
    def execute(self,calls=None,duration=180_000_000_000,delay=0,complete=True):
        clock=Clock();history=[];futures=[]
        def submit(request):
            identity=str(len(history));row=dict(request,opId=identity,startNanos=clock(),outcome='PENDING',endNanos=None)
            history.append(row);future=concurrent.futures.Future();futures.append(future);clock.now+=delay
            if complete:
                response=dict(outcome='SUCCESS',opId=identity);row.update(response=response,outcome='SUCCESS',endNanos=clock());future.set_result(response)
            return identity,future
        calls=model.program() if calls is None else calls
        receipt,pending=load.dispatch(calls,duration,submit,clock=clock,sleep=clock.sleep)
        return receipt,pending,history,clock

    def test_initial_token_is_not_the_completed_setup_publication(self):
        clock=Clock()
        def status(index,sequence,state='FOLLOWER'):return dict(state=state,publishedIndex=index,sequence=sequence)
        workers={n:Mock() for n in ('node-1','node-2','node-3')}
        workers['node-1'].call.return_value=status(5,4,'LEADER_READY')
        workers['node-2'].call.return_value=status(5,4)
        workers['node-3'].call.side_effect=[status(2,1),status(5,4,'RECOVERING'),status(5,4)]
        result=await_publication(workers,5,4,clock=lambda:clock()/1e9,sleep=clock.sleep)
        self.assertEqual(4,result['node-3']['sequence']);self.assertEqual(3,workers['node-3'].call.call_count)
        self.assertTrue(all(c.args==('status',) for worker in workers.values() for c in worker.call.call_args_list))

    def test_failed_or_never_caught_up_preparation_cannot_start_load(self):
        clock=Clock();worker=Mock();worker.call.return_value=dict(state='FAILED',publishedIndex=5,sequence=4)
        with self.assertRaisesRegex(ValueError,'prepared voter failed'):await_publication({'node-1':worker},5,4,clock=lambda:clock()/1e9,sleep=clock.sleep)
        worker.call.return_value=dict(state='FOLLOWER',publishedIndex=2,sequence=1)
        with self.assertRaisesRegex(ValueError,'publication unavailable'):await_publication({'node-1':worker},5,4,clock=lambda:clock()/1e9,sleep=clock.sleep)

    def test_all_1980_offers_keep_original_time_and_wait_entire_window(self):
        receipt,pending,history,clock=self.execute();load.drain(receipt,pending,1,clock=clock)
        result=load.validate(receipt,model.program(),180_000_000_000,history)
        self.assertEqual(1980,result['offered']);self.assertEqual({'SUCCESS':1980},result['outcomes'])
        self.assertEqual(receipt['startNanos']+180_000_000_000,receipt['dispatchEndNanos'])

    def test_outstanding_futures_do_not_pace_offers(self):
        receipt,pending,history,clock=self.execute(complete=False)
        self.assertEqual(1980,len(pending));self.assertTrue(all(not f.done() for _,f in pending))
        self.assertEqual(receipt['startNanos']+180_000_000_000,receipt['dispatchEndNanos'])
        load.drain(receipt,pending,.001,clock=clock)
        self.assertEqual(1980,receipt['unobserved']);self.assertTrue(all(not f.cancelled() for _,f in pending))
        with self.assertRaisesRegex(ValueError,'incomplete observation'):load.validate(receipt,model.program(),180_000_000_000,history)

    def test_slow_dispatch_records_lateness_without_resetting_due_or_retry(self):
        calls=model.program()[:4];receipt,pending,history,clock=self.execute(calls,1_000_000_000,delay=200_000_000)
        load.drain(receipt,pending,1,clock=clock);result=load.validate(receipt,calls,1_000_000_000,history)
        self.assertEqual(4,len(history));self.assertGreater(result['latencies'][1]['offerDelayNanos'],0)
        self.assertEqual(receipt['startNanos']+calls[1]['offsetNanos'],receipt['offers'][1]['dueNanos'])

    def test_transport_failure_preserves_undispatched_suffix(self):
        clock=Clock();count=0
        def submit(call):
            nonlocal count
            count+=1;raise BrokenPipeError('transport disconnected')
        receipt,pending=load.dispatch(model.program(),180_000_000_000,submit,clock=clock,sleep=clock.sleep)
        self.assertEqual(1,count);self.assertFalse(pending);self.assertEqual(1980,len(receipt['offers']))
        self.assertEqual('DISPATCH_FAILED',receipt['offers'][0]['status']);self.assertTrue(all(v['status']=='NOT_DISPATCHED' for v in receipt['offers'][1:]))
        self.assertEqual(clock.now,receipt['startNanos'])

    def test_rejections_are_counted_and_never_reissued(self):
        receipt,pending,history,clock=self.execute(model.program()[:1],1_000_000_000);load.drain(receipt,pending,1,clock=clock)
        history[0]['outcome']='REJECTED';history[0]['response']['outcome']='REJECTED'
        self.assertEqual({'REJECTED':1},load.validate(receipt,model.program()[:1],1_000_000_000,history)['outcomes'])

    def test_removed_changed_duplicate_or_shortened_offers_fail(self):
        calls=model.program()[:3];receipt,pending,history,clock=self.execute(calls,1_000_000_000);load.drain(receipt,pending,1,clock=clock)
        changes=[lambda r:r['offers'].pop(),lambda r:r['offers'][1].__setitem__('dueNanos',0),
                 lambda r:r['offers'][1].__setitem__('opId',r['offers'][0]['opId']),lambda r:r.__setitem__('dispatchEndNanos',r['startNanos']),
                 lambda r:r['offers'][0]['response'].__setitem__('outcome','REJECTED')]
        for change in changes:
            modified=copy.deepcopy(receipt);change(modified)
            with self.subTest(change=change),self.assertRaises(ValueError):load.validate(modified,calls,1_000_000_000,history)


if __name__=='__main__':unittest.main()
