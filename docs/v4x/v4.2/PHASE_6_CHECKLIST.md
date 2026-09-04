# GeneralSearchEngine V4.2 Phase 6 checklist

- **Status:** Local implementation candidate; protected and paid acceptance pending
- **Scope:** Performance, replacement-host, rollback and canonical cloud evidence

## Entry

- [x] Phase 5 merged through protected PR #111 as
  `5687a05aa2f495f58d8acc904ab1e663361cf6e3`.
- [x] Exact-master CI run `33880571096` passed.
- [x] Work is isolated on `feat/v4.2-phase6-performance-evidence`.

## Probe and evidence

- [x] Benchmark-only source/migrate/target instrumentation records the frozen scale
  and bounded metrics without adding production API.
- [x] Source bytes, backup identity, plan/projection/source-authority identities,
  target history, sequence and full logical oracles are bound in evidence.
- [x] Replacement-host target open, continued mutation, checkpoint and second reopen
  are mandatory evidence.
- [x] Rollback compiles and runs only against the checksum-pinned published `4.1.0`
  core JAR.
- [x] Logs and checksummed artifacts are bounded and exact-inventory validated.

## Cloud control plane

- [x] Suite `v4.2-storage-evolution-suite-v1`, preset
  `v4.2-storage-evolution-v1` and schema `gse-v42-migration-evidence-v1` are exact.
- [x] Experiment/failure-drill use one member; canonical uses three serial members.
- [x] Standard `c3d-standard-30`, two 200 GiB `pd-balanced` disks, ext4/defaults,
  1,800-second measurement, 5,400-second member limit and USD 25 budget are frozen.
- [x] Peak execution is bounded to 30 vCPU and 400 GiB regional SSD.
- [x] GCS permission preflight occurs before compute provisioning.
- [x] Partial-create, early-failure and normal cleanup ownership are fail-closed.
- [x] Workflow is manual-only, exact-master-bound, explicitly confirmed and
  `max-parallel: 1`.
- [x] GCS is transport/retention only and uses the dedicated V4.2 prefix.

## Local acceptance

- [x] Full reactor passes: 500 core tests and 5 processor tests, with only the two
  artifact-compat-owned published probes skipped.
- [x] Python unit and syntax gates pass.
- [x] Bounded real migration and published-4.1 rollback gate passes.
- [x] All three fake-cloud profiles pass.
- [x] Cloud runner dry-run passes without OIDC or paid resources.
- [x] Inherited Phase 5/4/3/2 acceptance chain passes.
- [x] Maven/JMH package builds successfully.

## Protected implementation acceptance

- [ ] Phase 6 implementation PR passes every required check.
- [ ] Phase 6 implementation merges to protected `master`.
- [ ] Exact protected-master commit and CI run are recorded.
- [ ] WIF condition admits only the exact V4.2 workflow ref while retaining all
  repository, owner, branch and environment predicates.

## Paid evidence

- [ ] Exact-master `experiment / 1 / actions` dry-run summary is reviewed.
- [ ] Experiment member passes and its downloaded bundle validates independently.
- [ ] Experiment cleanup receipt proves all three VMs, both disks and staging object
  are absent.
- [ ] Exact-master `canonical / 3 / gcs` dry-run summary is reviewed.
- [ ] Three serial canonical members pass at the frozen scale.
- [ ] Downloaded member bundles and aggregate canonical set validate independently.
- [ ] Canonical members are comparable and have distinct plan/target histories.
- [ ] GCS retention and complete cleanup are independently verified.

## Registration

- [x] Empty registry schema is tracked without claiming evidence.
- [x] Registration accepts only exact name `v4.2.0-migration-cloud`, an eligible
  canonical three-member set, and one append-only insertion.
- [ ] Canonical review is documented.
- [ ] Baseline registration is committed through a separate protected PR.

Phase 7 may begin only after protected implementation acceptance, paid canonical
review and immutable baseline registration are complete.
