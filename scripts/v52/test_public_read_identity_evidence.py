"""Identity fixtures change one field; format failures cannot masquerade as foreign histories."""
import base64
import hashlib
import unittest
from . import public_read_identity_evidence as e,token


class ReadIdentityEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.original=dict(version=1,groupId='11111111-1111-1111-1111-111111111111',
                           historyId='44444444-4444-4444-4444-444444444444',manifestDigest='01'*32,index=73)
        self.encoded=base64.b64encode(token.encode(self.original)).decode()

    def test_each_foreign_token_has_valid_checksum_and_only_one_identity_change(self):
        values=e.variants(self.encoded)
        for label,field in (('group','groupId'),('history','historyId'),('manifest','manifestDigest')):
            candidate=token.decode(base64.b64decode(values[label]['minimum']))
            self.assertEqual([field],[k for k in self.original if candidate[k]!=self.original[k]])
            self.assertEqual('INCOMPATIBLE_HISTORY',values[label]['reason'])
        maximum=token.decode(base64.b64decode(values['maximum-index']['minimum']))
        self.assertEqual(dict(self.original,index=(1<<63)-1),maximum)

    def test_invalid_version_and_reserved_bits_recompute_checksum_before_rejection(self):
        values=e.variants(self.encoded)
        for label in ('version','reserved','trailing','checksum'):
            raw=base64.b64decode(values[label]['minimum'])
            if label in ('version','reserved'):self.assertEqual(raw[80:],hashlib.sha256(token.DOMAIN+raw[:80]).digest())
            with self.subTest(label=label),self.assertRaisesRegex(ValueError,'^'+values[label]['reason']+'$'):token.decode(raw)

    def test_accidentally_unchanged_identity_fixture_fails_instead_of_claiming_rejection(self):
        original=dict(self.original,historyId='33333333-3333-3333-3333-333333333333')
        with self.assertRaisesRegex(ValueError,'identity fixture collision'):
            e.variants(base64.b64encode(token.encode(original)).decode())


if __name__=='__main__':unittest.main()
