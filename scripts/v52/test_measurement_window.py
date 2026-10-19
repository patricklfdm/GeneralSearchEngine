import copy
import unittest
from . import measurement_model as model,measurement_window as w


def fixture(mode='candidate-stale'):
    start=10_000_000_000;leader='node-1';target=leader if mode.endswith('strong') else 'node-3';history=[];offers=[]
    initial=dict(opId='setup',kind='read',setupToken=True,node=leader,query=model.query(0),startNanos=start-200,endNanos=start-100,
                 outcome='SUCCESS',response=dict(token='carried-token',outcome='SUCCESS'))
    for i,request in enumerate(model.program()):
        due=start+request['offsetNanos'];response=dict(opId=str(i),outcome='SUCCESS',receivedNanos=1000+i*100,apiStartNanos=1010+i*100,apiEndNanos=1020+i*100)
        call=dict(opId=str(i),kind=request['kind'],node=leader if request['kind']=='update' else target,startNanos=due+1,endNanos=due+30,outcome='SUCCESS',response=response)
        call.update({k:request[k] for k in ('query','document') if k in request})
        if mode=='candidate-minimum' and call['kind']=='read':call['minimum']='carried-token'
        history.append(call);offers.append(dict(ordinal=i,request=request,dueNanos=due,offerNanos=due,submittedNanos=due+10,status='DISPATCHED',opId=str(i),completionStatus='OBSERVED',response=response))
    offered=dict(startNanos=start,durationNanos=w.DURATION,dispatchEndNanos=start+w.DURATION,drainStartNanos=start+w.DURATION,
                 drainEndNanos=start+w.DURATION+1000,unobserved=0,failure=None,offers=offers)
    return offered,[initial,*history],mode,leader,target,'setup',1


class MeasurementWindowTest(unittest.TestCase):
    def test_full_program_counts_and_independent_clocks_for_every_mode(self):
        for mode in model.MODES:
            result=w.validate(*fixture(mode));self.assertEqual(1980,result['completed']);self.assertFalse(result['qualifiedMeasurement'])
            for name,reads,writes in (('warmup',600,60),('measured',1200,120)):
                groups=result['windows'][name]['operations'];self.assertEqual(reads,groups['read']['offered']);self.assertEqual(writes,groups['update']['offered'])
                self.assertEqual(10,groups['read']['latencyNanos']['apiNanos']['p99'])

    def test_failed_slow_call_remains_in_counts_and_latency_samples(self):
        data=fixture();call=data[1][2];call['outcome']='INDETERMINATE';call['response'].update(outcome='INDETERMINATE',reasonCode='QUORUM_UNAVAILABLE')
        call['endNanos']=data[0]['startNanos']+w.DURATION+500
        result=w.validate(*data);group=result['windows']['warmup']['operations']['update']
        self.assertEqual({'INDETERMINATE':1,'SUCCESS':59},group['outcomes']);self.assertEqual(1,group['completedAfterWindow'])
        self.assertEqual(60,group['latencyNanos']['dueToResponseNanos']['count']);self.assertGreater(group['latencyNanos']['dueToResponseNanos']['max'],60_000_000_000)

    def test_no_vacuous_success_with_all_failed_kind_or_window(self):
        for wanted_kind in ('read','update'):
            data=fixture()
            for call in data[1][1:]:
                if call['kind']==wanted_kind and (wanted_kind=='update' or call['query']['kind']=='highlight'):
                    call['outcome']='NOT_APPLICABLE' if wanted_kind=='read' else 'NOT_SUBMITTED';call['response'].update(outcome=call['outcome'],reasonCode='NOT_READY')
            with self.subTest(kind=wanted_kind),self.assertRaisesRegex(ValueError,'lacks successful'):w.validate(*data)

    def test_extra_mutation_retry_and_hidden_setup_read_reject(self):
        for change in ('extra','setup'):
            data=fixture()
            if change=='extra':
                extra=copy.deepcopy(data[1][2]);extra['opId']='retry';data[1].append(extra)
            else:data[1][1]['setupToken']=True
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'undeclared/missing|setup substitution'):w.validate(*data)

    def test_changed_target_token_or_repetition_rejects(self):
        data=list(fixture());data[4]='node-2'
        with self.assertRaisesRegex(ValueError,'frozen read target'):w.validate(*data)
        data=fixture('candidate-minimum');data[1][1]['minimum']='other-token'
        with self.assertRaisesRegex(ValueError,'carried initial token'):w.validate(*data)
        data=list(fixture());data[-1]=True
        with self.assertRaisesRegex(ValueError,'mode/repetition'):w.validate(*data)

    def test_original_due_times_window_and_call_counts_cannot_shrink(self):
        for change in (lambda d:d[0]['offers'].pop(),lambda d:d[0].__setitem__('durationNanos',120_000_000_000),
                       lambda d:d[0]['offers'][1000].__setitem__('dueNanos',0),lambda d:d[0]['offers'][1000]['request'].__setitem__('window','warmup')):
            data=fixture();change(data)
            with self.assertRaises(ValueError):w.validate(*data)

    def test_percentiles_include_tail_and_have_no_fabricated_empty_value(self):
        self.assertEqual(dict(count=0,min=None,p50=None,p95=None,p99=None,max=None),w.distribution([]))
        result=w.distribution(list(range(1,101)));self.assertEqual((50,95,99,100),(result['p50'],result['p95'],result['p99'],result['max']))
        for values in ([-1],[True],[1.5]):
            with self.assertRaises(ValueError):w.distribution(values)


if __name__=='__main__':unittest.main()
