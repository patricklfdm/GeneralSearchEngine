# Phase 3B — offline survivor retention investigation

Status: **OPEN**. This batch records a reproduced native-owner failure and bounded
retention research. It does not enable automatic membership, qualify a durable
peer-progress ledger, or close 3B. The frozen ancestry, coverage, image and deadline
limits remain unchanged. Exact sources, diagnostics and results are retained in the
[research receipt](phase3-evidence/survivor-retention.json).

## Genuine offline voter and two separate failures

The initial public bootstrap has five voters. All publish BARRIER at cut 1. Node 4
then stops participating; its complete on-disk inventory stays unchanged while
nodes 1/2/3/5 certify removal of node 5. Node 4 remains a voter in the resulting
four-member configuration. This is not a cloned identity or a removed-node-only
recovery case.

The unchanged implementation retains the 1→5 ancestry bridge through INTENT at
cut 6 and the next campaign's PREPARE/SELECTED. Fresh joint installation drops that
bridge. At cut 9 the newer full capsule has direct edges 0→5, 5→6, 6→7 and 7→9,
but cannot authenticate node 4's hidden cut 1. Native TCP adoption correctly
rejects the missing original parent. Fetching a complete newer generation does
not manufacture this missing proof.

An isolated conservative overlay carries every original ancestor across both
installation and subsequent publication. Genuine node 4 can then adopt. Its next
election still encounters the old inactive generation: adoption alone does not
authorize overwriting it. Actual TCP generation copies from node 1 and node 2,
plus node 4's own complete copy, establish the new governing majority floor.
Existing inactive-generation retirement and floor release then permit a fresh
all-survivor election.

That conservative overlay is **not a suitable fix**. At cut 10 its six retained
bridges start at 1, 2, 3, 4, 8 and 9. The next publication also needs the current
parent 10, and the unchanged admission guard refuses before ACCEPT. Keeping every
ancestor trades recovery failure for bounded-capacity failure.

A separate diagnostic pins only the endpoint read from the actual offline node's
original complete copy. It carries the exact required old-era bridge and renews
only required same-era bridges. Its registry is explicitly volatile, test-only
state; its native run is evidence about proof propagation and maintenance, not
about durable automatic peer tracking. It completes native adoption, network
majority-floor maintenance, a fresh election and twelve subsequent publications
(cuts 10–21), with at most four retained groups during that continuation.
The earlier failed overlays are retained,
including the fixture which forwarded an extra, unrequired old-era bridge.

## Retention policy requirements

The automatic owner must track **possible durable peer endpoints**, including
uncertainty caused by a lost reply. A peer whose publication was sent might still
hold the previous generation or might already have installed the new one.

1. Persist both possibilities before a publication/transfer can reach that peer.
   Do not issue a different target while the earlier target is unresolved.
2. Prune an old possibility only after a verified complete newer materialization
   or another explicitly proved fencing/completion path. STATUS/HEARTBEAT hints,
   elapsed time, an absent reply or a mere transfer offer cannot authorize pruning.
3. Observing the old generation does not cancel a publication still in flight.
   A late delivery must remain covered after that observation and after restart.
4. Preserve obligations through fresh selection, leader change, publication,
   copying and recovery. Imported metadata must not turn a claimed peer cut into
   authority; malformed, foreign, stale and unbacked claims require rejection.
5. Remove a voter obligation only through the actual completed configuration
   transition. A requested removal, pending INTENT, timeout or local drain is
   insufficient. Learner eligibility and joint old/new majorities stay explicit.
6. Keep obligations separate from old selected-source/first-publication coverage.
   If those combined endpoints exhaust the next publication's headroom, establish
   actual majority copies, retire only safely covered originals, and use a fresh
   selection at the same proven tip before admitting more work. Preserve any
   carried accepted entry. No synthetic reset or same-ballot reselection is allowed.

These are implementation requirements, not a newly accepted on-disk format. A
runtime change must first specify exact persistence, source exchange, force/crash
ordering, provenance and resource accounting. Any necessary contract amendment
must be explicit; this research changes neither the 1.3 catalog nor existing gates.

## Conditional stable-view model

[survivor_retention_research.py](../../../scripts/v53/survivor_retention_research.py)
models the controller's knowledge separately from each peer's actual durable cut.
Its fixture is generated by publications, same-tip consolidation and interrupted
transfers. It does not inject a finished physical history or infer a response from
the hidden environment truth.

A five-voter counterexample has confirmed majority cut 9, old selected/first cuts
5/6, and two unresolved transfers 1→7 and 2→8. All seven endpoints are required for
the next enlarged RANGE. A same-tip new selection removes the old round coverage
obligation while retaining every peer possibility, reducing the required set to
five. Two more publications fit; another consolidation is needed before the third.

The declared finite matrix covers stable sizes 3/4/5 and every delivered/not-delivered
outcome for their missing peers: eight histories with 10,000 further publications
each. These are **80,000 model transitions**, not JVM operations, a benchmark,
a liveness proof for all schedules, or distributed qualification. The adversarial
five-voter cases require 5,000 consolidations, illustrating a potential performance
cost. Normal healthy behavior is not measured by this experiment.

Assumptions still requiring implementation and independent evidence:

- Atomic durable recording before dispatch, with restart preserving uncertainty.
- Authenticated complete-copy observations and safe interpretation of imported state.
- Source/grant/coverage retirement and fresh-selection installation under existing
  image, metadata and original-deadline budgets.
- Exact encoded ancestry/coverage byte headroom, not only the six-group count.
- Cross-view pending contexts, learner/joint transitions, carried entries and all
  process/network crash boundaries. The model covers stable views only.

The physical diagnostic inspector checks selected inventories and original
applied-end ACK bytes, but does not reconstruct the whole ACCEPT/PROOF history,
application replay or force ordering. Its output is `INSPECTED`, never protocol
acceptance. Existing qualified physical oracles must be extended for the eventual
runtime, including original-first negative and portable replay.

## Next implementation boundary

Implement and qualify the durable bounded obligation lifecycle, then connect it to
actual automatic adoption, network floor maintenance and fresh activation. The
reproduced offline-voter history is a mandatory regression; retain-all and
latest-cut-only are rejected alternatives. Complete the remaining native pending
contexts and 3C–3E from the [Phase 3 checklist](PHASE_3_ENTRY_PLAN.md). Component or
research results do not change that closure boundary.
