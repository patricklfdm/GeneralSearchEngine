from pathlib import Path
import copy
import tempfile
import unittest
from unittest.mock import patch
from . import native_carried_storage_coverage as m
from . import storage_coverage_component as component
from . import campaign_storage_coverage as campaign
from . import test_storage_coverage_binding as binding_fixture


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


class NativeStorageOwnershipQualificationTest(unittest.TestCase):
    def targets(self):
        charges=[dict(unit=unit,owner='original-'+unit) for unit in ('GENERATION','SOURCE','JOURNAL','MISC')]
        charges += [dict(unit='APPLICATION',owner=name) for name in
                    ('generation-a:image','floor:copy:0','retirement:0','application-replay-input','applied-end',
                     '00000000-0000-0000-0000-000000000001:'+('a'*64))]
        return dict(owners=[dict(life=2,node='node-1',snapshots=[dict(eventIndex=19,point='CAPTURE',required=charges)])])

    def test_every_owner_family_requires_an_actual_file_witness(self):
        original=self.targets();targets=m.ownership_targets(original)
        self.assertEqual(m.OWNER_CASES,set(targets))
        self.assertEqual('applied-end',targets['applied-end']['owner'])
        for offset in range(len(m.OWNER_CASES)):
            changed=copy.deepcopy(original);changed['owners'][0]['snapshots'][0]['required'].pop(offset)
            with self.subTest(offset=offset),self.assertRaisesRegex(ValueError,'complete original owner cases'):
                m.ownership_targets(changed)
        changed=copy.deepcopy(original);changed['owners'][0]['snapshots'][0]['required'].append(dict(unit='APPLICATION',owner='foreign'))
        with self.assertRaisesRegex(ValueError,'supported original owner case'):m.ownership_targets(changed)

    def test_balanced_trace_with_foreign_owner_cannot_cover_original_files(self):
        fixture=binding_fixture.StorageCoverageBindingTest();rows,trace,events,boundaries=fixture.fixture()
        original=copy.deepcopy(trace)
        for closed in (True,False):
            source=copy.deepcopy(trace)
            if not closed:
                source['changes']=source['changes'][:3];source['transitions']=3;source['current']=source['changes'][-1]['usage']
            changed=m.rename_owner(source,'MISC','current-authority')
            self.assertEqual(m.coverage.t.replay(source,require_closed=closed),m.coverage.t.replay(changed,require_closed=closed))
            with self.assertRaisesRegex(ValueError,'^storage coverage original charge owner$'):
                m.coverage.bind(rows,changed,events,boundaries,'node-1',2,closed=closed,ordinals=m.coverage.ordinal_plans(rows))
        self.assertEqual(original,trace)

    def test_mutation_cannot_invent_target_or_alias_an_existing_owner(self):
        trace=binding_fixture.StorageCoverageBindingTest().fixture()[1]
        with self.assertRaisesRegex(ValueError,'distinct original mutation owner'):m.rename_owner(trace,'MISC','absent')
        changed=m.rename_owner(trace,'MISC','current-authority')
        with self.assertRaisesRegex(ValueError,'distinct original mutation owner'):m.rename_owner(changed,'MISC','unrelated-storage')
        changed['changes'][0]['added'].append(dict(unit='MISC',owner='current-authority',bytes=1,claimSource=''))
        with self.assertRaisesRegex(ValueError,'distinct original mutation owner'):m.rename_owner(changed,'MISC','current-authority')

    def test_failed_native_prerequisite_earns_no_negative_credit(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(m,'validate',side_effect=ValueError('original failure')),\
             patch.object(m,'ownership_targets') as targets,patch.object(m,'rename_owner') as mutate:
            with self.assertRaisesRegex(ValueError,'^original failure$'):m.qualify(temp)
            targets.assert_not_called();mutate.assert_not_called()


if __name__=='__main__':unittest.main()
