# GeneralSearchEngine V4.4 Phase 0 checklist

- **Status:** Accepted through protected PRs #132–#133
- **Scope:** Documentation-only final durable hardening freeze
- **Authoritative contract:** [PHASE_0_CONTRACT.md](PHASE_0_CONTRACT.md)

Checked items mean the candidate documents contain an explicit decision. They do not
record protected-master acceptance until the final acceptance section is completed.

## Scope and predecessor

- [x] V4.4 is final durable hardening and the immutable V5 comparison reference.
- [x] V4.4 is evidence-driven and may ship with no production-code change.
- [x] Signed `v4.3.0`, protected commit, exact-master CI, release workflow, Central
  deployment, production deployment, GitHub Release, clean consumers, baseline, and
  post-publication closure are pinned.
- [x] Phase 1 must resolve published `4.3.0` artifacts from fresh isolation.
- [x] V3.4 retrieval and all V4.0–V4.3 durability/operation/evolution/reopen guarantees
  are inherited without reinterpretation.
- [x] Phase 0 is documentation-only.

## Closed product boundary

- [x] No new public Java API is authorized by default.
- [x] No live or backup format `(1,3)` is introduced.
- [x] Exact `(1,0)`, `(1,1)`, and `(1,2)` meanings and bytes remain unchanged.
- [x] Default durable format remains `(1,0)` and in-memory behavior remains unchanged.
- [x] Published backup and migration edges remain the complete supported set.
- [x] No new authority member, automatic upgrade, repair, salvage, downgrade, or
  source deletion is implied.
- [x] Core and processor remain the only Maven artifacts.
- [x] Any API, format, authority, or migration expansion requires a reviewed Phase 0
  amendment before implementation.

## Deferred V5 architecture

- [x] Replication, consensus, leader/follower, sharding, distributed query, and
  multi-writer storage remain excluded.
- [x] Remote live WAL/object storage and zero-RPO cross-node guarantees remain
  excluded.
- [x] Vector/HNSW/hybrid retrieval, facets, new ranking, and changed retrieval
  semantics remain excluded.
- [x] Network filesystem, physical power-loss, firmware, and page-cache claims are not
  inferred from a JVM/VM harness.
- [x] A finding that requires a deferred capability blocks or moves to V5 instead of
  entering V4.4 as hidden hardening.

## Finding classification and production admission

- [x] Findings are classified as contract violation, measured regression,
  infrastructure defect, expected boundary, non-reproducible, or deferred
  architecture.
- [x] Only an admitted contract violation or measured regression may authorize a
  production change.
- [x] Admission requires exact source/environment, minimized reproduction, independent
  oracle, affected authority transitions, compatibility impact, bounds, and rollback.
- [x] Infrastructure defects are fixed and rerun rather than converted into weaker
  product thresholds.
- [x] Flaky or non-reproducible evidence does not authorize code by assertion.
- [x] A benchmark movement alone does not authorize production optimization.
- [x] Every admitted change is minimal and remains in its owning phase.

## Independent evidence

- [x] Expected results come from frozen logical models, independent byte parsers,
  immutable fixtures, isolated published-4.3 execution, or external inventories.
- [x] Production logs are diagnostic and never the sole proof.
- [x] Evidence bundles are schema-validated, source-bound, checksummed, bounded, and
  include failure logs and cleanup receipts.
- [x] Valid-authority cases prove complete retrieval equality and continued durable
  operation.
- [x] Invalid-authority cases prove exact fail-closed classification and no
  unauthorized mutation, repair, cleanup, or target publication.

## Local crash harness from Phase 1

- [x] Phase 1 establishes the V4.4 separate-process harness before production changes.
- [x] Writer, interrupter, inspector, recovery, verifier, and continuation are separate
  processes where process loss is claimed.
- [x] Stable barriers bind to real authority/cache force, rename, publication,
  completion, cleanup, and cutover transitions rather than sleeps.
