# V5.1 Phase 2 entry: durable automatic authority

**Status:** user authorized Phase 2 after switching to `feat/v5.1-phase2-storage`.
**Accepted base:** Phase 1 [PR #185](https://github.com/patricklfdm/GeneralSearchEngine/pull/185),
`5c5c02e728347f31e6ae7c9935ab9f6852d817f1`.
[Exact-master CI 35491646610](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35491646610)
passed all six jobs, including the complete reactor, configured-mode gates,
compatibility, no-GCP runner and release artifacts. Only the documentation-only step
and the two historical canonical-receipt uploads were skipped.

The accepted [contract](PHASE_0_CONTRACT.md), [selection/recovery rules](LEADERSHIP_AND_RECOVERY.md)
and [1.2 catalog](PHASE_1_FORMAT_CATALOG.md) govern this phase. No frozen fixture or
published V5.0 artifact is regenerated to accommodate an implementation.

## Coherent batches

### A — sealed root authority and forced ledgers (this batch)

- Production codecs for the 13 records needed to admit a sealed root directory and
  maintain PROMISE, ACCEPT and PROOF. Schema data is a reviewed static subset of the
  frozen catalog; product decoding does not load test resources or Python code.
- Existing-directory admission verifies exact identity, all-three seal, initial
  inventory binding, immutable metadata, journal headers and retained promise history.
  Acquire the existing exclusive lock; never create missing files or reset a voter.
- Force-before-return writes, exact retries without duplicate rows, monotonic ranked
  promises, at most one unresolved accepted slot, immutable carried entry origin and
  contiguous proof-backed logical position. Ambiguous I/O quarantines the handle.
- Independent directory inspection and real three-owner JVM halt/SIGKILL cuts for
  every ledger at write/force/ACK boundaries. Retain bytes before product reopen.
- Keep public automatic factory/bootstrap disabled and all configured-mode gates.

### B — frozen recovery and complete generation authority (still pending)

Implement frozen basis/image inventory and chunk identity, selected-next persistence,
highest-accepted quorum selection, snapshot/accepted-tail carry, generation inventory
and selector publication, root-promise preservation, recovery-floor evidence from two
complete durable sources and safe physical deletion. Include interruption/restart,
changed basis, accepted-tail and selector/floor/delete cuts. Unknown or incomplete
generation authority must keep rejecting until its complete recovery path exists.

Batch A deliberately permits reaccepting the same immutable value at a higher ballot;
it rejects replacing a different local accepted value. Batch B must supply the frozen
quorum selection that can justify that replacement. This conservative intermediate
restriction is not the final election protocol or a claimed liveness property.

## Phase exit

Both batches require reviewed source, independent/product byte agreement, meaningful
corruption negatives, actual process-cut evidence and exact accepted-master CI.
Phase 2 remains incomplete until Batch B is accepted. Only then review Phase 3's
election, activation, replication and retained-disk rejoin entry. Public automatic
enablement remains Phase 4; no cloud execution or release is part of this entry.

See the [current storage boundary](PHASE_2_STORAGE.md) and [checklist](PHASE_2_CHECKLIST.md).
