# Phase 3B — native original pending-context recovery

Status: locally qualified on the development branch. The
[source-bound receipt](phase3-evidence/owned-context.json) retains the original
failures and final verification. This batch does not close Phase 3 or enable
public membership operations.

## Original ownership

A carried pending vote can still belong to an older installed generation after
the current source has advanced. That original includes its own first/latest
publication coverage and supplemental ancestry. Substituting the current copy at
the same application position loses those distinctions; a replay can then reject
the old proof or lose the ancestry needed to settle the pending vote.

The native journal now reconstructs that exact original through either its actual
complete inactive generation or its active forced `pending.context`. The latter
requires the live exclusive journal owner, the exact retained PROMISE/BASIS, the
complete backing source and the exact context inventory. It revalidates ownership,
source bytes, context bytes and reconstructed files before and after verification.
A private, short-lived stored-copy capability is issued only by this path. Raw
packets, candidate-only files and caller-provided historical hashes cannot issue
it. Reconstructing bytes alone provides no voting authority.

The original generation, coverage, application images and ancestry still pass the
complete existing materialization checks. When a newer prefix covers the pending
slot, selection and installation retain the already authenticated bridges while
checking settlement. Verification occurs against the original typed capsule before
projecting it into a different packet, so supplemental historical proofs outside
that packet are preserved. The exact source-history adapter cannot substitute a
different packet, original grant or accepted tail. No copied historical statement
becomes a new vote or installation acknowledgement.

## Qualification design

Eight independent actual public-bootstrap histories cover ACCEPT, PROOF and
CERTIFICATE on a three-voter EMPTY group, plus CERTIFICATE at sizes 3/4/5 using
EMPTY and verified-backup sources. Two original publications precede the pending
entry, ensuring that hidden history is exercised. The tests then install the
carried entry, retire the original generation, advance the majority, rebind the
retained context, settle the covered minority and continue through a fresh barrier.
Final native opens must preserve all original and newly committed documents, the
exact application sequence and zero outstanding owner leases.

The process gate uses an actual three-voter EMPTY CERTIFICATE history. Each of
eleven context installation/cleanup boundaries is interrupted by halt or SIGKILL,
followed by another interruption during recovery and then completion: 22 cases,
66 child JVM executions and eleven exclusive-lock probes. Child inputs contain
only admitted paths; fresh native owners recover historical proof from their own
actual files. These are process failures, not power-loss durability qualification.

The independent Python readers reconstruct original bootstrap, exact grants,
publications, snapshots, source retention and cleanup before inspecting results.
They also independently decode the core backup images and verify document and
application-sequence semantics. Every unmodified history must pass before the
six normal-history and eight process-evidence mutations are tested. Replays must
agree normally, with Python assertions disabled and after unpacking elsewhere.

Earlier original-history failures, intermediate fixture failures and the final
build are retained separately under `target/v53-owned-context/`. A failed overall
build is not relabelled successful merely because some of its tests passed.

## Qualified results

The final isolated build passes all nine selected Java suites together: 58 tests,
zero failures/errors/skips. The eight native histories independently replay 110
node publications and retain at most seven physical application images. The 22
process cases pass all original snapshots, force/death ordering, 66 child exits
and eleven lock probes. All fourteen intended evidence mutations are rejected for
their specific reason, with identical results normally, under `-O` and after
portable unpacking. All 601 V5.3 Python tests pass normally and under `-O`.

The receipt binds the Java/POM and Python inputs, 780 compiled production files,
both built JARs, 43,509 raw evidence files and the nine JUnit reports. The initial
published-history failure was reproduced with all six changed production files
identical to the preceding commit. Fixture corrections and intermediate failures
remain distinct from that reproduced mechanism and the final successful build.
This is focused component qualification, not whole-reactor or protected-CI acceptance.

## Remaining Phase 3 work

These same-view histories still drive votes and campaigns explicitly. Cross-view
pending-context transitions, automatic discovery and election scheduling,
complete native network ownership integration, learner
ADD/REPLACE, old/new joint-majority completion, generalized distributed publication
and the full requirement-by-requirement Phase 3 audit remain open. The S/N matrix
does not become accepted from these component checks.

The batch changes no public factory, persistent format, resource or deadline
limit, POM, workflow, V5.2 Runner, paid experiment or release behavior.
