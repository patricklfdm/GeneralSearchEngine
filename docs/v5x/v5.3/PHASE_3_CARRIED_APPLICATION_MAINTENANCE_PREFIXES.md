# Phase 3 — same-history application maintenance captures

Phase 3 remains **OPEN**. This entry observes the actual writer-held files for
campaigns, FLOOR acquisition/release and ordinary generation/source retirement
across an application-ACK crash and recovery. It composes the preceding
[expected-state plans](PHASE_3_CARRIED_APPLICATION_MAINTENANCE_PLANS.md) with the
same original [interrupted application and old-end retirement captures](PHASE_3_CARRIED_APPLICATION_RETIREMENT_PREFIXES.md).
Runtime Java, persisted formats, bounds, deadlines and retry policies are unchanged.

## One original, five captured families

The new process fixture wraps the complete previous two-lifetime history and
its application sidecars. It adds three separate maintenance collections in both
original JVMs; their roots, PIDs, terminal states, event digests and callback
indices bind the same resource observers. It does not join a crash from one
execution to recovery or files from another.

The worker accepts either the existing resource-only application layout or all
three maintenance families together. Partial or extended maintenance arguments,
wrong kind/cut/lifetime and conflicting application capture modes refuse. The
first JVM must still stop at its original ACK-force boundary; the second must
complete the inherited operation and fresh stable barrier and close every owner.

Existing retirement, FLOOR and campaign recorders and schemas remain in use.
The FLOOR reader now recognizes the four explicit local-generation pin callbacks
already emitted by the runtime. Its preceding callback vocabulary rejected those
valid observations. Every such callback must still match the unchanged original
event stream, independent expected transaction and exact file/directory inventory.
The change does not accept an arbitrary `FLOOR_LOCAL_*` family.

## Independent validation and negatives

The complete original application storage/protocol/export/FLOOR/retention/resource
chain passes first, followed by first-lifetime interrupted application files and
second-lifetime old-end retirement files. The maintenance reader then derives
all three families from those same original snapshots, including deferred staged
owners and pinned local generations. It compares actual captured objects with
every original indexed state across both lifetimes.

All 84 existing maintenance-family negative cases remain mandatory: 22 retirement,
27 FLOOR and 35 campaign cases. Five additional physical negatives cover a
substituted pinned selector, missing pinned original image, early pin removal,
leftover pin after release and original-generation deletion during release.
Each negative changes only a temporary sidecar, recomputes ordinary inventory
accounting and must fail for its exact reason after the unmodified history passes.
The complete prerequisite history is preserved. Its separate 29 old-end retirement
and 24 interrupted-application negatives remain mandatory in the development replay.

```bash
python3 -B -m unittest scripts.v53.test_native_carried_application_maintenance_prefixes scripts.v53.test_native_carried_floor_prefixes
python3 -B -m scripts.v53.native_carried_application_maintenance_prefixes ORIGINAL_WRAPPER --qualify
```

Short composition tests use synthetic files and explicitly mocked prerequisite
authority; they are not native history qualification. Actual writer-held evidence
and its portable replay are retained separately with source, toolchain, compiled
classes, original inventories and unretried JUnit records.

## Development execution

One unretried `FINAL/SIGKILL` original completed in 609.424 seconds; the selected
Maven invocation took 647.525 seconds. All 16 selected Java tests passed across
five suites, with no skipped or rerun methods. The three other declared native
axes compiled and remain pending.

The complete relocated maintenance replay admits 457 campaign, 1,077 FLOOR and
597 ordinary retirement snapshots (2,131 total) in the original two lifetimes.
Its 89 exact negative cases pass, including all five pinned-original mutations.
The first process exited 137 at the requested boundary; the recovery process
exited normally. The [evidence index](phase3-evidence/carried-application-maintenance-prefix-development.json)
records the complete 218.796-second portable replay: 142 exact rejections
(89 maintenance, 29 old-end retirement, 24 interrupted application), 32 first-ACK
and 54 old-end prefixes, eight owner lifetimes and all 8,677 original files
(67,206,586 bytes) unchanged.

The producer snapshot identifies baseline `aba2e202` plus three modified and
four new executable/test files. It is development evidence, not an exact-commit
or final-source cohort. Short Python checks cover nine composition tests,
19 tests under optimized Python and 279 related tests; these suites overlap.
The preceding FLOOR vocabulary fails the retained local-pin positive fixture;
the corrected decoder passes it without weakening exact physical comparison.

## Remaining obligations

This composition covers maintenance plus the interrupted application and its
old-end retirement. It does not cover the remaining interrupted vote, normal
application/publication, peer/future ledger or control replay byte families as a
complete application-ACK cohort. Full physical charge composition, simultaneous
resource limits, source-bound admission and final-source hosted execution remain
open. No callback/prefix count substitutes for the complete required histories.

Rollback removes the dedicated composed entry, worker layout support, reader and
plan references together; preserve its original evidence. The exact four-point
FLOOR vocabulary correction can be retained independently. No runtime migration,
workflow topology change or frozen catalogue count change is involved.
