# Phase 3B — original source lifetime during asynchronous delivery

Status: locally qualified. This is a source-side prerequisite for
the [open transport/delivery/discovery batch](PHASE_3_ENTRY_PLAN.md); it does not
complete received-file staging, discovery/adoption or distributed activation.

`MembershipGrantJournal.exportSource` borrows one exact forced retained BASIS,
its original PROMISE, complete source packet and all declared application images.
It obtains the existing verified source from the live exclusive writer. The
returned `MembershipSourceExport` exposes only content digests, lengths, kinds and
bounded chunks; a caller cannot supply a filesystem path or replace the source
with the latest grant. A new promise can coexist with the old read-only borrow.
That does not authorize a vote under the old ballot or make an exported digest
an authenticated remote force observation.

## Ownership and cancellation

- At most six export handles exist per writer. Their copied original PROMISE and
  BASIS bytes reserve shared CONTROL capacity. The packet/images borrow existing
  physical SOURCE/APPLICATION reservations; no second physical set is created.
- The deadline starts before original-source verification. Construction and each
  read recheck that same deadline, including after disk validation. Reads cannot
  renew it. Expiration revokes the handle, and a clock rollback cannot revive a
  revoked handle. Protocol orchestration must still pass its remaining original
  request budget and preserve its three-attempt limit.
- The journal serializes chunk reads and source retirement. Each read checks
  whole-owner/file integrity before and after its bounded, no-follow file read.
  A source inode, hard-link count, length or content change prevents return.
- An active export prevents retirement of its exact original source **before**
  any retirement decision or journal pruning is written. That refusal leaves the
  writer usable. Ordinary safe journal rotation preserves the borrowed original.
- Close, expiration and journal shutdown release each control reservation once.
  Expiration is checked on export access/admission and retirement; no background
  timer is needed to unblock reclamation. Closing the owner revokes all handles
  before releasing its physical storage owners. Restart does not resurrect a
  process-local transfer capability.

No new disk format/file, public declaration, frozen limit or remote ACK is added.
The physical source still follows the existing governing-floor retirement rules
after its last active export ends. A transfer handle is not a service lease and
does not make elapsed time a consensus authority.

## Tests and evidence

The new tests cover actual public offline bootstrap at sizes 3/4/5; exact copied
records and file-backed chunks; new promises while reading old sources; six-handle
and global queue exhaustion; deadline expiry during verification; owner close and
reopen; changed files/inodes/hard links; and refusal followed by successful source
retirement. The retirement test also rotates the journal while the export is held.

A separate actual TCP test uses real admitted and installed local owners, real
governing-floor copies and a paused CHUNK request. Retirement is refused while
that reader owns its source, the response contains the original bytes, and
retirement succeeds after the reader's export closes. This is one source-lifetime
integration case, not a complete SOURCE_OFFER/TRANSFER_COMMIT receiver protocol.

The retained three-size physical trace includes original bootstrap, the fresh
grant/source capture, every exported byte/descriptor and unchanged final files.
An independent Python reader reconstructs those files from the original bootstrap
and checks ten reason-specific mutations only after the original passes. Those
raw files intentionally report `network: false`; the separate TCP race's execution
observation is its JUnit test and bound source/build, not this physical trace.

The [local receipt](phase3-evidence/source-export.json) binds 48 focused Java tests
across eight suites (including nine export tests), 539 Python tests in normal and
optimized modes, ten exact evidence negatives and relocated replay. The unchanged
activation evidence also replays against this runtime. These are local checks;
protected CI and the complete Phase 3 gate remain pending.

Still open: complete receiver staging and transfer-session cleanup, bounded source
delivery retries, authority discovery/adoption, failed-source rotation and full
network/fresh-process activation qualification. This component does not close an
S/N family or enable public membership operations.
