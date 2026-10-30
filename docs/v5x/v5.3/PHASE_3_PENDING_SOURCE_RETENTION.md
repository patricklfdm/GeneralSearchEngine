# Retaining the original pending joining source

Phase 3 remains **OPEN**. Before receiving the published JOINT history, the
pending learner must release its one LEARNER receiving category without dropping
or ceasing to account for the original SEALED history. The pending source is
immutable retained history, not another selected voting generation.

## Original marker and bounded accounting

`MembershipLearnerPendingIntent.retainSource()` requires the actual pending
owner and its complete forced ACK. It reserves one of the existing six SOURCE
slots before creating `retained-source.json`. The marker binds the pending plan
and its inode, source directory inode, typed receipt, ACK bytes and inode, and its
own inode. Force the exact marker and its parent before atomically changing the
original metadata lease from LEARNER to SOURCE. No byte, image, metadata or
staging charge is released by that change, and no physical copy is created.

An outstanding source claim prevents another acquisition from stealing its slot
or concurrently selecting the same learner as a generation. Cancellation retains
the original receiving charge; original-owner close revokes the claim. Existing
storage transfer and custody require the claims to have finished. SOURCE stays
at six, GENERATION at two and LEARNER at one; public limits and formats do not
change. The private pending JOURNAL reservation includes 32 KiB for this one
marker within its unchanged 32 MiB bound.

This choice preserves the second GENERATION slot for the existing voter stage.
The current typed image, pending source images, subsequent JOINT receive and
staged voter image all remain independently charged to APPLICATION. Freeing a
category never waives the aggregate staging budget.

## Recovery and capability boundary

Missing ACK or full SOURCE capacity refuses before marker creation, preserving
the pending owner. Failure during marker force or transfer revokes that live
owner and preserves all files. Explicit cold recovery validates the same typed
owner, source inventory, plan and ACK before any force, then completes only the
exact original marker prefix and re-forces it before transferring the receiving
category. A copied complete marker has the wrong inode and is rejected.

The returned private capability stays bound to the live pending owner; parent
close, changed originals or changed marker revoke it. The original checkpoint
listener can still serve its exact forced ACK. Ordinary learner acquisition
remains blocked by pending state. This capability does not install a selector,
create a vote, select JOINT or open public serving.

## Qualification and next integration

Focused qualification uses actual typed preparation, TCP acquisition, original
files and resource reservations; its old voting history is a conditional
fixture. All 29 focused tests passed: 15 resource tests, ten original-marker
cases (including seven injected cut points), and four checkpoint/persistence
regressions. A real TCP pull still obtains the same forced ACK after the source
category transfer; parent close still revokes it. Retained inputs are recorded in the
[component receipt](phase3-evidence/pending-source-retention.json).
Injected IO failures are not halt/SIGKILL qualification.

The next integration must use this private capability for one bounded published
JOINT acquisition, verify its exact pending INTENT and typed receipt, and retain
an explicitly linked full INTENT. Custody must include the pending originals and
all leases before existing placement/native handoff. General pending-state
bypasses or a decoded caller-supplied ACK cannot authorize that transition.
Complete native/process, all-profile and original physical/history replay remain
required; this component alone does not close Phase 3.
