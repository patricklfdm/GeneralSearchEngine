"""Finite initialization projection tests; not a native process qualification."""
import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch
from . import joining_initialization_process_evidence as e


class JoiningInitializationEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.final={name:(str(i),('original-'+name).encode()) for i,name in enumerate(e.ACTIVE)}

    def test_all_declared_first_cuts_and_recovery_preserve_original_inodes(self):
        first=e.steps(self.final)
        self.assertEqual(list(e.run.POINTS),[point for point,_ in first])
        for cut,prefix in first:
            with self.subTest(cut=cut):
                original=dict(prefix);recovery=e.steps(self.final,initial=prefix)
                self.assertEqual(original,prefix);self.assertEqual(self.final,recovery[-1][1])
                for _,state in recovery:
                    for active,candidate in zip(e.ACTIVE,e.NEXT):
                        for name in (active,candidate):
                            if name in state:self.assertEqual(self.final[active][0],state[name][0])

    def test_created_and_partial_seed_must_complete_same_candidate(self):
        candidate=e.NEXT[0];key,data=self.final[e.ACTIVE[0]]
        for prefix,expected_first in ((b'','JOINING_RETENTION_SEED_PREFIX_WRITTEN'),
                                      (data[:len(data)//2],'JOINING_RETENTION_SEED_WRITTEN'),
                                      (data,'JOINING_RETENTION_SEED_WRITTEN')):
            replay=e.steps(self.final,initial={candidate:(key,prefix)})
            self.assertEqual(expected_first,replay[0][0])
            self.assertNotIn('JOINING_RETENTION_SEED_CREATED',[v[0] for v in replay])

    def test_written_and_renamed_seed_take_different_recovery_paths(self):
        key,data=self.final[e.ACTIVE[0]]
        candidate=e.steps(self.final,initial={e.NEXT[0]:(key,data)})
        active=e.steps(self.final,initial={e.ACTIVE[0]:(key,data)})
        self.assertEqual('JOINING_RETENTION_SEED_WRITTEN',candidate[0][0])
        self.assertEqual(['JOINING_RETENTION_SEED_RECOVERY_FORCED','JOINING_RETENTION_SEED_RECOVERY_PARENT_FORCED'],
                         [v[0] for v in active[:2]])

    def test_completed_resume_only_reseals_original_seed_and_done(self):
        replay=e.steps(self.final,initial=self.final)
        self.assertEqual(['JOINING_RETENTION_SEED_RECOVERY_FORCED','JOINING_RETENTION_SEED_RECOVERY_PARENT_FORCED',
                          'JOINING_RETENTION_DONE_RECOVERY_FORCED','JOINING_RETENTION_DONE_RECOVERY_PARENT_FORCED'],
                         [v[0] for v in replay])
        self.assertTrue(all(v[1]==self.final for v in replay))

    def test_changed_prefix_inode_overlap_and_unknown_files_are_rejected(self):
        active,candidate=e.ACTIVE[0],e.NEXT[0];key,data=self.final[active]
        for prefix in ({candidate:(key,b'wrong')},{candidate:('changed',data)},
                       {active:(key,data[:-1])},{active:(key,data),candidate:(key,b'')},
                       {'unrelated':(key,data)},{e.ACTIVE[1]:self.final[e.ACTIVE[1]]},
                       {e.ACTIVE[-1]:self.final[e.ACTIVE[-1]]}):
            with self.subTest(prefix=prefix),self.assertRaises(ValueError):e.steps(self.final,initial=prefix)
        duplicate=dict(self.final);duplicate[e.ACTIVE[1]]=(key,b'other')
        with self.assertRaisesRegex(ValueError,'inode alias'):e.steps(duplicate)

    def test_callback_filter_cannot_change_node_or_process_scope(self):
        def row(event,**kwargs):
            return dict(origin='halt',value=dict(kind='EVENT',value=dict(node='node-4',scope='initialization-halt',event=event,**kwargs)))
        trace=[row('CURRENT_FORCED'),row(e.run.POINTS[0]),dict(origin='parent',value={})]
        self.assertEqual([e.run.POINTS[0]],e.callbacks(trace,'halt','node-4'))
        for key,value in (('node','node-1'),('scope','initialization-resume')):
            bad=row(e.run.POINTS[0]);bad['value']['value'][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'callback owner'):e.callbacks([bad],'halt','node-4')

    def test_every_ledger_candidate_has_prefix_force_rename_order(self):
        history=e.steps(self.final)
        for i,(active,candidate,label) in enumerate(zip(e.ACTIVE,e.NEXT,e.LABELS)):
            rows=history[i*7:(i+1)*7];key,raw=self.final[active]
            self.assertEqual((key,b''),rows[0][1][candidate]);self.assertNotIn(active,rows[0][1])
            self.assertEqual((key,raw[:len(raw)//2]),rows[1][1][candidate])
            for at in (2,3,4):self.assertEqual((key,raw),rows[at][1][candidate])
            for at in (5,6):
                self.assertNotIn(candidate,rows[at][1]);self.assertEqual((key,raw),rows[at][1][active])

    def test_bad_original_cannot_be_counted_as_successful_negatives(self):
        with tempfile.TemporaryDirectory() as directory:
            raw=Path(directory);(raw/'original').write_bytes(b'original')
            with patch.object(e,'validate',side_effect=ValueError('invalid original')),patch.object(e,'mutate') as mutate:
                with self.assertRaisesRegex(ValueError,'invalid original'):e.negatives(raw,'unused')
                mutate.assert_not_called()

    def test_unrelated_negative_failure_does_not_qualify(self):
        with tempfile.TemporaryDirectory() as directory:
            raw=Path(directory);(raw/'original').write_bytes(b'original')
            with patch.object(e,'validate',side_effect=[{},ValueError('unrelated broken source')]),patch.object(e,'mutate'):
                with self.assertRaisesRegex(ValueError,'unrelated negative'):e.negatives(raw,'unused')
            self.assertEqual(b'original',(raw/'original').read_bytes())

    def test_negative_copies_are_separate_and_exact_rejections_leave_original_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            raw=Path(directory);(raw/'original').write_bytes(b'original');seen=[]
            def mutation(copied,case,name):
                self.assertNotEqual(raw,copied);self.assertEqual(b'original',(copied/'original').read_bytes())
                (copied/'original').write_bytes(name.encode());seen.append(name)
            def validation(path,case):
                if path==raw:return {}
                raise ValueError(e.NEGATIVES[(path/'original').read_text()])
            with patch.object(e,'validate',side_effect=validation),patch.object(e,'mutate',side_effect=mutation):
                result=e.negatives(raw,'unused')
            self.assertEqual(list(e.NEGATIVES),seen);self.assertEqual(9,len(result))
            self.assertEqual(b'original',(raw/'original').read_bytes())


if __name__=='__main__':unittest.main()
