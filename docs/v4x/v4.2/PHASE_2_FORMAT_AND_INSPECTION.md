# GeneralSearchEngine V4.2 Phase 2 format and inspection contract

- **Status:** Implementation candidate; protected acceptance pending
- **Scope:** Exact `gse-durable (1,1)` bytes and codec-free dual-minor inspection
- **Default writable format:** Unchanged `gse-durable (1,0)`

## Phase boundary

Phase 2 adds public format values, explicit configuration selection, format reports,
exact physical `1.1` fixtures, and read-only structural support for live and backup
formats `1.0` and `1.1`. It does not enable production creation, open, checkpoint,
WAL append, backup, restore, or migration for `1.1`. An explicit `V1_1` selection is
rejected before directory creation until Phase 3 owns that write path.

Existing `1.0` stores continue to open and write byte-identical `1.0` members. No
inspection operation repairs, normalizes, upgrades, truncates, or loads a user codec.

## Primitive encoding

All integers are big-endian. Length-prefixed UTF-8 text uses a signed 32-bit byte
length followed by strict UTF-8 bytes. UUIDs are the existing signed 64-bit most and
least significant values. SHA-256 values are raw 32-byte digests. Each complete
member ends with the existing CRC32C of every preceding byte; WAL frame CRC behavior
is unchanged.

The existing magics and member names remain unchanged:

| Member | Magic |
|---|---|
| metadata | `0x4753454d45544131` (`GSEMETA1`) |
| checkpoint | `0x47534543484b3130` (`GSECHK10`) |
| checkpoint manifest | `0x4753454d414e3130` (`GSEMAN10`) |
| WAL generation | `0x47534557414c3130` (`GSEWAL10`) |
| backup manifest | `0x475345424b503130` (`GSEBKP10`) |

The major/minor pair is exactly `(1,1)`. The live inventory and naming grammar remain
those of `1.0`; the backup inventory remains exactly three members.

## Canonical profile

Metadata owns the complete profile. Its exact encoding is:

```text
int requiredCount
repeat requiredCount: int byteLength, strict UTF-8 capability
int optionalCount
repeat optionalCount: int byteLength, strict UTF-8 capability
```

Counts are at most `64`, the encoded profile is at most `4096` bytes, identifiers
match `[a-z0-9][a-z0-9-]{0,127}`, and each list is strictly sorted and duplicate-free.
The initial required list is exactly:

```text
canonical-documents-v1
checkpoint-authority-v1
crc32c-wal-v1
logical-index-config-v1
sha256-profile-binding-v1
```

The optional list is empty. The exact profile is `134` bytes. Its digest is:

```text
SHA-256("gse-durable-format-profile-v1\0" || profileBytes)
f5013976ba0c49b62a6a38ce8a6af4cf5f8acf53e24dcf9733d22382b1e5f50f
```

An intact canonical but unknown required/optional profile is `INCOMPATIBLE`. Invalid
UTF-8, bounds, ordering, duplication, digest, or a member binding that differs from
metadata is `CORRUPT`.

## Exact member layouts

Fields below are in byte order. “Published remainder” means the exact `1.0` fields in
their already frozen order and bounds.

### Metadata

```text
magic, major, minor, history UUID, family
profileLength, profileBytes, profileDigest
storageIdentity, schemaIdentity, codecIdentity, codecVersion
maxKeyBytes, maxDocumentBytes, maxBulkElements, maxDocuments
checkpointWalBytes, maxRetainedBytes
indexCount, logical index descriptors
whole-member CRC32C
```

### Checkpoint and checkpoint manifest

```text
checkpoint:
magic, major, minor, history UUID, profileDigest
sequence, nextDocId, liveDocumentCount, indexCount
logical index descriptors, slotCount, canonical slot records
whole-member CRC32C

checkpoint manifest:
magic, major, minor, history UUID, profileDigest
sequence, checkpointBytes, checkpointCRC32C, checkpointFile
walGeneration, walFirstSequence
whole-member CRC32C
```

### WAL generation and frames

The `1.1` generation header is exactly `80` bytes:

```text
magic[8], major[2], minor[2], history UUID[16], profileDigest[32],
generation[8], firstSequence[8], headerCRC32C[4]
```

WAL frames keep the published encoding but declare minor `1`. A generation/header,
frame, metadata, checkpoint, or manifest minor disagreement is `CORRUPT`; no parser
infers a minor from the `80`-byte length.

### Backup manifest

The manifest is:

```text
magic, backup major/minor, backup family
source family, source major/minor, source profileDigest
source history UUID, sequence
storageIdentity, schemaIdentity, codecIdentity, codecVersion
payloadCount and canonical payload descriptors
contentDigest, createdEpochMillis, requestId
whole-member CRC32C
```

The payloads are byte-identical `1.1` metadata and checkpoint bytes. Content identity
is `SHA-256("gse-backup-content-v2\0" || canonical fields)` and is rendered as
`gse-backup-v2-<64 lowercase hex>`. The fixture identity is
`gse-backup-v2-980f862c5a7eebaa4b5191d183ff066f43254b68f60bee0bda580165988ac8ff`.

## Inspection and classification

`inspectStoreFormat` takes the same exclusive live-store lock as structural
verification, calls the same bounded structural reader, and then retains an intact
CRC-valid common-header declaration. `inspectBackupFormat` permits concurrent readers
of an immutable bundle. Both reports contain the existing structural report; a
declaration is absent when the relevant header is missing, non-regular, out of bound,
invalid UTF-8, or checksum-invalid.

V4.2 chooses parsing from the intact family/major/minor before reading versioned
fields. It supports exact `1.0`, exact known-profile `1.1`, rejects higher minor as
`INCOMPATIBLE`, rejects another family/major as `UNSUPPORTED`, and classifies damaged
known layouts or mixed bindings as `CORRUPT`.

## Published V4.1 boundary

An isolated child JVM containing only the SHA-256-pinned published `4.1.0` core runs
the exact Phase 2 fixtures. Because that immutable parser consumes `1.0` fields before
its higher-minor check, the inserted profile bytes are observed as invalid `1.0`
lengths. Exact live and backup `1.1` fixtures therefore return `CORRUPT`, not
`INCOMPATIBLE`. They are never opened or interpreted as `1.0`.

This is the executable Phase 2 correction to the earlier classification assumption.
Rollback compatibility remains exact: published V4.1 reopens the untouched `1.0`
source, while only V4.2 reads the new target.

## Immutable evidence

Exact lowercase-hex members, SHA-256 inventory, profile digest, and backup identity
are under `src/test/resources/compatibility/v42-storage-v11/`. The independent
`scripts/v42/storage_format_v11.py` encoder/parser shares no production reader code.
Any byte, hash, capability, member, domain, or classification change requires review
as a new format decision rather than fixture regeneration.
