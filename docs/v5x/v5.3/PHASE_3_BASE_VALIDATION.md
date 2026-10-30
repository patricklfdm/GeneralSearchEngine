# Serialized base validation

Phase 3 remains **OPEN**. This optimization concerns repeated original-file
inspection within one private read-only journal check. It is not a new authority,
network acknowledgement, deadline policy or complete native history gate.

## Scope

`MembershipGrantJournal.checkWithoutFloor()` checks the live allocator, original
journal inode and bytes, source inventory, capture/rotation/retirement state,
pending vote/context, all retention ledgers and application/replay owners before
inspecting generations. Current generation inspection recursively uses the
journal-minted `HistoryRead` capability, which previously checked the same base
originals again.

Only while the current thread holds the journal monitor and is executing the
private read-only traversal may that recursive capability reuse the just-completed
base check. Current and inactive generation inventories, inodes, lengths and
hashes are still inspected. Retention ancestry and required endpoint checks are
unchanged. The marker is restored in `finally`, including every exceptional exit.
Every top-level call performs the complete base check again. Unlocked reads and
constructors get no reuse. No floor write, force, retirement callback, external
guard, network call or application execution occurs inside this scope. Volatile
higher-ballot observation and all fencing checks are unchanged.

## Complete floor plan snapshot

`MembershipFloorFiles` builds its immutable write plan from one defensive snapshot
per complete offered copy. Previously each `fileBytes()` call revalidated every
member, the original selected/grant bindings and ancestry. The new `copyFiles()`
validates the entire copy before and after cloning all members, without callbacks,
I/O or a retained validation marker between these checks. All original force
observations remain mandatory. Individual reads and every subsequent snapshot
still reject changed original bytes; no lifetime cache is introduced. Floor
write/force, original inode checks, handoff, recovery and release are unchanged.

## Validation and limits

The [source-bound receipt](phase3-evidence/base-validation.json) retains all
executions, diagnostics, input hashes and complete original evidence. Thirty-four
focused Java tests passed: 16 owner/generation/fencing checks, then 18 floor
checks on the final implementation. The new cases cover failed validation
followed by journal corruption, unchanged resource ownership, higher-ballot
fencing, defensive floor snapshots and later mutation of every authority class.
Eleven Python checks also pass. Independent fenced-staging replay passed seven
boundaries, eleven exact negatives and relocated replay.

The unchanged-source diagnostic run and the base-only optimization both failed
at the first ACCEPT. The final floor-plan implementation completed BARRIER 8,
including ACCEPT/PROOF/APPLY/PUBLISH and READY, in this execution. It then failed
on DATA 9 ACCEPT after three five-second attempts. Thus **the complete producer
still FAILS**, and this is not a demonstrated general timing fix. The observed
barrier ACCEPT responses took approximately 13.2 seconds from their first send;
this leaves limited margin under the existing finite attempts.

Runner-reported elapsed values were 324.179 seconds for the JFR diagnostic,
285.433 for the base-only history and 324.858 for the final history. These are
single whole executions with different progress, not comparable service latency
benchmarks. JFR sampling is diagnostic only: inclusive stack sample counts overlap
and cannot be interpreted as CPU fractions or wall-clock savings.

Original-first replay of each native run derives the seven preparation slots,
both adoptions and 54 snapshots. The base-only and final runs each reject all
eleven exact evidence mutations. These readers deliberately return PARTIAL and
do not independently qualify BARRIER 8, DATA 9 or post-adoption floor mutations.
The final barrier result is a producer/wire observation, not full-history oracle
acceptance. No failing result is replaced or reclassified as PASS.

Next work must investigate the next-slot maintenance and acceptance path under
the unchanged bounds, complete independent service replay, then cover the other
native profiles and autonomous elections. Large whole-history acceptance remains
eligible for the deferred hosted campaign, without splitting a continuous history.

Rollback removes the read-only marker, routes `HistoryRead.check()` directly
to the full base check, and restores per-member `fileBytes()` in floor planning.
There is no persistent format, source compatibility,
resource limit, POM, workflow or paid-cloud change.
