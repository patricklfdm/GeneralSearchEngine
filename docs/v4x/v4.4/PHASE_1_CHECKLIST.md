# GeneralSearchEngine V4.4 Phase 1 checklist

- **Status:** Local implementation complete; protected acceptance pending
- **Scope:** Non-production final-hardening evidence foundation

## Entry and coordinates

- [x] Phase 0 acceptance PR #133 merged as `c59b828`.
- [x] Exact-master CI run `34583543174` passed.
- [x] Core, processor, reactor, example and four consumers use
  `4.4.0-SNAPSHOT` atomically.
- [x] No `src/main` production behavior, public API or persisted format changed.
- [x] No paid workflow, IAM mutation, cloud resource or registry entry exists.

## Published 4.3 and closed public surface

- [x] Published `4.3.0` core is pinned to SHA-256 `c5ecf5cf…778583`.
- [x] Fresh isolated resolution and checksum verification are configured.
- [x] Japicmp against published 4.3 rejects every public modification, including
  otherwise binary-compatible additions.
- [x] Independent `javap` inventory freezes 177 public types, 2,939 canonical lines
  and inventory SHA-256 `d67f7f18…d83650b`.
- [x] Published/current compiler emission order is normalized without removing
  declarations, descriptors or constants.
- [x] Current JAR exactly matches the published inventory.
- [x] Four published-style consumers target the snapshot coordinates.

## Independent fixtures and classifications

- [x] Ten final-hardening matrix families are frozen.
- [x] Twenty bounded representative cases name fault, oracle, expected result and
  continuation requirement.
- [x] Every family is represented and every case uses an accepted independent oracle.
- [x] Exact `(1,0)`, `(1,1)` and `(1,2)` are the complete format inventory.
- [x] All six finding classifications are frozen.
- [x] Fixture inventory and contents are checksummed and fail closed on drift.
- [x] Fixtures say `PHASE2_PENDING` and claim no production execution.

## Local crash/fault and evidence infrastructure

- [x] Stable barrier `v44-phase1-model-publication-v1` is explicit.
- [x] Graceful close, runtime halt, external kill, startup failure, injected I/O,
  malformed bytes and corrupt bytes are distinct cases.
- [x] External kill is issued by a separate interrupter JVM.
- [x] Writer, inspector, recovery and continuation are separate JVM roles.
- [x] Independent Python inspection occurs before recovery and validates CRC32C and
  exact semantic fields.
- [x] Valid authority continues through mutation, second publication and second
  inspection.
- [x] Startup/I/O paths prove no canonical publication; malformed/corrupt paths fail
  closed.
- [x] Every process is externally deadline-bound.
- [x] Strict checksummed evidence binds source, seed, case, exit, bounded logs and
  exact cleanup.
- [x] An inherited real `v4-wal-after-force-v1` external-kill bridge performs
  codec-free pre-open inspection, recovery, continued mutation and repeated reopen.
- [x] The scaffold is test-only and makes no power-loss or production-format claim.

## Calibration, resources and fake cloud

- [x] Published 4.3 and current source run the same 20,000-document, four-index,
  checkpoint/reopen diagnostic from source compiled only against published API.
- [x] Both produce semantic digest `76588235…6848043`.
- [x] Local timing is labeled single-run, page-cache-uncontrolled, noncanonical and
  non-SLA.
- [x] Dense and persistent workloads freeze exact seeds, corpus, operation mix,
  cadence, readers/writer, heap, GC, duration, watchdog and page-cache treatment.
- [x] Paired exactness and ratio thresholds remain the Phase 0 values.
- [x] Fake profiles use `1/3/1` independent serial members.
- [x] Source deletion, fresh replacement host, continued operation, retention and
  cleanup are modeled.
- [x] Peak 30 vCPU / 400-GiB data / 500-GiB provisioned disk respects known quotas.
- [x] Image, filesystem, mount, duration, deadline, USD 40 cap, GCS layout, future
  workflow identity and environment are frozen.
- [x] Fake-cloud tests provision no GCP and the paid lane remains Phase 6-only.

## Canonical release toolchain

- [x] Canonical Linux/amd64 Temurin image tag, OCI index/platform/base digests and
  Java `21.0.12+8` are frozen.
- [x] Maven Wrapper URL, Maven/archive digest and Wrapper version match repository
  inputs.
- [x] Compiler/source/Javadoc/JAR/GPG/deploy/Central plugin versions match POMs.
- [x] Locale, timezone, umask, clean workspace and timestamp policies are explicit.
- [x] The exact two POM / six unsigned JAR inventory is machine-readable.
- [x] Other JDK builds remain diagnostic semantic comparisons.
- [x] Independent-workspace canonical builds and release binding remain Phase 5.

## Local acceptance

- [x] Version alignment passes for `4.4.0-SNAPSHOT`.
- [x] Independent model, evidence, fake-cloud and toolchain unit tests pass.
- [x] All seven separate-process crash/fault cases pass.
- [x] All three fake-cloud profiles pass with exact cleanup.
- [x] Published and current API inventories match.
- [x] Paired semantic calibration passes.
- [x] Full reactor tests pass locally (537 core tests plus five processor tests).
- [x] Fresh isolated published compatibility and closed-surface Japicmp pass.
- [x] All four consumers pass.
- [x] Release artifact, reproducible-build and bounded JMH gates pass.

## Protected acceptance

- [ ] Phase 1 PR passes required checks.
- [ ] Phase 1 merges through protected `master`.
- [ ] Exact-master CI passes before Phase 2.

Phase 2 remains analysis-only: it may execute and classify the frozen local matrix,
but it may not implement a product correction.
