from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_carried_storage_coverage as m
from . import storage_coverage_component as component
from . import campaign_storage_coverage as campaign


class NativeCarriedStorageCoverageTest(unittest.TestCase):
    def test_missing_family_or_duplicate_callback_cannot_shrink_coverage(self):
        events=[dict(node='node-1',event=p) for p in ('REPLAY_RESERVED','RETENTION_BEFORE_WRITE','ACCEPT_VALIDATED')]
        rows=[dict(life=2,eventIndex=i) for i in range(3)]
        m.complete_callbacks(rows,events,2)
        for changed in (rows[:-1],[*rows,rows[0]]):
            with self.assertRaisesRegex(ValueError,'^storage coverage complete family callbacks: all-seven$'):
                m.complete_callbacks(changed,events,2)

    def test_generation_callbacks_outside_selected_or_publication_scope_are_not_invented(self):
        # CURRENT opening by itself is not a publication transaction.
        m.complete_callbacks([], [dict(node='node-1',event='CURRENT_GENERATION_OPEN')],1)

    def test_future_ack_and_protocol_return_are_not_ledger_file_callbacks(self):
        events=[dict(node='node-1',event=p) for p in ('FUTURE_RETENTION_BEFORE_RETURN','FUTURE_RETENTION_ACK_BEFORE_RETURN',
                  'FUTURE_RETENTION_PROMOTED','FUTURE_RETENTION_CLEARED','FUTURE_RETENTION_PARENT_FORCED')]
        m.complete_callbacks([dict(life=2,eventIndex=4)],events,2)

    def test_old_capture_scope_cannot_claim_the_seven_family_gate(self):
        events=[dict(node='node-1',event=p) for p in ('RETIREMENT_OLD_FILES_FORCED','ACCEPT_VALIDATED')]
        rows=[dict(life=2,eventIndex=0)]
        m.complete_callbacks(rows,events,2,families='retirement-floor-campaign')
        with self.assertRaisesRegex(ValueError,'^storage coverage complete family callbacks: all-seven$'):
            m.complete_callbacks(rows,events,2)
        with self.assertRaisesRegex(ValueError,'^storage coverage supported family scope$'):
            m.complete_callbacks(rows,events,2,families='subset')

    def test_campaign_original_failure_cannot_earn_storage_coverage(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(campaign.prerequisite,'validate',side_effect=ValueError('original failure')),\
             patch.object(campaign.m,'project') as project:
            with self.assertRaisesRegex(ValueError,'^original failure$'):campaign.validate(temp)
            project.assert_not_called()

    def test_complete_native_prerequisite_precedes_projection(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(m.prerequisite,'validate',side_effect=ValueError('original failure')),\
             patch.object(m,'plans') as plans,patch.object(m,'project') as project:
            with self.assertRaisesRegex(ValueError,'^original failure$'):m.validate(temp)
            plans.assert_not_called();project.assert_not_called()

    def test_component_prerequisite_precedes_resources(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(component.component,'validate',side_effect=ValueError('original failure')),\
             patch.object(component.coverage,'bind') as bind:
            with self.assertRaisesRegex(ValueError,'^original failure$'):component.validate(temp)
            bind.assert_not_called()

    def test_original_changes_during_projection_reject(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(m.prerequisite,'validate',return_value={'status':'PARTIAL'}),\
             patch.object(m,'plans',return_value=[]),patch.object(m,'project',side_effect=lambda *_:Path(temp,'extra').write_text('x')):
            with self.assertRaisesRegex(ValueError,'^storage coverage original changed$'):m.validate(temp)

    def test_callback_acceptance_keeps_full_runtime_and_phase_open(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(m.prerequisite,'validate',return_value={'status':'PARTIAL'}),\
             patch.object(m,'plans',return_value=[]),patch.object(m,'project',return_value={'capturedBytesQualified':False}) as project:
            result=m.validate(temp)
            self.assertEqual(Path(temp)/'previous/previous/previous/previous/maintenance/prefixes/observed',project.call_args.args[0])
            self.assertTrue(result['capturedCallbackBytesQualified']);self.assertFalse(result['wholeRuntimeResourcesQualified'])
            self.assertFalse(result['phase3Complete']);self.assertFalse(result['cohortAdmitted'])


if __name__=='__main__':unittest.main()
