"""Conditional custody/entry regressions, not a substitute for native replay."""
import copy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import required_four_maintenance as r
from . import pinned_floor_evidence as pinned


class RequiredFourMaintenanceTest(unittest.TestCase):
    def fixture(self):
        copies={node:dict(node=node,manifest=('manifest-'+node).encode(),
                members={'source.gscp':b'packet','promise.gsr':b'promise','a.image':b'image'})
                for node in ('node-1','node-2','node-3','node-6')}
        own=copies['node-1'];selector=r.m.f.encode('records','SELECTOR',dict(root='a'*64,node='node-1',generation='a',
                                                                        digest=r.m.sha(own['manifest'])))
        files={'selector.gsr':selector,'floor-copies/local.gsr':selector,
               'generations/a/generation.gsr':own['manifest'],
               **{'generations/a/'+name:raw for name,raw in own['members'].items()}}
        rows=[dict(node='node-1',steps=[dict(event=10,files=copy.deepcopy(files)),dict(event=20,files=copy.deepcopy(files))])]
        return copies,own,selector,rows

    def test_pinned_events_keep_logical_four_but_only_three_copied_generations(self):
        copies,own,selector,_=self.fixture()
        actual=r.m.floor_events(copies,own['node'],True,pinned=True)
        self.assertEqual(4,len(copies));self.assertEqual(3,actual.count('FLOOR_MANIFEST_FORCED'))
        self.assertEqual(3,actual.count('FLOOR_COPY_HANDED_OFF'));self.assertEqual(12,actual.count('FLOOR_RELEASE_FILE_DELETED'))
        self.assertEqual(3,actual.count('FLOOR_RELEASE_COPY_DELETED'))
        # Independent existing pin transaction derives identical disk boundaries.
        raw={r.m.sha(v['manifest']):dict(v['members'],**{'generation.gsr':v['manifest']}) for v in copies.values()}
        forced,files,dirs=pinned.floor_plan(raw,b'floor',selector)
        expected=forced+pinned.release_events(dict({n:dict(directory=True) for n in dirs},
                                                  **{n:pinned.original.info(v) for n,v in files.items()}))
        self.assertEqual(expected,[v for v in actual if v!='FLOOR_COPY_HANDED_OFF'])
        self.assertEqual(4,r.m.floor_events(copies,own['node'],True).count('FLOOR_COPY_HANDED_OFF'))
        for flag in (1,'true',None):
            with self.assertRaisesRegex(ValueError,'pinned local copy'):r.m.floor_events(copies,own['node'],True,pinned=flag)

    def test_selector_and_every_captured_original_member_are_bound(self):
        _,own,selector,rows=self.fixture();self.assertTrue(r.captured_pin(rows,own,0,30,selector))
        for name in ('floor-copies/local.gsr','selector.gsr','generations/a/generation.gsr','generations/a/source.gscp','generations/a/a.image'):
            with self.subTest(name=name):
                changed=copy.deepcopy(rows);changed[0]['steps'][-1]['files'][name]=b'changed'
                with self.assertRaisesRegex(ValueError,'original pin(ned generation| selector) binding'):
                    r.captured_pin(changed,own,0,30,selector)
        changed=copy.deepcopy(rows);changed[0]['steps'][0]['files']['generations/a/extra']=b'extra'
        with self.assertRaisesRegex(ValueError,'original pinned generation binding'):r.captured_pin(changed,own,0,30,selector)

    def test_pin_cannot_point_to_another_owner_or_manifest(self):
        _,own,selector,rows=self.fixture()
        value=r.m.f.decode(selector,'records','SELECTOR')
        for key,other in (('node','node-2'),('digest','b'*64)):
            changed=r.m.f.encode('records','SELECTOR',dict(value,**{key:other}))
            for step in rows[0]['steps']:step['files']['floor-copies/local.gsr']=changed
            with self.assertRaisesRegex(ValueError,'original pin selector binding'):r.captured_pin(rows,own,0,30,changed)

    def test_pin_never_substitutes_a_duplicate_local_copy_or_partial_lifetime(self):
        _,own,selector,rows=self.fixture()
        changed=copy.deepcopy(rows);changed[0]['steps'][0]['files']['floor-copies/'+r.m.sha(own['manifest'])]=None
        with self.assertRaisesRegex(ValueError,'pinned original also copied'):r.captured_pin(changed,own,0,30,selector)
        with self.assertRaisesRegex(ValueError,'pin capture outside floor'):r.captured_pin(rows,own,15,30,selector)
        rows[0]['steps'][0]['files'].pop('floor-copies/local.gsr')
        with self.assertRaisesRegex(ValueError,'original pin selector binding'):r.captured_pin(rows,own,0,30,selector)

    def test_other_owner_or_floor_cannot_supply_a_pin(self):
        _,own,selector,rows=self.fixture()
        self.assertFalse(r.captured_pin(rows,own,30,40,selector))
        rows[0]['node']='node-2';self.assertFalse(r.captured_pin(rows,own,0,30,selector))
        rows[0]['node']='node-1'
        for step in rows[0]['steps']:step['files'].pop('floor-copies/local.gsr')
        self.assertFalse(r.captured_pin(rows,own,0,30,selector))

    def test_expected_events_choose_pin_from_original_bytes_not_callbacks(self):
        copies,own,selector,rows=self.fixture()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'selector.gsr').write_bytes(selector);own['path']='.'
            reader=r.Replay.__new__(r.Replay);reader.root=root;reader.capture_transactions=rows;reader.pinned_floors=set()
            reader.events=[]
            names=reader.expected_events(copies,own,True,0,30)
            self.assertIn('FLOOR_LOCAL_ORIGINAL_FORCED',names);self.assertEqual({('node-1',0)},reader.pinned_floors)
            reader.capture_transactions=[];reader.events=[dict(event=point) for point in r.PIN_POINTS]
            self.assertNotIn('FLOOR_LOCAL_ORIGINAL_FORCED',reader.expected_events(copies,own,True,0,30))

    def test_all_old_negatives_and_five_pin_boundaries_remain_required(self):
        self.assertEqual(20,len(r.NEGATIVES))
        self.assertEqual(r.profile.NEGATIVES,{k:v for k,v in r.NEGATIVES.items() if not k.startswith('pin/')})
        self.assertEqual(set(r.PIN_POINTS),{k[4:] for k in r.NEGATIVES if k.startswith('pin/')})

    def test_temporal_floor_reader_rejects_each_missing_pin_boundary(self):
        copies,own,selector,rows=self.fixture()
        names=r.m.floor_events(copies,own['node'],True,pinned=True)
        before=names.index('FLOOR_BEFORE_RETURN')+1
        names[before:before]=['SOURCE_RETIREMENT_CREATED','SOURCE_RETIREMENT_BEFORE_RETURN']
        for step,at in zip(rows[0]['steps'],(before,before+1)):step['event']=at
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'selector.gsr').write_bytes(selector)
            own.update(path='.',start=-1,end=len(names)+1)
            reader=r.Replay.__new__(r.Replay);reader.root=root;reader.capture_transactions=rows
            reader.windows=[own];reader.model=SimpleNamespace(joining='node-6')
            reader.acquired=lambda *args:(copies,['original hint']);reader.governing=lambda *args:None
            for removed in (None,*r.PIN_POINTS):
                reader.pinned_floors=set()
                reader.events=[dict(node='node-1',event=point if point!=removed else 'REMOVED') for point in names]
                if removed is None:
                    result=r.m.Replay.floors(reader)
                    self.assertEqual(4,result['completeCopies']);self.assertEqual({('node-1',0)},reader.pinned_floors)
                else:
                    with self.subTest(removed=removed),self.assertRaisesRegex(ValueError,'exact copy force/release order'):
                        r.m.Replay.floors(reader)

    def test_invalid_original_stops_before_maintenance_or_mutation(self):
        with patch.object(r.collection,'inventory',return_value={}),patch.object(r.exports,'validate',side_effect=ValueError('original refused')), \
             patch.object(r,'replay') as replay,patch.object(r.shutil,'copytree') as copied:
            for action in (r.validate,r.qualify):
                with self.assertRaisesRegex(ValueError,'^original refused$'):action('/unused')
            replay.assert_not_called();copied.assert_not_called()

    def test_full_entry_compares_physical_pin_count_and_keeps_scope(self):
        original=dict(precondition=dict(physical=dict(physical=dict(pinnedMaintenanceFloors=3))))
        result=dict(pinnedMaintenanceFloors=3)
        with patch.object(r.collection,'inventory',return_value={}),patch.object(r.exports,'validate',return_value=original), \
             patch.object(r,'replay',return_value=result):
            receipt=r.validate('/unused');self.assertTrue(receipt['maintenanceForceQualified'])
            for flag in ('peerLedgerCompositionQualified','wholeRuntimeResourcesQualified','completePhysicalQualified',
                         'processDeathQualified','finalSourceCohortQualified','phase3Complete'):
                self.assertFalse(receipt[flag])
            result['pinnedMaintenanceFloors']=2
            with self.assertRaisesRegex(ValueError,'complete physical pin coverage'):r.validate('/unused')
            result['pinnedMaintenanceFloors']=3
            with patch.object(r.collection,'inventory',side_effect=[{},dict(changed=True)]):
                with self.assertRaisesRegex(ValueError,'maintenance original changed'):r.validate('/unused')

    def test_failed_prerequisite_never_counts_as_a_negative(self):
        for stage in ('network','content','control'):
            with patch.object(r.exports.network,'replay',side_effect=ValueError('network') if stage=='network' else None), \
                 patch.object(r.exports,'content',side_effect=ValueError('content') if stage=='content' else None), \
                 patch.object(r.exports,'controls',side_effect=ValueError('control') if stage=='control' else None), \
                 patch.object(r,'replay') as replay:
                with self.assertRaisesRegex(ValueError,'^'+stage+'$'):r.rejection_stage('/unused')
                replay.assert_not_called()

    def test_missing_mutation_or_physical_substitution_is_a_failure(self):
        inventory=dict(files={'original':'digest'},directories=[])
        for failure,after,reason in ((StopIteration(),inventory,'missing maintenance mutation target'),
                (None,dict(files={'original':'changed'},directories=[]),'negative changed physical inputs')):
            with patch.object(r,'validate',return_value={}),patch.object(r.collection,'inventory',side_effect=[inventory,after]), \
                 patch.object(r.shutil,'copytree'),patch.object(r,'mutate',side_effect=failure),patch.object(r,'rejection_stage') as stage:
                with self.assertRaisesRegex(ValueError,reason):r.qualify('/unused')
                stage.assert_not_called()

    def test_accepted_or_unrelated_negative_is_a_failure(self):
        inventory=dict(files={},directories=[])
        for failure,reason in ((None,'mutation accepted'),(ValueError('unrelated'),'unrelated maintenance negative')):
            def check():
                if failure:raise failure
            with patch.object(r,'validate',return_value={}),patch.object(r.collection,'inventory',return_value=inventory), \
                 patch.object(r.shutil,'copytree'),patch.object(r,'mutate'),patch.object(r,'rejection_stage',return_value=check):
                with self.assertRaisesRegex(ValueError,reason):r.qualify('/unused')


if __name__=='__main__':unittest.main()
