# Keep live ownership during evidence snapshots

Phase 3 remains **OPEN**. The original `V53JournalApplicationTest.copy` helper
opened source files with `Files.copy`. On Linux, closing that independent reader
can release the observing process's POSIX lock on the same inode. Java's original
lock object can still appear valid. This was reproduced by a separate JVM: the
lock was unavailable before the snapshot and acquirable immediately afterward.
The red execution is retained; older green histories cannot establish exclusion
at this boundary merely because their Java owner stayed open.

Ordinary files now use `MembershipFileAccess` to borrow an existing owned source
descriptor. Closing the reader leaves its owner and OS lock intact. Destinations
are still newly created independent files; existing evidence cannot be replaced.
The copy is a diagnostic snapshot, not an atomic history or a substitute for
original-path/inode validation.

The test helper preserves its existing content-only handling of symbolic and
hard links. Symbolic links are resolved before borrowing. Deliberately malformed
hard-link evidence is copied in a separate JVM, so closing its reader cannot
release the parent's lock. Production admission still rejects multi-link files;
no production path, resource limit, format, authority or timing rule changes.

The [component receipt](phase3-evidence/evidence-snapshots.json) records the exact
red/final executions and an intermediate test-authoring error: the hard-link
negative initially expected `IllegalArgumentException`, while the actual public
admission failure is `ReplicationException(STORAGE_FAILURE)`. This assertion was
corrected without changing production behavior. Final checks cover repeated
recursive copies, two original process locks, multi-buffer data, destination
independence, overwrite refusal, symbolic/hard-link negatives and the four
existing membership ownership regressions.

The preceding [native joining result](PHASE_3_PUBLISHED_LEARNER_SOURCE.md) remains
source-bound to its own recorded helper. The next continuous joint/FINAL run
must include probes against the actual old-voter roots after snapshots. Full
original-first physical/history replay and process-death/all-profile acceptance
remain in the [deferred queue](PHASE_3_DEFERRED_ACCEPTANCE.md). This small tool
correction does not retroactively upgrade any older qualification.

Rollback restores the old test helper only; original runtime bytes are unchanged.
Any such rollback must also keep snapshot-sensitive ownership acceptance open.
