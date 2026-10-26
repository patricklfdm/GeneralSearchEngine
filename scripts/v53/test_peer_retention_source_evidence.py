import struct
import tempfile
import unittest
from . import peer_retention_source_evidence as e


class PeerRetentionSourceEvidenceTest(unittest.TestCase):
    def sample(self):
        promise = e.f.encode('records', 'PROMISE', dict(root='a'*64, view='b'*64,
            ballot=dict(counter=2, proposer='node-1', incarnation='00000000-0000-0000-0000-000000000001'),
            basisId='00000000-0000-0000-0000-000000000002'))
        state = e.r.frame(dict(root='a'*64, owner={}, revision=0, previous=None, plan=dict(root='a'*64)))
        return promise, state

    def test_exact_canonical_snapshot_and_every_truncated_prefix(self):
        promise, state = self.sample();raw = e.wrap(promise, state)
        self.assertEqual((promise, state), e.unwrap(raw))
        for n in range(len(raw)):
            with self.assertRaises(ValueError):e.unwrap(raw[:n])

    def test_checksum_protocol_extent_and_nested_state_are_checked(self):
        promise, state = self.sample();raw = e.wrap(promise, state)
        for offset in (0, 4, 6, 8, 15, 16, len(raw)-1):
            bad = bytearray(raw);bad[offset] ^= 1
            with self.assertRaises(ValueError):e.unwrap(bytes(bad))
        for offset in (48, 52+len(promise)):
            bad = bytearray(raw);bad[offset:offset+4] = struct.pack('>I', 2**31)
            bad[16:48] = bytes.fromhex(e.sha(bytes(bad[:16]+bad[48:])))
            with self.assertRaises(ValueError):e.unwrap(bytes(bad))
        bad = bytearray(state);bad[-1] ^= 1
        with self.assertRaisesRegex(ValueError, 'retention checksum'):e.unwrap(e.wrap(promise, bytes(bad)))

    def test_fence_without_basis_cannot_declare_capture(self):
        promise, state = self.sample();v = e.f.decode(promise, 'records', 'PROMISE');v['basisId'] = None
        with self.assertRaisesRegex(ValueError, 'capture promise'):
            e.unwrap(e.wrap(e.f.encode('records', 'PROMISE', v), state))

    def test_missing_original_is_not_a_negative_success(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'complete frozen capture matrix'):e.qualify(temp)


if __name__ == '__main__':unittest.main()
