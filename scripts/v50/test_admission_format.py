"""Frozen 1.1 projections, independently inspected without Java or production codecs."""
import hashlib
import json
from pathlib import Path
import unittest
from . import admission_format as oracle

FIXTURE = Path(__file__).resolve().parents[2] / 'general-search-engine-replication/src/test/resources/replication/v50-admission-fixtures-v2.json'


class AdmissionFormatTest(unittest.TestCase):
    def test_frozen_positive_and_negative_bytes(self):
        valid = rejected = 0
        for case, files in oracle.cases(FIXTURE):
            with self.subTest(case=case['name']):
                before = {name: hashlib.sha256(raw).digest() for name, raw in files.items()}
                if case['valid']:
                    self.assertEqual(case['expected'], oracle.validate(files))
                    valid += 1
                else:
                    with self.assertRaises((ValueError, KeyError, UnicodeError)):
                        oracle.validate(files)
                    rejected += 1
                self.assertEqual(before, {name: hashlib.sha256(raw).digest() for name, raw in files.items()})
        self.assertEqual(5, valid)
        self.assertEqual(48, rejected)

    def test_checksum_inventory_freezes_every_fixture_byte(self):
        checks = FIXTURE.with_suffix('.sha256').read_text().splitlines()
        self.assertEqual(1, len(checks))
        expected, name = checks[0].split()
        self.assertEqual(FIXTURE.name, name)
        self.assertEqual(expected, hashlib.sha256(FIXTURE.read_bytes()).hexdigest())

    def test_history_derivation_and_application_control_offset(self):
        for case, files in oracle.cases(FIXTURE):
            if not case['valid']:
                continue
            result = oracle.validate(files)
            base = result['baseSequence']
            self.assertEqual([base, base + 1, base + 1, base + 1], result['snapshotSequences'])
            self.assertNotEqual('33333333-3333-3333-3333-333333333333', result['applicationHistory'])


if __name__ == '__main__':
    unittest.main()
