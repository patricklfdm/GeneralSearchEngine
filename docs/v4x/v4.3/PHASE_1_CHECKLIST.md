# GeneralSearchEngine V4.3 Phase 1 checklist

- **Status:** Merged through protected PR #120; exact-master CI record pending
- **Scope:** Non-production fast-reopen foundation and calibrated evidence plan

## Entry and coordinates

- [x] Phase 0 merged through protected PR #119 as
  `d3b34010a26888dee18f3e01d2e8215e952f5ea7`.
- [x] Exact-master CI run `34435766321` passed.
- [x] Core, processor, reactor, example and four consumers use
  `4.3.0-SNAPSHOT` atomically.
- [x] No production `(1,2)` format, derived-state operation or image behavior exists.

## Published compatibility and API fixture

- [x] Published `4.2.0` core is pinned to SHA-256 `8dba2f09…8191`.
- [x] Fresh isolated artifact copy/checksum and published-4.2 Japicmp are configured.
- [x] Published 4.2 independently reopens current default `(1,0)` bytes without
  changing their complete tree digest.
- [x] Exact format/config/inspection/report/diagnostic declaration names are frozen.
- [x] Status/outcome enum order, report components, bounds and default optional behavior
  are frozen.
- [x] Published `DurabilityMetrics`, verification and migration API shapes remain
  unchanged.
- [x] The declaration fixture compiles while proposed production types remain absent.

## Independent model and fixtures

- [x] Equality, range, prefix and SimpleAnalyzer text are independently modeled.
- [x] Equality/range use representative live slots and canonical bitmaps rather than
  serialized Java values.
- [x] Prefix/text use canonical UTF-8 ordering; text retains postings, positions and
  field lengths.
- [x] Model output is deterministic across input order.
- [x] Checksummed logical fixtures cover all eight classifications and interrupted
  component/catalog publication.
- [x] The independent Python validator checks exact inventory and cannot mask invalid
  canonical authority.
- [x] Fixtures explicitly retain `PHASE2_PENDING` and claim no production bytes.

## Crash harness and fake cloud

- [x] Parent/child/verifier use separate JVMs and stable barrier
  `v43-phase1-derived-plan-no-output-v1`.
- [x] Internal halt and external kill prove canonical bytes unchanged, derived state
  absent and graceful close not run.
- [x] Checksummed evidence schema is `gse-v43-fast-reopen-evidence-v1` with bounded
  logs and fail-closed tamper handling.
- [x] Fake profiles use `1/3/1` serial members and all ten frozen cells.
- [x] Replacement host, sequential transient targets, retention, GCS layout, cleanup
  receipt and no-paid status are modeled.
- [x] Peak `30` vCPU and `400 GiB` regional SSD respect established quotas.

## Calibration and bounds

- [x] Exact published-4.2 diagnostic ran with 20,000 documents, four indexes and five
  samples; median reopen was `343,941,594 ns`.
- [x] The result is labeled same-JVM/page-cache-uncontrolled and not cold-device
  evidence or an SLA.
- [x] Exact internal size/count/text/diagnostic/temporary-amplification limits are
  frozen before Phase 2.
- [x] Cloud machine, disks, filesystem, workload, duration, runtime, cost, retention,
  GCS prefix, future OIDC workflow identity and thresholds are frozen.
- [x] Paid workflow creation, IAM mutation, execution and registration remain Phase 6.

## Local acceptance

- [x] Focused Java fixture and oracle tests pass.
- [x] Independent Python fixture/evidence/fake-cloud tests pass.
- [x] Internal-halt, external-kill and every fake profile pass.
- [x] Published-4.2 isolated checksum and diagnostic pass.
- [x] Version alignment passes for `4.3.0-SNAPSHOT`.
- [x] Full reactor tests pass locally (`507` core tests, `0` failures/errors;
  processor `5/5`).
- [x] Fresh isolated published compatibility passes, including published-4.2
  rollback and Japicmp.
- [x] All four independent consumers, release-profile artifact integrity,
  reproducible-build and bounded JMH smoke gates pass locally.

## Protected acceptance

- [x] Phase 1 pull request #120 passed required checks.
- [x] Phase 1 merged to protected `master` as `148d253`.
- [ ] Exact protected-master CI passes before Phase 2.

Production `(1,2)` bytes and codec-free derived inspection remain prohibited until
Phase 2. Image-assisted reopen remains prohibited until Phases 3 and 4.
