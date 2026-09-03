# GeneralSearchEngine V4.1 Phase 4 semantic verification and restore

## Scope

Phase 4 implements the typed half of V4.1 operational safety. It adds synchronous
semantic verification on `SearchEngineBuilder<K,T>` and logical restore into an absent
target. It does not add cleanup, migration, incremental backup, a new live format, or
paid cloud execution.

## Typed semantic pass

`verifyDurableBackup` first requires a codec-free structural `VALID` result. It then
matches the expected storage, schema and codec identities, codec version, bounded
decode limits and builder startup-index descriptors. Identity mismatch returns a
bounded `IDENTITY_MISMATCH` report before document decode.

The production checkpoint reader performs the canonical bounded pass. Every live key
and document is decoded once in that pass, round-trip encoding is checked, key and
document identity must agree, duplicate keys are rejected, and canonical slots,
`nextDocId`, live count and dynamic durable-index descriptors are retained. Derived
indexes are rebuilt from decoded documents and are never treated as authority. Codec
failure and reconstructed-state failure are reported separately without payload bytes.

The immutable bundle is structurally verified again before a successful semantic
report is returned. A changed or no-longer-valid bundle therefore fails closed rather
than producing a stale semantic claim.

## New-history restore

Restore validates target/path admission before it invokes the codec. The target must
be absent below an existing real local-filesystem parent and may not overlap the
backup in either direction. The full persisted target config must equal the source
metadata except for its target directory. Sequence `Long.MAX_VALUE` is rejected with
the inherited `SEQUENCE_EXHAUSTED` category before addition can overflow.

After structural and semantic verification, restore creates a distinct non-zero
history and re-encodes an ordinary `gse-durable (1,0)` store:

- a zero-length `gse.lock`;
- `gse-metadata` containing the new history and unchanged persisted identities/bounds;
- one checkpoint at source sequence `B`, encoded against the new history;
- `gse-checkpoint-manifest` selecting that checkpoint and WAL generation 2; and
- an empty generation-2 WAL beginning at `B + 1`.

No provenance, receipt, backup manifest, or V4.1-only sidecar enters the target. The
returned `DurableRestoreResult` carries external provenance instead.

## Publication and failure behavior

A restore uses `.gse-v41-restore-<uuid32>.staging` and a locked sibling
`.operation` marker whose operation kind is 2. The marker and staging directory are
forced before authority work. Metadata, checkpoint, WAL and manifest are individually
forced; the completed staging directory passes codec-free structural verification and
a second typed state validation before publication.

Publication is an absent-target atomic sibling rename followed by parent-directory
force, final structural and typed verification, marker removal and a second parent
force. Normal pre-publication failure removes only members created in the unique
staging directory and its marker. Once the final directory has been renamed, automatic
rollback never deletes it; independent verification resolves caller-indeterminate
completion.

## Compatibility

The restored target is intentionally readable by published V4.0 when the same schema,
codec, startup indexes and persisted safety bounds are supplied. Its first continued
mutation receives sequence `B + 1`; checkpoint, close and later reopen retain the new
history and ordinary V4 recovery semantics.
