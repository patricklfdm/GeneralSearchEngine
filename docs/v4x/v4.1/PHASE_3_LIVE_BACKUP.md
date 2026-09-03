# GeneralSearchEngine V4.1 Phase 3 live backup

## Scope

Phase 3 implements the frozen asynchronous live-engine backup operation. It adds no
semantic verifier, restore or public cleanup operation. The source remains an ordinary
`gse-durable (1,0)` store; all operation staging and the immutable bundle are siblings
outside the source directory.

## Exact cut

`DurableSearchEngine.backup` admits one writer-ordered control task. At the task's
position the writer selects the current published durable sequence `B`, cuts a new WAL
generation and publishes a complete source checkpoint exactly at `B`. The checkpoint
is pinned before the writer coordination finishes. Mutations and later checkpoints
may then proceed while a dedicated executor copies the immutable metadata/checkpoint
bytes. A later checkpoint cleanup skips the pin; releasing the pin never rewrites
source authority.

A sequence-zero source is valid. An unrelated active checkpoint is not reused as a
backup by timing accident. Only one backup may be active; a second request fails with
`OPERATION_IN_PROGRESS`. Close rejects new requests and waits for an accepted backup
to release its pin and finish.

## Bundle and publication

The writer emits exactly:

```text
gse-backup-checkpoint
gse-backup-manifest
gse-backup-metadata
```

Metadata and checkpoint are exact bounded source copies. SHA-256 payload descriptors,
the domain-separated canonical content identity and the checksummed `gse-backup (1,0)`
manifest match the immutable Phase 1 format. Production and independent Python
parsers both accept production-generated bundles.

The final target and a unique `.gse-v41-backup-<uuid>.staging` directory share one
existing real parent. A checksummed locked sibling `.operation` marker binds the kind,
UUID, staging basename and final basename. Payload files are streamed and forced;
the manifest is written and atomically published last. The complete staging bundle is
structurally verified, atomically renamed to the absent final target, parent-forced,
and verified again. The marker is removed and its parent forced before successful
future completion. No operation overwrites or deletes a caller-created final target.

The marker layout is big-endian `GSEOP100`, major/minor `(1,0)`, operation kind byte
`1`, UUID most/least bits, length-prefixed staging basename, length-prefixed target
basename, then CRC32C. It never serializes an absolute path.

## Failure and interruption

Target copy, force, hash, capacity and publication failures complete the backup future
exceptionally without making a known-good source terminal. Before final publication,
normal failure removes only exact operation-owned members. After final rename, the
bundle and marker are retained for independent classification; successful return is
never inferred merely from reaching a filesystem step.

Sixteen named crash barriers cover admission/cut, source checkpoint authority, pin,
marker, partial payloads, payload forces, manifest force/rename, final rename, parent
force and pre-completion. Every abrupt child is inspected before reopen by independent
V4/V4.1 parsers. A replacement JVM then reopens the source at sequence 1 and continues
at sequence 2. No crash case relies on production open to classify the pre-open state.

## Deferred work

Phase 4 owns typed semantic verification and new-history restore. Phase 5 owns public
plan-bound cleanup of the operation remnants deliberately left by abrupt death.
