# V4.0 Phase 2 storage and WAL baseline

## Entry and boundary

Phase 2 begins from accepted protected-master commit
`8758106d30223cc1ad6c2faf66a2f0d1131d507c`; exact-master CI run `33578036261` passed.
It admits the frozen additive durable API, exclusive fresh-directory ownership,
immutable metadata, deterministic codec validation, bounded framed WAL units,
contiguous sequence allocation, group force, publication ordering, durability metrics,
and dynamic built-in index transitions.

Phase 2 deliberately does not open initialized storage. It provides no replay,
incomplete-tail truncation, derived-index rebuild, checkpoint, manifest, generation
rollover, cleanup, or paid cloud execution. `checkpoint()` is present as the frozen API
and fails explicitly until Phase 4; checkpoint on a closed engine uses durable CLOSED.

## Writer integration

The V3.4 in-memory writer remains authoritative. Durable mode inserts one optional
commit coordinator after each private candidate has passed schema/codec/capacity
validation and before its immutable state is published:

```text
prepare candidate and canonical bytes
  -> allocate one sequence per logical unit
  -> append complete frame(s)
  -> force once for the group
  -> publish the prepared snapshot
  -> expose published sequence
  -> complete successful Futures
```

Ordinary `build()` constructs no coordinator and retains the prior branch and timing
order. Empty bulk remains an immediate no-op. A non-empty bulk is one frame and one
sequence. Successful missing remove/drop consumes one sequence. Installed built-in
index create and drop are durable transitions; unsupported definitions fail before
sequencing.

## Failure boundary

Codec round-trip, decoded-key consistency, candidate, frame-size, live-document and
retained-capacity rejection occur before sequence allocation and leave the writer
usable. Append/force failure or sequence exhaustion is terminal: queued writes fail,
the last published snapshot remains readable, and only close releases ownership.

The format is frozen in [Phase 2 storage format](PHASE_2_STORAGE_FORMAT.md). The local
matrix reaches all ten production WAL barriers through a separate JVM, adds one
external-kill case, validates complete-prefix/tail structure independently, retains a
checksummed artifact and labels actual recovery `DEFERRED_PHASE3` rather than claiming
reader behavior that is not implemented.

## Local acceptance evidence

The full reactor passes 401 core and 5 processor tests with zero failures. Published
1.0.0 through 3.4.0 Japicmp comparisons, all three independent consumers, strict
Javadocs, six release artifacts and two-build byte reproducibility pass. V4's frozen
additive API requires retiring the V3.4-only `breakBuildOnModifications` zero-addition
rule for the 3.3 comparison; binary and source incompatibility gates remain enabled for
every published baseline. Protected PR and exact-master evidence remain pending.
