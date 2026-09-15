# V5.0 architecture and authority

- **Status:** Candidate Phase 0 architecture
- **Authority:** subordinate to `PHASE_0_CONTRACT.md`

## Runtime shape

Each application JVM owns at most one replica runtime and one exclusive replica
directory. The three JVMs run concurrently:

```text
application/client
        |
        v
configured leader A ---- follower B
        |
        `--------------- follower C
```

There is one dataset, one immutable membership manifest and one ordered replicated
history. V5.0 has no proxy, coordinator, shard map, discovery service or externally
managed daemon.

## Restricted consensus core

V5.0 is deliberately more than primary/backup copying. Its persisted term-like epoch,
quorum promise, predecessor validation, durable entry quorum and durable commit proof
form a restricted consensus core. The only eligible leader candidate is the manifest's
configured leader NodeId. V5.1 may expand candidate eligibility and automate the same
activation protocol; it may not change the meaning of a V5.0 committed entry.

Configured identity does not grant permanent authority. Every process incarnation
must acquire a higher quorum-persisted epoch before writes. Voters that promise the
higher epoch fence all older incarnations without clocks or leases.

## Authority layers

| Layer | Meaning | May define cluster truth? |
| --- | --- | --- |
| Genesis manifest | Fixed group and voter identity | Yes, as identity root |
| Replicated entry log | Ordered proposed history | Only with commit proof |
| Commit-proof ledger | Durable proof that entry quorum preceded commit | Yes |
| Replicated snapshot | Verified compact recovery representation | Yes, through its included committed index |
| Applied materialization | Search/document state through AppliedIndex | No; reconstructible from authority |
| Derived index image | Reopen acceleration | No |
| V4 application backup | Portable committed application cut | No authority for an existing group |

## Commit recovery rationale

Entry presence on one remaining follower is not enough to distinguish a committed
entry from an append that crashed before commit. Therefore V5.0 persists a separate
commit proof on quorum before Future success. A valid surviving proof is evidence of
the earlier entry quorum under the crash-fault model. Recovery never infers commitment
from longest-log, wall clock, local snapshot version or application sequence alone.

## Storage and apply boundary

The replicated log is written once per logical entry. Committed application entries
are applied to the immutable snapshot engine in log order. The V4 canonical encoders
and snapshot components may be reused, but the ordinary V4 WAL does not record a
second independent decision. This prevents an entry from being locally durable yet
cluster-uncommitted and accidentally visible after reopen.

ApplicationSequence changes only for committed document/index operations. Control
entries consume LogIndex but not ApplicationSequence. Replicated snapshot metadata
binds both identities so replay resumes without assuming they are equal.

## Availability envelope

| Condition | Leader reads | New writes | Required action |
| --- | --- | --- | --- |
| Three voters healthy | Allowed | Allowed | None |
| One follower unavailable | Allowed | Allowed with leader + READY follower | Repair follower |
| Both followers unavailable | Last AppliedIndex only | Rejected | Restore quorum |
| Leader process down | Unavailable | Unavailable | Restart configured leader |
| Leader disk permanently lost | Unavailable | Unavailable | Offline reconstruct configured leader from valid group evidence |
| Conflicting/corrupt authority | Fail closed | Rejected | Operator investigation/recovery |

V5.0 never silently promotes a follower. That availability limitation is explicit and
removed only by a later accepted automated-leadership contract.

## Physical compaction

Logical history immutability does not require infinite log retention. A verified
snapshot plus tail is an equivalent recovery representation. The quorum recovery
floor prevents independent compaction from deleting the final recoverable copy.
Metrics and cleanup plans expose the floor and every retained representation.
