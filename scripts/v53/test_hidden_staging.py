import struct
import unittest
from unittest.mock import patch
from . import hidden_staging_evidence as h
from . import test_covered_staging as fixtures


class HiddenStagingTest(unittest.TestCase):
    def fixture(self):
        original,marker=fixtures.CoveredStagingTest().original()
        with patch.object(h.q,'authority',return_value=marker):marker=h.authority({}, {}, b'original endorsed ancestry')
        return original,marker

    def test_marker_binds_exact_supplemental_bytes_and_preserves_inventory(self):
        _,before=fixtures.CoveredStagingTest().original()
        with patch.object(h.q,'authority',return_value=before):
            a=h.authority({}, {}, b'proof a');b=h.authority({}, {}, b'proof b')
        self.assertNotEqual(a,b);body=h.e.parse(a[48:]);self.assertEqual(body['files'],h.e.parse(before[48:])['files'])
        self.assertEqual(h.e.digest(b'proof a'),body['authority']['appliedAncestry'])
        self.assertEqual(struct.pack('>4sHHII',b'GSAT',1,3,0,len(a)-48),a[:16])
        self.assertEqual(bytes.fromhex(h.e.digest(a[:16]+a[48:])),a[16:48])

    def test_all_hidden_cleanup_interruptions_resume_with_original_vote(self):
        initial,marker=self.fixture()
        for cut in h.CUTS:
            with self.subTest(cut=cut):
                first,_=h.q.cleanup(initial,marker,cut);second,_=h.q.cleanup(first,marker,'SUPERSEDED_END_AUTHORITY_FORCED')
                final,_=h.q.cleanup(second,marker)
                self.assertEqual(h.q.without_staging(initial),final)
                self.assertEqual(h.e.parse(marker[48:])['authority'],h.e.parse(second['applied-end/retirement.gsat'][48:])['authority'])

    def test_retained_marker_refuses_a_different_validly_framed_proof_digest(self):
        initial,marker=self.fixture();state,_=h.q.cleanup(initial,marker,'SUPERSEDED_END_AUTHORITY_FORCED')
        body=h.e.parse(marker[48:]);body['authority']['appliedAncestry']='0'*64;body=h.e.f.canonical(body)
        header=struct.pack('>4sHHII',b'GSAT',1,3,0,len(body));state['applied-end/retirement.gsat']=header+bytes.fromhex(h.e.digest(header+body))+body
        with self.assertRaisesRegex(ValueError,'exact retained authority'):h.q.cleanup(state,marker)

    def test_invalid_original_never_counts_as_successful_rejections(self):
        with patch.object(h,'validate',side_effect=ValueError('invalid original')),patch.object(h.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'invalid original'):h.qualify('profiles','interrupted')
            copied.assert_not_called()

    def test_portable_replay_requires_equal_original_and_moved_results(self):
        with patch.object(h,'qualify',side_effect=[{'status':'PASS'},{'status':'FAIL'}]),patch.object(h.shutil,'copytree'):
            with self.assertRaisesRegex(ValueError,'relocated replay changed'):h.portable('profiles','interrupted')


if __name__=='__main__':unittest.main()
