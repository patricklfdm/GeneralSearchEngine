# Phase 3 — interrupted native transition proposer

Status: locally qualified for the exact eight-case same-proposer matrix. Full
Phase 3 remains OPEN.
The preceding [departing restart gate](PHASE_3_DEPARTING_RESTART.md) interrupts
completed acknowledgement delivery. This matrix instead kills the actual proposer
while it publishes INTENT or FINAL, then restarts an independent JVM against the
same original directories and continues the same operation.

## Declared matrix

Start from the actual four-voter admitted REMOVE preparation, sealed at index 4.
The three other voters retain their live native TCP listeners. The parent releases
its original proposer owner, transport and endpoint before starting the child.
The child owns the native journal, activation endpoint, transport and round driver;
no external historical voting observations or caller-selected transition commands
are passed to it.

Eight cases combine INTENT (index 5) or FINAL (index 6),
`PUBLICATION_SELECTOR_FORCED` or `PUBLICATION_BEFORE_RETURN`, and halt or SIGKILL.
SIGKILL requires an exact independent refusal to open the live child's storage.
The original interrupted child must never return READY. A new child reopens the
same directories, performs fresh activation, completes the exact original REMOVE,
and returns internal readiness only after the new-stable BARRIER at index 7.
The test then explicitly closes the child and verifies resource release.

The first diagnostic execution passed and its independent complete physical
projection matched the original snapshots. It selected only `5-PUBLICATION_SELECTOR_FORCED-halt` as a
source-bound diagnostic. The full test defaults to all eight cases. A selective
execution is not the complete matrix. Failed attempts and their raw history remain
retained; a passing retry cannot erase their diagnosis.

## Evidence and limits

Store snapshots are captured at completed selected installation, complete applied
ends and completed slot publication. The child pauses at these test observation
boundaries until the parent has copied all four original stores. This makes the
snapshots consistent; it does not qualify unobserved asynchronous schedules or
power loss. The same 600-second round lifetime and 30-second request timeout as
the existing transition semantic profile remain in effect, with finite original
retry and campaign limits. The default production timeout is unchanged; earlier
default-profile latency failures remain separately documented.

Retain both child logs, original wire records, force events, intermediate and
interrupted stores, original operation descriptors and complete preparation.
Independent original-first physical/history replay must establish fresh ballots,
old and joint majorities, exact operation binding, original force-before-ACK,
selector recovery and the final barrier before this gate is qualified.
A Java result or READY marker alone cannot establish that evidence.

This matrix is same-proposer process recovery for one REMOVE profile. It does not
close alternative-leader takeover, every local write prefix, learner ADD/REPLACE,
all seven profiles, maximum combined headroom, automatic election scheduling,
public APIs or the [whole Phase 3 audit](PHASE_3_ENTRY_PLAN.md).

## Completed source-bound qualification

The immutable full matrix passes eight JUnit tests with no skips, failures or
errors. All eight original interrupted children and eight fresh resumed children
complete their required outcomes; the four SIGKILL cases independently refuse a
concurrent live storage open. Each original and relocated `python -O` replay checks
the exact physical inventories and force-before-ACK/lifecycle ordering, then
rejects eighteen named mutations with exact reasons: 144 unique negative cases,
288 executions across original and portable evidence. Four unchanged prior
transition/departure histories also pass with 44 exact regression negatives.

The full Python suite passes 734 tests. All 1,140 Java/resource/POM
inputs match the immutable JVM build. The archive is inventoried and every file
hash is checked after packing; [the receipt](phase3-evidence/transition-process.json)
records its exact digest, source inputs, outcomes and scope.

The first independent reader assumed remote PUBLISH sequence 1. Actual dispatch
uses the governing voter-union size plus one, following the retention requests;
local completion remains sequence 1. That reader failure, its correction and the
earlier one-profile diagnostic are retained. No original runtime bytes were
rewritten, and the diagnostic is not counted as a ninth matrix profile.

Reproduction: from the archive's `readers/` directory, run
`python3 -O -m scripts.v53.transition_process_evidence ../raw/<profile> --qualify`.
All eight profile names combine index 5/6, PUBLICATION_SELECTOR_FORCED or
PUBLICATION_BEFORE_RETURN, and halt/kill. This controlled observation matrix
does not establish every asynchronous schedule, physical power-loss durability,
restarted transfer delivery, alternate-leader takeover or whole Phase 3 closure.
