"""Original-first and scope guards; actual pressure negatives run on real bytes."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import queue_completion_evidence as q
from .test_resource_transitions import trace,row


class QueueCompletionEvidenceTest(unittest.TestCase):
    def value(self):
        return dict(receipt=dict(schema='gse-v53-queue-completion-v1',status='PASS',points=[],attempts=[],traces=[],
                                phase3Complete=False,combinedMaximumQualified=False,pressureRequired=True),
                    trace=trace([row('START')]),events=[],selected={})

    def test_partial_queue_observation_cannot_be_upgraded_to_combined_or_phase_closure(self):
        for flag in ('phase3Complete','combinedMaximumQualified'):
            value=self.value();value['receipt'][flag]=True
            with self.subTest(flag=flag),self.assertRaisesRegex(ValueError,'^queue completion scope$'):q.replay(value)

    def test_small_image_rehearsal_cannot_qualify_full_queue_pressure(self):
        value=self.value();value['receipt']['pressureRequired']=False
        with self.assertRaisesRegex(ValueError,'^queue completion scope$'):q.replay(value)

    def test_empty_closed_resources_do_not_replace_actual_completion_boundaries(self):
        with self.assertRaisesRegex(ValueError,'^queue completion complete milestones$'):q.replay(self.value())

    def test_lowered_queue_limit_is_not_full_byte_pressure(self):
        value=self.value();value['trace']['queueLimit']-=1
        with self.assertRaisesRegex(ValueError,'^queue completion frozen queue$'):q.replay(value)

    def test_original_physical_replay_precedes_resource_observations(self):
        receipt=dict(status='PASS',kind='REMOVE',activations=3,publicReady=False,automaticLifecycle=False)
        with tempfile.TemporaryDirectory() as root,patch.object(q.history.d,'read',return_value=receipt),\
                patch.object(q.history,'history',side_effect=ValueError('original failed')) as physical,patch.object(q.t,'read') as resources:
            (Path(root)/'continuous-result.json').write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError,'^original failed$'):q.load(root)
            self.assertTrue(physical.call_args.kwargs['backup']);self.assertTrue(physical.call_args.kwargs['current_maintenance']);resources.assert_not_called()

    def test_linked_or_oversized_receipt_is_rejected_before_reading(self):
        for mode in ('symlink','oversized'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as temp,patch.object(q.history.d,'read') as read:
                root=Path(temp);scope=root/'continuous-result.json'
                if mode=='symlink':scope.symlink_to('/missing')
                else:scope.write_bytes(b'x'*4097)
                with self.assertRaisesRegex(ValueError,'^queue completion regular receipt$'):q.load(root)
                read.assert_not_called()

    def test_original_basis_is_selected_by_ballot_not_journal_tail(self):
        rows=[('PROMISE',b'old-promise',{'ballot':1}),('BASIS',b'old-basis',{'ballot':1}),
              ('PROMISE',b'promise',{'ballot':2}),('BASIS',b'basis',{'ballot':2}),('SELECTED',b'selection',{'ballot':2})]
        self.assertEqual((b'promise',b'basis'),q.joint_grant(rows,2))
        for changed in (rows[:-2]+rows[-1:],rows+[rows[-2]]):
            with self.assertRaisesRegex(ValueError,'^queue completion original joint grant$'):q.joint_grant(changed,2)

    def test_broken_original_cannot_be_counted_as_negative_success(self):
        with patch.object(q,'replay',side_effect=ValueError('original failed')) as replay,patch.object(q.copy,'deepcopy') as mutate:
            with self.assertRaisesRegex(ValueError,'^original failed$'):q.qualify({})
            replay.assert_called_once_with({});mutate.assert_not_called()

    def test_unrelated_failure_does_not_satisfy_a_negative(self):
        value=self.value()
        with patch.object(q,'replay',side_effect=[dict(status='PASS'),ValueError('unrelated')]):
            with self.assertRaisesRegex(ValueError,'negative reason drift'):q.qualify(value)


if __name__=='__main__':unittest.main()
