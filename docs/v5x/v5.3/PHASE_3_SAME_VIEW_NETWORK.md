# Phase 3 — original same-view recovery network replay

This composes the [same-view storage derivation](PHASE_3_SAME_VIEW_PHYSICAL.md)
with the original transport transcript. It reuses the retained `3-REPLACE`
execution; no workload is rerun and no histories are stitched together.

## Boundaries

`scripts.v53.joining_same_view_network` first derives the complete original
storage history. Only then does it supply the exact recovery SELECTED bytes to
the shared transport reader. Ordinary ADD/REPLACE readers still require their
original selection inventory; an extra recovery cannot silently pass them.

The recovery must use the joining voter as proposer, the exact final cut and
authority, and its original selected sources. The fresh PREPARE/PROMISE exchanges
bind every source to its full captured grant. Each promise follows its original
force sequence; selection follows delivery of all selected remote promises.
Every SELECTED force belongs to a known selected owner and campaign. Unknown
owners, extra forces and incorrect owner lifetimes are rejected.

Remote installation ACKs bind the exact selection and cut. Their force windows
require the manifest, every image/member, generation, selector rename and parent,
and current generation reseal before the installation return and ACK. The
recovery's remote snapshot is `same-view-installed`, not a previous campaign's
similarly numbered snapshot.

The joining proposer must return its durable selection before propagation and
receive the remote installation ACK before beginning its own installation. Its
original member inventory determines the local force sequence through return,
before the original stable cold-open boundary. Missing, duplicate, prematurely
executed or foreign-owner installation events fail. Local installation is not
represented as a fabricated network ACK.

The complete transport replay also retains response-less failures and their
caller/receiver terminal observations. Byte-identical transfer retries keep their
original attempt identity; they do not produce extra measurements or votes.

## Validation

```bash
python3 -B -m scripts.v53.joining_same_view_network /original/raw --qualify
```

The original must pass first. Each negative then changes only `events.json` and
`wire.json` in a disposable copy. All other original files, hashes and directory
entries must remain identical before the storage derivation can be reused.
The exact designated failure is required; an unrelated failure or an accepted
mutation cannot count as a rejection.

The matrix includes the existing 22 transport/force negatives, twelve recovery
negatives, and six terminal negatives when the original contains a paired failed
attempt. Fifteen focused conditional tests cover explicit dispatch, authority,
remote/local installation order, missing ACKs, immutable originals and rejection
integrity. These small fixtures do not claim native execution qualification.

The [batch receipt](phase3-evidence/same-view-network.json) records the retained
source, original input, actual replay outcomes, archive and portable validation.
The positive original binds 19 grants, 14 selection forces, nine PROMISE replies,
seven installation ACKs, 55 slot-phase responses, 524 committed transfers and
five failed attempts. The recovery contributes one remote installation ACK and
one local joining installation.

The frozen original-first matrix passed all 40 exact negatives in 205.958
seconds; all 466 joining Python tests passed. An earlier complete `3-REPLACE`
history reproduced its exact previous network result. After archive extraction,
the new history also reproduced its exact result with Python assertions disabled
in 24.153 seconds. The archive verifies 13,080 files and 1,489 directories,
including empty directories. Earlier failed diagnostics remain retained.

## Remaining scope

The result remains **PARTIAL**. `observedNetworkQualified`, `durableACKsQualified`
and `recoveryLocalInstallationQualified` describe the above observed boundaries.
Full export authorization and the composition of every maintenance, peer/learner
ledger and installation lifetime remain open. This batch does not independently
qualify all retention-write force windows merely because their final storage
bytes were derived. `sameViewPhysicalQualified`, `completePhysicalQualified`,
`forceAndNetworkQualified`, `processDeathQualified` and `phase3Complete` remain
false. The complete current-source profile cohort, REMOVE histories, process
cuts and frozen acceptance mapping are still required.

No Java runtime, wire format, workflow, POM, resource limit or time budget changes.
No paid cloud, push or workflow dispatch is part of this batch.
