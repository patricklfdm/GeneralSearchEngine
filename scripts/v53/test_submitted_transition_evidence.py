from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import submitted_transition_evidence as e


class SubmittedTransitionEvidenceTest(unittest.TestCase):
    def test_invalid_original_cannot_count_as_negative_qualification(self):
        with patch.object(e,'validate',side_effect=ValueError('bad original')),patch.object(e.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^bad original$'):e.qualify(Path('/original'))
        copied.assert_not_called()

    def test_inventory_link_is_rejected_before_reading_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'events.json').symlink_to('/absent')
            with patch.object(e.a,'prelude') as prelude:
                with self.assertRaisesRegex(ValueError,'^submitted regular original inventory$'):e.validate(root)
            prelude.assert_not_called()

    def test_missing_joint_campaign_or_readiness_inside_transition_is_rejected(self):
        names=['INSTALLED','SLOT_BEGIN','SLOT_COMPLETE','BEFORE_READY','SLOT_BEGIN','SLOT_COMPLETE',
               'SLOT_BEGIN','SLOT_COMPLETE','INSTALLED','SLOT_BEGIN','SLOT_COMPLETE',
               'INSTALLED','SLOT_BEGIN','SLOT_COMPLETE','BEFORE_READY']
        missing=names.copy();missing.pop(8)
        early=names.copy();early.insert(11,early.pop())
        for wrong in (missing,early):
            with patch.object(e.d,'read',return_value=[dict(event='ROUND_'+v) for v in wrong]):
                with self.assertRaisesRegex(ValueError,'^submitted exact lifecycle$'):e.lifecycle(Path('/original'))

    def test_physical_history_precedes_lifecycle_validation(self):
        with patch.object(e,'layout'),patch.object(e.a,'prelude',side_effect=ValueError('bad physical')) as prelude,patch.object(e,'lifecycle') as lifecycle:
            with self.assertRaisesRegex(ValueError,'^bad physical$'):e.validate(Path('/original'))
        prelude.assert_called_once_with(Path('/original'),'READY');lifecycle.assert_not_called()

    def test_original_preparation_cannot_silently_accept_an_unknown_profile(self):
        with self.assertRaisesRegex(ValueError,'^transition preparation profile$'):e.a.prelude(Path('/original'),'OTHER')

    def test_original_source_anchor_conflict_is_not_deduplicated(self):
        slot=e.NativeSlot.__new__(e.NativeSlot);slot.voters=('node-1',);slot.first=None
        slot.group={'node-1':{'sources/a/source.gscp':b'a','sources/b/source.gscp':b'b'}}
        packets=[dict(capsule=dict(cut=dict(index=3,entry='a'),catalog='c',application='i')),
                 dict(capsule=dict(cut=dict(index=3,entry='b'),catalog='c',application='i'))]
        with patch.object(e.e.p,'decode',side_effect=packets):
            with self.assertRaisesRegex(ValueError,'^submitted conflicting retained source anchor$'):slot.required_anchors()


if __name__=='__main__':unittest.main()
