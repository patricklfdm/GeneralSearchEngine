# Migration boundary: 4.3 to 4.4

## Dependency upgrade

Applications may update both GSE coordinates from `4.3.0` to `4.4.0` without an API
or storage migration. Java 21, artifact layout, retrieval behavior, durable defaults
and live/backup format meanings are unchanged. Existing `(1,0)`, `(1,1)` and `(1,2)`
stores remain in their declared formats and are not rewritten on open.

Upgrade the runtime and optional annotation processor together. Recompile, run the
application's own codec/index/query compatibility suite, take and independently
verify a current backup, then roll out using the same storage identity, schema
identity, codec identity, format and logical index configuration.

## Operational validation

For durable deployments, checkpoint and close cleanly before the first controlled
upgrade. Retain the untouched store and a verified backup until application-level
validation is complete. After open, compare sequence, document/key inventory, index
descriptors and representative complete query results, then perform one bounded
mutation, checkpoint, close and second reopen.

For `(1,2)`, derived images remain disposable. A complete warm reopen may load them;
missing, stale or invalid derived state follows the published fallback and refresh
rules. Do not copy derived files between stores or interpret a warm/cold timing
difference as an authority change.

## Rollback

Because V4.4 writes no new format or semantics, an untouched source or a verified
backup remains the rollback boundary. Stop V4.4 writes before rollback. If writes
were accepted after cutover, reconcile them at the application layer before opening
an older deployment; GSE does not merge histories or provide reverse replication.

V4.4 requires no offline migration job. Existing explicit V4.2/V4.3 migration APIs
retain their published source-preserving contracts, and unsupported edges still fail
before source mutation or target publication.

## Scope boundary

This release does not introduce repair, salvage, implicit upgrade, remote authority,
replication, consensus, sharding or any V5 capability. The executable public-only
reference remains `compatibility/v4-style-consumer`; normative guarantees remain in
the V4.0–V4.4 contracts.
