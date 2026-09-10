from __future__ import annotations

import copy
import unittest
from pathlib import Path

from scripts.v43.derived_format_v12 import (
    DerivedFormatError,
    fixture,
    inspect_backup,
    inspect_live,
    load_hex_fixture,
)


class DerivedFormatV12Test(unittest.TestCase):
    ROOT = Path("src/test/resources/compatibility/v43-derived-v12")

    def test_frozen_bytes_match_independent_encoder(self) -> None:
        self.assertEqual(fixture(), load_hex_fixture(self.ROOT))

    def test_live_derived_and_canonical_only_backup_validate(self) -> None:
        value = load_hex_fixture(self.ROOT)
        live = inspect_live(value.live)
        backup = inspect_backup(value.backup)
        self.assertEqual("VALID", live["status"])
        self.assertEqual(4, len(live["components"]))
        self.assertEqual(value.catalog_identity, live["identity"])
        self.assertEqual(value.backup_identity, backup["contentIdentity"])
        self.assertFalse(any(name.startswith("gse-derived-")
                             for name in value.backup))

    def test_catalog_component_and_backup_tampering_fail_closed(self) -> None:
        value = fixture()
        for member in ("gse-derived-manifest",
                       next(name for name in value.live
                            if name.startswith("gse-derived-index-"))):
            live = copy.deepcopy(value.live)
            changed = bytearray(live[member])
            changed[len(changed) // 2] ^= 1
            live[member] = bytes(changed)
            with self.assertRaises(DerivedFormatError):
                inspect_live(live)
        backup = copy.deepcopy(value.backup)
        changed = bytearray(backup["gse-backup-manifest"])
        changed[-1] ^= 1
        backup["gse-backup-manifest"] = bytes(changed)
        with self.assertRaises(DerivedFormatError):
            inspect_backup(backup)


if __name__ == "__main__":
    unittest.main()
