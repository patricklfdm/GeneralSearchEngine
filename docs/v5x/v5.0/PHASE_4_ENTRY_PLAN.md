# V5.0 Phase 4 recovery entry plan

- **Status:** Accepted through protected PR #149 and exact-master CI 34950041552
- **Branch:** `feat/v5.0-phase4-recovery`
- **Starting master:** `911c9de0bd63149e5d48e7f4d5cb0ea7042a951e`
- **Phase 3 acceptance:** [PR #148](https://github.com/patricklfdm/GeneralSearchEngine/pull/148),
  [exact-master CI 34940262703](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/34940262703)

## Deliverables

1. Fence older incarnations through a new durable promise quorum before selecting
   committed recovery authority. Preserve every observed valid proof; reject conflicting
   proofs and missing committed data instead of choosing the longest log.
2. Install verified recovery state with an atomic generation pointer under the existing
   replica owner lock. Interrupted staging preserves prior authority; publication and
   cleanup must be restartable and independently inspectable.
3. Recover committed entries after lost responses, remove only proven uncommitted
   suffixes, and replay application state before completing the activation NO_OP.
4. Catch up retained contiguous history in bounded batches. Transfer immutable application
   snapshots in bounded chunks when the required prefix has been compacted.
5. Keep replaced disks non-voting until verified reconstruction. Reconstruct a configured
   leader disk only with both surviving follower identities; preserve fixed membership.
6. Advance a recovery floor only with two durable recovery representations. Compact only
   behind a verified local snapshot, with exact, crash-safe cleanup.
7. Add independent snapshot/generation inspection and real process recovery/crash evidence;
   retain the Phase 1/2/3 gates, public API inventories and old storage fixtures.

## Boundary

The Phase 2 seven-file layout remains readable and byte-stable. Recovery adds explicitly
versioned optional generation/snapshot metadata; existing record IDs are not reused.
The root promise ledger and process lock remain outside replaceable generations.
Application materialization continues to use in-memory engines without a V4 WAL.

Public group-bootstrap and engine admission remain reserved until their separate complete
bootstrap authority workflow is reviewed. Phase 4 implements internal recovery, not a
synthetic bootstrap receipt. No automatic election, follower public reads, membership
changes, paid cloud or signed release is included.

## Acceptance

Use a new Phase 4 gate over real concurrent JVMs, with independent parsing of retained
files and application checks. Cover interrupted installation/cleanup, late committed
proofs, uncommitted suffixes, missing/corrupt sources, restart, follower replacement,
leader replacement, snapshot fallback and compacted-history recovery. Local evidence is
candidate evidence until protected PR and exact-master CI acceptance.