- [x] Graceful close, `Runtime.halt`, external kill, injected I/O failure, and corrupt
  bytes are distinguished.
- [x] Independent pre-recovery inspection and inventory precede production open.
- [x] External deadlines terminate complete child-process groups and retain evidence.
- [x] Randomized cases print a replayable seed and have deterministic bounded replay.
- [x] The harness does not overclaim physical power-loss guarantees.
- [x] Every new admitted authority transition adds a barrier or proves existing
  coverage.

## Authority and corruption matrix

- [x] Metadata, checkpoint manifest/payload, WAL frame/generation/sequence,
  format/profile, schema/codec/storage identity, checksum, and digest faults are
  covered.
- [x] Backup structural/semantic and completion-publication faults are covered.
- [x] Migration stale-plan, source-change, transform, target, interruption,
  publication, source-preservation, and rollback faults are covered.
- [x] Derived catalog/component absence, stale/mismatch/corrupt/partial states,
  WAL-after-image, refresh, fallback, and cleanup races are covered.
- [x] Truncation, missing/duplicate/swapped/unknown members, links, permissions,
  read-only storage, changed inventory, I/O, and ENOSPC are covered.
- [x] Canonical failures retain inherited fail-closed reasons.
- [x] Derived-only failures never mask canonical corruption and rebuild only where the
  V4.3 contract permits it.
- [x] Corrupt or ambiguous state never grants cleanup authority.

## Lifecycle, format, and compatibility matrix

- [x] Fresh, WAL-only, checkpoint-only, checkpoint-plus-WAL, multiple-generation,
  automatic/explicit checkpoint, and repeated reopen paths are covered.
- [x] Single, bulk, document, and dynamic-index mutations run with concurrent readers
  and immutable snapshot checks.
- [x] Repeated mutation/checkpoint/backup/verify/restore/continue loops are covered.
- [x] Every published format-only, transform, index-change, direct `(1,2)`, and
  meaningful same-format migration path is covered.
- [x] Untouched-source rollback is verified with the appropriate published version.
- [x] Complete warm, partial/full fallback, restored/migrated cold-first, refresh,
  WAL-after-image, and derived cleanup paths are covered.
- [x] Repeated close/reopen and failed-open ownership/resource release are covered.
- [x] Documents, keys, descriptors, sequence, results, score bits, order, estimates,
  statistics, durable checksums, and continuation are compared.
- [x] Unsupported operations fail before source mutation or target publication.

## Scale, time, concurrency, and resources

- [x] Phase 1 freezes a frequent dense correctness workload and a larger persistent-
  corpus/long-duration workload.
- [x] Exact distributions, sizes, operations, threads, cadence, duration, heap, GC,
  filesystem/device, page-cache treatment, limits, deadlines, progress, and seed are
  recorded.
- [x] Peak/final heap, GC, CPU, wall time, operations, latency, throughput, I/O, all
  byte categories, peak provisioned bytes, and cleanup are recorded.
- [x] Allocation estimates are not mislabeled as measured allocation.
- [x] Retained and temporary bytes remain hard-bounded and overflow-safe.
- [x] There is no unbounded soak; timeout retains evidence and still runs cleanup.
- [x] Ordinary PR/master CI runs only bounded reduced matrices and never provisions
  paid resources.

## Published-4.3 paired controls

- [x] Phase 1 calibrates published `4.3.0` and current source in the same environment
  before production changes.
- [x] Correctness/checksum/cleanup equality is mandatory.
- [x] Provisional lower-is-better median/member ratio limits are `1.20`/`1.35`.
- [x] Provisional higher-is-better median/member ratio floors are `0.80`/`0.65`.
- [x] Outlier invalidation and replacement rules are declared before execution.
- [x] Incomparable metrics remain separate rather than producing false ratios.
- [x] Thresholds are release evidence gates, not portable user SLAs.
- [x] Phase 1 may tighten; weakening requires a reviewed Phase 0 amendment before
  production change or paid canonical execution.

