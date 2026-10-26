import copy
import hashlib
import struct
import unittest
from . import peer_retention_evidence as e


class PeerRetentionEvidenceTest(unittest.TestCase):
    def value(self):
        return dict(root='a'*64, owner={}, revision=0, previous=None, plan=dict(root='a'*64))

    def test_every_prefix_and_wrong_protocol_refused(self):
        raw = e.frame(self.value())
        self.assertEqual(self.value(), e.decode(raw))
        for n in range(len(raw)):
            with self.assertRaises(ValueError):e.decode(raw[:n])
        for offset in (0, 4, 6, 11, 12, len(raw)-1):
            changed = bytearray(raw);changed[offset] ^= 1
            with self.assertRaises(ValueError):e.decode(changed)

    def test_canonical_fields_counter_and_root_are_required(self):
        for field, value in [('revision', True), ('revision', -1), ('revision', 2**63-1),
                             ('previous', 'f'*64), ('unknown', 0), ('root', 'b'*64)]:
            changed = copy.deepcopy(self.value());changed[field] = value
            with self.assertRaises(ValueError):e.decode(e.frame(changed))

    def test_duplicate_keys_cannot_hide_prior_revision(self):
        raw = e.frame(self.value());body = raw[44:].replace(b'"revision":0', b'"revision":1,"revision":0')
        envelope = struct.pack('>IHHI', 0x47535052, 1, 3, 44+len(body))+hashlib.sha256(body).digest()+body
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):e.decode(envelope)

    def test_missing_original_is_not_negative_success(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'complete retention crash matrix'):e.qualify(temp)


if __name__ == '__main__':unittest.main()
