"""Independent journal witnesses reject torn, forgotten and reused promises."""
from pathlib import Path
import tempfile
import unittest
from . import public_promise_evidence as evidence, storage_fixture as fixture


class PublicPromiseEvidenceTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.frames = fixture.create(self.root)
        encoded = (self.root/'node-1/manifest.gsr').read_bytes()
        self.manifest = dict(evidence.a.f.inspect(encoded, 'MANIFEST'), digest=encoded[16:48].hex())
        self.initial = (self.root/'node-1/promises.gsr').read_bytes()
        self.written = self.initial+self.frames['PROMISE']
        self.later = self.written+fixture.records(encoded, epoch=5)['PROMISE']

    def inspect(self, data, node='node-1'):
        return evidence.journal(data, self.manifest, node)

    def test_complete_journals_keep_exact_monotonic_ballots(self):
        self.assertEqual([1, 2, 5], [r['epoch'] for _, r in self.inspect(self.later)])
        self.assertEqual(self.frames['PROMISE'], self.inspect(self.written)[-1][0])

    def test_complete_bytes_do_not_by_themselves_claim_a_force(self):
        evidence.extension(self.initial, self.written, self.later, True)
        evidence.extension(self.initial, self.initial, self.later, False)
        with self.assertRaisesRegex(ValueError, 'write boundary'):
            evidence.extension(self.initial, self.written, self.later, False)

    def test_header_and_body_truncations_are_rejected_without_repair(self):
        for suffix in (b'x', self.frames['PROMISE'][:47], self.frames['PROMISE'][:-1]):
            with self.subTest(size=len(suffix)), self.assertRaisesRegex(ValueError, 'torn'):
                self.inspect(self.initial+suffix)

    def test_duplicate_and_backwards_complete_promises_are_rejected(self):
        for data in (self.written+self.frames['PROMISE'], self.later+self.frames['PROMISE']):
            with self.subTest(size=len(data)), self.assertRaisesRegex(ValueError, 'reused epoch'): self.inspect(data)

    def test_mismatched_voter_and_metadata_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'journal identity'): self.inspect(self.initial, 'node-2')
        with self.assertRaises(ValueError): self.inspect((self.root/'node-1/accepted.gsr').read_bytes())

    def test_corrupt_payload_and_oversized_frame_are_rejected(self):
        data = bytearray(self.written); data[-2] ^= 1
        with self.assertRaises(ValueError): self.inspect(bytes(data))
        data = bytearray(self.initial); data[12:16] = (1 << 20).to_bytes(4, 'big')
        with self.assertRaisesRegex(ValueError, 'oversized'): self.inspect(bytes(data))

    def test_missing_initial_promise_is_rejected(self):
        header_size = 48+int.from_bytes(self.initial[12:16], 'big')
        for data in (b'', self.initial[:header_size], self.initial[:header_size]+self.frames['PROMISE']):
            with self.subTest(size=len(data)), self.assertRaises(ValueError): self.inspect(data)

    def test_missing_or_rewritten_pre_crash_prefix_is_rejected(self):
        for saved, final in ((self.initial, self.later), (self.written, self.initial),
                             (b'changed'+self.written, self.later), (self.written, b'changed'+self.later)):
            with self.subTest(saved=len(saved), final=len(final)), self.assertRaises(ValueError):
                evidence.extension(self.initial, saved, final, True)


if __name__ == '__main__': unittest.main()
