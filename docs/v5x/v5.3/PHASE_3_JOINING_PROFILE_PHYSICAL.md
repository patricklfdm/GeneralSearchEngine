# Phase 3 — profile-aware joining publication and old-voter replay

The shared readers now accept the five explicit ADD/REPLACE profiles for three
bounded checks: slot force/ACK binding, exact applied-to-published inventories,
and independently reconstructed old-voter storage from bootstrap through INTENT.
The command returns `PARTIAL`. Joining initialization, continuation, newer-prefix
adoption, complete control attempts, export authority, maintenance/peer chains,
process death, all-profile execution and frozen mapping remain separate gates.
This batch does not change Java runtime code, workload parameters or workflows.
The bounded test-evidence envelope correction is described below.

## Actual profile owners and original publication receipts

Slot force validation derives permanent old/joining identities from the explicit
profile and actual certificate voters. An old node-4 is distinct from a joining
node-5/6. Unknown force owners, missing selected-owner forces and a joining force
from the wrong lifetime are rejected. Old-voter transition replay derives its
live majority from the profile, preserving offline originals and every observed
storage inventory instead of assuming two live owners.

A forced ACK is not necessarily an ACK collected by a publisher. The complete
3-REPLACE history illustrates this: the joiner writes its original checkpoint
ACK, but old node-1/node-2 already satisfy both majorities. The original
publication endpoint collects that sufficient pair. The earlier reader included
every globally observed ACK and therefore expected different publication bytes.

The corrected reader reconstructs each publisher's own ACK and complete remote
ACK transfers between its original `APPLY_BEFORE_RETURN` and
`PUBLICATION_VALIDATED`. It authenticates send/read/response/delivery, permanent
identities, ordered transfer sequences, exact content hashes and delivered
commits. The decoded voter must be the actual donor; the statement and ACK bytes
must match the independent semantic history. Duplicate voters, unobserved bytes,
foreign statements and out-of-window completion cannot supply a majority.
Expected published packets, ancestry, manifests, ledgers and selectors are then
derived from those collected originals, never from the output endorsement list.
Retained ancestry may contain an exact sufficient subset of observed ACKs; its
original bytes, canonical voter order and both majorities are still required.

Transport transcript replay is shared with the existing complete network reader.
The publication caller explicitly qualifies transfers only. The full reader's
strict treatment of unmatched/overlapping controls remains unchanged. In the
retained 3-REPLACE history, five unanswered `FUTURE_RETENTION_INTENT` sends target
an unselected joining owner. The original observations do not close those
attempts. They remain `NOT_QUALIFIED` for the full network gate; a successful
publication or semantic FINAL does not promote them to successful control ACKs.

## Four-member collection failure and bounded evidence envelopes

The new complete 4-ADD execution observed FINAL at 10, the stable BARRIER at 11
and the retaining cold reopen. Its single JUnit test then failed during
`Network.close`: serializing `wire.json` exceeded the old 16 MiB evidence limit.
The writer had not yet saved `wire.json`, `events.json` or the final old-owner
snapshot. The native receipt remains FAIL; neither successful stage messages
nor the retained joining cold snapshot can turn this incomplete history into
qualification. The failed execution took 1,181.365 seconds and was not retried.

The test writer and all joining-history readers now share 64 MiB wire / 32 MiB
event limits and a maximum of 65,536 rows. Individual rows remain bounded to
16 MiB with the existing canonical JSON depth/token/field checks. Delimiters
count toward the aggregate limit. Protocol messages, storage/runtime resource
limits, frozen workload parameters and deadlines are unchanged. This is a
bounded test artifact capacity correction, not an unlimited runtime allocation.
A focused writer regression preserves every byte of an 18 MB aggregate rejected
by the old envelope, and readers check the matching capacity and reject both
excess row count and oversized individual rows. A complete corrected-source
4-ADD execution remains required in the later hosted cohort.

The failed original still supports a clearly marked diagnostic: independent
reduction of eleven stored slot certificates and derivation/comparison of 84
old-owner snapshots through slot 8. That diagnostic is NOT_QUALIFIED and does
not replace the missing network/force trace or a successful complete execution.

## Commands and rejection checks

```bash
python3 -B -m scripts.v53.joining_profile_physical_evidence /path/to/raw \
  --profile 3-REPLACE --qualify

python3 -B -m scripts.v53.joining_profile_physical_evidence /path/to/raw \
  --profile 4-ADD --qualify
```

Supported profiles are `3-ADD`, `4-ADD`, `3-REPLACE`, `4-REPLACE`, `5-REPLACE`.
The producer remains `scripts.v53.joining_profile_run --complete`; each native
history owns fresh disks and is never retried or spliced to another history.
Reader source and native source/build are recorded separately when replaying an
older retained execution. A whole profile can run independently in a future
hosted cohort; its bootstrap, membership slots and cold reopen cannot be split.

The original must pass all three scoped readers before any of twelve disposable
mutations runs. Each mutation must still pass the semantic reader and fail its
specified physical/causal gate for the exact declared reason. Cases remove a
selected-owner force or checkpoint send/delivery, add a foreign force owner,
change published objects/coverage/retention and alter installed/applied storage
or offline owners. Applied-state mutations also recompute a self-consistent
published successor, so rejection must come from the earlier storage history.
Original inventories are checked again after validation and negative replay.
The existing default 3-ADD reader/negative entry points are retained.

## Evidence and next boundary

The [batch receipt](phase3-evidence/joining-profile-physical.json) records actual
executions, reader/source/build identities, regression results, retained failures
and portable replay. Its flags distinguish supported profiles from executed
profiles and these three scoped gates from complete Phase 3 qualification.

Next generalize the joining initialization/continuation and maintenance readers,
including unselected joining adoption and same-view recovery. Add original
terminal observations and refusal binding for unsuccessful control attempts;
keep the complete reader fail-closed until those attempts are explained. Then
run the remaining complete profiles, fault/process compositions, both REMOVE
profiles and unchanged frozen S/N requirements. No public READY, paid-cloud or
full-phase acceptance follows from this batch alone.
