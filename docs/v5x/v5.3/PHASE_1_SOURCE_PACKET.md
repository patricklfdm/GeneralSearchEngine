# Phase 1 bounded source packet

Status: **transport inventory locally qualified**. The separate
[complete capsule walk](PHASE_1_CAPSULES.md) checks conditional authority;
source selection remains pending. This implements the previously unspecified packing syntax for
the complete bounded inventory required by the 1.3 contract. It adds no 25th storage
kind, no 22nd wire kind, and no public API. The 24/21 golden frames remain unchanged.

## GSCP 1.3 container

All integers are unsigned big-endian on the wire. Check the actual byte count and
declared lengths before member allocation. The whole packet is at most 32 MiB.

| Offset | Bytes | Meaning |
| --- | --- | --- |
| 0 | 4 | ASCII `GSCP` |
| 4 | 2 + 2 | Major 1, minor 3 |
| 8 | 2 + 2 | Reserved kind 0, flags 0 |
| 12 | 4 | Body bytes, exactly total bytes minus 48 |
| 16 | 32 | SHA-256 of bytes 0–15 followed by the body |
| 48 | 4 + variable | Length and complete CAPSULE 1.3 frame |
| Next | 4 + variable | Length and canonical inventory JSON |
| Rest | Variable | Exact metadata bodies in inventory digest order |

The fixed header, two length fields, capsule frame and inventory JSON together
must fit **1 MiB**, not 1 MiB per field. Each metadata member is at most 8 MiB;
its actual record-kind bound is checked when decoded. Empty metadata is permitted
for a BARRIER payload. No padding or trailing bytes are allowed.

Inventory fields are exactly:

```json
{"schema":"gse-membership-source-index/1.3","objects":[{"bytes":123,"sha256":"<64 lowercase hex>"}],"images":[{"bytes":456,"sha256":"<64 lowercase hex>"}]}
```

The example hashes are placeholders. Real arrays are nonempty and strictly ordered
by full SHA-256, with no duplicates. `objects` has at most 65,536 entries; `images`
has at most seven. The existing 16-depth / 65,536-token JSON budget and 1 MiB total
envelope can impose smaller practical limits. No filenames, offsets or arbitrary
paths are supplied. Every declared metadata byte must be present and hash correctly
before the decoder returns.

Application images are **not inlined** in this metadata packet. Their declared
sizes are 1..64 MiB each; the separate transfer and shared staging budget still
apply. Materialization verification requires the exact complete declared image set,
not merely the current image's hash. Dummy fixture images do not establish inherited
application/search semantics.

## Nonrecursive digest bindings

The CAPSULE frame and inventory JSON are envelope objects, excluded from the
`objects` array. This avoids a digest containing itself:

- `CAPSULE.inventory` and `BASIS.inventory` are the hash of the exact inventory JSON.
- `BASIS.capsule` is the hash of the complete CAPSULE frame.
- `CAPSULE.initial` identifies the retained original GENESIS frame.
- `CAPSULE.catalog` identifies its complete terminal CATALOG frame; its root/cut
  and application digest must equal the capsule's fields.
- The transfer's whole-content digest hashes the complete GSCP packet, separately
  from the inventory and capsule digests.
- `BASIS.accepted`, if nonnull, identifies the original ACCEPT frame. Its immutable
  ENTRY and payload must also be present; root, view, next index, parent and ballot
  ordering must agree. Missing bodies cannot be replaced by receipt hashes.

`MembershipSourcePacket.bind` checks that the supplied original basis references
these exact contents. The caller must additionally check the selected source's
full identity, original basis UUID/digest, current campaign and immutable selection.
This container does not grant permission to change that selection.

## What this establishes

The internal Java encoder/decoder checks transport syntax, byte inventory, terminal
catalog and basic accepted-tail references. A separate Python reader reconstructs
the same container without importing the production decoder. Fresh JVM fixtures
cover an initial source and a source with one original accepted BARRIER; portable
replay and 30 original-first malformed packet/basis variants are checked.

Successful packet decoding is **not** a verified capsule. It does not walk every
checkpoint range and explicit membership edge, check their actual owned endorsements,
establish the entire verified ancestry, authorize recovery selection, force a
selector, or delete a generation. Invoke the separate capsule verifier with
authenticated ownership observations for that walk; selection and storage
integration remain separate obligations. Packet receipts continue to say
`capsuleAuthorityVerified: false`.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  -Dtest=V53SourcePacketTest,V53ContextTest,V53ResourceTransferTest,V53FormatTest \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m unittest scripts.v53.test_source_packet
python3 -m scripts.v53.source_packet_qualification target/v53-packets/run-UNIQUE
```

Current-coordinate shared build bundles additionally require the executed,
unskipped packet suite. Logs/raw bytes: `target/v53-phase1-packets/`. An initial
Java test compilation failed on a wildcard list mutation; it was corrected before
the passing qualification, with the original log retained. Local source/JAR/class
bindings do not represent protected CI or a published predecessor.

[Retained local receipt](phase1-evidence/source-packet.json): 23 focused Java tests,
31 Python context/packet/build-contract tests, both Java packet fixtures, 30
malformed variants and relocated replay passed. The receipt preserves exact packet,
JAR, source-inventory and log identities; final reporting edits are identified.
