# GeneralSearchEngine V4.3 Phase 6 checklist

- **Status:** Local implementation accepted; PR, exact CI and paid evidence pending
- **Scope:** benchmark-only instrumentation, exact-source cloud lane and evidence

## Entry

- [x] Phase 5 merged through protected PR #124 as
  `e241e1499861e0b44583a948d410ce0ac9c3c286`.
- [x] Exact Phase 5 protected-master CI run `34529966882` passed.
- [x] Work is isolated on `feat/v4.3-phase6-performance-evidence`.

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
- [ ] Implementation PR passes required checks and merges to protected `master`.
- [ ] Exact protected-master CI passes.
- [ ] Operator extends WIF and GCS prefix permissions for the reviewed workflow.
- [ ] One exact-source experiment run passes independent validation and cleanup.
- [ ] Three exact-source canonical members and their aggregate set pass.
- [ ] Canonical evidence review is merged separately.
- [ ] `v4.3.0-fast-reopen-cloud` is registered in a separate append-only PR.

No cloud run or registry entry may be represented as accepted before these ordered
gates produce its exact evidence.
