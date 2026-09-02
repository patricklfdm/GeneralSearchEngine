# V4.0 Phase 2 storage and WAL format appendix

## Scope and byte order

This appendix freezes the first production bytes for storage family `gse-durable`,
format `(1,0)`. All integers are signed big-endian values unless explicitly described
as a bit pattern. Text is strict UTF-8 preceded by a signed 32-bit byte length. CRCs
use CRC32C (Castagnoli) and are stored as the unsigned 32-bit checksum bit pattern.

Phase 2 creates fresh WAL-only stores and writes production logical units. It does not
open initialized storage, truncate an incomplete tail, replay, rebuild indexes, or
checkpoint. Those reader actions begin in their ordered phases; the bytes below are
already their immutable input.

## Engine-owned names

One Phase 2 store contains exactly:

- `gse.lock`: lifetime exclusive-lock inode, never durability authority;
- `gse-metadata`: forced and atomically renamed immutable storage metadata; and
- `gse-wal-00000000000000000001.log`: generation 1 header and logical-unit frames.

Metadata is first written to `gse-metadata.staging`, forced, atomically renamed to
`gse-metadata`, and followed by a directory force. A staging name is never authority.
The generation header is forced before the durable engine is returned.

## Metadata layout

`gse-metadata` has this exact ordered layout:

| Field | Width / encoding |
| --- | --- |
| magic `GSEMETA1` | 8 bytes (`0x4753454d45544131`) |
| format major / minor | 2 bytes / 2 bytes (`1`, `0`) |
| random history identity | two 8-byte UUID halves |
| format family | length + UTF-8 (`gse-durable`) |
| storage identity | length + UTF-8 |
| schema identity | length + UTF-8 |
| codec ID | length + UTF-8 |
| codec version | 4 bytes |
| max key/document bytes | 4 bytes each |
| max bulk/live documents | 4 bytes each |
| checkpoint WAL / retained byte limits | 8 bytes each |
| startup index count | 4 bytes |
| each startup index | kind byte, field string, analyzer string |
| checksum | CRC32C over every preceding metadata byte |

Index kinds are equality `1`, range `2`, prefix `3`, and text `4`. Non-text analyzer
strings are empty. V4.0 text indexes support only analyzer identity `gse-simple-v1`.
Startup descriptor order is the builder order.

## WAL generation header

The generation header is exactly 48 bytes:

| Offset | Field | Width |
| ---: | --- | ---: |
| 0 | magic `GSEWAL10` (`0x47534557414c3130`) | 8 |
| 8 | format major / minor | 2 / 2 |
| 12 | history UUID most / least halves | 8 / 8 |
| 28 | generation (`1`) | 8 |
| 36 | first possible sequence (`1`) | 8 |
| 44 | CRC32C of bytes `[0,44)` | 4 |

## Logical-unit frame

Each frame is one independently atomic logical unit. Its 28-byte fixed header is:

| Offset | Field | Width |
| ---: | --- | ---: |
| 0 | magic `GSEF` (`0x47534546`) | 4 |
| 4 | frame major / minor | 2 / 2 |
| 8 | total frame length | 4 |
| 12 | contiguous positive sequence | 8 |
| 20 | unit type | 1 |
| 21 | flags, currently zero | 1 |
| 22 | reserved, currently zero | 2 |
| 24 | payload length | 4 |

The payload follows immediately. A four-byte trailer contains CRC32C over the complete
fixed header and payload. Total length must equal `28 + payloadLength + 4` and may not
exceed 256 MiB. A complete invalid frame is corruption; only a physically incomplete
newest terminal frame is eligible for Phase 3 truncation.

Unit types are single mutation `1`, atomic bulk `2`, installed index create `3`, and
index drop `4`.

## Payloads

A mutation entry is:

```text
operation byte (ADD=1, UPDATE=2, REMOVE=3)
key length (int32) + key bytes
document length (int32) + document bytes
```

REMOVE has document length `-1` and no document bytes. ADD/UPDATE require a non-negative
bounded document length. A single payload is exactly one mutation entry. A bulk payload
starts with a positive int32 element count followed by that many complete mutation
entries; no element receives an independent sequence or frame.

Index create contains kind byte, field string, and analyzer string. Index drop contains
one field string. Unsupported custom index/analyzer behavior fails before sequence
allocation.

## Hard bounds

Configured values cannot exceed 64 MiB per key, 256 MiB per document, 1,000,000 bulk
elements, 100,000,000 live documents, 1 TiB checkpoint trigger, or 16 TiB retained
engine bytes. The independent 256 MiB complete-frame bound may reject a bulk even when
every element satisfies its individual limit. All size arithmetic is checked before
sequence allocation or storage append.

## Commit and crash barriers

One writer group may append several frames and force once. It then publishes exactly
that prefix and completes Futures. Phase 2 exposes these stable harness barriers:

- `v4-wal-before-sequence-v1`, `v4-wal-after-sequence-v1`;
- `v4-wal-partial-header-v1`, `v4-wal-partial-payload-v1`,
  `v4-wal-partial-trailer-v1`;
- `v4-wal-complete-before-force-v1`, `v4-wal-after-force-v1`;
- `v4-wal-before-publication-v1`, `v4-wal-after-publication-v1`; and
- `v4-wal-before-future-completion-v1`.

The separate-process harness reaches every ID through production code. Its Python
inspector validates metadata, generation/frame identities, CRC32C, lengths, payload
structure and contiguous complete sequence without invoking a production reader.
