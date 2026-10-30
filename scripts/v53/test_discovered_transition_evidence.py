import unittest
from unittest.mock import patch
from . import discovered_transition_evidence as d


class DiscoveredTransitionEvidenceTest(unittest.TestCase):
    def test_invalid_original_never_reaches_adoption(self):
        with patch.object(d, 'prelude', side_effect=ValueError('invalid original')), patch.object(d, 'adopted') as adoption:
            with self.assertRaisesRegex(ValueError, '^invalid original$'): d.inspect('unused')
            adoption.assert_not_called()

    def test_qualification_checks_unmodified_evidence_before_mutations(self):
        with patch.object(d, 'inspect', side_effect=ValueError('invalid original')), patch.object(d.shutil, 'copytree') as copy:
            with self.assertRaisesRegex(ValueError, '^invalid original$'): d.qualify('unused')
            copy.assert_not_called()

    def test_invalid_bootstrap_sizes_are_rejected_before_read(self):
        for size in (True, 2, 6, '5'):
            with self.subTest(size=size), patch.object(d.a.p, 'original') as original:
                with self.assertRaisesRegex(ValueError, '^inherited adoption bootstrap size$'):
                    d.a.Walk('unused', size=size)
                original.assert_not_called()


if __name__ == '__main__': unittest.main()
