# Phase 3 — profile future and learner ledger composition

This follows [profile peer ledgers](PHASE_3_PROFILE_PEERS.md). One unchanged
original must pass physical continuation, attempted network, original export,
control, maintenance and peer-ledger validation before these two ledgers are
accepted. The profile selects actual old voters and the joining identity; a
producer result label does not supply quorum or ownership authority.

The readers share the original maintenance/control context, not the peer
ledger constructor. The first qualification attempt showed that constructing
another peer ledger intercepted two learner-reopen negatives before the
designated learner checks. That failed attempt is retained. Complete original
peer validation still precedes both readers; each negative must reach its exact
designated ledger rejection instead of borrowing an error from another layer.

Both readers now use all original voters and the five declared joining-owner
opens. Old `node-4` is an ordinary voter in larger profiles; joining `node-5` or
`node-6` has its own scoped admission, initialization, continuation and cold
recovery. Every observed force, revision, completion and reseal still has to be
consumed once. Derived predecessors are compared against original captured,
installed, adopted, applied, published and cold bytes, never reset from them.

## Original recording rounds

The future reader obtains the proposer and proof targets from the original
certificate. The proposer's local recording ACK must precede the earliest
original send to **any** recipient for that certificate and target. Matching
only the eventual publication target could admit an ACK after an earlier send
to another voter. Every remote recording remains bounded by its original
receive/response interval and exact derived revision and digest. Future records
are promoted and cleared through the existing continuous revision chain.

The learner reader groups recording requests by original sender and trace.
Sender identity, view, ballot and payload must agree throughout the group, and
remote voters must be distinct and different from the sender. The sending
generation owns one local write before the first send; each remote owns its
own observed write before its response. Two remote ACKs do not schedule the
same local write twice. An unused late or undelivered reply does not move the
local force into a later generation. The preceding profile control reader still
requires the original delivered governing majority before learner export.

Admission custody is a distinct eleven-callback transaction. It does not count
as a learner ledger revision. Confirmation proofs, selected merges, no-op
accounting and exact revision/predecessor checks retain their existing rules.

## Qualification and evidence scope

```bash
python3 -B -m scripts.v53.joining_profile_ledger_evidence /path/to/original \
  --profile 5-REPLACE --qualify --workers 2
```

The adapter exposes nineteen future and twenty-six learner negative cases.
After complete original-first validation, each disposable mutation may change
only its designated callback family. All physical files, wire bytes, directories
and every other observation must remain unchanged. The designated ledger reader
must then fail with the exact expected reason. The mutated prerequisite chain
is **not** separately replayed; receipts explicitly record this scope, rather
than claiming every preceding gate passed on each mutated input. Invalid
originals, unrelated errors, missing targets and accepted mutations fail.

The one explicit applicability exception is learner `wrong-write-scope`: if
the independently derived original chain contains zero joining-owner writes,
there is no such transaction to mutate. It is reported as `NOT_APPLICABLE`,
separately from successful rejections. Conditional tests still exercise valid
and invalid actual joining-owner scopes. No other missing target is skipped.
Replay concurrency is bounded to one through four workers; each worker has its
own disposable copy. There are no measurement or workload retries.

The [receipt](phase3-evidence/profile-ledgers.json) records original provenance,
reader source, conditional regressions, measured negatives and portable replay.
Historical three-node originals and conditional larger-profile checks do not
establish a final-source larger-profile native cohort.

Measured validation: all 1,872 V5.3 Python tests pass, including eighteen new
conditional regressions. The retained 3-REPLACE derives 44 future writes and
eight learner writes; historical 3-ADD derives 54 and nine respectively. Both
original ledger chain hashes match the preceding read-only composition audit.
Across these two originals, 89 exact negative cases are rejected and one absent
joining-owner write target is explicitly not applicable. The complete same-view
result is unchanged in every field.

All three originals replay identically after archive extraction with Python
assertions disabled. The 40,726,869-byte archive retains
21,463 files, original producer provenance, frozen reader source
and regression diagnostics. Original and extracted inventories remain unchanged.
These results do not establish new larger-profile native or process execution.

## Remaining closure and rollback

[Profile ballot composition](PHASE_3_PROFILE_BALLOTS.md) is now recorded separately.
Final-source seven-profile/native process and fault cohorts, combined resource
bounds and frozen S/N coverage remain OPEN. Phase 3
is not complete. This batch changes evidence readers and tests only; Java,
POMs, workflows, persisted formats, workloads and timing/resource limits are
unchanged. Long complete cohorts remain in the deferred hosted acceptance plan.

Rollback restores the shared future/learner helpers and removes this adapter,
while retaining original evidence, source manifests and failed regression logs.
