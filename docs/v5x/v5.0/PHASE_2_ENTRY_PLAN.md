# V5.0 Phase 2 replicated storage entry plan

- **Status:** Accepted through protected PR #147 and exact-master CI `34934537274`
- **Branch:** `feat/v5.0-phase2-replicated-storage`
- **Starting master:** `2e78bddd37fff6638c621da4e4f7f27c3f85a8aa`
- **Phase 1 acceptance:** protected PR #146, exact-master CI `34930568130` (success)

## Scope

1. Freeze production outer storage family `gse-replicated (1,0)` and golden bytes.
2. Implement immutable manifest and local identity, exclusive directory ownership,
   bounded checksummed journals, epoch/incarnation promises and follower durable append.
3. Persist and independently validate received commit proofs against exact entries
   and distinct voter receipts. A stored proof may establish local CommitIndex;
   no group quorum operation or application Future is implemented here.
4. Enable existing codec-free `ReplicationStorageOperations.inspect(Path)` without
   changing the frozen public Java declarations or core/processor implementation.
5. Verify Java-produced bytes using an independent Python parser and open Python
   golden bytes in Java. Reject identity mismatch, unsupported versions, corrupt or
   incomplete records, conflicting retries, stale epochs and resource exhaustion.
6. Add real separate-JVM crash cases at storage write/force/ACK boundaries, retain
   pre-reopen evidence and test I/O failure poisoning, ownership and restart behavior.
7. Add a Phase 2 CI gate and record the exact validation baseline/checklist.

## Exclusions

No public engine construction, application apply/publication, leader activation
quorum, socket listener, group bootstrap, suffix reconciliation, snapshot install,
physical compaction, election, membership change or paid cloud execution. Internal
empty-store initialization creates storage for tests/future bootstrap; it is not an
accepted three-target bootstrap receipt. Torn authoritative tails fail closed;
Phase 4 owns any reviewed recovery/truncation procedure.

The Phase 1 JSON examples remain logical fixtures. They are not reinterpreted as
production directory bytes, and their schemas and inspector remain unchanged.

## Exit

Production/independent fixture, malformed-input, crash, ownership and bounded-I/O
gates, existing Phase 1 gates, reactor, consumers and release artifact checks pass.
Protected PR acceptance and successful exact-master CI precede Phase 3.
