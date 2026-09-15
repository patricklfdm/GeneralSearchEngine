"""Independent gse-replicated (1,0) generator/inspector; no production imports."""

import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import re
import struct
import uuid


FILES = {"replica.lock", "manifest.gsr", "node.gsr", "promises.gsr", "entries.gsr", "proofs.gsr", "storage-ready.gsr"}
PREFIX = struct.Struct(">4sHHHHi")
MAX_FRAME = 64 * 1024 * 1024
MAX_METADATA = 64 * 1024
MAX_ENTRIES = 1_000_000
MAX_PROMISES = 10_000
OPERATIONS = ("ADD", "UPDATE", "REMOVE", "ADD_ALL", "UPDATE_ALL", "REMOVE_ALL",
              "INDEX_CREATE", "INDEX_DROP", "NO_OP", "SNAPSHOT_MARKER")
VOTERS = ("node-1", "node-2", "node-3")
INCARNATION = "22222222-2222-2222-2222-222222222222"
# Character.isWhitespace, as used by ReplicationEndpoint.host().isBlank().
JAVA_WHITESPACE = frozenset("\t\n\v\f\r\x1c\x1d\x1e\x1f \u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2008\u2009\u200a\u2028\u2029\u205f\u3000")


def check(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(value).digest()


def text(value):
    raw = value.encode("utf-8")
    return struct.pack(">i", len(raw)) + raw


def frame(kind, body):
    prefix = PREFIX.pack(b"GSER", 1, 0, kind, 0, len(body))
    return prefix + digest(prefix + body) + body


class Reader:
    def __init__(self, value):
        self.value, self.offset = value, 0

    def take(self, length):
        check(0 <= length <= len(self.value) - self.offset, "truncated storage field")
        result = self.value[self.offset:self.offset + length]
        self.offset += length
        return result

    def number(self, fmt):
        return struct.unpack(">" + fmt, self.take(struct.calcsize(">" + fmt)))[0]

    def string(self, maximum):
        length = self.number("i")
        check(0 < length <= maximum, "invalid string length")
        return self.take(length).decode("utf-8", errors="strict")

    def identity(self, maximum=128):
        value = self.string(maximum)
        check(re.fullmatch(r"[a-z0-9][a-z0-9._-]{0," + str(maximum - 1) + "}", value),
              "invalid storage identity")
        return value

    def end(self):
        check(self.offset == len(self.value), "trailing storage fields")


def read_frame(source, kind, maximum):
    prefix = source.read(16)
    if not prefix:
        return None
    check(len(prefix) == 16, "incomplete frame header")
    magic, major, minor, actual_kind, flags, length = PREFIX.unpack(prefix)
    check((magic, major, minor) == (b"GSER", 1, 0), "unsupported storage family/version")
    check(actual_kind == kind and flags == 0, "wrong record kind/flags")
    check(0 < length <= maximum - 48, "frame capacity exceeded")
    checksum = source.read(32)
    body = source.read(length)
    check(len(checksum) == 32 and len(body) == length, "incomplete frame body")
    check(checksum == digest(prefix + body), "record checksum mismatch")
    return body, checksum


def single(path, kind):
    with path.open("rb") as source:
        result = read_frame(source, kind, MAX_METADATA)
        check(result is not None and not source.read(1), "metadata must contain one frame")
        return result


def receipt(node, entry):
    return digest(text("gse-replication/1.0/DURABLE_ACK") + entry["manifestDigest"]
                  + text(node) + struct.pack(">q", entry["epoch"]) + entry["incarnation"]
                  + struct.pack(">q", entry["index"]) + entry["digest"])


def inspect(directory):
    directory = Path(directory)
    _inventory(directory)
    with (directory / "replica.lock").open("rb") as lock:
        # POSIX record locks interoperate with Java FileChannel locks; flock does not.
        try:
            fcntl.lockf(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("storage directory has another owner") from error
        return _inspect_locked(directory)


def _inventory(directory):
    check(not any(p.is_symlink() for p in (directory, *directory.parents)), "unsafe storage path")
    check(directory.is_dir(), "storage directory absent")
    members = []
    for member in directory.iterdir():
        check(len(members) < 7, "too many storage members")
        members.append(member)
    check(len(members) == 7 and {p.name for p in members} == FILES, "incomplete or unknown storage inventory")
    check(all(p.is_file() and not p.is_symlink() and p.stat().st_nlink == 1 for p in members),
          "unsafe storage member")
    check((directory / "replica.lock").stat().st_size == 0, "invalid lock member")
    check(sum(p.stat().st_size for p in members) <= 1024 ** 4, "retained-byte capacity exceeded")


def _inspect_locked(directory):
    _inventory(directory)
    manifest_body, manifest_digest = single(directory / "manifest.gsr", 1)
    manifest = Reader(manifest_body)
    check(manifest.string(32) == "gse-replicated" and manifest.number("H") == 1
          and manifest.number("H") == 0 and manifest.string(32) == "gse-replication"
          and manifest.number("H") == 1 and manifest.number("H") == 0,
          "unsupported manifest family/version")
    group, configuration = str(uuid.UUID(bytes=manifest.take(16))), manifest.identity()
    check(manifest.number("q") == 1, "invalid genesis epoch")
    leader = manifest.identity(64)
    check(manifest.number("i") == 3, "invalid voter count")
    voters, endpoints = [], []
    for _ in range(3):
        voters.append(manifest.identity(64))
        host, port = manifest.string(1012), manifest.number("i")
        check(any(c not in JAVA_WHITESPACE for c in host) and len(host.encode("utf-16-le")) // 2 <= 253 and 1 <= port <= 65535,
              "invalid endpoint")
        endpoints.append((host, port))
        check(manifest.number("B") == 1, "non-voter in manifest")
    check(len(set(voters)) == 3 and len(set(endpoints)) == 3 and leader in voters, "ambiguous manifest membership")
    codec, codec_version = manifest.identity(), manifest.number("i")
    schema, schema_version = manifest.identity(), manifest.number("i")
    check(codec_version > 0 and schema_version > 0, "invalid identity version")
    index_digest = manifest.take(32)
    manifest.end()
    node_body, node_digest = single(directory / "node.gsr", 2)
    node_reader = Reader(node_body)
    check(node_reader.take(32) == manifest_digest, "local manifest mismatch")
    node = node_reader.identity(64)
    check(node in voters, "unknown local voter")
    node_reader.end()
    headers, promises, entries, proofs = [], {}, [], []
    previous_epoch, previous_digest, committed = 1, manifest_digest, 0
    for filename, kind in (("promises.gsr", 4), ("entries.gsr", 5), ("proofs.gsr", 6)):
        with (directory / filename).open("rb") as source:
            header = read_frame(source, 3, MAX_METADATA)
            check(header is not None, "absent journal header")
            headers.append(header[1])
            reader = Reader(header[0])
            check(reader.take(32) == manifest_digest and reader.identity(64) == node
                  and reader.number("H") == kind, "journal identity mismatch")
            reader.end()
            while True:
                record = read_frame(source, kind, MAX_FRAME if kind == 5 else MAX_METADATA)
                if record is None:
                    break
                reader = Reader(record[0])
                check(reader.take(32) == manifest_digest, "record manifest mismatch")
                if kind == 4:
                    check(reader.identity(64) == leader, "promise leader mismatch")
                    epoch, incarnation = reader.number("q"), reader.take(16)
                    check(len(promises) < MAX_PROMISES and epoch > max(promises, default=1)
                          and incarnation != bytes(16), "invalid/nonmonotonic promise")
                    promises[epoch] = incarnation
                elif kind == 5:
                    epoch, incarnation, index, operation = reader.number("q"), reader.take(16), reader.number("q"), reader.number("B")
                    prev_epoch, prev_index, prev_digest = reader.number("q"), reader.number("q"), reader.take(32)
                    length, payload_digest = reader.number("i"), reader.take(32)
                    payload = reader.take(length)
                    check(len(entries) < MAX_ENTRIES and index == len(entries) + 1 and prev_index == index - 1,
                          "noncontiguous entry index")
                    check(1 <= operation <= len(OPERATIONS) and epoch >= previous_epoch
                          and promises.get(epoch) == incarnation, "entry type/promise mismatch")
                    check((prev_epoch, prev_digest) == (previous_epoch, previous_digest), "entry predecessor mismatch")
                    check(digest(payload) == payload_digest, "payload checksum mismatch")
                    entries.append({"manifestDigest": manifest_digest, "epoch": epoch, "incarnation": incarnation,
                                    "index": index, "digest": record[1], "previousDigest": prev_digest,
                                    "operation": OPERATIONS[operation - 1]})
                    previous_epoch, previous_digest = epoch, record[1]
                else:
                    epoch, incarnation, index = reader.number("q"), reader.take(16), reader.number("q")
                    entry_digest, prev_digest, count = reader.take(32), reader.take(32), reader.number("i")
                    check(committed < index <= len(entries) and 2 <= count <= 3, "proof index/quorum mismatch")
                    entry = entries[index - 1]
                    check((epoch, incarnation, entry_digest, prev_digest) ==
                          (entry["epoch"], entry["incarnation"], entry["digest"], entry["previousDigest"]),
                          "proof entry identity mismatch")
                    receipt_nodes = []
                    for _ in range(count):
                        voter, ack = reader.identity(64), reader.take(32)
                        check(voter in voters and ack == receipt(voter, entry), "invalid proof voter/receipt")
                        receipt_nodes.append(voter)
                    check(receipt_nodes == sorted(set(receipt_nodes)), "duplicate/unsorted receipt voters")
                    committed = index
                    proofs.append(index)
                reader.end()
    ready_body, _ = single(directory / "storage-ready.gsr", 7)
    check(ready_body == manifest_digest + node_digest + b"".join(headers), "incomplete initialization marker")
    return {"groupId": group, "configurationId": configuration, "nodeId": node,
            "manifestDigest": manifest_digest.hex(), "promisedEpoch": max(promises, default=1),
            "lastLogIndex": len(entries), "commitIndex": committed, "appliedIndex": 0,
            "applicationSequence": 0, "entries": [{"index": e["index"], "epoch": e["epoch"],
              "operation": e["operation"], "digest": e["digest"].hex()} for e in entries],
            "codecId": codec, "codecVersion": codec_version, "schemaId": schema,
            "schemaVersion": schema_version, "indexConfigurationDigest": index_digest.hex()}


def generate(directory, populated=True):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    manifest_body = text("gse-replicated") + struct.pack(">HH", 1, 0) + text("gse-replication") + struct.pack(">HH", 1, 0)
    manifest_body += uuid.UUID("11111111-1111-1111-1111-111111111111").bytes + text("config-v1")
    manifest_body += struct.pack(">q", 1) + text("node-1") + struct.pack(">i", 3)
    for i, node in enumerate(VOTERS, 1):
        manifest_body += text(node) + text(f"10.0.0.{i}") + struct.pack(">iB", 19501, 1)
    manifest_body += text("fixture-codec") + struct.pack(">i", 1) + text("fixture-schema") + struct.pack(">i", 1) + digest(b"")
    manifest = frame(1, manifest_body)
    manifest_digest = manifest[16:48]
    local = frame(2, manifest_digest + text("node-2"))
    headers = [frame(3, manifest_digest + text("node-2") + struct.pack(">H", kind)) for kind in (4, 5, 6)]
    members = {"replica.lock": b"", "manifest.gsr": manifest, "node.gsr": local,
               "promises.gsr": headers[0], "entries.gsr": headers[1], "proofs.gsr": headers[2],
               "storage-ready.gsr": frame(7, manifest_digest + local[16:48] + b"".join(h[16:48] for h in headers))}
    if populated:
        incarnation = uuid.UUID(INCARNATION).bytes
        members["promises.gsr"] += frame(4, manifest_digest + text("node-1") + struct.pack(">q", 2) + incarnation)
        previous_epoch, previous_digest, entries = 1, manifest_digest, []
        for index, (operation, payload) in enumerate((("NO_OP", b""), ("ADD_ALL", b"two-documents"), ("UPDATE", b"uncommitted")), 1):
            entry_body = manifest_digest + struct.pack(">q", 2) + incarnation + struct.pack(">qBqq", index, OPERATIONS.index(operation) + 1, previous_epoch, index - 1)
            entry_body += previous_digest + struct.pack(">i", len(payload)) + digest(payload) + payload
            encoded = frame(5, entry_body)
            entries.append({"manifestDigest": manifest_digest, "epoch": 2, "incarnation": incarnation,
                            "index": index, "digest": encoded[16:48], "previousDigest": previous_digest})
            members["entries.gsr"] += encoded
            previous_epoch, previous_digest = 2, encoded[16:48]
        entry = entries[1]
        proof = manifest_digest + struct.pack(">q", 2) + incarnation + struct.pack(">q", 2)
        proof += entry["digest"] + entry["previousDigest"] + struct.pack(">i", 2)
        proof += b"".join(text(node) + receipt(node, entry) for node in VOTERS[:2])
        members["proofs.gsr"] += frame(6, proof)
    for name, value in members.items():
        (directory / name).write_bytes(value)
    return inspect(directory)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "inspect"))
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    document = generate(args.directory) if args.command == "generate" else inspect(args.directory)
    print(json.dumps(document, sort_keys=True))
