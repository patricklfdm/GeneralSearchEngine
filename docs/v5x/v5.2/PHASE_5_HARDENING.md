# V5.2 Phase 5 combined read hardening

**Status:** plan frozen before execution; implementation and validation pending.
Phase 4 is [locally verified](PHASE_4_QUALIFICATION.md). Continue under the
[local commit authorization](LOCAL_DEVELOPMENT_SEQUENCE.md); no push or paid run.
The machine schedule is [phase5-hardening-plan.json](phase5-hardening-plan.json).
It is correctness qualification, not the later M01–M04 measured workload.

## Two combined partition/restart histories

Start three real public JVMs, confirm three bulks and a strong token, and wait for
actual recovery floors on all three voters. Hold a stale callback on the leader
after its first complete seven-method report. Queue and cancel an ahead minimum
on its original Future; verify actual cancellation and remaining captured ownership.
Partition that leader. The other majority activates, confirms a new bulk and issues
a strong token; observe its actual later recovery floor. Heal until the old voter
forces the successor's higher promise, then isolate it again while the callback
is held. Release it, repeat the complete report at its original cut, and halt or
SIGKILL precisely after view release and before response. Keep that lost response
PENDING, retain pre-reopen files, restart the same authority and require verified
catch-up plus a new read carrying the original token. Compare the recovered result
to the later successor report. No token reconstructs authority and no write retries.

## One continuous bounded-pressure history

Use P=4, R=3 for sixteen cycles in one source/history/process set. Each cycle starts
with zero read ownership and all voters at the preceding confirmed recovery floor.
Pause a captured stale callback after its first seven-method report. Register an
ahead 60-second minimum and a queued stale call, filling all three read slots.
Reject the excess explicit call. Submit one writer using the reserved fourth slot.
Cancel the queued call, then admit a separate 100 ms minimum and observe its actual
expiry while the callback remains held. Cancel the original minimum and captured
Future; the latter still owns its view. Release the callback, verify its repeated
report is unchanged, complete the original write and read its complete publication.
All ownership, timers and permits must return before the next cycle.

The 100 ms request is admitted only after the capacity assertion. Capacity coverage
does not depend on racing a short expiry. Recovery-floor barriers delimit the
controlled rounds; they do not retry or hide a failed business request. These
sixteen cycles are not split across jobs or recombined from separate histories.

## Bounds, evidence and failure rules

Use existing public bootstrap, transport, fault observer, bounded trace writer and
actual resource probes. The three cases retain exact source/tree/artifact/control,
compiled consumer, Java, run/attempt and plan bytes/hash. Keep operation timeout
60 seconds, callback pause 60 seconds, recovery observation 80 seconds and probe
observation 10 seconds. The standalone local gate has a 900-second process bound.
These are controlled test bounds; public wait semantics and production defaults do
not change. No fixed sleep substitutes for an observed transition.

Independent validation requires physical proven/published prefixes, actual chosen
pairs and higher promises, retained restart files, atomic ownership conservation,
original-Future outcomes and query truth from published V4.4. Repeated reports of
cancelled/lost calls must bind to their actual captured cut, not a success invented
after cancellation. All undeclared failed calls reject the case. Preserve failed
receipts and raw inputs. Original evidence must pass before exact-reason negative
mutations; repeat query/physical/negative checks after archive relocation.

A complete case is indivisible. Only the three independent histories could be
parallelized. Partial execution never qualifies the matrix. Finite local hardening
does not establish an unbounded liveness guarantee or replace final protected CI.
The next phase freezes measurements and prepares fresh cloud admission before the
operator performs the combined push/merge and manually starts paid qualification.
