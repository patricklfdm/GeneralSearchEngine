# Election decisions across prefix discovery

Phase 3 remains **OPEN**. This increment corrects two scheduling boundaries
before the local activation starts; complete competing-owner qualification is
separate from the component results below.

## Problem and behavior

An automatic owner first waits for an election timeout, then scans original peer
prefixes. Previously, an authenticated higher ballot during that scan became a
failed campaign and consumed one of the three automatic recovery rounds, even
though this node had not allocated its first ballot. Three such observations
could fail a healthy follower. A newer same-ballot heartbeat during the scan also
did not revoke the expired election decision, allowing an unnecessary campaign.

The wait now returns a private decision containing the checked original cut/view,
fence, and consumed volatile heartbeat/milestone. After discovery and its drain,
the round checks those inputs again. Changed inputs return to the ordinary wait
and a fresh discovery pass. New contacts retain their original arrival time;
duplicate milestones cannot renew it. The decision does not grant a vote, lease,
READY, or exclusive ownership. Activity racing the final check is still governed
by normal ballot fencing and source selection.

Only direct higher-ballot fencing, or a changed cut/view revalidated from original
local storage, during a fully drained discovery pass **before durable adoption
starts** can resume waiting within this invocation. A separate typed outcome
marks that exact boundary. Once adoption starts, a failure remains
terminal to the pass, including higher-ballot fencing. Wrapped failures, corrupt
originals, unavailable resources and failed cleanup do not become this outcome.
The explicit nonautomatic discovery path retains its existing error behavior.

Every wait/scan uses the original enclosing start and deadline. Repeated incoming
activity cannot create a new lifetime or accumulate live discovery children.
Once local activation starts, its existing bounded recovery rules still apply.
No client operation is replayed. Election policy, resource capacities, maximum
campaign/automatic-round counts, wire/record catalogues and public API stay fixed.

## Qualification

The final source passes **73** Java tests across eight suites, with no failures or
skips, in 371.539 seconds including the isolated build. Eleven new checks cover
incoming fencing, post-scan same-ballot contact, the original lifetime, decision
freshness, corrupt bytes/closed owners, once-only milestones, exact exception
classification, incoming verified adoption and failed durable adoption. Existing
election timing, automatic campaign/client behavior and node close/reopen tests
remain in the same execution. Nine Python contract/format checks pass; all 56
byte fixtures, nine command fixtures and the frozen acceptance plan remain intact.

Both native regression mechanisms fail against original scheduling from
`bafce01e`: higher incoming contacts exhaust recovery before local activation,
and a same-ballot heartbeat permits PREPARE after two STATUS probes instead of
the required fresh two-peer scan. The latter comparison retains new diagnostic
helpers and tests; it does not claim to be an unmodified old repository build.
The failed original runs, a passing initial 22-test execution, and an intermediate
28-test execution with one fixture failure are retained. That fixture generated
PREPARE again while testing a duplicate and hit its own exchange-attempt limit;
the corrected fixture reuses the exact request without changing runtime limits.

Source-bound measurements and raw histories are retained at
`target/v53-election-discovery`. The [receipt](phase3-evidence/election-discovery.json)
binds all six executions, unchanged snapshot inventories, 318 identical final
production/POM inputs and the verified 4,546,948-byte archive. The whole-owner
producer now records monotonic
event times and exact per-owner round/loss diagnostics so future failures need
not infer retry exhaustion from an exception alone. This observer addition does
not choose a winner or authorize another client mutation.

The original peer-confirmation whole-history failure remains unchanged. Its
ordering motivated this investigation; it did not itself record contact times
or recovery counts, so the component reproductions establish the corrected
mechanisms rather than retroactively attributing every earlier loss to them.

The final-source ungated whole-owner probe **fails**, after 162.922 seconds
including its isolated build. Nodes 3 and 2 each complete startup and later lose
readiness to a higher ballot. No client DATA is completed. Node 1 exhausts its
three actual rounds with losses `CONTACT_UNAVAILABLE`, `HIGHER_BALLOT`, then
`CONTACT_UNAVAILABLE`; the last error is `original source retention capacity`
from fresh grant admission, with the underlying resource ownership/count refusal.
This is a remaining activation/resource convergence failure, not a passing full
history or a reason to enlarge the bounds. All three nodes close successfully
with zero remaining resource leases and no closing failure.

The measured event sequence places node 3's first INSTALLED at 25.274 seconds and
BEFORE_READY at 47.453 seconds; node 2 allocates another ballot at 47.102 seconds,
before node 3's first heartbeat at 52.588 seconds. Node 2's next INSTALLED/READY
span is 57.829 to 85.735 seconds, while node 3 starts a newer ballot at 79.472
seconds. These are observations from one run, relative to its first retained
event, not a latency distribution or proof that timing alone explains the later
capacity refusal. Pre-ready liveness and the actual retained-source lifecycle
need further qualification. No retry of that whole execution was used to seek a
green result.

## Rollback and remaining work

Reverting the private decision check and pre-adoption outcome restores the prior
wait/discovery sequencing without changing any durable format. Diagnostics can
remain independently. Before Phase 3 closes, the original-history readers,
complete competition/process recovery, joining and all frozen profiles still
need their own acceptance. A passing component or producer does not waive those
gates or establish a failover SLA.
