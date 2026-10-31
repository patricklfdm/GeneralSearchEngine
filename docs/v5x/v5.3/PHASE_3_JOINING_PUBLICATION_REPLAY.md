# Native joining publication inventory replay

`scripts.v53.joining_publication_evidence` adds an independent physical transition
reader to the [complete original native ADD history](PHASE_3_JOINING_CATALOG_REPLAY.md).
The [batch receipt](phase3-evidence/joining-publications.json) binds the original
producer, current reader source, qualification results and portable inputs.

## Derived publication boundary

First replay the original bootstrap, eleven catalog transitions, original phased
certificates and checkpoint acknowledgements. For each of the 24 participating
node/slot pairs, use the original **applied** snapshot to construct the expected
**published** inventory. The expected bytes never come from that published
snapshot or its claimed hashes.

- Derive required anchors from the selected original bases, the first publication
  under that selection, retained original sources, peer possible/renewal points
  and learner possible/renewal points. Bind each anchor to the independently
  reduced history. Require exact applied ancestor labels and endpoints. This
  fixture has no unretired governing floor at these snapshots; a new such input
  is refused rather than ignored.
- Derive the compacted RANGE or membership item, exact packet object inventory,
  descriptor and original certificate bytes. Preserve the first certificate for
  same-selection continuation. Checkpoint ACKs must have actual observations and
  meet both governing majorities.
- Derive required ancestor groups and their order. At INTENT/FINAL, a retained
  hidden endpoint keeps its original stable-era statement and ACK bytes. No new
  cross-view ACK is manufactured to replace that original evidence.
- Construct selected or round coverage, then the complete alternate generation
  manifest and selector. Keep the previous generation intact until subsequent
  authorized maintenance; remove the applied-end tree and clear the pending vote.
  Reject extra generation members, unreferenced packet objects and omitted files.
- Reconstruct future-retention proof frames and the final cleared predecessor
  hash. Add the actual published endpoint only to dispatched peer rows, retaining
  prior confirmations and renewal debt. Publication does not itself reconcile
  the peer plan's governing view. All other ledger/source/grant bytes are unchanged
  across this transaction.

The original run passes all 24 publication comparisons, totaling 3,406,994 file
bytes (repeated snapshots counted separately). Its workload was **not rerun**.
Twenty-six original-first negatives cover self-consistent generation/packet
rewrites, missing first proof/ancestry, discarded old generations, altered
sources/grants/ledgers, incomplete retirement, early view promotion, the joining
owner's copied inventory, and missing/misnumbered applied ancestors. Each mutant
must still pass the earlier semantic reader and then fail the new reader for its
declared reason; an unrelated rejection cannot count as a successful negative.

```bash
python3 -B -m scripts.v53.joining_publication_evidence <original-raw-directory> --qualify
```

## Scope and remaining work

This is exact **applied-to-published** replay for one native `3-ADD` history,
including old owners and the joining owner's FINAL/new-stable BARRIER. It is not
yet whole-history physical qualification. Unchanged files are compared against
their original applied snapshot, not independently reconstructed through every
intervening election, selected installation, maintenance, source retirement and
joining custody transition. In particular, this gate does not turn a decoded
pre-publication ledger revision or confirmation into an independent force receipt.

The [slot force/ACK reader](PHASE_3_JOINING_PHASE_REPLAY.md) remains a separate
qualification of actual causal observations. Full send/arrival/transfer replay
still requires the updated producer's fresh complete execution. Preserve the
existing `df22c398` original and do not stitch it to another attempt.

`publicationPhysicalQualified` is true for this boundary only;
`completePhysicalQualified`, `forceAndNetworkQualified`, `processDeathQualified`
and `phase3Complete` remain false. All seven profiles, process interruption
matrix and frozen scenario/negative mappings remain required. No production
Java, public API, persisted format, POM, frozen limit or workflow changes are
made by this batch.
