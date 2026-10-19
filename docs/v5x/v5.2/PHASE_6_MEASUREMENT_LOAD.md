# V5.2 Phase 6E offered-load driver and resource observations

**Status:** locally qualified dispatch/sampling infrastructure. Formal M01–M04
execution and its complete machine-plan freeze remain open. This stage does not
substitute a shorter measured window for the declared 60/120-second windows.

## Dispatch and outcomes

`measurement_load.py` offers each request once at its original monotonic due time.
It does not wait for API completion before offering the next request. A late
controller retains the original due time and reports its lateness; it neither
reschedules the stream relative to completion nor silently drops late requests.
A successful dispatch phase waits through the entire declared window. Completion
observation uses one common drain bound, not a new timeout for every future.

Each offered row retains the exact request, due/offer/submission times, public
operation identity and original response. Independent validation binds those rows
to the public controller ledger and reports every outcome, due-to-response,
offer-to-response, dispatch delay and submission interval. These controller
intervals do not subtract JVM clock readings. Existing physical read validation
separately reports JVM-local API/queue/capture intervals.

A broken transport stops further offers and retains an explicit undispatched
suffix. It does not retry uncertain operations or wait out the remaining offered
window merely to conceal failure. Unobserved futures remain unobserved, without
cancellation or replacement. Such a run cannot pass complete-workload validation.
The driver is bounded to 4,096 offers; the frozen healthy stream contains 1,980.

## JVM observations

Each JVM can start one sampler, take named window markers and stop it. Periodic
samples keep their original one-second due times, including delayed samples. The
start/stop command responses bind the local sampling interval to controller
observations; they do not assert synchronized clocks or an exact global cut.
There are at most 1,024 samples per JVM, including markers and endpoints.

Each sample records its own collection interval, heap/non-heap usage, process CPU,
JVM total allocation counter when available, live/peak thread counts, GC counters,
client executor occupancy, runtime queue/read-permit counters and retained bytes.
Unsupported, disabled or unavailable metrics are explicit states, never zero.
The sampler does not enable allocation monitoring if the JVM disabled it.

CPU/allocation are process-wide and include observer work. Sampled maxima are
labelled as sampled high-water values, not exact peaks or per-call allocation.
Actual read ownership events still supply the independent finite-resource proof.
Candidate samples must include explicit-read counters; the published V5.1 control
may lack those fields. Missing samples, changed due times, regressing cumulative
counters, wrong process identities, fabricated unavailable metrics and missing
candidate counters reject. A sampler failure is surfaced when stopping/closing.

## Local verification

The existing required consumer integration gate now exercises the driver and
sampler in all five modes, using ten offered reads in a labelled **three-second
integration window**, after the original setup query and three updates. This is
an implementation check, not an M01 repetition, throughput comparison or SLA.
No workflow/job identity, suite count, artifact or old verification step changes.

Complete fresh evidence: `target/v52-measurement-runtime/run.MQiDFK/evidence`.
All five modes pass raw and relocated physical/public-query replay: 15 JVMs,
55 reads, 15 confirmed updates and 75 resource samples. Both CPU and allocation
counters were available in this local Ubuntu Java 21 runtime. Each location rejects
57 precise mutations (8/9/13/13/14 by mode), 114 total. Every JVM closes cleanly.
The original binding is base `0b2ad55122fc267b45d3e3036a04dc67c8e2cee4`, checkout
`4e659ef2bf64a3e48eb22b2fd98549bc1db3299f7d135da88982f091f2b167ed`.

Eleven new deterministic driver/sample tests exercise the entire 1,980-request
schedule with a fake clock, unresolved futures, delayed dispatch, transport
failure, explicit rejection and altered/missing observations. All 84 V5.2 Python
tests and 141 CI contract tests pass. Inventory, existing documentation contract,
changed local links, shell syntax and whitespace checks pass. The first CI-test
invocation used unittest discovery on the namespace-only `scripts` directory;
that invocation failed before loading tests. Explicit module loading passes and
both logs remain under `target/v52-measurement-load`.

Only test consumers/observers and validation tools changed. They compile afresh
against the existing verified candidate and published JARs. No new reactor or
hosted-source acceptance is claimed, and no measured or paid execution occurred.

## Next boundary

Provide the separately bounded large-evidence package and streaming measured
validator, complete M02–M04 schedules, then commit the full execution freeze before
running any formal measured history. Preserve every continuous history and its
source/artifact/environment binding through aggregation and portable replay.
Continue under the [local development authorization](LOCAL_DEVELOPMENT_SEQUENCE.md).
