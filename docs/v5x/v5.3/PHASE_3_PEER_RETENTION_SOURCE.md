# Phase 3B — original-source retention snapshots

Status: **LOCAL SOURCE CAPTURE COMPONENT QUALIFICATION**. This connects the
[native local retention ledger](PHASE_3_PEER_RETENTION_STORAGE.md) to original
PREPARE/BASIS capture. It does not establish quorum intent, enable dispatch, or
close the [offline-survivor obligation](PHASE_3_SURVIVOR_RETENTION.md).

## Original binding

Before appending a new PROMISE, the exclusive native owner reads its exact active
retention bytes and verifies their root, permanent identity, current configuration
and required original ancestry. The new source contains an immutable wrapper of
those bytes and that original PROMISE. Its SHA-256 and length enter the ordinary
source inventory; CAPSULE commits that inventory and BASIS commits both CAPSULE
and inventory. Receivers read only that source's indexed bytes, never a live file
or optional STATUS hint. A missing snapshot, duplicate matching original, foreign
owner or inconsistent original PROMISE is refused.

The private GSRP wrapper is not a voting record or a new wire message. Its 48-byte
header contains big-endian magic `0x47535250`, major/minor 1/3, zero 32-bit flags,
a 32-bit body length, and SHA-256 of the first sixteen header bytes plus body.
The body is a 32-bit original PROMISE length, exact PROMISE, a 32-bit active GSPR
length, and exact GSPR. Maximum extent is 73,784 bytes: 48 + 8 + 8,192 + 65,536.
The existing per-object, complete packet, inventory and shared journal limits
remain enforced before PROMISE/capture admission. No resource ceiling is enlarged.

Packet objects can include arbitrary application payloads. A matching four-byte
magic prefix alone does not declare a retention wrapper: decoding must succeed,
and the original basisId/root/view/ballot must match. An unrelated malformed object
cannot replace the required valid snapshot or invalidate ordinary application data.
Decoding the copied plan establishes metadata binding only. Its endpoints must
still be checked against authenticated history when selected plans are merged.

## Update and recovery boundaries

A duplicate PREPARE returns the original BASIS and exact source even after a newer
local ledger revision. A fresh ballot captures the newer revision. Local ledger
updates are excluded while an incomplete grant/capture can still depend on those
bytes. An incomplete PROMISE without capture requires a fresh ballot; it cannot
capture a newly altered local plan under the previous grant.

Capture recovery precedes construction of the complete shared-journal store. It
therefore reads the same bounded active ledger under the already-held native lock,
reconstructs the original capture intent and checks its exact prefix. Normal open
subsequently revalidates/reseals the active ledger before any exposed response.
Unexposed `peer-retention.next.gspr` is never selected as a capture source.

Pending contexts may still name an older source envelope. New capture preserves
its indexed objects while adding the fresh wrapper, and rebinds the context to the
actual new capsule. It cannot strip an older wrapper merely because it belongs
to an earlier ballot. Ordinary certified application compaction can omit obsolete
extra objects; the original retained BASIS source stays immutable until its normal
retirement. Repeated elections without publication remain subject to the existing
packet/source limits; this batch does not establish unlimited election progress.

## Qualification and remaining work

Focused Java checks cover original immutability across local updates and reopen,
fresh election capture, certified compaction, incomplete-PROMISE refusal, malformed
conditional source fixtures, and a native pending context whose recapture is
interrupted. The conditional mutation fixtures explicitly construct ownership
assumptions; they are negative component checks, not actual remote grants.

The process matrix uses actual public bootstrap and independent child JVMs at seven
capture boundaries in both halt and SIGKILL modes. Independent Python replay starts
with the original bootstrap and derives the frozen plan, original PROMISE/BASIS,
exact source inventory, complete interrupted/recovered/updated physical maps and
force ordering. Separate Java publication/context histories are not claimed as
complete independent protocol replay by this narrower capture validator.

The [source-bound receipt](phase3-evidence/peer-retention-source.json) retains the
focused Java package, source snapshots, raw crash inventories, nine exact evidence
negatives, normal/optimized Python checks and relocated archive replay. The earlier
15-test snapshot is retained separately; it precedes the additional malformed-data,
inner-root and pending-context checks and is not final-source qualification.

Quorum replication before dispatch, durable merged selection state across source
retirement, authenticated observations, bounded automatic maintenance, cross-view
pending contexts, real learners and the full 3B–3E acceptance remain open. Public
membership remains disabled. This batch changes no workflow, POM, paid runner,
released format catalog or V5.2 experiment.
