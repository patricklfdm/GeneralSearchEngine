from copy import deepcopy
import unittest
from . import cloud_image_policy as p


class ImagePolicyTest(unittest.TestCase):
    expected = dict(name='frozen-image', id='1234', status='READY', architecture='X86_64')

    def test_active_and_deprecated_are_idempotent_and_keep_exact_identity(self):
        for dep in (None, {}, {'state':'ACTIVE'}, {'state':'DEPRECATED', 'replacement':'not-followed'}):
            value = p.observe(dict(self.expected, deprecated=dep), self.expected)
            self.assertEqual(value, p.observe(value, self.expected))
            self.assertEqual(self.expected, {k: value[k] for k in self.expected})
            self.assertEqual(bool(dep and dep.get('state') == 'DEPRECATED'), bool(p.warnings(value)))
            self.assertNotIn('not-followed', str(value))

    def test_unusable_unknown_and_malformed_states_fail_closed(self):
        for dep in ([], False, '', 0, {'replacement':'other'}, {'state':None}, {'state':[]},
                    {'state':'OBSOLETE'}, {'state':'DELETED'}, {'state':'NEW'}, {'state':'deprecated'}):
            with self.subTest(dep=dep), self.assertRaises(ValueError):
                p.observe(dict(self.expected, deprecated=dep), self.expected)

    def test_deprecated_does_not_exempt_identity_or_readiness(self):
        for key in self.expected:
            for change in ('different', None, True):
                value = dict(self.expected, deprecated={'state':'DEPRECATED'}); value[key] = change
                with self.subTest(key=key, change=change), self.assertRaises(ValueError):
                    p.observe(value, self.expected)
            value=deepcopy(self.expected);del value[key]
            with self.assertRaises(ValueError): p.observe(value, self.expected)


if __name__ == '__main__': unittest.main()
