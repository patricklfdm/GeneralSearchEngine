"""Fail closed on unqualified scope, absent originals and invalid resource rows."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import joint_floor_recovery_evidence as r


class JointFloorRecoveryEvidenceTest(unittest.TestCase):
    def test_missing_empty_and_linked_originals_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'empty').mkdir(); (root/'link').symlink_to(root/'empty', target_is_directory=True)
            for path in (root/'missing', root/'empty', root/'link'):
                with self.subTest(path=path), self.assertRaises(ValueError): r.validate(path)

    def test_component_cannot_claim_phase_or_process_death(self):
        with tempfile.TemporaryDirectory() as tmp:
            side = Path(tmp)/'joint-floor-recovery'; side.mkdir()
            for name in r.FILES:
                if name != 'receipt.json': (side/name).touch()
            for field, value in [('phase3Complete', True), ('processDeath', True), ('sameDirectory', 1)]:
                r.h.save(side/'receipt.json', dict(r.SCOPE, **{field: value}))
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'bounded scope'): r.validate(tmp)

    def test_resources_require_actual_integer_counts_and_full_charge(self):
        valid = dict(event='FLOOR_BEFORE_RETURN', usage=dict(metadata=1024, staging=2048, queued=0, leases=12,
                                                         counts=dict(APPLICATION=7, SOURCE=5)))
        r.bounded([valid], 7, 5)
        import copy
        for kind in ('boolean', 'overflow', 'headroom', 'leases'):
            row = copy.deepcopy(valid)
            if kind == 'boolean': row['usage']['counts']['SOURCE'] = True
            elif kind == 'overflow': row['usage']['staging'] = 512*1024**2+1
            elif kind == 'headroom': row['usage']['counts']['APPLICATION'] = 6; row['usage']['leases'] = 11
            else: row['usage']['leases'] = 13
            with self.subTest(kind=kind), self.assertRaises(ValueError): r.bounded([row], 7, 5)

    def test_original_failure_cannot_become_successful_mutations(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(r, 'validate', side_effect=ValueError('invalid original')), patch.object(r.shutil, 'copytree') as copied:
            with self.assertRaisesRegex(ValueError, 'invalid original'): r.qualify(tmp)
            copied.assert_not_called()

    def test_unrelated_negative_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            side = Path(tmp)/'joint-floor-recovery'; side.mkdir(); r.h.save(side/'receipt.json', r.SCOPE)
            with patch.object(r, 'validate', side_effect=[{}, ValueError('unrelated')]), self.assertRaisesRegex(ValueError, 'unrelated rejection'):
                r.qualify(tmp)

    def test_unknown_mutation_refuses(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, 'declared mutation'):
            r.mutate(Path(tmp), 'unknown')

    def test_history_uses_per_message_budget_and_rejects_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'events.json'
            rows = [{'event': 'retained', 'bytes': 'x'*1024} for _ in range(1200)]
            r.h.save(path, rows)
            self.assertEqual(rows, r.read(path))
            path.write_text('{"event":"retained","event":"changed"}')
            with self.assertRaisesRegex(ValueError, 'duplicate JSON key'): r.read(path)
