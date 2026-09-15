"""Independent parser for Phase 4 snapshots, generation selectors and recovery floors."""

import io
import json
from pathlib import Path
import uuid
from scripts.v50 import storage_format as sf

SLOTS = {"generation-a", "generation-b"}
SLOT_FILES = {"snapshot.gsr", "entries.gsr", "proofs.gsr", "generation.gsr"}
OPTIONAL = SLOTS | {"current.gsr", "current.pending.gsr", "recovery-floor.gsr", "recovery-floor.pending.gsr", "rebuilding.gsr", "generation-started.gsr", "transfer"}
MAX_IMAGE = 64 * 1024 * 1024


def regular(path):
    sf.check(path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1, "unsafe recovery member")


def inventory(directory):
    sf.check(not any(p.is_symlink() for p in (directory, *directory.parents)) and directory.is_dir(), "unsafe replica path")
    names = set()
    total = 0
    for path in directory.iterdir():
        sf.check(len(names) < len(sf.FILES | OPTIONAL) and path.name in sf.FILES | OPTIONAL, "unknown replica member")
        names.add(path.name)
        if path.name in SLOTS or path.name == "transfer":
            sf.check(path.is_dir() and not path.is_symlink(), "unsafe recovery directory")
            allowed = SLOT_FILES if path.name in SLOTS else {"offer.gsr", "image.bin"}
            count = 0
            for child in path.iterdir():
                count += 1
                sf.check(count <= len(allowed) and child.name in allowed, "unknown staged member")
                regular(child)
                limit = MAX_IMAGE if child.name in {"snapshot.gsr", "image.bin"} else sf.MAX_METADATA if child.name in {"offer.gsr", "generation.gsr"} else 1024 ** 4
                sf.check(child.stat().st_size <= limit, "staged member exceeds capacity")
                total += child.stat().st_size
        else:
            regular(path)
            total += path.stat().st_size
    sf.check(sf.FILES <= names and (directory / "replica.lock").stat().st_size == 0, "incomplete replica inventory")
    sf.check(total <= 2 * 1024 ** 4, "recovery retention/staging capacity exceeded")


def record(path, kind, maximum=sf.MAX_METADATA):
    regular(path)
    sf.check(0 < path.stat().st_size <= maximum, "recovery record exceeds bound")
    with path.open("rb") as source:
        result = sf.read_frame(source, kind, maximum)
        sf.check(result is not None and not source.read(1), "incomplete/trailing recovery record")
        return result


def embedded(value, kind, maximum):
    source = io.BytesIO(value)
    result = sf.read_frame(source, kind, maximum)
    sf.check(result is not None and not source.read(1), "incomplete/trailing embedded recovery record")
    return result


def blob(reader, maximum):
    length = reader.number("i")
    sf.check(0 <= length <= maximum, "recovery blob exceeds bound")
    return reader.take(length)


def parse_proof(value, manifest, voters, entries):
    body, checksum = embedded(value, 6, sf.MAX_METADATA)
    reader = sf.Reader(body)
    sf.check(reader.take(32) == manifest, "snapshot proof manifest mismatch")
    epoch, incarnation, index = reader.number("q"), reader.take(16), reader.number("q")
    entry_digest, previous, count = reader.take(32), reader.take(32), reader.number("i")
    sf.check(1 <= index <= len(entries) and 2 <= count <= 3, "snapshot proof index/quorum mismatch")
    entry = entries[index - 1]
    sf.check((epoch, incarnation, entry_digest, previous) == (entry["epoch"], entry["incarnation"], entry["digest"], entry["previousDigest"]), "snapshot proof ancestry mismatch")
    receipt_nodes = []
    for _ in range(count):
        node, receipt = reader.identity(64), reader.take(32)
        sf.check(node in voters and receipt == sf.receipt(node, entry), "invalid snapshot proof receipt")
        receipt_nodes.append(node)
    sf.check(receipt_nodes == sorted(set(receipt_nodes)), "duplicate/unsorted snapshot voters")
    reader.end()
    return {"index": index, "digest": checksum.hex(), "receiptVoters": receipt_nodes}


