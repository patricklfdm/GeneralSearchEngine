# Migration boundary: 3.4 to 4.0

## Staying in memory

Existing applications may upgrade coordinates and continue using `build()` or
`fromAnnotatedClass(...)`. They supply no storage path or codec and retain the V3.4
process-lifetime behavior. V4.0 does not transparently persist an existing engine.

## Opting into durability

A durable application must deliberately provide a local directory, stable storage and
schema identities, deterministic key/document codec, safety bounds, checkpoint
threshold, and disk limit, then call `buildDurable(...)`.

The first open creates a new empty durable history. Importing an already populated
V3.4 in-memory instance is not implicit: the application must open a fresh durable
engine and bulk-add source-of-truth documents. Successful bulk completion is the
durable import boundary.

## Application responsibilities

- Treat accepted documents as immutable just as in V3.4.
- Keep codec and schema meanings stable for a storage identity.
- Change explicit identities/versions when persisted meaning changes.
- Use only built-in durable index/analyzer configurations.
- Place storage on a supported local filesystem and monitor capacity.
- Treat incomplete Futures at crash as indeterminate and inspect recovered state by
  business key or application idempotency rules.
- Back up or replicate the persistent device for physical-disk-loss protection.

## Reopen differences

Reopen blocks while documents decode, WAL replays, and indexes rebuild. Recovered
objects are newly decoded instances. Snapshot versions, metrics counters, and cursors
are process-local and reset/expire; durable sequence continues. Query truth, score
bits, canonical ordering, and successfully completed mutations must not change.

## Downgrade and format change

V3.4 cannot read V4 storage. Copying V4 files into an older engine is unsupported.
Changing codec/schema identities requires an explicit export/import or future offline
migration tool; opening under a different interpretation fails closed.
