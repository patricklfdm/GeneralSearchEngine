# GeneralSearchEngine V4.4 Phase 5 checklist

- **Status:** Local implementation complete; protected entry and acceptance pending
- **Baseline:** [PHASE_5_BASELINE.md](PHASE_5_BASELINE.md)

## Entry and scope

- [x] Phase 4 local decision is `PASS_NO_MEASURED_REGRESSION`.
- [x] No product, public API, format or authority change is introduced.
- [x] No paid GCP resource, IAM mutation or baseline registration occurs.
- [x] Phase 2 merged through protected `master`; exact-master CI `34591678426`
  passed on `96b43c9`.
- [ ] Phases 3–4 merge through protected `master` and exact-master CI passes.

## Stabilization and compatibility

- [x] Full Maven test suite and V4.4 Phase 1–4 gates pass locally.
- [x] Published-4.3 API inventory and paired semantics remain exact.
- [x] All independent consumers remain part of required CI.
- [x] Release packaging, Javadocs, artifact contents and reproducibility remain gated.

## Canonical release toolchain

- [x] Frozen manifest and repository Maven/plugin inputs validate.
- [x] Docker image resolves to the frozen OCI index digest on Linux/amd64.
- [x] Java version/runtime, locale, timezone and umask are checked inside the image.
- [x] The frozen Maven ZIP is verified outside and inside each container, then
  extracted with the JDK without relying on Wrapper cache or container `unzip`.
- [x] Two clean independent source workspaces build two POMs and six unsigned JARs.
- [x] Exact SHA-256 inventories match and checksummed evidence validates.
- [x] Other JDK builds remain diagnostic only.

## Cloud readiness without GCP

- [x] Workflow is manual, trusted-master-only and `cloud-benchmark` protected.
- [x] Experiment/failure-drill use one member; canonical uses three serial members.
- [x] Resource, image, duration, deadline, cost, retention and GCS layout are exact.
- [x] Source deletion, replacement host, continued operation and cleanup are wired.
- [x] Published-4.3 paired ratios enforce member `1.35` and set median `1.20` limits.
- [x] Failure artifacts upload under `always()` with per-resource receipts.
- [x] Strict member/set tamper and threshold tests pass.
- [x] All profiles pass dry-run without invoking GCP.
- [x] Required WIF workflow and prefix-delete IAM amendments are documented, not run.

## V5 handoff

- [x] Frozen guarantees and exact supported formats are recorded.
- [x] Known single-node, local-authority and evidence limitations are recorded.
- [x] Distributed authority and new retrieval/storage architecture remain deferred.
- [x] Pending Phase 6–8 identities are explicitly not claimed.

## Protected acceptance

- [ ] Phase 5 PR passes required checks after accepted predecessors.
- [ ] Phase 5 merges through protected `master`.
- [ ] Exact-master CI passes before any Phase 6 paid execution.
