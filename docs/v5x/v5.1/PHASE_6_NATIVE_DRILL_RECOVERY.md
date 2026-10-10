# Native drill startup correction and flexible member order

**Status:** local correction candidate, 2026-10-09. Corrected-source protected CI
and paid qualification remain pending. Full Phase 6 remains open.

## Retained failure and cause

PR #311 merged at `99df69f1d5c50daae8690f2ed4237482b0e88830`;
[master CI 37957278096](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37957278096)
passed on attempt 2. The full-preset native experiment
[37970604996](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37970604996)
passed. The subsequent native failure-drill
[37981974124](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37981974124)
executed eleven cells, then failed `minority-capacity` during initial fencing.
The failed cell had no workload calls. Its 259.324 seconds were below its
600-second cell ceiling; the original 180-second fencing wait expired.

Before starting the bounded voter and healing PREPARE traffic, node-2 was the
healthy leader at epoch 3. After healing, node-1 became `LEADER_READY` at epoch 5;
node-2 and node-3 were followers at epoch 5. The controller retained the old
node-2 choice and only polled node-2/node-3. Retained node-1 trace samples show
it ready for about 196 seconds before shutdown. A deterministic replay of these
observations reproduces the original failure.

All 46 guest commands completed successfully. Cleanup confirmed all thirteen
exact resources absent, with no leftovers; retention was `VERIFIED` and the lease
was released. The conservative ledger total after this attempt was USD 110 / 200.
Original failure evidence remains at `target/v51-failure-drill-37981974124/`,
including `diagnosis.json`, downloaded receipts and decoded member traces.

The correction observes both healthy voters and the bounded follower after heal,
and returns the single observed healthy leader sharing the follower's epoch.
All observations use one original absolute deadline, clipped to the cell limit;
late replies cannot satisfy it. No election is forced or mutation replayed.
The exact timeout now maps to `RUNTIME_BOUNDED_VOTER_FENCING`, with a closed safe
description instead of unclassified or raw exception text. An observed leader
can still change later; normal workload/history validation remains mandatory.

## Operator-authorized member-order amendment

The operator requested that all five members may start in any order. New native
v3 sequences can select **`runner_order=any-order`**, now the workflow default.
The paid execution selector still defaults to `off`. Any of `experiment`,
`failure-drill`, `canonical-1`, `canonical-2`, or `canonical-3` may be first or next
if it has not already passed in that sequence.

- A complete set still requires all five distinct members on the same source,
  archive, configuration, frozen workload and timing-plan identity. A partial set
  cannot close Phase 6.
- Canonical member numbers fix repetitions and control hosts 1/2/3. They do not
  depend on execution position. Cell order and all measured parameters remain
  frozen within each member.
- Sequence order is immutable. Existing `experiment-first`/`canonical-first`
  sequences keep their successful-prefix requirements, and legacy v1/v2 and fake
  requests retain their original admission rules. Use a new sequence for the new
  source and ordering mode; historical PASS evidence cannot be moved into it.
- Only one pending attempt is permitted globally. Duplicate completed PASS
  members are rejected. Experiment/drill failures can be retried by a new
  prepare/run attempt, with all prior charges retained. A failed canonical member
  still blocks its entire sequence; `any-order` does not permit selective retries.
- Offline price review derives the remaining set from validated same-sequence
  PASS entries, not a suffix of the chosen starting member. Every remaining member
  needs a quote and maximum. Previous reservations plus all remaining maxima must
  fit USD 200. PASS entries from other sequences cannot reduce that requirement.
- Each run still needs fresh exact-source CI, cleanup/precheck, prices, prepared
  plan and exact approval. The implementation adds no ledger reset or automatic
  refund path. Paid dispatch remains an operator action.

## Separate operator accounting restart — 2026-10-09

After the correction was prepared, the owner explicitly requested clearing the
ledger. All seven prior attempts were terminal; no active Runner, lease or V5.1
instance/disk/firewall remained. The original USD 110 ledger at generation
`1791580114713617` was backed up byte-for-byte under
`.local/v51-ledger-backups/1791580114713617/`, outside Maven output and ignored by
Git. Its SHA-256 is
`710ba869435f13c5fbc540469895d5dd7897340a9416517de66e1f9011b29a4d`.

A write conditional on that exact generation replaced only the current budget
ledger. Read-back confirmed generation `1791584099285775`, no entries, USD 0 / 200
and no active lease. The backup directory retains the original bytes, inspected
plan and PASS receipt. Historical experiment/cleanup/evidence objects were not
deleted. This explicit accounting restart does not refund prior cloud spending
or turn a failed attempt into a successful one.

Fresh plans must use the new ledger observation and a new source-bound sequence.
The USD 200 ceiling and ordinary failed-attempt accounting remain unchanged;
future resets require separate operator authorization.

## Verification and next step

Deterministic startup regressions cover both leader switches, unchanged leader,
convergence, wrong epoch, bounded-leader rejection, original and clipped
deadlines, late replies and transport failure propagation. Ledger regressions
cover all 120 permutations, duplicate/pending/identity/failure/budget rejection,
legacy compatibility and complete remaining-set pricing. Prepare/run qualification
also exercises `canonical-3` first using the offline provider boundary.

Local verification passed: 112 focused tests; final five startup regressions and
25 authority/workflow checks; the complete admission gate's 48 native and 221
preflight/admission tests plus its offline qualifications and review validators;
36 control tests and the control failure matrix; 30 CI scope tests. The generated
workflow matches, all sixteen shell blocks parse, and frozen workload/timing-plan
hashes are unchanged. Logs and a file/hash index are retained in
`target/v51-native-drill-flexible-order/validation-summary.json`.

These are controller and admission checks, not new paid engine evidence. Existing
complete owned failure-drill and three canonical CI gates remain required.
After corrected-source CI and fresh cleanup/preflight, create a new `any-order`
sequence, review its remaining budget and manually prepare/run the selected
member. Native failure-drill and all three canonical repetitions still need
complete independent replay, retention and cleanup for final acceptance.