def application(value):
    reader = sf.Reader(value)
    sf.check(reader.number("H") == 1, "unsupported application snapshot")
    count = reader.number("i")
    sf.check(0 <= count <= 10_000 and count <= (len(value) - reader.offset) // 4, "snapshot index count exceeds bound")
    indexes, fields = [], []
    for _ in range(count):
        encoded = reader.string(8192)
        index = json.loads(encoded)
        sf.check(set(index) == {"analyzer", "field", "kind"} and index["kind"] in {"equality", "range", "prefix", "text"}, "invalid snapshot index")
        sf.check(index["analyzer"] == ("gse-simple-v1" if index["kind"] == "text" else "") and isinstance(index["field"], str)
                 and 0 < len(index["field"].encode()) <= 1024, "invalid snapshot analyzer/field")
        sf.check(json.dumps(index, sort_keys=True, separators=(",", ":"), ensure_ascii=True) == encoded, "noncanonical index descriptor")
        indexes.append(index)
        fields.append(index["field"])
    sf.check(fields == sorted(set(fields), key=lambda value: value.encode("utf-16-be")), "duplicate/unsorted snapshot indexes")
    count = reader.number("i")
    sf.check(0 <= count <= sf.MAX_ENTRIES and count <= (len(value) - reader.offset) // 8, "snapshot document count exceeds bound")
    documents, keys = [], set()
    for _ in range(count):
        key, document = blob(reader, MAX_IMAGE), blob(reader, MAX_IMAGE)
        sf.check(key not in keys, "duplicate snapshot key")
        keys.add(key)
        documents.append({"keyHex": key.hex(), "documentHex": document.hex()})
    reader.end()
    return {"indexes": indexes, "documents": documents}


def snapshot(path, manifest, voters):
    body, checksum = record(path, 8, MAX_IMAGE)
    reader = sf.Reader(body)
    sf.check(reader.take(32) == manifest, "snapshot manifest mismatch")
    count = reader.number("i")
    sf.check(0 <= count <= sf.MAX_ENTRIES and count <= (len(body) - reader.offset) // 89, "snapshot ancestor count exceeds bound")
    entries, previous, previous_epoch, previous_incarnation = [], manifest, 1, bytes(16)
    for index in range(1, count + 1):
        epoch, incarnation, operation = reader.number("q"), reader.take(16), reader.number("B")
        digest, payload = reader.take(32), reader.take(32)
        sf.check(epoch >= max(2, previous_epoch) and incarnation != bytes(16) and (epoch > previous_epoch or incarnation == previous_incarnation) and 1 <= operation <= len(sf.OPERATIONS), "invalid snapshot ancestor")
        entries.append({"manifestDigest": manifest, "index": index, "epoch": epoch, "incarnation": incarnation,
                        "operation": sf.OPERATIONS[operation - 1], "digest": digest, "payloadDigest": payload, "previousDigest": previous})
        previous, previous_epoch, previous_incarnation = digest, epoch, incarnation
    proof = blob(reader, sf.MAX_METADATA)
    sf.check(bool(entries) == bool(proof), "snapshot terminal proof missing/unexpected")
    proofs = [parse_proof(proof, manifest, voters, entries)] if proof else []
    sf.check(not proofs or proofs[0]["index"] == len(entries), "snapshot terminal proof behind ancestry")
    state = application(blob(reader, MAX_IMAGE))
    reader.end()
    return {"digest": checksum.hex(), "entries": entries, "proofs": proofs, "application": state,
            "sequence": sum(entry["operation"] not in {"NO_OP", "SNAPSHOT_MARKER"} for entry in entries)}


def select(directory, manifest, node, voters):
    rebuilding = directory / "rebuilding.gsr"
    if rebuilding.exists():
        reader = sf.Reader(record(rebuilding, 13)[0])
        sf.check(reader.take(32) == manifest and reader.identity(64) == node, "replacement identity mismatch")
        reader.end()
    started = directory / "generation-started.gsr"
    if started.exists():
        reader = sf.Reader(record(started, 15)[0])
        sf.check(reader.take(32) == manifest and reader.identity(64) == node, "generation-started identity mismatch")
        reader.end()
    pointer = directory / "current.gsr"
    if not pointer.exists():
        sf.check(not started.exists() and not (directory / "recovery-floor.gsr").exists(), "installed generation selector is missing")
        return directory, None, 0, not rebuilding.exists()
    reader = sf.Reader(record(pointer, 10)[0])
    sf.check(reader.take(32) == manifest and reader.identity(64) == node, "pointer identity mismatch")
    slot, generation, seal_digest, admitted = reader.string(32), reader.take(16), reader.take(32), reader.number("B")
    reader.end()
    sf.check(slot in SLOTS and admitted in {0, 1}, "invalid generation selector")
    selected = directory / slot
    sf.check({p.name for p in selected.iterdir()} == SLOT_FILES, "incomplete selected generation")
    seal_body, digest = record(selected / "generation.gsr", 11)
    sf.check(digest == seal_digest, "selector/seal mismatch")
    reader = sf.Reader(seal_body)
    sf.check(reader.take(32) == manifest and reader.identity(64) == node and reader.take(16) == generation, "generation identity mismatch")
    result = snapshot(selected / "snapshot.gsr", manifest, voters)
    sf.check(reader.take(32).hex() == result["digest"], "snapshot/seal mismatch")
    for file in ("entries.gsr", "proofs.gsr"):
        with (selected / file).open("rb") as source:
            header = sf.read_frame(source, 3, sf.MAX_METADATA)
            sf.check(header is not None and header[1] == reader.take(32), "generation journal/header mismatch")
    reader.end()
    floor = 0
    path = directory / "recovery-floor.gsr"
    if path.exists():
        reader = sf.Reader(record(path, 12)[0])
        sf.check(reader.take(32) == manifest and reader.identity(64) == node, "floor identity mismatch")
        floor, digest, count = reader.number("q"), reader.take(32), reader.number("i")
        sf.check(0 <= floor <= len(result["entries"]) and 2 <= count <= 3, "floor exceeds installed snapshot")
        sf.check(digest == (manifest if floor == 0 else result["entries"][floor - 1]["digest"]), "floor ancestry mismatch")
        receipts = [reader.identity(64) for _ in range(count)]
        sf.check(receipts == sorted(set(receipts)) and set(receipts) <= set(voters), "invalid floor recovery voters")
        reader.end()
    return selected, result, floor, bool(admitted)


def generate(directory):
    """Canonical codec-free format fixture; this is not application/bootstrap authority."""
    import struct
    directory = Path(directory)
    original = sf.generate(directory)
    manifest, node = bytes.fromhex(original["manifestDigest"]), original["nodeId"]

    def frames(path):
        raw, result, offset = path.read_bytes(), [], 0
        while offset < len(raw):
            end = offset + 48 + struct.unpack_from(">i", raw, offset + 12)[0]
            result.append(raw[offset:end]); offset = end
        return result

    ancestors = original["entries"][:2]
    body = manifest + struct.pack(">i", len(ancestors))
    for entry in ancestors:
        body += struct.pack(">q", entry["epoch"]) + uuid.UUID(entry["incarnationId"]).bytes
        body += struct.pack(">B", sf.OPERATIONS.index(entry["operation"]) + 1)
        body += bytes.fromhex(entry["digest"]) + bytes.fromhex(entry["payloadDigest"])
    proof = frames(directory / "proofs.gsr")[-1]
    app = struct.pack(">Hii", 1, 0, 0)
    body += struct.pack(">i", len(proof)) + proof + struct.pack(">i", len(app)) + app
    snapshot_bytes = sf.frame(8, body)
    slot = "generation-a"
    target = directory / slot; target.mkdir()
    entry_frames, proof_frames = frames(directory / "entries.gsr"), frames(directory / "proofs.gsr")
    (target / "snapshot.gsr").write_bytes(snapshot_bytes)
    (target / "entries.gsr").write_bytes(entry_frames[0] + entry_frames[3])
    (target / "proofs.gsr").write_bytes(proof_frames[0])
    generation = uuid.UUID("44444444-4444-4444-4444-444444444444").bytes
    seal = sf.frame(11, manifest + sf.text(node) + generation + snapshot_bytes[16:48] + entry_frames[0][16:48] + proof_frames[0][16:48])
    (target / "generation.gsr").write_bytes(seal)
    (directory / "current.gsr").write_bytes(sf.frame(10, manifest + sf.text(node) + sf.text(slot) + generation + seal[16:48] + b"\x01"))
    (directory / "generation-started.gsr").write_bytes(sf.frame(15, manifest + sf.text(node)))
    (directory / "recovery-floor.gsr").write_bytes(sf.frame(12, manifest + sf.text(node) + struct.pack(">q", 2) + bytes.fromhex(ancestors[-1]["digest"])
                                                          + struct.pack(">i", 2) + sf.text("node-1") + sf.text("node-2")))
    return sf.inspect(directory)
