"""Guard against false negative qualification and ambiguous persisted votes."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import context_mixed_acceptance_evidence as m
from . import context_mixed_recovery_evidence as r


class MixedEvidenceTest(unittest.TestCase):
    def test_invalid_original_cannot_count_as_successful_negatives(self):
        for module in (m,r):
            with self.subTest(module=module.__name__),patch.object(module,'validate',side_effect=ValueError('bad original')) as validate,patch.object(module.shutil,'copytree') as copytree:
                with self.assertRaisesRegex(ValueError,'bad original'):module.qualify('absent')
                validate.assert_called_once();copytree.assert_not_called()

    def test_missing_or_linked_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'missing'
            for module in (m,r):
                with self.assertRaises(ValueError):module.validate(root)
            real=Path(tmp)/'real';real.mkdir();root.symlink_to(real,target_is_directory=True)
            for module in (m,r):
                with self.assertRaises(ValueError):module.validate(root)

    def test_no_context_does_not_guess_an_optional_certificate(self):
        with patch.object(m.carried,'pending',side_effect=ValueError('trailing bytes')) as pending:
            with self.assertRaisesRegex(ValueError,'trailing bytes'):m.vote({'pending.accept':b'vote'})
            pending.assert_called_once_with(b'vote',())

    def test_context_requires_the_exact_declared_phase_extent(self):
        for proof,cert,phases in ((None,None,()),('p',None,('PROOF',)),('p','c',('PROOF','CERTIFICATE'))):
            with self.subTest(phases=phases),patch.object(m.e,'decode',return_value=(None,None,dict(proof=proof,certificate=cert))),patch.object(m.carried,'pending',side_effect=ValueError('truncated')) as pending:
                with self.assertRaisesRegex(ValueError,'truncated'):m.vote({'pending.accept':b'vote','pending.context':b'context'})
                pending.assert_called_once_with(b'vote',phases)

    def test_recovery_matrix_uses_real_distinct_handoff_events(self):
        self.assertEqual(12,len(set(r.ACCEPT_CUTS+r.SOURCE_CUTS)))
        self.assertTrue(set(r.ACCEPT_CUTS)<=set(r.acceptance.CUTS))
        self.assertTrue(set(r.SOURCE_CUTS)<=set(r.source.CUTS))
        self.assertIn('CONTEXT_ACCEPT_CLEARED',r.ACCEPT_CUTS)
        self.assertIn('FLOOR_RELEASE_RELINQUISHED',r.ACCEPT_CUTS)
        self.assertIn('SOURCE_RETIREMENT_JOURNAL_PRUNED',r.SOURCE_CUTS)

    def test_hash_inventory_preserves_empty_members_and_directories(self):
        actual=r.state({'dir':None,'dir/empty':b'','dir/payload':b'data'})
        self.assertEqual({'directory':True},actual['dir'])
        self.assertEqual(0,actual['dir/empty']['bytes'])
        self.assertEqual(m.e.digest(b''),actual['dir/empty']['sha256'])
        self.assertEqual(m.e.digest(b'data'),actual['dir/payload']['sha256'])


if __name__=='__main__':unittest.main()
