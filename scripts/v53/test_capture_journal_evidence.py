import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.v53 import capture_journal_evidence as e
from scripts.v53 import capture_journal_negatives as n
from scripts.v53 import capture_journal_qualification as q


class CaptureJournalEvidenceTest(unittest.TestCase):
    def test_retains_every_original_profile_and_adds_real_torn_recovery_boundaries(self):
        cases=e.cases();self.assertEqual(82,len(cases));self.assertEqual(len(cases),len({c['name'] for c in cases}))
        self.assertTrue({c['name'] for c in e.base.cases()}<={c['name'] for c in cases})
        for mode in ('halt','kill'):self.assertEqual(set(e.CUTS),{c['cut'] for c in cases if c['mode']==mode})
        for mode in ('recover-halt','recover-kill'):self.assertEqual(set(e.RECOVERY+e.base.CLEAR),{c['cut'] for c in cases if c['mode']==mode})

    def test_unmodified_evidence_must_pass_before_mutations(self):
        with patch.object(e,'validate',side_effect=ValueError('invalid original')),patch.object(n.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'invalid original'):n.run('absent')
            copy.assert_not_called()

    def test_unrelated_rejection_cannot_satisfy_negative(self):
        with patch.object(e,'validate'),patch.object(n.shutil,'copytree'),patch.object(n,'mutate'),patch.object(e,'validate_case',side_effect=ValueError('unrelated')):
            with self.assertRaisesRegex(ValueError,'unrelated capture journal negative'):n.run('absent')

    def test_existing_output_and_incomplete_case_sets_fail_closed(self):
        with tempfile.TemporaryDirectory() as root,patch.object(e,'validate_case') as replay:
            keep=Path(root)/'keep';keep.write_text('old')
            with self.assertRaises(FileExistsError):q.run(root)
            with self.assertRaisesRegex(ValueError,'capture journal complete case inventory'):e.validate(root)
            replay.assert_not_called();self.assertEqual('old',keep.read_text())


if __name__=='__main__':unittest.main()
