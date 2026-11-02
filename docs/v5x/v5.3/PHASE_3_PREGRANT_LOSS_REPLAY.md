# Original pre-grant-loss history replay

Phase 3 remains **OPEN**. This continuation consumes the untouched native history
retained by [actual lifecycle collection](PHASE_3_AUTOMATIC_LIFECYCLE.md). That
producer passed, but integration originally refused its zero-retirement branch.
No native workload was rerun and no easier schedule was substituted.

The physical reader now permits an empty maintenance interval only when the
derived prefix ends exactly at the first `INSTALL_RESERVED`. A nonempty interval
still requires its complete governing-floor transaction. Both paths compare the
derived final allocator, grant journal and source inventory. No missing retirement
or unexpected owner write can disappear into the empty path.

Outgoing scratch ownership follows the original fully forced ballot reservations.
Activation creates that scratch before attempting its local grant. A competing
owner may therefore leave a drained outgoing directory despite never creating a
grant. Exact owner metadata, directory inventory, empty locks, drain receipts and
zero leases remain mandatory; residual payloads and unknown directories refuse.

The activation reader consumes discovery for every derived reservation, including
abandoned reservations. For the observed pre-grant case it requires the actual
first ROUND_BEGIN before allocation, a local current-capture callback without
intervening durable writes, the actual unready `HIGHER_BALLOT` LOSS, and an earlier
received authenticated PREPARE with its original proposer promise. Comparison uses
the full ballot: in this history both counters are 2, but node-3 orders above
node-1. The higher incoming grant starts after the observed loss. A diagnostic
reason alone cannot supply any of these dependencies. Lifecycle anchors are mapped
through recorded grant-copy annotations without changing the original event list.
Receipt positions for this binding refer to that merged replay timeline.

This original has no incomplete SELECTED transfer. The export reader therefore
parses every complete transfer and reports zero incomplete transfers. It does not
invent a partial record or commit. Six partial-transfer mutations and the
source-retirement mutation are explicitly `notApplicable`, not successful tests.
A separate end-of-history mutation checks that a journal capability cannot outlive
its captured current-generation authority. The earlier four-grant history still
runs all 26 of its original capability negatives.

## Retained results and limits

The complete replay accounts for two campaign reservations, four discovery probes,
one pre-grant loss, 240 request attempts, 225 answered exchanges, two published
slots and one client mutation. All 61 committed transfers bind to nine current
generation windows, two frozen-source windows and 54 original record windows.
Seven mutations of copied original evidence reject with exact reasons: substituted
loss cause, loss before the incoming request, missing source image, changed final
allocator, leftover payload, missing abandoned scratch and invented idle scratch.
Twenty applicable capability mutations and twelve lifecycle mutations also reject.
These are validator negatives, not new native fault executions.

Packing/unpacking the original into a new directory and running Python with `-O`
preserves those results and the original inventory. The old maintenance history
still passes all 14 negatives and the old export history all 26. Focused tests
cover empty-interval refusal, full-ballot causal checks, original-index mapping,
exact scratch ownership and applicable-negative accounting. The
[development receipt](phase3-evidence/competing-pregrant.json) retains the previous
failures, immutable producer source identity and final reader validation separately.

This closes the particular integration gap recorded by the preceding batch. It
does not qualify arbitrary multiple-round competition, expiry/close under faults,
all recovery paths or a final-source cohort. The native source remains its recorded
working-byte snapshot; changing the Python reader does not make that run an
execution of the current commit. Java, frozen budgets and workflows are unchanged.

```bash
python3 -B -m scripts.v53.competing_pregrant_evidence "$RAW"
python3 -B -m scripts.v53.competing_export_evidence "$RAW" --qualify
```
