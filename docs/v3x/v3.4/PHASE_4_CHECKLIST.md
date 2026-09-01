# V3.4 Phase 4 checklist

Status: accepted through PR #71 as protected-master commit
`0433de39a318a1885322ee22377e3b8a76738c62`. Phase 4 implements and fake-tests the
isolated `final-v34` evidence lane. It starts no paid job, changes no production source
or public API, registers no baseline, and does not convert the version or begin V4.

## Entry boundary

- [x] Phase 3 merged through PR #70 as protected-master commit
  `34760b326fda6da31a0463d7b4765d6c6da5921c`.
- [x] The independent Phase 4 branch starts from that exact merge.
- [x] Exact-commit protected-master CI succeeded in
  [run 33436691459](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33436691459)
  for `34760b326fda6da31a0463d7b4765d6c6da5921c`.
- [x] Published releases, baseline registries, production source, public API, and all
  existing modes/presets remain unchanged.

## Frozen V3.4 lane

- [x] Workflow mode `final-v34`, suite `v3.4-final-in-memory-suite-v1`, preset
  `v3.4-final-in-memory-v1`, and future registration name
  `v3.4.0-in-memory-cloud` propagate end to end.
- [x] The preset freezes equal 16 GiB heap bounds, G1, all workload controls, seeds,
  schedules, queue capacities, timeouts, and metric schema recorded in the
  [Phase 4 baseline](PHASE_4_BASELINE.md).
- [x] Canonical requests accept only three or five Standard/GCS 30-minute members.
- [x] The required two-hour lane accepts only one Standard/GCS experiment and remains
  distinct from canonical evidence.
- [x] Six-, twelve-, and twenty-four-hour requests fail before provisioning.
- [x] Every slot is capped at three hours and the family is capped at five slots; dry
  run reports VM and vCPU-hour upper bounds.
- [x] Existing `v3-production-*-v1` and `v3.1-ranked-v1` definitions and fingerprints
  retain their exact shapes.

## Evidence and lifecycle

- [x] Raw evidence requires the exact suite file set, status/config agreement, five
  cold runs, nine extreme axes, nine burst cells, ordered long-run windows, complete
  summary fields, and both inner and outer SHA-256 manifests.
- [x] Analyzer output normalizes cold, extreme, burst, long-run, and per-window metrics
  and binds the complete configuration into the benchmark fingerprint.
- [x] Changed workload controls, incomplete cells/windows, failed or partial output,
  JVM/suite/preset mismatch, and incompatible existing modes fail closed.
- [x] Synthetic three-member aggregation retains every member and accepts only the
  frozen future registration name; registration still requires a verified durable
  upload receipt and is not performed in Phase 4.
- [x] Existing fake lifecycle coverage retains benchmark failure, upload failure,
  cancellation/timeout result precedence, partial evidence, resume/replace, checksum,
  cleanup, and immutable-plan gates.

## Local validation

- [x] Python 3.11 analyzer/workflow/comparison/upload unit suites pass.
- [x] Fake-gcloud V1, set runner, workflow static, system-fact, and upload runner suites
  pass without provisioning.
- [x] `V34Phase4FinalCloudContractTest` accepts only the 30-minute and two-hour final
  cloud kinds while the local kind remains capped.
- [x] `verify-v34-phase4-final-suite.sh` executes a reduced combined cold/extreme/burst/
  long-run suite and verifies status, cardinality, configuration, artifacts, and
  checksums.
- [x] Core, reactor, JMH profile/smoke, consumers, artifact compatibility, Javadocs,
  release artifacts, reproducibility, Markdown, and diff-hygiene gates pass on the
  final Phase 4 tree.
- [x] No GCP, GCS, GitHub Actions paid benchmark, upload, baseline registration, tag,
  deployment, or release operation was executed.

## Phase 5 entry

- [x] Merge Phase 4 through protected PR #71 as
  `0433de39a318a1885322ee22377e3b8a76738c62`; exact-merge protected-master CI
  succeeded in [run 33470856585](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33470856585).
- [x] Create `release/v3.4.0` from that exact merge and convert all active coordinates
  atomically to final `3.4.0` on the separate release branch.
- [x] Repeat final compatibility, artifact, and reproducibility gates before the Phase
  5 candidate commit.
- [x] Run the one-repeat two-hour Standard/GCS experiment from the exact final source.
- [x] Run and locally review a three-member Standard/GCS canonical `final-v34` set.
- [ ] Register `v3.4.0-in-memory-cloud` only after durable upload and protected review.
- [x] Keep the eligible 4/8/16 GiB heap matrix and all V4 handoff gates explicit; the
  final-source matrix passes separately from canonical evidence.
