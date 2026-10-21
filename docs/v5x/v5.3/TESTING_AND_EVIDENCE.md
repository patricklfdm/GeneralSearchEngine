# V5.3 testing and evidence

## Entry model scope

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

## Later foundation and runtime coverage

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
