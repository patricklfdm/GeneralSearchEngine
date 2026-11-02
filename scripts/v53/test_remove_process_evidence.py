"""Fail-closed original-first reader boundaries; native history is retained separately."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import remove_process_evidence as r
from . import test_remove_retirement_evidence as generation_fixture
from . import test_joining_retirement_replay as source_fixture


class RemoveProcessEvidenceTest(unittest.TestCase):
    def test_all_declared_cases_remain_distinct_exact_profiles(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for case in r.run.CASES:
                original=r.run.selected(case);(root/'profile.json').write_bytes(r.f.canonical(original))
                self.assertEqual(original,r.profile_at(root))

    def test_invalid_profile_cannot_substitute_other_boundaries(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);original=r.run.selected(r.run.CASES[0])
            for change in ({'index':True},{'index':6},{'profile':'3-REMOVE'},{'schema':'other'},
                           {'mode':'resume'},{'point':'RETIREMENT_FILE_DELETED@2'},{'retry':True}):
                (root/'profile.json').write_bytes(r.f.canonical(dict(original,**change)))
                with self.subTest(change=change),self.assertRaises(ValueError):r.profile_at(root)

    def test_linked_or_oversized_profile_is_not_read(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path=root/'profile.json';path.symlink_to('/no-external-evidence')
            with self.assertRaisesRegex(ValueError,'^REMOVE process regular profile$'):r.profile_at(root)
            path.unlink();path.write_bytes(b' '*4097)
            with self.assertRaisesRegex(ValueError,'^REMOVE process regular profile$'):r.profile_at(root)

    def test_original_failure_precedes_mutations_and_process_claims(self):
        with patch.object(r,'validate',side_effect=ValueError('original differs')),patch.object(r,'ProcessPoolExecutor') as pool:
            with self.assertRaisesRegex(ValueError,'^original differs$'):r.qualify('/original')
        pool.assert_not_called()
        with patch.object(r.run.h,'inventory',return_value={}),patch.object(r,'profile_at',return_value={}),\
             patch.object(r,'layout'),patch.object(r.d,'read',return_value=[]),\
             patch.object(r,'physical',side_effect=ValueError('physical differs')),patch.object(r,'lifecycle') as lifetime:
            with self.assertRaisesRegex(ValueError,'^physical differs$'):r.validate('/original')
        lifetime.assert_not_called()

    def test_original_inventory_change_is_rejected(self):
        with patch.object(r.run.h,'inventory',side_effect=[{'a':'before'},{'a':'after'}]),\
             patch.object(r,'profile_at',return_value={}),patch.object(r,'layout'),\
             patch.object(r.d,'read',return_value=[]),patch.object(r,'physical',return_value={}),patch.object(r,'lifecycle'):
            with self.assertRaisesRegex(ValueError,'^REMOVE process original changed$'):r.validate('/original')

    def test_mutation_requires_its_exact_error_not_any_failure(self):
        for error,reason in ((ValueError('other'),'unrelated negative'),(None,'mutation accepted')):
            with patch.object(r.shutil,'copytree'),patch.object(r,'mutate'),patch.object(r,'validate',side_effect=error),\
                 self.assertRaisesRegex(ValueError,'^REMOVE process '+reason):r.negative('/original','wrong-exit')
        with patch.object(r.shutil,'copytree'),patch.object(r,'mutate'),\
             patch.object(r,'validate',side_effect=ValueError(r.NEGATIVES['wrong-exit'])):
            self.assertEqual('REJECTED',r.negative('/original','wrong-exit')['status'])

    def test_worker_limit_refuses_before_reading_original(self):
        for workers in (0,5,True,1.1,'2'):
            with patch.object(r,'validate') as original,self.assertRaisesRegex(ValueError,'^REMOVE process replay workers$'):
                r.qualify('/original',workers=workers)
            original.assert_not_called()

    def test_first_file_callback_cannot_select_a_later_matching_prefix(self):
        rows=[('START',{}),('DELETE',{'first':True}),('DELETE',{'second':True})]
        self.assertEqual(1,r.prefix_at(rows,'DELETE'))
        with self.assertRaisesRegex(ValueError,'^REMOVE process reachable original retirement cut$'):r.prefix_at(rows,'ABSENT')

    def test_capacity_counts_physical_copies_not_unique_image_hashes(self):
        state={f'floor-copies/{i}/same.image':dict(bytes=10,sha256='a'*64) for i in range(7)}
        r.capacity(state);state['retirement/source/same.image']=dict(bytes=10,sha256='a'*64)
        with self.assertRaisesRegex(ValueError,'^REMOVE process unchanged physical capacity$'):r.capacity(state)

    def test_early_borrow_prefix_already_owns_one_source_reservation(self):
        state={f'sources/{i}':dict(directory=True) for i in range(3)}
        state.update({f'floor-copies/{i}':dict(directory=True) for i in range(3)})
        r.capacity(state);state[r.retirement.images.BINDING]=dict(bytes=1,sha256='a'*64)
        with self.assertRaisesRegex(ValueError,'^REMOVE process unchanged physical capacity$'):r.capacity(state)
        del state['sources/2'];state['retirement/source']=dict(directory=True);r.capacity(state)

    def test_generation_projection_recovers_every_prefix_with_original_protected_bytes(self):
        fixture=generation_fixture.RemoveRetirementEvidenceTest()
        for count in (6,7):
            after,steps,_=fixture.generation(count)
            for point,state in steps:
                with self.subTest(count=count,point=point):
                    recovered,replay,_=fixture.generation(count,recover=state)
                    self.assertEqual(after,recovered)
                    self.assertEqual(r.retirement.physical(after),replay[-1][1] if replay else state)

    def test_all_six_source_cuts_recover_only_old_source_and_keep_latest_grant(self):
        files,identifier,current,coverage,_,kept=source_fixture.JoiningRetirementReplayTest().decision_inputs()
        for point in r.run.POINTS:
            if point.startswith('RETIREMENT_'):continue
            with self.subTest(point=point),patch.object(r.c,'current',return_value=current):
                prefix,recovered,replay,steps=r.source_interruption(files,point,coverage)
                self.assertEqual(point,steps[-1][0]);self.assertEqual(kept,recovered['grants.gsr'])
                self.assertNotIn('sources/'+identifier,recovered)
                self.assertEqual(files['selector.gsr'],recovered['selector.gsr'])
                self.assertEqual(files['floor-copies/floor.gsr'],recovered['floor-copies/floor.gsr'])
                self.assertEqual(r.retirement.physical(recovered),replay[-1][1] if replay else prefix)
                self.assertEqual(point=='SOURCE_RETIREMENT_CLEARED',not replay)

    def test_source_recovery_cannot_invent_floor_coverage(self):
        files,_,current,_,_,_=source_fixture.JoiningRetirementReplayTest().decision_inputs()
        with patch.object(r.c,'current',return_value=current),self.assertRaisesRegex(ValueError,'REMOVE retirement old source ballot|governing source coverage'):
            r.source_interruption(files,'SOURCE_RETIREMENT_WRITTEN',{})


if __name__=='__main__':unittest.main()
