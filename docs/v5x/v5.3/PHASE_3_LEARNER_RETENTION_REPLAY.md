# Independent replay of protected learner cancellation

Status: **PASS for the retained native history**, not complete Phase 3 acceptance.
The [source-bound receipt](phase3-evidence/learner-retention-replay.json) identifies
the runtime snapshot, reader inputs and original evidence. This completes the
reader gap recorded by [protected serving](PHASE_3_LEARNER_RETENTION_SERVING.md).

## Authority and original bytes

`learner_cancellation_evidence --retained-learners` explicitly enables the new
history model. It derives the empty owner ledgers from the original bootstrap,
the full PROMISE/ledger snapshots, selected merge objects, installation and each
native publication. Source offers add exactly the modeled endpoints 3 and 5 to
node 1 and node 2. The independently derived obligations preserve endpoint 3
through READY and CANCEL. Every physical snapshot must match the derived files;
neither a decoded ledger, a reported PASS nor an ACK supplies original authority.

The reader checks both local and remote file/parent force sequences before the
matching ACK and the first source exposure. It checks the complete request,
permanent identities, ballot, correlation, endpoint, ledger digest and revision.
All learner-retention wire rows must belong to the two original rounds; reusing
a trace cannot hide another endpoint. This fixture's ACKs are not withheld.
The original future-intent limit remains 15 attempts, separately from at most
three identical learner-intent attempts per round to the unavailable voter.

The original 31 acquisition and 28 progress exchanges, received generation bytes,
certified CANCEL, learner force order, unchanged original inodes and cold reopen
must all validate before any evidence mutation. The resulting terminal ancestry
contains exact endpoints 0, 1, 3, 4 and 5. Cancellation does not create a voter,
live core or public-ready runtime.

## Regression and retained scope

The native original passes, followed by 31 exact-reason evidence rejections:
the existing 12 cancellation cases and 19 retention cases. These include
well-framed wrong owners/roots/requests/identities/endpoints, lost obligations,
stale revisions, altered frozen and selected objects, ACK and force-order
changes, early source exposure, hidden extra rounds and retry-budget expansion.
An invalid unmodified history cannot count as successful negative qualification.

Legacy mode continues to require the old physical inventory. The earlier failed
native history still diagnoses the missing prepared ancestor as PARTIAL. The
original selected-retention process evidence replays all 16 halt/SIGKILL cases
and 12 negatives with a result identical to its historical receipt. Those process
cases cover the older selected-retention runtime; they do not establish process
death qualification for the new learner-retention path.

No Java or workload was rerun for this reader change. The native original is the
`learnerservingfinal` snapshot already executed in 377.4 seconds under its original
600-second budget. It precedes the final serving cut guard, as recorded by the
previous batch. This replay does not turn that snapshot into current-source,
all-profile, autonomous or process-death acceptance.

From the matching checkout, replay a retained original with:

```bash
python3 -m scripts.v53.learner_cancellation_evidence "$RAW" --retained-learners --qualify
```

Forced learner-head confirmation/narrowing, matching locally forced INTENT,
all five joining profiles, combined resource maxima, actual process cuts and
autonomous integration remain OPEN. Complete continuous histories remain intact
in the [deferred hosted matrix](PHASE_3_DEFERRED_ACCEPTANCE.md).
