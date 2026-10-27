"""Original-first and explicit-profile boundaries for native context evidence."""
import unittest
from unittest.mock import patch
from . import owned_context_evidence as q
from . import owned_context_process_evidence as p


class OwnedContextEvidenceTest(unittest.TestCase):
    def test_invalid_original_profiles_stop_before_mutations(self):
        with patch.object(q,'validate',side_effect=ValueError('original failed')),patch.object(q.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'original failed'):q.qualify('missing')
            copied.assert_not_called()

    def test_invalid_original_processes_stop_before_mutations(self):
        with patch.object(p,'validate',side_effect=ValueError('original failed')),patch.object(p.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'original failed'):p.qualify('missing')
            copied.assert_not_called()

    def test_profile_cannot_substitute_size_source_or_pending_phase(self):
        for changes in (dict(size=4),dict(backup=True),dict(phase='ACCEPT')):
            original=dict(size=3,backup=False,phase='CERTIFICATE');original.update(changes)
            with self.subTest(changes=changes),patch.object(q.q,'clean',return_value=original),patch.object(q,'images') as image:
                with self.assertRaisesRegex(ValueError,'native context original profile'):q.profile('raw',3,False,'CERTIFICATE')
                image.assert_not_called()

    def test_image_semantics_run_only_after_complete_original_replay(self):
        original=dict(size=3,backup=False,phase='CERTIFICATE')
        with patch.object(q.q,'clean',return_value=original) as clean,patch.object(q,'images',side_effect=ValueError('wrong application')):
            with self.assertRaisesRegex(ValueError,'wrong application'):q.profile('raw',3,False,'CERTIFICATE')
            clean.assert_called_once_with('raw',2,selected_prefix=None)

    def test_unknown_predecessor_span_cannot_change_replay_scope(self):
        for value in (True,1,-1,3,None,'2'):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'prelude'):p.p.original('missing',value)


if __name__=='__main__':unittest.main()
