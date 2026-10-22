import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.v53 import captured_source_release_evidence as e
from scripts.v53 import captured_source_release_negatives as n
from scripts.v53 import captured_source_release_qualification as q


class CapturedSourceReleaseEvidenceTest(unittest.TestCase):
    def test_profiles_cover_every_size_view_tail_and_all_transaction_boundaries(self):
        rows=e.cases();self.assertEqual(44,len(rows));self.assertEqual(44,len({r['name'] for r in rows}))
        self.assertEqual({(size,through,tail) for size in (3,4,5) for through in (6,7) for tail in (False,True)},
                         {(r['size'],r['through'],r['tail']) for r in rows if r['mode']=='clean'})
        for mode in ('halt','kill'):self.assertEqual(set(e.e.CUTS),{r['cut'] for r in rows if r['mode']==mode})
        self.assertEqual({'repeat-halt','repeat-kill'},{r['mode'] for r in rows if r['mode'].startswith('repeat-')})

    def test_invalid_original_is_not_counted_as_negative_rejections(self):
        with patch.object(e,'validate',side_effect=ValueError('invalid original')),patch.object(n.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'invalid original'):n.run('absent')
            copy.assert_not_called()

    def test_unrelated_rejection_cannot_satisfy_negative_contract(self):
        with patch.object(e,'validate'),patch.object(n.shutil,'copytree'),patch.object(n,'mutate'),patch.object(e,'validate_case',side_effect=ValueError('unrelated')):
            with self.assertRaisesRegex(ValueError,'unrelated source release negative'):n.run('absent')

    def test_capture_scope_and_original_plan_are_explicit(self):
        with patch.object(e.e,'validate_case',return_value='checked') as call:
            self.assertEqual('checked',e.validate_case('path',{'size':3}))
            call.assert_called_once_with('path',{'size':3},plan_builder=e.plan,execution='private-captured-source-retirement')

    def test_complete_inventory_is_required_before_any_case_replay(self):
        with tempfile.TemporaryDirectory() as root,patch.object(e,'validate_case') as replay:
            with self.assertRaisesRegex(ValueError,'captured source complete cases'):e.validate(root)
            replay.assert_not_called()

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'old';path.write_text('keep')
            with self.assertRaises(FileExistsError):q.run(root)
            self.assertEqual('keep',path.read_text())


if __name__=='__main__':unittest.main()
