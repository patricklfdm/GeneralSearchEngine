# GeneralSearchEngine V4.1 Phase 6 checklist

- **Status:** Local implementation and free pre-cloud gates complete; paid evidence pending
- **Scope:** Profiling, large corpus, true source loss, replacement host and canonical evidence

## Entry and boundary

- [x] Phase 5 merged through protected PR #98 as `5f1c750`.
- [x] Exact-master CI run `33730252965` passed on that commit.
- [x] Active coordinates remain `4.1.0-SNAPSHOT`.
- [x] No production API, live format, backup format or retrieval semantic changed.
- [x] Speculative optimization remains unauthorized.

## Local and control-plane evidence

- [x] One benchmark-only Java probe implements independently executable source and
  restore stages.
- [x] Bounded smoke executes real backup, independent byte inspection, source removal,
  restore, full oracle, continued mutation, checkpoint and second reopen.
- [x] Source-impact, duration, byte, heap, retained-storage and restore metrics are
  recorded without payloads.
- [x] Existing experiment/canonical/failure-drill fake-cloud profiles still pass.
- [x] Exact plan validation freezes workload, profiles, machine, disks, duration,
  runtime, budget, serialization and retention.
- [x] Job Summary renders the validated plan as a readable table with run identity.
- [x] Successful member and set bundles are checksummed and bounded.

## Real source-loss topology

- [x] Source and restore execute on distinct VMs and fresh data disks.
- [x] Verified bundle, checksum and source proof cross temporary GCS transport.
- [x] Source VM/disk and local source copies disappear before restore provisioning.
- [x] Replacement host performs independent byte verification before Java restore.
- [x] Source and restore disks never coexist; matrix members run serially.
- [x] VM expiry, exact output roots, bounded logs and five-resource cleanup receipts
  are enforced.
- [x] A payload-free create/read/delete probe runs before the first paid Compute
  resource, and project-wide SSH keys are blocked on both VMs.
- [x] OIDC provider condition explicitly allows the merged workflow identity.
- [ ] Exact-source experiment member passes and cleanup is reviewed.
- [ ] Three independent canonical members pass with durable GCS evidence.
- [ ] Canonical set is downloaded and independently validated.
- [ ] Baseline `v4.1.0-operational-cloud` is registered exactly once.

## Gates and acceptance

- [x] `scripts/verify-v41-phase6-evidence.sh` passes locally.
- [x] Full reactor passes with 471 core and 5 processor tests.
- [x] Artifact compatibility and all three consumer fixtures pass.
- [x] Release-profile verification, six-JAR integrity and reproducibility pass.
- [ ] Phase 6 PR CI passes and merges to protected `master`.
- [ ] Exact-master CI passes and its commit/run are recorded.
- [ ] Reviewed canonical evidence and registry commit merge before Phase 7.

Rejected experiment run `33737706926` does not satisfy an evidence gate. No further
paid execution is authorized until its preflight/SSH correction merges, the new exact
protected-master CI passes and the operator explicitly confirms a replacement run.
