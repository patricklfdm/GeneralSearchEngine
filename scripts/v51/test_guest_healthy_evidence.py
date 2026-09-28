"""Frozen complete-window replay tests with explicitly synthetic process records."""
from pathlib import Path
import tempfile
import unittest
from .test_guest_evidence import Fixture
from . import guest_evidence as e, cloud_package as package, performance_model as m
from . import remote_schedule as schedule, remote_schedule_evidence as scheduling


class HealthyFixture(Fixture):
    def __init__(self, root, **kwargs):
        super().__init__(root, **kwargs)
        self.transcript=self.transcript[:-3 if self.active else -2]
        self.exchanges.pop();self.results.pop()
        self.extra=[];starts=[(1_500_000_000,'warmup')] if self.active else []
        now=13*10**9 if self.active else 1_100_000_000
        specs=schedule.windows('healthy','experiment')[1 if self.active else 0:]
        for spec in specs:
            response=self.exchange('configure',dict(window=spec['window']),now+100,now+200)
            starts.append((now+150,spec['window']))
            if not self.active:
                self.control('fault',dict(action='configure',window=spec['window']),response,now,now+1000)
                now+=spec['durationNanos']+10**9;continue
            events=[];window=schedule.WindowState(spec,now+1000,events.append)
            for call in spec['calls']:
                when=window.start+call['dueMillis']*10**6
                window.offer(call,when);window.invoke(call['ordinal'],when)
                response=self.exchange('call',call,when+5,when+15)
                before=self.state.sequence;answer=None
                if call['operation'] in m.OP_IDS:self.state.apply(m.OP_IDS[call['operation']],bytes.fromhex(call['payload']))
                else:answer=self.state.answer(call['operation'],call['cycle'])
                response['call']=dict({k:call[k] for k in ('ordinal','window','cycle','operation','keys','lane')},
                    outcome='SUCCESS',payloadSha256=m.sha(bytes.fromhex(call['payload'])),answer=answer,
                    answerSha256=m.sha(m.canonical(answer)),beforeSequence=before,afterSequence=self.state.sequence,
                    apiStartNanos=when+7,apiEndNanos=when+13)
                window.complete(call['ordinal'],when+20,dict(outcome='SUCCESS',opId=response['opId'],resultSha256=m.sha(m.canonical(response))))
            result=window.finish(window.start+spec['durationNanos'])
            self.control('window',dict(cell='healthy',preset='experiment',window=spec['window']),
                dict(window=spec['window'],calls=len(spec['calls']),validation=scheduling.validate(spec,events,result)),now,result['endedNanos']+100)
            self.extra.append((spec,events,result));now=result['endedNanos']+10**9
        if self.active:
            negative=self.control('collect',{},None,now,now+100)
            negative.pop('result');negative.update(state='FAILED',error=dict(type='ValueError',message='guest collection requires stopped JVM'))
        self.exchange('close',{},now+200,now+300)
        self.control('stop-voter',dict(forced=False),dict(stopped=True),now+150,now+400)
        self.control('collect',{},None,now+500,now+600)
        self.samples=[self.sample(0,t,'start' if t==0 else 'periodic') for t in range(0,now,10**9)]
        self.samples += [self.sample(0,now+300,'closed')]
        self.samples += [dict(self.sample(0,t,'window-start'),window=name) for t,name in starts]
        self.samples.sort(key=lambda s:s['localNanos'])
        for i,row in enumerate(self.samples,1):row['order']=i

    def render(self):
        for spec,events,result in self.extra:
            prefix='window-healthy-'+spec['window']+'/'
            self.files[prefix+'spec.json']=m.canonical(spec)
            self.files[prefix+'result.json']=m.canonical(result)
            self.files[prefix+'arrivals.jsonl']=b''.join(m.canonical(r)+b'\n' for r in events)
        super().render()

    def validate(self):return e.validate(self.root,self.config,self.manifest,self.base,self.transcript,active=self.active,healthy=True)


class HealthyEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.serial=0
    def fixture(self,**kwargs):
        self.serial+=1;return HealthyFixture(self.root/str(self.serial),**kwargs)
    def reject(self,change,**kwargs):
        f=self.fixture(**kwargs);change(f);f.render()
        with self.assertRaises((ValueError,KeyError)):f.validate()
    def test_complete_tape_in_all_modes_and_passive_members(self):
        for mode,active in [(v,True) for v in package.MODES]+[(v,False) for v in package.MODES[1:]]:
            with self.subTest(mode=mode,active=active):
                f=self.fixture(mode=mode,active=active);f.render();result=f.validate()
                self.assertEqual(result['calls'],90 if active else 0);self.assertFalse(result['physicalHistoryQualified'])
    def test_warmup_cannot_be_upgraded_to_complete_healthy(self):
        f=Fixture(self.root/'warmup');f.render()
        with self.assertRaisesRegex(ValueError,'issuer coverage'):
            e.validate(f.root,f.config,f.manifest,f.base,f.transcript,active=True,healthy=True)
    def test_missing_reordered_or_duplicate_window_rejected(self):
        self.reject(lambda f:f.transcript.pop(3))
        self.reject(lambda f:f.transcript.__setitem__(slice(3,5),f.transcript[3:5][::-1]))
        self.reject(lambda f:f.transcript.insert(4,f.transcript[3]))
    def test_frozen_later_window_cannot_be_shortened(self):
        self.reject(lambda f:f.extra[-1][0].update(durationNanos=10**9))
    def test_later_read_resealed_everywhere_still_needs_correct_logical_answer(self):
        f=self.fixture();response=f.results[-2];response['call'].update(answer=[],answerSha256=m.sha(m.canonical([])))
        for spec,events,result in f.extra:
            for row in [*events,*result['calls']]:
                if 'result' in row and row['result']['opId']==response['opId']:row['result']['resultSha256']=m.sha(m.canonical(response))
        f.render()
        with self.assertRaisesRegex(ValueError,'logical answer'):f.validate()
    def test_passive_window_missing_or_reordered_is_not_accepted(self):
        self.reject(lambda f:f.transcript.pop(3),active=False)
        self.reject(lambda f:f.transcript.__setitem__(slice(2,4),f.transcript[2:4][::-1]),active=False)
        self.reject(lambda f:f.exchanges[2]['request'].update(window='other'),active=False)
    def test_missing_later_resource_boundary_rejected_on_both_roles(self):
        for active in (True,False):
            self.reject(lambda f:f.samples.remove(next(s for s in reversed(f.samples) if s['boundary']=='window-start')),active=active)
    def test_complete_scope_is_explicit_not_inferred_from_guest(self):
        f=self.fixture();f.render()
        with self.assertRaisesRegex(ValueError,'issuer coverage'):
            e.validate(f.root,f.config,f.manifest,f.base,f.transcript,active=True)


if __name__=='__main__':unittest.main()
