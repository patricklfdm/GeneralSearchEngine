"""Source-backed retirement replay guards and authority ordering."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import retirement_source_images_evidence as r


class RetirementSourceImagesEvidenceTest(unittest.TestCase):
    def test_invalid_original_cannot_count_as_rejected_mutations(self):
        with patch.object(r,'validate',side_effect=ValueError('invalid original')) as validate,patch.object(r.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'invalid original'):r.qualify('missing')
            validate.assert_called_once();copy.assert_not_called()

    def test_missing_or_linked_matrix_refuses_before_original_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'root';root.mkdir();link=Path(tmp)/'link';link.symlink_to(root,target_is_directory=True)
            for path in (root,link):
                with self.subTest(path=path),patch.object(r,'plan') as plan,self.assertRaisesRegex(ValueError,'inventory'):r.validate(path)
                plan.assert_not_called()

    def test_complete_layout_does_not_replace_original_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'reference').mkdir();(root/'initial').mkdir();(root/'receipt.json').write_text('{}')
            for cut in r.CUTS:(root/cut).mkdir()
            with self.assertRaisesRegex(ValueError,'source retirement reference inventory'):r.validate(root)

    def test_source_and_floor_are_resealed_before_authority_and_deletion(self):
        before={'generations/b':None,'generations/b/generation.gsr':b'manifest','sources/pinned/image':b'original'}
        old={'generation.gsr':b'manifest'};sealing=['CONTEXT_SOURCE_PARENT_FORCED','RETIREMENT_BORROWED_SOURCE_FORCED','RETIREMENT_BORROWED_IMAGES_FORCED']
        first,events=r.transaction(before,old,'generations/b/',b'record',b'binding',sealing,'RETIREMENT_AUTHORITY_FORCED')
        self.assertIn('generations/b/generation.gsr',first);self.assertIn('retirement/retirement.gsr',first)
        self.assertLess(events.index('CONTEXT_SOURCE_PARENT_FORCED'),events.index('RETIREMENT_AUTHORITY_WRITTEN'))
        second,events=r.transaction(first,old,'generations/b/',b'record',b'binding',sealing,'RETIREMENT_AUTHORITY_RESEALED')
        self.assertEqual(first,second);self.assertLess(events.index('RETIREMENT_BORROWED_SOURCE_FORCED'),events.index('RETIREMENT_AUTHORITY_RESEALED'))
        final,events=r.transaction(second,old,'generations/b/',b'record',b'binding',sealing)
        self.assertEqual({'sources/pinned/image':b'original'},final)
        self.assertLess(events.index('RETIREMENT_DIRECTORY_DELETED'),events.index('RETIREMENT_BORROW_CLEARED'))
        self.assertLess(events.index('RETIREMENT_BORROW_CLEARED'),events.index('RETIREMENT_AUTHORITY_CLEARED'))

    def test_missing_cut_and_completed_retirement_do_not_invent_callbacks(self):
        before={'sources/pinned/image':b'original'}
        state,events=r.transaction(before,{},'generations/b/',b'record',b'binding',[])
        self.assertEqual(before,state);self.assertEqual(r.covered.OPEN+r.covered.SEAL,events)
        with self.assertRaisesRegex(ValueError,'not reached'):r.transaction(before,{},'generations/b/',b'record',b'binding',[],'RETIREMENT_BEFORE_RETURN')


if __name__=='__main__':unittest.main()
