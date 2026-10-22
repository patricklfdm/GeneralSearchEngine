# Stable rounds and complete metadata retention

Phase 0 candidate decisions D03/D06/D09. This refines the deliberately expensive
fresh-ballot/full-prefix research reference. Production Java remains unchanged.

## Stable round

An activated round is bound to immutable root, ordered ballot, leader incarnation,
stable configuration generation/digest, original frozen bases and the exact forced
selected source set. A current-ballot fresh barrier must first be proven, locally
forced and published. The local proposer belongs to that selected quorum.

Reuse that round for sequential DATA, CONTROL and strong-read BARRIER entries.
Every entry binds its exact forced predecessor and retains separate durable ACCEPT
and PROOF quorum requirements. One unresolved slot is allowed; there is no pipeline
past an uncertified predecessor. Operation commands also satisfy the deterministic
catalog reducer before voting and after applying; CONTROL cannot encode INTENT.
Reusing a round does not reuse an earlier entry's receipts or grant a time lease.

The original basis remains immutable. Duplicate PREPARE at this ballot returns it,
even after later publications. A new ballot freezes the current prefix and owned
accepted tail. A failed selected source requires a new ballot; do not substitute
another source in the existing selected set. Retry only the identical exchange
under its original correlation/deadline, never resubmit an indeterminate mutation
as a new client call. Recover the selected tail before taking another operation.

INTENT is the final old-stable-round entry. Local INTENT force ends old READY and
fences further old-era service; FINAL uses a fresh joint campaign. After FINAL,
a fresh new-stable barrier activates service. A membership round trip cannot reuse
an old grant merely because its voter names happen to match: generation is bound.
The removed proposer may help finish the joint campaign if it is still an eligible
old voter, but cannot activate or serve as the new stable leader.

A higher observed ballot prevents a pending force/publication at the old ballot.
A leader process restart permanently ends its old volatile round, including any
pending callback. Recovery retains durable promises, original bases, selections
and owned tails; it never reconstructs READY from a file. A follower restart may
resume the live leader's exact round only after verifying retained grant, selected
installation and proven parent, and only absent a higher promise/fence.

The new reference starts with an actual independently replayed global activation,
not an invented READY bit. It tests stable sequential extension separately from
the operation reducer. Their full same-round composition and actual Java/storage
behavior remain required Phase 1–4 tests, not claims of this abstract model.

## Complete catalog capsule

The application snapshot alone is insufficient. A checkpoint binds the complete
operation catalog: current descriptors/configuration, generation, next operation
number, retired-result watermark, retained result rows, active preparation/revision,
learner receipt, and all permanently reserved identities, including cancellations.
Deleting an old result must not free its number, disk identity or endpoint.

A stable range may summarize DATA, BARRIER and CONTROL only with **new durable
checkpoint endorsements** over the exact start/end authority, before/after catalog
hashes and application hashes. These receipts are a different domain from ACCEPT
and PROOF. They cannot be copied from an old range to an extended range. Endorsers
must have already forced and applied that exact prefix. Evidence records the source
watermark so a future observation cannot validate an earlier endorsement.

Retain every original INTENT and FINAL certificate, including full sealed
`request/prepared/receipt` bytes whose digest is the operation binding. Retiring the
query result does not retire those membership descriptors. No range may conceal a
membership boundary. Checkpoint endorsements at a cut use its **next authority**:
old stable before INTENT, both majorities after INTENT, new stable after FINAL.
This also avoids relying on already departed voters to attest a new stable snapshot.

A consumer walks immutable genesis through linked ranges and explicit boundaries
to the current catalog and application snapshot. The crash-fault assumption is
authenticated exclusive replica identity; these digests are not signatures and do
not provide Byzantine tolerance. An arbitrary local status file is not authority.

Incremental production construction reuses all complete prior items. Re-endorse
only an enlarged trailing stable range; append original membership boundaries and
the next range as needed. If a departing quorum is needed to retain a boundary,
collect its exact already-forced receipt before deleting the source. Unavailable
evidence causes backpressure/refusal, never an invented trust anchor. The finite
reference rebuilds from retained input to make independent checking possible;
it does not claim to implement streaming disk compaction.

For a lifetime bound of M completed/pending changes, there are at most 2M explicit
membership edges and M+1 stable ranges: **3M+1 logical items**. Only the current
catalog is retained in full; historical edges retain bounded sealed descriptors
and catalog hashes, avoiding a catalog copy per generation. Ordinary DATA extends
the last range and does not spend membership/identity/result capacity. Physical
byte caps, frozen sources and old/new generation peaks are specified separately
in the final resource contract; this item bound alone is not a disk-space bound.

Capsule validity does not authorize file deletion. The existing research floor,
forced selector, exact owned unresolved tail, promise/basis and retirement inventory
rules still apply. Keep the old generation until the new complete state and required
floor copies are durable; a missing receipt must not turn into genesis fallback.

## Local evidence

- 17 added regressions cover fixed sources, higher fences, force/crash cuts, late
  callbacks after leader restart, original basis retention, hidden membership,
  lost checkpoint endorsements, stale source watermarks, missing full descriptors,
  result retirement and cancelled identity preservation.
- [Continuity receipt](continuity-research.json): 49 serialized histories replayed,
  252 stable-round publications, 70 successive metadata capsules, 5,504 observed
  extension/endorsement events. Source activation/application events are separately
  replayed and are not included in that event count.
- Output: `target/v53-continuity-research/final/`. Each capsule profile extends
  every cut of one real integrated add/remove/replace trace. These are bounded
  composition examples, not all message interleavings or physical fault tests.

Remaining before Phase 0 closure: exact production APIs/byte catalogs/resource
budgets, numbered later acceptance register, final contract and requirement audit.
