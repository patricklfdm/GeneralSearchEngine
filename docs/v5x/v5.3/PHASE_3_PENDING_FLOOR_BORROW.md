# Phase 3 full joint-floor reacquisition without a seventh SOURCE

Sequential [automatic floor resumption](PHASE_3_AUTOMATIC_FLOOR_RESUME.md) still
needs a receiving SOURCE for each remote prefix. A five-voter REPLACE can require
four governing originals: node-1/node-2/node-5/node-6 satisfy both joint
majorities, but removing any of these four does not. Four retained floor copies
and two real PROMISE sources occupy all six SOURCE slots and seven application
images. If FLOOR authority was interrupted, a redundant receiving copy cannot
fit, even when every original file is already complete.

## Bounded reuse of original bytes

`MembershipFloorFiles.PendingPrefix` is a read-only borrow of complete retained
bytes. It binds the original proposal/reference, exact manifest and member
inventory, original inodes/digests, local generation, permanent identities and
actual resource owner. Closing it does not delete files or release their storage
charges. Journal close, file replacement, proposal completion/replacement or
local generation change invalidates the borrow.

The borrow is **not** a stored remote-force receipt. `MembershipSourcePull` must
obtain a fresh packet offer from the permanent remote owner, compare every chunk
against the retained original and complete the transfer under the original
deadline and fence. It then performs the existing complete generation/ancestry
exchange and exact materialization validation. A changed same-cut generation
still cannot replace the proposal. Merely reading retained bytes cannot produce
a verified prefix or governing copy.

This path creates no receiving SOURCE or image file. Already charged originals
remain owned throughout acquisition and resumption. Unusable retained manifests
or incomplete members cannot be borrowed; the existing full-receive path still
has to authenticate originals and match every retained prefix before writing.
There is no fallback that treats incomplete proposal bytes as force authority.

## Validation scope

`V53PendingFloorBorrowTest` uses real conditional joint-generation stores and
the actual transfer service. Two successive PREPARE operations create the two
real source directories; four original floor copies are forced before an
injected interruption. Reopening observes SOURCE=6 and APPLICATION=7. All three
remote originals are reacquired and the exact floor completes without increasing
those counts. This is an in-process conditional storage/transport component,
not an admitted five-node native transition or a maximum metadata test.

Additional cases cover a missing remote, one lost commit ACK and exhausted commit
replies, original deadline expiry, higher-ballot fencing, altered wire bytes,
closed borrow/owner, same-byte inode replacement, incomplete packet/manifest,
foreign proposal reference and an actual same-cut replacement generation.
Neither failed acquisition nor stored bytes alone may publish FLOOR authority.
The development checks also rerun the admitted 4-REMOVE TCP recovery and its
existing independent storage replay; they do not upgrade that replay to full
remote-force or continuation admission.

See the [development receipt](phase3-evidence/pending-floor-borrow.json) for exact
sources, actual toolchain, test executions and retained intermediate failures.
No resource/time limits, protocol formats, POM, workflow or Required gates change.

## Remaining boundary

A full four-copy proposal with incomplete bodies may still lack a receiving slot;
this change does not implement in-place receiving/ownership transfer for that
state. It must remain safely unavailable until exact recovery is possible.
Admitted 5-REPLACE interruption/recovery, full independent continuation replay,
legitimate controller overlap and maximum metadata occupancy remain open, along
with final-source Phase 3 cohort qualification. The eleven optional hosted
subsets and 512 planned histories are unchanged.
