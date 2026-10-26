# Phase 3B — authentic complete historical copies

The later [supplemental ancestry component](PHASE_3_RETAINED_ANCESTRY.md) extends
this boundary to original retained ancestor files. This document and its original
receipt continue to describe the preceding complete-capsule batch.

Status: internal component implementation; local qualification is recorded in the
[source-bound receipt](phase3-evidence/retained-provenance.json). Autonomous adoption,
runtime reopen and the full Phase 3 gate remain open.

## Historical authority and new voting are different operations

The [frozen protocol](MEMBERSHIP_PROTOCOL.md) assumes crash faults and authentic,
exclusive replica identities. A correct replica exports only a previously verified
current generation or its original frozen BASIS source. It cannot invent another
replica's force event. This component lets a receiver verify the complete historical
copy under that assumption without requiring removed former voters to stay online.

This is not Byzantine authentication or a signature scheme. A bare witness hash,
arbitrary packet, generic record download or uncontacted sender still proves no
force. New ACCEPT/PROOF/checkpoint observations retain their original actual-owner
checks. The existing strict `MembershipCapsule.verify` and contextual voting APIs
are unchanged at that boundary; they reject missing `Owned` observations.

`MembershipSourcePull` alone can construct the private `RetainedCopy` capability,
after every packet and indexed application transfer has completed through the exact
authenticated source. The capability checks original ROOT bytes, permanent source,
exact packet and discovered cut or original BASIS binding, physical receiving files,
local owner fence and the original deadline before and after the historical walk.
Partial transfers and generic record pulls cannot produce it. Callers must keep the
receiving owner alive while using the borrowed result; it is not a durable reopening
credential or permission to release the image reservation early.

## Complete validation and exact reuse

The historical walk still validates the complete ROOT-to-current chain, explicit
membership edges, original ENTRY/ACCEPT/PROOF bytes, immutable entry origins, sealed
descriptors, exact witness identities/receipts, both governing majorities, checkpoint
statements and end endorsements, catalog/application state and complete inventory.
No latest-configuration shortcut is introduced.

Already verified historical statements are stored separately from `Owned` values.
A membership certificate is bound to its exact original certificate digest and
parent cut. A checkpoint is bound to its exact statement and ordered endorsement
set. Extensions may reuse those same verified statements while new ones still
require new provenance. Re-proving an entry under another ballot or changing its
endorsements cannot inherit the old statement's authority. Inventory extras not used
by the verified chain do not become historical authority. Retaining one actually
verified certificate through compaction preserves its exact parent and original
phased bytes; no copied tuple is converted into a new voter receipt.

The completed-grant overload likewise authenticates only its complete retained
history. The contacted source's actual original BASIS/tail observations remain
separate and are checked against its real identity, configuration and ballot. This
does not count other historical voters in the new campaign or admit an installation.

## Qualification and remaining integration

Real TCP histories at stable sizes 3/4/5 use public offline bootstrap, actual phased
BARRIER voting/publication and original physical storage snapshots. They retrieve
the complete history without injecting historical observations into the receiving
verifier. Independent replay reconstructs original forces/publication before checking
the exact read-only transcript, receiving bytes and unchanged authority. Normal,
optimized and relocated replay must reject the same thirteen evidence mutations.

Adopted joint/final fixtures separately check a removed reader, exact certificate
and checkpoint reuse, source close, local receive close, fencing, expiration,
modified files, unused inventory records and structurally invalid complete copies.
Their original membership forces remain explicitly conditional fixture inputs; they
do not establish a real distributed member replacement. A well-formed FINAL proof
with only the old majority must fail the new majority check. The first version of
that negative fixture failed at the byte array minimum instead; its failed build is
retained separately from the corrected qualification.

Remaining Phase 3 work includes authenticated supplemental ancestry outside the
capsule's used chain, automatic verified cross-view adoption and fresh elections,
durable reopening without fixture observations, maximal combined image lifetime,
learner/joint completion, generalized voting/publication and complete distributed
S/N mapping. Existing activation/selection components that explicitly inject a
verifier continue to do so. Public automatic membership remains disabled. No
protected CI, cloud execution or release is claimed.

## Rollback

Remove the internal completed-copy overloads and exact historical reuse set, and
restore the exclusively explicit-observation verification path. No public API,
wire kind, persistent format, frozen inventory or resource/timing limit changed.
Preserve original test/source/evidence snapshots as historical qualification.
