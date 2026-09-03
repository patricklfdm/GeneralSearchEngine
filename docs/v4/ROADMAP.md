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

Phase 2 merged through protected PR #79 at
`7056a5ad00d1f38757f984c51ad21d83ee922443`. The additive durable API, fresh-store
ownership, immutable metadata and generation header, framed logical units,
force-before-publication coordinator, independent byte inspectors, and all ten
production WAL crash barriers form the Phase 3 storage boundary. The exact-master CI
run `33583721019` passed on that protected merge.

### Phase 3 — recovery

Implement startup validation, WAL-only bootstrap, deterministic replay, canonical
slot and `nextDocId` restoration, derived-index rebuild, incomplete-tail handling,
fail-closed corruption, and uninterrupted-versus-recovered differential tests.

Phase 3 merged through protected PR #80 at `2664638`; exact-master CI run
`33589193180` passed. Authoritative WAL-only reopen,
bounded two-pass scanning,
tail truncation and force, canonical replay, derived-index reconstruction, three stable
recovery barriers, independent corruption fixtures, uninterrupted-versus-recovered
semantic comparison, and the local/fake-cloud failure-drill matrix are accepted.

### Phase 4 — checkpoints and bounded history

Implement versioned checkpoints, non-authoritative staging, integrity validation,
durable manifest publication, explicit and threshold-triggered checkpoints, WAL
generation rollover, conservative cleanup, and checkpoint-plus-WAL recovery.

Phase 4 is accepted through protected PR #81 at
`32e9c84c944ebd4f5c0b9f2d69efd690d25058cc`; exact-master CI run `33594843119`
passed. Checkpoint/manifest format `1.0`, writer-cut plus asynchronous serialization,
explicit coalescing, automatic threshold requests, multi-generation recovery,
fail-closed authority, conservative cleanup, eleven crash barriers, independent byte
inspection and the fake-cloud checkpoint failure drill form the Phase 5 boundary.

### Phase 5 — lifecycle and crash hardening

Cover every mutation and supported dynamic-index transition, close/admission races,
concurrent producers, repeated process crashes, checkpoint/WAL races, disk capacity,
retained-footprint bounds, and long-running recovery loops.

Phase 5 local validation is complete. It adds no API or format change. Deterministic
I/O faults, concurrent producer/reader and close races, bounded short-write checkpoint
loops, eight same-history hard crashes with per-cycle independent recovery, and the
fake-cloud hardening drill pass together with the reactor, published compatibility,
release artifacts, reproducibility and JMH gates. Phase 5 is accepted through protected
PR #82 at `c9a8b472`; exact-master CI run `33597658600` passed.

### Phase 6 — performance and operational hardening

Measure in-memory compatibility, durable mutation latency/throughput, force grouping,
checkpoint cost, replay/rebuild/open time, disk amplification, large corpora, and the
independent durable cloud family. Optimize only from reviewed evidence.

Phase 6 implementation and paid evidence are complete. Local validation, the paid
experiment, preserved-disk replacement-VM drill and serial three-member canonical run
all passed. The reviewed set from exact source
`fe2060b9a872e66ff0067be6e8b7c900f0099708` is registered append-only as
`v4.0.0-durable-cloud`. The protected registration/evidence merge is PR #88 at
`adbe96d9bf73bf03d3082f2ceb58a66ca75dd325`; exact-master CI run
`33694586398` passed and forms the Phase 7 boundary.

### Phase 7 — release candidate

Convert to final `4.0.0`; close migration and storage documentation, public API,
published-3.4 compatibility, independent consumers, strict Javadocs, artifacts,
reproducibility, release automation, and protected-master gates.

Phase 7 is complete. The candidate added no production behavior or format change: it
converted the eight active coordinates, froze format `1.0` fixtures, added the
independent V4 durable consumer, and made both local and remote release validation
exercise that boundary. It merged through protected PR #90 as `0f2ea5e`; the
evidence-workspace boundary merged through PR #91 as final protected-master commit
`73479da344f24f69e15904660d46783459d80dcf`. Exact-master CI run `33705710878`
passed before tagging.

### Phase 8 — publication

Publish signed `v4.0.0`, Maven Central artifacts, and GitHub Release. Run a clean
external durable consumer, verify deployment and storage fixtures, record the final
durable evidence identity, and close post-publication documentation.

Phase 8 is complete. Signed `v4.0.0` points to the exact final protected commit.
Release workflow run `33706352253` passed, core and processor `4.0.0` artifacts are
published and remotely verified, clean V3/V4 consumers and immutable format fixtures
pass against Central, deployment `6235596306` reports success, and GitHub Release
`381684854` is published as neither draft nor prerelease.

## Phase dependency

Each phase begins from a successful exact-master CI run for the prior accepted phase.
Production durability starts only in Phase 2. Later phases may amend contracts only
through an explicit reviewed change that states storage and migration consequences.

## Deferred beyond V4.0

Distributed search, replication, consensus, multiple writers, remote live storage,
persisted derived indexes, online format upgrade, cross-engine persistent cursors,
new retrieval semantics, and richer operational controls remain outside V4.0.
