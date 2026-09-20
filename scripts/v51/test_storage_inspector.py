"""Negative oracle witnesses alter actual authority bytes and causal force events."""
import tempfile
from pathlib import Path
import unittest

from .storage_fixture import create, records
from .storage_inspector import inspect, inventory
from .storage_harness import force_order, bind_events


class StorageInspectorTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.records = create(self.root); self.node = self.root / 'node-1'

    def append(self, kind, value=None):
        name = {'PROMISE': 'promises.gsr', 'ACCEPT': 'accepted.gsr', 'PROOF': 'proofs.gsr'}[kind]
        with (self.node / name).open('ab') as stream: stream.write(self.records[kind] if value is None else value)

    def test_genesis_accepted_and_proven_states_have_independent_cuts(self):
        self.assertEqual((1, 0, 0), self.positions())
        self.append('PROMISE'); self.append('ACCEPT')
        self.assertEqual((2, 1, 0), self.positions())
        self.append('PROOF'); before = inventory(self.node)
        report = inspect(self.node)
        self.assertEqual((2, 1, 1), self.positions()); self.assertEqual(1, report['applicationSequence'])
        self.assertEqual(before, inventory(self.node))

    def positions(self):
        v = inspect(self.node); return v['promisedEpoch'], v['acceptedThrough'], v['provenThrough']

    def test_removing_promise_or_acceptance_cannot_leave_a_valid_proof(self):
        self.append('PROMISE'); self.append('ACCEPT'); self.append('PROOF')
        for name, kind in [('promises.gsr', 'PROMISE'), ('accepted.gsr', 'ACCEPT')]:
            with self.subTest(name=name):
                path = self.node / name; data = path.read_bytes(); path.write_bytes(data[:-len(self.records[kind])])
                before = inventory(self.node)
                with self.assertRaises(ValueError): inspect(self.node)
                self.assertEqual(before, inventory(self.node)); path.write_bytes(data)

    def test_complete_rechecksummed_conflicting_acceptance_is_rejected(self):
        self.append('PROMISE'); self.append('ACCEPT')
        other = records((self.node / 'manifest.gsr').read_bytes(), epoch=5, payload=b'conflict')
        self.append('PROMISE', other['PROMISE']); self.append('ACCEPT', other['ACCEPT'])
        with self.assertRaisesRegex(ValueError, 'conflicting acceptance'): inspect(self.node)

    def test_same_value_can_be_carried_with_new_acceptance_ballot(self):
        self.append('PROMISE'); self.append('ACCEPT')
        other = records((self.node / 'manifest.gsr').read_bytes(), epoch=5)
        for kind in ('PROMISE', 'ACCEPT', 'PROOF'): self.append(kind, other[kind])
        self.assertEqual((5, 1, 1), self.positions())

    def test_duplicate_complete_records_and_partial_records_are_not_silently_trimmed(self):
        self.append('PROMISE'); path = self.node / 'promises.gsr'; original = path.read_bytes()
        for suffix in (self.records['PROMISE'], self.records['PROMISE'][:7]):
            path.write_bytes(original + suffix); before = inventory(self.node)
            with self.assertRaises(ValueError): inspect(self.node)
            self.assertEqual(before, inventory(self.node))

    def test_sealed_inventory_is_required_and_cannot_be_copied_to_new_path(self):
        import shutil
        clone = self.root / 'copied'; shutil.copytree(self.node, clone)
        with self.assertRaisesRegex(ValueError, 'seal path'): inspect(clone)
        (self.node / 'selected.gsr').write_bytes(b'future phase')
        with self.assertRaises(ValueError): inspect(self.node)

    def test_force_removal_wrong_process_and_wrong_record_invalidate_ack(self):
        forced = dict(node='node-1', pid=42, recordSha256='a'*64, stage='ACCEPT_AFTER_FORCE')
        ack = dict(forced, stage='ACCEPT_ACK')
        force_order([forced, ack])
        for rows in ([ack], [ack, forced], [dict(forced, pid=43), ack], [dict(forced, recordSha256='b'*64), ack]):
            with self.assertRaisesRegex(ValueError, 'earlier force'): force_order(rows)

    def test_force_must_reference_actual_retained_record_bytes(self):
        from .storage_fixture import sha
        self.append('PROMISE')
        event = dict(node='node-1', pid=42, stage='PROMISE_AFTER_FORCE', recordSha256=sha(self.records['PROMISE']))
        bind_events(self.root, [event])
        with self.assertRaisesRegex(ValueError, 'absent from retained'):
            bind_events(self.root, [dict(event, recordSha256='f'*64)])


if __name__ == '__main__': unittest.main()