## Fake cloud and paid evidence from Phase 1

- [x] Artifact schema is `gse-v44-final-durable-evidence-v1`.
- [x] Cloud suite is `v4.4-final-durable-suite-v1`.
- [x] Cloud preset is `v4.4-final-durable-v1`.
- [x] Eventual append-only baseline is `v4.4.0-final-durable-cloud`.
- [x] GCS prefix is `v4.4-final-durable/` and is evidence transport only.
- [x] Experiment is one member; canonical is three independent serial members.
- [x] The source VM is deleted before replacement-host proof where source loss is
  claimed.
- [x] Surviving targets continue writes, checkpoint, verify, close, and reopen again.
- [x] The known 32-global-vCPU and 500-GiB-regional-SSD envelope is respected unless a
  verified quota change is recorded.
- [x] Exact project/zone/machine/non-deprecated image/disks/filesystem/workload/runtime/
  cost/retention/GCS/OIDC/IAM/cleanup/summary are frozen during Phase 1.
- [x] Delete IAM is prefix-scoped and failure artifacts survive member failure.
- [x] Paid execution is Phase 6-only after exact-source CI, local/fake/dry-run/budget/
  IAM checks, explicit user initiation, and cleanup validation.

## Release toolchain and artifacts

- [x] Phase 1 freezes a machine-readable canonical OS/container, Java, Maven Wrapper,
  plugin, locale, timezone, file-mode, and timestamp identity.
- [x] Two clean independent canonical builds must produce identical six unsigned JAR
  hashes.
- [x] Phase 7 records the canonical candidate hashes.
- [x] Release records hashes immediately before signing/deploying the exact bytes.
- [x] Phase 8 matches all six Central JAR hashes and verifies detached signatures and
  repository checksums.
- [x] V4.3 empty-directory and JDK `legal/` differences remain transparently recorded.
- [x] V4.4 pins one canonical toolchain or normalizes ancillary entries before making
  cross-environment byte-identity claims.
- [x] Noncanonical JDK builds remain diagnostic unless normalization is proven.
- [x] The reproducibility claim cannot be silently weakened to close release.

## Phase ownership

- [x] Phase 1 owns `4.4.0-SNAPSHOT`, published baseline, API inventory, independent
  models/fixtures, harnesses, fake cloud, toolchain identity, and calibration only.
- [x] Phase 2 owns exhaustive local matrices and finding classification, not fixes.
- [x] Phase 3 owns only admitted minimal correctness/operational fixes.
- [x] Phase 4 owns bounded scale/resource/long-run hardening and only admitted measured
  internal optimization.
- [x] Phase 5 owns stabilization, compatibility, release artifacts/toolchain, cloud
  readiness, and V5 handoff draft.
- [x] Phase 6 alone owns paid evidence, independent review, and registration.
- [x] Phases 7 and 8 own candidate assembly and publication separately.
- [x] A zero-production-change V4.4 remains a valid outcome.

## Protected acceptance

- [x] Charter, contract, roadmap links, and checklist are reviewed on the Phase 0
  branch.
- [x] Documentation links and whitespace checks pass.
- [x] The diff contains no POM version, production code, executable test/harness,
  workflow, cloud-IAM, registry, or paid-resource change.
- [x] Phase 0 pull request required checks passed.
- [x] Phase 0 merged through protected PR #132 as
  `8fd5dafb544efe9df1e07dd6c2791b0d16d3a634`.
- [x] Exact-master CI run `34581708843` passed before Phase 1.
- [x] Supplemental acceptance record merged through protected PR #133 as `c59b828`;
  exact-master CI run `34583543174` passed.

## Exit decision

Phase 0 is accepted. Phase 1 may establish only the frozen non-production foundation;
production corrections and paid cloud work remain unauthorized until their owning
phases.
