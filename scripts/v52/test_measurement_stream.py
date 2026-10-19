import unittest
from . import measurement_stream as s


class Source:
    def __init__(self):self.visited=0
    def __iter__(self):
        for generation in (1,2):
            for ordinal in range(1,10001):
                self.visited+=1
                yield dict(node='node-1',pid=generation+100,generation=generation,order=ordinal,event='ORIGINAL',values={'x':ordinal})


class MeasurementStreamTest(unittest.TestCase):
    def test_only_target_generation_changes_and_multiple_passes_are_identical(self):
        original=Source()
        def mutate(row):row['values']['x']=-1;return row
        changed=s.changed({'node-1':original},lambda r:r['generation']==2 and r['order']==3,mutate)['node-1']
        for _ in range(2):
            observations=[(r['generation'],r['order']) for r in changed if r['values']['x']==-1]
            self.assertEqual([(2,3)],observations)
        self.assertTrue(all(r['values']['x']>0 for r in original))

    def test_dispatch_is_lazy_and_does_not_materialize_source(self):
        source=Source();changed=s.ChangedRow(source,('node-1',101,1,2),lambda row:None);iterator=iter(changed)
        self.assertEqual(0,source.visited);self.assertEqual(1,next(iterator)['order']);self.assertEqual(1,source.visited)
        self.assertEqual(3,next(iterator)['order']);self.assertEqual(3,source.visited);iterator.close()

    def test_missing_or_duplicate_target_never_qualifies_a_negative(self):
        source=Source()
        with self.assertRaisesRegex(ValueError,'target not found'):s.changed({'node-1':source},lambda r:r['order']==0,lambda r:r)
        with self.assertRaisesRegex(ValueError,'target missing/duplicate'):list(s.ChangedRow(source,('node-1',999,1,1),lambda r:r))
        duplicate=[dict(node='node-1',pid=101,generation=1,order=1)]*2
        with self.assertRaisesRegex(ValueError,'target missing/duplicate'):list(s.ChangedRow(duplicate,('node-1',101,1,1),lambda r:r))


if __name__=='__main__':unittest.main()
