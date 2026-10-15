# V5.2 Phase 6V queued-response observation

**Status:** local controller regressions pass. The second frozen cohort remains
failed; a fresh source/build/machine freeze and complete cohort are required.
Continue under the [local development authorization](LOCAL_DEVELOPMENT_SEQUENCE.md).

## Retained failure

On freeze `cfc32c6`, the first published-V5.1 M01 history dispatched all 1,980
requests over 180.000348 seconds. The common 35.005076-second drain left seven
original responses unobserved. They subsequently returned SUCCESS between 0.111
and 3.054 seconds after that drain; the last business response arrived 38.066434
seconds after dispatch ended. All three consumers exited zero, with no close
errors. The maximum observed client queue delay was 48.211 seconds; the maximum
read API interval was 7.310 seconds. These clocks describe this failed attempt,
not a latency guarantee or a successful formal cohort.

The raw history and FAIL receipts remain unchanged in
`target/v52-formal-measurement/cohort-2/`. Late results cannot retroactively repair
the original observation. No completed members are available to splice or resume.

## Explicit controller revision

Legacy synchronous reads occupy one of eight consumer threads until the API
returns; another 64 requests can be queued before invocation. The former common
35-second drain did not account for this queue. Nine batches at the unchanged
9.6-second operation interval plus the existing 35-second observer margin total
121.4 seconds. The revised M01 drain rounds that allowance to **125 seconds**.
This is a finite operational allowance, not a claim that scheduler stalls,
callbacks or storage must complete within that interval.

There is still one drain deadline for all original futures. It returns as soon
as they complete, preserves every outcome, and never retries or cancels an
uncertain business request. Incomplete observation now reports its missing
response count and actual drain duration. Exceeding the revised bound still
fails the member and stops the cohort.

The 60-second warmup, 120-second measurement, offered rate/count/order, read
targets, eight consumer threads, queue size, API deadlines, three repetitions,
all M02–M04 profiles and physical/query/resource validators are unchanged.
`phase6-program.json` and its hash are unchanged. The new M01 `drainSeconds` is
part of the next machine freeze, so the old frozen contract is rejected for new
execution. Previous histories keep their original Git source and receipts.

## Validation

Two deterministic regressions fail on the former controller: original responses
arriving 38 seconds after dispatch are retained with the complete offered
program; responses still absent at 125 seconds fail after one common wait.
The tests also check that futures are not cancelled and no request is reissued.
All 220 V5.2 Python tests pass. These virtual-clock cases establish controller
behavior only; they do not replace physical measurement or hosted acceptance.

Failure hashes, before/after test logs and validation receipts are retained in
`target/v52-m01-drain/`. No production Java, POM, workflow, published artifact or
paid-cloud behavior changes in this correction.
