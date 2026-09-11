# GeneralSearchEngine V4.4 Phase 0 final-hardening contract

- **Phase:** 0 — Final durable hardening and V5-reference freeze
- **Status:** Candidate for protected acceptance
- **Reference baseline:** Published GeneralSearchEngine `4.3.0`
- **Production V4.4 changes:** Authorized only after evidence admission in their
  owning later phase

## Authority and interpretation

This document is the normative V4.4 contract. The
[development charter](DEVELOPMENT_CHARTER.md) defines the release boundary, and the
[Phase 0 checklist](PHASE_0_CHECKLIST.md) records whether each required decision is
explicit. A conflict with a published V3.4 or V4.0–V4.3 guarantee blocks Phase 0; it
is not an implicit amendment.

Normative terms `MUST`, `MUST NOT`, `SHOULD`, and `MAY` have their ordinary standards
meaning. V4.4 hardening MUST preserve the difference between tested behavior,
measured evidence, and portable product guarantees.

## Exact predecessor identity

The predecessor is signed tag `v4.3.0` at protected-master commit
`b6b4660ac6bf2cadc6b94be5f2db29e41ab0fe6d`. Exact-master CI `34572477812`,
release workflow `34573738901`, Maven Central deployment
`2526d3b2-7ec9-4ad6-ad97-31621ee2de99`, production deployment `6388475724`,
GitHub Release `386867175`, and clean remote V3/V4 consumers passed. Published
coordinates are:

```text
io.github.patricklfdm:general-search-engine:4.3.0
io.github.patricklfdm:general-search-engine-processor:4.3.0
```

The post-publication evidence record merged through protected PR #131 as
`78805e642da99eca46dfdf26c77b058c23e1ffff`; exact-master CI `34578997788`
passed. Phase 1 MUST resolve published `4.3.0` from a fresh isolated repository and
MUST pin its API, artifacts, formats, fixtures, behavior, and failure boundaries.
Current reactor output is not a published baseline.

## Inherited guarantees

V4.4 inherits without reinterpretation:

- V3.4 immutable snapshots, lock-free readers, single-writer publication, mutation
  ordering, matching, scoring, sorting, pagination, highlighting, Explain, dynamic
  indexes, cancellation, and in-memory lifecycle behavior;
- V4.0 force-before-completion, incomplete-Future crash indeterminacy, contiguous WAL
  logical units, bulk atomicity, checkpoint authority, deterministic recovery,
  corruption fail-closed, exclusive ownership, and bounded retained storage;
- V4.1 codec-free structural verification, typed semantic verification, exact-cut
  backup, new-history restore, plan-bound cleanup, operational classifications, and
  source-loss/replacement-host semantics;
- V4.2 exact `(1,0)`/`(1,1)` readability, explicit format selection, profile binding,
  source-preserving offline migration, transforms, absent-target publication,
  operator-owned cutover, and rollback boundaries; and
- V4.3 exact `(1,2)`, canonical-only backup, direct migration targets, optional
  reconstructible images, selective/full fallback, bounded refresh, derived
  inspection/cleanup, and complete-snapshot reopen semantics.

No test, optimization, packaging change, or operational convenience may weaken these
guarantees.

## Closed product surface

V4.4 MUST begin with no new public Java API and no new storage format. Specifically:

- live formats remain exactly `(1,0)`, `(1,1)`, and `(1,2)`;
- backup formats remain their published exact counterparts;
- default durable and in-memory construction remain unchanged;
- Maven coordinates remain the core and processor artifacts only;
- no published constructor, record component, enum order, exception reason, default
  method, builder behavior, or serialized identity changes; and
- no new supported migration edge, authority member, repair mode, or automatic
  upgrade is implied.

Phase 1 MUST freeze an independently generated public API inventory and compile clean
published-style consumers. Any later need for API or format expansion requires a
separate reviewed Phase 0 amendment. A change is not exempt merely because it is
additive under Java binary compatibility.

Private implementation changes MAY occur only after admission and MUST preserve all
public and persisted behavior. Tests, harnesses, documentation, benchmark-only
instrumentation, and workflow safety changes do not require production-code admission
but remain owned by their phases.

## Finding classification and admission

Every Phase 2–5 finding MUST be recorded as one of:

- `CONTRACT_VIOLATION`: deterministic correctness, durability, authority,
  compatibility, or bounded-resource failure;
