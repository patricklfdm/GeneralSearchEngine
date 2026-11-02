"""Scoped floor continuity and original-first negative qualification guards."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import remove_process_maintenance as r


class RemoveProcessMaintenanceTest(unittest.TestCase):
    def test_reuse_ignores_observation_location_but_requires_all_original_generation_bytes(self):
        original=dict(node='node-1',identity=dict(storage='id'),manifest=b'm',members={'source.gscp':b'p'},packet=dict(root='r'),start=0,end=10,path='old')
        reopened=dict(original,start=11,end=20,path='reopened')
        self.assertTrue(r.same_generation(original,reopened))
        for key,value in [('node','node-2'),('identity',dict(storage='other')),('manifest',b'other'),('members',{}),('packet',dict(root='other'))]:
            with self.subTest(key=key):self.assertFalse(r.same_generation(original,dict(reopened,**{key:value})))

    def test_retained_floor_requires_complete_equal_bytes_in_both_original_snapshots(self):
        reader=r.Replay.__new__(r.Replay);reader.root=Path('/original');reader.files=lambda _:{}
        own=dict(node='node-1');copies={'node-1':own};expected={'floor-copies':None,'floor-copies/proposal.gsr':b'p','floor-copies/floor.gsr':b'p','floor-copies/id/member':b'm'}
        for interrupted,reopened in [(expected,expected),(dict(expected,**{'floor-copies/id/member':b'x'}),expected),(expected,{}),(expected,dict(expected,**{'floor-copies/extra':b'x'}))]:
            with patch.object(r.originals,'governing',return_value=expected),patch.object(r.c,'inventory',side_effect=[interrupted,reopened]):
                if interrupted==reopened==expected:self.assertEqual(expected,reader.retained(copies,own))
                else:
                    with self.assertRaisesRegex(ValueError,'exact retained floor across death'):reader.retained(copies,own)

    def test_omitting_every_floor_cannot_qualify_a_recovered_history(self):
        reader=r.Replay.__new__(r.Replay);reader.events=[];reader.live=[(0,1),(2,3)];reader.process_root=Path('/original');reader.profile={}
        with patch.object(r.p,'physical',return_value=dict(retirement={})),self.assertRaisesRegex(ValueError,'original retained floor was not consumed'):
            reader.floors()

    def test_unknown_floor_owner_or_claimed_scope_refuses_before_replay(self):
        for row in [dict(node='unknown',event='FLOOR_COPY_BEFORE_RETURN'),dict(node='node-1',event='FLOOR_COPY_BEFORE_RETURN',scope='borrowed')]:
            reader=r.Replay.__new__(r.Replay);reader.events=[row];reader.history=SimpleNamespace(old=('node-1',))
            with patch.object(r.p,'physical') as physical,self.assertRaisesRegex(ValueError,'^REMOVE process floor observation shape$'):reader.floors()
            physical.assert_not_called()

    def test_release_size_is_derived_from_original_members_not_declared_counts(self):
        copies={'node-1':dict(node='node-1',manifest=b'a',members={'one':b'1','two.image':b'2'}),
                'node-2':dict(node='node-2',manifest=b'b',members={'one':b'1'})}
        points=r.m.floor_events(copies,'node-1',True)
        self.assertEqual(5,points.count('FLOOR_RELEASE_FILE_DELETED'))
        self.assertEqual(2,points.count('FLOOR_RELEASE_COPY_DELETED'))
        self.assertLess(points.index('FLOOR_COPIES_FORCED'),points.index('FLOOR_AUTHORITY_FORCED'))
        self.assertLess(points.index('FLOOR_RELEASE_AUTHORITY_FORCED'),points.index('FLOOR_RELEASE_RELINQUISHED'))

    def test_failed_export_precondition_prevents_maintenance_claim(self):
        with patch.object(r.p.run.h,'inventory',return_value={}),patch.object(r.e,'validate',side_effect=ValueError('bad export')),patch.object(r,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'^bad export$'):r.validate('/original')
        replay.assert_not_called()

    def test_original_failure_prevents_any_mutation(self):
        with patch.object(r,'validate',side_effect=ValueError('bad original')),patch.object(r,'ProcessPoolExecutor') as pool:
            with self.assertRaisesRegex(ValueError,'^bad original$'):r.qualify('/original')
        pool.assert_not_called()

    def test_worker_bound_precedes_original_read(self):
        for count in (0,5,True,1.2):
            with patch.object(r,'validate') as validate,self.assertRaisesRegex(ValueError,'maintenance replay workers'):r.qualify('/original',workers=count)
            validate.assert_not_called()

    def test_changed_physical_copy_bad_export_or_wrong_error_never_counts_as_negative(self):
        before=dict(files={'owner/selector':'a'},directories=[])
        for after,export_error,maintenance_error,reason in (
            (dict(files={'owner/selector':'b'},directories=[]),None,None,'negative changed physical inputs'),
            (before,ValueError('bad export'),None,'bad export'),
            (before,None,ValueError('unrelated'),'unrelated maintenance negative'),
            (before,None,None,'mutation accepted')):
            with patch.object(r.shutil,'copytree'),patch.object(r,'mutate'),patch.object(r.p.run.h,'inventory',return_value=after),\
                 patch.object(r.e,'validate',side_effect=export_error),patch.object(r,'replay',side_effect=maintenance_error):
                with self.assertRaisesRegex(ValueError,reason):r.negative('/original',{},before,'manifest-force')


if __name__=='__main__':unittest.main()
