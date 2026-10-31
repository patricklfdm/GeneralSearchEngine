# Phase 3B — original donor transfer process recovery

Status: the complete local 18-case transfer process matrix passes. The complete
[Phase 3 checklist](PHASE_3_ENTRY_PLAN.md) remains open.

## Original execution boundary

`V53TransferProcessTest` bootstraps one independent original filesystem for each
combination of stable size 3/4/5, reply kind SOURCE_OFFER/CHUNK/TRANSFER_COMMIT and
termination mode halt/SIGKILL. Each case captures one native PROMISE/BASIS and its
complete source, closes the initial owner, then opens that same donor directory
in a new JVM. Node 2 requests the original PROMISE using real TCP and the existing
bounded pull implementation. Other bootstrapped members remain passive.

The donor stops at `BEFORE_RESPONSE_WRITE` for the declared reply. The parent
verifies that the live donor still holds its real exclusive replica lock before
acknowledging the observation. The halt path calls `Runtime.halt(73)`; the kill
path waits for external `destroyForcibly()` and exits 137. Neither path executes
the donor's normal close methods. The interrupted client exhausts the original
three identical requests with IO failures; it does not publish a received record.

A second fresh JVM opens the **same original directory**, identity, PROMISE,
BASIS and retained source, without allocating a new ballot. A new client transfer
with fresh trace/transfer IDs receives the original record, then explicitly stops
the donor. The parent observes exit zero, lock release and zero client resources;
the resumed donor observes zero resources after normal close. Its original
storage bytes are independently compared before death, after death and after
reopen. This is a fresh transfer after the failed pull, not a renewal of its old
deadline or a retry of an expired protocol scope.

| Reply boundary | Attempts per case, including resumed pull | Cases |
| --- | ---: | ---: |
| SOURCE_OFFER | 6 | 6 |
| CHUNK | 7 | 6 |
| TRANSFER_COMMIT | 8 | 6 |

The full matrix contains 18 independent histories, 36 child JVMs, 126 attempts,
18 interrupted replies and 18 original received records. Each scope retains its
existing 60-second protocol budget and three-attempt limit. No workload window,
retry setting, production timeout or frozen parameter changed.

## Physical and process replay

`scripts.v53.transfer_process_evidence` independently derives the bootstrap,
allocator/PROMISE/BASIS, captured source and exported bytes. Complete interrupted
and final replica inventories must equal those original bytes. Worker paths must
equal the paths in the original bootstrap plan; relocation never opens those
recorded paths.

The reader binds distinct parent/child PIDs within each case, exact termination
codes, original worker stdout, recovery force order, live-lock/refusal and
post-death release observations. Instrumentation uses an acknowledged pipe so a
server boundary is retained before its callback returns. It cannot replace any
TCP protocol reply. The cut marker must follow the actual offered response and
precede the client's IO failure. Later retries may fail during connect or after
request write, but cannot contain a server read or a delivered reply.

The expected offer, data and commit bytes come from the original physical
PROMISE. Requests retain root/view/ballot, permanent identities, sequence, original
deadline and exact bytes. The resumed transfer must use distinct trace and
transfer IDs and return the same original record. The reader checks exact matrix,
case and worker inventories, bounded regular inputs and duplicate JSON keys.

Original-first qualification performs 23 evidence mutations. They cover missing
cases, changed interrupted/final storage, substituted records, foreign paths,
PID/exit substitution, missing recovery forces or held locks, premature cut
markers, source substitution, deadlines, retries, falsely delivered replies,
non-IO failures, missing sends, reused scopes, resource leaks and missing original
stdout/stop records. Every mutation must reject with its exact declared reason;
the untouched original is validated first and its inventory must remain unchanged.

```bash
python3 -B -m unittest scripts.v53.test_transfer_process_evidence
python3 -B -m scripts.v53.transfer_process_evidence /path/to/original/matrix --qualify
```

The full native entry is `V53TransferProcessTest`. Its optional
`-Dv53.transfer.process.case=3-SOURCE_OFFER-halt` selector is only a diagnostic:
it emits `completeMatrix=false` and cannot pass the complete-matrix reader.
Any future hosted distribution must keep each interrupted/reopened pair on one
runner with the same filesystem, then require the exact full source/build-bound
matrix. It must not aggregate only successful cases or rerun a measurement.

## Retained result and limits

See [the source-bound receipt](phase3-evidence/transfer-process.json). All 18 cases,
23 evidence negatives and 51 scoped Python tests pass. Source, compiled classes,
JUnit reports, process stdout/stderr, physical snapshots and reader code are
retained in a hash-checked archive; its relocated original is replayed with its
own frozen reader. The first execution exposed a collector error: it called the
cold-only fixture snapshot while the source owner was still open. The collector
now snapshots after closing that owner. The failed source/report and partial
execution remain retained. The successful receipt comes from one new complete
execution, without splicing successes from the failure.

These are actual OS process deaths, not simulated exceptions or power loss.
They qualify one original PROMISE transfer (one data chunk in these executions),
not a multi-content application snapshot, voting/publication during process death,
large-image cancellation, arbitrary partitions, whole-cluster crashes or all seven
membership-change profiles. No public service-ready, complete Phase 3 physical or
network qualification, or frozen S/N-family closure is claimed. Those gates remain
required. This batch changes tests, validation and documentation only; no workflow
or paid cloud operation is added.
