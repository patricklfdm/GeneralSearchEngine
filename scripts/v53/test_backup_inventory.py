"""Whole-original capacity is explicit and shared across all retained evidence."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import bootstrap_replay_contract as policy
from . import joining_history_run as legacy
from . import maximum_transition_inventory as large
from . import test_bootstrap_replay_contract as routes
from . import required_four_resources as resources


class BackupInventoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def inventory(self):
        return policy.inventory(self.root, bootstrap_source=policy.BACKUP, wire_layout=policy.SEGMENTED)

    def test_ordinary_json_preserves_default_policy_and_call_shape(self):
        for source in (policy.EMPTY, policy.BACKUP):
            with patch.object(legacy, 'inventory', return_value={'original': True}) as old, \
                 patch.object(large, 'inventory') as expanded:
                self.assertEqual({'original': True}, policy.inventory(self.root, bootstrap_source=source))
                old.assert_called_once_with(self.root); expanded.assert_not_called()
        self.assertEqual(512*1024**2, legacy.inventory.__kwdefaults__['maximum'])

    def test_layout_is_never_selected_by_an_original_marker(self):
        (self.root/'receipt.json').write_text('{"wireLayout":"SEGMENTED_BACKUP"}')
        with patch.object(large, 'inventory') as expanded:
            policy.inventory(self.root, bootstrap_source=policy.BACKUP)
            expanded.assert_not_called()
        for source, layout in ((policy.EMPTY, policy.SEGMENTED), (policy.BACKUP, {'wireLayout': policy.SEGMENTED})):
            with patch.object(large, 'inventory') as expanded, patch.object(legacy, 'inventory') as old:
                with self.assertRaises(ValueError):policy.inventory(self.root, bootstrap_source=source, wire_layout=layout)
                expanded.assert_not_called(); old.assert_not_called()

    def test_all_complete_entry_points_check_original_capacity_before_decode(self):
        calls = [(routes.catalog.validate, ()), (routes.publication.validate, ()),
                 (routes.semantic.validate, ()), (routes.physical.validate, ()),
                 (routes.four_network.validate, ()), (routes.four_exports.validate, ()),
                 (routes.maintenance.validate, ()), (routes.ledgers.validate, ()),
                 (routes.resources.validate, ('5-REPLACE-required-four',)),
                 (routes.native.validate, ('5-REPLACE-required-four',))]
        for call, args in calls:
            with self.subTest(call=call), patch.object(large, 'inventory', side_effect=ValueError('whole original blocked')) as read:
                with self.assertRaisesRegex(ValueError, '^whole original blocked$'):
                    call(self.root, *args, bootstrap_source=policy.BACKUP, wire_layout=policy.SEGMENTED)
                read.assert_called_once_with(self.root, maximum=128*1024**3)
        with patch.object(large, 'inventory', side_effect=ValueError('whole original blocked')) as read:
            with self.assertRaisesRegex(ValueError, '^whole original blocked$'):
                resources.qualify_backup(self.root, wire_layout=policy.SEGMENTED)
            read.assert_called_once_with(self.root, maximum=128*1024**3)

    def test_cuts_segments_snapshots_and_metadata_share_one_total(self):
        names = ['segmented-wire/wire/segments/segment-1.jsonl', 'segmented-wire/wire/cuts/observed.json',
                 'segmented-wire/index.json', 'applied-1/node-1/application.gscp', 'events.json']
        for name in names:
            path = self.root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'1234')
        with patch.object(policy, 'ORIGINAL_BYTES', 20):
            result = self.inventory()
            self.assertEqual(20, result['bytes'])
            self.assertEqual({name:hashlib.sha256(b'1234').hexdigest() for name in names}, result['files'])
            (self.root/'unlisted').write_bytes(b'x')
            with self.assertRaisesRegex(ValueError, 'inventory byte bound'):self.inventory()

    def test_existing_member_count_depth_and_file_bounds_remain_effective(self):
        self.assertEqual((128*1024**3,256*1024**2,65536),
                         (policy.ORIGINAL_BYTES,large.FILE_LIMIT,large.MEMBERS))
        (self.root/'item').write_bytes(b'1234')
        with patch.object(large, 'FILE_LIMIT', 3), patch.object(large.os, 'open') as opened:
            with self.assertRaisesRegex(ValueError, 'inventory byte bound'):self.inventory()
            opened.assert_not_called()
        with patch.object(large, 'MEMBERS', 0), patch.object(large.os, 'open') as opened:
            with self.assertRaisesRegex(ValueError, 'inventory member bound'):self.inventory()
            opened.assert_not_called()
        parent = self.root
        for _ in range(65):parent = parent/'d'; parent.mkdir()
        with self.assertRaisesRegex(ValueError, 'inventory directory'):self.inventory()


if __name__ == '__main__':unittest.main()
