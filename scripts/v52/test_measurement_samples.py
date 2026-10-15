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


if __name__=='__main__':unittest.main()
