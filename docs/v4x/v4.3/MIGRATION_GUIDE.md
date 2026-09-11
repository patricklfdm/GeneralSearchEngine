# Migration boundary: 4.2 to 4.3

## Upgrade without format migration

Applications may update both GSE coordinates from `4.2.0` to `4.3.0` without
changing ordinary in-memory or durable startup code. Java 21, artifact layout,
retrieval behavior and default live format `(1,0)` are unchanged. Existing `(1,0)`
and `(1,1)` stores remain byte-for-byte in their declared formats.

Choose `(1,2)` only when faster reopen is operationally useful and its additional
derived-state disk budget is acceptable. Persisted images are accelerators, not a
new source of truth.

## Prepare an explicit migration

Stop writes, checkpoint and close the source. Keep a verified backup outside source
and target. Record source format, history, sequence, identities, index configuration
and a byte digest. Plan a source-preserving offline migration into an absent target,
using the same deterministic API introduced in V4.2 but selecting
`DurableStorageFormat.V1_2` and a reviewed `maxDerivedStateBytes` bound.

Planning is read-only. Review the source authority, exact `(1,2)` target profile,
transform and projection digests, target history, index changes and capacity bounds.
Apply only the reviewed plan while the source remains closed and unchanged.

## Validate cold then warm behavior

Migration writes canonical target authority, not derived images. The first target
open must therefore report `FULL_FALLBACK`, reconstruct every configured built-in
index from canonical documents, preserve query results and attempt a bounded derived
refresh. Inspect the closed target with
`DurableStorageOperations.inspectDerivedState(target)` and require `VALID` before
evaluating warm behavior.

The next open should report `COMPLETE_WARM`, with every checkpoint index loaded and
none rebuilt. Compare equality, range, prefix and text results with a forced rebuild,
then perform a bounded mutation, checkpoint, close and reopen. Performance ratios are
diagnostic; correctness never depends on meeting a latency threshold.

## Cutover, rollback and cleanup

Cutover remains application/operator orchestration. Keep the `(1,1)` source immutable
during the rollback window. Published `4.2.0` can reopen that untouched source but
cannot open the `(1,2)` target. Writes accepted only by the target require external
reconciliation before rollback because GSE supplies neither reverse migration nor
history merge.

Do not copy catalog or component files between stores, treat images as backup
members, or delete files by name. Use codec-free inspection and the dry-run-first,
authority-bound cleanup API. Unknown or ambiguous members remain fail-closed.

The executable public-only reference is `compatibility/v4-style-consumer`; normative
semantics remain in the V4.3 Phase 0 and phase-specific contracts.
