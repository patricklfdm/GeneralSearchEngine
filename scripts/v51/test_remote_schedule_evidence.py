import copy
import unittest
from . import remote_schedule as s, remote_schedule_evidence as evidence


def fixture():
    spec=s.windows('healthy','experiment')[0]
    events=[]
    state=s.WindowState(spec,10**9,events.append)
    for call in spec['calls']:
        now=state.start+call['dueMillis']*10**6
        state.offer(call,now)
        state.invoke(call['ordinal'],now)
        state.complete(call['ordinal'],now+1000,{'outcome':'SUCCESS'})
    return spec,events,state.finish(state.start+spec['durationNanos'])


class RemoteScheduleEvidenceTest(unittest.TestCase):
    def test_complete_frozen_window_independently_validates(self):
        self.assertEqual('PASS',evidence.validate(*fixture())['status'])

    def test_resealed_schedule_or_bound_drift_rejected(self):
        for key,value in [('durationNanos',1),('lanes',4),('latenessNanos',999_000_000),
                          ('burstSpreadNanos',10_000_000),('drainNanos',100*10**9),('workloadSha256','0'*64)]:
            spec,events,result=fixture()
            spec[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):evidence.validate(spec,events,result)
        spec,events,result=fixture()
        spec['calls'][0]['payload']='00'
        with self.assertRaises(ValueError):evidence.validate(spec,events,result)

    def test_omitted_duplicate_and_unplanned_arrivals_rejected(self):
        for mode in ('omit','duplicate','extra','transition'):
            spec,events,result=fixture()
            if mode=='omit': events=events[3:];result['calls']=result['calls'][1:]
            if mode=='duplicate':result['calls'][-1]=result['calls'][0]
            if mode=='extra':events.append(dict(events[-1],ordinal=999))
            if mode=='transition':events.pop(1)
            with self.subTest(mode=mode),self.assertRaises(ValueError):evidence.validate(spec,events,result)

    def test_late_dispatch_or_changed_clock_cannot_be_resealed(self):
        for patch in ({'invokedNanos':1_251_000_000,'endedNanos':1_252_000_000},
                      {'dueNanos':-1},{'offeredNanos':-1}):
            spec,events,result=fixture()
            events[2].update(patch)
            result['calls'][0].update(patch)
            with self.subTest(patch=patch),self.assertRaises(ValueError):evidence.validate(spec,events,result)

    def test_failure_or_early_finish_cannot_be_relabelled_pass(self):
        spec,events,result=fixture()
        events[2]['result']={'outcome':'INDETERMINATE'}
        result['calls'][0]['result']={'outcome':'INDETERMINATE'}
        with self.assertRaises(ValueError):evidence.validate(spec,events,result)
        spec,events,result=fixture()
        result['endedNanos']-=1
        with self.assertRaises(ValueError):evidence.validate(spec,events,result)

    def test_intermediate_invocation_clock_must_match_terminal_row(self):
        spec,events,result=fixture()
        events[1]['invokedNanos']+=1
        with self.assertRaisesRegex(ValueError,'clock changed'):evidence.validate(spec,events,result)
