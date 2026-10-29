"""Small portable-copy parser tests; none are native learner qualification."""
import copy
from pathlib import Path
import shutil
import tempfile
import unittest
from . import learner_slot_snapshot as s


class LearnerSlotSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'raw'; self.root.mkdir()
        self.ids = {}
        for name in sorted(s.ROOTS):
            present = name in ('operation', 'replica', 'seed', 'slots', 'slot-typed')
            members = {'.': dict(key=name + '-directory-original', directory=True)} if present else {}
            if present:
                path = self.root / name; path.mkdir(); (path / 'record').write_bytes(name.encode())
                members['record'] = dict(key=name + '-file-original', bytes=len(name), sha256=s.digest(name.encode()))
            self.ids[name] = dict(path='/unavailable-original-learner/' + name, present=present, members=members)
        self.usage = dict(counts=dict(MISC=1, GENERATION=1, APPLICATION=2), leases=4, metadata=2097252, staging=100, queued=0)
        self.save()

    def save(self):
        (self.root / 'original-identities.json').write_bytes(s.f.canonical(self.ids))
        (self.root / 'resources.json').write_bytes(s.f.canonical(self.usage))

    def test_relocated_copy_uses_recorded_original_identity_and_never_claims_native_acceptance(self):
        other = Path(self.temp.name) / 'download'; shutil.copytree(self.root, other)
        old = (self.root / 'slots/record').stat().st_ino; new = (other / 'slots/record').stat().st_ino
        self.assertNotEqual(old, new)
        actual = s.read(other).fingerprints('slots', ['record', '.'])
        expected = [dict(path=p, sha256=s.digest(s.f.canonical(self.ids['slots']['members'][p]))) for p in ('.', 'record')]
        self.assertEqual(expected, actual)
        self.assertEqual(s.validate(self.root), s.validate(other))
        self.assertEqual('PARTIAL', s.validate(other)['status'])
        self.assertFalse(s.validate(other)['selectedHeadQualified'])

    def test_changed_copied_bytes_are_rejected(self):
        (self.root / 'slots/record').write_bytes(b'wrong')
        with self.assertRaisesRegex(ValueError, '^learner snapshot original bytes$'): s.read(self.root)

    def test_missing_or_extra_copied_members_are_rejected(self):
        for extra in (False, True):
            with self.subTest(extra=extra):
                path = self.root / 'slots' / ('foreign' if extra else 'record')
                if extra: path.write_bytes(b'x')
                else: path.unlink()
                with self.assertRaisesRegex(ValueError, '^learner snapshot copied inventory$'): s.read(self.root)
                if extra: path.unlink()
                else: path.write_bytes(b'slots')

    def test_absent_roots_cannot_hide_retained_files(self):
        (self.root / 'seed-typed').mkdir()
        with self.assertRaisesRegex(ValueError, '^learner snapshot exact layout$'): s.read(self.root)

    def test_false_absence_with_members_is_rejected(self):
        self.ids['slots']['present'] = False; self.save()
        with self.assertRaisesRegex(ValueError, '^learner snapshot absent root has members$'): s.read(self.root)

    def test_traversal_and_overlapping_original_roots_are_rejected(self):
        original = copy.deepcopy(self.ids)
        for path, reason in [('/a/../b', 'original path'), ('/unavailable-original-learner/seed', 'overlapping original roots')]:
            with self.subTest(path=path):
                self.ids['slots']['path'] = path; self.save()
                with self.assertRaisesRegex(ValueError, '^learner snapshot ' + reason + '$'): s.read(self.root)
                self.ids = copy.deepcopy(original)

    def test_recorded_inode_alias_is_rejected(self):
        self.ids['slots']['members']['record']['key'] = self.ids['seed']['members']['record']['key']; self.save()
        with self.assertRaisesRegex(ValueError, '^learner snapshot original inode alias$'): s.read(self.root)

    def test_symlinks_and_hardlinks_are_rejected(self):
        path = self.root / 'slots/record'; path.unlink(); path.symlink_to(self.root / 'seed/record')
        with self.assertRaisesRegex(ValueError, '^learner snapshot copied inventory$'): s.read(self.root)
        path.unlink(); path.hardlink_to(self.root / 'seed/record')
        with self.assertRaisesRegex(ValueError, '^learner snapshot regular member$'): s.read(self.root)

    def test_resources_cannot_claim_unbounded_or_unaccounted_ownership(self):
        original = copy.deepcopy(self.usage)
        changes = [('counts', dict(GENERATION=3), 'resource counts'), ('leases', 3, 'resource leases'),
                   ('staging', 512 * s.e.MIB + 1, 'resource bytes'), ('metadata', True, 'resource bytes')]
        for field, value, reason in changes:
            with self.subTest(field=field):
                self.usage = dict(copy.deepcopy(original), **{field: value}); self.save()
                with self.assertRaisesRegex(ValueError, '^learner snapshot ' + reason + '$'): s.read(self.root)

    def test_missing_fingerprint_member_cannot_be_ignored(self):
        with self.assertRaisesRegex(ValueError, '^learner snapshot fingerprint roots/paths$'):
            s.read(self.root).fingerprints('slots', ['unknown'])

    def test_malformed_original_directory_is_a_typed_refusal(self):
        self.ids['slots']['members']['.'] = False; self.save()
        with self.assertRaisesRegex(ValueError, '^learner snapshot original root directory$'): s.read(self.root)


if __name__ == '__main__': unittest.main()
