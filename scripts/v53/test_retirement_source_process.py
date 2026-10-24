"""Original-first and typed process evidence regression guards."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import retirement_source_process_evidence as p


class RetirementSourceProcessEvidenceTest(unittest.TestCase):
    def test_invalid_original_is_not_a_negative_success(self):
        with patch.object(p,'validate',side_effect=ValueError('original failed')) as validate,patch.object(p.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'original failed'):p.qualify('missing')
            validate.assert_called_once();copy.assert_not_called()

    def test_missing_or_linked_matrix_never_starts_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'root';root.mkdir();link=Path(tmp)/'link';link.symlink_to(root,target_is_directory=True)
            for path in (root,link):
                with self.subTest(path=path),patch.object(p.model,'plan') as plan,self.assertRaisesRegex(ValueError,'inventory'):p.validate(path)
                plan.assert_not_called()

    def test_layout_cannot_substitute_for_admitted_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'reference').mkdir();(root/'reference/reference').mkdir();(root/'reference/initial').mkdir()
            for mode in ('halt','kill'):
                for cut in p.model.CUTS:(root/(mode+'-'+cut)).mkdir()
            for name in ('inputs.json','receipt.json'):(root/name).write_text('{}')
            with self.assertRaisesRegex(ValueError,'source retirement reference inventory'):p.validate(root)

    def test_numeric_truth_cannot_replace_scope_or_integer_exit(self):
        for actual,expected in [(dict(runtimeEnabled=0),dict(runtimeEnabled=False)),(dict(publicBootstrap=1),dict(publicBootstrap=True)),(dict(exitCode=False),dict(exitCode=0))]:
            with self.subTest(actual=actual),self.assertRaisesRegex(ValueError,'typed'):p.same(actual,expected,'typed')

    def test_trace_rejects_partial_or_linked_lock_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trace';path.write_bytes(b'{"event":"LOCK_HELD"}')
            with self.assertRaisesRegex(ValueError,'complete trace'):p.trace(path)
            path.write_bytes(b'{"event":"LOCK_HELD"}\n');link=Path(tmp)/'link';link.symlink_to(path)
            with self.assertRaisesRegex(ValueError,'bound/type'):p.trace(link)


if __name__=='__main__':unittest.main()
