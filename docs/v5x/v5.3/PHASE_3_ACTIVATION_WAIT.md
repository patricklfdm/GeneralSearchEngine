# Activation waiting without writer contention

Phase 3 remains **OPEN**. This correction changes idle activation waiting,
not voting rules, selected-source arithmetic, storage formats or request limits.

## Reproduced defect

The driver previously performed full owner/file validation before and after
every 50 ms completion-queue poll, including polls with no completed work. Those
checks acquire the journal monitor also used by incoming source requests.
Consequently a waiter could block behind unrelated storage work before cancelling
an RPC after a higher ballot had already been observed without that monitor.

Two deterministic regressions hold the writer after a pending PREPARE or SELECTED
exchange has entered queue polling, observe a higher ballot, and require the RPC
to be cancelled while the writer remains held. Both fail against the original
implementation. The test releases the writer for cleanup even on failure; it does
not require freeing exports or closing a storage owner without its writer lock.

This mechanism is independently reproduced. It is not by itself proof that it
accounts for the complete PREPARE timeout in the
[retained failed native history](phase3-evidence/corrected-joint-history.json).

## Work boundaries remain fully checked

Idle polling now checks the original deadline, interrupt/close/fatal state and
the live current-view/root ballot fence without taking the journal monitor or
reading files. `checkActivationWait` is solely a cancellation check and does not
authorize protocol work. No state is selected, installed, sent or returned by it.

Launching work and consuming each completion still use full owner, grant, scratch
and retained-source checks. Transfer workers retain their existing checks before
requests and after responses. Selection, every remote installation ACK, local
installation and readiness retain the existing full checks. A regression corrupts
either the original selector or scratch marker while an RPC is held and confirms
that its resumed response cannot force SELECTED or install locally.

The 50 ms poll interval, alternative-peer opportunity, exact request retries,
campaign count, original overall deadline and resource reservations are unchanged.
An idle owner does not continuously scan storage; corruption must be rejected
before subsequent use. It can still be blocked by an actual work-boundary check
or by cleanup that needs the writer. This is not a general nonblocking runtime.

## Validation boundary

The unchanged 3/4/5-node conditional TCP activation tests and the focused driver,
endpoint, scratch and generation suites passed: 58 tests, no failures or skips,
288.052 seconds including compilation. The two new cancellation regressions both
failed against the original runtime. Joining snapshot/ledger readers passed 24
Python tests, and the documentation contract passed. Source/archive hashes and
exact executions are in [the component receipt](phase3-evidence/activation-idle.json).

The native joining fixture now includes node-4 handler/transport events in the
existing optional diagnostic stream. Diagnostic timestamps and JVM profiles do
not replace independent original-byte/force/history replay. The whole early-start
history, default-bound native publication and full seven-profile/process matrix
remain separate final-source qualification requirements.

## Native publication diagnostic after the correction

One shorter native stable run with the unchanged default RPC bounds and optional
transport/JFR recording still failed at the second DATA publication. Execution
including compilation took 134.592 seconds. The first PUBLISH required three
identical requests and delivered its ACK 11.088 seconds after the first send.
The second sent three identical requests, delivered no response, and observed
endpoint-close failures during cleanup at 16.070 seconds. The first publication
issued two reverse CHUNK requests and one commit; the second issued four CHUNK
requests and two commits. These are observed events, not invented timing targets.

The JFR stream records owner-monitor contention and filesystem work, but also
native polling/sleeping carrier and command threads. Its sampling counts cannot
be read as CPU percentages, and the default stack depth/virtual-thread sampling
does not fully attribute receiver work. Recording adds overhead; no claim of a
performance improvement or full timeout root-cause isolation is made. JFR startup
logging caused a separate Surefire native-stream warning; the actual test error
was `membership exchange deadline`.

The [diagnostic receipt](phase3-evidence/native-publication-profile.json) binds
the exact source, original trace, full JFR recording and retained member hashes.
No workload was retried to obtain a green result. Further work must separate
checkpoint collection from repeated integrity checks and preserve force,
ownership, fencing and original-deadline guarantees before changing that path.

## Reuse within one retention validation

`MembershipGrantJournal.checkWithoutFloor` now reads the immutable current
generation's ancestry once for its peer, learner and pending-future checks.
Those consumers only validate bytes under the same serialized journal owner.
The byte array is local to that invocation; it is not retained in the owner,
returned as a capability or reused by a later request. `ancestry()` still checks
the original generation, and the next owner check reads it again. Future-retention
callers outside this combined check continue to obtain their own checked bytes.

This removes duplicate reads, not a protocol stage. Checkpoint statements still
collect original-owner endorsements serially, and selector publication, original
authority checks, journal capacity, request retries and deadlines are unchanged.
Validation results are recorded separately from the earlier profiled failure;
reducing redundant work alone does not establish that the timeout is resolved.

On this implementation, all 23 existing current-generation, learner-retention,
future-retention and publication-ancestry tests passed. The added native-storage
case corrupts ancestry, source, selector and each of the three ledgers after a
successful owner check, requires rejection without a journal write, restores the
bytes and reopens the owner. Its first version wrongly expected a poisoned ledger
handle to recover without reopening; that test expectation was corrected. The
corrected case passed with unchanged resource accounting, including deliberate
continued refusal by each poisoned handle. Nine Python replay/contract tests pass.

The separate default-bound stable TCP round still failed on its second PUBLISH.
Its first PUBLISH delivered after 8.999 seconds; the second issued three identical
requests and was closed at 16.109 seconds without a response. This run did not
enable JFR, so its timing is not an equivalent before/after benchmark. The
[source-bound receipt](phase3-evidence/retention-validation.json) retains both
test executions and the full raw history. No full-history PASS is inferred and
the failed history is not submitted to positive evidence qualification.
