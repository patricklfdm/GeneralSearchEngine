import copy
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
from . import pinned_floor_process_evidence as e


class PinnedFloorProcessEvidenceTest(unittest.TestCase):
    def test_each_establishment_retirement_and_release_boundary_has_both_death_modes(self):
        rows=e.cases();self.assertEqual(36,len(rows));self.assertEqual(36,len({v['case'] for v in rows}))
        for mode in ('halt','kill'):self.assertEqual(set(e.CUTS),{v['cut'] for v in rows if v['mode']==mode})
        self.assertIn('FLOOR_LOCAL_ORIGINAL_FORCED',e.CUTS)
        self.assertIn('FLOOR_RELEASE_LOCAL_CLEARED',e.CUTS)
        self.assertIn('RETIREMENT_FILE_DELETED',e.CUTS)

    def test_producer_and_reader_bind_the_same_ordered_cut_matrix(self):
        root=Path(__file__).resolve().parents[2]
        path=root/'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication/V53PinnedFloorProcessTest.java'
        cuts=path.read_text().split('CUTS=List.of(',1)[1].split(');',1)[0]
        self.assertEqual(list(e.CUTS),re.findall(r'"([A-Z_]+)"',cuts))

    @staticmethod
    def fixture(path,action='fault',mode='kill'):
        cut='FLOOR_LOCAL_SELECTOR_FORCED';events=['CURRENT_VALIDATED','FLOOR_LOCAL_ORIGINAL_FORCED',cut]
        metadata=dict(pid=123,action=action,exit=(137 if mode=='kill' else 73) if action=='fault' else 0,lockProbe=action=='fault' and mode=='kill')
        rows=[dict(event='STARTED',pid=123,action=action)]
        rows.extend(dict(event=v,sources=2,images=4) for v in events)
        if action=='fault':
            rows.append(dict(event='CUT',cut=cut,pid=123))
            if mode=='kill':rows.append(dict(event='AWAITING_KILL',cut=cut))
        else:rows.append(dict(status='PASS',pid=123,action=action,peakSources=2,peakImages=4,nativeHistory=False))
        (path/(action+'.stdout')).write_bytes(b''.join(e.e.f.canonical(v)+b'\n' for v in rows));(path/(action+'.stderr')).write_bytes(b'')
        return metadata,dict(mode=mode,cut=cut),events,rows

    def test_exit_lock_probe_and_process_start_are_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);meta,row,events,_=self.fixture(path);self.assertEqual(123,e.process(path,meta,'fault',row,events))
            for field,value in (('exit',0),('exit',True),('lockProbe',False),('pid',True),('pid',124)):
                with self.subTest(field=field,value=value),self.assertRaises(ValueError):e.process(path,dict(meta,**{field:value}),'fault',row,events)

    def test_missing_original_force_or_invented_capacity_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);meta,row,events,rows=self.fixture(path)
            for mode in ('missing','order','capacity'):
                changed=copy.deepcopy(rows)
                if mode=='missing':changed.pop(2)
                elif mode=='order':changed[1],changed[2]=changed[2],changed[1]
                else:changed[2]['images']=8
                (path/'fault.stdout').write_bytes(b''.join(e.e.f.canonical(v)+b'\n' for v in changed))
                with self.subTest(mode=mode),self.assertRaises(ValueError):e.process(path,meta,'fault',row,events)

    def test_recovered_result_cannot_overstate_the_observed_peak(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);meta,row,events,rows=self.fixture(path,action='resume')
            e.process(path,meta,'resume',row,events)
            for field,value in (('peakImages',7),('nativeHistory',0)):
                changed=copy.deepcopy(rows);changed[-1][field]=value
                (path/'resume.stdout').write_bytes(b''.join(e.e.f.canonical(v)+b'\n' for v in changed))
                with self.subTest(field=field),self.assertRaisesRegex(ValueError,'return binding'):e.process(path,meta,'resume',row,events)

    def test_non_object_return_is_an_evidence_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);meta,row,events,rows=self.fixture(path,action='resume')
            rows[-1]='PASS'
            (path/'resume.stdout').write_bytes(b''.join(e.e.f.canonical(v)+b'\n' for v in rows))
            with self.assertRaisesRegex(ValueError,'return binding'):e.process(path,meta,'resume',row,events)

    def test_invalid_original_never_counts_as_successful_negatives(self):
        with patch.object(e,'inventory',return_value={}),patch.object(e,'validate',side_effect=ValueError('original')),patch.object(e.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'original'):e.qualify('absent')
            copied.assert_not_called()

    def test_unrelated_negative_is_rejected(self):
        with patch.object(e,'inventory',return_value={}),patch.object(e,'validate',side_effect=[{},ValueError('unrelated')]),patch.object(e.shutil,'copytree'),patch.object(e,'mutate'):
            with self.assertRaisesRegex(ValueError,'unrelated negative'):e.qualify('absent')

    def test_original_cannot_change_during_mutation_replay(self):
        with patch.object(e,'inventory',side_effect=[{},dict(changed=True)]),patch.object(e,'validate',side_effect=[{}]+[ValueError(v) for v in e.NEGATIVES.values()]),patch.object(e.shutil,'copytree'),patch.object(e,'mutate'):
            with self.assertRaisesRegex(ValueError,'changed original'):e.qualify('absent')

    def test_inventory_refuses_symlink_and_hardlink_aliases(self):
        import os
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);original=path/'original';original.write_bytes(b'original')
            alias=path/'alias';alias.symlink_to('original')
            with self.assertRaisesRegex(ValueError,'history type/count'):e.inventory(path)
            alias.unlink();os.link(original,alias)
            with self.assertRaisesRegex(ValueError,'history alias'):e.inventory(path)

    def test_every_projected_boundary_preserves_current_and_capacity(self):
        original={'generations/a':dict(directory=True),'generations/a/data.image':dict(bytes=1,sha256='a'*64)}
        self.assertEqual((0,1),e.physical(original,original))
        with self.assertRaisesRegex(ValueError,'original lifetime'):e.physical({},original)
        full=dict(original,**{'floor-copies/'+str(i):dict(directory=True) for i in range(7)})
        with self.assertRaisesRegex(ValueError,'physical capacity'):e.physical(full,original)
        full=dict(original,**{'floor-copies/'+str(i)+'/data.image':dict(bytes=1,sha256='a'*64) for i in range(7)})
        with self.assertRaisesRegex(ValueError,'physical capacity'):e.physical(full,original)


if __name__=='__main__':unittest.main()
