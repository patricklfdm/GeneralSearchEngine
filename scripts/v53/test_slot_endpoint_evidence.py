import unittest
from unittest.mock import patch
from . import slot_endpoint_evidence as evidence


class SlotEndpointEvidenceTest(unittest.TestCase):
    def test_invalid_original_cannot_count_as_successful_negative_qualification(self):
        with patch.object(evidence, 'validate', side_effect=ValueError('invalid original')) as original:
            with patch.object(evidence.tempfile, 'TemporaryDirectory') as mutation:
                with self.assertRaisesRegex(ValueError, '^invalid original$'):
                    evidence.qualify('unavailable-original')
                original.assert_called_once_with('unavailable-original')
                mutation.assert_not_called()


if __name__ == '__main__':
    unittest.main()
