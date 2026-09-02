# V4 durable single-node roadmap

## Goal

V4 introduces opt-in local durability while preserving the published V3.4 search and
publication semantics. Documents, their canonical internal order, supported index
configuration, and committed sequence metadata are durable truth. Search indexes are
derived state in V4.0 and are rebuilt on open.

## Phase order

### Phase 0 — contract freeze

Freeze scope, public API shape, sequence and completion semantics, codec and storage
identity, WAL and checkpoint rules, recovery and corruption behavior, lifecycle,
platform assumptions, resource bounds, compatibility, validation, and evidence. Freeze
the local process-crash protocol, stable barrier IDs, evidence bundle, fake/cloud
control plane, persistent-disk failure drill, cost, retention, and cleanup contracts as
first-class architecture. This phase changes documentation only.

### Phase 1 — pre-change foundation

Move all active coordinates atomically to `4.0.0-SNAPSHOT`. Pin published `3.4.0` as
the immediate compatibility and behavioral baseline. Add API/consumer fixtures,
independent history and recovery models, process-crash/corruption harness scaffolding,
storage inspection utilities, the executable artifact validator, fake cloud durable
lane, and pre-change in-memory evidence. No production WAL.

Phase 1 is accepted at protected-master commit
`8758106d30223cc1ad6c2faf66a2f0d1131d507c`; exact-master CI run `33578036261`
passed. The snapshot version, published-3.4 compatibility gate, independent history
oracle, separate-JVM crash scaffold, evidence validator, storage inspector, and fake
durable cloud lane are the accepted entry boundary for production storage work.

### Phase 2 — storage ownership and WAL

Implement exclusive directory ownership, storage metadata, deterministic codecs,
contiguous committed sequences, bounded framed WAL records, checksums, atomic single
and bulk units, group force, exact Future ordering, terminal writer failure, and
format inspection tests.

Phase 2 is in implementation from the accepted Phase 1 boundary. The additive durable
API, fresh-store ownership, immutable metadata and generation header, framed logical
units, force-before-publication coordinator, independent byte inspectors, and all ten
production WAL crash barriers are implemented locally. Full reactor/release validation
and protected acceptance remain open. Authoritative reopen/replay is intentionally not
claimed before Phase 3.

### Phase 3 — recovery

Implement startup validation, WAL-only bootstrap, deterministic replay, canonical
slot and `nextDocId` restoration, derived-index rebuild, incomplete-tail handling,
fail-closed corruption, and uninterrupted-versus-recovered differential tests.

### Phase 4 — checkpoints and bounded history

Implement versioned checkpoints, non-authoritative staging, integrity validation,
durable manifest publication, explicit and threshold-triggered checkpoints, WAL
generation rollover, conservative cleanup, and checkpoint-plus-WAL recovery.

### Phase 5 — lifecycle and crash hardening

Cover every mutation and supported dynamic-index transition, close/admission races,
concurrent producers, repeated process crashes, checkpoint/WAL races, disk capacity,
retained-footprint bounds, and long-running recovery loops.

### Phase 6 — performance and operational hardening

Measure in-memory compatibility, durable mutation latency/throughput, force grouping,
checkpoint cost, replay/rebuild/open time, disk amplification, large corpora, and the
independent durable cloud family. Optimize only from reviewed evidence.

### Phase 7 — release candidate

Convert to final `4.0.0`; close migration and storage documentation, public API,
published-3.4 compatibility, independent consumers, strict Javadocs, artifacts,
reproducibility, release automation, and protected-master gates.

### Phase 8 — publication

Publish signed `v4.0.0`, Maven Central artifacts, and GitHub Release. Run a clean
external durable consumer, verify deployment and storage fixtures, record the final
durable evidence identity, and close post-publication documentation.

## Phase dependency

Each phase begins from a successful exact-master CI run for the prior accepted phase.
Production durability starts only in Phase 2. Later phases may amend contracts only
through an explicit reviewed change that states storage and migration consequences.

## Deferred beyond V4.0

Distributed search, replication, consensus, multiple writers, remote live storage,
persisted derived indexes, online format upgrade, cross-engine persistent cursors,
new retrieval semantics, and richer operational controls remain outside V4.0.
