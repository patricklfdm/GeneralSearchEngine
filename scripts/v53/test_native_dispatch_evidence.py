import unittest
from unittest.mock import patch
from . import native_dispatch_evidence as evidence


class NativeDispatchEvidenceTest(unittest.TestCase):
    def test_invalid_original_stops_before_any_negative_is_generated(self):
        with patch.object(evidence, 'validate', side_effect=ValueError('invalid original')) as original:
            with patch.object(evidence.tempfile, 'TemporaryDirectory') as mutations:
                with self.assertRaisesRegex(ValueError, '^invalid original$'):
                    evidence.qualify('invalid-root')
                original.assert_called_once_with('invalid-root')
                mutations.assert_not_called()


if __name__ == '__main__':
    unittest.main()
