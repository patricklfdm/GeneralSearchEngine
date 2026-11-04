"""Automatic floor storage evidence keeps its incomplete replay scope explicit."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import automatic_floor_resume_evidence as r


class AutomaticFloorResumeEvidenceTest(unittest.TestCase):
    def test_missing_empty_and_linked_originals_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'empty').mkdir();(root/'link').symlink_to(root/'empty',target_is_directory=True)
            for path in (root/'missing',root/'empty',root/'link'):
                with self.subTest(path=path),self.assertRaises(ValueError):r.validate(path)

    def test_receipt_cannot_promote_storage_replay_to_phase_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('pressure','recovery','automatic-floor'):(root/name).mkdir()
            for name in ('lineage.json','floor-events.json','floor-usage.json'):r.h.save(root/name,{})
            value=dict(schema='gse-v53-automatic-floor-resume-v1',status='PASS',profile='4-REMOVE',pressureOutcome='FAIL',sameDirectories=True,
                partialFloorRecoveryQualified=False,automaticRuntimeReachabilityQualified=False,phase3Complete=False)
            for field,wrong in [('partialFloorRecoveryQualified',True),('automaticRuntimeReachabilityQualified',True),('phase3Complete',True),('sameDirectories',1)]:
                with self.subTest(field=field):
                    r.h.save(root/'receipt.json',dict(value,**{field:wrong}))
                    with self.assertRaisesRegex(ValueError,'bounded scope'):r.validate(root)

    def test_original_must_pass_before_mutations(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(r,'validate',side_effect=ValueError('invalid original')),patch.object(r.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'invalid original'):r.qualify(tmp)
            copy.assert_not_called()

    def test_unrelated_rejection_cannot_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            r.h.save(Path(tmp)/'receipt.json',{})
            with patch.object(r,'validate',side_effect=[{},ValueError('unrelated')]),self.assertRaisesRegex(ValueError,'unrelated rejection'):
                r.qualify(tmp)

    def test_unknown_mutation_refuses(self):
        with tempfile.TemporaryDirectory() as tmp,self.assertRaisesRegex(ValueError,'declared mutation'):r.mutate(Path(tmp),'unknown')
