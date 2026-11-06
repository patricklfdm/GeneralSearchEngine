# Phase 3 — publication handoff and cooperative liveness

Phase 3 remains **OPEN**. The first native seven-family capture exposed an
old-view heartbeat during FINAL publication. This increment corrects that
scheduling boundary; it does not relax pending-vote adoption or make partial
publication service-ready.

## Retained failure

The original `1014f510` FINAL/PROOF/SIGKILL producer failed after reopening on its
same four original directories. Both selected remote voters published cut 6 in
the new stable view. Node 1 retained cut 5, its certified ACCEPT and native applied
end. It received node 2's publication ACK; node 3 produced an ACK, but no receive
was observed. While waiting, the coordinator sent heartbeats under the old joint
view. The changed peers could not supply that old-view contact. Fresh discovery
then attempted adoption and correctly refused the still-pending ACCEPT:
`pending ACCEPT requires covered-prefix publication before adoption`.

The original failed process receipt, callbacks, TCP responses and 8,180 files
(58,845,658 bytes) remain unchanged. Their inventory and diagnostic sequence are
under `target/v53-native-seven-capture`. The full reader rejects this original
before owner-mutation qualification; its failure earns no successful capture or
negative-test credit. No overall producer timeout caused this failure.

## Corrected boundary

All selected receivers first complete APPLY. Every intended receiver then gets
the existing governing future-retention quorum before any PUBLISH dispatch.
Immediately before those dispatches, the slot compares its actual certified
application's target view with the original installed view. When they differ,
only cooperative heartbeat sampling stops for the remaining publication handoff.

This pause covers the interval in which a remote PUBLISH may have changed its
view, even if the acknowledgement has not arrived. It ends with the slot's
lifetime. The outer round still needs actual local publication, a new installed
authority and its fresh barrier before READY. INTENT and FINAL therefore cannot
mistake their successful remote view change for lost old-view liveness.

Ordinary same-view slots keep sampling throughout publication. Before dispatch,
transition recovery also keeps sampling. Local voting, future-retention and
transport write guards continue checking cancellation, exact application owner,
original ballot and original deadline. The change creates no lease, resets no
deadline and alters no persisted format, workload parameter or resource limit.
The pending-ACCEPT adoption guard is unchanged. Other genuinely lost publication
or higher-ballot histories still require their own recovery qualification.

## Qualification and follow-up

`V53PublicationPulseTest` uses real native activation, application and TCP
publication. Its FINAL regression fails against the unchanged original runtime
at the obsolete sample. It also covers INTENT, same-view sampling and guards
at the actual publication write boundary. Scheduling and joint-quorum tests
remain separate from full process/history evidence.

The seven-family storage reader also gains original-first owner negatives. It
selects actual required GENERATION, SOURCE, JOURNAL, MISC and six APPLICATION
owners from the admitted file/resource joins. Substitution preserves the complete
accounting transitions and totals, yet must fail the exact physical-owner binding.
Unknown/missing owners, aliased substitutions and an invalid original cannot earn
negative credit. Mutations are in-memory accounting variants; no mutated physical
prerequisite or whole-runtime acceptance is claimed.

Validation results and their source/hash bindings are recorded in
[`publication-handoff-development.json`](phase3-evidence/publication-handoff-development.json).
The corrected local runtime passes all 13 Java checks (five native publication
cases, five scheduling checks and three joint-quorum checks), with no errors,
failures or skips. The old runtime fails the FINAL regression at the declared
obsolete sample. The reader has 397 related Python checks and 40 focused checks;
the focused set also passes with Python assertions disabled.

One corrected FINAL/PROOF/SIGKILL producer completes in 595.443 test seconds.
The first child exits 137 at its declared boundary; the second opens the same
four original stores, completes recovery and a fresh barrier, then exits 0 with
zero client calls. Its receipt remains `PARTIAL`, separate from the independent
physical, callback, network and resource replay. All 10,188 retained files
(75,690,709 bytes) remain available for that replay.

The complete seven-family prerequisite and original file/resource join pass
before any negative mutation, covering eight owner lifetimes:

| Captured family | Original boundaries |
| --- | ---: |
| Generation/source retirement | 595 |
| FLOOR acquisition and cleanup | 998 |
| Campaign/grant/selected installation | 457 |
| ACCEPT/PROOF/CERTIFICATE | 169 |
| Applied-end/publication/covered cleanup | 450 |
| Peer/future retention ledgers | 298 |
| Control replay scratch | 115 |
| **Total** | **3,082** |

All ten owner substitutions preserve accounting totals and reject with the exact
`storage coverage original charge owner` reason. This is one native axis, not
the complete crash/profile matrix. Physical peaks are observed logical extents
at captured callbacks, not a proof of all internal writes or the full simultaneous
runtime resource envelope.

Two predeclared capture mutations per family also reject exactly: one missing
callback and one family-specific altered physical prefix, 14 variants in total.
These are targeted checks, not execution of every family's entire negative
matrix. Relocating the complete original collection to a new directory and
replaying with `python -O` produces exactly the same decoded original result.
The original and corrected collections retain their original hashes throughout.

Remaining process axes, DATA/internal-core interruptions, complete simultaneous
resource qualification and final-source hosted acceptance remain OPEN.

Rollback restores the previous slot sampling boundary; no disk migration is
needed. Preserve this batch's original failure and corrected observations as
separate evidence.
