# GeneralSearchEngine V4.x roadmap

- **Status:** Proposed post-V4.0 governing roadmap
- **Reference baseline:** Published GeneralSearchEngine `4.0.0`
- **Theme:** Mature the durable single-node engine from correctness to operability,
  evolvability, fast reopen, and final hardening.

## Why the roadmap changes after V4.0

V4.0 delivered more operational maturity than its original outline required. It
already includes opt-in single-node durability, deterministic codecs and storage
identities, framed CRC32C WAL, contiguous committed sequences, group force, WAL
generations, explicit and automatic checkpoints, retained-byte hard limits,
deterministic recovery, corruption classification, durability metrics,
repeated-crash evidence, and the immutable `v4.0.0-durable-cloud` baseline.

The remaining V4.x line therefore does not allocate another minor release to basic
WAL rotation or checkpoint thresholds.

```text
V4.0  Correct Durability               COMPLETE
  ↓
  V4.1  Operational Safety               ACTIVE PHASE 2 VERIFICATION
  ↓
V4.2  Storage Evolution
  ↓
V4.3  Fast Reopen
  ↓
V4.4  Final Durable Hardening
  ↓
V5    Next Architecture Boundary
```

## Governing rules

1. V4.x remains a single-node durable search-engine line.
2. No minor release silently changes V4.0 force-before-completion, crash
   indeterminacy, checkpoint authority, corruption fail-closed, immutable-snapshot,
   single-writer, or retrieval semantics.
3. The maturity sequence is correctness, operability, evolvability, performance,
   then evidence.
4. Each minor release begins with an accepted documentation-only Phase 0 contract.
5. Production code, version conversion, executable infrastructure, and paid work are
   admitted only by the phase that owns them.
6. A roadmap entry is direction, not executable semantics; its minor-release Phase 0
   contract is authoritative.

## V4.0 — Correct Durability — complete

Published `4.0.0` proves that completed durable mutations survive supported process
and machine failures when the persistent block device survives; incomplete futures
are indeterminate at crash; committed sequence order is authoritative; bulk units
recover atomically; committed corruption fails closed; checkpoints publish
atomically; derived indexes rebuild deterministically; and retained storage is
bounded.

The signed release, Maven Central artifacts, production deployment, release evidence,
and `v4.0.0-durable-cloud` registration are immutable V4.x references. The complete
record remains under [`docs/v4/`](../v4/README.md).

## V4.1 — Operational Safety

### Goal

Make a V4 durable store safe to inspect, back up, restore, and maintain without
weakening V4.0 fail-closed guarantees.

### Required capabilities

- an explicit checkpoint-consistent full backup at one durable sequence;
- an independently verifiable immutable backup bundle;
- restore as a new history into an absent target;
- codec-free offline structural verification;
- typed semantic backup and restored-state verification;
- authoritative, non-authoritative, incomplete, incompatible, corrupt, and
  unsupported classification;
- offline dry-run-first cleanup of proven non-authoritative remnants;
- bounded diagnostics and operational failure categories;
- local child-process interruption matrices from Phase 1 onward;
- fake-cloud planning and replacement-host paid evidence from the start of the
  implementation program.

### Exclusions

- incremental or deduplicated backup;
- zero-RPO replication or remote synchronous commit;
- skipping corrupt committed WAL;
- heuristic repair or history merge;
- live format `gse-durable (1,0)` changes;
- automatic migration;
- persisted derived indexes;
- distributed or retrieval-semantic changes.

### Core rule

A backup is a complete independently restorable artifact for one known durable
sequence, not a recursive live-directory copy. The exact V4.1 decisions are frozen in
the [development charter](v4.1/DEVELOPMENT_CHARTER.md) and
[Phase 0 contract](v4.1/PHASE_0_CONTRACT.md).

## V4.2 — Storage Evolution

### Goal

Make durable storage safely evolvable across future format, codec, and schema
changes.

