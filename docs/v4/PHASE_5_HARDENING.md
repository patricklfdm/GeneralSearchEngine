# V4.0 Phase 5 lifecycle and crash hardening

## Scope

Phase 5 closes lifecycle, concurrency and repeated-failure behavior over the accepted
WAL and checkpoint formats. It adds no public API and changes neither format `1.0` nor
published V1–V3.4 in-memory behavior. Phase 6 owns performance characterization and
paid cloud evidence.

## Lifecycle and concurrency matrix

The focused Java matrix covers every single and bulk mutation, successful no-ops,
all four supported dynamic index kinds, drop and rebuild, concurrent producers,
lock-free readers, explicit checkpoint coalescing, mutations admitted after a WAL
generation cut, close while checkpoint serialization is active, and rejection after
close admission stops. Every accepted Future is recovered with one contiguous durable
sequence.

## Deterministic I/O failure matrix

The package-private validation controls use `gse.v4.ioFailurePoint`; they are not API
or persisted configuration. Phase 5 exercises:

- checkpoint data rename failure before authority;
- manifest force and rename failure before authority;
- directory-force failure after manifest replacement;
- cleanup deletion and cleanup directory-force failure; and
- bounded short writes through `gse.v4.ioMaxWriteBytes`.

Pre-authority failures preserve the previous authority and keep a healthy WAL writer
usable. Failure after manifest replacement is ambiguous and makes the current writer
terminal until reopen. Cleanup failure is diagnostic: the new authority is valid,
older files may remain, and a later checkpoint retries conservative cleanup.

## Repeated-crash protocol

`scripts/v4/durable_repeat.py` keeps one storage history across eight child JVM hard
halts. The stable schedule alternates WAL publication, checkpoint authority before
cleanup, and checkpoint completion after cleanup. Every cycle performs independent
byte inspection, opens a separate recovery verifier, checks every prior document and
sequence, closes, and opens a second time before the next crash. Evidence uses the
existing checksummed V4 schema and deletes the engine workspace only after the final
oracle passes.

The inspector accepts conservatively retained pre-manifest WAL generations only when
their real headers and sequences are contiguous and the exact manifest generation and
first sequence match. It never treats retained history, staging, or an unreferenced
checkpoint as authority.

## Resource boundary

Repeated successful checkpoints must retain one authoritative checkpoint, manifest,
current WAL generation and fixed metadata/lock files after cleanup. The local matrix
runs 24 checkpoint cycles under a 256 KiB configured bound with three-byte writes and
asserts the retained metric and file cardinality after every cycle. Capacity rejection
and decode corruption remain covered by the accepted Phase 2/3 matrices.

No paid cloud resource is required in Phase 5. The `phase5-hardening` fake-cloud
failure drill proves that the preserved-device control plane, evidence schema and
cleanup contract can carry the repeated-recovery identity before Phase 6 measurement.
