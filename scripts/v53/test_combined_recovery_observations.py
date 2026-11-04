"""Narrow observation results cannot be promoted to full recovery qualification."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import combined_recovery_observations as r

class CombinedRecoveryObservationTest(unittest.TestCase):
    def test_departed_final_has_forced_application_but_no_successor_checkpoint_vote(self):
        before=dict(generation=2,operation={'number':1},old=['node-1','node-2','node-3','node-4'],new=['node-1','node-2','node-3'])
        after=dict(generation=3,operation=None,old=before['new'],new=before['new'])
        self.assertEqual('APPLY_NONVOTING_DIRECTORY_FORCED',r.application_boundary(before,after,'node-4','FINAL'))
        self.assertEqual('APPLY_ACK_DIRECTORY_FORCED',r.application_boundary(before,after,'node-3','FINAL'))
        for kind,node in [('INTENT','node-4'),('BARRIER','node-4'),('FINAL','node-5')]:
            with self.subTest(kind=kind,node=node),self.assertRaisesRegex(ValueError,'exact departing FINAL'):
                r.application_boundary(before,after,node,kind)
        with self.assertRaisesRegex(ValueError,'exact departing FINAL'):
            r.application_boundary(before,dict(after,generation=4),'node-4','FINAL')

    def test_absent_linked_and_empty_history_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'empty').mkdir();(root/'link').symlink_to(root/'empty',target_is_directory=True)
            for path in (root/'missing',root/'empty',root/'link'):
                with self.subTest(path=path),self.assertRaises(ValueError):r.inspect(path)

    def test_complete_recovery_claim_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('pressure','recovery'):(root/name).mkdir()
            r.h.save(root/'lineage.json',{})
            r.h.save(root/'receipt.json',dict(schema='gse-v53-combined-recovery-v1',status='PASS',profile='4-REMOVE',pressureOutcome='FAIL',sameDirectories=True,
                partialFloorRecoveryQualified=True,automaticRuntimeReachabilityQualified=False,phase3Complete=False))
            with self.assertRaisesRegex(ValueError,'bounded scope'):r.inspect(root)

    def test_invalid_original_prevents_negative_replay(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(r,'inspect',side_effect=ValueError('original')),\
                patch.object(r.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'original'):r.qualify(tmp)
            copy.assert_not_called()

    def test_wrong_rejection_does_not_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);r.h.save(root/'receipt.json',{})
            with patch.object(r,'inspect',side_effect=[{},ValueError('unrelated')]),self.assertRaisesRegex(ValueError,'unrelated rejection'):
                r.qualify(root)

    def test_unknown_mutation_cannot_alias_another_case(self):
        with tempfile.TemporaryDirectory() as tmp,self.assertRaisesRegex(ValueError,'declared mutation'):
            r.mutate(Path(tmp),'unknown')