### Required direction

- readable-format policy beyond `1.0`;
- explicit offline migration with dry-run and capacity preflight;
- source-preserving migration into a new target;
- target verification before cutover;
- explicit codec/schema transforms;
- rollback-safe operator guidance;
- immutable migration fixtures and an independent inspector.

Opening an old store must never silently rewrite it. The expected initial model is:

```text
format 1.0 source
    ↓ explicit offline migration
format 1.1 target
```

The source remains untouched until the target is independently verified. V4.2 must
also define the reusable format-evolution framework required by V4.3; it must not be a
one-off converter whose policy cannot support later derived formats.

## V4.3 — Fast Reopen

### Goal

Reduce restart cost for large durable corpora without making derived indexes
authoritative.

V4.3 may persist derived index images or an equivalent recovery accelerator only
after V4.2 supplies explicit versioning and migration. Potential staged work is:

1. persisted structured indexes;
2. persisted text-index state;
3. selective deterministic rebuild fallback;
4. evidence-driven optimization.

Canonical documents and durable logical index configuration remain authoritative.
Every derived image binds to checkpoint sequence, history identity, schema identity,
codec identity/version, analyzer/index configuration, derived-format version, and
integrity metadata. Failure to validate an optional derived image must select a
contracted deterministic rebuild path rather than reinterpret canonical state.

Memory mapping is not implied; it requires separate platform profiling and evidence.

## V4.4 — Final Durable Hardening

### Goal

Freeze the mature single-node durable line as the comparison reference for V5.

V4.4 is predominantly hardening and evidence, not feature expansion. Expected themes
include:

- large persistent corpora and bounded heap/disk;
- long-running mutation/checkpoint/backup cycles;
- repeated crash/recovery/restore loops;
- supported storage migrations;
- persisted-index reopen and rebuild fallback;
- corruption and operational-failure matrices;
- replacement-machine recovery;
- recovery latency, backup cost, and storage amplification;
- an immutable baseline such as `v4.4.0-final-durable-cloud`.

The final baseline remains distinct from `v3.4.0-in-memory-cloud`,
`v4.0.0-durable-cloud`, and the V4.1 operational-safety family. If measurements reveal
no justified V4.4 production change, the version may remain an evidence-and-release
hardening line; roadmap presence alone does not require speculative code.

## Deferred beyond V4.x

- replication, leader/follower semantics, or consensus;
- sharding, distributed query execution, or multi-writer storage;
- remote live WAL or object-store live storage;
- zero-RPO cross-node durability or cross-node persistent cursors;
- vector/HNSW/hybrid retrieval;
- new ranking semantics.

These require a future V5 Phase 0 architecture decision.

## Repair policy

Safe V4.x operations are verification, diagnosis, classification, restore from a
known-good backup, cleanup of proven non-authoritative remnants, and explicit
supported migration.

V4.x does not skip corrupt committed WAL, invent missing sequences, heuristically
rewrite an authoritative checkpoint, merge unrelated histories, or silently salvage
into the same history. A future salvage tool would create a separate explicitly
marked history under its own contract.

## Version summary

| Version | Theme | Governing question |
|---|---|---|
| 4.0 | Correct Durability | Can completed state survive supported crashes correctly? |
| 4.1 | Operational Safety | Can operators safely verify, back up, restore, and maintain it? |
| 4.2 | Storage Evolution | Can durable state evolve without implicit rewriting? |
| 4.3 | Fast Reopen | Can large stores restart quickly without derived authority? |
| 4.4 | Final Durable Hardening | Is the single-node durable line ready to freeze before V5? |

## Current authority

V4.1 Phase 1 is accepted at protected-master commit `e183face`; exact-master CI run
`33717370973` passed. Phase 2 owns only codec-free read-only structural verification,
stable reports and the classification matrix. Backup writing, semantic verification,
restore and cleanup remain blocked by their later owning phases.
