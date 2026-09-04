from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.v42.storage_format_v11 import (
    StorageFormatError,
    fixture,
    inspect_backup,
    inspect_store,
    load_hex_fixture,
)


class StorageFormatV11Test(unittest.TestCase):
    ROOT = Path("src/test/resources/compatibility/v42-storage-v11")

    def test_frozen_bytes_match_independent_encoder(self) -> None:
        expected = fixture()
        frozen = load_hex_fixture(self.ROOT)
        self.assertEqual(expected.live, frozen.live)
        self.assertEqual(expected.backup, frozen.backup)
        self.assertEqual(expected.profile_sha256, frozen.profile_sha256)
        self.assertEqual(expected.backup_identity, frozen.backup_identity)

    def test_exact_live_and_backup_inventories_validate(self) -> None:
        frozen = load_hex_fixture(self.ROOT)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            live = root / "live"
            backup = root / "backup"
            live.mkdir()
            backup.mkdir()
            for name, value in frozen.live.items():
                (live / name).write_bytes(value)
            for name, value in frozen.backup.items():
                (backup / name).write_bytes(value)
            self.assertEqual("VALID", inspect_store(live)["status"])
            result = inspect_backup(backup)
            self.assertEqual("VALID", result["status"])
            self.assertEqual(frozen.backup_identity, result["contentIdentity"])

    def test_profile_binding_payload_and_inventory_tampering_fail_closed(self) -> None:
        frozen = load_hex_fixture(self.ROOT)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            live = root / "live"
            backup = root / "backup"
            live.mkdir()
            backup.mkdir()
            for name, value in frozen.live.items():
                (live / name).write_bytes(value)
            for name, value in frozen.backup.items():
                (backup / name).write_bytes(value)
            wal = live / "gse-wal-00000000000000000002.log"
            changed = bytearray(wal.read_bytes())
            changed[40] ^= 1
            wal.write_bytes(changed)
            with self.assertRaises(StorageFormatError):
                inspect_store(live)
            (backup / "unexpected").write_text("x", encoding="ascii")
            with self.assertRaises(StorageFormatError):
                inspect_backup(backup)


if __name__ == "__main__":
    unittest.main()
