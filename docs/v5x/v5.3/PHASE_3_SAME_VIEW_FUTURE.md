# Phase 3 — continuous same-view future-retention chain

The [same-view authority gate](PHASE_3_SAME_VIEW_AUTHORITY.md) remains the complete
original-first prerequisite. `scripts.v53.joining_same_view_future` adds continuous
GSFT revision derivation and exhaustive future-retention callback consumption for
that single retained `3-REPLACE` history. No second native execution supplies events
or storage, and observed per-slot snapshots never reset the expected ledger.

## Continuous derivation

Each original owner starts from its bootstrap empty ledger. The joining owner
gets a separately derived revision-zero empty ledger at completed initialization.
Every applied snapshot must equal the preceding derived state before a new target
can be recorded. Target proof records come from the already independently derived
original application end and campaign. Each successor names the exact preceding
bytes and increments its original owner's revision once.

A recording consumes one complete write/force/rename sequence, completed return
and ACK callback in the original owner scope. The local ACK precedes the matching
request send; the remote write follows its original receive and completes before
the matching response offer. The original network gate checks the full request,
response, revision, digest and delivered governing quorum.

Clearing requires the original publication's promotion boundary, one complete
durable replacement, the clear callback and the published ledger. The earlier
peer gate independently binds the covered dispatch merge before promotion.
Generation installation and FINAL adoption preserve the continuous local future
state. Cold snapshots must equal the derived terminal state.

All eight original opens require active-file and directory force in order, after
peer-ledger recovery. Ordinary opens finish future recovery before accept-file
recovery. The first joining owner instead follows completed joining initialization;
it does not invent an absent accept recovery or open-return callback. The retained
cold-open fixture also supplies an explicit return boundary. Unknown recovery
events, unfinished writes, duplicate completions and unconsumed events fail closed.

## Qualification boundaries

```bash
python3 -B -m scripts.v53.joining_same_view_future /original/raw \
  --qualify --workers 4
```

The full unchanged original passes physical, network, export, maintenance and peer
composition before any negative starts. Nineteen disposable-copy mutations target
only `FUTURE_RETENTION_*` callbacks. Every other original file (including wire),
directory and non-future observation must remain identical. The future reader must
reject each mutation with its exact declared reason; wrong errors do not qualify.
These are focused future-reader negatives: their mutated prerequisite layers are
not rerun, and the receipt explicitly records that distinction. Up to four evidence
replays run independently; no native history or measurement is retried or divided.

The [batch receipt](phase3-evidence/same-view-future.json) records the actual frozen
reader, test and qualification results, original-input references, archival hashes
and relocated replay. The development diagnostic that expected every owner to have
`FIXTURE_OPEN_RETURNED` is retained; actual originals record that marker only for
the final cold owner. The implementation now binds the actual native recovery
events for the other opens.

The frozen qualification completed in 101.042 seconds, with all 19 mutations
rejected. Its original has 44 durable writes (22 records and 22 clears), eight
open reseals and 78 ledger comparisons. Final revisions are 22 for nodes 1 and 2,
and zero for nodes 3 and 4. All 498 joining Python tests pass, including 15 new
focused regressions. The source and original input inventories remain unchanged.

The archive retains 8,683 files and 1,206 directories in 18,892,011 bytes. Every
file hash and directory entry, including empty directories, was verified after
extraction. Relocated `python -O -B` replay completed in 42.131 seconds with the
exact same composed result and unchanged source/input inventories.

## Remaining closure

The aggregate remains **PARTIAL**. This qualifies the observed continuous future
ledger of this one healthy original, alongside its existing authority prerequisite.
It does not qualify pending-target crash recovery or other histories merely by
reusing their component tests. Full learner-ledger composition, the current-source
profile cohort including REMOVE, whole-history process cuts and frozen acceptance
mapping remain open. `learnerLedgerCompositionQualified`,
`sameViewPhysicalQualified`, `completePhysicalQualified`, `forceAndNetworkQualified`,
`processDeathQualified` and `phase3Complete` remain false.

No production Java, workflow, POM, frozen resource/timing or paid-cloud changes.
