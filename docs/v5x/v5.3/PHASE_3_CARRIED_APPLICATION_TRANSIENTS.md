# Phase 3 — carried application transient composition

Phase 3 remains **OPEN**. This development entry adds vote, normal recovery
completion, peer/future ledger and typed replay captures to the existing
[five-family application history](PHASE_3_CARRIED_APPLICATION_STORAGE.md).
The original INTENT or FINAL application ACK death, old-end retirement, recovery
and fresh stable BARRIER remain one two-process history. It does not split the
history into independent fixtures or retry a mutation after an uncertain result.

## Original capture and independent replay

The producer retains the interrupted application sidecar in the first lifetime
and the normal completion sidecar only in the recovered lifetime. A missing
recovery lifetime or an extra first-lifetime normal completion directory rejects.
Vote, ledger and replay captures cover both original lifetimes. The worker accepts
the existing resource-only and maintenance layouts, or the complete new layout;
partial combinations reject. Existing constructor mutual-exclusion checks remain.

The application-specific protocol reducer projects interrupted ACCEPT and PROOF
transactions for the actual selected voters, and a CERTIFICATE only for the local
leader before the ACK death. It preserves the original staged-owner deferral and
local FLOOR pins. Recovery uses the existing complete completion file vocabulary.
Ledger models retain continuous revisions across both lifetimes and derive every
write/reseal from the original peer/future history. Typed replay includes old-end
retirement as well as the original control operations.

The reader first validates the complete original physical, protocol, wire,
export, retention, resource and five-capture chain. It then compares the four new
sidecars with independently projected exact file inventories. Expected states
alone earn no captured-byte credit. The existing replay resource-interval checks
remain mandatory.

Nine capture families contribute to physical resource binding. The only allowed
duplicate is a replay callback observed by both the old-end retirement sidecar
and the general replay sidecar. Original lifetime, event index, node, point and
file inventory must agree. The reader compares both physical captures, then
counts that callback once. Conflicting inventories, a third observation or any
other overlapping family reject. Each remaining callback binds to the same
owner's original resource sequence, including complete file lengths and the
existing interrupted-versus-normal-close rules.

## Negative qualification and scope

The new entry declares 116 exact negatives: 34 vote, 29 completion, 28 ledger and
25 replay mutations. Each mutation changes only a portable copy of one capture
family after the complete original passes. An unrelated error earns no negative
credit. The preceding 89 maintenance, 29 old-end and 24 first-ACK negatives retain
their own readers. Whole-union balanced-owner substitutions are checked separately
against the admitted original and preserve resource accounting totals.

`applicationTransientCompositionQualified` describes this one original's capture
composition. `fullTransientBytesQualified`, `wholeRuntimeResourcesQualified`,
`cohortAdmitted` and `phase3Complete` remain false. This is neither a complete
simultaneous resource envelope nor final-source cohort admission. The four native
entry methods exist, but a selected development execution does not establish the
remaining axes. Published-operation readiness and the frozen final acceptance
scenario matrix remain owned by Phases 4 and 5.

```bash
python3 -B -m unittest scripts.v53.test_native_carried_application_transients
python3 -B -m scripts.v53.native_carried_application_transient_prefixes \
  ORIGINAL_APPLICATION_TRANSIENT_WRAPPER --qualify
```

The short tests use synthetic states and mocked prerequisite failures. Portable
qualification must retain source/build/toolchain manifests, exact unretried
JUnit methods and the complete original inventory before a development result
can be recorded. Full hosted execution is deferred until source-bound cohort
admission is implemented.

## Recovery custody correction

The first development `FINAL/SIGKILL` process passed, but its portable physical
resource replay rejected two original recovery boundaries:
`RETENTION_RECOVERY_ACTIVE_FORCED` and `RETENTION_RECOVERY_PARENT_FORCED` on
node 1. The existing `applied-end/application.image` was present in both actual
captures, while its APPLICATION reservation was not acquired until after peer
ledger reseal. The four new capture families passed their file comparisons;
this was a live resource-custody gap, not a missing file-name mapping.

`MembershipGrantJournal` now opens the existing application replay/end owners
before learner and peer retention reseal. Certificate checks, completion
admission, force ordering and configured limits remain in place. A failed open
still closes the already acquired children through the journal's existing
rollback path. The reader continues to reject the original failed trace; no
later reservation is borrowed to make it pass.

The deterministic regression creates a real locally certified application end
interrupted at its ACK directory force. It checks exact live image ownership at
both peer reseal callbacks, injects an exception at each callback, verifies
unchanged storage and complete rollback, then opens and closes normally. It also
checks that an invalid application inventory rejects before those callbacks and
does not leak a reservation. This regression fails on the preceding runtime at
the missing image owner. It is not a substitute for a fresh two-process native
history on the corrected runtime.

## Development qualification

The [development index](phase3-evidence/carried-application-transients-development.json)
retains both source snapshots and the original failed trace. A fresh, unretried
`FINAL/SIGKILL` native execution on the corrected development source passed in
625.807 seconds. The first child exited 137 at the declared ACK cut; the second
reopened the same stores and closed normally with exit 0. All 17 selected Java
tests passed. The separate targeted run passed 24 non-network tests; its five
sandbox socket errors are retained, and those same five tests passed in the
permitted native group. These test counts overlap and are not added together.

Portable qualification passed in 426.353 seconds, including 258 exact file
negatives and ten balanced-owner substitutions. All 10,599 original files
(80,274,926 bytes), the producer source and compiled classes remained unchanged.
The same 14 executable files used by the producer remain bound to this record;
later documentation changes do not turn the dirty development snapshot into an
exact-commit cohort.

| Capture family | Original callbacks |
| --- | ---: |
| Interrupted application | 32 |
| Old-end retirement | 54 |
| Ordinary retirement | 597 |
| FLOOR | 1,077 |
| Campaigns | 457 |
| Votes | 198 |
| Normal completion | 450 |
| Peer/future ledgers | 298 |
| Typed replay | 161 |

The two replay sidecars agree at 23 shared callbacks, leaving **3,301 unique
callbacks** across eight owner lifetimes. The crash lifetime retains outstanding
charges; all four recovered owners close with no remaining charges. The 116 new
negatives and all 142 preceding capture negatives ran against this same original,
followed by the ten whole-union owner mutations. No separate historical success
was substituted for a stage of this qualification.

All 375 related Python tests, the 60 focused tests under optimized Python and
the 35 planning/contract tests pass. These suites also overlap. The 398 earlier
development index files are unchanged. Other application axes, source-bound
cohort admission, hosted execution and the complete resource envelope remain
pending; Phase 3 remains OPEN.

Rollback removes the new outer wrapper, four-family projections and entry methods
together, restoring the previous worker layouts and protocol collector dispatch.
Keep the original evidence and preceding five-family readers. Reverting the
runtime reorder restores the diagnosed custody gap and must not retain a claim
of corrected native qualification. Persisted formats, workload parameters,
resource limits, POMs and workflows are unchanged by this batch.
