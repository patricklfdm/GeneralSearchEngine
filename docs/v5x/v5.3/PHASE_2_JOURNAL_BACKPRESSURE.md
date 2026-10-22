# Phase 2 — automatic bounded journal backpressure

Local storage integration; Phase 2 remains **OPEN**. The previously qualified
[exact journal rotation](PHASE_2_JOURNAL_ROTATION.md) is now invoked at an admission
byte ceiling, rather than requiring every caller to invoke it first.

## One maintenance attempt before a new record

PROMISE/BASIS grant admission still reserves both maximum frames before PROMISE.
SELECTED, certificate-derived fence and adoption use their exact encoded record
size. If sufficient room exists, append normally. Otherwise, a rotation-capable
owner may make one exact-frame compaction attempt only when there is no inactive
generation, pending selector, incomplete floor/release or retirement. After that
attempt, recheck available bytes. If still insufficient, return
`CAPACITY_EXCEEDED / NOT_SUBMITTED` for the new operation.

There is no retry loop, automatic source/generation deletion, capacity increase or
resampling of an incomplete grant. Old open modes retain their existing capacity
refusal. Compaction preserves current/floor/source authority and highest promises;
a concurrent higher observation still fences the proposed append after rotation.
A failed rotation invalidates the owner, and reopen finishes its exact pending
transaction before admitting later work. A failed new grant is not automatically
reissued.

The production ceiling remains 32 MiB. A package-private lower-capacity open uses
the same admission and disk transaction to make deterministic exhaustion tests
small; it never changes public configuration, default bounds or reservations.

## Validation and limits

All **184 focused Java tests**, including **eight new admission regressions**,
and **20 build-contract Python tests** (also under `-O`) passed. The
[source/build/hash index](phase2-evidence/journal-backpressure.json) binds the tested
source, JARs and retained logs under `target/v53-journal-backpressure/`.

The targeted regressions cover grant and SELECTED admission, certificate fences,
adopted-prefix installation, no-op when space is sufficient, no reclaimable bytes,
occupied generation refusal, interruption before the journal rename, and a higher
observation during compaction. Lower ceilings and complete promise-only test
frames exercise capacity deterministically; they do not measure a 32 MiB soak.

This batch reuses the qualified rotation transaction rather than introducing new
disk boundaries. Its prior 135-case process matrix remains historical evidence
for that earlier source. Targeted tests validate this source's integration; full
protected/runtime/physical acceptance remains a separate Phase 2–6 obligation.
Original-source retirement and maximal coordinated lifetime progress are still
open; compaction cannot free the six original SOURCE slots.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53*Test,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
```

No public factory, workflow, paid-cloud operation, V5.2 Runner or frozen format is
changed. Local commits only under the continuous-development authorization.
