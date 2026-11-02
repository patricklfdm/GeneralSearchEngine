"""Ordinary REMOVE shares durable ballot rules, not process-specific paths."""
from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from . import remove_ballot_evidence as m


def event(name,node='node-1'):return dict(node=node,event=name)


class RemoveBallotTest(unittest.TestCase):
    def test_ordinary_constructor_derives_initial_state_before_comparing_originals(self):
        base=SimpleNamespace(history=SimpleNamespace(old=('node-1','node-2','node-3','node-4')))
        with patch.object(m.e,'Replay',return_value=base),patch.object(m.preparation,'prelude',return_value=SimpleNamespace(group='derived')) as prelude, \
             patch.object(m.Replay,'initialize') as initialize:
            m.Replay('/raw','4-REMOVE')
        prelude.assert_called_once_with(Path('/raw'),'INTENT',size=4)
        initialize.assert_called_once_with(Path('/raw'),'4-REMOVE',base,'derived')

    def test_process_constructor_retains_original_prelude_and_history_directory(self):
        shared=m.shared;base=SimpleNamespace(history=SimpleNamespace(old=('node-1','node-2','node-3','node-4','node-5')))
        with patch.object(shared.prior.r.m.e,'Replay',return_value=base),patch.object(shared.p.a,'prelude',return_value=SimpleNamespace(group='derived')) as prelude, \
             patch.object(shared.Replay,'initialize') as initialize:
            shared.Replay('/raw',{'profile':'5-REMOVE'})
        prelude.assert_called_once_with(Path('/raw/history'),'INTENT',size=5)
        initialize.assert_called_once_with(Path('/raw/history'),{'profile':'5-REMOVE'},base,'derived')

    def test_each_profile_has_ordinary_activations_without_interrupted_process_prelude(self):
        for profile in m.PROFILES:
            r=m.Replay.__new__(m.Replay);r.profile=profile;r.history=SimpleNamespace(phases=['old','joint','new'],activations=Mock(side_effect=AssertionError('process-only')))
            self.assertEqual(['old','joint','new'],r.activation_phases());r.history.activations.assert_not_called()

    def test_actual_voters_and_ordinals_map_to_apply_and_publication_boundaries(self):
        r=m.Replay.__new__(m.Replay);r.events=[];r.history=object()
        points={(1,'node-5'):dict(APPLY_BEFORE_RETURN=10,PUBLICATION_BEFORE_RETURN=20),
                (3,'node-3'):dict(APPLY_BEFORE_RETURN=30,PUBLICATION_BEFORE_RETURN=40)}
        with patch.object(m.n.phase,'blocks',return_value=points):rows=r.snapshot_actions()
        self.assertEqual([(10,'original',('node-5','applied-5/node-5','applied-5/node-5')),
                          (20,'original',('node-5','published-5/node-5','published-5/node-5')),
                          (30,'original',('node-3','applied-7/node-3','applied-7/node-3')),
                          (40,'original',('node-3','published-7/node-3','published-7/node-3'))],rows)

    def test_snapshot_compares_allocator_and_promise_instead_of_resetting_them(self):
        r=m.Replay.__new__(m.Replay);r.root=Path('/raw');r.state=m.shared.b.State('a'*64);r.state.seed('node-5',3,4);r.promise_comparisons=0
        for counter,promise,reason in ((2,4,'continuous allocator'),(3,3,'REMOVE ballot continuous promise')):
            raw=m.f.encode('records','ALLOCATOR',dict(root='a'*64,node='node-5',counter=counter))
            with patch.object(m.c,'inventory',return_value={'allocator.gsr':raw}),patch.object(r,'promised',return_value=promise):
                with self.assertRaisesRegex(ValueError,reason):r.original('node-5','published-5/node-5','published')
        self.assertEqual({'node-5':3},r.state.counters);self.assertEqual({'node-5':4},r.state.observed)

    def test_ordinary_promises_reject_missing_reordered_duplicate_and_foreign_callbacks(self):
        original=[event(v) for v in m.shared.b.PROMISE]
        variants=[original[:-1],original[::-1],original+[original[-1]],[original[0],dict(original[1],node='node-5'),original[2]]]
        for rows in variants:
            r=m.Replay.__new__(m.Replay);r.events=rows;r.promise_points=set()
            with self.assertRaisesRegex(ValueError,'^REMOVE ballot promise force order$'):r.promise('node-1',-1,len(rows),dict(counter=4),[])

    def test_captured_retirement_is_mandatory_before_ballot_or_negatives(self):
        with patch.object(m.n.collection,'inventory',return_value={}),patch.object(m.prior,'validate',side_effect=ValueError('missing captured bytes')), \
             patch.object(m,'replay') as replay,patch.object(m,'ProcessPoolExecutor') as workers:
            with self.assertRaisesRegex(ValueError,'^missing captured bytes$'):m.qualify('/raw','/captures','4-REMOVE')
            replay.assert_not_called();workers.assert_not_called()

    def test_invalid_profile_fails_before_replay(self):
        for profile in ('3-REMOVE','4-ADD','5-remove'):
            with patch.object(m.e,'Replay') as base,self.assertRaisesRegex(ValueError,'^REMOVE ballot profile$'):m.Replay('/raw',profile)
            base.assert_not_called()

    def test_original_and_capture_changes_are_both_detected(self):
        for inventories in ([{}, {}, {'changed':True}], [{},{},{},{'changed':True}]):
            with patch.object(m.n.collection,'inventory',side_effect=inventories),patch.object(m.prior,'validate'),patch.object(m,'replay',return_value={}):
                with self.assertRaisesRegex(ValueError,'^REMOVE ballot original changed$'):m.validate('/raw','/captures','5-REMOVE')

    def test_result_does_not_claim_process_death_or_final_source_full_cohort(self):
        with patch.object(m.n.collection,'inventory',return_value={}),patch.object(m.prior,'validate',return_value={'transientRetirementBytesQualified':True}), \
             patch.object(m,'replay',return_value=dict(status='PARTIAL',ballotForceCompositionQualified=True,phase3Complete=False)):
            value=m.validate('/raw','/captures','5-REMOVE')
        self.assertTrue(value['ballotForceCompositionQualified']);self.assertTrue(value['precondition']['transientRetirementBytesQualified'])
        for key in ('phase3Complete','processDeathQualified','allMembershipProfilesQualified','currentSourceNativeCohortQualified','originalObservationCoverageComplete'):self.assertIs(False,value[key])

    def test_mutations_use_actual_proposer_and_preserve_non_ballot_observations(self):
        points=['CURRENT_DIRECTORY_FORCED',*m.shared.b.WRITES,'CURRENT_BEFORE_CAPTURE',*m.shared.b.PROMISE,'GRANT_BEFORE_RETURN']
        original=[event(v,'node-4') for v in points]
        for name in m.NEGATIVES:
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);(root/'events.json').write_bytes(m.f.canonical(original));m.mutate(root,'5-REMOVE',name)
                changed=json.loads((root/'events.json').read_bytes())
                self.assertNotEqual(original,changed)
                self.assertEqual([v for v in original if not m.shared.relevant(v)],[v for v in changed if not m.shared.relevant(v)])

    def negative(self,*,change=None,precondition=None,error=None,accepted=False,missing=False):
        before=dict(files={'events.json':'event','wire.json':'wire','physical':'physical'},directories=['empty']);after=copy.deepcopy(before)
        rows=[event('CURRENT_VALIDATED')];altered=copy.deepcopy(rows)
        if change=='wire':after['files']['wire.json']='changed'
        elif change=='physical':after['files']['physical']='changed'
        elif change=='directory':after['directories']=[]
        elif change=='event':altered[0]['event']='CURRENT_FILES_FORCED'
        with patch.object(m.shutil,'copytree'),patch.object(m,'mutate',side_effect=StopIteration if missing else None), \
             patch.object(m.n.collection,'inventory',return_value=after),patch.object(m.n.collection,'read_json',side_effect=[rows,altered]), \
             patch.object(m.r,'replay',side_effect=precondition),patch.object(m,'replay',side_effect=None if accepted else ValueError(error or m.NEGATIVES['force-missing'])):
            return m.negative('/raw','4-REMOVE',before,'force-missing')

    def test_negatives_keep_original_files_wire_directories_and_other_observations(self):
        for kind in ('wire','physical','directory','event'):
            with self.assertRaisesRegex(ValueError,'negative changed'):self.negative(change=kind)

    def test_negative_retirement_failure_missing_target_or_unrelated_error_cannot_pass(self):
        for args,reason in ((dict(precondition=ValueError('bad retirement')),'bad retirement'),(dict(missing=True),'missing negative target'),
                            (dict(error='another failure'),'unrelated ballot negative'),(dict(accepted=True),'mutation accepted')):
            with self.assertRaisesRegex(ValueError,reason):self.negative(**args)
        value=self.negative();self.assertEqual('REJECTED',value['status']);self.assertEqual('PASS',value['retirementReplay'])

    def test_worker_bounds_and_exact_declared_results(self):
        for workers in (0,5,True,1.2):
            with patch.object(m,'validate') as validate,self.assertRaisesRegex(ValueError,'^REMOVE ballot replay workers$'):m.qualify('/raw','/captures','4-REMOVE',workers=workers)
            validate.assert_not_called()
        with patch.object(m,'validate',return_value={}),patch.object(m.n.collection,'inventory',return_value={}), \
             patch.object(m,'ProcessPoolExecutor',ThreadPoolExecutor),patch.object(m,'negative',side_effect=lambda root,profile,before,name:dict(case=name,status='REJECTED')):
            result=m.qualify('/raw','/captures','5-REMOVE',workers=2)
        self.assertEqual(sorted(m.NEGATIVES),[v['case'] for v in result['negatives']]);self.assertFalse(result['mutatedFullPrerequisiteReplayed'])

    def test_failed_workers_and_changed_captures_block_acceptance(self):
        with patch.object(m,'validate',return_value={}),patch.object(m.n.collection,'inventory',return_value={}), \
             patch.object(m,'ProcessPoolExecutor',ThreadPoolExecutor),patch.object(m,'negative',side_effect=ValueError('failed target')):
            with self.assertRaisesRegex(ValueError,'^REMOVE ballot negative matrix failed$'):m.qualify('/raw','/captures','4-REMOVE')
        with patch.object(m,'validate',return_value={}),patch.object(m.n.collection,'inventory',side_effect=[{},{},{},{'changed':True}]), \
             patch.object(m,'ProcessPoolExecutor',ThreadPoolExecutor),patch.object(m,'negative',return_value={'status':'REJECTED'}):
            with self.assertRaisesRegex(ValueError,'^REMOVE ballot qualification changed original$'):m.qualify('/raw','/captures','5-REMOVE')


if __name__=='__main__':unittest.main()
