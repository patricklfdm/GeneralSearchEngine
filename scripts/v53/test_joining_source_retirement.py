"""Collection refusal boundaries and independent prefix comparison."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import joining_source_retirement as r


class JoiningSourceRetirementTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.objects=self.root/r.DIRECTORY/'objects';self.objects.mkdir(parents=True)
        catalog=r.f.catalog()
        root=r.f.encode('records','ROOT',r.f.sample(catalog['records']['ROOT']['schema'],catalog['types']))
        node=r.f.sample(catalog['records']['NODE']['schema'],catalog['types']);node['root']=root[16:48].hex()
        self.files={'root.gsr':root,'node.gsr':r.f.encode('records','NODE',node)}
        self.events=[];self.index=0

    def point(self,point,files=None):
        self.index+=1;files=self.files if files is None else files;entries=[]
        for name,data in sorted(files.items()):
            if data is None:identity=dict(directory=True)
            else:
                digest=r.sha(data);(self.objects/digest).write_bytes(data);identity=dict(size=len(data),sha256=digest)
            entries.append(dict(name=name,identity=identity))
        metadata=dict(schema=r.SCHEMA,node='node-1',scope='test-owner',point=point,files=entries)
        raw=r.f.canonical(metadata);name=f'capture-{self.index:04d}.json';(self.root/r.DIRECTORY/name).write_bytes(raw)
        self.events += [dict(node='node-1',scope='test-owner',event=point),
            dict(node='node-1',scope='test-owner',event=r.EVENT,point=point,capture=r.DIRECTORY+'/'+name,sha256=r.sha(raw))]

    def transaction(self):
        self.point('SOURCE_RETIREMENT_CREATED');self.point('SOURCE_RETIREMENT_BEFORE_RETURN')

    def test_collection_is_not_independent_qualification(self):
        self.transaction();result=r.validate(self.root,self.events)
        self.assertEqual('PARTIAL',result['status']);self.assertEqual(2,result['capturedPrefixes'])
        self.assertFalse(result['independentlyDerived']);self.assertFalse(result['phase3Complete'])

    def test_start_copy_end_cannot_be_omitted_or_duplicated(self):
        self.transaction()
        for rows in (self.events[1:],self.events[:-1],self.events[:1]+self.events[2:],self.events[:2]+self.events):
            with self.subTest(rows=rows),self.assertRaises(ValueError):r.collect(self.root,rows)

    def test_scope_order_and_digest_are_bound_to_original_event(self):
        self.transaction()
        for field,value,reason in [('scope','wrong','event point/scope'),('point','WRONG','event point/scope'),
                ('sha256','0'*64,'event digest'),('capture','../wrong','ordered unique path')]:
            rows=copy.deepcopy(self.events);rows[1][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,reason):r.collect(self.root,rows)

    def test_missing_changed_or_unobserved_objects_fail(self):
        self.transaction();p=next(self.objects.iterdir());original=p.read_bytes()
        p.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'object identity/capacity'):r.collect(self.root,self.events)
        p.unlink()
        with self.assertRaisesRegex(ValueError,'missing object/size'):r.collect(self.root,self.events)
        p.write_bytes(original);extra=self.objects/r.sha(b'extra');extra.write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError,'unobserved object'):r.collect(self.root,self.events)

    def test_missing_parent_and_linked_object_are_rejected(self):
        self.point('SOURCE_RETIREMENT_CREATED',{**self.files,'absent/member':b'data'});self.point('SOURCE_RETIREMENT_BEFORE_RETURN')
        with self.assertRaisesRegex(ValueError,'parent directory'):r.collect(self.root,self.events)
        p=next(self.objects.iterdir());original=p.read_bytes();p.unlink();other=self.root/'external';other.write_bytes(original);p.symlink_to(other)
        with self.assertRaises(ValueError):r.collect(self.root,self.events)

    def test_independent_expected_prefix_rejects_reordered_force_and_other_file_change(self):
        initial={n:r.release.r.entry(data) for n,data in self.files.items()}
        initial.update({'sources':dict(directory=True),'sources/old':dict(directory=True),
                        'sources/old/source.gscp':r.release.r.entry(b'packet'),'grants.gsr':r.release.r.entry(b'prior')})
        expected=r.release.transaction(initial,b'decision',b'compact','old')
        # In this unit case the byte pool is independently supplied; no captured
        # snapshot or its checksums define the expected transaction.
        pool={r.sha(v):v for v in [*self.files.values(),b'packet',b'prior',b'decision',b'compact',b'']}
        rows=[dict(point=point,files={n:None if 'directory' in v else pool[v['sha256']] for n,v in state.items()}) for point,state in expected]
        transaction=dict(steps=rows)
        self.assertEqual(len(expected),r.compare(transaction,initial,b'decision',b'compact','old'))
        swapped=copy.deepcopy(transaction);swapped['steps'][1],swapped['steps'][2]=swapped['steps'][2],swapped['steps'][1]
        with self.assertRaisesRegex(ValueError,'original force order'):r.compare(swapped,initial,b'decision',b'compact','old')
        changed=copy.deepcopy(transaction);changed['steps'][-1]['files']['extra']=b'changed'
        with self.assertRaisesRegex(ValueError,'exact prefix'):r.compare(changed,initial,b'decision',b'compact','old')

    def test_invalid_original_cannot_count_as_negative_qualification(self):
        with patch.object(r,'component',side_effect=ValueError('invalid original')),patch.object(r,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):r.qualify_component('/unused')
            mutate.assert_not_called()

    def test_observation_marker_is_not_a_force_event(self):
        from . import joining_preparation_evidence as p
        from .test_joining_preparation_evidence import JoiningPreparationEvidenceTest
        rows=JoiningPreparationEvidenceTest().retirement()
        p.retirement_order([v for point in rows for v in (point,r.EVENT)],[2])
        with self.assertRaisesRegex(ValueError,'original source retirement order'):
            p.retirement_order([v for point in rows if point!='SOURCE_RETIREMENT_FORCED' for v in (point,r.EVENT)],[2])


if __name__=='__main__':unittest.main()
