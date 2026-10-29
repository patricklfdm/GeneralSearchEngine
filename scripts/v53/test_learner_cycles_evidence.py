"""Small replay contracts; synthetic inputs do not establish native acceptance."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import learner_cycles_evidence as e
from . import learner_cycle_forces as forces
from . import learner_cycle_bytes as states


class LearnerCyclesEvidenceTest(unittest.TestCase):
    def test_invalid_original_never_counts_as_successful_negatives(self):
        with patch.object(e,'validate',side_effect=ValueError('invalid original')),patch.object(e.shutil,'copytree') as copytree:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):e.qualify('/absent')
        copytree.assert_not_called()

    def test_extra_linked_and_hardlinked_evidence_stop_before_physical_replay(self):
        for kind,reason in [('extra','context selection learner cycles inventory'),('link','learner cycles regular bounded inventory'),('hardlink','learner cycles file capacity')]:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as temp,patch.object(e,'physical') as physical:
                root=Path(temp)/'raw';root.mkdir();outside=Path(temp)/'original';outside.write_bytes(b'original')
                if kind=='extra':(root/'extra').write_bytes(b'bad')
                elif kind=='link':(root/'extra').symlink_to(outside)
                else:(root/'extra').hardlink_to(outside)
                with self.assertRaisesRegex(ValueError,'^'+reason+'$'):e.validate(root)
                physical.assert_not_called()

    def test_native_reduction_failure_stops_copies_and_claims(self):
        with patch.object(e,'inventory'),patch.object(e,'physical',side_effect=ValueError('wrong physical history')),patch.object(e,'replay_snapshots') as replay:
            with self.assertRaisesRegex(ValueError,'^wrong physical history$'):e.validate('/absent')
        replay.assert_not_called()

    def test_unrelated_mutation_failure_is_not_counted_as_expected_rejection(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(e,'validate',side_effect=[{'status':'PASS'},ValueError('unrelated')]),patch.object(e,'mutate'):
            with self.assertRaisesRegex(ValueError,'^learner cycles unrelated negative: extra-file: unrelated$'):e.qualify(temp)

    def test_acquisition_partition_preserves_four_whole_distinct_sessions_per_revision(self):
        rows=[dict(request=str(i),response='reply') for i in range(24) for _ in range(1+i%3)]
        with patch.object(e.t.source.t.t,'wire',side_effect=lambda value:('ignored',dict(trace=value))):
            ranges=e.acquisitions(rows)
            self.assertEqual(6,len(ranges));self.assertEqual(0,ranges[0][0]);self.assertEqual(len(rows),ranges[-1][1])
            for index,(start,end) in enumerate(ranges):self.assertEqual({str(v) for v in range(index*4,index*4+4)},{v['request'] for v in rows[start:end]})
            for changed in (rows[:-3],rows+[rows[0]]):
                with self.assertRaises(ValueError):e.acquisitions(changed)
            duplicate=copy.deepcopy(rows);duplicate[-1]['request']='0'
            with self.assertRaisesRegex(ValueError,'^learner cycles reused trace$'):e.acquisitions(duplicate)

    def positions(self):
        return {name:dict(events=i+1,exchanges=i+1) for i,name in enumerate(e.STAGES)}

    def test_exact_stage_set_integer_monotonicity_and_full_consumption(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);positions=self.positions();events=['force']*len(e.STAGES);wire=[{}]*len(e.STAGES)
            (root/'current-head-events.json').write_bytes(e.f.canonical(events))
            def check(value):
                (root/'current-head-stages.json').write_bytes(e.f.canonical(value));return e.boundaries(root,wire)
            self.assertEqual((events,positions),check(positions))
            for mode in ('missing','extra','bool','decreasing','unconsumed'):
                value=copy.deepcopy(positions)
                if mode=='missing':value.pop(e.STAGES[0])
                elif mode=='extra':value['invented']=dict(events=0,exchanges=0)
                elif mode=='bool':value[e.STAGES[0]]['events']=True
                elif mode=='decreasing':value[e.STAGES[-1]]['events']=0
                else:value[e.STAGES[-1]]['events']-=1
                with self.subTest(mode=mode),self.assertRaises(ValueError):check(value)

    def trace_fixture(self):
        originals={i:{'source.gscp':b'packet','generation.gsr':b'generation','a.image':b'image'} for i in range(1,7)}
        files={'initial-typed':dict.fromkeys(['.','preparation.lock','preparation.json','learner.gsr','prepared.json','backup','backup/a','backup/b','backup/c']),
               'seed-typed':dict.fromkeys(['.','preparation.lock','preparation.json','learner.gsr','backup','backup/a','backup/b','backup/c'])}
        snapshots={'before-seed-handoff':states.s.Snapshot({},files,{})}
        intervals=forces.expected(originals,snapshots);events=[];positions={}
        for name,trace in intervals.items():events.extend(trace);positions[name]=dict(events=len(events))
        return originals,snapshots,intervals,events,positions

    def test_each_force_interval_rejects_missing_extra_or_reordered_events(self):
        originals,snapshots,intervals,events,positions=self.trace_fixture()
        self.assertEqual(tuple(intervals),e.STAGES);forces.validate(events,positions,originals,snapshots)
        start=0
        for stage,trace in intervals.items():
            for mode in ('missing','extra','reordered'):
                mutated=list(events);offsets=copy.deepcopy(positions)
                if mode=='reordered':mutated[start],mutated[start+1]=mutated[start+1],mutated[start]
                else:
                    if mode=='missing':mutated.pop(start)
                    else:mutated.insert(start,'UNACCOUNTED_EVENT')
                    for value in offsets.values():
                        if value['events']>start:value['events']+=-1 if mode=='missing' else 1
                with self.subTest(stage=stage,mode=mode),self.assertRaisesRegex(ValueError,'^learner cycles exact force interval: '+stage+'$'):
                    forces.validate(mutated,offsets,originals,snapshots)
            start+=len(trace)

    def test_replacement_marker_deletion_and_parent_force_precede_new_source(self):
        original={'source.gscp':b'packet','generation.gsr':b'generation'}
        for sequence in (3,4):
            trace=forces.install(original,sequence)
            self.assertLess(trace.index('LEARNER_SLOT_ACTIVE_PARENT_FORCED'),trace.index('LEARNER_SLOT_OLD_INSTALL_DELETED'))
            self.assertLess(trace.index('LEARNER_SLOT_OLD_INSTALL_DELETED'),trace.index('LEARNER_SLOT_OLD_INSTALL_PARENT_FORCED'))
            self.assertLess(trace.index('LEARNER_SLOT_OLD_INSTALL_PARENT_FORCED'),trace.index('LEARNER_SLOT_SOURCE_MOVED'))
        self.assertNotIn('LEARNER_SLOT_OLD_INSTALL_DELETED',forces.install(original,2))

    def test_retirement_release_follows_covering_head_deletes_and_clear_forces(self):
        trace=forces.retire(3)
        self.assertEqual('LEARNER_SLOT_HEAD_ACTIVE_FORCED',trace[0])
        self.assertEqual(3,trace.count('LEARNER_SLOT_RETIRE_MEMBER_DELETED'))
        self.assertEqual(['LEARNER_SLOT_CLEAR_ACTIVE_FORCED','LEARNER_SLOT_CLEAR_ACTIVE_PARENT_FORCED','LEARNER_SLOT_RETIRE_RELEASED'],trace[-3:])
        resumed=forces.retire(3,resume=True)
        self.assertNotIn('LEARNER_SLOT_RETIRE_MEMBER_DELETED',resumed)
        self.assertNotIn('LEARNER_SLOT_CLEAR_RENAMED',resumed)

    def test_cold_retirement_reseals_current_authority_without_rewriting_admission(self):
        trace=forces.reopen(3)
        self.assertEqual(['LEARNER_REPLICA_LOCKED','LEARNER_SLOT_HEAD_ACTIVE_FORCED','LEARNER_SLOT_HEAD_ACTIVE_PARENT_FORCED'],trace[:3])
        self.assertNotIn('LEARNER_ACTIVE_PLAN_FORCED',trace)
        self.assertNotIn('LEARNER_RETENTION_ACTIVE_FORCED',trace)
        self.assertNotIn('LEARNER_SOURCE_MOVED',trace)

    def test_record_canonical_shape_and_capacity(self):
        self.assertEqual({'original':True},states.record(b'{"original":true}'))
        for raw in (None,b'',b'[]',b'{"original": true}',b'{"a":1,"a":1}'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):states.record(raw)
        with self.assertRaises(ValueError):states.record(b'{"original":true}',4)

    def state_fixture(self):
        roots={name:{} for name in states.s.ROOTS};roots['operation']={'.':None,'record':b'original'}
        ids={name:dict(path='/recorded-original/'+name,present=bool(files),members={k:dict(key=name+':'+k) for k in files}) for name,files in roots.items()}
        snapshot=states.s.Snapshot(ids,roots,dict(counts=dict(GENERATION=1,APPLICATION=2)))
        model=states.States({}, {}, {}, {}, b'', {});model.check(snapshot,roots,1,2)
        return snapshot,model

    def test_equal_bytes_cannot_replace_original_inode_or_move_original_path(self):
        for mode in ('inode','path'):
            original,model=self.state_fixture();changed=copy.deepcopy(original)
            if mode=='inode':changed.identities['operation']['members']['record']['key']='replacement'
            else:changed.identities['operation']['path']='/different/operation'
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'^learner cycles '+('unchanged original identity' if mode=='inode' else 'fixed root paths')+'$'):
                model.reopened(changed)

    def test_recreated_removed_members_and_unreleased_generations_are_rejected(self):
        for mode in ('member','generation','learner'):
            original,model=self.state_fixture();changed=copy.deepcopy(original)
            if mode=='member':changed.files['seed']['removed-source']=b'stale'
            elif mode=='generation':changed.resources['counts']['GENERATION']=2
            else:changed.resources['counts']['LEARNER']=1
            with self.subTest(mode=mode),self.assertRaises(ValueError):model.reopened(changed)

    def test_fingerprints_use_recorded_identity_with_source_relative_paths(self):
        original,model=self.state_fixture();original.identities['operation']['members'].update({'source':dict(key='dir'),'source/a':dict(key='file')})
        actual=states.fingerprint(original,'operation','source')
        self.assertEqual([dict(path='.',sha256=states.s.digest(e.f.canonical(dict(key='dir')))),dict(path='a',sha256=states.s.digest(e.f.canonical(dict(key='file'))))],actual)
        with self.assertRaisesRegex(ValueError,'^learner cycles fingerprint inventory$'):states.fingerprint(original,'operation',names={'missing'})


if __name__=='__main__':unittest.main()
