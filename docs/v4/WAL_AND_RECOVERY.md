# V4.0 WAL and recovery contract

## WAL unit requirements

Each unit belongs to one storage history and records bounded, deterministic values for
magic, format family/version, frame length, sequence, operation type, payload length,
payload, and integrity checksum. A bulk payload includes its complete element count
and all key/document operations within one frame.

Decoders validate fixed headers, versions, lengths, checked arithmetic, configured
key/document limits, element counts, sequence, and checksum before allocating or
decoding caller data. Java native serialization is forbidden.

The exact byte offsets and checksum algorithm become an implementation appendix in
Phase 2, before a production writer is merged. That appendix may choose mechanics but
cannot alter the behaviors frozen here.

## Terminal tail versus corruption

Only a physically incomplete final frame may be discarded. It must begin immediately
after the last completely valid frame and end at the physical end of the newest WAL
generation. Examples are a partial fixed header, declared payload cut short by EOF,
or a missing trailer/checksum caused by abrupt termination.

A physically complete frame with an invalid checksum, type, version, length relation,
payload, sequence, or history identity is corruption and fails closed even when it is
the last frame. Invalid bytes between valid frames, a gap, and any invalid older
generation also fail closed. Recovery never scans ahead or skips damaged bytes.

When recovery permits an incomplete terminal frame, it truncates that generation to
the last valid boundary before accepting mutations, forces the truncation as required,
and records the action in diagnostics.

## Recovery algorithm

Open performs these steps without exposing an engine:

1. normalize the configured path and acquire exclusive ownership;
2. classify fresh versus initialized storage;
3. validate history, format, schema/configuration, codec, limits, and platform;
4. load the one authoritative checkpoint, if present;
5. restore canonical slots, internal IDs, `nextDocId`, index configuration, and
   checkpoint sequence;
6. validate WAL generations and scan units after the checkpoint boundary;
7. require contiguous sequence order and validate every complete unit;
8. discard only the permitted physically incomplete newest tail;
9. replay each valid unit atomically into an independent candidate state;
10. rebuild all supported derived indexes deterministically;
11. publish one recovered immutable snapshot at process-local version zero; and
12. enable normal admission only after every step succeeds.

Fresh empty storage initializes one new random history identity at sequence zero.
WAL-only bootstrap is supported before the first checkpoint. Empty storage is never a
fallback for damaged initialized storage.

## Recovery equivalence

For accepted history `H` and crash point `P`:

```text
V3.4 oracle state after the durable prefix of H at P
    ==
V4 state after recovering crash(H, P)
```

Comparison includes canonical slots and IDs, documents, supported dynamic indexes,
query/filter truth, ranked membership, exact score bits and order, phrase/fuzzy/BOOL/
BOOST, Explain, highlighting, exact totals, and first-page behavior. Existing cursors
are invalid across restart by contract.

## Failure precedence

Open fails before returning an engine in this order:

1. ownership, path, access, or unsupported-filesystem failure;
2. unsupported or incompatible storage/history/schema/codec identity;
3. authoritative checkpoint structure or integrity failure;
4. WAL generation, framing, integrity, or sequence failure;
5. key/document decode or key/document identity mismatch;
6. replay or deterministic index-rebuild failure; or
7. successful recovery.

Diagnostics preserve the primary category and safe contextual identity without
silently substituting an empty or older logical state.
