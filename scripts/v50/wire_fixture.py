"""Independent wire-envelope fixture codec. Never opens a socket or product store."""

import hashlib
import json
import re
import struct
import uuid
from pathlib import Path


HEADER = struct.Struct(">4sHHHHI")
HEADER_BYTES = HEADER.size + 32
DEFAULT_MAX_FRAME_BYTES = 8 * 1024 * 1024
HARD_MAX_FRAME_BYTES = 64 * 1024 * 1024
MESSAGE_TYPES = (
    "HANDSHAKE", "ACTIVATION_PROMISE", "APPEND", "DURABLE_ACK", "COMMIT_PROOF",
    "COMMIT_PROOF_ACK", "COMMIT_ADVANCE", "CONFLICT", "AUTHORITY_STATUS_PROBE",
    "SNAPSHOT_OFFER", "SNAPSHOT_CHUNK", "SNAPSHOT_INSTALL", "ACTIVATE_EPOCH",
    "AUTHORITY_STATUS", "SNAPSHOT_ABORT", "REJECT",
)
FIELDS = {"protocol", "groupId", "configurationId", "sender", "recipient", "epoch",
          "incarnationId", "traceId", "eventSequence", "type", "payload"}


def _bounded_json(value, depth=0):
    if depth > 16:
        raise ValueError("wire nesting exceeds bound")
    if value is None or type(value) in (str, bool):
        return
    if type(value) is int and -(1 << 63) <= value < (1 << 63):
        return
    if isinstance(value, list):
        for item in value:
            _bounded_json(item, depth + 1)
        return
    if isinstance(value, dict) and all(re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", key) for key in value):
        for item in value.values():
            _bounded_json(item, depth + 1)
        return
    raise ValueError("unsupported wire JSON type/key/number")


def _validate(envelope):
    if not isinstance(envelope, dict) or set(envelope) != FIELDS:
        raise ValueError("wire envelope fields are not exact")
    if envelope["protocol"] != "gse-replication/1.0" or envelope["type"] not in MESSAGE_TYPES:
        raise ValueError("unknown protocol or message type")
    for name in ("groupId", "incarnationId", "traceId"):
        if not isinstance(envelope[name], str) or str(uuid.UUID(envelope[name])) != envelope[name]:
            raise ValueError("wire UUID must be canonical")
    for name in ("configurationId", "sender", "recipient"):
        if not isinstance(envelope[name], str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", envelope[name]):
            raise ValueError("invalid wire member/configuration identity")
    for name in ("epoch", "eventSequence"):
        if type(envelope[name]) is not int or not 0 <= envelope[name] < (1 << 63):
            raise ValueError("wire counter outside signed 64-bit range")
    if envelope["epoch"] == 0 and envelope["type"] not in {"HANDSHAKE", "REJECT"}:
        raise ValueError("zero epoch is only valid before activation")
    if not isinstance(envelope["payload"], dict):
        raise ValueError("wire payload must be an object")
    _bounded_json(envelope)


def encode(envelope: dict) -> bytes:
    _validate(envelope)
    body = json.dumps(envelope, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")
    if HEADER_BYTES + len(body) > DEFAULT_MAX_FRAME_BYTES:
        raise ValueError("frame capacity exceeded")
    prefix = HEADER.pack(b"GSRP", 1, 0, MESSAGE_TYPES.index(envelope["type"]) + 1, 0, len(body))
    return prefix + hashlib.sha256(prefix + body).digest() + body


def inspect(frame: bytes, maximum=DEFAULT_MAX_FRAME_BYTES) -> dict:
    if type(maximum) is not int or not HEADER_BYTES <= maximum <= HARD_MAX_FRAME_BYTES:
        raise ValueError("invalid frame limit")
    if len(frame) < HEADER_BYTES:
        raise ValueError("incomplete frame header")
    prefix, checksum, body = frame[:16], frame[16:48], frame[48:]
    magic, major, minor, message_type, flags, length = HEADER.unpack(prefix)
    if magic != b"GSRP" or (major, minor) != (1, 0) or flags != 0:
        raise ValueError("unsupported frame family/version/flags")
    if not 1 <= message_type <= len(MESSAGE_TYPES):
        raise ValueError("unknown message type")
    if length + HEADER_BYTES > maximum:
        raise ValueError("frame capacity exceeded")
    if len(body) != length:
        raise ValueError("incomplete frame or trailing bytes")
    if hashlib.sha256(prefix + body).digest() != checksum:
        raise ValueError("frame integrity failure")
    try:
        envelope = json.loads(body)
        _validate(envelope)
    except (TypeError, KeyError, UnicodeError, RecursionError) as error:
        raise ValueError("invalid wire envelope") from error
    if envelope["type"] != MESSAGE_TYPES[message_type - 1]:
        raise ValueError("header/envelope type mismatch")
    canonical = json.dumps(envelope, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True, allow_nan=False).encode("ascii")
    if body != canonical:
        raise ValueError("noncanonical wire body")
    return envelope


def validate_fixture(path: Path) -> None:
    document = json.loads(path.read_text())
    if document["schemaVersion"] != "gse-v50-wire-fixtures-v1":
        raise ValueError("unsupported wire fixture")
    if document["messageTypes"] != {name: i for i, name in enumerate(MESSAGE_TYPES, 1)}:
        raise ValueError("wire message registry changed")
    for case in document["cases"]:
        frame = bytes.fromhex(case["hex"])
        if encode(case["envelope"]) != frame or inspect(frame) != case["envelope"]:
            raise ValueError("wire golden bytes changed")


if __name__ == "__main__":
    validate_fixture(Path("general-search-engine-replication/src/test/resources/replication/v50-wire-fixtures.json"))
    print("v50WireFixtures=PASS transport=java21-nio fixtureNetworking=disabled")
