import unittest
from unittest.mock import patch
from . import covered_context_mixed_evidence as q


class CoveredContextMixedEvidenceTest(unittest.TestCase):
    def test_corrupt_original_cannot_count_as_successful_mutations(self):
        with patch.object(q, 'validate', side_effect=ValueError('invalid original')), patch.object(q.shutil, 'copytree') as copied:
            with self.assertRaisesRegex(ValueError, 'invalid original'): q.qualify('raw')
            copied.assert_not_called()


if __name__ == '__main__': unittest.main()
