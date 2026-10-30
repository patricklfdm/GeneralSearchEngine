# Live borrowed-image validation

Phase 3 remains **OPEN**. This change reduces redundant image materialization
while checking a live original. It does not grant authority from a digest, change
resource accounting or extend a transport deadline.

## Physical checks

`MembershipImageBorrow.checkImage()` separates checking an exact original from
returning a byte array. Its default implementation still calls `image()`: a
retained source, including a supplemental older image, keeps its existing full
read and hash checks.

The current-prefix implementation checks the owning journal under its monitor.
That check verifies the current selector, every generation member's bytes,
length and inode, and the original export's lifetime. The requested digest and
extent must also match an application member of that exact generation. Only the
subsequent redundant chunk reads and returned image array are avoided. There is
no cross-call validation cache, and replacing a generation still revokes its
exports instead of pinning obsolete storage.

The receiving implementation checks its original packet, every owned verified
file, its directory inventory and deadline, and recursively checks all borrowed
originals before accepting the requested packet image extent. This preserves
the parent export's lifetime through multiple receiving owners. Calls that need
image bytes still use the unchanged `image()`/`images()` paths.

## Qualification boundary

Focused tests include a valid check followed by changed bytes, an identical-byte
inode replacement, export close, expiry and selector replacement. Changed bytes
are not repaired by checking; restoring them cannot revive a revoked export.
Wrong image hashes/extents remain rejected and closing borrowers releases their
scratch and reservations. Existing supplemental-source and receiver-chain
tests cover the fallback behavior.

The [source-bound receipt](phase3-evidence/image-validation.json) retains all
source snapshots, original files, transport diagnostics and test reports. All
26 focused Java tests and 18 Python tests passed. Independent prefix replay
passed the three stable sizes and 13 evidence negatives. The unchanged native
five-to-four history still **FAILS**, this time during the first BARRIER ACCEPT,
after both adoptions and selected installation. Its three attempts were sent
at approximately 21.9, 27.0 and 32.0 seconds from the first network diagnostic.
The endpoint-closed errors followed exchange expiry and are not the original
failure. Both peers reached floor release but no ACCEPT ACK was delivered.

The native runner recorded 259.453 seconds. The prior implementation's retained
run reached DATA 9, while this run stopped at BARRIER 8. These are single runs
with different progress, not a demonstrated timing improvement or evidence that
environmental variability alone caused the failure. Original-first inspection
still derives seven preparation slots, two adoptions and 54 snapshots, rejecting
all 11 exact negative mutations; it deliberately returns PARTIAL and cannot
accept the subsequent service round. No failed result is replaced by a rerun.

Complete heterogeneous recovery, independent replay of post-adoption service,
the remaining native membership profiles and autonomous elections remain
separate requirements. Prior failed histories remain retained in the
[base-validation receipt](phase3-evidence/base-validation.json).

The next maintenance audit must examine repeated floor/current/base checks at
each original boundary without sharing validation across force callbacks,
deletion or external protocol work. Reduced redundant image materialization
alone has not established native availability under the frozen bounds.

Rollback restores `MembershipSourceReceive.recheck()` to `image()` and removes
the internal `checkImage()` methods. No persistent format, wire kind, quorum,
public API, POM, workflow, measurement parameter or paid-cloud behavior changes.
