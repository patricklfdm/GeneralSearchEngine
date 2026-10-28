import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import departing_publication_evidence as e


class DepartingPublicationEvidenceTest(unittest.TestCase):
    def test_invalid_original_is_not_a_successful_mutation(self):
        with patch.object(e,'validate',side_effect=ValueError('invalid original')),patch.object(e.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):e.qualify(Path('/original'))
        copied.assert_not_called()

    def test_scope_cannot_claim_public_service_or_a_different_removed_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for profile,fields in e.PROFILES.items():
                original=dict(status='PASS',profile=profile,publicReady=False,**fields)
                for changed in ({'publicReady':True},{'removed':'node-3'},{'activations':4},{'phase3Complete':True}):
                    (root/'departure-result.json').write_text(json.dumps(dict(original,**changed)))
                    with self.assertRaisesRegex(ValueError,'^departure scope$'):e.scope(root)

    def test_proposer_cannot_enter_ready_after_removal(self):
        result=dict(e.PROFILES['removed-proposer'])
        rows=[dict(event='ROUND_'+v) for v in ['INSTALLED','SLOT_BEGIN','SLOT_COMPLETE','BEFORE_READY']]
        with patch.object(e.d,'read',return_value=rows):
            with self.assertRaisesRegex(ValueError,'^departure exact round lifecycle$'):e.lifecycle(Path('/original'),result)

    def test_survivor_cannot_skip_fresh_activation_and_barrier(self):
        result=dict(e.PROFILES['removed-follower'])
        rows=[dict(event='ROUND_'+v) for v in ['INSTALLED','SLOT_BEGIN','SLOT_COMPLETE','BEFORE_READY']]
        with patch.object(e.d,'read',return_value=rows):
            with self.assertRaisesRegex(ValueError,'^departure exact round lifecycle$'):e.lifecycle(Path('/original'),result)

    def test_symlink_is_rejected_before_any_scope_or_original_read(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'departure-result.json').symlink_to('/missing')
            with patch.object(e,'scope') as scope:
                with self.assertRaisesRegex(ValueError,'^departure regular original inventory$'):e.validate(root)
            scope.assert_not_called()

    def test_missing_original_proposer_fails_before_source_observation(self):
        with self.assertRaisesRegex(ValueError,'^selected retention original proposer absent$'):
            e.d.s.campaign(Path('/absent'),{},3,'installed',proposer='node-4')


if __name__=='__main__':unittest.main()
