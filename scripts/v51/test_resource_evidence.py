"""Counterexamples for exact limits, uncertain evidence and overflow boundaries."""
import copy
import unittest
from . import resource_evidence as e,model

class ResourceEvidenceTest(unittest.TestCase):
    def test_actual_reservation_exceeds_available_bytes(self):
        e.reservation(dict(limit=100,retained=90,replaced=10,requested=21))
    def test_exactly_fitting_reservation_cannot_prove_exhaustion(self):
        with self.assertRaises(ValueError):e.reservation(dict(limit=100,retained=90,replaced=10,requested=20))
    def test_replaced_bytes_cannot_exceed_existing_inventory(self):
        with self.assertRaises(ValueError):e.reservation(dict(limit=100,retained=10,replaced=11,requested=200))
    def probes(self):
        rows=[]
        for observed in ((1<<63)-7,(1<<63)-4,(1<<63)-1):
            for rank in range(3):
                row=dict(observed=observed,rank=rank)
                try:row['next']=model.next_epoch(observed,rank)
                except model.Rejected:row['reason']='CAPACITY_EXCEEDED'
                rows.append(row)
        return rows
    def test_ranked_epoch_boundary_preserves_success_and_overflow(self):e.epoch_probes(self.probes())
    def test_wrapped_epoch_is_rejected(self):
        rows=self.probes();rows[-1]=dict(observed=(1<<63)-1,rank=2,next=1)
        with self.assertRaisesRegex(ValueError,'overflow'):e.epoch_probes(rows)
    def test_success_at_wrong_rank_is_rejected(self):
        rows=self.probes();rows[0]['next']+=1
        with self.assertRaisesRegex(ValueError,'ranked'):e.epoch_probes(rows)
    def test_incomplete_rank_matrix_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'missing'):e.epoch_probes(self.probes()[:-1])
    def test_exact_promise_boundary(self):e.capacity_math('promise-count',10000,dict(promiseCount=10000,promisedEpoch=29996),dict(epoch=29999),0)
    def test_promise_limit_cannot_be_lowered_for_a_passing_case(self):
        with self.assertRaisesRegex(ValueError,'limit'):e.capacity_math('promise-count',10,dict(promiseCount=10,promisedEpoch=29),dict(epoch=32),0)
    def test_retained_byte_limit_is_exact(self):
        e.capacity_math('retained-bytes',800,{},dict(bytes=100),800)
        with self.assertRaisesRegex(ValueError,'full'):e.capacity_math('retained-bytes',800,{},dict(bytes=100),799)
    def test_transfer_reserves_total_image_plus_existing_inventory(self):e.capacity_math('transfer-staging',128<<10,{},dict(imageBytes=128<<10,receivedBytes=0),20000)
    def test_small_chunk_does_not_justify_oversized_transfer(self):
        with self.assertRaisesRegex(ValueError,'boundary'):e.capacity_math('transfer-staging',128<<10,{},dict(imageBytes=1,receivedBytes=0),20000)
    def test_ancestry_and_entry_limits_remain_distinct(self):
        for case,key in [('entry-count','index'),('ancestry-count','count')]:
            e.capacity_math(case,1000000,{}, {key:1000001},0)
            with self.assertRaises(ValueError):e.capacity_math(case,1000000,{}, {key:1000000},0)
    def test_capacity_does_not_allow_cleanup_or_a_different_reason(self):
        row=dict(case='entry-count',limit=1000000,rejection=dict(reason='CAPACITY_EXCEEDED'),eventsBefore={},eventsAfter={})
        e.internal_claim(row,{},dict(index=1000001),0)
        changed=copy.deepcopy(row);changed['eventsAfter']['DELETE_AFTER_ROOT_TRUNCATE']=1
        with self.assertRaisesRegex(ValueError,'wrote/deleted'):e.internal_claim(changed,{},dict(index=1000001),0)
        changed=copy.deepcopy(row);changed['rejection']['reason']='STORAGE_FAILURE'
        with self.assertRaisesRegex(ValueError,'misclassified'):e.internal_claim(changed,{},dict(index=1000001),0)
    def test_exact_retry_may_reforce_but_never_append(self):
        report=dict(promiseCount=10000,promisedEpoch=29996)
        row=dict(case='promise-count',limit=10000,rejection=dict(reason='CAPACITY_EXCEEDED'),afterStatus=report,eventsBefore={},eventsAfter=dict(PROMISE_AFTER_FORCE=1,PROMISE_BEFORE_ACK=1))
        e.internal_claim(row,report,dict(epoch=29999),0)
        row['eventsAfter']['PROMISE_AFTER_WRITE']=1
        with self.assertRaisesRegex(ValueError,'wrote/deleted'):e.internal_claim(row,report,dict(epoch=29999),0)

class SnapshotOfferEvidenceTest(unittest.TestCase):
    def pair(self,size=32769):
        request=dict(type='SNAPSHOT_OFFER',groupId='group',configurationId='config',manifestDigest='digest',
                     epoch=2,proposer='node-1',incarnationId='incarnation',traceId='trace',eventSequence=19,
                     sender='node-1',recipient='node-3',payload=dict(response=False,imageBytes=size))
        reply=dict(request,type='REJECT',sender='node-3',recipient='node-1',payload=dict(reason='CAPACITY_EXCEEDED'))
        return request,reply

    def test_offer_above_one_quarter_staging_is_a_real_rejection(self):
        self.assertEqual(dict(boundary='snapshot-offer',transferLimit=32768),e.snapshot_offer(*self.pair(),128<<10))

    def test_ci_image_and_exactly_fitting_image_do_not_prove_exhaustion(self):
        # Actual CI failure: cleanup let the 25,452-byte image fit repeatedly.
        for size in (25452,32768):
            with self.subTest(size=size),self.assertRaisesRegex(ValueError,'fits'):
                e.snapshot_offer(*self.pair(size),128<<10)

    def test_rejection_for_another_exchange_is_not_capacity_evidence(self):
        for key in ('traceId','eventSequence','epoch','proposer','incarnationId','sender','recipient','manifestDigest','groupId','configurationId'):
            request,reply=self.pair();reply[key]='different'
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'correlation'):
                e.snapshot_offer(request,reply,128<<10)

    def test_not_ready_or_integrity_failure_cannot_replace_capacity(self):
        for reason in ('NOT_READY','INTEGRITY_FAILURE','STALE_EPOCH'):
            request,reply=self.pair();reply['payload']['reason']=reason
            with self.assertRaisesRegex(ValueError,'capacity'):e.snapshot_offer(request,reply,128<<10)

    def test_successful_offer_does_not_establish_exhaustion(self):
        request,reply=self.pair();reply['type']='SNAPSHOT_OFFER'
        with self.assertRaisesRegex(ValueError,'capacity'):e.snapshot_offer(request,reply,128<<10)

    def test_enlarged_sealed_bound_invalidates_exhaustion_claim(self):
        with self.assertRaisesRegex(ValueError,'fits'):e.snapshot_offer(*self.pair(),256<<10)

    def test_global_image_limit_still_caps_large_staging_budget(self):
        self.assertEqual(64<<20,e.snapshot_offer(*self.pair((64<<20)+1),1<<30)['transferLimit'])

    def test_wrong_request_direction_or_kind_cannot_prove_exhaustion(self):
        for changes in (dict(type='SOURCE_OFFER'),dict(payload=dict(response=True,imageBytes=32769))):
            request,reply=self.pair();request.update(changes)
            with self.assertRaisesRegex(ValueError,'request'):e.snapshot_offer(request,reply,128<<10)

if __name__=='__main__':unittest.main()
