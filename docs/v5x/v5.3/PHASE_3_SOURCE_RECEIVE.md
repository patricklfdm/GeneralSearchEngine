# Phase 3B — complete source scratch ownership

Status: locally qualified. This extends [original source export](PHASE_3_SOURCE_EXPORT.md)
with actual receiving files. The [complete Phase 3B gate](PHASE_3_ENTRY_PLAN.md)
still requires discovery, source protocol orchestration and process recovery.

`MembershipSourceReceive` receives one original packet and its declared application
images into a new caller-owned scratch directory outside the authority inventory.
Its caller must first fetch the exact PROMISE/BASIS from the authenticated source.
The receiver binds those original records to the root, permanent source identity,
session, original basis ID/digest and cut. Each file additionally binds its transfer
ID, kind, exact length and digest. No dummy basis identity or current-state
substitution is allowed. Received bytes do not create an `Owned` observation,
select a generation or justify a voting/installation ACK.

## Files, accounting and completion

- Reserve original records against CONTROL capacity. Reserve a single SOURCE
  packet, then every declared APPLICATION image before accepting application
  bytes. The existing global counts, metadata headroom and shared staging budget
  apply. Six sources cannot silently grow into a second staged set.
- `MembershipReceiveFile` creates only absent files, holds an exclusive inode lock,
  and rejects symlinks, hard links, changed parent identities and replaced inodes.
  It never overwrites an existing file or recursively deletes a directory.
- Reuse the existing stop-and-wait transfer checks: exact binding, bounded chunks,
  exact next offset, identical last-chunk duplicate and complete hash. A malformed
  request cannot advance the file. A duplicate commit does not re-run semantic
  validation, but still checks the original file and deadline.
- Validate physical bytes, packet structure and original BASIS binding before
  forcing the file and its directory. Recheck integrity after semantic validation
  and force. No partial/failed/late file is exposed as verified.
- One original deadline includes construction, all chunks, packet/image creation,
  semantic checks, force and reads. It is not renewed between files. Observed
  expiry permanently fails the receiver; moving a clock backwards cannot revive it.
- Close removes only owned scratch files, forces deletion, then releases their
  reservations. Validation, write and cleanup failures do not silently release
  capacity for files still present. A changed inventory/inode requires restoration
  before cleanup can be retried. If construction cannot establish exclusive inode
  ownership, it fails closed and retains the charged capacity rather than deleting
  an uncertain file; the future runtime must treat that initialization failure as
  fatal to this receive session.

These scratch paths are not added to the frozen authority file inventory. Automatic
restart discovery/discard of abandoned scratch and attachment to the live journal
owner remain required before runtime activation. This component cannot reopen a
partial file as a verified source after restart.

## Qualification boundary

Tests exercise actual public offline bootstrap at stable sizes 3/4/5, original
packet/application bytes, source and shared staging exhaustion, changed files,
malformed bindings, deadlines, semantic/force failures and exact cleanup. A real
TCP test streams the complete packet/images from a live exclusive exporter into
these files, including duplicate delivery. The test supplies the already fetched
source descriptors; it is not discovery or the full SOURCE_OFFER/TRANSFER_COMMIT
state machine.

The independent physical reader reconstructs original bootstrap, grants and retained
source files, then compares the complete received inventory byte-for-byte. It checks
the original before exact negative variants and supports relocated evidence. Its
trace reports `network: false`; TCP integration remains separately evidenced by
the JUnit test. Public runtime, S/N family completion, protected CI, cloud and
performance acceptance are not claimed.

The [local receipt](phase3-evidence/source-receive.json) records 29 final Java tests
(15 receiving cases, seven resource/transfer tests and seven API checks), plus nine
source-export tests on the unchanged export implementation from the preceding
qualification run. All 542 V5.3 Python tests pass in normal and optimized modes.
The final source trace passes ten exact negatives in normal, optimized and
relocated replay. Java inputs in the isolated build were compared with the working
source; the evidence retains both earlier successful runs and failed checks.

One new regression first failed because image retrieval could use a cached packet
after the physical packet was changed. The correction revalidates the packet
before copying images and checks every completed file before returning the group.
The earlier reader also incorrectly compared scratch against the whole current
generation (including its additional promise file); it now compares the exact
retained source inventory reconstructed from the original journal. That failure
and its original evidence remain retained. Neither was retried into a success
without correcting its implementation.