- `MEASURED_REGRESSION`: statistically supported degradation against a frozen paired
  control without semantic failure;
- `INFRASTRUCTURE_DEFECT`: harness, workflow, IAM, quota, artifact collection, cleanup,
  or environment defect that does not establish a product failure;
- `EXPECTED_BOUNDARY`: behavior required by the published contract;
- `NON_REPRODUCIBLE`: insufficient evidence after bounded repeat and artifact review;
  or
- `DEFERRED_ARCHITECTURE`: a real need whose safe solution crosses the V5 boundary.

Only `CONTRACT_VIOLATION` and an accepted `MEASURED_REGRESSION` may admit production
changes. Admission requires exact source/environment identity, minimized reproduction,
independent expected result, affected authority transitions, resource bounds, cross-
format impact, and an explicit rollback decision.

An infrastructure defect MUST be fixed in infrastructure and rerun. It MUST NOT be
used to relax a product threshold. A non-reproducible finding cannot block or justify
code by assertion alone, but its retained evidence and disposition remain in the
phase record.

## Independent evidence

Evidence is independent only when the expected outcome is not calculated by calling
the same production path under test. At least one of the following MUST establish the
oracle for each family:

- a frozen logical reference model;
- a codec-free byte parser with separately implemented framing/checksum/order rules;
- immutable handcrafted fixture bytes and digest;
- published-4.3 execution from an isolated dependency repository;
- a query-result/checksum oracle built before the tested interruption; or
- an external filesystem/resource inventory captured independently of engine reports.

Production logs are diagnostic input, not sole proof. Every evidence bundle MUST be
checksummed, schema-validated, bounded, source-bound, and retain stdout/stderr plus a
cleanup receipt on failure.

## Local crash and fault harness

Phase 1 MUST create the V4.4 local harness before a V4.4 production change. It MUST:

- run writer, interrupter, inspector, recovery, verifier, and continuation in separate
  JVM processes where process loss is claimed;
- use stable named barriers tied to real publication/force/rename/completion
  transitions rather than sleeps;
- distinguish graceful close, `Runtime.halt`, external kill, startup failure, injected
  I/O failure, and malformed/corrupt bytes;
- capture a pre-recovery inventory and independent inspection before production open;
- run with an external deadline and terminate the complete child-process group on
  timeout;
- retain seed, command, barrier, exit status, source hash, environment, and evidence
  paths; and
- prove continued mutation, checkpoint, close, and second reopen whenever canonical
  authority remains valid.

The harness MUST NOT claim physical power-loss or disk-cache guarantees from JVM
termination. Randomized cases require a printed replayable seed and a deterministic
bounded reproduction path. Every new production authority transition added by an
admitted fix requires a corresponding barrier or a documented proof that an existing
barrier already covers it.

## Authority and corruption matrix

The local exhaustive matrix MUST distinguish canonical authority from disposable or
staged state. It includes at least:

- metadata, manifest, checkpoint, WAL frame/generation, sequence, format/profile,
  schema/codec/storage identity, and canonical checksum/digest faults;
- backup metadata/checkpoint/completion faults and semantic codec/key/document
  disagreement;
- migration source change, stale plan, target collision, transform failure,
  interruption, completion publication, and rollback-source preservation;
- derived catalog/component absence, staleness, mismatch, corruption, partial
  generation, WAL-after-image, refresh interruption, and cleanup races;
- truncation at framing boundaries and inside length/checksum/payload fields;
- missing, duplicate, swapped, unknown, hard-linked, symlinked, permission-denied,
  read-only, and changed-inventory cases; and
- ENOSPC and injected failures at create, write, force, rename, directory force,
  cleanup, and result publication.

Canonical faults MUST retain their exact inherited fail-closed result. Derived-only
faults MUST rebuild/fallback when the published V4.3 contract permits it and MUST NOT
mask a canonical fault. A corrupt or ambiguous member grants no cleanup permission.
Failed migration/restore publication MUST leave the source unchanged and MUST NOT
publish an apparently complete target.

## Lifecycle and format matrix

The matrix MUST exercise all three exact live formats and every published supported
operation. At minimum it covers:

- fresh store, WAL-only, checkpoint-only, checkpoint-plus-WAL, multiple WAL
  generations, automatic/explicit checkpoint, and repeated reopen;
- single/bulk/document/index mutations with concurrent readers and immutable snapshot
  checks;
