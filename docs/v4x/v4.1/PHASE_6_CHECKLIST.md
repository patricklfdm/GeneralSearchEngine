# GeneralSearchEngine V4.1 Phase 6 checklist

- **Status:** Canonical evidence accepted; append-only registration pending protected merge
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
- [x] Byte sampling is confined to owned source/backup paths and is tested with an
  inaccessible ext4-style `lost+found` sibling.
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
- [x] Exact-source experiment run `33754116526` passes and cleanup is reviewed.
- [x] Canonical run `33758217508` has three independent passing members with durable
  GCS evidence.
- [x] Canonical set is downloaded, checksummed and independently validated.
- [x] Baseline `v4.1.0-operational-cloud` is registered exactly once in the candidate
  append-only registry.

## Gates and acceptance

- [x] `scripts/verify-v41-phase6-evidence.sh` passes locally.
- [x] Full reactor passes with 471 core and 5 processor tests.
- [x] Artifact compatibility and all three consumer fixtures pass.
- [x] Release-profile verification, six-JAR integrity and reproducibility pass.
- [x] Phase 6 implementation and its corrections merge through protected PRs #99–#102.
- [ ] Exact-master CI passes and its commit/run are recorded.
- [ ] Reviewed canonical evidence and registry commit merge before Phase 7.

Rejected experiment run `33737706926` does not satisfy an evidence gate because final
transport deletion lacked authority. Its preflight/SSH correction subsequently merged
through protected PR #100 as `22c4c956ff91b454ee26e1519cabd9965bee8fe9`.

Replacement experiment run `33744312340` also does not satisfy an evidence gate. Its
receipt records `runStatus=FAIL`, while source VM/disk, replacement VM/disk, staging
object and aggregate cleanup all record `PASS`. Evidence assembly rejected a zero
`backup.peakObservedBytes` sample. The synchronous peak-sampling correction later
merged through protected PR #101; accepted runs do not reuse this attempt.

Replacement experiment run `33750556738` does not satisfy an evidence gate. Its source
stage failed with exit code `20` after mount-root sampling reached root-owned ext4
`lost+found`. The source VM and disk were deleted; replacement resources and staging
transport were never created. The corrected receipt truth table treats those
`NOT_APPLICABLE` resources as complete cleanup but still rejects every `FAIL`. No
member from this attempt is reused. The owned-path sampling correction merged through
protected PR #102, and both accepted runs use that exact protected-master source.
