# Phase 3 hosted review: 9444e4d2

Reviewed source: `9444e4d2b7cf3622c46c1d0ee7b698f6bfd13a60`, Automatic
[run 43691550635](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43691550635),
attempt 1. Six of eight jobs passed. All three originals passed; restart and
reply-revocation also passed their independent replays. Competition replay
rejected an unclassified original shape, so the exact-attempt aggregate failed.
This run remains FAIL. Phase 3 and final-source qualification remain OPEN.

## Single campaign with three started automatic owners

The original has three started automatic-owner sessions but only one native
ballot reservation, by node 2. That campaign obtains the node 1/2 pair, publishes
its BARRIER and one DATA call, and completes. The other two sessions have started
their first round but have not sent their own discovery or campaign requests
before closure. Serving the winning candidate's incoming requests is distinct
from initiating another campaign. No losing ballot, restart or loss is inferred.

The complete physical, network, temporal-export and lifecycle readers already
accepted this unchanged original. The composition selector previously covered
only losses, superseded selections and interrupted discovery; it rejected the
valid single-campaign outcome with `automatic unsupported original competition
shape; preserve evidence`.

The new explicit `single-campaign` branch requires two source windows, one
reservation, two discovery probes, zero abandoned selections, zero unanswered
bootstrap attempts, zero bootstrap maintenance and no loss/discovery-only
claims. An additional reader checks the original reservation, both grants,
selected pair and both selection forces, complete campaign-request ownership,
and all three actual session lifetimes. The two idle sessions cannot contribute
a vote or a losing-campaign claim. Unknown shapes still reject.

Ten copied-claim negatives exercise missing/extra reservations, altered grants,
selection and force bindings, invented idle-owner discovery/loss, missing owner
and late start. They follow complete original validation and do not count as
native fault executions. The existing 20 applicable export negatives and 12
lifecycle negatives remain required. Six incomplete-transfer mutations and one
retired-journal mutation remain explicitly inapplicable to this original;
the existing journal-after-history mutation still runs.

## Validation and next execution

The downloaded ZIP matches GitHub's recorded SHA-256
`7eba13a54b0af5110067ebc2706ed863d7a07903d53a8942d28a49ae4ef6a7c7`.
The original selector failure is reproduced locally; the classifier regression
fails before the correction. The corrected complete replay of that same original
passes all 42 applicable exact-reason negatives and preserves its inventory.
Raw evidence and diagnostic receipts remain at
`target/v53-action-review-9444e4d2/`. This is a reader correction against retained
old-source evidence, not a new-source hosted acceptance receipt.

All 4,739 V5.3 Python tests pass, including the new classifier and single-campaign
claim regressions. The 76-test focused suite, exact downloaded archive inventory,
documentation contract, coverage audit and whitespace checks also pass. No local
Maven or native workload rerun is needed for this Python-only reader correction.

Only the Automatic family needs a new hosted execution. Its three originals,
three downloaded replays, preparation and aggregate must share the corrected
source/build/run/attempt. No previous green result is spliced into that cohort.
Carried transition and the other green families retain their original source
identities. The coverage catalogue includes the new conditional negative vector;
the frozen acceptance plan is unchanged. No Java runtime, fixture timing,
workflow, concurrency, paid-cloud or release changes are made here.