- repeated mutation/checkpoint/backup/verify/restore/continue loops;
- `(1,0)` to `(1,1)`, `(1,0)` to `(1,2)`, `(1,1)` to `(1,2)`, and meaningful
  same-format migration cases already published, including transforms/index changes;
- untouched-source rollback using the appropriate published predecessor;
- `(1,2)` complete warm, structured/text partial fallback, catalog/full fallback,
  restored/migrated cold-first refresh, dynamic create/drop, and cleanup; and
- repeated open/close and failed-open resource release/exclusive ownership.

Every successful case compares documents, keys, index descriptors, sequence, complete
query results, score bits, order, estimates, statistics, durable checksums, and the
next continued mutation. Unsupported edges MUST fail before source mutation or target
publication.

## Scale, duration, concurrency, and resources

Phase 1 MUST calibrate and freeze at least two bounded workload classes:

1. a deterministic dense correctness workload that runs frequently and exercises the
   complete feature matrix; and
2. a larger persistent-corpus/long-duration workload that stresses retained storage,
   checkpoints, backups, migrations, derived images, reopen, and concurrent reads.

The final plan MUST state exact document/token/index distributions, key/value sizes,
operation mix, reader/writer counts, checkpoint/backup cadence, migration count,
duration, heap, GC, CPU, filesystem/device, page-cache treatment, disk limits,
watchdog/progress interval, and deterministic seed.

Every run MUST record peak and final heap, GC count/time, process CPU, wall time,
logical operation counts, latency distributions, throughput, read/write bytes,
canonical/derived/backup/target/staging bytes, retained bytes, peak provisioned bytes,
and cleanup. Allocation estimates MUST be labeled as estimates unless measured by a
specified profiler.

There is no unbounded soak. Local and cloud processes have external deadlines. A
timeout is a failure with retained evidence, not a reason to omit cleanup.

## Paired non-regression policy

Phase 1 MUST run a published `4.3.0` control and the current source under the same
workload/environment before production changes. It then freezes exact release gates.
Unless a reviewed Phase 0 amendment establishes a better calibrated bound, the
provisional canonical limits are:

- every correctness/checksum/cleanup result is exact;
- for latency/cost/amplification metrics where lower is better, the current three-
  member median ratio to paired published 4.3 is at most `1.20`, and no member exceeds
  `1.35`;
- for throughput metrics where higher is better, the current median is at least
  `0.80` of paired published 4.3, and no member is below `0.65`; and
- no outlier is discarded without a predeclared machine/environment invalidation rule
  and a separately authorized replacement member.

Metrics whose operation changed legitimately MUST be reported separately rather than
combined into a misleading ratio. Thresholds are release evidence gates for the
frozen environment, not portable user SLAs. Phase 1 may tighten these values. Any
weakening requires a reviewed documentation amendment before an affected production
change or paid canonical run.

## Cloud lane from Phase 1

Phase 1 MUST establish a no-GCP fake lane and dry-run contract with identities:

```text
evidence schema: gse-v44-final-durable-evidence-v1
suite:           v4.4-final-durable-suite-v1
preset:          v4.4-final-durable-v1
baseline:        v4.4.0-final-durable-cloud
GCS prefix:      v4.4-final-durable/
```

Experiment is one member. Canonical is three independent serial members. The final
topology MUST stay within the known project envelope of 32 global vCPUs and 500 GiB
regional SSD unless a separately verified quota increase is recorded. At most one
30-vCPU member runs at a time. Data/target disks are reused or deleted between cells
so peak data plus boot disk remains within the frozen bound.

The source VM creates authority and evidence, is deleted where source loss is claimed,
and a fresh replacement VM performs recovery/restore/migration/reopen verification.
Detaching and reattaching a persistent disk alone is not replacement-host proof unless
the source VM is actually deleted. Continued writes, checkpoint, verification, close,
and a second reopen are mandatory on the surviving target.

Phase 1 freezes exact project, zone, machine, non-deprecated image identity, boot/data
disk type and size, filesystem/mount, scheduling, corpus, duration, maximum member
runtime, maximum complete-run cost, artifact retention, GCS prefix, OIDC workflow
allowlist, IAM prefix conditions, cleanup order, and job summary.

GCS is transport/evidence retention only. It is never live authority. IAM delete
permission MUST be restricted to the V4.4 prefix. Failure artifacts MUST upload even
when a member fails, and cleanup properties MUST distinguish every VM, disk, and
staging object.

