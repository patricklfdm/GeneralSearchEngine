# V5.1 Phase 2B frozen recovery and generation authority

**Status:** accepted in [PR #187](https://github.com/patricklfdm/GeneralSearchEngine/pull/187),
master `eb2b8c0b51d9d3352b037d6435e3aad2839d788d`;
[exact-master CI 35503107173](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35503107173)
passed all six jobs. The documentation-only check and historical canonical receipt
uploads were skipped; V5.1 foundation/storage and inherited runtime gates executed.
**Accepted predecessor:** Batch A, [PR #186](https://github.com/patricklfdm/GeneralSearchEngine/pull/186),
master `284f23d398138d0a747bde42e041da291c68574f`;
[CI 35495493715](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35495493715)
passed all six jobs. The documentation-only step and historical V5.0/V4.4 receipt
uploads were skipped. This batch completes the planned local recovery storage work;
The protected merge and exact-master CI now close Phase 2 acceptance.

## Recovery selection

`AutomaticRecovery` checks the frozen 1.2 records; neither catalog nor fixture bytes
are regenerated. `AutomaticStore` owns the directory lock throughout each operation.
The supported production codec now covers all 25 catalog storage records; decoding
an offline-operation record does not enable the corresponding public operation.

A prepare first validates its prospective snapshot, then forces the root PROMISE,
then forces an immutable IMAGE and BASIS descriptor. The descriptor binds the exact
image checksum, length, complete file inventory, accepted tail and a fresh basis ID.
There is at most one current basis per requesting manifest member. A same-ballot retry
returns the original basis, even if the live accepted tail has changed. If death left
only the promise and an incomplete basis, that ballot cannot resample a replacement;
a higher ballot is required. Chunk reads bind the current ballot, requester, basis ID
and bounded byte range. A later promise invalidates earlier chunk requests.

Selection consumes exactly two complete frozen bases at the requesting ballot,
including its proposer. Proven ancestry must agree. The longest proven prefix wins;
minority acceptances already below that prefix are obsolete. At its next position,
the greatest **acceptance epoch** wins. Origin metadata and ENTRY bytes stay unchanged.
Equal-ballot different values reject. With no unresolved acceptance, the next local
activation value must be a fresh current-ballot NO_OP; this batch does not activate a
leader or publish an application result.

The two basis/image pairs are persisted in alternating `transfer/selection-a|b`
slots. Only after their files and directories are forced is `selected.gsr` published
through an atomic rename and parent-directory force. Restart recomputes the decision
from those exact bases. Changing a selection at the same ballot rejects. Selection
is never interpreted as an ACCEPT receipt: a prior local unproven vote survives until
a new local ACCEPT is forced or a longer proven prefix covers it. A subsequent campaign
can retain that vote through its frozen basis, even when the earlier selection record
has been superseded.

## Generations and transfer

A selected generation contains SNAPSHOT, ACCEPT and PROOF journals, and a GENERATION
seal with the exact initial inventory. Its snapshot retains the complete immutable
origin ancestry, application image, application sequence and terminal quorum proof.
The accepted journal initially carries only the local unresolved acceptance, if any;
a remote acceptance does not become a local vote. Future journal rows retain the
normal local-promise and contiguous-proof checks.

The inactive generation is forced before publishing `current.gsr` through
`current.pending.gsr`. Reopen uses only the complete generation named by that selector.
An unpublished partial stage is not voting authority and can resume only matching
bytes. An existing different complete generation requires floor-authorized retirement.
There is no largest-directory heuristic, truncation of torn required records, or
repair during read-only admission.

`generation-started.gsr` is also published atomically. If death occurred after the
first selector publication but before this marker, the next acceptance/proof forces
the marker before acknowledging. A missing selector with the marker or a durable
floor rejects, instead of reverting to older root logs. Root metadata and the entire
PROMISE journal always remain outside generations. Snapshot adoption cannot decrease
the promise or erase historical grants needed by local acceptance rows.

TRANSFER metadata binds manifest, local node, ballot, ID, total size and image digest.
Chunk bytes are forced before the received watermark is atomically published. Exact
acknowledged retries compare bytes; wrong identities, gaps and overlaps reject.
Unacknowledged bytes beyond the durable watermark may be overwritten on retry; they
never promote themselves to progress. Completion requires the complete matching IMAGE.
The caller still needs a verified selection to install recovery authority.

## Recovery floor and deletion

A local checkpoint alone authorizes no deletion. `recoverySource()` returns a complete
selected generation only after its files, selector and directories have been forced.
A floor requires two distinct admitted voters' complete sources at the same logical
cut and ancestry/application image, including the current local generation. The
receiver retains the full source packets in alternating `transfer/floor-a|b` slots
before publishing `recovery-floor.gsr`. Restart validates both packets, their journals,
selectors, seals and snapshot identities; two digest-only descriptors are insufficient.
These are trusted-voter durability reports, not cryptographic proof of a remote fsync.
Phase 3 must obtain the peer packet through the actual protocol, not invent one.

Cleanup first verifies the durable floor. An inactive generation is copied to a bounded
retirement inventory, then every remaining file must match it before any deletion.
The seal is deleted last. Interrupted deletion resumes against the same retained
inventory. Every retired proof must agree with the active snapshot, and every old
acceptance must be at or below the floor. If an old journal contains a tail above the
floor, this implementation conservatively defers retirement. Root ACCEPT/PROOF logs
are truncated only to their sealed initial headers after the same coverage check;
root PROMISE and identity files are never truncated or deleted.

## Bounds and scope

All owned paths are enumerated and bounded; unknown files, symlinks and unsupported
filesystems reject. Recovery copies, pending files, bases and both staging slots count
toward byte limits. Sealed frame, retained-byte and snapshot-staging limits cannot be
expanded on reopen. Recovery staging uses a conservative aggregate byte bound.
Complete source packets and generation journals are currently limited to 64 MiB per
file; appends enforce that ceiling before accepting bytes that could not be reopened.
The inline accepted tail must also fit the frozen 64 KiB BASIS descriptor, including
space for a future ballot; oversized votes reject before the ACCEPT write.
Schema/JSON object-count bounds may reject an image before its nominal byte ceiling.
Capacity never authorizes deleting an old generation without its recovery floor.

I/O ambiguity quarantines the handle. Recovery-operation rejection also requires a
fresh handle; ledger capacity checks retain their pre-write non-quarantine behavior.
The public automatic factory/bootstrap guards remain disabled. Application images are
opaque caller-supplied projections here: genuine V4 restore/publication verification,
network transfer, timers, election activation and service readiness belong to later
phases. A completely self-consistent rollback of an entire stable disk cannot be
identified from local bytes alone.

## Evidence

The existing `scripts/verify-v51-phase2-storage.sh --skip-build` gate now runs:

- Java codec/root/recovery test receipts from the current reactor build.
- 17 independent Python oracle/force-witness tests.
- The inherited 36 ledger halt/SIGKILL cuts.
- 72 recovery cuts: basis, selected-next, generation files, selector/marker, two-source
  floor, deletion and transfer progress; both owned halt and controller-owned SIGKILL.

Each process case has three concurrently owned storage JVMs. Before product reopen,
the harness archives all voter bytes and runs an independently implemented Python
inspector. It compares logical position, promise, ancestry and retained-byte accounting
with the product. Exact published bytes, process identities and force-before-ACK events
are bound in the evidence. Test workers use production JARs plus test-only controls;
setup certificates are assembled after real store acceptance receipts have returned.

CI always retains `target/v51-storage`, including failures. These are process-crash
witnesses, not power-loss/page-cache simulation or a network-failover qualification.
The [checklist](PHASE_2_CHECKLIST.md) distinguishes local implementation from protected
Phase 2 acceptance.
