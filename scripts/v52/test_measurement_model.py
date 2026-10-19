"""The offered schedule is fixed before any timed execution."""
import collections
import copy
import struct
import unittest
from . import measurement_model as m


class MeasurementProgramTest(unittest.TestCase):
    def test_fixed_open_loop_rates_and_window_boundaries(self):
        calls=m.program();self.assertEqual(1980,len(calls));self.assertEqual(181,m.projection(calls)['sequence'])
        counts=collections.Counter((r['window'],r['kind']) for r in calls)
        self.assertEqual({('warmup','read'):600,('warmup','update'):60,('measured','read'):1200,('measured','update'):120},counts)
        for ordinal in range(180):
            rows=[r for r in calls if ordinal*10**9<=r['offsetNanos']<(ordinal+1)*10**9]
            self.assertEqual(11,len(rows));self.assertEqual(ordinal*10**9+50_000_000,next(r['offsetNanos'] for r in rows if r['kind']=='update'))

    def test_each_measurement_window_has_exact_equal_query_mix(self):
        for window,count in (('warmup',120),('measured',240)):
            self.assertEqual({kind:count for kind in m.KINDS},collections.Counter(r['query']['kind'] for r in m.program() if r['kind']=='read' and r['window']==window))
        self.assertEqual(64,len({m.query(i)['id'] for i in range(1800) if i%5==0}))
        self.assertEqual(138,len(m.queries()))
        self.assertEqual({m.encoded(m.query(i)) for i in range(1800)},{m.encoded(q) for q in m.queries()})

    def test_all_generated_document_bytes_round_trip_without_coercion(self):
        for doc in m.corpus()+[v['document'] for v in m.program() if v['kind']=='update']:
            self.assertEqual(doc,m.decode_document(m.encode_document(doc)))
        for raw in (b'',struct.pack('>i',65)+b'out of range',struct.pack('>i',1)+b'java search',b'x'*129):
            with self.subTest(raw=raw[:8]),self.assertRaises(ValueError):m.decode_document(raw)
        for ordinal in (-1,1800,True):
            with self.assertRaises(ValueError):m.query(ordinal)

    def test_frozen_control_and_program_changes_reject(self):
        original=m.read(m.PLAN);m.validate(original)
        for field in ('warmupSeconds','measuredSeconds','offeredReadsPerSecond','minimumWaitTimeoutMillis'):
            changed=copy.deepcopy(original);changed['m01'][field]+=1
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'unreviewed'):m.validate(changed)
        changed=copy.deepcopy(original);changed['m01']['modes'][0]['name']='candidate-legacy-strong'
        with self.assertRaisesRegex(ValueError,'unreviewed'):m.validate(changed)

    def test_projection_cannot_turn_a_foreign_document_into_an_update(self):
        calls=m.program();mutated=copy.deepcopy(next(v for v in calls if v['kind']=='update'));mutated['document']['id']=65
        with self.assertRaises(ValueError):m.projection([mutated])


if __name__=='__main__':unittest.main()
