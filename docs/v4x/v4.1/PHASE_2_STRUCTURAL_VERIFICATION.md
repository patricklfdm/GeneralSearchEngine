# GeneralSearchEngine V4.1 Phase 2 structural verification

## Scope

Phase 2 implements the codec-free, synchronous and read-only portion of the accepted
V4.1 contract. It adds:

- `DurableStorageOperations.verifyStore(Path)`;
- `DurableStorageOperations.verifyBackup(Path)`;
- `DurableVerificationStatus`;
- `DurableVerificationFinding`;
- `DurableVerificationReport`; and
- `DurableOperationException` with the complete frozen V4.1 reason family.

It does not add backup creation, typed semantic verification, restore, cleanup,
operation-marker writing or any new live-store member. The readable live format
remains exactly `gse-durable (1,0)`.

## API meaning

Both verification methods are synchronous and codec-free. `VALID` proves only
structural format, member inventory, checksums, authority relationships, history,
sequence continuity and persisted bounds. It does not prove that user keys/documents
decode, that application identities match expectations, or that retrieval results are
correct.

Reports normalize the selected directory to an absolute path. Findings are immutable,
duplicate-free and sorted by `code`, `member`, then `detail`. A finding contains no
key/document payload. `sequence` is present only when a trustworthy structural
sequence was established. `authoritativeBytes` excludes the ownership lock and proven
non-authoritative remnants.

Reference-argument nulls fail with `NullPointerException`; malformed value components
fail with `IllegalArgumentException`. Access, ownership and unsupported-filesystem
failures that prevent a trustworthy report use `DurableOperationException`.

## Store verification

`verifyStore` requires an existing non-symbolic directory. For an initialized store it
opens the existing zero-length `gse.lock` without `CREATE`, obtains the ordinary V4
exclusive lock, and releases it after verification. A running writer therefore fails
with `STORAGE_IN_USE`. An absent ownership file produces `INCOMPLETE` without creating
one.

While holding the lock, the verifier independently parses:

1. metadata magic/version/history/identities/safety bounds/index descriptors and
   CRC32C;
2. checkpoint-manifest authority and CRC32C when present;
3. the authoritative checkpoint header, canonical slots, persisted bounds and CRC32C;
4. WAL generation headers, generation and sequence continuity, frame headers,
   payload structure, complete-frame CRC32C and the permitted final incomplete tail;
5. retained and authoritative byte inventories; and
6. every reserved, staging, unknown, symbolic, non-regular or hard-linked member.

The parser does not call `DurableRecovery`, open a WAL writable, truncate an incomplete
tail, rewrite a checksum, rename a member or delete a remnant. Checkpoint and WAL
payload bytes are streamed in bounded chunks instead of being allocated according to
file size.

An otherwise valid last WAL with a recognized incomplete frame prefix returns
`VALID_WITH_SAFE_REMNANTS` and `INCOMPLETE_WAL_TAIL`. Old pre-manifest WAL generations,
unnamed checkpoints and recognized V4 staging members are safe only after current
authority validates. Unknown members never become safe based on filename age.

## Backup verification

`verifyBackup` permits concurrent readers of a completed immutable bundle. It requires
the exact regular, non-symbolic three-member inventory:

```text
gse-backup-checkpoint
gse-backup-manifest
gse-backup-metadata
```

The verifier independently checks the source metadata/checkpoint CRC32C and structure,
completion-manifest CRC32C, source history and identities, checkpoint sequence,
canonical payload order, exact unsigned sizes, payload SHA-256 values, and the
domain-separated `gse-backup-v1-...` content digest. It checks each file identity,
size and modification timestamp across its read. A missing completion manifest is
`INCOMPLETE`; an extra member, alias, checksum mismatch or authority mismatch is
`CORRUPT`.

## Classification

| Status | Exact Phase 2 meaning |
|---|---|
| `VALID` | Supported authority and exact inventory validate with no status-changing finding. |
| `VALID_WITH_SAFE_REMNANTS` | Authority validates and every remnant is proven non-authoritative. |
| `INCOMPATIBLE` | Family and major are supported, bytes are intact, but minor-version policy differs. |
| `INCOMPLETE` | Required ownership, authority or completion publication is absent. |
| `CORRUPT` | Supported bytes violate checksum, framing, bounds, sequence, inventory or authority. |
| `UNSUPPORTED` | An intact header declares an unknown family or major version. |

Primary status is selected from accumulated evidence. Definite corruption outranks a
simultaneous missing member, and both findings remain visible. Unsupported and
incompatible classifications require an intact checksum before header policy is
considered.

Finding codes are stable uppercase identifiers. The emitted families cover member and
alias safety, missing authority, unsupported/incompatible headers, CRC/SHA integrity,
metadata/checkpoint bounds, WAL generation/frame/payload continuity, backup identity,
retained-byte overflow, safe remnants and changed-while-read detection.

## Independent evidence

Production Java parsing is separate from both V4 recovery and the repository Python
inspectors. Phase 2 runs it against generated stores plus the immutable published V4.0
format fixture matrix and the immutable V4.1 backup fixture. The Python
`storage_inspector.py` and `backup_format.py` parsers continue to validate those bytes
independently in CI.

## Phase boundary

Phase 2 makes no filesystem mutation beyond acquiring/releasing the already existing
OS file lock. Structural verification does not admit Phase 3 backup writing, Phase 4
typed verification/restore, or Phase 5 cleanup.
