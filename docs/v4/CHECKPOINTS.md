# V4.0 checkpoint and retention contract

## Authoritative checkpoint

A checkpoint is the complete durable logical state at one committed sequence `C`.
It preserves canonical slot order and internal IDs, `nextDocId`, supported index
configuration, storage identities, format metadata, and integrity information.

Checkpoint creation begins with a short writer-coordinated cut: force the current
generation, capture immutable logical state and sequence `C`, seal that generation,
create and force the next generation header and directory entry with first possible
sequence `C + 1`, and then resume admission. Checkpoint serialization uses the
captured immutable state while later units enter only the new generation. If
checkpoint construction fails, the old checkpoint plus both retained generations
still recover the history. The implementation may throttle serialization to bound
resources.

## Publication protocol

```text
capture sequence C
  -> seal old WAL and durably open post-C generation
  -> write a uniquely named staging checkpoint
  -> force checkpoint data
  -> validate complete bytes and checksum
  -> write and force staging manifest
  -> atomically replace the authoritative manifest in the same directory
  -> force the directory
  -> mark WAL <= C cleanup-eligible
```

Staging files are never recovery candidates. A crash before authoritative-manifest
publication leaves the previous checkpoint authoritative. A crash after publication
must recover the new checkpoint. Cleanup cannot precede publication and directory
durability.

## Corruption and fallback

V4.0 has exactly one authoritative checkpoint identity. If that checkpoint or its
manifest is missing, malformed, truncated, checksum-invalid, or incompatible,
initialized storage fails closed. Recovery does not silently choose an older
checkpoint, because that could return a state older than a successfully completed
mutation after required WAL history was cleaned.

Non-authoritative staging files may be ignored and cleaned only after successful open.
Stale but complete data files not referenced by the authoritative manifest never
outrank it.

## Trigger and lifecycle

Durable mode exposes explicit asynchronous `checkpoint()`. Configuration also defines
a positive automatic WAL-byte threshold. Crossing it requests a checkpoint without
changing mutation success semantics. Only one checkpoint may execute at a time;
concurrent requests share or serialize behind that work.

Close does not checkpoint by default. Recovery correctness is independent of clean
close and automatic checkpoint timing.

## Generations and disk bound

V4.0 uses the writer-coordinated generation cut above. Once checkpoint `C` is
authoritative and the post-`C` generation is safely active, closed generations whose
maximum sequence is at most `C` are cleanup-eligible. Deletion failure is
reported and retried; stale generations remain distinguishable and cannot be replayed
twice.

Configuration has a hard maximum retained engine-owned byte count greater than the
checkpoint trigger. Admission estimates the next frame before append. If the hard
limit would be exceeded, the operation fails with capacity diagnostics before sequence
allocation; reads continue and checkpoint/cleanup remain available. This is a bounded
V4.0 policy, not a deferred V4.1 correctness problem.

## Checkpoint failure

If staging or publication fails while WAL health remains known, the checkpoint Future
fails, the old checkpoint stays authoritative, and mutations may continue. If the
failure makes storage durability ambiguous or demonstrates a storage-wide I/O fault,
the durable writer enters terminal failure as defined by the completion contract.
