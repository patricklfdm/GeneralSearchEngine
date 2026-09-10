# GeneralSearchEngine V4.3 Phase 2 derived format and inspection

- **Status:** Implementation candidate; protected acceptance pending
- **Scope:** Exact `(1,2)` canonical/backup bytes, derived component bytes, and
  codec-free inspection
- **Default:** Unchanged `gse-durable (1,0)`

## Phase boundary

Phase 2 activates explicit canonical `gse-durable (1,2)` creation/open/checkpoint/WAL
and matching canonical-only `gse-backup (1,2)` backup/restore. It freezes derived
catalog and all four built-in component encodings and adds read-only codec-free
inspection. Production reopen still rebuilds every index from canonical documents;
it neither loads nor publishes an image and `lastReopenReport()` remains empty.

Structured image publication/load, migration to `(1,2)`, text materialization,
refresh, cleanup, performance claims and paid cloud execution remain later phases.
The default and exact `(1,0)`/`(1,1)` bytes are unchanged.

## Exact `(1,2)` profile and metadata

All integers are big-endian. Strings are signed 32-bit byte lengths followed by
strict UTF-8. Whole members end with CRC32C over every preceding byte. SHA-256 values
are raw 32-byte values.

The required capability list is strictly sorted:

```text
canonical-documents-v1
checkpoint-authority-v1
crc32c-wal-v1
logical-index-config-v1
reconstructible-derived-index-images-v1
sha256-profile-binding-v1
```

The optional list is empty. The exact profile digest is:

```text
SHA-256("gse-durable-format-profile-v1\0" || profileBytes)
596a1cdd7cf38f97f7bc740ff7a6e340fcca9c86b62ad261886db4c687b4595a
```

Metadata retains the `(1,1)` field order and inserts `long maxDerivedStateBytes`
after `maxRetainedBytes` and before the index count. It must be positive, at most
8 TiB, and no greater than the retained-byte bound. The public default is 2 GiB;
explicitly configuring the value with an older format is rejected.

Checkpoint, manifest and WAL use the published profile-bound layouts with minor `2`.
The WAL generation header remains 80 bytes. Existing names, logical records and
canonical checkpoint semantics do not change.

## Derived member grammar and identities

The fixed catalog is `gse-derived-manifest`; its staging name appends `.staging`.
Component names are:

```text
gse-derived-index-<20-digit checkpoint>-<5-digit ordinal>-<32 lowercase hex>.idx
```

and staging appends `.staging`. The generation token is the 128 UUID bits rendered
as 32 lowercase hexadecimal digits without separators, using the same
`UUID.randomUUID()` source already used by checkpoint publication. It distinguishes
publication attempts and is excluded from semantic authority.

Derived encoding is `(1,0)`. The magics and domains are:

| Member | Magic | SHA-256 domain |
|---|---|---|
| catalog | `0x4753454443415431` (`GSEDCAT1`) | `gse-derived-catalog-content-v1\0` |
| component | `0x4753454449445831` (`GSEDIDX1`) | `gse-derived-component-content-v1\0` |

The generator identity is exactly `gse-derived-generator-v1`, version `1`.
Catalog identity renders as `gse-derived-catalog-v1-<64 lowercase hex>`.

## Catalog layout

The catalog is at least 256 bytes and at most 16 MiB:

```text
catalog magic, derived encoding major/minor, live major/minor
live profile digest, history UUID, checkpoint sequence
checkpoint filename, complete byte length, stored CRC32C, whole-file SHA-256
storage identity, schema identity, codec identity/version
generator identity/version, nextDocId, liveDocumentCount, componentCount
repeat in ordinal order:
  ordinal, kind, index name, analyzer identity
  component filename, complete byte length, stored CRC32C, whole-file SHA-256
catalog content SHA-256
whole-member CRC32C
```

The content SHA covers its domain and every preceding catalog field, excluding the
stored identity and trailing CRC. Entries must exactly equal canonical metadata
descriptor order and bind the authoritative checkpoint.

## Component layout and payloads

Each component is at least 192 bytes and at most 2 GiB:

```text
component magic, derived encoding major/minor, live major/minor
live profile digest, history UUID, checkpoint sequence
checkpoint whole-file SHA-256, storage identity, schema identity, codec identity/version
generator identity/version, ordinal, kind, index name, analyzer identity
nextDocId, liveDocumentCount
kind-specific payload
component content SHA-256
whole-member CRC32C
```

The content SHA covers its domain and every preceding component field. Equality and
range payloads encode a group count, then representative document ID and canonical
strictly increasing bitmap for each group. Prefix encodes strict UTF-8 keys in
unsigned byte order followed by canonical bitmaps. Text encodes document count,
total field length, ordered `(document,length)` pairs, then UTF-8 ordered terms with
document frequency and ordered postings/positions.

Counts are bounded at 100,000,000; component/descriptors at 100,000; UTF-8 values at
1 MiB. IDs are within `[0,nextDocId)`. Duplicates, noncanonical order, invalid UTF-8,
overflow, trailing bytes, unknown kind/version or any binding/digest disagreement
reject the component.

## Inspection and authority separation

`inspectDerivedState` acquires the live-store lock, validates canonical authority
first, and then independently inspects derived members without a codec, repair,
deletion or refresh. Exact older formats report `NOT_APPLICABLE`; valid `(1,2)` with
no catalog reports `ABSENT`. Catalog-level failure rejects the generation. With a
valid catalog, one or more but not all admissible components reports `PARTIAL`.

Recognized derived damage, aliases, staging and old generations do not change a valid
canonical structural report. Inspection reports bounded, canonically ordered findings
and component/byte totals. Total derived bytes must fit the persisted allowance and
all engine-owned bytes continue to count toward the retained-byte bound.

## Backup and published boundary

Backup `(1,2)` has exactly three members and never transports derived files. Its
content domain is `gse-backup-content-v3\0` and its identity prefix is
`gse-backup-v3-`. Restore publishes a new-history canonical cold target.

The checksum-pinned published `4.2.0` artifact executes the exact frozen live and
backup fixtures in an isolated child JVM and rejects both fail-closed. Current V4.3
accepts the same canonical and derived bytes. The independent Python encoder/parser
shares no production reader code.

## Frozen physical evidence

The exact lowercase-hex fixtures, SHA-256 inventory and identities live in
`src/test/resources/compatibility/v43-derived-v12/`. Any change to their bytes,
magic, capability, domain, order, bounds, names or identities is a reviewed format
change—not routine fixture regeneration.
