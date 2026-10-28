from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import transition_process_evidence as e


class TransitionProcessEvidenceTest(unittest.TestCase):
    def test_distinct_workers_and_exact_lock_outcome(self):
        for mode in ('halt','kill'):
            profile=dict(mode=mode,index=5,point='PUBLICATION_SELECTOR_FORCED')
            original=dict(profile,parentPid=1,childPid=2,resumePid=3,exit=23 if mode=='halt' else 137,
                          resumeExit=0,publicReady=False,liveLockRefused=mode=='kill')
            e.process_outcome(original,profile)
            for changed in ({'resumePid':2},{'childPid':True},{'resumeExit':False},{'exit':0},
                            {'liveLockRefused':not original['liveLockRefused']},{'liveLockRefused':1},{'publicReady':True}):
                with self.subTest(mode=mode,changed=changed):
                    with self.assertRaisesRegex(ValueError,'^transition process distinct original workers$'):
                        e.process_outcome(dict(original,**changed),profile)

    def test_profile_does_not_silently_select_another_cut(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);original=dict(mode='halt',index=5,point='PUBLICATION_SELECTOR_FORCED')
            for changed in ({'mode':'resume'},{'index':7},{'index':True},{'point':'AFTER_READY'},{'allowRetry':True}):
                (root/'profile.json').write_bytes(e.f.canonical(dict(original,**changed)))
                with self.assertRaisesRegex(ValueError,'^transition process profile$'):e.profile_at(root)

    def test_trace_rejects_duplicate_fields_and_unlabelled_success(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'stdout'
            for line in ('STORE {"event":"PROMISE_FORCED","event":"PUBLICATION_SELECTOR_FORCED","index":5}\n',
                         'SUCCESS all\n','ROUND {"event":"INSTALLED","record":"","publicReady":true}\n'):
                path.write_text(line)
                with self.assertRaises(ValueError):e.trace(path)

    def test_invalid_original_never_counts_as_negative_rejection(self):
        with patch.object(e,'validate',side_effect=ValueError('bad original')),patch.object(e.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^bad original$'):e.qualify(Path('/original'))
        copied.assert_not_called()

    def test_physical_projection_precedes_lifecycle_claim(self):
        with patch.object(e,'profile_at',return_value={}),patch.object(e,'layout'),\
             patch.object(e,'physical',side_effect=ValueError('original prefix differs')),patch.object(e,'lifecycle') as lifetime:
            with self.assertRaisesRegex(ValueError,'^original prefix differs$'):e.validate(Path('/original'))
        lifetime.assert_not_called()

    def test_linked_profile_refuses_without_reading_external_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'profile.json').symlink_to('/not-authorized-evidence')
            with patch.object(e.d,'read') as read:
                with self.assertRaisesRegex(ValueError,'^transition process regular profile$'):e.profile_at(root)
            read.assert_not_called()


if __name__=='__main__':unittest.main()
