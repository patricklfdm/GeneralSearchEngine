"""Independent journal framing and exact surviving cleanup-inventory rejection tests."""
import json
from pathlib import Path
import struct
import tempfile
import unittest
from . import offline_format as oracle
from . import admission_format as f


class OfflineFormatTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.operation = self.root / 'operation'; self.operation.mkdir()
        self.target = self.root / 'node-1'; self.target.mkdir()
        self.source = self.root / 'source'; self.source.mkdir()
        self.plan = bytes.fromhex('11' * 32)
        self.row = self.journal(1, 1, f.ZERO)
        (self.operation / 'operation.gsr').write_bytes(self.row)
        (self.operation / 'operation.lock').write_bytes(b'')
        (self.target / 'owned').write_bytes(b'owned')
        (self.source / 'protected').write_bytes(b'protected')
        inventory = []
        for directory, owner in ((self.operation, self.plan.hex()), (self.target, self.plan.hex()), (self.source, 'source')):
            for path in [directory, *directory.iterdir()]:
                data = path.read_bytes() if path.is_file() else b''
                inventory.append(dict(path=str(path), owner=owner, kind='file' if path.is_file() else 'directory',
                                      size=len(data), digest=f.sha(data).hex() if path.is_file() else f.ZERO.hex()))
        inventory.sort(key=lambda e: e['path'].encode())
        self.descriptor = dict(operation=dict(path=str(self.operation), parentRealPath=str(self.root), fileStoreName='test',
                                             fileStoreType='ext4', parentFileKey='test-key'), inventory=inventory,
                               deletePaths=list(map(str, (self.target / 'owned', self.target, self.operation / 'operation.gsr',
                                                         self.operation / 'operation.lock', self.operation))))
        self.save()

    def journal(self, sequence, phase, previous):
        return f.framed(21, self.plan + struct.pack('>q', sequence) + previous + bytes([phase]) + f.ZERO * 4)

    def save(self):
        (self.operation / 'cleanup.gsr').write_bytes(f.framed(22, self.plan + self.row[16:48] + f.blob(f.canonical(self.descriptor))))

    def test_journal_framing_rejects_torn_checksum_and_broken_predecessor(self):
        self.assertEqual(1, oracle.rows(self.row)[0]['phase'])
        for damaged in (self.row[:-1], self.row + b'x', self.row[:-1] + b'\1', self.row + self.journal(2, 2, f.ZERO)):
            with self.subTest(size=len(damaged)), self.assertRaises(ValueError):
                oracle.rows(damaged)

    def test_cleanup_before_and_after_forced_abort_preserves_bytes(self):
        before = oracle.files(self.root)
        self.assertEqual(0, oracle.cleanup(self.root)['deletedPrefix'])
        self.assertEqual(before, oracle.files(self.root))
        (self.operation / 'operation.gsr').write_bytes(self.row + self.journal(2, 5, self.row[16:48]))
        (self.target / 'owned').unlink()
        self.assertEqual(1, oracle.cleanup(self.root)['deletedPrefix'])

    def test_cleanup_rejects_unknown_member(self):
        (self.target / 'foreign').write_bytes(b'foreign')
        with self.assertRaisesRegex(ValueError, 'unknown cleanup member'): oracle.cleanup(self.root)

    def test_cleanup_rejects_changed_protected_source(self):
        (self.source / 'protected').write_bytes(b'different')
        with self.assertRaisesRegex(ValueError, 'cleanup bytes changed'): oracle.cleanup(self.root)

    def test_cleanup_rejects_nonprefix_deletion(self):
        (self.operation / 'operation.lock').unlink()
        with self.assertRaisesRegex(ValueError, 'non-prefix'): oracle.cleanup(self.root)

    def test_cleanup_cannot_delete_protected_source(self):
        self.descriptor['deletePaths'].insert(0, str(self.source / 'protected')); self.save()
        with self.assertRaisesRegex(ValueError, 'ownership'): oracle.cleanup(self.root)

    def test_cleanup_rejects_parent_before_child(self):
        self.descriptor['deletePaths'][:2] = reversed(self.descriptor['deletePaths'][:2]); self.save()
        with self.assertRaisesRegex(ValueError, 'dependency'): oracle.cleanup(self.root)

    def test_cleanup_rejects_commit_to_abort_transition(self):
        (self.operation / 'operation.gsr').write_bytes(self.journal(1, 3, f.ZERO) + self.journal(2, 5, self.journal(1, 3, f.ZERO)[16:48]))
        with self.assertRaisesRegex(ValueError, 'abort decision'): oracle.cleanup(self.root)


if __name__ == '__main__':
    unittest.main()
