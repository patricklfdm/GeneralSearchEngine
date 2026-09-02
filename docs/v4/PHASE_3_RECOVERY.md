# V4.0 Phase 3 WAL-only recovery

## Scope

Phase 3 turns the Phase 2 generation-1 WAL into authoritative initialized-store
reopen. It does not add checkpoints, manifests, multiple generations, rollover,
cleanup, format migration, persisted derived indexes, or cross-process cursor reuse.
Those boundaries remain unchanged for Phase 4 or later.

## Open and validation order

Durable open normalizes the configured directory, rejects symbolic or unsupported
storage, and holds one exclusive lock for the engine lifetime. A fresh directory still
creates metadata and the generation-1 header. An initialized directory must contain
exactly metadata and the generation-1 WAL in addition to the lock file; missing,
unknown, symbolic, or non-regular members fail closed.

Before replay, open validates metadata size, CRC32C, strict UTF-8 structure, format,
non-zero history identity, storage/schema/codec identity, configured safety bounds,
startup index descriptors, retained capacity, WAL generation header and every complete
frame. The generation header is revalidated before the replay pass. Initialization
never falls back to an empty store after any validation failure.

## Bounded replay

The generation is scanned twice. The first pass validates the complete prefix and
classifies only an EOF-cut newest frame as a permitted incomplete tail. If present,
that tail is truncated to the last valid boundary and forced before replay. A complete
invalid checksum, header, length, type, payload, sequence or history identity remains
corruption even at physical EOF.

The second pass reads at most one bounded frame at a time. It decodes and canonically
re-encodes business keys and documents, verifies document/key identity, and applies
contiguous single, bulk, no-op and supported dynamic-index units into private state.
Bulk payloads are decoded and validated as one logical unit before application. No
recovered state is exposed until the whole pass and index rebuild succeed.

## Restored truth

Replay restores the accepted sequence, key-to-internal-ID mapping, canonical sparse
slots, live documents, `nextDocId`, and supported index configuration. Equality,
range, prefix and simple-text indexes are reconstructed deterministically from the
canonical live slots. The recovered engine exposes one process-local snapshot at
version zero while preserving the durable sequence separately. A normal write after
reopen consumes the next contiguous sequence, and repeated reopen produces the same
state. Existing search cursors remain invalid across restart.

## Stable failure categories

- ownership, filesystem and access failures retain their Phase 2 categories;
- incompatible metadata, identity, safety bounds and startup indexes use
  `INCOMPATIBLE_STORAGE`;
- generation, frame, checksum, sequence and complete-payload structure failures use
  `CORRUPT_WAL`;
- codec decode, canonical round trip, or key/document identity failure uses
  `CODEC_FAILURE`;
- logically impossible but structurally valid history uses `REPLAY_FAILURE`; and
- deterministic derived-index reconstruction failure uses `INDEX_REBUILD_FAILURE`.

Open preserves the primary failure and releases every partially acquired resource. It
never publishes a partially replayed snapshot.

## Crash and evidence boundary

The three Phase 3 recovery barriers are documented in
[the crash harness contract](CRASH_HARNESS_AND_CLOUD_LANE.md). The production harness
crashes during tail truncation, replay, and ready publication, then uses another JVM
to recover, compare the independent durable prefix, append one new unit, and reopen
again. Independent Python fixtures cover cut header/payload/trailer, valid-CRC invalid
payload, and valid-CRC sequence gap without calling the production reader.
