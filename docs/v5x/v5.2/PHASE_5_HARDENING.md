# V5.2 Phase 5 combined read hardening

**Status:** locally verified; protected exact-source hosted qualification pending.
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

## Implementation and local results

`verify-v52-phase5-hardening.sh` executes the three complete histories. The driver
uses the existing public consumer and observer unchanged. The common physical
checker now compares each intermediate seven-method report with the independent
query result for the **currently captured** publication. This also checks callbacks
whose original Future was cancelled or whose process died before responding.
The application-overlap negative driver expects this earlier, more specific
rejection; its unchanged six original/relocated inputs still pass all thirteen
negatives each.

The complete first execution passes at `target/v52-read-hardening/development-1`:

| Case | JVM generations | Reads | Confirmed bulk writes | Result |
| --- | ---: | ---: | ---: | --- |
| Partition, retained callback, halt and restart | 4 | 10 | 4 | PASS |
| Partition, retained callback, SIGKILL and restart | 4 | 10 | 4 | PASS |
| Sixteen continuous P=4 pressure rounds | 3 | 102 | 19 | PASS |

The 122 reads comprise 38 successes, 50 original-Future cancellations, sixteen
capacity rejections, sixteen actual deadline expiries and two deliberately lost
responses retained as PENDING. No business call was retried. The initial gate
passes sixteen negatives per case before/after relocation, with fresh published
V4.4 query execution in each location. The final stricter checker passes seventeen
negatives on each of those six unchanged inputs, adding rejection of a borrowed
pre-restart final probe or a reused pressure-round target. This final step is
checker replay, not another workload execution. Every recovered read must also
cover the successor's later token index, and successor floors decode both sources.

The original executions bind base `9792eae` and checkout
`3332f7812bc2cbdfcecd911d82e32feef1df10af8b7601b9264e454418f04e9a`.
The plan was committed before execution at `9792eae`; its SHA-256 is
`29b3ff1b7e6cfbf8f499cad7cc0f3e13f8048d408252ebe17c0cd2a199074059`.
Subsequent checker/CI/result documentation changes do not relabel that binding.
The local JVM is Ubuntu 21.0.12.1. Logs, retained checker replay and validation
hashes are under `target/v52-phase5-entry/`.

## CI integration and remaining boundary

The new required `V5.2 combined read hardening` lane restores the exact shared
build artifact and runs the whole matrix with a twenty-minute job ceiling. It
always retains build provenance and hardening evidence for fourteen days.
Existing suites, fixed matrices, exact-master/attempt consumers and released
artifact requirements are preserved. Full now has 51 expanded jobs; integration
has 48 and still skips only the three canonical repetitions; docs executes two
meta jobs and reports 41 skipped suite placeholders.

The topology audit also corrects stale assertions that still counted only the
first V5.2 lane and treated later V5.2 lanes as independent builds. Earlier failed
checks remain in the local logs. Broad Python discovery initially used the system
3.10 interpreter; existing V5.1 tests require `contextlib.chdir` from Python 3.11.
The final checks use the already installed Python 3.11.15 without changing product
code or weakening those tests.

Final local checks pass: 51 V5.2 Python tests, all 141 CI tests across ten modules,
and 56 toolchain/cloud-preflight/artifact-consumer tests. Generated inventory,
documentation contract, changed local links, shell syntax and whitespace pass.
No runtime Java changed in this batch; the preceding complete reactor/consumer
results remain recorded under Phase 4 rather than claimed as a new execution.

Phase 6 must freeze the measurement plan before M01–M04 execution. This Phase 5
result does not supply measured throughput, a latency SLA, hosted acceptance or
paid-cloud evidence. Protected full CI and fresh manual cloud admission remain
required after the accumulated local work is pushed and merged.
