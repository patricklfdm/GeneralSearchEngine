# Bounded proof continuity within an original stable round

Status: conditional private proof component. Storage continuation and Phase 2
remain **OPEN**. The current generation reader still rejects this new component's
metadata; no vote, writer, public API or READY path is enabled by this batch.

## Why first-slot coverage is insufficient

The installed SELECTED record and every original BASIS must remain immutable.
After several entries, the current predecessor is above that original selected
cut. Changing SELECTED to the new predecessor would erase the original decision;
merely relaxing the first-slot index check would lose the original carried-choice
proof. Retaining every intervening entry would grow with ordinary workload size.

The new private component keeps a bounded proof set:

- The original selected parent and the first certified end's cut/catalog/image.
- The exact first certificate, ENTRY, ACCEPT, PROOF and payload.
- The current predecessor and its exact next certificate, ENTRY, ACCEPT, PROOF
  and payload.
- The existing authenticated checkpoint/ancestry proofs covering those endpoints.

First and current records share their objects when they are the same slot. Later
extensions retain only those two proof sets, together with the ordinary capsule
and required ancestry. Intermediate ordinary certificates are not accumulated.
The component uses canonical metadata capped at the existing 4 KiB coverage
limit and the existing packet/object limits. Payloads remain inside the bounded
source packet; no hash is substituted for an absent original phase or payload.

## Verification boundary

Beginning coverage first validates the existing exact first-slot representation.
Advancing revalidates the previous coverage before importing its first proof.
Only observations for that exact proof are carried into the new verified capsule;
unrelated historical observations are discarded. Both first and current proofs
require their own authenticated ACCEPT/PROOF observations. Checkpoint endorsement
alone cannot replace either proof.

The original selected quorum, proposer, ballot and authority stay fixed. The first
entry must match its original carried choice or current-ballot origin. Subsequent
entries must have the same ballot/origin, an exact next index and exact predecessor.
First-parent, first-end and current-parent anchors must be authenticated by the
capsule or retained ancestry; an advanced index is insufficient.

The first slot must end in the same stable configuration. Subsequent stable
entries use the actual frozen command kinds: DATA, BARRIER, RESERVE, PREPARE,
READY, SEAL, CANCEL and RETIRE. INTENT may terminate the old stable round. An
attempt to advance from its joint successor is rejected. FINAL and activation in
the new configuration remain fresh-campaign work.

This component proves durable-selection continuity only under its authenticated
input assumptions. A first carried DATA entry is not an activation barrier;
the protocol must still recover it and publish a fresh current-ballot BARRIER
before READY. No metadata restores leader readiness or callbacks after restart.

## Local validation

The [local source/build index](phase2-evidence/round-coverage.json) records twelve
passing Java methods: six new component tests, four existing capsule tests and two
existing publication tests. The latter retain all 63 transition/cut projections.

- A 100-slot same-ballot BARRIER sequence retains constant object count after
  startup, at most two supplemental ancestry groups, one logical stable range
  and only first/current proof sets. The small fixture measured a maximum packet
  of 18,475 bytes and coverage of 1,407 bytes.
- Seven add/remove/replace profiles preserve operation controls through INTENT
  and reject continued use of the old round afterward.
- Missing first/current phased observations, missing original proof records,
  altered parent/end/selection/certificate, higher substituted ballot, different
  root, stale carried choice, malformed/noncanonical and oversized metadata reject.
- Existing storage coverage validation rejects this new representation; public
  runtime and durable same-round voting remain disabled.

These are conditional in-memory fixtures. They do not claim fresh-process forces,
maximal payload admission, independent physical replay or production readiness.
The initial development test exposed an immutable-map mutation in its negative
fixture and an incorrect generic `CONTROL` kind in the new component. The latter
was corrected to the repository's actual concrete command inventory; the frozen
command and wire catalogs were unchanged.

## Next integration

1. Admit complete round coverage through selected generation verification without
   replacing legacy first-slot evidence or original selected-source bytes.
2. Validate subsequent local votes against the exact forced current predecessor;
   continue to allow only one unresolved slot and fence every force/publication.
3. Carry first/latest coverage through application, selector publication and
   covered-vote recovery. Reserve its packet, ancestry, metadata and image
   completion headroom before accepting the new entry.
4. Exercise repeated writes, immutable duplicate PREPARE, recovery interrupted
   again, original-first negatives and portable physical replay before enabling
   stable continuation in the runtime.

This does not waive [the full storage closure](PHASE_2_CLOSURE_CHECKLIST.md) or the
later distributed activation and public-service gates.
