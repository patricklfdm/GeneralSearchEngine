import hashlib
import json
from pathlib import Path
import unittest

from scripts.v50.wire_fixture import HEADER, encode, inspect, validate_fixture


FIXTURE = Path(__file__).resolve().parents[2] / (
    "general-search-engine-replication/src/test/resources/replication/v50-wire-fixtures.json")


class WireFixtureTest(unittest.TestCase):
    def setUp(self):
        self.case = json.loads(FIXTURE.read_text())["cases"][0]
        self.frame = bytes.fromhex(self.case["hex"])

    def test_golden_bytes_and_every_message_family_are_stable(self):
        validate_fixture(FIXTURE)

    def test_truncated_corrupt_oversized_unknown_and_trailing_frames_fail_closed(self):
        changed_version = bytearray(self.frame)
        changed_version[5] = 2
        changed_digest = bytearray(self.frame)
        changed_digest[20] ^= 1
        oversized = HEADER.pack(b"GSRP", 1, 0, 1, 0, 0xffffffff) + b"0" * 32
        for frame in (self.frame[:47], self.frame[:-1], self.frame + b"x",
                      bytes(changed_version), bytes(changed_digest), oversized):
            with self.subTest(length=len(frame)), self.assertRaises(ValueError):
                inspect(frame)

    def test_valid_checksum_cannot_hide_missing_identity_or_noncanonical_json(self):
        for remove_identity in (False, True):
            envelope = dict(self.case["envelope"])
            if remove_identity:
                del envelope["incarnationId"]
            body = json.dumps(envelope).encode()
            header = HEADER.pack(b"GSRP", 1, 0, 1, 0, len(body))
            frame = header + hashlib.sha256(header + body).digest() + body
            with self.assertRaises(ValueError):
                inspect(frame)

    def test_invalid_counter_type_unknown_fields_and_deep_payload_fail_before_encoding(self):
        for field, value in (("epoch", True), ("eventSequence", 1 << 63),
                             ("sender", ""), ("payload", {"bad": 1.5})):
            envelope = dict(self.case["envelope"])
            envelope[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                encode(envelope)
        payload = {}
        for _ in range(20):
            payload = {"next": payload}
        envelope = dict(self.case["envelope"], payload=payload)
        with self.assertRaises(ValueError):
            encode(envelope)
