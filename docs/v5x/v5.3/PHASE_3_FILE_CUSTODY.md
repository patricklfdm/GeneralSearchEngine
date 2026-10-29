# Preserve OS locks through inspection and force

Phase 3 remains **OPEN**. Review of the learner-to-voter handoff found a real
descriptor-lifetime defect in the preceding source (`99d369f9`). Closing a second
descriptor for a process-locked inode can release its POSIX lock while the first
Java `FileLock` still reports valid. Two independent JVM probes reproduced this
after `MembershipBasisSources.inspect` and typed-preparation fingerprinting.
This was not a workload timeout or a flaky election.

The same mechanism affected nonempty receiving files: hash inspection, semantic
reads, retained-copy checks and later force operations could close another
descriptor. A valid Java handle alone did not establish continued kernel
exclusion. Earlier component receipts retain their original results, but did
not qualify this boundary. The new [component receipt](phase3-evidence/file-custody.json)
retains the original two failures separately from corrected-source results.

## Descriptor custody

`MembershipFileAccess` registers the actual owned inode, channel and lock for
V5.3 authority and receiving files. Ordinary access to that inode borrows the
same channel. Each view has an independent cursor, so reading or forcing cannot
move the receive writer's append position. Closing a borrowed view never closes
or unlocks its owner. Closing the owner revokes its views; closing an old view
cannot affect a later owner of the same inode. Renames preserve the same
registered inode; existing transaction guards still validate paths and parents.

An ordinary unowned descriptor is counted until close. Ownership acquisition
refuses while any such descriptor remains, preventing a later ordinary close
from unlocking a newly acquired owner. Registry operations serialize opening,
ownership acquisition and close; file reads do not hold the registry monitor.
The existing [custody transfer](PHASE_3_OWNERSHIP_TRANSFER.md) preserves this same
registration across wrapper transfer and stale-wrapper close.

All V5.3 regular-file opens use the helper. Shared bounded admission reads and
inventory hashing also use it, so they recognize a V5.3-owned file. Existing
legacy ownership algorithms are unchanged. Directory forcing remains separate;
new-file-only writes cannot open an existing owned inode. The private views
accept only the existing read/write/create options and refuse mapping or new
locks. They are not a general-purpose replacement for `FileChannel`.

This is process-local descriptor coordination, not a new filesystem security
model. It does not protect against arbitrary code bypassing the helper or an
external writer that ignores locks. Original path, inode, single-link, length,
hash and protocol checks remain required. A channel failure still invalidates
its owner. Transfer still requires quiescing old users before the semantic
handoff; already borrowed references do not become new voting capabilities.

## Qualification boundary

Tests attempt the lock from a separate JVM, rather than trusting `isValid()`.
They cover empty lock inspection, typed fingerprints, nonempty receive
verification, inventory hashing, force, retained rename, independent cursors,
ordinary-open/acquisition ordering, owner close, stale close and custody
transfer. Two real learner histories check initial and promoted typed heads,
matching INTENT retention and dormant voter staging. Their historical quorum
fixtures remain conditional; no joined-member vote is claimed.

The final production bytes pass 98 distinct Java tests in two snapshots
(43 and 55 cases, no failures or skips), including source reception/export,
bootstrap and ballot ownership, and V5.0/V5.1 admission paths affected by shared
reads. Bootstrap includes 84 internal interruption positions. One Python contract
test and the documentation/format check also pass. See the receipt for exact
executed snapshots and the separate two-test red run. Public bytes, resource limits,
timing limits and workload parameters are unchanged.

This correction does not implement joined-voter admission or close Phase 3.
The full native/process matrix in [deferred acceptance](PHASE_3_DEFERRED_ACCEPTANCE.md)
must run on the final source. Include actual competing-process ownership probes
around inspection, force, original moves and close in the complete takeover
history; preserve the original failed evidence.
