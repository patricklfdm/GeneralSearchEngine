"""Scope and original-first safeguards for distinct minority evidence."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import distinct_minority_evidence as m


class DistinctMinorityEvidenceTest(unittest.TestCase):
    def test_invalid_original_stops_before_mutations(self):
        with patch.object(m,'validate',side_effect=ValueError('invalid original')) as validate,patch.object(m.shutil,'copytree') as copytree:
            with self.assertRaisesRegex(ValueError,'invalid original'):m.qualify('missing')
            validate.assert_called_once();copytree.assert_not_called()

    def skeleton(self,path):
        for size in (3,4,5):
            for source in ('empty','backup'):(path/f'size-{size}-{source}').mkdir()
        return dict(schema='gse-v53-distinct-minority-v1',status='PASS',cases=[{} for _ in range(6)],publicBootstrap=True,publicRuntime=False,freshProcesses=False)

    def test_numeric_booleans_and_unperformed_process_scope_are_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);original=self.skeleton(root)
            for field,value in [('publicBootstrap',1),('publicRuntime',0),('freshProcesses',0),('freshProcesses',True),('status','INCOMPLETE')]:
                (root/'receipt.json').write_bytes(m.e.f.canonical(dict(original,**{field:value})))
                with self.subTest(field=field,value=value),patch.object(m,'validate_case') as cases,self.assertRaisesRegex(ValueError,'receipt scope'):
                    m.validate(root)
                cases.assert_not_called()

    def test_missing_and_duplicate_case_rows_fail_before_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);original=self.skeleton(root)
            for rows in ([],[{}]*5,[{}]*7,{}):
                (root/'receipt.json').write_bytes(m.e.f.canonical(dict(original,cases=rows)))
                with patch.object(m,'validate_case') as cases,self.assertRaisesRegex(ValueError,'complete receipt'):m.validate(root)
                cases.assert_not_called()

    def test_linked_root_and_extra_profile_cannot_supply_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'root';root.mkdir();link=Path(tmp)/'link';link.symlink_to(root,target_is_directory=True)
            with self.assertRaises(ValueError):m.validate(link)
            self.skeleton(root);(root/'size-6-empty').mkdir()
            with self.assertRaisesRegex(ValueError,'cases inventory'):m.validate(root)

    def test_calls_cannot_claim_an_empty_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'calls.json').write_text('[]')
            with self.assertRaisesRegex(ValueError,'complete call inventory'):m.calls(root,['node-1','node-2','node-3'],['node-1'],['node-2','node-3'])


if __name__=='__main__':unittest.main()
