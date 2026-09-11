# GeneralSearchEngine V4.4 development charter

- **Status:** Proposed governing charter for protected Phase 0 acceptance
- **Predecessor:** Published GeneralSearchEngine `4.3.0`
- **Theme:** Final durable hardening and an immutable V5 comparison reference

## Purpose

V4.0 established correct single-node durability, V4.1 added operational safety,
V4.2 added explicit storage evolution, and V4.3 added fast reopen through disposable
derived state. V4.4 asks the closing V4.x question:

> Can the complete single-node durable line survive representative scale, time,
> interruption, corruption, capacity, migration, replacement-host, and release-
> supply-chain stress without changing its published authority model?

V4.4 is evidence-driven hardening. It is not a feature quota that requires new
production code. If the accepted matrices find no contract violation or justified
optimization, V4.4 may consist of stronger tests, operational evidence, deterministic
release tooling, documentation, and final publication.

## Governing principles

1. Published V4.0 durability, V4.1 operations, V4.2 migration, V4.3 fast reopen, and
   V3.4 retrieval semantics remain frozen.
2. The default durable format remains exact `(1,0)`. Exact `(1,1)` and `(1,2)` remain
   explicit. V4.4 does not introduce `(1,3)` or change any published bytes.
3. The published Java API is closed by default. A new public type, member, enum
   constant, record component, exception reason, or Maven artifact requires a reviewed
   Phase 0 amendment before implementation.
4. A production change is admitted only for a reproducible contract violation or a
   measured, semantics-preserving resource/performance problem with an independent
   oracle and bounded regression proof.
5. Local separate-process crash testing, independent byte inspection, fake cloud,
   durable replacement-host planning, cleanup, cost, and release-toolchain evidence
   are first-class from Phase 1, before any production fix.
6. Canonical authority always fails closed. Final hardening never converts corruption
   into heuristic recovery, skips committed WAL, invents a sequence, or treats derived
   state as authority.
7. Scale claims must identify corpus, operations, duration, heap, filesystem, device,
   page-cache state, CPU, GC, I/O, retained bytes, temporary amplification, and exact
   source commit. “Large”, “long-running”, and “fast” never stand alone.
8. Cloud evidence uses independent serial members and replacement machines. One
   successful run is experiment evidence, not canonical proof.
9. Candidate and published artifact identity is established by a canonical declared
   release toolchain. Cross-JDK ancillary archive differences are either normalized or
   explicitly outside the byte-identity claim.
10. V4.4 ends with an explicit V5 handoff: frozen guarantees, supported formats and
    migrations, baselines, known limits, and deferred architecture are recorded.

## Scope

V4.4 adds or strengthens:

- an exact published-4.3 API, artifact, storage-format, fixture, and behavioral
  compatibility baseline;
- a complete inventory of V4.0–V4.3 authority transitions, failure classifications,
  crash barriers, formats, backup forms, migration edges, and derived-state paths;
- independent local matrices for mutation/checkpoint/backup/restore/migration/reopen/
  cleanup cycles, corruption, truncation, missing members, capacity, permissions,
  interruption, cancellation, concurrent reads, and repeated reopen;
- bounded large-corpus and long-duration evidence with retained-space, temporary-space,
  heap, GC, CPU, I/O, latency, throughput, and cleanup accounting;
- a quota-safe source-loss and replacement-host cloud lane established as a no-GCP
  fake control plane in Phase 1 and authorized for paid execution only in Phase 6;
- paired published-4.3 controls for final non-regression evidence;
- a canonical release-toolchain manifest and a path that binds candidate hashes to
  the exact unsigned artifacts later signed and deployed;
- an append-only `v4.4.0-final-durable-cloud` baseline; and
- a final V4.x compatibility, operational-boundary, and V5-handoff record.

Production changes are conditional. They may include the smallest internal correction
or measured optimization necessary to pass the accepted contract, but only in the
phase that owns it and only with independent regression evidence.

## Explicit exclusions

- replication, leader/follower operation, consensus, sharding, distributed query,
  multi-writer storage, or zero-RPO cross-node guarantees;
- remote live WAL, object-store live storage, network filesystems as a new supported
  authority, or persistent cross-node cursors;
- vector, HNSW, hybrid retrieval, facets, new ranking, changed scoring, matching,
  ordering, pagination, highlighting, or Explain semantics;
- live-format `(1,3)`, backup-format `(1,3)`, implicit upgrade, in-place migration,
  downgrade, history merge, repair, salvage, or source deletion;
- making a derived image, backup, cloud object, benchmark result, or release artifact
  a substitute for canonical live-store authority;