Paid execution is Phase 6-only and user-initiated after exact-source CI, local tests,
fake cloud, dry-run, budget validation, WIF/IAM review, and explicit confirmation.

## Release-toolchain and artifact contract

Phase 1 MUST create one machine-readable canonical release-toolchain identity that
pins:

- operating-system or container image digest;
- Java distribution and full runtime/tool version;
- Maven Wrapper distribution URL and SHA-256;
- Maven/plugin versions used for compiler, source, Javadoc, JAR, GPG, and deployment;
- locale, timezone, file-mode policy, output timestamp, and relevant environment; and
- the exact set of two POMs and six unsigned main/sources/Javadoc JARs.

Phase 5 MUST prove two clean builds in independent workspaces under this identity are
byte-identical. The Phase 7 candidate MUST record those six hashes. The release
workflow MUST record the six unsigned hashes immediately before signing/deployment,
and MUST ensure the deployed JAR bytes are those recorded bytes. Phase 8 MUST download
Central artifacts, verify signatures and repository checksums, and require all six
JAR SHA-256 values to match.

The locally observed V4.3 empty-directory and JDK `legal/` differences are accepted
as a cross-distribution packaging observation, not silently erased history. V4.4 MUST
choose one of:

1. use the exact canonical toolchain for candidate and release identity; or
2. normalize ancillary archive entries and prove the normalized archives across the
   supported build environments.

Diagnostic builds on other JDK distributions MAY compare extracted semantic content,
but MUST NOT be presented as canonical byte identity unless option 2 is implemented.

## CI and artifact retention

Ordinary PR/master CI MUST remain bounded. It runs deterministic reduced matrices and
must not provision GCP. Longer local matrices use explicit scripts and retained
workspaces on failure. Paid workflows remain manual and trusted-master-only.

Evidence schemas MUST reject unknown/missing fields, source/profile mismatch,
nonpositive required measurements, checksum mismatch, duplicate members, incomparable
environments, missing cleanup, and attempted baseline replacement. Raw downloaded
cloud evidence remains excluded from Git; only reviewed summaries and append-only
registrations are tracked.

## Phase ownership

| Phase | Authorized work | Explicitly not yet authorized |
|---|---|---|
| 0 | these documents and indexes | POM, code, tests, scripts, workflows, IAM, registry, or paid changes |
| 1 | `4.4.0-SNAPSHOT`, published-4.3 gates, API inventory, independent oracles/fixtures, crash/fault/soak/fake-cloud scaffolding, canonical-toolchain manifest, and calibration | production behavior changes and paid runs |
| 2 | exhaustive local matrix implementation/execution and finding classification | production fixes |
| 3 | only admitted minimal correctness/operational fixes with independent regressions | API, format, authority, or feature expansion |
| 4 | bounded scale/concurrency/resource/long-run hardening and only admitted measured internal optimization | paid evidence or unmeasured tuning |
| 5 | stabilization, compatibility, artifact/toolchain hardening, local/fake/dry-run cloud readiness, and V5 handoff draft | paid evidence and final registration |
| 6 | experiment/canonical cloud execution, independent review, and append-only registration | speculative production change |
| 7 | final coordinates, consumers, compatibility, Javadocs, exact artifacts, release docs, and protected acceptance | tag or publication |
| 8 | signed tag, Central, deployment, GitHub Release, remote proof, reconciliation, and V4.x closure | V5 implementation |

## Phase 0 exit gate

Phase 0 exits only when the checklist confirms:

- exact predecessor evidence and inherited guarantees are pinned;
- product API, artifacts, authority, formats, backups, migrations, and defaults are
  closed by default;
- finding classification and production-change admission are explicit;
- independent local crash/fault evidence precedes production fixes;
- complete authority, lifecycle, format, scale, duration, concurrency, resource, and
  replacement-host matrices are bounded;
- paired published-4.3 controls and provisional non-regression rules are explicit;
- fake cloud, quotas, cost, GCS/IAM, retention, cleanup, and paid-run authority are
  frozen before cloud implementation;
- canonical release-toolchain and Central artifact reconciliation close the V4.3
  packaging-boundary lesson; and
- phase ownership permits a zero-production-change release while prohibiting hidden
  feature or V5 work.

After protected acceptance, Phase 1 may open `4.4.0-SNAPSHOT` and build only the
foundation named above. It may not change production behavior or execute paid cloud
work.
