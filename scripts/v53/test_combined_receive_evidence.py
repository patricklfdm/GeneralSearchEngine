"""Reader entry and accounting guards; native mutation results are retained separately."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import combined_receive_evidence as r


class CombinedReceiveEvidenceTest(unittest.TestCase):
    def test_all_profiles_and_both_sides_of_actual_byte_boundary_are_required(self):
        self.assertEqual(9,len(r.CASES));self.assertEqual({3,4,5},{n for n,_ in r.CASES})
        self.assertEqual({'image-count','shared-short','shared-exact'},{mode for _,mode in r.CASES})
        p,image,control,metadata=3250,837,1077,100
        baseline=r.usage(metadata,p,image,control)
        full=r.usage(metadata,p,image,control,5)
        self.assertEqual(7,full['counts']['APPLICATION']);self.assertEqual(1,full['counts']['LEARNER'])
        self.assertEqual(5,full['counts']['SOURCE'])
        self.assertEqual(5*(p+image),full['staging']-baseline['staging'])
        # Failed validation retains its complete packet and control slot, but
        # cannot charge or expose an image it failed to reserve.
        failed=r.usage(metadata,p,image,control,5,True)
        self.assertEqual(p,failed['staging']-full['staging'])
        self.assertEqual(control,failed['queued']-full['queued']);self.assertEqual(7,failed['counts']['APPLICATION'])
        self.assertEqual(baseline,r.usage(metadata,p,image,control))
        self.assertEqual(dict(metadata=0,staging=0,queued=0,leases=0,counts={}),r.usage(metadata,p,image,control,closed=True))

    def test_incomplete_original_stops_before_mutation_or_copy(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(r,'validate',side_effect=ValueError('bad original')) as validate,\
                patch.object(r.shutil,'copytree') as copied,patch.object(r,'mutate') as mutate:
            root=Path(temp);(root/'retained').write_bytes(b'original')
            with self.assertRaisesRegex(ValueError,'bad original'):r.qualify(root)
            validate.assert_called_once_with(root);copied.assert_not_called();mutate.assert_not_called()
            self.assertEqual(b'original',(root/'retained').read_bytes())

    def test_missing_linked_or_empty_complete_matrices_refuse(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);empty=root/'empty';empty.mkdir();linked=root/'linked';linked.symlink_to(empty,target_is_directory=True)
            for path in (root/'missing',linked,empty):
                with self.subTest(path=path),self.assertRaises(ValueError):r.validate(path)

    def test_boolean_usage_does_not_equal_integer_accounting(self):
        with self.assertRaisesRegex(ValueError,'exact usage'):r.same({'leases':True},{'leases':1},'exact usage')

    def test_unknown_mutation_cannot_fall_through_to_a_known_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);case=root/'stable-3-image-count';case.mkdir();(case/'events.json').write_text('[]')
            with self.assertRaisesRegex(ValueError,'declared mutation'):r.mutate(root,'unknown')

    def test_an_unrelated_error_never_counts_as_expected_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);case=root/'stable-3-image-count';case.mkdir();(case/'events.json').write_text('[]')
            (root/'receipt.json').write_text(json.dumps(dict(simultaneousMaximumQualified=False)))
            with patch.object(r,'validate',side_effect=[{},ValueError('unrelated failure')]),self.assertRaisesRegex(ValueError,'unrelated negative'):
                r.qualify(root)
