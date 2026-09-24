import threading
import time
import unittest
from . import remote_schedule as s, cloud_workload_contract as contract


def fixture(lanes=4):
    return dict(calls=[dict(ordinal=i+1,lane=i,dueMillis=0) for i in range(lanes)],
                lanes=lanes, durationNanos=100_000_000, latenessNanos=250_000_000,
                burstSpreadNanos=10_000_000, drainNanos=100_000_000)


class RemoteScheduleTest(unittest.TestCase):
    def state(self, spec=None):
        return s.WindowState(spec or fixture(), 1_000_000_000, lambda row: None)

    def test_all_full_frozen_tapes_use_same_dispatch_state_machine(self):
        counts = {}
        for preset, cell in [('canonical','healthy'),('experiment','healthy'),('canonical','read-heavy'),('canonical','sustained')]:
            count = 0
            for spec in s.windows(cell,preset):
                state = self.state(spec)
                for call in spec['calls']:
                    now = state.start+call['dueMillis']*10**6+call['lane']*1000
                    self.assertTrue(state.offer(call,now))
                    self.assertTrue(state.invoke(call['ordinal'],now))
                    state.complete(call['ordinal'],now+500,{'outcome':'SUCCESS'})
                    count += 1
                self.assertEqual('PASS',state.finish(state.start+spec['durationNanos'])['status'])
            counts[preset,cell] = count
        self.assertEqual({('canonical','healthy'):260,('experiment','healthy'):90,('canonical','read-heavy'):120,('canonical','sustained'):180},counts)

    def test_global_healthy_cycles_continue_across_abba_windows(self):
        windows = s.windows('healthy')
        self.assertEqual([20,60,60,60,60],[len(w['calls']) for w in windows])
        self.assertEqual([0,2,8,14,20],[w['calls'][0]['cycle'] for w in windows])
        self.assertEqual(25,windows[-1]['calls'][-1]['cycle'])
        self.assertEqual(212, contract.projection(contract.load(),'healthy')['finalSequence'])

    def test_late_offer_is_recorded_without_catchup(self):
        state = self.state()
        self.assertFalse(state.offer(fixture()['calls'][0],state.start+250_000_001))
        self.assertEqual('LATE',state.rows[1]['reason'])
        self.assertFalse(state.offer(fixture()['calls'][1],state.start+250_000_002))
        self.assertEqual('PRIOR_FAILURE',state.rows[2]['reason'])

    def test_busy_lane_does_not_queue_or_replay(self):
        spec = fixture(1)
        spec['calls'].append(dict(ordinal=2,lane=0,dueMillis=1))
        state = self.state(spec)
        self.assertTrue(state.offer(spec['calls'][0],state.start))
        self.assertTrue(state.invoke(1,state.start))
        self.assertFalse(state.offer(spec['calls'][1],state.start+1_000_000))
        self.assertEqual('LANE_BUSY',state.rows[2]['reason'])
        state.complete(1,state.start+2_000_000,{'outcome':'SUCCESS'})
        self.assertEqual('FAIL',state.finish(state.start+spec['durationNanos'])['status'])

    def test_executor_delay_prevents_api_dispatch(self):
        state = self.state(fixture(1))
        state.offer(fixture(1)['calls'][0],state.start)
        self.assertFalse(state.invoke(1,state.start+250_000_001))
        self.assertEqual('EXECUTOR_LATE',state.rows[1]['reason'])

    def test_cancelled_and_missing_arrivals_do_not_pass(self):
        state = self.state()
        self.assertFalse(state.offer(fixture()['calls'][0],state.start,cancelled=True))
        self.assertEqual('CANCELLED',state.rows[1]['reason'])
        with self.assertRaisesRegex(ValueError,'missing'): state.finish(state.start+100_000_000)

    def test_failure_prevents_later_scheduled_operations(self):
        state = self.state()
        state.offer(fixture()['calls'][0],state.start)
        state.invoke(1,state.start)
        state.complete(1,state.start+1,{'outcome':'INDETERMINATE'})
        self.assertFalse(state.offer(fixture()['calls'][1],state.start+2))

    def test_slow_burst_cannot_pass_as_four_sequential_calls(self):
        state = self.state()
        for call in fixture()['calls']:
            now = state.start+call['lane']*4_000_000
            state.offer(call,now)
            state.invoke(call['ordinal'],now)
            state.complete(call['ordinal'],now+1000,{'outcome':'SUCCESS'})
        self.assertEqual('FAIL',state.finish(state.start+100_000_000)['status'])

    def test_short_window_overrun_and_unfinished_never_pass(self):
        for end in (99_999_999,200_000_001):
            state = self.state(fixture(1))
            state.offer(fixture(1)['calls'][0],state.start)
            state.invoke(1,state.start)
            state.complete(1,state.start+1,{'outcome':'SUCCESS'})
            self.assertEqual('FAIL',state.finish(state.start+end)['status'])
        state = self.state(fixture(1))
        state.offer(fixture(1)['calls'][0],state.start)
        state.invoke(1,state.start)
        self.assertEqual('FAIL',state.finish(state.start+200_000_000)['status'])
        state.complete(1,state.start+200_000_001,{'outcome':'SUCCESS'})
        self.assertEqual('LATE_RESULT',state.rows[1]['state'])
        self.assertTrue(state.failed)

    def test_real_threaded_executor_invokes_each_lane_once(self):
        seen, events = [], []
        barrier = threading.Barrier(4)
        def callback(call):
            seen.append(call['ordinal'])
            barrier.wait(3)
            return {'outcome':'SUCCESS'}
        result = s._execute(fixture(),callback,events.append,lambda:False)
        # Host timing is reported, not made green by relaxing the frozen 10ms rule.
        self.assertEqual([1,2,3,4],sorted(seen))
        self.assertEqual(4,len(result['calls']))
        self.assertTrue(all(row['state']=='COMPLETED' for row in result['calls']))
        calls = result['calls']
        self.assertLess(max(v['invokedNanos'] for v in calls),min(v['endedNanos'] for v in calls))
        expected = 'PASS' if max(v['invokedNanos'] for v in calls)-min(v['invokedNanos'] for v in calls)<=10_000_000 else 'FAIL'
        self.assertEqual(expected,result['status'])

    def test_unknown_window_or_preset_rejected(self):
        with self.assertRaises(ValueError): s.windows('healthy','unknown')
        with self.assertRaises(ValueError): s.execute_window('healthy','canonical','unknown',None,None)
