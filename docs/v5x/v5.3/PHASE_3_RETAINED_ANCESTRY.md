# Phase 3B — retained supplemental ancestry delivery

Status: component implementation and local qualification on the V5.3 branch. The
[source-bound receipt](phase3-evidence/retained-ancestry.json) records exact results. This
extends complete historical capsule verification to the supplemental ancestors
retained by the actual selected generation. Autonomous adoption/elections, durable
reopening and the complete Phase 3 gate remain open.

## Exact source and bounded transfer

A current-cut-derived lookup reference opens a read-only borrow of the selected
GENERATION manifest and, when present, its complete `ancestry.gsr`. The reference is
only an address; it is not a new record, digest attestation or vote. The original
GENERATION/CHECKPOINT/CHECKPOINT_ACK formats and CHUNK/TRANSFER_COMMIT frames are
unchanged. Packet/image and ancestry exchanges have separate trace identities and
share the same existing six-borrow owner limit, bounded registry and original time
budget. The ancestry exporter exposes at most two contents and one lookup alias.

Every read checks the actual source owner, selected generation, file identity and
hash. Generation replacement revokes the borrow; it cannot pin an obsolete
selector. A historical reader need not be a current voter. No PREPARE, observed
ballot update or installation ACK is produced by serving this copy.

The receiver starts with an already verified complete prefix and retains its image
owner through use. The original received manifest must match the source identity,
ROOT, cut, capsule/catalog/application and exact packet length/hash. Only its listed
ancestry file may be downloaded, at the exact length/hash. The existing 64 KiB
manifest, 96 KiB ancestry, six bridge and six-endorsement limits are enforced before
allocation/acceptance. Metadata reservations last until close. Missing ancestry is
an explicit empty inventory and never satisfies a missing required parent.

## Historical proof versus new votes

Only the completed exact manifest/ancestry exchange can mint the internal retained
ancestry capability. The historical walk still checks every original statement and
ACK, root and storage incarnation, exact stable-era endpoints, distinct ordered
voters and governing majority. Statement plus ordered ACK digests form the exact
historical key. No copied ACK becomes an `Owned` observation; direct current-owner
checkpoint acquisition retains its existing separate force-observation path.

Raw ancestry bytes remain untrusted. Replacing a statement or ACK set cannot inherit
another copy's authority. At most the new complete six-bridge set is attached to a
capsule; previously attached supplemental keys are pruned rather than accumulating
through repeated attachments. Packet inventory extras do not become ancestors.

This follows the frozen crash-fault/authentic-exclusive-replica assumption. It does
not add signatures or Byzantine tolerance. The capability is a receiving-lifetime
borrow, not a durable reopening credential, deletion permission or public READY.

## Evidence and remaining scope

Real TCP histories at stable sizes 3/4/5 begin with public offline bootstrap and two
actual phased publications, including a DATA application. The second publication
compacts the first applied cut. One contacted owner supplies both the complete
current prefix and the original retained ancestry; other voters are not queried for
new observations. Independent replay reconstructs original forces, publications,
application state and cleanup before checking exact manifests, files and both wire
transcripts. All authority files remain unchanged by the read-only exchange.

Separate adopted joint/final tests include an old/removed reader. Their original
membership force history remains a conditional fixture, not distributed transition
acceptance. Negative coverage includes mismatched owner/packet, oversize metadata,
torn/duplicate/excess ancestry, endpoint/ACK/quorum errors, original-deadline expiry,
higher local fences, cancellation, bounded transient retries, nonretryable errors
and selector replacement. Portable negative replay first requires valid original
evidence; an unrelated early failure cannot count as rejection success.

Remaining integration includes using these verified ancestors during automatic
cross-view adoption and new elections, handling unavailable required ancestry,
durable local reopening without fixture observations, maximal combined image
lifetime, repeated source maintenance, learners/joint completion, generalized
publication and complete distributed S/N qualification. No public membership API,
protected CI, cloud workload or release is enabled by this component.

## Rollback

Remove the ancestry lookup route, receiving capability and exact historical bridge
reuse, preserving the existing explicit-owner checkpoint path and packet/image
transfer. No persisted format or public API needs migration. Keep original source,
failed attempts and successful physical evidence bound to their own inputs.

## Subsequent local recovery component

[Owned selected-history reopening](PHASE_3_OWNED_GENERATION.md) subsequently restores
the actual local selected manifest, ancestry and publication proofs under its
exclusive journal owner. It is separate from the receiving-lifetime capability
above. Full runtime recovery, cross-view adoption and Phase 3 closure remain open.
