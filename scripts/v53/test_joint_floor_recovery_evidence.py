"""Fail closed on unqualified scope, absent originals and invalid resource rows."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import joint_floor_recovery_evidence as r


class JointFloorRecoveryEvidenceTest(unittest.TestCase):
    def test_connection_replies_require_original_socket_pair_and_delivery(self):
        from .test_connection_transcript import trace, overlap
        events, rows, ids, root = trace()
        r.delivered_replies(rows, events, ids, root, {events[0]['request']})
        # The parent observes NETWORK_* while a resumed child is scoped.
        # The legacy-named delivery deliberately carries no request hash.
        for row in events:
            row.pop('scope')
            if row['event']==r.joining_connections.t.SEND:row['event']='NETWORK_SEND'
            elif row['event']==r.joining_connections.t.READ:row['event']='NETWORK_REQUEST'
            elif row['event']==r.joining_connections.t.OFFER:
                row['event']='WIRE_RESPONSE';row.pop('kind');row.pop('responseKind')
            elif row['event']==r.joining_connections.t.DELIVER:
                row['event']='NETWORK_RECEIVED';row['kind']=row.pop('responseKind');row.pop('request')
        r.delivered_replies(rows, events, ids, root, {events[0]['request']})
        for change in ('missing', 'foreign', 'withheld', 'delivery', 'mixed'):
            events, rows, ids, root = trace()
            if change == 'missing': del rows[0]['connection']
            elif change == 'foreign': rows[0]['connection']['remote']['port'] += 1
            elif change == 'withheld': rows[0]['withheld'] = True
            elif change == 'delivery': events.pop()
            else: rows.append({k: v for k, v in rows[0].items() if k != 'connection'})
            with self.subTest(change=change), self.assertRaises(ValueError):
                r.delivered_replies(rows, events, ids, root, {events[0]['request']})
        events, rows, ids, root = overlap()
        with self.assertRaisesRegex(ValueError, 'joint floor delivered original replies'):
            r.delivered_replies(rows, events, ids, root, {events[0]['request']})

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