- a new public API, new Maven module/artifact, CLI, daemon, service, or management
  plane without a separately accepted Phase 0 amendment;
- unbounded fuzzing, unbounded soak, production workloads in ordinary CI, or paid
  cloud execution before Phase 6; and
- claims about physical power-loss behavior, storage firmware, network partitions,
  or page-cache eviction that the harness does not actually create and observe.

## Published predecessor

The predecessor is signed tag `v4.3.0` at protected-master commit
`b6b4660ac6bf2cadc6b94be5f2db29e41ab0fe6d`. Exact-master CI run `34572477812`
passed before tagging. Release workflow `34573738901`, Maven Central deployment
`2526d3b2-7ec9-4ad6-ad97-31621ee2de99`, production deployment `6388475724`,
GitHub Release `386867175`, and clean remote V3/V4 consumers were independently
verified. Post-publication documentation closed through protected PR #131 as
`78805e642da99eca46dfdf26c77b058c23e1ffff`; exact-master CI run `34578997788`
passed.

The fast-reopen baseline is `v4.3.0-fast-reopen-cloud`, bound to source
`1d59ba9c354f5ea5ca4ebc8d8b5b30519479aac6` and canonical run `34557940276`.
V4.0, V4.1, and V4.2 retain their distinct published baselines; V4.4 aggregates but
does not overwrite them.

## Compatibility and format freeze

V4.4 recognizes the existing exact live formats:

```text
gse-durable (1,0)  published default canonical format
gse-durable (1,1)  published explicit storage-evolution format
gse-durable (1,2)  published explicit reconstructible-derived-state format
```

It recognizes the corresponding published backup formats and only the migration
edges already accepted by V4.2 and V4.3. Existing stores, backups, fixtures, format
profiles, identities, checksums, digests, canonical ordering, and failure
classifications remain byte-compatible.

The default builder and all in-memory construction remain unchanged. Opening a store
never upgrades it. Migration remains offline, source-preserving, reviewed, explicit,
and absent-target. Derived files remain optional, reconstructible, checkpoint-bound,
and excluded from canonical recovery and backup authority.

## Defect and optimization admission

A proposed production change must have an admission record containing:

1. the exact source commit and environment;
2. a minimized deterministic reproducer or statistically justified paired workload;
3. the published contract or bounded resource invariant that is violated;
4. an independent logical or physical oracle that fails before the change;
5. the smallest proposed correction and the files/authority transitions it touches;
6. crash, corruption, concurrency, capacity, cross-format, and published-4.3 impact;
7. evidence that unrelated V3/V4 behavior is unchanged; and
8. a rollback and release decision if the correction cannot be proven safe.

A benchmark movement alone does not authorize code. A test that only restates the
production implementation is not independent evidence. A flaky or environment-only
failure must be classified and stabilized before it can justify production changes.

If a finding requires a new format, new authority, incompatible API, relaxed
fail-closed behavior, or a V5-deferred capability, V4.4 stops and requests a reviewed
architecture decision instead of hiding the change inside hardening.

## Evidence program

Phase 1 establishes the evidence foundation before production changes:

- an exact public API inventory and clean published-4.3 consumer baseline;
- independent parsers/oracles for the published live, backup, migration, cleanup, and
  derived-state fixture families used by the matrix;
- a separate-JVM crash driver with stable barrier names and fail-fast artifact
  collection;
- a deterministic fault/corruption manifest whose cases state expected pre-open
  inspection, recovery result, and post-open continuation;
- a no-GCP fake cloud control plane modeling serial members, fresh/detached disks,
  source deletion, replacement hosts, GCS transport, retention, failures, and complete
  cleanup;
- bounded scale and soak probes with independent watchdogs and progress evidence;
- paired published-4.3/current measurements; and
- a canonical release-toolchain manifest and two-workspace reproducibility probe.

The identities are distinct:

```text
artifact schema: gse-v44-final-durable-evidence-v1
cloud suite:     v4.4-final-durable-suite-v1
cloud preset:    v4.4-final-durable-v1
baseline:        v4.4.0-final-durable-cloud
GCS prefix:      v4.4-final-durable/
```

Phase 1 freezes exact workload, environment, thresholds, quota envelope, maximum
runtime, maximum cost, retention, summary, evidence hashes, and cleanup receipts.
Experiment uses one member. Canonical uses three independent serial members. Paid work
requires exact-source CI, local/fake/dry-run success, budget validation, verified IAM,
explicit user initiation, and proof that failure paths retain downloadable cleanup
evidence.

