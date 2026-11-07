"""Original-bound queue frames and isolated retained-memory checks, not native acceptance."""
import base64
import gc
import tracemalloc
import unittest
from . import segmented_queue_frames as m
from . import test_segmented_transcript as transcript
from . import test_wire_archive as archive


class SegmentedQueueFramesTest(unittest.TestCase):
    def capture(self,**options):
        data=transcript.trace(**options)
        fixture=archive.WireArchiveTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.original({'wire.json':data[1]})
        return fixture.open().read('wire.json'),fixture

    def index(self,source,side):
        frames=m.Frames(source,side)
        for index,row in enumerate(source):
            raw=base64.b64decode(row[side],validate=True);kind,value,size=m.queue.frame(raw)
            frames.record(index,m.queue.sha(raw),kind,size)
        return frames

    def test_frames_match_originals_and_return_fresh_decoded_values(self):
        source,_=self.capture()
        for side in ('request','response'):
            frames=self.index(source,side)
            for row in source:
                raw=base64.b64decode(row[side]);key=m.queue.sha(raw)
                self.assertEqual(m.queue.frame(raw),frames[key])
                frames[key][1]['payload'].clear()
                self.assertEqual(m.queue.frame(raw),frames[key])
            self.assertEqual(len(source),len(frames))
            with self.assertRaises(KeyError):frames['0'*64]

    def test_requires_checked_original_and_explicit_direction(self):
        source,_=self.capture()
        for original,side in ((list(source),'response'),(source,'auto'),(source,True)):
            with self.subTest(side=side),self.assertRaisesRegex(ValueError,'^segmented queue original frames$'):
                m.Frames(original,side)

    def test_positions_reject_wrong_types_bounds_and_conflicting_duplicate_sizes(self):
        source,_=self.capture();frames=self.index(source,'response')
        digest=next(iter(frames));index,kind,size=frames.positions[digest]
        for values in ((True,digest,kind,size),(len(source),digest,kind,size),(index,'x',kind,size),
                       (index,digest,'unknown',size),(index,digest,kind,True),(index,digest,kind,m.segmented.ROW_BYTES+1)):
            with self.subTest(values=values),self.assertRaisesRegex(ValueError,'^segmented queue frame position$'):frames.record(*values)
        with self.assertRaisesRegex(ValueError,'^segmented queue duplicate frame binding$'):
            frames.record(index,digest,kind,size+1)

    def test_retransmission_keeps_first_original_position_and_decodes_identically(self):
        data=transcript.trace(repetitions=1);rows=data[1];rows.append(dict(rows[0]))
        fixture=archive.WireArchiveTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.original({'wire.json':rows});source=fixture.open().read('wire.json')
        for side in ('request','response'):
            frames=self.index(source,side);raw=base64.b64decode(rows[0][side]);key=m.queue.sha(raw)
            self.assertEqual(len(rows)-1,len(frames));self.assertEqual(0,frames.positions[key][0])
            self.assertEqual(m.queue.frame(raw),frames[key])

    def test_position_kind_size_and_hash_cannot_substitute_a_different_frame(self):
        source,_=self.capture();frames=self.index(source,'response');key=next(iter(frames))
        index,kind,size=frames.positions[key]
        for wrong in ((index+1,kind,size),(index,'CHUNK',size),(index,kind,size+1)):
            frames.positions[key]=wrong
            with self.subTest(wrong=wrong),self.assertRaisesRegex(ValueError,'^segmented queue original frame binding$'):frames[key]
        frames.positions['0'*64]=(index,kind,size)
        with self.assertRaisesRegex(ValueError,'^segmented queue original frame binding$'):frames['0'*64]

    def test_changed_retained_original_is_rejected_instead_of_using_cached_frames(self):
        source,fixture=self.capture();frames=self.index(source,'response');key=next(iter(frames))
        original=frames[key]
        part=next((fixture.root/'segmented-wire/wire/segments').iterdir());part.write_bytes(part.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'segmented evidence'):frames[key]
        self.assertEqual('SOURCE_OFFER',original[0])

    def test_retained_index_does_not_grow_with_decoded_payloads(self):
        # Twelve distinct 256 KiB DATA responses retain >4 MiB when decoded.
        # The checked Reader is allocated before measurement; this test isolates
        # only the queue frame index, not whole-reader maximum-input memory.
        source,_=self.capture(data=b'x'*(256*1024),repetitions=12,chunk_bytes=256*1024)
        m.queue.frame(base64.b64decode(source[0]['response']))
        gc.collect();tracemalloc.start()
        try:
            frames=self.index(source,'response');gc.collect();retained,_=tracemalloc.get_traced_memory()
            self.assertEqual(36,len(frames));self.assertLess(retained,512*1024)
            self.assertTrue(all(type(v) is tuple and len(v)==3 for v in frames.positions.values()))
        finally:tracemalloc.stop()


if __name__=='__main__':unittest.main()
