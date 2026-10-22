# V5.3 testing and evidence

## Entry model scope

Implementation: [membership model](../../../scripts/v53/membership_model.py),
[counterexample tests](../../../scripts/v53/test_membership_model.py).
Invocation and retained results are in the [entry index](README.md) and
[status record](DEVELOPMENT_STATUS.md).

The first executable research model covers every stable set of 3–5 voters chosen
from six labelled identities, every allowed one-voter add/remove/replace transition,
and every distinct receipt subset of its old/new union. This includes four-voter
majority boundaries and six-node peak replacement. Labels are interchangeable for
this arithmetic check only; endpoint, process, incarnation and disk identity are
not modeled by that symmetry.

Check the joint predicate against an independently constructed family of minimal
old and new majorities. Enumerate all relevant quorum-pair intersections. Retain
witnesses for direct-switch, either-side-majority, union-majority, duplicate-vote
and learner-vote mistakes. Bind synthetic receipts to the complete supplied claim;
changing history, generation, configuration, operation, ballot, index, digest or
durability phase must reject even if the voter count is sufficient.

A complete bounded result is `PASS` with `productionQualified=false`. A traversal
limit produces `INCOMPLETE` and a failing command exit. Neither result is a network,
storage, crash, election, read, performance or cloud qualification. Validation
must use explicit exceptions and still work with Python assertions disabled.

The 2026-10-21 complete run checked 41 configurations, 510 directed transitions
(90 add, 90 remove, 330 replace), 12,480 receipt subsets, 53,760 synthetic
certificate checks and 82,770 quorum intersections. It also rejected 19 contextual
or voter mutations after accepting their unmodified originals. These numbers
describe this six-identity domain, not 510 physical cluster executions.

All 18 unit tests pass. Three deliberate implementation mutants independently
show that the checker detects either-side/union-majority substitution and omission
of receipt context validation. The CLI test confirms incomplete exploration exits
with failure and cannot overwrite a previous evidence directory. An optimized
Python subprocess confirms duplicate/foreign receipt rejection survives `-O`.

## Durable single-slot research

The [ballot/handoff research](BALLOT_AND_HANDOFF_RESEARCH.md) adds separate message,
force and crash events, frozen recovery bases, and a history oracle. Its 21-context,
2,884-case schedule matrix preserves chosen values despite lost ACKs and partial
writes. Five unsafe implementation mutants are detected by specific safety checks.
The direct-switch example passes each local configuration check but fails the
combined root/index check, so individual-view success cannot close reconfiguration.

This extends entry research. It does not meet the complete Phase 1 transition,
multi-slot recovery or physical storage gate. See the exact assumptions, excluded
schedules, retained JSON replay and [receipt](ballot-research.json).

## Predecessor-certified transition research

The [multi-slot model](TRANSITION_CHAIN_RESEARCH.md) adds locally forced authority
chains and a conservative old/joint/new handoff. The complete 196-case matrix and
13-slot size walk pass; 15 representative histories replay from compressed JSON.
Three unsafe implementation variants are rejected by a separate chronological
chain/local-view checker. Current receipts and source hashes are in
[transition-research.json](transition-research.json).

Full-chain transfer here retains every certificate and durable vote. It does not
model application snapshots, compaction, byte-level atomicity or the existing
production global-promise/activation machinery. Physical and public gates below
remain required; model results cannot substitute for those observations.

## Checkpoint/floor retention research

The [recovery model](RECOVERY_AND_RETENTION_RESEARCH.md) adds separate file,
selector, floor and retirement force boundaries. Its input histories cover old,
joint and new views in all seven size profiles, with and without an unresolved
acceptance. A separate observer checks preserved authority, local ownership,
monotonic root promise, immutable basis and exact retained source bytes. Five
unsafe implementations have specific rejection tests. Full chains remain retained
and capacity exhaustion refuses; no "latest configuration" shortcut is accepted.

