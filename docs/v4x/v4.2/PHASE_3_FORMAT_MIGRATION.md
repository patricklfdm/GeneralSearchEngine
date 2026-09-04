# GeneralSearchEngine V4.2 Phase 3 format-only migration

Phase 3 activates the exact `gse-durable (1,1)` bytes frozen in Phase 2 and the
smallest reviewed migration edge: a closed canonical `(1,0)` source to a new `(1,1)`
history with unchanged logical records and persisted application identities.

## Explicit `(1,1)` operation

`DurableStorageConfig.Builder.format(DurableStorageFormat.V1_1)` now admits fresh
creation and exact reopen. Metadata, checkpoints, checkpoint manifests, WAL headers
and WAL frames all bind the canonical profile digest. The default remains byte-for-byte
`V1_0`; opening never upgrades either minor.

Live `(1,1)` engines support the inherited mutation, checkpoint and recovery
protocols. Backup produces exact `gse-backup (1,1)` with the `gse-backup-content-v2`
domain and `gse-backup-v2-<sha256>` identity. Typed verification and restore accept
that bundle only when the target explicitly selects `V1_1`; restore preserves the
source format and creates a fresh history.

## Phase 3 migration edge

The only admitted edge is:

```text
gse-durable (1,0) -- identity-format-v1@1 --> gse-durable (1,1)
```

Storage, schema and codec identities, codec version, key/document bounds, document
bound and ordered durable index descriptors must match. Every transformed key and
document must round-trip canonically and produce exactly the source canonical bytes.
Codec/schema/key transforms and index changes remain rejected until Phase 4.

The source must be closed, structurally valid, fully checkpointed and canonical: one
authoritative checkpoint and one empty post-checkpoint WAL generation, no incomplete
tail, old generation, staging member, operation remnant or unknown member. Planning
does not recover, checkpoint, truncate or clean the source.

## Planning and apply

The target builder owns the target schema and index definitions. Planning:

1. validates the absent non-overlapping target and supported local filesystem;
2. independently verifies the source and acquires exclusive ownership;
3. decodes the authoritative checkpoint under exact expected identities;
4. hashes every authoritative source member;
5. invokes the transform serially in slot order and binds canonical output bytes;
6. allocates a fresh target history;
7. computes exact target authoritative and reserved peak bytes; and
8. returns a deterministic plan for that history without filesystem output.

Apply reacquires and revalidates all authority, reruns the transform, and rejects a
changed request, source, plan or projection before publication. It writes a new
history into a unique sibling staging directory, forces each authority member,
verifies the staged target, atomically renames it to the absent final path, forces the
parent, performs structural and typed verification, normally opens/closes the target,
rehashes the source and removes the operation marker. Successful return is not
application cutover and does not authorize source removal.

## Failure and crash boundary

The additive `DurableMigrationException` family reports the exact frozen reason and
stage without application payload text. Prepublication failure leaves the final
target absent. Once rename may have published authority, failure is reported as
publication-indeterminate unless source preservation itself is disproved.

Production crash barriers accompany marker force, metadata force, checkpoint rename,
WAL force, manifest rename, final rename and parent force. The Phase 3 separate-JVM
gate exercises both a complete staged/pre-rename crash and a post-parent-force crash.
An independent verifier proves the source byte identity in both cases and requires
the final target to be absent before publication or structurally and semantically
valid afterward. Broader remnant cleanup and repeated-fault policy remain Phase 5.

## Deliberate exclusions

Phase 3 does not add automatic or in-place upgrade, downgrade, backup-to-migration,
online migration, record filtering/fan-out, changed codec/schema/key semantics,
target index rebuild, cutover, source deletion, cloud execution or baseline
registration.
