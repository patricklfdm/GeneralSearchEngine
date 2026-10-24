# Inactive retirement from an exact pinned BASIS image

Phase 2 remains **OPEN**. Extending covered-minority recovery to all admitted
initial profiles reproduced a bounded-maintenance failure: three voters could
complete, but four-voter EMPTY failed with `retirement original image absent from
local floor`. The advanced selector was already installed. A retry could not make
the floor's new image become the old image.

Two generations and two original sources use four image slots; the governing
three-copy floor fills the remaining three slots. The existing
[floor-image borrowing](PHASE_2_RETIREMENT_IMAGES.md) correctly refuses to substitute
a different image. In this case the local floor generation binds an original
BASIS whose immutable source still contains the exact old image. That source is
already reserved and cannot be retired while inactive retirement is pending.

The owner keeps the full physical backup when it fits, and keeps the existing
floor-image representation when every exact old image is available there. Only
when capacity requires borrowing and the floor lacks the old image does it use
that local floor generation's exact original BASIS source. It does not search for
an arbitrary matching file. The source must bind the original BASIS, every image
must match the original deletion inventory's path/name/length/hash, and all images
come from the same pinned source. Missing original bytes still refuse.

The bounded private `gse-v53-retirement-source-images-v1` binding uses the existing
`retirement/images.json` slot and SOURCE metadata allowance. It binds the original
retirement record, floor, root/node/storage, selector, local floor generation,
BASIS digest and exact original image rows. No frozen RETIREMENT bytes, resource
limits, quorum rules or public API change. Actual image bytes remain charged to
the existing source. No extra image, hard link or uncharged copy is created.

Before forcing deletion authority, the owner rechecks and re-forces the original
source packet/images and source directories, then the complete floor. Recovery
reconstructs the exact old generation from saved metadata plus those source
images and repeats the same checks. It does not repair a missing or altered
binding from the old directory. Source/floor mutations stay blocked during the
transaction. The binding is cleared only after the old directory is deleted;
RETIREMENT remains the final authority to clear. Live same-byte inode replacement
must refuse before deletion.

Qualification retains the original four-voter failure and its source manifest.
The six clean admitted profiles (3/4/5 voters × EMPTY/verified backup) cover 24
voters, eight original minority votes and 40 actual node publications. The
five-voter profiles check both minority nodes. Complete original-source, voting,
published-prefix, later floor/source reclamation and BARRIER snapshots are derived
independently; 17 profile evidence mutations preserve exact rejection reasons.

The focused source-image suite additionally checks every existing non-image
retirement boundary, binding writes/forces, source resealing and repeated recovery,
with exact protected bytes and zero closed-owner reservations. Corrupt/missing
bindings, a foreign BASIS, missing source bytes, changed images and live inode
replacement must refuse without repairing authority. Its separate independent
reader derives the admitted floor, source-backed binding and every intermediate
write/deletion state. Final verified counts, hashes and executed checks are in the
[retained evidence index](phase2-evidence/retirement-source-images.json).

The subsequent [source-backed process gate](PHASE_2_RETIREMENT_SOURCE_PROCESS.md)
qualifies these new force boundaries with fresh-process halt/SIGKILL; the preceding
covered-vote process matrix qualifies the earlier transaction. This batch
does not establish maximum byte headroom, power-loss behavior, proof/context-
bearing covered recovery or complete cross-view lifetime. Public membership
runtime, workflows and the V5.2 cloud experiment remain outside this local batch.

The [append-only index correction](phase2-evidence/finalization-log-corrections.json)
records a separate bookkeeping issue in two preceding indexes: each finalizer
hashed its own redirected stdout before printing completion. Only that completion
log changed; all listed qualification logs were checked unchanged. Original
FINALIZED evidence and indexes remain intact. New indexes exclude this post-index
output from validation inputs.
