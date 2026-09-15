import unittest
from .core_api_delta import verify

APPROVED = "--- published-v4\n+++ candidate-v5\n@@ -1,0 +2 @@\n+approved method\n"


class CoreApiDeltaTest(unittest.TestCase):
    def test_exact_addition_is_allowed(self):
        before, after = ['old method'], ['old method', 'approved method']
        verify(before, after, APPROVED)

    def test_extra_addition_removal_and_changed_signature_are_rejected(self):
        before, approved = ['old method'], ['old method', 'approved method']
        expected = APPROVED
        for actual in (approved + ['unreviewed method'], ['approved method'], ['changed old method', 'approved method']):
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                verify(before, actual, expected)
