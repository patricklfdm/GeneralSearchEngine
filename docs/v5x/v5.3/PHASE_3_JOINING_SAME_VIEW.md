# Phase 3 — joining recovery within the final view

The complete `3-REPLACE` producer now has an explicit `--same-view` mode. It
executes one original bootstrap-to-FINAL history, lets the actual joining owner
adopt FINAL over TCP, then lets the old overlapping majority publish BARRIER.
The joining owner must install that newer cut through a fresh ordinary selected
campaign. It cannot substitute a newer-authority adoption, another workload slot,
a copied directory, a different selected quorum or a producer success label.

The first execution reached FINAL on the joining owner and BARRIER on the two
old surviving voters, then failed with `pre-grant original copies unavailable`.
Its inactive generation still needed safe retirement, but maintenance discarded
every peer whose current cut was newer. Repeating the same discovery could not
produce the missing exact-cut majority. The unchanged failed original is retained.

## Covering copies and the local floor

A complete original generation in the same governing view may now protect the
local floor when its verified capsule and retained ancestry prove the exact local
cut, catalog and application. A higher index or STATUS reply alone never suffices.
The existing original generation/force observation, permanent identity, complete
member and image checks, local original copy and both governing majorities remain
required. An earlier cut, another view or a compacted prefix without the local
anchor is rejected.

The FLOOR still records the local cut. Each source reference identifies its own
unaltered complete generation, catalog and application. Whenever a later operation
needs the floor's local anchor, it uses the local voter's reference, which need not
be the first row. Cold reopen rechecks the complete same-view containment proof.
The same-cut case retains its existing record bytes.

Maintenance fetches and checks complete newer generations before admitting them.
It keeps all original receiving/floor reservations and force-before-retirement
ordering. It does not advance the local peer ledger to a future endpoint that its
current capsule cannot yet represent; those conservative obligations remain until
selected installation. Newly added peer reconciliation still requires its exact
joining copy. Source/image/generation limits, deadlines, ballots, voting and READY
rules are unchanged. See [amendment A70](PHASE_3_CONTRACT_AMENDMENTS.md).

## Execution and semantic gate

```bash
python3 -u -B -m scripts.v53.joining_profile_run /new/whole-history \
  --profile 3-REPLACE --complete --same-view
python3 -B -m scripts.v53.joining_same_view_semantics /original/raw \
  --profile 3-REPLACE --qualify
```

The runner freezes source/build/toolchain evidence, reports progress each minute,
preserves failures and never retries or overwrites a history. It requires the exact
same-view JUnit method and reader; the ordinary completion method cannot satisfy
this mode. Other profiles are rejected before output creation.

The semantic reader first checks the full eleven-slot catalog/certificate chain
and original cold boundaries. It then checks the actual FINAL adoption and BARRIER
installation snapshots, permanent identity, fresh local ballot, selected majority
and installed selection bytes. Seventeen exact negatives include the nine existing
completion mutations and eight recovery-specific mutations. Invalid original
evidence or an unrelated mutation error cannot qualify a negative.

Semantic success remains **PARTIAL**. `sameViewPhysicalQualified`,
`completePhysicalQualified`, `finalAndColdReopenQualified` and `phase3Complete`
remain false. Full byte derivation of unequal-source maintenance and installation,
their force/transport/export composition, complete profile/process cohorts and the
frozen acceptance mapping remain separate required gates. The existing adoption-only
physical/network reader must continue rejecting this new path until that derivation
exists; the semantic result does not override it.

The subsequent [same-view storage replay](PHASE_3_SAME_VIEW_PHYSICAL.md) now
derives this original's unequal-source FLOOR, retained source transactions and
selected installation through cold reopen. Full force/transport/export composition
remains separate; this does not promote the semantic receipt to complete physical
qualification.

## Retained validation

The [batch receipt](phase3-evidence/joining-same-view.json) records the failed
original, the exact corrected execution and its reader, focused storage/maintenance
tests, semantic negatives and archive inventory. Java conditional-copy tests are
separate from the real TCP history. A passing local execution does not establish
all-profile or process-death qualification. No push, workflow dispatch or paid
cloud execution is part of this batch.

The corrected complete 3-REPLACE execution passed in 730.149 seconds, followed by
all seventeen semantic evidence negatives in 28.420 seconds. Original retirement
captures record a local node-4 floor at cut 10 backed by node-4's complete cut-10
copy and node-1's complete cut-11 copy. This observed inventory supports the
reproduction; it is not the pending independent full physical derivation.

Eighty-two focused Java cases pass, separately from that complete native history.
They cover exact-copy/quorum constraints, missing compacted ancestors, interrupted
mixed-copy floor establishment, cold reopen and corruption refusal, later adoption
using the local floor anchor, original retirement/release, conservative peer debt
and cancellation/drain. The new covering-copy regression fails on the original
implementation. One new test initially used the retirement-only storage opener
before exercising floor release; it now uses the existing maintenance opener.
That diagnostic is retained alongside its passing correction. All 441 joining
Python tests pass, including eleven new boundary/runner tests.

The complete archived history also passes the unchanged frozen semantic reader
after extraction, with Python assertions disabled and all seventeen exact negative
results unchanged. The failed original is rejected before mutation because its
post-recovery snapshot is absent. The first local archive omitted empty source
directories and failed bootstrap inventory validation; it remains retained. A
separate corrected archive verifies every original directory and file. No runtime
or reader change was needed for that packaging error.