## Final matrix families

The complete program must cover, without requiring every case to be paid-cloud:

1. in-memory and durable mutation/search compatibility under concurrent readers;
2. exact `(1,0)`, `(1,1)`, and `(1,2)` create/checkpoint/close/reopen cycles;
3. WAL-only, checkpoint-only, checkpoint-plus-WAL, generation rollover, retained-byte
   pressure, and repeated crash recovery;
4. structural/semantic verification, backup, source loss, restore, continuation, and
   repeated backup/restore cycles;
5. every supported format-only, transform, index-change, and direct `(1,2)` migration,
   including untouched-source rollback;
6. complete warm, partial fallback, full fallback, restored/migrated cold-first, WAL-
   after-image, refresh, and derived cleanup paths;
7. canonical corruption versus non-authoritative derived corruption, truncation,
   swapping, missing/duplicate members, stale plans, unknown members, permissions,
   I/O and ENOSPC;
8. repeated interruption at authority publication, force, rename, catalog, completion,
   cleanup, and cutover boundaries;
9. large persistent corpus, long mutation/checkpoint/backup/reopen cycles, heap/disk/
   temporary amplification, GC, CPU and I/O; and
10. retained-disk replacement-machine recovery followed by continued writes,
    checkpoint, verification, close, and second reopen.

Every valid-authority case proves a complete retrieval checksum and continued durable
operation. Every invalid-authority case proves the exact fail-closed classification
and no unauthorized mutation, repair, cleanup, or target publication.

## Release artifact boundary

V4.3 demonstrated same-toolchain reproducibility, while locally built sources and
Javadoc archives differed from GitHub-runner archives only through empty directory
entries and JDK-provided `legal/` files. V4.4 turns that observation into an explicit
supply-chain contract:

- Phase 1 selects a canonical builder identity including OS/container digest, Java
  vendor and full version, Maven Wrapper distribution digest, locale, timezone, and
  output timestamp policy;
- two clean canonical builds in independent workspaces must produce the same six
  unsigned JAR hashes;
- the release job records hashes immediately before signing/deploying and publishes
  those exact main, sources, and Javadoc bytes;
- post-publication verification must match all six Central JARs to the recorded
  canonical hashes and verify detached signatures and repository checksums; and
- a different JDK distribution is a diagnostic content comparison unless ancillary
  entries are normalized. It must not be mislabeled as a canonical byte-identity
  failure.

V4.4 may pin the canonical toolchain or normalize deterministic ancillary archive
entries. Either choice must be implemented and tested before Phase 7; silently
weakening the reproducibility claim is not allowed.

## Phase ownership

| Phase | Authorized work | Exit evidence |
|---|---|---|
| 0 | Documentation-only charter, contract, checklist, maps, and phase boundaries | protected acceptance of exact scope |
| 1 | `4.4.0-SNAPSHOT`, published-4.3/API/fixture gates, independent models, crash/fault/soak/fake-cloud scaffolding, toolchain manifest, and calibration | no production behavior change or paid work |
| 2 | Complete local authority, corruption, interruption, format, backup, migration, derived-state, and differential matrix | findings classified; no speculative fix |
| 3 | Only admitted minimal correctness/operational fixes and their independent regression evidence | no API/format/authority expansion |
| 4 | Bounded scale, concurrency, retained-space, long-run and performance hardening; only admitted measured internal optimization | no paid evidence |
| 5 | Full stabilization, published compatibility, release-toolchain/artifact hardening, local/fake/dry-run cloud readiness, and V5 handoff draft | exact-source release-evidence entry gate |
| 6 | User-initiated experiment/canonical cloud evidence, independent review, and append-only registration | immutable accepted final baseline |
| 7 | Final coordinates, consumers, compatibility, Javadocs, exact artifacts, release documents and protected candidate acceptance | no publication |
| 8 | Signed tag, Central, deployment, GitHub Release, remote consumers, artifact reconciliation, and post-publication proof | V4.x closed for V5 handoff |

## Release decision

V4.4 ships only if all accepted correctness matrices pass, every admitted finding is
closed or explicitly blocks release, resources and temporary amplification remain
bounded, replacement-host evidence is complete, published-4.3 paired controls show no
unaccepted regression, cleanup is proven on success and failure, and canonical release
artifacts reconcile exactly with Maven Central.

No production diff is itself an acceptable outcome. An unmeasured feature or broad
rewrite is not. If the evidence cannot support a truthful final durable baseline,
V4.4 remains unreleased and V5 does not inherit an asserted reference that was not
proven.