The matrix checks one checkpoint/retirement sequence per input at every named
crash cut. All 42 final histories replay from compressed JSON. Actual measurements
and exact source hashes are recorded in [recovery-research.json](recovery-research.json).
This adds abstract metadata recovery coverage, not application snapshot contents,
real disk atomicity, unlimited history compaction or concurrent election integration.

## Global promise and activation research

The [activation adapter](GLOBAL_PROMISE_AND_ACTIVATION_RESEARCH.md) adds durable
allocation, separate root-grant/basis forces, immutable source selection, exact
selected installation and a fenced publication callback to the transition model.
The independent observer catches five specific unsafe implementations. The finite
420-case matrix and 60 portable representative histories test recovery into a
fresh stable barrier; directed tests also recover accepted INTENT and reject a
removed proposer. [Source-bound results](activation-research.json) retain their
local/abstract scope. No production disk, service-read, timing or cloud claim follows.

## Later foundation and runtime coverage

[Operation/maintenance research](OPERATION_AND_MAINTENANCE.md) adds a committed
control-state reducer with an independent observer. Its 308 complete/cancel/reprepare
crash schedules all replay from serialized histories. Identity conflict, stale
revision, result retirement, future receipt, post-SEAL cancellation and maintenance
challenge counterexamples qualify the reducer rules only. Accepted-only tails and
actual quorum certification belong to the integrated protocol gate.

The [authority/learner research](AUTHORITY_AND_LEARNER_RESEARCH.md) adds a distinct
majority-endorsed stable-range representation and durable learner eligibility gate.
Its observer checks original proof history, complete membership boundaries, forced
endorsements and exact request/image/identity bindings, including source ordering.
The finite matrix covers 220 cases; 55 representative histories replay from gzip.
Source fixtures use only existing voters, without a preinstalled learner. Current
[receipt](admission-research.json) records local results. This is not physical
compaction, a replicated identity catalog or a fully integrated membership protocol.

| Family | Required schedules and independent observations |
| --- | --- |
| Membership | 3→4→5→4→3, replacement at each size, duplicate identity/endpoint, minimum/maximum refusal; exact old/new receipts |
| Partial transition | Crash before/after each intent, ACCEPT force, PROOF force, publication and response; lost replies query original operation |
| Competing leaders | Different candidates/operations on old, joint and new views; old-only/new-only partitions, higher ballots and late messages |
| Recovery | Restart all members or one member during each partial transition; accepted-only tails, divergent branches, superseded candidates |
| Learner | Lagging, corrupt, interrupted transfer, disk loss, stale catch-up receipt and repeated admission; no learner quorum contribution |
| Snapshot/floor | Install/selector crashes, compacted transition ancestors, bounded retained metadata; no unauthenticated configuration reconstruction |
| Reads | Strong barrier across membership change; stale/minimum capture, removed-node behavior, token continuity and wrong-history rejection |
| Operations | Stable ID and payload collision, timeout/cancellation, concurrent callers, bounded completed-result retention and stale plans |
| Maintenance | Serialized same-version stop/restart, leader removal, no-quorum refusal, node identity fencing and separately authorized cleanup |
| Resources | Six-identity peak, bounded transfer and queues, saturated/torn/corrupt authority, overflow and old operation metadata |

Phase 1 must add a genuine distributed transition/election model and independent
byte fixtures; this entry arithmetic model cannot substitute for them. Reuse the
existing deterministic transport and fresh-JVM patterns after choosing the new
protocol. Test corrupt evidence only after the original history passes, preserve
failed executions, and bind claims to the actual source/bytes/processes.

Freeze workloads, repetitions, control versions and exact bounds before formal
measurements. Later protected CI and cloud consumers need coherent source/artifact
inventories; don't append a workflow job while forgetting their exact-name/attempt
checks. V5.2's current 28-history or cloud results are predecessor evidence only.
