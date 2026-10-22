import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.v53 import capture_recovery_evidence as e
from scripts.v53 import capture_recovery_negatives as n
from scripts.v53 import capture_recovery_qualification as q


class CaptureRecoveryEvidenceTest(unittest.TestCase):
    def test_profiles_and_real_prefix_crash_boundaries(self):
        cases=e.cases();self.assertEqual(66,len(cases));self.assertEqual(len(cases),len({c['name'] for c in cases}))
        self.assertEqual({(s,v,t) for s in (3,4,5) for v in (0,6,7) for t in (False,True)},
                         {(c['size'],c['through'],c['tail']) for c in cases if c['mode']=='clean'})
        for mode in ('halt','kill'):self.assertEqual(set(e.CUTS),{c['cut'] for c in cases if c['mode']==mode})
        self.assertTrue({'SOURCE_PACKET_PREFIX_WRITTEN','SOURCE_IMAGE_PREFIX_WRITTEN','CAPTURE_INTENT_PREFIX_WRITTEN'}<=set(e.CUTS))
        self.assertEqual({'repeat-halt','repeat-kill'},{c['mode'] for c in cases if c['mode'].startswith('repeat-')})

    def test_completed_basis_only_clears_intent_and_never_rewrites_source(self):
        self.assertEqual(list(e.current.OPEN+e.CLEAR),e.recovery_order({e.AUTHORITY:0},'id',True))
        self.assertEqual(list(e.current.OPEN),e.recovery_order({},'id',True))

    def test_partial_capture_requires_all_remaining_forces_before_basis(self):
        events=e.recovery_order({e.AUTHORITY:0,'sources/id':{},'sources/id/source.gscp':{}},'id',False)
        self.assertNotIn('SOURCE_PACKET_CREATED',events);self.assertIn('SOURCE_IMAGE_CREATED',events)
        self.assertLess(events.index('SOURCE_DIRECTORY_FORCED'),events.index('BASIS_BEFORE_WRITE'))
        self.assertLess(events.index('BASIS_FORCED'),events.index('CAPTURE_INTENT_DELETED'))

    def test_invalid_original_cannot_count_as_negative_results(self):
        with patch.object(e,'validate',side_effect=ValueError('invalid original')),patch.object(n.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'invalid original'):n.run('absent')
            copy.assert_not_called()

    def test_unrelated_rejection_does_not_satisfy_negative(self):
        with patch.object(e,'validate'),patch.object(n.shutil,'copytree'),patch.object(n,'mutate'),patch.object(e,'validate_case',side_effect=ValueError('unrelated')):
            with self.assertRaisesRegex(ValueError,'unrelated capture negative'):n.run('absent')

    def test_complete_inventory_required(self):
        with tempfile.TemporaryDirectory() as root,patch.object(e,'validate_case') as replay:
            with self.assertRaisesRegex(ValueError,'capture complete case inventory'):e.validate(root)
            replay.assert_not_called()

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            keep=Path(root)/'old';keep.write_text('keep')
            with self.assertRaises(FileExistsError):q.run(root)
            self.assertEqual('keep',keep.read_text())


if __name__=='__main__':unittest.main()
