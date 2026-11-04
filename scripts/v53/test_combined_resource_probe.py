"""A diagnostic success must never stand in for a completed native history."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import combined_resource_probe as r


class CombinedResourceProbeTest(unittest.TestCase):
    def test_successful_or_invented_matrix_cannot_be_labeled_this_failed_probe(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'4-REMOVE').mkdir()
            value=dict(schema='gse-v53-combined-transition-v1',status='PASS',cases=[],network=True,
                       simultaneousMaximumQualified=False,publicRuntime=False,phase3Complete=False)
            (root/'receipt.json').write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'original failure scope'):r.diagnose(root)
            (root/'5-REMOVE').mkdir()
            with self.assertRaisesRegex(ValueError,'incomplete first profile'):r.diagnose(root)

    def test_missing_empty_and_linked_input_are_not_diagnosed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);empty=root/'empty';empty.mkdir();link=root/'link';link.symlink_to(empty,target_is_directory=True)
            for path in (root/'missing',empty,link):
                with self.subTest(path=path),self.assertRaises(ValueError):r.diagnose(path)

    def test_bad_original_stops_before_mutation_or_copy(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(r,'diagnose',side_effect=ValueError('invalid original')),\
                patch.object(r.shutil,'copytree') as copied,patch.object(r,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'invalid original'):r.qualify(temp)
            copied.assert_not_called();mutate.assert_not_called()

    def test_unrelated_error_cannot_count_as_expected_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'4-REMOVE').mkdir();(root/'receipt.json').write_text('{"status":"INCOMPLETE"}')
            with patch.object(r,'diagnose',side_effect=[{},ValueError('unrelated')]),self.assertRaisesRegex(ValueError,'unrelated negative'):
                r.qualify(root)

    def test_unknown_mutation_refuses_without_aliasing_a_known_case(self):
        with tempfile.TemporaryDirectory() as temp,self.assertRaisesRegex(ValueError,'declared mutation'):
            r.mutate(Path(temp),'unknown')
