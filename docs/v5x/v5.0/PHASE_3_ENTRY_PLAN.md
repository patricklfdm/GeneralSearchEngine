# V5.0 Phase 3 leader-path entry plan

- **Status:** Implementation candidate
- **Branch:** `feat/v5.0-phase3-leader-path`
- **Starting master:** `1895598412b82da9de57655027d0ae76f75e327c`
- **Phase 2 acceptance:** protected PR #147; exact-master CI `34934537274` passed

## Deliverables

1. Implement the frozen canonical `gse-replication/1.0` envelope and bounded Java
   NIO transport with private/loopback bind admission and correlated responses.
2. Add an internal node runtime over the Phase 2 storage authority. Probe a quorum,
   choose a fresh higher epoch/incarnation, force promises on quorum and establish
   leadership with a quorum-committed NO_OP before admitting application writes.
3. Serialize leader operations: validate deterministic payload, force local entry,
   obtain distinct entry receipts, force proof on quorum, apply/publish, then complete
   the application future. A missing quorum cannot publish a new application state.
4. Apply opaque operations through the existing in-memory snapshot engine, including
   atomic bulk and built-in index lifecycle operations. Maintain a separate private
   validation engine so application rejection precedes durable admission. Neither
   application engine owns a V4 WAL. LogIndex and ApplicationSequence stay distinct.
5. Enforce follower role rejection, finite pending/peer work, idempotent retries,
   cancellation without retracting accepted history, and deterministic close.
6. Compare production traces with the independent model; test real three-JVM TCP,
   one/two follower loss, force/ACK/publication barriers, corruption, stale responses
   and bounded admission. Keep raw process/network/storage evidence in CI.

## Phase boundary

Runtime constructors remain package-private until group bootstrap and recovery have
an accepted authority admission path. The public builder/bootstrap declarations stay
reserved; this phase does not pretend an internally initialized directory is a valid
three-target bootstrap receipt. Existing public API inventories stay frozen.

Activation in this phase requires a complete, matching committed prefix on the local
node and at least one peer. Divergent histories, uncommitted suffixes and missing
committed bytes reject activation; Phase 4 supplies reconciliation and catch-up.
A timed-out admitted mutation is indeterminate and stops further leader writes until
recovery; the last published state remains readable. Snapshot install/compaction,
backup/bootstrap workflows, automatic election and paid cloud are outside this phase.

The runtime, transport and application adapter are production implementations; test
workers only arrange fresh stores and control faults. Successful application futures
must traverse actual durable entry/proof and snapshot publication barriers.
