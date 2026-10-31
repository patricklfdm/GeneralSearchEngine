# Phase 3B — abandoned receiving scratch recovery

Status: locally qualified. This closes a receiving-workspace gap,
not the complete [Phase 3 protocol](PHASE_3_ENTRY_PLAN.md).

## Ownership and restart

Incoming activation and the outgoing driver now open a private derived-work scope
through their actual storage owner and shared resource budget. The scope must be
disjoint from the replica directory and its admitted application materialization.
Its exact ROOT, permanent local identity, incoming/outgoing role, absolute parent
binding and directory inode are recorded in a small canonical owner marker. An
empty persistent lock uses the existing process-local and cross-process exclusion.
The marker is housekeeping metadata outside authority; it is not a protocol record,
vote, installation receipt, selector or permission to retire durable sources.

The runtime caller must reuse one stable incoming path and one stable outgoing path
for a local owner. A clean close drains the component's children, releases its
reservations and leaves only the small marker and empty lock. Arbitrary abandoned
directories, including legacy scratch without this ownership, are not adopted.
An interrupted marker may be completed only when its bytes are the exact prefix of
this owner's expected marker and no received data exists yet.

## Bounded discard

After acquiring the exclusive scope lock, startup validates the complete finite
tree before its first deletion. Outgoing children are `source-<uuid>`; incoming
children are either direct `source-<uuid>` maintenance copies, or one
`selected-<uuid>` containing bounded `source-<index>` directories. Incoming control
work drains one layout before entering the other; a mixed layout is refused.
Each source contains only `source.gscp` and hash-named application images. The
existing six-source/seven-image counts and 32/64 MiB per-file limits still apply.
The scope's control reservation precedes even creating an empty directory. Every
remaining source/image file is charged to the shared budget before deletion begins.
Capacity failure refuses recovery before deleting any staged data.

Each deletion rechecks the root marker, exclusive lock, directory identities,
complete remaining inventory and file inode/length/modification time. Extra files,
links, changed ownership and unexpected paths stop cleanup. Only the enumerated
derived files are removed; each parent's deletion progress is forced. A process
death during cleanup is resumed by rescanning that same scope and charging its
remaining bytes. No partial or fully received file becomes authority on reopen.

Active protocol work continues checking its live scope. Shutdown can release an
empty scope even after protocol ownership has failed; it still cannot remove live
children or substitute another directory. Startup recovery failure prevents that
component from opening. A future autonomous runtime must propagate that failure
and must not evade it by allocating another scratch path.

## Evidence boundary

Unit cases cover normal reuse, active-owner exclusion, extra/linked/oversized
files, foreign root/identity/role/path, capacity refusal, changed files, interrupted
deletion and marker initialization. Actual storage integration rejects overlapping
replica/materialization paths and a separate unshared resource budget.

Process qualification starts from real public bootstrap and an actual retained
PROMISE/BASIS source. Twenty receiving cases cover both roles, both halt and SIGKILL,
and empty, partial-packet, verified-packet, partial-image and complete reception.
Each case dies again at a different cleanup boundary and then recovers in a third
JVM. Independent replay first reconstructs the original source/authority, then
checks exact received byte prefixes, both process cuts, deletion progress, final
inventory and released reservations. Portable replay retains the recorded original
path/inode bindings as evidence; it does not claim to recreate those host inodes.

The final fresh isolated build passes 73 Java tests in eleven suites, including
thirteen scratch unit cases, the twenty-case/sixty-JVM process matrix and a real
killed-receive scope reopened through the actual journal before successful driver
activation. All 570 Python tests pass in normal and optimized modes. Normal,
optimized and portable independent process replay and ten exact evidence negatives
are retained with the related original-first activation/source regressions in the
[local receipt](phase3-evidence/scratch-recovery.json).

An initial integration failure retained an old assertion that the scope directory
must disappear. The assertions now require precisely the persistent marker/lock,
no received children and released resources. A subsequent run exposed an existing
asynchronous fencing assertion: the storage fence may throw before the peer worker
reports its failure. The regression checks the specific higher-promise/fence cause,
one campaign and no SELECTED force for both paths. The earlier failed runs remain
retained; no production fencing order or retry rule was relaxed.

This is actual receiving-component process recovery, not a network partition or
whole-runtime crash test, power-loss qualification, autonomous election or public
READY. The activation TCP regression remains a separate integration check. Full
historical provenance, cross-view adoption, repeated-round source maintenance,
learner/joint transitions, generalized voting/publication and the complete Phase 3
distributed S/N mapping remain open. Frozen protocol formats and limits, V5.2,
workflow and cloud behavior are unchanged.

## Direct incoming maintenance recovery

The historical matrix above covered outgoing direct copies and incoming nested
SELECTED copies. Native `MembershipGenerationMaintenance` also receives original
floor copies at `incoming/source-<uuid>`. The old cold scan refused that actual
layout with `incoming scratch name/count`, preventing an endpoint from reopening
after a process died during maintenance reception. This is a runtime recovery
defect, independent of network delay; a fresh scratch path would evade ownership
rather than repair recovery.

The correction admits precisely those direct incoming source directories under
the original marker, identity, role, path, inode and lock. It reuses the existing
six-source/seven-image bounds, complete inventory validation, shared reservations,
per-deletion rechecks and parent forces. Mixed direct/nested trees, links,
unexpected members and excess counts remain errors before any staged deletion.
Neither a complete nor a partial received copy becomes floor authority on reopen.

The added process matrix explicitly selects `direct-incoming`: both halt and
external SIGKILL at five real receive boundaries, followed by another process
death during cleanup and recovery in a third JVM. Its distinct receipt and
`--direct-incoming` reader mode prevent reinterpreting old histories or falling
back from a failed original. The legacy twenty-case contract remains unchanged.
The independent reader reconstructs the original bootstrap/grant/packet/image
bytes before examining either crash, exact deletion progress and retained owners.

The first extended process run also exposed a test-marker race: the parent saw
the cut file after creation but before its JSON body was complete. The worker now
writes a sibling file and atomically publishes the complete cut before halting
or waiting for SIGKILL. A deterministic visibility check protects this handshake;
no receive/cleanup cut, deadline or production durability operation changes.

A separate integration check kills an actual direct receive at partial image,
opens the same incoming path through `MembershipActivationEndpoint` and the actual
journal owner, and checks that all durable replica files are unchanged. This
qualifies endpoint reopening, not a complete interrupted maintenance transaction,
whole automatic failover, power-loss safety or the full Phase 3 process matrix.
Source-bound results and original failed regressions are retained in
[the direct-recovery receipt](phase3-evidence/incoming-scratch.json).

Validation covers 65 distinct focused Java methods and 13 Python tests. The
first corrected Java run passed 58 of 64 methods: four TCP methods were blocked
by sandbox socket permissions and both process matrices exposed the marker race.
Targeted follow-ups passed all affected methods, the new marker check and the
modified process consumers; the original failures remain retained. This is
combined focused coverage, not a claim of one complete green reactor execution.
The two successful matrices contain 30 cases and 90 fresh JVMs. Original-first
replay and all 21 exact rejection mutations pass in normal and optimized Python;
both wrong-mode attempts reject. The first archive omitted empty directories and
correctly failed bootstrap replay. Its preserved replacement includes every
original directory and passes replay after extraction into another location.
