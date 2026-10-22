# V5.3 bounded resources and lifetime

The `resources` object in [format-catalog.json](format-catalog.json) is normative.
These are library admission/storage bounds, separate from soft experiment time
and monetary budgets. All integer arithmetic is checked before allocation/force;
overflow is CAPACITY_EXCEEDED, never wraparound or silently reset identity.

## Fixed membership-era limits

| Resource | Limit and exhaustion behavior |
| --- | --- |
| Stable voters / transition union | 3–5 / at most 6 distinct identities |
| Concurrent change / learner | One / one; BUSY before another reservation |
| Lifetime membership changes | 256; includes an admitted pending INTENT, never spend past the last slot; refuse next reservation at the bound |
| Permanent identity reservations | 512, including initial, cancelled and removed identities; never recycle within a root |
| Detailed operation results | 64; explicit certified contiguous terminal retirement frees detail slots only |
| Preparation revisions per operation | 64; cancel before SEAL and submit a new operation if exhausted; no internal revision reset |
| Operation / ballot / log counters | Largest allocatable value `2^63-2`; `2^63-1` is exhausted-next sentinel; compare before increment |
| Unresolved entry | One; preserve its exact original owned bytes across recovery/compaction |
| Selected source set | 2–6; contains proposer and satisfies both applicable majorities |
| Queued control messages / total queued bytes | 256 / 64 MiB, in addition to each existing per-peer bound |
| Membership waiters | 64 within the inherited total pending-client cap; reject before dispatch when full |
| Transfer chunk / frame | 4 MiB decoded / 8 MiB complete frame; apply the stricter caller bound |
| Automatic identical exchange attempts | Three total, under the original request deadline; new ballots have separately recorded attempts |

Do not count duplicate ACKs, endpoints or cloned incarnations as independent voters.
Reserve enough headroom for the already-admitted transition's FINAL, promise,
snapshot selector and failure/recovery metadata before writing RESERVE/INTENT.
A capacity rejection must not create a stranded transition that cannot store its
completion. If external disk exhaustion still occurs, fail closed and retain all
owned authority; do not delete evidence to make it look successful.

## Metadata envelope

All sizes include framing and referenced bytes. A membership edge contains its
certificate, full sealed descriptor, checkpoint statement and endorsements, within
48 KiB. Certificate ≤16 KiB; sealed descriptor ≤8 KiB; each checkpoint ACK ≤2 KiB; stable-range item including
endorsements ≤16 KiB. Current complete catalog ≤2 MiB. Capsule index/envelope ≤1 MiB.
Construction checks actual encoded sizes as well as logical counts; the smaller
limit wins. A large descriptor may reject even when nominal member count fits.

With M=256:

```
items <= 2*M + (M+1) = 769
capsule <= 2*M*48 KiB + (M+1)*16 KiB + 2 MiB + 1 MiB
        = 31.015625 MiB <= 32 MiB
peak metadata reservation
        = (2 generations + 6 selected sources + 1 learner)*32 MiB
          + 32 MiB metadata journal + 2 MiB catalog + 2 MiB miscellaneous
        = 324 MiB <= 384 MiB
```

This conservative reservation counts duplicate copies explicitly. Storage retains
at most two selectable generations and one staged learner image. Original bases
are immutable while in use. A new campaign may not accumulate a second set of six
sources before safely retiring/aborting the old staged set. One writer serializes
promise, selected install, prefix/selector and retirement mutations.

Metadata journal rotation checkpoints all surviving promise/basis/selection/tail
state before deleting the old journal. At 32 MiB, backpressure initiates that safe
rotation; inability to complete it refuses further work without corrupting the
prefix. A serialized checkpoint-endorsement accumulator retains at most one active
statement and six ACKs; abandoned attempts cannot append unbounded history.
Generation catalogs reference packed capsule files with finite inventories, not
one unbounded file per historic operation. Inventory records have exact path/count
limits and forbid symlinks, aliases, extra required objects and partial payloads.

Application/log space is accounted separately: existing `ReplicationBounds`
defaults and hard maxima remain the caller's contract (default retained log 8 GiB,
snapshot staging 16 GiB). A complete materialization image is bounded to 64 MiB
in this initial membership protocol; all selected/learner transfers count against
the shared staging allowance before reception. Per-peer limits are multiplied by
actual current union size for observation, while global queues keep the aggregate
within its explicit byte/count bounds. None of these are claims of free disk space.

Exhausting change/identity/result capacity does not stop ordinary DATA while stable.
Exhausting log/index/ballot/global storage capacity can stop service and is reported
explicitly. Terminal-detail retirement does not reclaim identity reservations or
historical membership edges. To reset lifetime limits, the operator must migrate a
verified backup to a new root; old tokens/operation IDs do not cross that boundary.

## Tests and acceptance boundaries

`test_format_fixture` checks the complete encoded resource formula, malformed
allocation inputs, integer-vs-boolean rejection, parser budgets and 10,000 DATA
reducer steps after an actual completed membership operation exhausts its test
change budget. This is a state-size observation, not 10,000 distributed commits.
Existing operation tests exercise result/identity/revision/counter refusal; recovery
tests retain exact owned tails and forced selectors. Later storage/public tests
must measure real bytes, peak staging, interrupted rotation and capacity headroom.
Passing a bound formula is not physical disk, long-duration or performance evidence.
