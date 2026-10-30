# Native joining qualification and retained diagnostics

Phase 3 remains **OPEN**. This increment adds a whole native early-start history
and a strict reader for the actual joining snapshot format. It does not change
runtime algorithms, production timeouts, frozen formats or cloud execution.

## Complete early-start entry

`V53JoiningIntentExportTest#joiningInitializerStartsBeforeOldPreparationAndCompletesNativeHistory`
keeps the existing native bootstrap, typed learner, publication and original
joining directory. The initializer starts before old-majority preparation.
Only an actual TCP CHUNK response for the exact preparation reference with initial
`NOT_READY` releases the old-proposer start. No hint or source is injected into
the initializer and no response is replaced by the test.

Before concurrency begins, capture the original unused joining generation,
capsule and ancestry. After the old majority freezes its sources, independently
calculate the expected initial ledgers from those immutable original inputs.
This avoids racing an unused-owner seed check with the real initializer's writes;
the original sequential history retains that check unchanged. The expected seed
is never passed to initialization as authority. Compare the actually forced
ledgers with it after the initializer returns.

Join the initialization task within the original 12-minute retention lifetime.
Its managed endpoint must become active, the old completion probe must succeed,
and the existing whole continuation must complete FINAL, stable activation,
fresh BARRIER and retaining cold reopen. The 40-minute outer history profile is
unchanged. The early-start marker retains the observed original request/reply;
that marker is an observation, not independent proof of a majority or force.

All Java sources compile and 25 related discovery/endpoint/task tests passed in
36.489 seconds. The original whole native execution from immutable
`joiningearlyhistory-4f644ca2` has now failed after completing early discovery,
remote old-majority retention initialization, endpoint promotion and retaining
cold reopen. The subsequent coordinator requested `scratch/preparation` without
an existing scratch parent and stopped with `parent must already exist`. This
is an implementation defect, not a timeout or an accepted full history. Original
source, raw files and failure reports remain retained.

The correction reuses one OUTGOING scratch scope serially: preparation closes
and drains before normal activation reopens the same original marker/lock. No
arbitrary parent is created and no path, ownership or resource check is relaxed.
A short regression reproduces the old failure; another proves overlap is refused
and drained reuse preserves the marker and journal. All 40 related tests pass.
The corrected whole history, `jointscratchhistory-a0ff0bb8`, completed with failure
after actual native cold reopen. Normal activation exhausted two campaigns while
waiting for node-4's PREPARE response (`membership exchange deadline`). It reached
the ordinary maintenance path; the old scratch-parent error did not recur. The
retained thread sample is one observation of generation/file checks, not proof
of the complete timing cause. Initial-ledger replay and all 13 exact mutations
pass on this run's original substage; they do not turn the failed history into PASS.
See [the scratch correction](phase3-evidence/joint-scratch.json) and
[the completed failed-history receipt](phase3-evidence/corrected-joint-history.json).

## Strict portable snapshot inventory

`scripts.v53.joining_snapshot` reads the `joinedSnapshot` custody-style inventory
emitted by the actual Java history. It checks all 15 declared roots, exact copied
layout, file bytes/hashes, original identity shapes, unique original inode keys,
nonoverlapping original paths and the existing custody extent/count bounds.
Symlinks, hardlinked copied files, unexpected members and noncanonical inventories
are refused. Recorded original paths and parent keys are data and are never
opened; archived copy inodes are not substituted for original identities.

The caller explicitly selects `placed` or `native`: placement must not contain
native-owner/retirement roots, while native snapshots must contain them. The
reader reads one bounded file at a time rather than retaining every image in
memory, and rechecks bytes on later member reads. Its output remains **PARTIAL**:
file presence does not prove forced initialization or replay the protocol.

The final parser tests passed 24 cases including the existing slot snapshot
suite. The first test iteration expected the local canonical-inventory error,
but the shared canonical parser rejected the mutation earlier; the assertion
was corrected to the actual rejection. No accepted malformed input was found.
After verifying all 1,359 files against the retained historical inventory,
replayed the placed/native/continuation snapshots from
`joiningcontinuationnativefinal-95d42274` (80/47/60 members). These are historical
source observations, not acceptance of current runtime code.

## Retained publication timeout

The original default-bound stable round failed again in the dedicated diagnostic
run `rounddeadlineprobe-81e08558` (one test, 141.672 seconds including build).
The existing diagnostic switch records same-JVM monotonic event times separately
from protocol evidence. No request timeout, retry count or round budget changed.

First publication: two client requests, the receiver's first response write
9.676 seconds after its first read, then successful delivery. Second DATA
publication: three identical requests, no response delivered, and endpoint-close
failures 15.895 seconds after the first client write. Between the second
publication's first read and close, the receiver issued four CHUNK requests and
two TRANSFER_COMMIT requests. The original round remains failed; these timings
cannot distinguish disk, scheduling, locking and repeated verification costs.
No claim that the issue is harmless or external is made.

A later [activation idle-wait correction](PHASE_3_ACTIVATION_WAIT.md) removes a
separately reproduced writer-contention/cancellation defect. Its 58 component
checks pass, but a subsequent default-bound stable native run still fails at the
second publication. The original trace and JFR profile are retained in the
[publication diagnostic receipt](phase3-evidence/native-publication-profile.json);
neither this diagnostic nor the earlier failed whole history qualifies Phase 3.

A subsequent [publication owner-check correction](PHASE_3_ACTIVATION_WAIT.md#coalesced-publication-owner-checks)
completed the default-bound stable two-slot history and its independent original
replay, including 35 exact evidence negatives. This result is confined to that
history and source; the longer early-start joining continuation and complete
seven-profile/process qualification are still required.

The original increment's source/archive hashes and focused checks are in
[its historical receipt](phase3-evidence/joining-early-start.json); the later
completed failed history is recorded separately above.
Remaining work includes reviewing this native execution, profiling the timeout
if necessary, integrating complete independent source/force/network replay,
exact negative qualification, all profiles/majorities, process death and the
remaining automatic election/adoption and removed-proposer handoff requirements.
