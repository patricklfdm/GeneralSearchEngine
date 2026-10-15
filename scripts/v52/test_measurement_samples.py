import copy
import unittest
from . import measurement_samples as s


def rows():
    result=[]
    for i,kind in enumerate(('START','PERIODIC','STOP')):
        t=10_000_000_000+i*s.INTERVAL
        result.append(dict(sampleKind=kind,sampleOrdinal=i,dueNanos=t,sampleStartNanos=t+1,sampleEndNanos=t+10,localNanos=t+20,
                           node='node-1',pid=77,generation=1,marker='',heapUsedBytes=10,heapCommittedBytes=20,heapMaxBytes=dict(status='AVAILABLE',value=30),
                           nonHeapUsedBytes=2,processCpuNanos=dict(status='AVAILABLE',value=100+i),allocatedBytes=dict(status='AVAILABLE',value=200+i),
                           liveThreads=8,peakLiveThreads=9,gc=[],retainedBytes=30,consumerActive=0,consumerQueued=0,
                           queues=dict(admissionAvailable=64,**{key:0 for key in s.READ_COUNTS})))
    return result


def window_rows():
    template=rows()[0];origin=template['dueNanos'];result=[]
    specs=[('START',0,''),('MARK',100,'warmup-start'),('PERIODIC',s.INTERVAL,''),
           ('MARK',s.INTERVAL+500_000_000,'measured-start'),('PERIODIC',2*s.INTERVAL,''),
           ('PERIODIC',3*s.INTERVAL,''),('MARK',3*s.INTERVAL+100,'measured-end'),('STOP',3*s.INTERVAL+1000,'')]
    for i,(kind,offset,marker) in enumerate(specs):
        row=copy.deepcopy(template);time=origin+offset
        row.update(sampleKind=kind,sampleOrdinal=i,marker=marker,dueNanos=time,sampleStartNanos=time+1,
                   sampleEndNanos=time+10,localNanos=time+20,heapUsedBytes=10+i)
        row['processCpuNanos']['value']=1000+i*10;row['allocatedBytes']['value']=2000+i*100;result.append(row)
    return result


def window_input():
    samples=window_rows();controls=[];markers=[]
    boundary=[samples[0],samples[1],samples[3],samples[6],samples[7]]
    for i,(kind,row) in enumerate(zip(('sample-start','sample-mark','sample-mark','sample-mark','sample-stop'),boundary)):
        identity=str(i);call=dict(opId=identity,node='node-1',kind=kind,outcome='SUCCESS',startNanos=100+i*100,endNanos=150+i*100,
                                 response=dict(sample={k:v for k,v in row.items() if k not in s.trace.META}))
        if kind=='sample-mark':
            call['marker']=row['marker'];markers.append(dict(name=row['marker'],dueNanos=200+(i-1)*100,operations={'node-1':identity}))
        controls.append(call)
    return samples,'candidate-stale',controls,dict(startNanos=160,drainEndNanos=490),markers,'node-1'


class MeasurementSamplesTest(unittest.TestCase):
    def test_only_same_process_deltas_and_sampled_peaks(self):
        result=s.validate(rows(),'candidate-stale');self.assertEqual(3,result['samples']);self.assertEqual(2,result['cumulativeDeltas']['allocatedBytes']['value'])
        self.assertIn('not-exact-peak',result['semantics'])

    def test_missing_unsupported_allocation_is_not_zero(self):
        data=rows()
        for r in data:r['allocatedBytes']={'status':'UNSUPPORTED'}
        result=s.validate(data,'candidate-stale');self.assertEqual({'status':'INCOMPLETE','observedStatuses':['UNSUPPORTED']},result['cumulativeDeltas']['allocatedBytes'])
        data[0]['allocatedBytes']['value']=0
        with self.assertRaisesRegex(ValueError,'fabricated unavailable metric'):s.validate(data,'candidate-stale')

    def test_changed_or_missing_timing_and_negative_resource_values_fail(self):
        changes=[lambda r:r.pop(1),lambda r:r[1].__setitem__('dueNanos',1),lambda r:r[1].__setitem__('pid',88),
                 lambda r:r[1].__setitem__('sampleStartNanos',r[1]['sampleEndNanos']+1),lambda r:r[1].__setitem__('consumerQueued',65),
                 lambda r:r[1]['processCpuNanos'].__setitem__('value',1),lambda r:r[1].__setitem__('retainedBytes',True)]
        for change in changes:
            data=rows();change(data)
            with self.subTest(change=change),self.assertRaises(ValueError):s.validate(data,'candidate-stale')

    def test_candidate_counters_are_required_old_control_may_lack_them(self):
        data=rows()
        for r in data:r['queues']={'admissionAvailable':64}
        s.validate(data,'published-v51-legacy-strong')
        with self.assertRaisesRegex(ValueError,'missing candidate read counters'):s.validate(data,'candidate-stale')

    def test_only_complete_ordered_markers_are_accepted(self):
        data=rows();data[1]['sampleKind']='MARK';data[1]['marker']='measured-end'
        with self.assertRaisesRegex(ValueError,'window markers'):s.validate(data,'candidate-stale')

    def test_window_deltas_use_worker_markers_not_whole_session_or_controller_clocks(self):
        result=s.windows(*window_input())
        self.assertEqual(70,result['wholeSession']['cumulativeDeltas']['processCpuNanos']['value'])
        warm=result['windows']['warmup'];measured=result['windows']['measured']
        self.assertEqual(20,warm['cumulativeDeltas']['processCpuNanos']['value']);self.assertEqual(30,measured['cumulativeDeltas']['processCpuNanos']['value'])
        self.assertEqual(100,warm['nominalControllerDurationNanos'])
        self.assertGreater(warm['observedBoundarySpacingNanos'],1_000_000_000)
        self.assertEqual(13,warm['sampledHighWater']['heapUsedBytes']);self.assertEqual(16,measured['sampledHighWater']['heapUsedBytes'])
        self.assertEqual(2,measured['periodicSamples'])

    def test_missing_or_forged_window_control_and_boundary_reject(self):
        for change,reason in (
                (lambda d:d[2].pop(1),'control ledger'),
                (lambda d:d[2][0].__setitem__('endNanos',10000),'do not cover'),
                (lambda d:d[4][1]['operations'].__setitem__('node-1','different'),'original dispatch'),
                (lambda d:d[2][2]['response']['sample'].__setitem__('heapUsedBytes',999),'differs from observation')):
            data=window_input();change(data)
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):s.windows(*data)

    def test_unsupported_window_allocation_is_not_a_zero_delta(self):
        data=window_input()
        for row in data[0]:row['allocatedBytes']={'status':'UNSUPPORTED'}
        for call,row in zip(data[2],[data[0][0],data[0][1],data[0][3],data[0][6],data[0][7]]):
            call['response']['sample']={k:v for k,v in row.items() if k not in s.trace.META}
        result=s.windows(*data)
        for name in ('warmup','measured'):
            self.assertEqual(dict(status='INCOMPLETE',observedStatuses=['UNSUPPORTED']),result['windows'][name]['cumulativeDeltas']['allocatedBytes'])


if __name__=='__main__':unittest.main()
