# V5.1 Phase 2 entry: durable automatic authority

**Status:** Batch A accepted; Batch B implemented locally after the user switched to
`feat/v5.1-phase2-recovery`; protected Phase 2 acceptance pending.
**Accepted base:** Batch A [PR #186](https://github.com/patricklfdm/GeneralSearchEngine/pull/186),
`284f23d398138d0a747bde42e041da291c68574f`.
[Exact-master CI 35495493715](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35495493715)
passed all six jobs. Only the documentation-only step and historical V5.0/V4.4
canonical-receipt uploads were skipped.

The accepted [contract](PHASE_0_CONTRACT.md), [selection/recovery rules](LEADERSHIP_AND_RECOVERY.md)
and [1.2 catalog](PHASE_1_FORMAT_CATALOG.md) govern this phase. No frozen fixture or
published V5.0 artifact is regenerated to accommodate an implementation.

## Coherent batches

### A — sealed root authority and forced ledgers (accepted)

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

### B — frozen recovery and complete generation authority (this batch)

Implemented frozen basis/image inventory and chunk identity, selected-next persistence,
highest-accepted quorum selection, snapshot/accepted-tail carry, generation inventory
and selector publication, root-promise preservation, recovery-floor evidence from two
complete durable sources and safe physical deletion. Includes interruption/restart,
changed basis, accepted-tail and selector/floor/delete cuts. Unknown or incomplete selected generation authority rejects. Unpublished stages do not
become voting authority. See [implementation and evidence](PHASE_2_RECOVERY.md).

Batch A deliberately permits reaccepting the same immutable value at a higher ballot;
it rejects replacing a different local accepted value. Batch B supplies the frozen
quorum selection that can justify that replacement. This conservative intermediate
restriction is not the final election protocol or a claimed liveness property.

## Phase exit

Both batches require reviewed source, independent/product byte agreement, meaningful
corruption negatives, actual process-cut evidence and exact accepted-master CI.
Phase 2 remains incomplete until Batch B is accepted. Only then review Phase 3's
election, activation, replication and retained-disk rejoin entry. Public automatic
enablement remains Phase 4; no cloud execution or release is part of this entry.

See the [current storage boundary](PHASE_2_STORAGE.md) and [checklist](PHASE_2_CHECKLIST.md).
