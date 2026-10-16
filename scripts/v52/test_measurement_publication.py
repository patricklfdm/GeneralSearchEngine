import unittest
from unittest.mock import patch
from . import measurement_publication as p


class MeasurementPublicationTest(unittest.TestCase):
    def setUp(self):
        self.image=b'X'*16+b'Y'*32+b'payload';self.offer=dict(imageBytes=len(self.image),imageDigest=self.image[16:48].hex(),epoch=1,incarnation='id',proposer='node-1')

    def test_only_complete_exact_acknowledged_image_qualifies(self):
        t=p.Transfers();t.offer(('node-2','id'),self.offer)
        t.chunk(('node-2','id'),0,self.image[:30])
        with self.assertRaisesRegex(ValueError,'differs from transferred'):t.image(('node-2','id'))
        t.chunk(('node-2','id'),30,self.image[30:]);self.assertEqual(self.image,t.image(('node-2','id')))

    def test_protocol_retries_preserve_exact_bytes_and_do_not_double_count(self):
        t=p.Transfers();t.offer('id',self.offer);t.offer('id',dict(self.offer));t.chunk('id',0,self.image);t.chunk('id',0,self.image)
        self.assertEqual(len(self.image),t.bytes)
        with self.assertRaisesRegex(ValueError,'changed snapshot chunk'):t.chunk('id',0,b'Z'*len(self.image))
        with self.assertRaisesRegex(ValueError,'changed snapshot offer'):t.offer('id',dict(self.offer,epoch=2))

    def test_gaps_overlap_wrong_digest_and_foreign_transfer_fail(self):
        for offset in (29,31):
            t=p.Transfers();t.offer('id',self.offer);t.chunk('id',0,self.image[:30]);t.chunk('id',offset,self.image[30:40])
            with self.assertRaisesRegex(ValueError,'transfer hole'):t.image('id')
        t=p.Transfers();t.offer('id',dict(self.offer,imageDigest='0'*64));t.chunk('id',0,self.image)
        with self.assertRaisesRegex(ValueError,'differs from transferred'):t.image('id')
        with self.assertRaisesRegex(ValueError,'without offer'):t.chunk('foreign',0,b'x')
        with self.assertRaisesRegex(ValueError,'lacks snapshot offer'):t.image('foreign')

    def test_count_and_byte_bounds_fail_before_retaining_data(self):
        with patch.object(p,'MAX_TRANSFERS',1):
            t=p.Transfers()
            t.offer('one',self.offer)
            with self.assertRaisesRegex(ValueError,'transfer count'):t.offer('two',self.offer)
        with patch.object(p,'MAX_TRANSFER_BYTES',1):
            with self.assertRaisesRegex(ValueError,'byte/count bound'):t.chunk('one',0,b'xx')
        self.assertEqual(0,t.bytes);self.assertEqual({},t.chunks['one'])
        for value in (0,-1,True,1+(16<<20)):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'offer byte bound'):t.offer('bad',dict(self.offer,imageBytes=value))

    def test_full_history_accepts_distinct_follower_transfers_without_changing_smoke_limit(self):
        measured=p.Transfers(p.MAX_MEASURED_TRANSFERS);smoke=p.Transfers()
        # The retained stale history has 94 + 71 offers in the two followers.
        for node,count in (('node-2',94),('node-3',71)):
            for i in range(count):
                key=(node,1,str(i));measured.offer(key,self.offer);measured.chunk(key,0,self.image)
                self.assertEqual(self.image,measured.image(key))
        self.assertEqual(165,len(measured.offers));self.assertEqual(165*len(self.image),measured.bytes)
        for i in range(128):smoke.offer(str(i),self.offer)
        with self.assertRaisesRegex(ValueError,'transfer count'):smoke.offer('129',self.offer)

    def test_full_transfer_limit_is_global_finite_and_rejects_before_allocation(self):
        t=p.Transfers(p.MAX_MEASURED_TRANSFERS)
        for i in range(2048):t.offer(('node-'+str(i%3+1),1,str(i)),self.offer)
        before=dict(t.offers)
        with self.assertRaisesRegex(ValueError,'transfer count'):t.offer(('node-3',2,'new'),self.offer)
        self.assertEqual(before,t.offers);self.assertEqual(2048,len(t.chunks));self.assertEqual(0,t.bytes)
        # Retry of an existing identity is still valid at capacity.
        t.offer(('node-1',1,'0'),self.offer)
        with self.assertRaisesRegex(ValueError,'changed snapshot offer'):t.offer(('node-1',1,'0'),dict(self.offer,epoch=2))

    def test_full_profile_keeps_the_same_aggregate_chunk_byte_limit(self):
        t=p.Transfers(p.MAX_MEASURED_TRANSFERS);t.offer('one',self.offer);t.offer('two',self.offer)
        with patch.object(p,'MAX_TRANSFER_BYTES',len(self.image)):
            t.chunk('one',0,self.image);t.chunk('one',0,self.image)
            with self.assertRaisesRegex(ValueError,'byte/count bound'):t.chunk('two',0,b'x')
        self.assertEqual(len(self.image),t.bytes);self.assertEqual({},t.chunks['two'])

    def test_unknown_unbounded_and_boolean_transfer_profiles_fail_before_replay(self):
        for limit in (0,-1,True,2049,1.5,'2048'):
            with self.subTest(limit=limit),patch.object(p,'selection_budget') as scan:
                with self.assertRaisesRegex(ValueError,'transfer profile limit'):
                    p.validate({},None,None,'candidate-stale',transfer_limit=limit)
                scan.assert_not_called()

    def test_chunk_ranges_and_sizes_are_exact(self):
        t=p.Transfers();t.offer('id',self.offer)
        for offset,data in ((-1,b'x'),(True,b'x'),(len(self.image),b'x'),(0,b''),(0,b'x'*65537)):
            with self.subTest(offset=offset,size=len(data)),self.assertRaisesRegex(ValueError,'chunk range'):t.chunk('id',offset,data)

    def test_only_published_control_may_lack_restoration_observation(self):
        # The enclosing validator binds the actual loaded published/candidate JAR.
        with patch.object(p,'selection_budget',return_value={}),patch.object(p.reads,'selected_prefixes',return_value={}):
            result=p.validate({'node-1':[]},{},None,'published-v51-legacy-strong')
            self.assertFalse(result['restorationObservable'])
            for mode in ('candidate-legacy-strong','candidate-stale','candidate-minimum','candidate-explicit-strong'):
                with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'missing initial restoration'):
                    p.validate({'node-1':[]},{},None,mode)


if __name__=='__main__':unittest.main()
