"""Profile completeness and scope guards for covered-minority qualification."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import covered_minority_profiles_evidence as p


class CoveredMinorityProfilesTest(unittest.TestCase):
    def skeleton(self,root):
        for size in (3,4,5):
            for source in ('empty','backup'):(root/f'size-{size}-{source}').mkdir()
        return dict(schema='gse-v53-covered-minority-profiles-v1',status='PASS',cases=[{}]*6,publicBootstrap=True,freshProcesses=False,publicRuntime=False)

    def test_invalid_original_stops_before_negative_copies(self):
        with patch.object(p,'validate',side_effect=ValueError('invalid original')) as original,patch.object(p.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'invalid original'):p.qualify('missing')
            original.assert_called_once();copy.assert_not_called()

    def test_scope_flags_are_typed_not_truthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);receipt=self.skeleton(root)
            for field,value in [('freshProcesses',0),('publicBootstrap',1),('publicRuntime',0),('publicRuntime',True),('status','FAIL')]:
                (root/'receipt.json').write_bytes(p.e.f.canonical(dict(receipt,**{field:value})))
                with self.subTest(field=field,value=value),patch.object(p.model,'clean') as replay,self.assertRaisesRegex(ValueError,'receipt scope'):p.validate(root)
                replay.assert_not_called()

    def test_receipt_cannot_omit_or_duplicate_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);receipt=self.skeleton(root)
            for rows in ([],[{}]*5,[{}]*7,{}):
                (root/'receipt.json').write_bytes(p.e.f.canonical(dict(receipt,cases=rows)))
                with patch.object(p.model,'clean') as replay,self.assertRaisesRegex(ValueError,'complete receipt'):p.validate(root)
                replay.assert_not_called()

    def test_unsupported_size_or_source_flag_refuses_before_reading(self):
        for size,backup in [(True,False),(2,False),(6,False),(3,0),(4,'backup')]:
            for reader in (p.model.clean,p.model.prefix):
                with self.subTest(size=size,backup=backup,reader=reader.__name__),self.assertRaisesRegex(ValueError,'initial profile'):reader(Path('missing'),size,backup)

    def test_extra_profile_and_symlinked_root_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'root';root.mkdir();self.skeleton(root);(root/'size-6-empty').mkdir()
            with self.assertRaisesRegex(ValueError,'inventory'):p.validate(root)
            link=Path(tmp)/'link';link.symlink_to(root,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'inventory'):p.validate(link)


if __name__=='__main__':unittest.main()
