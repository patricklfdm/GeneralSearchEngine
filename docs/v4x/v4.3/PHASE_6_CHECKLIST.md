# GeneralSearchEngine V4.3 Phase 6 checklist

- **Status:** Canonical evidence accepted; append-only registration under protected review
- **Scope:** benchmark-only instrumentation, exact-source cloud lane and evidence

## Entry

- [x] Phase 5 merged through protected PR #124 as
  `e241e1499861e0b44583a948d410ce0ac9c3c286`.
- [x] Exact Phase 5 protected-master CI run `34529966882` passed.
- [x] Work is isolated on `feat/v4.3-phase6-performance-evidence`.
- [x] Phase 6 implementation merged through protected PR #125 as `6686ba1`;
  exact-master CI run `34538794639` passed.
- [x] Clean-host wrapper correction merged through protected PR #126 as `1151b7c`.
- [x] Mount-layout correction merged through protected PR #127 as `1d59ba9`;
  exact-master CI run `34550893252` passed.

## Local and schema implementation

- [x] Published `4.2.0`, current forced rebuild and current warm samples share one
  deterministic oracle.
- [x] All ten frozen matrix cells are implemented without a production control.
- [x] Independent production `(1,2)` backup-byte inspection is part of assembly.
- [x] Fallback outcome/count, checkpoint+WAL, restore, migration and lifecycle
  invariants fail closed.
- [x] Heap, GC, CPU, I/O, byte amplification, duration and page-cache state are
  bounded evidence.
- [x] Member and set thresholds are independently enforced.
- [x] Evidence, cloud plan, set and registry schemas use frozen identities.

## Cloud safety

- [x] Preflight validates the exact protected-master SHA before OIDC or paid work.
- [x] Experiment/failure-drill are one member; canonical is three serial members.
- [x] Peak allocation is one 30-vCPU VM, two 200-GiB data disks and its
  auto-deleted 100-GiB boot disk (500 GiB provisioned in total).
- [x] Source deletion precedes replacement-host validation.
- [x] Cleanup receipts prove both VMs, both disks and staging objects absent.
- [x] GCS layout is confined to the V4.3 prefix.
- [x] Job summary includes run ID, topology, budget and thresholds.
- [x] The workflow is manual; local CI never requests OIDC or creates resources.

## Acceptance sequence

- [x] Complete local Phase 6 gate passes.
- [x] Full reactor, compatibility, release artifacts and inherited gates pass.
- [x] Implementation PR passes required checks and merges to protected `master`.
- [x] Exact protected-master CI passes.
- [x] Operator extends WIF and GCS prefix permissions for the reviewed workflow.
- [x] One exact-source experiment run passes independent validation and cleanup.
- [x] Three exact-source canonical members and their aggregate set pass.
- [x] Canonical evidence review merged separately through protected PR #128;
  exact-master CI run `34567122915` passed.
- [x] `v4.3.0-fast-reopen-cloud` is present exactly once in the candidate
  append-only registry.

## Paid evidence

- [x] Experiment run `34551484690`, attempt 1, passed from exact source
  `1d59ba9c354f5ea5ca4ebc8d8b5b30519479aac6` with one member and Actions
  retention.
- [x] Canonical run `34557940276`, attempt 1, passed from the same exact source with
  three serial members and GCS retention.
- [x] Downloaded experiment and canonical member bundles and aggregate sets validate
  independently.
- [x] Every accepted receipt proves both VMs, both data disks and staging objects
  deleted with aggregate `cleanup=PASS`.
- [x] Canonical set is comparable, `canonicalEligible=true`, and binds set digest
  `b91f780d8f630d626f8aec3bc090073a5c4bbd9273819bc437d07c10ff7200c4`.
- [x] Member ratios `0.256803`, `0.243176`, and `0.260551` satisfy the per-member
  `0.65` bound; median `0.256803` satisfies the set `0.50` bound.

## Registration

- [x] Empty registry schema remains tracked without claiming accepted evidence.
- [x] Registration accepts only exact name `v4.3.0-fast-reopen-cloud`, an eligible
  canonical three-member set, and one append-only insertion.
- [x] Canonical review is documented in
  [`PHASE_6_CANONICAL_REVIEW.md`](PHASE_6_CANONICAL_REVIEW.md).
- [x] Canonical review merged through protected PR #128 as `ae25c80`; exact-master
  CI run `34567122915` passed.
- [x] Baseline `v4.3.0-fast-reopen-cloud` is registered exactly once in the
  candidate append-only registry.
- [ ] Baseline registration is committed through a later separate protected PR.

Phase 7 may begin only after canonical-review acceptance and immutable baseline
registration are complete.
