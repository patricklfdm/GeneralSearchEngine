# Phase 3B — native local retention storage

Status: **LOCAL STORAGE COMPONENT QUALIFICATION**. This private container extends the
[peer endpoint projection](PHASE_3_PEER_RETENTION_PLAN.md). It is local storage,
not quorum intent replication, permission to send, a published API or full Phase 3
acceptance. The [survivor investigation](PHASE_3_SURVIVOR_RETENTION.md) remains open.

## Private format and ownership boundary

Two flat files live under the existing native replica lock: `peer-retention.gspr`
and `peer-retention.next.gspr`. No new frozen record or wire kind is introduced.
This is an explicit private-container addition, like the existing pending-vote and
pending-context containers, not a reinterpretation of a voting frame.

The 44-byte big-endian header is magic `0x47535052` (`GSPR`), unsigned 16-bit major
1 and minor 3, a 32-bit total length and the 32-byte SHA-256 of the body. Each whole
file is at most 65,536 bytes. The canonical JSON body has exactly `root`, `owner`,
`revision`, `previous`, and `plan`. Owner is the full original node/storage/host/port
identity. Revision is 0 through `Long.MAX_VALUE - 1`; only revision zero has a null
previous digest. A candidate must name the exact active file digest and next
revision. The self-contained active file does not claim a retained revision log.

The plan is at most 32,768 canonical bytes: exact root/view and lexically ordered
governing peer identities, each with one or two strictly increasing complete
cut/catalog/application anchors. Decoding validates shape and bytes; original
capsule ancestry and permanent identity verification are separate and mandatory.
Copied or invented JSON is not a peer observation or selected quorum receipt.

Active and candidate bytes count together against the existing 32 MiB JOURNAL
reservation, alongside grants, pending votes, application completion and pending
contexts. Candidate completion is checked before writing. No new MISC reservation,
larger metadata limit, ancestry limit or application-image allowance is introduced.

## Force, recovery and exposure rules

The native journal owns all mutations. Write candidate prefix/full bytes, force the
candidate and parent, atomically replace active, then force the parent again.
Only successful completion returns local durable state. A cut callback, I/O failure
or ownership failure prevents return and requires reopening the failed owner.
The files' inode/length/hash and native lock are rechecked during updates.

An unselected candidate, even a complete one, was never dispatch-visible. Recovery
may discard its exact bounded bytes after validating its framing and predecessor
when complete. This is specific to this pre-exposure intent transaction: it does
not permit discarding an unacknowledged ACCEPT, PROOF, published generation or an
already active dispatch. Cancellation of an unexposed expansion leaves no sent
target; cancellation of a narrowing leaves the older conservative possibilities.
The complete active file is forced again with its parent before recovered use.
Malformed complete candidates, unknown formats, foreign owners, symlinks and
damaged active bytes fail closed and remain present.

`openRetainingPeers` is the required-retention private entry. Initialization is
allowed only from exact unchanged original bootstrap metadata, including the
initial PROMISE, selector, generation, allocator and empty pending vote. A later
local tip or allocator reservation cannot recreate a missing ledger. Existing
component opens remain available for earlier tests; the future automatic owner
must use the required entry consistently. Merely allowing the optional filenames
does not activate this policy for every earlier component history.

## Native use and remaining obligations

Explicit owner methods persist dispatch, complete-copy observation and authenticated
configuration reconciliation. Known endpoints are included in publication capacity,
fresh selected installation and adoption checks. A missing required old bridge is
rejected before installation; it cannot silently disappear in a new election.

This batch still does not replicate an intent to a governing quorum, carry its
immutable bytes in PREPARE/BASIS selection, authenticate remote updates, automatically
schedule observations/consolidation, or solve every cross-view pending-context
case. Actual dispatch must remain disabled until those obligations are integrated.
Local durability alone cannot preserve peer uncertainty after loss of that node.
The all-seven-profile projection evidence remains conditional; learners and joint
completion still require the complete 3C–3E qualification.

## Retained validation

The [source-bound receipt](phase3-evidence/peer-retention-storage.json) separates
the final production-source build, subsequent test-only codec coverage and earlier
failed snapshots. The focused storage suite covers checksum/owner/inode/symlink
rejection, missing-state initialization refusal even before the first publication,
shared-journal exhaustion without file mutation and real native publication.

Fourteen actual fresh-JVM halt/SIGKILL cases interrupt seven update boundaries.
Killed paused children also hold the real storage lock against concurrent opens.
Recovery retains the last selected revision, discards only unexposed candidates,
reseals the active record and permits another update. Independent Python replay
first reconstructs the original public bootstrap, then checks exact active and
candidate bytes, revision/predecessor/identity, interrupted responses and recovery
force order. Eight deliberate evidence changes reach their exact required
rejections; normal, optimized and relocated archive replay agree. These are process
crashes, not simulated power-loss or a quorum replication qualification.

The native Java history explicitly gives all three owners the same genuine
complete-copy observation, completes three publications and two campaigns, rejects
a fresh installation missing that retained bridge without changing files, then
installs with the original proof and continues. This does not simulate automatic
quorum propagation. That history is checked by Java assertions; the new independent
Python replay covers the local retention transactions and original bootstrap,
not every vote/application in this separate native history.

The first implementation incorrectly required no PROMISE at initialization; real
bootstrap already contains its initial PROMISE. A second snapshot incorrectly
reserved MISC a second time. The next snapshot passed all fourteen crash cases but
exposed three incorrect test assertions (ancestry-map key type and two ownership
exception types). Their original logs and source inputs remain retained. None is
relabelled as successful protected CI or a final-source complete runtime gate.
